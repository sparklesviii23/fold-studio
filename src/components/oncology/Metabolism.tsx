import {useEffect, useState} from 'react';
import {Check, Download, LoaderCircle, Play, TriangleAlert} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');
const Ok = ({ok}: {ok: boolean}) => ok ? <Check size={14} className="ok"/> : <TriangleAlert size={14} className="bad"/>;

/** ATP per glucose and by-product secretion as the oxygen supply per glucose rises (computed optima, not measurements). */
function OxygenSweep({pts}: {pts: any[]}) {
  const W = 520, H = 230, xmax = Math.max(...pts.map(p => p.o2PerGlucose)), ymax = 34, X = (v: number) => 44 + v / xmax * (W - 64), Y = (v: number) => H - 30 - v / ymax * (H - 46);
  const line = (k: string, scale = 1) => pts.map((p, i) => `${i ? 'L' : 'M'}${X(p.o2PerGlucose)},${Y(p[k] * scale)}`).join('');
  return <svg viewBox={`0 0 ${W} ${H}`} className="onc-km" role="img" aria-label="ATP yield against oxygen per glucose">
    {[0, 8, 16, 24, 32].map(v => <g key={v}><line x1={44} x2={W - 20} y1={Y(v)} y2={Y(v)} className="grid"/><text x={38} y={Y(v) + 3} textAnchor="end">{v}</text></g>)}
    <path d={line('atp')} className="km-a"/><path d={line('succinate', 10)} className="km-u" strokeDasharray="4 3"/><path d={line('lactate', 10)} stroke="#ffd166" fill="none" strokeWidth={2}/>
    <text x={W / 2} y={H - 6} textAnchor="middle">O₂ available per glucose (mol/mol)</text>
    <g transform={`translate(${W - 230},14)`}><line x1={0} x2={16} y1={0} y2={0} className="km-a"/><text x={22} y={4}>ATP per glucose</text>
      <line x1={0} x2={16} y1={15} y2={15} className="km-u" strokeDasharray="4 3"/><text x={22} y={19}>succinate secreted (×10)</text>
      <line x1={0} x2={16} y1={30} y2={30} stroke="#ffd166" strokeWidth={2}/><text x={22} y={34}>lactate secreted (×10)</text></g>
  </svg>;
}

export default function Metabolism({projectId}: {projectId: string}) {
  const [st, setSt] = useState<any>(null), [r, setR] = useState<any>(null), [busy, setBusy] = useState(''), [error, setError] = useState('');
  async function read() { try { const s = await rpc<any>('onc_met_status', {projectId}); setSt(s); return s; } catch (e) { setError(err(e)); } }
  async function load() { setBusy('Loading model results'); try { setR(await rpc('onc_met_result', {projectId})); } catch (e) { setError(err(e)); } finally { setBusy(''); } }
  useEffect(() => { void read().then(s => { if (s?.result) void load(); }); }, []);
  useEffect(() => { if (!st?.job?.running && !st?.download?.running) return; const t = setTimeout(async () => { const s = await read(); if (s?.result && !s.job?.running) void load(); }, 4000); return () => clearTimeout(t); }, [st]);
  const act = async (a: string) => { try { setSt(await rpc(a, {projectId})); } catch (e) { setError(err(e)); } };
  const dm = r?.essentiality?.depmap;
  return <>
    <div className="page-heading"><div><span className="eyebrow">DEMO F · TUMOR METABOLIC MODEL · HUMAN-GEM × COBRApy</span><h1>What the stoichiometry <em>allows.</em></h1>
      <p>A genome-scale human metabolic reconstruction solved with flux balance analysis. Fluxes are feasible steady states under stated bounds, not measured rates; checked against textbook biochemistry and an independent CRISPR screen.</p></div></div>
    {error && <p className="caption cs-error">{error}</p>}{busy && <p className="caption"><LoaderCircle size={12} className="spin"/> {busy}…</p>}
    {st && <section className="quiet-panel"><p className="caption">{st.manifest ? `${st.manifest.model} ${st.manifest.release} · ${st.manifest.licence} · ${st.manifest.citation} Files verified by git hash.` : 'Human-GEM is not installed.'}</p>
      <div className="onc-row">{!st.installed && <button className="button primary" disabled={!st.runtimeReady || st.download?.running} onClick={() => act('onc_met_install')}><Download size={14}/>Install Human-GEM v2.1.1 (≈ 55 MB)</button>}
        {st.installed && <button className="button" disabled={st.job?.running} onClick={() => act('onc_met_run')}><Play size={14}/>{st.result ? 'Re-run (≈ 2.5 min, includes 2,870 gene knockouts)' : 'Run analysis (≈ 2.5 min)'}</button>}
        <span className="onc-evidence">Mechanistic simulation · constraint-based</span></div>
      {(st.job?.running || st.download?.running) && <pre className="gt-log gt-console onc-log">{(st.job ?? st.download).log}</pre>}</section>}
    {r && <>
      <section className="quiet-panel"><span className="eyebrow">Checks · solver and model</span>
        <ul className="tme-checks">
          <li><Ok ok={r.benchmark.passed}/><div><strong>Solver benchmark: {r.benchmark.model} optimum {fmt(r.benchmark.growth, 5)} h⁻¹</strong><span>published {r.benchmark.published}</span></div></li>
          <li><Ok ok={r.noNutrientATP.passed}/><div><strong>No nutrients → no ATP ({fmt(r.noNutrientATP.atp, 2)})</strong><span>no energy-generating cycles under these bounds</span></div></li>
          <li><Ok ok={r.atpYield.passed}/><div><strong>ATP per glucose: aerobic {fmt(r.atpYield.aerobic.atp, 3)} · glycolysis only {fmt(r.atpYield.anaerobicNoSuccinate.atp, 3)}</strong><span>{r.atpYield.expected}. {r.atpYield.note}</span></div></li>
        </ul>
        <p className="caption">{r.model.name}: {r.model.reactions.toLocaleString()} reactions · {r.model.metabolites.toLocaleString()} metabolites · {r.model.genes.toLocaleString()} genes · COBRApy {r.software.cobra}. Medium: {r.medium.name}; {r.medium.bounds}{r.medium.missing.length ? `; not in the model: ${r.medium.missing.join(', ')}` : ''}.</p></section>
      <section className="onc-two">
        <div className="quiet-panel"><span className="eyebrow">Oxygen and energy · the stoichiometric side of Warburg</span><OxygenSweep pts={r.oxygenSweep.points}/><p className="caption">{r.oxygenSweep.note}</p></div>
        <div className="quiet-panel"><span className="eyebrow">Growth vs glucose and oxygen supply</span>
          <table className="tme-table"><thead><tr><th>glucose ↓ · O₂ →</th>{r.sensitivity.oxygen.map((o: any) => <th key={o}>{o}</th>)}</tr></thead>
            <tbody>{r.sensitivity.growth.map((row: number[], i: number) => <tr key={i}><td>{r.sensitivity.glucose[i]}</td>{row.map((v, j) => <td key={j} style={{background: `rgba(126,224,161,${0.08 + 0.6 * v / Math.max(...r.sensitivity.growth.flat(), 1e-9)})`}}>{fmt(v, 2)}</td>)}</tr>)}</tbody></table>
          <p className="caption">Relative biomass under the stated bounds ({r.growth.units}). Growth plateaus where the capped amino acids, not glucose or oxygen, become limiting.</p></div>
      </section>
      <section className="quiet-panel"><span className="eyebrow">Central carbon fluxes · pFBA with FVA ranges (≥ 95 % of optimal growth)</span>
        <table className="tme-table"><thead><tr><th>Pathway</th><th>Reaction</th><th>Compartment</th><th>pFBA flux</th><th>FVA range</th></tr></thead>
          <tbody>{r.central.slice(0, 24).map((c: any) => <tr key={c.id}><td>{c.pathway}</td><td title={c.equation}>{c.name}</td><td>{c.compartment}</td><td>{fmt(c.pfba, 3)}</td><td>{fmt(c.min, 3)} to {fmt(c.max, 3)}</td></tr>)}</tbody></table>
        <p className="caption">{r.fvaNote}</p></section>
      <section className="quiet-panel"><span className="eyebrow">Predicted essential genes vs the DepMap CRISPR screen</span>
        <p>{r.essentiality.predictedEssential} of {r.essentiality.genes.toLocaleString()} model genes are essential in silico ({r.essentiality.definition}).</p>
        {dm && <><ul className="tme-checks"><li><Ok ok={dm.aucMeanEffect > 0.7}/><div><strong>AUC {fmt(dm.aucMeanEffect, 3)} · odds ratio {fmt(dm.oddsRatio, 3)} (p = {dm.fisherP.toExponential(1)}) · precision {fmt(dm.precision * 100, 2)} % · recall {fmt(dm.recall * 100, 2)} %</strong>
          <span>{dm.genesCompared.toLocaleString()} metabolic genes in both; {dm.depmapCommonEssential} DepMap common-essential ({dm.definition}). TP {dm.tp} · FP {dm.fp} · FN {dm.fn} · TN {dm.tn}.</span></div></li></ul>
          <div className="onc-three"><div><h4>Both essential</h4><p className="caption">{dm.examples.agree.join(', ')}</p></div><div><h4>Model only</h4><p className="caption">{dm.examples.modelOnly.join(', ')} — often a nutrient the medium lacks (e.g. coenzyme Q, fatty acids) that real cells obtain or bypass.</p></div>
            <div><h4>DepMap only</h4><p className="caption">{dm.examples.depmapOnly.join(', ')} — e.g. subunits of ATP synthase and V-ATPase that the model treats as redundant parts of complexes.</p></div></div></>}
        <p className="caption">{r.evidence}. In-silico essentiality is a model prediction; DepMap is an experimental screen in cancer cell lines. Neither alone establishes a safe therapeutic target.</p></section>
    </>}
  </>;
}
