import {describe,it,expect} from 'vitest';
import {solveCapillary,capillaryPresets,capillaryRecord,taylorArisCoefficient,defaultSolverSettings,type CapillaryInputs} from './taylorAris';
const benchmark=capillaryPresets.find(p=>p.id==='benchmark')!.inputs;
const small:CapillaryInputs={...benchmark,durationS:.2,axialCells:200,radialCells:16};
describe('capillary advection–diffusion solver (Demo D)',()=>{
 it('reproduces the Taylor–Aris dispersion coefficient at Pe = 20 within 1%',()=>{
  const r=solveCapillary(benchmark),b=r.benchmark;
  expect(r.derived.peclet).toBeCloseTo(20,10);expect(r.derived.taylorArisM2PerS).toBeCloseTo(1e-9*(1+400/48),20);
  expect(b.effectiveDispersion.applicable).toBe(true);expect(b.effectiveDispersion.relativeError).toBeLessThan(.01);expect(b.effectiveDispersion.pass).toBe(true);
  expect(b.mass.maxRelativeDrift).toBeLessThan(1e-10);expect(b.domain.pass).toBe(true);
  expect(Math.abs(b.centroidVelocity.numericalMPerS-4e-3)/4e-3).toBeLessThan(1e-5);
 },60000);
 it('reduces to molecular diffusion when there is no flow',()=>{
  const r=solveCapillary({...small,meanVelocityMmPerS:0});
  expect(r.derived.taylorArisM2PerS).toBe(1e-9);expect(r.benchmark.effectiveDispersion.relativeError).toBeLessThan(.01);expect(r.benchmark.mass.pass).toBe(true);
 },60000);
 it('passes for a capillary-scale macromolecule (Pe = 25)',()=>{
  const r=solveCapillary(capillaryPresets.find(p=>p.id==='macromolecule')!.inputs);
  expect(r.derived.peclet).toBeCloseTo(25,10);expect(r.benchmark.effectiveDispersion.pass).toBe(true);expect(r.benchmark.mass.pass).toBe(true);
 },60000);
 it('converges under axial refinement',()=>{
  const coarse=solveCapillary({...small,axialCells:80}).benchmark.effectiveDispersion.relativeError,fine=solveCapillary({...small,axialCells:320}).benchmark.effectiveDispersion.relativeError;
  expect(fine).toBeLessThan(coarse/2);
 },60000);
 it('is second order in time: backward Euler is visibly worse than Crank–Nicolson',()=>{
  const cn=solveCapillary(small).benchmark.effectiveDispersion.relativeError,be=solveCapillary(small,{...defaultSolverSettings,radialImplicitness:1}).benchmark.effectiveDispersion.relativeError;
  expect(cn).toBeLessThan(be);
 },60000);
 it('conserves mass to round-off and keeps a non-negative cross-sectional mean',()=>{
  const r=solveCapillary(small);
  for(const s of r.series)expect(Math.abs(s.massMol-1e-15)/1e-15).toBeLessThan(1e-10);
  expect(r.snapshots).toHaveLength(6);expect(new Set(r.snapshots.map(s=>s.t)).size).toBe(6);expect(r.snapshots[5].t).toBe(.2);
  for(const s of r.snapshots)expect(Math.min(...s.meanMolPerM3)).toBeGreaterThan(-1e-12*Math.max(...s.meanMolPerM3));
 },60000);
 it('records the slug passing a fixed detector at t ≈ z/U',()=>{
  const r=solveCapillary(benchmark),hits=r.series.filter(s=>s.detectorMolPerM3!==null);
  const peak=hits.reduce((a,s)=>s.detectorMolPerM3!>a.detectorMolPerM3!?s:a);
  expect(Math.abs(peak.t-.25)/.25).toBeLessThan(.03);
 },60000);
 it('refuses to call the benchmark valid before the radial transient decays',()=>{
  const r=solveCapillary({...small,durationS:.01});
  expect(r.benchmark.effectiveDispersion.applicable).toBe(false);expect(r.benchmark.effectiveDispersion.pass).toBe(false);
 },60000);
 it('rejects invalid or unbounded inputs',()=>{
  expect(()=>solveCapillary({...small,radiusUm:-1})).toThrow(/radius/);
  expect(()=>solveCapillary({...small,radialCells:10.5})).toThrow(/whole/);
  expect(()=>solveCapillary({...small,diffusivityUm2PerS:NaN})).toThrow();
  expect(()=>solveCapillary({...small,durationS:100,axialCells:2000,radialCells:64})).toThrow(/cell-steps/);
  expect(()=>solveCapillary(small,{...defaultSolverSettings,radialImplicitness:.2})).toThrow();
 });
 it('exports a deterministic research record with units, evidence category and limitations',async()=>{
  const a=await capillaryRecord(solveCapillary(small),'B','2026-10-29T00:00:00Z'),b=await capillaryRecord(solveCapillary(small),'B','2026-10-29T00:00:00Z');
  expect(a.reproducibility.contentSha256).toMatch(/^[0-9a-f]{64}$/);expect(a.reproducibility.contentSha256).toBe(b.reproducibility.contentSha256);
  expect(a.evidence.category).toBe('B');expect((a.inputs as any).radiusUm).toEqual({value:5,unit:'µm',description:'Capillary radius R'});
  expect(a.limitations.join(' ')).toMatch(/physiological/);expect(a.reproducibility.seed).toBeNull();
  expect((a.outputs as any).timeSeries.units.varianceM2).toBe('m²');
  const hypothesis=await capillaryRecord(solveCapillary(small),'D');expect(hypothesis.evidence.name).toBe('Parameterised hypothesis');
 },60000);
 it('computes the Aris coefficient analytically',()=>{const {peclet,effectiveDispersion}=taylorArisCoefficient(1e-6,1e-3,1e-9);expect(peclet).toBeCloseTo(1,12);expect(effectiveDispersion).toBeCloseTo(1e-9*(1+1/48),22);});
});
