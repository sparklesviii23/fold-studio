/** Molecule models for the EM cell view: atoms as (x, y, z, radius in Å, r, g, b); a carbon's colour is −1 so it takes the species colour. */
import type {MoleculeModel} from './VolumeStage';
import type {Vec3} from './emGeometry';

export const SPECIES_COLORS: Vec3[] = [[0.42, 0.92, 1], [1, 0.66, 0.36], [0.66, 1, 0.5], [1, 0.52, 0.84]];
export const SPECIES_HEX = ['#6bebff', '#ffa85c', '#a8ff80', '#ff85d6'];
/** Element colours (CPK-like) and van der Waals radii in Å. */
const ELEMENTS: Record<string, {color: Vec3; radius: number}> = {
  C: {color: [-1, -1, -1], radius: 1.7}, N: {color: [0.35, 0.5, 1], radius: 1.55}, O: {color: [1, 0.33, 0.3], radius: 1.52}, S: {color: [1, 0.86, 0.3], radius: 1.8},
  P: {color: [1, 0.6, 0.2], radius: 1.8}, SE: {color: [1, 0.7, 0.2], radius: 1.9}, FE: {color: [0.9, 0.45, 0.2], radius: 1.9}, ZN: {color: [0.6, 0.62, 0.75], radius: 1.4},
  MG: {color: [0.45, 0.95, 0.4], radius: 1.7}, CA: {color: [0.5, 0.95, 0.5], radius: 2.0}, NA: {color: [0.7, 0.5, 1], radius: 2.3}, CL: {color: [0.4, 0.95, 0.4], radius: 1.75},
};
const OTHER = {color: [0.85, 0.6, 0.9] as Vec3, radius: 1.8};

/** Atoms centred on their mean. `xyz` is flat, in Å. `thinned` > 1 means only every n-th atom is present, so spheres are enlarged to keep the shape filled. */
export function atomModel(xyz: ArrayLike<number>, elementOf: (i: number) => string, color: Vec3, thinned = 1): MoleculeModel {
  const grow = Math.cbrt(Math.max(1, thinned));
  const n = Math.floor(xyz.length / 3), atoms = new Float32Array(n * 7), c = [0, 0, 0];
  for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) c[k] += xyz[i * 3 + k] / n;
  let extent = 0;
  for (let i = 0; i < n; i++) {
    const e = ELEMENTS[elementOf(i).toUpperCase()] ?? OTHER, x = xyz[i * 3] - c[0], y = xyz[i * 3 + 1] - c[1], z = xyz[i * 3 + 2] - c[2];
    atoms.set([x, y, z, e.radius * grow, e.color[0], e.color[1], e.color[2]], i * 7);
    extent = Math.max(extent, Math.hypot(x, y, z) + e.radius * grow);
  }
  return {atoms, extentNm: extent / 10, color};
}

/** A molecule known only by its hydrodynamic radius: one sphere of that radius. */
export function sphereModel(radiusNm: number, color: Vec3): MoleculeModel {
  return {atoms: new Float32Array([0, 0, 0, radiusNm * 10, -1, -1, -1]), extentNm: radiusNm, color};
}

/** Everything needed to draw and inspect one saved structure: heavy atoms centred on their mean, with their identities. */
export interface StructureData {
  atoms: number; drawnEvery?: number; kind?: string; xyz: number[]; elements: string[]; element: number[]; chains: string[]; chain: number[];
  residues: [string, string, string][]; residueOf: number[]; atomNames: string[]; atomName: number[];
}
export type Representation = 'atoms' | 'chains' | 'backbone';
const CHAIN_COLORS: Vec3[] = [[0.42, 0.92, 1], [1, 0.72, 0.4], [0.7, 1, 0.55], [1, 0.55, 0.85], [0.75, 0.7, 1], [1, 0.9, 0.45], [0.5, 1, 0.85], [1, 0.6, 0.55]];
const BACKBONE = new Set(['CA', 'P', "C4'"]);

/** The structure open in the viewer, in the same shape the engine returns for a library file. */
export function fromAtomRecords(records: {xyz: [number, number, number]; element: string; chain: string; name: string; auth: number; atomName: string}[]): StructureData | null {
  const heavy = records.filter(a => a.element !== 'H' && a.name !== 'HOH');
  if (heavy.length < 4) return null;
  const index = <T,>(values: T[]) => { const list: T[] = [], seen = new Map<string, number>(); const of = values.map(v => { const k = JSON.stringify(v); if (!seen.has(k)) { seen.set(k, list.length); list.push(v); } return seen.get(k)!; }); return {list, of}; };
  const el = index(heavy.map(a => a.element.toUpperCase())), ch = index(heavy.map(a => a.chain)), an = index(heavy.map(a => a.atomName));
  const res = index(heavy.map(a => [a.chain, a.name, String(a.auth)] as [string, string, string]));
  return {atoms: heavy.length, xyz: heavy.flatMap(a => a.xyz), elements: el.list, element: el.of, chains: ch.list, chain: ch.of, residues: res.list, residueOf: res.of, atomNames: an.list, atomName: an.of,
    kind: heavy.filter(a => a.atomName === 'P').length > heavy.filter(a => a.atomName === 'CA').length ? 'nucleic acid' : 'protein'};
}

/** A drawable model of a structure. `ids` maps each drawn sphere back to its atom in `data`. */
export function modelOf(data: StructureData, color: Vec3, representation: Representation): MoleculeModel & {ids: Int32Array} {
  const keep: number[] = [];
  for (let i = 0; i < data.element.length; i++) if (representation !== 'backbone' || BACKBONE.has(data.atomNames[data.atomName[i]])) keep.push(i);
  const ids = Int32Array.from(keep.length ? keep : data.element.map((_, i) => i));
  const grow = representation === 'backbone' ? 1 : Math.cbrt(Math.max(1, data.drawnEvery ?? 1));
  const n = data.element.length, c = [0, 0, 0];
  for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) c[k] += data.xyz[i * 3 + k] / n;
  const atoms = new Float32Array(ids.length * 7); let extent = 0;
  ids.forEach((i, j) => {
    const e = ELEMENTS[data.elements[data.element[i]]] ?? OTHER, x = data.xyz[i * 3] - c[0], y = data.xyz[i * 3 + 1] - c[1], z = data.xyz[i * 3 + 2] - c[2];
    const radius = representation === 'backbone' ? 2.4 : e.radius * grow;
    const col = representation === 'atoms' ? e.color : data.chains.length > 1 ? CHAIN_COLORS[data.chain[i] % CHAIN_COLORS.length] : [-1, -1, -1];
    atoms.set([x, y, z, radius, col[0], col[1], col[2]], j * 7);
    extent = Math.max(extent, Math.hypot(x, y, z) + radius);
  });
  return {atoms, extentNm: extent / 10, color, ids};
}

/** Chain, residue and atom identity of one atom, as stored in the saved structure. */
export function describeAtom(data: StructureData, atom: number) {
  const r = data.residues[data.residueOf[atom]];
  return {chain: r?.[0] ?? data.chains[data.chain[atom]], residue: r?.[1] ?? '', number: r?.[2] ?? '', atom: data.atomNames[data.atomName[atom]] ?? '', element: data.elements[data.element[atom]]};
}
