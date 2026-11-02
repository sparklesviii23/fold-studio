import {Fragment, useEffect, useMemo, useRef, useState} from 'react';
import {Check, Download, LoaderCircle, Play, Trash2, TriangleAlert} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');
const ANNOT: Record<string, string> = {'Tumor cells': '#ff6b6b', 'Tumor stroma with inflammation': '#5fd4ff', 'Tumor stroma fibrous': '#c6a7ff', 'Adipose tissue': '#ffd166', 'Artifacts': '#6b7280', unannotated: 'rgba(200,210,230,.25)', unknown: 'rgba(200,210,230,.25)'};
const HUES = ['#ff6b6b', '#5fd4ff', '#c6a7ff', '#ffd166', '#7ee0a1', '#ff8a6b', '#8fa8ff', '#f78fb3', '#4fd1c5', '#e8c07d', '#b0e57c', '#9aa5ff', '#ffb3c6', '#6ec6ff', '#d4a5ff', '#ffe08a'];
const colourOf = (labels: string[]) => { const m: Record<string, string> = {}; [...new Set(labels)].sort().forEach((l, i) => { m[l] = ANNOT[l] ?? HUES[i % HUES.length]; }); return m; };

type Layer = {kind: 'annot'; name: string} | {kind: 'score'; name: string} | {kind: 'expr'; name: string};

/** The measured image (when deposited) with every spot or bead drawn at its measured position. */
function Section({r, layer, opacity, palette}: {r: any; layer: Layer; opacity: number; palette: Record<string, string>}) {
  const ref = useRef<HTMLCanvasElement>(null), img = useMemo(() => { if (!r.image.png) return null; const i = new Image(); i.src = 'data:image/png;base64,' + r.image.png; return i; }, [r]);
  const [zoom, setZoom] = useState(1), [pan, setPan] = useState<[number, number]>([0, 0]), drag = useRef<[number, number] | null>(null);
  const values: number[] | null = layer.kind === 'score' ? r.scores[layer.name] : layer.kind === 'expr' ? r.expression[layer.name] : null;
  // Colour scale tops out at the 99th percentile so a few extreme spots do not wash out the rest.
  const vmax = useMemo(() => { if (!values) return 1; const s = [...values].sort((a, b) => a - b); return Math.max(s[Math.floor(0.99 * (s.length - 1))], 1e-9); }, [values]);
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const draw = () => {
      const dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight; cv.width = W * dpr; cv.height = H * dpr;
      const g = cv.getContext('2d')!; g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
      const s = Math.min(W / r.image.width, H / r.image.height) * zoom, ox = (W - r.image.width * s) / 2 + pan[0], oy = (H - r.image.height * s) / 2 + pan[1];
      g.globalAlpha = 1; if (img) g.drawImage(img, ox, oy, r.image.width * s, r.image.height * s);
      const rad = Math.max(1, r.spotRadiusPx * s); g.globalAlpha = opacity; const labels = layer.kind === 'annot' ? r.annotations[layer.name] : null;
      r.spotsPx.forEach((p: number[], i: number) => {
        let c: string;
        if (labels) c = palette[labels[i]] ?? '#fff';
        else { const t = Math.min(1, Math.max(0, values![i] / vmax)); c = t <= 0 ? 'rgba(30,40,80,.35)' : `rgba(${Math.round(60 + 195 * t)},${Math.round(40 + 200 * t)},${Math.round(160 - 120 * t)},${0.45 + 0.55 * t})`; }
        g.fillStyle = c; g.beginPath(); g.arc(ox + p[0] * s, oy + p[1] * s, rad, 0, Math.PI * 2); g.fill();
      });
      if (r.umPerImagePx) { const bar = 500 / r.umPerImagePx * s; g.globalAlpha = 1; g.fillStyle = '#fff'; g.fillRect(16, H - 22, bar, 3); g.font = '11px Inter, system-ui'; g.fillText('500 µm', 16, H - 28); }
    };
    if (!img || img.complete) draw(); else img.onload = draw;
  }, [r, layer, opacity, zoom, pan, img, values, vmax, palette]);
  return <canvas ref={ref} className="onc-section" aria-label="Tissue section with measured spot positions"
    onWheel={e => setZoom(z => Math.max(1, Math.min(12, z * (e.deltaY < 0 ? 1.15 : 0.87))))}
    onPointerDown={e => { drag.current = [e.clientX, e.clientY]; (e.target as HTMLElement).setPointerCapture(e.pointerId); }} onPointerUp={() => { drag.current = null; }}
    onPointerMove={e => { if (!drag.current) return; const [x, y] = drag.current; setPan(([a, b]) => [a + e.clientX - x, b + e.clientY - y]); drag.current = [e.clientX, e.clientY]; }}/>;
}

/** Sections on disk, the CELLxGENE cancer spatial catalog, and the in-silico generator. */
function Library({projectId, current, open, setError}: {projectId: string; current: string; open: (id: string) => void; setError: (e: string) => void}) {
  const [view, setView] = useState<'mine' | 'browse' | 'simulate'>('mine'), [lib, setLib] = useState<any>(null), [cat, setCat] = useState<any>(null), [q, setQ] = useState(''), [dz, setDz] = useState('');
  const [sim, setSim] = useState({phenotype: 'excluded', nests: 3, seed: 1}), [confirm, setConfirm] = useState('');
  const refresh = async () => { try { setLib(await rpc('onc_sp_library', {projectId})); } catch (e) { setError(err(e)); } };
  useEffect(() => { void refresh(); }, []);
  useEffect(() => { if (!lib?.downloading?.length) return; const t = setTimeout(() => { void refresh(); if (cat) void rpc('onc_sp_catalog', {projectId}).then(setCat); }, 4000); return () => clearTimeout(t); }, [lib]);
  useEffect(() => { if (view === 'browse' && !cat) rpc('onc_sp_catalog', {projectId}).then(setCat).catch(e => setError(err(e))); }, [view]);
  const diseases = useMemo(() => cat ? [...new Set<string>(cat.datasets.flatMap((d: any) => d.disease))].sort() : [], [cat]);
  const rows = cat ? cat.datasets.filter((d: any) => (!dz || d.disease.includes(dz)) && (!q || (d.title + ' ' + d.collection + ' ' + d.tissue.join(' ') + ' ' + d.assay).toLowerCase().includes(q.toLowerCase()))) : [];
  const download = async (id: string) => { try { await rpc('onc_sp_install', {projectId, datasetId: id}); await refresh(); setCat({...cat, datasets: cat.datasets.map((d: any) => d.id === id ? {...d, pending: true} : d)}); } catch (e) { setError(err(e)); } };
  const remove = async (id: string) => { if (confirm !== id) { setConfirm(id); return; } try { const l = await rpc<any>('onc_sp_delete', {projectId, datasetId: id}); setLib(l); setConfirm(''); if (id === current) open(l.datasets[0]?.id ?? l.curated[0].id); if (cat) setCat(await rpc('onc_sp_catalog', {projectId})); } catch (e) { setError(err(e)); } };
  const simulate = async () => { try { const s = await rpc<any>('onc_sp_simulate', {projectId, ...sim}); await refresh(); open(s.datasetId); } catch (e) { setError(err(e)); } };
  return <section className="quiet-panel">
    <div className="tme-tabs">{([['mine', `My sections${lib ? ' · ' + lib.datasets.length : ''}`], ['browse', `Browse CELLxGENE${cat ? ' · ' + cat.datasets.length : ''}`], ['simulate', 'Simulate in silico']] as const).map(([k, l]) => <button key={k} className={'gt-view ' + (view === k ? 'selected' : '')} onClick={() => setView(k)}>{l}</button>)}</div>
    {view === 'mine' && lib && <table className="tme-table"><thead><tr><th>Section</th><th>Kind</th><th>Size</th><th>Analysed</th><th/></tr></thead>
      <tbody>{lib.datasets.map((d: any) => <tr key={d.id} className={d.id === current ? 'onc-current' : ''}><td>{d.title}</td><td>{d.synthetic ? <span className="onc-evidence">Synthetic · ground truth known</span> : 'Measured (CELLxGENE)'}</td><td>{d.sizeMB} MB</td><td>{d.analysed ? 'yes' : '—'}</td>
        <td className="onc-actions"><button className="button" onClick={() => open(d.id)}>{d.id === current ? 'Open ✓' : 'Open'}</button><button className={'button ' + (confirm === d.id ? 'danger' : '')} onClick={() => remove(d.id)}><Trash2 size={13}/>{confirm === d.id ? 'Confirm delete' : 'Delete'}</button></td></tr>)}
        {lib.downloading.map((id: string) => <tr key={id}><td colSpan={5}><LoaderCircle size={12} className="spin"/> {id} downloading or analysing…</td></tr>)}
        {!lib.datasets.length && <tr><td colSpan={5}>No sections yet: download one from CELLxGENE or generate a synthetic one.</td></tr>}</tbody></table>}
    {view === 'browse' && <>{!cat ? <p className="caption"><LoaderCircle size={12} className="spin"/> Reading the CELLxGENE Discover catalog…</p> : <>
      <div className="onc-row"><input className="field" placeholder="Search title, tissue, collection…" value={q} onChange={e => setQ(e.target.value)}/>
        <select className="field" value={dz} onChange={e => setDz(e.target.value)}><option value="">All cancers</option>{diseases.map(d => <option key={d}>{d}</option>)}</select>
        <span className="caption">{rows.length} of {cat.datasets.length} human cancer spatial datasets · catalog read {cat.retrieved.slice(0, 16).replace('T', ' ')} UTC</span></div>
      <div className="onc-scroll"><table className="tme-table"><thead><tr><th>Dataset</th><th>Cancer</th><th>Tissue</th><th>Assay</th><th>Spots</th><th>Size</th><th/></tr></thead>
        <tbody>{rows.map((d: any) => <tr key={d.id}><td title={d.citation}>{d.title}<small className="onc-sub">{d.collection}</small></td><td>{d.disease.join(', ')}</td><td>{d.tissue.join(', ')}</td><td>{d.assay.replace('Spatial Gene Expression ', '')}</td><td>{d.spots?.toLocaleString()}</td><td>{d.sizeMB} MB</td>
          <td>{d.installed ? <button className="button" onClick={() => open(d.id)}>Open</button> : lib?.downloading?.includes(d.id) || d.pending ? <span className="caption"><LoaderCircle size={12} className="spin"/> downloading</span> : <button className="button" onClick={() => download(d.id)}><Download size={13}/>Download</button>}</td></tr>)}</tbody></table></div>
      <p className="caption">Every public human cancer dataset on CZ CELLxGENE Discover measured with 10x Visium or Slide-seqV2. Data are CC BY 4.0 unless the collection states otherwise; cite the original study. Large files (some &gt; 1 GB) take time.</p></>}</>}
    {view === 'simulate' && <>
      <p className="caption">Generates a Visium-like section from a stated model (tumor nests, fixed cell-type fractions, negative-binomial counts) with a planted immune pattern, then runs the same analysis and scores it against the truth. It tests the methods; it is not tumor biology.</p>
      <div className="onc-row">
        <label className="caption">Immune pattern <select className="field" value={sim.phenotype} onChange={e => setSim({...sim, phenotype: e.target.value})}><option value="infiltrated">infiltrated</option><option value="excluded">excluded (T cells at the rim)</option><option value="desert">desert (few T cells)</option></select></label>
        <label className="caption">Tumor nests <input className="field" type="number" min={1} max={8} value={sim.nests} onChange={e => setSim({...sim, nests: Number(e.target.value)})}/></label>
        <label className="caption">Seed <input className="field" type="number" min={0} value={sim.seed} onChange={e => setSim({...sim, seed: Number(e.target.value)})}/></label>
        <button className="button primary" disabled={!lib?.runtimeReady} onClick={simulate}><Play size={14}/>Generate and analyse (≈ 15 s)</button></div></>}
  </section>;
}

export default function Spatial({projectId}: {projectId: string}) {
  const [id, setId] = useState<string>(() => { try { return localStorage.getItem('onc-sp-id') || 'b0d9408e-f02f-4ee4-9ab4-98d92cf290f1'; } catch { return 'b0d9408e-f02f-4ee4-9ab4-98d92cf290f1'; } });
  const [st, setSt] = useState<any>(null), [r, setR] = useState<any>(null), [layer, setLayer] = useState<Layer | null>(null), [opacity, setOpacity] = useState(0.75), [busy, setBusy] = useState(''), [error, setError] = useState('');
  async function read(did = id) { try { const s = await rpc<any>('onc_sp_status', {projectId, datasetId: did}); setSt(s); return s; } catch (e) { setError(err(e)); } }
  async function load(did = id) { setBusy('Loading section'); try { const x = await rpc<any>('onc_sp_result', {projectId, datasetId: did}); setR(x); setError(''); setLayer({kind: 'annot', name: x.primaryAnnotation}); } catch (e) { setError(err(e)); } finally { setBusy(''); } }
  const open = (did: string) => { setId(did); setR(null); setError(''); try { localStorage.setItem('onc-sp-id', did); } catch { /* per-viewer convenience only */ } void read(did).then(s => { if (s?.result && !s.job?.running) void load(did); }); };
  useEffect(() => { open(id); }, []);
  useEffect(() => { if (!st?.job?.running && !st?.download?.running) return; const t = setTimeout(async () => { const s = await read(); if (s?.result && !s.job?.running) void load(); }, 3000); return () => clearTimeout(t); }, [st]);
  const palette = useMemo(() => r && layer?.kind === 'annot' ? colourOf(r.annotations[layer.name]) : {}, [r, layer]);
  const syn = r?.synthetic;
  const label = !layer ? '' : layer.kind === 'annot' ? `${layer.name} · ${syn ? 'planted truth' : layer.name.includes('computed') ? 'statistical clustering (not an annotation)' : /patholog/i.test(layer.name) ? 'expert observation' : 'as deposited by the authors'}`
    : layer.kind === 'score' ? `${layer.name} · ${syn ? 'planted truth' : 'author score (usually a deconvolution prediction)'}` : `${layer.name} · ${syn ? 'simulated counts' : 'measured expression'} (log-normalised)`;
  const title = st?.manifest?.title ?? id;
  return <>
    <div className="page-heading"><div><span className="eyebrow">DEMO E · SPATIAL TUMOR EXPLORER · VISIUM · SLIDE-SEQ · IN SILICO</span><h1>Where the cells <em>actually are.</em></h1>
      <p>Real tumor sections from CELLxGENE Discover, or synthetic ones with known ground truth to test the methods. Each layer says what kind of evidence it is; nothing is reconstructed in 3D.</p></div></div>
    <Library projectId={projectId} current={id} open={open} setError={setError}/>
    {error && <p className="caption cs-error">{error}</p>}{busy && <p className="caption"><LoaderCircle size={12} className="spin"/> {busy}…</p>}
    {st && <section className="quiet-panel"><h3>{title}</h3><p className="caption">{st.manifest ? (st.manifest.synthetic ? `${st.manifest.model}. Generated locally; SHA-256 ${st.manifest.sha256.slice(0, 12)}…` : `${st.manifest.citation ? st.manifest.citation.split(' Dataset Version')[0] + ' · ' : ''}SHA-256 ${st.manifest.sha256.slice(0, 12)}… recorded · ${st.manifest.licence}`) : 'Not on disk yet.'}</p>
      <div className="onc-row">
        {!st.installed && !id.startsWith('sim-') && <button className="button primary" disabled={st.download?.running} onClick={async () => { try { setSt(await rpc('onc_sp_install', {projectId, datasetId: id})); } catch (e) { setError(err(e)); } }}><Download size={14}/>Download section</button>}
        {st.installed && <button className="button" disabled={!st.runtimeReady || st.job?.running} onClick={async () => { try { setSt(await rpc('onc_sp_run', {projectId, datasetId: id})); } catch (e) { setError(err(e)); } }}><Play size={14}/>{st.result ? 'Re-run analysis' : 'Run analysis'}</button>}
        {syn && <span className="onc-evidence">Synthetic · illustrative, not an observation</span>}
      </div>{(st.job?.running || st.download?.running) && <pre className="gt-log gt-console onc-log">{(st.job ?? st.download).log}</pre>}</section>}
    {r && layer && <>
      {syn && <section className="quiet-panel"><span className="eyebrow">Scored against the planted truth · {syn.phenotype} · {syn.nests} nests · seed {syn.seed}</span>
        <ul className="tme-checks">{syn.checks.map((c: any) => <li key={c.check}>{c.passed ? <Check size={14} className="ok"/> : <TriangleAlert size={14} className="bad"/>}<div><strong>{c.check}: {c.value}</strong></div></li>)}</ul>
        <p className="caption">{syn.model}. T cells inside tumor {syn.tCellInside}; outside {syn.tCellOutside}. Planted spatial genes: {syn.spatialGenes.join(', ')}; 300 pattern-free genes (SIMNULL…) estimate false positives.</p></section>}
      <section className="tme-stage">
        <div className="tme-view"><Section r={r} layer={layer} opacity={opacity} palette={palette}/><span className="tme-badge">{label}</span><span className="tme-count">{r.spots.toLocaleString()} {r.platform.startsWith('Visium') ? 'spots' : 'beads'} · {r.platform} · scroll to zoom, drag to pan</span></div>
        <div className="tme-side">
          <span className="eyebrow">Annotations</span>
          <div className="tme-tabs">{Object.keys(r.annotations).map((k: string) => <button key={k} className={'gt-view ' + (layer.kind === 'annot' && layer.name === k ? 'selected' : '')} onClick={() => setLayer({kind: 'annot', name: k})}>{k}</button>)}</div>
          {Object.keys(r.scores).length > 0 && <><span className="eyebrow">{syn ? 'Planted fractions' : 'Author scores (usually AI deconvolution)'}</span>
            <div className="tme-tabs onc-scroll-tabs">{Object.keys(r.scores).map((t: string) => <button key={t} className={'gt-view ' + (layer.kind === 'score' && layer.name === t ? 'selected' : '')} onClick={() => setLayer({kind: 'score', name: t})}>{t.replace('q05_spot_factors', '').replace('true fraction: ', '')}</button>)}</div></>}
          <span className="eyebrow">{syn ? 'Simulated expression' : 'Measured expression'}</span>
          <div className="tme-tabs">{Object.keys(r.expression).map((g: string) => <button key={g} className={'gt-view ' + (layer.kind === 'expr' && layer.name === g ? 'selected' : '')} onClick={() => setLayer({kind: 'expr', name: g})}>{g}</button>)}</div>
          <label className="caption">Spot opacity<input type="range" min={0} max={1} step={0.05} value={opacity} onChange={e => setOpacity(Number(e.target.value))}/></label>
          {layer.kind === 'annot' && <div className="tme-legend onc-legend">{Object.entries(palette).map(([k, c]) => <span key={k}><i style={{background: c}}/>{k}</span>)}</div>}
          <p className="caption">{r.geometry} Neighbours: {r.graph}.</p>
        </div>
      </section>
      <section className="onc-two">
        <div className="quiet-panel"><span className="eyebrow">Neighbourhood enrichment · {r.neighbourhood.annotation}</span>
          <div className="onc-scroll"><div className="onc-heat-grid onc-ne" style={{gridTemplateColumns: `150px repeat(${r.neighbourhood.labels.length}, minmax(52px, 1fr))`}}>
            <i/>{r.neighbourhood.labels.map((l: string) => <b key={l}>{l.replace('Tumor stroma', 'Stroma').replace(' with inflammation', ' (inflamed)')}</b>)}
            {r.neighbourhood.z.map((row: number[], i: number) => <Fragment key={i}><b>{r.neighbourhood.labels[i]}</b>{row.map((v, j) => <em key={j} style={{background: v >= 0 ? `rgba(255,107,107,${Math.min(0.9, 0.12 + v / 60)})` : `rgba(95,157,255,${Math.min(0.9, 0.12 - v / 60)})`}}>{fmt(v, 2)}</em>)}</Fragment>)}
          </div></div><p className="caption">z-scores, {r.neighbourhood.method} ({r.neighbourhood.permutations} permutations). Red = neighbours more often than chance.</p></div>
        <div className="quiet-panel"><span className="eyebrow">Tumor–immune interface</span>
          {!r.interface ? <p className="caption">{r.umPerImagePx ? 'No annotation in this section labels tumor regions, so distance to tumor cannot be measured.' : 'Position units are not stated for this deposit, so distances in µm cannot be computed.'}</p> : <>
          <table className="tme-table"><thead><tr><th>Distance to tumor</th>{r.interface.bins.map((b: string, i: number) => <th key={b} className={r.interface.spots[i] < 20 ? 'onc-dim' : ''}>{b}</th>)}</tr></thead>
            <tbody><tr><td>spots</td>{r.interface.spots.map((n: number, i: number) => <td key={i} className={n < 20 ? 'onc-dim' : ''}>{n}</td>)}</tr>
              {Object.entries(r.interface.profiles).map(([k, v]: any) => <tr key={k}><td>{k.startsWith('expr') ? k.replace('expr ', '') + (syn ? ' (simulated)' : ' (measured)') : k.replace('true fraction: ', '') + (syn ? ' (planted)' : ' (author score)')}</td>{v.map((x: number | null, i: number) => <td key={i} className={r.interface.spots[i] < 20 ? 'onc-dim' : ''}>{x == null ? '—' : fmt(x, 2)}</td>)}</tr>)}</tbody></table>
          {r.interface.exclusion && <p className="caption">{r.interface.exclusion.readout} inside tumor {fmt(r.interface.exclusion.insideMean, 2)} vs within 300 µm {fmt(r.interface.exclusion.rimMean, 2)} (ratio {fmt(r.interface.exclusion.ratio, 2)}, p = {r.interface.exclusion.p < 1e-3 ? r.interface.exclusion.p.toExponential(1) : fmt(r.interface.exclusion.p, 2)}). Tumor = "{r.interface.annotation}" labels. Bins with &lt; 20 spots are dimmed.</p>}</>}</div>
      </section>
      <section className="onc-two">
        <div className="quiet-panel"><span className="eyebrow">Spatially patterned genes · Moran's I</span>
          <table className="tme-table"><thead><tr><th>Gene</th><th>I</th><th>q</th><th/></tr></thead>
            <tbody>{r.moran.slice(0, 14).map((m: any) => <tr key={m.gene}><td>{m.gene}</td><td>{fmt(m.I, 3)}</td><td>{m.q < 1e-3 ? m.q.toExponential(1) : fmt(m.q, 2)}</td><td>{m.technical ? 'technical (depth / mitochondrial)' : ''}</td></tr>)}</tbody></table>
          <p className="caption">{r.moranSummary.significant} of {r.moranSummary.tested} variable genes at q &lt; 0.05; p from the moments of {r.moranSummary.nullPermutations} coordinate permutations. Shuffled-coordinate median I = {fmt(r.moranSummary.medianShuffledI, 2)} (expected ≈ 0).</p></div>
        <div className="quiet-panel"><span className="eyebrow">Does prediction agree with the annotation?</span>
          {!r.agreement.length ? <p className="caption">No tumor annotation to compare against in this section.</p> :
          <ul className="tme-checks">{r.agreement.map((a: any) => <li key={a.check}>{a.passed ? <Check size={14} className="ok"/> : <TriangleAlert size={14} className="bad"/>}<div><strong>{a.check}: AUC {fmt(a.auc, 2)}</strong><span>{a.passed ? 'meets' : 'below'} the pre-set 0.8 bar. Spots mix several cells and annotations are drawn over regions, so moderate agreement is expected.</span></div></li>)}</ul>}</div>
      </section>
    </>}
  </>;
}
