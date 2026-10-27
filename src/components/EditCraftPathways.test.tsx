import {describe,it,expect} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import EditCraftPathways,{parseGMT,pathwayResultExport} from './EditCraftPathways';
describe('explicit pathway input',()=>{
 it('retains exact collection identifiers without implicit gene mapping',()=>{
  expect(parseGMT('set_1\tProvided source\tG1\tg2')).toEqual([{id:'set_1',description:'Provided source',genes:['G1','g2']}]);
  expect(()=>parseGMT('set_1\tsource\tG1\tG1')).toThrow();expect(()=>parseGMT('set_1\tsource\tG1\nset_1\tsource\tG2')).toThrow();expect(()=>parseGMT('')).toThrow();
 });
 it('shows no enrichment or made-up universe before a completed result exists',()=>{
  const html=renderToStaticMarkup(<EditCraftPathways outputs={[]} onDraft={()=>{throw Error('No execution during rendering');}}/>);
  expect(html).toContain('No illustrative enrichment values');expect(html).toContain('Measured or testable background identifiers');expect(html).toContain('Collection license');expect(html).not.toContain('Computed membership enrichment');
 });
 it('makes each saved correction stage inspectable instead of hiding later results',()=>{
  const result={rows:[],selectedCount:3,backgroundCount:10,testedFamilySize:3,multipleTesting:'BH',collection:{name:'Synthetic finite reference',version:'1',organism:'Synthetic',identifierNamespace:'test'},scope:'Numerical reference only',collectionVerification:'Unverified biological attribution'};
  const html=renderToStaticMarkup(<EditCraftPathways outputs={['BH','BY'].map(method=>({operation:'pathway_enrichment',result:{...result,multipleTesting:method}}))} onDraft={()=>{}}/>);
  expect(html).toContain('Enrichment stage to inspect');expect(html).toContain('Stage 1');expect(html).toContain('Stage 2');expect(html).toContain('BY');
  expect(html).toContain('No observed overlap connects');
  expect(html).toContain('Export this exact pathway result');
 });
 it('exports the original saved stage without inventing missing background identifiers',()=>{
  const stage={operation:'pathway_enrichment',result:{method:'One-sided hypergeometric over-representation',rows:[{id:'set_1',overlapGenes:['g1'],adjustedPValue:.04}],backgroundSha256:'a'.repeat(64),sourceSha256:'b'.repeat(64)}};
  const payload=JSON.parse(pathwayResultExport(stage));
  expect(payload.savedStage).toEqual(stage);
  expect(payload.scope).toContain('not the complete background gene list');
  expect(()=>pathwayResultExport({operation:'pathway_enrichment'})).toThrow();
 });
});
