"""Clonal populations: what sequencing shows (observed, approximate) kept apart from what a selection model projects (hypothetical).

Observed — relative clonality per tumor from read counts in a cBioPortal cohort. No purity or ploidy estimates are available in
these downloads, so absolute cancer-cell fractions cannot be computed. Within each tumor, only mutations in copy-neutral genes
(GISTIC 0) with ≥ 30 reads are used; the reference is the median of the three highest allele fractions (taken as clonal).
Each mutation's allele fraction relative to it gets a 95 % Wilson interval: clonal-like if the interval reaches ≥ 0.75,
subclonal if it lies below 0.5, otherwise indeterminate. Evidence: Statistical estimate from observed sequencing reads.

Projection — sensitive and resistant clones sharing a carrying capacity, with a drug that kills the sensitive clone between a
start and stop time. Every parameter is the user's assumption. Evidence: Hypothetical (mathematical selection model).
"""
import math

import numpy as np


def _wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 1.0
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def observed(s, study, min_depth=30, min_tumors=10):
    import cancer_genomics as G
    c = G.Cohort(s, study); per, genes, skipped = {}, {}, {'lowDepth': 0, 'copyAltered': 0, 'noCounts': 0}
    for m in c.muts:
        if m['sampleId'] not in c.P or m['mutationType'] not in G.NON_SILENT:
            continue
        alt, ref = m.get('tumorAltCount'), m.get('tumorRefCount')
        if alt is None or ref is None or alt < 0 or ref < 0:
            skipped['noCounts'] += 1; continue
        if alt + ref < min_depth:
            skipped['lowDepth'] += 1; continue
        if c.cna.get((m['sampleId'], m['gene']), 0) != 0:
            skipped['copyAltered'] += 1; continue
        per.setdefault(m['sampleId'], []).append((m['gene'], alt, alt + ref))
    tumors = 0; het = []
    for sm, ms in per.items():
        if len(ms) < 3:
            continue
        tumors += 1; ref = float(np.median(sorted((a / n for _, a, n in ms), reverse=True)[:3]))
        if ref <= 0:
            continue
        sub = 0
        for g, a, n in ms:
            lo, hi = _wilson(a, n); r_lo, r_hi = lo / ref, hi / ref
            cls = 'clonal' if r_hi >= 0.75 else 'subclonal' if r_hi < 0.5 else 'indeterminate'
            genes.setdefault(g, {'clonal': 0, 'subclonal': 0, 'indeterminate': 0, 'rel': []}); genes[g][cls] += 1; genes[g]['rel'].append(a / n / ref); sub += cls == 'subclonal'
        het.append(sub / len(ms))
    rows = []
    for g, v in genes.items():
        n = v['clonal'] + v['subclonal'] + v['indeterminate']
        if n >= min_tumors:
            rows.append({'gene': g, 'tumors': n, 'clonal': v['clonal'] / n, 'subclonal': v['subclonal'] / n, 'indeterminate': v['indeterminate'] / n,
                         'medianRelative': float(np.median(v['rel'])), 'ci': list(_wilson(v['clonal'], n))})
    rows.sort(key=lambda r: -r['clonal'])
    return {'study': study, 'tumors': tumors, 'genes': rows, 'skipped': skipped, 'heterogeneity': {'median': float(np.median(het)) if het else None, 'values': sorted(round(h, 3) for h in het)},
            'method': f'relative allele fraction in copy-neutral genes, depth ≥ {min_depth}; reference = median of a tumor\'s three highest allele fractions; Wilson 95 % interval; clonal-like if it reaches ≥ 0.75 of the reference, subclonal if below 0.5',
            'evidence': 'Statistical estimate from observed sequencing reads (relative clonality; no purity or ploidy correction)',
            'caveat': 'Single-region bulk sequencing cannot distinguish a subclonal mutation from a clonal one in a subclone-rich sample without purity, ploidy and multi-region data; read this as a ranking of genes by how often they look clonal, not as cancer-cell fractions.'}


def projection(r_s=0.03, r_r=0.02, kill=0.06, resistant0=0.01, start=30.0, stop=180.0, t_end=365.0, K=1.0, n0=0.5):
    """Two clones, logistic growth with shared capacity K; drug adds a death rate `kill` (per day) to the sensitive clone only."""
    from scipy.integrate import solve_ivp
    def rhs(t, y):
        S, R = y; on = start <= t <= stop; tot = (S + R) / K
        return [r_s * S * (1 - tot) - (kill * S if on else 0.0), r_r * R * (1 - tot)]
    t = np.linspace(0, t_end, 400); sol = solve_ivp(rhs, (0, t_end), [n0 * (1 - resistant0), n0 * resistant0], t_eval=t, rtol=1e-9, atol=1e-12, max_step=1.0)
    S, R = sol.y; frac = R / np.maximum(S + R, 1e-15)
    dom = next((float(tt) for tt, f in zip(t, frac) if f > 0.5), None)
    return {'time': t.round(2).tolist(), 'sensitive': S.round(6).tolist(), 'resistant': R.round(6).tolist(), 'resistantFraction': frac.round(6).tolist(),
            'timeToResistantMajority': dom, 'burdenAtStop': float(np.interp(stop, t, S + R)), 'burdenAtEnd': float(S[-1] + R[-1]),
            'params': {'growthSensitive': r_s, 'growthResistant': r_r, 'drugKill': kill, 'resistantFraction0': resistant0, 'drugStart': start, 'drugStop': stop, 'capacity': K, 'burden0': n0},
            'evidence': 'Hypothetical (mathematical selection model; every parameter is an assumption)',
            'caveat': 'Two well-mixed clones, no mutation during treatment, no spatial structure, pharmacokinetics or immune effects. A projection of the stated assumptions, not a forecast for a patient.'}
