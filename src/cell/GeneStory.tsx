import {useEffect, useMemo, useRef, useState} from 'react';
import {Pause, Play, RotateCcw} from 'lucide-react';
import {aminoClass, aminoNames, buildGene, chapters, type Gene} from './storyGenetics';

const W = 1200, H = 640, DNA_Y = 470, PROMOTER = 210, GENE_END = 610, PORE: [number, number] = [770, 262], STEP = 5, CHAPTER_SECONDS = 7;
const clamp = (v: number, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const ease = (t: number) => { t = clamp(t); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
const span = (t: number, a: number, b: number) => ease((t - a) / (b - a));
type Pt = [number, number];

const themes = {
  storybook: {bg: '#f6efe2', paper: '#efe4cf', ink: '#2c2342', soft: '#6f6585', nucleus: '#f3dfe6', cyto: '#e2efe9', dnaA: '#6c5ce7', dnaB: '#a29bfe', nucleosome: '#c58bd8', pol: '#4fb6a8', tf: ['#ffb84d', '#ff7f7f', '#7fb2ff'], cap: '#f2b705', splice: '#5d8ff0', ribo: ['#f39b86', '#e8765f'], trna: '#9b7fd6', glow: 'none', base: {A: '#ff8a80', U: '#ffcf4d', G: '#7cc68a', C: '#64aef2'} as Record<string, string>, intron: '#c9bfae', aa: {hydrophobic: '#ffcf4d', positive: '#64aef2', negative: '#ff7f7f', special: '#bfb6a6', polar: '#7cc68a'} as Record<string, string>},
  midnight: {bg: '#050916', paper: '#0b1430', ink: '#dfe9ff', soft: '#8a9cc4', nucleus: '#1a1440', cyto: '#06213a', dnaA: '#9fdcff', dnaB: '#b9a6ff', nucleosome: '#8f6fe0', pol: '#5eead4', tf: ['#ffcf7a', '#ff9eb5', '#9fdcff'], cap: '#ffd27a', splice: '#7aa7ff', ribo: ['#ffb38a', '#ff8f6b'], trna: '#c9a7ff', glow: 'url(#story-glow)', base: {A: '#ff9eb5', U: '#ffd27a', G: '#5eead4', C: '#9fdcff'} as Record<string, string>, intron: '#3d4766', aa: {hydrophobic: '#ffd27a', positive: '#9fdcff', negative: '#ff9eb5', special: '#7f8bb0', polar: '#5eead4'} as Record<string, string>},
};
type Theme = typeof themes.storybook;

/** Walk a polyline by arclength. */
function along(route: Pt[], s: number): Pt {
  if (s <= 0) return route[0];
  for (let i = 1; i < route.length; i++) {
    const [ax, ay] = route[i - 1], [bx, by] = route[i], len = Math.hypot(bx - ax, by - ay);
    if (s <= len) return [ax + (bx - ax) * s / len, ay + (by - ay) * s / len];
    s -= len;
  }
  return route[route.length - 1];
}
// The 5' cap leads the message out through the pore and down to the ribosome.
const XR = 640;
const exportRoute: Pt[] = [[40, 250], [XR, 256], [PORE[0] - 30, PORE[1]], [PORE[0] + 40, PORE[1] + 6], [830, 380], [860, DNA_Y], [1400, DNA_Y]];
const routeLength = exportRoute.slice(1).reduce((s, p, i) => s + Math.hypot(p[0] - exportRoute[i][0], p[1] - exportRoute[i][1]), 0);
const mix = (a: Pt, b: Pt, w: number): Pt => [a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w];

function helix(x0: number, x1: number, phase: number, open: (x: number) => number): string {
  let a = '', b = '';
  for (let x = x0; x <= x1; x += 6) {
    const o = open(x), y1 = DNA_Y + (9 + o) * Math.sin(x * 0.075) - o * 0.6, y2 = DNA_Y + (9 + o) * Math.sin(x * 0.075 + Math.PI + phase) + o * 0.6;
    a += (x === x0 ? 'M' : 'L') + x.toFixed(1) + ' ' + y1.toFixed(1);
    b += (x === x0 ? 'M' : 'L') + x.toFixed(1) + ' ' + y2.toFixed(1);
  }
  return a + b;
}

/** Positions of every pre-mRNA / mRNA bead for the current time. */
function rnaLayout(gene: Gene, T: number): {pts: Pt[]; kinds: string[]; letters: string[]; opacity: number[]} {
  const e1 = gene.exon1.length, ni = gene.intron.length, e2 = gene.exon2.length, pre = gene.exon1 + gene.intron + gene.exon2;
  const tail = Math.round(24 * span(T, 4.05, 4.85));
  const letters = [...pre, ...'A'.repeat(tail)];
  const kinds = letters.map((_, i) => i < e1 ? 'exon' : i < e1 + ni ? 'intron' : i < e1 + ni + e2 ? 'exon' : 'tail');
  const mature = (i: number) => i < e1 ? i : i - ni;
  // Chapter 3: the transcript trails behind the moving polymerase.
  const trailing = (i: number, k: number): Pt => {
    const polX = PROMOTER + (GENE_END - PROMOTER) * k, s = (Math.floor(pre.length * k) - i) * STEP;
    return [polX - s * 0.45 + 10 * Math.sin(s * 0.045), DNA_Y - 34 - s * 0.62 + 6 * Math.cos(s * 0.06)];
  };
  // Chapters 4–5: laid out 5'→3' from right to left; the intron loops out and leaves.
  const join = span(T, 3.45, 3.9), loop = span(T, 3.25, 3.55), leave = span(T, 3.7, 4.0);
  const flat = (i: number): Pt => {
    const base: Pt = [XR - i * STEP, 250 + 8 * Math.sin(i * 0.25)];
    if (kinds[i] === 'intron') {
      const j = i - e1, angle = (j / ni) * Math.PI * 2 + Math.PI / 2, r = ni * STEP / (2 * Math.PI), cx = XR - (e1 + ni / 2) * STEP;
      const looped: Pt = [cx + r * Math.cos(angle), 250 - r - 30 + r * Math.sin(angle)];
      const p = mix(base, looped, loop);
      return [p[0], p[1] - 150 * leave];
    }
    return i >= e1 + ni ? [base[0] + ni * STEP * join, base[1]] : base;
  };
  const exported = (i: number, travel: number): Pt => along(exportRoute, 600 + (routeLength - 460 - 600) * travel - mature(i) * STEP);
  const codon = T >= 6 ? Math.min(gene.codons.length, (T - 6) * (gene.codons.length + 2)) : 0;
  const translating = (i: number): Pt => { const m = mature(i); return [940 + (m - codon * 3) * STEP * 1.6, DNA_Y + 4 * Math.sin(m * 0.3)]; };

  const made = T < 2 ? 0 : Math.floor(pre.length * span(T, 2.05, 2.95));
  const pts: Pt[] = [], opacity: number[] = [];
  for (let i = 0; i < letters.length; i++) {
    let p: Pt, o = 1;
    if (T < 3) { p = trailing(i, T < 2 ? 0 : span(T, 2.05, 2.95)); o = i < made ? 1 : 0; }
    else if (T < 5.02) p = mix(trailing(i, 1), flat(i), span(T, 3.0, 3.2));
    else if (T < 6) { const travel = span(T, 5.02, 5.95); p = mix(flat(i), exported(i, travel), Math.min(1, travel * 4)); }
    else { p = mix(exported(i, 1), translating(i), span(T, 6.0, 6.3)); if (p[0] < 790) o = clamp((p[0] - 740) / 50); }
    if (kinds[i] === 'intron' && T >= 3) o = T >= 4.02 ? 0 : 1 - leave;
    pts.push(p); opacity.push(o);
  }
  return {pts, kinds, letters, opacity};
}

export default function GeneStory({initialSequence}: {initialSequence?: string}) {
  const [T, setT] = useState(0), [playing, setPlaying] = useState(true), [theme, setTheme] = useState<'storybook'|'midnight'>('storybook');
  const [custom, setCustom] = useState(initialSequence ?? ''), [gene, setGene] = useState(() => buildGene(initialSequence)), [error, setError] = useState('');
  const last = useRef(0);
  useEffect(() => {
    if (!playing) return;
    let frame = 0;
    last.current = performance.now();
    const tick = (now: number) => {
      const dt = (now - last.current) / 1000; last.current = now;
      setT(t => { const next = t + dt / CHAPTER_SECONDS; return next >= chapters.length ? 0 : next; });
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [playing]);

  const c = themes[theme], chapter = Math.min(chapters.length - 1, Math.floor(T)), local = T - chapter;
  const layout = useMemo(() => rnaLayout(gene, T), [gene, T]);
  const polK = T < 2 ? 0 : span(T, 2.05, 2.95), polX = PROMOTER + (GENE_END - PROMOTER) * polK;
  const polIn = span(T, 1.35, 1.8), polOut = span(T, 2.95, 3.25);
  const bubble = (x: number) => T >= 1.8 && T < 3.1 ? 16 * Math.exp(-Math.pow((x - polX) / 34, 2)) : 0;
  const codonsRead = T >= 6 ? Math.min(gene.codons.length, Math.floor((T - 6) * (gene.codons.length + 2))) : 0;
  const chain = gene.protein.slice(0, codonsRead).replace('*', '');

  function applySequence() {
    try { setGene(buildGene(custom)); setError(''); setT(0); setPlaying(true); } catch (e) { setError(String((e as Error).message ?? e)); }
  }

  return <div className={'gene-story ' + theme}>
    <div className="gene-story-canvas">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={'Animated illustration: ' + chapters[chapter].title}>
        <defs>
          <filter id="story-ink"><feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="2" seed="4"/><feDisplacementMap in="SourceGraphic" scale={theme === 'storybook' ? 3 : 0}/></filter>
          <filter id="story-glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
          <radialGradient id="story-nucleus" cx="30%" cy="45%" r="75%"><stop offset="0" stopColor={c.nucleus}/><stop offset="1" stopColor={c.paper}/></radialGradient>
          <linearGradient id="story-pol" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#fff" stopOpacity=".55"/><stop offset=".4" stopColor={c.pol}/><stop offset="1" stopColor={c.pol}/></linearGradient>
          <pattern id="story-dots" width="18" height="18" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.2" fill={c.soft} opacity=".18"/></pattern>
        </defs>
        <rect width={W} height={H} fill={c.bg}/>
        {/* Nucleus on the left, cytoplasm on the right, divided by the double envelope with a pore. */}
        <rect width={W} height={H} fill={c.cyto} opacity=".55"/>
        <path d={`M0 0 H${PORE[0] - 6} C${PORE[0] - 40} 120 ${PORE[0] + 30} 200 ${PORE[0] - 6} ${PORE[1] - 30} L${PORE[0] - 6} ${PORE[1] + 30} C${PORE[0] - 40} 360 ${PORE[0] + 30} 520 ${PORE[0] - 6} ${H} H0 Z`} fill="url(#story-nucleus)"/>
        <rect width={W} height={H} fill="url(#story-dots)"/>
        <g filter="url(#story-ink)" fill="none" stroke={c.ink} strokeLinecap="round" strokeLinejoin="round">
          <path d={`M${PORE[0] - 6} 0 C${PORE[0] - 40} 120 ${PORE[0] + 30} 200 ${PORE[0] - 6} ${PORE[1] - 30}`} strokeWidth="4" opacity=".75"/>
          <path d={`M${PORE[0] + 8} 0 C${PORE[0] - 26} 120 ${PORE[0] + 44} 200 ${PORE[0] + 8} ${PORE[1] - 30}`} strokeWidth="2.5" opacity=".45"/>
          <path d={`M${PORE[0] - 6} ${PORE[1] + 30} C${PORE[0] - 40} 360 ${PORE[0] + 30} 520 ${PORE[0] - 6} ${H}`} strokeWidth="4" opacity=".75"/>
          <path d={`M${PORE[0] + 8} ${PORE[1] + 30} C${PORE[0] - 26} 360 ${PORE[0] + 44} 520 ${PORE[0] + 8} ${H}`} strokeWidth="2.5" opacity=".45"/>
          <ellipse cx={PORE[0] + 1} cy={PORE[1] - 30} rx="16" ry="7" fill={c.splice} fillOpacity=".5" strokeWidth="2.5"/>
          <ellipse cx={PORE[0] + 1} cy={PORE[1] + 30} rx="16" ry="7" fill={c.splice} fillOpacity=".5" strokeWidth="2.5"/>
        </g>
        <text x="36" y="48" className="story-region" fill={c.soft}>NUCLEUS</text>
        <text x={W - 36} y="48" textAnchor="end" className="story-region" fill={c.soft}>CYTOPLASM</text>

        {/* DNA: nucleosomes, promoter, the gene body and the transcription bubble. */}
        <g filter="url(#story-ink)" opacity={1 - span(T, 3.0, 3.4) * 0.55}>
          <path d={helix(30, 730, 0, bubble)} fill="none" stroke={c.dnaA} strokeWidth="4" strokeLinecap="round" style={{filter: c.glow}}/>
          <rect x={PROMOTER - 30} y={DNA_Y + 26} width="34" height="7" rx="3.5" fill={c.tf[0]} opacity={span(T, 0.2, 0.6)}/>
          <rect x={PROMOTER + 8} y={DNA_Y + 26} width={(GENE_END - PROMOTER - 8)} height="7" rx="3.5" fill={c.dnaB} opacity={span(T, 0.3, 0.8) * 0.8}/>
          {[70, 140, 260, 340, 420, 500, 580, 660, 720].map((x, i) => {
            const inGene = x > PROMOTER - 20 && x < GENE_END + 10, away = inGene ? span(T, 0.1 + i * 0.04, 0.7 + i * 0.03) : 0;
            return <g key={x} transform={`translate(${x + (x < 400 ? -1 : 1) * away * 30} ${DNA_Y - away * 90})`} opacity={1 - away}>
              <ellipse rx="22" ry="17" fill={c.nucleosome} stroke={c.ink} strokeWidth="2.5"/>
              <path d="M-20 -4 C-8 10 8 10 20 -4" fill="none" stroke={c.ink} strokeWidth="2" opacity=".5"/>
            </g>;
          })}
        </g>
        <text x={PROMOTER - 14} y={DNA_Y + 52} className="story-label" fill={c.soft} opacity={span(T, 0.3, 0.7)}>promoter</text>
        <text x={(PROMOTER + GENE_END) / 2} y={DNA_Y + 52} textAnchor="middle" className="story-label" fill={c.soft} opacity={span(T, 0.4, 0.8)}>gene</text>

        {/* Transcription factors and RNA polymerase II. */}
        <g filter="url(#story-ink)" stroke={c.ink} strokeWidth="2.5" opacity={1 - polOut}>
          {[[-22, -26], [2, -34], [24, -24]].map(([dx, dy], i) => {
            const k = span(T, 1.0 + i * 0.08, 1.4 + i * 0.08);
            return <circle key={i} cx={PROMOTER + dx} cy={DNA_Y + dy - (1 - k) * 260} r="13" fill={c.tf[i]} opacity={k}/>;
          })}
          <g transform={`translate(${polX} ${DNA_Y - 6 - (1 - polIn) * 300})`} opacity={polIn}>
            <path d="M-46 8 C-50 -36 -10 -52 18 -44 C52 -34 56 0 46 22 C34 46 -36 46 -46 8 Z" fill="url(#story-pol)" style={{filter: c.glow}}/>
            <circle cx="-14" cy="-20" r="5" fill={c.ink} stroke="none" opacity=".75"/>
            <text y="-58" textAnchor="middle" className="story-label" fill={c.ink} stroke="none">RNA Pol II</text>
          </g>
        </g>

        {/* Spliceosome, cap-binding and poly(A) polymerase appear at their moments. */}
        <g filter="url(#story-ink)" stroke={c.ink} strokeWidth="2.5">
          <g transform={`translate(${XR - (gene.exon1.length + gene.intron.length / 2) * STEP} ${215 - 20 * span(T, 3.2, 3.5)})`} opacity={span(T, 3.15, 3.3) * (1 - span(T, 3.75, 3.95))}>
            <path d="M-34 0 C-34 -30 34 -30 34 0 C34 24 -34 24 -34 0 Z" fill={c.splice} fillOpacity=".85"/>
            <text y="-36" textAnchor="middle" className="story-label" fill={c.ink} stroke="none">spliceosome</text>
          </g>
          {layout.pts.length > 0 && T >= 3 && <g transform={`translate(${layout.pts[0][0] + 13} ${layout.pts[0][1]})`} opacity={span(T, 3.02, 3.2) * layout.opacity[0]}>
            <path d="M-10 6 L-4 -10 L4 -10 L10 6 Z" fill={c.cap}/>
            {T < 5 && <text y="-18" textAnchor="middle" className="story-label" fill={c.ink} stroke="none">5′ cap</text>}
          </g>}
          {T >= 4 && T < 5 && (() => { const last = layout.pts[layout.pts.length - 1]; return <g transform={`translate(${last[0] - 22} ${last[1]})`} opacity={span(T, 4.0, 4.15) * (1 - span(T, 4.85, 5.0))}>
            <circle r="16" fill={c.tf[1]}/><text y="-24" textAnchor="middle" className="story-label" fill={c.ink} stroke="none">poly(A) polymerase</text></g>; })()}
        </g>

        {/* The RNA itself: one bead per nucleotide, coloured by base. */}
        <g style={{filter: c.glow}}>
          {layout.pts.map(([x, y], i) => i > 0 && layout.opacity[i] > 0.02 && layout.opacity[i - 1] > 0.02 && layout.kinds[i] !== 'intron' === (layout.kinds[i - 1] !== 'intron') ?
            <line key={'l' + i} x1={layout.pts[i - 1][0]} y1={layout.pts[i - 1][1]} x2={x} y2={y} stroke={layout.kinds[i] === 'intron' ? c.intron : c.ink} strokeOpacity={Math.min(layout.opacity[i], layout.opacity[i - 1]) * 0.6} strokeWidth="2.5"/> : null)}
          {layout.pts.map(([x, y], i) => layout.opacity[i] > 0.02 && <circle key={i} cx={x} cy={y} r={layout.kinds[i] === 'tail' ? 3.4 : 4.2}
            fill={layout.kinds[i] === 'intron' ? c.intron : c.base[layout.letters[i]]} stroke={c.ink} strokeWidth="1.2" opacity={layout.opacity[i]}/>)}
        </g>
        {T >= 3.1 && T < 3.5 && <text x={XR - (gene.exon1.length + gene.intron.length / 2) * STEP} y="300" textAnchor="middle" className="story-label" fill={c.soft}>intron · GU…AG</text>}
        {T >= 3.75 && T < 4.1 && <text x={XR - 60} y="300" className="story-label" fill={c.soft}>exons joined</text>}

        {/* Translation: ribosome, incoming tRNA and the emerging polypeptide. */}
        {T >= 5.85 && <g opacity={span(T, 5.85, 6.05)}>
          <g filter="url(#story-ink)" stroke={c.ink} strokeWidth="2.5">
            <path d="M906 486 C900 470 930 462 960 462 C1000 462 1018 474 1012 490 C1006 506 914 506 906 486 Z" fill={c.ribo[0]}/>
            <path d="M896 456 C884 404 930 380 966 382 C1010 384 1036 412 1024 452 C1018 470 904 474 896 456 Z" fill={c.ribo[1]}/>
            <text x="960" y="530" textAnchor="middle" className="story-label" fill={c.ink} stroke="none">ribosome</text>
          </g>
          {codonsRead < gene.codons.length && (() => {
            const k = clamp(((T - 6) * (gene.codons.length + 2)) % 1), aa = gene.protein[codonsRead] ?? '*';
            const x = 980 + (1 - ease(k * 1.4)) * 140, y = 420 - (1 - ease(k * 1.4)) * 200;
            return <g transform={`translate(${x} ${y})`} filter="url(#story-ink)" stroke={c.ink} strokeWidth="2.2" opacity={clamp(k * 3) * (1 - clamp((k - 0.85) * 6))}>
              <path d="M-14 30 L-14 -6 C-14 -22 14 -22 14 -6 L14 30" fill="none" stroke={c.trna} strokeWidth="9"/>
              <circle cy="-30" r="10" fill={c.aa[aminoClass(aa)]}/>
              <text y="-27" textAnchor="middle" className="story-aa" fill={c.ink} stroke="none">{aa === '*' ? '■' : aa}</text>
            </g>;
          })()}
          <g filter="url(#story-ink)">
            {[...chain].map((aa, i) => {
              const n = chain.length - 1 - i, a = n * 0.55, rr = 14 + n * 4.2;
              const x = 962 + Math.sin(a) * rr * 0.9, y = 372 - n * 9 + Math.cos(a) * 10;
              return <g key={i}>
                {i > 0 && <line x1={x} y1={y} x2={962 + Math.sin(a + 0.55) * (rr - 4.2) * 0.9} y2={372 - (n - 1) * 9 + Math.cos(a + 0.55) * 10} stroke={c.ink} strokeWidth="2" opacity=".5"/>}
                <circle cx={x} cy={y} r="9" fill={c.aa[aminoClass(aa)]} stroke={c.ink} strokeWidth="1.8"/>
                <text x={x} y={y + 3.5} textAnchor="middle" className="story-aa" fill={c.ink}>{aa}</text>
              </g>;
            })}
          </g>
        </g>}
      </svg>
      <div className={'gene-story-caption ' + (chapter >= 5 ? 'left' : 'right')} key={chapter}>
        <span className="eyebrow">Chapter {chapter + 1} of {chapters.length}</span>
        <h2>{chapters[chapter].title}</h2>
        <p>{chapters[chapter].body}</p>
      </div>
    </div>

    <div className="gene-story-controls">
      <button className="story-play" onClick={() => setPlaying(!playing)} aria-label={playing ? 'Pause' : 'Play'}>{playing ? <Pause size={18}/> : <Play size={18}/>}</button>
      <input type="range" min={0} max={chapters.length - 0.001} step={0.001} value={T} aria-label="Story time" onChange={e => { setPlaying(false); setT(Number(e.target.value)); }}/>
      <button className="icon-button" onClick={() => setT(0)} title="Restart"><RotateCcw size={16}/></button>
      <div className="cosmos-segment"><button className={theme === 'storybook' ? 'active' : ''} onClick={() => setTheme('storybook')}>Storybook</button><button className={theme === 'midnight' ? 'active' : ''} onClick={() => setTheme('midnight')}>Midnight</button></div>
    </div>
    <div className="gene-story-chapters">{chapters.map((ch, i) => <button key={ch.title} className={i === chapter ? 'active' : ''} onClick={() => setT(i + 0.001)}><span>{String(i + 1).padStart(2, '0')}</span>{ch.title}<i style={{transform: `scaleX(${i < chapter ? 1 : i === chapter ? local : 0})`}}/></button>)}</div>

    <div className="gene-story-readout">
      <div>
        <span className="eyebrow">{gene.name}</span>
        <p className="gene-sequence">
          <span className="seq-exon">{gene.exon1}</span><span className="seq-intron" style={{opacity: T >= 3.9 ? 0.25 : 1, textDecoration: T >= 3.9 ? 'line-through' : 'none'}}>{gene.intron.toLowerCase()}</span><span className="seq-exon">{gene.exon2}</span>{T >= 4.1 && <span className="seq-tail">AAAAAAAA…</span>}
        </p>
      </div>
      <div>
        <span className="eyebrow">Protein · {codonsRead} codons read</span>
        <p className="gene-protein">{[...gene.protein.replace('*', '')].map((aa, i) => <span key={i} title={aminoNames[aa]} className={i < chain.length ? 'made ' + aminoClass(aa) : ''}>{aa}</span>)}</p>
      </div>
      <label className="gene-custom">Use your own coding sequence
        <div><input value={custom} onChange={e => setCustom(e.target.value)} placeholder="ATG… (DNA or RNA, up to 60 codons)" spellCheck={false}/><button className="button" onClick={applySequence}>Animate</button></div>
        {error && <span className="error">{error}</span>}
      </label>
    </div>
  </div>;
}
