import {useCallback, useEffect, useRef, useState} from 'react';
import {rpc} from '../../lib/api';
import type {Playback} from '../em/VolumeStage';
import {boxOf, toWorld, type Vec3} from '../em/emGeometry';
import {SPECIES_COLORS, type StructureData} from '../em/molecules';
import {lastAtOrBefore} from './spatial';

export interface Check {name: string; passed: boolean | null; applicable: boolean; threshold: string; detail: string; value?: unknown}
export interface SpeciesResult {name: string; radiusNm: number; particles: number; capacity: number; D: number; home: string; accessible: string[]; target: string | null; msd: number[]; msdFromRelease: boolean;
  boundFraction: number[]; complexFraction: number[]; present: number[]; occupancySeries: Record<string, number[]>; compartmentVolumeUm3: Record<string, number>; encounters: Record<string, number>; crossings: Record<string, number>}
/** One thing that happened at a place and a time: a binding, a separation, a boundary crossing, a synthesis or a decay. */
export interface RunEvent {time: number; frame?: number; kind: 'bind' | 'unbind' | 'cross' | 'born' | 'decay' | 'convert'; a: number; b?: number; species: string[]; position: Vec3; compartment: string}
export interface Chunk {
  id: string; context: string; time: number[]; owner: number[]; frames: number[][]; bound: number[][]; paired: [number, number][][]; absent: number[][] | null; species: SpeciesResult[];
  events: Record<string, number>; pairEvents: RunEvent[]; kinEvents: RunEvent[];
  solver: {dt: number; stepsPerFrame: number; D: number[]; voxelUm: Vec3; geometry: string; kinetics: boolean; crossingProbability: Record<string, number> | null};
  checks: Check[]; passed: boolean; computeSeconds: number; sha256: string; state: unknown;
}
export interface Live {chunk: Chunk; time: number[]; series: {msd: number[]; bound: number[]; complex: number[]; present: number[]; occupancy: Record<string, number[]>}[]}

const KEEP = 720;
const empty = (): Playback => ({frames: [], state: [], pairs: [], owner: new Uint8Array(0), colors: [], index: 0, dirty: true, playing: false});
export const EVENT_COLOR: Record<RunEvent['kind'], Vec3> = {bind: [1, 0.82, 0.3], unbind: [0.62, 0.7, 0.85], cross: [0.45, 0.95, 1], born: [0.55, 1, 0.6], decay: [1, 0.45, 0.42], convert: [0.85, 0.6, 1]};
export const EVENT_LABEL: Record<RunEvent['kind'], string> = {bind: 'bound', unbind: 'separated', cross: 'crossed a boundary', born: 'synthesised', decay: 'decayed', convert: 'converted'};

/**
 * One streamed Brownian-dynamics run: asks the engine for consecutive chunks, keeps the computed frames in world
 * coordinates for the stage, and maps simulated time to frames. Two instances drive a side-by-side comparison.
 */
export function useSpatialRun(sizeUm: Vec3 | null) {
  const playback = useRef<Playback>(empty());
  const run = useRef({token: 0, state: null as unknown, busy: false, dropped: 0, lastUm: [] as number[], frameDt: 0, data: [] as (StructureData | null)[], radii: [] as number[], times: [] as number[], jump: null as RunEvent | null, markerWindow: 0});
  const series = useRef({time: [] as number[], species: [] as Live['series']});
  const [live, setLive] = useState<Live | null>(null), [events, setEvents] = useState<RunEvent[]>([]), [error, setError] = useState(''), [running, setRunning] = useState(false), [fps, setFps] = useState(30), [frames, setFrames] = useState(0);
  const all = useRef<RunEvent[]>([]);

  const stop = useCallback(() => { run.current.token++; run.current.busy = false; setRunning(false); playback.current.playing = false; }, []);
  const reset = useCallback(() => {
    stop(); playback.current = empty();
    series.current = {time: [], species: []}; Object.assign(run.current, {dropped: 0, lastUm: [], frameDt: 0, times: [], state: null, jump: null});
    all.current = []; setEvents([]); setLive(null); setFrames(0); setError('');
  }, [stop]);

  const pump = useCallback(async (token: number, first?: Record<string, unknown>) => {
    const r = run.current, p = playback.current;
    if (r.busy || token !== r.token || !sizeUm) return;
    r.busy = true;
    try {
      const chunk = await rpc<Chunk>('cell_em_simulate', first ?? {state: r.state});
      if (token !== r.token) return;
      r.state = chunk.state;
      const box = boxOf(sizeUm), n = chunk.owner.length;
      if (!p.owner.length) { p.owner = Uint8Array.from(chunk.owner); p.colors = chunk.species.map((_, i) => SPECIES_COLORS[i % SPECIES_COLORS.length]); }
      chunk.frames.forEach((f, k) => {
        const w = new Float32Array(f.length), st = new Uint8Array(n);
        for (let i = 0; i < n; i++) toWorld(f, sizeUm, box, w, i * 3, i * 3);
        chunk.bound[k].forEach(i => { st[i] = 1; });
        const flat = new Int32Array(chunk.paired[k].length * 2);
        chunk.paired[k].forEach(([a, b], j) => { st[a] = 2; st[b] = 2; flat[j * 2] = a; flat[j * 2 + 1] = b; });
        chunk.absent?.[k].forEach(i => { st[i] = 3; });
        p.frames.push(w); p.state.push(st); p.pairs.push(flat);
      });
      r.times.push(...chunk.time);
      r.lastUm = chunk.frames[chunk.frames.length - 1]; r.frameDt = chunk.solver.dt * chunk.solver.stepsPerFrame; r.markerWindow = r.frameDt * 14;
      const fresh = [...chunk.pairEvents, ...(chunk.kinEvents ?? [])].sort((a, b) => a.time - b.time);
      if (fresh.length) { all.current = [...all.current, ...fresh].slice(-1200); setEvents(all.current); }
      const drop = Math.min(p.frames.length - KEEP, p.index - 12);          // keep memory bounded; never drop unplayed frames
      if (drop > 0) { p.frames.splice(0, drop); p.state.splice(0, drop); p.pairs.splice(0, drop); p.index -= drop; r.dropped += drop; }
      const s = series.current;
      s.time.push(...chunk.time);
      chunk.species.forEach((sp, i) => {
        const t = s.species[i] ??= {msd: [], bound: [], complex: [], present: [], occupancy: {}};
        const before = t.msd.length;
        t.msd.push(...sp.msd); t.bound.push(...sp.boundFraction); t.complex.push(...sp.complexFraction); t.present.push(...sp.present);
        for (const key of new Set([...Object.keys(t.occupancy), ...Object.keys(sp.occupancySeries)])) {
          const o = t.occupancy[key] ??= new Array(before).fill(0);
          o.push(...(sp.occupancySeries[key] ?? new Array(sp.msd.length).fill(0)));
        }
      });
      const k = Math.ceil(s.time.length / 600), thin = <T,>(a: T[]) => k > 1 ? a.filter((_, i) => i % k === k - 1) : a.slice();
      setLive({chunk, time: thin(s.time), series: s.species.map(t => ({msd: thin(t.msd), bound: thin(t.bound), complex: thin(t.complex), present: thin(t.present), occupancy: Object.fromEntries(Object.entries(t.occupancy).map(([c, v]) => [c, thin(v)]))}))});
      setFrames(r.dropped + p.frames.length);
      setFps(Math.max(8, Math.min(30, Math.floor(chunk.frames.length / (chunk.computeSeconds + 0.35) * 0.9))));   // never outrun the engine
      p.dirty = true;
    } catch (e: any) { if (token === r.token) { setError(String(e?.message ?? e)); stop(); } }
    finally { r.busy = false; }
  }, [sizeUm?.[0], sizeUm?.[1], sizeUm?.[2], stop]);

  const launch = useCallback((payload: Record<string, unknown>, data: (StructureData | null)[], radii: number[], jump: RunEvent | null = null) => {
    reset();
    const token = run.current.token;
    Object.assign(run.current, {data, radii, jump});
    setRunning(true);
    void pump(token, payload);
    return token;
  }, [reset, pump]);

  /** Simulated time of the frame being shown. */
  const timeNow = () => run.current.times[run.current.dropped + playback.current.index] ?? 0;
  /** Show the last computed frame at or before simulated time t; false when that frame is no longer (or not yet) buffered. */
  const seek = useCallback((t: number) => {
    const r = run.current, p = playback.current;
    if (!p.frames.length) return false;
    const i = Math.max(0, lastAtOrBefore(r.times, t)) - r.dropped;
    if (i < 0) { p.index = 0; p.dirty = true; return false; }
    p.index = Math.min(p.frames.length - 1, i); p.dirty = true;
    return i <= p.frames.length - 1;
  }, []);
  /** Rings for the events of the last few frames, in the playback the stage reads. */
  const mark = useCallback((t: number) => {
    const r = run.current, p = playback.current;
    if (!sizeUm || !r.markerWindow) { p.markers = undefined; return; }
    const box = boxOf(sizeUm), recent = all.current.filter(e => e.time <= t + 1e-9 && t - e.time < r.markerWindow).slice(-80);
    const out = new Float32Array(recent.length * 7);
    recent.forEach((e, k) => { const w = toWorld(e.position, sizeUm, box) as number[], c = EVENT_COLOR[e.kind] ?? [1, 1, 1]; out.set([w[0], w[1], w[2], (t - e.time) / r.markerWindow, c[0], c[1], c[2]], k * 7); });
    p.markers = out; p.dirty = true;
  }, [sizeUm?.[0], sizeUm?.[1], sizeUm?.[2]]);

  useEffect(() => () => { run.current.token++; }, []);
  return {playback, run, series, live, events, error, setError, running, fps, frames, stop, reset, pump, launch, seek, mark, timeNow};
}
export type SpatialRun = ReturnType<typeof useSpatialRun>;
