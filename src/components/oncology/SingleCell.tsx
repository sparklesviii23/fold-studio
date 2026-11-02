import {useEffect, useMemo, useRef, useState} from 'react';
import {Check, CircleHelp, Download, LoaderCircle, Play, TriangleAlert} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';
import {Volcano} from './OncologyUniverse';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');
const sci = (v: number) => v == null || !Number.isFinite(v) ? '—' : v < 1e-3 ? v.toExponential(1) : fmt(v, 2);
const PAL = ['#ff8a6b', '#5fd4ff', '#c6a7ff', '#7ee0a1', '#ffd166', '#f5b6c8', '#8fa8ff', '#e8ecf4', '#ff6b6b', '#4fd1c5', '#b794f4', '#f6ad55', '#68d391', '#fc8181', '#90cdf4', '#d6bcfa'];

/** The computed UMAP (a visual summary of the neighbour graph, not a physical or causal space), coloured by a label or a gene. */
function Umap({emb, by}: {emb: any; by: string}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const cats = useMemo(() => by.startsWith('expr_') ? [] : [...new Set<string>(emb[by])].sort(), [emb, by]);
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight; cv.width = W * dpr; cv.height = H * dpr;
    const g = cv.getContext('2d')!; g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    const xs: number[] = emb.x, ys: number[] = emb.y; let [x0, x1, y0, y1] = [Infinity, -Infinity, Infinity, -Infinity];
    xs.forEach((x, i) => { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, ys[i]); y1 = Math.max(y1, ys[i]); });
    const X = (x: number) => 16 + (x - x0) / (x1 - x0) * (W - 32), Y = (y: number) => H - 16 - (y - y0) / (y1 - y0) * (H - 32);
    const vals: any[] = emb[by]; const vmax = by.startsWith('expr_') ? Math.max(...vals, 1e-9) : 0;
    const order = by.startsWith('expr_') ? xs.map((_, i) => i).sort((a, b) => vals[a] - vals[b]) : xs.map((_, i) => i);
    for (const i of order) {
      g.fillStyle = by.startsWith('expr_') ? (vals[i] > 0 ? `rgba(255,${Math.round(220 - 140 * vals[i] / vmax)},${Math.round(120 - 80 * vals[i] / vmax)},${0.35 + 0.6 * vals[i] / vmax})` : 'rgba(150,165,200,.12)') : PAL[cats.indexOf(vals[i]) % PAL.length];
      g.globalAlpha = by.startsWith('expr_') ? 1 : 0.7; g.beginPath(); g.arc(X(xs[i]), Y(ys[i]), 1.6, 0, Math.PI * 2); g.fill();
    }
    g.globalAlpha = 1;
  }, [emb, by, cats]);
  return <div><canvas ref={ref} className="onc-umap" aria-label={`UMAP coloured by ${by}`}/>
    {!by.startsWith('expr_') && cats.length <= 16 && <div className="tme-legend onc-legend">{cats.map((c, i) => <span key={c}><i style={{background: PAL[i % PAL.length]}}/>{c}</span>)}</div>}</div>;
}

export default function SingleCell({projectId}: {projectId: string}) {
  const [st, setSt] = useState<any>(null), [res, setRes] = useState<any>(null), [by, setBy] = useState('condition'), [site, setSite] = useState(true), [busy, setBusy] = useState(''), [error, setError] = useState('');
  async function read() { try { const s = await rpc<any>('onc_sc_status', {projectId}); setSt(s); return s; } catch (e) { setError(err(e)); } }
  async function open(key: string) { setBusy('Loading result'); setError(''); try { setRes(await rpc('onc_sc_result', {projectId, key})); } catch (e) { setError(err(e)); } finally { setBusy(''); } }
  useEffect(() => { void read().then(s => { if (s?.results?.[0]) void open(s.results[0]); }); }, []);
  useEffect(() => { if (!st?.job?.running && !st?.download?.running) return; const t = setTimeout(async () => { const s = await read(); if (s && !s.job?.running && st?.job?.running && s.results?.[0]) void open(s.results[0]); }, 4000); return () => clearTimeout(t); }, [st]);
  const cur = st?.curated?.[0];
  return <>
    <div className="page-heading"><div><span className="eyebrow">DEMO D · SINGLE-CELL TUMOR ATLAS · CZ CELLxGENE</span><h1>Cell by cell, <em>donor by donor.</em></h1>
      <p>A public tumor single-cell dataset: quality control, cell states, annotation review and tumor-versus-normal comparison with donors as replicates. Scanpy runs in its own runtime on this Mac.</p></div></div>
    {error && <p className="caption cs-error">{error}</p>}{busy && <p className="caption"><LoaderCircle size={12} className="spin"/> {busy}…</p>}
    {st && <section className="quiet-panel">
      <h3>{cur?.title}</h3>
      <p className="caption">{st.manifest ? <>{st.manifest.citation?.split(' Dataset Version')[0]} · SHA-256 {st.manifest.sha256.slice(0, 12)}… (recorded; CELLxGENE publishes none) · {st.manifest.licence}</> : 'Not downloaded.'} Expected biology: {cur?.expected}.</p>
      <div className="onc-row">
        {!st.installed && <button className="button primary" disabled={st.download?.running} onClick={async () => { try { setSt(await rpc('onc_sc_install', {projectId})); } catch (e) { setError(err(e)); } }}><Download size={14}/>Download dataset (≈ 93 MB)</button>}
        {st.installed && <><label className="tme-approve"><input type="checkbox" checked={site} onChange={e => setSite(e.target.checked)}/>Controls from the same body site (face) — all BCC samples are facial</label>
          <button className="button primary" disabled={!st.runtimeReady || st.job?.running} onClick={async () => { try { setSt(await rpc('onc_sc_run', {projectId, site: site ? 'face' : ''})); } catch (e) { setError(err(e)); } }}><Play size={14}/>Run analysis (≈ 2 min)</button></>}
        <span className="onc-evidence">{st.runtimeReady ? 'Scanpy runtime ready' : 'Scanpy runtime missing'}</span></div>
      {(st.job?.running || st.download?.running) && <pre className="gt-log gt-console onc-log">{(st.job ?? st.download).log}</pre>}
      {st.results.length > 1 && <div className="onc-row">{st.results.map((k: string) => <button key={k} className="gt-view" onClick={() => open(k)}>result {k}</button>)}</div>}
    </section>}
    {res && <>
      <section className="onc-two">
        <div className="quiet-panel"><span className="eyebrow">Cell states · Harmony-integrated UMAP</span>
          <div className="onc-row">{[['condition', 'tumor vs normal'], ['cellType', 'author cell type'], ['leiden', 'Leiden cluster'], ['donor', 'donor'], ...['GLI1', 'PTCH1', 'HHIP', 'KRT14', 'MKI67'].filter(g => res.embedding['expr_' + g]).map(g => ['expr_' + g, g])].map(([k, l]) => <button key={k} className={'gt-view ' + (by === k ? 'selected' : '')} onClick={() => setBy(k)}>{l}</button>)}</div>
          <Umap emb={res.embedding} by={by}/>
          <p className="caption">{res.embedding.x.length.toLocaleString()} of {res.cells.afterQC.toLocaleString()} cells shown (seeded sample). {res.methods.embedding}. UMAP distances are not physical or causal distances.</p></div>
        <div className="quiet-panel"><span className="eyebrow">Quality, batch and annotation</span>
          <ul className="tme-checks">
            <li><Check size={14} className="ok"/><div><strong>QC: {res.cells.loaded.toLocaleString()} → {res.cells.afterQC.toLocaleString()} cells</strong><span>{res.qcMethod}. Removed per donor: up to {Math.max(...res.qc.map((q: any) => q.removed))} cells.</span></div></li>
            <li>{res.batch.afterHarmony.clustersOver80pctOneDonor === 0 ? <Check size={14} className="ok"/> : <TriangleAlert size={14} className="bad"/>}<div><strong>Donor batch: {res.batch.beforeHarmony.clustersOver80pctOneDonor} → {res.batch.afterHarmony.clustersOver80pctOneDonor} single-donor clusters</strong>
              <span>Median donor dominance {fmt(res.batch.beforeHarmony.median * 100, 2)} % → {fmt(res.batch.afterHarmony.median * 100, 2)} % with Harmony. {res.batch.note}</span></div></li>
            <li><CircleHelp size={14}/><div><strong>Annotation review: ARI {fmt(res.annotation.ari, 2)} vs author cell types</strong><span>Low agreement: unsupervised clusters capture states (e.g. tumor vs normal) the ontology labels do not encode. {res.annotation.note}</span></div></li>
          </ul>
          <table className="tme-table"><thead><tr><th>Author cell type</th><th>Top exploratory markers</th></tr></thead>
            <tbody>{Object.entries(res.annotation.markers).map(([k, v]: any) => <tr key={k}><td>{k}</td><td>{v.slice(0, 6).join(', ')}</td></tr>)}</tbody></table></div>
      </section>
      <section className="quiet-panel"><span className="eyebrow">Tumor vs normal · {res.contrast.cellType} · donors as replicates</span>
        <div className="onc-callout"><strong>{res.significantNaiveCellLevel.toLocaleString()}</strong> genes look “significant” if each cell is treated as a replicate · <strong>{res.significantDonorLevel}</strong> with donors as replicates (Welch) · <strong>{res.significantModerated}</strong> with moderated t. Cells from one person are not independent samples.</div>
        <p className="caption">{res.contrast.caseDonors.length} {res.contrast.case} donors vs {res.contrast.controlDonors.length} {res.contrast.control} donors{res.contrast.siteRestriction ? ` (${res.contrast.siteRestriction} only)` : ' (all sites — body site confounded with diagnosis)'}; {res.contrast.genesTested.toLocaleString()} genes tested. {res.methods.pseudobulk}.</p>
        <ul className="tme-checks">{res.controls.map((c: any) => <li key={c.gene}>{c.passed ? <Check size={14} className="ok"/> : c.passedModerated ? <CircleHelp size={14}/> : <TriangleAlert size={14} className="bad"/>}<div><strong>{c.gene}: log2 fold change {fmt(c.log2FC, 3)} (95 % CI {fmt(c.ci[0], 2)} to {fmt(c.ci[1], 2)})</strong>
          <span>Welch q = {sci(c.q)} {c.passed ? '(significant)' : '(not significant)'} · moderated q = {sci(c.qModerated)} {c.passedModerated ? '(significant)' : '(not significant)'}. Expected up in BCC (Hedgehog target).</span></div></li>)}
          {res.hedgehog && <li>{res.hedgehog.q < 0.05 && res.hedgehog.direction === 'up in case' ? <Check size={14} className="ok"/> : <TriangleAlert size={14} className="bad"/>}<div><strong>Hallmark Hedgehog signalling {res.hedgehog.direction}</strong><span>{res.hedgehog.genes} genes, mean t {fmt(res.hedgehog.meanT, 2)}, q = {sci(res.hedgehog.q)}.</span></div></li>}</ul>
        <p className="caption">{res.methods.moderated}.</p>
        <div className="onc-two"><div><Volcano points={res.volcano} xLabel="log2 fold change, tumor vs normal (donor pseudobulk)" highlight={['GLI1', 'PTCH1', 'HHIP']}/></div>
          <div><table className="tme-table"><thead><tr><th>Gene</th><th>log2FC</th><th>95 % CI</th><th>Welch q</th><th>Moderated q</th></tr></thead>
            <tbody>{res.de.slice(0, 18).map((d: any) => <tr key={d.gene}><td>{d.gene}</td><td>{fmt(d.log2FC, 3)}</td><td>{fmt(d.ci[0], 2)} to {fmt(d.ci[1], 2)}</td><td>{sci(d.q)}</td><td>{sci(d.qModerated)}</td></tr>)}</tbody></table></div></div>
      </section>
      <section className="quiet-panel"><span className="eyebrow">Hallmark pathways</span>
        <table className="tme-table"><thead><tr><th>Gene set</th><th>Direction</th><th>Genes</th><th>Mean t</th><th>q</th></tr></thead>
          <tbody>{res.pathways.slice(0, 15).map((p: any) => <tr key={p.set} className={p.set === 'HALLMARK_HEDGEHOG_SIGNALING' ? 'best' : ''}><td>{p.set.replace('HALLMARK_', '').replace(/_/g, ' ').toLowerCase()}</td><td>{p.direction}</td><td>{p.genes}</td><td>{fmt(p.meanT, 2)}</td><td>{sci(p.q)}</td></tr>)}</tbody></table>
        <p className="caption">{res.methods.pathways}. Competitive tests rank sets against other genes; they do not show a pathway is causally active. Scanpy {res.software.scanpy} · AnnData {res.software.anndata} · {res.seconds} s.</p></section>
    </>}
  </>;
}
