import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import GenomeEvidence from './GenomeEvidence';
describe('attributed gene evidence',()=>{
 it('requires exact context and does not display invented essentiality',()=>{
  const html=renderToStaticMarkup(<GenomeEvidence projectId="p" reference={{id:'r'}} feature={{type:'gene',attributes:{ID:'gene-1'}}}/>);
  expect(html).toContain('gene-1');expect(html).toContain('Import attributed evidence CSV');expect(html).toContain('no essentiality is inferred');expect(html).not.toContain('essential gene');
 });
});
