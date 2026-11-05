import {useEffect, useRef, useState} from 'react';
import {Check, Cloud, LoaderCircle, Play, TriangleAlert, X} from 'lucide-react';
import {rpc} from '../lib/api';
import {fmt, SERIES} from './mechanistic/MechCharts';
import './mechanistic/mechanistic.css';
import './multiscale/multiscale.css';
import RunController, {liveRun} from './biomodels/RunController';

const TRNA = 'GCGGAUUUAGCUCAGUUGGGAGAGCGCCAGACUGAAGAUCUGGAGGUCCUGUGUUCGAUCCACAGAAUUCGCACCA';

/** C1' traces of predicted models, rigidly superposed onto the reference server-side; all drawn around one shared centre. */
function Traces({result}: {result: any}) {
  const ref = useRef<HTMLCanvasElement>(null), [angle, setAngle] = useState(0.6);
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight; cv.width = W * dpr; cv.height = H * dpr;
    const g = cv.getContext('2d')!; g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    const all = [...(result.reference ? [{name: 'reference', t: result.reference.trace, c: '#ffffff'}] : []), ...result.names.map((n: string, i: number) => ({name: n, t: result.traces[n], c: SERIES[i % SERIES.length]}))];
    const ca = Math.cos(angle), sa = Math.sin(angle);
    const t0 = all[0]?.t ?? [], m = [0, 1, 2].map(i => t0.reduce((s: number, p: number[]) => s + p[i], 0) / (t0.length || 1));
    all.forEach(({t, c}, k) => {
      g.strokeStyle = c; g.globalAlpha = k === 0 && result.reference ? 0.9 : 0.75; g.lineWidth = k === 0 && result.reference ? 3 : 1.6; g.beginPath();
      t.forEach((p: number[], i: number) => { const x = p[0] - m[0], y = p[1] - m[1], z = p[2] - m[2]; const X = W / 2 + (ca * x + sa * z) * 5, Y = H / 2 - y * 5; i ? g.lineTo(X, Y) : g.moveTo(X, Y); });
      g.stroke();
    });
    g.globalAlpha = 1;
  });
  return <canvas ref={ref} className="md-canvas" style={{height: 300}} onPointerMove={e => e.buttons && setAngle(a => a + e.movementX * 0.01)} aria-label="C1′ traces of predicted models and the reference"/>;
}

/** Live server output: the image build while launching, then the container's own stdout/stderr while it runs. */
// Science view: the lines that say how a calculation is progressing (steps, energies, scores, files written, errors).
const SCIENCE = /\b(step|iter|epoch|energy|rmsd|plddt|ptm|confidence|loss|minimi[sz]|relax|converg|sampl|recycl|model|predict|saving|saved|wrote|written|done|finished|complete|error|fail|warn|traceback|sequence|structure|residue|seed|frame|time ?step|ns\/day|\d+(\.\d+)?\s*%)/i;
const VIEWS: [string, string, (l: string) => boolean][] = [
  ['science', 'Science', l => !/^\[(gpu|cpu)\]/.test(l) && (l.startsWith('[fold]') || SCIENCE.test(l))],
  ['raw', 'Raw · everything', () => true],
  ['gpu', 'GPU', l => l.startsWith('[gpu]') || /\b(cuda|nvidia|gpu|vram)\b/i.test(l)],
  ['cpu', 'CPU', l => l.startsWith('[cpu]')],
];

function ServerLog({phase, text}: {phase?: string; text?: string}) {
  const ref = useRef<HTMLPreElement>(null), [view, setView] = useState('science'), [find, setFind] = useState('');
  const lines = (text || '').split('\n'), test = VIEWS.find(v => v[0] === view)![2];
  const shown = lines.filter(l => test(l) && (!find || l.toLowerCase().includes(find.toLowerCase())));
  useEffect(() => { const el = ref.current; if (el) el.scrollTop = el.scrollHeight; }, [text, view, find]);
  return <div className="gt-serverlog">
    <span className="eyebrow"><span className="gt-live"/>{phase ?? 'Contacting your server'} · live</span>
    <div className="gt-logbar">{VIEWS.map(([id, label, f]) => <button key={id} className={'gt-view ' + (view === id ? 'selected' : '')} onClick={() => setView(id)}>{label} <small>{lines.filter(f).length}</small></button>)}
      <input aria-label="Filter log" placeholder="Filter…" value={find} onChange={e => setFind(e.target.value)}/></div>
    <pre ref={ref} className="gt-log gt-console">{shown.join('\n') || (text ? '[fold] nothing in this view yet' : '[fold] waiting for the first message from Modal…')}</pre>
  </div>;
}

/** System › Cloud GPU Tasks: anything that needs a GPU runs on the active server; the app is its interface. */
export default function GpuTasks({projectId}: {projectId: string}) {
  const [catalog, setCatalog] = useState<any>(null), [tasks, setTasks] = useState<any[]>([]), [error, setError] = useState('');
  const [recipe, setRecipe] = useState('rhofold'), [inputs, setInputs] = useState<any>({sequence: TRNA, samples: 5, ranks: 8, relaxSteps: 1000, registry: 'pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime', pip: '', apt: '', command: 'nvidia-smi > $OUT/gpu-check.txt', files: {}});
  const [gpu, setGpu] = useState(''), [approved, setApproved] = useState(false), [busy, setBusy] = useState(''), [open, setOpen] = useState<any>(null), [compare, setCompare] = useState<any>(null);
  const [autoRefresh,setAutoRefresh]=useState(true);
  const scope=useRef(0),selection=useRef(0);
  async function call<T>(label:string,action:string,payload:any){const generation=scope.current;setBusy(label);setError('');try{const result=await rpc<T>(action,{projectId,...payload});return generation===scope.current?result:undefined;}catch(e){if(generation===scope.current)setError(String(e).replace(/^Error:\s*/,''));}finally{if(generation===scope.current)setBusy('');}}
  async function refresh(){const generation=scope.current;const rows=await rpc<any[]>('gpu_tasks_list',{projectId});if(generation===scope.current)setTasks(rows);return rows;}
  useEffect(()=>{let active=true;const generation=++scope.current;selection.current++;setOpen(null);setTasks([]);setCompare(null);setError('');
    Promise.all([rpc<any>('gpu_tasks_catalog',{}),rpc<any[]>('gpu_tasks_list',{projectId})]).then(async([c,rows])=>{if(!active)return;setCatalog(c);setTasks(rows);const first=rows.find(t=>liveRun(t.state))??rows[0];if(first){const record=await rpc('gpu_task_record',{projectId,taskId:first.id});if(active&&generation===scope.current)setOpen(record);}}).catch(e=>{if(active)setError(String(e));});
    return()=>{active=false;scope.current++;};
  },[projectId]);
  useEffect(()=>{if(catalog)setGpu(catalog.recipes[recipe].gpu??'');setApproved(false);},[recipe,catalog]);
  useEffect(()=>{if(!open||!liveRun(open.state)||!autoRefresh)return;let active=true,timer:ReturnType<typeof setTimeout>;const id=open.id;
    async function tick(){if(!active)return;if(document.visibilityState==='hidden'){timer=setTimeout(()=>void tick(),5000);return;}try{const status=await rpc<any>('gpu_task_status',{projectId,taskId:id});const record=liveRun(status.state)?status:await rpc<any>('gpu_task_record',{projectId,taskId:id});if(active){setOpen((old:any)=>old?.id===id?{...old,...record}:old);await refresh();}}catch(e){if(active)setError(String(e).replace(/^Error:\s*/,''));}if(active)timer=setTimeout(()=>void tick(),4000);}
    timer=setTimeout(()=>void tick(),1000);return()=>{active=false;clearTimeout(timer);};
  },[projectId,open?.id,open?.state,autoRefresh]);
  async function readOpen(){if(!open)return;const id=open.id,generation=scope.current;try{const record=await rpc('gpu_task_record',{projectId,taskId:id});if(generation===scope.current)setOpen((old:any)=>old?.id===id?record:old);}catch(e){if(generation===scope.current)setError(String(e));}}
  async function updateOpen(action:string,payload:any={}){if(!open)return;const id=open.id,generation=scope.current;const status=await call<any>('Updating run',action,{taskId:id,...payload});if(status&&generation===scope.current){try{const record=await rpc<any>('gpu_task_record',{projectId,taskId:id});if(generation!==scope.current)return;setOpen((old:any)=>old?.id===id?{...record,...(liveRun(status.state)?status:{})}:old);await refresh();}catch(e){if(generation===scope.current)setError(String(e));}}}


  async function submit() {
    const generation=scope.current;
    const r = catalog.recipes[recipe];
    const payload: any = {recipe, approvedRemoteCost: approved, gpu: gpu || undefined, inputs: {}};
    for (const k of Object.keys(r.inputs)) payload.inputs[k] = k === 'pip' || k === 'apt' ? String(inputs[k]).split(/\s+/).filter(Boolean) : inputs[k];
    const rec = await call<any>('Launching on your server (image builds can take several minutes)', 'gpu_task_submit', payload);
    if (rec) { setApproved(false); await refresh(); if(generation===scope.current){setOpen(rec);setCompare(null);} }
  }
  async function view(id:string){const ticket=++selection.current;const r=await call<any>('Opening task','gpu_task_record',{taskId:id});if(r&&ticket===selection.current){setOpen(r);setCompare(null);}}
  async function run3d() { const r = await call<any>('Comparing structures', 'gpu_task_rna3d_compare', {taskId: open.id, reference: 'trna_phe'}); if (r) setCompare(r); }


  const r = catalog?.recipes[recipe];
  return <div className="page-content gpu-tasks">
    <header className="mech-head"><div><span className="eyebrow">System · Cloud GPU Tasks</span><h1>Your research, <em>under control.</em></h1>
      <p>Follow each run from start to finish. Open its terminal, inspect commands, and keep the files and evidence together.</p></div></header>
    {error && <div className="mech-error" role="alert"><TriangleAlert size={15}/>{error}</div>}
    {busy && <div className="mech-busy"><LoaderCircle size={16} className="spin"/>{busy}…</div>}
    <details className="gt-new-run"><summary>Start a new run</summary>
    {catalog && <section className="gt-recipes">{Object.entries(catalog.recipes).filter(([id])=>!id.startsWith('bio_')).map(([id, x]: [string, any]) =>
      <button key={id} className={'mech-panel gt-recipe ' + (recipe === id ? 'active' : '')} onClick={() => setRecipe(id)}>
        <span className="eyebrow">{x.demo ?? 'Any model'} · {x.gpu ? 'GPU ' + x.gpu : 'CPU ' + (x.cpu ?? 4) + ' cores'}</span><strong>{x.title}</strong><span>{x.purpose}</span></button>)}</section>}

    {r && <section className="mech-panel ms-panel gt-form">
      <span className="eyebrow">{r.evidence}</span>
      {'sequence' in r.inputs && <label>RNA sequence<textarea className="mono" rows={3} value={inputs.sequence} onChange={e => setInputs({...inputs, sequence: e.target.value})}/></label>}
      {'samples' in r.inputs && <label>Structures to sample<input type="number" min={1} max={25} value={inputs.samples} onChange={e => setInputs({...inputs, samples: Number(e.target.value)})}/></label>}
      {'relaxSteps' in r.inputs && <label>Amber relaxation steps (0 skips; the unrelaxed model is the prediction)<input type="number" min={0} max={5000} value={inputs.relaxSteps} onChange={e => setInputs({...inputs, relaxSteps: Number(e.target.value)})}/></label>}
      {'ranks' in r.inputs && <label>MPI ranks<input type="number" min={1} max={16} value={inputs.ranks} onChange={e => setInputs({...inputs, ranks: Number(e.target.value)})}/></label>}
      {recipe === 'custom' && <>
        <label>Container image<input className="mono" value={inputs.registry} onChange={e => setInputs({...inputs, registry: e.target.value})}/></label>
        <label>pip packages (space-separated)<input className="mono" value={inputs.pip} onChange={e => setInputs({...inputs, pip: e.target.value})}/></label>
        <label>apt packages<input className="mono" value={inputs.apt} onChange={e => setInputs({...inputs, apt: e.target.value})}/></label>
        <label>Command (bash; write results to $OUT)<textarea className="mono" rows={5} value={inputs.command} onChange={e => setInputs({...inputs, command: e.target.value})}/></label></>}
      {catalog.recipes[recipe].gpu !== null && <label>GPU<select value={gpu} onChange={e => setGpu(e.target.value)}>{catalog.gpus.map((g: string) => <option key={g}>{g}</option>)}</select></label>}
      <p className="caption">Source: {r.source}{r.reference && <> · <a href={'https://doi.org/' + r.reference.doi} target="_blank" rel="noreferrer">{r.reference.citation.split('.')[0]}…</a></>}<br/>Licence: {r.license}</p>
      <label className="gt-approve"><input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)}/> I approve running this on my server account. GPU time and the first image build are billed by the provider.</label>
      <button className="button primary" disabled={!approved || !!busy} onClick={submit}><Cloud size={14}/>Run on server</button>
    </section>}

    </details>
    <div className="gt-control-layout">
    <section className="mech-panel ms-panel gt-history">
      <div className="gt-runs-heading"><div><span className="eyebrow">LIBRARY RUNS</span><h2>Run history</h2><p>Select a run to open its controller.</p></div><button className="button" onClick={()=>void refresh().catch(e=>setError(String(e)))}>Refresh history</button></div>
      {tasks.length === 0 && <p className="caption">No tasks yet.</p>}
      <div className="ms-runs">{tasks.map(t => <button key={t.id} className={'ms-run ' + (open?.id === t.id ? 'active' : '')} onClick={() => view(t.id)}>
        <strong>{t.title}</strong><span>{t.created?new Date(t.created).toLocaleString():''} · {t.gpu ?? 'CPU'} · {t.state === 'launching' || t.state === 'running' ? <LoaderCircle size={11} className="spin"/> : t.state === 'done' || t.state === 'stopped' ? <Check size={11}/> : <X size={11}/>} {t.state}</span></button>)}</div>
    </section>

    {open&&<RunController key={open.id} task={open} projectId={projectId} busy={!!busy} autoRefresh={autoRefresh} onAutoRefresh={()=>setAutoRefresh(x=>!x)} onRefresh={()=>updateOpen('gpu_task_status')} onRead={readOpen} onStop={()=>updateOpen('gpu_task_cancel')} onRetryDownload={()=>updateOpen('gpu_task_status',{retryFetch:true})}/>}
    </div>
    {open && <section className="gt-analysis">
      {(open.state === 'done' || open.state === 'stopped') && (open.recipe === 'rhofold' || open.recipe === 'boltz_rna') && <button className="button primary" onClick={run3d}><Play size={14}/>Compare with tRNA-Phe crystal structure (1EHZ)</button>}
      {compare && <div className="gt-compare">
        <Traces result={compare}/>
        <table className="ms-table"><thead><tr><th>Model</th><th>C1′ RMSD to 1EHZ</th><th>Base-pair geometry</th><th>Clashes</th></tr></thead><tbody>
          {compare.models.map((m: any) => <tr key={m.model}><td className="mono">{m.model}</td><td>{fmt(m.rmsdToReference, 3)} Å</td><td>{fmt((m.basePairGeometry ?? 0) * 100, 3)} %</td><td>{m.clashes}</td></tr>)}
        </tbody></table>
        {compare.names.length > 1 && (() => {
          const v = compare.pairwise.flat().filter((x: number) => x > 0), lo = fmt(Math.min(...v), 3), hi = fmt(Math.max(...v), 3);
          // Relaxed and unrelaxed files are one prediction before and after Amber; their difference is not model uncertainty.
          const relaxOnly = compare.names.length === 2 && compare.names.every((n: string) => /relax/i.test(n));
          return <p className="caption">{relaxOnly ? `Relaxation shift: C1′ RMSD ${lo} Å between the same prediction before and after Amber relaxation (one prediction, so no model-uncertainty estimate).` : `Model disagreement: pairwise C1′ RMSD ${lo === hi ? lo : lo + '–' + hi} Å.`}</p>;
        })()}
        <p className="caption">{compare.note}</p></div>}

    </section>}
  </div>;
}
