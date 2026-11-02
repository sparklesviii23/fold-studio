/** Geometry for the illustrated binding animation: 2D projection, chains and interface. */
export interface TraceAtom {xyz: [number, number, number]; chain: string; atomName: string; auth?: number; name?: string}
export interface Chain2D {id: string; points: [number, number][]; centroid: [number, number]; residues: number}
export interface Scene2D {chains: Chain2D[]; interfaceTarget: [number, number][]; interfaceCentre: [number, number] | null; radius: number}

const sub = (a: number[], b: number[]) => a.map((v, i) => v - b[i]);
const dot = (a: number[], b: number[]) => a.reduce((s, v, i) => s + v * b[i], 0);
const norm = (a: number[]) => { const l = Math.hypot(...a) || 1; return a.map(v => v / l); };

/** The two principal axes of a point cloud, by power iteration on its covariance. */
export function principalAxes(points: number[][]): [number[], number[]] {
  const c = [0, 1, 2].map(k => points.reduce((s, p) => s + p[k], 0) / points.length);
  const cov = [0, 1, 2].map(i => [0, 1, 2].map(j => points.reduce((s, p) => s + (p[i] - c[i]) * (p[j] - c[j]), 0) / points.length));
  const mul = (m: number[][], v: number[]) => m.map(row => dot(row, v));
  let a = norm([1, 0.3, 0.2]);
  for (let i = 0; i < 60; i++) a = norm(mul(cov, a));
  let b = norm([0.2, 1, 0.3]);
  for (let i = 0; i < 60; i++) { b = mul(cov, b); b = norm(sub(b, a.map(v => v * dot(a, b)))); }
  return [a, b];
}

/**
 * Project the Cα trace of a complex onto its principal plane. `binder` lists the
 * chain ids treated as the incoming molecule; target residues whose Cα lies
 * within `contact` Å of any binder Cα form the highlighted interface.
 */
export function projectComplex(atoms: TraceAtom[], binder: string[], contact = 9): Scene2D | null {
  const ca = atoms.filter(a => a.atomName === 'CA' || a.atomName === 'P');
  if (ca.length < 3) return null;
  const centre = [0, 1, 2].map(k => ca.reduce((s, a) => s + a.xyz[k], 0) / ca.length);
  const [u, v] = principalAxes(ca.map(a => a.xyz));
  const flat = (p: number[]): [number, number] => { const d = sub(p, centre); return [dot(d, u), -dot(d, v)]; };
  const ids = [...new Set(ca.map(a => a.chain))];
  const chains = ids.map(id => {
    const own = ca.filter(a => a.chain === id), points = own.map(a => flat(a.xyz));
    const centroid: [number, number] = [points.reduce((s, p) => s + p[0], 0) / points.length, points.reduce((s, p) => s + p[1], 0) / points.length];
    return {id, points, centroid, residues: own.length};
  });
  const binderAtoms = ca.filter(a => binder.includes(a.chain)), contact2 = contact * contact;
  const interfaceTarget = ca.filter(a => !binder.includes(a.chain) && binderAtoms.some(b => (a.xyz[0] - b.xyz[0]) ** 2 + (a.xyz[1] - b.xyz[1]) ** 2 + (a.xyz[2] - b.xyz[2]) ** 2 < contact2)).map(a => flat(a.xyz));
  const interfaceCentre: [number, number] | null = interfaceTarget.length ? [interfaceTarget.reduce((s, p) => s + p[0], 0) / interfaceTarget.length, interfaceTarget.reduce((s, p) => s + p[1], 0) / interfaceTarget.length] : null;
  const radius = Math.max(...chains.flatMap(c => c.points.map(p => Math.hypot(p[0], p[1]))));
  return {chains, interfaceTarget, interfaceCentre, radius};
}

/** The smallest chain is the usual guess for a designed binder or peptide. */
export function guessBinder(atoms: TraceAtom[]): string | null {
  const counts = new Map<string, number>();
  for (const a of atoms) if (a.atomName === 'CA') counts.set(a.chain, (counts.get(a.chain) ?? 0) + 1);
  if (counts.size < 2) return null;
  return [...counts.entries()].sort((a, b) => a[1] - b[1])[0][0];
}
