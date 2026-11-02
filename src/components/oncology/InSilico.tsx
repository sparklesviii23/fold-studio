import {Fragment, useEffect, useState} from 'react';
import {Check, CircleHelp, LoaderCircle, Play, Trash2, TriangleAlert} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');
const PAL = ['#5fd4ff', '#ff8a6b', '#7ee0a1', '#ffd166', '#c6a7ff', '#8fa8ff', '#ff6b9a', '#4fd1c5'];
const cell = (v: any) => typeof v === 'number' ? (v !== 0 && Math.abs(v) < 1e-3 ? v.toExponential(1) : Number.isInteger(v) ? String(v) : fmt(v, 3)) : typeof v === 'boolean' ? (v ? 'yes' : '—') : v ?? '—';

/** What each demo's synthetic run plants, in one sentence for the page. */
const BLURB: Record<string, string> = {
  atlas: 'Generates CRISPR gene effects with planted common essentials, lineage-selective and mutation-linked dependencies, a lineage-confounded mutation and sister lines, then runs the Dependency atlas statistics unchanged.',
  drugs: 'Generates expression and drug responses driven by a few planted biomarker genes plus lineage, and a null compound, then runs the held-out-patient benchmark unchanged.',
  synergy: 'Generates dose–response plates with a planted Bliss excess (or a drug combined with itself), then scores HSA, Bliss, Loewe and ZIP with the Synergy code and compares each with its noise-free value.',
  signatures: 'Mixes COSMIC v3.4 signatures at known exposures into SBS96 catalogues, then refits them with the Signatures code and measures what was recovered.',
  genomics: 'Generates a cohort with planted mutual exclusivity, co-occurrence, copy-number-driven expression, a survival effect and an age-confounded alteration, then runs the Patient genomics statistics unchanged.',
  singlecell: 'Generates donors × cells counts with a planted program in tumor keratinocytes and donor-to-donor variability, then runs the full single-cell pipeline (QC, Harmony, pseudobulk, pathways).',
  metabolism: 'Runs Human-GEM under your medium and gene knockouts. This is a mechanistic what-if with no planted answer: it shows what the stoichiometric model allows, not what a tumor does.',
};

function Frame({w = 360, h = 240, children, label}: {w?: number; h?: number; children: any; label: string}) {
  return <svg viewBox={`0 0 ${w} ${h}`} className="onc-scatter" role="img" aria-label={label}>{children}</svg>;
}
const range = (v: number[]) => { const a = Math.min(...v), b = Math.max(...v); return a === b ? [a - 1, b + 1] : [a, b]; };

function Plot({p}: {p: any}) {
  const W = 360, H = 240, L = 42, B = 30;
  if (p.kind === 'scatter' || p.kind === 'volcano' || p.kind === 'embedding') {
    const pts: [number, number, string, string][] = p.kind === 'scatter' ? p.points.map((q: number[]) => [q[0], q[1], '', ''])
      : p.kind === 'volcano' ? p.points.map((q: any[]) => [q[1], q[2], q[0], ''])
      : p.x.map((x: number, i: number) => [x, p.y[i], '', p.groups[i]]);
    const [x0, x1] = range(pts.map(q => q[0])), [y0, y1] = range(pts.map(q => q[1])), X = (v: number) => L + (v - x0) / (x1 - x0) * (W - L - 10), Y = (v: number) => H - B - (v - y0) / (y1 - y0) * (H - B - 12);
    const groups = p.kind === 'embedding' ? [...new Set(pts.map(q => q[3]))] : [], hi = new Set(p.highlight ?? []);
    return <Frame label={p.title}><line x1={L} x2={W - 10} y1={H - B} y2={H - B} className="grid"/><line x1={L} x2={L} y1={8} y2={H - B} className="grid"/>
      {p.kind === 'scatter' && <line x1={X(Math.max(x0, y0))} y1={Y(Math.max(x0, y0))} x2={X(Math.min(x1, y1))} y2={Y(Math.min(x1, y1))} className="grid" strokeDasharray="4 4"/>}
      {p.kind === 'volcano' && y1 > 1.3 && <line x1={L} x2={W - 10} y1={Y(1.301)} y2={Y(1.301)} className="grid" strokeDasharray="4 4"/>}
      {pts.map((q, i) => <circle key={i} cx={X(q[0])} cy={Y(q[1])} r={p.kind === 'embedding' ? 1.2 : hi.has(q[2]) ? 3 : 1.8}
        style={{fill: p.kind === 'embedding' ? PAL[groups.indexOf(q[3]) % PAL.length] : hi.has(q[2]) ? '#ff8a6b' : p.kind === 'volcano' && q[1] > 1.301 ? 'rgba(95,212,255,.7)' : undefined, opacity: p.kind === 'volcano' && !hi.has(q[2]) && q[1] <= 1.301 ? 0.3 : undefined}}/>)}
      <text x={W / 2} y={H - 6} textAnchor="middle">{p.kind === 'embedding' ? 'UMAP 1' : p.xLabel}</text>
      <text x={12} y={H / 2} transform={`rotate(-90 12 ${H / 2})`} textAnchor="middle">{p.kind === 'volcano' ? '−log10 q' : p.kind === 'embedding' ? 'UMAP 2' : p.yLabel}</text>
      {groups.map((g, i) => <text key={g} x={W - 12} y={16 + i * 13} textAnchor="end" style={{fill: PAL[i % PAL.length], opacity: 1}}>{g}</text>)}
      {p.kind === 'volcano' && hi.size > 0 && <text x={W - 12} y={16} textAnchor="end" style={{fill: '#ff8a6b', opacity: 1}}>planted</text>}</Frame>;
  }
  if (p.kind === 'bars') {
    const n = p.labels.length, k = p.series.length, top = Math.max(1e-9, ...p.series.flatMap((s: any) => s.values)), bw = (W - L - 10) / n;
    return <Frame label={p.title}><line x1={L} x2={W - 10} y1={H - B - 20} y2={H - B - 20} className="grid"/>
      {p.labels.map((l: string, i: number) => <g key={l}>{p.series.map((s: any, j: number) => { const h = s.values[i] / top * (H - B - 40); return <rect key={j} x={L + i * bw + 2 + j * (bw - 4) / k} y={H - B - 20 - h} width={(bw - 4) / k - 1} height={h} style={{fill: PAL[j]}}/>; })}
        <text x={L + i * bw + bw / 2} y={H - B - 6} textAnchor="middle" transform={n > 6 ? `rotate(-35 ${L + i * bw + bw / 2} ${H - B - 6})` : undefined}>{l}</text></g>)}
      <text x={L - 4} y={16} textAnchor="end">{fmt(top, 2)}</text>
      {k > 1 && p.series.map((s: any, j: number) => <text key={s.name} x={W - 12} y={16 + j * 13} textAnchor="end" style={{fill: PAL[j], opacity: 1}}>{s.name}</text>)}</Frame>;
  }
  if (p.kind === 'heatmap') {
    const m: (number | null)[][] = p.matrix ?? [], vals = m.flat().filter((v): v is number => v != null), lim = Math.max(1e-9, ...vals.map(Math.abs));
    const r = m.length, c = m[0]?.length ?? 1, cw = (W - 80) / c, ch = (H - 50) / Math.max(r, 1);
    const col = (v: number | null) => v == null ? 'rgba(120,130,150,.2)' : p.diverging ? (v >= 0 ? `rgba(255,138,107,${Math.abs(v) / lim})` : `rgba(95,180,255,${Math.abs(v) / lim})`) : `rgba(198,167,255,${v / lim})`;
    return <Frame label={p.title}>{m.map((row, i) => row.map((v, j) => <g key={i + '-' + j}><rect x={70 + j * cw} y={8 + (r - 1 - i) * ch} width={cw - 1} height={ch - 1} style={{fill: col(v)}}/>
      <text x={70 + j * cw + cw / 2} y={8 + (r - 1 - i) * ch + ch / 2 + 3} textAnchor="middle">{v == null ? '—' : p.diverging ? (v * 100).toFixed(0) : v.toFixed(2)}</text></g>))}
      {p.rows.map((l: string, i: number) => <text key={l} x={66} y={8 + (r - 1 - i) * ch + ch / 2 + 3} textAnchor="end">{l}</text>)}
      {p.cols.map((l: string, j: number) => <text key={l} x={70 + j * cw + cw / 2} y={H - 28} textAnchor="middle">{l}</text>)}
      <text x={W / 2 + 30} y={H - 8} textAnchor="middle">{p.colLabel}</text><text x={10} y={H / 2} transform={`rotate(-90 10 ${H / 2})`} textAnchor="middle">{p.rowLabel}</text></Frame>;
  }
  if (p.kind === 'km') {
    const cs = Object.entries(p.curves) as [string, number[][]][], t1 = Math.max(1, ...cs.flatMap(([, c]) => c.map(q => q[0])));
    const X = (v: number) => L + v / t1 * (W - L - 10), Y = (v: number) => H - B - v * (H - B - 12);
    const step = (c: number[][]) => c.map((q, i) => i === 0 ? `M${X(q[0])},${Y(q[1])}` : `H${X(q[0])}V${Y(q[1])}`).join('') + `H${X(t1)}`;
    return <Frame label={p.title}><line x1={L} x2={W - 10} y1={H - B} y2={H - B} className="grid"/><line x1={L} x2={L} y1={8} y2={H - B} className="grid"/>
      {cs.map(([k, c], i) => <path key={k} d={step(c)} fill="none" stroke={PAL[i]} strokeWidth={1.8}/>)}
      {cs.map(([k], i) => <text key={k} x={W - 12} y={16 + i * 13} textAnchor="end" style={{fill: PAL[i], opacity: 1}}>{k}</text>)}
      <text x={W / 2} y={H - 6} textAnchor="middle">months</text><text x={12} y={H / 2} transform={`rotate(-90 12 ${H / 2})`} textAnchor="middle">survival</text></Frame>;
  }
  return null;
}

function Field({f, v, set}: {f: any; v: any; set: (v: any) => void}) {
  return <label className="caption">{f.label}{f.kind === 'choice'
    ? <select className="field" value={v} onChange={e => set(e.target.value)}>{f.options.map((o: string) => <option key={o}>{o}</option>)}</select>
    : f.kind === 'text' ? <input className="field" value={v} onChange={e => set(e.target.value)}/>
    : <input className="field" type="number" min={f.min} max={f.max} step={f.step ?? (f.kind === 'int' ? 1 : 0.1)} value={v} onChange={e => set(e.target.value === '' ? '' : Number(e.target.value))}/>}</label>;
}

const summary = (spec: any, p: any) => spec.params.map((f: any) => `${f.label.replace(/ \(.*\)$/, '').toLowerCase()} ${p[f.key]}`).join(' · ');

/** The in-silico lab for one demo: set parameters, run, list, open and delete runs. Every run is stored under oncology/insilico/<demo>/. */
export default function InSilico({projectId, demo}: {projectId: string; demo: string}) {
  const [spec, setSpec] = useState<any>(null), [params, setParams] = useState<any>({}), [list, setList] = useState<any>(null), [res, setRes] = useState<any>(null);
  const [openId, setOpenId] = useState(''), [pending, setPending] = useState(''), [confirm, setConfirm] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const refresh = async () => { try { const l = await rpc<any>('onc_sim_list', {projectId, demo}); setList(l); return l; } catch (e) { setError(err(e)); } };
  async function open(id: string) { setOpenId(id); setRes(null); setError(''); try { setRes(await rpc('onc_sim_result', {projectId, demo, id})); } catch (e) { setError(err(e)); } }
  useEffect(() => { setRes(null); setOpenId(''); setList(null);
    rpc<any>('onc_sim_spec', {projectId}).then(s => { setSpec(s[demo]); setParams(Object.fromEntries(s[demo].params.map((f: any) => [f.key, f.default]))); }).catch(e => setError(err(e)));
    void refresh().then(l => { const first = l?.runs.find((r: any) => r.done); if (first) void open(first.id); }); }, [demo]);
  useEffect(() => { if (!list?.runs.some((r: any) => r.running)) return;
    const t = setTimeout(async () => { const l = await refresh(); const r = l?.runs.find((x: any) => x.id === pending); if (r && !r.running) { setPending(''); if (r.done) void open(r.id); } }, 2500); return () => clearTimeout(t); }, [list]);
  async function run() { setBusy(true); setError(''); try { const l = await rpc<any>('onc_sim_run', {projectId, demo, params}); setList(l); setPending(l.started); } catch (e) { setError(err(e)); } finally { setBusy(false); } }
  async function remove(id: string) { if (confirm !== id) { setConfirm(id); return; }
    try { setList(await rpc('onc_sim_delete', {projectId, demo, id})); setConfirm(''); if (id === openId) { setRes(null); setOpenId(''); } } catch (e) { setError(err(e)); } }
  if (!spec) return <section className="quiet-panel">{error ? <p className="caption cs-error">{error}</p> : <p className="caption"><LoaderCircle size={12} className="spin"/> Opening the in-silico lab…</p>}</section>;
  const synthetic = demo !== 'metabolism';
  return <>
    <section className="quiet-panel">
      <span className="eyebrow">In silico · {spec.title}</span>
      <p className="caption">{BLURB[demo]} {synthetic && 'Every result here tests the method on data whose answer is known; none of it is an observation about cancer.'}</p>
      <div className="onc-row onc-sim-form">{spec.params.map((f: any) => <Field key={f.key} f={f} v={params[f.key]} set={v => setParams({...params, [f.key]: v})}/>)}
        <button className="button primary" disabled={busy || !spec.runtimeReady} onClick={run}><Play size={14}/>{synthetic ? 'Generate and analyse' : 'Run simulation'}</button></div>
      {!spec.runtimeReady && <p className="caption cs-error">This simulation needs the science runtime (runtimes/singlecell).</p>}
      {error && <p className="caption cs-error">{error}</p>}
      {list && <div className="onc-scroll"><table className="tme-table"><thead><tr><th>Run</th><th>Status</th><th>Size</th><th/></tr></thead>
        <tbody>{list.runs.map((r: any) => <tr key={r.id} className={r.id === openId ? 'onc-current' : ''}><td>{r.title ?? summary(spec, r.params)}</td>
          <td>{r.running ? <span className="caption"><LoaderCircle size={12} className="spin"/> running</span> : r.done ? (synthetic ? `${r.passed} passed${r.failedChecks ? ` · ${r.failedChecks} failed` : ''}` : 'done') : <span className="bad" title={r.log}>failed</span>}</td>
          <td>{r.sizeMB} MB</td>
          <td className="onc-actions">{r.done && <button className="button" onClick={() => open(r.id)}>{r.id === openId ? 'Open ✓' : 'Open'}</button>}
            {!r.running && <button className={'button ' + (confirm === r.id ? 'danger' : '')} onClick={() => remove(r.id)}><Trash2 size={13}/>{confirm === r.id ? 'Confirm delete' : 'Delete'}</button>}</td></tr>)}
          {!list.runs.length && <tr><td colSpan={4}>No runs yet. Set the parameters above and press {synthetic ? 'Generate and analyse' : 'Run simulation'}.</td></tr>}</tbody></table>
        {list.runs.filter((r: any) => r.failed && r.log).slice(0, 1).map((r: any) => <pre key={r.id} className="onc-log">{r.log}</pre>)}</div>}
    </section>
    {openId && !res && !error && <p className="caption"><LoaderCircle size={12} className="spin"/> Opening run…</p>}
    {res && <>
      <section className="quiet-panel">
        <span className="onc-evidence">{res.evidence}</span><h3>{res.title}</h3>
        <p className="caption">Model: {res.model}. Method: {res.method}. {res.seconds} s · record {res.recordId?.slice(0, 8)}.</p>
        <ul className="tme-checks">{res.checks.map((c: any) => <li key={c.name}>{c.passed === true ? <Check size={14} className="ok"/> : c.passed === false ? <TriangleAlert size={14} className="bad"/> : <CircleHelp size={14}/>}
          <div><strong>{c.name}: {c.observed}</strong><span>{c.passed === null ? 'Reported, not scored' : 'Expected'}: {c.expected}{c.note ? '. ' + c.note : ''}</span></div></li>)}</ul>
        {res.truth && <details><summary className="caption">Planted truth</summary><dl className="onc-truth">{Object.entries(res.truth).map(([k, v]) => <Fragment key={k}><dt>{k}</dt><dd>{typeof v === 'object' ? JSON.stringify(v) : cell(v)}</dd></Fragment>)}</dl></details>}
      </section>
      {res.plots?.length > 0 && <section className="onc-two">{res.plots.map((p: any) => <div key={p.title} className="quiet-panel"><span className="eyebrow">{p.title}</span><Plot p={p}/></div>)}</section>}
      {res.tables?.map((t: any) => <section key={t.title} className="quiet-panel"><span className="eyebrow">{t.title}</span>
        <div className="onc-scroll"><table className="tme-table"><thead><tr>{t.columns.map((c: string) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>{t.rows.map((r: any[], i: number) => <tr key={i}>{r.map((v, j) => <td key={j}>{cell(v)}</td>)}</tr>)}</tbody></table></div></section>)}
    </>}
  </>;
}
