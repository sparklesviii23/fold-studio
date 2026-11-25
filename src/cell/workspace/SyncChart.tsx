import {useRef} from 'react';

export interface ChartSeries {id: string; label: string; values: (number | null)[]; color: string; dash?: boolean; width?: number}
export interface ChartBand {lo: number[]; hi: number[]; color: string; label: string}
export interface ChartPoints {label: string; t: number[]; y: number[]; color: string; symbol?: 'circle' | 'square' | 'triangle'}
/** A line on its own times (for example another model evaluated only where measurements exist). Drawn dotted. */
export interface ChartLine {label: string; t: number[]; y: number[]; color: string}
export interface ChartEvent {time: number; label: string; kind: string}

const W = 640, H = 220, M = {l: 58, r: 14, t: 14, b: 34};
const nice = (v: number) => { const a = Math.abs(v); return a === 0 ? '0' : a >= 1e4 || a < 1e-2 ? v.toExponential(1).replace('e+', 'e') : a >= 100 ? v.toFixed(0) : a >= 10 ? v.toFixed(1) : v.toFixed(2); };

/**
 * A time chart that shares the workspace's time cursor: the cursor is drawn at `cursor`, a click or drag reports the time
 * under the pointer through `onSeek`, and events appear as ticks along the time axis. Every series has a colour, a dash
 * pattern or symbol and a text label, so no reading depends on colour alone.
 */
export default function SyncChart({time, series, bands = [], points = [], lines = [], events = [], cursor, onSeek, unit, timeUnit, log, height = H, title}: {time: number[]; series: ChartSeries[]; bands?: ChartBand[]; points?: ChartPoints[]; lines?: ChartLine[]; events?: ChartEvent[];
  cursor?: number | null; onSeek?: (t: number) => void; unit: string; timeUnit: string; log?: boolean; height?: number; title?: string}) {
  const ref = useRef<SVGSVGElement>(null);
  if (!time.length) return null;
  const tr = (v: number) => log ? Math.log10(Math.max(v, 1e-12)) : v;
  const all = [...series.flatMap(s => s.values), ...bands.flatMap(b => [...b.lo, ...b.hi]), ...points.flatMap(p => p.y), ...lines.flatMap(p => p.y)].filter((v): v is number => v !== null && Number.isFinite(v) && (!log || v > 0)).map(tr);
  let y0 = Math.min(...all, log ? Infinity : 0), y1 = Math.max(...all, log ? -Infinity : 0);
  if (!Number.isFinite(y0) || !Number.isFinite(y1)) { y0 = 0; y1 = 1; }
  if (y1 === y0) y1 = y0 + 1;
  const pad = (y1 - y0) * 0.06; y1 += pad; if (log) y0 -= pad;
  const t0 = Math.min(time[0], ...points.flatMap(p => p.t)), t1 = Math.max(time[time.length - 1], ...points.flatMap(p => p.t));
  const x = (t: number) => M.l + (t - t0) / (t1 - t0 || 1) * (W - M.l - M.r), y = (v: number) => height - M.b - (tr(v) - y0) / (y1 - y0) * (height - M.b - M.t);
  const path = (v: (number | null)[]) => { let d = '', pen = false; v.forEach((val, i) => { if (val === null || !Number.isFinite(val) || (log && val <= 0)) { pen = false; return; } d += (pen ? 'L' : 'M') + x(time[i]).toFixed(1) + ' ' + y(val).toFixed(1); pen = true; }); return d; };
  const area = (b: ChartBand) => b.hi.map((v, i) => (i ? 'L' : 'M') + x(time[i]).toFixed(1) + ' ' + y(v).toFixed(1)).join('') + b.lo.map((_, i) => { const k = b.lo.length - 1 - i; return 'L' + x(time[k]).toFixed(1) + ' ' + y(b.lo[k]).toFixed(1); }).join('') + 'Z';
  const seek = (e: React.PointerEvent) => {
    if (!onSeek || !ref.current) return;
    const r = ref.current.getBoundingClientRect(), px = (e.clientX - r.left) / r.width * W;
    onSeek(Math.max(t0, Math.min(t1, t0 + (px - M.l) / (W - M.l - M.r) * (t1 - t0))));
  };
  const ticksY = Array.from({length: 5}, (_, i) => y0 + (y1 - y0) * i / 4), ticksT = Array.from({length: 6}, (_, i) => t0 + (t1 - t0) * i / 5);
  const mark = (p: ChartPoints, i: number) => { const cx = x(p.t[i]), cy = y(p.y[i]);
    return p.symbol === 'square' ? <rect key={i} x={cx - 3} y={cy - 3} width={6} height={6}/> : p.symbol === 'triangle' ? <path key={i} d={`M${cx} ${cy - 4}L${cx + 4} ${cy + 3}L${cx - 4} ${cy + 3}Z`}/> : <circle key={i} cx={cx} cy={cy} r={3}/>; };
  return <figure className="ws-chart">
    {title && <figcaption className="ws-chart-title">{title}</figcaption>}
    <svg ref={ref} viewBox={`0 0 ${W} ${height}`} role="img" aria-label={(title ?? 'Chart') + ': ' + series.map(s => s.label).join(', ')} onPointerDown={e => { (e.target as Element).setPointerCapture?.(e.pointerId); seek(e); }} onPointerMove={e => e.buttons === 1 && seek(e)} style={{cursor: onSeek ? 'crosshair' : 'default'}}>
      {ticksY.map((v, i) => <g key={i}><line x1={M.l} x2={W - M.r} y1={height - M.b - (v - y0) / (y1 - y0) * (height - M.b - M.t)} y2={height - M.b - (v - y0) / (y1 - y0) * (height - M.b - M.t)} className="grid"/>
        <text x={M.l - 6} y={height - M.b - (v - y0) / (y1 - y0) * (height - M.b - M.t) + 3.5} textAnchor="end">{nice(log ? 10 ** v : v)}</text></g>)}
      {ticksT.map((t, i) => <text key={i} x={x(t)} y={height - M.b + 14} textAnchor="middle">{nice(t)}</text>)}
      <text x={W - M.r} y={height - 4} textAnchor="end" className="axis">{timeUnit === 'min' ? 'simulated time, min' : 'simulated time, ' + timeUnit}</text>
      <text x={W - M.r - 4} y={M.t + 9} textAnchor="end" className="axis">{unit}{log ? ' · log scale' : ''}</text>
      {bands.map((b, i) => <path key={i} d={area(b)} fill={b.color} opacity={0.16}/>)}
      {series.map(s => <path key={s.id} d={path(s.values)} fill="none" stroke={s.color} strokeWidth={s.width ?? 1.8} strokeDasharray={s.dash ? '5 4' : undefined} strokeLinejoin="round"/>)}
      {lines.map(l => <path key={l.label} d={l.t.map((t, i) => (i ? 'L' : 'M') + x(t).toFixed(1) + ' ' + y(l.y[i]).toFixed(1)).join('')} fill="none" stroke={l.color} strokeWidth={1.6} strokeDasharray="2 3" strokeLinejoin="round"/>)}
      {points.map(p => <g key={p.label} fill={p.symbol === 'triangle' ? 'none' : p.color} stroke={p.color} strokeWidth={1.2} fillOpacity={0.85}>{p.t.map((_, i) => mark(p, i))}</g>)}
      {events.map((e, i) => e.time >= t0 && e.time <= t1 && <g key={i} className={'ev ' + e.kind}><line x1={x(e.time)} x2={x(e.time)} y1={height - M.b} y2={height - M.b - 7}/><title>{e.label}</title></g>)}
      {cursor != null && cursor >= t0 && cursor <= t1 && <line className="cursor" x1={x(cursor)} x2={x(cursor)} y1={M.t} y2={height - M.b}/>}
    </svg>
    <ul className="ws-legend">
      {series.map(s => <li key={s.id}><svg width="22" height="8"><line x1="0" x2="22" y1="4" y2="4" stroke={s.color} strokeWidth="2" strokeDasharray={s.dash ? '5 4' : undefined}/></svg>{s.label}</li>)}
      {lines.map(l => <li key={l.label}><svg width="22" height="8"><line x1="0" x2="22" y1="4" y2="4" stroke={l.color} strokeWidth="2" strokeDasharray="2 3"/></svg>{l.label}</li>)}
      {bands.map(b => <li key={b.label}><i style={{background: b.color, opacity: 0.35}}/>{b.label}</li>)}
      {points.map(p => <li key={p.label}><svg width="10" height="10" fill={p.symbol === 'triangle' ? 'none' : p.color} stroke={p.color}>{p.symbol === 'square' ? <rect x="2" y="2" width="6" height="6"/> : p.symbol === 'triangle' ? <path d="M5 1L9 9L1 9Z"/> : <circle cx="5" cy="5" r="3"/>}</svg>{p.label}</li>)}
    </ul>
  </figure>;
}
