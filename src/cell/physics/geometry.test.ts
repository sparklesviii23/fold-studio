import {describe, expect, it} from 'vitest';
import {extent, interpolate, project, resample, scaleBar} from './geometry';

describe('cell physics drawing helpers', () => {
  it('projects orthographically and preserves lengths in the image plane', () => {
    const v = {yaw: 0, pitch: 0, scale: 10, cx: 100, cy: 50};
    expect(project([1, 0, 0], v)).toEqual([110, 50, 0]);
    expect(project([0, 1, 0], v)[1]).toBe(40);
    const r = {...v, yaw: 0.7, pitch: -0.3};
    const [x, y, z] = project([3, 4, 12], r);
    expect(Math.hypot((x - 100) / 10, (y - 50) / 10, z)).toBeCloseTo(13, 10);
  });
  it('picks a nice scale bar close to the target width', () => {
    expect(scaleBar(20)).toBe(5);
    expect(scaleBar(110)).toBe(1);
    expect(scaleBar(1000)).toBe(0.1);
  });
  it('interpolates without extrapolating', () => {
    expect(interpolate([0, 1, 2], [0, 10, 40], 1.5)).toBe(25);
    expect(interpolate([0, 1], [3, 5], 2)).toBeNull();
    expect(resample([0, 2], [0, 2], [0, 1, 3])).toEqual([0, 1, null]);
  });
  it('measures the extent of sampled tracks', () => {
    expect(extent([[[0, 0, 0], [3, 4, 0]], [[0, 0, -6]]])).toBe(6);
  });
});
