import {describe,expect,it} from 'vitest';
import {moveStage,validOrder} from './EditCraftWorkflow';
const stages=[{id:'gene',operation:'gene_context',parameters:{}},{id:'cds',operation:'sequence_analyze',inputFrom:'gene',parameters:{}},{id:'rna',operation:'rna_ensemble',inputFrom:'cds',parameters:{}}];
describe('scientific workflow edits',()=>{
 it('preserves typed dependencies during reorder',()=>{expect(validOrder(stages)).toBe(true);expect(moveStage(stages,1,-1)).toBeNull();expect(moveStage(stages,1,1)).toBeNull();});
 it('allows unrelated stages to be rearranged without mutating original input',()=>{const free=stages.map(({inputFrom,...stage})=>stage);const moved=moveStage(free,0,1);expect(moved?.map(s=>s.id)).toEqual(['cds','gene','rna']);expect(free[0].id).toBe('gene');});
 it('rejects an unsupported scientific conversion',()=>expect(validOrder([stages[0],{...stages[2],inputFrom:'gene'}])).toBe(false));
});
