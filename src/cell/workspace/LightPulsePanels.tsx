import {useEffect, useRef, useState} from 'react';
import {Check, FlaskConical, GitBranch, LoaderCircle, Play, Plus, RotateCcw, Trash2, TriangleAlert, X} from 'lucide-react';
import SyncChart, {type ChartEvent} from './SyncChart';
import {programAt, pulsesToProgram, RED, type LightPulse, type LpScore, type Program, type Pulse} from './useLightPulse';

export const C = {light: '#59e38a', reporter: '#e9f1f7', accent: '#5ee6ff', measured: '#ffb454', reference: '#8a94a3', learned: '#c792ea', baseline: '#ff6b6b', regulator: '#5ee6ff', transcription: '#ffd166', red: '#ff6b6b', violet: '#b79cff', immature: '#ffb86b', mature: '#8cff99', published: '#c792ea'};
const ledColor = (led: string) => led === RED ? C.red : C.violet;
const ledName = (led: string, nm?: number | null) => (led === RED ? 'red' : led.startsWith('3') ? 'near-UV' : led) + (nm ? ` · ${Math.round(nm)} nm` : '');
const fold = (rmse: number) => (10 ** rmse).toFixed(2) + '×';
const num = (v: number | null | undefined, d = 3) => v == null || !Number.isFinite(v) ? '–' : Math.abs(v) >= 1e4 ? v.toExponential(2).replace('e+', 'e') : Number(v.toPrecision(d)).toString();
const ROLE: Record<string, string> = {train: 'used for fitting', heldOut: 'held out', mixedColour: 'final test · red on green', otherColour: 'final test · 380 nm alone'};

/** The light program as a strip: drag on empty time to add a pulse, drag a pulse to move it. Heights show intensity on a log scale. */
function PulseStrip({pulses, duration, max, onChange, cursor, disabled, program, tone, name = 'Light'}: {pulses: Pulse[]; duration: number; max: number; onChange: (p: Pulse[]) => void; cursor: number | null; disabled: boolean; program?: Program; tone?: string; name?: string}) {
  const ref = useRef<SVGSVGElement>(null), drag = useRef<{mode: 'new' | 'move'; index: number; t0: number; start: number} | null>(null);
  const W = 320, H = 64, x = (t: number) => t / duration * W, h = (i: number) => i <= 0 ? 0 : 6 + (H - 22) * Math.log10(1 + 99 * i / max) / 2;
  const at = (e: React.PointerEvent) => { const r = ref.current!.getBoundingClientRect(); return Math.max(0, Math.min(duration, (e.clientX - r.left) / r.width * duration)); };
  const snap = (t: number) => Math.round(t / 5) * 5;
  const down = (e: React.PointerEvent) => {
    if (disabled) return;
    const t = at(e), hit = pulses.findIndex(p => t >= p.start && t <= p.start + p.duration);
    (e.target as Element).setPointerCapture?.(e.pointerId);
    if (hit >= 0) drag.current = {mode: 'move', index: hit, t0: t, start: pulses[hit].start};
    else { drag.current = {mode: 'new', index: pulses.length, t0: snap(t), start: snap(t)}; onChange([...pulses, {start: snap(t), duration: 5, intensity: pulses[pulses.length - 1]?.intensity ?? 5}]); }
  };
  const move = (e: React.PointerEvent) => {
    const d = drag.current; if (!d) return;
    const t = at(e);
    onChange(pulses.map((p, i) => i !== d.index ? p : d.mode === 'move' ? {...p, start: Math.max(0, Math.min(duration - p.duration, snap(d.start + t - d.t0)))} : {...p, start: Math.min(d.t0, snap(t)), duration: Math.max(5, Math.abs(snap(t) - d.t0))}));
  };
  const steps = program?.steps;
  return <svg ref={ref} className={'ws-strip' + (disabled ? ' locked' : '') + (tone ? ' ' + tone : '')} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" onPointerDown={down} onPointerMove={move} onPointerUp={() => { drag.current = null; }}
    role="img" aria-label={name + ' program over ' + duration + ' minutes: ' + (steps ? steps.length + ' steps' : pulses.map(p => `${p.intensity} from ${p.start} for ${p.duration} min`).join('; '))}>
    <line x1={0} x2={W} y1={H - 12} y2={H - 12} className="base"/>
    {steps ? steps.map(([t, v], i) => v > 0 && <rect key={i} x={x(t)} width={Math.max(1, x((steps[i + 1]?.[0] ?? duration) - t))} y={H - 12 - h(v)} height={h(v)} className="pulse"/>)
      : pulses.map((p, i) => <rect key={i} x={x(p.start)} width={Math.max(2, x(p.duration))} y={H - 12 - h(p.intensity)} height={h(p.intensity)} className="pulse" rx={1.5}/>)}
    {[0, 0.25, 0.5, 0.75, 1].map(f => <text key={f} x={Math.min(W - 2, Math.max(2, f * W))} y={H - 2} textAnchor={f === 0 ? 'start' : f === 1 ? 'end' : 'middle'}>{Math.round(f * duration)}</text>)}
    {cursor != null && <line x1={x(cursor)} x2={x(cursor)} y1={0} y2={H - 12} className="cursor"/>}
  </svg>;
}

/** Inputs of the light-pulse experiment: the pulse editor, measured schedules, and the run button. */
export function LightInputs({lp, cursor}: {lp: LightPulse; cursor: number | null}) {
  const {cat} = lp;
  if (!cat) return <div className="ws-pad">{lp.error ? <p className="ws-error"><TriangleAlert size={13}/>{lp.error}</p> : <p className="ws-note"><LoaderCircle size={13} className="spin"/> Fitting the model to the training schedules. This takes about 15 seconds the first time and is then remembered.</p>}</div>;
  const max = cat.limits.intensity[1], locked = !!lp.chosen;
  let problem = ''; try { lp.program(); } catch (e: any) { problem = String(e?.message ?? e); }
  let redProblem = ''; try { lp.other(); } catch (e: any) { redProblem = String(e?.message ?? e); }
  const patch = (i: number, change: Partial<Pulse>) => lp.setPulses(lp.pulses.map((p, k) => k === i ? {...p, ...change} : p));
  const preset = (ps: Pulse[]) => { lp.setSchedule(''); lp.setPulses(ps); };
  return <div className="ws-pad">
    <section className="ws-sec">
      <header><h4>Light program</h4><span className="ws-tag modeled">green · 526 nm</span></header>
      <PulseStrip pulses={lp.pulses} duration={lp.total} max={max} onChange={lp.setPulses} cursor={cursor} disabled={locked} program={lp.chosen?.program}/>
      <p className="ws-hint">{locked ? 'A measured schedule runs exactly as it was recorded.' : 'Drag on the strip to add a pulse, drag a pulse to move it. Time in minutes.'}</p>
      {!locked && <>
        <div className="ws-pulses">{lp.pulses.map((p, i) => <div key={i} className="ws-pulse">
          <label>Start<input type="number" min={0} max={lp.duration} step={5} value={p.start} onChange={e => patch(i, {start: Number(e.target.value)})}/><small>min</small></label>
          <label>Lasts<input type="number" min={1} step={5} value={p.duration} onChange={e => patch(i, {duration: Number(e.target.value)})}/><small>min</small></label>
          <label title="µmol m⁻² s⁻¹ of green light; 0.16–20 was measured">Intensity<input type="number" min={0} max={max} step={0.5} value={p.intensity} onChange={e => patch(i, {intensity: Number(e.target.value)})}/><small>µmol m⁻² s⁻¹</small></label>
          <button className="ws-icon" onClick={() => lp.setPulses(lp.pulses.filter((_, k) => k !== i))} aria-label="Remove this pulse" disabled={lp.pulses.length < 2}><Trash2 size={13}/></button>
        </div>)}</div>
        <div className="ws-row">
          <button className="ws-btn" onClick={() => lp.setPulses([...lp.pulses, {start: Math.min(lp.duration - 30, Math.max(0, ...lp.pulses.map(p => p.start + p.duration)) + 30), duration: 30, intensity: lp.pulses[lp.pulses.length - 1]?.intensity ?? 5}])}><Plus size={13}/>Add pulse</button>
          <button className="ws-btn" onClick={() => preset([{start: 30, duration: 90, intensity: 5}])}>One pulse</button>
          <button className="ws-btn" onClick={() => preset([0, 1, 2, 3].map(i => ({start: 30 + i * 90, duration: 30, intensity: 5})))}>Pulse train</button>
          <button className="ws-btn" onClick={() => preset([{start: 30, duration: lp.duration - 30, intensity: 5}])}>Step on</button>
        </div>
        <label className="ws-field"><span>Experiment length</span><div><input type="number" min={cat.limits.durationMin[0]} max={cat.limits.durationMin[1]} step={30} value={lp.duration} onChange={e => lp.setDuration(Number(e.target.value))}/><small>min simulated</small></div></label>
      </>}
      {problem && <p className="ws-error"><TriangleAlert size={13}/>{problem}</p>}
    </section>
    <section className="ws-sec">
      <header><h4>Red light</h4><span className="ws-tag modeled">red · 657 nm</span></header>
      {locked ? (Object.keys(lp.chosen!.other).length ? Object.entries(lp.chosen!.other).map(([led, prog]) => <div key={led}>
          <PulseStrip pulses={[]} duration={lp.total} max={max} onChange={() => undefined} cursor={cursor} disabled program={prog} tone={led === RED ? 'red' : 'violet'} name={ledName(led)}/>
          <p className="ws-hint">{ledName(led, cat.channels.find(c => c.led === led)?.centroidNm)} as recorded. It {cat.channels.find(c => c.led === led)?.structureName ?? 'has no calibrated effect'}.</p></div>)
        : <p className="ws-hint">This schedule uses green light only.</p>)
      : <>
        {lp.redPulses.length > 0 && <PulseStrip pulses={lp.redPulses} duration={lp.total} max={max} onChange={lp.setRedPulses} cursor={cursor} disabled={false} tone="red" name="Red light"/>}
        <div className="ws-pulses">{lp.redPulses.map((p, i) => { const set = (c: Partial<Pulse>) => lp.setRedPulses(lp.redPulses.map((q, k) => k === i ? {...q, ...c} : q)); return <div key={i} className="ws-pulse">
          <label>Start<input type="number" min={0} max={lp.duration} step={5} value={p.start} onChange={e => set({start: Number(e.target.value)})}/><small>min</small></label>
          <label>Lasts<input type="number" min={1} step={5} value={p.duration} onChange={e => set({duration: Number(e.target.value)})}/><small>min</small></label>
          <label title="µmol m⁻² s⁻¹ of red light; 0.01–20 was measured at steady state">Intensity<input type="number" min={0} max={max} step={0.5} value={p.intensity} onChange={e => set({intensity: Number(e.target.value)})}/><small>µmol m⁻² s⁻¹</small></label>
          <button className="ws-icon" onClick={() => lp.setRedPulses(lp.redPulses.filter((_, k) => k !== i))} aria-label="Remove this red pulse"><Trash2 size={13}/></button>
        </div>; })}</div>
        <div className="ws-row">
          <button className="ws-btn" onClick={() => lp.setRedPulses([...lp.redPulses, {start: Math.min(lp.duration - 30, Math.max(60, ...lp.redPulses.map(p => p.start + p.duration + 30))), duration: 30, intensity: 10}])}><Plus size={13}/>Add red pulse</button>
          {lp.redPulses.length > 0 && <button className="ws-btn" onClick={() => lp.setRedPulses([])}>No red light</button>}
        </div>
        <p className="ws-hint">Red light switches the sensor off. Its rate is calibrated on steady-state measurements; its effect during a program was tested on two measured schedules, retrospectively.</p>
        {redProblem && <p className="ws-error"><TriangleAlert size={13}/>{redProblem}</p>}
      </>}
    </section>
    <section className="ws-sec">
      <header><h4>Measured schedules</h4><span className="ws-tag measured">measured</span></header>
      <select value={lp.schedule} onChange={e => lp.setSchedule(e.target.value)} aria-label="Run a measured schedule">
        <option value="">My own program (no measurement to compare)</option>
        {(['mixedColour', 'otherColour', 'heldOut', 'train'] as const).map(role => <optgroup key={role} label={role === 'heldOut' ? 'Held out from fitting · green' : role === 'mixedColour' ? 'Final test · red light on a green program' : role === 'otherColour' ? 'Final test · a 380 nm LED alone' : 'Used for fitting'}>
          {cat.schedules.filter(s => s.role === role).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</optgroup>)}
      </select>
      {lp.chosen && <p className="ws-hint">{lp.chosen.runs} run{lp.chosen.runs === 1 ? '' : 's'}, {lp.chosen.points} measured points · {ROLE[lp.chosen.role]}{Object.keys(lp.chosen.other).length ? ` · includes ${Object.keys(lp.chosen.other).map(l => ledName(l)).join(', ')} light` : ''}.</p>}
    </section>
    {lp.parent && <p className="ws-branch"><GitBranch size={12}/>Variant of run {lp.parent.slice(0, 8)}. Change the program, then run.<button className="ws-icon" onClick={lp.endBranch} aria-label="Stop comparing"><X size={11}/></button></p>}
    <input className="ws-label" value={lp.label} placeholder="Name this experiment (optional)" maxLength={120} onChange={e => lp.setLabel(e.target.value)} aria-label="Experiment name"/>
    <button className="ws-go" disabled={!!problem || !!redProblem || lp.busy === 'run'} onClick={lp.run}>{lp.busy === 'run' ? <LoaderCircle size={15} className="spin"/> : <Play size={15}/>}Run the light program<small>{cat.models[cat.selected].toLowerCase()}</small></button>
    {lp.error && <p className="ws-error"><TriangleAlert size={13}/>{lp.error}</p>}
    <p className="ws-hint">Predictor: <strong>{cat.models[cat.selected]}</strong>, chosen by the held-out benchmark ({fold(cat.summary.heldOut[cat.selected])} error; static baseline {fold(cat.summary.heldOut.baseline)}). Change it under Parameters.</p>
    {lp.runs.length > 0 && <section className="ws-sec">
      <header><h4>Saved experiments</h4></header>
      <div className="ws-saved">{lp.runs.slice(0, 8).map(r => <button key={r.id} className={lp.result?.id === r.id ? 'on' : ''} onClick={() => lp.open(r.id)} title="Reopen and recompute this saved experiment">
        <span>{r.label || 'Run ' + r.id.slice(0, 8)}</span><small>{r.created.slice(0, 16).replace('T', ' ')} · peak {num(r.peak)} MEFL{r.schedule ? ' · measured schedule' : ''}</small></button>)}</div>
    </section>}
  </div>;
}

function ScoreChart({s, model, cursor, onSeek, title, compare = 'baseline'}: {s: LpScore; model: string; cursor?: number | null; onSeek?: (t: number) => void; title: string; compare?: string}) {
  const m = s.models[model], b = s.models[compare], symbols = ['circle', 'square', 'triangle'] as const, compareLabel = compare === 'green' ? 'Green-only model' : compare === 'published' ? 'Published model' : 'Static baseline';
  return <SyncChart title={title} time={m.t} unit="MEFL" timeUnit="min" log cursor={cursor} onSeek={onSeek}
    series={[{id: 'm', label: 'Predicted', values: m.fl, color: C.reporter, width: 2}, ...(b ? [{id: 'b', label: compareLabel, values: b.fl, color: C.baseline, dash: true}] : [])]}
    bands={s.models.mechanistic?.interval && model !== 'learned' ? [{lo: s.models.mechanistic.interval.low, hi: s.models.mechanistic.interval.high, color: C.accent, label: '90 % predictive interval'}] : []}
    points={s.replicates.map((r, i) => ({label: 'Measured · ' + r.run.replace('rgv2_', 'run '), t: r.t, y: r.fl, color: C.measured, symbol: symbols[i % 3]}))}/>;
}

/** Results of the light-pulse experiment in the dock: response, validation, comparison, sweeps and closed loop. */
export function LightDock({lp, cursor, onSeek, tab, events}: {lp: LightPulse; cursor: number | null; onSeek: (t: number) => void; tab: string; events: ChartEvent[]}) {
  const {cat, result: r} = lp;
  const [vary, setVary] = useState<'duration' | 'intensity' | 'period'>('duration'), [target, setTarget] = useState(30000);
  useEffect(() => { if (tab === 'validation') void lp.loadBench(); }, [tab]);
  if (!cat) return null;
  if (tab === 'response') {
    if (!r) return <p className="ws-empty">Run the light program to see the stimulus and the predicted response on one time axis.</p>;
    const meas = r.measured, f = r.record.outputs.features, u = r.record.outputs.uncertainty;
    const others = Object.keys(r.series).filter(k => k.startsWith('light:')).map(k => k.slice(6)), ignored = Object.keys(r.record.experiment.config.other ?? {}).filter(l => !others.includes(l));
    const greenOnly = meas && r.model !== 'green' && others.length ? meas.models.green : null, pub = meas?.models.published;
    return <div className="ws-grid2">
      <div>
        <SyncChart title={others.length ? 'Stimulus · light per LED' : 'Stimulus · green light'} time={r.time} unit="µmol m⁻² s⁻¹" timeUnit="min" cursor={cursor} onSeek={onSeek} events={events} height={120}
          series={[{id: 'l', label: 'Green · 526 nm', values: r.series.light, color: C.light, width: 2}, ...others.map(led => ({id: led, label: ledName(led, cat.channels.find(c => c.led === led)?.centroidNm), values: r.series['light:' + led], color: ledColor(led), width: 2})), ...(lp.baseline && lp.baseline.id !== r.id ? [{id: 'lb', label: 'Baseline program', values: lp.baseline.series.light, color: C.reference, dash: true}] : [])]}/>
        <SyncChart title={'Reporter · ' + r.modelName} time={r.time} unit="MEFL" timeUnit="min" cursor={cursor} onSeek={onSeek} events={events}
          series={[{id: 'g', label: 'Predicted reporter', values: r.series.reporter, color: C.reporter, width: 2.2},
            ...(lp.baseline && lp.baseline.id !== r.id ? [{id: 'gb', label: 'Baseline run', values: lp.baseline.series.reporter, color: C.accent, dash: true}] : []),
            ...(r.reference ? [{id: 'ref', label: 'No light (dark reference)', values: r.reference.reporter, color: C.reference, dash: true}] : [])]}
          lines={[...(greenOnly ? [{label: 'Green-only model at the measured times', t: greenOnly.t, y: greenOnly.fl, color: C.baseline}] : []), ...(pub ? [{label: 'Published model at the measured times', t: pub.t, y: pub.fl, color: C.published}] : [])]}
          bands={r.series.predictiveLow ? [{lo: r.series.predictiveLow, hi: r.series.predictiveHigh, color: C.accent, label: '90 % predictive interval'}] : []}
          points={meas ? meas.replicates.map((rep, i) => ({label: 'Measured · ' + rep.run.replace('rgv2_', 'run '), t: rep.t, y: rep.fl, color: C.measured, symbol: (['circle', 'square', 'triangle'] as const)[i % 3]})) : []}/>
      </div>
      <div>
        {r.series.regulator && <SyncChart title="Inside the chain · regulator and transcription" time={r.time} unit="fraction of range" timeUnit="min" cursor={cursor} onSeek={onSeek} height={150}
          series={[{id: 'a', label: 'Regulator activity (active fraction)', values: r.series.regulator, color: C.regulator}, {id: 'T', label: 'Transcription drive (fraction of range)', values: r.series.transcription.map(v => (v - cat.parameters[4].value) / cat.parameters[5].value), color: C.transcription, dash: true}]}/>}
        {r.series.mature && <SyncChart title="Reporter molecules per cell · the one count behind fluorescence and 3D" time={r.time} unit="molecules (relative)" timeUnit="min" cursor={cursor} onSeek={onSeek} height={150}
          series={[{id: 'G', label: 'Mature (fluorescent)', values: r.series.mature, color: C.mature, width: 2}, {id: 'U', label: 'Immature', values: r.series.immature, color: C.immature}]}/>}
        <table className="ws-table"><thead><tr><th>Response</th><th>Predicted</th>{meas && <th>Measured</th>}{r.reference && !meas && <th>Dark reference</th>}</tr></thead><tbody>
          {(['amplitude', 'timeToPeakMin', 'halfRecoveryMin'] as const).map(k => { const mf = meas?.models[r.model]?.features[k]; return <tr key={k}><td>{k === 'amplitude' ? 'Amplitude (MEFL)' : k === 'timeToPeakMin' ? 'Time to peak (min)' : 'Half recovery after the peak (min)'}</td>
            <td>{num(f[k])}</td>{meas && <td>{mf?.supported ? num(mf.measured) : 'not reached by the sampling'}</td>}{r.reference && !meas && <td>{num(r.reference.features[k])}</td>}</tr>; })}
          {meas && <tr><td>Error against the measurement</td><td colSpan={2}>{fold(meas.models[r.model].rmseLog10)} root-mean-square{greenOnly ? ` · green-only model ${fold(greenOnly.rmseLog10)}` : ''}{pub ? ` · published model ${fold(pub.rmseLog10)}` : ''} · static baseline {fold(meas.models.baseline.rmseLog10)}{meas.replicateSdLog10 ? ` · run-to-run spread ${fold(meas.replicateSdLog10)}` : ''}</td></tr>}
          {meas?.models[r.model].interval && <tr><td>Measured points inside the 90 % interval</td><td colSpan={2}>{meas.models[r.model].interval!.inside} of {meas.models[r.model].interval!.total}</td></tr>}
          {u && <tr><td>5–95 % of parameter sets at the peak</td><td colSpan={2}>{num(u.atPeak.low)} – {num(u.atPeak.high)} MEFL</td></tr>}
        </tbody></table>
        {ignored.length > 0 && <p className="ws-warn"><TriangleAlert size={12}/> This program contains {ignored.map(l => ledName(l)).join(', ')} light that the chosen predictor does not take, so this prediction is expected to be wrong: it shows what the missing input costs.</p>}
        {r.warnings.map(w => <p key={w} className="ws-warn"><TriangleAlert size={12}/> {w}</p>)}
        {r.reproduced && <p className={r.reproduced.identical ? 'ws-ok' : 'ws-warn'}>{r.reproduced.identical ? <Check size={12}/> : <TriangleAlert size={12}/>} {r.reproduced.statement}</p>}
        <div className="ws-row"><button className="ws-btn" onClick={lp.branch} title="Keep this run as the baseline and edit a variant"><GitBranch size={13}/>Branch</button>
          {others.length > 0 && r.model !== 'green' && <button className="ws-btn" disabled={lp.busy === 'green'} onClick={lp.compareGreen} title="Run the same program through the green-only chain and show it as the baseline, in the plots and in 3D">{lp.busy === 'green' ? <LoaderCircle size={13} className="spin"/> : <FlaskConical size={13}/>}Compare with green-only model</button>}
          <span className="ws-id">Run {r.id.slice(0, 8)} · SHA-256 {r.sha256.slice(0, 12)}… · light_pulse/runs</span></div>
      </div>
    </div>;
  }
  if (tab === 'validation') {
    const b = lp.bench;
    if (!b) return <p className="ws-empty"><LoaderCircle size={13} className="spin"/> Loading the benchmark…</p>;
    const ok = b.schedules.heldOut.find(s => s.id === 'dynamic-green')!, red = b.schedules.mixedColour.find(s => s.id === 'dynamic-green-red-perturbation')!, uv = b.schedules.otherColour[0];
    const models = ['mechanistic', 'green', 'published', 'learned', 'combined', 'baseline'], st = b.stages, reg = b.regression, roles = ['mixedColour', 'otherColour', 'heldOut', 'train'] as const;
    const pct = (v: number | null | undefined) => v == null ? '–' : (v > 0 ? '+' : '') + num(v * 100, 2) + ' %';
    return <div className="ws-validation">
      <p className={b.gate.passed ? 'ws-ok' : 'ws-warn'}>{b.gate.passed ? <Check size={12}/> : <TriangleAlert size={12}/>} {b.gate.statement} {b.selectionNote}</p>
      <p className={reg.improved ? 'ws-ok' : 'ws-warn'}>{reg.improved ? <Check size={12}/> : <TriangleAlert size={12}/>} <strong>Retrospective.</strong> {reg.statement} {st.finalTest.statement}</p>
      <div className="ws-grid2">
        <div><ScoreChart s={red} model="mechanistic" compare="green" title="Final test · green program with red light, three runs"/>
          <p className="ws-hint">With the red input {fold(red.models.mechanistic.rmseLog10)}; green-only model {fold(red.models.green.rmseLog10)} (the regression case); two runs of the same program differ by {fold(red.replicateSdLog10 ?? 0)}. Amplitude {pct(red.models.mechanistic.features.amplitude?.relativeError)} against {pct(red.models.green.features.amplitude?.relativeError)} without red.</p></div>
        <div><ScoreChart s={ok} model={b.selected} title="Held out · dynamic green program, three runs"/>
          <p className="ws-hint">Error {fold(ok.models[b.selected].rmseLog10)}; run-to-run spread {fold(ok.replicateSdLog10 ?? 0)}. {ok.models.mechanistic.interval ? `${ok.models.mechanistic.interval.inside} of ${ok.models.mechanistic.interval.total} points fall inside the 90 % interval: it is too narrow because day-to-day variation is not in the training plates.` : ''}</p></div>
      </div>
      <h5>Three stages, three sets of data</h5>
      <table className="ws-table"><tbody>
        <tr><td><strong>Calibration</strong></td><td>{st.calibration.data} {st.calibration.leds} LEDs, {st.calibration.points} points, fitted within {fold(st.calibration.rmseLog10)}. The green chain is {st.calibration.greenChain}; on {st.calibration.greenSpectrum.points} green action-spectrum points it never saw it is {fold(st.calibration.greenSpectrum.rmseLog10)} off.</td></tr>
        <tr><td><strong>Model selection</strong></td><td>{st.modelSelection.method} Result: {Object.entries(st.modelSelection.structures).map(([k, v]) => `${v} ${k === 'none' ? 'without effect' : k === 'both' ? 'on and off' : k + ' only'}`).join(', ')}. {Object.entries(st.modelSelection.usedInFinalTest).map(([led, v]) => `${ledName(led)}: ${v.structure} (left-out error ${fold(v.cvRmseLog10[v.structure])} against ${fold(v.cvRmseLog10.none)} with no effect)`).join('; ')}.</td></tr>
        <tr><td><strong>Final test</strong> <span className="ws-tag warn">retrospective</span></td><td>{st.finalTest.schedules.length} complete schedules from other experimental runs: pooled {fold(st.finalTest.pooled.mechanistic)}, published model {fold(st.finalTest.pooled.published)}, green-only {fold(st.finalTest.pooled.green)}, static baseline {fold(st.finalTest.pooled.baseline)}. {st.finalTest.coverage.inside} of {st.finalTest.coverage.total} measured points lie inside the 90 % interval ({num(st.finalTest.coverage.coverage * 100, 2)} %).</td></tr>
      </tbody></table>
      {st.finalTest.failures.length > 0 && <><h5>Misses in the final test</h5>
        {st.finalTest.failures.map(x => <p key={x.id} className="ws-warn"><TriangleAlert size={12}/> {x.name}: trajectory {fold(Math.log10(x.foldError))}, amplitude {pct(x.features.amplitude?.relativeError)}, time to peak {pct(x.features.timeToPeakMin?.relativeError)}, recovery {pct(x.features.halfRecoveryMin?.relativeError)}; {num(x.coverage * 100, 2)} % of points inside the interval. Missed: {x.why.join(', ')}.</p>)}
        {uv && <ScoreChart s={uv} model="mechanistic" compare="published" title="Miss · program driven by the 380 nm LED alone"/>}</>}
      <table className="ws-table"><thead><tr><th>Schedule</th><th>Role</th>{models.map(m => <th key={m}>{cat.models[m].split(' (')[0]}</th>)}<th>Amplitude</th><th>Timing</th><th>Recovery</th><th>In 90 % interval</th></tr></thead><tbody>
        {roles.flatMap(role => b.schedules[role].map(s => { const f = s.models[b.selected].features, timing = f.timeToPeakMin ?? f.halfRiseMin, rec = f.halfRecoveryMin, iv = s.models.mechanistic.interval;
          return <tr key={s.id} className={role}><td>{s.name}</td><td>{ROLE[role]}</td>{models.map(m => <td key={m} className={m === b.selected ? 'sel' : ''}>{fold(s.models[m].rmseLog10)}</td>)}
            <td>{f.amplitude?.supported ? pct(f.amplitude.relativeError) : '–'}</td><td>{timing?.supported ? `${num(timing.error, 2)} min` : 'not reached'}</td><td>{rec?.supported ? `${num(rec.error, 2)} min` : 'not reached'}</td><td>{iv ? `${iv.inside}/${iv.total}` : '–'}</td></tr>; }))}
        {roles.map(role => <tr key={role} className="total"><td>Pooled · {ROLE[role]}</td><td/>{models.map(m => <td key={m} className={m === b.selected ? 'sel' : ''}>{fold(b.summary[role][m])}</td>)}<td colSpan={3}>{role === 'mixedColour' ? 'fold error: 1.00× is perfect' : ''}</td><td>{num(b.intervalCoverage[role].coverage * 100, 2)} %</td></tr>)}
      </tbody></table>
      <p className="ws-hint">{b.publishedNote} {b.greenOnlyNote}</p>
      <p className="ws-hint">Growth check: the fit puts one doubling at {num(cat.measuredGrowth.fittedDoublingMin, 3)} min; the paper measured {cat.measuredGrowth.doublingMin} min, which the fit never saw.</p>
    </div>;
  }
  if (tab === 'sweep') {
    const base = lp.pulses[0] ?? {start: 30, duration: 60, intensity: 5}, values = vary === 'duration' ? [5, 15, 30, 60, 120, 240] : vary === 'intensity' ? [0.16, 0.5, 1.5, 5, 10, 20] : [45, 60, 90, 120, 180];
    const sw = lp.sweep;
    return <div>
      <div className="ws-row">
        <label className="ws-inline">Vary<select value={vary} onChange={e => setVary(e.target.value as typeof vary)}><option value="duration">pulse length</option><option value="intensity">pulse intensity</option><option value="period">gap between four pulses</option></select></label>
        <button className="ws-btn primary" disabled={lp.busy === 'sweep'} onClick={() => lp.runSweep(vary, values, {intensity: base.intensity, duration: vary === 'period' ? 30 : base.duration, start: base.start, pulses: vary === 'period' ? 4 : 1})}>{lp.busy === 'sweep' ? <LoaderCircle size={13} className="spin"/> : <FlaskConical size={13}/>}Run {values.length} programs</button>
        <span className="ws-hint">Starts from your first pulse ({base.intensity} µmol m⁻² s⁻¹, {base.duration} min at {base.start} min). Nothing is saved.</span>
      </div>
      {sw && <table className="ws-table"><thead><tr><th>{sw.vary === 'duration' ? 'Pulse length' : sw.vary === 'intensity' ? 'Intensity' : 'Period'} ({sw.unit})</th><th>Peak reporter (MEFL)</th><th>Time to peak (min)</th><th>Half recovery (min)</th><th>Light dose (µmol m⁻² s⁻¹ · min)</th></tr></thead>
        <tbody>{sw.rows.map((row: any) => <tr key={row.value}><td>{row.value}</td><td>{num(row.peak)}</td><td>{num(row.timeToPeakMin)}</td><td>{num(row.halfRecoveryMin)}</td><td>{num(row.dose)}</td></tr>)}</tbody></table>}
    </div>;
  }
  if (tab === 'control') {
    const c = lp.control, lo = cat.parameters[4].value * 1.05, hi = (cat.parameters[4].value + cat.parameters[5].value) * 0.95;
    return <div>
      {!cat.gate.passed ? <p className="ws-warn"><TriangleAlert size={12}/> {cat.gate.statement}</p> : <div className="ws-row">
        <label className="ws-inline">Hold the reporter at<input type="number" min={Math.ceil(lo)} max={Math.floor(hi)} step={1000} value={target} onChange={e => setTarget(Number(e.target.value))}/>MEFL</label>
        <button className="ws-btn primary" disabled={lp.busy === 'control'} onClick={() => lp.runControl(target)}>{lp.busy === 'control' ? <LoaderCircle size={13} className="spin"/> : <RotateCcw size={13}/>}Compare open and closed loop</button>
        <span className="ws-hint">Enabled because the open-loop model passed its held-out gate.</span></div>}
      {c && <div className="ws-grid2">
        <SyncChart title="Reporter of the virtual culture" time={c.closed.time} unit="MEFL" timeUnit="min" series={[{id: 'c', label: 'Closed loop (measured every ' + c.intervalMin + ' min)', values: c.closed.reporter, color: C.reporter, width: 2},
          {id: 'o', label: 'Open loop (constant light from the model)', values: c.open.reporter, color: C.measured, dash: true}, {id: 't', label: 'Target', values: c.closed.time.map(() => c.target), color: C.reference, dash: true}]}/>
        <div><SyncChart title="Light chosen by the controller" time={c.closed.time} unit="µmol m⁻² s⁻¹" timeUnit="min" height={130} series={[{id: 'l', label: 'Closed loop', values: c.closed.light, color: C.light}, {id: 'lo', label: 'Open loop', values: c.open.light, color: C.reference, dash: true}]}/>
          <table className="ws-table"><tbody><tr><td>Mean error in the second half · open loop</td><td>{num(c.open.relativeErrorSecondHalf * 100, 3)} %</td></tr><tr><td>Mean error in the second half · closed loop</td><td>{num(c.closed.relativeErrorSecondHalf * 100, 3)} %</td></tr></tbody></table>
          <p className="ws-hint">{c.evidence.statement}</p></div>
      </div>}
    </div>;
  }
  return null;
}

/** Parameters, solver checks and provenance of the light-pulse model, for the drawers. */
export function LightDrawer({lp, kind}: {lp: LightPulse; kind: 'parameters' | 'solver' | 'provenance' | 'diagnostics'}) {
  const {cat, result: r} = lp;
  if (!cat) return null;
  if (kind === 'parameters') return <>
    <label className="ws-field"><span>Predictor</span><select value={lp.model} onChange={e => lp.setModel(e.target.value)}><option value="auto">Chosen by the benchmark · {cat.models[cat.selected]}</option>{cat.runnable.map(k => <option key={k} value={k}>{cat.models[k]} · {fold(cat.summary.heldOut[k])} held-out error</option>)}</select></label>
    <div className="ws-row"><label className="ws-field"><span>Uncertainty samples</span><div><input type="number" min={0} max={cat.limits.samples} value={lp.samples} onChange={e => lp.setSamples(Number(e.target.value))}/><small>parameter sets</small></div></label>
      <label className="ws-field"><span>Seed</span><div><input type="number" min={0} value={lp.seed} onChange={e => lp.setSeed(Number(e.target.value))}/></div></label></div>
    <table className="ws-table"><thead><tr><th>Parameter</th><th>Value</th><th>95 % of accepted sets</th><th>Source</th></tr></thead><tbody>
      {cat.parameters.map(p => <tr key={p.key}><td title={p.description}><strong>{p.key}</strong> <small>{p.description}</small></td><td>{num(p.value)} <small>{p.unit}</small></td><td>{p.ci95 ? `${num(p.ci95[0])} – ${num(p.ci95[1])}` : '–'}</td>
        <td><span className={'ws-tag ' + (p.provenance.kind === 'fitted' ? 'modeled' : 'assumed')} title={p.provenance.note}>{p.provenance.kind}</span>{p.provenance.kind === 'fitted' && !p.determined && <span className="ws-tag warn" title="The training data leave this parameter loosely determined; the uncertainty band carries it.">loose</span>}</td></tr>)}
    </tbody></table>
    <p className="ws-hint">Fitted to {cat.training.points} points; all {cat.training.starts} starting points reach the same optimum. Learned model: ridge on {cat.learned.features} of filtered light (penalty {cat.learned.lambda}).</p>
    <h5>Other LEDs · switching rates from the action spectra</h5>
    <table className="ws-table"><thead><tr><th>LED</th><th>Effect</th><th>k1 on</th><th>k2 off</th><th>Published k1 · k2</th><th>Fit</th></tr></thead><tbody>
      {cat.channels.map(c => <tr key={c.led} className={c.led === RED ? 'sel' : ''}><td><strong>{c.led}</strong> <small>{c.centroidNm ? Math.round(c.centroidNm) + ' nm' : ''}</small></td><td>{c.structureName}</td>
        <td title={c.ci95 ? `95 % of accepted sets ${num(c.ci95.k1[0])} – ${num(c.ci95.k1[1])}` : ''}>{c.k1 ? num(c.k1) : '0'}</td><td title={c.ci95 ? `95 % of accepted sets ${num(c.ci95.k2[0])} – ${num(c.ci95.k2[1])}` : ''}>{c.k2 ? num(c.k2) : '0'}</td>
        <td>{num(c.published.k1 && c.published.k1 > 1e-5 ? c.published.k1 : 0)} · {num(c.published.k2 && c.published.k2 > 1e-5 ? c.published.k2 : 0)}</td><td>{fold(c.rmseLog10)}</td></tr>)}
    </tbody></table>
    <p className="ws-hint">Units m² s µmol⁻¹ min⁻¹. Each LED has {cat.channels[0]?.points} steady-state points; whether it switches the sensor on, off, both or neither is chosen by leaving one experimental run out. Published rates belong to the published model, whose other parameters differ, so they are shown for orientation only.</p>
  </>;
  if (kind === 'solver') return <>
    <p className="ws-hint">{cat.engine.numericalMethod}</p>
    <ul className="ws-eq">{cat.engine.equations.map(e => <li key={e}>{e}</li>)}</ul>
    {r ? <ul className="ws-checks">{r.checks.map(c => <li key={c.name} className={c.passed === false ? 'bad' : c.passed ? 'ok' : ''}>{c.passed ? <Check size={12}/> : <TriangleAlert size={12}/>}<div><strong>{c.name}</strong> · {c.threshold}<small>{c.detail}{c.value?.maxRelativeDifference != null ? ` Largest difference ${num(c.value.maxRelativeDifference * 100, 2)} %; ${c.value.solver}.` : ''}{c.value?.error ? ' ' + c.value.error : ''}</small></div></li>)}</ul> : <p className="ws-hint">Run an experiment to see its numerical checks.</p>}
  </>;
  if (kind === 'provenance') { const s = cat.dataset.source, sys = cat.dataset.system; return <>
    <dl className="ws-dl"><div><dt>Cell context</dt><dd>{sys.organism}, {sys.strain}</dd></div><div><dt>Sensor and reporter</dt><dd>{sys.sensor}; {sys.reporter}</dd></div><div><dt>Measurement</dt><dd>{sys.measurement}</dd></div>
      <div><dt>Data</dt><dd>{s.authors}. {s.title}. {s.journal}. doi:{s.doi}. {s.dataset}. {s.licence}.</dd></div><div><dt>Dataset SHA-256</dt><dd className="mono">{cat.dataset.sha256}</dd></div><div><dt>Changes to the data</dt><dd>{s.changes}</dd></div>
      {r && <><div><dt>This run</dt><dd className="mono">{r.id} · content {r.sha256.slice(0, 16)}… · series {r.seriesSha256.slice(0, 16)}…</dd></div><div><dt>Model and fit</dt><dd className="mono">{cat.engine.name} {r.record.solver.modelVersion} · fit {r.record.solver.fitSha256.slice(0, 16)}… · seed {r.record.inputs.seed.value}</dd></div>
        <div><dt>What drove the outputs</dt><dd>{r.record.drivers.map((d: any) => `${d.output}: ${d.drivenBy.join(', ')}`).join(' · ')}</dd></div></>}</dl></>; }
  return <>
    <h5>Assumptions</h5><ul className="ws-list">{cat.engine.assumptions.map(a => <li key={a}>{a}</li>)}</ul>
    <h5>Limits</h5><ul className="ws-list">{cat.engine.limits.map(a => <li key={a}>{a}</li>)}</ul>
    <h5>One state · version {cat.state.version}</h5>
    <table className="ws-table"><thead><tr><th>Quantity</th><th>Unit</th><th>Computed as</th><th>Drawn at</th></tr></thead><tbody>{cat.state.variables.map(v => <tr key={v.key}><td>{v.name}</td><td>{v.unit}</td><td className="mono">{v.from}</td><td>{v.where}</td></tr>)}</tbody></table>
    <p className="ws-hint"><span className="ws-tag assumed">relative</span> φ = {cat.state.phi.value} {cat.state.phi.unit}. {cat.state.phi.provenance.note}</p>
    <h5>Clocks</h5><ul className="ws-list">{cat.state.clocks.map(c => <li key={c.key}><strong>{c.key}</strong>{c.stepMin ? ` · ${c.stepMin} min` : ''}{c.frames ? ` · ${c.frames} frames` : ''}. {c.what}</li>)}</ul>
    <h5>Hand-offs</h5><ul className="ws-list">{cat.state.handoffs.map(h => <li key={h}>{h}</li>)}</ul>
    <h5>What has a location here</h5><p className="ws-hint">{cat.spatial.statement}</p>
    <table className="ws-table"><tbody>{cat.spatial.components.map(c => <tr key={c.quantity}><td>{c.quantity}</td><td>{c.where}</td><td>{c.note}</td></tr>)}</tbody></table>
    <p className="ws-hint">A protein crosses the cell in about {cat.spatial.mixing.equilibrationMs} ms ({cat.spatial.mixing.source}), so every modelled step sees a mixed cell.</p>
  </>;
}
export {pulsesToProgram, programAt};
