import {describe, expect, it} from 'vitest';
import {guessBinder, principalAxes, projectComplex} from './bindingGeometry';

const line = (chain: string, n: number, x0: number, y: number) => Array.from({length: n}, (_, i) => ({xyz: [x0 + i * 3.8, y, 0] as [number, number, number], chain, atomName: 'CA'}));

describe('binding geometry', () => {
  it('finds the long axis first', () => {
    const [a] = principalAxes(Array.from({length: 20}, (_, i) => [i * 5, i % 2, 0]));
    expect(Math.abs(a[0])).toBeGreaterThan(0.99);
  });
  it('guesses the smallest chain as the binder', () => {
    expect(guessBinder([...line('A', 40, 0, 0), ...line('P', 8, 0, 6)])).toBe('P');
    expect(guessBinder(line('A', 10, 0, 0))).toBeNull();
  });
  it('marks target residues within the contact distance as interface', () => {
    const scene = projectComplex([...line('A', 40, 0, 0), ...line('P', 5, 0, 6)], ['P'])!;
    expect(scene.chains.map(c => c.id)).toEqual(['A', 'P']);
    expect(scene.interfaceTarget.length).toBeGreaterThan(3);
    expect(scene.interfaceTarget.length).toBeLessThan(12);
    expect(scene.interfaceCentre).not.toBeNull();
  });
});
