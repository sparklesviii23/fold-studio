import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import ModalComputePanel,{generatorDesign} from './ModalComputePanel';

describe('Full Fab cloud configuration',()=>{
 it('retains the original scaffold protocol without applying a peptide length',()=>{
  expect(generatorDesign('Fab',20)).toEqual({modality:'Fab',count:1,attempts:1});
  expect(generatorDesign('peptide',20)).toEqual({modality:'peptide',lengths:[20],count:1,attempts:1});
 });
 it('exposes a separately reviewed cloud format and preserves approval controls',()=>{
  const html=renderToStaticMarkup(<ModalComputePanel projectId="fixture" structures={[]}/>);
  expect(html).toContain('Full Fab · cloud-only');
  expect(html).toContain('Review campaign · no upload or GPU');
  expect(html).toContain('Approve transferring');
  expect(html).toContain('full workload');
 });
 it('opens Fab configuration directly with the complete-scaffold format and no length input',()=>{
  const html=renderToStaticMarkup(<ModalComputePanel initialFab projectId="fixture" structures={[]}/>);
  expect(html).toContain('value="Fab" selected=""');
  expect(html).toContain('Original full heavy/light scaffold with constant domains');
  expect(html).not.toContain('Generated binder length');
 });
});
