import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import EditCraftOfftargets,{OfftargetResults,ReferenceWindowResults} from './EditCraftOfftargets';
describe('off-target scientific scope in native forms',()=>{
 it('requires real input and makes no launch or genome-wide promise for inline FASTA',()=>{
  const html=renderToStaticMarkup(<EditCraftOfftargets references={[]} outputs={[]} onDraft={()=>{throw Error('Render must not launch');}} onPrepareReference={async()=>{throw Error('Render must not download');}}/>);
  expect(html).toContain('My supplied FASTA');expect(html).toContain('does not make it a genome-wide search');expect(html).toMatch(/disabled="">Prepare off-target search/);
 });
 it('preserves forward-coordinate intervals and distinct exact matches',()=>{
  const html=renderToStaticMarkup(<OfftargetResults outputs={[{operation:'cas_offinder',result:{method:'Cas-OFFinder 2.4.1',siteCount:1,reference:{assembly:'synthetic-v1',coverage:'supplied_sequence_only'},parameters:{mismatches:0,pam:'NGG'},rows:[{guideId:'g1',contig:'circle',intervals:[{start:13,end:23},{start:1,end:12}],wrapsOrigin:true,strand:'-',mismatches:0,mismatchPositions:[],sequence5to3:'ACGT'}],rawOutputTSV:'original-output',scope:'Sequence matches only'}}]}/>);
  expect(html).toContain('13–23 / 1–12');expect(html).toContain('origin crossing');expect(html).toContain('exact spacer match');expect(html).toContain('Supplied sequence only');expect(html).toContain('original-output');
 });
 it('labels actual complete-assembly receipts without implying activity probabilities',()=>{
  const html=renderToStaticMarkup(<OfftargetResults outputs={[{operation:'cas_offinder',result:{method:'Cas-OFFinder 2.4.1',siteCount:0,reference:{assembly:'GCF_000005845.2',coverage:'complete_assembly'},parameters:{mismatches:0,pam:'NGG'},rows:[],rawOutputTSV:'',scope:'No cutting probability inferred.'}}]}/>);
  expect(html).toContain('Verified complete assembly');expect(html).toContain('No cutting probability inferred');expect(html).toContain('successful upstream calculation');
 });
 it('reports an actual strand-aware reference window separately from predictions',()=>{
  const html=renderToStaticMarkup(<ReferenceWindowResults outputs={[{operation:'reference_window',result:{reference:{assembly:'GCF_000005845.2'},contig:'NC_000913.3',start:10,end:13,strand:-1,sequence:'ACGT',scope:'Observed reference bases'}}]}/>);
  expect(html).toContain('REFERENCE ASSEMBLY BASES');expect(html).toContain('10–13');expect(html).toContain('Observed reference bases');expect(html).toContain('ACGT');
 });
});
