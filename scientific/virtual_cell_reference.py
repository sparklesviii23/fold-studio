"""Build the K-562 reference pack the virtual cell runs on (science runtime: NumPy, SciPy, anndata).

    python virtual_cell_reference.py <library root>

Inputs, all already in the library and verified on download:
  Norman 2019 CRISPRa Perturb-seq in K-562 (CC BY 4.0)   oncology/perturbseq/norman2019/NormanWeissman2019_filtered.h5ad
  Demo J held-out benchmark on the same data             oncology/perturbseq/norman2019/result.json
  DepMap 24Q4 CRISPR gene effect and expression (CC BY 4.0)  oncology/depmap/24Q4

Processing is identical to Demo J (scientific/perturb_model.py), so its held-out scores describe what the virtual cell
does: per-cell normalisation to 10,000 counts, log1p; gene panel = 2,000 most variable genes plus every perturbed gene;
an effect = mean of a perturbation's cells minus the mean of control cells; perturbations need ≥ 20 cells.

Output: <library>/virtualcell/reference/k562/pack.npz and manifest.json.
"""
import hashlib
import json
import pathlib
import sys
import time

import numpy as np

MIN_CELLS = 20
DEPMAP_MODEL = 'ACH-000551'      # K-562, Cellosaurus CVCL_0004


def _sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def build(root):
    import anndata as ad
    import scipy.sparse as sp
    root = pathlib.Path(root); t0 = time.time()
    log = lambda m: print(f'[{time.time() - t0:6.1f}s] {m}', flush=True)
    nd = root / 'oncology' / 'perturbseq' / 'norman2019'; dm = root / 'oncology' / 'depmap' / '24Q4'
    h5 = nd / 'NormanWeissman2019_filtered.h5ad'
    for f in (h5, nd / 'result.json', dm / 'gene_effect.npy', dm / 'expression.npy'):
        if not f.is_file():
            raise FileNotFoundError(f'Missing input {f.relative_to(root)}; install it in Oncology Universe first.')
    log('reading Norman 2019')
    A = ad.read_h5ad(h5)
    labels = A.obs['perturbation'].astype(str).values; ctrl = labels == 'control'
    X = sp.csr_matrix(A.X).astype(np.float32); lib = np.asarray(X.sum(1)).ravel()
    X = sp.csr_matrix(X.multiply(1e4 / np.maximum(lib, 1)[:, None])); X.data = np.log1p(X.data)
    names = np.array(A.var.index).astype(str); ens = np.array(A.var['ensemble_id']).astype(str)
    split = lambda p: [g for g in p.replace('+', '_').split('_') if g and g != 'control']
    counts = {p: int(n) for p, n in zip(*np.unique(labels[~ctrl], return_counts=True))}
    perts = sorted(p for p, n in counts.items() if n >= MIN_CELLS)
    mean = np.asarray(X.mean(0)).ravel(); var = np.asarray(X.multiply(X).mean(0)).ravel() - mean ** 2
    targets = {g for p in perts for g in split(p)}
    idx = sorted(set(np.argsort(-var)[:2000]) | {i for i, n in enumerate(names) if n in targets})
    panel = set(names[idx]); perts = [p for p in perts if all(g in panel for g in split(p))]      # as Demo J: targets must be measured genes
    Xs = X[:, idx]; c_mean = np.asarray(Xs[ctrl].mean(0)).ravel()
    c_sd = np.sqrt(np.maximum(np.asarray(Xs[ctrl].multiply(Xs[ctrl]).mean(0)).ravel() - c_mean ** 2, 0))
    log(f'{A.n_obs} cells, {int(ctrl.sum())} controls, panel {len(idx)} genes, {len(perts)} perturbations with ≥ {MIN_CELLS} cells')
    eff = np.zeros((len(idx), len(perts)), np.float32)
    for j, p in enumerate(perts):
        eff[:, j] = np.asarray(Xs[labels == p].mean(0)).ravel() - c_mean
    singles = [p for p in perts if len(split(p)) == 1]; pairs = [p for p in perts if len(split(p)) == 2]
    log(f'{len(singles)} single and {len(pairs)} paired activations')
    # DepMap K-562 row
    ge_meta = json.loads((dm / 'gene_effect.json').read_text()); ex_meta = json.loads((dm / 'expression.json').read_text())
    ge = np.load(dm / 'gene_effect.npy', mmap_mode='r'); ex = np.load(dm / 'expression.npy', mmap_mode='r')
    ge_row = np.array(ge[ge_meta['models'].index(DEPMAP_MODEL)], np.float32); ex_row = np.array(ex[ex_meta['models'].index(DEPMAP_MODEL)], np.float32)
    demo_j = json.loads((nd / 'result.json').read_text())
    out = root / 'virtualcell' / 'reference' / 'k562'; out.mkdir(parents=True, exist_ok=True)
    kd, kd_meta = {}, None
    rp = root / 'virtualcell' / 'data' / 'replogle2022' / 'ReplogleWeissman2022_K562_essential.h5ad'
    if rp.is_file():
        kd, kd_meta = knockdowns(rp, list(names[idx]), log)
    np.savez_compressed(out / 'pack.npz', genes=names[idx], ensembl=ens[idx], control=c_mean.astype(np.float32), controlSd=c_sd.astype(np.float32),
                        effects=eff, perturbations=np.array(perts), cells=np.array([counts[p] for p in perts]),
                        depmapGenes=np.array(ge_meta['genes']), depmapEffect=ge_row, depmapExprGenes=np.array(ex_meta['genes']), depmapExpression=ex_row, **kd)
    manifest = {
        'context': 'K-562', 'cellosaurus': 'CVCL_0004', 'depmapModel': DEPMAP_MODEL, 'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'panel': len(idx), 'singles': len(singles), 'pairs': len(pairs), 'controlCells': int(ctrl.sum()), 'minCells': MIN_CELLS,
        'expressionUnit': 'log1p(counts per 10,000)',
        'baselineNote': 'Baseline = mean of Norman 2019 control cells: K-562 carrying the CRISPRa machinery with non-targeting guides, not parental K-562.',
        'inputs': {'norman2019': {'file': h5.name, 'sha256': _sha(h5)}, 'depmap24q4': {'release': '24Q4', 'model': DEPMAP_MODEL},
                   **({'replogle2022': {'file': rp.name, 'sha256': _sha(rp)}} if kd else {})},
        'benchmark': {'source': 'Demo J held-out evaluation (scientific/perturb_model.py), 5-fold over perturbations', 'results': demo_j['results'],
                      'noiseCeiling': demo_j['noiseCeiling'], 'interactionScaling': demo_j.get('interactionScaling')},
        'knockdown': kd_meta, 'seconds': round(time.time() - t0, 1)}
    clean = lambda x: {k: clean(v) for k, v in x.items()} if isinstance(x, dict) else [clean(v) for v in x] if isinstance(x, list) else None if isinstance(x, float) and not np.isfinite(x) else x
    (out / 'manifest.json').write_text(json.dumps(clean(manifest), indent=1, default=float, allow_nan=False))
    log(f'wrote {out}')
    return manifest


def knockdowns(path, panel, log, folds=5, seed=0):
    """Replogle 2022 K-562 essential-gene CRISPRi screen, processed like Norman: per-cell normalisation to 10,000 counts,
    log1p; effect = knockdown mean minus control mean on the panel genes the screen measured.

    Also returns the on-target remaining fraction (target expression in knockdown cells / in controls, linear scale) and
    a 5-fold held-out benchmark over knockdowns whose target is a panel gene: mean training effect versus the linear model
    (Ahlmann-Eltze et al. 2025), scored like Demo J (Pearson over all scored genes and over the 20 most changed).
    """
    import anndata as ad
    import scipy.sparse as sp
    import perturb_model as pm
    A = ad.read_h5ad(path, backed='r')                      # 310k × 8.6k stored dense: streamed in chunks, never loaded whole
    labels = A.obs['perturbation'].astype(str).values; ctrl = np.isin(labels, ['control', 'non-targeting'])
    vnames = np.array(A.var['gene_symbol'] if 'gene_symbol' in A.var else A.var.index).astype(str); vi = {g: i for i, g in enumerate(vnames)}
    cols = np.array([vi.get(g, -1) for g in panel]); measured = cols >= 0
    counts = dict(zip(*np.unique(labels[~ctrl], return_counts=True)))
    perts = sorted(p for p, n in counts.items() if n >= MIN_CELLS and '_' not in p and '+' not in p)
    log(f'Replogle: {A.n_obs} cells, {int(ctrl.sum())} controls, {len(perts)} single knockdowns with >= {MIN_CELLS} cells; {int(measured.sum())}/{len(panel)} panel genes measured')
    # group index per cell: 0 = control, 1.. = knockdowns, -1 = unused; each cell also gets a random half for the noise ceiling
    gid = {p: k + 1 for k, p in enumerate(perts)}; grp = np.array([0 if c else gid.get(l, -1) for l, c in zip(labels, ctrl)])
    rng = np.random.default_rng(seed); half = rng.integers(0, 2, A.n_obs)
    sums = np.zeros((2, len(perts) + 1, A.n_vars)); n = np.zeros((2, len(perts) + 1))
    for start in range(0, A.n_obs, 20000):
        X = np.asarray(A.X[start:start + 20000], np.float32)
        X = np.log1p(X * (1e4 / np.maximum(X.sum(1, keepdims=True), 1)))
        g, h = grp[start:start + 20000], half[start:start + 20000]; keep = g >= 0
        np.add.at(sums, (h[keep], g[keep]), X[keep]); np.add.at(n, (h[keep], g[keep]), 1)
    mean = sums.sum(0) / np.maximum(n.sum(0), 1)[:, None]; halves = sums / np.maximum(n, 1)[:, :, None]
    c_all = mean[0]
    eff = np.full((len(panel), len(perts)), np.nan, np.float32); remaining = np.full(len(perts), np.nan, np.float32); half_r = []
    for j, p in enumerate(perts):
        m = mean[j + 1]
        eff[measured, j] = (m - c_all)[cols[measured]]
        if p in vi and np.expm1(c_all[vi[p]]) > 0.05:
            remaining[j] = np.expm1(m[vi[p]]) / np.expm1(c_all[vi[p]])
        ea = (halves[0, j + 1] - halves[0, 0])[cols[measured]]; eb = (halves[1, j + 1] - halves[1, 0])[cols[measured]]
        half_r.append(pm._pearson(ea, eb))
    # held-out benchmark over knockdowns whose target is a measured panel gene
    pidx = {g: k for k, g in enumerate(np.array(panel)[measured])}
    Y = eff[measured]; ok = [j for j, p in enumerate(perts) if p in pidx]
    order = np.random.default_rng(seed + 1).permutation(ok); res = {'mean effect': [], 'linear model': []}
    for f in range(folds):
        test = set(order[f::folds]); train = [j for j in ok if j not in test]
        lin = pm.linear_fit(Y[:, train].astype(float), [[perts[j]] for j in train], pidx)
        mu = Y[:, train].mean(1)
        for j in test:
            obs = Y[:, j].astype(float); excl = [pidx[perts[j]]]
            res['mean effect'].append(pm._score(mu, obs, excl)); res['linear model'].append(pm._score(lin([[perts[j]]])[:, 0], obs, excl))
    summ = lambda rows: {k: {'mean': float(np.nanmean([r[k] for r in rows])), 'sd': float(np.nanstd([r[k] for r in rows]))} for k in ('pearson', 'pearsonTop20', 'mse')}
    meta = {'knockdowns': len(perts), 'controlCells': int(ctrl.sum()), 'panelMeasured': int(measured.sum()),
            'medianRemaining': float(np.nanmedian(remaining)), 'remainingKnown': int(np.isfinite(remaining).sum()),
            'noiseCeiling': {'pearson': {'mean': float(np.nanmean(half_r))}}, 'benchmark': {'task': 'unseen knockdowns (target in panel), 5-fold', 'n': len(ok), **{k: summ(v) for k, v in res.items()}},
            'baselineNote': 'Effects are relative to Replogle control cells (CRISPRi machinery, non-targeting guides) and are applied to the Norman baseline: cross-dataset composition.'}
    log(f"Replogle: median on-target remaining {meta['medianRemaining']:.2f}; held-out linear r {meta['benchmark']['linear model']['pearson']['mean']:.2f} vs mean {meta['benchmark']['mean effect']['pearson']['mean']:.2f}")
    return {'kdEffects': eff, 'kdPerturbations': np.array(perts), 'kdCells': np.array([counts[p] for p in perts]), 'kdRemaining': remaining, 'kdMeasured': measured}, meta


if __name__ == '__main__':
    build(sys.argv[1])
