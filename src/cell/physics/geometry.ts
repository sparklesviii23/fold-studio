/** Pure helpers for drawing computed particle positions: no physics happens here. */
import type {Vec3} from './types';

export interface View {yaw: number; pitch: number; scale: number; cx: number; cy: number}

/** Orthographic camera: rotate about y (yaw) then x (pitch); returns screen x, y and depth (+ towards the viewer). */
export function project([x, y, z]: Vec3, v: View): [number, number, number] {
  const cy = Math.cos(v.yaw), sy = Math.sin(v.yaw), cp = Math.cos(v.pitch), sp = Math.sin(v.pitch);
  const x1 = cy * x + sy * z, z1 = -sy * x + cy * z;
  const y2 = cp * y - sp * z1, z2 = sp * y + cp * z1;
  return [v.cx + x1 * v.scale, v.cy - y2 * v.scale, z2];
}

const NICE = [0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100];
/** Scale-bar length in µm whose on-screen size is closest to `targetPx`. */
export function scaleBar(pxPerMicron: number, targetPx = 110): number {
  return NICE.reduce((a, b) => Math.abs(b * pxPerMicron - targetPx) < Math.abs(a * pxPerMicron - targetPx) ? b : a);
}

/** Linear interpolation of (xs, ys) at x; xs ascending. Values outside the range are null, never extrapolated. */
export function interpolate(xs: number[], ys: number[], x: number): number | null {
  if (!xs.length || x < xs[0] || x > xs[xs.length - 1]) return null;
  let lo = 0, hi = xs.length - 1;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (xs[mid] <= x) lo = mid; else hi = mid; }
  if (xs[hi] === xs[lo]) return ys[lo];
  const f = (x - xs[lo]) / (xs[hi] - xs[lo]);
  return ys[lo] + f * (ys[hi] - ys[lo]);
}

/** Resample a reference curve onto another time grid (null outside its domain). */
export function resample(xs: number[], ys: number[], grid: number[]): (number | null)[] {
  return grid.map(t => interpolate(xs, ys, t));
}

/** Largest distance from the origin over all sampled frames (for framing the view). */
export function extent(tracks: Vec3[][]): number {
  let m = 0;
  for (const tr of tracks) for (const [x, y, z] of tr) m = Math.max(m, Math.hypot(x, y, z));
  return m;
}
