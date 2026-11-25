import {describe, expect, it} from 'vitest';
import {buildPlayback, countsAt, frameAt, type LpParticles} from './lightParticles';

const p = {context: 'ecoli-bw29655-ccasr', sizeUm: [2.8, 1.12, 1.12], time: [0, 5, 10], owner: [0, 1, 1], frames: [[1, 0.5, 0.5, 1.2, 0.5, 0.5, 1.4, 0.6, 0.5], [1, 0.5, 0.5, 1.3, 0.5, 0.5, 1.5, 0.6, 0.5], [1, 0.5, 0.5, 1.1, 0.5, 0.5, 1.6, 0.6, 0.5]],
  absent: [[2], [], [0]], weight: 100, seed: 7, model: 'mechanistic', passed: true, checks: [], fluorescence: [100, 200, 200],
  species: [{key: 'regulator', name: 'Active sensor', where: 'Envelope', compartment: 'pm', radiusNm: 3.5, capacity: 1, weight: 1, molecules: [1, 1, 0], particles: [1, 1, 0], evidence: 'assumed'},
    {key: 'mature', name: 'Mature reporter', where: 'Cytoplasm', compartment: 'cytosol', radiusNm: 2.4, capacity: 2, weight: 100, molecules: [100, 200, 200], particles: [1, 2, 2], evidence: 'predicted'}],
  phi: {value: 1, unit: 'MEFL per molecule', mapping: 'relative', provenance: {kind: 'assumed', note: ''}}, evidence: {positions: '', numbers: ''}} as unknown as LpParticles;

describe('light-pulse particles', () => {
  it('maps time to the last display frame at or before it', () => {
    expect(frameAt(p.time, -1)).toBe(0); expect(frameAt(p.time, 4.99)).toBe(0); expect(frameAt(p.time, 5)).toBe(1); expect(frameAt(p.time, 99)).toBe(2);
  });
  it('builds snapshot frames with absent copies marked and no trail', () => {
    const play = buildPlayback(p);
    expect(play.snapshots).toBe(true); expect(play.frames).toHaveLength(3); expect(play.frames[0]).toHaveLength(9);
    expect(Array.from(play.state[0])).toEqual([0, 0, 3]); expect(Array.from(play.state[2])).toEqual([3, 0, 0]);
    expect(Math.max(...Array.from(play.frames[0]).map(Math.abs))).toBeLessThanOrEqual(1);
  });
  it('reports molecule numbers, not dot counts, as the quantity', () => {
    const c = countsAt(p, 1)[1];
    expect(c.molecules).toBe(200); expect(c.particles * c.weight).toBe(c.molecules);
  });
});
