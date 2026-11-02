import {useEffect, useState} from 'react';
import {LoaderCircle, Play} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');

/** Stacked bar per gene: share of tumors where the mutation looks clonal, indeterminate or subclonal. */
function ClonalBars({rows}: {rows: any[]}) {
  const W = 620, row = 18, H = rows.length * row + 24, X = (v: number) => 110 + v * (W - 130);
  return <svg viewBox={`0 0 ${W} ${H}`} className="onc-scatter" role="img" aria-label="Clonal share per gene">
    {rows.map((r, i) => { const y = 6 + i * row; return <g key={r.gene}>
      <text x={104} y={y + 11} textAnchor="end">{r.gene} · {r.tumors}</text>
      <rect x={X(0)} y={y} width={X(r.clonal) - X(0)} height={row - 5} style={{fill: '#7ee0a1'}}/>
      <rect x={X(r.clonal)} y={y} width={X(r.clonal + r.indeterminate) - X(r.clonal)} height={row - 5} style={{fill: 'rgba(200,210,230,.35)'}}/>
      <rect x={X(r.clonal + r.indeterminate)} y={y} width={X(1) - X(r.clonal + r.indeterminate)} height={row - 5} style={{fill: '#ff8a6b'}}/></g>; })}
    <text x={X(0)} y={H - 4}>0</text><text x={X(1)} y={H - 4} textAnchor="end">100 % of tumors with the mutation · green clonal-like · grey indeterminate · orange subclonal</text></svg>;
}

function Lines({p}: {p: any}) {
  const W = 620, H = 220, L = 40, B = 26, t = p.time as number[], top = Math.max(...p.sensitive.map((v: number, i: number) => v + p.resistant[i]), 1e-9);
  const X = (v: number) => L + v / t[t.length - 1] * (W - L - 10), Y = (v: number) => H - B - v / top * (H - B - 10);
  const path = (ys: number[]) => ys.map((y, i) => `${i ? 'L' : 'M'}${X(t[i]).toFixed(1)},${Y(y).toFixed(1)}`).join('');
  return <svg viewBox={`0 0 ${W} ${H}`} className="onc-scatter" role="img" aria-label="Projected clone sizes">
    <rect x={X(p.params.drugStart)} y={8} width={Math.max(0, X(Math.min(p.params.drugStop, t[t.length - 1])) - X(p.params.drugStart))} height={H - B - 8} style={{fill: 'rgba(143,168,255,.08)'}}/>
    <line x1={L} x2={W - 10} y1={H - B} y2={H - B} className="grid"/>
    <path d={path(p.sensitive)} fill="none" stroke="#5fd4ff" strokeWidth={1.8}/><path d={path(p.resistant)} fill="none" stroke="#ff8a6b" strokeWidth={1.8}/>
    <text x={W - 12} y={16} textAnchor="end" style={{fill: '#5fd4ff', opacity: 1}}>sensitive</text><text x={W - 12} y={30} textAnchor="end" style={{fill: '#ff8a6b', opacity: 1}}>resistant</text>
    <text x={W / 2} y={H - 6} textAnchor="middle">days (shaded = drug on) · burden relative to carrying capacity</text></svg>;
}

/** Clonal populations: approximate clonality observed in sequenced tumors, kept apart from a hypothetical selection model. */
export default function Clonal({projectId}: {projectId: string}) {
  const [studies, setStudies] = useState<any[]>([]), [study, setStudy] = useState('luad_tcga_pan_can_atlas_2018'), [obs, setObs] = useState<any>(null);
  const [q, setQ] = useState({r_s: 0.03, r_r: 0.02, kill: 0.06, resistant0: 0.01, start: 30, stop: 180, t_end: 365}), [proj, setProj] = useState<any>(null), [busy, setBusy] = useState(''), [error, setError] = useState('');
  useEffect(() => { rpc<any>('onc_cohorts', {projectId}).then(c => setStudies(c.installed ?? [])).catch(() => {}); void project(); }, []);
  async function go(label: string, f: () => Promise<void>) { setBusy(label); setError(''); try { await f(); } catch (e) { setError(err(e)); } finally { setBusy(''); } }
  async function project(v = q) { try { setProj(await rpc('onc_clonal_projection', {projectId, ...v})); } catch (e) { setError(err(e)); } }
  const field = (k: keyof typeof q, label: string, step: number) => <label className="caption">{label}<input className="field" type="number" step={step} value={q[k]} onChange={e => { const v = {...q, [k]: Number(e.target.value)}; setQ(v); void project(v); }}/></label>;
  return <>
    <div className="page-heading"><div><span className="eyebrow">CLONAL POPULATIONS · OBSERVED READ COUNTS · HYPOTHETICAL SELECTION MODEL</span><h1>Which mutations came first, <em>and what selection could do next.</em></h1>
      <p>The upper half reads sequenced tumors: how often each gene's mutation looks clonal, from read counts. The lower half is a stated mathematical model of two competing clones under a drug; its curves are consequences of your assumptions, not observations.</p></div></div>
    <section className="quiet-panel"><span className="eyebrow">Observed · relative clonality in a patient cohort</span>
      <div className="onc-row onc-sim-form"><label className="caption">Cohort<select className="field" value={study} onChange={e => setStudy(e.target.value)}>{studies.map((m: any) => <option key={m.study} value={m.study}>{m.name}</option>)}</select></label>
        <button className="button primary" onClick={() => go('Reading read counts', async () => setObs(await rpc('onc_clonal', {projectId, study})))}><Play size={14}/>Analyse</button></div>
      {error && <p className="caption cs-error">{error}</p>}{busy && <p className="caption"><LoaderCircle size={12} className="spin"/> {busy}…</p>}
      {obs && <>
        <p className="caption"><span className="onc-evidence">{obs.evidence}</span> {obs.tumors} tumors with ≥ 3 usable mutations · excluded: {obs.skipped.copyAltered} in copy-altered genes, {obs.skipped.lowDepth} with fewer reads than required.</p>
        <ClonalBars rows={obs.genes.slice(0, 30)}/>
        <p className="caption">Method: {obs.method}. {obs.caveat}</p></>}
      {studies.length === 0 && <p className="caption">Install a cohort in Patient genomics first.</p>}</section>
    <section className="quiet-panel"><span className="eyebrow">Hypothetical · two clones under therapy</span>
      <div className="onc-row onc-sim-form">{field('r_s', 'Sensitive growth (/day)', 0.005)}{field('r_r', 'Resistant growth (/day)', 0.005)}{field('kill', 'Drug kill of sensitive (/day)', 0.01)}
        {field('resistant0', 'Resistant fraction at start', 0.005)}{field('start', 'Drug starts (day)', 5)}{field('stop', 'Drug stops (day)', 5)}{field('t_end', 'Days simulated', 30)}</div>
      {proj && <><Lines p={proj}/>
        <p>{proj.timeToResistantMajority != null ? `The resistant clone becomes the majority on day ${Math.round(proj.timeToResistantMajority)}.` : 'The resistant clone never becomes the majority in this window.'} Burden {fmt(proj.burdenAtStop, 3)} when the drug stops, {fmt(proj.burdenAtEnd, 3)} at the end.</p>
        <p className="caption"><span className="onc-evidence">{proj.evidence}</span> {proj.caveat} You can start from an observed subclone share above; that still leaves every rate an assumption.</p></>}
    </section>
  </>;
}
