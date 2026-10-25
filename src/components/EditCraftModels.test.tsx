import {describe,expect,it} from 'vitest';
import {renderToStaticMarkup} from 'react-dom/server';
import EditCraftModels,{modelRows,ModelResults} from './EditCraftModels';
describe('EditCraft scientific model contracts',()=>{
 it('keeps input identity and context sequences intact',()=>expect(modelRows('acgt\n\nGCAT')).toEqual([{id:'sequence_1',sequence:'ACGT'},{id:'sequence_2',sequence:'GCAT'}]));
 it('exposes supported editor choices without implying experimental qualification',()=>{
  const html=renderToStaticMarkup(<EditCraftModels baseEditing onDraft={()=>{}} outputs={[]}/>);
  expect(html).toContain('ABEmax');expect(html).toContain('BE4max');expect(html).toContain('PRIDICT2');expect(html).toContain('all five folds');expect(html).not.toContain('ABE8e');
 });
 it('preserves a negative guide score without turning it into a percentage',()=>{
  const html=renderToStaticMarkup(<ModelResults outputs={[{operation:'rs3_activity',result:{method:'Rule Set 3',units:'upstream score',scope:'sequence only',rows:[{id:'reference',context30mer:'ACGT',predictedActivity:-.90030944}]}}]}/>);
  expect(html).toContain('-0.9003');expect(html).toContain('Activity score');expect(html).not.toContain('%');
 });
});
