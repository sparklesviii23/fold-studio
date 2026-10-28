import {describe,it,expect} from 'vitest';
import {interplanarSpacing} from './crystalPlanes';
describe('reciprocal-plane spacing',()=>{
 it('matches cubic spacing and rejects the undefined origin plane',()=>{
  const cell:any={latticeVectorsAngstrom:[[4,0,0],[0,4,0],[0,0,4]],parsedTextSha256:'source'};
  expect(interplanarSpacing(cell,[1,1,1]).spacingAngstrom).toBeCloseTo(4/Math.sqrt(3),12);
  expect(()=>interplanarSpacing(cell,[0,0,0])).toThrow();expect(()=>interplanarSpacing(cell,[.5,1,0])).toThrow();
 });
 it('uses the dual metric for a nonorthogonal cell',()=>{
  const cell:any={latticeVectorsAngstrom:[[2,0,0],[1,3,0],[2,-1,4]],parsedTextSha256:'source'};
  const result=interplanarSpacing(cell,[1,0,0]);
  expect(result.spacingAngstrom).toBeCloseTo(1/Math.hypot(.5,-1/6,-7/24),12);
  expect(result.scope).toContain('No plane-family equivalence');
 });
});
