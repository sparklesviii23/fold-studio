import {useEffect, useMemo, useRef, useState} from 'react';
import {Check, CircleHelp, Cloud, LoaderCircle, Pause, Play, TriangleAlert} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt, SERIES, TimeChart} from '../mechanistic/MechCharts';

const SAMPLES: Record<string, {title: string; text: string; days: number}> = {
  cancer_immune: {title: '3D tumor–immune', text: 'A 3D tumor with heterogeneous immunogenicity grows in oxygen; at day 14 immune cells are seeded around it and attack. Ozik et al. 2018.', days: 21},
  heterogeneity: {title: '2D heterogeneous tumor', text: 'An oxygen-limited tumor whose cells carry an inherited oncoprotein level that sets their proliferation rate; a necrotic core forms where oxygen runs out. Ghaffarizadeh et al. 2018.', days: 21},
};
const TYPE_COLORS = ['#ff8a6b', '#5fd4ff', '#c6a7ff', '#7ee0a1', '#ffd166'];
const DEAD = '#59606e';

/** Oncoprotein (0–2) colour ramp: blue (low) → amber (high), as in the published heterogeneity figures. */
function ramp(v: number) { const t = Math.max(0, Math.min(1, v / 2)); return `rgb(${Math.round(70 + 185 * t)},${Math.round(120 + 70 * t)},${Math.round(255 - 200 * t)})`; }
function heat(t: number) { t = Math.max(0, Math.min(1, t)); return [Math.round(20 + 235 * t ** 0.8), Math.round(30 + 180 * t), Math.round(90 + 120 * (1 - Math.abs(t - 0.5) * 2))]; }

/** Every cell PhysiCell saved (or a recorded uniform sample of it) drawn as a shaded sphere at its computed position; drag to rotate, wheel to zoom. */
function TumorScene({data, frame, colorBy}: {data: any; frame: number; colorBy: string}) {
  const flat = data.grid.nz <= 1, ref = useRef<HTMLCanvasElement>(null), rot = useRef(flat ? {a: 0, b: 0} : {a: 0.5, b: -0.35}), zoom = useRef(1), drag = useRef<[number, number] | null>(null), [, redraw] = useState(0);
  // Frame the tumor, not the whole mesh: the widest cell extent over the run, with a margin.
  const extent = useMemo(() => { let m = 50; for (const f of data.frames) for (const c of f.cells) m = Math.max(m, Math.abs(c[0]), Math.abs(c[1]), Math.abs(c[2])); return m * 1.15; }, [data]);
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight; cv.width = W * dpr; cv.height = H * dpr;
    const g = cv.getContext('2d')!; g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    const cells: number[][] = data.frames[frame].cells, x = data.grid.x, half = (x[x.length - 1] - x[0]) / 2 + 10;
    const s = Math.min(W, H) / (2 * Math.min(extent, half)) * zoom.current, {a, b} = rot.current, ca = Math.cos(a), sa = Math.sin(a), cb = Math.cos(b), sb = Math.sin(b);
    const pts = cells.map(c => { const x1 = ca * c[0] + sa * c[2], z1 = -sa * c[0] + ca * c[2]; const y2 = cb * c[1] - sb * z1, z2 = sb * c[1] + cb * z1; return [W / 2 + x1 * s, H / 2 - y2 * s, z2, c] as [number, number, number, number[]]; });
    pts.sort((p, q) => p[2] - q[2]);
    // Domain box: the BioFVM mesh boundary, where the Dirichlet oxygen condition is applied.
    g.strokeStyle = 'rgba(160,190,255,.16)'; g.lineWidth = 1;
    const corners = [-1, 1].flatMap(i => [-1, 1].flatMap(j => [-1, 1].map(k => [i * half, j * half, data.grid.nz > 1 ? k * half : 0])));
    const P = (p: number[]) => { const x1 = ca * p[0] + sa * p[2], z1 = -sa * p[0] + ca * p[2]; return [W / 2 + x1 * s, H / 2 - (cb * p[1] - sb * z1) * s]; };
    for (let i = 0; i < 8; i++) for (let j = i + 1; j < 8; j++) { const d = [0, 1, 2].filter(k => corners[i][k] !== corners[j][k]).length; if (d === 1) { const [p, q] = [P(corners[i]), P(corners[j])]; g.beginPath(); g.moveTo(p[0], p[1]); g.lineTo(q[0], q[1]); g.stroke(); } }
    for (const [px, py, , c] of pts) {
      const r = Math.max(1.2, c[3] * s), dead = c[5] >= 0.5;
      const col = dead ? DEAD : colorBy === 'oncoprotein' ? ramp(c[7]) : TYPE_COLORS[c[4] % TYPE_COLORS.length];
      const grad = g.createRadialGradient(px - r * 0.35, py - r * 0.35, r * 0.1, px, py, r);
      grad.addColorStop(0, 'rgba(255,255,255,.85)'); grad.addColorStop(0.25, col); grad.addColorStop(1, 'rgba(0,0,0,.55)');
      g.fillStyle = grad; g.globalAlpha = dead ? 0.55 : 0.95; g.beginPath(); g.arc(px, py, r, 0, Math.PI * 2); g.fill();
    }
    g.globalAlpha = 1;
  });
  return <canvas ref={ref} className="tme-scene" aria-label="PhysiCell cells at their computed positions"
    onPointerDown={e => { drag.current = [e.clientX, e.clientY]; (e.target as HTMLElement).setPointerCapture(e.pointerId); }}
    onPointerUp={() => { drag.current = null; }}
    onPointerMove={e => { if (!drag.current) return; rot.current.a += (e.clientX - drag.current[0]) * 0.01; rot.current.b += (e.clientY - drag.current[1]) * 0.01; drag.current = [e.clientX, e.clientY]; redraw(n => n + 1); }}
    onWheel={e => { zoom.current = Math.max(0.4, Math.min(6, zoom.current * (e.deltaY < 0 ? 1.1 : 0.9))); redraw(n => n + 1); }}/>;
}

/** The computed substrate field on the mesh mid-plane (z₀), with the cells lying in that plane overlaid. */
function FieldSlice({data, frame, sub}: {data: any; frame: number; sub: number}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const max = useMemo(() => { let m = 1e-12; for (const f of data.frames) for (const v of f.fields[sub]) if (v != null && v > m) m = v; return m; }, [data, sub]); // a loop: spreading ~10⁵ values overflows the stack
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const {x, y, z0} = data.grid, nx = x.length, ny = y.length, f = data.frames[frame].fields[sub];
    const img = new ImageData(nx, ny);
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) { const v = f[j * nx + i], k = ((ny - 1 - j) * nx + i) * 4, [r, gg, b] = v == null ? [0, 0, 0] : heat(v / max); img.data[k] = r; img.data[k + 1] = gg; img.data[k + 2] = b; img.data[k + 3] = 255; }
    const off = document.createElement('canvas'); off.width = nx; off.height = ny; off.getContext('2d')!.putImageData(img, 0, 0);
    const dpr = window.devicePixelRatio || 1, S = cv.clientWidth; cv.width = S * dpr; cv.height = S * dpr;
    const g = cv.getContext('2d')!; g.setTransform(dpr, 0, 0, dpr, 0, 0); g.imageSmoothingEnabled = true; g.drawImage(off, 0, 0, S, S);
    const dx = x[1] - x[0], x0 = x[0] - dx / 2, span = x[nx - 1] - x[0] + dx;
    g.strokeStyle = 'rgba(255,255,255,.55)'; g.lineWidth = 0.6;
    for (const c of data.frames[frame].cells as number[][]) if (Math.abs(c[2] - z0) <= dx) { g.beginPath(); g.arc((c[0] - x0) / span * S, S - (c[1] - x0) / span * S, Math.max(0.6, c[3] / span * S), 0, Math.PI * 2); g.stroke(); }
  }, [data, frame, sub, max]);
  const s = data.substrates[sub];
  return <div className="tme-field"><canvas ref={ref} aria-label={`${s.name} on the mid-plane`}/>
    <div className="tme-scale"><span>0</span><i/><span>{fmt(max, 3)} {s.units}</span></div>
    <small>{s.name} · z = {fmt(data.grid.z0, 3)} µm · D = {fmt(s.diffusion, 3)} µm²/min · decay {fmt(s.decay, 3)} /min · boundary {fmt(s.dirichlet, 3)}</small></div>;
}

/** Analyse › Oncology Universe › Tumor Microenvironment: PhysiCell runs on your server; the app shows and checks what it computed. */
export default function TumorLab({projectId}: {projectId: string}) {
  const [runs, setRuns] = useState<any[]>([]), [data, setData] = useState<any>(null), [error, setError] = useState(''), [busy, setBusy] = useState('');
  const [sample, setSample] = useState('cancer_immune'), [days, setDays] = useState(21), [approved, setApproved] = useState(false);
  const [immune, setImmune] = useState({immuneScale: 1, immuneStartDay: -1, killScale: 1});
  const [frame, setFrame] = useState(0), [playing, setPlaying] = useState(false), [sub, setSub] = useState(0), [colorBy, setColorBy] = useState('type');
  async function refresh() { const r = await rpc<any[]>('tme_runs', {projectId}).catch(() => null); if (r) setRuns(r); return r; }
  useEffect(() => { void refresh().then(r => { const first = r?.find(x => x.ready); if (first) void open(first.id); }); }, []);
  useEffect(() => { // One status request at a time while a run is on the server.
    const live = runs.filter(r => r.state === 'launching' || r.state === 'running'); if (!live.length) return;
    let stop = false, timer: any;
    const tick = async () => { for (const r of live) { if (stop) return; await rpc('gpu_task_status', {projectId, taskId: r.id}).catch(() => null); } if (!stop) { await refresh(); timer = setTimeout(tick, 5000); } };
    timer = setTimeout(tick, 2000); return () => { stop = true; clearTimeout(timer); };
  }, [runs.map(r => r.id + r.state).join()]);
  useEffect(() => { if (!playing || !data) return; const t = setInterval(() => setFrame(f => (f + 1) % data.frames.length), 160); return () => clearInterval(t); }, [playing, data]);

  async function open(id: string) { setBusy('Loading results'); setError(''); try { const d = await rpc<any>('tme_load', {projectId, taskId: id}); setData(d); setFrame(d.frames.length - 1); setColorBy(d.sample === 'heterogeneity' ? 'oncoprotein' : 'type'); } catch (e) { setError(String(e).replace(/^Error:\s*/, '')); } finally { setBusy(''); } }
  async function launch() {
    setBusy('Sending to your server'); setError('');
    try { await rpc('gpu_task_submit', {projectId, recipe: 'physicell', inputs: {sample, days, ...(sample === 'cancer_immune' ? immune : {})}, approvedRemoteCost: approved}); setApproved(false); await refresh(); }
    catch (e) { setError(String(e).replace(/^Error:\s*/, '')); } finally { setBusy(''); }
  }

  const f = data?.frames[frame];
  const series = data ? Object.entries(data.series).flatMap(([name, v]: any) => [{id: name + 'l', label: name + ' · live', values: v.live}, {id: name + 'd', label: name + ' · dead', values: v.dead}]) : [];
  const best = data?.growthFits.fits.filter((m: any) => m.deltaAic != null).sort((a: any, b: any) => a.deltaAic - b.deltaAic)[0];
  return <div className="page-content tme-lab">
    <div className="page-heading"><div><span className="eyebrow">ONCOLOGY UNIVERSE · TUMOR MICROENVIRONMENT</span><h1>Inside a <em>living tumor.</em></h1>
      <p>Cells, oxygen and immune attack computed by PhysiCell on your server, from published reference models. What you see is what the solver computed.</p></div></div>

    <section className="quiet-panel tme-launch">
      <div className="tme-samples">{Object.entries(SAMPLES).map(([id, s]) => <button key={id} className={'tme-sample ' + (sample === id ? 'selected' : '')} onClick={() => { setSample(id); setDays(s.days); }}><strong>{s.title}</strong><span>{s.text}</span>{sample === id && <Check size={14}/>}</button>)}</div>
      <div className="tme-launch-row">
        <label>Simulated days<input type="number" min={1} max={45} value={days} onChange={e => setDays(Number(e.target.value))}/></label>
        {sample === 'cancer_immune' && <>
          <label>Immune cells seeded × <input type="number" min={0} max={5} step={0.25} value={immune.immuneScale} onChange={e => setImmune({...immune, immuneScale: Number(e.target.value)})}/></label>
          <label>Immune cells arrive on day (−1 = sample's day 14)<input type="number" min={-1} max={45} step={1} value={immune.immuneStartDay} onChange={e => setImmune({...immune, immuneStartDay: Number(e.target.value)})}/></label>
          <label>Kill rate × <input type="number" min={0} max={5} step={0.25} value={immune.killScale} onChange={e => setImmune({...immune, killScale: Number(e.target.value)})}/></label></>}
        <label className="tme-approve"><input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)}/>Run on my active server account (16 CPU cores, billed by the provider; a 21-day 3D run can take hours)</label>
        <button className="button primary" disabled={!approved || !!busy} onClick={launch}><Cloud size={14}/>Run on server</button>
      </div>
      {sample === 'cancer_immune' && days <= (immune.immuneStartDay >= 0 ? immune.immuneStartDay : 14) && <p className="caption"><TriangleAlert size={12}/> Immune cells are seeded on day {immune.immuneStartDay >= 0 ? immune.immuneStartDay : 14}; simulate past that day to see the attack.</p>}
      <div className="tme-runs">{runs.map(r => <button key={r.id} className={'tme-run ' + (data?.taskId === r.id ? 'selected' : '')} disabled={!r.ready} onClick={() => open(r.id)}>
        <strong>{SAMPLES[r.inputs?.sample]?.title ?? r.inputs?.sample} · {r.inputs?.days} d{r.inputs?.immuneScale != null && (r.inputs.immuneScale !== 1 || r.inputs.killScale !== 1 || r.inputs.immuneStartDay >= 0) ? ` · immune ×${r.inputs.immuneScale}, kill ×${r.inputs.killScale}${r.inputs.immuneStartDay >= 0 ? `, day ${r.inputs.immuneStartDay}` : ''}` : ''}</strong>
        <span>{(r.state === 'running' || r.state === 'launching') && <LoaderCircle size={12} className="spin"/>}{r.ready ? 'results ready' : r.state}{r.created ? ' · ' + r.created.replace('T', ' ').slice(0, 16) : ''}</span></button>)}
        {!runs.length && <p className="caption">No runs yet. Live server logs for each run are in System › Cloud GPU Tasks.</p>}</div>
      {error && <p className="caption cs-error">{error}</p>}{busy && <p className="caption"><LoaderCircle size={12} className="spin"/> {busy}…</p>}
    </section>

    {data && f && <>
      <section className="tme-stage">
        <div className="tme-view"><TumorScene data={data} frame={frame} colorBy={colorBy}/>
          <div className="tme-legend">{colorBy === 'oncoprotein' ? <span><i style={{background: 'linear-gradient(90deg,' + ramp(0) + ',' + ramp(2) + ')'}}/>oncoprotein 0 → 2</span> : Object.entries(data.types).map(([id, n]: any) => <span key={id}><i style={{background: TYPE_COLORS[Number(id) % TYPE_COLORS.length]}}/>{n}</span>)}<span><i style={{background: DEAD}}/>dead</span></div>
          <span className="tme-badge">Mechanistic simulation · {data.engine} {data.version}</span>
          <span className="tme-count">{f.total.toLocaleString()} cells{f.sampled < f.total ? ` · ${f.sampled.toLocaleString()} drawn` : ''}</span></div>
        <div className="tme-side">
          <div className="tme-tabs">{data.substrates.map((s: any, i: number) => <button key={s.name} className={'gt-view ' + (sub === i ? 'selected' : '')} onClick={() => setSub(i)}>{s.name}</button>)}
            {data.frames[0].cells[0]?.[7] !== undefined && data.sample === 'heterogeneity' && <button className={'gt-view ' + (colorBy === 'oncoprotein' ? 'selected' : '')} onClick={() => setColorBy(colorBy === 'oncoprotein' ? 'type' : 'oncoprotein')}>colour by oncoprotein</button>}</div>
          <FieldSlice data={data} frame={frame} sub={sub}/>
        </div>
      </section>
      <div className="tme-timeline"><button className="button" onClick={() => setPlaying(p => !p)}>{playing ? <Pause size={14}/> : <Play size={14}/>}</button>
        <input type="range" min={0} max={data.frames.length - 1} value={frame} onChange={e => { setPlaying(false); setFrame(Number(e.target.value)); }}/>
        <span>day {fmt(f.t / 1440, 3)} · frame {frame + 1}/{data.frames.length} (of {data.snapshots} saved)</span></div>

      <section className="tme-grid">
        <div className="quiet-panel"><span className="eyebrow">Populations</span>
          <TimeChart time={data.days} timeUnit="d" unit="cells" xLabel="simulated days" series={series} playhead={frame}/>
          <p className="caption">{data.evidence.simulation}. Counts include every cell, not only the drawn sample.</p></div>
        <div className="quiet-panel"><span className="eyebrow">Growth law · {data.growthFits.population}</span>
          <table className="tme-table"><thead><tr><th>Model</th><th>Equation</th><th>Parameters (± SE, per day)</th><th>ΔAIC</th></tr></thead>
            <tbody>{data.growthFits.fits.map((m: any) => <tr key={m.model} className={m === best ? 'best' : ''}><td>{m.model}</td><td>{m.equation}</td>
              <td>{m.params ? m.params.map((p: number, i: number) => fmt(p, 3) + (m.se?.[i] != null ? ' ± ' + fmt(m.se[i], 2) : '')).join(', ') : m.error}</td><td>{m.deltaAic != null ? fmt(m.deltaAic, 3) : '—'}</td></tr>)}</tbody></table>
          <p className="caption">{data.evidence.fits}. ΔAIC below 2 means the data cannot separate the models.</p></div>
        <div className="quiet-panel"><span className="eyebrow">Checks on the returned output</span>
          <ul className="tme-checks">{data.checks.map((c: any) => <li key={c.check}>{c.passed === true ? <Check size={14} className="ok"/> : c.passed === false ? <TriangleAlert size={14} className="bad"/> : <CircleHelp size={14}/>}<div><strong>{c.check}</strong><span>{c.detail}</span></div></li>)}</ul>
          <p className="caption">{data.evidence.checks}. These test the run's internal physics, not agreement with a real tumor.</p></div>
        <div className="quiet-panel"><span className="eyebrow">Provenance</span>
          <p className="caption">{data.engine} {data.version} · sample “{data.sample}” · BioFVM mesh {data.grid.x.length} × {data.grid.y.length} × {data.grid.nz} voxels · {data.snapshots} saved snapshots · {data.sampling}.</p>
          <p className="caption">Parameters are the published reference set shipped with PhysiCell (config file returned with the run). Not calibrated to a patient, cell line or dataset: a reference scenario, not a digital twin.</p></div>
      </section>
    </>}
  </div>;
}
