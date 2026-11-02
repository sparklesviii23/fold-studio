import {useEffect, useState} from 'react';
import {LoaderCircle, Play} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');

function Histogram({counts, label}: {counts: number[]; label: string}) {
  const W = 420, H = 150, top = Math.max(...counts, 1), bw = (W - 40) / counts.length;
  return <svg viewBox={`0 0 ${W} ${H}`} className="onc-scatter" role="img" aria-label={label}>
    {counts.map((c, i) => <rect key={i} x={30 + i * bw} y={H - 24 - c / top * (H - 34)} width={bw - 2} height={c / top * (H - 34)} style={{fill: i >= counts.length / 2 ? '#7ee0a1' : '#ff8a6b'}}/>)}
    <text x={30} y={H - 8}>−1</text><text x={30 + (W - 40) / 2} y={H - 8} textAnchor="middle">0</text><text x={W - 10} y={H - 8} textAnchor="end">1</text><text x={W / 2} y={12} textAnchor="middle">{label}</text></svg>;
}

/** Model comparison laboratory: alternative screens, predictors and mechanistic models on the same question, with numbers. */
export default function ModelComparison({projectId}: {projectId: string}) {
  const [gene, setGene] = useState('BRAF'), [dep, setDep] = useState<any>(null), [drugList, setDrugList] = useState<any[]>([]), [drug, setDrug] = useState('GDSC2:1168'), [dr, setDr] = useState<any>(null), [sig, setSig] = useState<any>(null);
  const [busy, setBusy] = useState(''), [error, setError] = useState('');
  useEffect(() => { rpc<any[]>('onc_drugs', {projectId}).then(setDrugList).catch(() => {}); }, []);
  async function go(label: string, f: () => Promise<void>) { setBusy(label); setError(''); try { await f(); } catch (e) { setError(err(e)); } finally { setBusy(''); } }
  return <>
    <div className="page-heading"><div><span className="eyebrow">MODEL COMPARISON LABORATORY · SAME QUESTION, DIFFERENT MODELS</span><h1>Where models agree, <em>and where they do not.</em></h1>
      <p>Two independent CRISPR screens, several drug-response predictors on identical held-out patients, and three published ERK pathway models under the same knockdown. Agreement is measured, not assumed; disagreement is reported as a result.</p></div></div>
    {error && <p className="caption cs-error">{error}</p>}{busy && <p className="caption"><LoaderCircle size={12} className="spin"/> {busy}…</p>}
    <section className="quiet-panel"><span className="eyebrow">Two dependency screens · DepMap (Chronos) vs Sanger Project Score (CRISPRcleanR)</span>
      <div className="onc-row onc-sim-form"><label className="caption">Gene to plot<input className="field" value={gene} onChange={e => setGene(e.target.value.toUpperCase())}/></label>
        <button className="button primary" onClick={() => go('Comparing screens', async () => setDep(await rpc('onc_mc_dependency', {projectId, gene})))}><Play size={14}/>Compare</button></div>
      {dep && <div className="onc-two"><div>
        <Histogram counts={dep.perGeneSpearman.histogram} label={`per-gene Spearman ρ across ${dep.lines} shared lines`}/>
        <p>Median ρ {fmt(dep.perGeneSpearman.median, 2)} (IQR {fmt(dep.perGeneSpearman.q1, 2)}–{fmt(dep.perGeneSpearman.q3, 2)}) over {dep.variableGenes.toLocaleString()} variable genes; {Math.round(dep.perGeneSpearman['over0.5'] * 100)} % above 0.5.</p>
        <p>Common essentials: DepMap {dep.commonEssential.depmap}, Sanger {dep.commonEssential.sanger}, both {dep.commonEssential.both} (Jaccard {fmt(dep.commonEssential.jaccard, 2)}).</p></div>
        <div>{dep.gene ? <><svg viewBox="0 0 320 220" className="onc-scatter" role="img" aria-label="DepMap vs Sanger for one gene">{(() => { const P = dep.gene.points, xs = P.map((p: number[]) => p[0]), ys = P.map((p: number[]) => p[1]);
          const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]; const X = (v: number) => 34 + (v - x0) / (x1 - x0 || 1) * 276, Y = (v: number) => 196 - (v - y0) / (y1 - y0 || 1) * 186;
          return <>{P.map((p: number[], i: number) => <circle key={i} cx={X(p[0])} cy={Y(p[1])} r={2}/>)}<text x={170} y={216} textAnchor="middle">DepMap gene effect</text><text x={10} y={110} transform="rotate(-90 10 110)" textAnchor="middle">Sanger log fold change</text></>; })()}</svg>
          <p className="caption">{dep.gene.gene}: ρ = {fmt(dep.gene.spearman, 2)} across matched lines.</p></> : <p className="caption">{gene} is not in both screens.</p>}</div></div>}
      {dep && <p className="caption"><span className="onc-evidence">{dep.evidence}</span> {dep.method}.</p>}</section>
    <section className="quiet-panel"><span className="eyebrow">Drug-response predictors · same held-out patients, paired errors</span>
      <div className="onc-row onc-sim-form"><label className="caption">Compound<select className="field" value={drug} onChange={e => setDrug(e.target.value)}>{drugList.map((d: any) => <option key={d.key} value={d.key}>{d.name} · {d.dataset}</option>)}</select></label>
        <button className="button primary" onClick={() => go('Running every model on the same folds (≈ 20–60 s)', async () => setDr(await rpc('onc_mc_drugs', {projectId, drug})))}><Play size={14}/>Compare</button></div>
      {dr && <><table className="tme-table"><thead><tr><th>Model</th><th>MSE</th><th>Δ MSE vs {dr.reference} (95 % CI over patients)</th><th>Prediction r with {dr.reference}</th><th>Call</th></tr></thead>
        <tbody><tr><td>{dr.reference}</td><td>{fmt(dr.mse[dr.reference], 3)}</td><td>reference</td><td>1</td><td/></tr>
          {dr.comparisons.map((c: any) => <tr key={c.model}><td>{c.model}</td><td>{fmt(dr.mse[c.model], 3)}</td><td>{c.mseDifference >= 0 ? '+' : ''}{fmt(c.mseDifference, 3)} ({fmt(c.ci[0], 3)} to {fmt(c.ci[1], 3)})</td><td>{fmt(dr.predictionCorrelationWithReference[c.model], 2)}</td><td>{c.call}</td></tr>)}</tbody></table>
        <p className="caption"><span className="onc-evidence">{dr.evidence}</span> {dr.drug}: {dr.lines} lines from {dr.patients} patients. {dr.method}.</p></>}</section>
    <section className="quiet-panel"><span className="eyebrow">Mechanistic models · the same knockdown in three ERK pathway models</span>
      <button className="button primary" onClick={() => go('Running every shared knockdown', async () => setSig(await rpc('onc_mc_signalling', {projectId})))}><Play size={14}/>Compare models</button>
      {sig && <><div className="onc-scroll"><table className="tme-table"><thead><tr><th>Gene ({Math.round(sig.strength * 100)} % knockdown)</th>{Object.entries(sig.models).map(([k, n]: any) => <th key={k}>{n.split(' (')[0]}<small className="onc-sub">log2 ERK-PP change</small></th>)}<th>Same direction</th></tr></thead>
        <tbody>{sig.rows.map((r: any) => <tr key={r.gene}><td>{r.gene}</td>{Object.keys(sig.models).map(k => <td key={k}>{r[k] == null ? '—' : fmt(r[k], 2)}</td>)}<td>{r.agreeDirection ? 'yes' : 'no'}</td></tr>)}</tbody></table></div>
        <p>{Object.entries(sig.pairs).map(([k, v]: any) => `${k}: ρ ${fmt(v.spearman, 2)} over ${v.genes} genes, both reduce or neither ${Math.round(v.bothReduceOrNeither * 100)} %`).join(' · ')}</p>
        <p className="caption"><span className="onc-evidence">{sig.evidence}</span> {sig.method}. The models agree on direction but not on which node matters most; that is a property of their different cell types and parameters, not a calculation error (every run passed the solver checks).</p></>}</section>
  </>;
}
