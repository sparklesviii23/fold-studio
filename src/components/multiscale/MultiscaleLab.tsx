import {useEffect, useState} from 'react';
import {ArrowRight, Check, Dna, FlaskConical, GitBranch, History, LoaderCircle, RotateCcw, TriangleAlert, X} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt, SensitivityBars, TimeChart} from '../mechanistic/MechCharts';
import '../mechanistic/mechanistic.css';
import './multiscale.css';
import SpatialLab from './SpatialLab';
import MdLab from './MdLab';
import '../rna-lab/rna-lab.css';

type Demo = 'demo5'|'demo8'|'demo11'|'demo12';
const STAGE_ICON: Record<string, string> = {rna: 'RNA', translation: 'Ribosome', cell: 'Cell', body: 'Body', capillary: 'Vessel', binding: 'Plasma'};
const KIND_LABEL: Record<string, string> = {literature: 'Literature', database: 'Database', derived: 'Derived', hypothetical: 'Hypothetical', assumption: 'Assumption'};

function Trace({node, depth = 0}: {node: any; depth?: number}) {
  return <div className="ms-trace-node" style={{marginLeft: depth ? 18 : 0}}>
    {node.transfer && <div className="ms-trace-link"><GitBranch size={12}/>{node.transfer.how}{node.transfer.assumption && <em> · {node.transfer.assumption}</em>}</div>}
    <div className="ms-trace-card">
      <div className="ms-trace-head"><code>{node.output}</code><b>{fmt(node.value, 4)} {node.unit}</b><span className="ms-evidence">{node.evidence}</span></div>
      <p className="ms-trace-model">{node.model} · {node.family}</p>
      {node.equations.map((e: string) => <p key={e} className="mono ms-eq">{e}</p>)}
      {node.parameters.length > 0 && <div className="ms-trace-params">{node.parameters.map((p: any) => <span key={p.name} className={'ms-chip ' + p.kind} title={p.description}>
        {p.name} = {fmt(p.value, 4)} {p.unit === '1' ? '' : p.unit}<i>{KIND_LABEL[p.kind]}{p.source?.doi ? ' · ' + p.source.doi : ''}</i></span>)}</div>}
    </div>
    {node.upstream.map((u: any) => <Trace key={u.output} node={u} depth={depth + 1}/>)}
  </div>;
}

function StageChart({sid, r}: {sid: string; r: any}) {
  const d = r.data;
  if (sid === 'translation') return <TimeChart time={d.grid} timeUnit="s" unit="Proteins completed (one mRNA)" series={[{id: 'p', label: 'Proteins', values: d.produced}]}/>;
  if (sid === 'cell') return <TimeChart time={d.time} timeUnit="h" unit="Molecules per cell" series={[{id: 'pool', label: 'In secretory pathway', values: d.pool}, {id: 'sec', label: 'Secreted (cumulative)', values: d.secreted}]}/>;
  if (sid === 'body') return <TimeChart time={d.days} timeUnit="day" unit="Body albumin pool (g)" series={[{id: 'pool', label: 'Pool', values: d.pool}]}/>;
  if (sid === 'capillary') return <TimeChart time={d.series.map((s: any) => s.t)} timeUnit="s" unit="Outlet albumin (mol/m³)" series={[{id: 'out', label: 'Outlet cup-mixing', values: d.series.map((s: any) => s.outletCupMolPerM3)}, {id: 'mid', label: 'Mid-vessel mean', values: d.series.map((s: any) => s.midMeanMolPerM3)}]}/>;
  if (sid === 'binding') return <TimeChart time={d.time} timeUnit="s" unit="Concentration (nM)" series={[{id: 'free', label: 'Free ligand', values: d.free}, {id: 'cx', label: 'Albumin·ligand', values: d.complex}]}/>;
  if (sid === 'rna') {
    const idx = d.unpaired.map((_: number, i: number) => i + 1);
    return <><TimeChart time={idx} timeUnit="nt" unit="P(unpaired)" series={[{id: 'u', label: 'Unpaired probability', values: d.unpaired}]}/>
      <p className="caption">Start codon at nt {d.startIndex + 1}–{d.startIndex + 3}: P(unpaired) {d.augUnpaired.map((x: number) => fmt(x, 2)).join(', ')} · {d.backend === 'viennarna' ? 'ViennaRNA ' + d.backendVersion : 'built-in model'} · MFE {fmt(d.mfe.energy, 3)} kcal/mol</p>
      <p className="mono ms-db">{d.window}<br/>{d.mfe.structure}</p></>;
  }
  return null;
}

/** Analyse › Multiscale Experiments: one reference molecule followed through coupled engines. */
export default function MultiscaleLab() {
  const [demo, setDemo] = useState<Demo>('demo8'), [run, setRun] = useState<any>(null), [busy, setBusy] = useState(''), [error, setError] = useState('');
  const [selected, setSelected] = useState('translation'), [overrides, setOverrides] = useState<Record<string, number>>({}), [traceOut, setTraceOut] = useState('');
  const [runs, setRuns] = useState<any[]>([]), [label, setLabel] = useState('');

  async function call<T>(text: string, action: string, payload: any) {
    setBusy(text); setError('');
    try { return await rpc<T>(action, payload); } catch (e) { setError(String(e).replace(/^Error:\s*/, '')); } finally { setBusy(''); }
  }
  async function execute(samples = 0, over = overrides, name = label) {
    const r = await call<any>(samples ? `Running ${samples} coupled samples` : 'Running the coupled chain', 'multiscale_run', {demo, overrides: over, samples, seed: 1, label: name});
    if (r) { setRun(r); setTraceOut(r.outputs[r.outputs.length - 1]); refreshRuns(); }
  }
  async function refreshRuns() { const r = await call<any[]>('', 'multiscale_runs', {}); if (r) setRuns(r); }
  async function reopen(id: string) { const r = await call<any>('Opening saved run', 'multiscale_record', {id}); if (r) { setRun(r); setDemo(r.demo); setOverrides(r.overrides); setTraceOut(r.outputs[r.outputs.length - 1]); } }
  useEffect(() => { setOverrides({}); setRun(null); if (demo === 'demo5' || demo === 'demo8') void execute(0, {}, ''); }, [demo]);

  const stages: any[] = run?.model.stages ?? [];
  const stage = stages.find(s => s.id === selected) ?? stages[0];
  const res = stage && run?.results[stage.id];
  const transferInto = (sid: string) => run?.transfers.filter((t: any) => t.to.split('.')[0] === sid) ?? [];
  const failed = run?.checks.filter((c: any) => !c.passed) ?? [];

  return <div className="ms-lab">
    <header className="mech-head">
      <div><span className="eyebrow">Analyse · Multiscale experiments</span>{demo === 'demo12' ? <h1>Atoms <em>in motion.</em></h1> : demo === 'demo11' ? <h1>From membrane <em>to nucleus.</em></h1> : <h1>From mRNA <em>to plasma.</em></h1>}</div>
      <div className="cosmos-segment"><button className={demo === 'demo5' ? 'active' : ''} onClick={() => setDemo('demo5')}>Demo 5 · Protein biogenesis</button><button className={demo === 'demo8' ? 'active' : ''} onClick={() => setDemo('demo8')}>Demo 8 · Cross-laboratory chain</button><button className={demo === 'demo11' ? 'active' : ''} onClick={() => setDemo('demo11')}>Demo 11 · Spatial gradient</button><button className={demo === 'demo12' ? 'active' : ''} onClick={() => setDemo('demo12')}>Demo 12 · Molecular dynamics</button></div>
    </header>
    {demo === 'demo11' && <SpatialLab/>}
    {demo === 'demo12' && <MdLab/>}
    {(demo === 'demo5' || demo === 'demo8') && run && <p className="ms-question">{run.question}</p>}
    {(demo === 'demo5' || demo === 'demo8') && busy && <div className="mech-busy"><LoaderCircle size={16} className="spin"/>{busy}…</div>}
    {error && <div className="mech-error" role="alert"><TriangleAlert size={15}/>{error}</div>}

    {(demo === 'demo5' || demo === 'demo8') && run && <>
      <section className="ms-identity mech-panel">
        <Dna size={18}/>
        <div><strong>{run.entity.name}</strong><span>mRNA <a href="https://www.ncbi.nlm.nih.gov/nuccore/NM_000477.7" target="_blank" rel="noreferrer">{run.identity.mrna}</a> · protein <a href="https://www.uniprot.org/uniprotkb/P02768" target="_blank" rel="noreferrer">{run.identity.protein}</a> · {run.identity.senseCodons} codons</span></div>
        <span className={'ms-pill ' + (run.identity.translationMatchesUniProt ? 'ok' : 'fail')}>{run.identity.translationMatchesUniProt ? <Check size={12}/> : <X size={12}/>}CDS translation matches UniProt</span>
        <span className={'ms-pill ' + (failed.length ? 'fail' : 'ok')}>{failed.length ? <X size={12}/> : <Check size={12}/>}{run.checks.length - failed.length}/{run.checks.length} numerical checks</span>
        <span className="ms-env">{run.environment.viennarna ? 'ViennaRNA ' + run.environment.viennarna : 'built-in RNA model'} · SciPy {run.environment.scipy} · {fmt(run.seconds, 2)} s</span>
      </section>

      <div className="ms-chain" role="list">
        {stages.map((s, i) => { const r = run.results[s.id], t = transferInto(s.id); const sc = r.checks ?? [];
          return <div key={s.id} className="ms-step" role="listitem">
            {i > 0 && <div className="ms-arrow">{t.length ? t.map((x: any) => <span key={x.to}>{fmt(x.value, 3)} {x.unit}{x.unit !== x.convertedUnit && <> → {fmt(x.converted, 3)} {x.convertedUnit}</>}<small>{x.how}</small></span>) : <span className="ms-uncoupled">not coupled</span>}<ArrowRight size={14}/></div>}
            <button className={'ms-stage mech-panel ' + (selected === s.id ? 'active' : '')} onClick={() => setSelected(s.id)}>
              <span className="eyebrow">{STAGE_ICON[s.id] ?? s.id}</span>
              <strong>{s.title}</strong>
              {Object.entries(r.outputs).map(([k, v]) => <span key={k} className="ms-out"><code>{k}</code><b>{fmt(v as number, 3)}</b><i>{s.outputs[k] === '1' ? '' : s.outputs[k]}</i></span>)}
              <span className="ms-foot"><span className="ms-evidence">{run.model.stages.find((x: any) => x.id === s.id) && ({experimental: 'Experimental', physics: 'Physics-simulated', statistical: 'Statistically predicted', hypothesis: 'Parameterised hypothesis', illustrative: 'Illustrative'} as any)[s.evidence]}</span>
                {sc.length > 0 && <span className={'ms-pill ' + (sc.every((c: any) => c.passed) ? 'ok' : 'fail')}>{sc.filter((c: any) => c.passed).length}/{sc.length}</span>}</span>
            </button>
          </div>; })}
      </div>

      {stage && res && <section className="ms-detail">
        <div className="mech-panel ms-detail-main">
          <div className="ms-detail-head"><div><span className="eyebrow">{stage.family}</span><h2>{stage.title}</h2></div><span className="ms-engine">{stage.engine} · {fmt(res.seconds, 2)} s</span></div>
          <StageChart sid={stage.id} r={res}/>
          {res.checks?.map((c: any) => <div key={c.check} className={'mech-check ' + (c.passed ? 'ok' : 'fail')}>{c.passed ? <Check size={14}/> : <X size={14}/>}<div><strong>{c.check}</strong><span>{c.detail}</span></div></div>)}
        </div>
        <aside className="mech-panel ms-detail-side">
          <span className="eyebrow">Governing equations</span>
          {stage.equations.map((e: string) => <p key={e} className="mono ms-eq">{e}</p>)}
          <span className="eyebrow">Parameters</span>
          {stage.parameters.length === 0 && <p className="caption">Inputs come only from the reference sequence and upstream stages.</p>}
          {stage.parameters.map((p: any) => { const key = stage.id + '.' + p.name, editable = p.kind === 'hypothetical' || p.kind === 'assumption';
            return <div key={p.name} className={'ms-param ' + p.kind}>
              <div><code>{p.name}</code><span className={'ms-chip ' + p.kind}>{KIND_LABEL[p.kind]}</span></div>
              <small>{p.description}{p.range ? ` · explored ${fmt(p.range[0])}–${fmt(p.range[1])}` : ''}</small>
              {p.source?.doi && <small className="ms-source">“{p.source.quote}” — {p.source.context} · <a href={'https://doi.org/' + p.source.doi} target="_blank" rel="noreferrer">doi:{p.source.doi}</a></small>}
              {p.source?.url && !p.source.doi && <small className="ms-source"><a href={p.source.url} target="_blank" rel="noreferrer">{p.source.citation}</a></small>}
              <div className="ms-param-value">{editable ? <input type="number" step="any" value={overrides[key] ?? p.value} onChange={e => setOverrides(o => ({...o, [key]: Number(e.target.value)}))}/> : <b>{fmt(p.value, 5)}</b>}<span>{p.unit === '1' ? '' : p.unit}</span></div>
            </div>; })}
          <span className="eyebrow">Assumptions</span>
          <ul className="ms-list">{stage.assumptions.map((a: string) => <li key={a}>{a}</li>)}{stage.limitations.map((a: string) => <li key={a} className="ms-limit">{a}</li>)}</ul>
          <div className="ms-actions">
            <input placeholder="Scenario label" value={label} onChange={e => setLabel(e.target.value)}/>
            <button className="button primary" disabled={!!busy} onClick={() => execute()}><FlaskConical size={14}/>Re-run</button>
            {Object.keys(overrides).length > 0 && <button className="button" onClick={() => { setOverrides({}); void execute(0, {}, ''); }}><RotateCcw size={14}/>Defaults</button>}
          </div>
        </aside>
      </section>}

      {run.calibration && <section className="mech-panel ms-panel">
        <span className="eyebrow">Measured versus model</span>
        <table className="ms-table"><thead><tr><th>Quantity</th><th>Model</th><th>Reference</th><th>Difference</th><th>Source</th></tr></thead><tbody>
          {run.results.body.data.comparisons.map((c: any) => <tr key={c.quantity}><td>{c.quantity}</td><td>{fmt(c.model, 3)} {c.unit}</td><td>{fmt(c.reference, 3)} {c.unit}</td><td>{fmt((c.model - c.reference) / c.reference * 100, 3)} %</td><td><a href={'https://doi.org/' + c.source.doi} target="_blank" rel="noreferrer">Levitt & Levitt 2016</a> · {c.kind}</td></tr>)}
        </tbody></table>
        <div className={'ms-calibration ' + (run.calibration.feasibleAtCurrentCopies ? 'ok' : 'warn')}>
          <TriangleAlert size={16}/>
          <div>
            <strong>{run.calibration.feasibleAtCurrentCopies ? 'Measured synthesis is reachable with these assumptions.' : 'Measured synthesis is not reachable with these assumptions.'}</strong>
            <span>Matching {run.calibration.target} needs {fmt(run.calibration.requiredRatePerMRNA, 3)} proteins/s per mRNA; ribosome exclusion limits one mRNA to {fmt(run.calibration.maximalCurrent, 3)}/s. That implies at least {fmt(run.calibration.minimumCopiesAtMaximalCurrent, 3)} ALB mRNA copies per hepatocyte, or {fmt(run.calibration.requiredCopiesAtSimulatedRate, 3)} at the simulated rate.</span>
            <small>{run.calibration.note}</small>
          </div>
          {run.calibration.requiredCopiesAtSimulatedRate && <button className="button" onClick={() => { const o = {...overrides, 'cell.mrnaCopies': Math.round(run.calibration.requiredCopiesAtSimulatedRate)}; setOverrides(o); void execute(0, o, 'Calibrated to 10.5 g/day'); }}>Apply calibrated scenario</button>}
        </div>
      </section>}

      <section className="ms-grid">
        <div className="mech-panel ms-panel">
          <div className="ms-row"><span className="eyebrow">Uncertainty · hypothetical and assumed parameters</span><button className="button" disabled={!!busy} onClick={() => execute(32)}>Run 32 samples</button></div>
          {run.uncertainty ? <>{run.outputs.map((o: string) => { const s = run.uncertainty.summary[o]; return <div key={o} className="ms-unc"><code>{o}</code><span>{fmt(s.p5, 3)} · <b>{fmt(s.p50, 3)}</b> · {fmt(s.p95, 3)}</span></div>; })}
            <p className="caption">5th · median · 95th percentile over {run.uncertainty.samples} Latin-hypercube samples (seed {run.uncertainty.seed}).</p>
            <span className="eyebrow">What drives {traceOut}</span>
            <SensitivityBars label="Spearman rank correlation" items={(run.uncertainty.sensitivity[traceOut] ?? []).map((s: any) => ({name: s.parameter, value: s.spearman}))}/>
            <p className="caption">Only causally upstream parameters are ranked.</p></>
            : <p className="caption">Sample the uncertain inputs to see how widely the outputs move and which assumptions matter most.</p>}
        </div>
        <div className="mech-panel ms-panel">
          <div className="ms-row"><span className="eyebrow">Causal chain</span><select value={traceOut} onChange={e => setTraceOut(e.target.value)}>{run.outputs.map((o: string) => <option key={o} value={o}>{o}</option>)}</select></div>
          {run.traces[traceOut] && <Trace node={run.traces[traceOut]}/>}
        </div>
      </section>

      <section className="mech-panel ms-panel">
        <div className="ms-row"><span className="eyebrow"><History size={12}/> Saved runs</span><span className="caption">Record {run.id.slice(0, 10)} · SHA-256 {run.sha256.slice(0, 12)} · stored with inputs, sources, transfers and outputs</span></div>
        <div className="ms-runs">{runs.slice(0, 12).map(r => <button key={r.id} className={'ms-run ' + (r.id === run.id ? 'active' : '')} onClick={() => reopen(r.id)}>
          <strong>{r.label || (r.demo === 'demo5' ? 'Protein biogenesis' : 'Cross-laboratory chain')}</strong><span>{r.created.replace('T', ' ').slice(0, 16)} · {Object.keys(r.overrides).length} changed · {r.passed ? 'all checks pass' : 'check failed'}</span></button>)}</div>
      </section>
      <p className="cell-disclaimer">A research model, not a clinical prediction. Each result keeps its own evidence category; numerical checks show the calculations are correct, not that the biology is.</p>
    </>}
  </div>;
}
