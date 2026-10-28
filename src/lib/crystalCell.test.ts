import {describe,it,expect} from 'vitest';
import {readFileSync} from 'node:fs';
import {inspectUnitCell,cellGeometry,cifMeasuredNumber,type Vector3} from './crystalCell';
const cif=(values=['10','10','10','90','90','90'])=>'data_reference\n'+['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma'].map((field,i)=>`_cell.${field} ${values[i]}`).join('\n')+'\n';
describe('reported crystallographic cell',()=>{
 it('inspects the preserved genuine 1BNA DNA crystal reference without changing its source',async()=>{
  const text=readFileSync(new URL('../../fixtures/nucleic-acids/1BNA.cif',import.meta.url),'utf8'),sha='76d550f32963de46f4f3c63caacb530f91a24f333fbc4312766d240b14e8cf30';
  const result=await inspectUnitCell(text,sha);
  expect(result.lengthsAngstrom).toEqual([24.87,40.39,66.2]);expect(result.anglesDegrees).toEqual([90,90,90]);expect(result.volumeAngstromCubed).toBeCloseTo(24.87*40.39*66.2,8);
  expect(result.reportedSymmetry['_symmetry.space_group_name_H-M']).toBe('P 21 21 21');expect(result.reportedSymmetry['_symmetry.Int_Tables_number']).toBe('19');expect(result.parsedTextSha256).toBe(sha);
  expect(result.fractionalSites?.state).toBe('unavailable');expect(result.fractionalSites?.scope).toContain('not converted implicitly');
 });
 it('reads an actual CIF scalar category, uncertainty notation and quoted symmetry with provenance',async()=>{
  const text=cif(['10.0(2)','10','10','90','90','90'])+"_symmetry.space_group_name_H-M 'P 1'\n_symmetry.Int_Tables_number 1\n";
  const result=await inspectUnitCell(text,'a'.repeat(64));
  expect(result.volumeAngstromCubed).toBeCloseTo(1000,10);expect(result.reportedCellValues.length_a).toBe('10.0(2)');expect(result.lengthsAngstrom).toEqual([10,10,10]);
  expect(result.reportedSymmetry['_symmetry.space_group_name_H-M']).toBe('P 1');expect(result.recordedSourceSha256).toBe('a'.repeat(64));expect(result.parsedTextSha256).toMatch(/^[a-f0-9]{64}$/);expect(result.scope).toContain('not independently determined');
  expect(result.latticeVectorsAngstrom[1][0]).toBeCloseTo(0,12);expect(result.latticeVectorsAngstrom[2][2]).toBeCloseTo(10,12);
 });
 it('recovers triclinic vectors and volume from independently constructed vectors',()=>{
  const a:Vector3=[2,0,0],b:Vector3=[1,3,0],c:Vector3=[2,-1,4];
  const length=(x:Vector3)=>Math.hypot(...x),angle=(x:Vector3,y:Vector3)=>Math.acos(x.reduce((s,v,i)=>s+v*y[i],0)/(length(x)*length(y)))*180/Math.PI;
  const result=cellGeometry([length(a),length(b),length(c)],[angle(b,c),angle(a,c),angle(a,b)]);
  expect(result.volumeAngstromCubed).toBeCloseTo(24,12);
  for(const [i,vector] of [a,b,c].entries())for(let j=0;j<3;j++)expect(result.latticeVectorsAngstrom[i][j]).toBeCloseTo(vector[j],12);
 });
 it('supports nominal uncertainty/exponent syntax and rejects unsupported or invalid geometry',()=>{
  for(const text of ['1.23(4)e2','1.23e2(4)'])expect(cifMeasuredNumber(text)).toBe(123);
  for(const text of ['?','.','NaN','Infinity','12garbage','1.2(3)e2(4)'])expect(()=>cifMeasuredNumber(text)).toThrow();
  for(const [lengths,angles] of [[[0,1,1],[90,90,90]],[[1,1,1],[0,90,90]],[[1,1,1],[10,10,170]],[[1e200,1e200,1e200],[90,90,90]]] as [Vector3,Vector3][])expect(()=>cellGeometry(lengths,angles)).toThrow();
 });
 it('does not invent cells or silently choose ambiguous cells',async()=>{
  await expect(inspectUnitCell('data_no_cell\n_entry.id X\n')).rejects.toThrow('no reported unit cell');
  await expect(inspectUnitCell(cif(['?','10','10','90','90','90']))).rejects.toThrow('missing');
  await expect(inspectUnitCell(cif()+'\ndata_second\n_cell.length_a 5\n')).rejects.toThrow('Multiple');
  await expect(inspectUnitCell('x'.repeat(20*1024**2+1))).rejects.toThrow('20 MiB');
 });
 it('supports a single-row loop without reading cell-like tags inside descriptive text',async()=>{
  const text='data_loop\n_struct.title\n;\n_cell.length_a 999\n;\nloop_\n'+['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma'].map(field=>'_cell.'+field).join('\n')+'\n2 3 4 90 90 90\n';
  expect((await inspectUnitCell(text)).volumeAngstromCubed).toBeCloseTo(24,12);
 });
});
