import {describe, expect, it} from 'vitest';
import {compare, pairsOf, ribosomesAt, smooth} from './rnaLab';

const TRNA = '(((((((..((((........)))).(((((.......))))).....(((((.......))))))))))))....';

describe('RNA laboratory helpers', () => {
  it('parses the tRNA cloverleaf into its 21 pairs', () => {
    const p = pairsOf(TRNA);
    expect(p).toHaveLength(21);
    expect(p[0]).toEqual([0, 71]);
    expect(() => pairsOf('(()')).toThrow();
  });

  it('computes base-pair sensitivity, PPV and F1', () => {
    expect(compare(TRNA, TRNA)).toMatchObject({tp: 21, fp: 0, fn: 0, f1: 1});
    const a = compare('((....))..', '(......)..');
    expect(a).toMatchObject({tp: 1, fp: 1, fn: 0});
    expect(a.ppv).toBeCloseTo(0.5);
    expect(a.f1).toBeCloseTo(2 / 3);
    expect(compare('..........', '(......)..').f1).toBe(0);
  });

  it('only interpolates ribosomes present in both exact frames', () => {
    const frames = [{t: 0, ribosomes: [[1, 10], [2, 0]] as [number, number][]}, {t: 1, ribosomes: [[1, 14], [3, 0]] as [number, number][]}];
    const mid = ribosomesAt(frames, 0.5);
    expect(mid).toEqual([{id: 1, codon: 12, interpolated: true}, {id: 2, codon: 0, interpolated: false}]);
    expect(ribosomesAt(frames, 1)).toEqual([{id: 1, codon: 14, interpolated: false}, {id: 3, codon: 0, interpolated: false}]);
    expect(ribosomesAt([], 3)).toEqual([]);
  });

  it('smooths without changing length', () => {
    expect(smooth([0, 3, 0], 3)).toEqual([1.5, 1, 1.5]);
    expect(smooth([1, 2], 1)).toEqual([1, 2]);
  });
});
