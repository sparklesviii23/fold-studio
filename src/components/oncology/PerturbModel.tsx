import {useEffect, useState} from 'react';
import {Download, LoaderCircle, Play, TriangleAlert} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');

function Results({r, ceiling}: {r: any; ceiling: any}) {
  return <table className="tme-table"><thead><tr><th>Model</th><th>Pearson, all scored genes</th><th>Pearson, top-20 changed genes</th><th>MSE</th></tr></thead>
    <tbody>{Object.entries(r).map(([k, v]: any) => <tr key={k}><td>{k}</td><td>{fmt(v.pearson.mean, 3)} ± {fmt(v.pearson.sd, 2)}</td><td>{fmt(v.pearsonTop20.mean, 3)} ± {fmt(v.pearsonTop20.sd, 2)}</td><td>{fmt(v.mse.mean, 3)}</td></tr>)}
      <tr className="onc-current"><td>noise ceiling (two halves of the same cells)</td><td>{fmt(ceiling.pearson.mean, 3)}</td><td>{fmt(ceiling.pearsonTop20.mean, 3)}</td><td>{fmt(ceiling.mse.mean, 3)}</td></tr></tbody></table>;
}

function Bars({ex}: {ex: any}) {
  const W = 620, row = 14, H = ex.genes.length * row + 24, top = Math.max(...ex.observed.map(Math.abs), ...ex.additive.map(Math.abs), 1e-9), X = (v: number) => 330 + v / top * 260;
  return <svg viewBox={`0 0 ${W} ${H}`} className="onc-scatter" role="img" aria-label={`Observed vs additive change for ${ex.perturbation}`}>
    <line x1={330} x2={330} y1={4} y2={H - 18} className="grid"/>
    {ex.genes.map((g: string, i: number) => { const y = 6 + i * row; return <g key={g}><text x={64} y={y + 9} textAnchor="end">{g}</text>
      <rect x={Math.min(X(0), X(ex.observed[i]))} y={y} width={Math.abs(X(ex.observed[i]) - X(0))} height={5} style={{fill: '#5fd4ff'}}/>
      <rect x={Math.min(X(0), X(ex.additive[i]))} y={y + 6} width={Math.abs(X(ex.additive[i]) - X(0))} height={5} style={{fill: '#ffd166'}}/></g>; })}
    <text x={W - 10} y={H - 4} textAnchor="end">blue observed · gold additive prediction (log-expression change vs control)</text></svg>;
}

/** Demo J: predicting transcriptional responses to unseen CRISPRa perturbations, against baselines and a noise ceiling. */
export default function PerturbModel({projectId}: {projectId: string}) {
  const [st, setSt] = useState<any>(null), [res, setRes] = useState<any>(null), [pick, setPick] = useState(0), [error, setError] = useState('');
  const read = async () => { try { const s = await rpc<any>('onc_pm_status', {projectId}); setSt(s); if (s.done && !s.job?.running && !res) setRes(await rpc('onc_pm_result', {projectId})); return s; } catch (e) { setError(err(e)); } };
  useEffect(() => { void read(); }, []);
  useEffect(() => { if (!st?.job?.running && !st?.download?.running) return; const t = setTimeout(async () => { const s = await read(); if (s?.done && !s.job?.running) setRes(await rpc('onc_pm_result', {projectId})); }, 3000); return () => clearTimeout(t); }, [st]);
  const act = async (a: string) => { setError(''); try { setSt(await rpc(a, {projectId})); } catch (e) { setError(err(e)); } };
  const examples = res ? [res.example, ...res.examplesWorst].filter(Boolean) : [];
  return <>
    <div className="page-heading"><div><span className="eyebrow">DEMO J · CELLULAR PERTURBATION MODEL · NORMAN 2019 PERTURB-SEQ (K562, CRISPRa)</span><h1>Predicting how cells respond <em>to perturbations never seen.</em></h1>
      <p>Single and paired gene activations measured by single-cell RNA-seq. Models are trained on some perturbations and scored on held-out ones against the measured expression change, next to simple baselines and the noise ceiling set by the data itself. A predicted expression change is not cell killing.</p></div></div>
    <section className="quiet-panel"><div className="onc-row">
      {!st?.installed && <button className="button primary" disabled={st?.download?.running} onClick={() => act('onc_pm_install')}><Download size={14}/>Download Norman 2019 (≈ 700 MB, MD5-verified)</button>}
      {st?.installed && <button className="button primary" disabled={st?.job?.running || !st?.runtimeReady} onClick={() => act('onc_pm_run')}><Play size={14}/>{res ? 'Run again' : 'Run the benchmark'} (≈ 2–5 min)</button>}
      {(st?.download?.running || st?.job?.running) && <span className="caption"><LoaderCircle size={12} className="spin"/> {st.download?.running ? `downloading · ${(st.bytes / 1e6).toFixed(0)} MB` : 'running'}…</span>}</div>
      {error && <p className="caption cs-error">{error}</p>}
      {(st?.job?.running || st?.download?.running) && <pre className="onc-log">{(st.job?.running ? st.job : st.download).log}</pre>}</section>
    {res && <>
      <section className="quiet-panel"><span className="onc-evidence">{res.evidence}</span>
        <p>{res.cells.toLocaleString()} cells ({res.controlCells.toLocaleString()} controls); {res.singles} single and {res.pairs} paired perturbations with ≥ 20 cells; {res.genesScored.toLocaleString()} genes scored (targets excluded); 5-fold splits over perturbations.</p>
        <span className="eyebrow">Unseen pairs (both singles seen in training)</span><Results r={res.results.pairs} ceiling={res.noiseCeiling}/>
        <span className="eyebrow">Unseen single perturbations</span><Results r={res.results.singles} ceiling={res.noiseCeiling}/>
        <ul className="onc-claims">{res.paired.map((d: any) => <li key={d.a + d.b}>{d.a} − {d.b} ({d.metric}, {d.n} perturbations): {fmt(d.meanDifference, 3)} (95 % CI {fmt(d.ci[0], 3)} to {fmt(d.ci[1], 3)}) — {d.ci[0] > 0 ? `${d.a} better` : d.ci[1] < 0 ? `${d.b} better` : 'no clear difference'}</li>)}</ul>
        <p className="caption">"No change" predicts zero everywhere, so its correlation is undefined (—); only its error is meaningful. The noise ceiling compares two halves of each perturbation's cells, each with half the cells, so it is conservative: a model scored against the full-cell profile can exceed it on the all-gene correlation.</p>
        <p className="caption">Method: {res.method}</p></section>
      {examples.length > 0 && <section className="quiet-panel"><span className="eyebrow">Predicted vs measured transcriptional change</span>
        <select className="field" value={pick} onChange={e => setPick(Number(e.target.value))}>{examples.map((x: any, i: number) => <option key={i} value={i}>{x.perturbation}{i === 0 ? ' (additive fits best)' : ' (largest departure from additivity)'}</option>)}</select>
        <Bars ex={examples[pick]}/></section>}
      <section className="quiet-panel"><span className="eyebrow">Genetic interactions · pairs that depart most from the sum of their singles</span>
        <table className="tme-table"><thead><tr><th>Pair</th><th>Cells</th><th>Scaling of the additive profile</th><th>Unexplained share</th><th>r with additive</th></tr></thead>
          <tbody>{res.interactions.slice(0, 15).map((x: any) => <tr key={x.pair}><td>{x.pair}</td><td>{x.cells}</td><td>{fmt(x.scaling, 2)}</td><td>{fmt(x.residualFraction, 2)}</td><td>{fmt(x.additivePearson, 2)}</td></tr>)}</tbody></table>
        <p className="caption">Scaling &gt; 1: the pair does more than the sum (synergy-like); &lt; 1: less (buffering). Median scaling {fmt(res.interactionScaling.median, 2)}. A departure from additivity in expression is a statistical deviation, not a demonstrated mechanism.</p>
        <ul className="tme-checks"><li><TriangleAlert size={13}/><div><span>{res.caveat} The State model (Arc Institute) is not run here: it needs GPU time on your server, and its command line and licence still need checking before a recipe is added.</span></div></li></ul></section>
    </>}
  </>;
}
