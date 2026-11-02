import {readFileSync} from 'node:fs';
import {describe,expect,it} from 'vitest';
import {crossCheckWithDemoD,frameValue,type BloodInputs} from './bloodTransport';

// Produced by `python3 scientific/blood_transport.py --reference fixtures/blood/python-taylor-aris-reference.json`
// (lab-frame axisymmetric FV, 24 × 500 cells); tests/test_blood_transport.py checks the fixture is current.
const ref=JSON.parse(readFileSync(new URL('../../fixtures/blood/python-taylor-aris-reference.json',import.meta.url),'utf8')) as {inputs:BloodInputs;numericalKM2PerS:number;taylorArisM2PerS:number;final:{zUm:number[];meanMolPerM3:number[]}};

describe('Demo 6 plasma transport vs the in-app Demo D solver',()=>{
 it('agrees on the Taylor–Aris dispersion coefficient and the cross-sectional profile',()=>{
  const check=crossCheckWithDemoD(ref.inputs,ref.numericalKM2PerS,ref.final);
  expect(check.applicable).toBe(true);
  expect(check.kRelativeDifference!).toBeLessThan(.01);
  expect(check.profileL1Difference!).toBeLessThan(.02);
  expect(check.pass).toBe(true);
  // Both solvers are independently within 1 % of the analytical coefficient.
  expect(Math.abs(ref.numericalKM2PerS-ref.taylorArisM2PerS)/ref.taylorArisM2PerS).toBeLessThan(.01);
  expect(Math.abs(check.tsK!-ref.taylorArisM2PerS)/ref.taylorArisM2PerS).toBeLessThan(.01);
 });
 it('refuses the cross-check where Demo D does not model the experiment',()=>{
  expect(crossCheckWithDemoD({...ref.inputs,inletMode:'pulse'},1,ref.final).applicable).toBe(false);
  expect(crossCheckWithDemoD({...ref.inputs,wallPermeabilityUmPerS:1},1,ref.final).applicable).toBe(false);
 });
 it('decodes display frames against the run peak',()=>{
  expect(frameValue(65535,2.5,65535)).toBe(2.5);expect(frameValue(0,2.5,65535)).toBe(0);
 });
});
