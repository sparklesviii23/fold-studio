import {describe,it,expect} from 'vitest';
import {fixedPositions,substitutions} from './evolution';
describe('Explicit mutation input',()=>{
 it('preserves a human-readable wild type and a 1-based sequence identity',()=>{
  expect(substitutions('d3a; K12E')).toEqual([{position:3,from:'D',to:'A'},{position:12,from:'K',to:'E'}]);
 });
 it('refuses ambiguous numbering, modified residues and conflicting substitutions',()=>{
  for(const s of ['D0A','3A','D3X','D3A,D3E','D3.5A',''])expect(()=>substitutions(s)).toThrow();
 });
 it('does not silently accept floating-point or structural residue identifiers as sequence indices',()=>{
  expect(fixedPositions('1, 2; 5')).toEqual([1,2,5]);
  for(const s of ['A:19','2.5','0','-3'])expect(()=>fixedPositions(s)).toThrow();
 });
});
