import {useState} from 'react';
import {LoaderCircle, Send, TriangleAlert} from 'lucide-react';
import {rpc} from '../../lib/api';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');
const EXAMPLES = ['Which datasets support the BRAF dependency in Skin?', 'Does MAP2K1 reproduce in another screen in BRAF mutant lines?', 'How does MAPK1 in BRAF change after controlling for lineage?',
  'What normal-tissue evidence is missing for PRMT5?', 'Is the KRAS RAF1 interaction experimental or predicted?', 'Which paper first reported BRAF and MAP2K1?',
  'What model equation explains MDM2 behaviour?', 'How well does the Erlotinib model generalize to Lung?'];

/** Research assistant: questions answered only from computations on the app's data and named databases, each claim labelled. */
export default function Assistant({projectId}: {projectId: string}) {
  const [text, setText] = useState(''), [log, setLog] = useState<any[]>([]), [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function ask(t = text) { if (!t.trim()) return; setBusy(true); setError(''); try { const r = await rpc<any>('onc_ask', {projectId, text: t}); setLog([{text: t, r}, ...log]); setText(''); } catch (e) { setError(err(e)); } finally { setBusy(false); } }
  return <>
    <div className="page-heading"><div><span className="eyebrow">RESEARCH ASSISTANT · ANSWERS COMPUTED FROM YOUR DATA</span><h1>Ask, and see <em>where the answer comes from.</em></h1>
      <p>Each answer is assembled from analyses run on the installed datasets and named public databases; every claim shows its evidence class and source, and gaps are listed. No language model writes numbers here. The question is matched to one of the supported question types, and the interpretation is shown so you can rephrase.</p></div></div>
    <section className="quiet-panel">
      <div className="onc-row"><input className="field onc-ask" placeholder="e.g. Does MAP2K1 reproduce in another screen in BRAF mutant lines?" value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === 'Enter' && ask()}/>
        <button className="button primary" disabled={busy} onClick={() => ask()}>{busy ? <LoaderCircle size={14} className="spin"/> : <Send size={14}/>}Ask</button></div>
      <div className="onc-row onc-chips">{EXAMPLES.map(x => <button key={x} className="gt-view" onClick={() => ask(x)}>{x}</button>)}</div>
      {error && <p className="caption cs-error">{error}</p>}</section>
    {log.map(({text: t, r}, i) => <section key={i} className="quiet-panel">
      <span className="eyebrow">You asked: {t}</span>
      <p className="caption">Interpreted as “{r.question}” with {Object.entries(r.arguments).map(([k, v]) => `${k} ${v}`).join(', ') || 'no arguments'}.</p>
      <p>{r.answer}</p>
      <ul className="onc-claims">{r.claims.map((c: any, j: number) => <li key={j}><span className="onc-evidence">{c.evidence}</span> {c.text} <small className="onc-sub">{c.source}</small></li>)}</ul>
      {r.gaps.length > 0 && <ul className="tme-checks">{r.gaps.map((g: string) => <li key={g}><TriangleAlert size={13}/><div><span>{g}</span></div></li>)}</ul>}
      <p className="caption">Saved as experiment record {r.recordId?.slice(0, 8)}.</p></section>)}
  </>;
}
