"""Drug-response prediction benchmark: GDSC measured responses, DepMap expression features.

Evidence: AI prediction (statistical model) evaluated against Experimental observation (GDSC fitted LN_IC50).
A predicted IC50 is a statement about a cell line in a viability assay, never about patients or clinical benefit.

Leakage controls built in (each split reports what it checked):
  * Cell lines are split by DepMap PatientID, so sister lines from one donor never sit on both sides.
  * Feature selection (most-variable genes) and standardisation are fitted on the training fold only.
  * Held-out compounds: the same compound screened in GDSC1 and GDSC2 (same name, different DRUG_ID) is one compound.
  * Hyper-parameters are chosen by inner cross-validation inside the training fold.
"""
import json
import math
import re

import numpy as np

import oncology_data as D

EVIDENCE = 'AI prediction (regularised regression) scored against experimental GDSC dose–response fits'


def _norm(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())


class Data:
    def __init__(self, s, gdsc='8.5'):
        self.dep = D.Release(s)
        g = D.root(s, 'gdsc', gdsc)
        if not (g / 'responses.npz').is_file():
            raise ValueError('GDSC is not installed yet. Install it from Oncology › Data.')
        r = np.load(g / 'responses.npz', allow_pickle=True)
        self.r = {k: r[k] for k in r.files}
        self.drugs = {d['key']: d for d in json.loads((g / 'drugs.json').read_text())}
        self.sanger = {m.get('SangerModelID'): k for k, m in self.dep.models.items() if m.get('SangerModelID')}
        X, xm, xg, xgi, _ = self.dep.matrix('expression')
        self.X, self.xrow, self.genes = X, {m: i for i, m in enumerate(xm)}, xg

    def table(self, drug):
        """Mean LN_IC50 per DepMap model for one drug (replicate curves averaged; their count is kept)."""
        sel = self.r['drug'] == drug
        acc = {}
        for sid, y in zip(self.r['model'][sel], self.r['ln_ic50'][sel]):
            m = self.sanger.get(sid)
            if m and m in self.xrow and np.isfinite(y):
                acc.setdefault(m, []).append(y)
        ids = sorted(acc)
        return ids, np.array([np.mean(acc[m]) for m in ids]), sum(len(v) > 1 for v in acc.values()), int(sel.sum())

    def meta(self, m, k):
        return self.dep.models.get(m, {}).get(k) or m


def _folds(groups, k, seed=0):
    u = sorted(set(groups)); rng = np.random.default_rng(seed); rng.shuffle(u)
    fold = {g: i % k for i, g in enumerate(u)}
    return np.array([fold[g] for g in groups])


def _prep(Xtr, Xte, top):
    v = Xtr.var(0); idx = np.argsort(v)[::-1][:top]
    mu, sd = Xtr[:, idx].mean(0), Xtr[:, idx].std(0) + 1e-8
    return (Xtr[:, idx] - mu) / sd, (Xte[:, idx] - mu) / sd


def _ridge_path(X, y, lams):
    U, s, Vt = np.linalg.svd(X, full_matrices=False); Uy = U.T @ y
    return [Vt.T @ (s / (s ** 2 + l) * Uy) for l in lams]


def _enet(X, y, lam, alpha=0.5, b=None, sweeps=60):
    n, p = X.shape; G = X.T @ X / n; c = X.T @ y / n; b = np.zeros(p) if b is None else b.copy(); diag = np.diag(G)
    for _ in range(sweeps):
        delta = 0.0
        for j in range(p):
            rho = c[j] - G[j] @ b + diag[j] * b[j]
            new = np.sign(rho) * max(abs(rho) - lam * alpha, 0) / (diag[j] + lam * (1 - alpha))
            delta = max(delta, abs(new - b[j])); b[j] = new
        if delta < 1e-5:
            break
    return b


def _fit(kind, Xtr, ytr, groups, top):
    """Inner grouped CV picks the penalty; returns a predictor and the inner residual SD (for prediction intervals)."""
    lams = {'ridge': [10, 100, 1e3, 1e4, 1e5], 'enet': [0.3, 0.15, 0.08, 0.04, 0.02]}[kind]
    inner = _folds(groups, 3, seed=1); err = np.zeros(len(lams)); res = []
    for f in range(3):
        a, b_ = inner != f, inner == f
        A, B = _prep(Xtr[a], Xtr[b_], top); m = ytr[a].mean()
        if kind == 'ridge':
            preds = [B @ w + m for w in _ridge_path(A, ytr[a] - m, lams)]
        else:
            w, preds = None, []
            for l in lams:
                w = _enet(A, ytr[a] - m, l, b=w); preds.append(B @ w + m)
        err += [((p - ytr[b_]) ** 2).sum() for p in preds]
    best = lams[int(np.argmin(err))]
    A, _ = _prep(Xtr, Xtr[:1], top); m = ytr.mean()
    w = _ridge_path(A, ytr - m, [best])[0] if kind == 'ridge' else _enet(A, ytr - m, best)
    sd = math.sqrt(err.min() / len(ytr))
    def predict(Xte):
        _, B = _prep(Xtr, Xte, top)
        return B @ w + m
    return predict, best, sd, int((np.abs(w) > 1e-8).sum())


TREES = {'forest': 'random forest, 300 trees, √p features per split, ≥ 5 lines per leaf, seed 0',
         'boosting': 'histogram gradient boosting, 200 iterations, learning rate 0.05, ≤ 15 leaves, L2 1.0, no early stopping, seed 0',
         'note': 'fixed settings, not tuned, so no inner selection can leak; same top-variable genes chosen inside each training fold'}


def _tree(kind, X, y):
    from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
    m = RandomForestRegressor(n_estimators=300, max_features='sqrt', min_samples_leaf=5, n_jobs=-1, random_state=0) if kind == 'forest' else \
        HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, l2_regularization=1.0, early_stopping=False, random_state=0)
    return m.fit(X, y)


def _metrics(y, p, sd=None):
    from scipy.stats import pearsonr, spearmanr
    out = {'n': int(len(y)), 'rmse': float(np.sqrt(((p - y) ** 2).mean())), 'mae': float(np.abs(p - y).mean())}
    if np.std(p) > 1e-9 and len(y) > 2:
        out['pearson'] = float(pearsonr(y, p)[0]); out['spearman'] = float(spearmanr(y, p)[0])
    if sd:
        out['coverage90'] = float((np.abs(p - y) <= 1.645 * sd).mean())
    return out


def held_out_cell_lines(s, drug, top=500, k=5, d=None):
    d = d or Data(s)
    if drug not in d.drugs:
        raise ValueError('Choose a GDSC drug.')
    ids, y, reps, curves = d.table(drug)
    if len(ids) < 50:
        raise ValueError(f'Only {len(ids)} cell lines link to DepMap expression for this drug.')
    X = np.asarray(d.X[[d.xrow[m] for m in ids]], float)
    groups = [d.meta(m, 'PatientID') for m in ids]; lineage = [d.meta(m, 'OncotreeLineage') for m in ids]
    fold = _folds(groups, k)
    try:
        import sklearn                                    # tree baselines need scikit-learn (science runtime); without it they are skipped and said so
        trees = ('forest', 'boosting')
    except ImportError:
        trees = ()
    preds = {n: np.zeros(len(y)) for n in ('mean', 'lineage', 'ridge', 'enet', *trees)}; sds = {'ridge': [], 'enet': []}; chosen = {'ridge': [], 'enet': []}
    leak = []
    for f in range(k):
        tr, te = fold != f, fold == f
        shared = {groups[i] for i in np.where(tr)[0]} & {groups[i] for i in np.where(te)[0]}
        leak.append(len(shared))
        preds['mean'][te] = y[tr].mean()
        lm = {}
        for i in np.where(tr)[0]:
            lm.setdefault(lineage[i], []).append(y[i])
        preds['lineage'][te] = [np.mean(lm[lineage[i]]) if lineage[i] in lm else y[tr].mean() for i in np.where(te)[0]]
        g_tr = [groups[i] for i in np.where(tr)[0]]
        for kind in ('ridge', 'enet'):
            fn, lam, sd, nz = _fit(kind, X[tr], y[tr], g_tr, top)
            preds[kind][te] = fn(X[te]); sds[kind].append((te, sd)); chosen[kind].append({'penalty': lam, 'nonzero': nz})
        for kind in trees:
            A, B = _prep(X[tr], X[te], top)              # same fold-internal feature selection as the linear models
            preds[kind][te] = _tree(kind, A, y[tr]).predict(B)
    res = {}
    for n, p in preds.items():
        sd = None
        if n in sds:
            sd_vec = np.zeros(len(y))
            for te, v in sds[n]:
                sd_vec[te] = v
            res[n] = _metrics(y, p); res[n]['coverage90'] = float((np.abs(p - y) <= 1.645 * sd_vec).mean())
        else:
            res[n] = _metrics(y, p)
    dr = d.drugs[drug]
    return {'split': 'held-out cell lines', 'drug': dr, 'cellLines': len(ids), 'curves': curves, 'linesWithReplicates': reps, 'folds': k, 'features': f'top {top} most-variable genes (chosen within each training fold), DepMap {d.dep.release} expression',
            'results': res, 'penalties': chosen, 'points': [[m, d.meta(m, 'CellLineName'), lineage[i], round(float(y[i]), 3), round(float(preds['ridge'][i]), 3)] for i, m in enumerate(ids)],
            'leakage': {'patientsSharedAcrossFolds': int(sum(leak)), 'featureSelection': 'inside training folds', 'standardisation': 'training-fold statistics', 'penaltyChoice': 'inner grouped 3-fold CV'},
            'trees': TREES if trees else 'not run: scikit-learn is only in the science runtime (runtimes/singlecell)',
            'predictions': {'observed': np.round(y, 4).tolist(), 'patient': groups, **{n: np.round(v, 4).tolist() for n, v in preds.items()}},   # held-out, for paired comparisons
            'units': 'LN_IC50 (natural log of IC50 in µM)', 'evidence': EVIDENCE,
            'caveat': 'Cell-line viability IC50 under GDSC assay conditions; says nothing about patient response.'}


def held_out_compounds(s, dataset='GDSC2', k=5):
    """Predict responses to compounds never seen in training: cell-line general sensitivity + mean of the drug's pathway."""
    d = Data(s)
    keys = [kk for kk, v in d.drugs.items() if v['dataset'] == dataset]
    cols = {kk: d.table(kk)[:2] for kk in keys}
    models = sorted({m for ids, _ in cols.values() for m in ids}); mi = {m: i for i, m in enumerate(models)}
    Y = np.full((len(models), len(keys)), np.nan)
    for j, kk in enumerate(keys):
        ids, y = cols[kk]
        Y[[mi[m] for m in ids], j] = y
    comp = [_norm(d.drugs[kk]['name']) for kk in keys]          # one compound = one name, across screens and IDs
    fold = _folds(comp, k); path = [d.drugs[kk]['pathway'] for kk in keys]
    out = {'global': [], 'pathway': [], 'pathway+cell': []}; rank = {'pathway+cell': []}; leak = 0
    for f in range(k):
        tr, te = np.where(fold != f)[0], np.where(fold == f)[0]
        leak += len({comp[j] for j in tr} & {comp[j] for j in te})
        mu = np.nanmean(Y[:, tr], 0)
        Z = (Y[:, tr] - mu) / (np.nanstd(Y[:, tr], 0) + 1e-9); cell = np.nanmean(Z, 1)
        pm = {}
        for j in tr:
            pm.setdefault(path[j], []).append(mu[list(tr).index(j)])
        g = float(np.nanmean(Y[:, tr])); sd_all = float(np.nanmean(np.nanstd(Y[:, tr], 0)))
        for j in te:
            obs = ~np.isnan(Y[:, j]); y = Y[obs, j]
            base = np.mean(pm[path[j]]) if path[j] in pm else g
            c = np.nan_to_num(cell[obs])
            for name, p in (('global', np.full(len(y), g)), ('pathway', np.full(len(y), base)), ('pathway+cell', base + sd_all * c)):
                out[name].append((y, p))
            if np.std(y) > 0:
                from scipy.stats import spearmanr
                rank['pathway+cell'].append(spearmanr(y, c)[0])
    res = {n: _metrics(np.concatenate([a for a, _ in v]), np.concatenate([b for _, b in v])) for n, v in out.items()}
    res['pathway+cell']['meanWithinDrugSpearman'] = float(np.nanmean(rank['pathway+cell']))
    return {'split': 'held-out compounds', 'dataset': dataset, 'compounds': len(set(comp)), 'drugScreens': len(keys), 'cellLines': len(models), 'folds': k, 'results': res,
            'leakage': {'compoundsSharedAcrossFolds': leak, 'compoundIdentity': 'normalised drug name (GDSC1/GDSC2 duplicates and re-IDs grouped)'},
            'method': 'global mean; mean of training drugs in the same GDSC pathway; plus each cell line\'s general sensitivity (mean z-scored response to training drugs)',
            'units': 'LN_IC50', 'evidence': EVIDENCE}


def held_out_lineage(s, drug, lineage, top=500):
    d = Data(s)
    ids, y, *_ = d.table(drug)
    lin = np.array([d.meta(m, 'OncotreeLineage') == lineage for m in ids])
    if lin.sum() < 10:
        raise ValueError(f'{lineage}: fewer than 10 lines screened with this drug.')
    X = np.asarray(d.X[[d.xrow[m] for m in ids]], float); tr = ~lin
    fn, lam, sd, nz = _fit('ridge', X[tr], y[tr], [d.meta(ids[i], 'PatientID') for i in np.where(tr)[0]], top)
    p = fn(X[lin])
    return {'split': f'held-out lineage ({lineage})', 'drug': d.drugs[drug], 'train': int(tr.sum()), 'test': int(lin.sum()),
            'results': {'mean': _metrics(y[lin], np.full(lin.sum(), y[tr].mean())), 'ridge': {**_metrics(y[lin], p), 'coverage90': float((np.abs(p - y[lin]) <= 1.645 * sd).mean())}},
            'domainShift': {'trainMean': float(y[tr].mean()), 'testMean': float(y[lin].mean())}, 'evidence': EVIDENCE}


def drugs(s):
    d = Data(s)
    out = []
    for kk, v in d.drugs.items():
        out.append({**v, 'curves': int((d.r['drug'] == kk).sum())})
    return sorted(out, key=lambda v: (v['dataset'] != 'GDSC2', v['name'].lower()))


def biomarker_scan(s, gene, kind='hotspot', dataset='GDSC2', min_mutant=5):
    """Every drug in one screen: LN_IC50 difference between lines with and without a mutation, lineage-adjusted (BH). Negative Δ = mutant lines more sensitive."""
    from scipy.stats import t as T
    import oncology_stats as S
    d = Data(s); Mu, mm, mg, mgi, _ = d.dep.matrix('mut_' + kind)
    if gene not in mgi:
        raise ValueError(f'{gene} has no {kind} mutation calls.')
    mrow = {m: i for i, m in enumerate(mm)}; out = []
    for key, dr in d.drugs.items():
        if dr['dataset'] != dataset:
            continue
        ids, y, *_ = d.table(key)
        keep = [i for i, m in enumerate(ids) if m in mrow]
        if len(keep) < 30:
            continue
        x = np.array([Mu[mrow[ids[i]], mgi[gene]] > 0 for i in keep]); yy = y[keep]
        if x.sum() < min_mutant or (~x).sum() < min_mutant:
            continue
        # Lineage fixed effects (Frisch–Waugh–Lovell): lineage drives both mutation frequency and drug sensitivity.
        L, k = S._lineage_design(d.dep, [ids[i] for i in keep]); P = L @ np.linalg.pinv(L)
        rx = x.astype(float) - P @ x.astype(float); ry = yy - P @ yy; sxx = rx @ rx
        if sxx < 1e-9:
            continue
        diff = (rx @ ry) / sxx; dfree = len(yy) - k - 1; se = math.sqrt(((ry - rx * diff) ** 2).sum() / dfree / sxx)
        out.append({'drug': dr['name'], 'key': key, 'target': dr['target'], 'pathway': dr['pathway'], 'mutant': int(x.sum()), 'wildtype': int((~x).sum()), 'deltaLnIC50': float(diff),
                    'ci': [float(diff - T.ppf(.975, dfree) * se), float(diff + T.ppf(.975, dfree) * se)], 'p': float(2 * T.sf(abs(diff / se), dfree))})
    q = S._bh([r['p'] for r in out]) if out else []
    for r, v in zip(out, q):
        r['q'] = float(v)
    out.sort(key=lambda r: r['p'])
    return {'gene': gene, 'kind': kind, 'dataset': dataset, 'drugsTested': len(out), 'results': out, 'method': 'OLS of LN_IC50 on mutation status with lineage fixed effects (DepMap mutation calls and lineages), BH over drugs',
            'evidence': 'Statistical association between a measured genotype and measured drug response in cell lines', 'caveat': 'Lineage-adjusted; other confounders (growth rate, assay batch) are not. Cell-line response is not patient benefit.'}


if __name__ == '__main__':
    import sys, types
    if sys.argv[1] == 'cells':                           # run in the science runtime so the tree baselines are available
        print(json.dumps(held_out_cell_lines(types.SimpleNamespace(root=sys.argv[2]), sys.argv[3]), default=float))
