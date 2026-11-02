import {describe, expect, it} from 'vitest';
import {chromatinFibre, coarseGrain, demoParticle, MAX_BEADS} from './micrograph';

describe('micrograph geometry', () => {
  it('coarse-grains a long chain to at most MAX_BEADS centred beads', () => {
    const atoms = Array.from({length: 500}, (_, i) => ({xyz: [i * 3.8, 10, -4] as [number, number, number], chain: 'A', atomName: 'CA'}));
    const p = coarseGrain(atoms, 'long')!;
    expect(p.beads.length).toBeLessThanOrEqual(MAX_BEADS);
    expect(p.residues).toBe(500);
    const cx = p.beads.reduce((s, b) => s + b.x * b.weight, 0) / p.beads.reduce((s, b) => s + b.weight, 0);
    expect(Math.abs(cx)).toBeLessThan(1e-6);
    expect(p.radius).toBeGreaterThan(900);
  });
  it('does not merge residues across chains', () => {
    const atoms = [...Array.from({length: 3}, (_, i) => ({xyz: [i, 0, 0] as [number, number, number], chain: 'A', atomName: 'CA'})), ...Array.from({length: 3}, (_, i) => ({xyz: [100 + i, 0, 0] as [number, number, number], chain: 'B', atomName: 'CA'}))];
    expect(coarseGrain(atoms, 'two')!.beads).toHaveLength(6);
  });
  it('returns null without a trace and offers a demo particle', () => {
    expect(coarseGrain([{xyz: [0, 0, 0], chain: 'A', atomName: 'N'}], 'x')).toBeNull();
    expect(demoParticle().source).toBe('demo');
  });
  it('builds a fibre with one nucleosome per 197 bp repeat, within the bead budget', () => {
    const f = chromatinFibre(1970);
    expect(f.nucleosomes).toBe(10);
    expect(f.beads.length).toBeLessThanOrEqual(MAX_BEADS);
    expect(f.beads.filter(b => b.sigma === 30)).toHaveLength(10);
    expect(chromatinFibre(1970, 50, 7)).toEqual(chromatinFibre(1970, 50, 7));
  });
});
