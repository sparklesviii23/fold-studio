/** What the user sets up for a spatial run, and how it becomes an engine request. */
import type {Vec3} from '../em/emGeometry';
import type {StructureData} from '../em/molecules';

export interface ClassInfo {id: number; key: string; name: string; color: string; voxels?: number; volumeUm3?: number}
export interface InputSpec {key: string; unit: string; description: string; bounds: [number, number]; default: number; integer?: boolean}
export interface ContextInfo {id: string; name: string; short: string; species: string; cell: string; geometry: 'measured' | 'illustrative'; geometryLabel: string; resolution: string; installed: boolean; hasImage: boolean; painting: boolean;
  meta: {dims: Vec3; voxelUm: Vec3; sizeUm: Vec3; classes: ClassInfo[]; illustrative?: boolean} | null; defaults: {slowdown: {value: number; provenance: {kind: string; note: string}}}}
export interface Region {id: string; level: string; dims: Vec3; voxelUm: Vec3; originUm: Vec3; sizeUm: Vec3; blocks: number; bytes: number; sha256: string}
export interface Catalog {
  engine: {name: string; version: string; numericalMethod: string; equations: string[]; assumptions: string[]; limits: string[]; benchmarks: {name: string; reference: string; acceptance: string}[]};
  dataset: {id: string; name: string; cellLine: string; method: string; url: string; licence: string; acquired: string; installedLevel: string; downloadMb: number; citation: string[]; caveats: string[]};
  installed: boolean; outdated: boolean; contexts: ContextInfo[]; regions: Region[]; regionLevels: {id: string; voxelNm: Vec3}[];
  inputs: InputSpec[]; speciesInputs: InputSpec[]; pairInputs: InputSpec[]; kineticInputs: InputSpec[]; exchangeInput: InputSpec; reactionInput: InputSpec;
  molecules: {id: string; name: string; radiusNm: number; note: string}[]; classes: ClassInfo[];
  limits: {species: number; particles: number}; painting: Record<string, {stain: string; color: string; weights: Record<string, number>}>;
}
export type Release = {compartment: string} | {point: Vec3};
export interface Species {key: number; name: string; source: string; radiusNm: string; particles: string; release: Release; nuclear: boolean; target: string; pBind: string; koff: string; data: StructureData | null; asset?: string; sha256?: string; note: string; busy?: boolean;
  capacity: string; synthesisRate: string; synthesisIn: string; decay: string; exchangeThrough: string; exchangeTo: string; permeability: string}
export interface Pair {a: number; b: number; on: boolean; reachNm: string; rate: string; koff: string}
export interface Conversion {from: number; to: number; rate: string}

let nextKey = 1;
export const newKey = () => nextKey++;

export function freshSpecies(c: Catalog, source: string, name: string, radius: number, data: StructureData | null, note: string): Species {
  const d = Object.fromEntries(c.speciesInputs.map(s => [s.key, String(s.default)]));
  return {key: newKey(), name, source, radiusNm: radius.toFixed(2), particles: d.particles, release: {compartment: 'cytosol'}, nuclear: false, target: '', pBind: '0.2', koff: d.koff, data, note,
    capacity: '', synthesisRate: '0', synthesisIn: 'cytosol', decay: '0', exchangeThrough: '', exchangeTo: '', permeability: String(c.exchangeInput.default)};
}

/** The engine request for a run. Kinetic keys are sent only when used, so a plain run stays a plain run. */
export function payload(context: string, sp: Species[], pr: Pair[], cv: Conversion[], g: Record<string, string>, label: string, parent: string | null) {
  return {...Object.fromEntries(Object.entries(g).map(([k, v]) => [k, Number(v)])), context, frameSeconds: 0.004, label, parent,
    species: sp.map(s => {
      const syn = Number(s.synthesisRate) > 0, cap = Number(s.capacity) || 0;
      return {name: s.name, structure: s.asset ?? null, structureSha256: s.sha256 ?? null, structureName: s.asset ? s.name : null, radiusNm: Number(s.radiusNm), particles: Number(s.particles), release: s.release,
        nuclearExchange: s.nuclear, target: s.target || null, pBind: s.target ? Number(s.pBind) : 0, koff: Number(s.koff),
        ...(cap > Number(s.particles) || syn ? {capacity: Math.max(cap, Number(s.particles) + (syn && !cap ? 60 : 0))} : {}),
        ...(syn ? {synthesis: {rate: Number(s.synthesisRate), compartment: s.synthesisIn}} : {}), ...(Number(s.decay) > 0 ? {decay: Number(s.decay)} : {}),
        ...(s.exchangeThrough && s.exchangeTo ? {exchange: [{through: s.exchangeThrough, to: s.exchangeTo, permeabilityUmS: Number(s.permeability)}]} : {})};
    }),
    pairs: pr.filter(p => p.on && p.a < sp.length && p.b < sp.length).map(p => ({a: p.a, b: p.b, reachNm: Number(p.reachNm), rate: Number(p.rate), koff: Number(p.koff)})),
    reactions: cv.filter(c => c.from < sp.length && c.to < sp.length && c.from !== c.to).map(c => ({from: c.from, to: c.to, rate: Number(c.rate)}))};
}

/** Rebuild the setup from a saved configuration (the inverse of `payload`). */
export function fromConfig(cfg: any, loaded: ({data: StructureData; note: string; sha256: string} | null)[]): {species: Species[]; pairs: Pair[]; conversions: Conversion[]} {
  const species: Species[] = cfg.species.map((c: any, i: number) => ({key: newKey(), name: c.name, source: loaded[i] ? 'asset:' + c.structure : 'custom', radiusNm: String(c.radiusNm), particles: String(c.particles), release: c.release, nuclear: c.nuclearExchange,
    target: c.target ?? '', pBind: String(c.pBind), koff: String(c.koff), data: loaded[i]?.data ?? null, asset: c.structure ?? undefined, sha256: c.structureSha256 ?? undefined,
    note: loaded[i] ? (loaded[i]!.sha256 === c.structureSha256 || !c.structureSha256 ? loaded[i]!.note : 'The library file has changed since this run (different SHA-256); the run is replayed with its recorded size.') : c.structure ? 'The saved structure is no longer in this project; replayed as a sphere of its recorded radius.' : 'Size preset.',
    capacity: c.capacity > c.particles ? String(c.capacity) : '', synthesisRate: String(c.synthesis?.rate ?? 0), synthesisIn: c.synthesis?.compartment ?? 'cytosol', decay: String(c.decay ?? 0),
    exchangeThrough: c.exchange?.[0]?.through ?? '', exchangeTo: c.exchange?.[0]?.to ?? '', permeability: String(c.exchange?.[0]?.permeabilityUmS ?? 5)}));
  return {species, pairs: (cfg.pairs ?? []).map((q: any) => ({a: q.a, b: q.b, on: true, reachNm: String(q.reachNm), rate: String(q.rate), koff: String(q.koff)})),
    conversions: (cfg.reactions ?? []).map((q: any) => ({from: q.from, to: q.to, rate: String(q.rate)}))};
}

export const DEFAULT_OPACITY: Record<string, number> = {outside: 0, cytosol: 0, pm: 0.05, er: 0.5, nucleus: 0.3, mito: 0.95, golgi: 0.95, endo: 0.9, lyso: 0.95, ld: 0.95, vesicle: 0.95, chromatin: 0.55, nucleolus: 0.9, ne: 0.35};
export const ROD_OPACITY: Record<string, number> = {outside: 0, cytosol: 0.12, pm: 0.28, chromatin: 0.5};
export const hexToRgb = (hex: string): Vec3 => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255) as Vec3;
