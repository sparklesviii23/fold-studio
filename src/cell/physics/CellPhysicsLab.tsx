import {useEffect, useMemo, useState} from 'react';
import {Check as CheckIcon, Download, LoaderCircle, Minus, Pause, Play, TriangleAlert, X} from 'lucide-react';
import {exportFile, rpc} from '../../lib/api';
import {evidenceCategories} from '../../lib/engineContract';
import {fmt, TimeChart} from '../../components/mechanistic/MechCharts';
import ParticleStage, {type StageScene} from './ParticleStage';
import {extent, resample} from './geometry';
import type {BindingRecord, Check, DiffusionRecord, InputSpec, PhysicsCatalog, RunResult, SweepRecord} from './types';
import '../../components/mechanistic/mechanistic.css';
import './physics.css';

type Demo = 'diffusion' | 'binding';
const HYPOTHETICAL = new Set(['kon', 'koff', 'diffusion', 'ligands', 'receptors']);

/** Cell Explorer › Physics: Brownian-dynamics demos computed by scientific/cell_physics.py. Every frame drawn is a computed frame. */
export default function CellPhysicsLab() {
  const [catalog, setCatalog] = useState<PhysicsCatalog | null>(null);
  const [demo, setDemo] = useState<Demo>('diffusion');
  const [values, setValues] = useState<Record<Demo, Record<string, string>>>({diffusion: {}, binding: {}});
  const [busy, setBusy] = useState<string>(''), [error, setError] = useState('');
  const [diffusion, setDiffusion] = useState<DiffusionRecord | null>(null);
  const [binding, setBinding] = useState<BindingRecord | null>(null);
  const [sweep, setSweep] = useState<SweepRecord | null>(null);
  const [scenario, setScenario] = useState<'sphere' | 'free'>('sphere');
  const [frame, setFrame] = useState(0), [playing, setPlaying] = useState(false);

  useEffect(() => {
    rpc<PhysicsCatalog>('cell_physics_catalog').then(c => {
      setCatalog(c);
      const init = (spec: InputSpec[]) => Object.fromEntries(spec.map(s => [s.key, String(s.default)]));
      setValues({diffusion: init(c.demos.diffusion.inputs), binding: init(c.demos.binding.inputs)});
    }).catch(e => setError(String(e?.message ?? e)));
  }, []);

  const record = demo === 'diffusion' ? diffusion : binding;
  const time = record?.outputs.time ?? [];
  const frames = time.length;
  useEffect(() => { setFrame(f => Math.min(f, Math.max(0, frames - 1))); }, [frames]);
  useEffect(() => {
    if (!playing || frames < 2) return;
    const id = window.setInterval(() => setFrame(f => (f + 1) % frames), 60);
    return () => window.clearInterval(id);
  }, [playing, frames]);

  const scene = useMemo<StageScene | null>(() => {
    if (demo === 'diffusion' && diffusion) {
      const tracks = diffusion.outputs.sampled[scenario], R = Number(diffusion.inputs.radius.value);
      return scenario === 'sphere' ? {tracks, membrane: R, viewRadius: R * 1.08} : {tracks, viewRadius: Math.max(extent(tracks), R) * 1.05};
    }
    if (demo === 'binding' && binding) {
      const s = binding.outputs.sampled;
      return {tracks: s.track, bound: s.bound, receptors: s.receptors, receptorsBound: s.receptorsBound, membrane: Number(binding.inputs.membraneRadius.value), outer: Number(binding.inputs.outerRadius.value), viewRadius: Number(binding.inputs.outerRadius.value) * 1.05};
    }
    return null;
  }, [demo, diffusion, binding, scenario]);

  async function run(action: 'cell_physics_diffusion' | 'cell_physics_binding' | 'cell_physics_sweep') {
    setBusy(action); setError(''); setPlaying(false);
    const payload: Record<string, unknown> = Object.fromEntries(Object.entries(values[demo]).map(([k, v]) => [k, Number(v)]));
    try {
      if (action === 'cell_physics_sweep') {
        delete payload.koff; delete payload.replicates; delete payload.tEnd;
        payload.koffValues = catalog?.demos.binding.sweepDefault;
        setSweep((await rpc<RunResult<SweepRecord>>(action, payload)).record);
      } else {
        const r = await rpc<RunResult<DiffusionRecord | BindingRecord>>(action, payload);
        if (action === 'cell_physics_diffusion') setDiffusion(r.record as DiffusionRecord); else setBinding(r.record as BindingRecord);
        setFrame(0); setPlaying(true);
      }
    } catch (e: any) { setError(String(e?.message ?? e)); } finally { setBusy(''); }
  }

  const spec = catalog?.demos[demo].inputs ?? [];
  const sampledNote = record ? (demo === 'diffusion' ? (record as DiffusionRecord).outputs.sampled.note : (record as BindingRecord).outputs.sampled.note) : '';
  const total = record ? Number(demo === 'diffusion' ? record.inputs.particles.value : record.inputs.ligands.value) : 0;
  const shown = scene?.tracks.length ?? 0;

  return <div className="cp-lab">
    <div className="cp-top">
    <div className="cell-layout cp-layout">
      {scene ? <ParticleStage scene={scene} frame={frame}/> : <div className="cp-empty">
        <span className="eyebrow">Brownian dynamics · not yet run</span>
        <h3>{demo === 'diffusion' ? 'Diffusion inside a virtual cell' : 'Ligands finding membrane receptors'}</h3>
        <p>Run the engine to see computed particle trajectories. Nothing is drawn until there is data.</p>
      </div>}
      <div className="cp-badges">
        <span className="evidence-badge cp-evidence" title={'Category B · ' + evidenceCategories.B.meaning}>Physics-simulated · B</span>
        {demo === 'binding' && <span className="evidence-badge cp-hypothetical" title="kon, koff, D and molecule counts are generic values chosen to exercise the physics; they do not describe any real receptor.">Hypothetical parameters</span>}
        {scene && <span className="cp-chip" title={sampledNote}>Sampled {shown} of {total} computed {demo === 'diffusion' ? 'particles' : 'ligands'}</span>}
      </div>
      {demo === 'diffusion' && diffusion && <div className="cosmos-segment cp-scenario" role="tablist">
        {(['sphere', 'free'] as const).map(s => <button key={s} role="tab" aria-selected={scenario === s} className={scenario === s ? 'active' : ''} onClick={() => setScenario(s)}>{s === 'sphere' ? 'Inside the cell' : 'Free space'}</button>)}
      </div>}
      {frames > 1 && <div className="cp-playback">
        <button className="story-play" onClick={() => setPlaying(p => !p)} aria-label={playing ? 'Pause playback' : 'Play computed frames'}>{playing ? <Pause size={16}/> : <Play size={16}/>}</button>
        <input type="range" min={0} max={frames - 1} value={frame} onChange={e => { setPlaying(false); setFrame(Number(e.target.value)); }} aria-label="Computed frame"/>
        <span className="mono">t = {fmt(time[frame], 3)} s · frame {frame + 1}/{frames}</span>
      </div>}
    </div>

      <aside className="cell-card cp-controls">
        <div className="cosmos-segment" role="tablist">
          {(['diffusion', 'binding'] as Demo[]).map(d => <button key={d} role="tab" aria-selected={demo === d} className={demo === d ? 'active' : ''} onClick={() => { setDemo(d); setFrame(0); setPlaying(false); }}>{d === 'diffusion' ? 'Demo 1 · Diffusion' : 'Demo 2 · Binding'}</button>)}
        </div>
        <p className="caption">{demo === 'diffusion'
          ? 'Particles with a known D start at the centre: once in free space, once inside a reflecting sphere. Checked against MSD = 6Dt and the plateau 3/5 R².'
          : 'Ligands diffuse in the shell around the cell and bind single-site membrane receptors (Doi model). Equilibrium is checked against the exact ensemble and the Mechanistic Lab ODE.'}</p>
        <div className="cp-inputs">
          {spec.map(s => <label key={s.key} title={s.description + ` (${s.bounds[0]}–${s.bounds[1]} ${s.unit})`}>
            <span>{s.description}{demo === 'binding' && HYPOTHETICAL.has(s.key) && !/hypothetical/i.test(s.description) && <em> · hypothetical</em>}</span>
            <div><input type="number" value={values[demo][s.key] ?? ''} step="any" min={s.bounds[0]} max={s.bounds[1]} onChange={e => setValues(v => ({...v, [demo]: {...v[demo], [s.key]: e.target.value}}))}/><small>{s.unit}</small></div>
          </label>)}
        </div>
        <button className="button primary" disabled={!!busy || !catalog} onClick={() => run(demo === 'diffusion' ? 'cell_physics_diffusion' : 'cell_physics_binding')}>
          {busy && busy !== 'cell_physics_sweep' ? <><LoaderCircle size={14} className="spin"/>Computing…</> : 'Run Brownian dynamics'}
        </button>
        {demo === 'binding' && <button className="text-button" disabled={!!busy || !catalog} onClick={() => run('cell_physics_sweep')}>
          {busy === 'cell_physics_sweep' ? <><LoaderCircle size={13} className="spin"/>Sweeping koff (≈1 min)…</> : `Sweep koff (${catalog?.demos.binding.sweepDefault.join(', ')} s⁻¹)`}
        </button>}
        {error && <p className="cp-error"><TriangleAlert size={13}/>{error}</p>}
      </aside>
    </div>

    {demo === 'diffusion' && diffusion && <DiffusionResults record={diffusion} frame={frame}/>}
    {demo === 'binding' && binding && <BindingResults record={binding} frame={frame}/>}
    {demo === 'binding' && sweep && <SweepResults record={sweep}/>}
    {catalog && <details className="cp-about cell-card">
      <summary>Engine · {catalog.engine.name} {catalog.engine.version}</summary>
      <p>{catalog.engine.numericalMethod}</p>
      <p><strong>Solver choice.</strong> {catalog.engine.solverChoice.evaluated} {catalog.engine.solverChoice.reason}</p>
      <div className="cp-columns">
        <div><span className="eyebrow">Assumptions</span><ul>{catalog.engine.assumptions.map(a => <li key={a}>{a}</li>)}</ul></div>
        <div><span className="eyebrow">Validated domain</span><ul>{catalog.engine.validatedDomain.map(a => <li key={a}>{a}</li>)}</ul></div>
        <div><span className="eyebrow">Limits</span><ul>{catalog.engine.limits.map(a => <li key={a}>{a}</li>)}</ul></div>
      </div>
      <p className="caption">{catalog.engine.uncertainty}</p>
    </details>}
  </div>;
}

function Checks({checks}: {checks: Check[]}) {
  return <div className="cp-checks">{checks.map(c => <div key={c.name} className={'cp-check ' + (c.passed === null ? 'na' : c.passed ? 'pass' : 'fail')}>
    <i>{c.passed === null ? <Minus size={12}/> : c.passed ? <CheckIcon size={12}/> : <X size={12}/>}</i>
    <strong>{c.name}</strong><span>{c.detail}</span><small>{c.passed === null ? 'not applicable' : 'accept ' + c.threshold}</small>
  </div>)}</div>;
}

function RecordFooter({record}: {record: DiffusionRecord | BindingRecord | SweepRecord}) {
  return <div className="cp-footer">
    <span className="mono">seed {record.reproducibility.seed} · {record.reproducibility.runtime} · SHA-256 {record.reproducibility.contentSha256.slice(0, 16)}…</span>
    <button className="text-button" onClick={() => exportFile(`fold-cell-physics-${record.kind}-${record.id.slice(0, 8)}.json`, {text: JSON.stringify(record, null, 1)})}><Download size={13}/>Export research record (JSON)</button>
  </div>;
}

function band(mean: number[], se: number[]) {
  return {lo: mean.map((m, i) => m - 2 * se[i]), hi: mean.map((m, i) => m + 2 * se[i]), lo50: mean.map((m, i) => m - se[i]), hi50: mean.map((m, i) => m + se[i])};
}

function DiffusionResults({record, frame}: {record: DiffusionRecord; frame: number}) {
  const o = record.outputs, checks = record.benchmark.checks ?? [];
  return <section className="cp-results">
    <div className="cp-results-head"><span className="eyebrow">Demo 1 · results</span><span className={'cp-verdict ' + (record.benchmark.passed ? 'pass' : 'fail')}>{record.benchmark.passed ? 'All applicable validations pass' : 'A validation failed'}</span></div>
    <div className="cp-charts">
      <figure><figcaption>Inside the cell · MSD from the centre (µm²), ±1/±2 SE</figcaption>
        <TimeChart time={o.time} timeUnit="s" unit="MSD (µm²)" playhead={frame} bands={band(o.sphere.msd, o.sphere.se)}
          series={[{id: 'sphere', label: 'BD (sphere)', values: o.sphere.msd}, {id: 'plateau', label: '3/5 R²', values: o.time.map(() => o.sphere.plateau)}]}/></figure>
      <figure><figcaption>Free space · MSD (µm²), ±1/±2 SE</figcaption>
        <TimeChart time={o.time} timeUnit="s" unit="MSD (µm²)" playhead={frame} bands={band(o.free.msd, o.free.se)}
          series={[{id: 'free', label: 'BD (free)', values: o.free.msd}, {id: 'ref', label: '6Dt', values: o.free.reference}]}/></figure>
    </div>
    <Checks checks={checks}/>
    <RecordFooter record={record}/>
  </section>;
}

function BindingResults({record, frame}: {record: BindingRecord; frame: number}) {
  const o = record.outputs, eq = o.equilibrium, d = o.derived;
  const ode = resample(o.ode.time, o.ode.occupancy, o.time).map(v => v ?? 0);
  return <section className="cp-results">
    <div className="cp-results-head"><span className="eyebrow">Demo 2 · results</span><span className={'cp-verdict ' + (record.benchmark.passed ? 'pass' : 'fail')}>{record.benchmark.passed ? 'All applicable validations pass' : 'A validation failed'}</span></div>
    <div className="ll-tiles cp-tiles">
      <div className="quiet-panel"><span>Equilibrium occupancy · BD</span><strong>{fmt(eq.occupancy * 100, 3)}<em> % ± {fmt(eq.occupancySe * 100, 2)}</em></strong><small>{fmt(eq.bd, 4)} ± {fmt(eq.se, 2)} complexes, mean of {eq.perReplicate.length} replicates over {fmt(eq.window[0], 3)}–{fmt(eq.window[1], 3)} s</small></div>
      <div className="quiet-panel"><span>Well-mixed ODE · Mechanistic Lab</span><strong>{fmt(eq.odeOccupancy * 100, 4)}<em> %</em></strong><small>{fmt(eq.ode, 5)} complexes (SciPy LSODA on composed SBML)</small></div>
      <div className="quiet-panel"><span>Exact ideal ensemble</span><strong>{fmt(eq.exact / Number(record.inputs.receptors.value) * 100, 4)}<em> %</em></strong><small>{fmt(eq.exact, 5)} ± {fmt(eq.exactSd, 3)} (SD) complexes</small></div>
      <div className="quiet-panel"><span>Hypothetical constants</span><strong>{fmt(d.konMolar, 2)}<em> M⁻¹s⁻¹</em></strong><small>kon = {fmt(Number(record.inputs.kon.value), 3)} µm³/s · koff = {fmt(Number(record.inputs.koff.value), 3)} s⁻¹ · K_D = {fmt(d.kdMolar * 1e9, 3)} nM · V = {fmt(d.volume, 4)} µm³</small></div>
    </div>
    <figure><figcaption>Receptor occupancy (fraction bound): BD mean ±1/±2 SE across replicates vs the well-mixed ODE</figcaption>
      <TimeChart time={o.time} timeUnit="s" unit="Fraction bound" playhead={frame} bands={band(o.occupancy.mean, o.occupancy.se)}
        series={[{id: 'bd', label: 'BD', values: o.occupancy.mean}, {id: 'ode', label: 'ODE', values: ode}, {id: 'exact', label: 'Exact eq.', values: o.time.map(() => eq.exact / Number(record.inputs.receptors.value))}]}/></figure>
    <p className="caption">Kinetics (not a validation): the largest BD–ODE gap is {fmt(o.kinetics.maxDeviationFromOde * 100, 3)} % of the equilibrium value. {o.kinetics.note} Here kD/(kD + kon) = {fmt(o.kinetics.collinsKimballFactor, 3)}. Doi λ = {fmt(d.lambda, 4)} s⁻¹, λΔt = {fmt(d.pOn, 3)}, V_rx = {fmt(d.reactionVolume, 3)} µm³.</p>
    <Checks checks={record.benchmark.checks ?? []}/>
    <RecordFooter record={record}/>
  </section>;
}

function SweepResults({record}: {record: SweepRecord}) {
  const {rows, curve} = record.outputs;
  const W = 760, H = 260, M = {l: 64, r: 24, t: 14, b: 40};
  const lx = (k: number) => M.l + (Math.log(k) - Math.log(curve.koff[0])) / (Math.log(curve.koff[curve.koff.length - 1]) - Math.log(curve.koff[0])) * (W - M.l - M.r);
  const y = (f: number) => H - M.b - f * (H - M.t - M.b);
  return <section className="cp-results">
    <div className="cp-results-head"><span className="eyebrow">Demo 2 · koff sweep</span><span className={'cp-verdict ' + (record.benchmark.passed ? 'pass' : 'fail')}>{record.benchmark.passed ? 'Every point agrees with the ODE equilibrium' : 'A point disagrees'}</span></div>
    <figure className="mc-chart"><figcaption>Equilibrium occupancy vs koff: BD ± 2 SE (points) and the well-mixed mass-action equilibrium (line)</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Equilibrium occupancy against koff">
        <g className="mc-axes">
          {[0, 0.25, 0.5, 0.75, 1].map(v => <g key={v}><line x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} className="mc-grid"/><text x={M.l - 8} y={y(v) + 4} textAnchor="end">{v}</text></g>)}
          {rows.map(r => <text key={r.koff} x={lx(r.koff)} y={H - M.b + 16} textAnchor="middle">{fmt(r.koff, 3)}</text>)}
          <text x={(M.l + W - M.r) / 2} y={H - 6} textAnchor="middle" className="mc-axis-label">koff (s⁻¹, log)</text>
          <text transform={`translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)`} textAnchor="middle" className="mc-axis-label">Fraction bound</text>
        </g>
        <path d={curve.koff.map((k, i) => (i ? 'L' : 'M') + lx(k).toFixed(1) + ' ' + y(curve.occupancy[i]).toFixed(1)).join('')} fill="none" stroke="#d95926" strokeWidth="2"/>
        {rows.map(r => <g key={r.koff}>
          <line x1={lx(r.koff)} x2={lx(r.koff)} y1={y(r.occupancy - 2 * r.occupancySe)} y2={y(r.occupancy + 2 * r.occupancySe)} stroke="#3987e5" strokeWidth="2"/>
          <circle cx={lx(r.koff)} cy={y(r.occupancy)} r="5" fill="#3987e5" stroke="#0b1328" strokeWidth="2"><title>{`koff ${r.koff} s⁻¹: BD ${fmt(r.occupancy, 4)} ± ${fmt(r.occupancySe, 2)}, ODE ${fmt(r.odeOccupancy, 4)}`}</title></circle>
        </g>)}
      </svg>
      <div className="mc-legend"><span><i style={{background: '#3987e5'}}/>BD ± 2 SE</span><span><i style={{background: '#d95926'}}/>Well-mixed equilibrium (mass-action root; the table's ODE column is the Mechanistic Lab integration)</span></div>
    </figure>
    <table className="cp-table"><thead><tr><th>koff (s⁻¹)</th><th>K_D (nM)</th><th>t_end (s)</th><th>BD occupancy</th><th>ODE</th><th>z vs ODE</th><th>Status</th></tr></thead>
      <tbody>{rows.map(r => { const c = r.checks.find(c => c.name === 'Equilibrium vs well-mixed ODE'); return <tr key={r.koff}>
        <td>{fmt(r.koff, 3)}</td><td>{fmt(r.kdMolar * 1e9, 3)}</td><td>{fmt(r.tEnd, 3)}</td><td>{fmt(r.occupancy, 4)} ± {fmt(r.occupancySe, 2)}</td><td>{fmt(r.odeOccupancy, 4)}</td>
        <td>{c?.applicable ? fmt(c.value?.z, 3) : '—'}</td><td>{c?.passed === null ? 'n/a' : r.passed ? 'pass' : 'fail'}</td></tr>; })}</tbody></table>
    <RecordFooter record={record}/>
  </section>;
}
