import {describe,it,expect} from 'vitest';
import {rnaFeatures} from './rnaTopology';
describe('display topology from saved RNA dot bracket',()=>{
 it('identifies contiguous paired stems and hairpin nucleotides without inventing pairs',()=>{const f=rnaFeatures('((...))');expect(f.find(f=>f.kind==='stem')).toMatchObject({positions:[1,2,6,7],pairs:[[1,7],[2,6]]});expect(f.find(f=>f.kind==='hairpin')?.positions).toEqual([3,4,5]);});
 it('distinguishes one-sided bulges from two-sided internal loops',()=>{expect(rnaFeatures('((.((...))))').filter(f=>f.kind==='bulge')).toHaveLength(1);expect(rnaFeatures('((.((...)).))').filter(f=>f.kind==='internal loop')).toHaveLength(1);});
 it('identifies a multiloop and external unpaired residues',()=>{const f=rnaFeatures('.((..((...))..((...))..)).');expect(f.find(f=>f.kind==='multiloop')?.positions).toEqual([4,5,13,14,22,23]);expect(f.find(f=>f.kind==='external loop')?.positions).toEqual([1,26]);});
 it('handles unpaired RNA and refuses unsupported or corrupt structures',()=>{expect(rnaFeatures('....')).toEqual([{id:'external',kind:'external loop',positions:[1,2,3,4],pairs:[]}]);for(const bad of ['((..)',']..['])expect(()=>rnaFeatures(bad)).toThrow();});
});
