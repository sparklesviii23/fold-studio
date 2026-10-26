import type {Job} from '../lib/types';

export default function FabCampaignControls({job,busy,onCloud}:{job:Job;busy:boolean;onCloud?:()=>void}){
 const memory=job.data.memoryExecution?.telemetry,stage=job.data.memoryExecution?.stage;
 const samples=memory?.latestSamples??[],latest=samples[samples.length-1];
 return <>
  <p className="caption">Full Fab is cloud-only. Complete heavy/light chains, constant domains, original scientific settings and historical outcomes are preserved. Local generation, optimization, SSD offload and local campaign recovery are disabled. Review a separate cloud campaign before any upload or paid execution.</p><button className="button" disabled={busy||!onCloud} onClick={onCloud}>Configure Fab in Cloud Compute</button>
  {memory&&<p className="caption">Historical local Fab worker · {latest?`${(latest.physicalFootprintBytes/1024**3).toFixed(2)} GiB ${job.state==='running'?'current':'last observed'} · `:''}{typeof memory.peakFootprintBytes==='number'?`${(memory.peakFootprintBytes/1024**3).toFixed(2)} GiB peak · `:''}historical 14 GiB limit{typeof stage?.completedGradients==='number'?` · ${stage.completedGradients} gradient calculations completed`:''}{typeof latest?.elapsedSeconds==='number'?` · ${Math.floor(latest.elapsedSeconds/60)} min observed runtime`:''}. {job.state==='running'?'Current phase: ':'Last observed phase: '}{stage?.stage?.replaceAll('_',' ')}{memory.state==='bounded_resource_refusal'?' · Stopped safely; see the recorded resource limit.':''}</p>}
 </>;
}
