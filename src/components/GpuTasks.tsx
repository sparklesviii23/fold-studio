import {useEffect, useRef, useState} from 'react';
import {Check, Cloud, LoaderCircle, Play, Square, Terminal, TriangleAlert, X} from 'lucide-react';
import {rpc} from '../lib/api';
import {fmt, SERIES} from './mechanistic/MechCharts';
import './mechanistic/mechanistic.css';
import './multiscale/multiscale.css';
import ModalTerminal from './biomodels/ModalTerminal';

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
  const [cmd, setCmd] = useState(''), [term, setTerm] = useState<{cmd: string; out: string; code: number}[]>([]), [cmdOk, setCmdOk] = useState(false);

  async function call<T>(label: string, action: string, payload: any) { setBusy(label); setError(''); try { return await rpc<T>(action, {projectId, ...payload}); } catch (e) { setError(String(e).replace(/^Error:\s*/, '')); } finally { setBusy(''); } }
  async function refresh() { const r = await rpc<any[]>('gpu_tasks_list', {projectId}).catch(() => null); if (r) setTasks(r); }
  useEffect(() => { rpc<any>('gpu_tasks_catalog', {}).then(c => { setCatalog(c); }).catch(e => setError(String(e))); void refresh(); }, []);
  useEffect(() => { if (catalog) setGpu(catalog.recipes[recipe].gpu ?? ''); setApproved(false); }, [recipe, catalog]);
  useEffect(() => {
    const live = tasks.filter(t => t.state === 'launching' || t.state === 'running');
    if (!live.length) return;
    // One poll at a time: each poll is a round trip to the server, so never start the next before the last returns.
    let stop = false, timer: any;
    const tick = async () => { for (const x of live) { if (stop) return; try { const s = await rpc<any>('gpu_task_status', {projectId, taskId: x.id}); setOpen((o: any) => o?.id === s.id ? {...o, ...s} : o); } catch (e) { setError(String(e).replace(/^Error:\s*/, '')); } } if (!stop) { await refresh(); timer = setTimeout(tick, 3000); } };
    timer = setTimeout(tick, 1000);
    return () => { stop = true; clearTimeout(timer); };
  }, [tasks.map(t => t.id + t.state).join()]);

  async function submit() {
    const r = catalog.recipes[recipe];
    const payload: any = {recipe, approvedRemoteCost: approved, gpu: gpu || undefined, inputs: {}};
    for (const k of Object.keys(r.inputs)) payload.inputs[k] = k === 'pip' || k === 'apt' ? String(inputs[k]).split(/\s+/).filter(Boolean) : inputs[k];
    const rec = await call<any>('Launching on your server (image builds can take several minutes)', 'gpu_task_submit', payload);
    if (rec) { setApproved(false); await refresh(); setOpen(rec); setCompare(null); }
  }
  async function view(id: string) { const r = await call<any>('Opening task', 'gpu_task_record', {taskId: id}); if (r) { setOpen(r); setCompare(null); setTerm([]); } }
  async function run3d() { const r = await call<any>('Comparing structures', 'gpu_task_rna3d_compare', {taskId: open.id, reference: 'trna_phe'}); if (r) setCompare(r); }
  async function exec() { const r = await call<any>('Running command in the task container', 'gpu_task_exec', {taskId: open.id, command: cmd, approvedRemoteCommand: cmdOk}); if (r) { setTerm(t => [...t, {cmd, out: (r.stdout || '') + (r.stderr ? '\n' + r.stderr : ''), code: r.exitCode}]); setCmd(''); setCmdOk(false); } }

  const r = catalog?.recipes[recipe];
  return <div className="page-content gpu-tasks">
    <header className="mech-head"><div><span className="eyebrow">System · Cloud GPU Tasks</span><h1>Your server, <em>this interface.</em></h1>
      <p>Models that need a GPU run in containers on your active Modal account. Results return to this library with their recipe, logs and checksums.</p></div></header>
    {error && <div className="mech-error" role="alert"><TriangleAlert size={15}/>{error}</div>}
    {busy && <div className="mech-busy"><LoaderCircle size={16} className="spin"/>{busy}…</div>}
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

    <section className="mech-panel ms-panel">
      <span className="eyebrow">Tasks</span>
      {tasks.length === 0 && <p className="caption">No tasks yet.</p>}
      <div className="ms-runs">{tasks.map(t => <button key={t.id} className={'ms-run ' + (open?.id === t.id ? 'active' : '')} onClick={() => view(t.id)}>
        <strong>{t.title}</strong><span>{t.created?.replace('T', ' ').slice(0, 16)} · {t.gpu ?? 'CPU'} · {t.state === 'launching' || t.state === 'running' ? <LoaderCircle size={11} className="spin"/> : t.state === 'done' || t.state === 'stopped' ? <Check size={11}/> : <X size={11}/>} {t.state}</span></button>)}</div>
    </section>

    {open && <section className="mech-panel ms-panel">
      <div className="ms-row"><span className="eyebrow">{open.title} · {open.state}</span>
        {open.fetchError && <button className="button" onClick={async () => { const x = await call<any>('Downloading', 'gpu_task_status', {taskId: open.id, retryFetch: true}); if (x) { setOpen(x); void refresh(); } }}>Retry download</button>}
        {(open.state === 'running' || open.state === 'launching') && <button className="button" onClick={async () => { const x = await call<any>('Stopping', 'gpu_task_cancel', {taskId: open.id}); if (x) { setOpen(x); void refresh(); } }}><Square size={13}/>Stop</button>}</div>
      <p className="caption">Account {open.accountId?.slice(0, 8)} · sandbox {open.sandboxId ?? '—'} · inputs SHA-256 {open.inputsSha256?.slice(0, 12)}</p>
      {open.error && <div className="mech-error"><TriangleAlert size={14}/>{open.error}</div>}
      {(open.state === 'launching' || open.state === 'running') && <ModalTerminal projectId={projectId} taskId={open.id} state={open.state} phase={open.phase} log={open.serverLog}/>}
      {open.outputs && <><span className="eyebrow">Returned files ({open.outputs.length})</span>
        <ul className="ms-list mono">{open.outputs.slice(0, 40).map((f: any) => <li key={f.path}>{f.path} · {fmt(f.bytes / 1024, 3)} KB · {f.sha256.slice(0, 10)}</li>)}</ul></>}
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
      {(open.stdout || open.stderr) && <details><summary>Logs</summary><pre className="gt-log">{open.stdout}{open.stderr ? '\n' + open.stderr : ''}</pre></details>}
      {open.state === 'running' && <div className="gt-terminal">
        <span className="eyebrow"><Terminal size={12}/> Terminal · inside the running task container</span>
        {term.map((t, i) => <pre key={i} className="gt-log"><b>$ {t.cmd}</b>{'\n'}{t.out}{t.code ? `\n[exit ${t.code}]` : ''}</pre>)}
        <div className="gt-term-row"><input className="mono" value={cmd} placeholder="nvidia-smi" onChange={e => { setCmd(e.target.value); setCmdOk(false); }}/>
          <label><input type="checkbox" checked={cmdOk} onChange={e => setCmdOk(e.target.checked)}/> run on server</label>
          <button className="button" disabled={!cmd.trim() || !cmdOk || !!busy} onClick={exec}>Run</button></div>
      </div>}
    </section>}
  </div>;
}
