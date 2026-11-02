"""Oncology model comparison laboratory: two (or more) models on the same data, with numerical agreement and disagreement.

  dependency  DepMap Chronos vs Sanger Project Score (CRISPRcleanR) in the cell lines both screened, one model per patient
  drugs       held-out-patient predictions of every drug-response model on the same folds; paired error differences with a
              bootstrap over patients (not over cell lines, which would ignore sister lines)
  signalling  the same 90 % knockdown in every published ERK pathway model that contains the gene; direction and size of the
              ERK-PP change compared across models
"""
import json
import math

import numpy as np


def dependency(root, rel, gene=None):
    import oncology_stats as S
    import sanger_score as SS
    from scipy.stats import spearmanr
    import pathlib
    d = pathlib.Path(root) / 'oncology' / 'sanger'
    if not SS.installed(root):
        raise ValueError('Install Sanger Project Score in the Data tab first.')
    idx = json.loads((d / 'index.json').read_text()); L = np.load(d / 'lfc.npy', mmap_mode='r'); B = np.load(d / 'binary.npy', mmap_mode='r')
    E, em, genes, gi, keep, _ = S._rows(rel, 'gene_effect'); erow = {em[i]: i for i in keep}
    pairs, seen = [], set()
    for j, m in enumerate(idx['models']):
        pid = (rel.models.get(m) or {}).get('PatientID') or m
        if m in erow and pid not in seen:
            seen.add(pid); pairs.append((erow[m], j))
    common = [g for g in idx['genes'] if g in gi]; sg = {g: i for i, g in enumerate(idx['genes'])}
    Ed = np.asarray(E[[a for a, _ in pairs]][:, [gi[g] for g in common]], float); Ld = np.asarray(L[[b for _, b in pairs]][:, [sg[g] for g in common]], float)
    Bd = np.asarray(B[[b for _, b in pairs]][:, [sg[g] for g in common]], float)
    var = np.nanstd(Ed, 0) > 0.15                                                        # genes with real variation across lines
    rho = np.array([spearmanr(Ed[:, k], Ld[:, k], nan_policy='omit')[0] if var[k] else np.nan for k in range(len(common))])
    dep_ess = np.nanmean(Ed < -0.5, 0) >= 0.9; san_ess = np.nanmean(Bd, 0) >= 0.9
    jac = float((dep_ess & san_ess).sum() / max((dep_ess | san_ess).sum(), 1))
    out = {'lines': len(pairs), 'genes': len(common), 'variableGenes': int(var.sum()),
           'perGeneSpearman': {'median': float(np.nanmedian(rho)), 'q1': float(np.nanquantile(rho, .25)), 'q3': float(np.nanquantile(rho, .75)), 'over0.5': float(np.mean(rho[np.isfinite(rho)] > 0.5)),
                               'histogram': np.histogram(rho[np.isfinite(rho)], bins=20, range=(-1, 1))[0].tolist()},
           'commonEssential': {'depmap': int(dep_ess.sum()), 'sanger': int(san_ess.sum()), 'both': int((dep_ess & san_ess).sum()), 'jaccard': jac},
           'method': 'matched lines (DepMap name match, one per patient); per-gene Spearman of Chronos gene effect vs CRISPRcleanR log fold change, genes with SD > 0.15; common essential = effect < −0.5 (DepMap) or binary call (Sanger) in ≥ 90 % of lines',
           'evidence': 'Statistical comparison of two experimental screens (different libraries, laboratories and corrections)'}
    if gene and gene in common:
        k = common.index(gene); out['gene'] = {'gene': gene, 'spearman': float(rho[k]) if np.isfinite(rho[k]) else None, 'points': [[round(float(a), 3), round(float(b), 3)] for a, b in zip(Ed[:, k], Ld[:, k]) if np.isfinite(a) and np.isfinite(b)]}
    return out


def drugs(result, n_boot=2000, seed=0):
    """Paired comparison of the held-out predictions in one drug benchmark result (from drug_response.held_out_cell_lines)."""
    P = result.get('predictions')
    if not P:
        raise ValueError('Run the drug benchmark again: this result has no stored predictions.')
    y = np.array(P['observed']); pts = np.array(P['patient']); models = [k for k in P if k not in ('observed', 'patient')]
    up, inv = np.unique(pts, return_inverse=True); rng = np.random.default_rng(seed)
    err = {m: (np.array(P[m]) - y) ** 2 for m in models}
    def boot(diff):
        per = np.bincount(inv, weights=diff, minlength=len(up)); cnt = np.bincount(inv, minlength=len(up))
        stats = []
        for _ in range(n_boot):
            s = rng.integers(0, len(up), len(up)); stats.append(per[s].sum() / cnt[s].sum())
        return float(np.quantile(stats, .025)), float(np.quantile(stats, .975))
    ref = 'ridge' if 'ridge' in models else models[0]; rows = []
    for m in models:
        if m == ref:
            continue
        d = err[m] - err[ref]; lo, hi = boot(d)
        rows.append({'model': m, 'vs': ref, 'mseDifference': float(d.mean()), 'ci': [lo, hi],
                     'call': f'{m} worse than {ref}' if lo > 0 else f'{m} better than {ref}' if hi < 0 else 'no clear difference'})
    corr = {m: float(np.corrcoef(np.array(P[m]), np.array(P[ref]))[0, 1]) if np.std(P[m]) > 0 else None for m in models if m != ref}
    return {'drug': result.get('drug', {}).get('name'), 'lines': len(y), 'patients': len(up), 'reference': ref, 'comparisons': rows, 'predictionCorrelationWithReference': corr,
            'mse': {m: float(err[m].mean()) for m in models},
            'method': f'squared error per held-out line, difference to {ref}; 95 % interval from {n_boot} bootstrap resamples of patients',
            'evidence': 'Statistical comparison of AI predictions against experimental observations'}


def signalling(models=('mapk', 'schoeberl', 'hatakeyama'), strength=0.9):
    import perturbation as P
    out = {m: P.MODELS[m]['name'] for m in models}; shared = sorted({g for m in models for g in P.MODELS[m]['genes'] if sum(g in P.MODELS[x]['genes'] for x in models) >= 2})
    rows = []
    for g in shared:
        row = {'gene': g}
        for m in models:
            if g in P.MODELS[m]['genes']:
                e = P.ode_model(m, P._norm_perturbations([{'kind': 'gene', 'gene': g, 'strength': strength}]), {})
                m0 = e['metrics'][0]; row[m] = math.log2(max(m0[2], 1e-12) / max(m0[1], 1e-12))
        vals = [row[m] for m in models if m in row]
        row['agreeDirection'] = len({v > 0.05 for v in vals if abs(v) > 0.05}) <= 1; rows.append(row)
    pair = {}
    for i, a in enumerate(models):
        for b in models[i + 1:]:
            both = [r for r in rows if a in r and b in r]
            if len(both) >= 3:
                from scipy.stats import spearmanr
                pair[f'{a} vs {b}'] = {'genes': len(both), 'spearman': float(spearmanr([r[a] for r in both], [r[b] for r in both])[0]),
                                       'bothReduceOrNeither': float(np.mean([(r[a] < -0.05) == (r[b] < -0.05) for r in both]))}
    return {'models': out, 'rows': rows, 'pairs': pair, 'strength': strength,
            'method': f'{strength:.0%} knockdown (each model\'s stated mapping) of every gene present in ≥ 2 models; log2 fold change of the main ERK-PP readout; "both reduce or neither" counts genes where the two models agree on a > 3 % fall',
            'evidence': 'Comparison of mechanistic simulations (published models, different cell types and parameterisations)'}
