import {useEffect, useMemo, useRef, useState} from 'react';
import {Check, CircleHelp, Combine, Database, Dna, Fingerprint, FlaskRound, Grid3x3, Map as MapIcon, Share2, Download, FlaskConical, FolderOpen, LoaderCircle, Microscope, Pill, ScrollText, Search, TriangleAlert} from 'lucide-react';
import {rpc, chooseDirectory} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';
import TumorLab from './TumorLab';
import Genomics from './Genomics';
import SingleCell from './SingleCell';
import Spatial from './Spatial';
import Metabolism from './Metabolism';
import EvidenceGraph from './EvidenceGraph';
import {Signatures, Synergy} from './SynergySignatures';
import InSilico from './InSilico';
import PerturbationLab from './PerturbationLab';
import Discovery from './Discovery';
import SyntheticLethality from './SyntheticLethality';
import Clonal from './Clonal';
import CellComm from './CellComm';
import ModelComparison from './ModelComparison';
import Assistant from './Assistant';
import Pathology from './Pathology';
import PerturbModel from './PerturbModel';

type Tab = 'pm' | 'pathology' | 'assistant' | 'discovery' | 'sl' | 'clonal' | 'cellcomm' | 'compare' | 'lab' | 'evidence' | 'tme' | 'atlas' | 'genomics' | 'singlecell' | 'spatial' | 'metabolism' | 'signatures' | 'drugs' | 'synergy' | 'data' | 'records';
const TABS: [Tab, string, any][] = [['assistant', 'Research assistant', CircleHelp], ['discovery', 'Discovery workflow', Search], ['lab', 'Perturbation lab', FlaskRound], ['compare', 'Model comparison', Grid3x3], ['tme', 'Tumor microenvironment', Microscope], ['atlas', 'Dependency atlas', FlaskConical], ['sl', 'Synthetic lethality', Combine], ['genomics', 'Patient genomics', Dna], ['signatures', 'Signatures', Fingerprint], ['clonal', 'Clonal evolution', Share2], ['singlecell', 'Single-cell', Grid3x3], ['cellcomm', 'Cell communication', Share2], ['pm', 'Perturbation model', Grid3x3], ['spatial', 'Spatial', MapIcon], ['pathology', 'Pathology', Microscope], ['metabolism', 'Metabolism', FlaskRound], ['evidence', 'Evidence graph', Share2], ['drugs', 'Drug response', Pill], ['synergy', 'Synergy', Combine], ['data', 'Data', Database], ['records', 'Records', ScrollText]];
const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');
const sci = (v: number) => v == null || !Number.isFinite(v) ? '—' : v < 1e-3 ? v.toExponential(1) : fmt(v, 2);

function Evidence({text}: {text: string}) { return <span className="onc-evidence">{text}</span>; }

/** Volcano plot of every tested gene: effect (x) against −log10 q (y); the strongest hits are labelled. */
export function Volcano({points, xLabel, highlight}: {points: [string, number, number][]; xLabel: string; highlight?: string[]}) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const dpr = window.devicePixelRatio || 1, W = cv.clientWidth, H = cv.clientHeight; cv.width = W * dpr; cv.height = H * dpr;
    const g = cv.getContext('2d')!; g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    let xmin = 0, xmax = 0, ymax = 1; for (const p of points) { xmin = Math.min(xmin, p[1]); xmax = Math.max(xmax, p[1]); ymax = Math.max(ymax, p[2]); }
    const pad = 36, X = (v: number) => pad + (v - xmin) / (xmax - xmin || 1) * (W - pad - 12), Y = (v: number) => H - pad - v / ymax * (H - pad - 14);
    g.strokeStyle = 'rgba(160,190,255,.25)'; g.beginPath(); g.moveTo(pad, H - pad); g.lineTo(W - 12, H - pad); g.moveTo(X(0), 10); g.lineTo(X(0), H - pad); g.stroke();
    g.setLineDash([4, 4]); g.beginPath(); g.moveTo(pad, Y(-Math.log10(0.05))); g.lineTo(W - 12, Y(-Math.log10(0.05))); g.stroke(); g.setLineDash([]);
    for (const p of points) { const sig = p[2] > 1.301; g.fillStyle = sig ? (p[1] < 0 ? 'rgba(255,138,107,.75)' : 'rgba(95,212,255,.6)') : 'rgba(200,210,230,.18)'; g.fillRect(X(p[1]) - 1.2, Y(p[2]) - 1.2, 2.4, 2.4); }
    const label = [...points].sort((a, b) => b[2] - a[2]).slice(0, 8).map(p => p[0]).concat(highlight ?? []);
    g.font = '11px Inter, system-ui'; g.fillStyle = '#e8ecf6';
    for (const p of points) if (label.includes(p[0])) { g.beginPath(); g.arc(X(p[1]), Y(p[2]), 3, 0, Math.PI * 2); g.fill(); g.fillText(p[0], X(p[1]) + 5, Y(p[2]) - 4); }
    g.fillStyle = 'rgba(220,228,245,.6)'; g.fillText(xLabel, W / 2 - 60, H - 8); g.save(); g.translate(12, H / 2 + 30); g.rotate(-Math.PI / 2); g.fillText('−log10 q (BH)', 0, 0); g.restore();
  }, [points, xLabel, highlight]);
  return <canvas ref={ref} className="onc-volcano" aria-label="Volcano plot of all tested genes"/>;
}

/** Per-lineage distribution of a gene's effect: box (quartiles), whiskers (range), median tick; sorted most dependent first. */
function LineageBoxes({profile}: {profile: any}) {
  const rows = profile.lineages.filter((l: any) => l.n >= 3), lo = Math.min(-2.5, ...rows.map((r: any) => r.min)), hi = Math.max(0.8, ...rows.map((r: any) => r.max));
  const W = 640, row = 20, H = rows.length * row + 30, X = (v: number) => 170 + (v - lo) / (hi - lo) * (W - 190);
  return <svg viewBox={`0 0 ${W} ${H}`} className="onc-boxes" role="img" aria-label={`${profile.gene} effect by lineage`}>
    {[-2, -1, -0.5, 0].filter(v => v >= lo).map(v => <g key={v}><line x1={X(v)} x2={X(v)} y1={4} y2={H - 22} className={v === -0.5 ? 'thr' : 'grid'}/><text x={X(v)} y={H - 6} textAnchor="middle">{v}</text></g>)}
    {rows.map((r: any, i: number) => { const y = 12 + i * row; return <g key={r.lineage}>
      <text x={162} y={y + 4} textAnchor="end">{r.lineage} · {r.n}</text>
      <line x1={X(r.min)} x2={X(r.max)} y1={y} y2={y} className="whisk"/><rect x={X(r.q1)} y={y - 6} width={Math.max(1, X(r.q3) - X(r.q1))} height={12} rx={3} className="box" style={{opacity: 0.35 + 0.65 * r.fracDependent}}/>
      <line x1={X(r.median)} x2={X(r.median)} y1={y - 7} y2={y + 7} className="med"/></g>; })}
  </svg>;
}

function Scatter({points, xLabel, yLabel}: {points: number[][]; xLabel: string; yLabel: string}) {
  const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)], W = 360, H = 260, X = (v: number) => 40 + (v - x0) / (x1 - x0 || 1) * (W - 52), Y = (v: number) => H - 30 - (v - y0) / (y1 - y0 || 1) * (H - 44);
  return <svg viewBox={`0 0 ${W} ${H}`} className="onc-scatter" role="img" aria-label={`${yLabel} against ${xLabel}`}>
    <line x1={40} x2={W - 12} y1={H - 30} y2={H - 30} className="grid"/><line x1={40} x2={40} y1={10} y2={H - 30} className="grid"/>
    {points.map((p, i) => <circle key={i} cx={X(p[0])} cy={Y(p[1])} r={2.2}/>)}
    <text x={W / 2} y={H - 8} textAnchor="middle">{xLabel}</text><text x={12} y={H / 2} transform={`rotate(-90 12 ${H / 2})`} textAnchor="middle">{yLabel}</text>
  </svg>;
}

function HitTable({hits, effect, label}: {hits: any[]; effect: string; label: string}) {
  return <table className="tme-table onc-hits"><thead><tr><th>Gene</th><th>{label}</th><th>95 % CI</th><th>q (BH)</th></tr></thead>
    <tbody>{hits.slice(0, 25).map(h => <tr key={h.gene}><td>{h.gene}</td><td>{fmt(h[effect], 3)}</td><td>{fmt(h.ci[0], 2)} to {fmt(h.ci[1], 2)}</td><td>{sci(h.q)}</td></tr>)}</tbody></table>;
}

function Atlas({projectId}: {projectId: string}) {
  const [meta, setMeta] = useState<any>(null), [gene, setGene] = useState('KRAS'), [profile, setProfile] = useState<any>(null), [scan, setScan] = useState<any>(null), [mscan, setMscan] = useState<any>(null);
  const [lineage, setLineage] = useState('Skin'), [mutGene, setMutGene] = useState('BRAF'), [kind, setKind] = useState('hotspot'), [controls, setControls] = useState<any>(null), [busy, setBusy] = useState(''), [error, setError] = useState('');
  async function go<T>(label: string, action: string, p: any, set: (v: T) => void) { setBusy(label); setError(''); try { set(await rpc<T>(action, {projectId, ...p})); } catch (e) { setError(err(e)); } finally { setBusy(''); } }
  useEffect(() => { void go('Opening DepMap', 'onc_lineages', {}, setMeta); }, []);
  useEffect(() => { if (meta) void go('Profiling ' + gene, 'onc_gene', {gene}, setProfile); }, [meta]);
  if (!meta) return <section className="quiet-panel">{busy ? <p className="caption"><LoaderCircle size={12} className="spin"/> {busy}…</p> : <p className="caption">{error || 'Install DepMap in the Data tab first.'}</p>}</section>;
  return <>
    <div className="page-heading"><div><span className="eyebrow">DEMO A · PAN-CANCER DEPENDENCY ATLAS · DEPMAP {meta.release}</span><h1>What each cancer <em>cannot live without.</em></h1>
      <p>CRISPR knockout effects across {meta.lineages.reduce((a: number, l: any) => a + l[1], 0)} cancer models. Sister lines from one patient count once; lineage is controlled where it confounds.</p></div></div>
    {error && <p className="caption cs-error">{error}</p>}{busy && <p className="caption"><LoaderCircle size={12} className="spin"/> {busy}…</p>}
    <section className="quiet-panel">
      <div className="onc-row"><Search size={15}/><input list="onc-genes" value={gene} onChange={e => setGene(e.target.value.toUpperCase())} onKeyDown={e => e.key === 'Enter' && go('Profiling ' + gene, 'onc_gene', {gene}, setProfile)} aria-label="Gene"/>
        <datalist id="onc-genes">{meta.genes.slice(0, 20000).map((g: string) => <option key={g} value={g}/>)}</datalist>
        <button className="button" onClick={() => go('Profiling ' + gene, 'onc_gene', {gene}, setProfile)}>Profile gene</button><Evidence text="Statistical association · Chronos gene effect"/></div>
      {profile && <div className="onc-two">
        <div><h3>{profile.gene} <small>· mean {fmt(profile.mean, 2)} · dependent (&lt; −0.5) in {fmt(profile.fracDependent * 100, 2)} % of {profile.n} models{profile.collapsedSamePatient ? ` · ${profile.collapsedSamePatient} same-patient lines collapsed` : ''}</small></h3>
          <LineageBoxes profile={profile}/><p className="caption">{profile.note} Box opacity = fraction of dependent models.</p></div>
        <div>{profile.expressionLink?.points ? <><h3>Dependency vs own expression</h3><Scatter points={profile.expressionLink.points} xLabel="expression log2(TPM+1)" yLabel="gene effect"/>
          <p className="caption">Lineage-adjusted partial r = {fmt(profile.expressionLink.partialR, 2)} (95 % CI {fmt(profile.expressionLink.ci[0], 2)} to {fmt(profile.expressionLink.ci[1], 2)}), p = {sci(profile.expressionLink.p)}, n = {profile.expressionLink.n}. Association, not causation.</p></> : <p className="caption">{profile.expressionLink?.error}</p>}</div>
      </div>}
    </section>
    <section className="onc-two">
      <div className="quiet-panel"><span className="eyebrow">Lineage-selective dependencies</span>
        <div className="onc-row"><select value={lineage} onChange={e => setLineage(e.target.value)} aria-label="Lineage">{meta.lineages.map(([l, n]: any) => <option key={l} value={l}>{l} ({n})</option>)}</select>
          <button className="button" onClick={() => go('Scanning ' + lineage, 'onc_lineage_scan', {lineage}, setScan)}>Scan all genes</button></div>
        {scan && <><Volcano points={scan.volcano} xLabel={`effect difference: ${scan.lineage} − other lineages`}/>
          <p className="caption">{scan.method}. {scan.nIn} vs {scan.nOut} independent models; {scan.significant} genes at q &lt; 0.05 of {scan.tested}.</p>
          <HitTable hits={scan.hits} effect="diff" label="Δ effect"/></>}</div>
      <div className="quiet-panel"><span className="eyebrow">Mutation-associated dependencies</span>
        <div className="onc-row"><input value={mutGene} onChange={e => setMutGene(e.target.value.toUpperCase())} aria-label="Mutated gene"/><select value={kind} onChange={e => setKind(e.target.value)} aria-label="Mutation class"><option value="hotspot">hotspot</option><option value="damaging">damaging</option></select>
          <button className="button" onClick={() => go('Scanning ' + mutGene, 'onc_mutation_scan', {gene: mutGene, kind}, setMscan)}>Scan all genes</button></div>
        {mscan && <><Volcano points={mscan.volcano} xLabel={`β: effect shift in ${mscan.kind} ${mscan.mutation} models (lineage-adjusted)`} highlight={[mscan.mutation]}/>
          <p className="caption">{mscan.method}. {mscan.mutant} mutant of {mscan.n} models, {mscan.lineages} lineages; {mscan.significant} genes at q &lt; 0.05.</p>
          <HitTable hits={mscan.hits} effect="beta" label="β"/></>}</div>
    </section>
    <section className="quiet-panel"><span className="eyebrow">Validation against established biology</span>
      <div className="onc-row"><button className="button" onClick={() => go('Running controls', 'onc_controls', {}, (r: any) => setControls(r.controls))}>Run positive and negative controls</button>
        <span className="caption">Known oncogene addictions, lineage dependencies, a common-essential and a null gene. If these fail, the data or the method is wrong.</span></div>
      {controls && <ul className="tme-checks">{controls.map((c: any) => <li key={c.control}>{c.passed === true ? <Check size={14} className="ok"/> : c.passed === false ? <TriangleAlert size={14} className="bad"/> : <CircleHelp size={14}/>}<div><strong>{c.control}</strong><span>{c.detail}</span></div></li>)}</ul>}
    </section>
  </>;
}

function Drugs({projectId}: {projectId: string}) {
  const [drugs, setDrugs] = useState<any[]>([]), [drug, setDrug] = useState(''), [res, setRes] = useState<any>(null), [comp, setComp] = useState<any>(null), [lin, setLin] = useState<any>(null), [lineage, setLineage] = useState('Skin'), [busy, setBusy] = useState(''), [error, setError] = useState('');
  async function go(label: string, action: string, p: any, set: (v: any) => void) { setBusy(label); setError(''); try { set(await rpc(action, {projectId, ...p})); } catch (e) { setError(err(e)); } finally { setBusy(''); } }
  useEffect(() => { rpc<any[]>('onc_drugs', {projectId}).then(d => { setDrugs(d); setDrug(d.find(x => x.name === 'Dabrafenib' && x.dataset === 'GDSC2')?.key ?? d[0]?.key ?? ''); }).catch(e => setError(err(e))); }, []);
  const sel = drugs.find(d => d.key === drug);
  const Metrics = ({r}: {r: any}) => <table className="tme-table"><thead><tr><th>Model</th><th>RMSE</th><th>MAE</th><th>Pearson r</th><th>Spearman ρ</th><th>90 % PI coverage</th></tr></thead>
    <tbody>{Object.entries(r).map(([k, v]: any) => <tr key={k}><td>{k}</td><td>{fmt(v.rmse, 3)}</td><td>{fmt(v.mae, 3)}</td><td>{v.pearson != null ? fmt(v.pearson, 2) : '—'}</td><td>{v.spearman != null ? fmt(v.spearman, 2) : '—'}</td><td>{v.coverage90 != null ? fmt(v.coverage90 * 100, 2) + ' %' : '—'}</td></tr>)}</tbody></table>;
  return <>
    <div className="page-heading"><div><span className="eyebrow">DEMO C · DRUG-RESPONSE PREDICTION · GDSC 8.5 × DEPMAP</span><h1>Predicting response, <em>honestly scored.</em></h1>
      <p>Measured GDSC dose–response curves; models must beat simple baselines on cell lines, compounds and lineages they have never seen. Cell-line IC50 only: no claim about patients.</p></div></div>
    {error && <p className="caption cs-error">{error}</p>}{busy && <p className="caption"><LoaderCircle size={12} className="spin"/> {busy}…</p>}
    <section className="quiet-panel">
      <div className="onc-row"><select value={drug} onChange={e => setDrug(e.target.value)} aria-label="Drug" className="onc-drug">{drugs.map(d => <option key={d.key} value={d.key}>{d.name} · {d.dataset} · {d.target || 'target n/a'} ({d.curves})</option>)}</select>
        <button className="button primary" onClick={() => go('Cross-validating ' + sel?.name, 'onc_drug_cells', {drug}, setRes)}>Held-out cell lines</button><Evidence text="AI prediction vs experimental observation"/></div>
      {sel && <p className="caption">{sel.name} · putative target {sel.target || 'n/a'} · pathway {sel.pathway}</p>}
      {res && <div className="onc-two"><div><Metrics r={res.results}/>
          <p className="caption">{res.cellLines} cell lines ({res.curves} curves) · {res.folds}-fold CV grouped by patient · {res.features}. mean = training mean; lineage = training mean of the same lineage; ridge / enet = regularised regression with inner-CV penalty.{typeof res.trees === 'object' ? ` forest = ${res.trees.forest}; boosting = ${res.trees.boosting} (${res.trees.note}).` : res.trees ? ` Tree baselines ${res.trees}.` : ''}</p>
          <ul className="tme-checks">{Object.entries(res.leakage).map(([k, v]: any) => <li key={k}><Check size={14} className="ok"/><div><strong>{({patientsSharedAcrossFolds: 'Patients shared across folds', featureSelection: 'Feature selection', standardisation: 'Standardisation', penaltyChoice: 'Penalty choice'} as any)[k] ?? k}</strong><span>{String(v)}</span></div></li>)}</ul></div>
        <div><h3>Observed vs predicted (ridge)</h3><Scatter points={res.points.map((p: any) => [p[4], p[3]])} xLabel="predicted LN_IC50" yLabel="measured LN_IC50"/><p className="caption">{res.caveat}</p></div></div>}
    </section>
    <section className="onc-two">
      <div className="quiet-panel"><span className="eyebrow">Held-out lineage (domain shift)</span>
        <div className="onc-row"><input value={lineage} onChange={e => setLineage(e.target.value)} aria-label="Lineage to hold out"/><button className="button" onClick={() => go('Holding out ' + lineage, 'onc_drug_lineage', {drug, lineage}, setLin)}>Train without it, test on it</button></div>
        {lin && <><Metrics r={lin.results}/><p className="caption">Train {lin.train} · test {lin.test} · mean LN_IC50 {fmt(lin.domainShift.trainMean, 3)} (train) vs {fmt(lin.domainShift.testMean, 3)} (test).</p></>}</div>
      <div className="quiet-panel"><span className="eyebrow">Held-out compounds (all GDSC2)</span>
        <div className="onc-row"><button className="button" onClick={() => go('Holding out compounds', 'onc_drug_compounds', {}, setComp)}>Predict unseen compounds</button></div>
        {comp && <><Metrics r={comp.results}/><p className="caption">{comp.compounds} compounds ({comp.drugScreens} screens), {comp.cellLines} lines, {comp.folds}-fold CV over compounds. {comp.method}. Mean within-drug Spearman ρ (ranking cell lines for a new drug): {fmt(comp.results['pathway+cell'].meanWithinDrugSpearman, 2)}. Compounds shared across folds: {comp.leakage.compoundsSharedAcrossFolds}.</p></>}</div>
    </section>
  </>;
}

function Data({projectId}: {projectId: string}) {
  const [st, setSt] = useState<any>(null), [release, setRelease] = useState('26Q3'), [error, setError] = useState('');
  async function read() { try { setSt(await rpc('onc_data_status', {projectId})); } catch (e) { setError(err(e)); } }
  useEffect(() => { void read(); }, []);
  const running = st && Object.values(st.installs).some((i: any) => i.running);
  useEffect(() => { if (!running) return; const t = setTimeout(read, 3000); return () => clearTimeout(t); }, [st]);
  async function install(source: string) { setError(''); try { setSt(await rpc('onc_data_install', {projectId, source})); } catch (e) { setError(err(e)); } }
  async function importFolder() { const folder = await chooseDirectory(); if (!folder) return; try { setSt(await rpc('onc_data_import', {projectId, folder, release})); } catch (e) { setError(err(e)); } }
  return <>
    <div className="page-heading"><div><span className="eyebrow">DATA FOUNDATION · VERSIONED, CHECKSUMMED, ORIGINAL VALUES KEPT</span><h1>The evidence <em>underneath.</em></h1>
      <p>Public cancer datasets cached in your research library, each release with its licence, citation and verified checksums.</p></div></div>
    {error && <p className="caption cs-error">{error}</p>}
    {st && <section className="onc-two">{(['depmap', 'gdsc'] as const).map(src => <div className="quiet-panel" key={src}>
      <span className="eyebrow">{src === 'depmap' ? 'DepMap (Broad) · CRISPR, omics, models' : 'GDSC (Sanger) · measured drug responses'}</span>
      {st.releases[src].map((m: any) => <div key={m.release} className="onc-release"><h3>{m.release} <small>installed {m.installed?.slice(0, 10)} · {m.licence}</small></h3>
        <ul>{Object.entries(m.original).map(([f, v]: any) => <li key={f}>{v.verified ? <Check size={12} className="ok"/> : <CircleHelp size={12}/>} {f} · {(v.bytes / 1e6).toFixed(1)} MB · MD5 {v.md5.slice(0, 10)}…{v.verified ? ' verified' : ' recorded'}</li>)}</ul>
        <p className="caption">{m.citation}</p></div>)}
      {!st.releases[src].length && <p className="caption">Not installed.</p>}
      <div className="onc-row"><button className="button" disabled={st.installs[src]?.running} onClick={() => install(src)}><Download size={14}/>{src === 'depmap' ? 'Install DepMap 24Q4 (≈1.1 GB)' : 'Install GDSC 8.5 (≈95 MB)'}</button></div>
      {src === 'depmap' && <div className="onc-row"><input value={release} onChange={e => setRelease(e.target.value)} aria-label="Release name" style={{width: 80}}/><button className="button" onClick={importFolder}><FolderOpen size={14}/>Import a release downloaded in the browser</button></div>}
      {src === 'depmap' && <p className="caption">{st.available.note}</p>}
      {st.installs[src] && <pre className="gt-log gt-console onc-log">{st.installs[src].log}</pre>}
    </div>)}</section>}
    {st && <section className="quiet-panel"><span className="eyebrow">Sanger Project Score · independent CRISPR screen (replication)</span>
      {st.sanger ? <p className="caption"><Check size={12} className="ok"/> {st.sanger.lines} lines, {st.sanger.matchedToDepMap} matched to DepMap {st.sanger.depmapRelease} · installed {st.sanger.installed?.slice(0, 10)} · SHA-256 {st.sanger.sha256?.slice(0, 12)}… · {st.sanger.citation}</p> : <p className="caption">Not installed. Used by Demo L to test whether each dependency replicates in a second laboratory's screen.</p>}
      <div className="onc-row"><button className="button" disabled={st.installs.sanger?.running} onClick={() => install('sanger')}><Download size={14}/>{st.sanger ? 'Reinstall' : 'Install'} Project Score (≈240 MB)</button></div>
      {st.installs.sanger && (st.installs.sanger.running || !st.sanger) && <pre className="gt-log gt-console onc-log">{st.installs.sanger.log}</pre>}</section>}
    <section className="quiet-panel"><span className="eyebrow">Other sources</span><p className="caption">Connected elsewhere: cBioPortal and NCI GDC cohorts (Patient genomics), CELLxGENE (Single-cell, Spatial), ChEMBL and BindingDB potencies (Perturbation lab, fetched per compound), UniProt, Reactome, STRING, Open Targets, CIViC and Europe PMC (Evidence graph), BioModels (mechanistic models). Not connected: PRISM (its downloads require a browser verification, which this app does not bypass), HTAN, OmniPath.</p></section>
  </>;
}

function Records({projectId}: {projectId: string}) {
  const [rows, setRows] = useState<any[]>([]), [open, setOpen] = useState<any>(null);
  useEffect(() => { rpc<any[]>('onc_records', {projectId}).then(setRows).catch(() => {}); }, []);
  return <>
    <div className="page-heading"><div><span className="eyebrow">EXPERIMENT RECORDS</span><h1>Every result, <em>reproducible.</em></h1><p>Question, parameters, dataset releases, software versions and full numerical output of every analysis.</p></div></div>
    <section className="quiet-panel"><table className="tme-table"><thead><tr><th>When</th><th>Question</th><th>Method</th><th>Data</th></tr></thead>
      <tbody>{rows.map(r => <tr key={r.id} onClick={() => rpc('onc_record', {projectId, id: r.id}).then(setOpen)} style={{cursor: 'pointer'}}><td>{r.created.replace('T', ' ').slice(0, 16)}</td><td>{r.question}</td><td>{r.kind}</td><td>{Object.entries(r.datasets).map(([k, v]: any) => k + ' ' + v.join('')).join(' · ')}</td></tr>)}</tbody></table>
      {!rows.length && <p className="caption">No analyses yet.</p>}
      {open && <pre className="gt-log gt-console onc-log">{JSON.stringify({...open, result: Object.fromEntries(Object.entries(open.result).filter(([k]) => !['volcano', 'points'].includes(k)))}, null, 1).slice(0, 20000)}</pre>}</section>
  </>;
}

/** Analyse › Oncology Universe: one workspace, separate labs that share the data foundation and the record store. */
const SIMULATED = new Set<string>(['atlas', 'drugs', 'synergy', 'signatures', 'genomics', 'singlecell', 'metabolism']);

/** Directive §75 visualization modes: each groups the views that answer that kind of question; "All" shows every tab. */
const VIEW_MODES: [string, string, Tab[] | null, string?][] = [
  ['all', 'All', null],
  ['atlas', 'Atlas', ['atlas', 'genomics', 'signatures', 'drugs', 'synergy', 'sl', 'data', 'records'], 'Experimental cancer and tissue datasets.'],
  ['cellular', 'Cellular', ['singlecell', 'cellcomm', 'pm', 'clonal', 'metabolism'], 'Individual cells and cell populations.'],
  ['physics', 'Tumor physics', ['tme', 'lab'], 'Model-derived fields and multicellular behaviour.'],
  ['spatial', 'Spatial omics', ['spatial'], 'Measured spatial gene expression.'],
  ['immune', 'Immune', ['tme', 'lab', 'cellcomm'], 'Immune-cell models (PhysiCell tumor–immune, Kuznetsov, PD-1 signalling) and inferred immune communication.'],
  ['uncertainty', 'Uncertainty', ['discovery', 'compare', 'assistant', 'records'], 'Where evidence is weak, contradictory or missing: scorecards, model disagreement, gaps.'],
  ['comparison', 'Comparison', ['compare', 'lab', 'pm'], 'Two models or conditions side by side.'],
  ['pathology', 'Pathology', ['pathology'], 'Actual microscopy and histology (Demo I, NuInsSeg H&E images with expert annotations).'],
  ['molecular', 'Molecular', [], 'Protein structures and interactions live in the main Fold Studio workspace (structure viewer and Evidence graph tab).'],
  ['cinematic', 'Cinematic', [], 'Scientific storytelling lives in the Cinema section of the main app; the TME tab plays PhysiCell runs over time.'],
];

export default function OncologyUniverse({projectId}: {projectId: string}) {
  const [view, setView] = useState<string>(() => { try { return localStorage.getItem('onc-view') || 'all'; } catch { return 'all'; } });
  useEffect(() => { try { localStorage.setItem('onc-view', view); } catch {} }, [view]);
  const vm = VIEW_MODES.find(v => v[0] === view) ?? VIEW_MODES[0], shown = vm[2] ? TABS.filter(([id]) => vm[2]!.includes(id)) : TABS;
  const [tab, setTab] = useState<Tab>(() => { try { return (localStorage.getItem('onc-tab') as Tab) || 'tme'; } catch { return 'tme'; } });
  useEffect(() => { try { localStorage.setItem('onc-tab', tab); } catch {} }, [tab]);
  const body = useMemo(() => ({pm: <PerturbModel projectId={projectId}/>, pathology: <Pathology projectId={projectId}/>, assistant: <Assistant projectId={projectId}/>, discovery: <Discovery projectId={projectId}/>, sl: <SyntheticLethality projectId={projectId}/>, clonal: <Clonal projectId={projectId}/>, cellcomm: <CellComm projectId={projectId}/>, compare: <ModelComparison projectId={projectId}/>, lab: <PerturbationLab projectId={projectId}/>, tme: <TumorLab projectId={projectId}/>, atlas: <Atlas projectId={projectId}/>, genomics: <Genomics projectId={projectId}/>, signatures: <Signatures projectId={projectId}/>, singlecell: <SingleCell projectId={projectId}/>, spatial: <Spatial projectId={projectId}/>, metabolism: <Metabolism projectId={projectId}/>, evidence: <EvidenceGraph projectId={projectId}/>, synergy: <Synergy projectId={projectId}/>, drugs: <Drugs projectId={projectId}/>, data: <Data projectId={projectId}/>, records: <Records projectId={projectId}/>})[tab], [tab, projectId]);
  const [mode, setMode] = useState<Record<string, string>>(() => { try { return JSON.parse(localStorage.getItem('onc-mode') || '{}'); } catch { return {}; } });
  useEffect(() => { try { localStorage.setItem('onc-mode', JSON.stringify(mode)); } catch {} }, [mode]);
  const sim = SIMULATED.has(tab) && mode[tab] === 'sim';
  return <div className="onc-universe">
    <nav className="onc-modes" aria-label="Visualization mode">{VIEW_MODES.map(([id, label, , hint]) => <button key={id} title={hint} className={'gt-view ' + (view === id ? 'selected' : '')} onClick={() => { setView(id); const v = VIEW_MODES.find(x => x[0] === id)!; if (v[2]?.length && !v[2].includes(tab)) setTab(v[2][0]); }}>{label}</button>)}</nav>
    {vm[3] && <p className="caption onc-mode-hint">{vm[3]}</p>}
    <nav className="onc-tabs" aria-label="Oncology Universe">{shown.map(([id, label, Icon]) => <button key={id} className={'onc-tab ' + (tab === id ? 'selected' : '')} onClick={() => setTab(id)}><Icon size={14}/>{label}</button>)}</nav>
    {tab === 'tme' ? body : <div className="page-content onc-page">
      {SIMULATED.has(tab) && <div className="tme-tabs onc-mode" role="tablist" aria-label="Data source">{([['real', tab === 'metabolism' ? 'Reference analysis' : 'Real data'], ['sim', tab === 'metabolism' ? 'What-if simulation' : 'In silico (planted truth)']] as const).map(([k, l]) =>
        <button key={k} role="tab" aria-selected={(mode[tab] === 'sim') === (k === 'sim')} className={'gt-view ' + ((mode[tab] === 'sim') === (k === 'sim') ? 'selected' : '')} onClick={() => setMode({...mode, [tab]: k})}>{l}</button>)}</div>}
      {sim ? <InSilico projectId={projectId} demo={tab}/> : body}</div>}
  </div>;
}
