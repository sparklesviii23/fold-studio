"""Demo E · spatial tumor explorer on measured 10x Visium data. Runs in the isolated single-cell runtime.

    python spatial_tumor.py <dataset.h5ad> <out.json> [permutations]

Everything here uses measured spot coordinates of one 2D section; nothing is reconstructed in 3D.
Evidence per layer
  H&E image, spot positions, gene counts                 Experimental observation
  pathologist_annotation                                  Expert annotation (observation by a pathologist)
  stereoscope proportions                                 AI prediction (deconvolution against a single-cell reference)
  neighbourhood enrichment, Moran's I, interface profiles Statistical association
Visium geometry: spots 55 µm wide on a hexagonal grid, 100 µm centre to centre; neighbours = the six adjacent spots.
"""
import base64
import io
import json
import re
import sys
import time

import numpy as np


def bh(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p); q = np.empty(n)
    q[o] = np.minimum.accumulate((p[o] * n / np.arange(1, n + 1))[::-1])[::-1].clip(max=1)
    return q


def hex_neighbours(row, col):
    """Visium array coordinates: neighbours are (±0, ±2) and (±1, ±1)."""
    idx = {(r, c): i for i, (r, c) in enumerate(zip(row, col))}
    nb = [[idx[(r + dr, c + dc)] for dr, dc in ((0, 2), (0, -2), (1, 1), (1, -1), (-1, 1), (-1, -1)) if (r + dr, c + dc) in idx] for r, c in zip(row, col)]
    return nb


def morans_i(x, nb):
    """Moran's I with binary adjacency weights."""
    z = x - x.mean(); W = sum(len(n) for n in nb)
    num = sum(z[i] * z[n].sum() for i, n in enumerate(nb) if n)
    return float(len(x) / W * num / (z @ z + 1e-12))


def morans_matrix(Z, nb):
    """Moran's I for every column of a standardised matrix at once (sparse neighbour sum)."""
    import scipy.sparse as sp
    rows = [i for i, n in enumerate(nb) for _ in n]; cols = [j for n in nb for j in n]
    A = sp.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(nb), len(nb)))
    Zc = Z - Z.mean(0)
    return len(nb) / A.sum() * np.einsum('ij,ij->j', Zc, A @ Zc) / (np.einsum('ij,ij->j', Zc, Zc) + 1e-12)


def neighbourhood_enrichment(labels, nb, perms, rng):
    cats = sorted(set(labels)); k = len(cats); lab = np.array([cats.index(l) for l in labels])
    pairs = np.array([(i, j) for i, n in enumerate(nb) for j in n])
    def count(l):
        M = np.zeros((k, k)); np.add.at(M, (l[pairs[:, 0]], l[pairs[:, 1]]), 1); return M
    obs = count(lab); null = np.array([count(rng.permutation(lab)) for _ in range(perms)])
    z = (obs - null.mean(0)) / (null.std(0) + 1e-9)
    return cats, z, obs


STANDARD = {'assay', 'disease', 'sex', 'tissue', 'donor_id', 'development_stage', 'self_reported_ethnicity', 'suspension_type', 'is_primary_data', 'tissue_type',
            'observation_joinid', 'replicate', 'in_tissue', 'array_row', 'array_col', 'organism'}
TUMOR = re.compile(r'tumou?r|malignan|cancer|carcinoma|neoplas', re.I)
NOT_TUMOR = re.compile(r'stroma|adjacent|normal|non.?tumou?r|border|margin|immune|necro|benign', re.I)
is_tumor = lambda x: bool(TUMOR.search(x)) and not NOT_TUMOR.search(x)
TCELL = re.compile(r'(^|[_ ])T([_ -]?cells?)?$|CD8|T-cells', re.I)
QC = re.compile(r'count|n_genes|pct|mt$|_orig$|^x$|^y$|leiden|size_factor', re.I)


def annotation_layers(obs):
    """Author-deposited categorical columns per spot (2–40 levels), ordered by how directly they come from an expert."""
    out = {}
    for c in obs.columns:
        if c in STANDARD or c.endswith('ontology_term_id') or not (str(obs[c].dtype) in ('category', 'object')):
            continue
        v = obs[c].astype(object).where(obs[c].notna(), 'unannotated').astype(str)
        if 2 <= v.nunique() <= 40:
            out[c] = v.values
    rank = lambda c: (0 if 'patholog' in c.lower() or 'truth' in c.lower() else 1 if c == 'cell_type' else 2)
    return dict(sorted(out.items(), key=lambda kv: rank(kv[0])))


def score_layers(obs):
    """Author-deposited numeric per-spot scores (typically deconvolution fractions or abundances)."""
    out = {}
    for c in obs.columns:
        if c in STANDARD or QC.search(c) or str(obs[c].dtype) not in ('float32', 'float64'):
            continue
        v = obs[c].astype(float).values
        if np.isfinite(v).all() and v.std() > 0:
            out[c] = v
    return dict(list(out.items())[:48])


def main(path, out, perms='500'):
    import warnings; warnings.filterwarnings('ignore')
    import anndata as ad, scipy.sparse as sp
    from scipy.spatial import cKDTree
    from scipy.stats import spearmanr, mannwhitneyu, rankdata
    import matplotlib.image as mpimg
    t0 = time.time(); perms = int(perms); rng = np.random.default_rng(0)
    a = ad.read_h5ad(path)
    a = a[a.obs['in_tissue'].astype(int) == 1].copy() if 'in_tissue' in a.obs else a
    X = sp.csr_matrix(a.X); genes = np.array(a.var['feature_name'].astype(str) if 'feature_name' in a.var else a.var_names)
    if not np.allclose(X[:200].data, np.round(X[:200].data)):
        if a.raw is not None:
            X = sp.csr_matrix(a.raw.X); genes = np.array(a.raw.var['feature_name'].astype(str) if 'feature_name' in a.raw.var else a.raw.var_names)
        if not np.allclose(X[:200].data, np.round(X[:200].data)):
            raise SystemExit('Expected raw counts in X or raw.X.')
    lib = np.asarray(X.sum(1)).ravel(); keep = lib > 0; a, X, lib = a[keep].copy(), X[keep], lib[keep]
    L = sp.diags(1e4 / lib) @ X; L.data = np.log1p(L.data)          # log-normalised expression
    gene = lambda g: np.asarray(L[:, int(np.where(genes == g)[0][0])].todense()).ravel()
    xy = np.asarray(a.obsm['spatial'], float)[:, :2]                  # measured positions as deposited
    visium = 'array_row' in a.obs and 'array_col' in a.obs
    if visium:
        nb = hex_neighbours(a.obs['array_row'].astype(int).values, a.obs['array_col'].astype(int).values); graph = 'six adjacent Visium spots (hexagonal array)'
    else:
        nb = [list(r[1:]) for r in cKDTree(xy).query(xy, k=7)[1]]; graph = 'six nearest beads (k-nearest neighbours on measured positions)'
    keys = [k for k in a.uns.get('spatial', {}) if k != 'is_single']; S = a.uns['spatial'][keys[0]] if keys else None
    image, scale, um_per_px, spot_r = None, 1.0, None, None
    if S is not None and 'images' in S and 'hires' in S['images']:
        sf = S['scalefactors']; full = np.asarray(S['images']['hires']); half = full.shape[0] > 1200; img = full[::2, ::2] if half else full
        scale = sf['tissue_hires_scalef'] * (0.5 if half else 1.0); um_per_px = 55.0 / sf['spot_diameter_fullres'] / scale; spot_r = sf['spot_diameter_fullres'] * scale / 2
        buf = io.BytesIO(); mpimg.imsave(buf, np.clip(img, 0, 1) if img.dtype.kind == 'f' else img, format='png')
        image = {'png': base64.b64encode(buf.getvalue()).decode(), 'width': int(img.shape[1]), 'height': int(img.shape[0])}
    pos = xy * scale
    if image is None:                                                  # no image deposited: frame the measured positions
        lo = pos.min(0) - 20; pos = pos - lo; image = {'png': None, 'width': float(pos[:, 0].max() + 20), 'height': float(pos[:, 1].max() + 20)}
        spot_r = float(np.median(cKDTree(pos).query(pos, k=2)[0][:, 1]) / 2)
    # ---- annotations: everything the authors deposited, plus expression clusters computed here
    ann = annotation_layers(a.obs)
    import scanpy as sc
    b = ad.AnnData(sp.csr_matrix(L)); sc.pp.highly_variable_genes(b, n_top_genes=2000, flavor='seurat'); sc.pp.pca(b, n_comps=30, mask_var='highly_variable', random_state=0)
    sc.pp.neighbors(b, random_state=0); sc.tl.leiden(b, resolution=0.6, flavor='igraph', n_iterations=2, random_state=0)
    ann['expression clusters (computed)'] = np.array(['cluster ' + v for v in b.obs['leiden'].astype(str)])
    primary = next(iter(ann))
    scores = score_layers(a.obs)
    # ---- spatial autocorrelation; the gene count and null size shrink for large bead arrays to stay tractable
    ng, nperm = (2000, 200) if a.n_obs <= 10000 else (800, 100)
    mean = np.asarray(L.mean(0)).ravel(); var = np.asarray(L.multiply(L).mean(0)).ravel() - mean ** 2
    expressed = (np.asarray((X > 0).sum(0)).ravel() >= 0.05 * a.n_obs)
    cand = np.where(expressed)[0][np.argsort(-var[expressed])[:ng]]
    Z = L[:, cand].toarray(); I = morans_matrix(Z, nb)
    null = np.array([morans_matrix(Z[rng.permutation(len(Z))], nb) for _ in range(nperm)])
    # p from the permutation null's moments (normal approximation) so q-values are not floored at 1/(permutations + 1)
    from scipy.stats import norm
    p = norm.sf((I - null.mean(0)) / (null.std(0) + 1e-12)); q = bh(p); order = np.argsort(-I)
    TECHNICAL = {'MALAT1', 'NEAT1'} | {g for g in genes[cand] if str(g).startswith(('MT-', 'RPL', 'RPS'))}
    moran = [{'gene': str(genes[cand[j]]), 'I': float(I[j]), 'p': float(p[j]), 'q': float(q[j]), 'technical': str(genes[cand[j]]) in TECHNICAL} for j in order[:40]]
    shuffled_I = float(np.median(morans_matrix(Z[rng.permutation(len(Z))], nb)))
    # ---- neighbourhood enrichment of the primary annotation
    cats, zz, obs = neighbourhood_enrichment(list(ann[primary]), nb, perms, rng)
    ne = {'annotation': primary, 'labels': cats, 'z': np.round(zz, 2).tolist(), 'counts': obs.astype(int).tolist(), 'permutations': perms,
          'method': 'observed adjacent label pairs vs label-permutation null; z-score per pair'}
    # ---- tumor–immune interface: needs a tumor label in some annotation and a position scale
    tum_key = next((k for k, v in ann.items() if 'computed' not in k and any(is_tumor(x) for x in set(v))), None)
    interface, agree = None, []
    synthetic = json.loads(a.uns['synthetic_truth']) if 'synthetic_truth' in a.uns else None
    # On a synthetic section the deposited fractions are the planted truth, so the readout must be measured expression instead.
    tcell_key = None if synthetic else next((k for k in scores if TCELL.search(k)), None)
    if tum_key is not None:
        tum = np.array([is_tumor(x) for x in ann[tum_key]])
        if um_per_px is not None:
            dist = cKDTree(pos[tum]).query(pos)[0] * um_per_px; dist[tum] = 0.0
            bins = [0, 1, 150, 300, 500, 800, 1500, 1e9]; lab = ['inside tumor', '≤150 µm', '150–300', '300–500', '500–800', '800–1500', '>1500']
            prof = {}
            for k in [k for k in scores if TCELL.search(k) or re.search(r'B.?cell|myeloid|macroph|CAF|fibro', k, re.I)][:6]:
                prof[k] = [float(scores[k][(dist >= lo) & (dist < hi)].mean()) if ((dist >= lo) & (dist < hi)).any() else None for lo, hi in zip(bins[:-1], bins[1:])]
            for g in ('CD8A', 'PTPRC', 'CD3E'):
                if g in genes:
                    v = gene(g); prof['expr ' + g] = [float(v[(dist >= lo) & (dist < hi)].mean()) if ((dist >= lo) & (dist < hi)).any() else None for lo, hi in zip(bins[:-1], bins[1:])]
            tc = scores[tcell_key] if tcell_key else (gene('CD8A') if 'CD8A' in genes else None)
            exclusion = None
            if tc is not None and ((dist > 0) & (dist <= 300)).sum() >= 10:
                inside, rim = tc[tum], tc[(dist > 0) & (dist <= 300)]
                exclusion = {'readout': tcell_key or 'CD8A expression', 'insideMean': float(inside.mean()), 'rimMean': float(rim.mean()), 'ratio': float(inside.mean() / (rim.mean() + 1e-12)),
                             'p': float(mannwhitneyu(inside, rim).pvalue), 'method': 'T-cell readout inside tumor spots vs non-tumor spots within 300 µm; Mann–Whitney'}
            interface = {'annotation': tum_key, 'bins': lab, 'profiles': prof, 'spots': [int(((dist >= lo) & (dist < hi)).sum()) for lo, hi in zip(bins[:-1], bins[1:])], 'exclusion': exclusion,
                         'spearmanTcellDistance': (lambda r: {'rho': float(r[0]), 'p': float(r[1])})(spearmanr(dist[~tum], tc[~tum])) if tc is not None else None}
        def auc(score):
            r = rankdata(score); n1, n0 = tum.sum(), (~tum).sum(); return float((r[tum].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))
        if 0 < tum.sum() < len(tum):
            for k in ([] if synthetic else [k for k in scores if re.search(r'cancer|malignan|tumou?r', k, re.I)][:3]):
                agree.append({'check': f'Author score "{k}" ranks annotated tumor spots first', 'auc': auc(scores[k])})
            dz = ' '.join(map(str, set(a.obs['disease'].astype(str)))).lower() if 'disease' in a.obs else ''
            panel = ('PMEL', 'MLANA') if 'melanoma' in dz else ('CA9', 'NDUFA4L2') if 'renal' in dz else ('EPCAM', 'KRT8', 'KRT18')   # tumor-cell markers by disease
            for g in panel:
                if g in genes and (X[:, int(np.where(genes == g)[0][0])].nnz >= 0.02 * a.n_obs):
                    agree.append({'check': f'{g} expression ranks annotated tumor spots first', 'auc': auc(gene(g))})
            for r in agree:
                r['passed'] = r['auc'] > 0.8
    expr = {}
    for g in ('EPCAM', 'KRT8', 'PTPRC', 'CD8A', 'CD3E', 'MS4A1', 'COL1A1', 'CD68', 'MKI67', 'CA9', 'PMEL', 'ESR1', 'ERBB2'):
        if g in genes:
            expr[g] = np.round(gene(g), 2).tolist()
    for m in moran[:6]:
        expr.setdefault(m['gene'], np.round(gene(m['gene']), 2).tolist())
    if synthetic:
        synthetic['checks'] = synthetic_checks(synthetic, moran, I, q, genes[cand], interface)
    res = {'spots': int(a.n_obs), 'genes': int(len(genes)), 'platform': 'Visium (55 µm spots)' if visium else 'bead array (e.g. Slide-seqV2, ≈10 µm beads)', 'graph': graph,
           'image': image, 'spotsPx': np.round(pos, 1).tolist(), 'spotRadiusPx': float(spot_r), 'umPerImagePx': um_per_px,
           'annotations': {k: v.tolist() for k, v in ann.items()}, 'primaryAnnotation': primary,
           'scores': {k: np.round(v, 3).tolist() for k, v in scores.items()}, 'expression': expr,
           'moran': moran, 'moranSummary': {'tested': int(len(cand)), 'significant': int((q < 0.05).sum()), 'medianShuffledI': shuffled_I, 'nullPermutations': nperm},
           'neighbourhood': ne, 'interface': interface, 'agreement': agree, 'synthetic': synthetic,
           'evidence': {'image': 'Experimental observation (H&E)', 'expression': 'Experimental observation (counts, log-normalised)', 'annotations': 'As deposited by the authors (pathologist or author labels); computed clusters are statistical',
                        'scores': 'As deposited by the authors; usually deconvolution (an AI / statistical prediction)', 'statistics': 'Statistical association'},
           'geometry': ('One 2D tissue section; measured positions; no 3D reconstruction. ' + ('Spots are 55 µm and contain several cells.' if visium else 'Beads ≈10 µm; position units as deposited (not stated), so no scale bar.')),
           'seconds': round(time.time() - t0, 1)}
    if synthetic:
        res['geometry'] = 'Synthetic section generated in silico with known ground truth. ' + res['geometry']
        res['evidence'] = {k: 'Synthetic (in-silico ground truth) — illustrative, not an observation' for k in res['evidence']}
    json.dump(res, open(out, 'w'))
    print(f'done in {res["seconds"]} s', flush=True)


def synthetic_checks(truth, moran, I, q, tested, interface):
    """Score the pipeline against the planted truth: spatial genes found, null genes not, infiltration phenotype recovered."""
    tested = [str(g) for g in tested]; sig = {g for g, qq in zip(tested, q) if qq < 0.05}
    planted = [g for g in truth['spatialGenes'] if g in tested]; nulls = [g for g in truth['nullGenes'] if g in tested]
    out = [{'check': 'Planted spatially patterned genes detected (q < 0.05)', 'value': f'{sum(g in sig for g in planted)} of {len(planted)}', 'passed': len(planted) > 0 and sum(g in sig for g in planted) >= 0.9 * len(planted)},
           {'check': 'Pattern-free genes falsely called spatial (q < 0.05)', 'value': f'{sum(g in sig for g in nulls)} of {len(nulls)}', 'passed': sum(g in sig for g in nulls) <= max(1, 0.1 * len(nulls))}]
    ex = (interface or {}).get('exclusion')
    if ex:
        want = truth['phenotype']; ratio = ex['ratio']
        got = 'excluded' if ratio < 0.5 and ex['p'] < 0.01 else 'infiltrated' if ratio >= 0.8 else 'intermediate'
        if want == 'desert':
            out.append({'check': 'Immune desert not mistaken for exclusion (planted: desert)', 'value': f'inside/rim {ex["readout"]} ratio {ratio:.2f} → {got}; a ratio cannot tell a desert from an infiltrated tumor without an absolute immune reference', 'passed': got != 'excluded'})
        else:
            out.append({'check': f'Immune phenotype recovered (planted: {want})', 'value': f'inside/rim {ex["readout"]} ratio {ratio:.2f} → {got}', 'passed': got == want})
    return out


if __name__ == '__main__':
    main(*sys.argv[1:])
