import {useEffect, useState} from 'react';
import {Check, FlaskConical, History, LoaderCircle, RotateCcw, TriangleAlert, X} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt, ScanChart, TimeChart} from '../mechanistic/MechCharts';

const KIND_LABEL: Record<string, string> = {literature: 'Literature', database: 'Database', derived: 'Derived', hypothetical: 'Hypothetical', assumption: 'Assumption'};

/** Central z-slice of the voxel mesh: one value per voxel, null outside the cell. */
function Slice({grid, labels, h, title, unit, stretch}: {grid: (number | null)[][]; labels: number[][]; h: number; title: string; unit: string; stretch?: boolean}) {
  const n = grid.length, size = 260, c = size / n;
  const vals = grid.flat().filter((v): v is number => v !== null), hi = Math.max(...vals, 1e-9), lo = stretch ? Math.min(...vals) : 0;
  const ramp = (v: number) => { const t = hi > lo ? (v - lo) / (hi - lo) : 0; const c0 = [14, 26, 60], c1 = [255, 196, 120]; return `rgb(${c0.map((q, k) => Math.round(q + (c1[k] - q) * Math.sqrt(t))).join(',')})`; };
  return <figure className="sp-slice">
    <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label={title}>
      {grid.map((row, i) => row.map((v, j) => v === null ? null :
        <rect key={i + '-' + j} x={j * c} y={i * c} width={c + 0.4} height={c + 0.4} fill={ramp(v)} stroke={labels[i][j] === 2 ? 'rgba(255,255,255,0.10)' : 'none'} strokeWidth="0.5"><title>{fmt(v, 3)} {unit}</title></rect>))}
    </svg>
    <figcaption><strong>{title}</strong><span>{fmt(lo, 3)} – {fmt(hi, 3)} {unit} · voxel {h} µm · nucleus outlined</span></figcaption>
  </figure>;
}

/** Demo 11: a membrane-kinase / cytoplasmic-phosphatase gradient on a voxel mesh (RDME, next-subvolume method). */
export default function SpatialLab() {
  const [run, setRun] = useState<any>(null), [busy, setBusy] = useState(''), [error, setError] = useState('');
  const [overrides, setOverrides] = useState<Record<string, number>>({}), [label, setLabel] = useState(''), [runs, setRuns] = useState<any[]>([]);

  async function call<T>(text: string, action: string, payload: any) {
    setBusy(text); setError('');
    try { return await rpc<T>(action, payload); } catch (e) { setError(String(e).replace(/^Error:\s*/, '')); } finally { setBusy(''); }
  }
  async function refreshRuns() { const r = await call<any[]>('', 'spatial_runs', {}); if (r) setRuns(r); }
  async function execute(over = overrides, name = label) {
    const r = await call<any>('Simulating ~2 million voxel events', 'spatial_run', {overrides: over, seed: 1, label: name});
    if (r) { setRun(r); refreshRuns(); }
  }
  async function reopen(id: string) { const r = await call<any>('Opening saved run', 'spatial_record', {id}); if (r) { setRun(r); setOverrides(r.overrides); } }
  useEffect(() => { void execute({}, ''); }, []);

  const failed = run?.checks.filter((c: any) => !c.passed) ?? [];
  const mids = run?.profile.edges.slice(0, -1).map((e: number, i: number) => (e + run.profile.edges[i + 1]) / 2) ?? [];
  const cont = run?.checks.find((c: any) => c.rows);
  const cme = run?.checks.find((c: any) => c.histogram);

  return <>
    {busy && <div className="mech-busy"><LoaderCircle size={16} className="spin"/>{busy}…</div>}
    {error && <div className="mech-error" role="alert"><TriangleAlert size={15}/>{error}</div>}
    {run && <>
      <p className="ms-question">{run.question}</p>
      <section className="ms-identity mech-panel">
        <FlaskConical size={18}/>
        <div><strong>{run.method}</strong><span>{run.mesh.voxels.toLocaleString()} voxels · {run.mesh.membraneVoxels} membrane · {run.mesh.nucleusVoxels} nuclear · {run.events.toLocaleString()} stochastic events</span></div>
        <span className={'ms-pill ' + (failed.length ? 'fail' : 'ok')}>{failed.length ? <X size={12}/> : <Check size={12}/>}{run.checks.length - failed.length}/{run.checks.length} numerical checks</span>
        <span className="ms-env">SciPy {run.environment.scipy} · {fmt(run.seconds, 2)} s</span>
      </section>

      <section className="sp-outputs">
        {Object.entries(run.outputs).map(([k, o]: [string, any]) => <div key={k} className="mech-panel sp-output"><span className="eyebrow">{o.label}</span><b>{fmt(o.value, 3)}<i>{o.unit === '1' ? '' : ' ' + o.unit.replace('um', 'µm')}</i></b></div>)}
      </section>

      <section className="ms-detail">
        <div className="mech-panel ms-detail-main">
          <div className="ms-detail-head"><div><span className="eyebrow">{run.evidence.biology} · physics checks: {run.evidence.checks}</span><h2>Phosphorylated fraction from centre to membrane</h2></div></div>
          <TimeChart time={mids} timeUnit="µm" xLabel="Distance from centre (µm)" unit="Phosphorylated fraction" series={[{id: 'fv', label: 'Finite volume', values: run.profile.fv}, {id: 'rdme', label: 'RDME average', values: run.profile.rdme}]}/>
          <p className="caption">Ten radial shells of {fmt(mids[1] - mids[0], 2)} µm. The step near {run.profile.nucleusRadius} µm is the nuclear envelope; the inner shells are the nucleus.</p>
          <div className="sp-slices">
            <Slice grid={run.slice.fv} labels={run.slice.labels} h={run.slice.h} title="Mean field: phosphorylated fraction" unit="" stretch/>
            <Slice grid={run.slice.rdme} labels={run.slice.labels} h={run.slice.h} title="One stochastic snapshot: P molecules" unit="molecules"/>
          </div>
          <span className="eyebrow">How far the signal reaches · phosphatase sweep (finite volume)</span>
          <ScanChart values={run.sweep.map((s: any) => s.phosphatase)} readout={run.sweep.map((s: any) => s.nucleus / s.membrane)} xLabel="Phosphatase rate kₚ (1/s)" yLabel="Nucleus ÷ membrane" log/>
          <span className="eyebrow">Total phosphorylated molecules (RDME)</span>
          <TimeChart time={run.timeline.t} timeUnit="s" unit="P molecules" series={[{id: 'p', label: 'Phosphorylated', values: run.timeline.P}]}/>
          <p className="caption">Averages are taken after the {run.timeline.burn} s burn-in.</p>
        </div>
        <aside className="mech-panel ms-detail-side">
          <span className="eyebrow">Governing equations</span>
          {run.equations.map((e: string) => <p key={e} className="mono ms-eq">{e}</p>)}
          <span className="eyebrow">Parameters</span>
          {run.parameters.map((p: any) => <div key={p.name} className={'ms-param ' + p.kind}>
            <div><code>{p.name}</code><span className={'ms-chip ' + p.kind}>{KIND_LABEL[p.kind]}</span></div>
            <small>{p.description}{p.range ? ` · plausible ${fmt(p.range[0])}–${fmt(p.range[1])}` : ''}</small>
            <div className="ms-param-value">{p.editable ? <input type="number" step="any" value={overrides[p.name] ?? p.value} onChange={e => setOverrides(o => ({...o, [p.name]: Number(e.target.value)}))}/> : <b>{fmt(p.value, 4)}</b>}<span>{p.unit.replace('um', 'µm').replace('2/s', '²/s')}</span></div>
          </div>)}
          <span className="eyebrow">Assumptions</span>
          <ul className="ms-list">{run.assumptions.map((a: string) => <li key={a}>{a}</li>)}{run.limitations.map((a: string) => <li key={a} className="ms-limit">{a}</li>)}</ul>
          <span className="eyebrow">Sources</span>
          <ul className="ms-list">{Object.values(run.references).map((r: any) => <li key={r.doi}>{r.citation} <a href={'https://doi.org/' + r.doi} target="_blank" rel="noreferrer">doi:{r.doi}</a></li>)}</ul>
          <div className="ms-actions">
            <input placeholder="Scenario label" value={label} onChange={e => setLabel(e.target.value)}/>
            <button className="button primary" disabled={!!busy} onClick={() => execute()}><FlaskConical size={14}/>Re-run</button>
            {Object.keys(overrides).length > 0 && <button className="button" onClick={() => { setOverrides({}); void execute({}, ''); }}><RotateCcw size={14}/>Defaults</button>}
          </div>
        </aside>
      </section>

      <section className="mech-panel ms-panel">
        <span className="eyebrow">Benchmarks · numerical correctness, not biological validation</span>
        {run.checks.map((c: any) => <div key={c.name} className={'mech-check ' + (c.passed ? 'ok' : 'fail')}>{c.passed ? <Check size={14}/> : <X size={14}/>}<div><strong>{c.name}</strong><span>{c.detail} · {c.statName} {fmt(c.stat, 3)}</span></div></div>)}
        <div className="ms-grid">
          {cont && <div><span className="eyebrow">Analytical gradient (no nucleus) against mesh refinement</span>
            <TimeChart time={cont.curve.r} timeUnit="µm" xLabel="Distance from centre (µm)" unit="p / total" series={[{id: 'a', label: 'Analytical', values: cont.curve.fraction}, ...cont.rows.filter((r: any) => r.profile.every((v: number | null) => v !== null)).map((r: any) => ({id: 'h' + r.h, label: `h = ${r.h} µm`, values: r.profile}))]}/>
            <p className="caption">Shell means against the analytical curve. Meshes with an empty shell (h = 1 µm leaves one without voxel centres) are listed in the errors above but not drawn.</p></div>}
          {cme && <div><span className="eyebrow">A + B ⇌ C: stationary distribution</span>
            <TimeChart time={cme.exact.map((_: number, i: number) => i)} timeUnit="molecules" xLabel="C molecules" unit="Probability" series={[{id: 'e', label: 'Exact CME', values: cme.exact}, {id: 's', label: 'NSM samples', values: cme.histogram}]}/></div>}
        </div>
      </section>

      <section className="mech-panel ms-panel">
        <div className="ms-row"><span className="eyebrow"><History size={12}/> Saved runs</span><span className="caption">Record {run.recordId.slice(0, 10)} · SHA-256 {run.sha256.slice(0, 12)} · seed {run.seed}</span></div>
        <div className="ms-runs">{runs.slice(0, 12).map(r => <button key={r.id} className={'ms-run ' + (r.id === run.recordId ? 'active' : '')} onClick={() => reopen(r.id)}>
          <strong>{r.label || 'Spatial gradient'}</strong><span>{r.created.replace('T', ' ').slice(0, 16)} · nucleus ÷ membrane {fmt(r.nucleusToMembrane, 3)} · {r.passed ? 'all checks pass' : 'check failed'}</span></button>)}</div>
      </section>
      <p className="cell-disclaimer">Parameter values are hypothetical. The benchmarks show the solver is correct; they do not show that any real cell has this gradient.</p>
    </>}
  </>;
}
