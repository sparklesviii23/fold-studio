import { invoke, isTauri } from '@tauri-apps/api/core';
import { open, save } from '@tauri-apps/plugin-dialog';
import { openUrl } from '@tauri-apps/plugin-opener';
export interface VisualReceipt {state:'synchronized'|'partial'|'failed'|'not_rendered';revision?:string;models?:number;atoms?:number;meshes?:number;details?:string;unsupported?:string[]}
let sink:(()=>Promise<VisualReceipt>)|undefined,flushCamera:(()=>Promise<void>)|undefined;
let mutations:Promise<unknown>=Promise.resolve();
let delegate:((action:string,payload:unknown)=>Promise<any>)|undefined;
export function registerScientificDelegate(send:(action:string,payload:unknown)=>Promise<any>){delegate=send;return()=>{if(delegate===send)delegate=undefined;};}
const changes=new Set(['intelligence_overlay','intelligence_overlay_mix','intelligence_prepare','chimerax_execute','chimerax_open','chimerax_python','chimerax_selection','chimerax_select','chimerax_session_restore','comparison_run']);
export function registerScientificViewer(update:()=>Promise<VisualReceipt>,camera:()=>Promise<void>){sink=update;flushCamera=camera;return()=>{if(sink===update){sink=undefined;flushCamera=undefined;}};}
export async function refreshScientificScene(){return sink?await sink():{state:'not_rendered',details:'Open the Molecular Laboratory to display engine results.'} as VisualReceipt;}
async function backend<T>(action:string,payload:unknown):Promise<T>{
  if(isTauri())return invoke<T>('scientific',{action,payload});
  const token=import.meta.env.DEV?import.meta.env.VITE_FOLD_DEV_TOKEN:null;
  if(!token)throw new Error('Open the FOLD desktop app to use the scientific engine.');
  const response=await fetch('/api/scientific',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify({action,payload})});
  const body=await response.json();if(body.error)throw new Error(body.error);return body.result;
}
export async function rpc<T=any>(action:string,payload:unknown={}):Promise<T>{
  if(delegate)return delegate(action,payload);
  if(!changes.has(action))return backend<T>(action,payload);
  const operation=mutations.catch(()=>{}).then(async()=>{
    if(flushCamera)await flushCamera();
    const result=await backend<any>(action,payload);
    if(result?.state!=='review_required'){
      try{result.visualSync=await refreshScientificScene();}
      catch(error){result.visualSync={state:'failed',details:String(error)};}
      if(result.historyId&&(payload as any)?.projectId){await backend('console_sync',{id:result.historyId,projectId:(payload as any).projectId,status:result.visualSync.state+(result.visualSync.details?' · '+result.visualSync.details:'')});}
    }
    return result;
  });mutations=operation;return operation;
}
export async function chooseSave(defaultPath:string):Promise<string|null>{if(isTauri())return save({defaultPath});throw new Error('Save files from the native FOLD app.');}
export async function chooseFile(extensions:string[]):Promise<string|null>{if(!isTauri())throw new Error('Import files from the native FOLD app.');const path=await open({multiple:false,directory:false,filters:[{name:'Scientific files',extensions}]});return typeof path==='string'?path:null;}
export async function exportFile(name:string,content:{text?:string;base64?:string;asset?:string}){
  if(isTauri()){const path=await chooseSave(name);if(path)await rpc('export_file',{path,...content});}
  else if(import.meta.env.DEV)await rpc('preview_export',{name,...content});
}
export async function exportConfidence(structureId:string,kind:string):Promise<boolean>{
  if(isTauri()){const path=await chooseSave('fold-confidence-'+kind+'.json');if(!path)return false;await rpc('confidence_export',{structureId,kind,path});}
  else if(import.meta.env.DEV)await rpc('preview_confidence_export',{structureId,kind});
  else throw new Error('Open FOLD to export verified confidence data.');return true;
}
export async function external(url:string){if(isTauri())await openUrl(url);else window.open(url,'_blank','noopener,noreferrer');}
export function proteinName(p:any):string{return p.proteinDescription?.recommendedName?.fullName?.value??p.proteinDescription?.submissionNames?.[0]?.fullName?.value??p.uniProtkbId??p.primaryAccession;}
export function geneName(p:any):string{return p.genes?.[0]?.geneName?.value??p.primaryAccession;}

export async function chooseDirectory():Promise<string|null>{if(!isTauri())throw new Error("Choose folders from the native FOLD app.");const path=await open({multiple:false,directory:true});return typeof path==="string"?path:null;}

export async function chooseSSHKey():Promise<string|null>{if(!isTauri())throw new Error("Choose a key from the native fold app.");const path=await open({multiple:false,directory:false,title:"Choose an existing SSH private key"});return typeof path==="string"?path:null;}
