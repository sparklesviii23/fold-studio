import {useEffect, useRef, useState} from 'react';
import {project, scaleBar, type View} from './geometry';
import type {Vec3} from './types';

export interface StageScene {
  /** particle × frame positions in µm, exactly as returned by the engine */
  tracks: Vec3[][];
  bound?: number[][];
  receptors?: Vec3[];
  receptorsBound?: number[][];
  membrane?: number;
  outer?: number;
  viewRadius: number;
}

const TRAIL = 14;

/** Draws one computed frame of sampled particles (orthographic, drag to rotate). Nothing is interpolated or invented between frames. */
export default function ParticleStage({scene, frame}: {scene: StageScene; frame: number}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [size, setSize] = useState({w: 800, h: 520});
  const [angles, setAngles] = useState({yaw: 0.6, pitch: -0.35});
  const drag = useRef<{x: number; y: number; yaw: number; pitch: number} | null>(null);
  const scale = Math.min(size.w, size.h) * 0.42 / Math.max(scene.viewRadius, 1e-6);

  useEffect(() => {
    const el = canvas.current!.parentElement!;
    const ro = new ResizeObserver(() => setSize({w: el.clientWidth, h: el.clientHeight}));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const c = canvas.current!, dpr = window.devicePixelRatio || 1;
    c.width = size.w * dpr; c.height = size.h * dpr;
    const g = c.getContext('2d');
    if (!g) return;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, size.w, size.h);
    const v: View = {...angles, scale, cx: size.w / 2, cy: size.h / 2};
    const sphere = (R: number, fill: boolean, dash: number[]) => {
      g.save();
      if (fill) {
        const grad = g.createRadialGradient(v.cx - R * scale * 0.3, v.cy - R * scale * 0.35, R * scale * 0.1, v.cx, v.cy, R * scale);
        grad.addColorStop(0, 'rgba(159,220,255,0.10)'); grad.addColorStop(0.85, 'rgba(120,150,255,0.05)'); grad.addColorStop(1, 'rgba(185,166,255,0.16)');
        g.fillStyle = grad; g.beginPath(); g.arc(v.cx, v.cy, R * scale, 0, Math.PI * 2); g.fill();
      }
      g.setLineDash(dash); g.strokeStyle = fill ? 'rgba(207,233,255,0.55)' : 'rgba(207,233,255,0.28)'; g.lineWidth = 1.2;
      g.beginPath(); g.arc(v.cx, v.cy, R * scale, 0, Math.PI * 2); g.stroke();
      // Equator and one meridian as depth cues (geometry of the wall, not data).
      g.setLineDash([2, 4]); g.strokeStyle = 'rgba(207,233,255,0.16)';
      for (const ring of [(a: number): Vec3 => [R * Math.cos(a), 0, R * Math.sin(a)], (a: number): Vec3 => [0, R * Math.cos(a), R * Math.sin(a)]]) {
        g.beginPath();
        for (let k = 0; k <= 96; k++) { const [x, y] = project(ring(k / 96 * Math.PI * 2), v); if (k) g.lineTo(x, y); else g.moveTo(x, y); }
        g.stroke();
      }
      g.restore();
    };
    if (scene.outer) sphere(scene.outer, false, [6, 6]);
    if (scene.membrane) sphere(scene.membrane, true, []);
    // Receptors, coloured by their computed occupancy in this frame.
    if (scene.receptors) {
      const on = new Set(scene.receptorsBound?.[frame] ?? []);
      scene.receptors.map((r, i) => [project(r, v), on.has(i)] as const).sort((a, b) => a[0][2] - b[0][2]).forEach(([[x, y, z], b]) => {
        const front = z >= 0;
        g.fillStyle = b ? `rgba(255,179,102,${front ? 0.95 : 0.35})` : `rgba(185,166,255,${front ? 0.55 : 0.18})`;
        g.beginPath(); g.arc(x, y, b ? 3.2 : 2.2, 0, Math.PI * 2); g.fill();
      });
    }
    // Sampled particles: trail over the preceding computed frames, then the current position.
    const items = scene.tracks.map((tr, i) => ({tr, i, p: project(tr[Math.min(frame, tr.length - 1)], v)})).sort((a, b) => a.p[2] - b.p[2]);
    const depth = (z: number) => 0.45 + 0.55 * Math.max(0, Math.min(1, 0.5 + z / (2 * scene.viewRadius)));
    for (const {tr, i, p} of items) {
      const b = !!scene.bound?.[i]?.[frame];
      const a = depth(p[2]);
      g.lineWidth = 1.1;
      for (let k = Math.max(1, frame - TRAIL + 1); k <= Math.min(frame, tr.length - 1); k++) {
        const [x0, y0] = project(tr[k - 1], v), [x1, y1] = project(tr[k], v);
        g.strokeStyle = `rgba(159,220,255,${(a * 0.55 * (1 - (frame - k) / TRAIL)).toFixed(3)})`;
        g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.stroke();
      }
      g.fillStyle = b ? `rgba(255,190,120,${a})` : `rgba(230,244,255,${a})`;
      g.shadowColor = b ? '#ffb366' : '#9fdcff'; g.shadowBlur = 8;
      g.beginPath(); g.arc(p[0], p[1], b ? 3.6 : 2.8, 0, Math.PI * 2); g.fill();
      g.shadowBlur = 0;
    }
  }, [scene, frame, size, angles, scale]);

  const bar = scaleBar(scale);
  return <div className="cp-stage">
    <canvas ref={canvas} style={{width: size.w, height: size.h}} aria-label="Sampled particle positions from the Brownian-dynamics run; drag to rotate"
      onPointerDown={e => { drag.current = {x: e.clientX, y: e.clientY, ...angles}; (e.target as HTMLCanvasElement).setPointerCapture(e.pointerId); }}
      onPointerMove={e => { const d = drag.current; if (d) setAngles({yaw: d.yaw + (e.clientX - d.x) * 0.008, pitch: Math.max(-1.5, Math.min(1.5, d.pitch + (e.clientY - d.y) * 0.008))}); }}
      onPointerUp={() => { drag.current = null; }}/>
    <div className="cell-scale" aria-label={'Scale bar ' + bar + ' micrometres'}><i style={{width: bar * scale}}/><span>{bar} µm</span></div>
  </div>;
}
