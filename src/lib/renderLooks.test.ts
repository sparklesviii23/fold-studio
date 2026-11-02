import {beforeEach, describe, expect, it} from 'vitest';
import {looks, lookColour, lookTypeParams, setColourMode} from './renderLooks';
import type {EngineAtom, EngineModel} from './engineScene';

const atom = (chain: string, residue: number, extra: Partial<EngineAtom> = {}) => ({chain, residue, atom: 'CA', polymerType: 'Protein', residueName: 'ALA', secondaryStructure: 1, ...extra}) as EngineAtom;
const model = (atoms: EngineAtom[]) => ({atoms}) as EngineModel;
const look = (id: string) => looks.find(l => l.id === id)!;

describe('render looks', () => {
  beforeEach(() => { const store = new Map<string, string>(); (globalThis as any).localStorage = {getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => store.set(k, v)}; (globalThis as any).window = {dispatchEvent: () => true}; });
  it('gives ribbons Mol* ribbon proportions, never stick proportions', () => {
    for (const l of looks) { const p = lookTypeParams(true, l) as any; expect(p.aspectRatio).toBeGreaterThanOrEqual(4); expect(p.sizeFactor).toBeLessThan(0.5); }
    expect((lookTypeParams(false, looks[0]) as any).aspectRatio).toBeUndefined();
  });
  it('colours chains distinctly and keeps engine colours in scientific mode', () => {
    const a = atom('A', 1), b = atom('B', 1), m = model([a, b]);
    expect(lookColour(a, m, look('nebula'))).not.toBe(lookColour(b, m, look('nebula')));
    setColourMode('scientific');
    expect(lookColour(a, m, look('nebula'))).toBeUndefined();
  });
  it('runs the rainbow from N- to C-terminus and treats unclassified residues as ligands', () => {
    const first = atom('A', 1), lastAtom = atom('A', 100), lig = atom('A', 200, {polymerType: 'Unclassified', residueName: 'ATP'}), m = model([first, lastAtom, lig]);
    expect(lookColour(first, m, look('maestro'))).not.toBe(lookColour(lastAtom, m, look('maestro')));
    expect(lookColour(lig, m, look('maestro'))).toBe(0xe9edf5);
  });
});
