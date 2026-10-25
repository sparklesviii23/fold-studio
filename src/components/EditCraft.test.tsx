import {afterEach,describe,expect,it,vi} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import EditCraft,{evidenceLabel,transcriptTrack} from './EditCraft';
afterEach(()=>vi.unstubAllGlobals());
describe('native EditCraft workspace',()=>{
 it('offers one integrated navigation destination and explicit cloud approval controls',()=>{
  vi.stubGlobal('localStorage',{getItem:()=>null,setItem:()=>{}});
  const html=renderToStaticMarkup(<EditCraft projectId="fixture" structures={[]} onOpen={()=>{}} onRefresh={()=>{}}/>);
  expect(html).toContain('GENOME &amp; RNA ENGINEERING');expect(html).toContain('Research Notebook');expect(html).toContain('Workflow Studio');expect(html).toContain('No GPU or trained checkpoints');expect(html).not.toContain('99% editing efficiency');
 });
 it('lets the shared inspector control hide the domain inspector',()=>{
  vi.stubGlobal('localStorage',{getItem:()=>null,setItem:()=>{}});
  const html=renderToStaticMarkup(<EditCraft projectId="fixture" inspectorOpen={false} structures={[]} onOpen={()=>{}} onRefresh={()=>{}}/>);
  expect(html).toContain('no-inspector');expect(html).not.toContain('Deploy reviewed CPU worker');
 });
 it('keeps exon rendering inclusive for a single-base exon',()=>{
  const [exon]=transcriptTrack({Exon:[{id:'e',start:101,end:101}]},101,200);
  expect(exon.x).toBe(20);expect(exon.width).toBeCloseTo(9.2);
 });
 it('preserves the distinction between hypotheses and measurements',()=>{
  expect(evidenceLabel('hypothesis')).toBe('Research hypothesis');expect(evidenceLabel('experimental_observation')).toBe('Experimental observation');expect(evidenceLabel('invented')).toBe('Unresolved evidence');
 });
});
