import {useEffect, useMemo, useRef, useState} from 'react';
import {ArrowRight, Check, ChevronLeft, ChevronRight, Download, FileUp, FlaskConical, LoaderCircle, Pause, Play, Search, Sigma, TriangleAlert, X} from 'lucide-react';
import {chooseSave, rpc} from '../../lib/api';
import {fmt, Heatmap, ScanChart, SensitivityBars, TimeChart} from './MechCharts';
import {KnowledgeGraph, ReactionNetwork, type GraphData, type ModelDescription} from './NetworkView';
import './mechanistic.css';

type Experiment = 'run'|'scan'|'scan2d'|'uncertainty'|'sensitivity';
interface Loaded {key: string; model: ModelDescription & {units: {substance: string; time: string; volume: string}; odes: {species: string; equation: string}[]; parameters: {id: string; name: string; value: number | null; units: string | null; scope: string; usedBy: string[]; provenance: string}[]; executable: boolean; unsupported: string[]; source: any; references: any[]; rules: any[]; sha256: string}; demo: any}
interface Sweep {name: string; min: number; max: number; steps: number; log: boolean}

const experiments: [Experiment, string][] = [['run', 'Time course'], ['scan', 'Parameter scan'], ['scan2d', '2D scan'], ['uncertainty', 'Uncertainty'], ['sensitivity', 'Sensitivity']];
const readouts: [string, string][] = [['final', 'Final value'], ['max', 'Peak'], ['min', 'Minimum'], ['auc', 'Area under curve'], ['time_of_max', 'Time of peak']];

function concentrationUnit(u?: {substance: string; volume: string}) {
  if (!u) return '';
  if (u.substance.includes('item')) return 'molecules';
  if (u.substance === '10^-9 mole' && u.volume === 'litre') return 'nM';
  if (u.substance === 'mole' && u.volume === 'litre') return 'M';
  return u.substance + ' / ' + u.volume;
}
const short = (t: string) => ({second: 's', minute: 'min', hour: 'h', day: 'd'} as Record<string, string>)[t] ?? t;

/** Analyse › Mechanistic Biology Lab: published and composed kinetic models, executed with SciPy, inspected down to their equations and sources. */
export default function MechanisticLab({initialQuery}: {initialQuery?: string}) {
  const [catalog, setCatalog] = useState<any>(null), [busy, setBusy] = useState(''), [error, setError] = useState('');
  const [query, setQuery] = useState(initialQuery ?? ''), [search, setSearch] = useState<any>(null), [target, setTarget] = useState<any>(null), [discovery, setDiscovery] = useState<any>(null);
  const [loaded, setLoaded] = useState<Loaded | null>(null), [checks, setChecks] = useState<any[] | null>(null);
  const [centre, setCentre] = useState<'network'|'knowledge'>('network'), [inspector, setInspector] = useState<'equations'|'parameters'|'evidence'>('evidence');
  const [experiment, setExperiment] = useState<Experiment>('run');
  const [tEnd, setTEnd] = useState(100), [method, setMethod] = useState('LSODA'), [rtol, setRtol] = useState(1e-8);
  const [overrides, setOverrides] = useState<Record<string, number>>({}), [initial, setInitial] = useState<Record<string, number>>({});
  const [outputs, setOutputs] = useState<string[]>([]), [readout, setReadout] = useState('final'), [targetOut, setTargetOut] = useState('');
  const [sweep, setSweep] = useState<Sweep>({name: '', min: 0.1, max: 10, steps: 9, log: true}), [sweepB, setSweepB] = useState<Sweep>({name: '', min: 0.1, max: 10, steps: 7, log: true});
  const [uncertain, setUncertain] = useState<string[]>([]), [spread, setSpread] = useState(2), [samples, setSamples] = useState(64), [seed, setSeed] = useState(1);
  const [result, setResult] = useState<any>(null), [runId, setRunId] = useState(''), [playhead, setPlayhead] = useState(0), [playing, setPlaying] = useState(false);
  const [selected, setSelected] = useState<string | null>(null), [highlight, setHighlight] = useState<string | null>(null);
  const [leftOpen, setLeftOpen] = useState(true), [rightOpen, setRightOpen] = useState(true);
  const file = useRef<HTMLInputElement>(null);

  async function call<T>(label: string, action: string, payload: any): Promise<T | undefined> {
    setBusy(label); setError('');
    try { return await rpc<T>(action, payload); } catch (e) { setError(String(e).replace(/^Error:\s*/, '')); return undefined; } finally { setBusy(''); }
  }
  useEffect(() => { call('Opening the laboratory', 'mech_catalog', {}).then(c => { if (c) { setCatalog(c); void loadDemo('cascade'); } }); }, []);
  useEffect(() => { if (initialQuery) void runSearch(initialQuery); }, [initialQuery]);

  async function runSearch(q = query) {
    if (!q.trim()) return;
    const r = await call<any>('Searching UniProt and BioModels', 'mech_search', {query: q.trim()});
    if (r) setSearch(r);
  }
  async function chooseTarget(t: any) {
    setTarget(t); setDiscovery(null); setCentre('knowledge');
    const r = await call<any>('Finding published models for ' + (t.genes?.[0] ?? t.accession) + ' — downloading and checking each model can take a minute', 'mech_discover', {target: t});
    if (r) setDiscovery(r);
  }
  function adopt(l: Loaded, demo?: any) {
    setLoaded(l); setChecks(null); setResult(null); setRunId(''); setOverrides({}); setInitial({}); setSelected(null); setHighlight(null); setCentre('network');
    const state = l.model.species.filter(s => s.state).map(s => s.id);
    const outs = (demo?.outputs as string[] | undefined) ?? state.slice(0, 4);
    setOutputs(outs); setTargetOut(outs[0] ?? '');
    setTEnd(demo?.tEnd ?? 100);
    const firstParam = l.model.parameters.find(p => (p.value ?? 0) > 0)?.id ?? '';
    const s = demo?.sweep ?? {name: firstParam, min: 0, max: 0, steps: 9, log: true};
    const base = s.name.startsWith('init:') ? l.model.species.find(x => x.id === s.name.slice(5))?.initial : l.model.parameters.find(p => p.id === s.name)?.value;
    setSweep({name: s.name, min: s.min || (base ? base / 4 : 0.1), max: s.max || (base ? base * 4 : 10), steps: s.steps ?? 9, log: s.log ?? true});
    const second = l.model.parameters.filter(p => (p.value ?? 0) > 0 && p.id !== s.name)[0];
    if (second) setSweepB({name: second.id, min: second.value! / 4, max: second.value! * 4, steps: 7, log: true});
    setUncertain(l.model.parameters.filter(p => (p.value ?? 0) > 0).slice(0, 3).map(p => p.id));
    return l;
  }
  async function loadDemo(id: string) {
    const l = await call<Loaded>('Loading demonstration', 'mech_load', {source: 'demo', id});
    if (!l) return;
    adopt(l, l.demo);
    await simulate(l, l.demo.tEnd);
    const v = await call<any>('Running validation checks', 'mech_validate', {id});
    if (v) setChecks(v.checks);
  }
  async function loadBioModel(id: string) {
    const l = await call<Loaded>('Downloading ' + id + ' from BioModels', 'mech_load', {source: 'biomodels', id});
    if (l) { adopt(l); if (l.model.executable) await simulate(l, 100); }
  }
  async function importFile(f: File) {
    if (f.size > 8 * 1024 * 1024) { setError('SBML files are limited to 8 MB.'); return; }
    const l = await call<Loaded>('Reading ' + f.name, 'mech_load', {source: 'sbml', text: await f.text(), name: f.name});
    if (l) { adopt(l); if (l.model.executable) await simulate(l, 100); }
  }
  const common = () => ({key: loaded!.key, tEnd, method, rtol, overrides, initial});
  async function simulate(l = loaded, end = tEnd) {
    if (!l) return;
    const r = await call<any>('Integrating the model', 'mech_simulate', {key: l.key, tEnd: end, points: 400, method, rtol, overrides: l === loaded ? overrides : {}, initial: l === loaded ? initial : {}});
    if (r) { setResult({kind: 'run', ...r}); setRunId(r.runId); setPlayhead(r.time.length - 1); setExperiment('run'); }
  }
  async function runExperiment() {
    if (!loaded) return;
    if (experiment === 'run') return simulate();
    const label = {scan: 'Scanning ' + sweep.name, scan2d: 'Scanning a parameter grid', uncertainty: 'Sampling parameter uncertainty', sensitivity: 'Computing sensitivity coefficients'}[experiment];
    const payload = experiment === 'scan' ? {...common(), sweep, target: targetOut, kind: readout}
      : experiment === 'scan2d' ? {...common(), a: sweep, b: sweepB, target: targetOut, kind: readout}
      : experiment === 'uncertainty' ? {...common(), target: targetOut, kind: readout, samples, seed, ranges: uncertain.map(name => { const v = name.startsWith('init:') ? loaded.model.species.find(s => s.id === name.slice(5))!.initial : paramValue(name); return {name, min: v / spread, max: v * spread, log: true}; })}
      : {...common(), target: targetOut, kind: readout};
    const r = await call<any>(label!, 'mech_' + experiment, payload);
    if (r) { setResult({...r, readoutKind: r.kind, kind: experiment}); setRunId(r.runId); }
  }
  async function exportRun() {
    if (!runId) return;
    const path = await chooseSave((loaded?.model.id ?? 'experiment') + '.omex');
    if (!path) return;
    const r = await call<any>('Writing COMBINE archive', 'mech_export', {runId, path});
    if (r) setError('');
  }
  const paramValue = (id: string) => overrides[id] ?? loaded?.model.parameters.find(p => p.id === id)?.value ?? 0;

  useEffect(() => {
    if (!playing || result?.kind !== 'run') return;
    let frame = 0, last = performance.now();
    const tick = (now: number) => { if (now - last > 40) { last = now; setPlayhead(p => { if (p >= result.time.length - 1) { setPlaying(false); return p; } return p + 1; }); } frame = requestAnimationFrame(tick); };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing, result]);

  const m = loaded?.model;
  const unit = concentrationUnit(m?.units), tu = short(m?.units.time ?? 's');
  const run = result?.kind === 'run' ? result : null;
  const values = useMemo(() => run ? Object.fromEntries(Object.entries(run.series as Record<string, number[]>).map(([k, v]) => [k, v[Math.min(playhead, v.length - 1)]])) : undefined, [run, playhead]);
  const maxima = useMemo(() => run ? Object.fromEntries(Object.entries(run.series as Record<string, number[]>).map(([k, v]) => [k, Math.max(...v)])) : undefined, [run]);
  const sweepables = m ? [...m.parameters.map(p => ({id: p.id, label: p.id + (p.units ? ' · ' + p.units : '')})), ...m.species.map(s => ({id: 'init:' + s.id, label: 'initial ' + s.id + ' · ' + unit}))] : [];
  const reaction = m?.reactions.find(r => r.id === selected);
  const provenance = loaded?.demo?.provenance ?? {};
  const diagnostics = run?.diagnostics;

  return <div className="mech-shell"><div className={'mech-lab' + (leftOpen ? '' : ' left-closed') + (rightOpen ? '' : ' right-closed')}>
    <header className="mech-head">
      <div><span className="eyebrow">Analyse · Mechanistic Biology Lab</span><h1>Mechanisms, <em>in numbers.</em></h1></div>
      <p>Published and composed kinetic models, integrated with SciPy and traceable to their equations and sources. Numbers come only from executed calculations; a converged solver says nothing about whether the biology is right.</p>
    </header>

    <aside className="mech-left mech-panel">
      <button className="mech-collapse" onClick={() => setLeftOpen(!leftOpen)} aria-label={leftOpen ? 'Collapse' : 'Expand'}>{leftOpen ? <ChevronLeft size={15}/> : <ChevronRight size={15}/>}</button>
      {leftOpen && <>
        <section>
          <span className="eyebrow">Target</span>
          <form className="mech-search" onSubmit={e => { e.preventDefault(); void runSearch(); }}><Search size={15}/><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Protein, gene or pathway — e.g. EGFR"/></form>
          {search?.proteins.results.map((p: any) => <button key={p.accession} className={'mech-hit' + (target?.accession === p.accession ? ' active' : '')} onClick={() => chooseTarget(p)}>
            <strong>{p.genes[0] ?? p.accession}</strong><span>{p.name}</span><small>{p.accession} · {p.organism}</small></button>)}
          {target && <div className="mech-target"><span className="eyebrow">UniProt {target.accession}</span><p>{target.function || 'No function annotation.'}</p>{target.locations?.length > 0 && <small>{target.locations.join(' · ')}</small>}</div>}
        </section>
        {discovery && <section>
          <span className="eyebrow">Published models · {discovery.models.length}</span>
          {discovery.models.map((d: any) => <button key={d.id} className="mech-model" onClick={() => loadBioModel(d.id)} disabled={!d.executable}>
            <strong>{d.name}</strong><small>{d.id} · {d.why}</small>{!d.executable && <small className="mech-warn">{d.unsupported[0]}</small>}</button>)}
          {discovery.models.length === 0 && <p className="caption">No published model found for this target. The pathways remain available as qualitative knowledge.</p>}
        </section>}
        <section>
          <span className="eyebrow">Validated demonstrations</span>
          {catalog?.demos.map((d: any) => <button key={d.id} className={'mech-model' + (loaded?.key === 'demo:' + d.id ? ' active' : '')} onClick={() => loadDemo(d.id)}><strong>{d.title}</strong><small>{d.question}</small></button>)}
        </section>
        <section>
          <span className="eyebrow">Your model</span>
          <button className="button" onClick={() => file.current?.click()}><FileUp size={14}/>Import SBML</button>
          <input ref={file} type="file" accept=".xml,.sbml" hidden onChange={e => { const f = e.target.files?.[0]; if (f) void importFile(f); e.target.value = ''; }}/>
        </section>
      </>}
    </aside>

    <main className="mech-centre mech-panel">
      <div className="mech-centre-bar">
        <div className="cosmos-segment"><button className={centre === 'network' ? 'active' : ''} onClick={() => setCentre('network')} disabled={!m}>Reaction network</button><button className={centre === 'knowledge' ? 'active' : ''} onClick={() => setCentre('knowledge')} disabled={!discovery}>Knowledge graph</button></div>
        {m && <span className="mech-model-name">{m.name}</span>}
      </div>
      {centre === 'network' && m && <ReactionNetwork model={m} values={values} maxima={maxima} selected={selected} highlight={highlight} onSelect={id => { setSelected(id); setInspector('equations'); setRightOpen(true); }}/>}
      {centre === 'knowledge' && discovery && <KnowledgeGraph graph={discovery.graph as GraphData} onModel={id => loadBioModel(id)}/>}
      {centre === 'knowledge' && !discovery && <div className="mech-empty"><Search size={30}/><p>Search for a target to see its pathways and published models.</p></div>}
      {!m && centre === 'network' && <div className="mech-empty"><Sigma size={30}/><p>Choose a demonstration or a published model.</p></div>}
      {run && <div className="mech-playbar">
        <button className="story-play" onClick={() => { if (playhead >= run.time.length - 1) setPlayhead(0); setPlaying(!playing); }} aria-label={playing ? 'Pause' : 'Play'}>{playing ? <Pause size={15}/> : <Play size={15}/>}</button>
        <input type="range" min={0} max={run.time.length - 1} value={playhead} onChange={e => { setPlaying(false); setPlayhead(Number(e.target.value)); }} aria-label="Time"/>
        <span className="mono">t = {fmt(run.time[playhead], 4)} {tu}</span>
        <span className="evidence-badge mech-quant">Computed concentrations · not a spatial or atomic trajectory</span>
      </div>}
    </main>

    <aside className="mech-right mech-panel">
      <button className="mech-collapse right" onClick={() => setRightOpen(!rightOpen)} aria-label={rightOpen ? 'Collapse' : 'Expand'}>{rightOpen ? <ChevronRight size={15}/> : <ChevronLeft size={15}/>}</button>
      {rightOpen && m && <>
        <div className="cosmos-segment mech-tabs">{(['evidence', 'equations', 'parameters'] as const).map(t => <button key={t} className={inspector === t ? 'active' : ''} onClick={() => setInspector(t)}>{t[0].toUpperCase() + t.slice(1)}</button>)}</div>
        {inspector === 'evidence' && <div className="mech-inspect">
          {loaded?.demo?.evidence && <span className="evidence-badge">{loaded.demo.evidence}</span>}
          {loaded?.demo?.question && <p className="mech-question">{loaded.demo.question}</p>}
          <dl>
            <dt>Source</dt><dd>{m.source?.kind === 'biomodels' ? <>BioModels {m.source.id}{m.source.curation ? ' · ' + m.source.curation.toLowerCase() : ''}{m.source.retrieved ? ' · retrieved ' + m.source.retrieved.slice(0, 10) : ''}{m.source.bundled ? ' · bundled copy' : ''}</> : m.source?.kind === 'composed' ? 'Composed from the mechanism library' : 'Imported SBML file'}</dd>
            {m.source?.publication?.title && <><dt>Publication</dt><dd>{m.source.publication.title}{m.source.publication.link && <> · <a href={m.source.publication.link} target="_blank" rel="noreferrer">{m.source.publication.link.replace('http://identifiers.org/', '')}</a></>}</dd></>}
            <dt>Model</dt><dd>SBML L{m.level}V{m.version} · {m.species.length} species · {m.reactions.length} reactions · SHA-256 <code>{m.sha256.slice(0, 12)}</code></dd>
            <dt>Units</dt><dd>{unit} · time in {m.units.time}</dd>
            <dt>Executable</dt><dd>{m.executable ? 'Yes, unmodified' : 'No — ' + m.unsupported.join('; ')}</dd>
          </dl>
          {checks && <div className="mech-checks"><span className="eyebrow">Validation</span>{checks.map((c: any) => <div key={c.check} className={'mech-check ' + (c.passed ? 'ok' : 'fail')}>{c.passed ? <Check size={14}/> : <X size={14}/>}<div><strong>{c.check}</strong><span>{c.detail}{c.value !== null && c.value !== undefined ? ' · ' + fmt(c.value, 3) : ''}{c.threshold ? ' (limit ' + fmt(c.threshold, 1) + ')' : ''}</span></div></div>)}</div>}
          {diagnostics && <div className="mech-checks"><span className="eyebrow">Last calculation</span>
            <div className={'mech-check ' + (diagnostics.reliable ? 'ok' : 'fail')}>{diagnostics.reliable ? <Check size={14}/> : <TriangleAlert size={14}/>}<div><strong>{diagnostics.reliable ? 'Numerically reliable' : 'Check the numerics'}</strong>
              <span>{run.solver.method} · rtol {run.solver.rtol} · {diagnostics.rhsEvaluations} evaluations · tolerance sensitivity {fmt(diagnostics.toleranceSensitivity, 2)} · {diagnostics.conservation.laws} conservation laws, drift {fmt(diagnostics.conservation.maxRelativeDrift, 2)}</span></div></div>
            <p className="caption">Numerical reliability is about the calculation, not about whether the model describes the biology.</p></div>}
          {m.references?.length > 0 && <div className="mech-refs"><span className="eyebrow">Cross-references</span>{m.references.slice(0, 10).map((r: any) => <a key={r.uri} href={r.uri} target="_blank" rel="noreferrer">{r.database}:{r.accession}</a>)}</div>}
        </div>}
        {inspector === 'equations' && <div className="mech-inspect">
          {reaction ? <div className="mech-reaction"><span className="eyebrow">Reaction {reaction.id}</span><h3>{reaction.name}</h3><p className="mono">{reaction.scheme}</p><p className="mech-equation">v = {reaction.rate}</p>
            <span className="eyebrow">Symbols</span>{reaction.parameters.map(pid => { const p = m.parameters.find(x => x.id === pid); return p && <button key={pid} className={'mech-symbol' + (highlight === pid ? ' active' : '')} onClick={() => setHighlight(highlight === pid ? null : pid)}><code>{pid}</code><span>{fmt(paramValue(pid), 4)} {p.units ?? ''}</span><small>{provenance[pid]?.kind ?? p.provenance} · used by {p.usedBy.length} reaction{p.usedBy.length === 1 ? '' : 's'}</small></button>; })}
            {reaction.modifiers.length > 0 && <p className="caption">Modifiers: {reaction.modifiers.join(', ')}</p>}
            <button className="text-button" onClick={() => setSelected(null)}>All reactions<ArrowRight size={13}/></button></div>
          : <>{m.reactions.slice(0, 200).map(r => <button key={r.id} className="mech-rx-row" onClick={() => setSelected(r.id)}><code>{r.id}</code><span>{r.scheme}</span></button>)}
            <span className="eyebrow">Differential equations</span>{m.odes.slice(0, 60).map(o => <p key={o.species} className="mono mech-ode">{o.equation}</p>)}</>}
        </div>}
        {inspector === 'parameters' && <div className="mech-inspect">
          <p className="caption">Edit a value to run a hypothetical variant. The original stays in the model file; edits are recorded in each run.</p>
          {m.parameters.slice(0, 250).map(p => <div key={p.id} className={'mech-param' + (overrides[p.id] !== undefined ? ' changed' : '') + (highlight === p.id ? ' active' : '')}>
            <button className="mech-param-name" onClick={() => setHighlight(highlight === p.id ? null : p.id)}><code>{p.id}</code><small>{p.units ?? 'units not declared'} · {provenance[p.id]?.kind === 'literature' ? provenance[p.id].derivation + ' · ' + provenance[p.id].doi : provenance[p.id]?.kind ?? p.provenance}</small></button>
            <input type="number" value={overrides[p.id] ?? p.value ?? ''} step="any" onChange={e => { const v = Number(e.target.value); setOverrides(o => { const n = {...o}; if (e.target.value === '' || v === p.value) delete n[p.id]; else n[p.id] = v; return n; }); }}/>
          </div>)}
          {Object.keys(overrides).length > 0 && <button className="text-button" onClick={() => setOverrides({})}>Restore published values</button>}
        </div>}
      </>}
    </aside>

    <section className="mech-bottom mech-panel">
      <div className="mech-exp-bar">
        <div className="cosmos-segment">{experiments.map(([id, label]) => <button key={id} className={experiment === id ? 'active' : ''} onClick={() => setExperiment(id)} disabled={!m?.executable}>{label}</button>)}</div>
        <label>End time ({tu})<input type="number" value={tEnd} min={0} step="any" onChange={e => setTEnd(Number(e.target.value))}/></label>
        <label>Integrator<select value={method} onChange={e => setMethod(e.target.value)}>{(catalog?.methods ?? ['LSODA']).map((x: string) => <option key={x}>{x}</option>)}</select></label>
        <label>Rel. tolerance<select value={rtol} onChange={e => setRtol(Number(e.target.value))}>{[1e-6, 1e-8, 1e-10].map(x => <option key={x} value={x}>{x.toExponential(0)}</option>)}</select></label>
        <button className="button primary" disabled={!m?.executable || !!busy} onClick={runExperiment}><FlaskConical size={14}/>Run</button>
        <button className="button" disabled={!runId || !!busy} onClick={exportRun} title="SBML + SED-ML + CSV + JSON record"><Download size={14}/>Export .omex</button>
      </div>
      {m && experiment !== 'run' && <div className="mech-exp-settings">
        <label>Output<select value={targetOut} onChange={e => setTargetOut(e.target.value)}>{m.species.map(s => <option key={s.id} value={s.id}>{s.id}</option>)}</select></label>
        <label>Readout<select value={readout} onChange={e => setReadout(e.target.value)}>{readouts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        {(experiment === 'scan' || experiment === 'scan2d') && [[sweep, setSweep, 'Vary'] as const, ...(experiment === 'scan2d' ? [[sweepB, setSweepB, 'and'] as const] : [])].map(([s, set, label]) => <div key={label} className="mech-sweep">
          <label>{label}<select value={s.name} onChange={e => set({...s, name: e.target.value})}>{sweepables.map(x => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
          <label>From<input type="number" step="any" value={s.min} onChange={e => set({...s, min: Number(e.target.value)})}/></label>
          <label>To<input type="number" step="any" value={s.max} onChange={e => set({...s, max: Number(e.target.value)})}/></label>
          <label>Steps<input type="number" min={2} max={60} value={s.steps} onChange={e => set({...s, steps: Number(e.target.value)})}/></label>
          <label className="checkbox-label"><input type="checkbox" checked={s.log} onChange={e => set({...s, log: e.target.checked})}/>Log</label>
        </div>)}
        {experiment === 'uncertainty' && <>
          <label>Uncertain parameters<select multiple value={uncertain} onChange={e => setUncertain([...e.target.selectedOptions].map(o => o.value))} className="mech-multi">{sweepables.map(x => <option key={x.id} value={x.id}>{x.label}</option>)}</select></label>
          <label>Spread (÷/×)<input type="number" min={1.05} step="0.05" value={spread} onChange={e => setSpread(Number(e.target.value))}/></label>
          <label>Samples<input type="number" min={8} max={400} value={samples} onChange={e => setSamples(Number(e.target.value))}/></label>
          <label>Seed<input type="number" value={seed} onChange={e => setSeed(Number(e.target.value))}/></label>
        </>}
      </div>}
      {experiment === 'run' && m && <div className="mech-outputs">{m.species.slice(0, 60).map(s => <button key={s.id} className={outputs.includes(s.id) ? 'on' : ''} onClick={() => setOutputs(o => o.includes(s.id) ? o.filter(x => x !== s.id) : o.length < 6 ? [...o, s.id] : o)}>{s.id}</button>)}</div>}
      <div className="mech-results">
        {busy && <div className="mech-busy"><LoaderCircle size={16} className="spin"/>{busy}…</div>}
        {error && <div className="mech-error" role="alert"><TriangleAlert size={15}/>{error}</div>}
        {run && experiment === 'run' && <TimeChart time={run.time} timeUnit={tu} unit={'Concentration (' + unit + ')'} playhead={playhead} series={outputs.filter(o => run.series[o]).map(o => ({id: o, label: o, values: run.series[o]}))}/>}
        {result?.kind === 'scan' && experiment === 'scan' && <><ScanChart values={result.values} readout={result.readout} log={result.sweep.log} xLabel={result.sweep.name.replace('init:', 'initial ')} yLabel={`${readouts.find(r => r[0] === result.readoutKind)?.[1] ?? result.readoutKind} of ${result.target} (${result.readoutKind === 'time_of_max' ? tu : result.readoutKind === 'auc' ? unit + '·' + tu : unit})`}/>
          <TimeChart time={result.time} timeUnit={tu} unit={result.target + ' (' + unit + ')'} series={result.curves.filter((_: any, i: number) => i % Math.ceil(result.curves.length / 6) === 0).slice(0, 6).map((c: number[], i: number) => ({id: String(i), label: fmt(result.values[i * Math.ceil(result.curves.length / 6)], 3), values: c}))}/></>}
        {result?.kind === 'scan2d' && experiment === 'scan2d' && <Heatmap a={{name: result.a.name, values: result.a.values}} b={{name: result.b.name, values: result.b.values}} grid={result.grid} label={(readouts.find(r => r[0] === result.readoutKind)?.[1] ?? result.readoutKind) + ' of ' + result.target}/>}
        {result?.kind === 'uncertainty' && experiment === 'uncertainty' && <div className="mech-split">
          <TimeChart time={result.time} timeUnit={tu} unit={result.target + ' (' + unit + ')'} series={[{id: 'median', label: 'Median', values: result.bands['50']}]} bands={{lo: result.bands['5'], hi: result.bands['95'], lo50: result.bands['25'], hi50: result.bands['75']}}/>
          <div><span className="eyebrow">Global sensitivity · Spearman ρ</span><SensitivityBars label="Rank correlation with the readout" items={result.sensitivity.map((s: any) => ({name: s.name, value: s.spearman}))}/>
            <p className="caption">Bands: 5–95 % and 25–75 % of {samples} Latin-hypercube samples (seed {result.seed}). Readout 5/50/95 %: {fmt(result.summary['5'])} · {fmt(result.summary['50'])} · {fmt(result.summary['95'])} {unit}. {result.failures ? result.failures + ' samples failed and are excluded.' : ''}</p></div>
        </div>}
        {result?.kind === 'sensitivity' && experiment === 'sensitivity' && <div className="mech-split"><div><span className="eyebrow">Local sensitivity · ∂ ln y / ∂ ln p</span><SensitivityBars label="Normalised sensitivity coefficients" items={result.coefficients.map((c: any) => ({name: c.name, value: c.sensitivity}))}/></div>
          <p className="caption">Central differences of ±{result.step * 100}% around the current values. A coefficient of 1 means a 1% change in the parameter moves the {readouts.find(r => r[0] === result.readoutKind)?.[1].toLowerCase()} of {result.target} by 1%. Baseline {fmt(result.baseline)}.</p></div>}
        {!busy && !result && !error && <p className="caption mech-hint">Run an experiment to see quantitative results here.</p>}
      </div>
    </section>
  </div></div>;
}
