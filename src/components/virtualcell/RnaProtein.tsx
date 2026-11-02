import {X} from 'lucide-react';
import {fmt} from '../mechanistic/MechCharts';

/** Measured RNA vs measured protein in one context (virtual_cell.state_dispatch 'vcell_rna_protein'): rank agreement only. */
export default function RnaProtein({r, onClose}: {r: any; onClose: () => void}) {
  if (r.supported === false) return <section className="vc-card"><header><div><h3>RNA vs protein</h3></div><button className="vc-icon" title="Close" onClick={onClose}><X size={13}/></button></header><p className="vc-warn">{r.reason}</p></section>;
  return <section className="vc-card">
    <header><div><h3>RNA vs protein · {r.context}</h3><small>RNA: {r.rna}</small></div><button className="vc-icon" title="Close" onClick={onClose}><X size={13}/></button></header>
    <div className="vc-protein-grid">{r.comparisons.map((c: any) => {
      const pts = c.sample ?? [], lx = (v: number) => Math.log10(v + 0.1), xs = pts.map((p: any) => lx(p[0])), ys = pts.map((p: any) => Math.log10(p[1] + 0.01));
      const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
      return <div key={c.dataset}>
        <span className="eyebrow">{c.dataset}</span>
        {c.spearman == null ? <p className="caption">{c.note}</p> : <>
          <p className="vc-evidence"><b>Spearman ρ {fmt(c.spearman, 3)}</b> · n = {c.n.toLocaleString()} proteins with both · p {c.p.toExponential(1)}</p>
          <svg className="vc-scatter" viewBox="0 0 200 140" role="img" aria-label={`RNA vs protein, ${c.dataset}`}>
            <line x1="20" y1="125" x2="195" y2="125"/><line x1="20" y1="5" x2="20" y2="125"/>
            {pts.map((p: any, i: number) => <circle key={i} cx={20 + 175 * (xs[i] - x0) / (x1 - x0 || 1)} cy={125 - 120 * (ys[i] - y0) / (y1 - y0 || 1)} r="1.1"><title>{p[2]}: RNA {fmt(p[0], 3)}, protein {fmt(p[1], 3)} ppm</title></circle>)}
            <text x="108" y="138" textAnchor="middle">log10 RNA (TPM + 0.1)</text><text x="6" y="65" textAnchor="middle" transform="rotate(-90 6 65)">log10 ppm</text></svg>
          <p className="caption">{c.method}; {c.unit}. Shown: {pts.length} of {c.n} points (evenly sampled by gene name). {c.note}</p></>}
      </div>; })}</div>
  </section>;
}
