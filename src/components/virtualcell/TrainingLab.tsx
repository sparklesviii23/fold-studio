import {useEffect, useState} from 'react';
import {ArrowRight, BrainCircuit, Check, ChevronDown, Database, Dna, FlaskConical, Layers3, LoaderCircle, RefreshCw, ShieldCheck, Terminal, X} from 'lucide-react';
import {rpc} from '../../lib/api';
import './traininglab.css';

const number = (n?: number) => n == null ? '—' : n.toLocaleString();
const models = [
  ['numeric', 'Numerical predictor', 'A direct numerical network using the same measured inputs. Establishes what the inputs can predict without Qwen.'],
  ['biology_numeric', 'Biology encoder + predictor', 'Cell2Sentence supplies a representation of the starting cell to the numerical network.'],
  ['qwen', 'Grounded Qwen', 'Structured cell and intervention evidence flows through Qwen into full gene-response outputs.'],
  ['qwen_frozen', 'Fixed-Qwen comparison', 'Same foundation practice; Qwen adapters stay fixed during response training. Numerical layers still learn.'],
  ['qwen_biology', 'Qwen + biological memory', 'Cell2Sentence representations join the measured inputs inside Qwen’s numerical prefix.'],
];

export function TrainingOverview({experiment}: {experiment: any}) {
  const data = experiment.data, tasks = data.textLengths;
  return <>
    <div className="ctl-stat-grid">
      <div><Database size={19}/><strong>{number(data.distinctTrainingCells)}</strong><span>distinct training cells</span></div>
      <div><Layers3 size={19}/><strong>{number(data.featureWidth)}</strong><span>structured input features</span></div>
      <div><Dna size={19}/><strong>2,132</strong><span>gene-response channels</span></div>
      <div><ShieldCheck size={19}/><strong>Complete context</strong><span>zero descriptions truncated</span></div>
    </div>
    <section className="ctl-section"><div className="ctl-section-title"><span className="ctl-step">01</span><div><h2>Evidence before prediction</h2><p>The starting cell, the intervention and the experiment each retain their own meaning.</p></div></div>
      <div className="ctl-evidence-grid">
        <article><span className="ctl-tag">MEASURED CELL</span><h3>A real starting state</h3><p>Quantitative expression, measured-gene masks and ranked gene context. Drug baselines come from DepMap; activation and inhibition controls come from their own screens.</p></article>
        <article><span className="ctl-tag">INTERVENTION</span><h3>More than a name</h3><p>Molecular fingerprints and chemical properties, gene and pathway annotations, source-backed targets, dose and explicit indicators for missing evidence.</p></article>
        <article><span className="ctl-tag">KNOWN LIMITS</span><h3>Unknown stays unknown</h3><p>Exposure duration and perturbation strength are marked unavailable when absent. Bulk baselines and single-cell responses retain their different assay units.</p></article>
      </div>
    </section>
    <section className="ctl-section"><div className="ctl-section-title"><span className="ctl-step">02</span><div><h2>Each task earns its own checkpoint</h2><p>Separate validation, early stopping and saved weights for every response family.</p></div></div>
      <div className="ctl-task-grid">{[['pair','Gene pairs','Familiar development cases'],['inhibition','Gene inhibition','Fresh intervention identities'],['drug','Drug response','Chemical identities held together']].map(([id,label,note]) =>
        <article key={id}><h3>{label}</h3><p>{note}</p><dl><div><dt>Training conditions</dt><dd>{number(tasks[id+'_train']?.conditions)}</dd></div><div><dt>Validation conditions</dt><dd>{number(tasks[id+'_validation']?.conditions)}</dd></div><div><dt>Final test conditions</dt><dd>{tasks[id+'_test'] ? number(tasks[id+'_test'].conditions) : 'No fresh pair test'}</dd></div></dl><small>{data.units[id]}</small></article>)}</div>
      <p className="ctl-footnote">Final answers stay on this Mac. Additional drug tests hold out {data.heldoutContexts.length} cellular contexts. Test outcomes are opened only after model selection and prediction sealing.</p>
    </section>
  </>;
}

export default function TrainingLab({projectId,onOpenRuns}: {projectId: string;onOpenRuns:()=>void}) {
  const [workspace,setWorkspace]=useState<any>(null),[selected,setSelected]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(''),[review,setReview]=useState(false);
  const [costApproved,setCostApproved]=useState(false),[downloadApproved,setDownloadApproved]=useState(false),[notice,setNotice]=useState('');
  async function refresh(){try {const r=await rpc<any>('vcell_training_status',{});setWorkspace(r);setSelected(s=>r.experiments.some((e:any)=>e.id===s)?s:r.experiments[0]?.id??'');}catch(e){setError(String(e));}}
  useEffect(()=>{refresh();},[]);
  const active=workspace?.preparationJobs?.length || workspace?.experiments?.some((e:any)=>['launching','running'].includes(e.state));
  useEffect(()=>{if(!active)return;const timer=setTimeout(refresh,5000);return()=>clearTimeout(timer);},[workspace,active]);
  async function action(name:string,payload:any){setBusy(name);setError('');try{const r=await rpc<any>(name,payload);await refresh();return r;}catch(e){setError(String(e).replace(/^Error:\s*/,''));}finally{setBusy('');}}
  const experiment=workspace?.experiments?.find((e:any)=>e.id===selected),encoder=workspace?.encoder,plan=experiment?.plan;
  async function start(){const r=await action('vcell_training_launch',{experimentId:selected,projectId,approvedRemoteCost:costApproved,approvedEncoderDownload:downloadApproved});if(r){setReview(false);setNotice('Started one bounded attempt. Follow its progress in Runs & terminal.');onOpenRuns();}}
  return <div className="ctl-workspace">
    <header className="ctl-hero"><div className="ctl-hero-content"><span className="eyebrow">VIRTUAL CELL · TRAINING LABORATORY</span><h1>Teach the model.<br/><em>Measure what it learns.</em></h1><p>Ground Qwen in measured cells, chemical structures and biological evidence. Compare every gain with a simpler explanation.</p>
      <div className="button-row"><button className="button" onClick={onOpenRuns}><Terminal size={15}/>Runs & terminal</button><button className="text-button" onClick={refresh}><RefreshCw size={14}/>Refresh</button></div></div>
      <div className="ctl-orbit" aria-hidden="true"><span/><span/><span/><BrainCircuit size={54}/></div>
    </header>
    {error&&<div className="vc-error" role="alert">{error}</div>}{notice&&<div className="vc-busy" role="status">{notice}</div>}
    {!workspace?<div className="ctl-loading"><LoaderCircle className="spin"/>Reading saved experiments…</div>:<>
      <div className="ctl-toolbar"><label>Experiment<select aria-label="Training experiment" value={selected} onChange={e=>{setSelected(e.target.value);setReview(false);setCostApproved(false);setDownloadApproved(false);}}>{workspace.experiments.map((e:any)=><option key={e.id} value={e.id}>{e.id.slice(0,8)} · {e.state.replace('_',' ')}</option>)}</select></label>
        <button className="text-button" disabled={!!busy||!!active||!workspace.sourcesReady} onClick={async()=>{const r=await action('vcell_training_prepare',{projectId});if(r)setNotice('Preparing a fresh local data bundle. No model training or cloud allocation has started.');}}>{busy==='vcell_training_prepare'?<LoaderCircle size={15} className="spin"/>:<Database size={15}/>}Prepare fresh experiment</button>
        {experiment?.state==='prepared'&&<button className="button primary" onClick={()=>setReview(true)}>Review cloud run<ArrowRight size={15}/></button>}
        {['launching','running'].includes(experiment?.state)&&<button className="button" onClick={onOpenRuns}><LoaderCircle size={14} className="spin"/>Open active run</button>}
      </div>
      {!experiment?<div className="ctl-empty"><Database size={28}/><h2>Start with the evidence</h2><p>Prepare a verified local bundle to review its data, models and cloud budget.</p></div>:<TrainingOverview experiment={experiment}/>}
      <section className="ctl-section"><div className="ctl-section-title"><span className="ctl-step">03</span><div><h2>Five ways to test the same idea</h2><p>Full numerical outputs. A protected RNA expert. Controlled comparisons that include negative results.</p></div></div><div className="ctl-model-list">{models.map(([id,title,description],i)=><article key={id}><span className="ctl-model-number">0{i+1}</span><div><h3>{title}</h3><p>{description}</p></div><span className="ctl-pill">{id.includes('biology')?'Cell2Sentence':'Measured inputs'}</span></article>)}</div>
        <div className="ctl-encoder"><BrainCircuit size={23}/><div><strong>Biological encoder · Cell2Sentence 410M</strong><p>{encoder.installed?'Checkpoint present; integrity is checked again before each launch.':`${((encoder.downloadBytes??0)/1e9).toFixed(2)} GB official checkpoint · awaiting explicit download approval`}</p><small>{encoder.license} · {workspace.compounds.resolved} compounds have resolved structure evidence</small></div><span className="ctl-pill">{encoder.installed?'Available':'Download required'}</span></div>
      </section>
      <section className="ctl-section"><div className="ctl-section-title"><span className="ctl-step">04</span><div><h2>Accuracy has several dimensions</h2><p>Every candidate faces unchanged, training-average and regularized linear predictions.</p></div></div><div className="ctl-metric-grid">{[['Magnitude','Full-panel error and error on the largest measured effects.'],['Direction','Whether the genes with the largest measured effects move up or down correctly.'],['Specificity','Whether each prediction identifies the correct intervention signature.'],['Generalization','Fresh chemical/target groups, held-out contexts and group-bootstrap score intervals.']].map(([title,detail])=><article key={title}><FlaskConical size={18}/><h3>{title}</h3><p>{detail}</p></article>)}</div><p className="ctl-footnote">One seed in the prepared pilot. Predictive confidence is not calibrated. Group intervals describe evaluation uncertainty; they do not certify individual predictions. Model defaults change only after a separate reviewed decision.</p></section>
      {workspace.previous&&<details className="ctl-history"><summary><ChevronDown size={17}/>Previous run · keep the comparison honest</summary><p>The best checkpoint improved familiar gene-pair development error by {((1-workspace.previous.primaryBestMse/workspace.previous.primaryReferenceMse)*100).toFixed(2)}%. Gene-inhibition tests stayed close to the training-average baseline; drug tests performed slightly worse than that baseline.</p><button className="text-button" onClick={onOpenRuns}>View saved results and logs<ArrowRight size={14}/></button></details>}
      {experiment?.finalSummary&&<section className="ctl-section"><h2>Saved final-test results</h2>{Object.entries(experiment.finalSummary).map(([task,arms]:[string,any])=><div className="ctl-results" key={task}><h3>{task.replaceAll('_',' ')}</h3><table><thead><tr><th>Candidate</th><th>Error ↓</th><th>Direction</th><th>Validation choice</th></tr></thead><tbody>{Object.entries(arms).map(([arm,row]:[string,any])=><tr key={arm}><td>{arm.replaceAll('_',' ')}</td><td>{row.mse.toFixed(6)}</td><td>{row.direction==null?'Unavailable':(row.direction*100).toFixed(1)+'%'}</td><td>{row.selected?'Selected before test':''}</td></tr>)}</tbody></table></div>)}</section>}
    </>}
    {review&&plan&&<div className="ctl-review-backdrop"><section className="ctl-review" role="dialog" aria-modal="true" aria-labelledby="ctl-review-title"><button className="ctl-close" aria-label="Close cloud review" onClick={()=>setReview(false)}><X size={20}/></button><span className="eyebrow">ONE PREPARED ATTEMPT</span><h2 id="ctl-review-title">Review before running.</h2><p>Five controlled model variants, task-specific validation and local final-answer scoring.</p><dl><div><dt>Compute</dt><dd>Modal · A100 80 GB</dd></div><div><dt>Container limit</dt><dd>{Math.round(plan.timeout/60)} minutes</dd></div><div><dt>Estimated cost</dt><dd>${plan.estimatedUsd[0]}–${plan.estimatedUsd[1]}</dd></div><div><dt>Explicit upload list</dt><dd>{(plan.uploadBytes/1e9).toFixed(2)} GB</dd></div></dl><p className="ctl-footnote">The time limit is not a dollar cap. Building, CPU, memory, persistent storage and transfer may add charges. One attempt, no automatic retry. Only prepared public-data inputs, reviewed source and model assets are uploaded; final answers stay local.</p>
      {!encoder.installed&&<label className="ctl-consent"><input type="checkbox" checked={downloadApproved} onChange={e=>setDownloadApproved(e.target.checked)}/><span>Approve the official {(encoder.downloadBytes/1e9).toFixed(2)} GB Cell2Sentence checkpoint download. Weights: CC BY 4.0, attributed to the van Dijk Lab.</span></label>}
      <label className="ctl-consent"><input type="checkbox" checked={costApproved} onChange={e=>setCostApproved(e.target.checked)}/><span>Approve this single paid Modal attempt using the displayed budget and limits.</span></label><button className="button primary" disabled={!!busy||!costApproved||(!encoder.installed&&!downloadApproved)||!projectId} onClick={start}>{busy?<LoaderCircle className="spin" size={16}/>:<Check size={16}/>}Start approved attempt</button>
    </section></div>}
  </div>;
}
