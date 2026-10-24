import {useEffect,useState} from 'react';
import {rpc} from '../lib/api';
export type ExecutionBackend={mode:'local'|'modal'|'vast';profileId?:string};
const listeners=new Set<(value:ExecutionBackend)=>void>();
export async function selectExecutionBackend(value:ExecutionBackend){const result=await rpc<ExecutionBackend>('execution_backend_select',value);listeners.forEach(fn=>fn(result));return result;}
export function useExecutionBackend(){const[value,setValue]=useState<ExecutionBackend>({mode:'local'});useEffect(()=>{listeners.add(setValue);rpc<ExecutionBackend>('execution_backend_get').then(setValue).catch(()=>{});return()=>{listeners.delete(setValue);};},[]);return value;}
export default function ExecutionBackendSelector(){
 const selected=useExecutionBackend();const[profiles,setProfiles]=useState<any[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{rpc<any>('gpu_profiles').then(v=>setProfiles(v.profiles)).catch(()=>{});},[]);
 async function choose(value:string){setBusy(true);setError('');try{const [mode,profileId]=value.split(':');await selectExecutionBackend({mode:mode as ExecutionBackend['mode'],...(profileId?{profileId}:{})});}catch(e){setError(String(e));}finally{setBusy(false);}}
 return <div className="bc-panel"><label>Execution backend<select aria-label="Execution backend" value={selected.mode==='vast'?`vast:${selected.profileId}`:selected.mode} disabled={busy} onChange={e=>choose(e.target.value)}><option value="local">LOCAL — Apple Metal</option><option value="modal">CLOUD — Modal NVIDIA</option>{profiles.map(p=><option key={p.id} value={`vast:${p.id}`}>CLOUD — Vast / SSH · {p.name}</option>)}</select></label><p className="caption">{selected.mode==='local'?'Local scientific engines are explicitly selected.':'Cloud-only scientific execution. Models, orchestration and analysis stay remote; unavailable stages stop with a blocker.'}</p>{error&&<p className="error" role="alert">{error}</p>}</div>;
}
