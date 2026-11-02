/** Pure helpers for the RNA-to-Protein Laboratory views (no computation of science here). */

export type Pair = [number, number];

export function pairsOf(dotBracket: string): Pair[] {
  const stack: number[] = [], out: Pair[] = [];
  for (let i = 0; i < dotBracket.length; i++) {
    const c = dotBracket[i];
    if (c === '(') stack.push(i);
    else if (c === ')') { const j = stack.pop(); if (j === undefined) throw new Error('Unbalanced structure'); out.push([j, i]); }
  }
  if (stack.length) throw new Error('Unbalanced structure');
  return out.sort((a, b) => a[0] - b[0]);
}

export interface Accuracy {tp: number; fp: number; fn: number; sensitivity: number; ppv: number; f1: number}

export function compare(predicted: string, reference: string): Accuracy {
  const key = (p: Pair) => p[0] + ':' + p[1];
  const ref = new Set(pairsOf(reference).map(key)), pred = new Set(pairsOf(predicted).map(key));
  let tp = 0; pred.forEach(k => { if (ref.has(k)) tp++; });
  const fp = pred.size - tp, fn = ref.size - tp;
  const sensitivity = tp + fn ? tp / (tp + fn) : 0, ppv = tp + fp ? tp / (tp + fp) : 0;
  return {tp, fp, fn, sensitivity, ppv, f1: sensitivity + ppv ? 2 * sensitivity * ppv / (sensitivity + ppv) : 0};
}

/** Half-ellipse arc between bases i and j on a baseline; `up` draws above it, `flatten` scales its height. */
export function arcPath(i: number, j: number, x: (k: number) => number, baseline: number, up = true, flatten = 1) {
  const x1 = x(i), x2 = x(j), r = (x2 - x1) / 2;
  return `M${x1.toFixed(2)} ${baseline}A${r.toFixed(2)} ${(r * flatten).toFixed(2)} 0 0 ${up ? 1 : 0} ${x2.toFixed(2)} ${baseline}`;
}

export interface Frame {t: number; ribosomes: [number, number][]}
export interface PlacedRibosome {id: number; codon: number; interpolated: boolean}

/**
 * Ribosome positions at time t. Frames are exact simulated states; between two frames a ribosome
 * present in both is drawn at a linearly interpolated codon (visual only, flagged `interpolated`).
 */
export function ribosomesAt(frames: Frame[], t: number): PlacedRibosome[] {
  if (!frames.length) return [];
  if (t <= frames[0].t) return frames[0].ribosomes.map(([id, codon]) => ({id, codon, interpolated: false}));
  const last = frames[frames.length - 1];
  if (t >= last.t) return last.ribosomes.map(([id, codon]) => ({id, codon, interpolated: false}));
  let lo = 0, hi = frames.length - 1;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (frames[mid].t <= t) lo = mid; else hi = mid; }
  const a = frames[lo], b = frames[hi], f = (t - a.t) / (b.t - a.t || 1);
  if (f === 0) return a.ribosomes.map(([id, codon]) => ({id, codon, interpolated: false}));
  const next = new Map(b.ribosomes);
  return a.ribosomes.map(([id, codon]) => {
    const to = next.get(id);
    return to === undefined ? {id, codon, interpolated: false} : {id, codon: codon + (to - codon) * f, interpolated: to !== codon};
  });
}

/** Rolling mean used only to draw a readable occupancy trace; the raw profile is kept alongside. */
export function smooth(values: number[], window: number) {
  if (window <= 1) return values.slice();
  const half = Math.floor(window / 2), out: number[] = [];
  for (let i = 0; i < values.length; i++) {
    let s = 0, n = 0;
    for (let k = Math.max(0, i - half); k <= Math.min(values.length - 1, i + half); k++) { s += values[k]; n++; }
    out.push(s / n);
  }
  return out;
}
