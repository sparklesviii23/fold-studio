"""Cancer dependency statistics on DepMap CRISPR gene effect (Chronos).

Every result is a Statistical association computed from a measured screen's corrected estimates. Design choices:
  * One model per patient by default: DepMap contains several cell lines from the same donor (PatientID); counting them
    separately is pseudoreplication. Collapsing keeps the first ModelID per patient and is reported.
  * Lineage is a confounder for mutation/expression associations (e.g. BRAF mutation ↔ skin lineage), so those are adjusted
    for OncotreeLineage by Frisch–Waugh–Lovell residualisation (equivalent to OLS with lineage fixed effects).
  * Multiple testing: Benjamini–Hochberg across all genes tested; effect sizes and 95 % CIs always accompany p-values.
  * Chronos already corrects copy-number cutting toxicity and guide efficacy; residual biases are noted, not re-corrected.
"""
import math

import numpy as np

EVIDENCE = 'Statistical association (DepMap Chronos gene effect: corrected estimate from a measured CRISPR screen)'


def _bh(p):
    p = np.asarray(p, float); n = np.isfinite(p).sum(); q = np.full_like(p, np.nan)
    idx = np.where(np.isfinite(p))[0]; o = idx[np.argsort(p[idx])]
    ranked = p[o] * n / np.arange(1, n + 1)
    q[o] = np.minimum.accumulate(ranked[::-1])[::-1].clip(max=1)
    return q


def _tp(t, df):
    from scipy.stats import t as T
    return 2 * T.sf(np.abs(t), df)


def _rows(rel, name, dedupe=True):
    M, models, genes, gi, entrez = rel.matrix(name)
    keep, seen, dropped = [], set(), 0
    for i, m in enumerate(models):
        meta = rel.models.get(m, {})
        pid = meta.get('PatientID') or m
        if dedupe and pid in seen:
            dropped += 1; continue
        seen.add(pid); keep.append(i)
    return M, models, genes, gi, keep, dropped


def lineages(rel):
    M, models, *_ = rel.matrix('gene_effect')
    c = {}
    for m in models:
        l = rel.models.get(m, {}).get('OncotreeLineage') or 'Unknown'
        c[l] = c.get(l, 0) + 1
    return sorted(([k, v] for k, v in c.items()), key=lambda x: -x[1])


def gene_profile(rel, gene, dedupe=True):
    M, models, genes, gi, keep, dropped = _rows(rel, 'gene_effect', dedupe)
    if gene not in gi:
        raise ValueError(f'{gene} is not in the DepMap {rel.release} CRISPR screen.')
    v = np.asarray(M[keep, gi[gene]], float); ids = [models[i] for i in keep]
    ok = np.isfinite(v); v = v[ok]; ids = [m for m, o in zip(ids, ok) if o]
    by = {}
    for m, x in zip(ids, v):
        by.setdefault(rel.models.get(m, {}).get('OncotreeLineage') or 'Unknown', []).append(x)
    lin = []
    for l, xs in by.items():
        xs = np.sort(xs)
        lin.append({'lineage': l, 'n': len(xs), 'mean': float(xs.mean()), 'median': float(np.median(xs)), 'q1': float(np.quantile(xs, .25)), 'q3': float(np.quantile(xs, .75)),
                    'min': float(xs[0]), 'max': float(xs[-1]), 'fracDependent': float((xs < -0.5).mean())})
    lin.sort(key=lambda r: r['median'])
    pts = [{'model': m, 'name': rel.models.get(m, {}).get('CellLineName'), 'lineage': rel.models.get(m, {}).get('OncotreeLineage'), 'disease': rel.models.get(m, {}).get('OncotreePrimaryDisease'), 'effect': round(float(x), 4)} for m, x in zip(ids, v)]
    return {'gene': gene, 'release': rel.release, 'n': int(len(v)), 'collapsedSamePatient': dropped, 'mean': float(v.mean()), 'fracDependent': float((v < -0.5).mean()),
            'lineages': lin, 'points': pts, 'threshold': -0.5, 'evidence': EVIDENCE,
            'note': 'Gene effect < −0.5 is a conventional, not absolute, dependency threshold; −1 ≈ median effect of common-essential genes.'}


def lineage_scan(rel, lineage, dedupe=True, top=60):
    """Genes more essential in one lineage than in all others: Welch t-test per gene, BH-FDR, mean difference with 95 % CI."""
    M, models, genes, gi, keep, dropped = _rows(rel, 'gene_effect', dedupe)
    X = np.asarray(M[keep], float); lin = np.array([rel.models.get(models[i], {}).get('OncotreeLineage') == lineage for i in keep])
    if lin.sum() < 5:
        raise ValueError(f'{lineage}: fewer than 5 independent models.')
    A, B = X[lin], X[~lin]
    na, nb = np.isfinite(A).sum(0), np.isfinite(B).sum(0)
    ma, mb = np.nanmean(A, 0), np.nanmean(B, 0); va, vb = np.nanvar(A, 0, ddof=1), np.nanvar(B, 0, ddof=1)
    se = np.sqrt(va / na + vb / nb); d = ma - mb; t = d / se
    df = (va / na + vb / nb) ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    p = _tp(t, df); q = _bh(p)
    from scipy.stats import t as T
    half = T.ppf(0.975, df) * se
    cohen = d / np.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    order = np.argsort(np.where(np.isfinite(t), t, np.inf))[:top]
    hits = [{'gene': genes[j], 'diff': float(d[j]), 'ci': [float(d[j] - half[j]), float(d[j] + half[j])], 'cohenD': float(cohen[j]), 'meanIn': float(ma[j]), 'meanOut': float(mb[j]),
             'p': float(p[j]), 'q': float(q[j])} for j in order]
    vol = [[genes[j], round(float(d[j]), 4), round(float(-math.log10(max(q[j], 1e-300))), 3)] for j in range(len(genes)) if np.isfinite(q[j])]
    return {'lineage': lineage, 'release': rel.release, 'nIn': int(lin.sum()), 'nOut': int((~lin).sum()), 'collapsedSamePatient': dropped, 'tested': int(np.isfinite(p).sum()),
            'significant': int((q < 0.05).sum()), 'hits': hits, 'volcano': vol, 'method': 'Welch t-test per gene, in-lineage vs all other lineages; Benjamini–Hochberg FDR across genes',
            'evidence': EVIDENCE}


def _lineage_design(rel, ids):
    labs = [rel.models.get(m, {}).get('OncotreeLineage') or 'Unknown' for m in ids]
    u = sorted(set(labs)); L = np.zeros((len(ids), len(u)))
    for i, l in enumerate(labs):
        L[i, u.index(l)] = 1
    return L, len(u)


def mutation_scan(rel, mut_gene, kind='hotspot', dedupe=True, top=60, min_mutant=5):
    """Dependencies associated with a mutation, adjusted for lineage (OLS with lineage fixed effects via residualisation)."""
    E, em, genes, gi, keep, dropped = _rows(rel, 'gene_effect', dedupe)
    Mu, mm, mg, mgi, *_ = rel.matrix('mut_' + kind)
    if mut_gene not in mgi:
        raise ValueError(f'{mut_gene} has no {kind} mutation calls in DepMap {rel.release}.')
    mrow = {m: i for i, m in enumerate(mm)}
    rows = [i for i in keep if em[i] in mrow]; ids = [em[i] for i in rows]
    x = np.array([float(Mu[mrow[m], mgi[mut_gene]] > 0) for m in ids])
    if x.sum() < min_mutant:
        raise ValueError(f'Only {int(x.sum())} independent models carry a {kind} {mut_gene} mutation (need ≥ {min_mutant}).')
    Y = np.asarray(E[rows], float)
    L, k = _lineage_design(rel, ids)
    P = L @ np.linalg.pinv(L)                       # projection onto lineage means
    rx = x - P @ x
    Yf = np.where(np.isfinite(Y), Y, np.nanmean(Y, 0))   # rare missing values: column-mean imputed, counted below
    ry = Yf - P @ Yf
    sxx = (rx ** 2).sum(); beta = (rx @ ry) / sxx
    n = len(x); df = n - k - 1
    resid = ry - np.outer(rx, beta); s2 = (resid ** 2).sum(0) / df; se = np.sqrt(s2 / sxx)
    t = beta / se; p = _tp(t, df); q = _bh(p)
    from scipy.stats import t as T
    half = T.ppf(0.975, df) * se
    order = np.argsort(np.where(np.isfinite(t), t, np.inf))[:top]
    hits = [{'gene': genes[j], 'beta': float(beta[j]), 'ci': [float(beta[j] - half[j]), float(beta[j] + half[j])], 'p': float(p[j]), 'q': float(q[j])} for j in order]
    vol = [[genes[j], round(float(beta[j]), 4), round(float(-math.log10(max(q[j], 1e-300))), 3)] for j in range(len(genes)) if np.isfinite(q[j])]
    return {'mutation': mut_gene, 'kind': kind, 'release': rel.release, 'n': n, 'mutant': int(x.sum()), 'lineages': k, 'collapsedSamePatient': dropped,
            'imputedCells': int((~np.isfinite(Y)).sum()), 'hits': hits, 'volcano': vol, 'significant': int((q < 0.05).sum()),
            'method': f'gene effect ~ {kind} {mut_gene} status + lineage fixed effects (OLS); Benjamini–Hochberg FDR across genes', 'evidence': EVIDENCE}


def expression_link(rel, gene, dedupe=True):
    """Partial correlation of a gene's dependency with its own expression, adjusted for lineage."""
    E, em, genes, gi, keep, dropped = _rows(rel, 'gene_effect', dedupe)
    X, xm, xg, xgi, *_ = rel.matrix('expression')
    if gene not in gi or gene not in xgi:
        raise ValueError(f'{gene} needs both CRISPR and expression data.')
    xr = {m: i for i, m in enumerate(xm)}
    ids = [em[i] for i in keep if em[i] in xr and np.isfinite(E[i, gi[gene]])]
    y = np.array([float(E[i, gi[gene]]) for i in keep if em[i] in xr and np.isfinite(E[i, gi[gene]])])
    x = np.array([float(X[xr[m], xgi[gene]]) for m in ids])
    L, k = _lineage_design(rel, ids); P = L @ np.linalg.pinv(L)
    rx, ry = x - P @ x, y - P @ y
    r = float(rx @ ry / math.sqrt((rx @ rx) * (ry @ ry)))
    n = len(x); df = n - k - 1; t = r * math.sqrt(df / max(1e-12, 1 - r * r))
    z = math.atanh(max(-0.999999, min(0.999999, r))); h = 1.96 / math.sqrt(max(1, n - k - 3))
    return {'gene': gene, 'n': n, 'partialR': r, 'ci': [math.tanh(z - h), math.tanh(z + h)], 'p': float(_tp(np.array([t]), df)[0]),
            'points': [[round(a, 3), round(b, 3)] for a, b in zip(x.tolist(), y.tolist())], 'method': 'Partial Pearson correlation of gene effect and log2(TPM+1), lineage-adjusted; Fisher-z CI',
            'evidence': EVIDENCE}


# Positive and negative controls from established biology: if these fail, the data or the method is wrong.
CONTROLS = [
    ('mutation', 'KRAS', 'KRAS', 'Oncogene addiction: KRAS-mutant models depend on KRAS (Behan 2019 Nature; Tsherniak 2017 Cell)'),
    ('mutation', 'BRAF', 'BRAF', 'BRAF-hotspot models depend on BRAF'),
    ('mutation', 'NRAS', 'NRAS', 'NRAS-hotspot models depend on NRAS'),
    ('mutation', 'PIK3CA', 'PIK3CA', 'PIK3CA-hotspot models depend on PIK3CA'),
    ('lineage', 'Skin', 'SOX10', 'Melanoma lineage dependency on SOX10'),
    ('lineage', 'Myeloid', 'SPI1', 'Myeloid lineage dependency on SPI1/PU.1'),
    ('common', None, 'RPL11', 'Ribosomal protein: common-essential (mean effect ≤ −0.8)'),
    ('null', None, 'OR2T4', 'Olfactory receptor not expressed in cell lines: no effect (|mean| < 0.2)'),
]


def controls(rel):
    out = []
    for kind, ctx, gene, why in CONTROLS:
        try:
            if kind == 'mutation':
                r = mutation_scan(rel, ctx, 'hotspot', top=20000)
                rank = next(i for i, h in enumerate(r['hits']) if h['gene'] == gene) + 1
                h = r['hits'][rank - 1]
                out.append({'control': why, 'passed': rank <= 10 and h['q'] < 0.05, 'detail': f'{gene} ranks #{rank} of {r["volcano"].__len__()}; β = {h["beta"]:.2f} (95 % CI {h["ci"][0]:.2f} to {h["ci"][1]:.2f}), q = {h["q"]:.1e}; {r["mutant"]} mutant models'})
            elif kind == 'lineage':
                r = lineage_scan(rel, ctx, top=20000)
                rank = next(i for i, h in enumerate(r['hits']) if h['gene'] == gene) + 1
                h = r['hits'][rank - 1]
                out.append({'control': why, 'passed': rank <= 25 and h['q'] < 0.05, 'detail': f'{gene} ranks #{rank} of {r["tested"]} in {ctx}; Δ = {h["diff"]:.2f}, q = {h["q"]:.1e}; n = {r["nIn"]} vs {r["nOut"]}'})
            else:
                g = gene_profile(rel, gene)
                ok = g['mean'] <= -0.8 if kind == 'common' else abs(g['mean']) < 0.2
                out.append({'control': why, 'passed': ok, 'detail': f'{gene} mean effect {g["mean"]:.2f} across {g["n"]} models'})
        except (ValueError, StopIteration) as e:
            out.append({'control': why, 'passed': None, 'detail': f'not assessable: {e or "gene not tested"}'})
    return out
