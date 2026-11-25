import {useCallback, useEffect, useState} from 'react';
import {rpc} from '../../lib/api';
import type {LpParticles} from './lightParticles';

export interface Pulse {start: number; duration: number; intensity: number}
export interface Program {pre: number; steps: [number, number][]}
export interface LpEvent {time: number; kind: string; scale: string; label: string; value: number}
export interface LpParam {key: string; value: number; unit: string; description: string; relativeSe?: number; ci95?: [number, number]; determined: boolean; atBound?: boolean; provenance: {kind: string; note: string}}
export interface LpCheck {name: string; passed: boolean | null; applicable: boolean; threshold: string; detail: string; value: any}
export interface LpFeature {label: string; unit: string; measured: number | null; predicted: number | null; supported: boolean; error?: number; relativeError?: number | null; note?: string | null}
export interface LpScore {id: string; name: string; kind: string; role?: string; supported?: boolean; reason?: string; replicates: {run: string; t: number[]; fl: number[]; rcv?: number[]; features?: Record<string, number | null>}[];
  models: Record<string, {t: number[]; fl: number[]; rmseLog10: number; foldError: number; features: Record<string, LpFeature>; interval?: {low: number[]; high: number[]; inside: number; total: number; coverage: number; note: string}}>;
  replicateSdLog10?: number; program: Program; led?: string; inputs?: {led: string; centroidNm: number | null; peak: number}[]; second?: {led: string; peak: number; perMinute?: number[]} | null}
export interface LpCatalog {
  engine: {name: string; version: string; numericalMethod: string; equations: string[]; assumptions: string[]; limits: string[]}; context: string;
  dataset: {sha256: string; source: Record<string, any>; system: Record<string, any>; units: Record<string, string>};
  schedules: {id: string; name: string; kind: string; role: string; runs: number; points: number; intensity?: number; program: Program; other: Record<string, Program>; led: string; second: string | null}[];
  models: Record<string, string>; selected: string; gate: {passed: boolean; statement: string; worstHeldOutRmseLog10: number; baselineRatio: number; thresholds: {rmseLog10: number; beatsBaselineBy: number}};
  summary: Record<string, Record<string, number>>; parameters: LpParam[]; measuredGrowth: {doublingMin: number; fittedDoublingMin: number; source: string};
  limits: {durationMin: [number, number]; intensity: [number, number]; steps: number; samples: number}; spatial: {statement: string; components: {quantity: string; where: string; interpretable: boolean; note: string}[]; mixing: {equilibrationMs: number; source: string}};
  training: {points: number; rmseLog10: number; starts: number}; learned: {lambda: number; features: string}; combined: {lambda: number};
  runnable: string[]; channels: LpChannel[]; stages: LpStages; regression: LpRegression; spectral: {sha256: string; design: Record<string, string>; green: {led: string; centroidNm: number}};
  state: {schema: string; version: number; variables: {key: string; name: string; unit: string; from: string; where: string}[]; clocks: {key: string; what: string; stepMin?: number; frames?: number}[]; handoffs: string[];
    phi: LpParticles['phi']; sensor: {copies: number; provenance: {kind: string; note: string}}};
}
/** Switching rates of one LED, calibrated on its action spectrum. */
export interface LpChannel {led: string; centroidNm: number | null; structure: 'none' | 'off' | 'on' | 'both'; structureName: string; k1: number; k2: number; rmseLog10: number; points: number; cvRmseLog10: Record<string, number>;
  published: {k1: number | null; k2: number | null}; ci95: {k1: [number, number]; k2: [number, number]} | null}
export interface LpStages {
  calibration: {data: string; leds: number; points: number; rmseLog10: number; greenChain: string; shortcutCheck: {maxRelativeDifference: number; passed: boolean; threshold: string}; greenSpectrum: {points: number; rmseLog10: number; note: string}};
  modelSelection: {method: string; structures: Record<string, number>; usedInFinalTest: Record<string, {structure: string; cvRmseLog10: Record<string, number>}>};
  finalTest: {schedules: string[]; status: string; untouched: boolean; statement: string; pooled: Record<string, number>; mixedColour: Record<string, number>; otherColour: Record<string, number>; coverage: {inside: number; total: number; coverage: number};
    failures: {id: string; name: string; foldError: number; replicateFold: number; coverage: number; why: string[]; features: Record<string, {relativeError: number | null; error: number | null; unit: string; supported: boolean}>}[]};
}
export interface LpRegression {case: string; schedules: string[]; greenOnlyFoldError: number; withRedFoldError: number; publishedFoldError: number; failureReproduced: boolean; improved: boolean; statement: string}
export interface LpRun {
  id: string; time: number[]; series: Record<string, number[]>; reference: {light: number[]; reporter: number[]; features: Record<string, number | null>} | null; measured: LpScore | null; model: string; modelName: string;
  record: any; sha256: string; seriesSha256: string; passed: boolean; checks: LpCheck[]; warnings: string[]; hasState?: boolean;
  reproduced?: {identical: boolean; statement: string; savedVersions: Record<string, string>; currentVersions: Record<string, string>};
}
export interface LpSaved {id: string; created: string; label: string; parent: string | null; passed: boolean; model: string; time: number; peak: number; sha256: string; schedule: string | null}
export interface LpBenchmark {schedules: Record<string, LpScore[]>; summary: Record<string, Record<string, number>>; intervalCoverage: Record<string, any>; selected: string; best: string; selectionNote: string; gate: LpCatalog['gate'];
  unsupported: {id: string; name: string; reason: string}[]; stages: LpStages; regression: LpRegression; publishedNote: string; greenOnlyNote: string}

export const DARK: Program = {pre: 0, steps: [[0, 0]]};
/** The LED offered in the editor besides green: red light, which switches the sensor off. */
export const RED = '660-LS';
const r1 = (v: number) => Math.round(v * 10) / 10;

/** Pulses → a step program. Throws a plain-language error when pulses overlap or are empty. */
export function pulsesToProgram(pulses: Pulse[], duration: number): Program {
  const edges: [number, number][] = [[0, 0]];
  for (const q of [...pulses].sort((a, b) => a.start - b.start)) {
    const a = r1(q.start), b = r1(q.start + q.duration);
    if (!(q.duration > 0) || a < 0) throw new Error('Each pulse needs a start at or after 0 and a positive duration.');
    if (a < edges[edges.length - 1][0]) throw new Error('Two pulses overlap. Move or shorten one of them.');
    if (a >= duration) continue;
    if (a === edges[edges.length - 1][0]) edges[edges.length - 1] = [a, q.intensity]; else edges.push([a, q.intensity]);
    edges.push([b, 0]);
  }
  return {pre: 0, steps: edges.filter(e => e[0] < duration || e[0] === 0)};
}
export function programAt(p: Program, t: number) { let v = p.pre; for (const [ts, val] of p.steps) { if (ts <= t + 1e-9) v = val; else break; } return v; }

/** State of the virtual light-pulse experiment: the catalogue, the program being edited, the current run and its comparisons. */
export function useLightPulse(active: boolean) {
  const [cat, setCat] = useState<LpCatalog | null>(null), [loading, setLoading] = useState(false), [error, setError] = useState('');
  const [pulses, setPulses] = useState<Pulse[]>([{start: 30, duration: 90, intensity: 5}]), [redPulses, setRedPulses] = useState<Pulse[]>([]), [particles, setParticles] = useState<LpParticles | null>(null), [baseParticles, setBaseParticles] = useState<LpParticles | null>(null), [duration, setDuration] = useState(480), [model, setModel] = useState('auto'), [samples, setSamples] = useState(60), [seed, setSeed] = useState(7);
  const [schedule, setSchedule] = useState(''), [label, setLabel] = useState(''), [parent, setParent] = useState<string | null>(null);
  const [result, setResult] = useState<LpRun | null>(null), [baseline, setBaseline] = useState<LpRun | null>(null), [busy, setBusy] = useState('');
  const [runs, setRuns] = useState<LpSaved[]>([]), [bench, setBench] = useState<LpBenchmark | null>(null), [sweep, setSweep] = useState<any>(null), [control, setControl] = useState<any>(null);

  useEffect(() => {
    if (!active || cat || loading) return;
    setLoading(true);
    rpc<LpCatalog>('light_pulse_catalog').then(async c => { setCat(c); setRuns(await rpc<LpSaved[]>('light_pulse_runs')); }).catch(e => setError(String(e?.message ?? e))).finally(() => setLoading(false));
  }, [active]);
  const guard = async (name: string, f: () => Promise<void>) => { setBusy(name); setError(''); try { await f(); } catch (e: any) { setError(String(e?.message ?? e)); } finally { setBusy(''); } };
  const chosen = cat?.schedules.find(s => s.id === schedule) ?? null;
  const program = useCallback((): Program => chosen ? chosen.program : pulsesToProgram(pulses, duration), [chosen, pulses, duration]);
  const total = chosen ? 480 : duration;
  /** Programs of the other LEDs: recorded ones for a measured schedule, the red pulses otherwise. */
  const other = useCallback((): Record<string, Program> => chosen ? chosen.other : redPulses.length ? {[RED]: pulsesToProgram(redPulses, duration)} : {}, [chosen, redPulses, duration]);
  const config = () => ({program: program(), other: other(), durationMin: total, preMin: chosen ? 480 : 0, samples, seed, schedule: schedule || null, reference: DARK});
  // molecule numbers of the current run and of the baseline as particles for the 3-D view
  const fetchParticles = (r: LpRun | null, set: (p: LpParticles | null) => void) => { let live = true; set(null); if (r?.hasState) rpc<LpParticles>('light_pulse_particles', {id: r.id}).then(p => { if (live) set(p); }).catch(() => undefined); return () => { live = false; }; };
  useEffect(() => fetchParticles(result, setParticles), [result?.id]);
  useEffect(() => fetchParticles(baseline, setBaseParticles), [baseline?.id]);
  // one scale for two views: both draw with the larger of the two weights, so equal dot counts mean equal molecule numbers
  useEffect(() => {
    if (!particles || !baseParticles || particles.weight === baseParticles.weight || !result || !baseline) return;
    const weight = Math.max(particles.weight, baseParticles.weight), low = particles.weight < weight ? {r: result, set: setParticles} : {r: baseline, set: setBaseParticles};
    let live = true; rpc<LpParticles>('light_pulse_particles', {id: low.r.id, weight}).then(p => { if (live) low.set(p); }).catch(() => undefined);
    return () => { live = false; };
  }, [particles?.weight, baseParticles?.weight, result?.id, baseline?.id]);

  const run = () => guard('run', async () => {
    const r = await rpc<LpRun>('light_pulse_simulate', {...config(), model, label: label || (chosen ? chosen.name : ''), parent});
    setResult(r); setRuns(await rpc<LpSaved[]>('light_pulse_runs'));
  });
  /** Reopen a saved experiment: it is recomputed from its saved configuration and compared with what was saved. */
  const open = (id: string) => guard('open', async () => {
    const r = await rpc<LpRun>('light_pulse_run_get', {id}), cfg = r.record.experiment.config;
    setResult(r); setDuration(cfg.durationMin); setModel(cfg.model); setSamples(cfg.samples); setSeed(cfg.seed); setLabel(cfg.label ?? ''); setParent(cfg.parent ?? null); setSchedule(cfg.schedule ?? '');
    if (!cfg.schedule) { const toPulses = (st: [number, number][]) => { const ps: Pulse[] = []; st.forEach(([t, v], i) => { if (v > 0) ps.push({start: t, duration: r1((st[i + 1]?.[0] ?? cfg.durationMin) - t), intensity: v}); }); return ps; };
      const ps = toPulses(cfg.program.steps); setPulses(ps.length ? ps : [{start: 30, duration: 60, intensity: 5}]); setRedPulses(toPulses(cfg.other?.[RED]?.steps ?? [])); }
    if (cfg.parent) { try { setBaseline(await rpc<LpRun>('light_pulse_run_get', {id: cfg.parent})); } catch { setBaseline(null); } } else setBaseline(null);
  });
  /** Keep the current run as the baseline and edit a variant of it. */
  const branch = () => { if (!result) return; setBaseline(result); setParent(result.id); setLabel(l => 'Variant of ' + (l || result.id.slice(0, 8))); setSchedule(''); };
  const endBranch = () => { setBaseline(null); setParent(null); };
  /** Run the same program through the green-only chain of version 1 and keep it as the baseline: what the other light changes. */
  const compareGreen = () => guard('green', async () => {
    if (!result) return;
    const cfg = result.record.experiment.config;
    const g = await rpc<LpRun>('light_pulse_simulate', {...cfg, model: 'green', label: 'Green-only model · ' + (cfg.label || result.id.slice(0, 8)), parent: null});
    setBaseline(g); setRuns(await rpc<LpSaved[]>('light_pulse_runs'));
  });
  const loadBench = () => bench || guard('bench', async () => setBench(await rpc<LpBenchmark>('light_pulse_benchmark')));
  const runSweep = (vary: 'intensity' | 'duration' | 'period', values: number[], base: Partial<Record<string, number>>) => guard('sweep', async () => setSweep(await rpc('light_pulse_sweep', {vary, values, ...base, durationMin: total, model})));
  const runControl = (target: number) => guard('control', async () => setControl(await rpc('light_pulse_control', {target, durationMin: total, seed})));

  return {cat, loading, error, setError, pulses, setPulses, redPulses, setRedPulses, other, particles, baseParticles, compareGreen, duration, setDuration, model, setModel, samples, setSamples, seed, setSeed, schedule, setSchedule, label, setLabel, parent, chosen, program, total,
    result, baseline, busy, runs, bench, sweep, control, run, open, branch, endBranch, loadBench, runSweep, runControl};
}
export type LightPulse = ReturnType<typeof useLightPulse>;

/** Modelled activity of each compartment of the illustrative cell at one time: regulator on the envelope, transcription at the nucleoid, reporter in the cytoplasm, each 0…1. */
export function activityAt(run: LpRun | null, cat: LpCatalog | null, t: number) {
  if (!run || !cat) return null;
  const k = Math.max(0, Math.min(run.time.length - 1, run.time.findIndex(v => v >= t - 1e-9) < 0 ? run.time.length - 1 : run.time.findIndex(v => v >= t - 1e-9)));
  const b = cat.parameters.find(p => p.key === 'b')!.value, A = cat.parameters.find(p => p.key === 'A')!.value, norm = (v: number | undefined) => v === undefined ? null : Math.max(0, Math.min(1, (v - b) / A));
  return {index: k, light: run.series.light[k], regulator: run.series.regulator?.[k] ?? null, transcription: norm(run.series.transcription?.[k]), reporter: norm(run.series.reporter[k]), reporterMEFL: run.series.reporter[k]};
}
