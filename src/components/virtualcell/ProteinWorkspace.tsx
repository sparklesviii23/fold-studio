import {useEffect, useMemo, useState} from 'react';
import {ExternalLink, LoaderCircle, X} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';
import {KnowledgeGraph, type GraphData} from '../mechanistic/NetworkView';
import TranscriptInspector from './TranscriptInspector';
import '../mechanistic/mechanistic.css';

const LAYER_LABEL: Record<string, string> = {dna: 'Nucleus', mito: 'Mitochondria', er: 'ER', golgi: 'Golgi', vesicles: 'Vesicles'};
const EVIDENCE_LABEL: Record<string, string> = {experimental: 'experimental (ECO:0000269)', inferred: 'inferred', unstated: 'evidence not stated'};

/** Protein → localization, measured expression / fitness in this context, Reactome pathways and structures
 *  (virtual_cell.protein / pathway / pathway_enrichment). The Reactome graph reuses the Mechanistic Lab KnowledgeGraph. */
export default function ProteinWorkspace({protein, cellId, onClose, onError}: {protein: any; cellId: string; onClose: () => void; onError: (e: string) => void}) {
  const [pathway, setPathway] = useState<any>(null), [models, setModels] = useState<any>(null), [busy, setBusy] = useState(''), [tx, setTx] = useState<any>(null);
  useEffect(() => { if (protein.symbol) rpc<any>('vcell_transcripts', {id: cellId, gene: protein.symbol, ensembl: protein.identifiers?.ensembl?.[0]}).then(setTx).catch(e => setTx({supported: false, reason: String(e).replace(/^Error:\s*/, '')})); }, [protein.symbol, cellId]);
  async function call<T>(text: string, action: string, payload: any) {
    setBusy(text);
    try { return await rpc<T>(action, payload); } catch (e) { onError(String(e).replace(/^Error:\s*/, '')); return undefined; } finally { setBusy(''); }
  }
  const graph = useMemo<GraphData | null>(() => {
    const t = protein.mechanisticTarget; if (!t) return null;
    const pid = 'uniprot:' + t.accession;
    const nodes: GraphData['nodes'] = [{id: pid, kind: 'protein', label: protein.symbol, detail: protein.identifiers.uniprot.join(', '), source: 'UniProt'}];
    const edges: GraphData['edges'] = [];
    for (const p of protein.pathways.slice(0, 14)) {
      nodes.push({id: 'reactome:' + p.id, kind: 'pathway', label: p.name, detail: p.topLevel ? `Within ${p.topLevel}` : undefined, url: p.url, source: 'Reactome'});
      edges.push({from: pid, to: 'reactome:' + p.id, relation: 'participates in', evidence: `curated pathway annotation (${p.evidence})`, source: 'Reactome'});
    }
    for (const m of models?.graph.nodes ?? []) if (m.kind === 'model' || m.kind === 'publication') nodes.push(m);
    for (const e of models?.graph.edges ?? []) if (!e.to.startsWith('reactome:')) edges.push(e);
    return {nodes, edges};
  }, [protein, models]);

  if (protein.resolution?.status !== 'resolved') return <section className="vc-card vc-protein">
    <header><div><h3>Protein</h3><small>{protein.resolution?.matchedBy ?? 'No match'}</small></div><button className="vc-icon" title="Close" onClick={onClose}><X size={13}/></button></header>
    <p className="vc-warn">{protein.resolution?.status === 'ambiguous' ? `Ambiguous identifier: it names ${protein.resolution.candidates.join(', ')}. Search one of these symbols.` : `“${protein.resolution?.query}” is not a reviewed human UniProt entry, HGNC symbol, alias or Ensembl gene.`}</p>
  </section>;

  const loc = protein.localization, e = protein.expression, hpa = loc.hpa;
  return <section className="vc-card vc-protein">
    <header><div><h3>{protein.symbol} <span className="vc-chip">{protein.context}</span></h3>
      <small>{protein.identifiers.uniprot.join(', ')} · {protein.identifiers.ensembl.join(', ') || 'no Ensembl gene'} · {protein.identifiers.hgnc ?? 'no HGNC'}{protein.identifiers.length ? ` · ${protein.identifiers.length} aa` : ''} · resolved by {protein.resolution.matchedBy}</small></div>
      <button className="vc-icon" title="Close" onClick={onClose}><X size={13}/></button></header>
    {busy && <div className="vc-busy"><LoaderCircle size={14} className="spin"/>{busy}</div>}

    <div className="vc-protein-grid">
      <div><span className="eyebrow">Expression here</span>
        {e.inPanel ? <p className="vc-evidence"><b>{fmt(e.baseline, 3)}</b> {e.unit} · <b>{protein.expression.evidenceBaseline}</b>{e.change != null && Math.abs(e.change) > 1e-9 ? <> · modelled change {e.change > 0 ? '+' : ''}{fmt(e.change, 3)} ({e.changeEvidence})</> : ''}</p>
          : <p className="vc-warn">Not measured in this context's expression data.</p>}
        {e.depmapBulk && <p className="caption">Parental bulk RNA-seq: {fmt(e.depmapBulk.value, 3)} {e.depmapBulk.unit}</p>}
        {e.baselineSource && <p className="caption">{e.baselineSource}</p>}
        <span className="eyebrow">Knockout fitness</span>
        <p className="vc-evidence">{protein.fitness ? <><b>Chronos {fmt(protein.fitness.chronos, 3)}</b> · {protein.fitness.source}</> : 'Not screened in this context.'}</p>
        <p className="caption">{protein.abundance}</p>
      </div>
      <div><span className="eyebrow">Localization</span>
        {hpa ? <>
          <p className="vc-evidence">HPA · <b>{hpa.reliability}</b>{hpa.drawn ? '' : ' (not drawn: uncertain calls never drive the cell view)'}</p>
          <div className="vc-terms-list">{hpa.terms.map((t: any) => <span key={t.term} className={'vc-term ' + (t.layer && hpa.drawn ? 'on' : '')} title={t.layer ? `Drawn in the ${LAYER_LABEL[t.layer]} layer` : 'No layer in the cell view: listed only'}>{t.term}{t.main ? '' : ' · additional'}</span>)}</div>
          {hpa.cellCycleDependency && <p className="caption">Cell-cycle dependency (HPA): {hpa.cellCycleDependency}</p>}
          <p className="caption">{hpa.scope}</p>
        </> : <p className="caption">No HPA subcellular call.</p>}
        {loc.uniprot.length > 0 && <p className="caption">UniProt: {loc.uniprot.slice(0, 8).map((l: any) => `${l.location}${l.isoform ? ` [${l.isoform}]` : ''} (${EVIDENCE_LABEL[l.evidence]})`).join(' · ')}</p>}
        {loc.humanGem.length > 0 && <p className="caption">Human-GEM: {loc.humanGem.join(', ')}</p>}
        <p className="caption">{loc.note}</p>
      </div>
      <div><span className="eyebrow">Structures</span>
        <p className="vc-evidence">{protein.structures.count ? <>{protein.structures.count} PDB entr{protein.structures.count === 1 ? 'y' : 'ies'}</> : 'No experimental structure cross-referenced.'}</p>
        <div className="vc-terms-list">{protein.structures.pdb.slice(0, 12).map((id: string) => <a key={id} className="vc-term on" href={`https://www.rcsb.org/structure/${id}`} target="_blank" rel="noreferrer">{id}</a>)}</div>
        <p className="caption">{protein.structures.source} A structure is not evidence of a cellular function.</p>
      </div>
    </div>

    <TranscriptInspector data={tx}/>

    <div className="vc-row"><span className="eyebrow">Reactome · {protein.pathways.length} pathway{protein.pathways.length === 1 ? '' : 's'}{protein.manifest.reactomeRelease ? ` · release ${protein.manifest.reactomeRelease}` : ''}</span>
      {protein.mechanisticTarget && !models && <button className="text-button" disabled={!!busy} onClick={async () => { const r = await call<any>('Searching BioModels (downloads and checks each model; about a minute)', 'mech_discover', {target: protein.mechanisticTarget}); if (r) setModels(r); }}>Find published models</button>}</div>
    {graph && protein.pathways.length > 0 && <div className="vc-graph"><KnowledgeGraph graph={graph} onModel={id => window.open(`https://www.ebi.ac.uk/biomodels/${id}`, '_blank')}/></div>}
    {models && <p className="caption">BioModels: {models.models.length} candidate{models.models.length === 1 ? '' : 's'} ranked by annotation evidence; open the Mechanistic Lab to simulate one. {models.notes?.join(' ')}</p>}
    <table className="vc-table"><thead><tr><th>Pathway</th><th>Within</th><th>Evidence</th></tr></thead>
      <tbody>{protein.pathways.map((p: any) => <tr key={p.id} className="vc-click" onClick={async () => { const r = await call<any>('Reading pathway', 'vcell_pathway', {id: cellId, pathway: p.id}); if (r) setPathway(r); }}>
        <td>{p.name}</td><td>{p.topLevel}</td><td className="mono">{p.evidence}</td></tr>)}</tbody></table>
    <p className="caption">{protein.pathwayEvidence}</p>

    {pathway && <div className="vc-pathway">
      <div className="vc-row"><strong>{pathway.name}</strong>
        <a className="text-button" href={pathway.url} target="_blank" rel="noreferrer"><ExternalLink size={12}/>Reactome {pathway.id}</a>
        <button className="vc-icon" title="Close pathway" onClick={() => setPathway(null)}><X size={13}/></button></div>
      <small>{pathway.ancestry.map((a: any) => a.name).join(' › ')} · {pathway.measured} of {pathway.members.length} members measured in {pathway.context}</small>
      <table className="vc-table"><thead><tr><th>Gene</th><th>Expression</th><th>Change</th><th>Layers</th></tr></thead>
        <tbody>{[...pathway.members].sort((a: any, b: any) => (b.baseline ?? -1) - (a.baseline ?? -1)).map((m: any) => <tr key={m.gene}>
          <td>{m.gene}</td><td>{m.inPanel ? fmt(m.baseline, 3) : '—'}</td><td className={(m.change ?? 0) < 0 ? 'down' : 'up'}>{m.change != null && Math.abs(m.change) > 1e-9 ? fmt(m.change, 3) : ''}</td>
          <td>{m.layers.map((l: string) => LAYER_LABEL[l]).join(', ')}</td></tr>)}</tbody></table>
      <p className="caption">{pathway.note} Expression unit: {pathway.members[0]?.unit}.</p>
    </div>}
  </section>;
}

/** Reactome over-representation among this cell's largest modelled changes. */
export function Enrichment({r, onClose}: {r: any; onClose: () => void}) {
  return <section className="vc-card">
    <header><div><h3>Pathway enrichment</h3><small>{r.empty ?? `${r.query} · ${r.queryInUniverse} in a universe of ${r.universe?.toLocaleString()} · ${r.tested} pathways tested`}</small></div>
      <button className="vc-icon" title="Close" onClick={onClose}><X size={13}/></button></header>
    {!r.empty && <>
      <p className="vc-evidence"><b>{r.evidence}</b> · {r.method}</p>
      <table className="vc-table"><thead><tr><th>Pathway</th><th>Hits</th><th>p</th><th>FDR</th></tr></thead>
        <tbody>{r.rows.map((x: any) => <tr key={x.id} title={x.hits.join(', ')}><td>{x.name}</td><td>{x.hits.length} / {x.size}</td><td>{x.p.toExponential(1)}</td><td>{x.fdr.toExponential(1)}</td></tr>)}</tbody></table>
      <p className="caption">{r.note}</p></>}
  </section>;
}
