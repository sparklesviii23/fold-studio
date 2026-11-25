/** Geometry shared by the EM volume renderer, picking and the particle overlay. Positions in µm use the dataset's x, y, z. */
export type Vec3 = [number, number, number];
export interface Camera {yaw: number; pitch: number; distance: number; target: Vec3}
export interface Cut {axis: number; at: number}            // axis −1 = no cut, else 0 | 1 | 2   // at: fraction 0–1 along the axis

export const FOCAL = 1.7;

/** Half extents of the world box: the longest edge spans −1…1. */
export function boxOf(sizeUm: Vec3): Vec3 {
  const m = Math.max(...sizeUm);
  return [sizeUm[0] / m, sizeUm[1] / m, sizeUm[2] / m];
}
export function toWorld(um: ArrayLike<number>, sizeUm: Vec3, box: Vec3, out: Float32Array | number[] = [0, 0, 0], offset = 0, from = 0) {
  for (let i = 0; i < 3; i++) out[offset + i] = (um[from + i] / sizeUm[i] * 2 - 1) * box[i];
  return out;
}
export function toUm(world: Vec3, sizeUm: Vec3, box: Vec3): Vec3 {
  return [0, 1, 2].map(i => (world[i] / box[i] + 1) / 2 * sizeUm[i]) as Vec3;
}
export function eye(c: Camera): Vec3 {
  return [c.target[0] + c.distance * Math.cos(c.pitch) * Math.sin(c.yaw), c.target[1] + c.distance * Math.sin(c.pitch), c.target[2] + c.distance * Math.cos(c.pitch) * Math.cos(c.yaw)];
}

/**
 * The kept part of the box. The cut removes the side the camera looks from: `view` is eye − target, so the choice
 * does not flip when the camera dives below the cut face. `face` is the world coordinate of the cut.
 */
export function cutBounds(cut: Cut, box: Vec3, view: Vec3): {lo: Vec3; hi: Vec3; face: number} {
  const lo: Vec3 = [-box[0], -box[1], -box[2]], hi: Vec3 = [box[0], box[1], box[2]];
  if (cut.axis < 0) return {lo, hi, face: 0};
  const face = (cut.at * 2 - 1) * box[cut.axis];
  if (view[cut.axis] >= 0) hi[cut.axis] = face; else lo[cut.axis] = face;
  return {lo, hi, face};
}
export const viewOf = (c: Camera): Vec3 => { const e = eye(c); return [e[0] - c.target[0], e[1] - c.target[1], e[2] - c.target[2]]; };

const sub = (a: Vec3, b: Vec3): Vec3 => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const cross = (a: Vec3, b: Vec3): Vec3 => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const norm = (a: Vec3): Vec3 => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };

/** Ray through a screen point (u, v in −aspect…aspect, −1…1), matching the fragment shader. */
export function ray(camera: Camera, u: number, v: number): {origin: Vec3; direction: Vec3} {
  const origin = eye(camera), fw = norm(sub(camera.target, origin)), rt = norm(cross(fw, [0, 1, 0])), up = cross(rt, fw);
  return {origin, direction: norm([0, 1, 2].map(i => fw[i] * FOCAL + u * rt[i] + v * up[i]) as Vec3)};
}

/** Where a ray enters the kept box, and whether that entry lies on the cut face. Null when it misses. */
export function enter(origin: Vec3, direction: Vec3, cut: Cut, box: Vec3, view: Vec3 = origin): {point: Vec3; onFace: boolean} | null {
  const {lo, hi, face} = cutBounds(cut, box, view);
  let near = 0, far = Infinity, axis = -1;
  for (let i = 0; i < 3; i++) {
    const inv = 1 / direction[i], a = (lo[i] - origin[i]) * inv, b = (hi[i] - origin[i]) * inv, n = Math.min(a, b), f = Math.max(a, b);
    if (n > near) { near = n; axis = i; }
    far = Math.min(far, f);
  }
  if (!(near < far)) return null;
  const point = [0, 1, 2].map(i => origin[i] + direction[i] * near) as Vec3;
  return {point, onFace: cut.axis >= 0 && axis === cut.axis && Math.abs(point[cut.axis] - face) < 1e-6};
}

/** Sphere-equivalent hydrodynamic radius (nm) from atom coordinates in Å: R = √(5/3)·Rg. A rough estimate for a compact particle. */
export function estimateRadiusNm(atoms: {xyz: [number, number, number]}[]): number | null {
  if (atoms.length < 20) return null;
  const c = [0, 0, 0];
  for (const a of atoms) for (let i = 0; i < 3; i++) c[i] += a.xyz[i] / atoms.length;
  let s = 0;
  for (const a of atoms) for (let i = 0; i < 3; i++) s += (a.xyz[i] - c[i]) ** 2;
  return Math.sqrt(5 / 3 * s / atoms.length) / 10;
}

/** A fixed, well-spread unit quaternion (x, y, z, w) for molecule `i`. Tumbling is not simulated; this only varies the pose between copies. */
export function orientation(i: number): [number, number, number, number] {
  const h = (k: number) => { let x = Math.imul(i * 3 + k + 1, 0x9e3779b1) >>> 0; x ^= x >>> 15; x = Math.imul(x, 0x85ebca6b) >>> 0; x ^= x >>> 13; return (x >>> 0) / 4294967296; };
  const u = h(0), v = h(1) * 2 * Math.PI, w = h(2) * 2 * Math.PI;      // Shoemake's uniform random rotation
  return [Math.sqrt(1 - u) * Math.sin(v), Math.sqrt(1 - u) * Math.cos(v), Math.sqrt(u) * Math.sin(w), Math.sqrt(u) * Math.cos(w)];
}
