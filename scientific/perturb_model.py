"""Demo J · cellular perturbation model: predict transcriptional responses to CRISPR activation, with genuine held-out evaluation.

    python perturb_model.py <NormanWeissman2019_filtered.h5ad> <out.json>

Data: Norman TM et al., Science 2019;365:786 — CRISPRa Perturb-seq in K562 cells, single and paired gene activations (scPerturb
harmonised file, Zenodo 7041849, CC BY 4.0). Effects: per perturbation, mean log-normalised expression minus the control mean,
on the 2,000 most variable genes plus every perturbed gene; a perturbation's own target genes are excluded when scoring.

Tasks and models (all fitted on training perturbations only; folds over perturbations, 5-fold)
  Unseen pairs     both single perturbations seen, the pair held out: no change · mean training pair · additive (A + B) ·
                   linear model with summed perturbation embeddings
  Unseen singles   the perturbed gene never perturbed in training: no change · mean training effect · linear model
  Linear model     Ahlmann-Eltze C, Huber W, Anders S, Nat Methods 2025: Y ≈ G W Pᵀ + b, G = top-10 principal components of the
                   training effect matrix (genes), P = rows of G for the perturbed genes, W by ridge (λ = 0.1)
  Noise ceiling    each perturbation's cells split in two halves; agreement between the halves' effects
Metrics per held-out perturbation: Pearson r of predicted vs observed change over all scored genes and over the 20 genes that
change most; mean squared error. Evidence: AI prediction (statistical model) scored against experimental observation.
A predicted expression change is not cell death, proliferation or a therapeutic effect.
"""
import json
import sys
import time

import numpy as np


def _pearson(a, b):
    a, b = a - a.mean(), b - b.mean(); d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else float('nan')


def _score(pred, obs, exclude):
    keep = np.ones(len(obs), bool); keep[list(exclude)] = False; p, o = pred[keep], obs[keep]
    top = np.argsort(-np.abs(o))[:20]
    return {'pearson': _pearson(p, o), 'pearsonTop20': _pearson(p[top], o[top]), 'mse': float(((p - o) ** 2).mean())}


def linear_fit(Y, P_genes, gi, K=10, lam=0.1):
    """Y: genes × training perturbations (effects). Returns predict(list of perturbed-gene lists) → genes × n."""
    b = Y.mean(1, keepdims=True); Yc = Y - b
    U, S, Vt = np.linalg.svd(Yc, full_matrices=False); G = U[:, :K] * S[:K]                         # gene embedding
    emb = lambda genes: sum(G[gi[g]] for g in genes)                                                  # a pair = sum of its genes' rows
    P = np.vstack([emb(gs) for gs in P_genes])                                                        # perturbations × K
    A = np.linalg.solve(G.T @ G + lam * np.eye(K), G.T @ Yc @ P); W = np.linalg.solve((P.T @ P + lam * np.eye(K)).T, A.T).T
    return lambda gl: G @ W @ np.vstack([emb(gs) for gs in gl]).T + b


def main(path, out, folds=5, seed=0):
    import anndata as ad, scipy.sparse as sp
    t0 = time.time(); log = lambda m: print(f'[{time.time() - t0:6.1f}s] {m}', flush=True)
    A = ad.read_h5ad(path); obs = A.obs; col = 'perturbation' if 'perturbation' in obs else obs.columns[0]
    labels = obs[col].astype(str).values; ctrl = np.isin(labels, ['control', 'ctrl', 'non-targeting', 'NT'])
    X = sp.csr_matrix(A.X).astype(np.float32); lib = np.asarray(X.sum(1)).ravel(); X = sp.csr_matrix(X.multiply(1e4 / np.maximum(lib, 1)[:, None])); X.data = np.log1p(X.data)
    names = np.array(A.var['gene_symbol'] if 'gene_symbol' in A.var else A.var.index).astype(str)
    log(f'{A.n_obs} cells, {A.n_vars} genes, {int(ctrl.sum())} control cells')
    perts = sorted(set(labels[~ctrl])); split = lambda p: [g for g in p.replace('+', '_').split('_') if g and g != 'control']
    mean = np.asarray(X.mean(0)).ravel(); sq = np.asarray(X.multiply(X).mean(0)).ravel(); var = sq - mean ** 2
    hv = set(np.argsort(-var)[:2000]); targets = {g for p in perts for g in split(p)}; idx = sorted(hv | {i for i, n in enumerate(names) if n in targets})
    gi = {names[i]: k for k, i in enumerate(idx)}; Xs = X[:, idx]
    c_mean = np.asarray(Xs[ctrl].mean(0)).ravel(); rng = np.random.default_rng(seed)
    eff, half_r, ncells = {}, [], {}
    for p in perts:
        rows = np.where(labels == p)[0]; ncells[p] = len(rows)
        if len(rows) < 20 or any(g not in gi for g in split(p)):
            continue
        eff[p] = np.asarray(Xs[rows].mean(0)).ravel() - c_mean
        h = rng.permutation(rows); a, b = h[:len(h) // 2], h[len(h) // 2:]
        ea, eb = np.asarray(Xs[a].mean(0)).ravel() - c_mean, np.asarray(Xs[b].mean(0)).ravel() - c_mean
        half_r.append(_score(ea, eb, [gi[g] for g in split(p)]))
    singles = [p for p in eff if len(split(p)) == 1]; pairs = [p for p in eff if len(split(p)) == 2 and all(g in {split(s)[0] for s in singles} for g in split(p))]
    sgene = {split(p)[0]: p for p in singles}
    log(f'{len(singles)} single and {len(pairs)} paired perturbations with ≥ 20 cells; {len(idx)} genes scored')
    res = {'pairs': {k: [] for k in ('no change', 'mean pair', 'additive', 'linear model')}, 'singles': {k: [] for k in ('no change', 'mean effect', 'linear model')}}
    per = {'pairs': {}, 'singles': {}}
    # ---- unseen pairs
    fold = {p: i % folds for i, p in enumerate(rng.permutation(pairs))}
    for f in range(folds):
        tr = [p for p in pairs if fold[p] != f]; te = [p for p in pairs if fold[p] == f]
        train = singles + tr; Y = np.column_stack([eff[p] for p in train]); lin = linear_fit(Y, [split(p) for p in train], gi)
        mp = np.mean([eff[p] for p in tr], 0); L = lin([split(p) for p in te])
        for j, p in enumerate(te):
            ex = [gi[g] for g in split(p)]; a, b = split(p)
            preds = {'no change': np.zeros_like(eff[p]), 'mean pair': mp, 'additive': eff[sgene[a]] + eff[sgene[b]], 'linear model': L[:, j]}
            for k, v in preds.items():
                s = _score(v, eff[p], ex); res['pairs'][k].append(s); per['pairs'].setdefault(p, {})[k] = s
    # ---- unseen singles
    fold = {p: i % folds for i, p in enumerate(rng.permutation(singles))}
    for f in range(folds):
        tr = [p for p in singles if fold[p] != f]; te = [p for p in singles if fold[p] == f]
        Y = np.column_stack([eff[p] for p in tr]); lin = linear_fit(Y, [split(p) for p in tr], gi); me = Y.mean(1); L = lin([split(p) for p in te])
        for j, p in enumerate(te):
            ex = [gi[g] for g in split(p)]
            for k, v in {'no change': np.zeros_like(eff[p]), 'mean effect': me, 'linear model': L[:, j]}.items():
                s = _score(v, eff[p], ex); res['singles'][k].append(s); per['singles'].setdefault(p, {})[k] = s
    summ = lambda xs: {m: {'mean': float(np.nanmean([x[m] for x in xs])), 'sd': float(np.nanstd([x[m] for x in xs]))} for m in ('pearson', 'pearsonTop20', 'mse')}
    def paired(task, a, b, metric='pearsonTop20', n=2000):
        d = np.array([per[task][p][a][metric] - per[task][p][b][metric] for p in per[task]]); d = d[np.isfinite(d)]
        bs = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(n)]
        return {'a': a, 'b': b, 'metric': metric, 'meanDifference': float(d.mean()), 'ci': [float(np.quantile(bs, .025)), float(np.quantile(bs, .975))], 'n': int(len(d))}
    # ---- genetic interactions: departure of observed pairs from the additive expectation
    inter = []
    for p in pairs:
        a, b = split(p); add = eff[sgene[a]] + eff[sgene[b]]; ex = [gi[g] for g in split(p)]; keep = np.ones(len(add), bool); keep[ex] = False
        o, ad_ = eff[p][keep], add[keep]; beta = float(o @ ad_ / max(ad_ @ ad_, 1e-12))
        inter.append({'pair': p, 'cells': ncells[p], 'scaling': beta, 'residualFraction': float(((o - beta * ad_) ** 2).sum() / max((o ** 2).sum(), 1e-12)),
                      'additivePearson': _pearson(ad_, o)})
    inter.sort(key=lambda r: -r['residualFraction'])
    ex_pair = max(pairs, key=lambda p: per['pairs'][p]['additive']['pearsonTop20'] if np.isfinite(per['pairs'][p]['additive']['pearsonTop20']) else -9) if pairs else None
    def example(p):
        a, b = split(p); keep = [k for k in np.argsort(-np.abs(eff[p])) if k not in {gi[g] for g in split(p)}][:25]
        inv = {k: n for n, k in gi.items()}
        return {'perturbation': p, 'genes': [inv[k] for k in keep], 'observed': [round(float(eff[p][k]), 3) for k in keep], 'additive': [round(float(eff[sgene[a]][k] + eff[sgene[b]][k]), 3) for k in keep]}
    out_d = {'cells': int(A.n_obs), 'controlCells': int(ctrl.sum()), 'genesScored': len(idx), 'singles': len(singles), 'pairs': len(pairs),
             'results': {t: {k: summ(v) for k, v in r.items()} for t, r in res.items()},
             'paired': [paired('pairs', 'linear model', 'additive'), paired('pairs', 'additive', 'mean pair'), paired('singles', 'linear model', 'mean effect')],
             'noiseCeiling': summ(half_r), 'interactions': inter[:40], 'interactionScaling': {'median': float(np.median([r['scaling'] for r in inter])) if inter else None},
             'example': example(ex_pair) if ex_pair else None, 'examplesWorst': [example(r['pair']) for r in inter[:3]],
             'perPerturbation': {t: {p: {k: round(v['pearsonTop20'], 3) if np.isfinite(v['pearsonTop20']) else None for k, v in d.items()} for p, d in per[t].items()} for t in per},
             'method': __doc__.split('Tasks and models')[1].split('Metrics per')[0].strip(), 'evidence': 'AI prediction (statistical models) scored against experimental observation (Perturb-seq)',
             'caveat': 'K562 leukaemia cells under CRISPR activation; predicted expression changes are not cell killing, proliferation or therapeutic effects, and do not transfer to other cell types or to knockouts without evidence.',
             'dataset': {'name': 'Norman 2019 (scPerturb)', 'citation': 'Norman TM et al. Science 2019;365:786–793; Peidli S et al. Nat Methods 2024 (scPerturb).', 'licence': 'CC BY 4.0', 'zenodo': '7041849'},
             'seconds': round(time.time() - t0, 1)}
    json.dump(out_d, open(out, 'w')); log('done')


RECORD, FILE = 'https://zenodo.org/api/records/7041849', 'NormanWeissman2019_filtered.h5ad'


def install(folder, log=print):
    """Download the scPerturb Norman 2019 file (≈ 700 MB, resumable) and verify it against Zenodo's published MD5."""
    import hashlib
    import pathlib
    import urllib.request
    d = pathlib.Path(folder); d.mkdir(parents=True, exist_ok=True); z = d / FILE
    f = next(x for x in json.loads(urllib.request.urlopen(RECORD, timeout=60).read())['files'] if x['key'] == FILE)
    while not z.is_file() or z.stat().st_size < f['size']:
        have = z.stat().st_size if z.is_file() else 0; log(f'downloading from byte {have:,} of {f["size"]:,}')
        with urllib.request.urlopen(urllib.request.Request(f'{RECORD}/files/{FILE}/content', headers={'Range': f'bytes={have}-'}), timeout=120) as r, open(z, 'ab') as out:
            while chunk := r.read(1 << 22):
                out.write(chunk)
    h = hashlib.md5()
    with open(z, 'rb') as fh:
        while chunk := fh.read(1 << 22):
            h.update(chunk)
    if h.hexdigest() != f['checksum'].split(':', 1)[1]:
        z.rename(z.with_suffix('.corrupt')); raise SystemExit('MD5 mismatch; the file was set aside.')
    (d / 'manifest.json').write_text(json.dumps({'file': FILE, 'record': RECORD, 'md5': h.hexdigest(), 'bytes': f['size'], 'licence': 'CC BY 4.0'}, indent=1)); log('verified')


if __name__ == '__main__':
    install(sys.argv[2]) if sys.argv[1] == 'install' else main(*sys.argv[1:3])
