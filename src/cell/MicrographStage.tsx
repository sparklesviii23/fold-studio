import {useEffect, useMemo, useRef, useState} from 'react';
import {Shuffle} from 'lucide-react';
import {fitCanvas, fullscreenQuad, type Quad} from '../cosmos/gl';
import {micrographFragment, micrographVertex} from './micrographShader';
import {chromatinFibre, MAX_BEADS, type Bead, type Particle} from './micrograph';

const modes = ['Cryo-EM', 'Negative stain', 'Illustrated'] as const;
const niceBars = [5, 10, 20, 25, 50, 100, 200, 500];

/**
 * Microscope: a simulated micrograph of the open protein (a field of randomly
 * oriented copies) or of a schematic chromatin fibre. Drag to pan, scroll to zoom.
 */
export default function MicrographStage({particle}: {particle: Particle}) {
  const canvas = useRef<HTMLCanvasElement>(null), quad = useRef<Quad | null>(null);
  const [scene, setScene] = useState<'protein'|'chromatin'>('protein'), [mode, setMode] = useState(0);
  const [noise, setNoise] = useState(0.07), [defocus, setDefocus] = useState(0.55), [fill, setFill] = useState(0.62), [seed, setSeed] = useState(3);
  const [bp, setBp] = useState(4000), [paper, setPaper] = useState(false), [failure, setFailure] = useState('');
  const view = useRef({pan: [0, 0], field: 0}), [scaleNm, setScaleNm] = useState<{nm: number; px: number}>({nm: 50, px: 100});
  const fibre = useMemo(() => chromatinFibre(bp, 50, seed), [bp, seed]);
  const beads: Bead[] = scene === 'protein' ? particle.beads : fibre.beads;
  const radius = scene === 'protein' ? particle.radius : Math.max(...fibre.beads.map(b => Math.hypot(b.x, b.y) + b.sigma));
  const draw = useRef<() => void>(() => {});

  useEffect(() => { view.current = {pan: [0, 0], field: scene === 'protein' ? Math.max(400, particle.radius * 22) : radius * 2.6}; draw.current(); }, [scene, particle, radius]);

  draw.current = () => {
    const q = quad.current, element = canvas.current;
    if (!q || !element) return;
    const {gl} = q;
    fitCanvas(element, Math.min(window.devicePixelRatio || 1, 2) * 0.75);
    gl.viewport(0, 0, element.width, element.height);
    const data = new Float32Array(MAX_BEADS * 4), weights = new Float32Array(MAX_BEADS);
    beads.forEach((b, i) => { data.set([b.x, b.y, b.z, b.sigma], i * 4); weights[i] = b.weight; });
    const meanWeight = beads.reduce((s, b) => s + b.weight, 0) / Math.max(1, beads.length);
    gl.uniform2f(q.uniform('uResolution'), element.width, element.height);
    gl.uniform2f(q.uniform('uPan'), view.current.pan[0], view.current.pan[1]);
    gl.uniform1f(q.uniform('uField'), view.current.field);
    gl.uniform4fv(q.uniform('uBeads'), data);
    gl.uniform1fv(q.uniform('uWeights'), weights);
    gl.uniform1i(q.uniform('uCount'), beads.length);
    gl.uniform1f(q.uniform('uRadius'), radius);
    gl.uniform1f(q.uniform('uSpacing'), radius * 2.7);
    gl.uniform1f(q.uniform('uFill'), fill);
    gl.uniform1f(q.uniform('uScene'), scene === 'protein' ? 0 : 1);
    gl.uniform1f(q.uniform('uMode'), mode);
    gl.uniform1f(q.uniform('uGain'), 1 / (meanWeight * (scene === 'protein' ? 2.4 : 1.6)));
    gl.uniform1f(q.uniform('uNoise'), noise);
    gl.uniform1f(q.uniform('uDefocus'), defocus);
    gl.uniform1f(q.uniform('uSeed'), seed * 17);
    gl.uniform1f(q.uniform('uPaper'), paper ? 1 : 0);
    q.draw();
    // Scale bar: pick a round length near 120 px.
    const pxPerNm = element.clientHeight / (view.current.field / 10);
    const nm = niceBars.reduce((a, b) => Math.abs(b * pxPerNm - 120) < Math.abs(a * pxPerNm - 120) ? b : a);
    setScaleNm(s => s.nm === nm && Math.abs(s.px - nm * pxPerNm) < 1 ? s : {nm, px: nm * pxPerNm});
  };

  useEffect(() => { draw.current(); });

  useEffect(() => {
    const element = canvas.current!;
    try { quad.current = fullscreenQuad(element, micrographVertex, micrographFragment); } catch (e) { setFailure(String(e)); return; }
    let frame = 0;
    const redraw = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(() => draw.current()); };
    let drag: {x: number; y: number} | null = null;
    const down = (e: PointerEvent) => { drag = {x: e.clientX, y: e.clientY}; element.setPointerCapture(e.pointerId); };
    const move = (e: PointerEvent) => {
      if (!drag) return;
      const k = view.current.field / element.clientHeight;
      view.current.pan = [view.current.pan[0] - (e.clientX - drag.x) * k, view.current.pan[1] + (e.clientY - drag.y) * k];
      drag = {x: e.clientX, y: e.clientY}; redraw();
    };
    const up = () => { drag = null; };
    const wheel = (e: WheelEvent) => { e.preventDefault(); view.current.field = Math.max(80, Math.min(20000, view.current.field * Math.exp(e.deltaY * 0.0012))); redraw(); };
    const resize = new ResizeObserver(redraw);
    element.addEventListener('pointerdown', down); element.addEventListener('pointermove', move); element.addEventListener('pointerup', up); element.addEventListener('wheel', wheel, {passive: false});
    resize.observe(element);
    redraw();
    return () => {
      cancelAnimationFrame(frame); resize.disconnect();
      element.removeEventListener('pointerdown', down); element.removeEventListener('pointermove', move); element.removeEventListener('pointerup', up); element.removeEventListener('wheel', wheel);
      quad.current?.dispose(); quad.current = null;
    };
  }, []);

  return <div className="cell-layout micrograph-layout">
    <canvas ref={canvas} className="micrograph-canvas" aria-label="Simulated micrograph. Drag to pan, scroll to zoom."/>
    {failure && <div className="cell-failure"><strong>The microscope needs WebGL2.</strong><span>{failure}</span></div>}
    <div className="micrograph-scale"><i style={{width: scaleNm.px}}/><span>{scaleNm.nm} nm</span></div>
    <div className="micrograph-label"><span className="evidence-badge">Simulated from coordinates · illustrative</span><strong>{scene === 'protein' ? particle.name : `Chromatin fibre · ${fibre.nucleosomes} nucleosomes`}</strong></div>
    <aside className="cell-card cell-controls">
      <section>
        <span className="eyebrow">Specimen</span>
        <div className="cosmos-segment"><button className={scene === 'protein' ? 'active' : ''} onClick={() => setScene('protein')}>Your protein</button><button className={scene === 'chromatin' ? 'active' : ''} onClick={() => setScene('chromatin')}>Chromatin</button></div>
        <p className="caption">{scene === 'protein' ? (particle.source === 'demo' ? 'Open a structure in the Molecular Laboratory to image it here; showing a synthetic demo.' : `${particle.residues} residues, coarse-grained to ${particle.beads.length} beads.`) : 'A schematic 10 nm fibre: 147 bp around each nucleosome, 50 bp linkers.'}</p>
      </section>
      <section>
        <span className="eyebrow">Imaging</span>
        <div className="cell-styles">{modes.map((m, i) => <button key={m} className={'cell-style' + (mode === i ? ' active' : '')} onClick={() => setMode(i)}><i className={'mg' + i}/>{m}</button>)}</div>
        {mode === 2 && <label className="checkbox-label"><input type="checkbox" checked={paper} onChange={e => setPaper(e.target.checked)}/>Paper background</label>}
      </section>
      <section>
        {mode < 2 && <label className="cell-slider">Noise<input type="range" min={0} max={0.2} step={0.005} value={noise} onChange={e => setNoise(Number(e.target.value))}/></label>}
        {mode === 0 && <label className="cell-slider">Defocus fringes<input type="range" min={0} max={1} step={0.01} value={defocus} onChange={e => setDefocus(Number(e.target.value))}/></label>}
        {scene === 'protein' ? <label className="cell-slider">Particle density<input type="range" min={0.1} max={1} step={0.01} value={fill} onChange={e => setFill(Number(e.target.value))}/></label>
          : <label className="cell-slider">DNA length · {(bp / 1000).toFixed(1)} kb<input type="range" min={1000} max={8000} step={100} value={bp} onChange={e => setBp(Number(e.target.value))}/></label>}
        <button className="cell-toggle" onClick={() => setSeed(s => s + 1)}><Shuffle size={13}/>New field</button>
      </section>
      <p className="caption">A projection of Gaussian-bead density with approximate noise and defocus. It shows what the molecule might look like under the technique; it is not experimental image data.</p>
    </aside>
  </div>;
}
