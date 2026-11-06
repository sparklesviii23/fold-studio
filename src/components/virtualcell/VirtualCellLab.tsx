import {useEffect, useMemo, useState, type ReactNode} from 'react';
import {Activity, ArrowLeft, ChevronDown, Dna, Microscope, Download, GitBranch, History, LoaderCircle, Pill, Plus, RefreshCw, Scissors, Search, Sparkles, Trash2, TriangleAlert, VolumeX, X} from 'lucide-react';
import {exportFile, rpc} from '../../lib/api';
import {fmt, TimeChart} from '../mechanistic/MechCharts';
import CellStage, {type CellSettings} from '../../cell/CellStage';
import {layerNames} from '../../cell/organelles';
import ProteinWorkspace, {Enrichment} from './ProteinWorkspace';
import CellCycleTimeline from './CellCycleTimeline';
import SimulationResult from './SimulationResult';
import RnaProtein from './RnaProtein';
import CellPainting from './CellPainting';
import BenchmarkPanel from './BenchmarkPanel';
import RegulatoryPanel from './RegulatoryPanel';
import GpuTasks from '../GpuTasks';
import CellResearchNavigation, {type CellResearchView} from './CellResearchNavigation';
import TrainingLab from './TrainingLab';
import {Coverage, Snapshots} from './StatePanels';
import './virtualcell.css';

type Readout = 'expression' | 'fitness' | 'metabolism' | 'signalling';
type Sim = 'overexpress' | 'knockdown' | 'knockout' | 'drug' | 'protein' | 'cycle' | 'results' | 'signature' | 'design' | 'history';
const OP_LABEL: Record<string, string> = {gene_overexpression: 'Over-express', gene_knockdown: 'Knock down', gene_knockout: 'Knock out', small_molecule: 'Drug'};
const CHANNEL_COLOR: Record<string, string> = {dna: '#3d6bff', mito: '#ff3a52', er: '#38ff80', golgi: '#ffd633', rna: '#ff8033', vesicles: '#f066e6'};
const STYLE = {channels: 2, illustrated: 0};
const stepLabel = (h: any) => `${OP_LABEL[h.op]} ${h.op === 'small_molecule' ? `${h.drug} ${h.concentration} µM` : h.gene}`;

function Terms({terms}: {terms?: any[]}) {
  if (!terms?.length) return null;
  return <p className="vc-terms">{terms.map(t => <span key={t.id} title={t.citation}>{t.name} · {t.licence}{t.nonCommercial ? ' · non-commercial' : ''}</span>)}</p>;
}

function Bars({rows}: {rows: {gene: string; delta: number}[]}) {
  const max = Math.max(1e-9, ...rows.map(r => Math.abs(r.delta)));
  return <div className="vc-bars">{rows.map(r => <div key={r.gene} className="vc-bar">
    <code>{r.gene}</code>
    <div className="vc-bar-track"><i className={r.delta < 0 ? 'down' : 'up'} style={{width: `${Math.abs(r.delta) / max * 50}%`, [r.delta < 0 ? 'right' : 'left']: '50%'} as any}/></div>
    <span className="mono">{r.delta > 0 ? '+' : ''}{fmt(r.delta, 3)}</span>
  </div>)}</div>;
}

/** Compartment programmes as a radar: mean change of each compartment's genes; the bright ring is the baseline. */
function Radar({channels}: {channels: any[]}) {
  const R = 84, C = 120, n = Math.max(1, channels.length);
  const pt = (i: number, v: number) => { const a = -Math.PI / 2 + i * 2 * Math.PI / n, r = R * (0.5 + Math.max(-0.5, Math.min(0.5, v / 2))); return [C + r * Math.cos(a), C + r * Math.sin(a)]; };
  const poly = channels.map((c, i) => pt(i, c.score ?? 0).join(',')).join(' ');
  return <svg className="vc-radar" viewBox="0 0 240 240" role="img" aria-label="Compartment programme radar">
    {[0.25, 0.5, 0.75, 1].map(f => <circle key={f} cx={C} cy={C} r={R * f} className={f === 0.5 ? 'base' : ''}/>)}
    {channels.map((c, i) => { const [x, y] = pt(i, 1); const [lx, ly] = pt(i, 1.42); return <g key={c.id}><line x1={C} y1={C} x2={x} y2={y}/>
      <text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle">{c.name.split(' ·')[0]}</text></g>; })}
    <polygon points={poly}/>
    {channels.map((c, i) => { const [x, y] = pt(i, c.score ?? 0); return <circle key={c.id} cx={x} cy={y} r="3.5" fill={CHANNEL_COLOR[c.id]}><title>{`${c.name}: ${c.score == null ? 'no genes' : fmt(c.score, 3) + ' SD'} (${c.genes} genes)`}</title></circle>; })}
  </svg>;
}

function Panel({title, sub, children, actions}: {title: string; sub?: string; children: ReactNode; actions?: ReactNode}) {
  return <section className="vc-card"><header><div><h3>{title}</h3>{sub && <small>{sub}</small>}</div>{actions}</header>{children}</section>;
}

/** Analyse › Virtual Cell: persistent cells you perturb, read out, branch and design against (scientific/virtual_cell.py). */
const RETURN_KEY = 'fold-vcell-return';

export default function VirtualCellLab({onOpenStructure, projectId = ''}: {onOpenStructure?: (id: string, label: string) => Promise<void>; projectId?: string} = {}) {
  const [catalog, setCatalog] = useState<any>(null), [cells, setCells] = useState<any[]>([]), [current, setCurrent] = useState<any>(null);
  const [open, setOpen] = useState<Sim | null>('overexpress'), [tab, setTab] = useState<Readout>('expression');
  const [readout, setReadout] = useState<any>(null), [design, setDesign] = useState<any>(null), [busy, setBusy] = useState(''), [error, setError] = useState('');
  const [gene, setGene] = useState(''), [genes, setGenes] = useState(''), [drug, setDrug] = useState(''), [dose, setDose] = useState('');
  const [targetCell, setTargetCell] = useState(''), [up, setUp] = useState(''), [down, setDown] = useState(''), [withDrugs, setWithDrugs] = useState(true);
  const [context, setContext] = useState('K562'), [view, setView] = useState<'channels' | 'illustrated'>('channels');
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  const [query, setQuery] = useState(''), [protein, setProtein] = useState<any>(null), [enrich, setEnrich] = useState<any>(null);
  const [coverage, setCoverage] = useState<any>(null), [snaps, setSnaps] = useState<any[]>([]), [comparison, setComparison] = useState<any>(null);
  const [rnaProtein, setRnaProtein] = useState<any>(null), [mode, setMode] = useState<CellResearchView>('3d');
  const [results, setResults] = useState<any[] | null>(null), [result, setResult] = useState<any>(null);
  const [cycle, setCycle] = useState<any>(null), [cycleTime, setCycleTime] = useState(0), [gf, setGf] = useState('1'), [hours, setHours] = useState('120'), [notice, setNotice] = useState('');

  async function call<T>(text: string, action: string, payload: any = {}) {
    setBusy(text); setError('');
    try { return await rpc<T>(action, payload); } catch (e) { setError(String(e).replace(/^Error:\s*/, '')); return undefined; } finally { setBusy(''); }
  }
  async function refresh() {
    const c = await call<any>('', 'vcell_catalog'); if (c) setCatalog(c);
    if (c?.reference.ready) { const l = await call<any[]>('', 'vcell_list'); if (l) setCells(l); }
  }
  useEffect(() => {
    refresh();
    let back: any = null;
    try { back = JSON.parse(sessionStorage.getItem(RETURN_KEY) ?? 'null'); sessionStorage.removeItem(RETURN_KEY); } catch { /* storage unavailable */ }
    if (back?.cellId) (async () => {                       // returning from the Molecular Viewer: same cell, same protein
      const r = await call<any>('Returning to the cell', 'vcell_get', {id: back.cellId}); if (!r) return;
      setCurrent(r); loadState(back.cellId); observe('expression', r);
      if (back.query) { setQuery(back.query); setOpen('protein'); const pr = await call<any>('Resolving protein', 'vcell_protein', {id: back.cellId, query: back.query}); if (pr) { setProtein(pr); const layers: string[] = pr.localization?.layers ?? [];
        setHidden(layers.length ? Object.fromEntries(['dna', 'mito', 'er', 'golgi', 'rna', 'vesicles'].map(id => [id, !layers.includes(id)])) : {}); } }
      if (back.notice) setNotice(back.notice);
    })();
  }, []);
  async function openStructure(id: string, name: string, selectedGene = protein?.symbol ?? query) {
    if (!onOpenStructure) return;
    try { sessionStorage.setItem(RETURN_KEY, JSON.stringify({cellId: current.cell.id, query: selectedGene, notice: `Returned from ${name}.`})); } catch { /* storage unavailable */ }
    try { await onOpenStructure(id, `${current.context.name} · ${selectedGene}`); } catch (e) { setError(String(e).replace(/^Error:\s*/, '')); }
  }
  useEffect(() => {
    if (!catalog?.reference.job?.running && !catalog?.annotations?.job?.running) return;
    const t = setTimeout(refresh, 3000); return () => clearTimeout(t);
  }, [catalog]);

  async function observe(kind: Readout = tab, cell = current) {
    if (!cell) return;
    setTab(kind);
    const r = await call<any>('Computing readout', 'vcell_observe', {id: cell.cell.id, readout: kind, genes: genes.split(/[\s,;]+/).filter(Boolean)});
    if (r) setReadout(r);
    if (r?.running) setTimeout(() => observe(kind, cell), 3000);
  }
  async function loadState(id: string) {
    const [c, s] = await Promise.all([rpc<any>('vcell_coverage', {id}).catch(() => null), rpc<any[]>('vcell_snapshot_list', {id}).catch(() => [])]);
    setCoverage(c); setSnaps(s ?? []);
  }
  async function openCell(id: string) { const r = await call<any>('Opening cell', 'vcell_get', {id}); if (r) { setCurrent(r); setDesign(null); setCycle(null); setComparison(null); loadState(id); observe('expression', r); } }
  async function after(r: any) { if (r) { setCurrent(r); setDesign(null); const l = await call<any[]>('', 'vcell_list'); if (l) setCells(l); loadState(r.cell.id); observe(tab === 'expression' ? tab : 'expression', r); } }
  async function runCycle(g = Number(gf), h = Number(hours), at?: number) {
    const r = await call<any>('Integrating the cell-cycle model (about 10 s the first time)', 'vcell_cycle_run', {id: current.cell.id, gf: g, hours: h});
    if (r) { setCycle(r); setCycleTime(at ?? r.time[0]); setGf(String(r.gf)); setHours(String(r.hours)); }
  }
  async function saveSnapshot(label: string, t?: number) {
    const sim = t != null && cycle ? {key: cycle.key, time: t} : undefined;
    const r = await call<any>('Saving state', 'vcell_snapshot_save', {id: current.cell.id, label: label || (sim ? `t = ${t!.toFixed(1)} h` : ''), simulation: sim});
    if (r) { setNotice(`Saved snapshot ${r.label || r.id.slice(0, 8)} (${r.kind}).`); loadState(current.cell.id); }
  }
  async function restoreSnapshot(sid: string) {
    const s = await call<any>('Restoring state', 'vcell_snapshot_get', {id: current.cell.id, snapshot: sid}); if (!s) return;
    if (s.simulation) await runCycle(s.simulation.parameters.GF, s.simulation.hours, s.simulation.time);
    setNotice(`Restored ${s.label || s.id.slice(0, 8)}${s.simulation ? ` at t = ${s.simulation.time.toFixed(1)} h (${s.simulation.phase ?? 'unlabelled'})` : ''}.${s.intact ? '' : ' Integrity check FAILED: the file changed after saving.'}${s.cellChanged ? ' This cell\'s history has changed since the snapshot; branch from the history to recreate it exactly.' : ''}`);
  }
  async function exportSnapshot(sid: string) { const b = await call<any>('Exporting', 'vcell_snapshot_export', {id: current.cell.id, snapshot: sid}); if (b) exportFile(`fold-virtual-cell-state-${sid.slice(0, 8)}.json`, {text: JSON.stringify(b, null, 1)}); }
  async function importSnapshot(bundle: any) { if (!bundle) { setError('That file is not JSON.'); return; } const r = await call<any>('Importing', 'vcell_snapshot_import', {id: current.cell.id, bundle}); if (r) { setNotice('Imported ' + r.label + '.'); loadState(current.cell.id); } }
  async function deleteSnapshot(sid: string) { const r = await call<any[]>('Deleting', 'vcell_snapshot_delete', {id: current.cell.id, snapshot: sid}); if (r) setSnaps(r); }
  async function compareSnapshots(a: string, b: string) { const r = await call<any>('Comparing', 'vcell_snapshot_compare', {id: current.cell.id, a, b}); if (r) setComparison(r); }
  async function create() { after(await call('Creating a cell', 'vcell_create', {name: '', context})); }
  async function apply(op: string) {
    const payload = op === 'small_molecule' ? {id: current.cell.id, op, drug, concentration: Number(dose)} : {id: current.cell.id, op, gene};
    const r = await call<any>('Applying perturbation', 'vcell_perturb', payload); if (r) { setGene(''); after(r); }
  }
  async function branch(step: number) { after(await call('Branching', 'vcell_branch', {id: current.cell.id, step})); }
  async function remove(id: string) {
    await call('Deleting', 'vcell_delete', {id}); if (current?.cell.id === id) setCurrent(null);
    const l = await call<any[]>('', 'vcell_list'); if (l) setCells(l);
  }
  async function designFor() {
    const target = targetCell ? {cellId: targetCell} : {up: up.split(/[\s,;]+/).filter(Boolean), down: down.split(/[\s,;]+/).filter(Boolean)};
    const r = await call<any>('Searching thousands of interventions', 'vcell_design', {id: current.cell.id, target, limit: 15, drugs: withDrugs}); if (r) setDesign(r);
  }

  async function findProtein(q = query) {
    const r = await call<any>('Resolving protein', 'vcell_protein', {id: current.cell.id, query: q});
    if (!r) return;
    setProtein(r);
    const layers: string[] = r.localization?.layers ?? [];       // show only the compartments it is annotated to (compartment level)
    setHidden(layers.length ? Object.fromEntries(['dna', 'mito', 'er', 'golgi', 'rna', 'vesicles'].map(id => [id, !layers.includes(id)])) : {});
  }
  async function enrichment() { const r = await call<any>('Testing Reactome pathways', 'vcell_enrichment', {id: current.cell.id}); if (r) setEnrich(r); }
  async function installAnnotations() { const c = await call<any>('Starting', 'vcell_annotations_install'); if (c) setCatalog(c); }

  const ref = catalog?.reference, atlas = catalog?.drugs, notes = catalog?.annotations;
  const drugInfo = atlas?.list.find((d: any) => d.name.toLowerCase() === drug.trim().toLowerCase());
  const k562 = current?.cell.context === 'K562';
  const kind = catalog?.contexts.find((c: any) => c.id === current?.cell.context)?.kind;
  const channels: any[] = current?.state.channels ?? [];
  const cycleVisual = useMemo(() => {                    // backend-defined rule (virtual_cell_cycle.VISUAL); recomputed at the scrubbed time
    if (!cycle?.visual) return null;
    const t: number[] = cycle.time; let i = 0; for (let k = 1; k < t.length; k++) if (Math.abs(t[k] - cycleTime) < Math.abs(t[i] - cycleTime)) i = k;
    const v: number[] = cycle.series[cycle.visual.variable]; const max = Math.max(...v, 1e-12), x = v[i] / max, lab = cycle.analysis.labels[i];
    return {...cycle.visual, normalised: x, gain: cycle.visual.base + cycle.visual.scale * x, time: t[i],
            phase: cycle.analysis.quiescent ? 'quiescent (G0-like)' : lab == null ? 'unlabelled' : cycle.analysis.phases[lab]};
  }, [cycle, cycleTime]);
  const settings = useMemo<CellSettings>(() => {
    const g: Record<string, number> = Object.fromEntries(channels.map(c => [c.id, c.gain]));
    if (cycleVisual) g[cycleVisual.layer] = cycleVisual.gain;
    const on = (id: string) => !hidden[id];
    return {style: STYLE[view], cut: true, slice: 0.1, glass: view === 'illustrated', animate: true, quality: 'balanced', cellType: k562 ? 'lymphocyte' : 'generic',
            layers: layerNames.map((_, i) => [on('dna'), on('dna'), on('mito'), on('er'), on('golgi'), on('rna'), on('vesicles'), true, false][i]),
            gains: [g.dna ?? 1, 1, g.mito ?? 1, g.er ?? 1, g.golgi ?? 1, g.rna ?? 1, g.vesicles ?? 1, 1]};
  }, [channels, hidden, view, k562, cycleVisual]);

  const status = <>
    {error && <div className="vc-error"><TriangleAlert size={14}/>{error}</div>}
    {busy && <div className="vc-busy"><LoaderCircle size={14} className="spin"/>{busy}</div>}
    {notice && !busy && <div className="vc-busy" role="status">{notice}<button className="vc-icon" title="Dismiss" onClick={() => setNotice('')}><X size={12}/></button></div>}
  </>;

  // ---------------------------------------------------------------- cells home
  if (mode === 'training') return <div className="vc-home"><button className="text-button" onClick={() => setMode('3d')}><ArrowLeft size={14}/>Back to cells</button><TrainingLab projectId={projectId} onOpenRuns={() => setMode('runs')}/></div>;
  if (!current && mode === 'runs') return <div className="vc-home">
    <button className="text-button" onClick={() => setMode('3d')}><ArrowLeft size={14}/>Back to cells</button>
    <GpuTasks projectId={projectId} embedded/>
  </div>;
  if (!current) return <div className="vc-home">
    <header className="vc-head">
      <div><span className="eyebrow">Analyse · Virtual Cell</span><h1>Virtual cells</h1>
        <p>Persistent cells you perturb, read out, branch and design against. Every readout says what kind of evidence it is and which data it came from.</p></div>
      <div className="button-row"><button className="button" onClick={() => setMode('training')}><Sparkles size={14}/>Cell AI training</button>{projectId && <button className="button" onClick={() => setMode('runs')}><Activity size={14}/>Runs & terminal</button>}<button className="text-button" onClick={refresh}><RefreshCw size={13}/>Refresh</button></div>
    </header>
    {status}
    <div className="vc-home-grid">
      <section className="vc-card vc-new">
        <header><div><h3>New cell</h3><small>Choose a context</small></div></header>
        {!ref ? <small>Loading…</small> : !ref.ready ? <>
          <small>{ref.inputsReady ? 'Build the K-562 reference from the Norman 2019, Replogle 2022 and DepMap data in your library (about 2 min, local).' : 'Install Norman 2019 and DepMap in Oncology Universe first.'}</small>
          <button disabled={!ref.inputsReady || ref.job?.running} onClick={() => call('Starting', 'vcell_reference_build').then(c => c && setCatalog(c))}>{ref.job?.running ? 'Building…' : 'Build reference'}</button>
          {ref.job?.log && <pre className="vc-log">{ref.job.log}</pre>}
        </> : <>
          <select value={context} onChange={e => setContext(e.target.value)}>{catalog.contexts.map((c: any) => <option key={c.id} value={c.id}>{c.name}{c.kind === 'tahoe' ? ' · drugs + knockouts' : c.kind === 'depmap' ? ' · measured baseline + knockouts' : ' · genetic + drugs'}</option>)}</select>
          <button onClick={create}><Plus size={14}/>Create cell</button>
          <small>K-562: {ref.manifest.singles} measured activations, {ref.manifest.knockdown?.knockdowns?.toLocaleString() ?? 0} measured knockdowns, DepMap fitness. Tahoe lines: {atlas?.list.length ?? 0} drugs at measured doses. Hep G2 (parental, CVCL_0027): DepMap 24Q4 measured RNA and knockout fitness; HepG2/C3A is a separate Tahoe derivative.</small>
        </>}
      </section>
      {cells.map(c => <div key={c.id} className="vc-card vc-cell-card" role="button" tabIndex={0} onClick={() => openCell(c.id)} onKeyDown={e => e.key === 'Enter' && openCell(c.id)}>
        <span className="vc-chip">{(catalog?.contexts.find((x: any) => x.id === c.context)?.name) ?? c.context}</span>
        <strong>{c.name}</strong>
        <small>{c.steps} step{c.steps === 1 ? '' : 's'}{c.parent ? ` · branched from ${c.parent.name} @ ${c.parent.step}` : ''}</small>
        <small className="mono">{c.id.slice(0, 12)} · {c.created.slice(0, 16).replace('T', ' ')}</small>
        <button className="vc-icon vc-del" title="Delete this cell" onClick={e => { e.stopPropagation(); remove(c.id); }}><Trash2 size={13}/></button>
      </div>)}
    </div>
    <div className="vc-home-grid two">
      <section className="vc-card">
        <header><div><h3>Drug atlas · Tahoe-100M</h3><small>{atlas?.ready ? (atlas.complete ? `Complete · ${atlas.list.length} drugs · ${catalog.contexts.length - 1} cell lines` : `${atlas.filesDone} of 1,026 files · ${catalog.contexts.length - 1} cell lines so far`) : 'Not installed'}</small></div></header>
        {atlas?.benchmark ? <p className="caption">Held-out Pearson r (top 200 significant genes, active conditions): dose interpolation {fmt(atlas.benchmark.interpolation.mean, 2)}, transfer to an unseen cell line {fmt(atlas.benchmark.transfer.mean, 2)} (generic drug-response baseline {fmt(atlas.benchmark.genericResponse?.mean, 2)}), single replicate plates {fmt(atlas.benchmark.replicatePlates.mean, 2)}.</p> : <small>Benchmark not run yet.</small>}
      </section>
      <section className="vc-card vc-resources">
        <header><div><h3>Data and models</h3><small>Every resource with its licence</small></div></header>
        <div className={'vc-res ' + (notes?.ready ? 'on' : '')}>
          <strong>Protein annotations · localization and pathways</strong>
          <small>{notes?.ready ? `Built ${notes.manifest.built.slice(0, 10)} · ${notes.manifest.counts.genes.toLocaleString()} genes, ${notes.manifest.counts.hpaGenes.toLocaleString()} with HPA calls, ${notes.manifest.counts.pathways.toLocaleString()} Reactome pathways${notes.manifest.reactomeRelease ? ` (release ${notes.manifest.reactomeRelease})` : ''}` : 'HPA subcellular, UniProt reviewed human, Reactome (about 50 MB, from the providers)'}</small>
          {!notes?.ready && <button disabled={notes?.job?.running} onClick={installAnnotations}>{notes?.job?.running ? 'Installing…' : 'Install annotations'}</button>}
          {notes?.job?.running && <pre className="vc-log">{notes.job.log}</pre>}
        </div>
        <div className={'vc-res ' + (catalog?.transcripts?.ready ? 'on' : '')}>
          <strong>Hep G2 transcript isoforms · ENCODE ENCSR000CPE</strong>
          <small>{catalog?.transcripts?.ready ? 'Built · RSEM transcript quantifications, 2 biological replicates, GENCODE V29 structure' : catalog?.transcripts?.inputsReady ? 'Downloaded; index not built' : 'Not downloaded (≈100 MB from ENCODE and GENCODE, md5-checked)'}</small>
          {!catalog?.transcripts?.ready && catalog?.transcripts?.inputsReady && <button disabled={catalog?.transcripts?.job?.running} onClick={() => call<any>('Starting', 'vcell_transcripts_build').then(c => c && setCatalog(c))}>{catalog?.transcripts?.job?.running ? 'Building…' : 'Build transcript index'}</button>}
        </div>
        {catalog?.resources.map((r: any) => <div key={r.id} className={'vc-res ' + (r.installed ? 'on' : '')} title={r.citation}>
          <strong>{r.name}</strong>
          <small>{r.installed ? 'Installed' : r.install} · {r.licence}{r.licenceVerified ? '' : ' (licence not yet checked)'}{r.nonCommercial ? ' · non-commercial' : ''}{r.plugin ? ' · optional plugin' : ''}</small>
          {r.benchmark?.mrr && <small className="vc-bench">In-silico knockout benchmark ({r.benchmark.targets.length} Replogle knockdowns, {r.benchmark.candidates} candidates): mean reciprocal rank {r.benchmark.mrr.gbcell != null ? `GB.Cell ${fmt(r.benchmark.mrr.gbcell, 3)}, ` : ''}co-expression {fmt(r.benchmark.mrr.pca, 3)}, chance {fmt(r.benchmark.chanceMrr, 3)}</small>}
        </div>)}
      </section>
    </div>
  </div>;

  // ---------------------------------------------------------------- studio
  const geneForm = (op: string, verb: string, placeholder: string, note: ReactNode) => <>
    <input value={gene} placeholder={placeholder} onChange={e => setGene(e.target.value)} onKeyDown={e => e.key === 'Enter' && gene.trim() && apply(op)}/>
    <button disabled={!gene.trim()} onClick={() => apply(op)}>{verb}</button><small>{note}</small></>;
  const sims: {id: Sim; label: string; icon: ReactNode; show: boolean; body: ReactNode}[] = [
    {id: 'overexpress', label: 'Overexpress gene', icon: <Sparkles size={15}/>, show: k562,
     body: geneForm('gene_overexpression', 'Apply CRISPRa', 'e.g. KLF1', `${ref?.singles.length} genes measured in Norman 2019; other panel genes use a linear model.`)},
    {id: 'knockdown', label: 'Silence gene', icon: <VolumeX size={15}/>, show: k562,
     body: geneForm('gene_knockdown', 'Apply CRISPRi', 'e.g. GATA1', `${ref?.manifest?.knockdown?.knockdowns?.toLocaleString()} knockdowns measured in Replogle 2022; median ${fmt((ref?.manifest?.knockdown?.medianRemaining ?? 0) * 100, 2)} % of the target's mRNA remains.`)},
    {id: 'knockout', label: 'Knockout gene', icon: <Scissors size={15}/>, show: true,
     body: geneForm('gene_knockout', 'Apply knockout', 'e.g. DHODH', 'Read out as fitness (DepMap), metabolism (Human-GEM) and signalling (SPARCED). No knockout transcriptome exists: use Silence gene for expression.')},
    {id: 'drug', label: 'Expose small molecule', icon: <Pill size={15}/>, show: kind !== 'depmap', body: <>
      <input list="vc-drugs" value={drug} placeholder="e.g. Trametinib" onChange={e => setDrug(e.target.value)}/>
      <datalist id="vc-drugs">{atlas?.list.map((d: any) => <option key={d.name} value={d.name}/>)}</datalist>
      <div className="vc-row"><input list="vc-doses" value={dose} placeholder="µM" inputMode="decimal" onChange={e => setDose(e.target.value)} onKeyDown={e => e.key === 'Enter' && drug.trim() && dose && apply('small_molecule')}/>
        <datalist id="vc-doses">{drugInfo?.concentrations.map((c: number) => <option key={c} value={c}/>)}</datalist>
        <button disabled={!drug.trim() || !dose} onClick={() => apply('small_molecule')}>Expose</button></div>
      <small>{drugInfo ? `Measured at ${drugInfo.concentrations.join(', ')} µM on ${drugInfo.lines} line${drugInfo.lines === 1 ? '' : 's'}. ` : `${atlas?.list.length ?? 0} drugs in Tahoe-100M. `}{k562 ? 'K-562 is not in Tahoe: the response is transferred from the Tahoe lines (measured doses only).' : 'Doses between measured ones are interpolated.'}</small></>},
    {id: 'protein', label: 'Protein & pathways', icon: <Microscope size={15}/>, show: true, body: <>
      <input value={query} placeholder="Symbol, UniProt or Ensembl, e.g. ALB" onChange={e => setQuery(e.target.value)} onKeyDown={e => e.key === 'Enter' && query.trim() && findProtein()}/>
      <button disabled={!query.trim() || !notes?.ready} onClick={() => findProtein()}>Inspect protein</button>
      <button disabled={!notes?.ready || !current.cell.history.length} onClick={enrichment}>Enrich changed genes in Reactome</button>
      <button onClick={async () => { const r = await call<any>('Comparing RNA and protein measurements', 'vcell_rna_protein', {id: current.cell.id}); if (r) setRnaProtein(r); }}>Compare RNA and protein</button>
      <small>{notes?.ready ? 'Localization (HPA, UniProt), measured expression and fitness here, Reactome pathways and PDB structures. The cell view shows only its annotated compartments.' : 'Install the protein annotations from the Virtual Cell home first.'}</small></>},
    {id: 'cycle', label: 'Cell-cycle timeline', icon: <Activity size={15}/>, show: true, body: <>
      <div className="vc-row"><label className="vc-check">GF <input value={gf} inputMode="decimal" onChange={e => setGf(e.target.value)} aria-label="Growth factor level"/></label>
        <label className="vc-check">hours <input value={hours} inputMode="numeric" onChange={e => setHours(e.target.value)} aria-label="Duration in hours"/></label></div>
      <button onClick={() => runCycle()}>Run model</button>
      <small>Gérard & Goldbeter 2009 (BioModels BIOMD0000000730), solved by the Mechanistic Lab. Generic mammalian parameters, not calibrated to {current.context.name}. GF 0–5, 24–240 h.</small></>},
    {id: 'results', label: 'Saved lab results', icon: <History size={15}/>, show: true, body: <>
      {!results ? <button onClick={async () => { const r = await call<any[]>('Reading saved laboratory records', 'vcell_results_list'); if (r) setResults(r); }}>List Cell Physics and RNA results</button>
        : <div className="vc-results">{results.length === 0 && <small>No saved records in this library.</small>}{results.map(x => <button key={x.source + x.id} className="text-button" onClick={async () => { const r = await call<any>('Opening result', 'vcell_result_get', {source: x.source, result: x.id}); if (r) setResult(r); }}>
          {x.kind?.replace(/_/g, ' ')} · {x.engine} · {x.created?.slice(0, 10)}{x.integrity ? '' : ' · integrity FAILED'}</button>)}</div>}
      <small>Read-only. These runs describe the idealised systems in their own inputs, not this cell.</small></>},
    {id: 'signature', label: 'Gene signature', icon: <Dna size={15}/>, show: true, body: <>
      <input value={genes} placeholder="Genes to read, e.g. HBG1 GATA1" onChange={e => setGenes(e.target.value)} onKeyDown={e => e.key === 'Enter' && observe('expression')}/>
      <button onClick={() => observe('expression')}>Read expression</button></>},
    {id: 'design', label: 'Design intervention', icon: <Search size={15}/>, show: true, body: <>
      <select value={targetCell} onChange={e => setTargetCell(e.target.value)}><option value="">Target: a gene direction</option>{cells.filter(c => c.id !== current.cell.id && c.context === current.cell.context).map(c => <option key={c.id} value={c.id}>Target: {c.name}</option>)}</select>
      {!targetCell && <><input value={up} placeholder="Raise, e.g. HBG1 HBG2" onChange={e => setUp(e.target.value)}/><input value={down} placeholder="Lower (optional)" onChange={e => setDown(e.target.value)}/></>}
      <label className="vc-check"><input type="checkbox" checked={withDrugs} onChange={e => setWithDrugs(e.target.checked)}/>Include drugs</label>
      <button onClick={designFor}>Search interventions</button></>},
    {id: 'history', label: 'History & branches', icon: <History size={15}/>, show: true, body: <div className="vc-history">
      {[{label: 'Baseline'}, ...current.cell.history.map((h: any) => ({label: stepLabel(h)}))].map((h, i) => <div key={i} className="vc-step"><span className="mono">{i}</span><strong>{h.label}</strong>
        <button className="vc-icon" title={`Branch a new cell from step ${i}`} onClick={() => branch(i)}><GitBranch size={13}/></button></div>)}
      <span className="eyebrow">Saved states</span>
      <Snapshots list={snaps} comparison={comparison} onSave={l => saveSnapshot(l)} onRestore={restoreSnapshot} onCompare={compareSnapshots} onExport={exportSnapshot} onImport={importSnapshot} onDelete={deleteSnapshot}/>
    </div>},
  ];

  return <div className={'vc-studio' + (mode !== '3d' ? ' vc-research-mode' : '')}>
    <div className="vc-top">
      <button className="text-button" onClick={() => { setCurrent(null); setProtein(null); setEnrich(null); setHidden({}); setCycle(null); setComparison(null); setNotice(''); refresh(); }}><ArrowLeft size={14}/>Back to cells</button>
      <span className="vc-chip">{current.context.name}</span>
      <code>{current.cell.id}</code>
      <span className="vc-top-meta">{current.cell.history.length} step{current.cell.history.length === 1 ? '' : 's'} · {current.state.composition} · <b>{current.state.evidence}</b></span>
      <button className="text-button" onClick={() => exportFile(`fold-virtual-cell-${current.cell.id.slice(0, 8)}.json`, {text: JSON.stringify(current.cell, null, 1)})}><Download size={13}/>Export</button>
      <button className="text-button" title="Context, dataset versions and checksums, coverage, capability statuses, snapshots and what is missing" onClick={async () => { const r = await call<any>('Assembling the research report', 'vcell_report', {id: current.cell.id}); if (r) exportFile(`fold-virtual-cell-report-${current.cell.id.slice(0, 8)}.json`, {text: JSON.stringify(r, null, 1)}); }}><Download size={13}/>Research report</button>
    </div>
    {status}

    <CellResearchNavigation value={mode} onChange={setMode}/>
    <aside className="vc-sims">
      <span className="vc-sims-title">Simulations</span>
      {sims.filter(s => s.show).map(s => <div key={s.id} className={'vc-sim ' + (open === s.id ? 'open' : '')}>
        <button className="vc-sim-head" onClick={() => setOpen(open === s.id ? null : s.id)}>{s.icon}<span>{s.label}</span><ChevronDown size={14}/></button>
        {open === s.id && <div className="vc-sim-body">{s.body}</div>}
      </div>)}
    </aside>

    <main className="vc-viewport">
      {mode === '3d' && <div className="vc-overlay">
        <div className="vc-view-toggle"><span>View:</span>
          {(['channels', 'illustrated'] as const).map(v => <button key={v} className={mode === '3d' && view === v ? 'active' : ''} onClick={() => { setMode('3d'); setView(v); }}>{v}</button>)}
        </div>
{mode === '3d' && <div className="vc-channel-list"><span>Channels</span>
          {channels.map(c => <button key={c.id} className={'vc-channel ' + (hidden[c.id] ? 'off' : '')} onClick={() => setHidden({...hidden, [c.id]: !hidden[c.id]})}
            title={`${c.genes} genes · mean change ${c.score == null ? '—' : fmt(c.score, 3)} SD · brightness ×${fmt(c.gain, 2)}`}>
            <i style={{background: CHANNEL_COLOR[c.id]}}/>{c.name.split(' ·')[0]}{c.score != null && Math.abs(c.score) > 0.05 && <em className={c.score > 0 ? 'up' : 'down'}>{c.score > 0 ? '▲' : '▼'}</em>}</button>)}
        </div>}
      </div>}
      {mode === 'runs' ? <GpuTasks projectId={projectId} embedded/> : mode === 'regulatory' ? <div className="vc-benchmark-view"><RegulatoryPanel cellId={current.cell.id} onError={setError} onSaved={() => loadState(current.cell.id)} onOpenRuns={() => setMode('runs')} onOpenStructure={onOpenStructure ? openStructure : undefined}/></div> : mode === 'benchmarks' ? <div className="vc-benchmark-view"><BenchmarkPanel cellId={current.cell.id} onError={setError}/></div> : mode === 'painting' ? <CellPainting cellId={current.cell.id} onError={setError}/> :
      <div className="vc-stage"><CellStage settings={settings} journey="" onJourneyDone={() => {}} onSelect={() => {}}/>
        {cycleVisual && <div className="vc-stage-cycle" role="status"><span className="vc-phase">{cycleVisual.phase}</span><span className="mono">t {cycleVisual.time.toFixed(1)} h</span>
          <small>DNA layer ×{cycleVisual.gain.toFixed(2)} · visualization rule</small></div>}</div>}
      {mode === '3d' && <><p className="vc-stage-note">Geometry is illustrative (E). Channel brightness follows this cell's predicted change in each compartment's genes. {current.state.channelSource}{cycleVisual ? ` Cell-cycle timeline open: ${cycleVisual.rule}` : ''}{protein?.symbol && protein.localization.layers.length ? ` Showing the compartments ${protein.symbol} is annotated to; position inside each compartment is not known.` : ''}</p>
      <div className="vc-timeline">{[{label: 'Baseline'}, ...current.cell.history.map((h: any) => ({label: stepLabel(h)}))].map((h, i) =>
        <button key={i} className={'vc-tl-step ' + (i === current.cell.history.length ? 'now' : '')} title={`Branch a new cell from step ${i}`} onClick={() => branch(i)}><span>{i}</span>{h.label}</button>)}</div>
      {protein && <ProteinWorkspace key={protein.symbol ?? protein.resolution?.query} protein={protein} cellId={current.cell.id} onError={setError} onSaved={() => loadState(current.cell.id)} onOpenStructure={onOpenStructure ? openStructure : undefined} onClose={() => { setProtein(null); setHidden({}); }}/>}</>}
      {enrich && <Enrichment r={enrich} onClose={() => setEnrich(null)}/>}
      {result && <SimulationResult r={result} onClose={() => setResult(null)}/>}
      {rnaProtein && <RnaProtein r={rnaProtein} onClose={() => setRnaProtein(null)}/>}
      {cycle && <CellCycleTimeline run={cycle} time={cycleTime} onTime={setCycleTime} onSnapshot={t => saveSnapshot('', t)} onClose={() => setCycle(null)}/>}
    </main>

    <aside className="vc-insights">
      <Panel title="Data coverage" sub={`${current.context.name} · what this cell context actually has`}><Coverage coverage={coverage}/></Panel>
      <Panel title="Compartment programmes" sub={`${current.context.name} · mean change per compartment (SD units)`}><Radar channels={channels}/></Panel>
      <Panel title="Most changed transcripts" sub={`${current.context.name} · vs baseline`}>{current.state.changed.length ? <Bars rows={current.state.changed}/> : <small>Unperturbed baseline.</small>}</Panel>
      {design && <Panel title="Designed interventions" sub={design.space} actions={<button className="vc-icon" title="Close" onClick={() => setDesign(null)}><X size={13}/></button>}><Result r={design}/></Panel>}
      <Panel title="Readouts" sub="Choose what to observe">
        <div className="cosmos-segment">{(['expression', 'fitness', 'metabolism', 'signalling'] as Readout[]).map(k => <button key={k} className={tab === k ? 'active' : ''} onClick={() => observe(k)}>{k[0].toUpperCase() + k.slice(1)}</button>)}</div>
        {readout && readout.readout === tab && <Result r={readout}/>}
      </Panel>
      <Panel title="Compartment genes" sub="Genes behind each channel, largest change first">
        <table className="vc-table"><thead><tr><th>Gene</th><th>Compartment</th><th>Change (SD)</th></tr></thead>
          <tbody>{channels.flatMap(c => c.top.map((t: any) => <tr key={c.id + t.gene}><td><i className="vc-dot" style={{background: CHANNEL_COLOR[c.id]}}/>{t.gene}</td><td>{c.name}</td><td className={t.z < 0 ? 'down' : 'up'}>{t.z > 0 ? '+' : ''}{fmt(t.z, 2)}</td></tr>))}</tbody></table>
      </Panel>
    </aside>
  </div>;
}

function Result({r}: {r: any}) {
  if (r.readout === 'expression') return <div className="vc-result">
    <p className="vc-evidence"><b>{r.evidence}</b> · {r.composition} · {r.unit}</p>
    {r.notModelled && <p className="vc-warn">{r.notModelled}</p>}
    {r.knockdownEfficiency && <p className="caption">On-target knockdown (target mRNA remaining vs controls): {r.knockdownEfficiency.map((k: any) => `${k.gene} ${k.remaining == null ? 'not measured' : fmt(k.remaining * 100, 2) + ' %'}`).join(' · ')}. {r.knockdownNote}</p>}
    {r.benchmark && <p className="caption">Held-out accuracy of this transition ({r.benchmark.task}): {r.benchmark.pearson ? `Pearson r ${fmt(r.benchmark.pearson.mean, 2)}` : ''}{r.benchmark.replicatePlates ? `, replicate plates ${fmt(r.benchmark.replicatePlates.mean, 2)}` : ''}{r.benchmark.pearsonTop20 ? `, top-20 genes ${fmt(r.benchmark.pearsonTop20.mean, 2)}` : ''}{r.benchmark.baseline ? `; average-effect baseline ${fmt(r.benchmark.baseline.pearson.mean, 2)}` : ''}. {r.benchmark.note}</p>}
    {r.requested?.length > 0 && <Table rows={r.requested}/>}
    {r.notInPanel?.length > 0 && <small>Not in the panel: {r.notInPanel.join(', ')}</small>}
    <span className="eyebrow">Largest changes</span><Table rows={r.top}/>
    <small>{r.baselineNote}</small><Terms terms={r.terms}/>
  </div>;
  if (r.readout === 'fitness') return <div className="vc-result">
    <p className="vc-evidence"><b>{r.evidence}</b> · {r.meaning}</p>
    {r.empty && <small>{r.empty}</small>}
    {r.rows.length > 0 && <table className="vc-table"><thead><tr><th>Gene</th><th>Chronos</th><th>Call</th><th>Expression log₂(TPM+1)</th></tr></thead>
      <tbody>{r.rows.map((x: any) => <tr key={x.gene}><td>{x.gene}</td><td>{x.chronos == null ? '—' : fmt(x.chronos, 3)}</td><td>{x.call ?? 'not screened'}</td><td>{x.expressionTpmLog1p == null ? '—' : fmt(x.expressionTpmLog1p, 3)}</td></tr>)}</tbody></table>}
    {r.notModelled && <p className="vc-warn">{r.notModelled}</p>}{r.knockdownNote && <small>{r.knockdownNote}</small>}{r.overexpressionNote && <small>{r.overexpressionNote}</small>}<Terms terms={r.terms}/>
  </div>;
  if (r.readout === 'metabolism') return <div className="vc-result">
    <p className="vc-evidence"><b>{r.evidence}</b> · {r.meaning ?? ''}</p>
    {r.empty && <small>{r.empty}</small>}{r.unavailable && <p className="vc-warn">{r.unavailable}</p>}
    {r.running && <small><LoaderCircle size={12} className="spin"/> Solving Human-GEM (about 10 s)…</small>}
    {r.failed && <pre className="vc-log">{r.log}</pre>}
    {r.relativeGrowth !== undefined && <>
      <div className="quiet-panel"><span>Relative biomass growth</span><strong>{r.relativeGrowth == null ? '—' : fmt(r.relativeGrowth * 100, 3) + ' %'}</strong>
        <small>{r.reactionsRemoved.length} reactions removed · {r.genes.filter((g: any) => !g.inModel).map((g: any) => g.gene).join(', ') || 'all genes'}{r.genes.some((g: any) => !g.inModel) ? ' not in the metabolic model' : ' mapped'} · {r.medium}</small></div>
      {r.crossCheck && <p className={r.crossCheck.agree ? 'caption' : 'vc-warn'}>Cross-check with DepMap: model says {r.crossCheck.metabolicModel}, measured {r.crossCheck.depmap}. {r.crossCheck.agree ? 'The two agree.' : r.crossCheck.note}</p>}
    </>}
    <Terms terms={r.terms}/>
  </div>;
  if (r.readout === 'signalling') return <div className="vc-result">
    <p className="vc-evidence"><b>{r.evidence}</b> · {r.meaning}</p>
    {r.empty && <small>{r.empty}</small>}{r.unavailable && <p className="vc-warn">{r.unavailable}</p>}
    {r.running && <small><LoaderCircle size={12} className="spin"/> Simulating 24 h of SPARCED (about 30 s)…</small>}
    {r.failed && <pre className="vc-log">{r.log}</pre>}
    {r.outputs && <>
      <p className="caption">mRNA inputs changed: {r.applied.map((a: any) => `${a.gene} ×${fmt(a.fold, 3)}`).join(' · ')}{r.notInModel?.length ? ` · not in SPARCED: ${r.notInModel.length}` : ''} · solver {r.diagnostics.reliable ? 'reliable (tolerance and conservation checks pass)' : 'check failed: treat with caution'}</p>
      <div className="vc-sig-grid">{r.outputs.map((o: any) => <figure key={o.species}><figcaption>{o.species} · {o.meaning} · 24 h ratio {o.endRatio == null ? '—' : fmt(o.endRatio, 3)}</figcaption>
        <TimeChart time={r.hours} timeUnit="h" unit={o.unit} series={[{id: 'b', label: 'Baseline', values: o.baseline}, {id: 'p', label: 'This cell', values: o.perturbed}]}/></figure>)}</div>
    </>}
    <Terms terms={r.terms}/>
  </div>;
  if (r.readout === 'design') return <div className="vc-result">
    <p className="vc-evidence">Searched {r.searched.toLocaleString()} interventions · score: {r.score}</p>
    <table className="vc-table"><thead><tr><th>Intervention</th><th>Kind</th><th>Score</th><th>Cosine</th><th>Evidence</th></tr></thead>
      <tbody>{r.candidates.map((c: any) => <tr key={c.ops.map((o: any) => o.label).join('+')}><td>{c.ops.map((o: any) => o.label).join(' + ')}</td><td>{c.kind}</td><td>{fmt(c.score, 3)}</td><td>{fmt(c.cosine, 3)}</td><td>{c.evidence}</td></tr>)}</tbody></table>
    {r.bestMeasured?.length > 0 && <small>Best fully measured options: {r.bestMeasured.map((c: any) => `${c.ops.map((o: any) => o.label).join(' + ')} (${fmt(c.score, 3)})`).join(' · ')}</small>}
    <p className="vc-warn">{r.caution}</p><Terms terms={r.terms}/>
  </div>;
  return null;
}

function Table({rows}: {rows: any[]}) {
  return <table className="vc-table"><thead><tr><th>Gene</th><th>Baseline</th><th>Now</th><th>Change</th><th>z (control SD)</th></tr></thead>
    <tbody>{rows.map(x => <tr key={x.gene}><td>{x.gene}</td><td>{fmt(x.baseline, 3)}</td><td>{fmt(x.value, 3)}</td><td className={x.delta < 0 ? 'down' : 'up'}>{x.delta > 0 ? '+' : ''}{fmt(x.delta, 3)}</td><td>{x.z == null ? '—' : fmt(x.z, 2)}</td></tr>)}</tbody></table>;
}
