import {useEffect,useRef,useState} from 'react';
import {rpc} from '../lib/api';
import {graphEnvelope,initialGraph,type GraphState} from './graph';
export class DraftWriter {
 revision=0;recoveryAvailable=false;allowSnapshots=true;latest:GraphState=initialGraph();saved='';queue=Promise.resolve();
 constructor(readonly context:string,readonly write:(payload:any)=>Promise<any>,readonly status:(value:string)=>void){}
 snapshot(){
  this.recoveryAvailable=false;
  if(!this.allowSnapshots)throw new Error('Rejected original recovery is protected.');
  localStorage.setItem('fold-molecular-draft-v2:'+this.context,JSON.stringify({revision:this.revision,state:this.latest}));
  this.recoveryAvailable=true;
 }
 changed(s:GraphState){
  this.latest=s;
  try{this.snapshot();this.status(JSON.stringify(s)===this.saved?'Saved locally':'Saving…');}
  catch{this.status('Local recovery unavailable · saving to library…');}
 }
 flush(){
  this.queue=this.queue.catch(()=>{}).then(async()=>{
   const state=structuredClone(this.latest),serialized=JSON.stringify(state);
   if(serialized===this.saved){this.status('Saved locally');return;}
   this.status('Saving…');
   try{
    const result=await this.write({projectId:this.context==='local-practice'?undefined:this.context,revision:this.revision,state});
    this.revision=result.revision;this.saved=serialized;
    try{this.snapshot();}catch{}
    this.status(JSON.stringify(this.latest)===serialized?'Saved locally':'Newer edit queued…');
   }catch(e){this.status(this.recoveryAvailable?'Recovery snapshot retained · library sync failed':'Save failed · no local recovery snapshot');throw e;}
  });
  return this.queue;
 }
}
export function useDraft(projectId:string){
 const context=projectId||'local-practice',writer=useRef<DraftWriter|null>(null),[ready,setReady]=useState(false),[loaded,setLoaded]=useState<GraphState|null>(null),[status,setStatus]=useState('Loading…'),[error,setError]=useState(''),[recovery,setRecovery]=useState<GraphState|null>(null);
 useEffect(()=>{
  let active=true;
  const w=new DraftWriter(context,p=>rpc('molecular_draft_save',p),s=>active&&setStatus(s));writer.current=w;
  function local(){
   const raw=localStorage.getItem('fold-molecular-draft-v2:'+context);
   if(!raw)return null;
   try{const value=JSON.parse(raw);graphEnvelope(value.state);if(!Number.isInteger(value.revision)||value.revision<0)throw new Error('Invalid revision.');return value;}
   catch(e){
    try{localStorage.setItem('fold-molecular-rejected-v2:'+context,raw);}catch{w.allowSnapshots=false;}
    if(active)setError('Malformed local snapshot retained for recovery; it was not loaded. '+String(e));
    return null;
   }
  }
  rpc<any>('molecular_draft_load',{projectId:projectId||undefined}).then(result=>{
   if(!active)return;
   let state=result.state?graphEnvelope(result.state):initialGraph();w.revision=result.revision;
   const snapshot=local();
   if(snapshot){if(snapshot.revision===result.revision)state=snapshot.state;else if(JSON.stringify(snapshot.state)!==JSON.stringify(state))setRecovery(snapshot.state);}
   w.latest=state;w.saved=JSON.stringify(result.state??initialGraph());setLoaded(state);setReady(true);
   setStatus(JSON.stringify(state)===w.saved?'Saved locally':'Recovered local edit · saving…');
   if(result.migrationError)setError('Legacy draft retained; migration refused: '+result.migrationError);
  }).catch(e=>{
   if(!active)return;setError(String(e));setStatus('Library unavailable · local practice recovery');
   try{const snapshot=local(),state=snapshot?.state??initialGraph();w.latest=state;w.revision=snapshot?.revision??0;setLoaded(state);setReady(true);}
   catch{setLoaded(initialGraph());setReady(true);}
  });
  return()=>{active=false;w.flush().catch(()=>{});};
 },[context]);
 const change=(state:GraphState)=>writer.current?.changed(state);
 const flush=async()=>{try{const w=writer.current;if(w){do{await w.flush();}while(JSON.stringify(w.latest)!==w.saved);}}catch(e){setError(String(e));throw e;}};
 return {hasRecovery:()=>!!writer.current?.recoveryAvailable,ready,loaded,status,error,setError,recovery,setRecovery,change,flush};
}
