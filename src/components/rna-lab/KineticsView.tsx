import {useEffect, useState} from 'react';
import {Check, FlaskConical, History, LoaderCircle, TriangleAlert, X} from 'lucide-react';
import {rpc} from '../../lib/api';
import {arcPath, pairsOf} from '../../lib/rnaLab';
import {fmt, SERIES, TimeChart} from '../mechanistic/MechCharts';

/** One basin's representative structure as an arc diagram. */
function Arcs({seq, db, color}: {seq: string; db: string; color: string}) {
  const W = 300, H = 92, M = 10, n = seq.length, x = (k: number) => M + (k + 0.5) * (W - 2 * M) / n, base = H - 22;
  return <svg viewBox={`0 0 ${W} ${H}`} className="rk-arcs" role="img" aria-label={'Structure ' + db}>
    {pairsOf(db).map(([i, j]) => <path key={i + '-' + j} d={arcPath(i, j, x, base, true, (base - 8) / ((W - 2 * M) / 2))} fill="none" stroke={color} strokeWidth="2"/>)}
    {[...seq].map((c, k) => <text key={k} x={x(k)} y={base + 14} className={'rna-base b-' + c}>{c}</text>)}
  </svg>;
}

/** Demo 10: exact folding kinetics on the complete secondary-structure landscape. */
export default function KineticsView() {
  const [run, setRun] = useState<any>(null), [busy, setBusy] = useState(''), [error, setError] = useState('');
  const [seq, setSeq] = useState(''), [temp, setTemp] = useState(37), [runs, setRuns] = useState<any[]>([]);

  async function call<T>(text: string, action: string, payload: any) {
    setBusy(text); setError('');
    try { return await rpc<T>(action, payload); } catch (e) { setError(String(e).replace(/^Error:\s*/, '')); } finally { setBusy(''); }
  }
  async function refresh() { const r = await call<any[]>('', 'rna_kinetics_runs', {}); if (r) setRuns(r); }
  async function execute(sequence = seq, temperature = temp) {
    const r = await call<any>('Enumerating every structure and solving the master equation', 'rna_kinetics_run', {sequence: sequence || null, temperature, seed: 1});
    if (r) { setRun(r); setSeq(r.sequence); refresh(); }
  }
  async function reopen(id: string) { const r = await call<any>('Opening saved run', 'rna_kinetics_record', {id}); if (r) { setRun(r); setSeq(r.sequence); setTemp(r.temperature); } }
  useEffect(() => { void execute('', 37); }, []);

  const logt = run?.times.map((t: number) => Math.log10(t)) ?? [];
  const failed = run?.checks.filter((c: any) => !c.passed) ?? [];
  const ssa = run?.checks.find((c: any) => c.rows);

  return <div className="rk">
    <section className="mech-panel rk-input">
      <label>RNA (8–24 nt)<input className="mono" value={seq} onChange={e => setSeq(e.target.value)} spellCheck={false}/></label>
      <label>Temperature (°C)<input type="number" value={temp} min={0} max={80} onChange={e => setTemp(Number(e.target.value))}/></label>
      <button className="button primary" disabled={!!busy} onClick={() => execute()}><FlaskConical size={14}/>Solve kinetics</button>
    </section>
    {busy && <div className="mech-busy"><LoaderCircle size={16} className="spin"/>{busy}…</div>}
    {error && <div className="mech-error" role="alert"><TriangleAlert size={15}/>{error}</div>}
    {run && <>
      <p className="ms-question">{run.question}</p>
      <section className="ms-identity mech-panel">
        <FlaskConical size={18}/>
        <div><strong>{run.method}</strong><span>{run.landscape.states.toLocaleString()} structures · {run.landscape.moves.toLocaleString()} moves · {run.landscape.minima} local minima · ViennaRNA {run.landscape.viennarna}</span></div>
        <span className={'ms-pill ' + (failed.length ? 'fail' : 'ok')}>{failed.length ? <X size={12}/> : <Check size={12}/>}{run.checks.length - failed.length}/{run.checks.length} checks</span>
        <span className="ms-env">{fmt(run.seconds, 2)} s</span>
      </section>
      <div className="rna-badges"><span className="evidence-badge">{run.evidence.kinetics}</span><span className="rna-note">Energies: {run.evidence.energies}. Time is measured in units of 1/k₀, which is not calibrated.</span></div>

      <section className="mech-panel ms-panel">
        <span className="eyebrow">Population of each folding basin from the open chain</span>
        <TimeChart time={logt} timeUnit="log₁₀ t" xLabel="log₁₀ time (1/k₀)" unit="Probability"
          series={[...run.basins.map((b: any, i: number) => ({id: 'b' + i, label: b.structure, values: b.population})), {id: 'o', label: 'all other states', values: run.other}]}/>
        <p className="caption">Exact solution of the master equation on all {run.landscape.states.toLocaleString()} structures, lumped into steepest-descent basins for display. Slowest relaxation {fmt(run.outputs.slowestRelaxation, 3)}/k₀; mean first passage from the open chain to the MFE {fmt(run.outputs.mfptOpenToMfe, 3)}/k₀.</p>
      </section>

      <section className="rk-basins">
        {run.basins.map((b: any, i: number) => <div key={b.structure} className="mech-panel rk-basin">
          <Arcs seq={run.sequence} db={b.structure} color={SERIES[i]}/>
          <code className="mono">{b.structure}</code>
          <span>{fmt(b.energy, 3)} kcal/mol · {b.states} states</span>
          <span>equilibrium {fmt(b.equilibrium * 100, 3)} % · at t = 10³/k₀ {fmt((run.outputs.kineticPartition[b.structure] ?? 0) * 100, 3)} %</span>
        </div>)}
      </section>

      <section className="ms-grid">
        <div className="mech-panel ms-panel">
          <span className="eyebrow">Exact barriers between basins (lowest saddle on the full landscape)</span>
          <table className="ms-table"><thead><tr><th>From</th><th>To</th><th>Saddle</th><th>Barrier</th></tr></thead><tbody>
            {run.barriers.map((b: any) => <tr key={b.from + b.to}><td className="mono">{b.from}</td><td className="mono">{b.to}</td><td>{fmt(b.saddle, 3)}</td><td>{fmt(b.barrierFrom, 3)} / {fmt(b.barrierTo, 3)}</td></tr>)}
          </tbody></table>
          <p className="caption">kcal/mol; barrier heights measured from each side.</p>
        </div>
        <div className="mech-panel ms-panel">
          <span className="eyebrow">Checks · numerical correctness, not measured kinetics</span>
          {run.checks.map((c: any) => <div key={c.name} className={'mech-check ' + (c.passed ? 'ok' : 'fail')}>{c.passed ? <Check size={14}/> : <X size={14}/>}<div><strong>{c.name}</strong><span>{c.detail}</span></div></div>)}
          {ssa && <p className="caption">Gillespie runs are an independent solver on the same rate matrix, so agreement checks the solution, not the model.</p>}
        </div>
      </section>

      <section className="ms-grid">
        <div className="mech-panel ms-panel">
          <span className="eyebrow">Assumptions and limits</span>
          <ul className="ms-list">{run.assumptions.map((a: string) => <li key={a}>{a}</li>)}{run.limitations.map((a: string) => <li key={a} className="ms-limit">{a}</li>)}</ul>
          <span className="eyebrow">Sources</span>
          <ul className="ms-list">{Object.values(run.references).map((r: any) => <li key={r.doi}>{r.citation} <a href={'https://doi.org/' + r.doi} target="_blank" rel="noreferrer">doi:{r.doi}</a></li>)}</ul>
        </div>
        <div className="mech-panel ms-panel">
          <div className="ms-row"><span className="eyebrow"><History size={12}/> Saved runs</span><span className="caption">SHA-256 {run.sha256.slice(0, 12)}</span></div>
          <div className="ms-runs">{runs.slice(0, 10).map(r => <button key={r.id} className={'ms-run ' + (r.id === run.recordId ? 'active' : '')} onClick={() => reopen(r.id)}>
            <strong className="mono">{r.sequence}</strong><span>{r.created.replace('T', ' ').slice(0, 16)} · {r.temperature} °C · {r.states.toLocaleString()} states · {r.passed ? 'all checks pass' : 'check failed'}</span></button>)}</div>
        </div>
      </section>
    </>}
  </div>;
}
