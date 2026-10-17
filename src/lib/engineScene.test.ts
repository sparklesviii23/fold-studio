import {describe,it,expect} from 'vitest';
import {validateScene,chartAtom,nativeSelectionSpec,nativeCamera,rgb,type EngineScene,type EngineModel,type EngineAtom} from './engineScene';
const atom=()=>({key:'atom:123',spec:'#7/B:32A@CA',index:0,chain:'B',labelChain:'C1',residue:32,label:1,insertion:'A',residueName:'LYS',atom:'CA',element:'C',serial:55,altLoc:'B',xyz:[1,2,3],bFactor:27,occupancy:0.5,radius:1.7,color:[255,0,255,128],ribbonColor:[0,255,255,255],shown:true,ribbonShown:true,style:1,selected:true,secondaryStructure:1} as EngineAtom);
const model=()=>({id:'7',instance:'987',atoms:[atom()],bonds:[],display:true} as unknown as EngineModel);
const scene=()=>({schemaVersion:1,sessionId:'real',engineGui:false,models:[model()]} as EngineScene);
describe('authoritative scientific scene transport',()=>{
 it('retains author numbering, insertion, alternate location and model identity',()=>{const a=chartAtom(atom(),model(),3);expect(a).toMatchObject({auth:32,label:1,insertion:'A',altLoc:'B',nativeModelId:'7',nativeSpec:'#7/B:32A@CA',xyz:[1,2,3],bFactor:27,occupancy:0.5});expect(nativeSelectionSpec([a],[a.key])).toBe('#7/B:32A@CA');});
 it('maps exact engine colour bytes',()=>{expect(rgb([255,0,255,128])).toBe(0xff00ff);expect(rgb([0,255,255,255])).toBe(0x00ffff);});
 it('rejects GUI sessions and unsupported schemas',()=>{expect(()=>validateScene({...scene(),engineGui:true})).toThrow();expect(()=>validateScene({...scene(),schemaVersion:2} as any)).toThrow();});
 it('rejects duplicate native identities and nonfinite coordinates',()=>{const s=scene();s.models!.push(model());expect(()=>validateScene(s)).toThrow();const t=scene();t.models![0].atoms[0].xyz[1]=NaN;expect(()=>validateScene(t)).toThrow();});
 it('rejects invalid native bonds and colour values',()=>{const s=scene();s.models![0].bonds=[{a:0,b:8,radius:0.2,shown:true}];expect(()=>validateScene(s)).toThrow();const t=scene();t.models![0].atoms[0].color[1]=256;expect(()=>validateScene(t)).toThrow();});
 it('uses the native camera basis and field of view',()=>{const s={...scene(),camera:{name:'mono',matrix:[[1,0,0,4],[0,1,0,5],[0,0,1,6]],position:[4,5,6],target:[0,0,0],fieldOfView:30}} as EngineScene;expect(nativeCamera(s)).toMatchObject({up:[0,1,0],position:[4,5,6],fov:Math.PI/6,mode:'perspective'});});
});
