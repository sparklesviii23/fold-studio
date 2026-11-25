import {describe, expect, it} from 'vitest';
import {boxOf} from '../em/emGeometry';
import {classAt, clock, densityField, lastAtOrBefore, NM_PER_COPY_PER_UM3, pickCompartment, pickMolecule, type Grid} from './spatial';

const grid = (): Grid => {                       // 10 × 4 × 6 voxels of 1 µm; class 5 fills x 6…8
  const dims: [number, number, number] = [10, 4, 6], classes = new Uint8Array(240).fill(1);
  for (let z = 0; z < 6; z++) for (let y = 0; y < 4; y++) for (let x = 6; x < 8; x++) classes[(z * 4 + y) * 10 + x] = 5;
  return {dims, sizeUm: [10, 4, 6], classes};
};

describe('workspace spatial helpers', () => {
  it('reads classes in physical coordinates', () => {
    const g = grid();
    expect(classAt(g, [6.5, 1, 1])).toBe(5); expect(classAt(g, [5.9, 1, 1])).toBe(1); expect(classAt(g, [-1, 1, 1])).toBe(0);
  });
  it('picks the first visible compartment along a ray and reports where', () => {
    const g = grid(), box = boxOf(g.sizeUm), lo = box.map(v => -v) as [number, number, number];
    const ray = {origin: [-3, 0, 0] as [number, number, number], direction: [1, 0, 0] as [number, number, number]};
    const all = pickCompartment(ray, box, lo, box, g, () => true)!;
    expect(all.cls).toBe(1); expect(all.um[0]).toBeLessThan(0.5);
    const only5 = pickCompartment(ray, box, lo, box, g, c => c === 5)!;
    expect(only5.cls).toBe(5); expect(only5.um[0]).toBeGreaterThanOrEqual(6); expect(only5.um[0]).toBeLessThan(6.6);
    expect(pickCompartment({...ray, direction: [0, 1, 0]}, box, lo, box, g, () => true)).toBeNull();
  });
  it('picks the nearest molecule on the ray and ignores absent ones', () => {
    const frame = Float32Array.from([0.5, 0, 0, 0.2, 0.001, 0, 0.1, 0, 0]), ray = {origin: [-1, 0, 0] as [number, number, number], direction: [1, 0, 0] as [number, number, number]};
    expect(pickMolecule(ray, frame, Uint8Array.from([0, 0, 3]), 0.02)).toBe(1);
    expect(pickMolecule({...ray, origin: [-1, 0.5, 0]}, frame, Uint8Array.from([0, 0, 0]), 0.02)).toBe(-1);
  });
  it('turns positions into a density with physical units', () => {
    const box = boxOf([10, 4, 6]), frame = Float32Array.from([-0.95, 0, 0, -0.95, 0, 0, 0.5, 0, 0]);
    const f = densityField([frame, frame], [new Uint8Array(3), new Uint8Array(3)], () => true, box, [10, 4, 6], [10, 4, 6]);
    expect(Math.max(...f.bytes)).toBe(255); expect(f.maxPerUm3).toBeCloseTo(2); expect(f.copies).toBe(3);   // 2 copies in a 1 µm³ bin
    expect(NM_PER_COPY_PER_UM3).toBeCloseTo(1.6605, 3);
  });
  it('maps time to frames and formats simulated time', () => {
    expect(lastAtOrBefore([0.1, 0.2, 0.3], 0.25)).toBe(1); expect(lastAtOrBefore([0.1, 0.2], 0.05)).toBe(-1); expect(lastAtOrBefore([0.1, 0.2], 9)).toBe(1);
    expect(clock(0.0482, 's')).toEqual({value: '48.2', unit: 'ms'}); expect(clock(132.44, 'min')).toEqual({value: '2.21', unit: 'h'}); expect(clock(42, 'min')).toEqual({value: '42.0', unit: 'min'});
  });
});
