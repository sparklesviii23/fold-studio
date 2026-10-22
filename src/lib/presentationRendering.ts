import {ParamDefinition as PD} from 'molstar/lib/mol-util/param-definition';
import {SsaoParams} from 'molstar/lib/mol-canvas3d/passes/ssao';
import {OutlineParams} from 'molstar/lib/mol-canvas3d/passes/outline';
import {Color} from 'molstar/lib/mol-util/color';

// Mol* replaces mapped parameter groups; it does not deep-merge their defaults.
export function presentationPostprocessing(outline:boolean,paper:boolean){
 return {outline:outline?{name:'on' as const,params:{...PD.getDefaultValues(OutlineParams),scale:1,threshold:.33,color:Color(paper?0x625963:0x171c32),includeTransparent:true}}:{name:'off' as const,params:{}},occlusion:{name:'on' as const,params:{...PD.getDefaultValues(SsaoParams),samples:16,radius:4,bias:.8,blurKernelSize:15,resolutionScale:1}}};
}
