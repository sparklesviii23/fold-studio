import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import BiologyGuidedDesign from './BiologyGuidedDesign';
describe('Biology-guided workspace scientific boundaries',()=>{
 it('distinguishes saved proposals, actual compute and separately billed API operations',()=>{
  const html=renderToStaticMarkup(<BiologyGuidedDesign projectId="fixture" structures={[]}/>);
  expect(html).toContain('Automated multi-engine evolution remains in development');
  expect(html).toContain('No concatenation or shared binding pose');
  expect(html).toContain('Allow external sequence upload for a cost estimate');
  expect(html).toContain('Approve this external paid run after reviewing its quote');
  expect(html).toContain('external service bills separately from Vast and Modal');
  expect(html).not.toContain('GPU ready');
  expect(html).not.toContain('validated binder');
 });
});
