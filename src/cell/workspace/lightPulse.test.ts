import {describe, expect, it} from 'vitest';
import {programAt, pulsesToProgram} from './useLightPulse';

describe('light program editing', () => {
  it('turns pulses into steps that return to dark', () => {
    const p = pulsesToProgram([{start: 120, duration: 30, intensity: 2}, {start: 30, duration: 60, intensity: 5}], 480);
    expect(p).toEqual({pre: 0, steps: [[0, 0], [30, 5], [90, 0], [120, 2], [150, 0]]});
    expect(programAt(p, 29.9)).toBe(0); expect(programAt(p, 30)).toBe(5); expect(programAt(p, 100)).toBe(0); expect(programAt(p, 130)).toBe(2);
  });
  it('starts lit when a pulse begins at zero and joins touching pulses', () => {
    expect(pulsesToProgram([{start: 0, duration: 10, intensity: 3}, {start: 10, duration: 5, intensity: 1}], 60).steps).toEqual([[0, 3], [10, 1], [15, 0]]);
  });
  it('refuses overlapping or empty pulses and drops pulses after the end', () => {
    expect(() => pulsesToProgram([{start: 10, duration: 30, intensity: 1}, {start: 20, duration: 30, intensity: 1}], 480)).toThrow(/overlap/);
    expect(() => pulsesToProgram([{start: 10, duration: 0, intensity: 1}], 480)).toThrow();
    expect(pulsesToProgram([{start: 500, duration: 10, intensity: 1}], 480).steps).toEqual([[0, 0]]);
  });
});
