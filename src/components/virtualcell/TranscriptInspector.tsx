import {fmt} from '../mechanistic/MechCharts';

/** ENCODE Hep G2 transcript isoforms (virtual_cell_transcripts.py): per-replicate RSEM values and GENCODE V29 structure. */
export default function TranscriptInspector({data}: {data: any}) {
  if (!data) return null;
  if (data.supported === false) return <p className="vc-warn">Transcripts: {data.reason}</p>;
  if (!data.transcripts?.length) return <p className="caption">{data.note}</p>;
  const m = data.manifest, span = Math.max(1, data.end - data.start), top = data.transcripts.slice(0, 25);
  const pos = (x: number) => (data.strand === '-' ? data.end - x : x - data.start) / span * 100;
  return <div className="vc-tx">
    <div className="vc-row"><span className="eyebrow">Transcripts · {data.transcripts.length} in GENCODE V29 · {data.chrom}:{data.start.toLocaleString()}–{data.end.toLocaleString()} ({data.strand})</span>
      <a className="text-button" href={m.experimentUrl} target="_blank" rel="noreferrer">ENCODE {m.experiment}</a></div>
    <p className="vc-evidence"><b>A · Experimental</b> · gene total {Object.entries(data.geneTPM.perReplicate).map(([f, v]: any) => `${fmt(v, 4)} TPM (${f})`).join(' · ')} · {data.geneTPM.derivation}</p>
    <table className="vc-table"><thead><tr><th>Transcript</th><th>Structure (5′→3′)</th><th>Rep 1 TPM · %</th><th>Rep 2 TPM · %</th><th>pme_TPM 95 % CI</th></tr></thead>
      <tbody>{top.map((x: any) => <tr key={x.transcript_name ?? x.gene_id}>
        <td title={x.tags.join(', ')}><strong>{x.transcript_name}</strong><br/><small>{x.type.replace(/_/g, ' ')}{x.uniprot ? ` · ${x.uniprot}` : ''}{x.tags.includes('CCDS') ? ' · CCDS' : ''}{x.tags.includes('basic') ? ' · basic' : ''}</small></td>
        <td><svg className="vc-exons" viewBox="0 0 100 10" preserveAspectRatio="none" role="img" aria-label={`${x.exons.length} exons`}>
          <line x1={pos(x.start)} x2={pos(x.end)} y1="5" y2="5"/>
          {x.exons.map(([s, e]: number[], k: number) => { const a = pos(s), b = pos(e); return <rect key={k} x={Math.min(a, b)} width={Math.max(0.4, Math.abs(b - a))} y="2" height="6"/>; })}
          {x.cds.map(([s, e]: number[], k: number) => { const a = pos(s), b = pos(e); return <rect key={'c' + k} className="cds" x={Math.min(a, b)} width={Math.max(0.4, Math.abs(b - a))} y="1" height="8"/>; })}</svg>
          <small>{x.exons.length} exon{x.exons.length === 1 ? '' : 's'}</small></td>
        {[0, 1].map(r => { const v = x.replicates[r]; return <td key={r}>{v ? <>{fmt(v.TPM, 4)} · {fmt(v.IsoPct, 3)} %</> : 'not quantified'}</td>; })}
        <td><small>{x.replicates.map((v: any) => `${fmt(v.TPM_ci_lower_bound, 3)}–${fmt(v.TPM_ci_upper_bound, 3)}`).join(' · ')}</small></td></tr>)}</tbody></table>
    {data.transcripts.length > top.length && <p className="caption">Showing the {top.length} most abundant of {data.transcripts.length} transcripts.</p>}
    <p className="caption">RSEM maximum-likelihood TPM and IsoPct (share of the gene) per biological replicate, as reported by ENCODE ({m.lab}, {m.biosample}; {m.gtf.release}). The credible interval belongs to the posterior-mean TPM, not to TPM. Two replicates only: no error model. Thick boxes: CDS; thin: UTR / non-coding exon.</p>
  </div>;
}
