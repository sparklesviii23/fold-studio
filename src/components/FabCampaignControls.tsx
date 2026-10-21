import type {Job} from '../lib/types';

export default function FabCampaignControls({job,ready,busy,onStart}:{job:Job;ready:boolean;busy:boolean;onStart:()=>void}){
 const memory=job.data.memoryExecution?.telemetry,stage=job.data.memoryExecution?.stage;
 const samples=memory?.latestSamples??[],latest=samples[samples.length-1];
 return <>
  {job.state==='prepared'&&<><p className="caption">Full Fab · complete heavy and light chains with constant domains. Uses the saved original design-model pool and held-out multimer validation. The protected CPU worker combines recomputation and bounded SSD checkpoints with a 14 GiB task-memory ceiling. Experimental; complete campaign validation is in progress.</p>{ready?<button className="button" disabled={busy} onClick={onStart}>Start full Fab · experimental protected CPU</button>:<p className="caption">Full-length gradient and repeated-step validation are in progress. Campaign launch remains unavailable until those checks pass.</p>}</>}
  {memory&&<p className="caption">Fab worker · {latest?`${(latest.physicalFootprintBytes/1024**3).toFixed(2)} GiB ${job.state==='running'?'current':'last observed'} · `:''}{typeof memory.peakFootprintBytes==='number'?`${(memory.peakFootprintBytes/1024**3).toFixed(2)} GiB peak · `:''}14 GiB limit{typeof stage?.completedGradients==='number'?` · ${stage.completedGradients} gradient calculations completed`:''}{typeof latest?.elapsedSeconds==='number'?` · ${Math.floor(latest.elapsedSeconds/60)} min observed runtime`:''}. {job.state==='running'?'Current phase: ':'Last observed phase: '}{stage?.stage?.replaceAll('_',' ')}{memory.state==='bounded_resource_refusal'?' · Stopped safely; see the recorded resource limit.':''}</p>}
 </>;
}
