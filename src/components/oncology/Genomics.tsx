import {useEffect, useMemo, useRef, useState} from 'react';
import {Download, LoaderCircle, TriangleAlert} from 'lucide-react';
import {rpc} from '../../lib/api';
import {fmt} from '../mechanistic/MechCharts';

const err = (e: unknown) => String(e).replace(/^Error:\s*/, '');
const sci = (v: number) => v == null || !Number.isFinite(v) ? '—' : v < 1e-3 ? v.toExponential(1) : fmt(v, 2);
const ALT: Record<string, string> = {missense: '#7ee0a1', trunc: '#f2f4f8', inframe: '#c9a26b', amp: '#ff6b6b', del: '#5f9dff'};
const DEFAULT = 'luad_tcga_pan_can_atlas_2018';

/** Oncoprint: genes × samples, each cell coloured by the alteration classes measured in that sample (CNA as background, mutation as bar). */
function Oncoprint({op}: {op: any}) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current; if (!cv) return;
    const dpr = window.devicePixelRatio || 1, W = cv.clientWidth, rowH = 14, H = op.genes.length * rowH + 4; cv.style.height = H + 'px'; cv.width = W * dpr; cv.height = H * dpr;
    const g = cv.getContext('2d')!; g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, W, H);
    const left = 70, cw = (W - left) / op.samples;
    g.font = '11px Inter, system-ui'; g.textAlign = 'right';
    op.genes.forEach((gene: string, i: number) => {
      const y = i * rowH + 2; g.fillStyle = 'rgba(230,236,248,.75)'; g.fillText(gene, left - 8, y + 10);
      g.fillStyle = 'rgba(160,190,255,.08)'; g.fillRect(left, y, W - left, rowH - 3);
      op.grid[i].forEach((kinds: string[], j: number) => {
        if (!kinds.length) return; const x = left + j * cw;
        for (const k of kinds.filter(k => k === 'amp' || k === 'del')) { g.fillStyle = ALT[k]; g.fillRect(x, y, Math.max(cw, 0.8), rowH - 3); }
        const m = kinds.find(k => k !== 'amp' && k !== 'del'); if (m) { g.fillStyle = ALT[m]; g.fillRect(x, y + 3, Math.max(cw, 0.8), rowH - 9); }
      });
    });
  }, [op]);
  return <div><canvas ref={ref} className="onc-oncoprint" aria-label="Oncoprint of the most altered genes"/>
    <div className="tme-legend onc-legend">{Object.entries(ALT).map(([k, c]) => <span key={k}><i style={{background: c}}/>{({missense: 'missense', trunc: 'truncating', inframe: 'in-frame indel', amp: 'amplification', del: 'deep deletion'} as any)[k]}</span>)}</div></div>;
}

function KM({km, gene}: {km: any; gene: string}) {
  const W = 520, H = 280, tmax = Math.max(...km.altered.map((p: number[]) => p[0]), ...km.unaltered.map((p: number[]) => p[0]), 1);
  const X = (t: number) => 44 + t / tmax * (W - 60), Y = (s: number) => H - 34 - s * (H - 50);
  const path = (c: number[][]) => c.map((p, i) => (i ? `H${X(p[0])}V${Y(p[1])}` : `M${X(0)},${Y(1)}`)).join('') + `H${X(tmax)}`;
  return <svg viewBox={`0 0 ${W} ${H}`} className="onc-km" role="img" aria-label={`Kaplan–Meier curves by ${gene} alteration`}>
    {[0, 0.25, 0.5, 0.75, 1].map(v => <g key={v}><line x1={44} x2={W - 16} y1={Y(v)} y2={Y(v)} className="grid"/><text x={38} y={Y(v) + 3} textAnchor="end">{v}</text></g>)}
    <path d={path(km.unaltered)} className="km-u"/><path d={path(km.altered)} className="km-a"/>
    <text x={W / 2} y={H - 8} textAnchor="middle">months</text>
    <g transform={`translate(${W - 190},16)`}><line x1={0} x2={18} y1={0} y2={0} className="km-a"/><text x={24} y={4}>{gene} altered</text><line x1={0} x2={18} y1={16} y2={16} className="km-u"/><text x={24} y={20}>not altered</text></g>
  </svg>;
}

export default function Genomics({projectId}: {projectId: string}) {
  const [studies, setStudies] = useState<any[]>([]), [cohorts, setCohorts] = useState<any>(null), [study, setStudy] = useState(DEFAULT), [sum, setSum] = useState<any>(null);
  const [sort, setSort] = useState<'altered' | 'recurrent'>('recurrent'), [pairs, setPairs] = useState<any>(null), [expr, setExpr] = useState<any>(null), [surv, setSurv] = useState<any>(null);
  const [eg, setEg] = useState('CDKN2A'), [sg, setSg] = useState('STK11'), [ep, setEp] = useState('OS'), [busy, setBusy] = useState(''), [error, setError] = useState('');
  async function go(label: string, action: string, p: any, set: (v: any) => void) { setBusy(label); setError(''); try { set(await rpc(action, {projectId, study, ...p})); } catch (e) { setError(err(e)); } finally { setBusy(''); } }
  async function readCohorts() { const c = await rpc<any>('onc_cohorts', {projectId}).catch(() => null); if (c) setCohorts(c); return c; }
  useEffect(() => { rpc<any[]>('onc_studies', {projectId}).then(setStudies).catch(() => {}); void readCohorts(); }, []);
  useEffect(() => { if (!cohorts?.running) return; const t = setTimeout(readCohorts, 3000); return () => clearTimeout(t); }, [cohorts]);
  const installed = (cohorts?.installed ?? []).some((m: any) => m.study === study);
  useEffect(() => { setSum(null); setPairs(null); setExpr(null); setSurv(null); if (installed) void go('Summarising cohort', 'onc_cohort_summary', {}, setSum); }, [study, installed]);
  const genes = useMemo(() => sum ? [...sum.genes].sort((a: any, b: any) => sort === 'altered' ? b.altered - a.altered : b.recurrent - a.recurrent || b.altered - a.altered) : [], [sum, sort]);
  return <>
    <div className="page-heading"><div><span className="eyebrow">DEMO B · CANCER GENOMICS WORKSPACE · cBioPortal / TCGA PANCANCER ATLAS / NCI GDC</span><h1>What is <em>written in the tumor.</em></h1>
      <p>Measured mutations, copy number and expression for a public patient cohort, with sample identifiers and provenance kept. Cohort-level associations, never individual prognosis.</p></div></div>
    {error && <p className="caption cs-error">{error}</p>}{busy && <p className="caption"><LoaderCircle size={12} className="spin"/> {busy}…</p>}
    <section className="quiet-panel"><div className="onc-row">
      <select value={study} onChange={e => setStudy(e.target.value)} aria-label="Study" className="onc-drug">{(studies.length ? studies : [{id: DEFAULT, name: 'Lung Adenocarcinoma (TCGA, PanCancer Atlas)'}]).map(s => <option key={s.id} value={s.id}>{s.name}{(cohorts?.installed ?? []).some((m: any) => m.study === s.id) ? ' · installed' : ''}</option>)}</select>
      {!installed && <button className="button primary" disabled={cohorts?.running} onClick={async () => { try { setCohorts(await rpc('onc_cohort_install', {projectId, study, gdc: studies.find(x => x.id === study)?.gdc})); } catch (e) { setError(err(e)); } }}><Download size={14}/>{studies.find(x => x.id === study)?.gdc ? 'Download from GDC (mutations and survival)' : 'Download cohort (≈ 100–300 MB)'}</button>}</div>
      {cohorts?.log && (cohorts.running || !installed) && <pre className="gt-log gt-console onc-log">{cohorts.log}</pre>}
      {sum && sum.study.source?.startsWith('NCI GDC') && <p className="caption">{sum.study.name} · {sum.study.citation} · GDC open access, installed {sum.study.installed?.slice(0, 10)} · {sum.profiledSamples} cases with open mutation calls · {sum.study.genes} genes. Not imported: {sum.study.notImported}.</p>}
      {sum && !sum.study.source?.startsWith('NCI GDC') && <p className="caption">{sum.study.name} · {sum.study.citation} · PMID {String(sum.study.pmid).split(',')[0]} · cBioPortal {sum.study.portal}, imported {sum.study.importDate?.slice(0, 10)} · {sum.profiledSamples} samples profiled for mutation and copy number ({sum.patients} patients) · {sum.study.genes} genes ({sum.study.geneSource}).</p>}
      {sum && Object.keys(sum.builds.counts).length > 1 && <p className="caption"><TriangleAlert size={12}/> Reference builds: {Object.entries(sum.builds.counts).map(([b, n]: any) => `${b} (${n})`).join(', ')}. {sum.builds.note}</p>}
    </section>
    {sum && <>
      <section className="quiet-panel"><span className="eyebrow">Oncoprint · {sort === 'recurrent' ? 'driver-enriched (recurrent positions)' : 'most frequently altered'}</span>
        <div className="onc-row"><button className={'gt-view ' + (sort === 'recurrent' ? 'selected' : '')} onClick={() => setSort('recurrent')}>sort by recurrent positions</button><button className={'gt-view ' + (sort === 'altered' ? 'selected' : '')} onClick={() => setSort('altered')}>sort by any alteration</button>
          <span className="onc-evidence">Experimental observation · TCGA</span></div>
        <Oncoprint op={sort === 'altered' ? sum.oncoprint : {...sum.oncoprint, genes: genes.slice(0, 25).map((g: any) => g.gene).filter((g: string) => sum.oncoprint.genes.includes(g)), grid: genes.slice(0, 25).map((g: any) => sum.oncoprint.genes.indexOf(g.gene)).filter((i: number) => i >= 0).map((i: number) => sum.oncoprint.grid[i])}}/>
        <p className="caption">{sum.definitions.altered}. {sum.definitions.passengers}</p></section>
      <section className="onc-two">
        <div className="quiet-panel"><span className="eyebrow">Genes</span><table className="tme-table"><thead><tr><th>Gene</th><th>Altered</th><th>Mutated</th><th>CNA only</th><th>Recurrent pos.</th><th>Counted as</th></tr></thead>
          <tbody>{genes.slice(0, 25).map((g: any) => <tr key={g.gene}><td>{g.gene}</td><td>{fmt(g.freq * 100, 2)} %</td><td>{g.mutated}</td><td>{g.cna}</td><td>{g.recurrent}</td><td>{g.role}</td></tr>)}</tbody></table>
          <p className="caption">{sum.definitions.recurrent}.</p></div>
        <div className="quiet-panel"><span className="eyebrow">Oncogenic pathways</span>
          {sum.pathways.map((p: any) => <div key={p.pathway} className="onc-bar"><span>{p.pathway}</span><i><b style={{width: p.freq * 100 + '%'}}/></i><em>{fmt(p.freq * 100, 2)} %</em></div>)}
          <p className="caption">{sum.definitions.pathways}. Tumor mutational burden (nonsynonymous / Mb): median {fmt(sum.tmb.median, 3)} (IQR {fmt(sum.tmb.q1, 3)}–{fmt(sum.tmb.q3, 3)}), n = {sum.tmb.n}.</p></div>
      </section>
      <section className="quiet-panel"><span className="eyebrow">Co-occurrence and mutual exclusivity</span>
        <div className="onc-row"><button className="button" onClick={() => go('Testing pairs', 'onc_cohort_pairs', {genes: genes.filter((g: any) => g.recurrent >= 3).slice(0, 12).map((g: any) => g.gene)}, setPairs)}>Test the 12 most recurrently mutated genes</button><span className="onc-evidence">Statistical association</span></div>
        {pairs && <><table className="tme-table"><thead><tr><th>Pair</th><th>Tendency</th><th>Both / A only / B only / neither</th><th>log2 OR</th><th>p</th><th>q (BH)</th></tr></thead>
          <tbody>{pairs.pairs.slice(0, 15).map((r: any) => <tr key={r.a + r.b} className={r.q < 0.05 ? 'best' : ''}><td>{r.a} · {r.b}</td><td>{r.tendency}</td><td>{r.both} / {r.aOnly} / {r.bOnly} / {r.neither}</td><td>{fmt(r.log2OR, 2)}</td><td>{sci(r.p)}</td><td>{sci(r.q)}</td></tr>)}</tbody></table>
          <p className="caption">{pairs.method}; {pairs.n} samples. {pairs.caveat}</p></>}</section>
      <section className="onc-two">
        <div className="quiet-panel"><span className="eyebrow">Expression by copy number</span>
          <div className="onc-row"><input value={eg} onChange={e => setEg(e.target.value.toUpperCase())} aria-label="Gene"/><button className="button" onClick={() => go('Comparing', 'onc_cohort_expression', {gene: eg}, setExpr)}>Compare</button></div>
          {expr && <><svg viewBox="0 0 420 200" className="onc-scatter" role="img" aria-label={`${expr.gene} expression by GISTIC level`}>
            {Object.entries(expr.groups).map(([k, v]: any, i, all) => { const lo = -3, hi = 3, Y = (z: number) => 170 - (Math.max(lo, Math.min(hi, z)) - lo) / (hi - lo) * 150, x = 50 + i * (340 / Math.max(1, all.length - 1 || 1));
              return <g key={k}>{v.values.slice(0, 400).map((z: number, j: number) => <circle key={j} cx={x + ((j * 37) % 30) - 15} cy={Y(z)} r={1.6}/>)}<line x1={x - 20} x2={x + 20} y1={Y(v.median)} y2={Y(v.median)} className="med-line"/><text x={x} y={192} textAnchor="middle">GISTIC {k} · {v.n}</text></g>; })}
          </svg><p className="caption">Spearman ρ = {fmt(expr.spearman, 2)}, p = {sci(expr.p)}. {expr.units}. {expr.method}.</p></>}</div>
        <div className="quiet-panel"><span className="eyebrow">Survival by alteration</span>
          <div className="onc-row"><input value={sg} onChange={e => setSg(e.target.value.toUpperCase())} aria-label="Gene"/><select value={ep} onChange={e => setEp(e.target.value)} aria-label="Endpoint">{['OS', 'PFS', 'DSS', 'DFS'].map(x => <option key={x}>{x}</option>)}</select>
            <button className="button" onClick={() => go('Fitting survival', 'onc_cohort_survival', {gene: sg, endpoint: ep}, setSurv)}>Kaplan–Meier + Cox</button></div>
          {surv && <><KM km={surv.km} gene={surv.gene}/>
            <table className="tme-table"><thead><tr><th>Cox term</th><th>HR</th><th>95 % CI</th><th>p</th></tr></thead><tbody>{surv.cox.map((c: any) => <tr key={c.term}><td>{c.term}</td><td>{fmt(c.hr, 3)}</td><td>{fmt(c.ci[0], 3)}–{fmt(c.ci[1], 3)}</td><td>{sci(c.p)}</td></tr>)}</tbody></table>
            <p className="caption">{surv.endpoint}: {surv.patients} patients, {surv.events} events, {surv.altered} altered; log-rank p = {sci(surv.logrank.p)}. {surv.caveat}</p></>}</div>
      </section>
    </>}
  </>;
}
