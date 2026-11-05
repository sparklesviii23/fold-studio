import {useEffect, useState} from 'react';
import {rpc} from '../../lib/api';
import ProteinWorkspace from './ProteinWorkspace';
import {RegulatoryTrack, type Track} from './RegulatoryTrack';
export {RegulatoryTrack} from './RegulatoryTrack';

export default function RegulatoryPanel({cellId, onError, onSaved, onOpenRuns, onOpenStructure}: {cellId: string; onError: (message: string) => void; onSaved?: () => void; onOpenRuns?: () => void; onOpenStructure?: (id: string, name: string, gene: string) => Promise<void>}) {
  const [runs, setRuns] = useState<{run: string; jobState: string; trackIndex: number}[]>([]), [track, setTrack] = useState<Track | null>(null);
  const [saved, setSaved] = useState('');
  const [query, setQuery] = useState('ANGPTL3'), [gene, setGene] = useState('ANGPTL3');
  const [protein, setProtein] = useState<any>(null), [geneError, setGeneError] = useState('');
  useEffect(() => {
    let active = true; setProtein(null); setGeneError('');
    if (gene) rpc('vcell_protein', {id: cellId, query: gene}).then(r => {if (active) setProtein(r);}).catch(e => {if (active) {setGeneError(String(e)); onError(String(e));}});
    return () => {active = false;};
  }, [cellId, gene, onError]);
  useEffect(() => {
    let active = true;
    setTrack(null); setRuns([]); setSaved('');
    rpc<{runs: typeof runs}>('vcell_regulatory_runs', {id: cellId}).then(r => { if (active) setRuns(r.runs); }).catch(e => { if (active) onError(String(e)); });
    return () => { active = false; };
  }, [cellId, onError]);
  async function open(run: string) {
    try { setSaved(''); setTrack(await rpc<Track>('vcell_regulatory_track', {id: cellId, run})); } catch (e) { onError(String(e)); }
  }
  async function save() {
    if (!track?.supported) return;
    try { const r = await rpc<{id: string}>('vcell_snapshot_save', {id: cellId, regulatoryRun: track.run, label: `Borzoi · ${track.track.identifier}`}); setSaved(`Saved prediction snapshot ${r.id.slice(0, 8)}. Cell expression and history are unchanged.`); onSaved?.(); }
    catch (e) { onError(String(e)); }
  }
  return <section aria-label="Genes and genomic regulation">
    <header className="vc-research-heading"><span className="eyebrow">From gene to cell evidence</span><h2>Genes & regulation</h2>
      <p>Explore measured RNA, transcript isoforms, protein evidence and compatible regulatory predictions for this cell. Each result retains its source and evidence category.</p>
    </header>
    <form className="vc-gene-search" onSubmit={e => {e.preventDefault(); if (query.trim()) setGene(query.trim());}}>
      <label>Gene or protein<input value={query} onChange={e => setQuery(e.target.value)} placeholder="e.g. ANGPTL3, ALB, APOA1"/></label>
      <button className="button" type="submit" disabled={!query.trim()}>Explore gene</button>
    </form>
    {geneError && <p className="vc-warn">{geneError}</p>}
    {gene && !protein && !geneError && <p role="status">Gathering compatible gene evidence…</p>}
    {protein && <ProteinWorkspace key={cellId + gene} protein={protein} cellId={cellId} onError={onError} onSaved={onSaved} onClose={() => {setProtein(null); setGene('');}} onOpenStructure={onOpenStructure ? (id, name) => {void onOpenStructure(id, name, gene);} : undefined}/>}
    {onOpenRuns && <button className="text-button" onClick={onOpenRuns}>Open runs & terminal</button>}
    <details className="vc-single-tracks"><summary>Original single-track runs</summary>
    <p>Inspect a saved single-track Borzoi job. Expanded panel profiles appear in gene evidence above; aggregate accuracy is under Benchmarks. Each assay must match this cell line.</p>
    {!runs.length && <p className="caption">No completed single-track result is recorded for this library. This does not describe the availability of expanded panel results.</p>}
    {runs.map(r => <button key={r.run} disabled={r.jobState !== 'done'} onClick={() => open(r.run)}>Track {r.trackIndex} · {r.jobState} · {r.run.slice(0, 8)}</button>)}
    {track && <RegulatoryTrack track={track}/>}
    {track?.supported && <button onClick={save}>Save prediction in state history</button>}
    {saved && <p role="status">{saved}</p>}
    </details>
  </section>;
}
