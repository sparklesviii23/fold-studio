import {useState} from 'react';
import {Check, CircleHelp, LoaderCircle, Search, X} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');
const sci = (v: number | null | undefined) => v == null ? '—' : v < 1e-3 ? v.toExponential(1) : fmt(v, 3);
/** Label colours: demonstrated (curated) vs predicted vs context-only, never merged. */
const LABEL: Record<string, string> = {'Experimentally demonstrated': '#8fa8ff', 'Predicted': '#c6a7ff', 'Context-specific': '#ffd166'};
const colour = (l: string) => LABEL[Object.keys(LABEL).find(k => l.startsWith(k)) ?? ''] ?? '#e8ecf4';

/** Synthetic-lethality research on measured CRISPR screens, keeping co-dependency, context dependency, demonstrated and predicted SL apart. */
export default function SyntheticLethality({projectId}: {projectId: string}) {
  const [gene, setGene] = useState('SMARCA4'), [kind, setKind] = useState('damaging'), [res, setRes] = useState<any>(null), [bench, setBench] = useState<any>(null), [busy, setBusy] = useState(''), [error, setError] = useState('');
  async function go(label: string, f: () => Promise<void>) { setBusy(label); setError(''); try { await f(); } catch (e) { setError(err(e)); } finally { setBusy(''); } }
  const run = () => go(`Scanning ${gene}`, async () => setRes(await rpc('onc_sl', {projectId, gene, kind})));
  return <>
    <div className="page-heading"><div><span className="eyebrow">SYNTHETIC LETHALITY · DEPMAP CRISPR · SANGER REPLICATION · REFERENCE PAIRS</span><h1>What becomes essential <em>when a gene is lost.</em></h1>
      <p>Four labels are kept apart: statistical co-dependency, context-specific dependency, predicted synthetic lethality (replicated in an independent screen), and experimentally demonstrated synthetic lethality from published experiments. No combinatorial knockout data are installed, so genetic-interaction scores are not computed.</p></div></div>
    <section className="quiet-panel"><div className="onc-row onc-sim-form">
      <label className="caption">Lost gene<input className="field" value={gene} onChange={e => setGene(e.target.value.toUpperCase())} onKeyDown={e => e.key === 'Enter' && run()}/></label>
      <label className="caption">Loss defined as<select className="field" value={kind} onChange={e => setKind(e.target.value)}><option value="damaging">damaging mutation</option><option value="expression">not expressed (deletion or silencing)</option><option value="hotspot">hotspot mutation</option></select></label>
      <button className="button primary" onClick={run}><Search size={14}/>Scan</button>
      <button className="button" onClick={() => go('Testing the reference pairs', async () => setBench(await rpc('onc_sl_benchmark', {projectId})))}>Benchmark against demonstrated pairs</button></div>
      {error && <p className="caption cs-error">{error}</p>}{busy && <p className="caption"><LoaderCircle size={12} className="spin"/> {busy}…</p>}</section>
    {bench && <section className="quiet-panel"><span className="eyebrow">Positive controls · experimentally demonstrated pairs</span>
      <p>Recovered: {bench.damaging.recovered} of {bench.damaging.testable} testable with damaging mutations; {bench.expression.recovered} of {bench.expression.testable} with loss of expression.</p>
      <div className="onc-scroll"><table className="tme-table"><thead><tr><th>Lost</th><th>Dependency</th><th>Mechanism</th><th>Damaging mutation</th><th>No expression</th><th>Source</th></tr></thead>
        <tbody>{bench.pairs.map((r: any) => <tr key={r.lost + r.dependency}><td>{r.lost}</td><td>{r.dependency}</td><td>{r.mechanism}</td>
          {(['damaging', 'expression'] as const).map(k => <td key={k}>{r[k].recovered == null ? <span title={r[k].note}><CircleHelp size={12}/> not testable</span> : <>{r[k].recovered ? <Check size={12} className="ok"/> : <X size={12} className="bad"/>} rank {r[k].rank ?? '—'} · β {fmt(r[k].beta, 2)} · q {sci(r[k].q)} · {r[k].lost} lost</>}</td>)}
          <td><small>{r.citation}</small></td></tr>)}</tbody></table></div>
      <p className="caption">{bench.note}</p></section>}
    {res && <>
      <section className="quiet-panel"><span className="eyebrow">Context-specific dependencies · {res.gene} {res.loss.kind === 'expression' ? 'not expressed' : res.loss.kind} in {res.loss.mutant} of {res.loss.n} independent models · {res.loss.lineages} lineages adjusted</span>
        {!res.loss.hits.length ? <p className="caption">No gene is significantly more essential where {res.gene} is lost (q &lt; 0.05).</p> :
        <div className="onc-scroll"><table className="tme-table"><thead><tr><th>Gene</th><th>Label</th><th>Δ gene effect</th><th>95 % CI</th><th>q</th><th>Paralog of {res.gene}</th><th>Sanger replication</th></tr></thead>
          <tbody>{res.loss.hits.map((h: any) => <tr key={h.gene}><td>{h.gene}</td><td><span className="onc-evidence" style={{color: colour(h.label)}}>{h.label}</span>{h.reference && <small className="onc-sub">{h.reference[1]}</small>}</td>
            <td>{fmt(h.beta, 3)}</td><td>{fmt(h.ci[0], 2)} to {fmt(h.ci[1], 2)}</td><td>{sci(h.q)}</td><td>{h.paralog ? h.paralog.replace('_', ' ') : res.loss.paralogsKnown ? '—' : 'not checked'}</td>
            <td>{h.replication ? `${fmt(h.replication.delta, 2)} (p ${sci(h.replication.p)})${h.replication.replicates ? ' · replicates' : ''}` : res.loss.kind === 'expression' ? 'n/a (expression loss)' : res.loss.replication?.note ?? 'not installed'}</td></tr>)}</tbody></table></div>}
        <p className="caption">{res.loss.method}. Predicted synthetic lethality = also significant in the independent Sanger Project Score screen. A context dependency is a hypothesis, not a demonstrated genetic interaction.</p></section>
      <section className="quiet-panel"><span className="eyebrow">Statistical co-dependency · genes whose knockout effects correlate with {res.gene}</span>
        {res.coDependency.error ? <p className="caption">{res.coDependency.error}</p> : <><table className="tme-table"><thead><tr><th>Gene</th><th>r (lineage removed)</th><th>q</th></tr></thead>
          <tbody>{res.coDependency.hits.slice(0, 15).map((h: any) => <tr key={h.gene}><td>{h.gene}</td><td>{fmt(h.r, 3)}</td><td>{sci(h.q)}</td></tr>)}</tbody></table>
          <p className="caption">{res.coDependency.method}. Co-dependency usually marks genes in one complex or pathway; it is not synthetic lethality.</p></>}</section>
    </>}
  </>;
}
