import {X} from 'lucide-react';
import {fmt, TimeChart} from '../mechanistic/MechCharts';

/** A saved Cell Physics / RNA lab research record in the shared result shape (virtual_cell_results.py). */
export default function SimulationResult({r, onClose, onOpen3D}: {r: any; onClose: () => void; onOpen3D?: (run: string, event?: number, source?: string) => void}) {
  const sp = r.spatial, tl = r.timeline;
  const series = (r.series ?? []).filter((s: any) => !/\.se$/.test(s.id)).slice(0, 6).map((s: any) => ({id: s.id, label: s.id, values: s.values}));
  const profile = r.profiles?.[0], pmax = profile ? Math.max(...profile.values, 1e-12) : 1;
  const inputs = Object.entries(r.inputs ?? {}).map(([k, v]: any) => [k, v && typeof v === 'object' && 'value' in v ? `${v.value} ${v.unit ?? ''}`.trim() : typeof v === 'object' ? JSON.stringify(v).slice(0, 60) : String(v), v?.provenance?.kind]);
  return <section className="vc-card">
    <header><div><h3>{r.model?.name} · {r.kind?.replace(/_/g, ' ')}</h3><small>{r.lab} · v{r.model?.version} · {r.created} · {r.scale}</small></div>
      <div className="vc-row">{sp && onOpen3D && <button onClick={() => onOpen3D(r.id, undefined, r.source)} title="Replay this exact run in the 3-D cell from its saved configuration and seed">Open 3D Run</button>}{tl && onOpen3D && <button onClick={() => onOpen3D(r.id, undefined, r.source)} title="Reopen this experiment in the workspace; it is recomputed from its saved configuration and compared with what was saved">Open Experiment</button>}<button className="vc-icon" title="Close" onClick={onClose}><X size={13}/></button></div></header>
    <p className="vc-evidence"><b>{r.evidence?.category} · {r.evidence?.name}</b> · {r.evidence?.statement}</p>
    <p className="vc-warn">{r.context}</p>
    {r.time && series.length > 0 && <div className="vc-chart"><TimeChart time={r.time.values} series={series} timeUnit={r.time.unit} unit={r.lengthUnit ? `${r.lengthUnit}-based, as recorded` : 'as recorded'} xLabel={`time (${r.time.unit})`}/></div>}
    {profile && <><span className="eyebrow">{profile.id} · {profile.values.length} positions</span>
      <svg className="vc-profile" viewBox={`0 0 ${profile.values.length} 40`} preserveAspectRatio="none" role="img" aria-label={profile.id}>
        {profile.values.map((v: number, i: number) => <rect key={i} x={i} y={40 - 40 * v / pmax} width="1" height={40 * v / pmax}/>)}</svg></>}
    {sp && <>
      <span className="eyebrow">Spatial outcome · {sp.specimen}</span>
      <table className="vc-table"><tbody>
        <tr><td>Complexes formed / separated</td><td>{sp.counts?.pairBinds ?? 0} / {sp.counts?.pairReleases ?? 0}</td></tr>
        <tr><td>Compartment bindings / releases</td><td>{sp.counts?.binds ?? 0} / {sp.counts?.releases ?? 0}</td></tr>
        {sp.structures.map((x: any, i: number) => <tr key={i}><td>{x.name}</td><td>{x.structure ? <>saved structure <code>{x.structure}</code>{x.structureSha256 ? ' · SHA-256 ' + x.structureSha256.slice(0, 12) + '…' : ''}</> : 'size preset (no structure)'}</td></tr>)}
        {sp.experiment?.parent && <tr><td>Branched from</td><td><code>{sp.experiment.parent.slice(0, 8)}</code></td></tr>}
      </tbody></table>
      {sp.events.length > 0 && <><span className="eyebrow">Binding events · {sp.events.length}{sp.eventsTruncated ? ' (first shown)' : ''}{onOpen3D ? ' · click to see one in 3-D' : ''}</span>
        <div className="vc-events">{sp.events.slice(0, 60).map((e: any, i: number) => <button key={i} disabled={!onOpen3D} onClick={() => onOpen3D?.(r.id, i)}>
          <span>{(e.time * 1000).toFixed(2)} ms</span><span>{e.kind}</span><span>{e.species.join(' + ')} · {e.compartment}</span><span>x {e.position[0].toFixed(1)} · y {e.position[1].toFixed(1)} · z {e.position[2].toFixed(1)} µm</span></button>)}</div></>}
      <p className="caption">Readouts this run produces: spatial outcomes only. Expression, fitness, metabolism and signalling are not computed by it; no model links them yet.</p>
    </>}
    {tl && <>
      <span className="eyebrow">What happened · {tl.experiment?.context} · times in {tl.unit}</span>
      <div className="vc-events">{tl.events.map((e: any, i: number) => <button key={i} disabled={!onOpen3D} onClick={() => onOpen3D?.(r.id, undefined, r.source)}><span>{e.time} {tl.unit}</span><span>{e.scale}</span><span>{e.label}</span><span>{fmt(e.value, 4)}</span></button>)}</div>
      {tl.validation && <p className="caption">Validation of the model behind this run: {tl.validation.selected} predictor; pooled error on schedules held out from fitting {(10 ** tl.validation.heldOut[tl.validation.selected]).toFixed(2)}-fold, static baseline {(10 ** tl.validation.heldOut.baseline).toFixed(2)}-fold.</p>}
      {tl.warnings.map((w: string) => <p key={w} className="vc-warn">{w}</p>)}
      {tl.drivers.length > 0 && <p className="caption">What drove the outputs: {tl.drivers.map((d: any) => `${d.output}: ${d.drivenBy.join(', ')}`).join(' · ')}</p>}
    </>}
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
