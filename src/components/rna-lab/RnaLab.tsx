import {useEffect, useMemo, useRef, useState} from 'react';
import {Check, FlaskConical, LoaderCircle, Minus, Pause, Play, ShieldCheck, TriangleAlert, X} from 'lucide-react';
import {rpc} from '../../lib/api';
import {arcPath, compare, pairsOf, ribosomesAt, smooth, type Frame} from '../../lib/rnaLab';
import {fmt, SERIES, TimeChart} from '../mechanistic/MechCharts';
import GeneStory from '../../cell/GeneStory';
import KineticsView from './KineticsView';
import '../multiscale/multiscale.css';
import '../mechanistic/mechanistic.css';
import './rna-lab.css';

type Mode = 'fold' | 'kinetics' | 'translate' | 'story';
interface CheckRow {check: string; detail: string; value: number | null; threshold?: number; passed: boolean; skipped?: boolean}

function Checks({checks, runtime}: {checks: CheckRow[] | null; runtime?: string}) {
  if (!checks) return null;
  return <div className="mech-checks"><span className="eyebrow">Validation{runtime ? ' · ' + runtime : ''}</span>
    {checks.map(c => <div key={c.check} className={'mech-check ' + (c.skipped ? 'skip' : c.passed ? 'ok' : 'fail')}>{c.skipped ? <Minus size={14}/> : c.passed ? <Check size={14}/> : <X size={14}/>}
      <div><strong>{c.check}</strong><span>{c.detail}{c.value !== null && c.value !== undefined ? ' · statistic ' + fmt(c.value, 3) : ''}{c.threshold !== undefined ? ' (limit ' + fmt(c.threshold, 3) + ')' : ''}</span></div></div>)}
  </div>;
}

function Metric({label, value, note}: {label: string; value: string; note?: string}) {
  return <div className="rna-metric"><small>{label}</small><strong>{value}</strong>{note && <span>{note}</span>}</div>;
}

/* ---------------- Demo 3: folding ensemble ---------------- */

const AW = 760, AH = 300, AM = 18;

function ArcDiagram({seq, shown, reference, bpp, label}: {seq: string; shown: string; reference?: string; bpp: [number, number, number][]; label: string}) {
  const n = seq.length, x = (k: number) => AM + (k + 0.5) * (AW - 2 * AM) / n, base = AH / 2;
  const flat = (base - 30) / ((AW - 2 * AM) / 2);
  const refKeys = new Set(reference ? pairsOf(reference).map(p => p.join(':')) : []);
  const shownPairs = pairsOf(shown), shownKeys = new Set(shownPairs.map(p => p.join(':')));
  const missed = reference ? pairsOf(reference).filter(p => !shownKeys.has(p.join(':'))) : [];
  const step = n > 90 ? 10 : 5;
  return <svg className="rna-arcs" viewBox={`0 0 ${AW} ${AH}`} role="img" aria-label={`Arc diagram: ${label} above the sequence, base-pair probabilities below`}>
    {missed.map(([i, j]) => <path key={'m' + i} d={arcPath(i, j, x, base - 8, true, flat)} className="rna-arc missed"/>)}
    {shownPairs.map(([i, j]) => <path key={'s' + i + '-' + j} d={arcPath(i, j, x, base - 8, true, flat)} className={'rna-arc ' + (!reference ? 'plain' : refKeys.has(i + ':' + j) ? 'hit' : 'extra')}/>)}
    {bpp.filter(b => b[2] >= 0.05).map(([i, j, p]) => <path key={'p' + i + '-' + j} d={arcPath(i, j, x, base + 8, false, flat)} className="rna-arc prob" style={{opacity: 0.15 + 0.85 * p, strokeWidth: 0.6 + 2.2 * p}}><title>{`${seq[i]}${i + 1}–${seq[j]}${j + 1}: p = ${p.toFixed(3)}`}</title></path>)}
    {[...seq].map((c, k) => <text key={k} x={x(k)} y={base + 3} className={'rna-base b-' + c}>{n <= 120 ? c : ''}</text>)}
    {Array.from({length: Math.floor(n / step)}, (_, k) => (k + 1) * step).map(v => <text key={'t' + v} x={x(v - 1)} y={AH - 4} className="rna-tick">{v}</text>)}
    <text x={AM} y={14} className="rna-caption-svg">{label}</text>
    <text x={AM} y={AH - 18} className="rna-caption-svg">base-pair probability (McCaskill)</text>
  </svg>;
}

function DotPlot({n, bpp, lower, reference}: {n: number; bpp: [number, number, number][]; lower: string; reference?: string}) {
  const S = 300, c = S / n;
  const ref = reference ? pairsOf(reference) : [];
  return <svg className="rna-dotplot" viewBox={`0 0 ${S} ${S}`} role="img" aria-label="Dot plot: pair probabilities upper right, selected structure lower left">
    <rect x={0} y={0} width={S} height={S} className="rna-dot-frame"/>
    <line x1={0} y1={0} x2={S} y2={S} className="rna-dot-diag"/>
    {bpp.map(([i, j, p]) => { const s = Math.max(0.8, c * Math.sqrt(p)); return <rect key={i + '-' + j} x={j * c + (c - s) / 2} y={i * c + (c - s) / 2} width={s} height={s} fill={SERIES[0]}><title>{`${i + 1}–${j + 1}: p = ${p.toFixed(3)}`}</title></rect>; })}
    {ref.map(([i, j]) => <rect key={'r' + i} x={i * c} y={j * c} width={c} height={c} className="rna-dot-ref"/>)}
    {pairsOf(lower).map(([i, j]) => <rect key={'l' + i} x={i * c + c * 0.2} y={j * c + c * 0.2} width={c * 0.6} height={c * 0.6} fill={SERIES[1]}/>)}
  </svg>;
}

function Profile({values, label, unit, color = SERIES[0], raw}: {values: number[]; label: string; unit: string; color?: string; raw?: number[]}) {
  const W = 760, H = 150, l = 52, r = 12, t = 10, b = 26;
  const max = Math.max(...values, ...(raw ?? []), 1e-9), n = values.length;
  const x = (k: number) => l + (k + 0.5) * (W - l - r) / n, y = (v: number) => H - b - v / max * (H - t - b);
  return <svg className="rna-profile" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label}>
    <line x1={l} x2={W - r} y1={H - b} y2={H - b} className="mc-baseline"/>
    <text x={l - 6} y={t + 8} textAnchor="end" className="rna-tick">{fmt(max, 2)}</text><text x={l - 6} y={H - b} textAnchor="end" className="rna-tick">0</text>
    {raw && raw.map((v, k) => <rect key={k} x={x(k) - (W - l - r) / n / 2} width={Math.max(0.5, (W - l - r) / n)} y={y(v)} height={H - b - y(v)} fill={color} opacity="0.22"/>)}
    <path d={values.map((v, k) => (k ? 'L' : 'M') + x(k).toFixed(1) + ' ' + y(v).toFixed(1)).join('')} fill="none" stroke={color} strokeWidth="1.8"/>
    <text x={(l + W - r) / 2} y={H - 6} textAnchor="middle" className="rna-tick">{label}</text>
    <text transform={`translate(12 ${(t + H - b) / 2}) rotate(-90)`} textAnchor="middle" className="rna-tick">{unit}</text>
  </svg>;
}

function FoldView({catalog}: {catalog: any}) {
  const demo = catalog.fold.demo;
  const [seq, setSeq] = useState(demo.sequence), [ref, setRef] = useState(demo.structure), [samples, setSamples] = useState(1000), [seed, setSeed] = useState(1);
  const [res, setRes] = useState<any>(null), [busy, setBusy] = useState(''), [error, setError] = useState(''), [checks, setChecks] = useState<any>(null);
  const [view, setView] = useState<string>('mfe');
  async function run() {
    setBusy('Computing MFE, partition function, pair probabilities and ' + samples + ' sampled structures'); setError('');
    try { const r = await rpc<any>('rna_lab_fold', {sequence: seq, reference: ref.trim() || null, samples, seed}); setRes(r); setView('mfe'); }
    catch (e) { setError(String(e).replace(/^Error:\s*/, '')); } finally { setBusy(''); }
  }
  async function validate() {
    setBusy('Running folding validation (exhaustive enumeration, 1EHZ geometry, sampling)');
    try { setChecks(await rpc<any>('rna_lab_validate', {demo: 'fold'})); } catch (e) { setError(String(e)); } finally { setBusy(''); }
  }
  useEffect(() => { void run(); }, []);
  const shown = !res ? '' : view === 'mfe' ? res.mfe.structure : view === 'centroid' ? res.centroid.structure : view === 'reference' ? res.reference?.structure : res.alternativeStates[Number(view)]?.structure;
  const shownLabel = view === 'mfe' ? 'MFE structure' : view === 'centroid' ? 'Centroid (pairs with p > 0.5)' : view === 'reference' ? 'Reference (1EHZ cloverleaf)' : 'Sampled state ' + (Number(view) + 1);
  const acc = res?.reference && shown ? compare(shown, res.reference.structure) : null;
  const model = res?.model;
  return <div className="rna-grid">
    <aside className="mech-panel rna-side">
      <span className="eyebrow">Sequence</span>
      <textarea className="rna-seq" value={seq} onChange={e => setSeq(e.target.value)} rows={4} spellCheck={false} aria-label="RNA sequence"/>
      <span className="eyebrow">Reference dot-bracket (optional)</span>
      <textarea className="rna-seq" value={ref} onChange={e => setRef(e.target.value)} rows={3} spellCheck={false} aria-label="Reference structure"/>
      <p className="caption">{seq === demo.sequence ? demo.name + '. ' + demo.structureSource : 'Your sequence. Accuracy statistics appear only if you give a reference structure.'}</p>
      <div className="rna-fields">
        <label>Samples<input type="number" min={10} max={5000} value={samples} onChange={e => setSamples(Number(e.target.value))}/></label>
        <label>Seed<input type="number" value={seed} onChange={e => setSeed(Number(e.target.value))}/></label>
      </div>
      <div className="button-row">
        <button className="button primary" onClick={run} disabled={!!busy}><FlaskConical size={14}/>Fold</button>
        <button className="button" onClick={() => { setSeq(demo.sequence); setRef(demo.structure); }} disabled={!!busy}>tRNA-Phe demo</button>
      </div>
      <div className="rna-tools"><span className="eyebrow">Installed tools</span>
        <p><b>ViennaRNA</b> {catalog.tools.viennarna.installed ? 'v' + catalog.tools.viennarna.version : 'not installed here'}</p>
        <p><b>RNAstructure</b> {catalog.tools.rnastructure.installed ? 'installed' : 'not installed'}</p>
        <p className="caption">{catalog.tools.viennarna.note ?? ''} {catalog.tools.rnastructure.note ?? ''}</p>
      </div>
    </aside>

    <main className="mech-panel rna-main">
      <div className="rna-badges"><span className="evidence-badge">C · Statistically predicted / thermodynamic model</span><span className="rna-note">Equilibrium ensemble of an isolated RNA — not an observed in-cell structure</span></div>
      {busy && <div className="mech-busy"><LoaderCircle size={16} className="spin"/>{busy}…</div>}
      {error && <div className="mech-error" role="alert"><TriangleAlert size={15}/>{error}</div>}
      {res && <>
        <div className="cosmos-segment rna-views">
          <button className={view === 'mfe' ? 'active' : ''} onClick={() => setView('mfe')}>MFE</button>
          <button className={view === 'centroid' ? 'active' : ''} onClick={() => setView('centroid')}>Centroid</button>
          {res.reference && <button className={view === 'reference' ? 'active' : ''} onClick={() => setView('reference')}>Reference</button>}
          {res.alternativeStates.map((_: any, k: number) => <button key={k} className={view === String(k) ? 'active' : ''} onClick={() => setView(String(k))}>State {k + 1}</button>)}
        </div>
        <ArcDiagram seq={res.sequence} shown={shown} reference={view !== 'reference' ? res.reference?.structure : undefined} bpp={res.bpp} label={shownLabel}/>
        <p className="mono rna-db">{shown}</p>
        {res.reference && view !== 'reference' && <p className="caption rna-legend"><i className="hit"/>pair also in reference <i className="extra"/>predicted, not in reference <i className="missed"/>reference pair missed</p>}
        <div className="rna-two">
          <div><span className="eyebrow">Dot plot</span><DotPlot n={res.length} bpp={res.bpp} lower={shown} reference={res.reference?.structure}/>
            <p className="caption">Upper right: pair probability (area ∝ p). Lower left: {shownLabel.toLowerCase()} (orange){res.reference ? ', reference outline' : ''}.</p></div>
          <div><span className="eyebrow">Alternative states · {res.samples.count} samples, seed {res.samples.seed}</span>
            <div className="rna-states">{res.alternativeStates.map((s: any, k: number) => <button key={k} className={'rna-state' + (view === String(k) ? ' active' : '')} onClick={() => setView(String(k))}>
              <span className="rna-state-bar"><i style={{width: `${s.frequency * 100}%`}}/></span>
              <strong>State {k + 1} · {fmt(s.frequency * 100, 3)} % of samples</strong>
              <small>ΔG {fmt(s.energy, 3)} kcal/mol · {s.bpDistanceToMfe} bp from MFE · Boltzmann p of this exact structure {fmt(s.boltzmannProbability, 2)}</small></button>)}</div>
            <p className="caption">Distinct sampled structures grouped within {res.samples.clusterRadius} base pairs of a representative (stochastic backtracking, Ding &amp; Lawrence 2003). {res.samples.distinct} distinct structures sampled.</p>
          </div>
        </div>
        <span className="eyebrow">Probability each base is unpaired</span>
        <Profile values={res.unpaired} label="Nucleotide position" unit="P(unpaired)" color={SERIES[2]}/>
      </>}
    </main>

    <aside className="mech-panel rna-side">
      {res && <>
        <span className="eyebrow">Ensemble</span>
        <div className="rna-metrics">
          <Metric label="MFE" value={fmt(res.mfe.energy, 4) + ' kcal/mol'}/>
          <Metric label="Ensemble free energy" value={fmt(res.ensembleFreeEnergy, 4) + ' kcal/mol'}/>
          <Metric label="P(MFE structure)" value={fmt(res.mfeProbability, 3)}/>
          <Metric label="Ensemble diversity" value={fmt(res.ensembleDiversity, 3) + ' bp'}/>
        </div>
        {res.reference && <>
          <span className="eyebrow">Against the reference</span>
          <table className="rna-table"><thead><tr><th/><th>Sens.</th><th>PPV</th><th>F1</th></tr></thead><tbody>
            <tr><td>MFE</td><td>{fmt(res.reference.mfe.sensitivity)}</td><td>{fmt(res.reference.mfe.ppv)}</td><td>{fmt(res.reference.mfe.f1)}</td></tr>
            <tr><td>Centroid</td><td>{fmt(res.reference.centroid.sensitivity)}</td><td>{fmt(res.reference.centroid.ppv)}</td><td>{fmt(res.reference.centroid.f1)}</td></tr>
            {acc && view !== 'mfe' && view !== 'centroid' && view !== 'reference' && <tr><td>Shown</td><td>{fmt(acc.sensitivity)}</td><td>{fmt(acc.ppv)}</td><td>{fmt(acc.f1)}</td></tr>}
          </tbody></table>
          <p className="caption">Expected sensitivity Σp(reference pairs)/21 = {fmt(res.reference.expectedSensitivity, 3)}. The reference structure has ΔG {fmt(res.reference.energy, 3)} kcal/mol in this model and Boltzmann probability {fmt(res.reference.boltzmannProbability, 2)}.</p>
          {res.priorViennaReceipt && <p className="caption">Recorded prior run, not re-executed: {res.priorViennaReceipt.engine} gave MFE {fmt(res.priorViennaReceipt.mfeKcalMol, 3)} kcal/mol for this sequence. {res.backend === 'viennarna' ? (Math.abs(res.mfe.energy - res.priorViennaReceipt.mfeKcalMol) < 0.005 ? 'This local ViennaRNA run reproduces it.' : 'This local ViennaRNA run differs from it.') : 'Differences reflect the omitted energy terms below.'}</p>}
        </>}
        {res.comparison && <>
          <span className="eyebrow">Second method · same sequence</span>
          <table className="rna-table"><thead><tr><th/><th>MFE</th><th>G ens.</th><th>F1</th></tr></thead><tbody>
            {res.comparison.rows.map((r: any) => <tr key={r.backend}><td title={r.title}>{r.backend === 'viennarna' ? 'ViennaRNA' : 'Built-in'}</td><td>{fmt(r.mfe.energy, 3)}</td><td>{fmt(r.ensembleFreeEnergy, 4)}</td><td>{r.accuracy ? fmt(r.accuracy.f1, 3) : '—'}</td></tr>)}
          </tbody></table>
          <p className="caption">Energies in kcal/mol. The two MFE structures differ by {res.comparison.mfeBpDistance} base pairs. ViennaRNA uses the full Turner 2004 set with dangles; the built-in model is the reduced Turner 1999 subset.</p>
        </>}
        <span className="eyebrow">Model</span>
        <p className="caption"><b>{model.title}</b> · backend {res.backend} · {fmt(res.seconds, 2)} s · record <code>{res.recordSha256.slice(0, 12)}</code></p>
        {model.omitted && <p className="caption">Not modelled: {model.omitted.join('; ')}.</p>}
      </>}
      <button className="button" onClick={validate} disabled={!!busy}><ShieldCheck size={14}/>Run validation</button>
      <Checks checks={checks?.checks ?? null} runtime={checks?.runtime}/>
    </aside>
  </div>;
}

/* ---------------- Demo 4: translation ---------------- */

const LW = 760, LH = 120, LM = 20;

function Lane({frames, t, codons, footprint}: {frames: Frame[]; t: number; codons: number; footprint: number}) {
  const x = (c: number) => LM + c / codons * (LW - 2 * LM);
  const placed = ribosomesAt(frames, t);
  const tick = codons > 300 ? 100 : 50;
  return <svg className="rna-lane" viewBox={`0 0 ${LW} ${LH}`} role="img" aria-label={`${placed.length} ribosomes on the mRNA at t = ${t.toFixed(1)} s`}>
    <line x1={x(0)} x2={x(codons)} y1={70} y2={70} className="rna-mrna"/>
    <text x={x(0)} y={92} className="rna-tick">5′ AUG</text><text x={x(codons)} y={92} textAnchor="end" className="rna-tick">stop 3′</text>
    {Array.from({length: Math.floor(codons / tick)}, (_, k) => (k + 1) * tick).map(v => <g key={v}><line x1={x(v)} x2={x(v)} y1={66} y2={74} className="rna-mrna"/><text x={x(v)} y={108} textAnchor="middle" className="rna-tick">{v}</text></g>)}
    {placed.map(r => { const a = x(Math.max(0, r.codon - footprint + 1)), b = x(r.codon + 1); return <g key={r.id}>
      <rect x={a} y={46} width={Math.max(3, b - a)} height={22} rx={8} fill={SERIES[r.id % SERIES.length]} opacity={0.9} className={r.interpolated ? 'interp' : ''}/>
      <circle cx={x(r.codon + 0.5)} cy={70} r={2.6} fill="#fff"/></g>; })}
    <text x={LM} y={20} className="rna-caption-svg">{placed.length} ribosome{placed.length === 1 ? '' : 's'} · footprint {footprint} codons · white dot = A site</text>
  </svg>;
}

function TranslateView({catalog}: {catalog: any}) {
  const demo = catalog.translate.demo, d = catalog.translate.defaults;
  const [cds, setCds] = useState(demo.sequence);
  const [p, setP] = useState({initiation: d.initiation.value, elongation: d.elongation.value, termination: d.termination.value, footprint: d.footprint.value, tEnd: 7200, burnIn: 600, seed: 1});
  const [res, setRes] = useState<any>(null), [busy, setBusy] = useState(''), [error, setError] = useState(''), [checks, setChecks] = useState<any>(null);
  const [t, setT] = useState(0), [playing, setPlaying] = useState(false), raf = useRef(0);
  async function run() {
    setBusy('Simulating ribosome traffic (exact Gillespie events)'); setError(''); setPlaying(false);
    try { const r = await rpc<any>('rna_lab_translate', {sequence: cds === demo.sequence ? null : cds, ...p}); setRes(r); setT(0); setPlaying(true); }
    catch (e) { setError(String(e).replace(/^Error:\s*/, '')); } finally { setBusy(''); }
  }
  async function validate() {
    setBusy('Running translation validation against exact and mean-field TASEP results');
    try { setChecks(await rpc<any>('rna_lab_validate', {demo: 'translate'})); } catch (e) { setError(String(e)); } finally { setBusy(''); }
  }
  useEffect(() => { void run(); }, []);
  const frames: Frame[] = res?.playback.frames ?? [], end = frames.length ? frames[frames.length - 1].t : 0;
  useEffect(() => {
    if (!playing || !end) return;
    let last = performance.now();
    const step = (now: number) => { const dt = (now - last) / 1000; last = now; setT(v => { const nv = v + dt * 8; if (nv >= end) { setPlaying(false); return end; } return nv; }); raf.current = requestAnimationFrame(step); };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [playing, end]);
  const o = res?.outputs;
  const occ = useMemo(() => res ? smooth(res.occupancy, 9) : [], [res]);
  const field = (key: keyof typeof p, label: string, step = 'any') => <label>{label}<input type="number" step={step} value={p[key]} onChange={e => setP({...p, [key]: Number(e.target.value)})}/></label>;
  return <div className="rna-grid">
    <aside className="mech-panel rna-side">
      <span className="eyebrow">Coding sequence</span>
      <textarea className="rna-seq" value={cds} onChange={e => setCds(e.target.value)} rows={5} spellCheck={false} aria-label="Coding sequence"/>
      <p className="caption">{cds === demo.sequence ? demo.name + '. ' + demo.source : 'Your CDS: must start with AUG, end with a stop codon and contain no in-frame stop.'}</p>
      <div className="rna-fields">
        {field('initiation', 'Initiation α (1/s)')}{field('elongation', 'Elongation k (codons/s)')}
        {field('termination', 'Termination β (1/s)')}{field('footprint', 'Footprint (codons)', '1')}
        {field('tEnd', 'Simulated time (s)')}{field('burnIn', 'Burn-in (s)')}{field('seed', 'Seed', '1')}
      </div>
      <button className="button primary" onClick={run} disabled={!!busy}><FlaskConical size={14}/>Simulate</button>
      <div className="rna-provenance"><span className="eyebrow">Parameter sources</span>
        {(['elongation', 'footprint', 'initiation', 'termination'] as const).map(k => <p key={k} className="caption"><b>{k}</b> {d[k].value} {d[k].unit} — {d[k].source}</p>)}
        <p className="caption">Elongation is the same at every codon: no per-codon rate dataset with a citable source is bundled, so codon-dependent rates are not used.</p>
      </div>
    </aside>

    <main className="mech-panel rna-main">
      <div className="rna-badges"><span className="evidence-badge">B · Stochastic kinetic simulation</span><span className="evidence-badge rna-hyp">D · initiation &amp; termination rates hypothetical</span></div>
      {busy && <div className="mech-busy"><LoaderCircle size={16} className="spin"/>{busy}…</div>}
      {error && <div className="mech-error" role="alert"><TriangleAlert size={15}/>{error}</div>}
      {res && <>
        <Lane frames={frames} t={t} codons={res.playback.codons} footprint={res.playback.footprint}/>
        <div className="mech-playbar rna-playbar">
          <button className="story-play" onClick={() => { if (t >= end) setT(0); setPlaying(!playing); }} aria-label={playing ? 'Pause' : 'Play'}>{playing ? <Pause size={15}/> : <Play size={15}/>}</button>
          <input type="range" min={0} max={end} step={0.1} value={t} onChange={e => { setPlaying(false); setT(Number(e.target.value)); }} aria-label="Time"/>
          <span className="mono">t = {t.toFixed(1)} s</span>
          <span className="evidence-badge mech-quant">{frames.length} exact simulated states · motion between them is visual interpolation</span>
        </div>
        <span className="eyebrow">Ribosome density per codon (A site, time-averaged after burn-in)</span>
        <Profile values={occ} raw={res.occupancy} label="Codon" unit="ribosomes / codon"/>
        <p className="caption">Line: 9-codon rolling mean for readability; bars: raw per-codon density. With uniform rates the profile is flat apart from stochastic noise and the initiation region.</p>
        <span className="eyebrow">Protein production</span>
        <TimeChart time={res.production.time} timeUnit="s" unit="Proteins completed" series={[{id: 'p', label: 'Proteins', values: res.production.proteins}]}/>
      </>}
    </main>

    <aside className="mech-panel rna-side">
      {o && <>
        <span className="eyebrow">Steady state (after burn-in)</span>
        <div className="rna-metrics">
          <Metric label="Protein output" value={fmt(o.proteinRate, 3) + ' ± ' + fmt(o.proteinRateSE, 2) + ' /s'} note={fmt(o.proteinsPerHour, 3) + ' per hour per mRNA'}/>
          <Metric label="Mean-field prediction" value={o.meanFieldRate !== null ? fmt(o.meanFieldRate, 3) + ' /s' : '—'} note={o.phase}/>
          <Metric label="Ribosomes on the mRNA" value={fmt(o.meanRibosomes, 3)} note={fmt(o.ribosomesPer100Codons, 3) + ' per 100 codons'}/>
          <Metric label="Transit time" value={fmt(o.meanTransit, 4) + ' s'} note={'isolated ribosome: ' + fmt(o.isolatedTransit, 4) + ' s'}/>
          <Metric label="Contact events" value={String(o.collisions)} note={fmt(o.collisionsPerProtein, 3) + ' per protein; ribosome stalled behind another ' + fmt(o.blockedFraction * 100, 2) + ' % of the time'}/>
          <Metric label="Events simulated" value={o.events.toLocaleString()} note={res.inputs.codons + ' codons · ' + fmt(res.seconds, 2) + ' s compute'}/>
        </div>
        <p className="caption">A contact event is a ribosome closing up directly behind the next one (each re-closure counted). The Mechanistic Biology Lab turnover demo uses a hypothetical k_tl = 50 h⁻¹; this scenario gives {fmt(o.proteinsPerHour, 3)} h⁻¹, which is likewise conditional on the hypothetical initiation rate.</p>
        <p className="caption">Record <code>{res.recordSha256.slice(0, 12)}</code> · seed {res.inputs.seed}</p>
      </>}
      <button className="button" onClick={validate} disabled={!!busy}><ShieldCheck size={14}/>Run validation</button>
      <Checks checks={checks?.checks ?? null} runtime={checks?.runtime}/>
    </aside>
  </div>;
}

/** Analyse › RNA-to-Protein Laboratory: thermodynamic folding ensembles and stochastic translation, each from a validated computation. */
export default function RnaLab() {
  const [mode, setMode] = useState<Mode>('fold'), [catalog, setCatalog] = useState<any>(null), [error, setError] = useState('');
  useEffect(() => { rpc<any>('rna_lab_catalog', {}).then(setCatalog, e => setError(String(e).replace(/^Error:\s*/, ''))); }, []);
  return <div className="page-content rna-lab">
    <header className="mech-head">
      <div><span className="eyebrow">Living Biology Universe · RNA</span><h1>RNA-to-Protein Laboratory</h1>
        <p>Fold an RNA into its thermodynamic ensemble and watch ribosomes translate an mRNA — every number comes from a declared, validated computation.</p></div>
      <div className="cosmos-segment">
        <button className={mode === 'fold' ? 'active' : ''} onClick={() => setMode('fold')}>Folding ensemble</button>
        <button className={mode === 'kinetics' ? 'active' : ''} onClick={() => setMode('kinetics')}>Folding kinetics</button>
        <button className={mode === 'translate' ? 'active' : ''} onClick={() => setMode('translate')}>Translation</button>
        <button className={mode === 'story' ? 'active' : ''} onClick={() => setMode('story')}>Illustrated story</button>
      </div>
    </header>
    {error && <div className="mech-error" role="alert"><TriangleAlert size={15}/>{error}</div>}
    {!catalog && !error && <div className="mech-busy"><LoaderCircle size={16} className="spin"/>Opening the laboratory…</div>}
    {catalog && mode === 'fold' && <FoldView catalog={catalog}/>}
    {mode === 'kinetics' && <KineticsView/>}
    {catalog && mode === 'translate' && <TranslateView catalog={catalog}/>}
    {mode === 'story' && <div className="rna-story"><div className="rna-badges"><span className="evidence-badge rna-ill">E · Illustrative</span><span className="rna-note">A drawn story of gene expression. Shapes, counts and motion are schematic, not computed.</span></div><GeneStory/></div>}
  </div>;
}
