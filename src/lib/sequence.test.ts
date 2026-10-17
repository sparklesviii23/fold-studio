import {describe,it,expect} from 'vitest';
import {align,fasta,properties} from './sequence';
describe('scientific sequence operations',()=>{
 it('maps missing observed residues without assuming author offsets',()=>{const a=align('ACDEFGHIKL','DEFGH');expect(a.identity).toBe(1);expect(a.pairs).toEqual([[3,1],[4,2],[5,3],[6,4],[7,5]]);});
 it('links only identical residues across a mutation',()=>{const a=align('ACDEFGHIKL','ACDEYGHIKL');expect(a.identity).toBe(.9);expect(a.pairs).not.toContainEqual([5,5]);expect(a.pairs).toContainEqual([10,10]);});
 it('detects unrelated sequences',()=>{expect(align('AAAAAA','WWWWWW').identity).toBe(0);});
 it('handles insertion codes through sequence order rather than numeric offsets',()=>{const a=align('ACDEFGHIKL','ACDPEFGHIKL');expect(a.pairs).toContainEqual([4,5]);expect(a.pairs).toContainEqual([10,11]);});
 it('exports numbered selections as valid FASTA',()=>{expect(fasta('ANGPTL3 | 25-30','ACDEFG')).toBe('>ANGPTL3 | 25-30\nACDEFG\n');});
 it('subtracts condensation water for average mass',()=>{expect(properties('AA').mass).toBeCloseTo(160.173,3);expect(properties('AA').composition.A).toBe(2);expect(properties('AX').valid).toBe(false);});
});
import {residueCorrespondence} from './sequence';
describe('conservative residue correspondence',()=>{
 it('maps a unique short contiguous fragment',()=>expect(residueCorrespondence('ACDEFGHIKL','EFGH')).toEqual([[4,1],[5,2],[6,3],[7,4]]));
 it('rejects repeated ambiguous fragments',()=>expect(residueCorrespondence('ACDEACDE','ACDE')).toEqual([]));
 it('rejects unrelated short sequences with scattered matches',()=>expect(residueCorrespondence('ACDEFGHIKLMNPQRSTVWY','ADFL')).toEqual([]));
});
