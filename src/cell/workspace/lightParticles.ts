import type {Playback} from '../em/VolumeStage';
import {boxOf, toWorld, type Vec3} from '../em/emGeometry';
import type {LpCheck} from './useLightPulse';

/** Molecule numbers of a light-pulse run on the display clock, as sent by `light_pulse_particles`. */
export interface LpParticles {
  context: string; sizeUm: Vec3; time: number[]; owner: number[]; frames: number[][]; absent: number[][]; weight: number; seed: number; model: string; passed: boolean; checks: LpCheck[];
  species: {key: string; name: string; where: string; compartment: string; radiusNm: number; capacity: number; weight: number; molecules: number[]; particles: number[]; evidence: string}[];
  fluorescence: number[]; phi: {value: number; unit: string; mapping: string; provenance: {kind: string; note: string}}; evidence: {positions: string; numbers: string};
}
/** Sensor, immature reporter, mature reporter. */
export const PARTICLE_COLORS: Vec3[] = [[0.37, 0.9, 1], [1, 0.72, 0.42], [0.55, 1, 0.6]];
export const PARTICLE_HEX = ['#5ee6ff', '#ffb86b', '#8cff99'];

/** Index of the last display frame at or before time t. */
export function frameAt(times: number[], t: number) {
  let lo = 0, hi = times.length - 1;
  while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (times[mid] <= t + 1e-9) lo = mid; else hi = mid - 1; }
  return lo;
}

/** Display frames in world coordinates. Every frame is an independent snapshot, so no trail is drawn between frames. */
export function buildPlayback(p: LpParticles): Playback {
  const box = boxOf(p.sizeUm), n = p.owner.length;
  const frames = p.frames.map(f => { const w = new Float32Array(f.length); for (let i = 0; i < n; i++) toWorld(f, p.sizeUm, box, w, i * 3, i * 3); return w; });
  const state = p.absent.map(gone => { const st = new Uint8Array(n); gone.forEach(i => { st[i] = 3; }); return st; });
  return {frames, state, pairs: frames.map(() => new Int32Array(0)), owner: Uint8Array.from(p.owner), colors: p.species.map((_, i) => PARTICLE_COLORS[i % PARTICLE_COLORS.length]), index: 0, dirty: true, playing: false, snapshots: true};
}

/** Molecule numbers and particles on screen at one display frame, per species. */
export function countsAt(p: LpParticles, frame: number) {
  return p.species.map((s, i) => ({key: s.key, name: s.name, molecules: s.molecules[frame], particles: s.particles[frame], weight: s.weight, color: PARTICLE_HEX[i % PARTICLE_HEX.length], evidence: s.evidence}));
}
