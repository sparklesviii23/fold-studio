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
  useEffect(() => {
    let active = true;
    rpc<{runs: Run[]; context: {name: string}}>('vcell_benchmarks', {id: cellId}).then(r => {
      if (active) { setRuns(r.runs); setContextName(r.context.name); setReport(null); setSelected(null); }
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
    <p>Compare response predictors using separate cell lines and plates in the installed Tahoe atlas. This local pilot saves its inputs, splits and predictions.</p>
    <button disabled={busy} onClick={run}><RefreshCw size={13}/>{busy ? 'Evaluating…' : 'Run local pilot'}</button>
    <p>Requires the completed Tahoe atlas and untreated DepMap RNA. Up to 12 conditions per line; this pilot uses eight. No model training or cloud compute.</p>
    {runs.map(r => <button key={r.id} disabled={busy} onClick={() => open(r)}>{new Date(r.created).toLocaleDateString()} · {r.testConditions} test conditions</button>)}
    {selected && <p className={selected.contextRole === 'test' ? 'vc-evidence' : 'vc-warn'}>{contextName}: {selected.contextNote}</p>}
    {report && <><BenchmarkReport report={report}/><button onClick={() => exportFile(`fold-benchmark-${report.id}.json`, {text: JSON.stringify(report, null, 2)})}><Download size={13}/>Export reproducible report</button></>}
  </section>;
}
