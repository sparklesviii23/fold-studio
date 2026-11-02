"""Demo D · tumor single-cell analysis. Runs in the isolated single-cell runtime (Scanpy 1.11, AnnData, scikit-learn).

    python singlecell_tumor.py <dataset.h5ad> <out.json> <hallmark.gmt> [cell_type] [condition_column] [case] [control] [site_restrict]

Steps and their evidence category
  QC (per-donor median ± 3 MAD on log counts / log genes; mitochondrial % > 3 MAD)   Experimental observation, filtered
  Normalisation, HVG, PCA, neighbours, UMAP, Leiden (seed 0)                          Computational representation
  Annotation review: Leiden vs author labels (ARI), exploratory Wilcoxon markers       Statistical association (exploratory)
  Donor-level pseudobulk DE (sum of raw counts per donor; log2 CPM; Welch t; BH)        Statistical association (donor = replicate)
  Naive cell-level Wilcoxon on the same contrast                                       shown only to expose pseudoreplication
  Hallmark pathways: competitive rank test of gene t-statistics (MSigDB, CC BY 4.0)    Statistical association
UMAP distances are a visual summary, not physical or causal distances.
"""
import json
import sys
import time

import numpy as np


def mad_flags(x, k=3.0, upper_only=False):
    med = np.median(x); mad = np.median(np.abs(x - med)) * 1.4826 + 1e-9
    return (x > med + k * mad) if upper_only else (np.abs(x - med) > k * mad)


def bh(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p); q = np.empty(n)
    q[o] = np.minimum.accumulate((p[o] * n / np.arange(1, n + 1))[::-1])[::-1].clip(max=1)
    return q


def main(path, out, gmt, cell_type='hair follicular keratinocyte', cond='disease', case='basal cell carcinoma', control='normal', site=None):
    import warnings; warnings.filterwarnings('ignore')
    import anndata as ad, scanpy as sc, scipy.sparse as sp
    from scipy.stats import t as T, mannwhitneyu
    from sklearn.metrics import adjusted_rand_score
    t0 = time.time(); log = lambda m: print(f'[{time.time() - t0:6.1f}s] {m}', flush=True)
    A = ad.read_h5ad(path)
    X = A.raw.X if A.raw is not None else A.X
    a = ad.AnnData(X=sp.csr_matrix(X).astype(np.float32), obs=A.obs.copy(), var=A.raw.var.copy() if A.raw is not None else A.var.copy())
    a.var_names = a.var['feature_name'].astype(str).values if 'feature_name' in a.var else a.var_names
    a.var_names_make_unique()
    if not np.allclose(a.X[:200].data, np.round(a.X[:200].data)):
        raise SystemExit('Expected raw integer counts in .raw.X')
    log(f'loaded {a.n_obs} cells × {a.n_vars} genes (raw counts)')
    # ---- QC, per donor so a donor's depth does not set everyone's thresholds
    a.var['mt'] = a.var_names.str.startswith('MT-')
    sc.pp.calculate_qc_metrics(a, qc_vars=['mt'], inplace=True, percent_top=None, log1p=True)
    keep = np.ones(a.n_obs, bool); qc = []
    for d, idx in a.obs.groupby('donor_id', observed=True).indices.items():
        o = a.obs.iloc[idx]
        bad = mad_flags(o['log1p_total_counts'].values) | mad_flags(o['log1p_n_genes_by_counts'].values) | mad_flags(o['pct_counts_mt'].values, upper_only=True)
        keep[idx[bad]] = False; qc.append({'donor': str(d), 'cells': int(len(idx)), 'removed': int(bad.sum()), cond: str(o[cond].iloc[0])})
    a = a[keep].copy(); log(f'QC kept {a.n_obs} cells')
    counts = a.X.copy()
    # ---- representation
    sc.pp.normalize_total(a, target_sum=1e4); sc.pp.log1p(a)
    a.layers['counts'] = counts
    sc.pp.highly_variable_genes(a, n_top_genes=2000, flavor='seurat', batch_key='donor_id' if a.obs['donor_id'].nunique() > 1 else None)
    sc.pp.pca(a, n_comps=40, mask_var='highly_variable', random_state=0)
    # Donor dominance per cluster: a cluster made of one donor is more likely batch than biology. Measured without and with
    # Harmony (Korsunsky 2019; harmonypy, GPL-3.0, used only inside this separate runtime, not redistributed).
    def cluster(rep, key):
        sc.pp.neighbors(a, n_neighbors=15, random_state=0, use_rep=rep, key_added=key)
        sc.tl.leiden(a, resolution=0.6, random_state=0, flavor='igraph', n_iterations=2, directed=False, neighbors_key=key, key_added='leiden_' + key)
        ct = a.obs.groupby(['leiden_' + key, 'donor_id'], observed=True).size().unstack(fill_value=0); dom = ct.max(1) / ct.sum(1)
        return {'clusters': int(a.obs['leiden_' + key].nunique()), 'median': float(dom.median()), 'clustersOver80pctOneDonor': int((dom > 0.8).sum()),
                'ari': float(adjusted_rand_score(a.obs['cell_type'].astype(str), a.obs['leiden_' + key].astype(str)))}
    before = cluster('X_pca', 'raw')
    import harmonypy
    Z = np.asarray(harmonypy.run_harmony(a.obsm['X_pca'], a.obs, 'donor_id', random_state=0, verbose=False).Z_corr)
    a.obsm['X_pca_harmony'] = Z if Z.shape[0] == a.n_obs else Z.T      # harmonypy 2.x returns cells × dims; 0.0.x returned dims × cells
    after = cluster('X_pca_harmony', 'harmony')
    a.obs['leiden'] = a.obs['leiden_harmony']
    sc.tl.umap(a, random_state=0, neighbors_key='harmony')
    log(f'Leiden: {before["clusters"]} clusters before, {after["clusters"]} after Harmony')
    # ---- annotation review
    ari = after['ari']
    cross = a.obs.groupby(['leiden', 'cell_type'], observed=True).size().unstack(fill_value=0)
    sc.tl.rank_genes_groups(a, 'cell_type', method='wilcoxon', n_genes=8)
    markers = {g: [str(x) for x in a.uns['rank_genes_groups']['names'][g][:8]] for g in a.uns['rank_genes_groups']['names'].dtype.names}
    # ---- donor-level pseudobulk
    def pseudobulk(mask_obs, label):
        sub = a.obs[mask_obs]; rows, meta = [], []
        for d, idx in sub.groupby('donor_id', observed=True).indices.items():
            if len(idx) < 20:
                continue
            cells = np.where(mask_obs)[0][idx]
            rows.append(np.asarray(counts[cells].sum(0)).ravel()); meta.append({'donor': str(d), 'cells': int(len(idx)), 'group': label})
        return rows, meta
    sel_ct = (a.obs['cell_type'] == cell_type).values
    site_ok = np.ones(a.n_obs, bool) if not site else (a.obs['02_group'].astype(str).isin(site.split('|'))).values
    r1, m1 = pseudobulk(sel_ct & (a.obs[cond] == case).values, 'case')
    r0, m0 = pseudobulk(sel_ct & (a.obs[cond] == control).values & site_ok, 'control')
    if len(r1) < 3 or len(r0) < 3:
        raise SystemExit(f'Too few donors with ≥ 20 {cell_type} cells: {len(r1)} case, {len(r0)} control.')
    C = np.vstack(r1 + r0); grp = np.array([1] * len(r1) + [0] * len(r0))
    cpm = C / C.sum(1, keepdims=True) * 1e6
    expressed = ((cpm > 1).sum(0) >= min(len(r1), len(r0)))
    L = np.log2(cpm[:, expressed] + 1); genes = np.array(a.var_names)[expressed]
    A1, A0 = L[grp == 1], L[grp == 0]
    m1_, m0_ = A1.mean(0), A0.mean(0); v1, v0 = A1.var(0, ddof=1), A0.var(0, ddof=1); n1, n0 = len(A1), len(A0)
    se = np.sqrt(v1 / n1 + v0 / n0) + 1e-9; lfc = m1_ - m0_; tt = lfc / se
    df = (v1 / n1 + v0 / n0) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v0 / n0) ** 2 / (n0 - 1) + 1e-12)
    p = 2 * T.sf(np.abs(tt), df); q = bh(p); half = T.ppf(0.975, df) * se
    # Sensitivity analysis added after seeing the Welch result (n = 5 vs 7 donors gives Welch little power): limma-style
    # empirical-Bayes moderated t (Smyth 2004), pooled variance shrunk towards a prior fitted across genes.
    from scipy.special import digamma, polygamma
    dg = n1 + n0 - 2; s2 = ((n1 - 1) * v1 + (n0 - 1) * v0) / dg + 1e-12
    z = np.log(s2) - digamma(dg / 2) + np.log(dg / 2); ev = np.var(z, ddof=1) - polygamma(1, dg / 2)
    if ev > 0:
        lo_, hi_ = 1e-3, 1e4                                  # solve trigamma(d0/2) = ev for d0
        for _ in range(200):
            mid = (lo_ * hi_) ** 0.5; lo_, hi_ = (mid, hi_) if polygamma(1, mid / 2) > ev else (lo_, mid)
        d0 = mid; s0 = np.exp(np.mean(z) + digamma(d0 / 2) - np.log(d0 / 2))
    else:
        d0, s0 = np.inf, np.exp(np.mean(z))
    s2p = s2 if not np.isfinite(d0) else (d0 * s0 + dg * s2) / (d0 + dg)
    s2p = s0 * np.ones_like(s2) if not np.isfinite(d0) else s2p
    tm = lfc / np.sqrt(s2p * (1 / n1 + 1 / n0)); dfm = dg + (d0 if np.isfinite(d0) else 1e6)
    pm = 2 * T.sf(np.abs(tm), dfm); qm = bh(pm)
    order = np.argsort(p)
    de = [{'gene': str(genes[j]), 'log2FC': float(lfc[j]), 'ci': [float(lfc[j] - half[j]), float(lfc[j] + half[j])], 'p': float(p[j]), 'q': float(q[j]), 'qModerated': float(qm[j])} for j in order[:80]]
    volcano = [[str(genes[j]), round(float(lfc[j]), 3), round(float(-np.log10(max(q[j], 1e-300))), 3), round(float(-np.log10(max(qm[j], 1e-300))), 3)] for j in range(len(genes))]   # 4th: moderated
    # ---- naive cell-level comparison (pseudoreplication), same genes and cells
    cmask1 = sel_ct & (a.obs[cond] == case).values; cmask0 = sel_ct & (a.obs[cond] == control).values & site_ok
    Xn = a[:, genes].X
    naive_sig = 0; naive_p = []
    for j in range(len(genes)):
        x1 = Xn[cmask1, j].toarray().ravel(); x0 = Xn[cmask0, j].toarray().ravel()
        naive_p.append(mannwhitneyu(x1, x0).pvalue if x1.std() + x0.std() > 0 else 1.0)
    naive_q = bh(naive_p); naive_sig = int((naive_q < 0.05).sum())
    # ---- Hallmark pathways: competitive Wilcoxon of gene t-statistics inside vs outside each set
    sets = {}
    for line in open(gmt):
        f = line.rstrip('\n').split('\t'); sets[f[0]] = set(f[2:])
    gi = {g: i for i, g in enumerate(genes)}; pw = []
    for name, members in sets.items():
        idx = [gi[g] for g in members if g in gi]
        if len(idx) < 10:
            continue
        inside = np.zeros(len(genes), bool); inside[idx] = True
        pv = mannwhitneyu(tt[inside], tt[~inside]).pvalue
        pw.append({'set': name, 'genes': len(idx), 'meanT': float(tt[inside].mean()), 'direction': 'up in case' if np.median(tt[inside]) > np.median(tt[~inside]) else 'down in case', 'p': float(pv)})
    for r, v in zip(pw, bh([r['p'] for r in pw])):
        r['q'] = float(v)
    pw.sort(key=lambda r: r['p'])
    # ---- embedding for display (subsample, seeded)
    rng = np.random.default_rng(0); show = np.sort(rng.choice(a.n_obs, min(a.n_obs, 6000), replace=False))
    U = a.obsm['X_umap'][show]
    emb = {'x': np.round(U[:, 0], 3).tolist(), 'y': np.round(U[:, 1], 3).tolist(), 'leiden': a.obs['leiden'].astype(str).values[show].tolist(),
           'cellType': a.obs['cell_type'].astype(str).values[show].tolist(), 'condition': a.obs[cond].astype(str).values[show].tolist(), 'donor': a.obs['donor_id'].astype(str).values[show].tolist()}
    hh = next((r for r in pw if r['set'] == 'HALLMARK_HEDGEHOG_SIGNALING'), None)
    for g in ('GLI1', 'PTCH1', 'HHIP', 'KRT14', 'KRT10', 'MKI67'):
        if g in a.var_names:
            emb['expr_' + g] = np.round(np.asarray(a[show, g].X.todense()).ravel(), 2).tolist()
    controls = []
    for g in ('GLI1', 'PTCH1', 'HHIP'):
        if g in gi:
            j = gi[g]; ok = lfc[j] > 1 and q[j] < 0.05
            controls.append({'gene': g, 'log2FC': float(lfc[j]), 'ci': [float(lfc[j] - half[j]), float(lfc[j] + half[j])], 'q': float(q[j]), 'passed': bool(ok),
                             'qModerated': float(qm[j]), 'passedModerated': bool(lfc[j] > 1 and qm[j] < 0.05)})
    res = {'cells': {'loaded': int(A.n_obs), 'afterQC': int(a.n_obs)}, 'qc': qc, 'qcMethod': 'per donor: |log counts| or |log genes| > 3 MAD, or mitochondrial % > median + 3 MAD',
           'clusters': after['clusters'], 'batch': {'beforeHarmony': before, 'afterHarmony': after, 'note': 'Donor dominance = largest single-donor share of a cluster; ARI = agreement with author cell types.'},
           'annotation': {'ari': float(ari), 'crosstab': {str(k): {str(c): int(v) for c, v in row.items()} for k, row in cross.iterrows()}, 'markers': markers,
                          'note': 'Markers are exploratory (cell-level Wilcoxon); author labels are reviewed, not replaced.'},
           'contrast': {'cellType': cell_type, 'case': case, 'control': control, 'siteRestriction': site, 'caseDonors': m1, 'controlDonors': m0, 'genesTested': int(len(genes))},
           'de': de, 'volcano': volcano, 'significantDonorLevel': int((q < 0.05).sum()), 'significantModerated': int((qm < 0.05).sum()), 'moderation': {'priorDf': float(d0) if np.isfinite(d0) else None, 'priorVar': float(s0)}, 'significantNaiveCellLevel': naive_sig,
           'pathways': pw[:25], 'hedgehog': hh, 'controls': controls, 'embedding': emb,
           'methods': {'pseudobulk': 'sum of raw counts per donor (≥ 20 cells); genes with CPM > 1 in at least the smaller group size; log2(CPM+1); Welch t; Benjamini–Hochberg (primary, pre-specified)',
                       'moderated': 'limma-style empirical-Bayes moderated t on pooled variance (Smyth 2004) — sensitivity analysis added after seeing the underpowered Welch result',
                       'pathways': 'MSigDB Hallmark v2025.1 (CC BY 4.0); competitive Mann–Whitney of per-gene t-statistics; BH',
                       'embedding': 'normalize_total 1e4, log1p, 2000 HVG (seurat dispersion on log data, batch=donor), PCA 40, kNN 15, UMAP, Leiden 0.6, seed 0'},
           'software': {'scanpy': sc.__version__, 'anndata': ad.__version__, 'numpy': np.__version__}, 'seconds': round(time.time() - t0, 1)}
    json.dump(res, open(out, 'w')); log('done')


if __name__ == '__main__':
    main(*sys.argv[1:])
