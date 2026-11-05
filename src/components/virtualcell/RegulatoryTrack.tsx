export type Track = {supported: boolean; reason?: string; run: string; status: string; model: string; checkpointSha256: string;
  sourceRevision: string | null; track: {identifier: string; description: string; scale: string; sum_stat: string};
  reference: {assembly: string; chromosome: string}; coordinateConvention: string; start: number; end: number; bins: number; binSize: number;
  unit: string; preview: {start: number; end: number; min: number; max: number; mean: number}[];
  comparison?: {status: string; region: [string, number, number]; fold: string; spearman: number; scoredBins: number; totalBins: number;
    predictedUnit: string; observedUnit: string; limitations: string[];
    preview: {start: number; end: number; predictedMean: number; observedMean: number | null}[]} | null;
  uncertainty: {supported: boolean; reason: string}; note: string};

export function RegulatoryTrack({track: t}: {track: Track}) {
  if (!t.supported) return <p className="vc-warn">{t.reason}</p>;
  const max = Math.max(1e-12, ...t.preview.map(x => x.max));
  const x = (v: number) => 35 + 730 * (v - t.start) / (t.end - t.start);
  const y = (v: number) => 180 - 145 * v / max;
  return <section>
    <p className="vc-evidence">Predicted genomic track · {t.status}</p>
    <h3>{t.track.description} · {t.track.identifier}</h3>
    <p>{t.reference.assembly} {t.reference.chromosome}:{t.start.toLocaleString()}–{t.end.toLocaleString()} · {t.coordinateConvention} · {t.binSize} bp bins</p>
    <svg viewBox="0 0 800 220" role="img" aria-label="Predicted regulatory coverage envelope">
      <line x1="35" x2="765" y1="180" y2="180" stroke="currentColor"/>
      {t.preview.map((v, i) => <line key={i} x1={x((v.start + v.end) / 2)} x2={x((v.start + v.end) / 2)} y1={y(v.max)} y2={y(v.min)} stroke="#6583e8"><title>{`${v.start}–${v.end}: min ${v.min}, max ${v.max}, mean ${v.mean}`}</title></line>)}
      <polyline fill="none" stroke="#95adff" points={t.preview.map(v => `${x((v.start+v.end)/2)},${y(v.mean)}`).join(' ')}/>
      <text x="35" y="205" fill="currentColor" fontSize="12">{t.start.toLocaleString()}</text><text x="765" y="205" textAnchor="end" fill="currentColor" fontSize="12">{t.end.toLocaleString()}</text>
    </svg>
    <p>{t.unit}. Target transform: {t.track.sum_stat}, scale {t.track.scale}. Full-resolution values remain in the original job CSV; this view shows min/max and mean envelopes.</p>
    <p className="vc-warn">{t.note} Uncertainty: {t.uncertainty.reason}</p>
    {t.comparison && <section aria-label="Observed versus predicted regulatory signal"><h3>Held-out FABP1 locus · {t.comparison.fold}</h3>
      <p>Spearman rank correlation {t.comparison.spearman.toFixed(3)} across {t.comparison.scoredBins} of {t.comparison.totalBins} 32 bp bins with complete reference coverage. {t.comparison.status}.</p>
      {(['predictedMean', 'observedMean'] as const).map(key => {
        const c = t.comparison!; const high = Math.max(1e-12, ...c.preview.map(p => p[key] ?? 0));
        return <figure key={key}><figcaption>{key === 'predictedMean' ? `Predicted · ${c.predictedUnit}` : `Observed · ${c.observedUnit}`}</figcaption>
          <svg viewBox="0 0 800 160" role="img" aria-label={key === 'predictedMean' ? 'Predicted FABP1 signal' : 'Observed ENCODE FABP1 signal'}>
            <line x1="35" x2="765" y1="130" y2="130" stroke="currentColor"/>
            {c.preview.filter(p => p[key] != null).map((p, i) => <circle key={i} cx={35+730*((p.start+p.end)/2-c.region[1])/(c.region[2]-c.region[1])} cy={130-110*p[key]!/high} r="3" fill={key === 'predictedMean' ? '#95adff' : '#7bd7af'}/>)}
            <text x="35" y="150" fill="currentColor" fontSize="12">{c.region[1].toLocaleString()}</text><text x="765" y="150" textAnchor="end" fill="currentColor" fontSize="12">{c.region[2].toLocaleString()}</text>
          </svg></figure>;
      })}
      <p>The two plots use independent vertical scales and different units; line height cannot be compared as abundance.</p>
      {t.comparison.limitations.map(note => <p key={note} className="caption">{note}</p>)}
    </section>}
    <details><summary>Model provenance</summary><p>{t.model} · source {t.sourceRevision ?? 'not reported by this run'}</p><code>{t.checkpointSha256}</code><p>Job {t.run}</p></details>
  </section>;
}

