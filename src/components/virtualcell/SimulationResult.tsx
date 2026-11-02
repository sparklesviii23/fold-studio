import {X} from 'lucide-react';
import {fmt, TimeChart} from '../mechanistic/MechCharts';

/** A saved Cell Physics / RNA lab research record in the shared result shape (virtual_cell_results.py). */
export default function SimulationResult({r, onClose}: {r: any; onClose: () => void}) {
  const series = (r.series ?? []).filter((s: any) => !/\.se$/.test(s.id)).slice(0, 6).map((s: any) => ({id: s.id, label: s.id, values: s.values}));
  const profile = r.profiles?.[0], pmax = profile ? Math.max(...profile.values, 1e-12) : 1;
  const inputs = Object.entries(r.inputs ?? {}).map(([k, v]: any) => [k, v && typeof v === 'object' && 'value' in v ? `${v.value} ${v.unit ?? ''}`.trim() : typeof v === 'object' ? JSON.stringify(v).slice(0, 60) : String(v), v?.provenance?.kind]);
  return <section className="vc-card">
    <header><div><h3>{r.model?.name} · {r.kind?.replace(/_/g, ' ')}</h3><small>{r.lab} · v{r.model?.version} · {r.created} · {r.scale}</small></div>
      <button className="vc-icon" title="Close" onClick={onClose}><X size={13}/></button></header>
    <p className="vc-evidence"><b>{r.evidence?.category} · {r.evidence?.name}</b> · {r.evidence?.statement}</p>
    <p className="vc-warn">{r.context}</p>
    {r.time && series.length > 0 && <div className="vc-chart"><TimeChart time={r.time.values} series={series} timeUnit={r.time.unit} unit={r.lengthUnit ? `${r.lengthUnit}-based, as recorded` : 'as recorded'} xLabel={`time (${r.time.unit})`}/></div>}
    {profile && <><span className="eyebrow">{profile.id} · {profile.values.length} positions</span>
      <svg className="vc-profile" viewBox={`0 0 ${profile.values.length} 40`} preserveAspectRatio="none" role="img" aria-label={profile.id}>
        {profile.values.map((v: number, i: number) => <rect key={i} x={i} y={40 - 40 * v / pmax} width="1" height={40 * v / pmax}/>)}</svg></>}
    <table className="vc-table"><tbody>
      {r.scalars.slice(0, 14).map((s: any) => <tr key={s.id}><td>{s.id}</td><td>{fmt(s.value, 4)}</td></tr>)}
    </tbody></table>
    <span className="eyebrow">Inputs</span>
    <table className="vc-table"><tbody>{inputs.map(([k, v, prov]: any) => <tr key={k}><td>{k}</td><td>{v}</td><td><small>{prov ?? ''}</small></td></tr>)}</tbody></table>
    {r.convergence?.checks && <><span className="eyebrow">Benchmark checks · {r.validation}</span>
      <ul className="vc-checks">{r.convergence.checks.map((c: any) => <li key={c.name} className={c.passed ? 'ok' : 'bad'}>{c.passed ? '✓' : '✗'} {c.name}: {c.detail}</li>)}</ul></>}
    <p className="caption">Method: {r.model?.numericalMethod} Solver: {Object.entries(r.solver ?? {}).filter(([, v]) => typeof v !== 'object').map(([k, v]) => `${k} ${v}`).join(' · ')}</p>
    <p className="caption">Assumptions: {(r.assumptions ?? []).join(' ')} Limitations: {(r.limitations ?? []).join(' ')}</p>
    <p className="caption">Integrity: {r.integrity.match ? 'content SHA-256 re-computed and matches' : 'MISMATCH — the record changed after it was written'} ({r.integrity.recipe.join(', ')}) · {r.reproducibility?.runtime} · seed {r.reproducibility?.seed}</p>
  </section>;
}
