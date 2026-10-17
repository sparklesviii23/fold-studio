import {isTauri} from '@tauri-apps/api/core';
import {listen,emitTo} from '@tauri-apps/api/event';
import {WebviewWindow} from '@tauri-apps/api/webviewWindow';
let opening:Promise<void>|null=null;
async function switchContext(projectId:string){
 const requestId=crypto.randomUUID();let resolve!:()=>void,reject!:(e:Error)=>void;
 const result=new Promise<void>((yes,no)=>{resolve=yes;reject=no;});
 const receive=(p:any)=>{if(p?.requestId!==requestId)return;p.error?reject(new Error(p.error)):resolve();};
 let cleanup:()=>void;
 if(isTauri())cleanup=await listen<any>('fold-arcade-context-result',e=>receive(e.payload));
 else{const fn=(e:StorageEvent)=>{if(e.key==='fold-arcade-context-result')try{receive(JSON.parse(e.newValue??'null'));}catch{}};window.addEventListener('storage',fn);cleanup=()=>window.removeEventListener('storage',fn);}
 const timer=setTimeout(()=>reject(new Error('Arcade kept its current project because the context change was not acknowledged. Bring it forward and try again.')),12000);
 try{if(isTauri())await emitTo('arcade','fold-arcade-context',{requestId,projectId});else localStorage.setItem('fold-arcade-context',JSON.stringify({requestId,projectId}));await result;}
 finally{clearTimeout(timer);cleanup();}
}
/** Serialized factory: rapid requests reuse the label and await draft/context acknowledgments. */
export function openArcade(projectId=''):Promise<void>{
 if(opening)return opening.then(()=>openArcade(projectId));
 opening=(async()=>{
  const url='index.html?arcade=1&project='+encodeURIComponent(projectId);
  if(!isTauri()){
   const existing=window.open('','fold-arcade');
   if(existing?.location.href.includes('arcade=1')){existing.focus();await switchContext(projectId);}
   else if(existing)existing.location.href='/?arcade=1&project='+encodeURIComponent(projectId);
   return;
  }
  const existing=await WebviewWindow.getByLabel('arcade');
  if(existing){await existing.show();await existing.setFocus();await switchContext(projectId);return;}
  let resolveReady!:()=>void,rejectReady!:(e:Error)=>void;
  const ready=new Promise<void>((yes,no)=>{resolveReady=yes;rejectReady=no;});
  const stopReady=await listen('fold-arcade-ready',()=>resolveReady());
  const timer=setTimeout(()=>rejectReady(new Error('Arcade opened but did not acknowledge readiness. Bring its window forward and retry.')),20000);
  try{
   const w=new WebviewWindow('arcade',{url,title:'Molecular Arcade · FOLD STUDIO',width:1360,height:900,minWidth:980,minHeight:690,titleBarStyle:'overlay',hiddenTitle:true,backgroundColor:'#071326'});
   const created=new Promise<void>((resolve,reject)=>{w.once('tauri://created',()=>resolve());w.once('tauri://error',e=>reject(new Error(String(e.payload))));});
   await Promise.all([created,ready]);
  }finally{clearTimeout(timer);stopReady();}
 })().finally(()=>opening=null);
 return opening;
}
