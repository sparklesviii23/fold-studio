/**
 * Geometry for simulated micrographs. Molecules are reduced to Gaussian beads
 * (x, y, z, sigma in ångström) whose projected density forms the image, the
 * way an electron micrograph is a projection of the specimen's density.
 */
export interface Bead {x: number; y: number; z: number; sigma: number; weight: number}
export interface Particle {name: string; source: 'structure'|'demo'; beads: Bead[]; radius: number; residues: number}
export const MAX_BEADS = 120;

interface Atomish {xyz: [number, number, number]; chain: string; atomName?: string; name?: string}

/** Centre the beads on their weighted centroid and measure the enclosing radius. */
function centre(beads: Bead[]): {beads: Bead[]; radius: number} {
  const w = beads.reduce((s, b) => s + b.weight, 0) || 1;
  const c = beads.reduce((s, b) => [s[0] + b.x * b.weight, s[1] + b.y * b.weight, s[2] + b.z * b.weight], [0, 0, 0]).map(v => v / w);
  const out = beads.map(b => ({...b, x: b.x - c[0], y: b.y - c[1], z: b.z - c[2]}));
  return {beads: out, radius: Math.max(10, ...out.map(b => Math.hypot(b.x, b.y, b.z) + b.sigma))};
}

/**
 * Coarse-grain a structure to at most MAX_BEADS beads: consecutive Cα (or P for
 * nucleic acids) positions along each chain are averaged, and each bead's sigma
 * grows with the spread of the residues it represents.
 */
export function coarseGrain(atoms: Atomish[], name: string): Particle | null {
  const trace = atoms.filter(a => (a.atomName ?? a.name) === 'CA' || (a.atomName ?? a.name) === 'P');
  if (trace.length < 4) return null;
  const perBead = Math.max(1, Math.ceil(trace.length / MAX_BEADS));
  const beads: Bead[] = [];
  for (let i = 0; i < trace.length;) {
    const group = [trace[i]];
    let j = i + 1;
    while (j < trace.length && group.length < perBead && trace[j].chain === trace[i].chain) group.push(trace[j++]);
    const m = [0, 1, 2].map(k => group.reduce((s, a) => s + a.xyz[k], 0) / group.length);
    const spread = Math.sqrt(group.reduce((s, a) => s + (a.xyz[0] - m[0]) ** 2 + (a.xyz[1] - m[1]) ** 2 + (a.xyz[2] - m[2]) ** 2, 0) / group.length);
    beads.push({x: m[0], y: m[1], z: m[2], sigma: 2.6 + spread * 0.8, weight: group.length});
    i = j;
  }
  const c = centre(beads);
  return {name, source: 'structure', beads: c.beads, radius: c.radius, residues: trace.length};
}

/** A synthetic three-helix bundle, used when no structure is open. */
export function demoParticle(): Particle {
  const atoms: Atomish[] = [];
  const axes: [number, number][] = [[0, 0], [10, 0], [5, 8.7]];
  axes.forEach(([ax, ay], h) => {
    for (let i = 0; i < 32; i++) {
      const t = i * (100 * Math.PI / 180), z = (h % 2 ? 46 - i * 1.5 : i * 1.5);
      atoms.push({xyz: [ax + 2.3 * Math.cos(t), ay + 2.3 * Math.sin(t), z], chain: 'A', atomName: 'CA'});
    }
  });
  return {...coarseGrain(atoms, 'Three-helix bundle (synthetic demo)')!, source: 'demo'};
}

function random(seed: number) { let s = seed >>> 0; return () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

/**
 * A schematic 10 nm "beads-on-a-string" chromatin fibre: nucleosome cores
 * (147 bp, ~11 nm discs) joined by linker DNA (0.34 nm per base pair), laid on
 * the grid as a persistent random walk. Returns beads in ångström.
 */
export function chromatinFibre(basePairs: number, linker = 50, seed = 7): {beads: Bead[]; nucleosomes: number} {
  const rnd = random(seed), repeat = 147 + linker;
  const nucleosomes = Math.max(1, Math.min(Math.floor(basePairs / repeat), Math.floor(MAX_BEADS / 6)));
  const beads: Bead[] = [];
  let x = 0, y = 0, heading = rnd() * Math.PI * 2;
  const linkerLength = linker * 3.4, linkerBeads = Math.max(2, Math.round(linkerLength / 34));
  for (let n = 0; n < nucleosomes; n++) {
    beads.push({x, y, z: 0, sigma: 30, weight: 6});
    for (let k = 1; k <= linkerBeads; k++) {
      heading += (rnd() - 0.5) * 0.9;
      const step = (55 + linkerLength) / (linkerBeads + 1);
      x += Math.cos(heading) * step; y += Math.sin(heading) * step;
      if (k < linkerBeads || n === nucleosomes - 1) beads.push({x, y, z: 0, sigma: 9, weight: 2.2});
    }
    x += Math.cos(heading) * 55; y += Math.sin(heading) * 55;
  }
  const cx = beads.reduce((s, b) => s + b.x, 0) / beads.length, cy = beads.reduce((s, b) => s + b.y, 0) / beads.length;
  return {beads: beads.slice(0, MAX_BEADS).map(b => ({...b, x: b.x - cx, y: b.y - cy})), nucleosomes};
}
