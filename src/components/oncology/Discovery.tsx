import {useEffect, useState} from 'react';
import {LoaderCircle, Play, Trash2, TriangleAlert} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');
/** Each step's evidence class keeps the colour it has in the Perturbation lab. */
const STEP_COLOUR = ['#5fd4ff', '#ffd166', '#ffd166', '#7ee0a1', '#8fa8ff', '#e8ecf4'];
const cell = (v: any) => v == null ? '—' : typeof v === 'number' ? (v !== 0 && Math.abs(v) < 1e-3 ? v.toExponential(1) : Number.isInteger(v) ? String(v) : fmt(v, 3)) : String(v);

const SCORE_ROWS: [string, string][] = [['support', 'Supporting experimental evidence'], ['replication', 'Independent replication'], ['modelQuality', 'Computational model quality'], ['plausibility', 'Biological plausibility'],
  ['alternatives', 'Alternative explanations'], ['normalTissue', 'Normal-tissue relevance'], ['uncertainty', 'Uncertainty'], ['contradictions', 'Contradictory evidence'], ['novelty', 'Novelty'], ['missing', 'Missing validation']];

/** The chain behind one candidate, step by step, each with its own evidence class (the causal-atlas view of a Demo L run). */
function traceOf(res: any, g: string) {
  const st = (n: number) => res.steps.find((s: any) => s.n === n), sc = res.scorecard.find((c: any) => c.candidate === g) ?? {};
  const rows = (n: number, pick: (r: any[]) => boolean): any[][] => (st(n)?.rows ?? []).filter(pick);
  const dep = rows(2, r => String(r[0]).split(' (')[0] === g)[0], drugs = rows(3, r => String(r[4]).split(', ').includes(g)), mech = rows(4, r => r[0] === g);
  return [
    {n: 1, title: 'Observed in patients', evidence: st(1)?.evidence, text: st(1)?.summary},
    {n: 2, title: 'Dependency in cell lines', evidence: st(2)?.evidence, text: dep ? `Δ gene effect ${Number(dep[1]).toFixed(2)} (q ${Number(dep[3]).toExponential(1)}) in ${res.question.gene}-${res.kind} lines; ${sc.alternatives ?? ''}` : 'not a candidate here'},
    {n: 2, title: 'Independent replication', evidence: 'Statistical association on an independent screen (Sanger Project Score)', text: sc.replication},
    {n: 3, title: 'Pharmacology', evidence: st(3)?.evidence, text: drugs.length ? drugs.map(r => `${r[0]} (Δ LN_IC50 ${Number(r[2]).toFixed(2)}, q ${Number(r[3]).toExponential(1)})`).join('; ') : 'no compound in GDSC targets it with a significant genotype effect'},
    {n: 4, title: 'Mechanism', evidence: st(4)?.evidence, text: mech.length ? mech.map(r => `${r[1]}: ${r[2]}`).join('; ') : 'not represented in any mechanistic model here'},
    {n: 5, title: 'Curated knowledge', evidence: st(5)?.evidence, text: st(5)?.summary},
    {n: 6, title: 'Remaining uncertainty', evidence: 'Synthesis', text: `${sc.uncertainty ?? ''}; contradictions: ${sc.contradictions ?? '—'}; missing: ${(sc.missing ?? []).join(', ')}`},
  ];
}

/** Demo L: a guided path from a patient observation to candidate targets, with each step's kind of evidence kept separate. */
export default function Discovery({projectId}: {projectId: string}) {
  const [spec, setSpec] = useState<any>(null), [q, setQ] = useState({gene: 'BRAF', kind: '', lineage: 'Skin', study: 'skcm_tcga_pan_can_atlas_2018', candidates: 5});
  const [trace, setTrace] = useState(''), [list, setList] = useState<any>(null), [res, setRes] = useState<any>(null), [openId, setOpenId] = useState(''), [pending, setPending] = useState(''), [confirm, setConfirm] = useState(''), [error, setError] = useState('');
  const refresh = async () => { try { const l = await rpc<any>('onc_dx_list', {projectId}); setList(l); return l; } catch (e) { setError(err(e)); } };
  async function open(id: string) { setOpenId(id); setRes(null); setError(''); try { setRes(await rpc('onc_dx_result', {projectId, id})); } catch (e) { setError(err(e)); } }
  useEffect(() => { rpc<any>('onc_pl_spec', {projectId}).then(setSpec).catch(e => setError(err(e))); void refresh().then(l => { const f = l?.runs.find((r: any) => r.done); if (f) void open(f.id); }); }, []);
  useEffect(() => { if (!list?.runs.some((r: any) => r.running)) return;
    const t = setTimeout(async () => { const l = await refresh(); const r = l?.runs.find((x: any) => x.id === pending); if (r && !r.running) { setPending(''); if (r.done) void open(r.id); } }, 2000); return () => clearTimeout(t); }, [list]);
  async function run() { setError(''); try { const l = await rpc<any>('onc_dx_run', {projectId, ...q, kind: q.kind || null}); setList(l); setPending(l.started); } catch (e) { setError(err(e)); } }
  async function remove(id: string) { if (confirm !== id) { setConfirm(id); return; } try { setList(await rpc('onc_dx_delete', {projectId, id})); setConfirm(''); if (id === openId) { setRes(null); setOpenId(''); } } catch (e) { setError(err(e)); } }
  return <>
    <div className="page-heading"><div><span className="eyebrow">DEMO L · INTEGRATED DISCOVERY WORKFLOW</span><h1>From a patient observation <em>to a testable target.</em></h1>
      <p>Start from a driver seen in patients. Measured CRISPR screens propose dependencies, measured drug screens propose compounds, mechanistic models show what inhibiting each candidate implies, and curated records say what is already known. Each step is a different kind of evidence; the result is a hypothesis to test, never a treatment.</p></div></div>
    <section className="quiet-panel">
      <div className="onc-row onc-sim-form">
        <label className="caption">Driver gene<input className="field" value={q.gene} onChange={e => setQ({...q, gene: e.target.value.toUpperCase()})}/></label>
        <label className="caption">Alteration<select className="field" value={q.kind} onChange={e => setQ({...q, kind: e.target.value})}><option value="">automatic (hotspot for oncogenes, damaging otherwise)</option><option value="hotspot">hotspot mutation</option><option value="damaging">damaging mutation</option></select></label>
        <label className="caption">Lineage<select className="field" value={q.lineage} onChange={e => setQ({...q, lineage: e.target.value})}>{(spec?.lineages ?? [q.lineage]).map((l: string) => <option key={l}>{l}</option>)}</select></label>
        <label className="caption">Patient cohort<select className="field" value={q.study} onChange={e => setQ({...q, study: e.target.value})}><option value="">none</option>{(spec?.studies ?? []).map((s: any) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
        <label className="caption">Candidates<input className="field" type="number" min={1} max={10} value={q.candidates} onChange={e => setQ({...q, candidates: Number(e.target.value)})}/></label>
        <button className="button primary" onClick={run}><Play size={14}/>Run workflow (~15 s)</button></div>
      {error && <p className="caption cs-error">{error}</p>}
      {list && list.runs.length > 0 && <div className="onc-scroll"><table className="tme-table"><thead><tr><th>Question</th><th>Candidates</th><th>Status</th><th/></tr></thead>
        <tbody>{list.runs.map((r: any) => <tr key={r.id} className={r.id === openId ? 'onc-current' : ''}><td>{r.title ?? r.question.gene}</td><td>{r.candidates?.join(', ') ?? '—'}</td>
          <td>{r.running ? <span className="caption"><LoaderCircle size={12} className="spin"/> running</span> : r.done ? 'done' : <span className="bad" title={r.log}>failed</span>}</td>
          <td className="onc-actions">{r.done && <button className="button" onClick={() => open(r.id)}>{r.id === openId ? 'Open ✓' : 'Open'}</button>}
            {!r.running && <button className={'button ' + (confirm === r.id ? 'danger' : '')} onClick={() => remove(r.id)}><Trash2 size={13}/>{confirm === r.id ? 'Confirm delete' : 'Delete'}</button>}</td></tr>)}</tbody></table>
        {list.runs.filter((r: any) => r.failed && r.log).slice(0, 1).map((r: any) => <pre key={r.id} className="onc-log">{r.log}</pre>)}</div>}
    </section>
    {openId && !res && !error && <p className="caption"><LoaderCircle size={12} className="spin"/> Opening…</p>}
    {res?.scorecard?.length > 0 && !res.scorecard[0].error && <section className="quiet-panel"><span className="eyebrow">Scorecard · every dimension shown, none combined into a score</span>
      <div className="onc-scroll"><table className="tme-table onc-scorecard"><thead><tr><th>Dimension</th>{res.scorecard.map((c: any) => <th key={c.candidate}><button className={'gt-view ' + (trace === c.candidate ? 'selected' : '')} onClick={() => setTrace(trace === c.candidate ? '' : c.candidate)}>{c.candidate}</button></th>)}</tr></thead>
        <tbody>{SCORE_ROWS.map(([k, label]) => <tr key={k}><td>{label}</td>{res.scorecard.map((c: any) => <td key={c.candidate}>{Array.isArray(c[k]) ? (c[k].length ? c[k].join('; ') : '—') : c[k]}</td>)}</tr>)}</tbody></table></div>
      <p className="caption">Click a candidate to trace it back through the evidence. There is deliberately no overall percentage: a candidate's chance of becoming a therapy is not computable from these data.</p></section>}
    {res && trace && <section className="quiet-panel"><span className="eyebrow">Trace · {trace} back to its evidence</span>
      <ol className="onc-trace">{traceOf(res, trace).map((s: any, i: number) => <li key={i} style={{borderLeft: `3px solid ${STEP_COLOUR[s.n - 1] ?? '#888'}`, paddingLeft: 10}}><strong>{s.title}</strong><em>{s.evidence}</em><span>{s.text}</span></li>)}</ol></section>}
    {res && res.steps.map((st: any) => <section key={st.n} className="quiet-panel onc-engine" style={{borderLeftColor: STEP_COLOUR[st.n - 1]}}>
      <div className="onc-engine-head"><span className="onc-evidence" style={{color: STEP_COLOUR[st.n - 1]}}>{st.evidence}</span><span className="caption">step {st.n} of 6{st.status !== 'ran' ? ' · ' + st.status : ''}</span></div>
      <h3>{st.title}</h3><p>{st.summary}</p>
      {st.rows.length > 0 && <div className="onc-scroll"><table className="tme-table"><thead><tr>{st.columns.map((c: string) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{st.rows.map((r: any[], i: number) => <tr key={i}>{r.map((v, j) => <td key={j}>{cell(v)}</td>)}</tr>)}</tbody></table></div>}
      {st.notes.length > 0 && <ul className="tme-checks">{st.notes.map((n: string) => <li key={n}><TriangleAlert size={13}/><div><span>{n}</span></div></li>)}</ul>}
    </section>)}
  </>;
}
