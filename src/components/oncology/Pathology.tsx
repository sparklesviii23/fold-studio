import {useEffect, useMemo, useState} from 'react';
import {Download, LoaderCircle, Play, TriangleAlert} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');

function Density({g}: {g: number[][]}) {
  const top = Math.max(1, ...g.flat()), n = g.length, c = 200 / n;
  return <svg viewBox="0 0 200 200" className="onc-density" role="img" aria-label="Nucleus density">{g.map((row, i) => row.map((v, j) => <rect key={i + '-' + j} x={j * c} y={i * c} width={c} height={c} style={{fill: `rgba(198,167,255,${v / top})`}}/>))}</svg>;
}

function Morph({pts, label}: {pts: number[][]; label: string}) {
  const W = 320, H = 200, xmax = Math.max(...pts.map(p => p[0]), 1), X = (v: number) => 34 + Math.sqrt(v / xmax) * (W - 44), Y = (v: number) => H - 26 - Math.min(v, 1.2) / 1.2 * (H - 36);
  return <svg viewBox={`0 0 ${W} ${H}`} className="onc-scatter" role="img" aria-label={label}>{pts.map((p, i) => <circle key={i} cx={X(p[0])} cy={Y(p[1])} r={1.4}/>)}
    <text x={W / 2} y={H - 6} textAnchor="middle">nucleus area (px, √ scale)</text><text x={10} y={H / 2} transform={`rotate(-90 10 ${H / 2})`} textAnchor="middle">circularity</text></svg>;
}

/** Demo I: classical nucleus segmentation on an openly licensed H&E dataset, scored against its expert annotations. */
export default function Pathology({projectId}: {projectId: string}) {
  const [st, setSt] = useState<any>(null), [res, setRes] = useState<any>(null), [pick, setPick] = useState(''), [error, setError] = useState('');
  const read = async () => { try { const s = await rpc<any>('onc_path_status', {projectId}); setSt(s); if (s.done && !s.job?.running && !res) setRes(await rpc('onc_path_result', {projectId})); return s; } catch (e) { setError(err(e)); } };
  useEffect(() => { void read(); }, []);
  useEffect(() => { if (!st?.job?.running && !st?.download?.running) return; const t = setTimeout(async () => { const s = await read(); if (s?.done && !s.job?.running) setRes(await rpc('onc_path_result', {projectId})); }, 3000); return () => clearTimeout(t); }, [st]);
  const keys = useMemo(() => res ? Object.keys(res.overlays) : [], [res]); const cur = pick || keys.find(k => k.startsWith('human melanoma')) || keys[0];
  const act = async (a: string) => { setError(''); try { setSt(await rpc(a, {projectId})); } catch (e) { setError(err(e)); } };
  return <>
    <div className="page-heading"><div><span className="eyebrow">DEMO I · PATHOLOGY ANALYSIS · NuInsSeg (CC BY 4.0)</span><h1>Nuclei found by the computer, <em>checked against the pathologists.</em></h1>
      <p>665 H&amp;E images from 31 human and mouse tissues, including melanoma, with expert outlines of every nucleus. The app tiles each image, separates the hematoxylin stain, segments nuclei, measures their shape and checks image quality, then scores itself against the experts. Regions the annotators marked as ambiguous are left out of the score.</p></div></div>
    <section className="quiet-panel"><div className="onc-row">
      {!st?.installed && <button className="button primary" disabled={st?.download?.running} onClick={() => act('onc_path_install')}><Download size={14}/>Download NuInsSeg (≈ 1.6 GB, MD5-verified)</button>}
      {st?.installed && <button className="button primary" disabled={st?.job?.running} onClick={() => act('onc_path_run')}><Play size={14}/>{res ? 'Analyse again' : 'Analyse all 665 images'} (≈ 5–10 min)</button>}
      {(st?.download?.running || st?.job?.running) && <span className="caption"><LoaderCircle size={12} className="spin"/> {st.download?.running ? `downloading · ${(st.bytes / 1e9).toFixed(2)} GB` : 'analysing'}…</span>}</div>
      {error && <p className="caption cs-error">{error}</p>}
      {(st?.job?.running || st?.download?.running) && <pre className="onc-log">{(st.job?.running ? st.job : st.download).log}</pre>}</section>
    {res && <>
      <section className="quiet-panel"><span className="onc-evidence">{res.evidence}</span>
        <p>{res.images} images, {res.organs} tissues. With nucleus splitting: Dice {fmt(res.overall.watershed.dice.mean, 2)}, detection F1 {fmt(res.overall.watershed.f1.mean, 2)}, AJI {fmt(res.overall.watershed.aji.mean, 2)} (mean over images). Threshold only: AJI {fmt(res.overall.threshold.aji.mean, 2)}. Splitting changes AJI by {fmt(res.splitting.meanAjiGain, 2)} (95 % CI {fmt(res.splitting.ci[0], 2)} to {fmt(res.splitting.ci[1], 2)}), better in {res.splitting.imagesImproved} images.</p>
        {res.bySpecies && <p>By species: {Object.entries(res.bySpecies).map(([sp, v]: any) => `${sp} ${v.images} images, AJI ${fmt(v.aji.mean, 2)}, Dice ${fmt(v.dice.mean, 2)}`).join(' · ')}.</p>}
        <p className="caption">Quality checks flagged {res.qc.flagged} images ({Object.entries(res.qc.flags).map(([k, v]) => `${k}: ${v}`).join('; ') || 'none'}); their AJI {fmt(res.qc.ajiFlagged, 2)} vs {fmt(res.qc.ajiUnflagged, 2)} for the rest. {res.dataset.citation} SHA-256 {res.dataset.sha256.slice(0, 12)}….</p></section>
      <section className="onc-two">
        <div className="quiet-panel"><span className="eyebrow">Overlay · expert outlines orange, computed green</span>
          <select className="field" value={cur} onChange={e => setPick(e.target.value)}>{keys.map(k => <option key={k} value={k}>{k.replace('|', ' · ')}</option>)}</select>
          {cur && <img className="onc-overlay" src={`data:image/jpeg;base64,${res.overlays[cur]}`} alt={`Segmentation overlay for ${cur}`}/>}</div>
        <div className="quiet-panel"><span className="eyebrow">Spatial · nucleus density (16 × 16 grid)</span>{cur && res.density[cur] && <Density g={res.density[cur]}/>}
          <span className="eyebrow">Morphology · {cur?.split('|')[0]}</span>{cur && res.morphology[cur.split('|')[0]] && <Morph pts={res.morphology[cur.split('|')[0]]} label="area vs circularity"/>}</div></section>
      <section className="quiet-panel"><span className="eyebrow">Benchmark by tissue (mean over images)</span>
        <div className="onc-scroll"><table className="tme-table"><thead><tr><th>Tissue</th><th>Images</th><th>Expert nuclei</th><th>Dice</th><th>F1 (IoU ≥ 0.5)</th><th>AJI</th><th>AJI threshold only</th><th>Median area (px)</th></tr></thead>
          <tbody>{res.byOrgan.map((o: any) => <tr key={o.organ}><td>{o.organ}</td><td>{o.images}</td><td>{o.nuclei.toLocaleString()}</td><td>{fmt(o.dice, 2)}</td><td>{fmt(o.f1, 2)}</td><td>{fmt(o.aji, 2)}</td><td>{fmt(o.ajiThreshold, 2)}</td><td>{fmt(o.medianArea, 3)}</td></tr>)}</tbody></table></div>
        {res.development && <><span className="eyebrow">Method development · {res.development.design}</span>
          <table className="tme-table"><thead><tr><th>Rule</th><th>Mouse AJI (development)</th><th>Human AJI (held out)</th></tr></thead>
            <tbody>{res.development.variants.map((v: any) => <tr key={v.rule}><td>{v.rule}</td><td>{fmt(v.mouseAJI, 3)}</td><td>{fmt(v.humanAJI, 3)}</td></tr>)}</tbody></table>
          <p className="caption">{res.development.decision}</p></>}
        <ul className="tme-checks"><li><TriangleAlert size={13}/><div><span>Classical segmentation, no trained model: deep models (e.g. HoVer-Net, StarDist) typically score higher on this kind of benchmark; this baseline shows what simple, transparent image analysis achieves. Measurements are in pixels; the images' physical resolution differs by tissue, so areas are not compared across tissues as sizes.</span></div></li></ul></section>
    </>}
  </>;
}
