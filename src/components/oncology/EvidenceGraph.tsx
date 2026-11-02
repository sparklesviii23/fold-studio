import {useEffect, useMemo, useRef, useState} from 'react';
import {Check, LoaderCircle, RefreshCw, TriangleAlert} from 'lucide-react';
import {rpc} from '../../lib/api';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');
const TYPE: Record<string, string> = {gene: '#ffffff', protein: '#e8ecf4', disease: '#ff6b6b', pathway: '#8fa8ff', interactor: '#5fd4ff', drug: '#ffd166', variant: '#ff8a6b', dataset: '#7ee0a1', publication: '#c6a7ff', model: '#4fd1c5', unavailable: '#6b7280'};
const ORIGIN: Record<string, {color: string; dash: string}> = {experimental: {color: '#7ee0a1', dash: ''}, curated: {color: '#8fa8ff', dash: ''}, computed: {color: '#ffd166', dash: '6 3'}, 'text-mined': {color: '#c6a7ff', dash: '2 4'}, predicted: {color: '#6b7280', dash: '1 5'}};

/** A small force layout (repulsion, springs, centring) computed once per graph; positions carry no meaning beyond readability. */
function layout(nodes: any[], edges: any[]) {
  const idx = new Map(nodes.map((n, i) => [n.id, i])); const P = nodes.map((n, i) => ({x: Math.cos(i * 2.4) * (80 + i * 4), y: Math.sin(i * 2.4) * (80 + i * 4), vx: 0, vy: 0, fixed: n.type === 'gene'}));
  P.forEach((p, i) => { if (nodes[i].type === 'gene') { p.x = 0; p.y = 0; } });
  const E = edges.map(e => [idx.get(e.source), idx.get(e.target)]).filter(([a, b]) => a != null && b != null) as [number, number][];
  for (let it = 0; it < 400; it++) {
    for (let i = 0; i < P.length; i++) for (let j = i + 1; j < P.length; j++) { const dx = P[i].x - P[j].x, dy = P[i].y - P[j].y, d2 = dx * dx + dy * dy + 0.01, f = 2600 / d2; P[i].vx += dx * f / Math.sqrt(d2); P[i].vy += dy * f / Math.sqrt(d2); P[j].vx -= dx * f / Math.sqrt(d2); P[j].vy -= dy * f / Math.sqrt(d2); }
    for (const [a, b] of E) { const dx = P[b].x - P[a].x, dy = P[b].y - P[a].y, d = Math.sqrt(dx * dx + dy * dy) + 0.01, f = (d - 110) * 0.02; P[a].vx += dx / d * f; P[a].vy += dy / d * f; P[b].vx -= dx / d * f; P[b].vy -= dy / d * f; }
    for (const p of P) { p.vx -= p.x * 0.004; p.vy -= p.y * 0.004; if (!p.fixed) { p.x += p.vx * 0.5; p.y += p.vy * 0.5; } p.vx *= 0.6; p.vy *= 0.6; }
  }
  return {pos: P, idx};
}

export default function EvidenceGraph({projectId}: {projectId: string}) {
  const [g, setG] = useState<any>(null), [show, setShow] = useState<Record<string, boolean>>({experimental: true, curated: true, computed: true, 'text-mined': true, predicted: true});
  const [sel, setSel] = useState<{kind: 'node' | 'edge'; item: any} | null>(null), [busy, setBusy] = useState(''), [error, setError] = useState(''), [gene, setGene] = useState('KRAS');
  async function load(rebuild = false, gn = gene) { setBusy(rebuild ? 'Querying UniProt, Reactome, STRING, Open Targets, CIViC, Europe PMC, BioModels and the local labs' : 'Loading evidence graph'); setError(''); setSel(null);
    try { setG(await rpc(rebuild ? 'onc_graph_build' : 'onc_graph', {projectId, gene: gn})); } catch (e) { setError(err(e)); } finally { setBusy(''); } }
  useEffect(() => { void load(); }, []);
  const lay = useMemo(() => g ? layout(g.nodes, g.edges) : null, [g]);
  const edges = useMemo(() => g ? g.edges.filter((e: any) => show[e.origin]) : [], [g, show]);
  const box = useMemo(() => { if (!lay) return '0 0 1 1'; const xs = lay.pos.map(p => p.x), ys = lay.pos.map(p => p.y); return `${Math.min(...xs) - 90} ${Math.min(...ys) - 40} ${Math.max(...xs) - Math.min(...xs) + 180} ${Math.max(...ys) - Math.min(...ys) + 80}`; }, [lay]);
  const near = sel?.kind === 'node' ? new Set(edges.filter((e: any) => e.source === sel.item.id || e.target === sel.item.id).flatMap((e: any) => [e.source, e.target])) : null;
  const label = (id: string) => g?.nodes.find((n: any) => n.id === id)?.label ?? id;
  return <>
    <div className="page-heading"><div><span className="eyebrow">DEMO K · CANCER EVIDENCE GRAPH · {gene} IN {(g?.available?.[gene] ?? 'lung adenocarcinoma').toUpperCase()}</span><h1>Every link, <em>with its receipt.</em></h1>
      <p>Curated databases, measured datasets, this app's own computations and the literature around one cancer feature. Click any node or edge to see where it comes from and what kind of evidence it is.</p></div></div>
    {g?.available && <div className="onc-row">{Object.entries(g.available).map(([k, d]: any) => <button key={k} className={'gt-view ' + (gene === k ? 'selected' : '')} onClick={() => { setGene(k); void load(false, k); }}>{k} · {d}{g.cached?.includes(k) ? '' : ' (not built yet)'}</button>)}</div>}
    {error && <p className="caption cs-error">{error}</p>}{busy && <p className="caption"><LoaderCircle size={12} className="spin"/> {busy}…</p>}
    {g && lay && <>
      <section className="tme-stage">
        <div className="tme-view">
          <svg viewBox={box} className="onc-graph" role="img" aria-label="Evidence graph" onClick={() => setSel(null)}>
            {edges.map((e: any, i: number) => { const a = lay.pos[lay.idx.get(e.source)!], b = lay.pos[lay.idx.get(e.target)!]; if (!a || !b) return null; const o = ORIGIN[e.origin];
              const dim = near && !(near.has(e.source) && near.has(e.target) && (e.source === sel!.item.id || e.target === sel!.item.id));
              return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={o.color} strokeDasharray={o.dash} strokeWidth={sel?.item === e ? 3.5 : 1.6} opacity={dim ? 0.12 : 0.75} className="onc-edge" onClick={ev => { ev.stopPropagation(); setSel({kind: 'edge', item: e}); }}/>; })}
            {g.nodes.map((n: any, i: number) => { const p = lay.pos[i], dim = near && !near.has(n.id) && sel?.item.id !== n.id;
              return <g key={n.id} transform={`translate(${p.x},${p.y})`} className="onc-node" opacity={dim ? 0.25 : 1} onClick={ev => { ev.stopPropagation(); setSel({kind: 'node', item: n}); }}>
                <circle r={n.type === 'gene' ? 16 : n.type === 'disease' ? 12 : 7} fill={TYPE[n.type] ?? '#fff'} stroke={sel?.item.id === n.id ? '#fff' : 'rgba(0,0,0,.4)'} strokeWidth={sel?.item.id === n.id ? 3 : 1}/>
                <text x={n.type === 'gene' ? 20 : 10} y={4}>{n.label.length > 34 ? n.label.slice(0, 32) + '…' : n.label}</text></g>; })}
          </svg>
          <span className="tme-badge">{g.nodes.length} nodes · {g.edges.length} edges · {Object.values(g.sources).filter((v: any) => v.ok).length}/{Object.keys(g.sources).length} sources answered</span>
        </div>
        <div className="tme-side">
          <span className="eyebrow">Evidence origin</span>
          <div className="onc-origins">{Object.entries(ORIGIN).map(([k, o]) => <label key={k}><input type="checkbox" checked={show[k]} onChange={e => setShow({...show, [k]: e.target.checked})}/><svg width={26} height={8}><line x1={0} x2={26} y1={4} y2={4} stroke={o.color} strokeWidth={2.5} strokeDasharray={o.dash}/></svg>{k}<small>{g.edges.filter((e: any) => e.origin === k).length} · {g.origins[k]}</small></label>)}</div>
          <div className="tme-legend onc-legend">{Object.entries(TYPE).filter(([k]) => g.nodes.some((n: any) => n.type === k)).map(([k, c]) => <span key={k}><i style={{background: c}}/>{k}</span>)}</div>
          <div className="onc-inspector">{!sel ? <p className="caption">Select a node or an edge.</p> : sel.kind === 'edge' ? <>
            <h3>{label(sel.item.source)} → {label(sel.item.target)}</h3>
            <dl>{[['relation', sel.item.relation], ['evidence origin', sel.item.origin], ['strength', sel.item.strength], ['source', sel.item.database], ['context', sel.item.context], ['species', sel.item.species], ['citation', sel.item.citation], ['direction', sel.item.direction], ['note', sel.item.note]].filter(([, v]) => v != null && v !== '').map(([k, v]) => <><dt key={k}>{k}</dt><dd key={k + 'v'}>{String(v)}</dd></>)}
              {sel.item.channels && <><dt>STRING channels</dt><dd>{Object.entries(sel.item.channels).map(([k, v]: any) => `${k} ${v}`).join(' · ')}</dd></>}
              {sel.item.datatypes && <><dt>Open Targets evidence types</dt><dd>{Object.entries(sel.item.datatypes).map(([k, v]: any) => `${k.replace('_', ' ')} ${v.toFixed(2)}`).join(' · ')}</dd></>}</dl></> : <>
            <h3>{sel.item.label}</h3><p className="caption">{sel.item.type}{sel.item.function ? ' · ' + sel.item.function : ''}{sel.item.preprint ? ' · preprint (not peer reviewed)' : ''}{sel.item.cited != null ? ` · cited ${sel.item.cited}×` : ''}</p>
            <ul className="onc-links">{edges.filter((e: any) => e.source === sel.item.id || e.target === sel.item.id).map((e: any, i: number) => <li key={i} onClick={() => setSel({kind: 'edge', item: e})}><i style={{background: ORIGIN[e.origin].color}}/>{e.relation} {e.source === sel.item.id ? '→ ' + label(e.target) : '← ' + label(e.source)}<small>{e.origin} · {e.database}</small></li>)}</ul></>}</div>
        </div>
      </section>
      <section className="onc-two">
        <div className="quiet-panel"><span className="eyebrow">Trace · from observation to clinic</span>
          <ol className="onc-trace">{g.trace.map((t: any) => <li key={t.step}><strong>{t.step}</strong><em>{t.category}</em><span>{t.claim}</span></li>)}</ol>
          <p className="caption">Each step is a different kind of evidence; none is inferred from the one before it.</p></div>
        <div className="quiet-panel"><span className="eyebrow">What this evidence does not show</span>
          <ul className="tme-checks">{g.gaps.map((x: string) => <li key={x}><TriangleAlert size={14}/><div><span>{x}</span></div></li>)}</ul></div>
      </section>
      <section className="quiet-panel"><span className="eyebrow">Sources queried · {g.built.replace('T', ' ').slice(0, 16)} UTC</span>
        <table className="tme-table"><thead><tr><th/><th>Source</th><th>Retrieved</th><th>SHA-256 of response</th></tr></thead>
          <tbody>{Object.entries(g.sources).map(([k, v]: any) => <tr key={k}><td>{v.ok ? <Check size={13} className="ok"/> : <TriangleAlert size={13} className="bad"/>}</td><td title={v.url}>{k.replace(/_/g, ' ')}</td><td>{v.retrieved?.slice(0, 16) ?? v.error}</td><td>{v.sha256?.slice(0, 16) ?? '—'}</td></tr>)}</tbody></table>
        <div className="onc-row"><button className="button" onClick={() => load(true)}><RefreshCw size={14}/>Rebuild from live sources</button><span className="caption">Literature: {g.literature.total?.toLocaleString()} records for {g.literature.query}, {g.literature.preprints} preprints.</span></div></section>
    </>}
  </>;
}
