import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {Activity, Box, Camera as CameraIcon, Check, ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Columns2, Crosshair, Download, Eye, EyeOff, FlaskConical, GitBranch, Hexagon, Home, Info, Layers, Lightbulb, Link2, LoaderCircle, Maximize2, Microscope, Palette, PanelBottom, PanelLeft, PanelRight,
  Pause, Pin, Play, Plus, Route, Scissors, Sigma, SlidersHorizontal, Sparkles, Trash2, TriangleAlert, Waves, X, ZoomIn} from 'lucide-react';
import {exportFile, external, rpc} from '../../lib/api';
import type {AtomRecord, Item} from '../../lib/types';
import VolumeStage, {type Playback, type VolumeHandle, type VolumeView} from '../em/VolumeStage';
import {boxOf, cutBounds, toUm, viewOf, type Camera, type Vec3} from '../em/emGeometry';
import {describeAtom, fromAtomRecords, modelOf, SPECIES_COLORS, SPECIES_HEX, sphereModel, type Representation, type StructureData} from '../em/molecules';
import SyncChart, {type ChartEvent} from './SyncChart';
import {C, LightDock, LightDrawer, LightInputs} from './LightPulsePanels';
import {activityAt, useLightPulse} from './useLightPulse';
import {buildPlayback, countsAt, frameAt, PARTICLE_COLORS, type LpParticles} from './lightParticles';
import {classAt, clock, densityField, lastAtOrBefore, NM_PER_COPY_PER_UM3, pickCompartment, pickMolecule, SCALE_BARS, scaleLabel, type Grid} from './spatial';
import {DEFAULT_OPACITY, freshSpecies, fromConfig, hexToRgb, newKey, payload, ROD_OPACITY, type Catalog, type ClassInfo, type Conversion, type InputSpec, type Pair, type Region, type Species} from './spatialSetup';
import {EVENT_LABEL, useSpatialRun, type RunEvent, type SpatialRun} from './useSpatialRun';
import './workspace.css';

type Selection = {type: 'compartment'; cls: number; um: Vec3} | {type: 'molecule'; particle: number} | {type: 'event'; event: RunEvent} | {type: 'lightEvent'; event: {time: number; label: string; kind: string; scale: string; value: number}} | null;
type Drawer = 'parameters' | 'solver' | 'provenance' | 'diagnostics' | 'shortcuts' | null;
interface Painting {id: string; psfFwhmNm: number; size: [number, number]; pixelUm: [number, number]; composite: string; images: Record<string, string>; channels: Record<string, {stain: string; color: string}>; evidence: {statement: string}; limitations: string[]}
interface Registry {contexts: {id: string; name: string; role: string; species: string; cellType: string; state: string; geometry: {kind: string; label: string; detail: string}; measurements: {name: string; state: string; evidence: string | null; source: string | null}[];
  models: {id: string; name: string; calibration: string}[]; experiments: Record<string, {supported: boolean; missing: string[]; note?: string}>; validation: {what: string; result: string; kind: string}[]; qualified: string[]}[]; experiments: Record<string, string>; rule: string; identity: string}
export interface WorkspaceRequest {item?: Item; run?: string; event?: number; lightRun?: string; n: number}

const SLAB = 50, HELA = 'hela-jrc_hela-2', ECOLI = 'ecoli-bw29655-ccasr';
const num = (v: number | null | undefined, d = 3) => v == null || !Number.isFinite(v) ? '–' : Math.abs(v) >= 1e5 || (Math.abs(v) < 1e-3 && v !== 0) ? v.toExponential(2).replace('e+', 'e') : Number(v.toPrecision(d)).toString();
/** A changed input in words: numbers as they are, rules as "a=1, b=2" lines rather than raw JSON. */
const show = (v: unknown): string => v == null ? '–' : Array.isArray(v) ? (v.length ? v.map(show).join(' · ') : 'none') : typeof v === 'object' ? Object.entries(v as object).map(([k, x]) => `${k} ${typeof x === 'object' && x ? JSON.stringify(x) : x}`).join(', ') : String(v);
async function inflate(base64: string) {
  const raw = atob(base64), bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
  return new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer());
}
const EVIDENCE: Record<string, {label: string; cls: string; title: string}> = {
  em: {label: 'Measured EM', cls: 'measured', title: 'Category A: the electron-microscopy signal of one fixed cell.'},
  seg: {label: 'ML segmentation', cls: 'segmented', title: 'Compartment classes are machine-learning segmentations of the image, not manual ground truth.'},
  illustrative: {label: 'Illustrative geometry', cls: 'illustrative', title: 'Category E: drawn from typical dimensions. It is not an image of any cell.'},
  motion: {label: 'Simulated motion', cls: 'modeled', title: 'Category B: Brownian dynamics of point particles; every rate is an assumption unless stated.'},
  field: {label: 'Modelled concentration', cls: 'modeled', title: 'Time-averaged density of the simulated copies. A model output, not a measurement.'},
  activity: {label: 'Predicted response', cls: 'predicted', title: 'Model quantities painted onto compartments. The readout was measured for the whole cell only.'},
  stain: {label: 'Synthetic image', cls: 'synthetic', title: 'Category D: a forward model of Cell Painting stains from the segmentation, not a photograph.'},
};
const Tag = ({k}: {k: keyof typeof EVIDENCE}) => <span className={'ws-tag ' + EVIDENCE[k].cls} title={EVIDENCE[k].title}>{EVIDENCE[k].label}</span>;

/**
 * Cell Explorer › Workspace: one place to open a cell, explore it, run an experiment in it, follow what happens and
 * compare runs. The viewport is the centre; layers, experiment inputs, the inspector, the timeline and the drawers
 * arrange themselves around what is being done.
 */
export default function CellWorkspace({structure, structures = [], request, onViewResults}: {structure?: {name: string; atoms: AtomRecord[]; asset?: string; sha256?: string} | null; structures?: Item[]; request?: WorkspaceRequest | null; onViewResults?: (run: string, source?: string) => void}) {
  const [catalog, setCatalog] = useState<Catalog | null>(null), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [contextId, setContextId] = useState(HELA), [experiment, setExperiment] = useState<'spatial' | 'light'>('spatial');
  const [installing, setInstalling] = useState(false), [loaded, setLoaded] = useState(0);
  const [registry, setRegistry] = useState<Registry | null>(null), [registration, setRegistration] = useState<any>(null);
  const stage = useRef<VolumeHandle>(null), stageB = useRef<VolumeHandle>(null), grid = useRef<Grid | null>(null), slabs = useRef<{kind: 'em' | 'classes'; z0: number; z1: number; bytes: Uint8Array}[]>([]);
  const [left, setLeft] = useState(() => window.innerWidth > 1100), [right, setRight] = useState(() => window.innerWidth > 1700), [dock, setDock] = useState(true), [pinned, setPinned] = useState(false), [drawer, setDrawer] = useState<Drawer>(null);
  const [leftTab, setLeftTab] = useState<'layers' | 'experiment'>('layers'), [dockTab, setDockTab] = useState('results');
  const [view, setView] = useState({mode: 'organelles' as VolumeView['mode'], cut: {axis: 1, at: 0.45}, face: true, invert: false, tint: 0.55, gain: 1, quality: 'balanced' as VolumeView['quality'], bounds: true, trail: true});
  const [clip, setClip] = useState<{lo: Vec3; hi: Vec3}>({lo: [0, 0, 0], hi: [1, 1, 1]}), [clipOpen, setClipOpen] = useState(false);
  const [hidden, setHidden] = useState<Set<string>>(new Set(['outside', 'cytosol'])), [opacity, setOpacity] = useState<Record<string, number>>({}), [isolated, setIsolated] = useState<string | null>(null);
  const [field, setField] = useState<{on: boolean; species: number; max: number}>({on: false, species: -1, max: 0});
  const [pxPerMicron, setPxPerMicron] = useState(10), [hover, setHover] = useState<Vec3 | null>(null), [atomic, setAtomic] = useState(0), [cam, setCam] = useState<Camera | null>(null);
  const [selection, setSelection] = useState<Selection>(null), [followed, setFollowed] = useState<number | null>(null), [atom, setAtom] = useState<{particle: number; atom: number} | null>(null), [representation, setRepresentation] = useState<Representation>('atoms');
  const [species, setSpecies] = useState<Species[]>([]), [pairs, setPairs] = useState<Pair[]>([]), [conversions, setConversions] = useState<Conversion[]>([]), [globals, setGlobals] = useState<Record<string, string>>({});
  const [placing, setPlacing] = useState<number | null>(null), [label, setLabel] = useState(''), [parent, setParent] = useState<string | null>(null), [preview, setPreview] = useState(false);
  const [paused, setPaused] = useState(false), [speed, setSpeed] = useState(1), [t, setT] = useState(0), [compare, setCompare] = useState(false), [comparison, setComparison] = useState<any>(null);
  const [busy, setBusy] = useState(''), [painting, setPainting] = useState<Painting | null>(null), [channels, setChannels] = useState<Set<string>>(new Set()), [replicates, setReplicates] = useState<any>(null), [sweep, setSweep] = useState<any>(null), [crowding, setCrowding] = useState<any>(null);
  const [regions, setRegions] = useState<Region[]>([]), [detail, setDetail] = useState<string | null>(null), [level, setLevel] = useState('s2');
  const [lpT, setLpT] = useState(0), [lpPlaying, setLpPlaying] = useState(false), [lpSpeed, setLpSpeed] = useState(30);

  const ctx = catalog?.contexts.find(c => c.id === contextId) ?? null, meta = ctx?.meta ?? null;
  const main = useSpatialRun(meta?.sizeUm ?? null), base = useSpatialRun(meta?.sizeUm ?? null);
  const lp = useLightPulse(experiment === 'light');
  const live = main.live, results = live?.chunk.species ?? [];
  const list: ClassInfo[] = meta?.classes ?? [];
  const nameOf = (key: string) => key === 'edge' ? 'Edge of the volume' : list.find(c => c.key === key)?.name ?? key;
  const root = useRef<HTMLDivElement>(null);
  const narrow = () => (root.current?.clientWidth ?? 2000) < 1000;
  useEffect(() => { if (right && left && narrow()) setLeft(false); }, [right]);
  useEffect(() => { if (left && right && narrow() && !pinned) setRight(false); }, [left]);
  const say = (text: string) => { setNotice(text); window.setTimeout(() => setNotice(n => n === text ? '' : n), 4200); };
  const fail = (e: any) => setError(String(e?.message ?? e));

  const loadedData = useMemo(() => structure ? fromAtomRecords(structure.atoms) : null, [structure]);
  const radiusOf = (d: StructureData) => { const n = d.element.length, c = [0, 0, 0]; let q = 0;
    for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) c[k] += d.xyz[i * 3 + k] / n;
    for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) q += (d.xyz[i * 3 + k] - c[k]) ** 2;
    return Math.sqrt(5 / 3 * q / n) / 10; };

  useEffect(() => { rpc<Catalog>('cell_em_catalog').then(c => { setCatalog(c); setRegions(c.regions ?? []); }).catch(fail); rpc<Registry>('vcell_contexts').then(setRegistry).catch(() => {}); }, []);
  // Each context keeps its own calibrated defaults.
  useEffect(() => { if (catalog && ctx) setGlobals(Object.fromEntries(catalog.inputs.map(s => [s.key, String(s.key === 'slowdown' ? ctx.defaults.slowdown.value : s.default)]))); }, [catalog, contextId]);
  useEffect(() => {                                              // start with the structure open in the viewer, else GFP
    if (!catalog || species.length || request?.item || request?.run) return;
    const gfp = catalog.molecules.find(m => m.id === 'gfp')!;
    setSpecies([loadedData && structure ? {...freshSpecies(catalog, 'loaded', structure.name, radiusOf(loadedData), loadedData, 'Open in the Molecular Laboratory. Radius from its coordinates (sphere with the same radius of gyration).'), asset: structure.asset, sha256: structure.sha256}
      : freshSpecies(catalog, 'preset:gfp', gfp.name, gfp.radiusNm, null, gfp.note)]);
  }, [catalog, loadedData]);

  // ---- volume: progressive loading, whole-cell classes first so the cell appears early, then the image
  const total = meta ? Math.ceil(meta.dims[2] / SLAB) * (ctx!.hasImage ? 2 : 1) : 0;
  useEffect(() => {
    if (!meta || !ctx) return;
    let cancelled = false; slabs.current = []; grid.current = null; setLoaded(0);
    const all = new Uint8Array(meta.dims[0] * meta.dims[1] * meta.dims[2]);
    (async () => {
      for (const kind of (ctx.hasImage ? ['classes', 'em'] : ['classes']) as ('classes' | 'em')[]) for (let z0 = 0; z0 < meta.dims[2]; z0 += SLAB) {
        const z1 = Math.min(meta.dims[2], z0 + SLAB);
        const bytes = await inflate((await rpc<{data: string}>('cell_em_volume', {kind, z0, z1, context: contextId})).data);
        if (cancelled) return;
        if (kind === 'classes') all.set(bytes, z0 * meta.dims[0] * meta.dims[1]);
        slabs.current.push({kind, z0, z1, bytes}); stage.current?.upload(kind, z0, z1, bytes); stageB.current?.upload(kind, z0, z1, bytes); setLoaded(n => n + 1);
        if (kind === 'classes' && z1 === meta.dims[2]) grid.current = {dims: meta.dims, sizeUm: meta.sizeUm, classes: all};
      }
    })().catch(e => !cancelled && fail(e));
    return () => { cancelled = true; };
  }, [contextId, meta?.dims[0]]);
  const lightSplit = experiment === 'light' && !!lp.baseline && lp.baseline.id !== lp.result?.id;
  useEffect(() => { if (compare || lightSplit) window.setTimeout(() => { slabs.current.forEach(s => stageB.current?.upload(s.kind, s.z0, s.z1, s.bytes)); const c = stage.current?.getCamera(); if (c) stageB.current?.setCamera(c); }, 60); }, [compare, lightSplit, contextId, loaded]);
  // A context switch starts clean: its own layers, no run from the other cell.
  useEffect(() => {
    main.reset(); base.reset(); setCompare(false); setComparison(null); setSelection(null); setFollowed(null); setPreview(false); setParent(null); setPainting(null); setDetail(null); stage.current?.setDetail(null);
    setHidden(new Set(contextId === HELA ? ['outside', 'cytosol'] : ['outside'])); setOpacity({}); setIsolated(null);
    setView(v => ({...v, mode: 'organelles', cut: {axis: contextId === HELA ? 1 : 2, at: contextId === HELA ? 0.45 : 0.5}}));
    setSpecies(sp => sp.map(s => ({...s, release: {compartment: 'cytosol'}, target: '', exchangeThrough: '', exchangeTo: ''})));
    if (contextId !== ECOLI) setExperiment('spatial');
    stage.current?.home();
  }, [contextId]);

  const opacityOf = (c: ClassInfo) => hidden.has(c.key) || (isolated && isolated !== c.key) ? 0 : opacity[c.key] ?? (contextId === HELA ? DEFAULT_OPACITY : ROD_OPACITY)[c.key] ?? 0.8;
  const lightNow = experiment === 'light' ? activityAt(lp.result, lp.cat, lpT) : null, lightBase = experiment === 'light' && lp.baseline ? activityAt(lp.baseline, lp.cat, lpT) : null;
  const activityOf = (a: typeof lightNow) => { const out = new Array(16).fill(0); if (a) list.forEach(c => { out[c.id] = c.key === 'pm' ? a.regulator ?? 0 : c.key === 'chromatin' ? a.transcription ?? 0 : c.key === 'cytosol' ? a.reporter ?? 0 : 0; }); return out; };
  const stageView = useMemo<VolumeView>(() => {
    const paint = list.map(c => { const out: Vec3 = [0, 0, 0]; for (const ch of Object.values(catalog?.painting ?? {})) { const w = ch.weights[c.key] ?? 0, col = hexToRgb(ch.color); for (let i = 0; i < 3; i++) out[i] += w * col[i]; } return out; });
    return {...view, clip, show: list.map(opacityOf), colors: list.map(c => hexToRgb(c.color)), paint, selected: selection?.type === 'compartment' ? selection.cls : -1, hasImage: !!ctx?.hasImage,
      field: field.on ? {gain: 26, color: field.species >= 0 ? SPECIES_COLORS[field.species % 4] : [0.45, 0.95, 1]} : null, activity: activityOf(lightNow), activityColor: [0.35, 1, 0.55]};
  }, [view, clip, hidden, opacity, isolated, list, catalog, selection, field.on, field.species, ctx?.hasImage, lightNow?.index, lp.result?.id, experiment]);
  const stageViewB = useMemo<VolumeView>(() => ({...stageView, activity: activityOf(lightBase), selected: -1, field: null}), [stageView, lightBase?.index, lp.baseline?.id]);

  // ---- structures
  async function readAsset(item: Item) {
    const r = await rpc<any>('cell_em_structure', {asset: item.data.asset});
    return {data: r as StructureData, asset: item.data.asset as string, sha256: r.sha256 as string, name: item.name, radiusNm: (r.radiusNm as number).toFixed(2),
      note: `${r.kind === 'other' ? 'Structure' : r.kind[0].toUpperCase() + r.kind.slice(1)} · ${r.atoms.toLocaleString()} heavy atoms${r.drawnEvery > 1 ? ` (every ${r.drawnEvery}th drawn)` : ''}, ${r.residueCount.toLocaleString()} residues, ${r.chains.length} chain${r.chains.length === 1 ? '' : 's'}, ≈ ${num(r.heavyAtomMassKDa)} kDa · file SHA-256 ${r.sha256.slice(0, 10)}… ${r.radiusNote}`};
  }
  const patch = (key: number, change: Partial<Species>) => setSpecies(all => all.map(s => s.key === key ? {...s, ...change} : s));
  async function choose(s: Species, source: string) {
    if (!catalog) return;
    if (source === 'loaded' && loadedData && structure) return patch(s.key, {source, name: structure.name, radiusNm: radiusOf(loadedData).toFixed(2), data: loadedData, asset: structure.asset, sha256: structure.sha256, note: 'Open in the Molecular Laboratory. Radius from its coordinates.'});
    if (source.startsWith('preset:')) { const m = catalog.molecules.find(m => 'preset:' + m.id === source)!; return patch(s.key, {source, name: m.name, radiusNm: String(m.radiusNm), data: null, asset: undefined, sha256: undefined, note: m.note}); }
    const item = structures.find(i => 'asset:' + i.data?.asset === source);
    if (!item) return;
    patch(s.key, {busy: true}); setError('');
    try { patch(s.key, {busy: false, source, ...(await readAsset(item))}); say(`${item.name} is ready to place.`); }
    catch (e: any) { patch(s.key, {busy: false}); setError(`${item.name}: ${String(e?.message ?? e)}`); }
  }
  /** Add to Cell: bring one saved structure in and go straight to placement. */
  useEffect(() => {
    const item = request?.item;
    if (!catalog || !item) return;
    if (!item.data?.asset) { setError(`${item.name} has no saved coordinates yet. Predict its structure first, then use Add to Cell on the result.`); return; }
    setExperiment('spatial'); setLeft(true); setLeftTab('experiment'); setError('');
    void readAsset(item).then(r => {
      const s = {...freshSpecies(catalog, 'asset:' + r.asset, r.name, Number(r.radiusNm), r.data, r.note), asset: r.asset, sha256: r.sha256};
      setSpecies(all => all.some(x => x.asset === r.asset) ? all : all.length >= catalog.limits.species ? [...all.slice(0, -1), s] : [...all.filter(x => x.source !== 'preset:gfp' || all.length > 1), s]);
      setView(v => ({...v, cut: {...v.cut, axis: v.cut.axis < 0 ? 1 : v.cut.axis}})); setPlacing(s.key); say(`${r.name} added. Click the cut face to choose where it starts, or pick a compartment.`);
    }).catch(e => setError(`${item.name}: ${String(e?.message ?? e)} Supported: PDB and mmCIF coordinate files saved in the library.`));
  }, [request?.n, !catalog]);
  /** Open 3D Run: rebuild a saved experiment from its configuration and replay it; the same seed reproduces every frame. */
  useEffect(() => {
    if (!catalog || !request?.run) return;
    let cancelled = false;
    (async () => {
      const rec = await rpc<any>('cell_em_run_get', {id: request.run}), cfg = rec.experiment.config, cid = cfg.context ?? HELA;
      const assets = await Promise.all(cfg.species.map(async (c: any) => { const item = c.structure && structures.find(i => i.data?.asset === c.structure); try { return item ? await readAsset(item) : null; } catch { return null; } }));
      if (cancelled) return;
      const setup = fromConfig(cfg, assets), g = Object.fromEntries(catalog.inputs.map(x => [x.key, String(cfg[x.key])]));
      setExperiment('spatial'); if (cid !== contextId) setContextId(cid);
      window.setTimeout(() => {                                 // after the context's own reset
        if (cancelled) return;
        setSpecies(setup.species); setPairs(setup.pairs); setConversions(setup.conversions); setGlobals(g); setLabel(cfg.label ?? ''); setParent(cfg.parent ?? null);
        const ev = request.event != null ? rec.outputs.pairEvents?.[request.event] ?? null : null;
        start(setup.species, setup.pairs, setup.conversions, g, cfg.label ?? '', cfg.parent ?? null, ev, cid);
        say(`Replaying saved run ${String(request.run).slice(0, 8)} from its configuration${ev ? ', then jumping to the chosen event' : ''}.`);
      }, 60);
    })().catch(e => !cancelled && fail(e));
    return () => { cancelled = true; };
  }, [request?.n, !catalog]);
  /** Open a saved light-pulse experiment from Virtual Cell. */
  useEffect(() => { if (catalog && request?.lightRun) { setContextId(ECOLI); window.setTimeout(() => { setExperiment('light'); setLeft(true); setLeftTab('experiment'); setDock(true); setDockTab('response'); lp.open(request.lightRun!); }, 80); } }, [request?.n, !catalog]);

  // ---- spatial run
  const colorOf = (i: number) => SPECIES_COLORS[i % SPECIES_COLORS.length];
  const models = (run: SpatialRun, target: VolumeHandle | null, rep: Representation) => target?.setModels(run.run.current.data.map((d, i) => d ? modelOf(d, colorOf(i), rep) : sphereModel(run.run.current.radii[i] || 1, colorOf(i))));
  function start(sp: Species[], pr: Pair[], cv: Conversion[], g: Record<string, string>, lab: string, par: string | null, jump: RunEvent | null = null, cid = contextId) {
    setError(''); setComparison(null); setCompare(false); base.reset(); setSelection(null); setFollowed(null); setAtom(null); setPreview(false); setReplicates(null); setSweep(null);
    main.launch(payload(cid, sp, pr, cv, g, lab, par), sp.map(s => s.data), sp.map(s => Number(s.radiusNm)), jump);
    window.setTimeout(() => models(main, stage.current, representation), 0);
    setPaused(false); setT(0); setDock(true); setDockTab('results'); stage.current?.inspect(null);
  }
  const run = () => { start(species, pairs, conversions, globals, label, parent); say('Released. The first frames are being computed.'); };
  async function previewPlacement() {
    if (!meta) return;
    main.reset(); setError(''); setBusy('preview');
    try {
      const r = await rpc<{owner: number[]; frames: number[][]; absent: number[][]}>('cell_em_simulate', {...payload(contextId, species, pairs, conversions, globals, label, parent), preview: true});
      const box = boxOf(meta.sizeUm), n = r.owner.length, w = new Float32Array(n * 3), st = new Uint8Array(n);
      for (let i = 0; i < n; i++) for (let k = 0; k < 3; k++) w[i * 3 + k] = (r.frames[0][i * 3 + k] / meta.sizeUm[k] * 2 - 1) * box[k];
      r.absent?.[0]?.forEach(i => { st[i] = 3; });
      Object.assign(main.run.current, {data: species.map(s => s.data), radii: species.map(s => Number(s.radiusNm))}); models(main, stage.current, representation);
      main.playback.current = {frames: [w], state: [st], pairs: [new Int32Array(0)], owner: Uint8Array.from(r.owner), colors: species.map((_, i) => colorOf(i)), index: 0, dirty: true, playing: false};
      setPreview(true); say(`${n - (r.absent?.[0]?.length ?? 0)} start positions shown. Nothing has moved yet.`);
    } catch (e: any) { fail(e); } finally { setBusy(''); }
  }
  useEffect(() => { if (main.run.current.data.length) models(main, stage.current, representation); if (base.run.current.data.length) models(base, stageB.current, representation); }, [representation]);

  // The clock: the primary run advances frame by frame; everything else (second view, charts, markers) follows its simulated time.
  const playing = main.running && !paused && experiment === 'spatial';
  useEffect(() => {
    main.playback.current.playing = playing; base.playback.current.playing = playing && compare;
    if (!playing) return;
    const id = window.setInterval(() => {
      const p = main.playback.current;
      if (p.index < p.frames.length - 1) { p.index++; p.dirty = true; const now = main.timeNow(); main.mark(now); if (compare) { base.seek(now); base.mark(now); } if (p.index % 4 === 0) setT(now); }
      if (p.frames.length - p.index < main.fps * 1.5) void main.pump(main.run.current.token);
      if (compare && base.playback.current.frames.length && (base.run.current.times[base.run.current.times.length - 1] ?? 0) < main.timeNow() + 0.05) void base.pump(base.run.current.token);
      const j = main.run.current.jump;
      if (j && j.time <= main.timeNow()) { main.run.current.jump = null; goToEvent(j); }
    }, 1000 / (main.fps * speed));
    return () => window.clearInterval(id);
  }, [playing, main.fps, speed, compare]);
  const seekTo = useCallback((time: number) => {
    setPaused(true);
    if (!main.seek(time)) say('That moment is no longer in memory. Restart the run to replay it; the same seed reproduces it.');
    const now = main.timeNow(); main.mark(now); if (compare) { base.seek(now); base.mark(now); } setT(now);
  }, [compare]);
  const step = (by: number) => { const p = main.playback.current; setPaused(true); p.index = Math.max(0, Math.min(p.frames.length - 1, p.index + by)); p.dirty = true; const now = main.timeNow(); main.mark(now); if (compare) base.seek(now); setT(now); };
  function goToEvent(e: RunEvent) {
    seekTo(e.time); setSelection({type: 'event', event: e}); setRight(true);
    const who = stage.current?.inspect(e.b != null ? [e.a, e.b] : [e.a]) ?? null; setFollowed(who); setAtom(null);
  }
  function follow(particle: number | null) {
    if (particle === null) { stage.current?.inspect(null); setFollowed(null); setAtom(null); return; }
    setFollowed(stage.current?.inspect([particle]) ?? null); setAtom(null);
  }
  // ---- concentration field, refreshed as the run plays
  useEffect(() => {
    if (!field.on || !meta || !main.playback.current.frames.length) { stage.current?.setField(null); return; }
    const p = main.playback.current, i1 = p.index, i0 = Math.max(0, i1 - 23), k = Math.max(1, Math.round(Math.max(...meta.dims) / 96));
    const dims = meta.dims.map(d => Math.max(4, Math.round(d / k))) as Vec3;
    const f = densityField(p.frames.slice(i0, i1 + 1), p.state.slice(i0, i1 + 1), i => field.species < 0 || p.owner[i] === field.species, boxOf(meta.sizeUm), meta.sizeUm, dims);
    stage.current?.setField(dims, f.bytes); if (Math.abs(f.maxPerUm3 - field.max) > field.max * 0.05) setField(v => ({...v, max: f.maxPerUm3}));
  }, [field.on, field.species, t, main.frames, contextId]);

  // ---- comparison: the baseline is replayed in a second view under the same camera, cut, layers and time
  async function openCompare() {
    if (!parent || !live) return;
    setBusy('compare'); setError('');
    try {
      const rec = await rpc<any>('cell_em_run_get', {id: parent}), cfg = rec.experiment.config;
      const assets = await Promise.all(cfg.species.map(async (c: any) => { const item = c.structure && structures.find(i => i.data?.asset === c.structure); try { return item ? await readAsset(item) : null; } catch { return null; } }));
      setCompare(true); setDock(true); setDockTab('compare');
      window.setTimeout(() => {
        slabs.current.forEach(s => stageB.current?.upload(s.kind, s.z0, s.z1, s.bytes));
        base.launch(cfg, assets.map(a => a?.data ?? null), cfg.species.map((c: any) => c.radiusNm));
        models(base, stageB.current, representation);
        const c = stage.current?.getCamera(); if (c) stageB.current?.setCamera(c);
      }, 80);
      setComparison(await rpc('cell_em_compare', {baseline: parent, variant: live.chunk.id, chunks: 4}));
      say('Baseline on the left, variant on the right. Camera, cut and time move together.');
    } catch (e: any) { fail(e); } finally { setBusy(''); }
  }
  const branch = () => { if (!live) return; setParent(live.chunk.id); setLabel(l => 'Variant of ' + (l || live.chunk.id.slice(0, 8))); main.stop(); setLeft(true); setLeftTab('experiment'); say('This run is now the baseline. Change one thing, then release again.'); };

  // ---- other actions
  async function install() { setInstalling(true); setError(''); try { await rpc('cell_em_install', {confirm: true}); const c = await rpc<Catalog>('cell_em_catalog'); setCatalog(c); say('The cell volume is installed.'); } catch (e: any) { fail(e); } finally { setInstalling(false); } }
  async function paintCell() {
    setBusy('paint'); setError('');
    try { const p = await rpc<Painting>('cell_em_paint', {psfNm: 250, molecules: main.run.current.lastUm.length ? main.run.current.lastUm : null}); setPainting(p); setChannels(new Set(Object.keys(p.images))); setDock(true); setDockTab('painting'); say('Five channels and the merged image are below.'); }
    catch (e: any) { fail(e); } finally { setBusy(''); }
  }
  async function loadRegion(centre: Vec3) {
    setBusy('region'); setError('');
    try { const r = await rpc<Region>('cell_em_region', {level, centerUm: centre, confirm: true}); setRegions(rs => [...rs.filter(x => x.id !== r.id), r]); await showRegion(r); }
    catch (e: any) { fail(e); } finally { setBusy(''); }
  }
  async function showRegion(r: Region) {
    stage.current?.setDetail({dims: r.dims, originUm: r.originUm, sizeUm: r.sizeUm}); setDetail(r.id);
    for (let z0 = 0; z0 < r.dims[2]; z0 += 64) { const z1 = Math.min(r.dims[2], z0 + 64); stage.current?.uploadDetail(z0, z1, await inflate((await rpc<{data: string}>('cell_em_volume', {kind: 'region', id: r.id, z0, z1})).data)); }
    const mid = r.originUm.map((v, i) => v + r.sizeUm[i] / 2) as Vec3;
    setView(v => ({...v, mode: 'organelles', face: true, cut: {axis: 1, at: mid[1] / meta!.sizeUm[1]}})); stage.current?.flyTo(mid, Math.max(r.sizeUm[0], r.sizeUm[2]) * 1.1);
    say(`Detail loaded at ${Math.round(r.voxelUm[0] * 1000)} nm voxels. It shows on the cut face inside the marked region.`);
  }
  const snapshot = () => { const url = stage.current?.snapshot(); if (url) void exportFile('cell-view.png', {base64: url.split(',')[1]}); };
  async function runReplicates() { if (!live) return; setBusy('replicates'); try { setReplicates(await rpc('cell_em_replicates', {id: live.chunk.id, seeds: 5, chunks: 3})); } catch (e: any) { fail(e); } finally { setBusy(''); } }
  async function runSweep(parameter: string, values: number[]) { if (!live) return; setBusy('sweep'); try { setSweep(await rpc('cell_em_sweep', {id: live.chunk.id, parameter, values, chunks: 2})); } catch (e: any) { fail(e); } finally { setBusy(''); } }
  async function runCrowding() { setBusy('crowding'); try { setCrowding(await rpc('cell_em_crowding', {volumeFraction: 0.1, crowderRadiusNm: 5, tracerRadiusNm: Number(species[0]?.radiusNm) || 2.8})); } catch (e: any) { fail(e); } finally { setBusy(''); } }
  useEffect(() => { if ((drawer === 'provenance' || right) && contextId === HELA && meta && !registration) rpc('cell_em_registration').then(setRegistration).catch(() => {}); }, [drawer, right, contextId, !meta]);

  // ---- picking
  const onRay = (ray: {origin: Vec3; direction: Vec3}, world: {box: Vec3}) => {
    if (placing !== null || !meta) return;
    const p = main.playback.current;
    if (p.frames.length) { const i = pickMolecule(ray, p.frames[Math.min(p.index, p.frames.length - 1)], p.state[Math.min(p.index, p.state.length - 1)], 0.018); if (i >= 0) { setSelection({type: 'molecule', particle: i}); setRight(true); setAtom(null); return; } }
    if (!grid.current) return;
    const c = stage.current!.getCamera(), {lo, hi} = cutBounds(view.cut, world.box, viewOf(c));
    for (let i = 0; i < 3; i++) { lo[i] = Math.max(lo[i], (clip.lo[i] * 2 - 1) * world.box[i]); hi[i] = Math.min(hi[i], (clip.hi[i] * 2 - 1) * world.box[i]); }
    const hit = pickCompartment(ray, world.box, lo, hi, grid.current, cls => { const info = list[cls]; return !!info && opacityOf(info) > 0; });
    if (hit) { setSelection({type: 'compartment', cls: hit.cls, um: hit.um}); setRight(true); } else if (!pinned) setSelection(null);
  };
  const onFace = (um: Vec3) => {
    if (placing !== null) { patch(placing, {release: {point: um}}); setPlacing(null); say('Start point set. Release when you are ready.'); return; }
    if (!grid.current) return;
    const cls = classAt(grid.current, um); if (cls > 0) { setSelection({type: 'compartment', cls, um}); setRight(true); }
  };

  // ---- light-pulse molecules in 3-D: the run's reporter counts as particles, on the same clock as the plots
  const lightPlay = useRef<Playback>({frames: [], state: [], pairs: [], owner: new Uint8Array(0), colors: [], index: 0, dirty: true, playing: false}), lightPlayB = useRef<Playback>({...lightPlay.current});
  const showParticles = (p: LpParticles | null, play: React.MutableRefObject<Playback>, target: VolumeHandle | null) => {
    play.current = p && contextId === ECOLI ? buildPlayback(p) : {frames: [], state: [], pairs: [], owner: new Uint8Array(0), colors: [], index: 0, dirty: true, playing: false};
    if (p && contextId === ECOLI) { play.current.index = frameAt(p.time, lpT); target?.setModels(p.species.map((sp, i) => sphereModel(sp.radiusNm, PARTICLE_COLORS[i % PARTICLE_COLORS.length]))); }
  };
  useEffect(() => { if (experiment === 'light') showParticles(lp.particles, lightPlay, stage.current); }, [lp.particles, experiment, contextId, !!meta]);
  useEffect(() => { if (experiment === 'light') showParticles(lp.baseParticles, lightPlayB, stageB.current); }, [lp.baseParticles, experiment, contextId, !!meta, lp.baseline?.id !== lp.result?.id && !!lp.baseline]);
  useEffect(() => {
    for (const [p, play] of [[lp.particles, lightPlay], [lp.baseParticles, lightPlayB]] as const) if (p && play.current.frames.length) { const i = frameAt(p.time, lpT); if (i !== play.current.index) { play.current.index = i; play.current.dirty = true; } }
  }, [lpT, lp.particles, lp.baseParticles]);
  // ---- light-pulse clock
  useEffect(() => { if (lp.result) { setLpT(0); setLpPlaying(true); setDock(true); setDockTab('response'); } }, [lp.result?.id]);
  useEffect(() => {
    if (!lpPlaying || !lp.result) return;
    const end = lp.result.time[lp.result.time.length - 1], id = window.setInterval(() => setLpT(v => { const n = v + lpSpeed / 20; if (n >= end) { setLpPlaying(false); return end; } return n; }), 50);
    return () => window.clearInterval(id);
  }, [lpPlaying, lpSpeed, lp.result?.id]);
  const lightEvents: ChartEvent[] = useMemo(() => (lp.result?.record.outputs.events ?? []).map((e: any) => ({time: e.time, label: `${e.label} · ${e.time} min`, kind: e.kind})), [lp.result?.id]);

  // ---- keyboard
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (el.closest('input, select, textarea, [contenteditable]') || e.metaKey || e.ctrlKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (e.key === ' ') { e.preventDefault(); experiment === 'light' ? setLpPlaying(v => !v) : main.live && setPaused(v => !v); }
      else if (e.key === 'ArrowRight') { experiment === 'light' ? setLpT(v => Math.min(lp.total, v + 5)) : step(1); }
      else if (e.key === 'ArrowLeft') { experiment === 'light' ? setLpT(v => Math.max(0, v - 5)) : step(-1); }
      else if (k === 'h') { stage.current?.home(); setFollowed(null); }
      else if (k === 'c') setView(v => ({...v, cut: {...v.cut, axis: v.cut.axis >= 2 ? -1 : v.cut.axis + 1}}));
      else if (k === 'l') setLeft(v => !v); else if (k === 'i') setRight(v => !v); else if (k === 'd') setDock(v => !v);
      else if (k === 'f' && selection?.type === 'molecule') follow(followed === selection.particle ? null : selection.particle);
      else if (k === '1') setView(v => ({...v, mode: 'organelles'})); else if (k === '2' && ctx?.hasImage) setView(v => ({...v, mode: 'density'})); else if (k === '3' && ctx?.painting) setView(v => ({...v, mode: 'painting'}));
      else if (k === 'p') setDrawer(d => d === 'parameters' ? null : 'parameters'); else if (e.key === '?') setDrawer(d => d === 'shortcuts' ? null : 'shortcuts');
      else if (e.key === 'Escape') { if (drawer) setDrawer(null); else if (placing !== null) setPlacing(null); else { setSelection(null); follow(null); } }
      else return;
    };
    window.addEventListener('keydown', on); return () => window.removeEventListener('keydown', on);
  });

  if (!catalog) return <div className="ws ws-blank">{error ? <p className="ws-error"><TriangleAlert size={13}/>{error}</p> : <LoaderCircle className="spin"/>}</div>;
  const d = catalog.dataset;
  const field_ = (spec: InputSpec, value: string, change: (v: string) => void, labelText?: string) => <label key={spec.key} className="ws-field" title={`${spec.description} (${spec.bounds[0]}–${spec.bounds[1]} ${spec.unit})`}>
    <span>{labelText ?? spec.description.replace(/ \((hypothetical|assumption)\)/, '')}{/hypothetical|assumption/.test(spec.description) && <em>assumed</em>}</span>
    <div><input type="number" step="any" min={spec.bounds[0]} max={spec.bounds[1]} value={value} onChange={e => change(e.target.value)}/><small>{spec.unit}</small></div></label>;
  const homeOf = (s: Species) => 'compartment' in s.release ? s.release.compartment : (grid.current ? list[classAt(grid.current, s.release.point)]?.key : null) ?? 'cytosol';
  const bar = SCALE_BARS.reduce((a, b) => Math.abs(b * pxPerMicron - 120) < Math.abs(a * pxPerMicron - 120) ? b : a);
  const copies = species.reduce((n, s) => n + (Number(s.particles) || 0), 0);
  const hasRun = experiment === 'spatial' ? !!live : !!lp.result;
  const stageNow = !meta ? 0 : !hasRun ? (leftTab === 'experiment' && left ? 2 : 1) : (compare || (experiment === 'light' && lp.baseline && lp.baseline.id !== lp.result?.id)) ? 4 : selection || followed !== null ? 3 : 2;
  const spatialT = clock(t, 's'), lightT = clock(lpT, 'min');
  const tMin = main.run.current.times[main.run.current.dropped] ?? 0, tMax = main.run.current.times[main.run.current.times.length - 1] ?? 0;
  const simDt = live ? live.chunk.solver.dt * live.chunk.solver.stepsPerFrame : 0;
  const selectedInfo = selection?.type === 'compartment' ? list[selection.cls] : null;
  const selParticle = selection?.type === 'molecule' ? selection.particle : followed;
  const selOwner = selParticle != null ? main.playback.current.owner[selParticle] : null, selData = selOwner != null ? main.run.current.data[selOwner] ?? null : null;
  const selState = selParticle != null ? main.playback.current.state[Math.min(main.playback.current.index, main.playback.current.state.length - 1)]?.[selParticle] ?? 0 : 0;
  const picked = atom && selData && atom.particle === followed ? describeAtom(selData, atom.atom) : null;
  const frameIdx = live ? Math.max(0, lastAtOrBefore(live.time, t)) : 0;
  const eventTicks: ChartEvent[] = main.events.slice(-300).map(e => ({time: e.time, kind: e.kind, label: `${EVENT_LABEL[e.kind]} · ${e.species.join(' + ')} · ${(e.time * 1000).toFixed(2)} ms`}));
  const noGeometry = registry?.contexts.filter(c => c.geometry.kind === 'none') ?? [];
  const lightSupported = contextId === ECOLI;
  const dockTabs = experiment === 'light' ? [['response', 'Response'], ['validation', 'Validation'], ['sweep', 'Sweep'], ['control', 'Closed loop']] : [['results', 'Readouts'], ['events', `Events${main.events.length ? ' · ' + main.events.length : ''}`], ['compare', 'Compare'], ['replicates', 'Replicates & sweeps'], ...(ctx?.painting ? [['painting', 'Cell Painting']] : [])];
  const activeDock = dockTabs.some(x => x[0] === dockTab) ? dockTab : dockTabs[0][0];
  const split = compare || (experiment === 'light' && !!lp.baseline && lp.baseline.id !== lp.result?.id);
  const syncCam = (from: 'a' | 'b') => (c: Camera) => { if (from === 'a') { setCam(c); stageB.current?.setCamera(c); } else stage.current?.setCamera(c); };

  const viewport = <main className={'ws-view' + (view.mode === 'painting' ? ' painting' : '') + (split ? ' split' : '')}>
    {!meta ? <div className="ws-install">
      <span className="ws-eyebrow">Electron microscopy · {catalog.outdated ? 'update available' : 'not installed'}</span>
      <h3>Open a real cell</h3>
      <p>{d.name}. {d.method}. Acquired at {d.acquired}; the overview level ({d.installedLevel}) with thirteen compartment segmentations is installed first, and finer regions load on request.</p>
      <p className="ws-hint">{catalog.outdated ? 'This version adds compartments: a small extra download, then the grids are rebuilt.' : `Downloads about ${d.downloadMb} MB from OpenOrganelle (Janelia) into your library, once.`} {d.licence}.</p>
      <button className="ws-go" disabled={installing} onClick={install}>{installing ? <><LoaderCircle size={14} className="spin"/>Downloading and building (1–2 min)…</> : <><Download size={14}/>{catalog.outdated ? 'Update the cell volume' : 'Install the cell volume'}</>}</button>
      <button className="ws-link" onClick={() => external(d.url)}>View the dataset on OpenOrganelle</button>
      <button className="ws-link" onClick={() => setContextId(ECOLI)}>Or open the E. coli reporter context, which needs no download</button>
      {error && <p className="ws-error"><TriangleAlert size={13}/>{error}</p>}
    </div> : <>
      {split && <div className="ws-pane b"><VolumeStage key={contextId + 'b'} ref={stageB} dims={meta.dims} sizeUm={meta.sizeUm} view={stageViewB} playback={experiment === 'light' ? lightPlayB : base.playback} onCamera={syncCam('b')} label="Baseline view, synchronised with the variant"/>
        <span className="ws-pane-label">Baseline{experiment === 'light' ? ` · ${lp.baseline?.record.experiment.config.label || lp.baseline?.id.slice(0, 8)}` : ` · run ${parent?.slice(0, 8)}`}</span>
        {experiment === 'light' && lightBase && <ActivityLegend a={lightBase} particles={lp.baseParticles} t={lpT}/>}</div>}
      <div className="ws-pane a"><VolumeStage key={contextId} ref={stage} dims={meta.dims} sizeUm={meta.sizeUm} view={stageView} playback={experiment === 'light' ? lightPlay : main.playback} onScale={setPxPerMicron} onHover={setHover} onAtomic={setAtomic} onAtom={setAtom} onPick={onFace} onRay={onRay} onCamera={syncCam('a')}/>
        {split && <span className="ws-pane-label">{experiment === 'light' ? `Variant · ${lp.result?.record.experiment.config.label || lp.result?.id.slice(0, 8)}` : `Variant · run ${live?.chunk.id.slice(0, 8)}`}</span>}
        {experiment === 'light' && lightNow && <ActivityLegend a={lightNow} particles={lp.particles} t={lpT}/>}</div>

      <nav className="ws-tools" aria-label="View tools">
        <button onClick={() => { stage.current?.home(); follow(null); }} title="Whole cell (H)"><Home size={16}/></button>
        <button className={view.cut.axis >= 0 ? 'on' : ''} onClick={() => setView(v => ({...v, cut: {...v.cut, axis: v.cut.axis >= 2 ? -1 : v.cut.axis + 1}}))} title="Slice: off → X → Y → Z (C)"><Scissors size={16}/><i>{['–', 'X', 'Y', 'Z'][view.cut.axis + 1]}</i></button>
        <button className={clipOpen ? 'on' : ''} onClick={() => setClipOpen(v => !v)} title="Clip box: keep only part of the volume"><Box size={16}/></button>
        <span/>
        {([['organelles', 'Compartments (1)', Layers, true], ['density', 'EM density (2)', Microscope, !!ctx?.hasImage], ['painting', 'Cell Painting stain model (3)', Palette, !!ctx?.painting]] as const).map(([m, title, Icon, ok]) => ok && <button key={m} className={view.mode === m ? 'on' : ''} onClick={() => setView(v => ({...v, mode: m}))} title={title}><Icon size={16}/></button>)}
        <span/>
        <button className={placing !== null ? 'on' : ''} disabled={!species.length || experiment !== 'spatial'} onClick={() => { setPlacing(placing !== null ? null : species[0].key); setView(v => ({...v, cut: {...v.cut, axis: v.cut.axis < 0 ? 1 : v.cut.axis}})); }} title="Place a molecule: click a point on the slice"><Crosshair size={16}/></button>
        <button className={field.on ? 'on' : ''} disabled={!live} onClick={() => setField(f => ({...f, on: !f.on}))} title="Concentration field of the simulated copies"><Waves size={16}/></button>
        <button className={view.trail ? 'on' : ''} onClick={() => setView(v => ({...v, trail: !v.trail}))} title="Path of the followed molecule"><Route size={16}/></button>
        <button className={view.quality === 'high' ? 'on' : ''} onClick={() => setView(v => ({...v, quality: v.quality === 'high' ? 'balanced' : 'high'}))} title="High detail"><Sparkles size={16}/></button>
        <button onClick={snapshot} title="Save this view as an image"><CameraIcon size={16}/></button>
      </nav>
      {view.cut.axis >= 0 && <label className="ws-slice" title="Slice position"><span>{'XYZ'[view.cut.axis]} {(view.cut.at * meta.sizeUm[view.cut.axis]).toFixed(2)} µm</span><input type="range" min={0.01} max={0.99} step={0.002} value={view.cut.at} onChange={e => setView(v => ({...v, cut: {...v.cut, at: Number(e.target.value)}}))} aria-label="Slice position"/></label>}
      {clipOpen && <div className="ws-clip" role="group" aria-label="Clip box">
        {[0, 1, 2].map(i => <div key={i}><span>{'XYZ'[i]}</span><input type="range" min={0} max={1} step={0.005} value={clip.lo[i]} onChange={e => setClip(c => ({...c, lo: c.lo.map((v, k) => k === i ? Math.min(Number(e.target.value), c.hi[i] - 0.02) : v) as Vec3}))} aria-label={'Clip from, ' + 'XYZ'[i]}/>
          <input type="range" min={0} max={1} step={0.005} value={clip.hi[i]} onChange={e => setClip(c => ({...c, hi: c.hi.map((v, k) => k === i ? Math.max(Number(e.target.value), c.lo[i] + 0.02) : v) as Vec3}))} aria-label={'Clip to, ' + 'XYZ'[i]}/>
          <small>{(clip.lo[i] * meta.sizeUm[i]).toFixed(1)}–{(clip.hi[i] * meta.sizeUm[i]).toFixed(1)} µm</small></div>)}
        <button className="ws-link" onClick={() => setClip({lo: [0, 0, 0], hi: [1, 1, 1]})}>Reset</button></div>}

      <div className="ws-chips">
        <span className="ws-chip id" title={contextId === HELA ? d.name + ' · ' + d.licence : ctx!.cell}>{contextId === HELA ? `${d.cellLine} · ${d.id}` : ctx!.short + ' · drawn rod'} · {meta.sizeUm.map(v => v.toFixed(1)).join(' × ')} µm</span>
        {ctx!.geometry === 'measured' ? <><Tag k="em"/><Tag k="seg"/></> : <Tag k="illustrative"/>}
        {experiment === 'spatial' && (live || preview) && <Tag k="motion"/>}{field.on && <Tag k="field"/>}{experiment === 'light' && lp.result && <Tag k="activity"/>}{view.mode === 'painting' && <Tag k="stain"/>}
        {loaded < total && <span className="ws-chip"><LoaderCircle size={10} className="spin"/> Loading {loaded < total / (ctx!.hasImage ? 2 : 1) ? 'compartments' : 'image'} {Math.round(loaded / total * 100)}%</span>}
        {atomic > 0 && <span className="ws-chip glow"><Hexagon size={11}/> {atomic} molecule{atomic === 1 ? '' : 's'} drawn atom by atom</span>}
      </div>
      <div className="ws-res" title="The simulation and the picture have different resolutions. Atoms are drawn from saved structures; they do not enter the dynamics.">
        <span>Geometry <b>{Math.round(meta.voxelUm[0] * 1000)} × {Math.round(meta.voxelUm[1] * 1000)} × {num(meta.voxelUm[2] * 1000, 4)} nm</b></span>
        {detail && <span>Detail region <b>{Math.round((regions.find(r => r.id === detail)?.voxelUm[0] ?? 0) * 1000)} nm</b></span>}
        {experiment === 'spatial' ? <span>Simulation <b>{live ? `${num(Math.sqrt(2 * Math.max(...live.chunk.solver.D) * live.chunk.solver.dt) * 1000, 3)} nm steps, point particles` : 'point particles'}</b></span> : <span>Simulation <b>whole-cell average, no geometry</b></span>}
        <span>Structures <b>{species.some(s => s.data) ? 'atomic (drawn only)' : 'spheres'}</b></span>
      </div>
      {placing !== null && <div className="ws-banner"><Crosshair size={14}/>Click a point on the slice to start {species.find(s => s.key === placing)?.name ?? 'the molecule'} there<button className="ws-icon" onClick={() => setPlacing(null)} aria-label="Cancel"><X size={13}/></button></div>}
      {notice && <div className="ws-toast" role="status">{notice}</div>}
      {hover && grid.current && <div className="ws-readout">{list[classAt(grid.current, hover)]?.name ?? 'Outside'} · x {hover[0].toFixed(2)} · y {hover[1].toFixed(2)} · z {hover[2].toFixed(2)} µm</div>}
      <div className="ws-scale" aria-label={'Scale bar ' + scaleLabel(bar)}><i style={{width: bar * pxPerMicron}}/><span>{scaleLabel(bar)}</span></div>
      {cam && <Triad camera={cam}/>}
      {field.on && live && <div className="ws-colorbar"><i style={{background: `linear-gradient(90deg, transparent, ${field.species >= 0 ? SPECIES_HEX[field.species % 4] : C.accent})`}}/><span>0</span><span>{num(field.max, 2)} copies/µm³ · {num(field.max * NM_PER_COPY_PER_UM3, 2)} nM</span></div>}
      {field.on && live && results.length > 1 && <select className="ws-fieldsel" value={field.species} onChange={e => setField(f => ({...f, species: Number(e.target.value)}))} aria-label="Molecule shown as a concentration field"><option value={-1}>All molecules</option>{results.map((s, i) => <option key={i} value={i}>{s.name}</option>)}</select>}
      {!hasRun && !preview && placing === null && <div className="ws-next">{stageNow <= 1 ? <>Click a compartment to inspect it · drag to orbit · scroll to zoom from cell to atoms · <button className="ws-link" onClick={() => { setLeft(true); setLeftTab('experiment'); }}>Set up an experiment</button></> : experiment === 'spatial' ? <>Choose where the molecule starts, then <button className="ws-link" onClick={run}>Release into the cell</button></> : <>Shape the light program on the left, then run it</>}</div>}
    </>}
  </main>;

  return <div className="ws" ref={root} data-left={left} data-right={right}>
    <header className="ws-top">
      <label className="ws-context" title={ctx ? `${ctx.species} · ${ctx.cell}` : ''}><Microscope size={14}/>
        <select value={contextId} onChange={e => setContextId(e.target.value)} aria-label="Cell context">
          {catalog.contexts.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          {noGeometry.length > 0 && <optgroup label="No 3D geometry · open in Virtual Cell">{noGeometry.map(c => <option key={c.id} value={c.id} disabled>{c.name}</option>)}</optgroup>}
        </select></label>
      <div className="ws-seg" role="tablist" aria-label="Experiment">
        <button role="tab" aria-selected={experiment === 'spatial'} className={experiment === 'spatial' ? 'on' : ''} onClick={() => setExperiment('spatial')}><FlaskConical size={13}/>Molecules in 3D</button>
        <button role="tab" aria-selected={experiment === 'light'} className={experiment === 'light' ? 'on' : ''} disabled={!lightSupported} onClick={() => { setExperiment('light'); setLeft(true); setLeftTab('experiment'); }}
          title={lightSupported ? 'A light-responsive reporter, fitted to and tested against published time courses' : 'Not available in this cell: ' + (registry?.contexts.find(c => c.id === contextId)?.experiments.light_pulse?.missing.join('; ') ?? 'no measurement of a light-responsive reporter exists for it') + '. Switch to the E. coli context.'}><Lightbulb size={13}/>Light pulse</button>
      </div>
      <ol className="ws-path" aria-label="Where you are">{['Open', 'Explore', 'Run', 'Inspect', 'Compare'].map((name, i) => <li key={name} className={i < stageNow ? 'done' : i === stageNow ? 'now' : ''}>{name}</li>)}</ol>
      <div className="ws-top-right">
        {([['parameters', SlidersHorizontal, 'Parameters (P)'], ['solver', Sigma, 'Solver settings and numerical checks'], ['provenance', Info, 'Provenance: data, versions, registration'], ['diagnostics', Activity, 'Diagnostics: assumptions and limits']] as const).map(([k, Icon, title]) =>
          <button key={k} className={'ws-drawer-btn' + (drawer === k ? ' on' : '')} onClick={() => setDrawer(d => d === k ? null : k)} title={title} aria-label={title}><Icon size={13}/><span className="long">{k[0].toUpperCase() + k.slice(1)}</span></button>)}
        <span className="ws-sep"/>
        <button className={'ws-icon' + (left ? ' on' : '')} onClick={() => setLeft(v => !v)} title="Layers and experiment (L)" aria-pressed={left}><PanelLeft size={15}/></button>
        <button className={'ws-icon' + (dock ? ' on' : '')} onClick={() => setDock(v => !v)} title="Timeline and readouts (D)" aria-pressed={dock}><PanelBottom size={15}/></button>
        <button className={'ws-icon' + (right ? ' on' : '')} onClick={() => setRight(v => !v)} title="Inspector (I)" aria-pressed={right}><PanelRight size={15}/></button>
        <button className="ws-icon" onClick={() => setDrawer(d => d === 'shortcuts' ? null : 'shortcuts')} title="Keyboard shortcuts (?)">?</button>
      </div>
    </header>

    {left && <aside className="ws-left">
      <div className="ws-tabs" role="tablist">
        <button role="tab" aria-selected={leftTab === 'layers'} className={leftTab === 'layers' ? 'on' : ''} onClick={() => setLeftTab('layers')}><Layers size={13}/>Layers</button>
        <button role="tab" aria-selected={leftTab === 'experiment'} className={leftTab === 'experiment' ? 'on' : ''} onClick={() => setLeftTab('experiment')}>{experiment === 'light' ? <Lightbulb size={13}/> : <FlaskConical size={13}/>}Experiment</button>
      </div>
      <div className="ws-scroll">
        {leftTab === 'layers' && meta && <div className="ws-pad">
          <section className="ws-sec">
            <header><h4>Compartments</h4><Tag k={ctx!.geometry === 'measured' ? 'seg' : 'illustrative'}/></header>
            {isolated && <button className="ws-btn" onClick={() => setIsolated(null)}><Eye size={13}/>Show all again</button>}
            <ul className="ws-layers">{list.filter(c => c.id > 0 && (c.voxels ?? 1) > 0).map(c => { const off = hidden.has(c.key) || (!!isolated && isolated !== c.key); return <li key={c.key} className={(off ? 'off' : '') + (selection?.type === 'compartment' && selection.cls === c.id ? ' sel' : '')}>
              <button className="ws-icon" onClick={() => setHidden(h => { const n = new Set(h); n.has(c.key) ? n.delete(c.key) : n.add(c.key); return n; })} aria-label={(off ? 'Show ' : 'Hide ') + c.name} aria-pressed={!off}>{off ? <EyeOff size={13}/> : <Eye size={13}/>}</button>
              <i style={{background: c.color}}/>
              <button className="ws-layer-name" onClick={() => { setSelection({type: 'compartment', cls: c.id, um: [0, 0, 0]}); setRight(true); }} title={`${c.volumeUm3} µm³`}>{c.name}</button>
              <input type="range" min={0} max={1} step={0.05} value={opacity[c.key] ?? (contextId === HELA ? DEFAULT_OPACITY : ROD_OPACITY)[c.key] ?? 0.8} onChange={e => setOpacity(o => ({...o, [c.key]: Number(e.target.value)}))} aria-label={c.name + ' opacity'}/>
              <button className={'ws-icon' + (isolated === c.key ? ' on' : '')} onClick={() => { setIsolated(v => v === c.key ? null : c.key); setHidden(h => { const n = new Set(h); n.delete(c.key); return n; }); }} title="Isolate" aria-label={'Isolate ' + c.name}><Maximize2 size={12}/></button></li>; })}</ul>
          </section>
          {ctx!.hasImage && <section className="ws-sec">
            <header><h4>Image on the slice</h4><Tag k="em"/></header>
            <div className="ws-row"><button className={'ws-switch' + (view.face ? ' on' : '')} aria-pressed={view.face} onClick={() => setView(v => ({...v, face: !v.face}))}>Show image</button>
              <button className={'ws-switch' + (view.invert ? ' on' : '')} aria-pressed={view.invert} onClick={() => setView(v => ({...v, invert: !v.invert}))} title="FIB-SEM shows stained material bright; inverted, it resembles a transmission micrograph.">Invert</button>
              <button className={'ws-switch' + (view.tint > 0 ? ' on' : '')} aria-pressed={view.tint > 0} onClick={() => setView(v => ({...v, tint: v.tint > 0 ? 0 : 0.55}))}>Tint</button></div>
            <label className="ws-field"><span>Brightness</span><input type="range" min={0.3} max={3} step={0.05} value={view.gain} onChange={e => setView(v => ({...v, gain: Number(e.target.value)}))}/></label>
          </section>}
          <section className="ws-sec">
            <header><h4>Overlays</h4></header>
            <div className="ws-row"><button className={'ws-switch' + (view.bounds ? ' on' : '')} aria-pressed={view.bounds} onClick={() => setView(v => ({...v, bounds: !v.bounds}))}>Volume bounds</button>
              <button className={'ws-switch' + (view.trail ? ' on' : '')} aria-pressed={view.trail} onClick={() => setView(v => ({...v, trail: !v.trail}))}>Trajectory</button>
              <button className={'ws-switch' + (field.on ? ' on' : '')} aria-pressed={field.on} disabled={!live} onClick={() => setField(f => ({...f, on: !f.on}))}>Concentration</button></div>
            <p className="ws-hint">Binding, crossing, synthesis and decay events appear as rings at the place and time they happen.</p>
          </section>
          {ctx!.hasImage && <section className="ws-sec">
            <header><h4>Finer detail</h4><Tag k="em"/></header>
            <p className="ws-hint">The whole cell is loaded at 64 nm. Load a region at a finer level of the same dataset; it appears on the slice.</p>
            <div className="ws-row"><select value={level} onChange={e => setLevel(e.target.value)} aria-label="Detail level">{catalog.regionLevels.map(l => <option key={l.id} value={l.id}>{Math.round(l.voxelNm[0])} nm voxels</option>)}</select>
              <button className="ws-btn" disabled={busy === 'region'} onClick={() => loadRegion(selection?.type === 'compartment' && selection.um.some(v => v) ? selection.um : toUm(stage.current!.getCamera().target, meta.sizeUm, boxOf(meta.sizeUm)))}>{busy === 'region' ? <LoaderCircle size={13} className="spin"/> : <ZoomIn size={13}/>}Load here</button></div>
            {regions.length > 0 && <div className="ws-saved">{regions.map(r => <button key={r.id} className={detail === r.id ? 'on' : ''} onClick={() => detail === r.id ? (stage.current?.setDetail(null), setDetail(null)) : void showRegion(r)}><span>{Math.round(r.voxelUm[0] * 1000)} nm · {r.sizeUm.map(v => v.toFixed(1)).join(' × ')} µm</span><small>at {r.originUm.map(v => v.toFixed(1)).join(', ')} µm · {(r.bytes / 1e6).toFixed(0)} MB{detail === r.id ? ' · shown' : ''}</small></button>)}</div>}
          </section>}
          {ctx!.painting && <section className="ws-sec">
            <header><h4>Cell Painting</h4><Tag k="stain"/></header>
            <div className="ws-stains">{Object.entries(catalog.painting).map(([k, ch]) => <span key={k} title={ch.stain}><i style={{background: ch.color}}/>{k}</span>)}</div>
            <button className="ws-btn" disabled={busy === 'paint'} onClick={paintCell}>{busy === 'paint' ? <LoaderCircle size={13} className="spin"/> : <Palette size={13}/>}Render the five channels</button>
          </section>}
        </div>}
        {leftTab === 'experiment' && experiment === 'light' && <LightInputs lp={lp} cursor={lp.result ? lpT : null}/>}
        {leftTab === 'experiment' && experiment === 'spatial' && meta && <div className="ws-pad">
          {species.map((s, i) => { const home = homeOf(s); return <section key={s.key} className="ws-card" style={{'--c': SPECIES_HEX[i % 4]} as React.CSSProperties}>
            <header><i className="ws-dot"/><strong>{s.name}</strong>{s.busy && <LoaderCircle size={13} className="spin"/>}{species.length > 1 && <button className="ws-icon" onClick={() => { setSpecies(all => all.filter(x => x.key !== s.key)); setPairs(all => all.filter(p => p.a !== i && p.b !== i).map(p => ({...p, a: p.a > i ? p.a - 1 : p.a, b: p.b > i ? p.b - 1 : p.b}))); setConversions(all => all.filter(c => c.from !== i && c.to !== i).map(c => ({...c, from: c.from > i ? c.from - 1 : c.from, to: c.to > i ? c.to - 1 : c.to}))); }} aria-label={'Remove ' + s.name}><Trash2 size={13}/></button>}</header>
            <select value={s.source} onChange={e => void choose(s, e.target.value)} aria-label="What this molecule is">
              {structure && loadedData && <option value="loaded">Open structure · {structure.name}</option>}
              {s.source === 'custom' && <option value="custom">{s.name} · recorded size</option>}
              <optgroup label="Size presets">{catalog.molecules.map(m => <option key={m.id} value={'preset:' + m.id}>{m.name}</option>)}</optgroup>
              {structures.some(x => x.data?.asset) && <optgroup label="Reference structures in your library">{structures.filter(x => x.data?.asset).map(x => <option key={x.id} value={'asset:' + x.data.asset}>{x.name}</option>)}</optgroup>}
            </select>
            <p className="ws-hint">{s.data ? <><Hexagon size={11}/> Saved model, every heavy atom. </> : 'Drawn as one sphere of its radius. '}{s.note}</p>
            <div className="ws-grid">{field_(catalog.speciesInputs[0], s.radiusNm, v => patch(s.key, {radiusNm: v}), 'Radius')}{field_(catalog.speciesInputs[1], s.particles, v => patch(s.key, {particles: v}), 'Copies')}</div>
            <label className="ws-field"><span>Starts</span>
              <select value={'compartment' in s.release ? s.release.compartment : 'point'} onChange={e => e.target.value === 'point' ? (setPlacing(s.key), setView(v => ({...v, cut: {...v.cut, axis: v.cut.axis < 0 ? 1 : v.cut.axis}}))) : patch(s.key, {release: {compartment: e.target.value}})}>
                {list.filter(c => c.id > 0 && (c.voxels ?? 1) > 0).map(c => <option key={c.key} value={c.key}>Anywhere in {c.name.toLowerCase()}</option>)}
                <option value="point">{'point' in s.release ? `At ${s.release.point.map(v => v.toFixed(1)).join(', ')} µm · ${nameOf(home)}` : 'At a point I click on the slice…'}</option>
              </select></label>
            <label className="ws-field"><span>Sticks to</span>
              <select value={s.target} onChange={e => patch(s.key, {target: e.target.value})}><option value="">nothing · collisions only</option>{list.filter(c => c.id > 0 && c.key !== home && (c.voxels ?? 1) > 0).map(c => <option key={c.key} value={c.key}>{c.name}</option>)}</select></label>
            {s.target && <div className="ws-grid">{field_(catalog.speciesInputs[2], s.pBind, v => patch(s.key, {pBind: v}), 'Chance per encounter')}{field_(catalog.speciesInputs[3], s.koff, v => patch(s.key, {koff: v}), 'Release rate')}</div>}
            <details className="ws-more"><summary>Transport and turnover</summary>
              {contextId === HELA && ['cytosol', 'nucleus', 'chromatin', 'nucleolus'].includes(home) && <button className={'ws-switch' + (s.nuclear ? ' on' : '')} aria-pressed={s.nuclear} onClick={() => patch(s.key, {nuclear: !s.nuclear})} title="Nuclear pores are not resolved at 64 nm. On: the nuclear boundary is fully open (an upper bound for small molecules).">Nucleus fully open</button>}
              <label className="ws-field"><span>Crosses a boundary<em>assumed</em></span><select value={s.exchangeThrough} onChange={e => patch(s.key, {exchangeThrough: e.target.value})}><option value="">no · boundaries are walls</option>{list.filter(c => c.id > 0 && c.key !== home && (c.voxels ?? 1) > 0).map(c => <option key={c.key} value={c.key}>through {c.name.toLowerCase()}</option>)}</select></label>
              {s.exchangeThrough && <div className="ws-grid"><label className="ws-field"><span>Into</span><select value={s.exchangeTo} onChange={e => patch(s.key, {exchangeTo: e.target.value})}><option value="">choose…</option>{list.filter(c => c.id > 0 && c.key !== home && c.key !== s.exchangeThrough && (c.voxels ?? 1) > 0).map(c => <option key={c.key} value={c.key}>{c.name}</option>)}</select></label>{field_(catalog.exchangeInput, s.permeability, v => patch(s.key, {permeability: v}), 'Permeability')}</div>}
              <div className="ws-grid">{field_(catalog.kineticInputs[1], s.synthesisRate, v => patch(s.key, {synthesisRate: v}), 'Synthesis')}{field_(catalog.kineticInputs[2], s.decay, v => patch(s.key, {decay: v}), 'Decay')}</div>
              {Number(s.synthesisRate) > 0 && <div className="ws-grid"><label className="ws-field"><span>Made in</span><select value={s.synthesisIn} onChange={e => patch(s.key, {synthesisIn: e.target.value})}>{list.filter(c => c.id > 0 && (c.voxels ?? 1) > 0).map(c => <option key={c.key} value={c.key}>{c.name}</option>)}</select></label>{field_(catalog.kineticInputs[0], s.capacity, v => patch(s.key, {capacity: v}), 'At most')}</div>}
              <p className="ws-hint">Runs cover milliseconds to seconds of simulated time, so rates need to be per second to show. Each is your assumption.</p>
            </details>
          </section>; })}
          {species.length < catalog.limits.species && <button className="ws-btn wide" onClick={() => { const m = catalog.molecules.find(m => m.id === 'igg') ?? catalog.molecules[0]; setSpecies(all => [...all, freshSpecies(catalog, 'preset:' + m.id, m.name, m.radiusNm, null, m.note)]); }}><Plus size={13}/>Add another molecule</button>}
          {species.length > 1 && <section className="ws-sec">
            <header><h4>Interactions</h4><span className="ws-tag assumed" title="No model here derives binding from structure. Reach, rates and conversions are your hypotheses.">your hypothesis</span></header>
            {species.flatMap((a, i) => species.slice(i + 1).map((b, k) => { const j = i + 1 + k, p = pairs.find(q => q.a === i && q.b === j); return <div key={a.key + '-' + b.key} className="ws-pair">
              <div className="ws-row"><i className="ws-dot" style={{background: SPECIES_HEX[i % 4]}}/><span>{a.name}</span><Link2 size={12}/><i className="ws-dot" style={{background: SPECIES_HEX[j % 4]}}/><span>{b.name}</span>
                <button className={'ws-switch' + (p?.on ? ' on' : '')} aria-pressed={!!p?.on} onClick={() => { const dflt = Object.fromEntries(catalog.pairInputs.map(s => [s.key, String(s.default)])); setPairs(all => p ? all.map(q => q === p ? {...q, on: !q.on} : q) : [...all, {a: i, b: j, on: true, reachNm: dflt.reachNm, rate: dflt.rate, koff: dflt.koff}]); }}>{p?.on ? 'Bind' : 'Off'}</button></div>
              {p?.on && <div className="ws-grid three">{catalog.pairInputs.map((s, n) => field_(s, (p as any)[s.key], v => setPairs(all => all.map(q => q === p ? {...q, [s.key]: v} : q)), ['Reach', 'On rate', 'Off rate'][n]))}</div>}</div>; }))}
            {conversions.map((c, n) => <div key={n} className="ws-pair"><div className="ws-row">
              <select value={c.from} onChange={e => setConversions(all => all.map((x, k) => k === n ? {...x, from: Number(e.target.value)} : x))} aria-label="Converted molecule">{species.map((s, i) => <option key={s.key} value={i}>{s.name}</option>)}</select><span>→</span>
              <select value={c.to} onChange={e => setConversions(all => all.map((x, k) => k === n ? {...x, to: Number(e.target.value)} : x))} aria-label="Product">{species.map((s, i) => <option key={s.key} value={i}>{s.name}</option>)}</select>
              <button className="ws-icon" onClick={() => setConversions(all => all.filter((_, k) => k !== n))} aria-label="Remove conversion"><Trash2 size={12}/></button></div>
              {field_(catalog.reactionInput, c.rate, v => setConversions(all => all.map((x, k) => k === n ? {...x, rate: v} : x)), 'Conversion rate')}</div>)}
            <button className="ws-btn" onClick={() => setConversions(all => [...all, {from: 0, to: 1, rate: String(catalog.reactionInput.default)}])}><Plus size={13}/>Add a conversion A → B</button>
          </section>}
          {parent && <p className="ws-branch"><GitBranch size={12}/>Variant of run {parent.slice(0, 8)}. Change one thing, then release.<button className="ws-icon" onClick={() => { setParent(null); setLabel(''); setCompare(false); }} aria-label="Stop comparing"><X size={11}/></button></p>}
          <input className="ws-label" value={label} placeholder="Name this experiment (optional)" maxLength={120} onChange={e => setLabel(e.target.value)} aria-label="Experiment name"/>
          <button className="ws-go" disabled={loaded < total / (ctx!.hasImage ? 2 : 1) || !species.length || species.some(s => s.busy)} onClick={run}><Play size={15}/>{main.running ? 'Restart' : 'Release into the cell'}<small>{copies} copies</small></button>
          <div className="ws-row"><button className="ws-btn" disabled={busy === 'preview' || !species.length} onClick={previewPlacement}>{busy === 'preview' ? <LoaderCircle size={13} className="spin"/> : <Eye size={13}/>}Preview placement</button>{main.running && <button className="ws-btn" onClick={main.stop}>Stop computing</button>}</div>
          {(error || main.error) && <p className="ws-error"><TriangleAlert size={13}/>{error || main.error}</p>}
        </div>}
      </div>
    </aside>}

    {viewport}

    {right && <aside className="ws-right">
      <header className="ws-insp-head"><span className="ws-eyebrow">{selection?.type === 'compartment' ? 'Compartment' : selection?.type === 'event' || selection?.type === 'lightEvent' ? 'Event' : selParticle != null ? 'Molecule' : 'Specimen'}</span>
        <button className={'ws-icon' + (pinned ? ' on' : '')} onClick={() => setPinned(v => !v)} title="Keep this panel's selection when clicking empty space" aria-pressed={pinned}><Pin size={13}/></button>
        <button className="ws-icon" onClick={() => setRight(false)} aria-label="Close inspector"><X size={13}/></button></header>
      <div className="ws-scroll ws-pad">
        {selection?.type === 'compartment' && selectedInfo && meta && <>
          <h3><i className="ws-dot" style={{background: selectedInfo.color}}/>{selectedInfo.name}</h3>
          <Tag k={ctx!.geometry === 'measured' ? 'seg' : 'illustrative'}/>
          <dl className="ws-dl"><div><dt>Volume in view</dt><dd>{num(selectedInfo.volumeUm3, 4)} µm³</dd></div><div><dt>Voxels</dt><dd>{(selectedInfo.voxels ?? 0).toLocaleString()}</dd></div>
            {selection.um.some(v => v) && <div><dt>Picked at</dt><dd>x {selection.um[0].toFixed(2)} · y {selection.um[1].toFixed(2)} · z {selection.um[2].toFixed(2)} µm</dd></div>}
            {live && results.map((s, i) => { const n = live.series[i]?.occupancy[selectedInfo.key]?.[frameIdx] ?? 0; return <div key={i}><dt>{s.name} here now</dt><dd>{n} copies · {num(n / Math.max(selectedInfo.volumeUm3 ?? 1, 1e-9) * NM_PER_COPY_PER_UM3, 3)} nM</dd></div>; })}
            {experiment === 'light' && lightNow && <div><dt>Modelled here</dt><dd>{selectedInfo.key === 'pm' ? `regulator ${num((lightNow.regulator ?? 0) * 100, 3)} % active` : selectedInfo.key === 'chromatin' ? `transcription at ${num((lightNow.transcription ?? 0) * 100, 3)} % of its range` : selectedInfo.key === 'cytosol' ? `reporter ${num(lightNow.reporterMEFL)} MEFL (whole cell)` : 'nothing'}</dd></div>}</dl>
          <label className="ws-field"><span>Opacity</span><input type="range" min={0} max={1} step={0.05} value={opacity[selectedInfo.key] ?? (contextId === HELA ? DEFAULT_OPACITY : ROD_OPACITY)[selectedInfo.key] ?? 0.8} onChange={e => setOpacity(o => ({...o, [selectedInfo.key]: Number(e.target.value)}))}/></label>
          <div className="ws-row"><button className={'ws-btn' + (isolated === selectedInfo.key ? ' on' : '')} onClick={() => { setIsolated(v => v === selectedInfo.key ? null : selectedInfo.key); setHidden(h => { const n = new Set(h); n.delete(selectedInfo.key); return n; }); say(isolated === selectedInfo.key ? 'All compartments are shown again.' : `Only ${selectedInfo.name.toLowerCase()} is shown.`); }}><Maximize2 size={13}/>{isolated === selectedInfo.key ? 'Show all' : 'Isolate'}</button>
            {selection.um.some(v => v) && <button className="ws-btn" onClick={() => stage.current?.flyTo(selection.um, 4)}><ZoomIn size={13}/>Zoom here</button>}</div>
          {experiment === 'spatial' && species[0] && <button className="ws-btn wide primary" onClick={() => { patch(species[0].key, {release: selection.um.some(v => v) ? {point: selection.um} : {compartment: selectedInfo.key}}); setLeft(true); setLeftTab('experiment'); say(`${species[0].name} will start in ${selectedInfo.name.toLowerCase()}.`); }}><Crosshair size={13}/>Place {species[0].name} here</button>}
          <p className="ws-hint">{ctx!.geometry === 'measured' ? 'A machine-learning segmentation of the image at 64 nm; thin membranes and small vesicles are only partly resolved.' : 'Drawn, not imaged.'}</p>
        </>}
        {selParticle != null && selection?.type !== 'compartment' && selection?.type !== 'event' && <>
          <h3><i className="ws-dot" style={{background: SPECIES_HEX[(selOwner ?? 0) % 4]}}/>{results[selOwner ?? 0]?.name ?? species[selOwner ?? 0]?.name ?? 'Molecule'}</h3>
          <Tag k="motion"/>
          <dl className="ws-dl"><div><dt>Copy</dt><dd>{selParticle + 1}</dd></div><div><dt>State</dt><dd>{selState === 2 ? 'in a complex' : selState === 1 ? 'bound to a compartment' : selState === 3 ? 'not present now' : 'free'}</dd></div>
            {selData && <div><dt>Model</dt><dd>{selData.atoms.toLocaleString()} heavy atoms · {selData.residues.length.toLocaleString()} residues · {selData.chains.length} chain{selData.chains.length === 1 ? '' : 's'}</dd></div>}
            {picked ? <div className="hit"><dt>Atom</dt><dd>{picked.atom} <small>({picked.element})</small> · {picked.residue} {picked.number} · chain {picked.chain}</dd></div> : <div><dt>Atom</dt><dd><small>{selData ? (followed === selParticle ? 'Click an atom to identify it' : 'Follow it, then click an atom') : 'Size preset: no atoms to inspect'}</small></dd></div>}</dl>
          <div className="ws-row"><button className={'ws-btn primary' + (followed === selParticle ? ' on' : '')} onClick={() => follow(followed === selParticle ? null : selParticle)}><ZoomIn size={13}/>{followed === selParticle ? 'Stop following' : 'Follow (F)'}</button></div>
          {selData && <div className="ws-seg small">{(['atoms', 'chains', 'backbone'] as const).map(r => <button key={r} className={representation === r ? 'on' : ''} onClick={() => setRepresentation(r)}>{r === 'atoms' ? 'Elements' : r === 'chains' ? 'Chains' : 'Backbone'}</button>)}</div>}
          <p className="ws-hint">Shape and orientation are drawn from the saved model. They do not enter the dynamics, and tumbling is not simulated.</p>
        </>}
        {selection?.type === 'event' && <>
          <h3>{selection.event.species.join(' + ')} {EVENT_LABEL[selection.event.kind]}</h3><Tag k="motion"/>
          <dl className="ws-dl"><div><dt>Simulated time</dt><dd>{(selection.event.time * 1000).toFixed(3)} ms</dd></div><div><dt>Where</dt><dd>{nameOf(selection.event.compartment)}</dd></div>
            <div><dt>Position</dt><dd>x {selection.event.position[0].toFixed(2)} · y {selection.event.position[1].toFixed(2)} · z {selection.event.position[2].toFixed(2)} µm</dd></div><div><dt>Copies</dt><dd>{selection.event.a + 1}{selection.event.b != null ? ' and ' + (selection.event.b + 1) : ''}</dd></div></dl>
          <div className="ws-row"><button className="ws-btn primary" onClick={() => goToEvent(selection.event)}><Crosshair size={13}/>Go there</button><button className="ws-btn" onClick={() => { setSelection({type: 'molecule', particle: selection.event.a}); }}>Inspect the molecule</button></div>
        </>}
        {selection?.type === 'lightEvent' && <>
          <h3>{selection.event.label}</h3><Tag k="activity"/>
          <dl className="ws-dl"><div><dt>Simulated time</dt><dd>{selection.event.time} min</dd></div><div><dt>Scale</dt><dd>{selection.event.scale}</dd></div><div><dt>Value</dt><dd>{num(selection.event.value)}</dd></div>
            <div><dt>Where</dt><dd>{selection.event.kind === 'regulator' ? 'cell envelope (illustrative)' : selection.event.kind === 'transcription' ? 'nucleoid region (illustrative)' : selection.event.kind === 'light' ? 'whole culture' : 'cytoplasm; measured for the whole cell'}</dd></div></dl>
          <button className="ws-btn primary" onClick={() => { setLpT(selection.event.time); setLpPlaying(false); }}><Crosshair size={13}/>Go to this moment</button>
        </>}
        {!selection && selParticle == null && ctx && <>
          <h3>{ctx.name}</h3>
          <div className="ws-tagrow">{ctx.geometry === 'measured' ? <><Tag k="em"/><Tag k="seg"/></> : <Tag k="illustrative"/>}</div>
          <dl className="ws-dl"><div><dt>Species</dt><dd>{ctx.species}</dd></div><div><dt>Cell</dt><dd>{ctx.cell}</dd></div>
            {meta && <><div><dt>{ctx.geometry === 'measured' ? 'Acquired volume' : 'Drawn box'}</dt><dd>{meta.sizeUm.map(v => v.toFixed(2)).join(' × ')} µm (x, y, z)</dd></div><div><dt>Voxel spacing</dt><dd>x {num(meta.voxelUm[0] * 1000, 4)} · y {num(meta.voxelUm[1] * 1000, 4)} · z {num(meta.voxelUm[2] * 1000, 4)} nm</dd></div>
              <div><dt>Grid</dt><dd>{meta.dims.join(' × ')} voxels</dd></div><div><dt>Origin</dt><dd>corner of the first voxel; y is up in the view</dd></div></>}
            {contextId === HELA && <><div><dt>Dataset</dt><dd>{d.name}</dd></div><div><dt>Acquired at</dt><dd>{d.acquired}</dd></div></>}
            <div><dt>Diffusion slowdown</dt><dd>{ctx.defaults.slowdown.value}× water · <span className={'ws-tag ' + (ctx.defaults.slowdown.provenance.kind === 'literature' ? 'measured' : 'assumed')} title={ctx.defaults.slowdown.provenance.note}>{ctx.defaults.slowdown.provenance.kind}</span></dd></div></dl>
          {registration && contextId === HELA && <ul className="ws-checks">{registration.checks.map((c: any) => <li key={c.name} className={c.passed ? 'ok' : 'bad'}>{c.passed ? <Check size={12}/> : <TriangleAlert size={12}/>}<div><strong>{c.name}</strong><small>{c.detail}</small></div></li>)}</ul>}
          <p className="ws-hint">{contextId === HELA ? 'One fixed HeLa cell with parts of three neighbours. It is not the Hep G2 molecular baseline of Virtual Cell; no readout is carried between them.' : 'The reporter experiment is a whole-cell model; this rod only shows where its parts sit.'}</p>
          <p className="ws-hint">Click a compartment or a molecule to inspect it.</p>
        </>}
      </div>
    </aside>}

    {hasRun && <footer className="ws-dock">
      <div className="ws-timeline">
        {experiment === 'spatial' && live ? <>
          <button className="ws-icon" onClick={() => step(-1)} aria-label="Previous computed frame" title="Step back (←)"><ChevronLeft size={15}/></button>
          <button className="ws-play" onClick={() => setPaused(p => !p)} aria-label={paused ? 'Play' : 'Pause'} title="Play or pause (Space)">{paused || !main.running ? <Play size={16}/> : <Pause size={16}/>}</button>
          <button className="ws-icon" onClick={() => step(1)} aria-label="Next computed frame" title="Step forward (→)"><ChevronRight size={15}/></button>
          <div className="ws-clock" title="Simulated time is the time inside the model. Playback speed is how fast you watch it."><strong>{spatialT.value}<small> {spatialT.unit}</small></strong><span>simulated</span></div>
          <Scrubber t0={tMin} t1={tMax} t={t} onSeek={seekTo} events={eventTicks} onEvent={i => goToEvent(main.events.slice(-300)[i])}/>
          <label className="ws-speed" title="Playback speed"><select value={speed} onChange={e => setSpeed(Number(e.target.value))} aria-label="Playback speed">{[0.25, 0.5, 1].map(v => <option key={v} value={v}>{v}× playback</option>)}</select><small>{num(simDt * main.fps * speed, 2)} s simulated per second watched</small></label>
          <button className="ws-btn" onClick={branch} title="Keep this run as the baseline and change one thing"><GitBranch size={13}/>Branch</button>
          {parent && <button className={'ws-btn' + (compare ? ' on' : ' primary')} disabled={busy === 'compare'} onClick={() => compare ? setCompare(false) : void openCompare()}>{busy === 'compare' ? <LoaderCircle size={13} className="spin"/> : <Columns2 size={13}/>}{compare ? 'Single view' : 'Compare side by side'}</button>}
          {onViewResults && <button className="ws-btn" onClick={() => onViewResults(live.chunk.id, 'cell_em')} title="Open this saved run in Virtual Cell"><Eye size={13}/>View Results</button>}
        </> : lp.result && <>
          <button className="ws-icon" onClick={() => { setLpPlaying(false); setLpT(v => Math.max(0, v - 5)); }} aria-label="Back 5 minutes" title="Step back (←)"><ChevronLeft size={15}/></button>
          <button className="ws-play" onClick={() => { if (lpT >= lp.result!.time[lp.result!.time.length - 1]) setLpT(0); setLpPlaying(v => !v); }} aria-label={lpPlaying ? 'Pause' : 'Play'} title="Play or pause (Space)">{lpPlaying ? <Pause size={16}/> : <Play size={16}/>}</button>
          <button className="ws-icon" onClick={() => { setLpPlaying(false); setLpT(v => Math.min(lp.result!.time[lp.result!.time.length - 1], v + 5)); }} aria-label="Forward 5 minutes" title="Step forward (→)"><ChevronRight size={15}/></button>
          <div className="ws-clock" title="Simulated time is the time inside the model. Playback speed is how fast you watch it."><strong>{lightT.value}<small> {lightT.unit}</small></strong><span>simulated</span></div>
          <Scrubber t0={0} t1={lp.result.time[lp.result.time.length - 1]} t={lpT} onSeek={v => { setLpPlaying(false); setLpT(v); }} events={lightEvents} onEvent={i => { const e = lp.result!.record.outputs.events[i]; setLpPlaying(false); setLpT(e.time); setSelection({type: 'lightEvent', event: e}); setRight(true); }}/>
          <label className="ws-speed" title="Playback speed"><select value={lpSpeed} onChange={e => setLpSpeed(Number(e.target.value))} aria-label="Playback speed">{[10, 30, 60, 120].map(v => <option key={v} value={v}>{v} min per second</option>)}</select><small>{lpSpeed * 60}× real time</small></label>
          {onViewResults && <button className="ws-btn" onClick={() => onViewResults(lp.result!.id, 'light_pulse')} title="Open this saved experiment in Virtual Cell"><Eye size={13}/>View Results</button>}
        </>}
        <div className="ws-tabs dock" role="tablist">{dockTabs.map(([k, name]) => <button key={k} role="tab" aria-selected={dock && activeDock === k} className={dock && activeDock === k ? 'on' : ''} onClick={() => { setDockTab(k); setDock(true); }}>{name}</button>)}
          <button className="ws-icon" onClick={() => setDock(v => !v)} title={dock ? 'Hide the readouts and keep the timeline (D)' : 'Show the readouts (D)'} aria-label={dock ? 'Hide readouts' : 'Show readouts'}>{dock ? <ChevronDown size={14}/> : <ChevronUp size={14}/>}</button></div>
      </div>
      {dock && <div className="ws-dock-body">
        {experiment === 'light' && <LightDock lp={lp} cursor={lpT} onSeek={v => { setLpPlaying(false); setLpT(v); }} tab={activeDock} events={lightEvents}/>}
        {experiment === 'spatial' && live && activeDock === 'results' && <div className="ws-grid2">
          <div>
            <SyncChart title="Copies in each compartment" time={live.time} unit="copies" timeUnit="s" cursor={t} onSeek={seekTo} events={eventTicks}
              series={results.flatMap((s, i) => Object.entries(live.series[i]?.occupancy ?? {}).filter(([, v]) => v.some(x => x > 0)).slice(0, 4).map(([key, v], k) => ({id: i + key, label: `${s.name} in ${nameOf(key).toLowerCase()}`, values: v, color: SPECIES_HEX[i % 4], dash: k > 0, width: k > 0 ? 1.4 : 2})))}/>
            {(results.some(s => s.target) || live.chunk.events.pairBinds > 0 || pairs.some(p => p.on)) && <SyncChart title="Fractions bound" time={live.time} unit="fraction" timeUnit="s" cursor={t} onSeek={seekTo} height={150}
              series={results.flatMap((s, i) => [...(s.target ? [{id: 'b' + i, label: `${s.name} on ${nameOf(s.target).toLowerCase()}`, values: live.series[i]?.bound ?? [], color: SPECIES_HEX[i % 4], dash: true}] : []), ...(pairs.some(p => p.on && (p.a === i || p.b === i)) ? [{id: 'c' + i, label: `${s.name} in a complex`, values: live.series[i]?.complex ?? [], color: SPECIES_HEX[i % 4]}] : [])])}/>}
          </div>
          <div>
            {results.every(s => s.msdFromRelease) ? <SyncChart title="Spread from the release positions" time={live.time} unit="µm²" timeUnit="s" cursor={t} onSeek={seekTo} height={150}
              series={[...results.map((s, i) => ({id: 'm' + i, label: `${s.name} · mean squared displacement`, values: live.series[i]?.msd ?? [], color: SPECIES_HEX[i % 4]})), {id: 'free', label: `6Dt · ${results[0].name} with no obstacles`, values: live.time.map(v => 6 * results[0].D * v), color: C.reference, dash: true}]}/>
              : <SyncChart title="Copies present" time={live.time} unit="copies" timeUnit="s" cursor={t} onSeek={seekTo} height={150} series={results.map((s, i) => ({id: 'p' + i, label: s.name, values: live.series[i]?.present ?? [], color: SPECIES_HEX[i % 4]}))}/>}
            <table className="ws-table"><thead><tr><th>Molecule</th><th>D (µm²/s)</th><th>Copies now</th><th>Stopped most by</th></tr></thead><tbody>{results.map((s, i) => { const top = Object.entries(s.encounters).sort((a, b) => b[1] - a[1])[0];
              return <tr key={i}><td><i className="ws-dot" style={{background: SPECIES_HEX[i % 4]}}/>{s.name}</td><td>{num(s.D)}</td><td>{live.series[i]?.present[frameIdx] ?? s.particles}</td><td>{top ? `${nameOf(top[0])} (${top[1].toLocaleString()})` : '–'}</td></tr>; })}</tbody></table>
            <p className="ws-hint">{live.chunk.events.pairBinds} complexes formed, {live.chunk.events.pairReleases} separated{live.chunk.solver.kinetics ? `; ${live.chunk.events.born ?? 0} synthesised, ${live.chunk.events.died ?? 0} decayed, ${live.chunk.events.converted ?? 0} converted, ${live.chunk.events.crossings ?? 0} boundary crossings` : ''}. Click a chart to move the time cursor.</p>
            <div className="ws-row"><span className={'ws-verdict ' + (live.chunk.passed ? 'ok' : 'bad')}>{live.chunk.passed ? <Check size={12}/> : <TriangleAlert size={12}/>}{live.chunk.passed ? 'Numerical checks passed' : 'A numerical check failed'}</span><span className="ws-id">Run {live.chunk.id.slice(0, 8)} · SHA-256 {live.chunk.sha256.slice(0, 12)}… · cell_em/runs</span></div>
          </div>
        </div>}
        {experiment === 'spatial' && activeDock === 'events' && (main.events.length ? <div className="ws-events">{main.events.slice(-120).reverse().map((e, i) => <button key={e.time + '-' + e.a + '-' + i} className={selection?.type === 'event' && selection.event === e ? 'on' : ''} onClick={() => goToEvent(e)}>
          <span>{(e.time * 1000).toFixed(2)} ms</span><b className={e.kind}>{EVENT_LABEL[e.kind]}</b><span>{e.species.join(' + ')}</span><span>{nameOf(e.compartment)}</span><span>x {e.position[0].toFixed(1)} · y {e.position[1].toFixed(1)} · z {e.position[2].toFixed(1)} µm</span></button>)}</div>
          : <p className="ws-empty">No events yet. Let two molecules bind, give one a boundary to cross, or add synthesis and decay under Experiment.</p>)}
        {experiment === 'spatial' && activeDock === 'compare' && (comparison ? <div className="ws-grid2">
          <div><p className={comparison.identicalDynamics ? 'ws-warn' : 'ws-hint'}>{comparison.identicalDynamics && <TriangleAlert size={12}/>} {comparison.note}</p>
            <table className="ws-table"><thead><tr><th>What changed</th><th>Baseline</th><th>Variant</th><th>Enters the simulation</th></tr></thead><tbody>{comparison.changed.length === 0 && <tr><td colSpan={4}>Nothing differs between the two setups.</td></tr>}
              {comparison.changed.map((c: any) => <tr key={c.what}><td>{c.what}</td><td>{show(c.baseline)}</td><td>{show(c.variant)}</td><td>{c.affectsDynamics ? 'yes' : 'no'}</td></tr>)}</tbody></table></div>
          <div><table className="ws-table"><thead><tr><th>Outcome at {(comparison.baseline.time * 1000).toFixed(0)} ms</th><th>Baseline</th><th>Variant</th></tr></thead><tbody>
            <tr><td>Complexes formed / separated</td><td>{comparison.baseline.events.pairBinds} / {comparison.baseline.events.pairReleases}</td><td>{comparison.variant.events.pairBinds} / {comparison.variant.events.pairReleases}</td></tr>
            {comparison.baseline.species.map((b: any, i: number) => { const v = comparison.variant.species[i]; return [<tr key={i + 'c'}><td>{b.name} · in a complex</td><td>{b.complexes} of {b.present}</td><td>{v ? `${v.complexes} of ${v.present}` : '–'}</td></tr>,
              <tr key={i + 'd'}><td>{b.name} · apparent D (µm²/s)</td><td>{num(b.apparentD)}</td><td>{v ? num(v.apparentD) : '–'}</td></tr>, <tr key={i + 'b'}><td>{b.name} · on its target</td><td>{num(b.boundFraction * 100)} %</td><td>{v ? num(v.boundFraction * 100) + ' %' : '–'}</td></tr>]; })}</tbody></table>
            <SyncChart title="Fraction in a complex" time={comparison.baseline.series.time} unit="fraction" timeUnit="s" cursor={t} onSeek={seekTo} height={140}
              series={[{id: 'b', label: 'Baseline', values: comparison.baseline.series.species[0].complex, color: C.accent, dash: true}, {id: 'v', label: 'Variant', values: comparison.variant.series.species[0].complex.slice(0, comparison.baseline.series.time.length), color: C.reporter}]}/></div>
        </div> : <p className="ws-empty">Branch a run, change one thing, release again, then choose Compare side by side. Both runs replay under one camera, one slice and one clock.</p>)}
        {experiment === 'spatial' && activeDock === 'replicates' && live && <div className="ws-grid2">
          <div><div className="ws-row"><button className="ws-btn primary" disabled={busy === 'replicates'} onClick={runReplicates}>{busy === 'replicates' ? <LoaderCircle size={13} className="spin"/> : <FlaskConical size={13}/>}Rerun with 5 seeds</button><span className="ws-hint">How much of the outcome is chance (about 10 s).</span></div>
            {replicates && <><SyncChart title="Fraction in a complex · mean and range of 5 seeds" time={replicates.time} unit="fraction" timeUnit="s" height={150}
              series={replicates.species.map((s: any, i: number) => ({id: 's' + i, label: s.name + ' · mean', values: s.complex.mean, color: SPECIES_HEX[i % 4]}))} bands={replicates.species.map((s: any, i: number) => ({lo: s.complex.min, hi: s.complex.max, color: SPECIES_HEX[i % 4], label: s.name + ' · range'}))}/>
              <p className="ws-hint">Complexes formed per seed: {replicates.pairBinds.join(', ')}. {replicates.note}</p></>}</div>
          <div><div className="ws-row"><span className="ws-hint">Sweep one input:</span>
            {pairs.some(p => p.on) && <button className="ws-btn" disabled={busy === 'sweep'} onClick={() => runSweep('pair.rate', [0, 500, 2000, 8000])}>Binding rate</button>}
            <button className="ws-btn" disabled={busy === 'sweep'} onClick={() => runSweep('slowdown', [1, Number(globals.slowdown) || 3.2, 2 * (Number(globals.slowdown) || 3.2), 4 * (Number(globals.slowdown) || 3.2)])}>Slowdown</button>
            {species[0]?.exchangeThrough && <button className="ws-btn" disabled={busy === 'sweep'} onClick={() => runSweep('permeabilityUmS', [0.5, 2, 8, 32])}>Permeability</button>}
            {busy === 'sweep' && <LoaderCircle size={13} className="spin"/>}</div>
            {sweep && <table className="ws-table"><thead><tr><th>{sweep.label} ({sweep.unit})</th><th>Complexes formed</th><th>{sweep.rows[0].species[0].name} · apparent D</th><th>Crossings</th></tr></thead><tbody>{sweep.rows.map((r: any) => <tr key={r.value}><td>{num(r.value)}</td><td>{r.events.pairBinds}</td><td>{num(r.species[0].apparentD)}</td><td>{r.events.crossings ?? '–'}</td></tr>)}</tbody></table>}
            {sweep && <p className="ws-hint">{sweep.note}</p>}
            <div className="ws-row"><button className="ws-btn" disabled={busy === 'crowding'} onClick={runCrowding}>{busy === 'crowding' ? <LoaderCircle size={13} className="spin"/> : null}Crowding benchmark</button><span className="ws-hint">A tracer among fixed crowders against obstruction theory (about 8 s).</span></div>
            {crowding && <p className={crowding.check.passed ? 'ws-ok' : 'ws-warn'}>{crowding.check.passed ? <Check size={12}/> : <TriangleAlert size={12}/>} D/D₀ = {num(crowding.relativeD)} ± {num(crowding.standardError, 2)}; theory {num(crowding.theory)}. {crowding.handover.note} <button className="ws-link" onClick={() => { setGlobals(g => ({...g, slowdown: (ctx!.defaults.slowdown.value * crowding.slowdown).toFixed(2)})); setDrawer('parameters'); }}>Use {num(crowding.slowdown)}× as extra slowdown</button></p>}</div>
        </div>}
        {experiment === 'spatial' && activeDock === 'painting' && (painting ? <PaintingView painting={painting} channels={channels} setChannels={setChannels} catalog={catalog} nameOf={nameOf} runId={live?.chunk.id}/> : <p className="ws-empty">Render the five channels from Layers › Cell Painting.</p>)}
      </div>}
    </footer>}
    {!hasRun && dock && (painting || comparison) && <footer className="ws-dock"><div className="ws-dock-body">{painting && <PaintingView painting={painting} channels={channels} setChannels={setChannels} catalog={catalog} nameOf={nameOf}/>}</div></footer>}

    {drawer && <div className="ws-drawer" role="dialog" aria-label={drawer}>
      <header><h4>{drawer === 'shortcuts' ? 'Keyboard shortcuts' : drawer[0].toUpperCase() + drawer.slice(1)}</h4><button className="ws-icon" onClick={() => setDrawer(null)} aria-label="Close"><X size={14}/></button></header>
      <div className="ws-scroll ws-pad">
        {drawer === 'shortcuts' && <table className="ws-table"><tbody>{[['Space', 'Play or pause'], ['← →', 'Step one frame (5 min in the light experiment)'], ['H', 'Whole cell'], ['C', 'Slice: off, X, Y, Z'], ['1 2 3', 'Compartments, EM density, Cell Painting'], ['F', 'Follow the selected molecule'], ['L', 'Layers and experiment panel'], ['I', 'Inspector'], ['D', 'Timeline and readouts'], ['P', 'Parameters'], ['Esc', 'Clear the selection or close a drawer'], ['?', 'This list']].map(([k, v]) => <tr key={k}><td><kbd>{k}</kbd></td><td>{v}</td></tr>)}</tbody></table>}
        {drawer !== 'shortcuts' && experiment === 'light' && <LightDrawer lp={lp} kind={drawer}/>}
        {drawer === 'parameters' && experiment === 'spatial' && <>
          <div className="ws-grid">{catalog.inputs.map(s => field_(s, globals[s.key] ?? '', v => setGlobals(g => ({...g, [s.key]: v}))))}</div>
          <p className="ws-hint">Slowdown in this cell: {ctx!.defaults.slowdown.value}× ({ctx!.defaults.slowdown.provenance.kind}). {ctx!.defaults.slowdown.provenance.note}</p>
          <p className="ws-hint">Every binding, permeability, synthesis, decay and conversion value is a hypothesis you set. No model here derives them from a structure; a structure enters the dynamics only through its radius.</p>
        </>}
        {drawer === 'solver' && experiment === 'spatial' && <>
          <p className="ws-hint">{catalog.engine.numericalMethod}</p><ul className="ws-eq">{catalog.engine.equations.map(e => <li key={e}>{e}</li>)}</ul>
          {live ? <><dl className="ws-dl"><div><dt>Time step</dt><dd>{num(live.chunk.solver.dt * 1e6)} µs</dd></div><div><dt>Steps per frame</dt><dd>{live.chunk.solver.stepsPerFrame}</dd></div><div><dt>Frame</dt><dd>{num(simDt * 1000)} ms simulated</dd></div>
            {live.chunk.solver.crossingProbability && Object.entries(live.chunk.solver.crossingProbability).map(([k, v]) => <div key={k}><dt>Crossing chance · {k}</dt><dd>{num(v as number)} per stopped move</dd></div>)}</dl>
            <ul className="ws-checks">{live.chunk.checks.map(c => <li key={c.name} className={c.passed ? 'ok' : 'bad'}>{c.passed ? <Check size={12}/> : <TriangleAlert size={12}/>}<div><strong>{c.name}</strong> · {c.threshold}<small>{c.detail}</small></div></li>)}</ul></> : <p className="ws-hint">Release a run to see its numerical checks.</p>}
          <h5>Benchmarks of the engine</h5><table className="ws-table"><tbody>{catalog.engine.benchmarks.map(b => <tr key={b.name}><td>{b.name}</td><td>{b.reference}</td><td>{b.acceptance}</td></tr>)}</tbody></table>
        </>}
        {drawer === 'provenance' && experiment === 'spatial' && <>
          <dl className="ws-dl"><div><dt>Cell context</dt><dd>{ctx!.species} · {ctx!.cell}</dd></div><div><dt>Geometry</dt><dd>{ctx!.geometryLabel} · {ctx!.resolution}</dd></div>
            {contextId === HELA && <><div><dt>Image</dt><dd>{d.citation[0]}</dd></div><div><dt>Segmentations</dt><dd>{d.citation[1]}</dd></div><div><dt>Licence</dt><dd>{d.licence}</dd></div></>}
            {live && <><div><dt>This run</dt><dd className="mono">{live.chunk.id} · {live.chunk.sha256.slice(0, 16)}…</dd></div><div><dt>Engine</dt><dd>{catalog.engine.name} {catalog.engine.version} · seed {globals.seed}</dd></div>
              {species.filter(s => s.asset).map(s => <div key={s.key}><dt>Structure · {s.name}</dt><dd className="mono">{s.asset} · {s.sha256?.slice(0, 16)}…</dd></div>)}</>}</dl>
          {registration && contextId === HELA && <><h5>Registration of image, masks and simulation</h5><ul className="ws-checks">{registration.checks.map((c: any) => <li key={c.name} className={c.passed ? 'ok' : 'bad'}>{c.passed ? <Check size={12}/> : <TriangleAlert size={12}/>}<div><strong>{c.name}</strong><small>{c.detail}</small></div></li>)}</ul>
            <table className="ws-table"><thead><tr><th>Array</th><th>Voxel (nm)</th><th>First corner (nm)</th></tr></thead><tbody>{registration.arrays.map((a: any) => <tr key={a.array}><td>{a.array.split('/').pop()}</td><td>{a.voxelNm.join(' × ')}</td><td>{a.cornerNm.join(', ')}</td></tr>)}</tbody></table></>}
          {registry && <><h5>Cell contexts</h5><p className="ws-hint">{registry.rule} {registry.identity}</p>
            <table className="ws-table"><thead><tr><th>Context</th><th>Geometry</th>{Object.keys(registry.experiments).map(e => <th key={e}>{e === 'spatial_diffusion' ? '3D molecules' : e === 'light_pulse' ? 'Light pulse' : 'Perturbation'}</th>)}</tr></thead><tbody>
              {registry.contexts.map(c => <tr key={c.id}><td><strong>{c.name}</strong><small> {c.role}</small></td><td>{c.geometry.label}</td>{Object.keys(registry.experiments).map(e => <td key={e} title={c.experiments[e].missing.join('; ') || c.experiments[e].note || 'Qualified'}>{c.experiments[e].supported ? '● yes' : '○ ' + (c.experiments[e].missing[0] ?? 'no')}</td>)}</tr>)}</tbody></table></>}
        </>}
        {drawer === 'diagnostics' && experiment === 'spatial' && <>
          <h5>Assumptions</h5><ul className="ws-list">{catalog.engine.assumptions.map(a => <li key={a}>{a}</li>)}</ul><h5>Limits</h5><ul className="ws-list">{catalog.engine.limits.map(a => <li key={a}>{a}</li>)}</ul>
          {contextId === HELA && <><h5>Specimen caveats</h5><ul className="ws-list">{d.caveats.map(a => <li key={a}>{a}</li>)}</ul></>}
        </>}
      </div>
    </div>}
  </div>;
}

function ActivityLegend({a, particles, t}: {a: NonNullable<ReturnType<typeof activityAt>>; particles?: LpParticles | null; t?: number}) {
  const counts = particles ? countsAt(particles, frameAt(particles.time, t ?? 0)) : null;
  const rows: [string, number | null, string][] = [['Envelope · regulator', a.regulator, '◆'], ['Nucleoid · transcription', a.transcription, '▲'], ['Cytoplasm · reporter', a.reporter, '●']];
  return <div className="ws-activity" aria-label="Modelled activity">{rows.map(([name, v, sym]) => <div key={name}><span>{sym} {name}</span><i><b style={{width: (v ?? 0) * 100 + '%'}}/></i><em>{v == null ? 'n/a' : Math.round(v * 100) + ' %'}</em></div>)}
    <small>Green light {a.light ? a.light + ' µmol m⁻² s⁻¹' : 'off'} · reporter {Math.round(a.reporterMEFL).toLocaleString()} MEFL</small>
    {counts && <div className="ws-counts" aria-label="Molecules drawn in 3D">{counts.map(c => <span key={c.key} title={c.evidence}><i style={{background: c.color}}/>{c.name}: {Math.round(c.molecules).toLocaleString()}{c.weight > 1 ? ` · ${c.particles} dots` : ''}</span>)}
      <small>One reporter dot = {particles!.weight.toLocaleString()} molecules (relative; φ assumed). Each frame redraws positions: a protein crosses the cell in 87 ms.</small></div>}</div>;
}

/** Where the data axes point on screen, from the camera. Data y is up in the view. */
function Triad({camera}: {camera: Camera}) {
  const sy = Math.sin(camera.yaw), cy = Math.cos(camera.yaw), sp = Math.sin(camera.pitch), cp = Math.cos(camera.pitch);
  const axes: [string, number, number][] = [['x', cy, -sy * sp], ['y', 0, cp], ['z', -sy, -cy * sp]];
  return <svg className="ws-triad" viewBox="-30 -30 60 60" aria-label="Orientation of the data axes">{axes.map(([n, x, y]) => <g key={n}><line x1={0} y1={0} x2={x * 20} y2={-y * 20}/><text x={x * 26} y={-y * 26 + 3} textAnchor="middle">{n}</text></g>)}</svg>;
}

function Scrubber({t0, t1, t, onSeek, events, onEvent}: {t0: number; t1: number; t: number; onSeek: (t: number) => void; events: ChartEvent[]; onEvent: (index: number) => void}) {
  const ref = useRef<HTMLDivElement>(null), span = Math.max(t1 - t0, 1e-12);
  const at = (e: React.PointerEvent) => { const r = ref.current!.getBoundingClientRect(); return t0 + Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)) * span; };
  return <div className="ws-scrub" ref={ref} role="slider" aria-label="Simulated time" aria-valuemin={t0} aria-valuemax={t1} aria-valuenow={t} tabIndex={0}
    onPointerDown={e => { (e.currentTarget as Element).setPointerCapture(e.pointerId); onSeek(at(e)); }} onPointerMove={e => e.buttons === 1 && onSeek(at(e))}>
    <i className="track"/><i className="fill" style={{width: Math.max(0, Math.min(1, (t - t0) / span)) * 100 + '%'}}/>
    {events.map((e, i) => e.time >= t0 && e.time <= t1 && <button key={i} className={'tick ' + e.kind} style={{left: (e.time - t0) / span * 100 + '%'}} title={e.label} aria-label={e.label} onPointerDown={ev => ev.stopPropagation()} onClick={() => onEvent(i)}/>)}
    <i className="head" style={{left: Math.max(0, Math.min(1, (t - t0) / span)) * 100 + '%'}}/>
  </div>;
}

/** The synthetic Cell Painting set: every channel and a composite merged from the channels that are switched on, at physical proportions with a scale bar. */
function PaintingView({painting, channels, setChannels, catalog, nameOf, runId}: {painting: Painting; channels: Set<string>; setChannels: (s: Set<string>) => void; catalog: Catalog; nameOf: (k: string) => string; runId?: string}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const widthUm = painting.size[0] * painting.pixelUm[0], heightUm = painting.size[1] * painting.pixelUm[1], ratio = widthUm / heightUm;
  useEffect(() => {
    const el = canvas.current; if (!el) return;
    el.width = painting.size[0]; el.height = painting.size[1];
    const g = el.getContext('2d')!; g.globalCompositeOperation = 'source-over'; g.fillStyle = '#000'; g.fillRect(0, 0, el.width, el.height); g.globalCompositeOperation = 'lighter';
    let cancelled = false;
    Object.entries(painting.images).filter(([k]) => channels.has(k)).forEach(([, b64]) => { const img = new Image(); img.onload = () => { if (!cancelled) g.drawImage(img, 0, 0); }; img.src = 'data:image/png;base64,' + b64; });
    return () => { cancelled = true; };
  }, [painting.id, [...channels].sort().join()]);
  const bar = 10 / widthUm * 100;
  const save = () => { const url = canvas.current?.toDataURL('image/png'); if (url) void exportFile('cell-painting-model.png', {base64: url.split(',')[1]}); };
  return <div className="ws-paint">
    <figure className="merged" style={{aspectRatio: String(ratio)}}><canvas ref={canvas} aria-label="Merged composite of the selected modelled channels"/><i className="bar" style={{width: bar + '%'}}><span>10 µm</span></i>
      <figcaption>Merged · {[...channels].join(' + ') || 'no channel'} · {widthUm.toFixed(1)} × {heightUm.toFixed(1)} µm · pixels {Math.round(painting.pixelUm[0] * 1000)} × {Math.round(painting.pixelUm[1] * 1000)} nm, drawn at physical proportions · {painting.psfFwhmNm} nm point spread function
        <button className="ws-link" onClick={save}><Download size={12}/> Save</button></figcaption></figure>
    <div className="channels">{Object.entries(painting.images).map(([k, b64]) => <figure key={k} className={channels.has(k) ? '' : 'off'}>
      <button onClick={() => { const n = new Set(channels); n.has(k) ? n.delete(k) : n.add(k); setChannels(n); }} aria-pressed={channels.has(k)} title="Include this channel in the merged image" style={{aspectRatio: String(ratio)}}><img src={'data:image/png;base64,' + b64} alt={k + ' channel'}/></button>
      <figcaption><i style={{background: painting.channels[k].color}}/><strong>{k}</strong> {painting.channels[k].stain}<small>{k === 'Probe' ? `simulated molecule positions${runId ? ' of run ' + runId.slice(0, 8) : ''}` : Object.entries(catalog.painting[k]?.weights ?? {}).map(([c, w]) => `${nameOf(c).toLowerCase()} × ${w}`).join(', ')}</small></figcaption></figure>)}</div>
    <p className="ws-hint"><span className="ws-tag synthetic">Synthetic image</span> {painting.evidence.statement} {painting.limitations.join(' · ')}</p>
  </div>;
}
