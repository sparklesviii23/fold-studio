import {useMemo, useState} from 'react';
import {fmt} from './MechCharts';

export interface ModelDescription {id: string; name: string; species: {id: string; name: string; state: boolean; initial: number}[]; reactions: {id: string; name: string; scheme: string; rate: string; species: string[]; parameters: string[]; modifiers: string[]}[]; [k: string]: any}
const W = 900, H = 560;
const MAX_SPECIES = 120, MAX_REACTIONS = 160;

function hash(s: string) { let h = 2166136261; for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return (h >>> 0) / 4294967296; }

/** Deterministic force layout (seeded by ids) so a model always draws the same way. */
function layout(nodes: string[], edges: [string, string][], iterations = 260) {
  const idx = new Map(nodes.map((n, i) => [n, i])), n = nodes.length;
  const x = nodes.map((id, i) => W / 2 + Math.cos(i / n * 6.283 + hash(id)) * W * 0.32), y = nodes.map((id, i) => H / 2 + Math.sin(i / n * 6.283 + hash(id)) * H * 0.32);
  const k = Math.sqrt(W * H / Math.max(n, 1)) * 0.55;
  for (let it = 0; it < iterations; it++) {
    const fx = new Float64Array(n), fy = new Float64Array(n), temp = 24 * (1 - it / iterations) + 0.5;
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      const dx = x[i] - x[j], dy = y[i] - y[j], d2 = dx * dx + dy * dy + 0.01, f = k * k / d2;
      fx[i] += dx * f; fy[i] += dy * f; fx[j] -= dx * f; fy[j] -= dy * f;
    }
    for (const [a, b] of edges) {
      const i = idx.get(a)!, j = idx.get(b)!, dx = x[i] - x[j], dy = y[i] - y[j], d = Math.sqrt(dx * dx + dy * dy) + 0.01, f = d / k;
      fx[i] -= dx * f; fy[i] -= dy * f; fx[j] += dx * f; fy[j] += dy * f;
    }
    for (let i = 0; i < n; i++) {
      fx[i] += (W / 2 - x[i]) * 0.02; fy[i] += (H / 2 - y[i]) * 0.02;
      const m = Math.hypot(fx[i], fy[i]) || 1;
      x[i] = Math.min(W - 40, Math.max(40, x[i] + fx[i] / m * Math.min(m, temp)));
      y[i] = Math.min(H - 30, Math.max(30, y[i] + fy[i] / m * Math.min(m, temp)));
    }
  }
  return new Map(nodes.map((id, i) => [id, [x[i], y[i]] as [number, number]]));
}

/** The model's reaction network, coloured by computed concentrations at the playhead. */
export function ReactionNetwork({model, values, maxima, selected, highlight, onSelect}: {model: ModelDescription; values?: Record<string, number>; maxima?: Record<string, number>; selected?: string | null; highlight?: string | null; onSelect: (reactionId: string) => void}) {
  const [hover, setHover] = useState<string | null>(null);
  const view = useMemo(() => {
    const degree = new Map<string, number>();
    for (const r of model.reactions) for (const s of r.species) degree.set(s, (degree.get(s) ?? 0) + 1);
    const species = [...model.species].sort((a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0)).slice(0, MAX_SPECIES).map(s => s.id);
    const keep = new Set(species);
    const compact = model.reactions.length > MAX_REACTIONS;
    const reactions = compact ? [] : model.reactions.filter(r => r.species.some(s => keep.has(s)));
    const edges: [string, string][] = [];
    if (compact) {
      const seen = new Set<string>();
      for (const r of model.reactions) {
        const s = r.species.filter(x => keep.has(x));
        for (let i = 0; i < s.length; i++) for (let j = i + 1; j < s.length; j++) { const key = s[i] + '|' + s[j]; if (!seen.has(key)) { seen.add(key); edges.push([s[i], s[j]]); } }
      }
    } else for (const r of reactions) for (const s of r.species) if (keep.has(s)) edges.push(['rx:' + r.id, s]);
    const pos = layout([...species, ...reactions.map(r => 'rx:' + r.id)], edges, compact || species.length > 60 ? 140 : 260);
    return {species, reactions, edges, pos, compact, hidden: model.species.length - species.length};
  }, [model]);
  const hot = new Set<string>();
  const focus = model.reactions.find(r => r.id === (selected ?? hover));
  if (focus) focus.species.forEach(s => hot.add(s));
  if (highlight) model.reactions.filter(r => r.parameters.includes(highlight)).forEach(r => { hot.add('rx:' + r.id); r.species.forEach(s => hot.add(s)); });
  const names = new Map(model.species.map(s => [s.id, s.name]));
  return <div className="mc-network">
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={'Reaction network of ' + model.name}>
      <defs><radialGradient id="mc-node" cx="35%" cy="30%"><stop offset="0" stopColor="#fff" stopOpacity="0.55"/><stop offset="1" stopColor="#fff" stopOpacity="0"/></radialGradient></defs>
      {view.edges.map(([a, b], i) => { const [x1, y1] = view.pos.get(a)!, [x2, y2] = view.pos.get(b)!; const on = hot.has(a) && hot.has(b) || (focus && (a === 'rx:' + focus.id)); return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} className={'mc-edge' + (on ? ' on' : '')}/>; })}
      {view.reactions.map(r => { const [x, y] = view.pos.get('rx:' + r.id)!; const on = selected === r.id || hot.has('rx:' + r.id); return <g key={r.id} transform={`translate(${x} ${y})`} className={'mc-rx' + (on ? ' on' : '')} onClick={() => onSelect(r.id)} onPointerEnter={() => setHover(r.id)} onPointerLeave={() => setHover(null)}>
        <rect x="-7" y="-7" width="14" height="14" rx="3" transform="rotate(45)"/><circle r="16" fill="transparent"/>
      </g>; })}
      {view.species.map(id => {
        const [x, y] = view.pos.get(id)!, v = values?.[id], m = maxima?.[id] || 0, level = v !== undefined && m > 0 ? Math.max(0, Math.min(1, v / m)) : 0.35;
        const r = 9 + level * 13, on = hot.has(id);
        return <g key={id} transform={`translate(${x} ${y})`} className={'mc-sp' + (on ? ' on' : '')}>
          <circle r={r + 6} className="mc-sp-halo" style={{opacity: 0.12 + level * 0.35}}/>
          <circle r={r} style={{fill: `rgb(${Math.round(30 + 27 * level)}, ${Math.round(70 + 65 * level)}, ${Math.round(140 + 89 * level)})`}}/>
          <circle r={r} fill="url(#mc-node)"/>
          <text y={r + 13} textAnchor="middle">{id.length > 14 ? id.slice(0, 13) + '…' : id}</text>
          <title>{(names.get(id) ?? id) + (v !== undefined ? ' · ' + fmt(v, 4) : '')}</title>
        </g>;
      })}
    </svg>
    {focus && <div className="mc-network-card"><strong>{focus.name}</strong><span className="mono">{focus.scheme}</span><span className="mono mc-rate">v = {focus.rate}</span></div>}
    {(view.compact || view.hidden > 0) && <p className="mc-network-note">{view.compact ? `${model.reactions.length} reactions: showing species connectivity only.` : ''} {view.hidden > 0 ? `${view.hidden} least-connected species hidden.` : ''}</p>}
  </div>;
}

export interface GraphData {nodes: {id: string; kind: string; label: string; detail?: string; url?: string; executable?: boolean; source: string}[]; edges: {from: string; to: string; relation: string; evidence: string; source: string}[]}

/** Radial knowledge graph: protein at the centre, Reactome pathways left, published models right. */
export function KnowledgeGraph({graph, onModel}: {graph: GraphData; onModel: (id: string) => void}) {
  const [hover, setHover] = useState<string | null>(null);
  const centre = graph.nodes.find(n => n.kind === 'protein')!;
  const pathways = graph.nodes.filter(n => n.kind === 'pathway'), models = graph.nodes.filter(n => n.kind === 'model'), pubs = graph.nodes.filter(n => n.kind === 'publication');
  const pos = new Map<string, [number, number]>([[centre.id, [W / 2, H / 2]]]);
  pathways.forEach((n, i) => { const a = Math.PI * (0.62 + 0.76 * (i + 0.5) / pathways.length); pos.set(n.id, [W / 2 + Math.cos(a) * 250, H / 2 + Math.sin(a) * 230]); });
  models.forEach((n, i) => { const a = Math.PI * (-0.32 + 0.64 * (i + 0.5) / Math.max(models.length, 1)); pos.set(n.id, [W / 2 + Math.cos(a) * 210, H / 2 + Math.sin(a) * 200]); });
  pubs.forEach(n => { const e = graph.edges.find(e => e.to === n.id); const [mx, my] = pos.get(e!.from)!; pos.set(n.id, [W / 2 + (mx - W / 2) * 1.55, H / 2 + (my - H / 2) * 1.32]); });
  const hoverEdge = graph.edges.find(e => e.to === hover);
  return <div className="mc-network">
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Knowledge graph">
      {graph.edges.map((e, i) => { const [x1, y1] = pos.get(e.from)!, [x2, y2] = pos.get(e.to)!; return <path key={i} d={`M${x1} ${y1} Q${(x1 + x2) / 2} ${(y1 + y2) / 2 - 20} ${x2} ${y2}`} className={'mc-kedge ' + (e.evidence.includes('unverified') ? 'weak' : '') + (hover === e.to ? ' on' : '')}/>; })}
      {graph.nodes.map(n => { const [x, y] = pos.get(n.id)!; const r = n.kind === 'protein' ? 26 : n.kind === 'model' ? 12 : n.kind === 'pathway' ? 7 : 5;
        return <g key={n.id} transform={`translate(${x} ${y})`} className={'mc-k ' + n.kind + (n.executable === false ? ' blocked' : '')} onPointerEnter={() => setHover(n.id)} onPointerLeave={() => setHover(null)} onClick={() => n.kind === 'model' && onModel(n.id.split(':')[1])}>
          <circle r={r + 8} fill="transparent"/><circle r={r}/>
          <text x={n.kind === 'pathway' ? -12 : n.kind === 'protein' ? 0 : 16} y={n.kind === 'protein' ? 5 : 4} textAnchor={n.kind === 'pathway' ? 'end' : n.kind === 'protein' ? 'middle' : 'start'}>{n.label.length > 42 ? n.label.slice(0, 40) + '…' : n.label}</text>
        </g>; })}
    </svg>
    {hover && <div className="mc-network-card">{(() => { const n = graph.nodes.find(n => n.id === hover)!; return <><span className="eyebrow">{n.kind} · {n.source}</span><strong>{n.label}</strong>{n.detail && <span>{n.detail}</span>}{hoverEdge && <span className="caption">{hoverEdge.relation} · evidence: {hoverEdge.evidence}</span>}{n.kind === 'model' && <span className="caption">{n.executable ? 'Executable here — click to load' : 'Not executable here'}</span>}</>; })()}</div>}
    <div className="mc-legend mc-klegend"><span><i className="k-protein"/>Protein · UniProt</span><span><i className="k-pathway"/>Pathway · Reactome</span><span><i className="k-model"/>Model · BioModels</span><span><i className="k-pub"/>Publication</span><span><i className="k-weak"/>Dashed: keyword match, unverified</span></div>
  </div>;
}
