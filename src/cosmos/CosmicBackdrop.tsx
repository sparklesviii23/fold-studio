import {useEffect, useRef} from 'react';
import {fitCanvas, fullscreenQuad} from './gl';
import {nebulaFragment, nebulaVertex} from './nebulaShader';

const variants: Record<string, number> = {stellar: 0, abyss: 1, scientific: 2};
const glowSelector = '.quiet-panel,.research-card,.project-card,.protein-result,.mi-card,.mi-panel,.ec-card,.bc-panel,.cloud-panel,.cell-card,.look-card,.settings-card,.environment-card,.button.primary';

/**
 * The living deep-space background behind every workspace. `mode` comes from
 * Settings: 'living' animates at ~30 fps, 'still' renders a single frame, and
 * 'off' leaves the CSS gradient. Heavy compute pauses the animation.
 */
export default function CosmicBackdrop({environment, mode, paused}: {environment: string; mode: 'living'|'still'|'off'; paused: boolean}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const live = useRef({variant: 0, animate: true});
  live.current = {variant: variants[environment.toLowerCase()] ?? 0, animate: mode === 'living' && !paused};

  useEffect(() => {
    const element = canvas.current;
    if (!element || mode === 'off') return;
    let quad: ReturnType<typeof fullscreenQuad>;
    try { quad = fullscreenQuad(element, nebulaVertex, nebulaFragment); } catch { return; }
    const {gl} = quad;
    const pointer = {x: 0.62, y: 0.6, tx: 0.62, ty: 0.6, glow: 0.3, target: 0.3, moved: 0};
    const started = performance.now() - 40_000 * Math.random();
    let frame = 0, last = 0, drawn = false, disposed = false;
    // The haze is soft by nature, so it renders well below screen resolution.
    const scale = Math.min(window.devicePixelRatio || 1, 2) * 0.5;

    const draw = (now: number) => {
      fitCanvas(element, scale);
      gl.viewport(0, 0, element.width, element.height);
      // Critically damped easing: the lantern drifts after the pointer and settles.
      pointer.x += (pointer.tx - pointer.x) * 0.06; pointer.y += (pointer.ty - pointer.y) * 0.06;
      pointer.target = now - pointer.moved < 1400 ? 1 : 0.3;
      pointer.glow += (pointer.target - pointer.glow) * 0.035;
      gl.uniform2f(quad.uniform('uResolution'), element.width, element.height);
      gl.uniform1f(quad.uniform('uTime'), (now - started) / 1000);
      gl.uniform2f(quad.uniform('uPointer'), pointer.x, pointer.y);
      gl.uniform1f(quad.uniform('uPointerGlow'), pointer.glow);
      gl.uniform1f(quad.uniform('uVariant'), live.current.variant);
      quad.draw();
      if (!drawn) { drawn = true; element.classList.add('ready'); }
    };
    const loop = (now: number) => {
      if (disposed) return;
      frame = requestAnimationFrame(loop);
      if (document.hidden || !document.hasFocus()) { if (!drawn) draw(now); return; }
      if (!live.current.animate) { if (!drawn || now - last > 1000) { last = now; draw(now); } return; }
      if (now - last < 41) return;
      last = now; draw(now);
    };
    frame = requestAnimationFrame(loop);
    const move = (e: PointerEvent) => { pointer.tx = e.clientX / window.innerWidth; pointer.ty = 1 - e.clientY / window.innerHeight; pointer.moved = performance.now(); };
    window.addEventListener('pointermove', move, {passive: true});
    return () => { disposed = true; cancelAnimationFrame(frame); window.removeEventListener('pointermove', move); quad.dispose(); element.classList.remove('ready'); };
  }, [mode]);

  return <div className="cosmos-backdrop" aria-hidden="true">
    {mode !== 'off' && <canvas ref={canvas}/>}
    <div className="cosmos-vignette"/>
    {mode === 'living' && <div className="cosmos-grain"/>}
  </div>;
}

/** Light the glass edge nearest the pointer, as on the website. */
export function useGlowField() {
  useEffect(() => {
    let current: HTMLElement | null = null;
    const move = (e: PointerEvent) => {
      const target = (e.target as HTMLElement | null)?.closest?.(glowSelector) as HTMLElement | null;
      if (current && current !== target) { current.style.removeProperty('--glow-x'); current.style.removeProperty('--glow-y'); }
      current = target;
      if (!target) return;
      const rect = target.getBoundingClientRect();
      target.style.setProperty('--glow-x', e.clientX - rect.left + 'px');
      target.style.setProperty('--glow-y', e.clientY - rect.top + 'px');
    };
    window.addEventListener('pointermove', move, {passive: true});
    return () => window.removeEventListener('pointermove', move);
  }, []);
}
