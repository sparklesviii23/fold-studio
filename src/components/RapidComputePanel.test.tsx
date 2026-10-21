import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import RapidComputePanel from './RapidComputePanel';
describe('RAPID scientific controls',()=>{
 it('requires explicit target transfer and separate model approval, without invented readiness',()=>{
  const html=renderToStaticMarkup(<RapidComputePanel profileId="fixture" projectId="project"/>);
  expect(html).toContain('Install / update RAPID Engine');
  expect(html).toContain('Download engine models');
  expect(html).toContain('Transfer this target to the selected server');
  expect(html).toContain('Reconnecting never submits another job');
  expect(html).toContain('Exact optimizer-step resume is not available');
  expect(html).toContain('ProteinMPNN · fixed-backbone redesign');
  expect(html).toContain('AlphaFold · held-out complex evaluation');
  expect(html).not.toContain('RTX 5090 Ready');
 });
});
