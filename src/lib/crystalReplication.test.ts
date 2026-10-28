import {describe,it,expect} from 'vitest';
import {inspectUnitCell,type Vector3} from './crystalCell';
import {fractionalToCartesian,cartesianToFractional,replicateFractionalSites,replicationCif} from './crystalReplication';
const source=`data_analytic
_cell.length_a 2
_cell.length_b 3
_cell.length_c 4
_cell.angle_alpha 90
_cell.angle_beta 90
_cell.angle_gamma 90
loop_
_atom_site.label
_atom_site.type_symbol
_atom_site.fract_x
_atom_site.fract_y
_atom_site.fract_z
_atom_site.occupancy
Origin C 0.00(1) 0 0 0.5(1)
Boundary C 1 0 0 ?
`;
describe('reported fractional sites and translations',()=>{
 it('parses reported sites, uncertainties and unknown occupancy without completing chemistry',async()=>{
  const cell=await inspectUnitCell(source);
  expect(cell.fractionalSites?.state).toBe('reported');expect(cell.fractionalSites?.sites).toHaveLength(2);
  expect(cell.fractionalSites?.sites[0]).toMatchObject({sourceRow:1,label:'Origin',typeSymbol:'C',fractional:[0,0,0],reportedFractional:['0.00(1)','0','0'],occupancy:'0.5(1)'});
  expect(cell.fractionalSites?.sites[1].occupancy).toBe('?');
  expect(cell.fractionalSites?.scope).toContain('No symmetry expansion');
 });
 it('converts analytical nonorthogonal coordinates in both directions',()=>{
  const basis:[Vector3,Vector3,Vector3]=[[2,0,0],[1,3,0],[2,-1,4]];
  const fractional:Vector3=[-0.25,0.5,1.25],cartesian=fractionalToCartesian(fractional,basis);
  expect(cartesian).toEqual([2.5,.25,5]);
  cartesianToFractional(cartesian,basis).forEach((value,i)=>expect(value).toBeCloseTo(fractional[i],13));
  expect(()=>cartesianToFractional([1,2,3],[[1,0,0],[2,0,0],[0,0,1]])).toThrow('nondegenerate');
  expect(()=>fractionalToCartesian([Infinity,0,0],basis)).toThrow('finite');
 });
 it('retains boundary duplicates with exact source rows/translations and does not mutate source',async()=>{
  const cell=await inspectUnitCell(source),original=JSON.stringify(cell),result=replicateFractionalSites(cell,[2,1,1]);
  expect(result.sites).toHaveLength(4);expect(result.lengthsAngstrom).toEqual([4,3,4]);expect(result.volumeAngstromCubed).toBeCloseTo(48);
  expect(result.sites.map(site=>[site.sourceRow,site.translation])).toEqual([[1,[0,0,0]],[2,[0,0,0]],[1,[1,0,0]],[2,[1,0,0]]]);
  expect(result.sites[1].cartesianAngstrom[0]).toBe(2);expect(result.sites[2].cartesianAngstrom[0]).toBe(2);
  expect(result.sites[3].supercellFractional[0]).toBe(1);expect(new Set(result.sites.map(site=>site.generatedLabel)).size).toBe(4);
  expect(result.sites[0].occupancy).toBe('0.5(1)');expect(JSON.stringify(cell)).toBe(original);
  expect(result.parsedTextSha256).toBe(cell.parsedTextSha256);expect(result.scope).toContain('asymmetric unit');
 });
 it('exports a valid derived CIF with source-row mapping and no inferred space group',async()=>{
  const cell=await inspectUnitCell(source),result=replicateFractionalSites(cell,[2,1,1]),text=replicationCif(result);
  const parsed=await inspectUnitCell(text);expect(parsed.lengthsAngstrom).toEqual([4,3,4]);expect(parsed.fractionalSites?.sites).toHaveLength(4);expect(parsed.reportedSymmetry).toEqual({});
  const {CIF}=await import('molstar/lib/mol-io/reader/cif');const raw=await CIF.parse(text).run();if(raw.isError)throw Error(raw.message);
  const sites=raw.result.blocks[0].categories.atom_site;
  expect(Array.from({length:4},(_,i)=>sites.getField('fold_source_row')!.str(i))).toEqual(['1','2','1','2']);
  expect(Array.from({length:4},(_,i)=>sites.getField('fold_translation_a')!.str(i))).toEqual(['0','0','1','1']);
  expect(text).toContain(cell.parsedTextSha256);expect(text).not.toContain('P 1');
 });
 it('refuses missing axes, unavailable fractional origins, invalid occupancies and oversized replicas',async()=>{
  await expect(inspectUnitCell(source.replace('_atom_site.fract_z','_atom_site.unrelated'))).rejects.toThrow('three axes');
  await expect(inspectUnitCell(source.replace('0.5(1)','1.1'))).rejects.toThrow('occupancies');
  const cell=await inspectUnitCell(source);
  for(const repeats of [[0,1,1],[4,1,1],[1.5,1,1]] as Vector3[])expect(()=>replicateFractionalSites(cell,repeats)).toThrow('one to three');
  expect(()=>replicateFractionalSites({...cell,fractionalSites:{state:'unavailable',sites:[],scope:'No fractional origin inferred'}},[1,1,1])).toThrow('required');
  const sites=Array.from({length:5000},(_,i)=>({...cell.fractionalSites!.sites[0],sourceRow:i+1}));
  expect(()=>replicateFractionalSites({...cell,fractionalSites:{state:'reported',sites,scope:''}},[3,3,3])).toThrow('20,000');
 });
});
