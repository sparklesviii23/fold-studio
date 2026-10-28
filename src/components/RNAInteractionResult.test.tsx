import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import RNAInteractionResult from './RNAInteractionResult';
describe('RNA pair scientific interpretation',()=>{
 it('flags the actual historical no-pair sentinel without presenting it as an energy',()=>{
  const html=renderToStaticMarkup(<RNAInteractionResult stages={{unpairable:{operation:'rna_cofold',result:{complexMfeKcalMol:100000,interstrandPairs:[],version:'2.7.2'}}}}/>);
  expect(html).toContain('No intermolecular MFE available');expect(html).toContain('Historical adapter receipt');expect(html).not.toContain('Complex MFE 100000');
 });
 it('shows genuine returned pair energy separately and handles corrected unavailable values',()=>{
  const stages={paired:{operation:'rna_cofold',result:{complexMfeKcalMol:-19,deltaMfeRelativeToSeparateFoldsKcalMol:-19,interstrandPairs:[{sequenceAPosition:8,sequenceBPosition:1}],intermolecularMfeState:'interstrand_mfe_returned'}},unpaired:{operation:'rna_cofold',result:{complexMfeKcalMol:null,interstrandPairs:[],intermolecularMfeState:'no_interstrand_mfe_returned'}}};
  const html=renderToStaticMarkup(<RNAInteractionResult stages={stages}/>);expect(html).toContain('Complex MFE -19');expect(html).toContain('No intermolecular MFE available');expect(html).not.toContain('Historical adapter receipt');
 });
});
