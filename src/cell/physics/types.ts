/** Shapes returned by the `cell_physics_*` worker actions (scientific/cell_physics.py). */
import type {EvidenceCategory} from '../../lib/engineContract';

export interface InputSpec {key: string; unit: string; description: string; bounds: [number, number]; default: number; integer?: boolean}
export interface Check {name: string; passed: boolean | null; applicable: boolean; value: Record<string, number> | null; threshold: string; detail: string}
export type Vec3 = [number, number, number];

export interface PhysicsCatalog {
  engine: {id: string; name: string; version: string; numericalMethod: string; assumptions: string[]; limits: string[]; validatedDomain: string[]; uncertainty: string;
    solverChoice: {chosen: string; evaluated: string; reason: string}};
  demos: {diffusion: {name: string; inputs: InputSpec[]}; binding: {name: string; inputs: InputSpec[]; sweepDefault: number[]}};
}

interface RecordBase<O> {
  schema: 'fold.research-record'; id: string; kind: string; created: string;
  engine: {id: string; name: string; version: string; numericalMethod: string};
  evidence: {category: EvidenceCategory; name: string; statement: string};
  inputs: Record<string, {value: number | number[] | null; unit: string; description: string; provenance?: {kind: string; note: string}}>;
  solver: Record<string, unknown>; outputs: O; benchmark: {checks?: Check[]; passed: boolean};
  assumptions: string[]; limitations: string[];
  reproducibility: {deterministic: boolean; seed: number; runtime: string; contentSha256: string; note: string};
}

export type DiffusionRecord = RecordBase<{
  time: number[]; timeUnit: 's'; lengthUnit: 'µm';
  free: {msd: number[]; se: number[]; reference: number[]};
  sphere: {msd: number[]; se: number[]; plateau: number};
  sampled: {note: string; free: Vec3[][]; sphere: Vec3[][]};
}>;

export interface Equilibrium {bd: number; se: number; exact: number; exactSd: number; meanField: number; ode: number; occupancy: number; occupancySe: number; odeOccupancy: number;
  seReplicates: number; seTheory: number; window: [number, number]; relaxationRate: number; perReplicate: number[]}

export type BindingRecord = RecordBase<{
  time: number[]; timeUnit: 's'; lengthUnit: 'µm';
  occupancy: {mean: number[]; se: number[]; replicates: number[][]};
  ode: {time: number[]; occupancy: number[]};
  equilibrium: Equilibrium;
  kinetics: {maxDeviationFromOde: number; collinsKimballFactor: number; note: string};
  derived: {reactionVolume: number; lambda: number; pOn: number; pOff: number; volume: number; receptorSpacing: number; konMolar: number; kdMolar: number; K: number};
  events: Record<string, number>;
  sampled: {note: string; track: Vec3[][]; bound: number[][]; receptors: Vec3[]; receptorsBound: number[][]};
}>;

export interface SweepRow {koff: number; tEnd: number; kdMolar: number; bd: number; se: number; exact: number; ode: number; occupancy: number; occupancySe: number; odeOccupancy: number; checks: Check[]; passed: boolean; seed: number}
export type SweepRecord = RecordBase<{rows: SweepRow[]; curve: {koff: number[]; occupancy: number[]}}>;

export interface RunResult<R> {record: R; checks?: Check[]; passed: boolean}
