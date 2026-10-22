import {describe,it,expect} from 'vitest';
import {presentationPostprocessing} from './presentationRendering';
describe('Complete Mol* presentation parameters',()=>{
 it('retains the nested SSAO fields required by the actual render pass',()=>{const p=presentationPostprocessing(true,true);expect(p.occlusion.params.multiScale.name).toBeDefined();expect(p.occlusion.params.blurDepthBias).toBeTypeOf('number');expect(p.occlusion.params.transparentThreshold).toBeTypeOf('number');expect(p.outline.name).toBe('on');});
 it('changes theme without mutating shared defaults',()=>{const paper=presentationPostprocessing(true,true);const night=presentationPostprocessing(false,false);expect(night.outline.name).toBe('off');expect(paper.outline.name).toBe('on');expect(night.occlusion.params.samples).toBe(16);});
});
