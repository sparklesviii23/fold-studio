import {describe,expect,it} from 'vitest';
import {pairedPositions,partners,type RnaResult} from './qwenRna';
describe('RNA position identity',()=>{
 it('keeps public positions one based through pair inspection',()=>{
  expect(pairedPositions('((....))')).toEqual([[2,7],[1,8]]);
  const result={basePairProbabilities:[[1,8,.7],[2,8,.1],[3,7,.4]]} as RnaResult;
  expect(partners(result,8)).toEqual([{position:1,probability:.7},{position:2,probability:.1}]);
 });
 it('refuses malformed folds instead of shifting bases',()=>{
  expect(()=>pairedPositions('(..')).toThrow();expect(()=>pairedPositions('..]')).toThrow();
 });
});
