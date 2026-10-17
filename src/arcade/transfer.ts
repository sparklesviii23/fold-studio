import {isTauri} from '@tauri-apps/api/core';
import {emitTo,listen} from '@tauri-apps/api/event';
import type {Transfer} from './transferTypes';
export async function sendTransfer(t:Transfer){
 const requestId=crypto.randomUUID();let cleanup=()=>{};
 try{await new Promise<void>(async(resolve,reject)=>{
  const timer=setTimeout(()=>{cleanup();reject(new Error('The main workspace did not acknowledge the transfer. Keep it open, then try again; your saved peptide is safe.'));},15000);
  const receive=(p:any)=>{if(p?.requestId!==requestId)return;clearTimeout(timer);cleanup();p.error?reject(new Error(p.error)):resolve();};
  try{if(isTauri()){const unlisten=await listen<any>('fold-peptide-transfer-result',e=>receive(e.payload));cleanup=unlisten;await emitTo('main','fold-peptide-transfer',{...t,requestId});}
  else{const fn=(e:StorageEvent)=>{if(e.key==='fold-peptide-transfer-result')try{receive(JSON.parse(e.newValue??'null'));}catch{}};window.addEventListener('storage',fn);cleanup=()=>window.removeEventListener('storage',fn);localStorage.setItem('fold-peptide-transfer',JSON.stringify({...t,requestId}));}}
  catch(e){clearTimeout(timer);cleanup();reject(e);}
 });}finally{cleanup();}
}
