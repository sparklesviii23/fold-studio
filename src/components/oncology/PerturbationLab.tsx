import {useEffect, useState} from 'react';
import {Check, CircleSlash, LoaderCircle, Play, Plus, Trash2, TriangleAlert, X} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');
const PAL = ['#5fd4ff', '#ff8a6b', '#7ee0a1', '#ffd166', '#c6a7ff'];
/** Engine kinds in reading order, each with the colour that marks its evidence class everywhere on the page. */
const KIND: [string, string, string][] = [['simulator', 'Mechanistic simulation', '#7ee0a1'], ['measured data', 'Experimental observation', '#5fd4ff'], ['statistical', 'Statistical association', '#ffd166'],
  ['AI model', 'AI prediction', '#c6a7ff'], ['curated knowledge', 'Curated evidence', '#8fa8ff'], ['error', 'Engine error', '#ff8a6b']];
const colour = (k: string) => KIND.find(x => x[0] === k)?.[2] ?? '#888';
const num = (v: any) => v == null ? '—' : typeof v === 'number' ? (v !== 0 && Math.abs(v) < 1e-3 ? v.toExponential(2) : Number.isInteger(v) ? String(v) : fmt(v, 3)) : String(v);
const change = (a: any, b: any) => typeof a === 'number' && typeof b === 'number' && a !== 0 ? `${b - a >= 0 ? '+' : ''}${((b - a) / Math.abs(a) * 100).toFixed(0)} %` : '';

type Pert = {kind: string; gene?: string; strength?: number; pair?: string; factor?: number; drug?: string; conc?: number | null};
const DEFAULT: Record<string, Pert> = {gene: {kind: 'gene', gene: 'EGFR', strength: 0.9}, interaction: {kind: 'interaction', pair: 'MEK–ERK', factor: 0.3},
  compound: {kind: 'compound', drug: 'GDSC2:1168', strength: 0.9, conc: 0.1}, immune: {kind: 'immune', factor: 2}};

function Series({s}: {s: any}) {
  const keys = Object.keys(s.baseline), W = 380, H = 200, L = 46, B = 26, t = s.time as number[];
  const top = Math.max(1e-9, ...keys.flatMap(k => [...s.baseline[k], ...s.perturbed[k]]));
  const X = (v: number) => L + v / t[t.length - 1] * (W - L - 8), Y = (v: number) => H - B - v / top * (H - B - 10);
  const path = (ys: number[]) => ys.map((y, i) => `${i ? 'L' : 'M'}${X(t[i]).toFixed(1)},${Y(y).toFixed(1)}`).join('');
  return <svg viewBox={`0 0 ${W} ${H}`} className="onc-scatter" role="img" aria-label="Baseline and perturbed time courses">
    <line x1={L} x2={W - 8} y1={H - B} y2={H - B} className="grid"/><line x1={L} x2={L} y1={6} y2={H - B} className="grid"/>
    {keys.map((k, i) => <g key={k}><path d={path(s.baseline[k])} fill="none" stroke={PAL[i]} strokeWidth={1.3} strokeDasharray="4 3" opacity={0.6}/><path d={path(s.perturbed[k])} fill="none" stroke={PAL[i]} strokeWidth={1.9}/>
      <text x={W - 10} y={14 + i * 12} textAnchor="end" style={{fill: PAL[i], opacity: 1}}>{k}</text></g>)}
    <text x={L - 4} y={12} textAnchor="end">{num(top)}</text><text x={W / 2} y={H - 6} textAnchor="middle">{s.unit} · dashed = baseline, solid = perturbed</text></svg>;
}

function EngineCard({e}: {e: any}) {
  return <section className="quiet-panel onc-engine" style={{borderLeftColor: colour(e.kind)}}>
    <div className="onc-engine-head"><span className="onc-evidence" style={{color: colour(e.kind)}}>{e.evidence || e.kind}</span>
      <span className="caption">{e.status === 'ran' ? <><Check size={12} className="ok"/> ran</> : e.status === 'unavailable' ? <><TriangleAlert size={12}/> unavailable</> : e.status === 'error' ? <><TriangleAlert size={12} className="bad"/> error</> : <><CircleSlash size={12}/> nothing to represent</>}</span></div>
    <h3>{e.name}</h3>{e.summary && <p>{e.summary}</p>}
    {e.represented?.length > 0 && <ul className="onc-repr">{e.represented.map((r: string) => <li key={r}><Check size={12} className="ok"/>{r}</li>)}</ul>}
    {e.ignored?.length > 0 && <ul className="onc-repr dim">{e.ignored.map((r: string) => <li key={r}><X size={12}/>{r}<small> · not represented by this engine</small></li>)}</ul>}
    {e.metrics?.length > 0 && <table className="tme-table"><thead><tr><th>Readout</th><th>Baseline</th><th>Perturbed / value</th><th>Change</th></tr></thead>
      <tbody>{e.metrics.map((m: any[], i: number) => <tr key={i}><td>{m[0]}</td><td>{num(m[1])}</td><td>{num(m[2])}</td><td>{change(m[1], m[2])}</td></tr>)}</tbody></table>}
    {e.series && <Series s={e.series}/>}
    {e.caveats?.length > 0 && <ul className="tme-checks">{e.caveats.map((c: string) => <li key={c}><TriangleAlert size={13}/><div><span>{c}</span></div></li>)}</ul>}
  </section>;
}

/** Perturbation lab: build a system, apply perturbations, and read every engine's answer with its evidence class kept separate. */
export default function PerturbationLab({projectId}: {projectId: string}) {
  const [spec, setSpec] = useState<any>(null), [system, setSystem] = useState({lineage: 'Lung', study: 'luad_tcga_pan_can_atlas_2018'}), [perts, setPerts] = useState<Pert[]>([DEFAULT.compound, DEFAULT.immune]);
  const [list, setList] = useState<any>(null), [res, setRes] = useState<any>(null), [openId, setOpenId] = useState(''), [pending, setPending] = useState(''), [confirm, setConfirm] = useState(''), [error, setError] = useState('');
  const refresh = async () => { try { const l = await rpc<any>('onc_pl_list', {projectId}); setList(l); return l; } catch (e) { setError(err(e)); } };
  async function open(id: string) { setOpenId(id); setRes(null); setError(''); try { setRes(await rpc('onc_pl_result', {projectId, id})); } catch (e) { setError(err(e)); } }
  useEffect(() => { rpc<any>('onc_pl_spec', {projectId}).then(setSpec).catch(e => setError(err(e))); void refresh().then(l => { const f = l?.runs.find((r: any) => r.done); if (f) void open(f.id); }); }, []);
  useEffect(() => { if (!list?.runs.some((r: any) => r.running)) return;
    const t = setTimeout(async () => { const l = await refresh(); const r = l?.runs.find((x: any) => x.id === pending); if (r && !r.running) { setPending(''); if (r.done) void open(r.id); } }, 2000); return () => clearTimeout(t); }, [list]);
  async function run() { setError(''); try { const l = await rpc<any>('onc_pl_run', {projectId, system, perturbations: perts}); setList(l); setPending(l.started); } catch (e) { setError(err(e)); } }
  async function remove(id: string) { if (confirm !== id) { setConfirm(id); return; } try { setList(await rpc('onc_pl_delete', {projectId, id})); setConfirm(''); if (id === openId) { setRes(null); setOpenId(''); } } catch (e) { setError(err(e)); } }
  const set = (i: number, v: Partial<Pert>) => setPerts(perts.map((p, j) => j === i ? {...p, ...v} : p));
  const drugName = (k?: string) => spec?.drugs.find((d: any) => d.key === k);
  if (!spec) return <section className="quiet-panel">{error ? <p className="caption cs-error">{error}</p> : <p className="caption"><LoaderCircle size={12} className="spin"/> Reading the engines…</p>}</section>;
  const engineIds: string[] = res ? res.engines.map((e: any) => e.id) : [];
  return <>
    <div className="page-heading"><div><span className="eyebrow">PERTURBATION LAB · ALL ENGINES, ONE EXPERIMENT</span><h1>Change one thing, <em>ask every engine.</em></h1>
      <p>Inhibit a gene, change an interaction, add a compound or alter immune infiltration. Simulators compute what their mechanisms imply; measured screens, patient associations, AI models and curated records answer beside them. No engine feeds another, so each answer keeps its evidence class.</p></div></div>
    <section className="quiet-panel">
      <span className="eyebrow">System</span>
      <div className="onc-row onc-sim-form">
        <label className="caption">Cancer lineage (DepMap, GDSC)<select className="field" value={system.lineage} onChange={e => setSystem({...system, lineage: e.target.value})}>{spec.lineages.map((l: string) => <option key={l}>{l}</option>)}</select></label>
        <label className="caption">Patient cohort<select className="field" value={system.study} onChange={e => setSystem({...system, study: e.target.value})}><option value="">none</option>{spec.studies.map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      </div>
      <span className="eyebrow">Perturbations (applied together)</span>
      {perts.map((p, i) => <div key={i} className="onc-row onc-sim-form onc-pert">
        <label className="caption">Kind<select className="field" value={p.kind} onChange={e => set(i, DEFAULT[e.target.value])}>
          <option value="gene">inhibit a gene</option><option value="interaction">change an interaction</option><option value="compound">administer a compound</option><option value="immune">alter immune infiltration</option></select></label>
        {p.kind === 'gene' && <label className="caption">Gene<input className="field" list="pl-genes" value={p.gene} onChange={e => set(i, {gene: e.target.value.toUpperCase()})}/></label>}
        {p.kind === 'interaction' && <label className="caption">Interaction<select className="field" value={p.pair} onChange={e => set(i, {pair: e.target.value})}>{spec.interactions.map((x: string) => <option key={x}>{x}</option>)}</select></label>}
        {p.kind === 'compound' && <label className="caption">Compound (GDSC)<select className="field" value={p.drug} onChange={e => set(i, {drug: e.target.value})}>{spec.drugs.map((d: any) => <option key={d.key} value={d.key}>{d.name} · {d.target} · {d.dataset}</option>)}</select></label>}
        {p.kind === 'compound' && <label className="caption">Dose model<select className="field" value={p.conc != null ? 'conc' : 'assumed'} onChange={e => set(i, {conc: e.target.value === 'conc' ? 0.1 : null})}>
          <option value="conc">concentration → ChEMBL potency</option><option value="assumed">assumed target inhibition</option></select></label>}
        {p.kind === 'compound' && p.conc != null && <label className="caption">Free concentration (µM)<input className="field" type="number" min={0.0001} max={1000} step="any" value={p.conc} onChange={e => set(i, {conc: Number(e.target.value)})}/></label>}
        {(p.kind === 'gene' || (p.kind === 'compound' && p.conc == null)) && <label className="caption">{p.kind === 'gene' ? 'Inhibition' : 'Assumed target inhibition'} {Math.round((p.strength ?? 0) * 100)} %<input type="range" min={0} max={1} step={0.05} value={p.strength} onChange={e => set(i, {strength: Number(e.target.value)})}/></label>}
        {(p.kind === 'interaction' || p.kind === 'immune') && <label className="caption">{p.kind === 'immune' ? 'Effector influx' : 'Strength'} × {p.factor}<input type="range" min={0} max={p.kind === 'immune' ? 5 : 3} step={0.1} value={p.factor} onChange={e => set(i, {factor: Number(e.target.value)})}/></label>}
        {perts.length > 1 && <button className="button" onClick={() => setPerts(perts.filter((_, j) => j !== i))} aria-label="Remove perturbation"><X size={13}/></button>}
      </div>)}
      <datalist id="pl-genes">{spec.mappedGenes.map((g: string) => <option key={g} value={g}/>)}</datalist>
      <div className="onc-row">{perts.length < 4 && <button className="button" onClick={() => setPerts([...perts, DEFAULT.gene])}><Plus size={13}/>Add perturbation</button>}
        <button className="button primary" onClick={run}><Play size={14}/>Run experiment</button>
        <span className="caption">{spec.runtimeReady ? 'Human-GEM runs in the science runtime (~10 s).' : 'Science runtime missing: Human-GEM will report unavailable.'}</span></div>
      {error && <p className="caption cs-error">{error}</p>}
      <details><summary className="caption">What the simulators contain ({spec.mappedGenes.length} genes and {spec.interactions.length} interactions mapped onto model terms)</summary>
        {spec.models.map((m: any) => <div key={m.id} className="caption onc-model-map"><strong>{m.name}</strong> · {m.context}.{Object.keys(m.genes).length > 0 && <> Genes: {Object.entries(m.genes).map(([g, w]) => `${g} (${w})`).join('; ')}.</>}{m.interactions.length > 0 && <> Interactions: {m.interactions.join(', ')}.</>}</div>)}
        <p className="caption">Any other gene still reaches DepMap, Human-GEM (if metabolic), the patient cohort and the evidence graph; compounds also reach GDSC and the response model.</p></details>
      {list && list.runs.length > 0 && <div className="onc-scroll"><table className="tme-table"><thead><tr><th>Experiment</th><th>Status</th><th/></tr></thead>
        <tbody>{list.runs.map((r: any) => <tr key={r.id} className={r.id === openId ? 'onc-current' : ''}><td>{r.title ?? r.experiment.perturbations.map((p: any) => p.gene ?? p.pair ?? drugName(p.drug)?.name ?? `immune × ${p.factor}`).join(' + ')}</td>
          <td>{r.running ? <span className="caption"><LoaderCircle size={12} className="spin"/> running</span> : r.done ? 'done' : <span className="bad" title={r.log}>failed</span>}</td>
          <td className="onc-actions">{r.done && <button className="button" onClick={() => open(r.id)}>{r.id === openId ? 'Open ✓' : 'Open'}</button>}
            {!r.running && <button className={'button ' + (confirm === r.id ? 'danger' : '')} onClick={() => remove(r.id)}><Trash2 size={13}/>{confirm === r.id ? 'Confirm delete' : 'Delete'}</button>}</td></tr>)}</tbody></table>
        {list.runs.filter((r: any) => r.failed && r.log).slice(0, 1).map((r: any) => <pre key={r.id} className="onc-log">{r.log}</pre>)}</div>}
    </section>
    {openId && !res && !error && <p className="caption"><LoaderCircle size={12} className="spin"/> Opening experiment…</p>}
    {res && <>
      <section className="quiet-panel">
        <span className="eyebrow">Which engine answered which perturbation · {res.system.lineage ?? ''}{res.system.study ? ' · ' + res.system.study : ''} · {res.seconds} s</span>
        <div className="onc-scroll"><table className="tme-table onc-matrix"><thead><tr><th>Perturbation</th>{res.engines.map((e: any) => <th key={e.id} title={e.name} style={{color: colour(e.kind)}}>{e.name.split(' (')[0]}</th>)}</tr></thead>
          <tbody>{res.matrix.map((m: any) => <tr key={m.perturbation}><td>{m.perturbation}</td>{engineIds.map(id => { const k = res.engines.find((e: any) => e.id === id).kind, st = m.engines[id];
            return <td key={id}>{st === 'ran' ? <i className="onc-dot" style={{background: colour(k)}} title="represented"/> : st === 'unavailable' ? '!' : '·'}</td>; })}</tr>)}</tbody></table></div>
        <div className="tme-legend onc-legend">{KIND.slice(0, 5).map(([k, l, c]) => <span key={k}><i style={{background: c}}/>{l}</span>)}</div>
        <p className="caption">{res.rule}</p>
      </section>
      {KIND.map(([k]) => res.engines.filter((e: any) => e.kind === k && e.status !== 'not applicable').map((e: any) => <EngineCard key={e.id} e={e}/>))}
      {res.engines.some((e: any) => e.status === 'not applicable') && <p className="caption">Not applicable to these perturbations: {res.engines.filter((e: any) => e.status === 'not applicable').map((e: any) => e.name).join('; ')}.</p>}
      <section className="quiet-panel"><span className="eyebrow">Outside what any engine here represents</span>
        <ul className="tme-checks">{res.outside.map((x: string) => <li key={x}><CircleSlash size={14}/><div><span>{x}</span></div></li>)}</ul></section>
    </>}
  </>;
}
