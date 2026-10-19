import {describe,it,expect} from 'vitest';
import {acceptedBinderFasta} from './campaignSequences';
describe('original accepted binder FASTA export',()=>{
 it('preserves sequence and separates every chain copy',()=>{expect(acceptedBinderFasta([{design:'actual_design_id',Binder_Sequence:'ACDE/FGHI'}])).toBe('>actual_design_id | binder chain 1\nACDE\n>actual_design_id | binder chain 2\nFGHI\n');});
 it('refuses missing, ambiguous or malformed source sequences and header injection',()=>{for(const rows of [[],[{design:'x',Binder_Sequence:'ACDX'}],[{design:'x',Binder_Sequence:'ACD/'}],[{design:'x\n>injected',Binder_Sequence:'ACD'}],[{design:'x'}]])expect(()=>acceptedBinderFasta(rows)).toThrow();});
 it('wraps long chains without changing residues',()=>{const sequence='ACDE'.repeat(30);const result=acceptedBinderFasta([{design:'x',Binder_Sequence:sequence}]);expect(result.split('\n').slice(1).join('')).toBe(sequence);expect(result.split('\n')[1]).toHaveLength(80);});
});
