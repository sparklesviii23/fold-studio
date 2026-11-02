import {useEffect, useRef, useState} from 'react';
import {Download, LoaderCircle} from 'lucide-react';
import {exportFile, rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

type Layer = {png: string; displayRange: number[]; stain: string; color: string; source: string};
const DEFAULT_GAIN = 0.55;                           // four additive channels at full gain saturate to white
const hex = (c: string) => [1, 3, 5].map(i => parseInt(c.slice(i, i + 2), 16));

/** Observed Cell Painting (virtual_cell_microscopy.py): additive channel composite, contrast, zoom/pan, mask outlines,
 *  per-field morphology. Display images are percentile-scaled copies; measurements come from the raw 16-bit pixels. */
export default function CellPainting({cellId, onError}: {cellId: string; onError: (e: string) => void}) {
  const [list, setList] = useState<any>(null), [key, setKey] = useState(''), [view, setView] = useState<any>(null), [busy, setBusy] = useState(false);
  const [on, setOn] = useState<Record<string, boolean>>({DNA: true, ER: true, AGP: true, Mito: true}), [gain, setGain] = useState<Record<string, number>>({});
  const [outline, setOutline] = useState<'none' | 'nuclei' | 'cells'>('nuclei'), [opacity, setOpacity] = useState(0.7), [zoom, setZoom] = useState(1), [pan, setPan] = useState([0, 0]);
  const canvas = useRef<HTMLCanvasElement>(null), pixels = useRef<Record<string, Uint8ClampedArray>>({}), drag = useRef<number[] | null>(null);

  useEffect(() => { rpc<any>('vcell_microscopy_list', {id: cellId}).then(r => { setList(r); if (r.images?.length) setKey(r.images[0].key); }).catch(e => onError(String(e))); }, [cellId]);
  useEffect(() => {
    if (!key) return; setBusy(true); pixels.current = {};
    rpc<any>('vcell_microscopy_view', {id: cellId, key}).then(async r => {
      await Promise.all(Object.entries(r.layers as Record<string, Layer>).map(([c, l]) => new Promise<void>(done => {
        const img = new Image(); img.onload = () => { const cv = document.createElement('canvas'); cv.width = img.width; cv.height = img.height; const x = cv.getContext('2d')!; x.drawImage(img, 0, 0);
          pixels.current[c] = x.getImageData(0, 0, img.width, img.height).data; done(); }; img.src = l.png; })));
      setView(r);
    }).catch(e => onError(String(e).replace(/^Error:\s*/, ''))).finally(() => setBusy(false));
  }, [key]);
  useEffect(() => {                                        // additive composite of the enabled channels, each tinted and gain-adjusted
    if (!view || !canvas.current) return;
    const [h, w] = view.size, cv = canvas.current; cv.width = w; cv.height = h;
    const ctx = cv.getContext('2d')!, out = ctx.createImageData(w, h), d = out.data;
    for (const [c, l] of Object.entries(view.layers as Record<string, Layer>)) {
      const src = pixels.current[c]; if (!on[c] || !src) continue; const [r, g, b] = hex(l.color), k = (gain[c] ?? DEFAULT_GAIN) / 255;
      for (let i = 0; i < d.length; i += 4) { const v = src[i] * k; d[i] += r * v; d[i + 1] += g * v; d[i + 2] += b * v; }
    }
    for (let i = 3; i < d.length; i += 4) d[i] = 255;
    ctx.putImageData(out, 0, 0);
  }, [view, on, gain]);

  if (list?.supported === false) return <div className="vc-painting"><p className="vc-warn">{list.reason}</p></div>;
  const a = view?.analysis, s = a?.summary;
  const row = (label: string, k: string, unit: string, d = 4) => s?.[k] ? <tr key={k}><td>{label}</td><td>{fmt(s[k].median, d)}</td><td>{fmt(s[k].q1, d)}–{fmt(s[k].q3, d)}</td><td>{unit}</td></tr> : null;
  return <div className="vc-painting">
    <div className="vc-row">
      <select value={key} onChange={e => setKey(e.target.value)} aria-label="Field of view">{list?.images.map((x: any) => <option key={x.key} value={x.key}>{x.plate} · well {x.well} · site {x.site} · {x.condition}</option>)}</select>
      {busy && <LoaderCircle size={14} className="spin"/>}
      <button className="text-button" disabled={!view} onClick={() => canvas.current && exportFile(`cellpainting-${key}.png`, {base64: canvas.current.toDataURL('image/png').split(',')[1]})}><Download size={13}/>Export view</button>
    </div>
    <div className="vc-paint-stage" onWheel={e => { e.preventDefault(); setZoom(z => Math.min(8, Math.max(1, z * (e.deltaY < 0 ? 1.15 : 1 / 1.15)))); }}
      onPointerDown={e => { drag.current = [e.clientX - pan[0], e.clientY - pan[1]]; (e.target as Element).setPointerCapture?.(e.pointerId); }}
      onPointerMove={e => { if (drag.current) setPan([e.clientX - drag.current[0], e.clientY - drag.current[1]]); }} onPointerUp={() => { drag.current = null; }}>
      <div className="vc-paint-layers" style={{transform: `translate(${pan[0]}px, ${pan[1]}px) scale(${zoom})`}}>
        <canvas ref={canvas} aria-label="Cell Painting composite"/>
        {view && outline !== 'none' && <img src={view.outlines[outline]} alt={`${outline} outlines`} style={{opacity}}/>}
      </div>
      <span className="vc-paint-badge">Observed microscopy · {list?.dataset?.licence}</span>
    </div>
    <div className="vc-paint-controls">
      {view && Object.entries(view.layers as Record<string, Layer>).map(([c, l]) => <label key={c} className="vc-paint-ch" title={`${l.stain}. Display range ${l.displayRange.map(v => Math.round(v)).join('–')} (raw counts).`}>
        <input type="checkbox" checked={!!on[c]} onChange={() => setOn({...on, [c]: !on[c]})}/><i style={{background: l.color}}/>{c}
        <input type="range" min={0.2} max={3} step={0.05} value={gain[c] ?? DEFAULT_GAIN} onChange={e => setGain({...gain, [c]: Number(e.target.value)})} aria-label={`${c} gain`}/></label>)}
      <label className="vc-paint-ch">Outlines <select value={outline} onChange={e => setOutline(e.target.value as any)}><option value="nuclei">nuclei</option><option value="cells">cells</option><option value="none">none</option></select>
        <input type="range" min={0} max={1} step={0.05} value={opacity} onChange={e => setOpacity(Number(e.target.value))} aria-label="Outline opacity"/></label>
      <button className="text-button" onClick={() => { setZoom(1); setPan([0, 0]); }}>Reset view</button>
    </div>
    {a && <>
      <p className="vc-evidence"><b>{a.evidence}</b> · {a.counts.nucleiDetected} nuclei detected, {a.counts.cellsMeasured} whole cells measured (border cells excluded) · {a.units}</p>
      <table className="vc-table"><thead><tr><th>Feature (per cell)</th><th>Median</th><th>IQR</th><th>Unit</th></tr></thead><tbody>
        {row('Nucleus area', 'nucleusArea', 'px²')}{row('Cell area', 'cellArea', 'px²')}{row('Nucleus / cell area', 'ratio', 'ratio', 3)}{row('Cell perimeter (crack)', 'cellPerimeter', 'px')}
        {row('Cell eccentricity', 'cellEccentricity', '0–1', 3)}{row('Nucleus form factor', 'nucleusFormFactor', '4πA/P²', 3)}{row('DNA texture CV', 'dnaTextureCv', 'ratio', 3)}
        {row('DNA GLCM contrast', 'dnaGlcmContrast', '16 levels', 3)}{row('Mito, cytoplasm mean', 'mitoCytoplasmMean', 'raw counts')}{row('ER, cell mean', 'erCellMean', 'raw counts')}{row('AGP, cell mean', 'agpCellMean', 'raw counts')}
      </tbody></table>
      <p className="caption">{list?.dataset?.name}; {list?.dataset?.citation}. Channels as named by the dataset's load_data (no RNA channel at this site). Raw image range: {Object.entries(a.raw).map(([c, r]: any) => `${c} ${r.min}–${r.max}`).join(', ')}. {a.method}</p>
    </>}
  </div>;
}
