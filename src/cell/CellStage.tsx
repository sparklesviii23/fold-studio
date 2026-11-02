import {useEffect, useRef, useState} from 'react';
import {fitCanvas, fullscreenQuad, type Quad} from '../cosmos/gl';
import {cellFragment, cellVertex} from './cellShader';
import {cellTypes, journeys, organelles} from './organelles';

export interface CellSettings {style: number; cut: boolean; slice: number; glass: boolean; layers: boolean[]; animate: boolean; quality: 'balanced'|'high'; cellType: string; gains?: number[]}
type Vec3 = [number, number, number];
interface Camera {yaw: number; pitch: number; distance: number; target: Vec3}

const ease = (t: number) => 1 - Math.pow(1 - t, 4);
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
function eye(c: Camera): Vec3 {
  return [c.target[0] + c.distance * Math.cos(c.pitch) * Math.sin(c.yaw), c.target[1] + c.distance * Math.sin(c.pitch), c.target[2] + c.distance * Math.cos(c.pitch) * Math.cos(c.yaw)];
}

/**
 * The WebGL stage. Drag to orbit, scroll to zoom, hover to identify. It
 * renders at a lower resolution while the camera moves and refines when still.
 */
export default function CellStage({settings, journey, journeyKey = 0, onJourneyDone, onSelect, onScale}: {settings: CellSettings; journey: string; journeyKey?: number; onJourneyDone: () => void; onSelect: (id: number) => void; onScale?: (pixelsPerMicron: number) => void}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const state = useRef({settings, dirty: true, moving: 0, highlight: 0});
  const camera = useRef<Camera>({yaw: 0.6, pitch: 0.28, distance: 3.4, target: [0, 0, 0]});
  const flight = useRef<{from: Camera; to: Camera; start: number; duration: number; slice: number} | null>(null);
  const quad = useRef<Quad | null>(null);
  const [hover, setHover] = useState<{id: number; x: number; y: number} | null>(null);
  const [failure, setFailure] = useState('');
  state.current.settings = settings; state.current.dirty = true;

  useEffect(() => {
    const j = journeys.find(j => j.id === journey);
    if (!j) return;
    const type = cellTypes.find(c => c.id === state.current.settings.cellType) ?? cellTypes[0];
    const target: Vec3 = j.id === 'nucleus' || j.id === 'chromatin' ? type.nucleus : j.target;
    flight.current = {from: {...camera.current, target: [...camera.current.target] as Vec3}, to: {yaw: j.yaw, pitch: j.pitch, distance: j.distance * (j.id === 'nucleus' ? type.nucleusRadius / 0.37 : 1), target}, start: performance.now(), duration: 2200, slice: j.slice};
  }, [journey, journeyKey]);

  useEffect(() => {
    const element = canvas.current!;
    try { quad.current = fullscreenQuad(element, cellVertex, cellFragment, {preserveDrawingBuffer: false}); }
    catch (e) { setFailure(String(e)); return; }
    const q = quad.current, {gl} = q;
    const started = performance.now();
    let frame = 0, time = 0, lastNow = performance.now(), sharpFrame = false, lastScale = 1;

    const uniforms = (pick: [number, number] | null) => {
      const s = state.current.settings, c = camera.current, e = eye(c);
      const n = [e[0] - c.target[0], e[1] - c.target[1], e[2] - c.target[2]], len = Math.hypot(n[0], n[1], n[2]);
      const nn = n.map(v => v / len);
      const w = nn[0] * c.target[0] + nn[1] * c.target[1] + nn[2] * c.target[2] + s.slice;
      gl.uniform2f(q.uniform('uResolution'), element.width, element.height);
      gl.uniform1f(q.uniform('uTime'), time);
      gl.uniform3f(q.uniform('uCamPos'), e[0], e[1], e[2]);
      gl.uniform3f(q.uniform('uCamTarget'), c.target[0], c.target[1], c.target[2]);
      gl.uniform4f(q.uniform('uCut'), nn[0], nn[1], nn[2], w);
      gl.uniform1f(q.uniform('uCutOn'), s.cut ? 1 : 0);
      gl.uniform1f(q.uniform('uStyle'), s.style);
      const L = s.layers.map(v => v ? 1 : 0);
      gl.uniform4f(q.uniform('uShowA'), L[0], L[1], L[2], L[3]);
      gl.uniform4f(q.uniform('uShowB'), L[4], L[5], L[6], L[7]);
      gl.uniform1f(q.uniform('uCrowd'), L[8]);
      const G = s.gains ?? [1, 1, 1, 1, 1, 1, 1, 1];
      gl.uniform4f(q.uniform('uGainA'), G[0], G[1], G[2], G[3]);
      gl.uniform4f(q.uniform('uGainB'), G[4], G[5], G[6], G[7]);
      gl.uniform1f(q.uniform('uGlass'), s.glass ? 1 : 0);
      gl.uniform1f(q.uniform('uHighlight'), state.current.highlight);
      const type = cellTypes.find(c => c.id === s.cellType) ?? cellTypes[0];
      gl.uniform3f(q.uniform('uNC'), ...type.nucleus);
      gl.uniform1f(q.uniform('uNR'), type.nucleusRadius);
      gl.uniform3f(q.uniform('uGC'), ...type.golgi);
      gl.uniform1f(q.uniform('uBox'), type.box);
      gl.uniform4f(q.uniform('uDroplet'), ...type.droplet);
      gl.uniform1f(q.uniform('uMitoExtra'), type.mitoExtra ? 1 : 0);
      gl.uniform1f(q.uniform('uGlycogen'), type.glycogen ? 1 : 0);
      gl.uniform1f(q.uniform('uPickMode'), pick ? 1 : 0);
      gl.uniform2f(q.uniform('uPick'), pick?.[0] ?? 0, pick?.[1] ?? 0);
    };

    const render = (now: number) => {
      frame = requestAnimationFrame(render);
      if (document.hidden || !element.isConnected || element.offsetParent === null) return;
      const s = state.current.settings, dt = Math.min(0.1, (now - lastNow) / 1000); lastNow = now;
      if (s.animate) { time += dt; state.current.dirty = true; }
      const f = flight.current;
      if (f) {
        const k = Math.min(1, (now - f.start) / f.duration), e = ease(k);
        camera.current = {yaw: lerp(f.from.yaw, f.to.yaw, e), pitch: lerp(f.from.pitch, f.to.pitch, e), distance: Math.exp(lerp(Math.log(f.from.distance), Math.log(f.to.distance), e)),
          target: [0, 1, 2].map(i => lerp(f.from.target[i], f.to.target[i], e)) as Vec3};
        state.current.moving = now; state.current.dirty = true;
        if (k >= 1) { flight.current = null; onJourneyDone(); }
      }
      const moving = now - state.current.moving < 180;
      if (!state.current.dirty && (moving || sharpFrame)) return;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const scale = moving || s.animate ? dpr * (s.quality === 'high' ? 0.6 : 0.42) : dpr * (s.quality === 'high' ? 1 : 0.72);
      fitCanvas(element, scale);
      gl.viewport(0, 0, element.width, element.height);
      uniforms(null);
      q.draw();
      sharpFrame = !moving && !s.animate;
      state.current.dirty = false;
      // Scale bar: visible half-height at the target plane, converted with the archetype's typical diameter.
      const type = cellTypes.find(c => c.id === s.cellType) ?? cellTypes[0];
      const pxPerMicron = (element.clientHeight / 2) / (camera.current.distance * 0.5 / 1.7) * (1.86 / type.diameter);
      if (onScale && Math.abs(pxPerMicron - lastScale) > lastScale * 0.02) { lastScale = pxPerMicron; onScale(pxPerMicron); }
    };
    frame = requestAnimationFrame(render);
    void started;

    const pickAt = (x: number, y: number) => {
      const rect = element.getBoundingClientRect(), sx = element.width / rect.width;
      const px = (x - rect.left) * sx, py = element.height - (y - rect.top) * sx;
      gl.viewport(0, 0, 1, 1);
      uniforms([px, py]);
      q.draw();
      const out = new Uint8Array(4);
      gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, out);
      state.current.dirty = true; sharpFrame = false;
      return Math.round(out[0] / 255 * 32);
    };

    let drag: {x: number; y: number; moved: boolean} | null = null, hoverTimer = 0;
    const down = (e: PointerEvent) => { drag = {x: e.clientX, y: e.clientY, moved: false}; element.setPointerCapture(e.pointerId); flight.current = null; };
    const move = (e: PointerEvent) => {
      if (drag) {
        const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
        if (Math.abs(dx) + Math.abs(dy) > 2) drag.moved = true;
        drag.x = e.clientX; drag.y = e.clientY;
        const c = camera.current;
        c.yaw -= dx * 0.006; c.pitch = Math.max(-1.45, Math.min(1.45, c.pitch + dy * 0.006));
        state.current.moving = performance.now(); state.current.dirty = true; sharpFrame = false;
        setHover(null);
        return;
      }
      clearTimeout(hoverTimer);
      const x = e.clientX, y = e.clientY;
      hoverTimer = window.setTimeout(() => {
        const id = pickAt(x, y), rect = element.getBoundingClientRect();
        state.current.highlight = id; state.current.dirty = true;
        setHover(id ? {id, x: x - rect.left, y: y - rect.top} : null);
      }, 90);
    };
    const up = (e: PointerEvent) => {
      if (drag && !drag.moved) { const id = pickAt(e.clientX, e.clientY); if (id) onSelect(id); }
      drag = null;
    };
    const wheel = (e: WheelEvent) => {
      e.preventDefault(); flight.current = null;
      const c = camera.current;
      c.distance = Math.max(0.25, Math.min(6, c.distance * Math.exp(e.deltaY * 0.0012)));
      state.current.moving = performance.now(); state.current.dirty = true; sharpFrame = false;
    };
    const leave = () => { clearTimeout(hoverTimer); state.current.highlight = 0; state.current.dirty = true; sharpFrame = false; setHover(null); };
    element.addEventListener('pointerdown', down); element.addEventListener('pointermove', move); element.addEventListener('pointerup', up);
    element.addEventListener('wheel', wheel, {passive: false}); element.addEventListener('pointerleave', leave);
    const resize = new ResizeObserver(() => { state.current.dirty = true; sharpFrame = false; });
    resize.observe(element);
    return () => {
      cancelAnimationFrame(frame); clearTimeout(hoverTimer); resize.disconnect();
      element.removeEventListener('pointerdown', down); element.removeEventListener('pointermove', move); element.removeEventListener('pointerup', up);
      element.removeEventListener('wheel', wheel); element.removeEventListener('pointerleave', leave);
      q.dispose(); quad.current = null;
    };
  }, []);

  return <div className="cell-stage">
    <canvas ref={canvas} aria-label="Interactive cell model. Drag to orbit, scroll to zoom, click an organelle to learn about it."/>
    {failure && <div className="cell-failure"><strong>The cell renderer needs WebGL2.</strong><span>{failure}</span></div>}
    {hover && organelles[hover.id] && <div className="cell-hover" style={{left: hover.x, top: hover.y}}><strong>{organelles[hover.id].name}</strong><span>Click to learn more</span></div>}
  </div>;
}
