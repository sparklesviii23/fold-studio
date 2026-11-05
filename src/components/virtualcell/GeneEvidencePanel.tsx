import {useEffect, useState} from 'react';
import {rpc, exportFile} from '../../lib/api';
import {RegulatoryTrack} from './RegulatoryTrack';

export function PanelGeneTrack({item}: {item: any}) {
  const region=item.region; const series=['f0','f1','ensemble']; const high=Math.max(1e-12,...item.preview.flatMap((p:any)=>series.map(k=>p[k])));
  const observedHigh=Math.max(1e-12,...item.preview.map((p:any)=>p.observed??0));
  const points=(key:string,max:number)=>item.preview.filter((p:any)=>p[key]!=null).map((p:any)=>`${30+740*((p.start+p.end)/2-region[1])/(region[2]-region[1])},${140-115*p[key]/max}`).join(' ');
  return <section><h4>{item.trackDescription} · {item.trackIdentifier}</h4>
    <p className="vc-evidence">Predicted · {item.cohort==='heldout'?'Held-out genomic region':'Training/validation-region illustration; not an independent test'}</p>
    <p>hg38 {region[0]}:{region[1]}–{region[2]} · 32 bp bins · {item.fold} · {item.cellosaurus}</p>
    {item.verificationPolicy&&<p className="caption">Original exact reproduction was verified in a prior run; this run uses a separate repeatability check on its assigned GPU. Strict cross-GPU comparison: {item.crossDeviceOriginalTolerancePassed?'passed':'failed; exact agreement across GPU variants is not established'}.</p>}
    {!item.fullGeneCovered&&<p className="vc-warn">The model output window covers only part of this gene. Whole-gene abundance is not estimated.</p>}
    <svg viewBox="0 0 800 165" role="img" aria-label="Borzoi model replicates and ensemble">
      {series.map((key,i)=><polyline key={key} points={points(key,high)} fill="none" stroke={['#95adff','#e2a4c8','#64d6b2'][i]}/>)}
    </svg>
    <p>Blue: replicate 0. Pink: replicate 1. Green: their explicitly evaluated mean. Raw assay-transformed output. Preview points average 16 model bins; metrics use the original 32 bp bins.</p>
    <svg viewBox="0 0 800 165" role="img" aria-label="Observed compatible ENCODE reference">
      {item.preview.filter((p:any)=>p.observed!=null).map((p:any,i:number)=><circle key={i} cx={30+740*((p.start+p.end)/2-region[1])/(region[2]-region[1])} cy={140-115*p.observed/observedHigh} r="2.4" fill="#dfc383"/>)}
    </svg>
    <p>Observed ENCODE reference · {item.observedUnit}. Independent vertical scale; each preview point averages only covered bins in its block. Uncovered bins are missing.</p>
    <table className="vc-table"><thead><tr><th>Model</th><th>Spearman</th><th>log-profile Pearson</th><th>Covered bins</th></tr></thead><tbody>
      {Object.entries(item.metrics).map(([key,m]:any)=><tr key={key}><td>{key}</td><td>{m.spearman==null?'not estimable':m.spearman.toFixed(3)}</td><td>{m.pearson==null?'not estimable':m.pearson.toFixed(3)}</td><td>{m.n} / 6144 · {m.status}</td></tr>)}
    </tbody></table>
    <p className="caption">Reference signal differs from the authors' processed target. These are profile associations, not calibrated count errors or proof of cell activity. Two-model disagreement is not a calibrated confidence interval.</p>
    <details><summary>Checkpoints and replicate variation</summary>{(item.checkpointProvenance??[]).map((p:any)=><p key={p.replicate} className="caption" style={{overflowWrap:'anywhere'}}>Replicate {p.replicate} · SHA-256 {p.sha256}</p>)}{typeof item.replicateMeanAbsoluteDisagreement==='number'&&<p className="caption">Mean absolute replicate disagreement: {item.replicateMeanAbsoluteDisagreement.toPrecision(4)} raw model units. This is not calibrated confidence.</p>}</details>
  </section>;
}

export default function GeneEvidencePanel({cellId,gene,onError,onSaved}: {cellId:string;gene:string;onError:(message:string)=>void;onSaved?:()=>void}) {
  const [report,setReport]=useState<any>(null),[saved,setSaved]=useState(''),[error,setError]=useState('');
  useEffect(()=>{let active=true;setReport(null);setSaved('');setError('');rpc<any>('vcell_gene_explore',{id:cellId,query:gene}).then(r=>{if(active)setReport(r);}).catch(e=>{if(active){setError(String(e));onError(String(e));}});return()=>{active=false;};},[cellId,gene,onError]);
  async function save(){try{const r=await rpc<any>('vcell_gene_snapshot',{id:cellId,query:gene});setSaved(`Saved ${r.snapshot.id.slice(0,8)} in this cell’s state history.`);onSaved?.();}catch(e){onError(String(e));}}
  return <section className="vc-tx" aria-label="Observed versus predicted gene explorer"><h3>Observed versus predicted · {gene}</h3>
    {error?<p className="vc-warn">Could not load this gene report: {error}</p>:!report?<p>Gathering compatible evidence…</p>:!report.supported?<p className="vc-warn">Resolve an unambiguous gene to continue.</p>:<>
      <p>Measured RNA, transcript isoforms and protein abundance appear above. Localization and pathway membership are curated annotations. Saved structures retain their own origin and confidence.</p>
      <h4>Regulatory predictions</h4>
      {report.regulatory.message&&<p className="vc-warn">{report.regulatory.message}</p>}
      {report.regulatory.predictions.map((p:any,i:number)=>p.provider==='bio_borzoi'?<RegulatoryTrack key={i} track={p.result}/>:<PanelGeneTrack key={i} item={p}/>)}
      <h4>Predictive cellular response</h4><p className="vc-warn">{report.predictiveResponse.message}</p><p>{report.predictiveResponse.reason}</p>
      <p>RNA expression, protein ppm and genomic coverage use distinct units. The data come from separate experiments; these values are not simultaneous measurements of one cell.</p>
      <button onClick={save}>Save gene evidence in state history</button>
      <button onClick={()=>exportFile(`fold-${gene}-observed-predicted.json`,{text:JSON.stringify(report,null,2)})}>Export observed-versus-predicted report</button>
      {saved&&<p role="status">{saved}</p>}
    </>}
  </section>;
}
