import {useEffect, useMemo, useRef, useState} from 'react';
import {Check, FlaskConical, History, LoaderCircle, Pause, Play, TriangleAlert, X} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt, SERIES, TimeChart} from '../mechanistic/MechCharts';

const ELEMENT: Record<string, [number, string]> = {C: [0.62, '#c9b8a6'], N: [0.6, '#7d9bff'], O: [0.6, '#ff6f61'], S: [0.75, '#ffd166'], H: [0.3, '#e8ecf4']};

/** Real trajectory frames drawn as depth-shaded ball-and-stick; drag to rotate. Nothing between frames is interpolated. */
function TrajectoryViewer({run, frame, ghost, hydrogens}: {run: any; frame: number; ghost: boolean; hydrogens: boolean}) {
  const ref = useRef<HTMLCanvasElement>(null), rot = useRef({a: 0.4, b: -0.3}), drag = useRef<[number, number] | null>(null);
  const [, redraw] = useState(0);
  const centre = useMemo(() => { const f = run.reference as number[][]; const c = [0, 0, 0]; f.forEach(p => { c[0] += p[0]; c[1] += p[1]; c[2] += p[2]; }); return c.map(v => v / f.length); }, [run]);
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight;
    cv.width = W * dpr; cv.height = H * dpr;
    const g = cv.getContext('2d')!; g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    const {a, b} = rot.current, ca = Math.cos(a), sa = Math.sin(a), cb = Math.cos(b), sb = Math.sin(b);
    const scale = Math.min(W, H) / 26;
    const project = (p: number[]) => { const x = p[0] - centre[0], y = p[1] - centre[1], z = p[2] - centre[2];
      const x1 = ca * x + sa * z, z1 = -sa * x + ca * z; const y1 = cb * y - sb * z1, z2 = sb * y + cb * z1;
      return [W / 2 + x1 * scale, H / 2 - y1 * scale, z2]; };
    const keep = (i: number) => hydrogens || run.atoms[i].element !== 'H';
    const draw = (coords: number[][], alpha: number) => {
      const P = coords.map(project);
      g.globalAlpha = alpha * 0.85; g.lineCap = 'round';
      for (const [i, j] of run.bonds) { if (!keep(i) || !keep(j)) continue;
        const d = (P[i][2] + P[j][2]) / 2, shade = Math.max(0.35, Math.min(1, 0.7 + d / 30));
        g.strokeStyle = `rgba(${Math.round(150 * shade)},${Math.round(170 * shade)},${Math.round(210 * shade)},1)`; g.lineWidth = 0.22 * scale;
        g.beginPath(); g.moveTo(P[i][0], P[i][1]); g.lineTo(P[j][0], P[j][1]); g.stroke(); }
      const order = P.map((p, i) => i).filter(keep).sort((i, j) => P[i][2] - P[j][2]);
      for (const i of order) { const [r, col] = ELEMENT[run.atoms[i].element] ?? [0.6, '#aaa']; const p = P[i], s = r * scale * 0.55 * (1 + p[2] / 60);
        const grad = g.createRadialGradient(p[0] - s * 0.35, p[1] - s * 0.35, s * 0.1, p[0], p[1], s);
        grad.addColorStop(0, '#ffffff'); grad.addColorStop(0.35, col); grad.addColorStop(1, 'rgba(10,16,34,0.95)');
        g.globalAlpha = alpha * Math.max(0.45, Math.min(1, 0.75 + p[2] / 25)); g.fillStyle = grad; g.beginPath(); g.arc(p[0], p[1], s, 0, Math.PI * 2); g.fill(); }
      g.globalAlpha = 1;
    };
    if (ghost) draw(run.reference, 0.18);
    draw(run.frames[frame], 1);
  });
  return <canvas ref={ref} className="md-canvas" aria-label={`Trajectory frame ${frame + 1} at ${run.times[frame]} ps`}
    onPointerDown={e => { drag.current = [e.clientX, e.clientY]; (e.target as HTMLElement).setPointerCapture(e.pointerId); }}
    onPointerMove={e => { if (!drag.current) return; rot.current.a += (e.clientX - drag.current[0]) * 0.01; rot.current.b += (e.clientY - drag.current[1]) * 0.01; drag.current = [e.clientX, e.clientY]; redraw(x => x + 1); }}
    onPointerUp={() => { drag.current = null; }}/>;
}

/** Demo 12: OpenMM reference dynamics of Trp-cage with real frames, fluctuations and contact persistence. */
export default function MdLab() {
  const [run, setRun] = useState<any>(null), [job, setJob] = useState<any>(null), [error, setError] = useState(''), [runs, setRuns] = useState<any[]>([]);
  const [ps, setPs] = useState(50), [seed, setSeed] = useState(1), [frame, setFrame] = useState(0), [playing, setPlaying] = useState(false);
  const [ghost, setGhost] = useState(true), [hyd, setHyd] = useState(false);

  async function refresh() { try { const r = await rpc<any[]>('md_reference_runs', {}); setRuns(r); return r; } catch (e) { setError(String(e).replace(/^Error:\s*/, '')); return []; } }
  async function open(id: string) { try { const r = await rpc<any>('md_reference_record', {id}); setRun(r); setFrame(0); } catch (e) { setError(String(e).replace(/^Error:\s*/, '')); } }
  async function start() {
    setError('');
    try { const j = await rpc<any>('md_reference_start', {production_ps: ps, seed}); setJob({...j, elapsed: 0}); } catch (e) { setError(String(e).replace(/^Error:\s*/, '')); }
  }
  useEffect(() => { refresh().then(r => { const done = r.find(x => x.state === 'done'); const live = r.find(x => x.state === 'running'); if (live) setJob(live); if (done) void open(done.id); }); }, []);
  useEffect(() => {
    if (!job || job.state !== 'running') return;
    const t = setInterval(async () => {
      try { const s = await rpc<any>('md_reference_status', {id: job.id}); setJob((j: any) => ({...j, ...s}));
        if (s.state === 'done') { void open(job.id); void refresh(); } if (s.state === 'failed') setError('The simulation stopped: ' + (s.log || '').slice(-400)); }
      catch (e) { setError(String(e)); }
    }, 2000);
    return () => clearInterval(t);
  }, [job?.id, job?.state]);
  useEffect(() => { if (!playing || !run) return; const t = setInterval(() => setFrame(f => (f + 1) % run.frames.length), 70); return () => clearInterval(t); }, [playing, run]);

  const failed = run?.checks.filter((c: any) => !c.passed) ?? [];
  const resIdx = run?.residues.map((_: string, i: number) => i + 1) ?? [];

  return <>
    <section className="mech-panel rk-input">
      <label>Production length (ps)<input type="number" min={5} max={200} value={ps} onChange={e => setPs(Number(e.target.value))}/></label>
      <label>Seed<input type="number" min={1} value={seed} onChange={e => setSeed(Number(e.target.value))}/></label>
      <button className="button primary" disabled={job?.state === 'running'} onClick={start}><FlaskConical size={14}/>Run OpenMM</button>
      {job?.state === 'running' && <span className="mech-busy"><LoaderCircle size={16} className="spin"/>Integrating Trp-cage in the OpenMM runtime · {fmt(job.elapsed ?? 0, 2)} s (about {Math.round(20 + ps)} s)</span>}
    </section>
    {error && <div className="mech-error" role="alert"><TriangleAlert size={15}/>{error}</div>}
    {run && <>
      <p className="ms-question">{run.question}</p>
      <section className="ms-identity mech-panel">
        <FlaskConical size={18}/>
        <div><strong>{run.system.name} · PDB {run.system.pdb}</strong><span>{run.system.atoms} atoms · {run.frames.length} frames over {run.config.production_ps} ps · OpenMM {run.software.openmm} ({run.software.platform}) · {fmt(run.performance.nsPerDay, 3)} ns/day</span></div>
        <span className={'ms-pill ' + (failed.length ? 'fail' : 'ok')}>{failed.length ? <X size={12}/> : <Check size={12}/>}{run.checks.length - failed.length}/{run.checks.length} checks</span>
      </section>
      <div className="rna-badges"><span className="evidence-badge">{run.evidence.trajectory}</span><span className="rna-note">Reference: {run.evidence.reference}. Every frame shown is an integration state; nothing is interpolated.</span></div>

      <section className="ms-detail">
        <div className="mech-panel ms-detail-main">
          <TrajectoryViewer run={run} frame={frame} ghost={ghost} hydrogens={hyd}/>
          <div className="md-controls">
            <button className="icon-button" onClick={() => setPlaying(p => !p)} aria-label={playing ? 'Pause' : 'Play'}>{playing ? <Pause size={16}/> : <Play size={16}/>}</button>
            <input type="range" min={0} max={run.frames.length - 1} value={frame} onChange={e => { setPlaying(false); setFrame(Number(e.target.value)); }}/>
            <span className="mono">{fmt(run.times[frame], 4)} ps · RMSD {fmt(run.rmsd[frame], 3)} Å</span>
            <label><input type="checkbox" checked={ghost} onChange={e => setGhost(e.target.checked)}/> NMR model 1</label>
            <label><input type="checkbox" checked={hyd} onChange={e => setHyd(e.target.checked)}/> Hydrogens</label>
          </div>
          <p className="caption">Drag to rotate. The faint structure is NMR model 1, the starting point.</p>
        </div>
        <aside className="mech-panel ms-detail-side">
          <span className="eyebrow">Cage contacts · persistence over the trajectory</span>
          <table className="ms-table"><thead><tr><th>Contact</th><th>MD mean</th><th>NMR mean</th><th>Formed</th></tr></thead><tbody>
            {run.contacts.map((c: any) => <tr key={c.name}><td>{c.name}</td><td>{fmt(c.mean, 3)} Å</td><td>{fmt(c.nmrMean, 3)} Å</td><td>{fmt(c.persistence * 100, 3)} % <small>(NMR {fmt(c.nmrPersistence * 100, 3)} %)</small></td></tr>)}
          </tbody></table>
          <p className="caption">Centroid distances; “formed” below 6.5 Å (5 Å for the salt bridge).</p>
          <span className="eyebrow">Assumptions and limits</span>
          <ul className="ms-list">{run.assumptions.map((a: string) => <li key={a}>{a}</li>)}{run.limitations.map((a: string) => <li key={a} className="ms-limit">{a}</li>)}</ul>
          <span className="eyebrow">Sources</span>
          <ul className="ms-list">{Object.values(run.references).map((r: any) => <li key={r.doi}>{r.citation} <a href={'https://doi.org/' + r.doi} target="_blank" rel="noreferrer">doi:{r.doi}</a></li>)}</ul>
        </aside>
      </section>

      <section className="ms-grid">
        <div className="mech-panel ms-panel"><span className="eyebrow">Backbone RMSD from NMR model 1</span>
          <TimeChart time={run.times} timeUnit="ps" unit="Å" series={[{id: 'r', label: 'MD', values: run.rmsd}, {id: 'n', label: 'widest NMR model', values: run.times.map(() => Math.max(...run.nmrRmsd))}]} playhead={frame}/></div>
        <div className="mech-panel ms-panel"><span className="eyebrow">Per-residue Cα fluctuation</span>
          <TimeChart time={resIdx} timeUnit="residue" xLabel="Residue" unit="RMSF (Å)" series={[{id: 'md', label: 'MD', values: run.rmsfMd}, {id: 'nmr', label: 'NMR ensemble spread', values: run.rmsfNmr}]}/></div>
        <div className="mech-panel ms-panel"><span className="eyebrow">Contact distances</span>
          <TimeChart time={run.times} timeUnit="ps" unit="Å" series={run.contacts.map((c: any, i: number) => ({id: 'c' + i, label: c.name.split(' (')[0], values: c.series}))} playhead={frame}/></div>
        <div className="mech-panel ms-panel"><span className="eyebrow">Kinetic temperature</span>
          <TimeChart time={run.times} timeUnit="ps" unit="K" series={[{id: 't', label: 'Instantaneous', values: run.temperature}]} playhead={frame}/></div>
      </section>

      <section className="mech-panel ms-panel">
        <span className="eyebrow">Checks · numerical correctness of the simulation</span>
        {run.checks.map((c: any) => <div key={c.name} className={'mech-check ' + (c.passed ? 'ok' : 'fail')}>{c.passed ? <Check size={14}/> : <X size={14}/>}<div><strong>{c.name}</strong><span>{c.detail}</span></div></div>)}
      </section>
      <section className="mech-panel ms-panel">
        <div className="ms-row"><span className="eyebrow"><History size={12}/> Saved runs</span><span className="caption">Record {run.id.slice(0, 10)} · SHA-256 {run.sha256.slice(0, 12)} · seed {run.config.seed}</span></div>
        <div className="ms-runs">{runs.slice(0, 12).map(r => <button key={r.id} disabled={r.state !== 'done'} className={'ms-run ' + (r.id === run.id ? 'active' : '')} onClick={() => open(r.id)}>
          <strong>{r.state === 'done' ? `${r.productionPs} ps · seed ${r.seed}` : r.state}</strong><span>{r.created ? r.created.replace('T', ' ').slice(0, 16) : ''} {r.state === 'done' ? '· ' + (r.passed ? 'all checks pass' : 'check failed') : ''}</span></button>)}</div>
      </section>
    </>}
    {!run && !job && <p className="caption">No saved trajectory yet. Run OpenMM to integrate the reference system.</p>}
  </>;
}
