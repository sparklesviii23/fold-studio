import {useEffect, useState} from 'react';
import {LoaderCircle, Play, TriangleAlert} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');

function Table({rows, contrast}: {rows: any[]; contrast?: boolean}) {
  return <div className="onc-scroll"><table className="tme-table"><thead><tr><th>Sender</th><th>Ligand</th><th>Receptor</th><th>Receiver</th>{contrast ? <><th>Tumor donors</th><th>Normal donors</th></> : <><th>Donors calling it</th><th>Median score</th></>}<th>LR resources</th></tr></thead>
    <tbody>{rows.map((r, i) => <tr key={i}><td>{r.sender}</td><td>{r.ligand}</td><td>{r.receptor}</td><td>{r.receiver}</td>
      {contrast ? <><td>{r.case}</td><td>{r.control}</td></> : <><td>{r.donors} of {r.donorsWithTypes}</td><td>{fmt(r.medianScore, 3)}</td></>}<td>{r.resources}</td></tr>)}</tbody></table></div>;
}

/** Inferred cell–cell communication: ligand–receptor co-expression with donors as replicates, never shown as measured signalling. */
export default function CellComm({projectId}: {projectId: string}) {
  const [st, setSt] = useState<any>(null), [res, setRes] = useState<any>(null), [error, setError] = useState('');
  const read = async () => { try { const s = await rpc<any>('onc_cc_status', {projectId}); setSt(s); if (s.done && !s.job?.running) setRes(await rpc('onc_cc_result', {projectId})); return s; } catch (e) { setError(err(e)); } };
  useEffect(() => { void read(); }, []);
  useEffect(() => { if (!st?.job?.running) return; const t = setTimeout(read, 2500); return () => clearTimeout(t); }, [st]);
  return <>
    <div className="page-heading"><div><span className="eyebrow">CELL–CELL COMMUNICATION · OMNIPATH LIGAND–RECEPTOR PAIRS · DONORS AS REPLICATES</span><h1>Who could be talking <em>to whom.</em></h1>
      <p>Ligand–receptor co-expression between cell types in the installed single-cell tumor atlas, called only where it holds across donors. This is inferred communication: expression does not show binding, signalling or that the cells are neighbours.</p></div></div>
    <section className="quiet-panel">
      <div className="onc-row"><button className="button primary" disabled={!st?.installed || !st?.runtimeReady || st?.job?.running} onClick={async () => { setError(''); try { setSt(await rpc('onc_cc_run', {projectId})); } catch (e) { setError(err(e)); } }}><Play size={14}/>{res ? 'Run again' : 'Infer communication'} (~10 s)</button>
        {st?.job?.running && <span className="caption"><LoaderCircle size={12} className="spin"/> running…</span>}
        {st && !st.installed && <span className="caption">Download the single-cell dataset in the Single-cell tab first.</span>}</div>
      {error && <p className="caption cs-error">{error}</p>}
      {st?.job?.log && st.job.running && <pre className="onc-log">{st.job.log}</pre>}</section>
    {res && <>
      <section className="quiet-panel"><span className="onc-evidence">{res.evidence}</span>
        <p>{res.called} interactions called across {Object.keys(res.donors).length} donors with at least two cell types ({res.cells.toLocaleString()} cells, {res.pairs.toLocaleString()} curated ligand–receptor pairs measured).</p>
        <p className="caption">Method: {res.method}. {res.resource ? `OmniPath retrieved ${res.resource.retrieved.slice(0, 10)}, SHA-256 ${res.resource.sha256.slice(0, 12)}….` : ''}</p>
        <ul className="tme-checks"><li><TriangleAlert size={13}/><div><span>{res.caveat} This dataset is mostly epithelial (keratinocytes, sebocytes, basal cells), so immune and stromal communication is not represented.</span></div></li></ul></section>
      <section className="quiet-panel"><span className="eyebrow">Most consistent interactions</span><Table rows={res.interactions.slice(0, 40)}/></section>
      <section className="quiet-panel"><span className="eyebrow">Called in tumor donors but not normal ({res.contrast.case} vs {res.contrast.control})</span>
        {res.gainedInCase.length ? <Table rows={res.gainedInCase.slice(0, 30)} contrast/> : <p className="caption">None meet the threshold (≥ 50 percentage points more donors, ≥ 2 donors per group).</p>}</section>
      <section className="quiet-panel"><span className="eyebrow">Called in normal donors but not tumor</span>
        {res.lostInCase.length ? <Table rows={res.lostInCase.slice(0, 30)} contrast/> : <p className="caption">None meet the threshold.</p>}</section>
    </>}
  </>;
}
