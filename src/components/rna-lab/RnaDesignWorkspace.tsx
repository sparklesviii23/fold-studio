import {useEffect, useState} from 'react';
import {rpc} from '../../lib/api';
import './rna-design.css';

function pairList(structure: string): [number, number][] {
  const stack: number[] = [], out: [number, number][] = [];
  [...structure].forEach((c, i) => {if (c === '(') stack.push(i + 1); else if (c === ')' && stack.length) out.push([stack.pop()!, i + 1]);});
  return out;
}

function Fold({structure, sequence, label, marked, color}: {structure: string; sequence: string; label: string; marked: number[][]; color: string}) {
  const n = structure.length, width = 520, x = (i: number) => 20 + (i - 1) * 480 / Math.max(1, n - 1);
  const has = (a: number, b: number) => marked.some(p => p[0] === a && p[1] === b);
  return <figure className="design-fold"><figcaption>{label}</figcaption>
    <svg viewBox={`0 0 ${width} 220`} role="img" aria-label={label}>
      <line x1="20" y1="174" x2="500" y2="174" stroke="currentColor" opacity="0.25"/>
      {pairList(structure).map(([a,b]) => <path key={a} d={`M${x(a)},170 Q${(x(a)+x(b))/2},${170-Math.min(300,(x(b)-x(a))*.65)} ${x(b)},170`} fill="none" stroke={has(a,b) ? color : '#6fc6b2'} strokeWidth={has(a,b) ? 3 : 1.6}/>) }
      {[...sequence].map((b,i) => <text key={i} x={x(i+1)} y="192" textAnchor="middle" fill="currentColor" fontSize={n > 65 ? 5 : n > 35 ? 8 : 12}>{b}</text>)}
      <text x="20" y="211" fontSize="10" fill="currentColor">1</text><text x="500" y="211" fontSize="10" textAnchor="end" fill="currentColor">{n} nt</text>
    </svg><code>{structure}</code></figure>;
}

const initial = {target: '((((....))))', locks: '', mask: '', wanted: 3, maxCandidates: 128, maxSeconds: 30, seed: 1, gcMin: 0, gcMax: 1, maxHomopolymer: 128, method: 'solver'};
export default function RnaDesignWorkspace({projectId, saved, onSaved}: {projectId: string; saved?: any; onSaved?: () => Promise<unknown>}) {
  const [input, setInput] = useState(initial), [catalog, setCatalog] = useState<any>(null), [quote, setQuote] = useState<any>(null);
  const [runId, setRunId] = useState<string | undefined>(), [job, setJob] = useState<any>(null), [result, setResult] = useState<any>(null);
  const [pollVersion, setPollVersion] = useState(0);
  const [selected, setSelected] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false), [approved, setApproved] = useState(false), [savedId, setSavedId] = useState(''), [history, setHistory] = useState<any[]>([]);
  useEffect(() => {void rpc<any>('rna_design_catalog', {}).then(setCatalog).catch(e => setError(String(e))); void rpc<any[]>('rna_design_history', {projectId}).then(setHistory);}, [projectId]);
  useEffect(() => {
    if (saved?.projectId === projectId && saved.result) {
      setResult(saved.result); setInput(saved.result.request); setRunId(undefined); setJob(null); setSelected(saved.candidate.id); setSavedId(saved.runId);
    }
  }, [saved, projectId]);
  useEffect(() => {
    let valid = true;
    setQuote(null); setApproved(false);
    const timer = setTimeout(() => {void rpc<any>('rna_design_quote', input).then(q => {if (valid) {setQuote(q); setError('');}}, e => {if (valid) setError(String(e));});}, 250);
    return () => {valid = false; clearTimeout(timer);};
  }, [input]);
  useEffect(() => {
    if (!runId) return;
    let live = true, timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const out = await rpc<any>('rna_design_run', {projectId, id: runId});
        if (!live) return;
        setJob(out.job);
        if (out.result) {setResult(out.result); setSelected(s => s || out.result.candidates[0]?.id || '');}
        if (['queued','running'].includes(out.job.state)) timer = setTimeout(poll, 1500);
      } catch (e) {if (live) {setError(String(e)); timer = setTimeout(poll, 4000);}}
    }
    void poll(); return () => {live = false; clearTimeout(timer);};
  }, [runId, projectId, pollVersion]);
  const active = job && ['queued','running'].includes(job.state);
  const choice = result?.candidates.find((c: any) => c.id === selected) ?? result?.candidates[0];
  async function start() {
    setBusy(true); setError('');
    try {
      const j = await rpc<any>('rna_design_start', {...input, projectId, quoteSha256: quote.quoteSha256, approvedRemoteCost: approved});
      setResult(null); setSelected(''); setSavedId(''); setJob(j); setRunId(j.id);
      setHistory(await rpc<any[]>('rna_design_history', {projectId}));
    } catch (e) {setError(String(e));} finally {setBusy(false);}
  }
  async function save() {
    setBusy(true);
    try {const row = await rpc<any>('rna_design_save', {projectId, id: runId, candidateId: choice.id}); setSavedId(row.id); await onSaved?.();}
    catch (e) {setError(String(e));} finally {setBusy(false);}
  }
  async function cancel() {
    try {const out = await rpc<any>('rna_design_cancel', {projectId, id: runId}); setJob(out.job); if (out.result) setResult(out.result);} catch (e) {setError(String(e));}
  }
  async function recover() {
    try {const out = await rpc<any>('rna_design_run', {projectId, id: runId, retryFetch:true}); setJob(out.job); if(out.result) setResult(out.result);}
    catch(e) {setError(String(e));}
  }
  async function resume() {
    setBusy(true); setError('');
    try {const j = await rpc<any>('rna_design_resume', {projectId, id: runId, maxSeconds: input.maxSeconds, maxCandidates: input.maxCandidates, wanted: input.wanted, quoteSha256: quote?.quoteSha256, approvedRemoteCost: approved}); setJob(j); setRunId(j.id); setPollVersion(v => v + 1);} catch (e) {setError(String(e));} finally {setBusy(false);}
  }
  return <div className="design-workspace">
    <aside className="mech-panel design-input">
      <span className="eyebrow">RNA Design</span><h2>Start with a target fold</h2>
      <label>Target secondary structure<textarea aria-label="Design target" className="rna-seq" rows={4} value={input.target} disabled={active} onChange={e => setInput({...input,target:e.target.value})} spellCheck={false}/></label>
      <p className="caption">Nested dot-bracket · 8–128 nt · isolated RNA at 37 °C</p>
      <div className="button-row"><button className="button" disabled={active} onClick={() => setInput({...initial})}>Simple target</button><button className="button" disabled={active} onClick={() => setInput({...initial,target:catalog?.hardTarget ?? initial.target})}>Branched target</button></div>
      <details><summary>Constraints and search limits</summary><div className="design-settings">
        <label>Locked bases · ACGU, dot for free<textarea aria-label="Locked bases" className="rna-seq" value={input.locks} disabled={active} onChange={e => setInput({...input,locks:e.target.value})}/></label>
        <label>Sequence mask · RNA IUPAC<textarea aria-label="Sequence mask" className="rna-seq" value={input.mask} disabled={active} onChange={e => setInput({...input,mask:e.target.value})}/></label>
        <label>Method<select value={input.method} disabled={active} onChange={e => setInput({...input,method:e.target.value})}><option value="solver">Solver · default</option>{catalog?.methods.includes('qwen') && <><option value="qwen">Qwen alone · research pilot</option><option value="hybrid">Qwen + solver · research pilot</option></>}</select></label>
        {(['wanted','maxCandidates','maxSeconds','seed','gcMin','gcMax','maxHomopolymer'] as const).map(k => <label key={k}>{{wanted:'Distinct candidates wanted',maxCandidates:'Candidate limit',maxSeconds:'Total search limit · s',seed:'Seed',gcMin:'Minimum GC fraction',gcMax:'Maximum GC fraction',maxHomopolymer:'Maximum repeated bases'}[k]}<input aria-label={k} type="number" value={input[k]} step={k.startsWith('gc') ? 0.05 : 1} disabled={active} onChange={e => setInput({...input,[k]:Number(e.target.value)})}/></label>)}
      </div></details>
      {quote && <><p className="design-hardware">{quote.hardware}</p><p className="caption">Limit: {quote.limits.candidates} candidates · {quote.limits.searchSeconds} s search{quote.mode === 'modal' ? ` · ${quote.limits.containerSeconds} s container` : ''}</p>
        <details><summary>Cost and uploaded inputs</summary><p>{quote.mode === 'modal' ? `Account: ${quote.accountName ?? quote.accountId ?? 'No account selected'}. ` : ''}Estimated compute: US${quote.cost.estimatedMaximum.toFixed(4)}. {quote.cost.note}</p><p>{quote.uploads.length ? quote.uploads.join(', ') : 'Inputs stay on This Mac.'}</p><p>Choose This Mac or Modal in Settings → Compute servers.</p><a href={quote.cost.rateSource} target="_blank" rel="noreferrer">Modal rates · checked {quote.cost.rateChecked}</a></details>
        {quote.mode === 'modal' && <label className="design-approval"><input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)}/>Approve this Modal CPU run and its estimated cost.</label>}
      </>}
      <button className="button primary" onClick={start} disabled={busy || active || !quote || (quote.mode === 'modal' && !approved)}>{busy ? 'Starting…' : 'Design RNA'}</button>
      {active && <button className="button" onClick={cancel}>Cancel · keep saved batches</button>}
      {!active && runId && job?.data?.remoteTaskId && <button className="button" onClick={recover}>Recover remote results</button>}
      {!active && runId && <button className="button" disabled={busy || !quote || (quote.mode === 'modal' && !approved)} onClick={resume}>Resume with current limits</button>}
      <details><summary>Run history</summary>{history.map(j => <button className="button" key={j.id} disabled={active} onClick={() => {setResult(null);setSelected('');setSavedId('');setRunId(j.id);setInput(j.data.request);}}>{j.name} · {j.state}</button>)}</details>
    </aside>
    <main className="mech-panel design-results">
      <div className="rna-badges"><span className="evidence-badge">Computational prediction</span><span className="rna-note">Experimental evidence is not available for these designs.</span></div>
      {error && <p className="mech-error" role="alert">{error}</p>}
      {job && <p role="status">{job.state} · {job.data.phase}{job.data.error ? ` · ${job.data.error}` : ''}</p>}
      {!result && <div className="design-empty"><h2>A target. Several distinct sequences.</h2><p>Design RNA searches for sequences whose predicted minimum energy fold matches your target. The second model checks the best candidates.</p></div>}
      {result && <><h2>{result.qualifyingCount} distinct candidates qualify</h2><p className="caption">{result.candidates.length} evaluated · {result.metrics.solverCalls} solver calls · {result.metrics.elapsedSeconds.toFixed(3)} s search · {result.metrics.stopReason}</p>
        <div className="design-table"><table><thead><tr><th>Compare sequence</th><th>Pair F1</th><th>Target probability</th><th>Second model</th></tr></thead><tbody>{result.candidates.slice(0,40).map((c: any) => <tr key={c.id} className={choice?.id === c.id ? 'selected' : ''}><td><button aria-label={`Compare ${c.sequence}`} onClick={() => {setSelected(c.id);setSavedId('');}}><code>{c.sequence}</code><small>{c.qualifies ? 'Qualifies' : 'Near miss'}</small></button></td><td>{c.pairF1.toFixed(3)}</td><td>{c.targetProbability.toPrecision(3)}</td><td>{c.independent ? c.independent.agreesWithTarget ? 'Agrees' : 'Disagrees' : 'Not checked'}</td></tr>)}</tbody></table></div>
        {choice && <><div className="design-folds"><Fold structure={result.request.target} sequence={choice.sequence} label="Target · missed pairs in amber" marked={choice.missedPairs} color="#e5b75e"/><Fold structure={choice.structure} sequence={choice.sequence} label="ViennaRNA prediction · extra pairs in rose" marked={choice.extraPairs} color="#ed899e"/></div>
          <p>{choice.failureReasons.length ? choice.failureReasons.join(' ') : 'The ViennaRNA minimum energy fold matches the target. All sequence constraints pass.'}</p>
          <p>Target energy gap: {choice.targetGapKcalMol.toFixed(3)} kcal/mol · Ensemble defect: {choice.ensembleDefect.toFixed(3)}</p>
          {choice.independent && <details open><summary>Second model · {choice.independent.agreesWithTarget ? 'agrees with target' : 'disagrees with target'}</summary><Fold structure={choice.independent.structure} sequence={choice.sequence} label="RNA Lab independent prediction" marked={choice.independent.disagreementPairs} color="#ed899e"/><p>Pair disagreements: {choice.independent.disagreementPairs.map((p: number[]) => p.join('–')).join(', ') || 'none'}. Model: {choice.independent.version}.</p></details>}
          {runId && <button className="button" disabled={busy} onClick={save}>Save exact candidate to Research Library</button>}{savedId && <p role="status">Saved result · {savedId}</p>}
          <details><summary>Scores, versions and provenance</summary><p>Run ID: {runId ?? saved?.runId}. Result SHA-256: {result.sha256}</p><p>{result.evidence}</p><p>{result.solverAccounting}</p><pre>{JSON.stringify({request:result.request,scorer:result.scorer,source:choice.source,metrics:result.metrics,startupSeconds:job?.data?.startupSeconds,wallSeconds:job?.data?.wallSeconds,remoteUsage:job?.data?.runtimeUsage,computeQuote:job?.data?.quote,proposalModel:result.proposalModel,billedCost:job?.data?.billedCost ?? null},null,2)}</pre></details>
        </>}
      </>}
    </main>
  </div>;
}
