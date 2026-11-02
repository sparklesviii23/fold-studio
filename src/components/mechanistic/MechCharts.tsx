import {useMemo, useRef, useState} from 'react';

/** Categorical slots in fixed order, validated for the dark chart surface (#0b1328). */
export const SERIES = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#9085e9'];
const W = 760, H = 260, M = {l: 64, r: 92, t: 14, b: 40};

export function fmt(v: number | null | undefined, digits = 3) {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—';
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-3 || a >= 1e5)) return v.toExponential(digits - 1).replace('e+', 'e');
  return Number(v.toPrecision(digits)).toLocaleString();
}

function ticks(lo: number, hi: number, n = 5, log = false): number[] {
  if (log) {
    const out: number[] = [];
    for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++) { const v = 10 ** e; if (v >= lo * 0.999 && v <= hi * 1.001) out.push(v); }
    return out.length >= 2 ? out : [lo, hi];
  }
  if (hi === lo) return [lo];
  const step0 = (hi - lo) / n, mag = 10 ** Math.floor(Math.log10(step0)), step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= step0)!;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(Number(v.toPrecision(12)));
  return out;
}

function scale(lo: number, hi: number, a: number, b: number, log = false) {
  if (log) { const l0 = Math.log(lo), l1 = Math.log(hi); return (v: number) => a + (Math.log(v) - l0) / (l1 - l0 || 1) * (b - a); }
  return (v: number) => a + (v - lo) / ((hi - lo) || 1) * (b - a);
}

function Axes({xs, ys, x, y, xLabel, yLabel, xLog, yLog}: {xs: number[]; ys: number[]; x: (v: number) => number; y: (v: number) => number; xLabel: string; yLabel: string; xLog?: boolean; yLog?: boolean}) {
  return <g className="mc-axes">
    {ys.map(v => <g key={'y' + v}><line x1={M.l} x2={W - M.r} y1={y(v)} y2={y(v)} className="mc-grid"/><text x={M.l - 8} y={y(v) + 4} textAnchor="end">{fmt(v, 3)}</text></g>)}
    {xs.map(v => <text key={'x' + v} x={x(v)} y={H - M.b + 16} textAnchor="middle">{fmt(v, 3)}</text>)}
    <line x1={M.l} x2={W - M.r} y1={H - M.b} y2={H - M.b} className="mc-baseline"/>
    <text x={(M.l + W - M.r) / 2} y={H - 6} textAnchor="middle" className="mc-axis-label">{xLabel}{xLog ? ' (log)' : ''}</text>
    <text transform={`translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)`} textAnchor="middle" className="mc-axis-label">{yLabel}{yLog ? ' (log)' : ''}</text>
  </g>;
}

export interface Series {id: string; label: string; values: number[]}

/** Nudge end-of-line labels apart so they never overlap (keeps their order). */
function placeLabels(ys: number[], gap = 13) {
  const order = ys.map((y, i) => [y, i] as [number, number]).sort((a, b) => a[0] - b[0]);
  const out = new Array(ys.length);
  let last = -Infinity;
  for (const [y, i] of order) { const v = Math.max(y, last + gap); out[i] = v; last = v; }
  return out as number[];
}

/** Time course: lines, optional 5–95 % and 25–75 % bands, crosshair tooltip and a playhead. */
export function TimeChart({time, series, timeUnit, unit, playhead, bands, xLabel}: {time: number[]; series: Series[]; timeUnit: string; unit: string; xLabel?: string; playhead?: number; bands?: {lo: number[]; hi: number[]; lo50: number[]; hi50: number[]}}) {
  const ref = useRef<SVGSVGElement>(null), [hover, setHover] = useState<number | null>(null);
  const all = series.flatMap(s => s.values).concat(bands ? [...bands.lo, ...bands.hi] : []).filter(Number.isFinite);
  const yMax = Math.max(...all, 0), yMin = Math.min(...all, 0);
  const x = scale(time[0], time[time.length - 1], M.l, W - M.r), y = scale(yMin, yMax === yMin ? yMin + 1 : yMax * 1.04, H - M.b, M.t);
  const path = (v: number[]) => v.map((val, i) => (i ? 'L' : 'M') + x(time[i]).toFixed(1) + ' ' + y(val).toFixed(1)).join('');
  const area = (lo: number[], hi: number[]) => path(hi) + lo.map((_, i) => 'L' + x(time[lo.length - 1 - i]).toFixed(1) + ' ' + y(lo[lo.length - 1 - i]).toFixed(1)).join('') + 'Z';
  const move = (e: React.PointerEvent) => {
    const r = ref.current!.getBoundingClientRect(), px = (e.clientX - r.left) / r.width * W;
    if (px < M.l || px > W - M.r) return setHover(null);
    const t = time[0] + (px - M.l) / (W - M.l - M.r) * (time[time.length - 1] - time[0]);
    let best = 0; for (let i = 1; i < time.length; i++) if (Math.abs(time[i] - t) < Math.abs(time[best] - t)) best = i;
    setHover(best);
  };
  const labels = series.length <= 4;
  return <div className="mc-chart">
    <svg ref={ref} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={'Time course of ' + series.map(s => s.label).join(', ')} onPointerMove={move} onPointerLeave={() => setHover(null)}>
      <Axes xs={ticks(time[0], time[time.length - 1])} ys={ticks(yMin, yMax)} x={x} y={y} xLabel={xLabel ?? 'Time (' + timeUnit + ')'} yLabel={unit}/>
      {bands && <><path d={area(bands.lo, bands.hi)} fill={SERIES[0]} opacity="0.16"/><path d={area(bands.lo50, bands.hi50)} fill={SERIES[0]} opacity="0.26"/></>}
      {series.map((s, i) => <path key={s.id} d={path(s.values)} fill="none" stroke={SERIES[i % SERIES.length]} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round"/>)}
      {labels && placeLabels(series.map(s => y(s.values[s.values.length - 1]))).map((ly, i) => <text key={'l' + series[i].id} x={W - M.r + 6} y={ly + 4} className="mc-direct">{series[i].label}</text>)}
      {playhead !== undefined && <line x1={x(time[playhead])} x2={x(time[playhead])} y1={M.t} y2={H - M.b} className="mc-playhead"/>}
      {hover !== null && <g>
        <line x1={x(time[hover])} x2={x(time[hover])} y1={M.t} y2={H - M.b} className="mc-crosshair"/>
        {series.map((s, i) => <circle key={s.id} cx={x(time[hover])} cy={y(s.values[hover])} r="4" fill={SERIES[i % SERIES.length]} stroke="#0b1328" strokeWidth="2"/>)}
      </g>}
    </svg>
    {hover !== null && <div className="mc-tooltip" style={{left: `${x(time[hover]) / W * 100}%`}}>
      <strong>{fmt(time[hover], 4)} {timeUnit}</strong>
      {series.map((s, i) => <span key={s.id}><i style={{background: SERIES[i % SERIES.length]}}/>{s.label}<b>{fmt(s.values[hover], 4)}</b></span>)}
    </div>}
    {series.length > 1 && <div className="mc-legend">{series.map((s, i) => <span key={s.id}><i style={{background: SERIES[i % SERIES.length]}}/>{s.label}</span>)}</div>}
  </div>;
}

/** Readout against one swept parameter. */
export function ScanChart({values, readout, xLabel, yLabel, log}: {values: number[]; readout: number[]; xLabel: string; yLabel: string; log?: boolean}) {
  const [hover, setHover] = useState<number | null>(null);
  const finite = readout.filter(Number.isFinite);
  const x = scale(values[0], values[values.length - 1], M.l, W - M.r, log), y = scale(Math.min(0, ...finite), Math.max(...finite) * 1.05 || 1, H - M.b, M.t);
  return <div className="mc-chart">
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={yLabel + ' against ' + xLabel}>
      <Axes xs={ticks(values[0], values[values.length - 1], 5, log)} ys={ticks(Math.min(0, ...finite), Math.max(...finite))} x={x} y={y} xLabel={xLabel} yLabel={yLabel} xLog={log}/>
      <path d={values.map((v, i) => (i ? 'L' : 'M') + x(v) + ' ' + y(readout[i])).join('')} fill="none" stroke={SERIES[0]} strokeWidth="2"/>
      {values.map((v, i) => <g key={i} onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)}>
        <circle cx={x(v)} cy={y(readout[i])} r="12" fill="transparent"/>
        <circle cx={x(v)} cy={y(readout[i])} r={hover === i ? 6 : 4.5} fill={SERIES[0]} stroke="#0b1328" strokeWidth="2"/>
      </g>)}
    </svg>
    {hover !== null && <div className="mc-tooltip" style={{left: `${x(values[hover]) / W * 100}%`}}><strong>{xLabel.split(' (')[0]} = {fmt(values[hover], 4)}</strong><span>{yLabel}<b>{fmt(readout[hover], 4)}</b></span></div>}
  </div>;
}

/** Sequential single-hue heatmap for a two-parameter scan. */
export function Heatmap({a, b, grid, label}: {a: {name: string; values: number[]}; b: {name: string; values: number[]}; grid: number[][]; label: string}) {
  const [hover, setHover] = useState<[number, number] | null>(null);
  const flat = grid.flat().filter(Number.isFinite), lo = Math.min(...flat), hi = Math.max(...flat);
  const ramp = (v: number) => { const t = hi > lo ? (v - lo) / (hi - lo) : 0.5; const c0 = [18, 34, 74], c1 = [159, 220, 255]; return `rgb(${c0.map((c, k) => Math.round(c + (c1[k] - c) * t)).join(',')})`; };
  const cw = (W - M.l - M.r) / b.values.length, ch = (H - M.t - M.b) / a.values.length;
  return <div className="mc-chart">
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label + ' over ' + a.name + ' and ' + b.name}>
      {grid.map((row, i) => row.map((v, j) => <rect key={i + '-' + j} x={M.l + j * cw + 1} y={H - M.b - (i + 1) * ch + 1} width={cw - 2} height={ch - 2} rx="3" fill={Number.isFinite(v) ? ramp(v) : '#333'}
        onPointerEnter={() => setHover([i, j])} onPointerLeave={() => setHover(null)}/>))}
      <g className="mc-axes">
        {b.values.map((v, j) => j % Math.ceil(b.values.length / 6) === 0 && <text key={j} x={M.l + (j + 0.5) * cw} y={H - M.b + 16} textAnchor="middle">{fmt(v, 2)}</text>)}
        {a.values.map((v, i) => i % Math.ceil(a.values.length / 6) === 0 && <text key={i} x={M.l - 8} y={H - M.b - (i + 0.5) * ch + 4} textAnchor="end">{fmt(v, 2)}</text>)}
        <text x={(M.l + W - M.r) / 2} y={H - 6} textAnchor="middle" className="mc-axis-label">{b.name}</text>
        <text transform={`translate(14 ${(M.t + H - M.b) / 2}) rotate(-90)`} textAnchor="middle" className="mc-axis-label">{a.name}</text>
      </g>
      <defs><linearGradient id="mc-ramp" x1="0" x2="0" y1="1" y2="0"><stop offset="0" stopColor={ramp(lo)}/><stop offset="1" stopColor={ramp(hi)}/></linearGradient></defs>
      <rect x={W - M.r + 24} y={M.t} width="12" height={H - M.t - M.b} rx="4" fill="url(#mc-ramp)"/>
      <text x={W - M.r + 42} y={M.t + 8} className="mc-axes-text">{fmt(hi)}</text><text x={W - M.r + 42} y={H - M.b} className="mc-axes-text">{fmt(lo)}</text>
    </svg>
    {hover && <div className="mc-tooltip" style={{left: `${(M.l + (hover[1] + 0.5) * cw) / W * 100}%`}}><strong>{a.name} = {fmt(a.values[hover[0]])}, {b.name} = {fmt(b.values[hover[1]])}</strong><span>{label}<b>{fmt(grid[hover[0]][hover[1]], 4)}</b></span></div>}
  </div>;
}

/** Diverging bars for sensitivity coefficients (blue positive, orange negative). */
export function SensitivityBars({items, label}: {items: {name: string; value: number | null}[]; label: string}) {
  const shown = useMemo(() => items.filter(i => i.value !== null).slice(0, 14), [items]);
  const max = Math.max(...shown.map(i => Math.abs(i.value!)), 1e-9);
  return <div className="mc-bars" role="table" aria-label={label}>
    {shown.map(i => <div key={i.name} className="mc-bar" role="row">
      <span role="cell" className="mc-bar-name">{i.name}</span>
      <span role="cell" className="mc-bar-track"><i style={{width: `${Math.abs(i.value!) / max * 50}%`, left: i.value! >= 0 ? '50%' : `${50 - Math.abs(i.value!) / max * 50}%`, background: i.value! >= 0 ? SERIES[0] : SERIES[1]}}/></span>
      <span role="cell" className="mc-bar-value">{fmt(i.value, 3)}</span>
    </div>)}
  </div>;
}
