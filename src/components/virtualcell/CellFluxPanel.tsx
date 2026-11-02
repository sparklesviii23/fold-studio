import {useEffect, useState} from 'react';
import {LoaderCircle} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

/** CellFlux generated crops for one observed field (virtual_cell_cellflux.py). Experimental research plugin:
 *  every result is labelled generated, out of domain for Hep G2, with its identity check. */
export default function CellFluxPanel({cellId, field, onError}: {cellId: string; field: string; onError: (e: string) => void}) {
  const [status, setStatus] = useState<any>(null), [query, setQuery] = useState(''), [perts, setPerts] = useState<any>(null), [pick, setPick] = useState('DMSO'), [job, setJob] = useState<any>(null);
  useEffect(() => { rpc<any>('vcell_cellflux_status', {id: cellId}).then(setStatus).catch(e => onError(String(e))); }, [cellId]);
  useEffect(() => { if (status?.installed) rpc<any>('vcell_cellflux_perturbations', {id: cellId, query}).then(setPerts).catch(() => {}); }, [status?.installed, query]);
  useEffect(() => {                                        // poll a running job
    if (job?.state !== 'running') return;
    const t = setTimeout(() => rpc<any>('vcell_cellflux_job', {id: cellId, run: job.id}).then(setJob).catch(e => onError(String(e))), 4000);
    return () => clearTimeout(t);
  }, [job]);
  async function run() { try { setJob(await rpc<any>('vcell_cellflux_run', {id: cellId, key: field, perturbation: pick, n: 4, seed: 0})); } catch (e) { onError(String(e).replace(/^Error:\s*/, '')); } }
  if (!status) return null;
  if (!status.installed) return <p className="caption">CellFlux plugin not installed: missing {Object.entries(status.parts).filter(([, v]) => !v).map(([k]) => k).join(', ')}.</p>;
  return <div className="vc-cellflux">
    <span className="eyebrow">CellFlux · generated images (experimental)</span>
    {status.benchmark && <p className="caption">In-domain benchmark (BBBC021, MCF7, {Object.keys(status.benchmark.compounds).length} compounds, {status.benchmark.nDmsoInputs} generated cells each): effect-direction cosine {fmt(status.benchmark.summary.effectCosine, 2)} vs {fmt(status.benchmark.summary.baselineCosine, 2)} for a compound-agnostic baseline; generated cells {fmt(status.benchmark.summary.distanceGeneratedToTreated, 2)} vs untreated {fmt(status.benchmark.summary.distanceUntreatedToTreated, 2)} from real treated cells (standardised features). {status.benchmark.caveats[0]} It says nothing about Hep G2.</p>}
    <p className="vc-warn">{status.warning} Inputs: slots {status.inputs.slots.join(', ')}; {Object.entries(status.inputs.fill).map(([k, v]) => `${k} slot filled with ${v}`).join(', ')}; {status.inputs.scaling}.</p>
    <div className="vc-row">
      <input value={query} placeholder={`Search ${perts?.total ?? ''} JUMP perturbations (compound, CRISPR, ORF)`} onChange={e => setQuery(e.target.value)}/>
      <select value={pick} onChange={e => setPick(e.target.value)} aria-label="Perturbation">{perts?.rows.map((p: any) => <option key={p.id} value={p.id}>{p.name} · {p.type}{p.state === 'control' ? ' · control' : ''}</option>)}</select>
      <button disabled={job?.state === 'running'} onClick={run}>{job?.state === 'running' ? <><LoaderCircle size={13} className="spin"/>Generating (≈ 70 s)</> : 'Generate 4 cells'}</button>
    </div>
    {job?.state === 'failed' && <pre className="vc-log">{job.log}</pre>}
    {job?.state === 'completed' && <>
      <p className="vc-evidence"><b>{job.evidence}</b> · {job.perturbation.name} ({job.perturbation.type}) · {job.model.checkpoint} · {job.run.method}, {job.run.nfe} steps, cfg {job.run.cfg}, noise {job.run.noiseLevel} · {job.run.device}, {job.run.seconds} s · seed {job.run.seed}</p>
      <div className="vc-cf-grid">{job.cells.map((c: any, i: number) => <figure key={i}><img src={c.input} alt="observed input crop"/><img src={c.generated} alt="generated crop"/>
        <figcaption>observed · generated</figcaption></figure>)}</div>
      <table className="vc-table"><tbody>
        <tr><td>Pearson r, whole crop</td><td>{Object.entries(job.identity).map(([k, v]: any) => `${k} ${fmt(v, 2)}`).join(' · ')}</td></tr>
        <tr><td>Pearson r, within the cell</td><td>{Object.entries(job.identityInCell).map(([k, v]: any) => `${k} ${fmt(v, 2)}`).join(' · ')}</td></tr>
        <tr><td>Nucleus mask Dice (DNA)</td><td>{job.nuclei.map((n: any) => `${fmt(n.dice, 2)} (area ${fmt(n.areaFractionIn, 2)} → ${fmt(n.areaFractionOut, 2)})`).join(' · ')}</td></tr>
        <tr><td>DNA intensity ratio</td><td>×{fmt(job.dnaIntensityRatio, 2)}</td></tr></tbody></table>
      <p className="caption">Identity check. {job.identityNote}</p>
      <p className="caption">{job.model.citation} {job.model.licence}. Checkpoint SHA-256 {job.checkpointSha256.slice(0, 12)}…</p>
    </>}
  </div>;
}
