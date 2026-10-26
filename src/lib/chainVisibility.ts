import type {EngineModel} from './engineScene';
export interface ChainVisibility {modelId:string;instance:string;geometry:string;chain:string;atoms:[string,boolean][];ribbons:[string,boolean][]}
export function chainTarget(modelId:string,chain:string){if(!/^\d+(\.\d+)*$/.test(modelId)||! /^[A-Za-z0-9_]+$/.test(chain))throw new Error('Use the native console for this chain identifier.');return '#'+modelId+'/'+chain;}
export function rememberChainVisibility(model:EngineModel,chain:string):ChainVisibility{
 chainTarget(model.id,chain);const atoms=model.atoms.filter(a=>a.chain===chain);if(!atoms.length)throw new Error('This chain is absent from the native scene.');
 const ribbons=new Map<string,boolean>();for(const a of atoms)ribbons.set(a.spec.split('@')[0],a.ribbonShown);
 return {modelId:model.id,instance:model.instance,geometry:model.geometry,chain,atoms:atoms.map(a=>[a.spec,a.shown]),ribbons:[...ribbons]};
}
export function restoreChainVisibility(model:EngineModel,saved:ChainVisibility):string[]{
 const target=chainTarget(model.id,saved.chain);
 if(model.id!==saved.modelId||model.instance!==saved.instance||model.geometry!==saved.geometry)throw new Error('The chain geometry changed. Choose its representation again before restoring visibility.');
 const commands:string[]=[];
 for(const [kind,states] of [['atoms',saved.atoms],['cartoons',saved.ribbons]] as const){
  // Set the majority once, then restore exceptions in bounded command batches.
  const show=states.filter(([,on])=>on).length>states.length/2;commands.push((show?'show ':'hide ')+target+' '+kind);
  const exceptions=states.filter(([,on])=>on!==show).map(([spec])=>{if(/[;\s\n\r]/.test(spec))throw new Error('A native atom selector requires console inspection.');return spec;});
  for(let i=0;i<exceptions.length;i+=128)commands.push((show?'hide ':'show ')+exceptions.slice(i,i+128).join('|')+' '+kind);
 }
 return commands;
}
