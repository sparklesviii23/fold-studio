import {useEffect, useState} from 'react';
import {Download, RefreshCw} from 'lucide-react';
import {exportFile, rpc} from '../../lib/api';

type Estimate = {mean: number | null; ci95: [number, number] | null; n: number};
type Scores = Record<string, {mae: Estimate; mse: Estimate; pearson: Estimate}>;
type Trial = {cellLine: string; cellosaurus: string; drug: string; concentration: number; unit: string;
  nearestDonor: string; metrics: Record<string, {mae: number; mse: number; pearson: number | null; genes: number}>};
export type Benchmark = {id: string; protocol: string; created: string; models: Record<string, string>;
  dataset: {unit: string}; summary: {test: Scores; validation: Scores}; results: {test: Trial[]};
  testMseDifferenceVsTrainingMean: Record<string, Estimate>; limitations: string[];
  split: {train: string[]; validation: string[]; test: string[]; trainPlates: number[]; validationPlates: number[]; testPlates: number[]};
  excludedContexts?: {cellosaurus: string; cellLine: string; reason: string}[];
  uncertainty: {method: string; predictiveCalibration: string}; promotion: {reason: string}};
type Run = {id: string; created: string; protocol: string; contextRole: string | null; contextNote: string; testConditions: number};
const value = (n: number | null | undefined) => n == null ? 'undefined' : n.toFixed(3);
const estimate = (x: Estimate) => `${value(x.mean)}${x.ci95 ? ` [${x.ci95.map(value).join(', ')}]` : ''}`;

export function BorzoiBenchmarkReport({report}: {report:any}) {
  return <div className="vc-benchmark-report"><h3>Borzoi · genomic coverage</h3>
    <p>{report.testLoci} held-out genomic loci; {report.illustrativeLoci} separate illustrative loci. The assays are related to training sources. This is not an independent-study test.</p>
    {report.tracks.map((t:any)=><section key={t.index}><h4>{t.metadata.description} · {t.metadata.identifier} · {t.cellosaurus}</h4>
      <table className="vc-table"><thead><tr><th>Model</th><th>Scored / attempted loci</th><th>Spearman</th><th>log-profile Pearson</th></tr></thead><tbody>
        {Object.entries(report.summary[String(t.index)]).map(([model,s]:any)=><tr key={model}><td>{model}</td><td>{s.scored} / {s.attempted}</td><td>{estimate({...s.spearman,n:s.scored})}</td><td>{estimate({...s.pearson,n:s.scored})}</td></tr>)}
      </tbody></table></section>)}
    <p>95% intervals resample whole loci. Failed or insufficient-reference loci remain in attempted counts. Pearson uses log1p values; Spearman compares ranks. Original ENCODE signal and model output have different transformations, so count-scale errors are not reported.</p>
    <details><summary>Per-locus results and failure cases</summary><div className="vc-benchmark-scroll"><table className="vc-table"><thead><tr><th>Gene</th><th>Track</th><th>Model</th><th>Cohort</th><th>Covered bins</th><th>Status</th><th>Spearman</th></tr></thead><tbody>
      {report.perLocus.map((r:any,i:number)=><tr key={i}><td>{r.symbol}</td><td>{r.track}</td><td>{r.model}</td><td>{r.cohort}</td><td>{r.n}</td><td>{r.status}</td><td>{value(r.spearman)}</td></tr>)}
    </tbody></table></div></details>
    <details><summary>Ensemble comparisons</summary><p>Paired whole-locus differences; positive favours the ensemble. These comparisons are exploratory, without adjustment for multiple comparisons.</p>{Object.entries(report.ensemblePairedComparisons??{}).map(([k,v]:any)=><p key={k}>{k}: {value(v.meanDifference)} {v.ci95?`[${v.ci95.map(value).join(', ')}]`:''} · {v.n} paired loci.</p>)}</details>
    <details><summary>Checkpoints, runtime and scientific limits</summary><pre>{JSON.stringify(report.checkpoints,null,2)}</pre><p>Total inference seconds: {value(report.inferenceSeconds)}. Seconds by replicate: {JSON.stringify(report.replicateSeconds)}.</p><ul>{report.limitations.map((s:string)=><li key={s}>{s}</li>)}</ul></details>
  </div>;
}

export function ResponseDiagnostics({report}:{report:any}) {
  const s=report.summary;
  return <details><summary>Why the original response models failed · {s.n} conditions</summary>
    <p>The matched drug/dose donor mean beat unchanged control in {s.donorBeatsControlCases} of {s.n} cases. Across-plate all-gene correlation was {value(s.sameLineAcrossPlateMeanPearson)}. In genes selected using the other plate only, it was {value(s.otherPlateSelectedMeanPearson)} across {s.otherPlateSelectedPairs} pairs. These answer different diagnostic questions and do not replace the original all-gene scores.</p>
    <p>Prediction energy {value(s.donorMeanPredictionEnergy)} exceeded twice its alignment with measured effects {value(s.donorMeanTwicePredictionTruthProduct)}, explaining its larger squared error mathematically. The biological and technical causes remain partly unresolved.</p>
    {Object.entries(report.classification).map(([k,v]:any)=><p key={k}><b>{k}</b>: {v}</p>)}
    <details><summary>Condition-level signal, sample counts and batches</summary>{report.conditions.map((r:any,i:number)=><p key={i}>{r.cellLine}, {r.drug} {r.concentration} {r.unit} · plates {r.targetPlates.join(', ')} · treated cells {r.treatedCells.join(', ')} · control cells {r.controlCells.join(', ')} · approximate |Wald z| &gt; 4 genes: {r.waldAbsZ4Genes.join(', ')}.</p>)}</details>
    <ul>{report.limitations.map((note:string)=><li key={note}>{note}</li>)}</ul>
    <button onClick={()=>exportFile(`fold-response-diagnostics-${report.sourceRun}.json`,{text:JSON.stringify(report,null,2)})}>Export diagnostic report</button>
  </details>;
}

export function BenchmarkReport({report}: {report: Benchmark}) {
  const failures = [...report.results.test].sort((a, b) =>
    (b.metrics.drug_dose_mean.mse - b.metrics.unchanged.mse) - (a.metrics.drug_dose_mean.mse - a.metrics.unchanged.mse)).slice(0, 5);
  return <div className="vc-benchmark-report">
    <p className="vc-evidence">Retrospective prediction benchmark · {report.dataset.unit}</p>
    <p>{report.split.train.length} training, {report.split.validation.length} validation and {report.split.test.length} test lines.
      Plates {report.split.trainPlates.join(', ')} train; {report.split.validationPlates.join(', ')} validate; {report.split.testPlates.join(', ')} test.</p>
    <p>Test scores across {report.results.test.length} conditions. Lower MAE and MSE are better. Brackets show 95% bootstrap intervals.</p>
    <div className="vc-benchmark-scroll"><table className="vc-table"><thead><tr><th>Predictor</th><th>MAE</th><th>MSE</th><th>Effect Pearson r</th></tr></thead>
      <tbody>{Object.entries(report.summary.test).map(([model, s]) => <tr key={model}><td>{report.models[model]}</td><td>{estimate(s.mae)}</td><td>{estimate(s.mse)}</td><td>{estimate(s.pearson)}</td></tr>)}</tbody></table></div>
    <p>Zero-response Pearson correlation is undefined. All models use the same eligible genes; no test-response gene selection.</p>
    <details><summary>Validation scores and paired comparisons</summary>
      {Object.entries(report.summary.validation).map(([model, s]) => <p key={model}>{report.models[model]}: validation MSE {estimate(s.mse)}</p>)}
      {Object.entries(report.testMseDifferenceVsTrainingMean).map(([model, s]) => <p key={model}>{report.models[model]}: test MSE difference versus training mean {estimate(s)}. Negative favours the predictor.</p>)}
    </details>
    <details><summary>Largest donor-mean errors relative to unchanged control</summary>
      {failures.map((x, i) => <p key={i}>{x.cellLine} ({x.cellosaurus}), {x.drug} {x.concentration} {x.unit}: donor-mean MSE {value(x.metrics.drug_dose_mean.mse)};
        unchanged {value(x.metrics.unchanged.mse)}; {x.metrics.unchanged.genes} scored genes.</p>)}
    </details>
    <p className="vc-warn">Research pilot. {report.promotion.reason}</p>
    <details><summary>Domain, uncertainty and limitations</summary>
      <p>{report.uncertainty.method}. Predictive calibration: {report.uncertainty.predictiveCalibration}.</p>
      <p>Test identities: {report.split.test.join(', ')}.</p>
      {report.excludedContexts?.map(x => <p key={x.cellosaurus}>Excluded {x.cellLine} ({x.cellosaurus}): {x.reason}.</p>)}
      <ul>{report.limitations.map(note => <li key={note}>{note}</li>)}</ul>
    </details>
    <small>{report.protocol} · {report.created} · {report.id}</small>
  </div>;
}

export default function BenchmarkPanel({cellId, onError}: {cellId: string; onError: (message: string) => void}) {
  const [runs, setRuns] = useState<Run[]>([]), [report, setReport] = useState<Benchmark | null>(null), [busy, setBusy] = useState(false);
  const [contextName, setContextName] = useState(''), [selected, setSelected] = useState<Run | null>(null);
  const [panels,setPanels]=useState<any[]>([]),[panel,setPanel]=useState<any>(null),[diagnostics,setDiagnostics]=useState<any[]>([]);
  useEffect(() => {
    let active = true;
    setReport(null);setSelected(null);setPanel(null);setPanels([]);setDiagnostics([]);
    rpc<{runs: Run[]; context: {name: string};regulatoryPanels?:any[];responseDiagnostics?:any[]}>('vcell_benchmarks', {id: cellId}).then(r => {
      if (active) { setRuns(r.runs); setContextName(r.context.name);setPanels(r.regulatoryPanels??[]);setDiagnostics(r.responseDiagnostics??[]); }
    }).catch(e => { if (active) onError(String(e)); });
    return () => { active = false; };
  }, [cellId, onError]);
  async function open(run: Run) {
    setBusy(true);
    try { const r = await rpc<Benchmark>('vcell_benchmark_get', {id: cellId, run: run.id}); setReport(r); setSelected(run); }
    catch (e) { onError(String(e)); } finally { setBusy(false); }
  }
  async function run() {
    setBusy(true);
    try {
      const r = await rpc<Benchmark>('vcell_benchmark_run', {id: cellId, seed: 17, conditionsPerLine: 8}); setReport(r);
      const listing = await rpc<{runs: Run[]}>('vcell_benchmarks', {id: cellId}); setRuns(listing.runs); setSelected(listing.runs.find(x => x.id === r.id) ?? null);
    } catch (e) { onError(String(e)); } finally { setBusy(false); }
  }
  return <section aria-label="Scientific benchmarking">
    <h3>Transcript response · Tahoe-100M</h3>
    <p>Compare response predictors using separate cell lines and plates in the installed Tahoe atlas. This local pilot saves its inputs, splits and predictions.</p>
    <button disabled={busy} onClick={run}><RefreshCw size={13}/>{busy ? 'Evaluating…' : 'Run local pilot'}</button>
    <p>Requires the completed Tahoe atlas and untreated DepMap RNA. Up to 12 conditions per line; this pilot uses eight. No model training or cloud compute.</p>
    {runs.map(r => <button key={r.id} disabled={busy} onClick={() => open(r)}>{new Date(r.created).toLocaleDateString()} · {r.testConditions} test conditions</button>)}
    {selected && <p className={selected.contextRole === 'test' ? 'vc-evidence' : 'vc-warn'}>{contextName}: {selected.contextNote}</p>}
    {report && <><BenchmarkReport report={report}/><button onClick={() => exportFile(`fold-benchmark-${report.id}.json`, {text: JSON.stringify(report, null, 2)})}><Download size={13}/>Export reproducible report</button></>}
    {diagnostics.map(d=><ResponseDiagnostics key={d.sourceRun} report={d}/>)}
    <h3>Regulatory coverage · Borzoi</h3>
    {!panels.length&&<p>No completed expanded Borzoi benchmark is saved in this library. A prepared panel is not an accuracy result. The earlier single-locus run remains under Genomic regulation.</p>}
    {panels.map(p=><button key={p.run} disabled={busy} onClick={async()=>{setBusy(true);try{setPanel(await rpc('vcell_borzoi_panel_get',{id:cellId,run:p.run}));}catch(e){onError(String(e));}finally{setBusy(false);}}}>{p.testLoci} test loci · {p.tracks.length} tracks · {p.run.slice(0,8)}</button>)}
    {panel&&<><BorzoiBenchmarkReport report={panel}/><button onClick={()=>exportFile(`fold-borzoi-panel-${panel.run}.json`,{text:JSON.stringify(panel,null,2)})}>Export reproducible Borzoi report</button></>}
  </section>;
}
