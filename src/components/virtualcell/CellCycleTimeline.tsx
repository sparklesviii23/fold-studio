import {useEffect, useMemo, useState} from 'react';
import {Camera, Pause, Play, RotateCcw, X} from 'lucide-react';
import {fmt, TimeChart} from '../mechanistic/MechCharts';

const PHASE_COLOR: Record<string, string> = {'G1': '#5d8bff', 'G1/S': '#44d6b0', 'S–G2': '#ffd36b', 'G2/M': '#ff6f8a'};
const LABEL: Record<string, string> = {Md: 'Cdk4–6/CycD', Me: 'Cdk2/CycE', Ma: 'Cdk2/CycA', Mb: 'Cdk1/CycB', E2F: 'E2F', Cdh1a: 'APC-Cdh1', Cdc20a: 'APC-Cdc20', p27: 'p27', Primer: 'Primer', Chk1: 'Chk1'};

/** Gérard & Goldbeter (2009) run by the Mechanistic Lab solver (virtual_cell_cycle.py): playback, scrubbing,
 *  phase proxies and snapshots. The 3D cell is not driven by this model (it has no geometric variables). */
export default function CellCycleTimeline({run, time, onTime, onSnapshot, onClose}: {run: any; time: number; onTime: (t: number) => void; onSnapshot: (t: number) => void; onClose: () => void}) {
  const [playing, setPlaying] = useState(false), [speed, setSpeed] = useState(2), [shown, setShown] = useState<string[]>(['Me', 'Ma', 'Mb', 'Cdc20a']);
  const t: number[] = run.time, a = run.analysis, end = t[t.length - 1];
  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => { const next = time + speed * 0.1 * 4; if (next >= end) { setPlaying(false); onTime(end); } else onTime(next); }, 40);
    return () => clearInterval(id);
  }, [playing, time, speed, end]);
  const i = useMemo(() => { let b = 0; for (let k = 1; k < t.length; k++) if (Math.abs(t[k] - time) < Math.abs(t[b] - time)) b = k; return b; }, [t, time]);
  const label = a.labels[i], phase = a.quiescent ? 'quiescent (G0-like)' : label == null ? 'unlabelled' : a.phases[label];
  const series = shown.filter(k => run.series[k]).map(k => ({id: k, label: LABEL[k] ?? k, values: run.series[k]}));
  return <section className="vc-card vc-cycle">
    <header><div><h3>Cell-cycle timeline</h3><small>{run.model.name} · {run.model.id} · GF {run.gf} · {run.hours} h · {run.evidence}</small></div>
      <button className="vc-icon" title="Close" onClick={onClose}><X size={13}/></button></header>
    <p className="vc-warn">{run.model.calibration} The 3D cell is not driven by this model: it has no size, nuclear or organelle variables.</p>
    <div className="vc-row vc-cycle-controls">
      <button className="vc-icon" title={playing ? 'Pause' : 'Play'} onClick={() => { if (time >= end) onTime(t[0]); setPlaying(!playing); }}>{playing ? <Pause size={14}/> : <Play size={14}/>}</button>
      <button className="vc-icon" title="Reset" onClick={() => { setPlaying(false); onTime(t[0]); }}><RotateCcw size={13}/></button>
      <select value={speed} onChange={e => setSpeed(Number(e.target.value))} aria-label="Playback speed">{[1, 2, 5, 10].map(s => <option key={s} value={s}>{s}×</option>)}</select>
      <input type="range" min={t[0]} max={end} step={t[1] - t[0]} value={time} onChange={e => { setPlaying(false); onTime(Number(e.target.value)); }} aria-label="Simulation time"/>
      <span className="mono">{fmt(t[i], 4)} h</span>
      <span className="vc-phase" style={{background: PHASE_COLOR[phase] ?? 'rgb(255 255 255 / 0.12)'}}>{phase}</span>
      <button className="text-button" onClick={() => onSnapshot(t[i])}><Camera size={13}/>Save snapshot</button>
    </div>
    <div className="vc-phasebar" aria-label="Phase proxies over time">{a.segments.map((s: any, k: number) =>
      <i key={k} title={`${s.phase} ${fmt(s.start, 3)}–${fmt(s.end, 3)} h`} style={{left: `${(s.start - t[0]) / (end - t[0]) * 100}%`, width: `${Math.max(0.3, (s.end - s.start) / (end - t[0]) * 100)}%`, background: PHASE_COLOR[s.phase]}}/>)}
      <b style={{left: `${(t[i] - t[0]) / (end - t[0]) * 100}%`}}/></div>
    <div className="vc-chart"><TimeChart time={t} series={series} timeUnit="h" unit="model concentration" xLabel="time (h)" playhead={i}/></div>
    <div className="vc-terms-list">{run.shown.map((k: string) => <button key={k} className={'vc-term ' + (shown.includes(k) ? 'on' : '')} onClick={() => setShown(shown.includes(k) ? shown.filter(x => x !== k) : [...shown, k])}>{LABEL[k] ?? k}</button>)}</div>
    <table className="vc-table"><tbody>
      <tr><td>Regime</td><td>{a.regime}</td></tr>
      <tr><td>Period</td><td>{a.period == null ? '—' : `${fmt(a.period, 4)} h${a.periodSd != null ? ` ± ${fmt(a.periodSd, 2)}` : ''} over ${a.cyclesAnalysed} cycles (after ${fmt(a.transientExcluded, 3)} h transient)`}</td></tr>
      <tr><td>Mitotic exit (proxy)</td><td>{a.mitoticExit.length ? a.mitoticExit.map((x: number) => fmt(x, 4) + ' h').join(', ') : '—'}</td></tr>
      <tr><td>Solver</td><td>{run.solver.library} · {run.solver.method} · rtol {run.solver.rtol} · {run.solver.points} points</td></tr>
      <tr><td>Numerical check</td><td>{run.diagnostics.reliable ? 'reliable' : 'NOT reliable'} · tolerance sensitivity {Number(run.diagnostics.toleranceSensitivity).toExponential(1)} · {run.diagnostics.negativeValues ? 'negative values' : 'no negative values'}</td></tr>
      <tr><td>Model</td><td>{run.model.species} species · {run.model.parameters} parameters · {run.model.sbml} · sha256 {run.model.sha256.slice(0, 12)} · {run.model.licence}</td></tr>
    </tbody></table>
    <p className="caption">Phase rule: {a.rule} Not modelled: {run.model.notModelled.join(', ')}. {run.interpretation}</p>
  </section>;
}
