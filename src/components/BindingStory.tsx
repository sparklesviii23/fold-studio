import {useEffect, useMemo, useRef, useState} from 'react';
import {Pause, Play, RotateCcw} from 'lucide-react';
import {guessBinder, projectComplex, type TraceAtom} from './bindingGeometry';

const W = 1200, H = 700, LOOP = 16;
const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const easeOut = (t: number) => 1 - Math.pow(1 - clamp(t), 3);
const themes = {
  paper: {bg: '#f2eee5', ink: '#2b2420', sheen: 'rgba(255,255,255,0.32)', target: ['#e08a6d', '#d8a46a', '#c98f86', '#b9a27a'], binder: '#7fb0a0', motes: '#c4b8a3', hot: '#ffcf5a', caption: 'light'},
  midnight: {bg: '#050917', ink: '#02040c', sheen: 'rgba(220,235,255,0.28)', target: ['#7fb6ff', '#9f8cff', '#6fd3e0', '#8ea8ff'], binder: '#f0abfc', motes: '#3b4a7a', hot: '#ffe08a', caption: 'dark'},
};
const phases = [
  {at: 0, title: 'The target', body: (t: string) => `${t}, drawn from its predicted coordinates.`},
  {at: 0.14, title: 'A binder approaches', body: (_: string, b: string) => `The designed ${b} drifts through solution towards its site.`},
  {at: 0.6, title: 'Docking', body: () => 'It settles into the pose predicted for the complex.'},
  {at: 0.72, title: 'Bound', body: (_: string, __: string, n: number) => `${n} target residues line the predicted interface.`},
];

/**
 * Illustrated binding animation for any complex. Shapes come from the real Cα
 * trace projected onto its principal plane; the approach is choreographed, not
 * simulated, and is labelled that way.
 */
export default function BindingStory({atoms, name}: {atoms: TraceAtom[]; name: string}) {
  const chains = useMemo(() => [...new Set(atoms.filter(a => a.atomName === 'CA').map(a => a.chain))], [atoms]);
  const [binder, setBinder] = useState<string | null>(() => guessBinder(atoms));
  useEffect(() => { setBinder(guessBinder(atoms)); }, [atoms]);
  const scene = useMemo(() => projectComplex(atoms, binder ? [binder] : []), [atoms, binder]);
  const [t, setT] = useState(0), [playing, setPlaying] = useState(true), [themeId, setThemeId] = useState<'paper'|'midnight'>('paper');
  const last = useRef(0);
  useEffect(() => {
    if (!playing) return;
    let frame = 0; last.current = performance.now();
    const tick = (now: number) => { const dt = (now - last.current) / 1000; last.current = now; setT(v => (v + dt / LOOP) % 1); frame = requestAnimationFrame(tick); };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing]);
  const motes = useMemo(() => Array.from({length: 46}, (_, i) => ({x: (i * 397) % W, y: (i * 613) % H, r: 1.5 + (i * 7) % 4, s: 0.3 + ((i * 13) % 10) / 14, p: i * 1.7})), []);

  if (!scene) return <div className="binding-empty"><h3>Open a structure to animate it.</h3><p>Choose a predicted complex — a target and its designed binder — in the Molecular Laboratory or Research Library.</p></div>;
  const c = themes[themeId], time = t * LOOP;
  const scale = Math.min(W * 0.62, H * 0.74) / (2 * scene.radius), cx = W * 0.47, cy = H * 0.52;
  const r = Math.max(2.5, 3.5 * scale), blur = r * 0.62;
  // Per-residue size jitter gives the silhouette a lumpy, surface-like edge.
  const lump = (i: number) => 0.82 + 0.4 * ((Math.sin(i * 12.9898) * 43758.5453) % 1 + 1) % 1;
  const toScreen = (p: [number, number]): [number, number] => [cx + p[0] * scale, cy + p[1] * scale];
  const target = scene.chains.filter(ch => ch.id !== binder), bound = scene.chains.find(ch => ch.id === binder);
  const tc = target.length ? [target.reduce((s, ch) => s + ch.centroid[0] * ch.residues, 0), target.reduce((s, ch) => s + ch.centroid[1] * ch.residues, 0)].map(v => v / target.reduce((s, ch) => s + ch.residues, 0)) : [0, 0];

  // Approach: from off-screen along the target→binder direction, swaying, then a small spring at contact.
  const dock = 0.6, k = easeOut(t / dock);
  let bx = 0, by = 0, angle = 0;
  if (bound) {
    const d = [bound.centroid[0] - tc[0], bound.centroid[1] - tc[1]], len = Math.hypot(d[0], d[1]) || 1, dir = [d[0] / len, d[1] / len], perp = [-dir[1], dir[0]];
    const far = W * 0.7, sway = Math.sin((1 - k) * Math.PI * 1.3) * 110 * (1 - k);
    bx = dir[0] * far * (1 - k) + perp[0] * sway; by = dir[1] * far * (1 - k) + perp[1] * sway;
    angle = 70 * Math.pow(1 - k, 1.6) + (t < dock ? 4 * Math.sin(time * 2.1) * (1 - k) : 0);
    if (t >= dock) { const s = (t - dock) * LOOP; const spring = -9 * Math.sin(s * 9) * Math.exp(-s * 3.2); bx += dir[0] * spring; by += dir[1] * spring; }
  }
  const breathe = 1 + 0.008 * Math.sin(time * 1.3), bc = bound ? toScreen(bound.centroid) : [0, 0];
  const after = clamp((t - dock) / 0.08), phase = [...phases].reverse().find(p => t >= p.at)!;
  const ic = scene.interfaceCentre ? toScreen(scene.interfaceCentre) : null;
  const targetName = target.length > 1 ? 'Target chains ' + target.map(ch => ch.id).join(', ') : 'Target chain ' + (target[0]?.id ?? '');
  const binderName = bound ? 'binder (chain ' + bound.id + ')' : 'binder';

  return <div className={'binding-story ' + themeId}>
    <div className="binding-canvas">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={'Illustrated binding animation: ' + phase.title}>
        <defs>
          <filter id="bs-blob" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur in="SourceGraphic" stdDeviation={blur} result="b"/>
            <feColorMatrix in="b" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 18 -8" result="goo"/>
            <feMorphology in="goo" operator="dilate" radius={Math.max(1.5, r * 0.32)} result="fat"/>
            <feFlood floodColor={c.ink} result="ink"/>
            <feComposite in="ink" in2="fat" operator="in" result="outline"/>
            <feTurbulence type="fractalNoise" baseFrequency="0.015" numOctaves="2" seed="5" result="wobble"/>
            <feMerge result="drawn"><feMergeNode in="outline"/><feMergeNode in="goo"/></feMerge>
            <feDisplacementMap in="drawn" in2="wobble" scale={themeId === 'paper' ? 4 : 1}/>
          </filter>
          <filter id="bs-sheen"><feGaussianBlur stdDeviation={blur * 1.2}/><feColorMatrix values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 14 -7"/></filter>
          <filter id="bs-glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="5"/></filter>
          <radialGradient id="bs-vignette" cx="50%" cy="50%" r="70%"><stop offset="0.6" stopColor={c.bg} stopOpacity="0"/><stop offset="1" stopColor={themeId === 'paper' ? '#d9d1c2' : '#000'} stopOpacity="0.7"/></radialGradient>
        </defs>
        <rect width={W} height={H} fill={c.bg}/>
        {motes.map((m, i) => <circle key={i} cx={(m.x + time * 8 * m.s) % W} cy={m.y + 8 * Math.sin(time * m.s + m.p)} r={m.r} fill={c.motes} opacity={0.35}/>)}

        <g transform={`translate(${cx} ${cy}) scale(${breathe}) translate(${-cx} ${-cy})`}>
          {target.map((ch, n) => <g key={ch.id}>
            <g filter="url(#bs-blob)">{ch.points.map((p, i) => { const [x, y] = toScreen(p); return <circle key={i} cx={x} cy={y} r={r * lump(i)} fill={c.target[n % c.target.length]}/>; })}</g>
            <g filter="url(#bs-sheen)" opacity="0.8">{ch.points.map((p, i) => { const [x, y] = toScreen(p); return <circle key={i} cx={x - r * 0.35} cy={y - r * 0.45} r={r * 0.5} fill={c.sheen}/>; })}</g>
          </g>)}
          {ic && after > 0 && [0, 1, 2].map(i => { const ph = ((time - dock * LOOP) * 0.5 + i / 3) % 1; return <circle key={i} cx={ic[0]} cy={ic[1]} r={20 + ph * 170} fill="none" stroke={c.hot} strokeWidth={2.5 * (1 - ph)} opacity={(1 - ph) * 0.7 * after}/>; })}
          {after > 0 && scene.interfaceTarget.map((p, i) => { const [x, y] = toScreen(p), a = clamp(after * 2.5 - i * 0.02); return <g key={i} opacity={a}><circle cx={x} cy={y} r={r * 0.9} fill={c.hot} filter="url(#bs-glow)" opacity="0.7"/><circle cx={x} cy={y} r={r * 0.42} fill={c.hot}/></g>; })}
        </g>

        {bound && <g transform={`translate(${bx} ${by}) rotate(${angle} ${bc[0]} ${bc[1]})`}>
          <g filter="url(#bs-blob)">{bound.points.map((p, i) => { const [x, y] = toScreen(p); return <circle key={i} cx={x} cy={y} r={r * lump(i + 7)} fill={c.binder}/>; })}</g>
          <g filter="url(#bs-sheen)" opacity="0.85">{bound.points.map((p, i) => { const [x, y] = toScreen(p); return <circle key={i} cx={x - r * 0.35} cy={y - r * 0.45} r={r * 0.5} fill={c.sheen}/>; })}</g>
        </g>}
        <rect width={W} height={H} fill="url(#bs-vignette)" pointerEvents="none"/>
      </svg>
      <div className={'binding-caption ' + c.caption} key={phase.title}>
        <span className="eyebrow">{name}</span>
        <h2>{bound ? phase.title : 'One chain'}</h2>
        <p>{bound ? phase.body(targetName, binderName, scene.interfaceTarget.length) : 'Open a complex with a target and a binder to see it bind.'}</p>
      </div>
      <span className="evidence-badge binding-evidence" title="Shapes come from the predicted coordinates; the approach motion is an illustration, not a simulation.">Predicted pose · illustrative motion</span>
    </div>
    <div className="gene-story-controls">
      <button className="story-play" onClick={() => setPlaying(!playing)} aria-label={playing ? 'Pause' : 'Play'}>{playing ? <Pause size={18}/> : <Play size={18}/>}</button>
      <input type="range" min={0} max={0.999} step={0.001} value={t} aria-label="Animation time" onChange={e => { setPlaying(false); setT(Number(e.target.value)); }}/>
      <button className="icon-button" onClick={() => setT(0)} title="Restart"><RotateCcw size={16}/></button>
      {chains.length > 1 && <label className="binding-chain">Binder<select value={binder ?? ''} onChange={e => setBinder(e.target.value)}>{chains.map(id => <option key={id} value={id}>Chain {id}</option>)}</select></label>}
      <div className="cosmos-segment"><button className={themeId === 'paper' ? 'active' : ''} onClick={() => setThemeId('paper')}>Paper</button><button className={themeId === 'midnight' ? 'active' : ''} onClick={() => setThemeId('midnight')}>Midnight</button></div>
    </div>
  </div>;
}
