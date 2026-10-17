import { describe, expect, it } from 'vitest';
import { confidenceResidues } from './confidenceSelection';
import type { Residue } from './types';
function residues(sequence:string):Residue[]{return [...sequence].map((one,index)=>({chain:'A',authChain:'A',label:index+1,auth:index+42,insertion:index===1?'B':'',name:'',one,xyz:[0,0,0],bFactor:90,unit:1,index}));}
describe('prediction token to coordinate selection',()=>{
 it('retains author numbering and insertion codes instead of using token numbers as atom identities',()=>{const rr=residues('AGSTL');expect(confidenceResidues('AGSTL',rr,[2,5])).toEqual([rr[1],rr[4]]);expect(confidenceResidues('AGSTL',rr,[2])[0].insertion).toBe('B');});
 it('rejects repeated fragment correspondence',()=>{expect(()=>confidenceResidues('AGAG',residues('AG'),[1])).toThrow('no verified');});
 it('rejects chain and model ambiguity',()=>{const rr=residues('AG');rr[1].unit=2;expect(()=>confidenceResidues('AG',rr,[1])).toThrow('unambiguous');});
 it('rejects noninteger, missing and mismatched tokens',()=>{expect(()=>confidenceResidues('AG',residues('AG'),[NaN])).toThrow();expect(()=>confidenceResidues('AG',residues('AA'),[2])).toThrow();});
});
