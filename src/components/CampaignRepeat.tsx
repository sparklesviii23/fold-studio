import {useState} from 'react';
import type {Job} from '../lib/types';
export default function CampaignRepeat({job,busy,onPrepare}:{job:Job;busy:boolean;onPrepare:(payload:{id:string;projectId:string;seed:number})=>Promise<void>}){
 const [seed,setSeed]=useState(String(job.data.preparation?.config?.campaign_seed??42));
 const value=Number(seed),valid=seed.trim()!==''&&Number.isInteger(value)&&value>=0&&value<=2147483647;
 return <details><summary>Prepare another run</summary><label>Repeat-run random seed<input type="number" min={0} max={2147483647} value={seed} onChange={e=>setSeed(e.target.value)} onBlur={()=>{if(valid)setSeed(String(value));}}/></label><p className="caption">Keeps the original target and scaffold files, selections and scientific filters. The seed change is recorded. This saves inputs; choose an execution backend afterward.</p><button className="button" disabled={busy||!valid} onClick={()=>onPrepare({id:job.id,projectId:job.project_id,seed:value})}>Save repeat-run inputs</button></details>;
}
