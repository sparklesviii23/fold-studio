import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import GenomeLaboratory from './GenomeLaboratory';
describe('local genome inspection entry point',()=>{
 it('requires attributed local input and does not invent annotation or start RNA compute',()=>{
  const html=renderToStaticMarkup(<GenomeLaboratory projectId="isolated" onRNA={()=>{throw Error('No RNA job during render');}}/>);
  expect(html).toContain('Genome &amp; RNA Laboratory');expect(html).toContain('Choose reference FASTA');expect(html).toContain('Choose optional GFF3');expect(html).toContain('No genes or essentiality evidence are inferred');expect(html).toContain('without analysis or cloud upload');
 });
});
