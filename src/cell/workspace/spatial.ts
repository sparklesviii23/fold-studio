/** Pure helpers of the experiment workspace: picking in the class grid, concentration fields, units. */
import {toUm, type Vec3} from '../em/emGeometry';

/** 1 copy per µm³ expressed in nM: 1 / (N_A × 10⁻¹⁵ L) × 10⁹. */
export const NM_PER_COPY_PER_UM3 = 1e9 / (6.02214076e23 * 1e-15);

export interface Grid {dims: Vec3; sizeUm: Vec3; classes: Uint8Array}

export function classAt(g: Grid, um: Vec3): number {
  const i = um.map((v, k) => Math.floor(v / g.sizeUm[k] * g.dims[k]));
  if (i.some((v, k) => v < 0 || v >= g.dims[k])) return 0;
  return g.classes[(i[2] * g.dims[1] + i[1]) * g.dims[0] + i[0]];
}

/**
 * First visible compartment along a ray. `lo`/`hi` bound the kept part of the world box; `visible[c]` says whether class c
 * is drawn. The ray is stepped at half the smallest voxel edge, so a compartment thinner than that can be missed.
 */
export function pickCompartment(ray: {origin: Vec3; direction: Vec3}, box: Vec3, lo: Vec3, hi: Vec3, g: Grid, visible: (c: number) => boolean): {cls: number; um: Vec3} | null {
  let near = 0, far = Infinity;
  for (let i = 0; i < 3; i++) {
    const inv = 1 / ray.direction[i], a = (lo[i] - ray.origin[i]) * inv, b = (hi[i] - ray.origin[i]) * inv;
    near = Math.max(near, Math.min(a, b)); far = Math.min(far, Math.max(a, b));
  }
  if (!(near < far)) return null;
  const step = Math.min(...box.map((b, i) => 2 * b / g.dims[i])) / 2;
  for (let t = near + step * 0.5, n = 0; t < far && n < 6000; t += step, n++) {
    const um = toUm([0, 1, 2].map(i => ray.origin[i] + ray.direction[i] * t) as Vec3, g.sizeUm, box), c = classAt(g, um);
    if (c > 0 && visible(c)) return {cls: c, um};
  }
  return null;
}

/** The molecule nearest to a ray among those within `tolerance` (world units, scaled by distance), or −1. */
export function pickMolecule(ray: {origin: Vec3; direction: Vec3}, frame: Float32Array, state: Uint8Array, tolerance: number): number {
  let best = -1, bestT = Infinity;
  for (let i = 0; i < state.length; i++) {
    if (state[i] === 3) continue;
    const dx = frame[i * 3] - ray.origin[0], dy = frame[i * 3 + 1] - ray.origin[1], dz = frame[i * 3 + 2] - ray.origin[2];
    const t = dx * ray.direction[0] + dy * ray.direction[1] + dz * ray.direction[2];
    if (t <= 0 || t >= bestT) continue;
    const d2 = dx * dx + dy * dy + dz * dz - t * t;
    if (d2 < (tolerance * t) ** 2) { best = i; bestT = t; }
  }
  return best;
}

/**
 * Time-averaged number density of some molecules on a coarse grid, as bytes scaled to the largest bin, with that
 * maximum in copies per µm³. `frames` are world coordinates; `use(i)` selects the molecules.
 */
export function densityField(frames: Float32Array[], states: Uint8Array[], use: (i: number) => boolean, box: Vec3, sizeUm: Vec3, dims: Vec3): {bytes: Uint8Array; maxPerUm3: number; copies: number} {
  const counts = new Float32Array(dims[0] * dims[1] * dims[2]);
  let copies = 0;
  frames.forEach((f, k) => {
    const st = states[k];
    for (let i = 0; i < st.length; i++) {
      if (st[i] === 3 || !use(i)) continue;
      const x = Math.floor((f[i * 3] / box[0] + 1) / 2 * dims[0]), y = Math.floor((f[i * 3 + 1] / box[1] + 1) / 2 * dims[1]), z = Math.floor((f[i * 3 + 2] / box[2] + 1) / 2 * dims[2]);
      if (x < 0 || y < 0 || z < 0 || x >= dims[0] || y >= dims[1] || z >= dims[2]) continue;
      counts[(z * dims[1] + y) * dims[0] + x] += 1; copies++;
    }
  });
  let max = 0;
  for (const c of counts) if (c > max) max = c;
  const bytes = new Uint8Array(counts.length);
  if (max > 0) for (let i = 0; i < counts.length; i++) bytes[i] = Math.round(counts[i] / max * 255);
  const bin = sizeUm[0] / dims[0] * sizeUm[1] / dims[1] * sizeUm[2] / dims[2];
  return {bytes, maxPerUm3: frames.length ? max / frames.length / bin : 0, copies: frames.length ? copies / frames.length : 0};
}

/** Index of the last element of an ascending array that is ≤ t (−1 when none). */
export function lastAtOrBefore(times: ArrayLike<number>, t: number): number {
  let lo = 0, hi = times.length - 1, ans = -1;
  while (lo <= hi) { const mid = (lo + hi) >> 1; if (times[mid] <= t + 1e-12) { ans = mid; lo = mid + 1; } else hi = mid - 1; }
  return ans;
}

/** Simulated time with a unit that keeps three significant figures readable. `unit` is the unit of `t`. */
export function clock(t: number, unit: 's' | 'min'): {value: string; unit: string} {
  if (unit === 'min') return t >= 120 ? {value: (t / 60).toFixed(2), unit: 'h'} : {value: t.toFixed(1), unit: 'min'};
  if (t < 1e-3) return {value: (t * 1e6).toFixed(0), unit: 'µs'};
  if (t < 1) return {value: (t * 1e3).toFixed(1), unit: 'ms'};
  return {value: t.toFixed(2), unit: 's'};
}

export function scaleLabel(um: number) { return um >= 1 ? `${um} µm` : um >= 0.001 ? `${Math.round(um * 1000)} nm` : `${Math.round(um * 1e4)} Å`; }
export const SCALE_BARS = [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20];
