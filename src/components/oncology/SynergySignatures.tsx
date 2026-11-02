import {useEffect, useMemo, useState} from 'react';
import {Check, Download, LoaderCircle, TriangleAlert} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');
const sci = (v: number) => v == null || !Number.isFinite(v) ? '—' : v < 1e-3 ? v.toExponential(1) : fmt(v, 2);
const molar = (c: number) => c >= 1e-6 ? fmt(c * 1e6, 2) + ' µM' : fmt(c * 1e9, 2) + ' nM';

/** Diverging heatmap: rows = drug A concentration, columns = drug B; red = more effect than the model expects, blue = less. */
function Heat({m, ca, cb, title, diverging}: {m: (number | null)[][]; ca: number[]; cb: number[]; title: string; diverging: boolean}) {
  const col = (v: number | null) => {
    if (v == null || !Number.isFinite(v)) return 'rgba(255,255,255,.04)';
    if (!diverging) return `rgba(255,138,107,${0.1 + 0.85 * Math.max(0, Math.min(1, v))})`;
    const t = Math.max(-1, Math.min(1, v / 0.3)); return t >= 0 ? `rgba(255,107,107,${0.12 + 0.8 * t})` : `rgba(95,157,255,${0.12 + 0.8 * -t})`;
  };
  return <div className="onc-heat"><span>{title}</span>
    <div className="onc-heat-grid" style={{gridTemplateColumns: `64px repeat(${cb.length}, 1fr)`}}>
      <i/>{cb.map(c => <b key={c}>{molar(c)}</b>)}
      {m.map((row, i) => <><b key={'r' + i}>{molar(ca[i])}</b>{row.map((v, j) => <em key={i + '-' + j} style={{background: col(v)}} title={v == null ? 'undefined' : fmt(v * 100, 3) + ' %'}>{v == null || !Number.isFinite(v) ? '·' : fmt(v * 100, 2)}</em>)}</>)}
    </div></div>;
}

export function Synergy({projectId}: {projectId: string}) {
  const [st, setSt] = useState<any>(null), [cell, setCell] = useState('SR'), [a, setA] = useState(0), [b, setB] = useState(0), [res, setRes] = useState<any>(null), [busy, setBusy] = useState(''), [error, setError] = useState('');
  async function read() { try { const r = await rpc<any>('onc_syn_status', {projectId}); setSt(r); if (r.installed && !a) { const n = (q: string) => r.drugs.find((d: any) => d.name.toLowerCase().includes(q))?.nsc ?? r.drugs[0].nsc; setA(n('idarubicin')); setB(n('epiadriamycin')); } } catch (e) { setError(err(e)); } }
  useEffect(() => { void read(); }, []);
  useEffect(() => { if (!st?.job?.running) return; const t = setTimeout(read, 3000); return () => clearTimeout(t); }, [st]);
  async function analyse() { setBusy('Scoring the combination'); setError(''); try { setRes(await rpc('onc_syn_analyse', {projectId, cell, a, b})); } catch (e) { setError(err(e)); } finally { setBusy(''); } }
  return <>
    <div className="page-heading"><div><span className="eyebrow">DRUG-COMBINATION ANALYSIS · NCI ALMANAC</span><h1>Together, <em>relative to what?</em></h1>
      <p>Measured combination matrices from the NCI-60 screen, scored against four reference models. Synergy only exists relative to a model, a cell line and a dose range.</p></div></div>
    {error && <p className="caption cs-error">{error}</p>}{busy && <p className="caption"><LoaderCircle size={12} className="spin"/> {busy}…</p>}
    {st && !st.installed && <section className="quiet-panel"><p>NCI ALMANAC (≈ 86 MB download, 3.7 M wells) is not installed.</p>
      <button className="button primary" disabled={st.job?.running} onClick={async () => { try { setSt(await rpc('onc_syn_install', {projectId})); } catch (e) { setError(err(e)); } }}><Download size={14}/>Install NCI ALMANAC</button>
      {st.job && <pre className="gt-log gt-console onc-log">{st.job.log}</pre>}</section>}
    {st?.installed && <section className="quiet-panel">
      <div className="onc-row">
        <select value={cell} onChange={e => setCell(e.target.value)} aria-label="Cell line">{st.cells.map((c: string) => <option key={c}>{c}</option>)}</select>
        <select value={a} onChange={e => setA(Number(e.target.value))} aria-label="Drug A" className="onc-drug">{st.drugs.map((d: any) => <option key={d.nsc} value={d.nsc}>{d.name}</option>)}</select>
        <span>+</span>
        <select value={b} onChange={e => setB(Number(e.target.value))} aria-label="Drug B" className="onc-drug">{st.drugs.map((d: any) => <option key={d.nsc} value={d.nsc}>{d.name}</option>)}</select>
        <button className="button primary" onClick={analyse}>Score combination</button><span className="onc-evidence">Model-based estimate from experimental screen</span></div>
      <p className="caption">{st.manifest.rows.toLocaleString()} valid wells · {st.cells.length} cell lines · {st.drugs.length} named drugs · {st.pairs.toLocaleString()} screened pairs. {st.manifest.citation}</p>
      {res && <>
        <table className="tme-table"><thead><tr><th>Reference model</th><th>Mean excess (points)</th><th>95 % CI over plates</th><th>Plates</th><th>Call</th></tr></thead>
          <tbody>{Object.entries(res.scores).map(([k, v]: any) => <tr key={k} className={v.call === 'synergy' ? 'best' : ''}><td>{k}</td><td>{fmt(v.mean, 3)}</td><td>{Number.isFinite(v.ci[0]) ? `${fmt(v.ci[0], 2)} to ${fmt(v.ci[1], 2)}` : '—'}</td><td>{v.plates}</td><td>{v.call}</td></tr>)}</tbody></table>
        <ul className="tme-checks">
          <li>{res.nciCheck.maxAbsDiff != null && res.nciCheck.maxAbsDiff < 0.01 ? <Check size={14} className="ok"/> : <TriangleAlert size={14} className="bad"/>}<div><strong>NCI expected growth reproduced</strong><span>{res.nciCheck.wells} wells; max |difference| from the published values {sci(res.nciCheck.maxAbsDiff)} percentage points</span></div></li>
          {res.loeweUndefined > 0 && <li><TriangleAlert size={14}/><div><strong>Loewe undefined in {res.loeweUndefined} wells</strong><span>Additivity would require more effect than one drug reaches alone; not extrapolated.</span></div></li>}
          {res.clippedWells > 0 && <li><TriangleAlert size={14}/><div><strong>{res.clippedWells} wells with net cell kill</strong><span>Percent growth below 0 is clipped to full inhibition for HSA/Bliss/Loewe/ZIP; the NCI ComboScore keeps it.</span></div></li>}
          {res.singleAgentFromSameExperiment > 0 && <li><Check size={14}/><div><strong>Single agents from the same experiment</strong><span>{res.singleAgentFromSameExperiment} plate(s) used single-agent wells from another plate of the same screener and test date.</span></div></li>}
        </ul>
        <div className="onc-heats"><Heat m={res.observed} ca={res.concA} cb={res.concB} title={`Observed inhibition · ${res.a.name} (rows) × ${res.b.name} (columns)`} diverging={false}/>
          {Object.entries(res.surfaces).map(([k, m]: any) => <Heat key={k} m={m} ca={res.concA} cb={res.concB} title={`${k} excess`} diverging/>)}</div>
        <p className="caption">“·” = concentration pair not measured on these plates (ALMANAC spreads its dose grid across plates) or, for Loewe, undefined. {res.method}. {res.units}. Hill fits: {res.a.name} {res.a.hill ? `EC50 ${molar(res.a.hill.ec50M)}, Emax ${fmt(res.a.hill.emax, 2)}` : 'not fitted'} · {res.b.name} {res.b.hill ? `EC50 ${molar(res.b.hill.ec50M)}, Emax ${fmt(res.b.hill.emax, 2)}` : 'not fitted'}. {res.caveat}</p>
      </>}
    </section>}
  </>;
}

const CLASS = ['C>A', 'C>G', 'C>T', 'T>A', 'T>C', 'T>G'], CLASS_COL = ['#5fd4ff', '#2b2f3a', '#ff6b6b', '#c6c9d1', '#7ee0a1', '#f5b6c8'];

export function Signatures({projectId}: {projectId: string}) {
  const [cohorts, setCohorts] = useState<any[]>([]), [study, setStudy] = useState('luad_tcga_pan_can_atlas_2018'), [st, setSt] = useState<any>(null), [res, setRes] = useState<any>(null), [smoke, setSmoke] = useState<any>(null), [busy, setBusy] = useState(''), [error, setError] = useState('');
  async function read() { try { setSt(await rpc('onc_sig_status', {projectId, study})); } catch (e) { setError(err(e)); } }
  useEffect(() => { rpc<any>('onc_cohorts', {projectId}).then(c => setCohorts(c.installed ?? [])).catch(() => {}); }, []);
  useEffect(() => { setRes(null); setSmoke(null); void read(); }, [study]);
  useEffect(() => { if (!st?.job?.running) return; const t = setTimeout(read, 4000); return () => clearTimeout(t); }, [st]);
  async function go(label: string, action: string, set: (v: any) => void) { setBusy(label); setError(''); try { set(await rpc(action, {projectId, study})); } catch (e) { setError(err(e)); } finally { setBusy(''); } }
  const order = useMemo(() => res ? Object.entries(res.samples).sort((x: any, y: any) => (y[1].exposures.find((e: any) => e.signature === 'SBS4')?.fraction ?? 0) - (x[1].exposures.find((e: any) => e.signature === 'SBS4')?.fraction ?? 0)) : [], [res]);
  const palette = useMemo(() => { const m: Record<string, string> = {}; const c = ['#ff8a6b', '#5fd4ff', '#c6a7ff', '#7ee0a1', '#ffd166', '#f5b6c8', '#8fa8ff', '#e8ecf4', '#b0bec5', '#ff6b6b']; res?.signatures.forEach((s: any, i: number) => m[s.signature] = c[i % c.length]); return m; }, [res]);
  const max = res ? Math.max(...res.cohortSpectrum) : 1;
  return <>
    <div className="page-heading"><div><span className="eyebrow">MUTATIONAL SIGNATURES · COSMIC v3.4 SBS · {study}</span><h1>The fingerprints of <em>what mutated them.</em></h1>
      <p>Single-base substitutions in their trinucleotide context, refitted to COSMIC reference signatures with bootstrap uncertainty. An attribution, not an observation of the process itself.</p></div></div>
    {error && <p className="caption cs-error">{error}</p>}{busy && <p className="caption"><LoaderCircle size={12} className="spin"/> {busy}…</p>}
    <section className="quiet-panel"><div className="onc-row">
      <select value={study} onChange={e => setStudy(e.target.value)} aria-label="Study" className="onc-drug">{(cohorts.length ? cohorts : [{study, name: study}]).map((c: any) => <option key={c.study} value={c.study}>{c.name}</option>)}</select>
      {st && !st.built && <button className="button primary" disabled={st.job?.running} onClick={async () => { try { setSt(await rpc('onc_sig_build', {projectId, study})); } catch (e) { setError(err(e)); } }}><Download size={14}/>Build SBS96 catalogue (fetches every SNV's context from Ensembl, ~10–20 min)</button>}
      {st?.built && <button className="button primary" onClick={() => go('Fitting signatures (first run ≈ 1 min)', 'onc_sig_analyse', setRes)}>Fit signatures</button>}
      <span className="onc-evidence">Statistical estimate</span></div>
      {st?.job && (st.job.running || !st.built) && <pre className="gt-log gt-console onc-log">{st.job.log}</pre>}
      {cohorts.length === 0 && <p className="caption">Download a cohort in Patient genomics first.</p>}
    </section>
    {res && <>
      <section className="quiet-panel"><span className="eyebrow">Cohort SBS96 spectrum · {res.catalogue.used.toLocaleString()} SNVs</span>
        <svg viewBox="0 0 960 180" className="onc-spectrum" role="img" aria-label="Cohort SBS96 spectrum">{res.cohortSpectrum.map((v: number, i: number) => <rect key={i} x={i * 10} y={160 - v / max * 150} width={8} height={v / max * 150} fill={CLASS_COL[Math.floor(i / 16)]}/>)}
          {CLASS.map((c, k) => <text key={c} x={k * 160 + 80} y={176} textAnchor="middle">{c}</text>)}</svg>
        <p className="caption">Excluded: {Object.entries(res.catalogue.skipped).map(([k, v]: any) => `${v.toLocaleString()} ${k}`).join(', ')}; {res.catalogue.referenceMismatch} SNVs whose reference base disagreed with {res.catalogue.genome}{res.catalogue.contextUnavailable ? `; ${res.catalogue.contextUnavailable} without context (Ensembl unavailable; rebuild to retry)` : ''}. {res.fitted} samples fitted, {res.tooFew} with fewer than {res.minSnv} SNVs not fitted.</p></section>
      <section className="onc-two">
        <div className="quiet-panel"><span className="eyebrow">Signatures present</span><table className="tme-table"><thead><tr><th>Signature</th><th>COSMIC aetiology</th><th>Samples</th><th>Median share</th></tr></thead>
          <tbody>{res.signatures.slice(0, 12).map((g: any) => <tr key={g.signature}><td><i className="onc-dot" style={{background: palette[g.signature]}}/>{g.signature}</td><td>{g.aetiology}</td><td>{g.samples}</td><td>{fmt(g.medianFraction * 100, 2)} %</td></tr>)}</tbody></table>
          <p className="caption">{res.method}. {res.caveat}</p></div>
        <div className="quiet-panel"><span className="eyebrow">Reference check · tobacco signature vs smoking history</span>
          <div className="onc-row"><button className="button" onClick={() => go('Comparing smokers and never-smokers', 'onc_sig_smoking', setSmoke)}>Run check</button></div>
          {smoke && <ul className="tme-checks"><li>{smoke.passed ? <Check size={14} className="ok"/> : <TriangleAlert size={14} className="bad"/>}<div><strong>{smoke.signature}: smokers {fmt(smoke.smokers.median * 100, 2)} % vs never-smokers {fmt(smoke.never.median * 100, 2)} % (median share)</strong>
            <span>{smoke.smokers.n} smokers ({fmt(smoke.smokers.fracWithSignature * 100, 2)} % carry it) · {smoke.never.n} never-smokers ({fmt(smoke.never.fracWithSignature * 100, 2)} %) · p = {sci(smoke.p)} ({smoke.method}). {smoke.reference}.</span></div></li></ul>}</div>
      </section>
      <section className="quiet-panel"><span className="eyebrow">Per-sample exposures · sorted by SBS4 share</span>
        <div className="onc-stack">{order.map(([sm, r]: any) => <div key={sm} title={`${sm} · ${r.snvs} SNVs · cosine ${fmt(r.cosine, 3)}`}>{r.exposures.map((e: any) => <i key={e.signature} style={{height: e.fraction * 100 + '%', background: palette[e.signature]}}/>)}</div>)}</div>
        <p className="caption">One bar per tumor ({order.length}); hover for SNV count and reconstruction cosine similarity. Bootstrap 95 % intervals are kept in the record.</p></section>
    </>}
  </>;
}
