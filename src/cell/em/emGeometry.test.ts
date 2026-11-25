import {describe, expect, it} from 'vitest';
import {boxOf, cutBounds, enter, estimateRadiusNm, eye, orientation, ray, toUm, toWorld, viewOf, type Camera, type Vec3} from './emGeometry';
import {atomModel, sphereModel} from './molecules';

const size: Vec3 = [48, 6.4, 33.3683], box = boxOf(size);

describe('EM volume geometry', () => {
  it('maps micrometres to the world box and back', () => {
    expect(box[0]).toBe(1);
    expect(box[1]).toBeCloseTo(6.4 / 48);
    const w = toWorld([12, 3.2, 33.3683], size, box) as number[];
    expect(w[0]).toBeCloseTo(-0.5); expect(w[1]).toBeCloseTo(0); expect(w[2]).toBeCloseTo(box[2]);
    toUm(w as Vec3, size, box).forEach((v, i) => expect(v).toBeCloseTo([12, 3.2, 33.3683][i]));
  });
  it('removes the camera side of the cut', () => {
    const above = cutBounds({axis: 1, at: 0.5}, box, [0, 2, 0]);
    expect(above.hi[1]).toBeCloseTo(0); expect(above.lo[1]).toBeCloseTo(-box[1]);
    const below = cutBounds({axis: 1, at: 0.5}, box, [0, -2, 0]);
    expect(below.lo[1]).toBeCloseTo(0); expect(below.hi[1]).toBeCloseTo(box[1]);
    expect(cutBounds({axis: -1, at: 0.5}, box, [0, 2, 0]).hi).toEqual(box);
    const dived: Camera = {yaw: 0.3, pitch: 0.7, distance: 0.001, target: [0.1, -0.1, 0.2]};      // eye below the face, still looking down
    expect(cutBounds({axis: 1, at: 0.5}, box, viewOf(dived)).hi[1]).toBeCloseTo(0);
  });
  it('picks the point under the cursor on the cut face', () => {
    const camera: Camera = {yaw: 0, pitch: Math.PI / 2 - 0.01, distance: 3, target: [0, 0, 0]};
    const centre = ray(camera, 0, 0), hit = enter(centre.origin, centre.direction, {axis: 1, at: 0.25}, box)!;
    expect(hit.onFace).toBe(true);
    const um = toUm(hit.point, size, box);
    expect(um[1]).toBeCloseTo(1.6, 3); expect(um[0]).toBeCloseTo(24, 0); expect(um[2]).toBeCloseTo(16.7, 0);
    expect(enter(eye(camera), [0, 1, 0], {axis: 1, at: 0.25}, box)).toBeNull();
    const side = enter([3, 0.05, 0], [-1, 0, 0], {axis: 1, at: 0.9}, box)!;
    expect(side.onFace).toBe(false);
  });
  it('estimates a sphere-equivalent radius from coordinates', () => {
    const atoms: {xyz: Vec3}[] = [];
    for (let x = -20; x <= 20; x += 2) for (let y = -20; y <= 20; y += 2) for (let z = -20; z <= 20; z += 2) if (x * x + y * y + z * z <= 400) atoms.push({xyz: [x, y, z]});
    expect(estimateRadiusNm(atoms)!).toBeCloseTo(2.0, 0);       // a 20 Å ball
    expect(estimateRadiusNm(atoms.slice(0, 5))).toBeNull();
  });
  it('gives every molecule a fixed unit orientation', () => {
    const q = orientation(5);
    expect(Math.hypot(...q)).toBeCloseTo(1, 6);
    expect(orientation(5)).toEqual(q);
    expect(orientation(6)).not.toEqual(q);
  });
  it('builds centred atom models with element radii', () => {
    const m = atomModel([0, 0, 0, 10, 0, 0], i => (i ? 'O' : 'C'), [1, 0, 0]);
    expect(Array.from(m.atoms.slice(0, 7))).toEqual([-5, 0, 0, expect.closeTo(1.7, 5), -1, -1, -1]);
    expect(m.atoms[7]).toBe(5); expect(m.atoms[11]).toBeGreaterThan(0.9);       // oxygen keeps its own colour
    expect(m.extentNm).toBeCloseTo(0.67, 2);
    const s = sphereModel(2.8, [0, 1, 0]);
    expect(s.atoms[3]).toBeCloseTo(28); expect(s.extentNm).toBe(2.8);
  });
});
