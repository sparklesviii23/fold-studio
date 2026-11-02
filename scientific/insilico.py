"""In-silico runs for every oncology demo: synthetic data with a planted answer, fed through the demo's own analysis code,
then scored against what was planted. A run is a test of the method on data where the truth is known, never an observation.

    python insilico.py <library root> <demo> <run id>        (parameters are read from oncology/insilico/<demo>/<id>/params.json)

Demos and what each simulator plants
  atlas       CRISPR gene effects: common essentials, lineage-selective dependencies, a mutation-linked dependency set,
              a lineage-confounded mutation with no dependencies of its own, and sister lines from one patient
  drugs       expression with latent structure, a response driven by a few biomarker genes plus lineage, a null compound
  synergy     dose–response plates with a known Bliss excess (or a sham combination of a drug with itself) and well noise
  signatures  SBS96 catalogues mixed from COSMIC signatures at known exposures, with smoking status for SBS4
  genomics    a cohort with planted mutual exclusivity, co-occurrence, copy-number → expression, a survival effect and
              an age-confounded alteration with no effect of its own
  singlecell  donors × cells counts with a planted program in one cell type of the case arm and donor-level variability
  metabolism  not planted: a what-if on Human-GEM (medium and gene knockouts), i.e. a mechanistic simulation
"""
import hashlib
import json
import math
import pathlib
import sys
import time
import types

import numpy as np

ILLUSTRATIVE = 'Synthetic data · tests the method against a planted answer; not an observation'


def _dir(root, demo, rid=''):
    return pathlib.Path(root) / 'oncology' / 'insilico' / demo / rid


def _clean(x):
    if isinstance(x, (float, np.floating)):
        return float(x) if math.isfinite(x) else None
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    if isinstance(x, np.ndarray):
        return _clean(x.tolist())
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


def check(name, expected, observed, passed, note=''):
    return {'name': name, 'expected': expected, 'observed': observed, 'passed': None if passed is None else bool(passed), 'note': note}


def _bh(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p); q = np.empty(n)
    q[o] = np.minimum.accumulate((p[o] * n / np.arange(1, n + 1))[::-1])[::-1].clip(max=1)
    return q


def _need(k, total):
    return max(1, math.ceil(2 * total / 3))


# ---------------------------------------------------------------- Demo A · dependency atlas
class _Release:
    """Duck-typed stand-in for oncology_data.Release holding synthetic matrices in memory."""
    def __init__(self, models, mats):
        self.release, self.manifest, self.models, self._m = 'synthetic', {'synthetic': True}, models, mats

    def matrix(self, name):
        if name not in self._m:
            raise ValueError(f'{name} is not part of the synthetic release.')
        return self._m[name]


def atlas(p):
    import oncology_stats as S
    rng = np.random.default_rng(p['seed']); L, n, G, delta, sis = p['lineages'], p['perLineage'], p['genes'], p['effect'], p['sisterShare']
    lins = [f'Lineage {chr(65 + i)}' for i in range(L)]
    genes = [f'SG{j:04d}' for j in range(G)]
    base = rng.normal(0, 0.12, G); idx = rng.permutation(G); nce = max(1, G // 20)
    common, sel_a, sel_b, mutdep = idx[:nce], idx[nce:nce + 3], idx[nce + 3:nce + 7], idx[nce + 7:nce + 11]
    base[common] -= 1.2
    models, rows, mut, pid = {}, [], [], 0
    patients = []
    for li, l in enumerate(lins):
        for _ in range(n):
            pid += 1; mA = rng.random() < 0.2; mB = rng.random() < (0.6 if li == 1 else 0.04)
            prof = base + rng.normal(0, 0.25, G)
            if li == 0:
                prof[sel_a] -= delta
            if li == 1:
                prof[sel_b] -= delta
            if mA:
                prof[mutdep] -= delta
            patients.append((f'SIM-PT{pid:04d}', l, prof, mA, mB))
    sisters = rng.choice(len(patients), int(round(sis * len(patients))), replace=False)
    entries = [(pt, 0) for pt in patients] + [(patients[i], 1) for i in sisters]
    for k, ((ptid, l, prof, mA, mB), sister) in enumerate(entries):
        mid = f'SIM-{k:05d}'
        models[mid] = {'ModelID': mid, 'PatientID': ptid, 'OncotreeLineage': l, 'CellLineName': f'SIM{k:05d}{"-sister" if sister else ""}', 'OncotreePrimaryDisease': f'{l} (synthetic)'}
        rows.append(prof + (rng.normal(0, 0.08, G) if sister else 0)); mut.append([float(mA), float(mB)])
    ids = list(models)
    E = np.array(rows, np.float32)
    rel = _Release(models, {'gene_effect': (E, ids, genes, {g: i for i, g in enumerate(genes)}, [None] * G),
                            'mut_hotspot': (np.array(mut, np.float32), ids, ['SIMMUT_A', 'SIMMUT_B'], {'SIMMUT_A': 0, 'SIMMUT_B': 1}, [None, None])})
    gset = lambda ix: {genes[i] for i in ix}
    ls, ma, mb = S.lineage_scan(rel, lins[0]), S.mutation_scan(rel, 'SIMMUT_A'), S.mutation_scan(rel, 'SIMMUT_B')
    sig = lambda vol: {g for g, _, nl in vol if nl > -math.log10(0.05)}
    def score(vol, planted):
        called = sig(vol); tp = len(called & planted)
        return tp, len(called) - tp, called
    tpA, fpA, _ = score(ls['volcano'], gset(sel_a)); tpM, fpM, _ = score(ma['volcano'], gset(mutdep)); _, fpB, calledB = score(mb['volcano'], set())
    # Same mutation-B contrast without the lineage term, to show what the adjustment removes.
    _, _, _, _, keep, _ = S._rows(rel, 'gene_effect'); x = np.array([mut[i][1] for i in keep]); Y = E[keep].astype(float)
    rx = x - x.mean(); ry = Y - Y.mean(0); beta = rx @ ry / (rx @ rx); res = ry - np.outer(rx, beta)
    se = np.sqrt((res ** 2).sum(0) / (len(x) - 2) / (rx @ rx)); from scipy.stats import t as T
    qn = _bh(2 * T.sf(np.abs(beta / se), len(x) - 2)); naive = {genes[j] for j in np.where(qn < 0.05)[0]}
    checks = [
        check('Sister lines collapsed to one per patient', len(sisters), ls['collapsedSamePatient'], ls['collapsedSamePatient'] == len(sisters)),
        check(f'Lineage-selective dependencies found in {lins[0]}', f'{len(sel_a)} planted', f'{tpA} found, {fpA} false', tpA >= _need(tpA, len(sel_a)) and fpA <= max(1, 0.1 * (tpA + fpA))),
        check('Dependencies linked to SIMMUT_A found (lineage-adjusted)', f'{len(mutdep)} planted', f'{tpM} found, {fpM} false', tpM >= _need(tpM, len(mutdep)) and fpM <= max(1, 0.1 * (tpM + fpM))),
        check('Lineage-confounded SIMMUT_B: no dependencies after adjustment', '0 (SIMMUT_B has no effect of its own)', f'{len(calledB)} called; {len(naive)} without lineage adjustment', fpB <= 1,
              f'SIMMUT_B is common in {lins[1]}, which has its own dependencies; the unadjusted test attributes them to the mutation.'),
    ]
    mark = lambda hits, planted: [{**h, 'planted': h['gene'] in planted} for h in hits[:15]]
    return {'title': f'Synthetic CRISPR screen · {L} lineages × {n} · {G} genes · effect {delta} · seed {p["seed"]}', 'checks': checks,
            'truth': {'commonEssential': len(common), 'lineageSelective': sorted(gset(sel_a)), 'confoundedLineageGenes': sorted(gset(sel_b)), 'mutationDependencies': sorted(gset(mutdep)),
                      'sisterLines': len(sisters), 'models': len(ids)},
            'tables': [{'title': f'Lineage scan · {lins[0]} vs rest', 'columns': ['gene', 'diff', 'q', 'planted'], 'rows': [[h['gene'], h['diff'], h['q'], h['planted']] for h in mark(ls['hits'], gset(sel_a))]},
                       {'title': 'Mutation scan · SIMMUT_A (lineage-adjusted)', 'columns': ['gene', 'beta', 'q', 'planted'], 'rows': [[h['gene'], h['beta'], h['q'], h['planted']] for h in mark(ma['hits'], gset(mutdep))]}],
            'plots': [{'kind': 'volcano', 'title': f'{lins[0]} vs other lineages', 'points': ls['volcano'], 'highlight': sorted(gset(sel_a)), 'xLabel': 'difference in gene effect'},
                      {'kind': 'volcano', 'title': 'SIMMUT_A, lineage-adjusted', 'points': ma['volcano'], 'highlight': sorted(gset(mutdep)), 'xLabel': 'β (mutant − wild type)'}],
            'model': 'gene effect = gene baseline (5 % common essentials at −1.2) + N(0, 0.25) per patient + planted shifts; sister lines = patient profile + N(0, 0.08)',
            'method': 'Demo A code unchanged: Welch lineage scan and lineage-adjusted OLS mutation scan, BH-FDR, one model per patient'}


# ---------------------------------------------------------------- Demo C · drug response
def drugs(p):
    import drug_response as R
    from scipy.stats import pearsonr
    rng = np.random.default_rng(p['seed']); N, K, r2, G = p['lines'], p['biomarkers'], p['r2'], 1500
    npat = int(N * 0.85); L = 8
    plin = rng.integers(0, L, npat); lin_mean = rng.normal(0, 0.5, (L, G)); W = rng.normal(0, 0.5, (10, G))
    Xp = lin_mean[plin] + rng.normal(0, 1, (npat, 10)) @ W + rng.normal(0, 1, (npat, G))
    owner = np.r_[np.arange(npat), rng.integers(0, npat, N - npat)]
    X = Xp[owner] + rng.normal(0, 0.2, (N, G)); lin = plin[owner]
    var_rank = np.argsort(-X.var(0)); bio = rng.choice(var_rank[:300], K, replace=False); w = rng.normal(0, 1, K)
    signal = X[:, bio] @ w; signal = (signal - signal.mean()) / signal.std()
    pnoise, lnoise = rng.normal(0, math.sqrt(0.5), npat), rng.normal(0, math.sqrt(0.5), N)       # patient-level (shared by sisters) + line-level
    noise = pnoise[owner] + lnoise; lin_eff = rng.normal(0, 0.4, L)
    y = 2.0 + math.sqrt(r2 / (1 - r2)) * signal + lin_eff[lin] + noise if r2 > 0 else 2.0 + lin_eff[lin] + noise
    ynull = 2.0 + rng.normal(0, 1, N)
    ids = [f'SIM-{i:05d}' for i in range(N)]
    models = {m: {'ModelID': m, 'PatientID': f'SIM-PT{owner[i]:04d}', 'OncotreeLineage': f'Lineage {chr(65 + lin[i])}', 'CellLineName': f'SIM{i:05d}'} for i, m in enumerate(ids)}
    genes = [f'SG{j:04d}' for j in range(G)]
    def data(models):
        d = types.SimpleNamespace(drugs={'SIM-A': {'key': 'SIM-A', 'name': 'Synthetic compound A', 'pathway': 'synthetic', 'dataset': 'synthetic', 'target': ', '.join(genes[b] for b in bio)},
                                         'SIM-NULL': {'key': 'SIM-NULL', 'name': 'Synthetic null compound', 'pathway': 'synthetic', 'dataset': 'synthetic', 'target': 'none'}},
                                  X=X, xrow={m: i for i, m in enumerate(ids)}, genes=genes, dep=types.SimpleNamespace(release='synthetic', models=models))
        d.table = lambda drug: (ids, y if drug == 'SIM-A' else ynull, 0, N)
        d.meta = lambda m, k: models.get(m, {}).get(k) or m
        return d
    a, z = R.held_out_cell_lines(None, 'SIM-A', d=data(models)), R.held_out_cell_lines(None, 'SIM-NULL', d=data(models))
    leaky = R.held_out_cell_lines(None, 'SIM-A', d=data({m: {**v, 'PatientID': m} for m, v in models.items()}))
    ceiling = float(pearsonr(y, (math.sqrt(r2 / (1 - r2)) * signal if r2 > 0 else 0) + lin_eff[lin])[0])
    rr, nr = a['results']['ridge'].get('pearson', 0.0), z['results']['ridge'].get('pearson', 0.0)
    inside = 'see note'
    checks = [
        check('Grouped split keeps sister lines on one side', 0, a['leakage']['patientsSharedAcrossFolds'], a['leakage']['patientsSharedAcrossFolds'] == 0),
        check('Ridge recovers most of the attainable signal', f'Pearson ≤ {ceiling:.2f} (noise ceiling)', f'{rr:.2f}', 0.6 * ceiling <= rr <= ceiling + 0.05,
              'The ceiling is the correlation of the response with its planted, noise-free part; no model can exceed it on average.'),
        check('Ridge beats the lineage-mean baseline', f'> {a["results"]["lineage"].get("pearson", 0):.2f}', f'{rr:.2f}', rr > a['results']['lineage'].get('pearson', 0) if r2 > 0 else None),
        check('No skill on the null compound', '|Pearson| < 0.15', f'{nr:.2f}', abs(nr) < 0.15, 'Its response is pure noise, so any apparent skill would be overfitting or leakage.'),
        check('Effect of splitting by cell line instead of patient', 'informational', f'ridge Pearson {leaky["results"]["ridge"].get("pearson", 0):.2f} ungrouped vs {rr:.2f} grouped', None,
              f'{leaky["leakage"]["patientsSharedAcrossFolds"]} patients straddled folds in the ungrouped split; sisters share a patient-level response component the expression does not explain.'),
    ]
    tab = lambda r: [[k, v.get('pearson'), v.get('spearman'), v.get('rmse'), v.get('coverage90')] for k, v in r['results'].items()]
    return {'title': f'Synthetic drug screen · {N} lines · {K} biomarkers · R² {r2} · seed {p["seed"]}', 'checks': checks,
            'truth': {'biomarkers': [genes[b] for b in bio], 'weights': w.round(3).tolist(), 'plantedR2': r2, 'noiseCeilingPearson': ceiling, 'patients': npat, 'sisterLines': N - npat},
            'tables': [{'title': 'Synthetic compound A · held-out patients', 'columns': ['model', 'Pearson', 'Spearman', 'RMSE', '90 % coverage'], 'rows': tab(a)},
                       {'title': 'Null compound · held-out patients', 'columns': ['model', 'Pearson', 'Spearman', 'RMSE', '90 % coverage'], 'rows': tab(z)}],
            'plots': [{'kind': 'scatter', 'title': 'Compound A · observed vs ridge prediction (held out)', 'points': [[q[3], q[4]] for q in a['points']], 'xLabel': 'observed (synthetic LN_IC50)', 'yLabel': 'predicted'},
                      {'kind': 'scatter', 'title': 'Null compound · observed vs ridge prediction', 'points': [[q[3], q[4]] for q in z['points']], 'xLabel': 'observed', 'yLabel': 'predicted'}],
            'model': 'expression = lineage mean + 10 latent factors + noise (sisters: + N(0, 0.2)); response = biomarker signal (planted R² of the non-lineage part) + lineage offset + patient noise shared by sisters + line noise',
            'method': 'Demo C code unchanged: 5-fold split by patient, top-500 variable genes and standardisation fitted inside each training fold, inner grouped CV for the penalty'}


# ---------------------------------------------------------------- Synergy
def synergy(p):
    import synergy as Y
    rng = np.random.default_rng(p['seed']); kind, delta, plates, noise = p['interaction'], p['delta'], p['plates'], p['noise'] / 100
    ca = cb = 10.0 ** np.linspace(-8, -5, 5)
    hill = lambda c, q: Y._hill(c, *q)
    qa = np.array([10 ** rng.uniform(-7.2, -6.2), rng.uniform(0.8, 2.0), rng.uniform(0.75, 0.95)])
    qb = qa.copy() if kind == 'sham' else np.array([10 ** rng.uniform(-7.2, -6.2), rng.uniform(0.8, 2.0), rng.uniform(0.75, 0.95)])
    Ea, Eb = hill(ca, qa), hill(cb, qb)
    bliss = Ea[:, None] + Eb[None, :] - Ea[:, None] * Eb[None, :]
    if kind == 'sham':
        E0 = np.array([[hill(np.array([a + b]), qa)[0] for b in cb] for a in ca])           # a drug combined with itself is dose-additive
    else:
        shape = bliss * (1 - bliss); shape /= shape.mean()                              # vanishes at 0 and 100 % inhibition, so little is clipped
        E0 = np.clip(bliss + {'synergy': 1, 'none': 0, 'antagonism': -1}[kind] * delta / 100 * shape, 0, 1)
    def plate(E, ea, eb):
        G, ga, gb = 100 * (1 - E), 100 * (1 - ea), 100 * (1 - eb)
        nci = np.array([[Y.nci_expected(x, y) for y in gb] for x in ga]) - G
        return {'ca': list(ca), 'cb': list(cb), 'E': E, 'Ea': ea, 'Eb': eb, 'G': G, 'nci': nci}
    truth, _, _ = Y.score_plates([plate(E0, Ea, Eb)], qa, qb)
    per, pool_a, pool_b = [], ([], []), ([], [])
    for _ in range(plates):
        ea, eb = np.clip(Ea + rng.normal(0, noise, 5), 0, 1), np.clip(Eb + rng.normal(0, noise, 5), 0, 1)
        E = np.clip(E0 + rng.normal(0, noise, E0.shape), 0, 1); per.append(plate(E, ea, eb))
        pool_a[0].extend(ca); pool_a[1].extend(ea); pool_b[0].extend(cb); pool_b[1].extend(eb)
    pa, pb = Y._fit_hill(*pool_a), Y._fit_hill(*pool_b)
    summary, surfaces, undefined = Y.score_plates(per, pa, pb)
    checks = []
    for k in ('Bliss', 'Loewe', 'HSA', 'ZIP'):
        if k in summary and k in truth:
            s, t = summary[k], truth[k]['mean']; ok = s['ci'][0] <= t <= s['ci'][1] if all(math.isfinite(v) for v in s['ci']) else None
            checks.append(check(f'{k}: interval covers the noise-free score', f'{t:+.1f} pp', f'{s["mean"]:+.1f} pp [{s["ci"][0]:+.1f}, {s["ci"][1]:+.1f}] · {s["call"]}', ok))
    if kind == 'sham':
        lo = summary.get('Loewe')
        checks.append(check('Sham combination: Loewe calls no interaction', 'consistent with no interaction', lo['call'] if lo else 'undefined', lo and lo['call'] == 'consistent with no interaction',
                            'Loewe additivity is defined so a drug combined with itself scores zero; Bliss is not, so it can call a sham "synergy" or "antagonism" depending on the Hill slope.'))
    elif kind != 'none':
        b = summary.get('Bliss'); want = 'synergy' if kind == 'synergy' else 'antagonism'
        checks.append(check('Bliss call matches the planted direction', want, b['call'] if b else '—', b and b['call'] == want))
    else:
        b = summary.get('Bliss')
        checks.append(check('No planted interaction: Bliss calls none', 'consistent with no interaction', b['call'] if b else '—', b and b['call'] == 'consistent with no interaction'))
    return {'title': f'Synthetic combination · {kind}{"" if kind in ("none", "sham") else f" {delta} pp"} · {plates} plates · noise {p["noise"]} pp · seed {p["seed"]}', 'checks': checks,
            'truth': {'interaction': kind, 'plantedBlissExcessPP': None if kind == 'sham' else {'synergy': 1, 'none': 0, 'antagonism': -1}[kind] * delta,
                      'hillA': {'ec50M': qa[0], 'slope': qa[1], 'emax': qa[2]}, 'hillB': {'ec50M': qb[0], 'slope': qb[1], 'emax': qb[2]},
                      'noiseFreeScores': {k: v['mean'] for k, v in truth.items()}},
            'tables': [{'title': 'Scores over plates (percentage points of inhibition)', 'columns': ['model', 'estimate', '95 % CI low', '95 % CI high', 'call', 'noise-free value'],
                        'rows': [[k, v['mean'], v['ci'][0], v['ci'][1], v['call'], truth.get(k, {}).get('mean')] for k, v in summary.items()]}],
            'plots': [{'kind': 'heatmap', 'title': 'Observed inhibition (mean of plates)', 'matrix': np.mean([r['E'] for r in per], 0).round(3).tolist(), 'rows': [f'{c:.0e}' for c in ca], 'cols': [f'{c:.0e}' for c in cb], 'rowLabel': 'drug A (M)', 'colLabel': 'drug B (M)', 'diverging': False},
                      {'kind': 'heatmap', 'title': 'Bliss excess (mean of plates)', 'matrix': surfaces.get('Bliss'), 'rows': [f'{c:.0e}' for c in ca], 'cols': [f'{c:.0e}' for c in cb], 'rowLabel': 'drug A (M)', 'colLabel': 'drug B (M)', 'diverging': True}],
            'loeweUndefined': undefined,
            'model': 'single agents: Hill curves; combination: Bliss expectation + planted excess shaped ∝ Bliss·(1 − Bliss) (mean = planted value before clipping at 100 %), or dose addition for a sham; Gaussian well noise; 5 × 5 doses',
            'method': 'Synergy demo code unchanged: per-plate HSA, Bliss, Loewe (Hill fits pooled over plates) and ZIP; 95 % t-interval over plates'}


# ---------------------------------------------------------------- Mutational signatures
SIG_SCENARIOS = {
    'lung-smoking': {'label': 'lung, smokers and never-smokers', 'mix': [('SBS1', 1.0, 1), ('SBS5', 1.0, 2), ('SBS4', 'smoker', 4), ('SBS2', 0.3, 1.5), ('SBS13', 0.3, 1.5)]},
    'mmr-deficient': {'label': 'mismatch-repair deficient colorectal', 'mix': [('SBS1', 1.0, 2), ('SBS5', 1.0, 1), ('SBS6', 0.6, 3), ('SBS15', 0.4, 2), ('SBS44', 0.4, 2)]},
    'uv-melanoma': {'label': 'UV-exposed melanoma', 'mix': [('SBS7a', 1.0, 4), ('SBS7b', 0.9, 2), ('SBS5', 1.0, 1), ('SBS1', 0.5, 0.5)]},
    'apobec-breast': {'label': 'breast with APOBEC and HR deficiency', 'mix': [('SBS1', 1.0, 1), ('SBS5', 1.0, 1), ('SBS2', 0.7, 2), ('SBS13', 0.7, 2), ('SBS3', 0.3, 2)]},
}


def signatures(p, root):
    import mutational_signatures as M
    from scipy.stats import mannwhitneyu
    rng = np.random.default_rng(p['seed']); sc = SIG_SCENARIOS[p['scenario']]; N, med = p['samples'], p['snvs']
    names, sigs = M.reference(types.SimpleNamespace(root=root)); ni = {n: i for i, n in enumerate(names)}
    rows, smokers = [], rng.random(N) < 0.7
    for i in range(N):
        present = [(s, a) for s, prev, a in sc['mix'] if (smokers[i] if prev == 'smoker' else rng.random() < prev)]
        w = rng.dirichlet([a for _, a in present]); n = max(20, int(rng.lognormal(math.log(med), 0.8)))
        x = rng.multinomial(n, sigs[:, [ni[s] for s, _ in present]] @ w / (sigs[:, [ni[s] for s, _ in present]] @ w).sum())
        rows.append({'truth': dict(zip([s for s, _ in present], w)), 'x': x, 'smoker': bool(smokers[i])})
    fitted, burden = [], []
    for r in rows:
        if r['x'].sum() < 50:
            r['fit'] = None; continue
        ex, cos = M.fit_one(r['x'], sigs, names); r['fit'] = {e['signature']: e for e in ex}; r['cos'] = cos
    done = [r for r in rows if r['fit'] is not None]
    for r in done:
        t, f = r['truth'], r['fit']
        big = [s for s, v in t.items() if v >= 0.1]
        r['sens'] = np.mean([s in f for s in big]) if big else np.nan
        r['false'] = sum(e['fraction'] for s, e in f.items() if s not in t)
        r['mae'] = np.mean([abs(t.get(s, 0) - (f[s]['fraction'] if s in f else 0)) for s in set(t) | set(f)])
        cov = [f[s]['ci'][0] <= t[s] <= f[s]['ci'][1] for s in t if s in f]; r['cov'] = cov
    sens, false = np.nanmean([r['sens'] for r in done]), np.median([r['false'] for r in done])
    cov = [c for r in done for c in r['cov']]
    tert = np.quantile([r['x'].sum() for r in done], [1 / 3, 2 / 3]) if done else [0, 0]
    band = lambda r: 0 if r['x'].sum() <= tert[0] else 1 if r['x'].sum() <= tert[1] else 2
    burden = [[['lowest', 'middle', 'highest'][b] + ' third', int(min(r['x'].sum() for r in done if band(r) == b)), int(max(r['x'].sum() for r in done if band(r) == b)),
               float(np.nanmean([r['sens'] for r in done if band(r) == b])), float(np.median([r['false'] for r in done if band(r) == b])), float(np.mean([r['mae'] for r in done if band(r) == b]))]
              for b in range(3) if any(band(r) == b for r in done)]
    checks = [check('Signatures with ≥ 10 % exposure recovered', '≥ 80 % of them', f'{sens:.0%}', sens >= 0.8),
              check('Exposure assigned to absent signatures (median per sample)', '≤ 10 %', f'{false:.1%}', false <= 0.1),
              check('Bootstrap 95 % intervals contain the true exposure', 'about 95 %', f'{np.mean(cov):.0%} of {len(cov)}' if cov else '—', None,
                    'Multinomial bootstraps capture sampling noise only, not signature misattribution, so coverage below 95 % is expected when similar signatures compete.')]
    if p['scenario'] == 'lung-smoking':
        sm = [r['fit'].get('SBS4', {}).get('fraction', 0.0) for r in done if r['smoker']]; nv = [r['fit'].get('SBS4', {}).get('fraction', 0.0) for r in done if not r['smoker']]
        pv = mannwhitneyu(sm, nv, alternative='greater').pvalue if len(sm) >= 5 and len(nv) >= 5 else float('nan')
        checks.append(check('SBS4 higher in smokers (Demo B smoking check, same test)', 'p < 0.01', f'p = {pv:.1e}; median {np.median(sm):.0%} vs {np.median(nv):.0%}', pv < 0.01))
    sigs_all = sorted({s for r in done for s in list(r['truth']) + list(r['fit'])}, key=lambda s: -np.mean([r['truth'].get(s, 0) for r in done]))
    return {'title': f'Synthetic catalogues · {sc["label"]} · {N} samples · median {med} SNVs · seed {p["seed"]}', 'checks': checks,
            'truth': {'scenario': sc['label'], 'mix': [{'signature': s, 'prevalence': prev, 'dirichletWeight': a} for s, prev, a in sc['mix']], 'fitted': len(done), 'tooFewSNVs': N - len(done)},
            'tables': [{'title': 'Recovery by mutation burden', 'columns': ['burden', 'min SNVs', 'max SNVs', 'recovered (≥10 %)', 'false exposure (median)', 'mean abs. error'], 'rows': burden},
                       {'title': 'Cohort mean exposure', 'columns': ['signature', 'planted', 'fitted', 'planted in scenario'],
                        'rows': [[s, float(np.mean([r['truth'].get(s, 0) for r in done])), float(np.mean([r['fit'][s]['fraction'] if s in r['fit'] else 0 for r in done])), any(s == m[0] for m in sc['mix'])] for s in sigs_all]}],
            'plots': [{'kind': 'bars', 'title': 'Mean exposure: planted vs fitted', 'labels': sigs_all, 'series': [{'name': 'planted', 'values': [float(np.mean([r['truth'].get(s, 0) for r in done])) for s in sigs_all]},
                                                                                                          {'name': 'fitted', 'values': [float(np.mean([r['fit'][s]['fraction'] if s in r['fit'] else 0 for r in done])) for s in sigs_all]}]}],
            'model': 'per sample: signatures present by prevalence (SBS4 only in smokers, 70 % of samples), exposures ~ Dirichlet, SNV count ~ lognormal(median, 0.8), counts ~ multinomial over COSMIC v3.4 exome SBS96',
            'method': 'Signature demo code unchanged: NNLS + backward elimination, artefact signatures excluded, 100 multinomial bootstraps; samples under 50 SNVs not fitted'}


# ---------------------------------------------------------------- Demo B · cohort genomics
def genomics(p):
    import cancer_genomics as G
    rng = np.random.default_rng(p['seed']); N, hr = p['patients'], p['hr']
    age = np.clip(rng.normal(62, 10, N), 30, 90)
    kras = rng.random(N) < 0.30
    egfr = np.where(kras, rng.random(N) < 0.02, rng.random(N) < 0.214)
    stk11 = np.where(kras, rng.random(N) < 0.35, rng.random(N) < 0.08)
    tp53 = rng.random(N) < 0.45
    atm = rng.random(N) < 1 / (1 + np.exp(2.2 - 0.08 * (age - 62)))
    myc = rng.random(N) < 0.12; cdkn2a = rng.random(N) < 0.20
    passengers = {f'SIMPASS{j:02d}': rng.random(N) < rng.uniform(0.03, 0.12) for j in range(1, 9)}
    muts = {'KRAS': kras, 'EGFR': egfr, 'STK11': stk11, 'TP53': tp53, 'ATM': atm, **passengers}
    genes = {g: 90000 + i for i, g in enumerate(['KRAS', 'EGFR', 'STK11', 'TP53', 'ATM', 'MYC', 'CDKN2A', *passengers])}
    c = G._Cohort.__new__(G._Cohort)
    sids = [f'SIM-P{i:04d}-01' for i in range(N)]; pids = [f'SIM-P{i:04d}' for i in range(N)]
    c.manifest = {'studyId': 'synthetic', 'name': 'Synthetic cohort', 'synthetic': True}; c.profiled = sorted(sids); c.P = set(sids)
    c.sample_patient = dict(zip(sids, pids)); c.genes = genes; c.builds = {'GRCh37': 0}; c.recurrent = set(); c.muts, c.cna, c.mrna = [], {}, {}
    pos = {'KRAS': lambda: 12, 'EGFR': lambda: 858, 'STK11': lambda: int(rng.integers(1, 433)), 'TP53': lambda: int(rng.choice([175, 248, 273, int(rng.integers(1, 393))]))}
    for g, v in muts.items():
        for i in np.where(v)[0]:
            c.muts.append({'sampleId': sids[i], 'patientId': pids[i], 'gene': g, 'entrezGeneId': genes[g], 'proteinPosStart': pos.get(g, lambda: int(rng.integers(1, 2000)))(),
                           'mutationType': 'Missense_Mutation' if g in ('KRAS', 'EGFR') or rng.random() < 0.6 else 'Nonsense_Mutation', 'ncbiBuild': 'GRCh37'})
    c.builds['GRCh37'] = len(c.muts)
    mrna_null = rng.normal(0, 1, N)
    for i, sm in enumerate(sids):
        c.cna[(sm, 'MYC')] = 2 if myc[i] else int(rng.choice([0, 0, 0, 1, -1])); c.cna[(sm, 'CDKN2A')] = -2 if cdkn2a[i] else int(rng.choice([0, 0, 0, -1, 1]))
        c.cna[(sm, 'SIMPASS01')] = int(rng.choice([-2, -1, 0, 0, 0, 0, 1, 2]))
        c.mrna[(sm, 'MYC')] = 0.5 * c.cna[(sm, 'MYC')] + (1.0 if myc[i] else 0) + rng.normal(0, 1); c.mrna[(sm, 'CDKN2A')] = -1.5 * cdkn2a[i] + rng.normal(0, 1); c.mrna[(sm, 'SIMPASS01')] = mrna_null[i]
    pos_count = {}
    for m in c.muts:
        pos_count.setdefault((m['gene'], m['proteinPosStart']), set()).add(m['sampleId'])
    c.recurrent = {k for k, v in pos_count.items() if len(v) >= 3}
    c.mut_by, c.cna_by = {}, {}
    for m in c.muts:
        c.mut_by.setdefault(m['gene'], []).append(m)
    for (sm, g), a in c.cna.items():
        if a in (2, -2):
            c.cna_by.setdefault(g, []).append((sm, a))
    tmb = rng.lognormal(math.log(6), 0.8, N)
    c.sclin = {sm: {'TMB_NONSYNONYMOUS': str(round(tmb[i], 2))} for i, sm in enumerate(sids)}
    hz = 0.012 * np.exp(math.log(hr) * stk11 + math.log(1.3) * (age - 62) / 10)
    t_ev, t_c = rng.exponential(1 / hz), rng.uniform(6, 120, N); t = np.minimum(t_ev, t_c); ev = t_ev <= t_c
    c.pclin = {pid: {'AGE': str(round(age[i], 1)), 'OS_MONTHS': str(round(t[i], 2)), 'OS_STATUS': '1:DECEASED' if ev[i] else '0:LIVING'} for i, pid in enumerate(pids)}
    test = ['KRAS', 'EGFR', 'STK11', 'TP53', 'ATM', *list(passengers)[:5]]
    pr = G.pairs(None, None, test, c=c); summ = G.summary(None, None, c=c)
    planted = {frozenset(('KRAS', 'EGFR')): 'exclusive', frozenset(('KRAS', 'STK11')): 'co-occurring', frozenset(('EGFR', 'STK11')): 'induced'}
    pick = lambda a, b: next(r for r in pr['pairs'] if {r['a'], r['b']} == {a, b})
    ke, ks = pick('KRAS', 'EGFR'), pick('KRAS', 'STK11')
    nulls = [r for r in pr['pairs'] if frozenset((r['a'], r['b'])) not in planted]; null_calls = [r for r in nulls if r['q'] < 0.05]
    em, en = G.expression_by_cna(None, None, 'MYC', c=c), G.expression_by_cna(None, None, 'SIMPASS01', c=c)
    sv = {g: G.survival(None, None, g, 'OS', c=c) for g in ('STK11', 'ATM', 'TP53')}
    cox = lambda g: sv[g]['cox'][0]
    checks = [
        check('KRAS–EGFR mutual exclusivity detected', 'q < 0.05, log2 OR < 0', f'q = {ke["q"]:.1e}, log2 OR = {ke["log2OR"]:.2f}', ke['q'] < 0.05 and ke['log2OR'] < 0),
        check('KRAS–STK11 co-occurrence detected', 'q < 0.05, log2 OR > 0', f'q = {ks["q"]:.1e}, log2 OR = {ks["log2OR"]:.2f}', ks['q'] < 0.05 and ks['log2OR'] > 0),
        check('Independent pairs not called', f'≤ 1 of {len(nulls)}', f'{len(null_calls)} called', len(null_calls) <= 1,
              'EGFR–STK11 is excluded from this set: both depend on KRAS, so they are associated by construction without interacting.'),
        check('MYC amplification raises MYC expression', 'ρ > 0, p < 0.05', f'ρ = {em["spearman"]:.2f}, p = {em["p"]:.1e}', em['spearman'] > 0 and em['p'] < 0.05),
        check('Copy number of a null gene does not track expression', 'p ≥ 0.05 (fails 1 in 20 by chance)', f'ρ = {en["spearman"]:.2f}, p = {en["p"]:.2f}', en['p'] >= 0.05),
        check('STK11 hazard ratio interval covers the planted value', f'HR {hr}', f'HR {cox("STK11")["hr"]:.2f} [{cox("STK11")["ci"][0]:.2f}, {cox("STK11")["ci"][1]:.2f}]', cox('STK11')['ci'][0] <= hr <= cox('STK11')['ci'][1]),
        check('Age-confounded ATM: no effect after adjusting for age', 'HR 1 inside the Cox interval', f'HR {cox("ATM")["hr"]:.2f} [{cox("ATM")["ci"][0]:.2f}, {cox("ATM")["ci"][1]:.2f}]; unadjusted log-rank p = {sv["ATM"]["logrank"]["p"]:.1e}',
              cox('ATM')['ci'][0] <= 1 <= cox('ATM')['ci'][1], 'ATM alteration is more common in older patients and age raises the hazard, so the unadjusted log-rank test can show a spurious association.'),
        check('TP53 (no planted effect) not associated with survival', 'HR 1 inside the interval', f'HR {cox("TP53")["hr"]:.2f} [{cox("TP53")["ci"][0]:.2f}, {cox("TP53")["ci"][1]:.2f}]', cox('TP53')['ci'][0] <= 1 <= cox('TP53')['ci'][1]),
    ]
    return {'title': f'Synthetic cohort · {N} patients · STK11 HR {hr} · seed {p["seed"]}', 'checks': checks,
            'truth': {'exclusive': 'KRAS–EGFR', 'coOccurring': 'KRAS–STK11', 'survival': f'STK11 HR {hr}; age HR 1.3 per 10 years; ATM, TP53 HR 1', 'ageConfounded': 'ATM', 'cnaExpression': 'MYC amplified (12 %) with higher mRNA'},
            'tables': [{'title': 'Pairwise co-occurrence and exclusivity', 'columns': ['pair', 'both', 'log2 OR', 'q', 'planted'], 'rows': [[f'{r["a"]}–{r["b"]}', r['both'], r['log2OR'], r['q'], planted.get(frozenset((r['a'], r['b'])), 'independent')] for r in pr['pairs'][:15]]},
                       {'title': 'Survival (Cox, adjusted for age)', 'columns': ['gene', 'altered', 'HR', 'CI low', 'CI high', 'log-rank p (unadjusted)'],
                        'rows': [[g, v['altered'], v['cox'][0]['hr'], v['cox'][0]['ci'][0], v['cox'][0]['ci'][1], v['logrank']['p']] for g, v in sv.items()]},
                       {'title': 'Most altered genes', 'columns': ['gene', 'altered', 'frequency', 'recurrent positions'], 'rows': [[r['gene'], r['altered'], r['freq'], r['recurrent']] for r in summ['genes'][:12]]}],
            'plots': [{'kind': 'km', 'title': f'STK11 (planted HR {hr})', 'curves': sv['STK11']['km']}, {'kind': 'km', 'title': 'ATM (no effect; confounded by age)', 'curves': sv['ATM']['km']}],
            'model': 'one tumor sample per patient; alteration probabilities with planted dependencies; exponential survival with STK11 and age effects; uniform censoring 6–120 months',
            'method': 'Demo B code unchanged: Fisher exact pairs with BH-FDR, Spearman CNA vs mRNA, Kaplan–Meier, log-rank and age-adjusted Cox'}


# ---------------------------------------------------------------- Demo D · single cell (single-cell runtime)
SC_PROGRAMS = {'proliferation (E2F targets)': 'HALLMARK_E2F_TARGETS', 'interferon-γ response': 'HALLMARK_INTERFERON_GAMMA_RESPONSE',
               'hypoxia': 'HALLMARK_HYPOXIA', 'epithelial–mesenchymal transition': 'HALLMARK_EPITHELIAL_MESENCHYMAL_TRANSITION'}


def singlecell(p, root, out_dir):
    import anndata as ad, pandas as pd, scipy.sparse as sp
    import singlecell_tumor as ST
    gmt = pathlib.Path(root) / 'oncology' / 'genesets' / 'h.all.v2025.1.Hs.symbols.gmt'
    if not gmt.is_file():
        raise SystemExit('The MSigDB Hallmark gene sets are not installed (Single-cell tab).')
    sets = {l.split('\t')[0]: l.rstrip('\n').split('\t')[2:] for l in gmt.read_text().splitlines()}
    rng = np.random.default_rng(p['seed']); prog = SC_PROGRAMS[p['program']]
    mt = [f'MT-{g}' for g in ('ND1', 'ND2', 'CO1', 'CO2', 'ATP8', 'ATP6', 'CO3', 'ND3', 'ND4L', 'ND4', 'ND5', 'ND6', 'CYB')]
    genes = sorted({g for v in sets.values() for g in v}) + mt; gi = {g: i for i, g in enumerate(genes)}; G = len(genes)
    members = [g for g in sets[prog] if g in gi]; planted = set(rng.choice(members, int(0.6 * len(members)), replace=False))
    logbase = rng.normal(0, 1.4, G); logbase[[gi[g] for g in mt]] = np.log(np.exp(logbase).sum() * 0.05 / len(mt))
    types_ = {'keratinocyte': ['KRT5', 'KRT14', 'KRT17'], 'T cell': ['CD3E', 'CD2', 'IL7R'], 'fibroblast': ['COL1A1', 'COL1A2', 'DCN']}
    type_shift = {t: np.zeros(G) for t in types_}
    for t, mk in types_.items():
        for g in mk:
            if g in gi:
                type_shift[t][gi[g]] = 3.0
    eff = np.zeros(G); eff[[gi[g] for g in planted]] = p['effect'] * math.log(2)
    X, obs = [], []
    for arm in ('carcinoma', 'normal'):
        for d in range(p['donors']):
            donor = f'{arm[:1].upper()}{d + 1:02d}'; dshift = rng.normal(0, p['donorSd'], G)          # biological donor-to-donor variability
            frac = rng.dirichlet([6, 2, 2]); n = rng.poisson(p['cells'])
            for t, k in zip(types_, rng.multinomial(n, frac)):
                mu = logbase + type_shift[t] + dshift + (eff if (arm == 'carcinoma' and t == 'keratinocyte') else 0)
                prob = np.exp(mu); prob /= prob.sum()
                lib = rng.lognormal(math.log(3000), 0.35, k)
                lam = rng.gamma(1 / 0.3, (lib[:, None] * prob[None, :]) * 0.3)
                X.append(sp.csr_matrix(rng.poisson(lam).astype(np.float32))); obs += [{'donor_id': donor, 'cell_type': t, 'disease': arm}] * k
    A = ad.AnnData(sp.vstack(X).tocsr(), obs=pd.DataFrame(obs, index=[f'cell{i}' for i in range(len(obs))]).astype('category'), var=pd.DataFrame({'feature_name': genes}, index=genes))
    out_dir.mkdir(parents=True, exist_ok=True); A.write_h5ad(out_dir / 'dataset.h5ad'); print(f'generated {A.n_obs} cells × {G} genes', flush=True)
    ST.main(str(out_dir / 'dataset.h5ad'), str(out_dir / 'analysis.json'), str(gmt), 'keratinocyte', 'disease', 'carcinoma', 'normal')
    r = json.loads((out_dir / 'analysis.json').read_text())
    called = {v[0] for v in r['volcano'] if v[2] > -math.log10(0.05)}; tested = {v[0] for v in r['volcano']}
    mod = {v[0] for v in r['volcano'] if len(v) > 3 and v[3] > -math.log10(0.05)}
    tp, fp = len(called & planted), len(called - planted); pt = len(planted & tested); tpm, fpm = len(mod & planted), len(mod - planted)
    pw = r['pathways']; rank = next((i + 1 for i, x in enumerate([x for x in pw if x['direction'] == 'up in case']) if x['set'] == prog), None)
    hit = next((x for x in pw if x['set'] == prog), None)
    checks = [
        check('Planted genes found · Welch t on donor pseudobulk (primary)', f'{pt} planted and tested', f'{tp} found ({tp / max(pt, 1):.0%}), {fp} false', None,
              'Power, not a pass/fail: with few donors per arm and thousands of genes, per-gene Welch tests after BH correction detect only large effects.'),
        check('Planted genes found · moderated t (sensitivity analysis)', f'{pt} planted and tested', f'{tpm} found ({tpm / max(pt, 1):.0%}), {fpm} false', None,
              'The empirical-Bayes moderated t borrows variance information across genes, which raises power at small donor numbers.'),
        check('False discoveries among called genes (both tests)', '≤ 10 %', f'Welch {fp} of {len(called)}; moderated {fpm} of {len(mod)}',
              fp <= max(1, 0.1 * len(called)) and fpm <= max(1, 0.1 * len(mod))),
        check(f'{prog.replace("HALLMARK_", "").replace("_", " ").title()} is the top up-regulated pathway', 'rank 1, q < 0.05', f'rank {rank}, q = {hit["q"]:.1e}' if hit else 'not in the top 25',
              rank == 1 and hit and hit['q'] < 0.05, 'Hallmark sets overlap; a set sharing many planted genes can rank close behind.'),
        check('Cell-level test over-calls (pseudoreplication)', 'many more calls than the donor-level test', f'{r["significantNaiveCellLevel"]} cell-level vs {r["significantDonorLevel"]} donor-level; {len(planted)} planted', None,
              'Cells from one donor are not independent; donor-to-donor variability makes the naive test call genes that differ only between donors.'),
        check('Clusters agree with the true cell types', 'ARI near 1', f'ARI {r["annotation"]["ari"]:.2f}', None),
    ]
    return {'title': f'Synthetic single-cell · {p["program"]} · {p["donors"]}+{p["donors"]} donors · log2FC {p["effect"]} · seed {p["seed"]}', 'checks': checks,
            'truth': {'program': prog, 'plantedGenes': len(planted), 'log2FC': p['effect'], 'donorSd': p['donorSd'], 'cellType': 'keratinocyte'},
            'tables': [{'title': 'Top donor-level hits', 'columns': ['gene', 'log2FC', 'q', 'q moderated', 'planted'], 'rows': [[d['gene'], d['log2FC'], d['q'], d['qModerated'], d['gene'] in planted] for d in r['de'][:20]]},
                       {'title': 'Pathways', 'columns': ['set', 'direction', 'q', 'planted'], 'rows': [[x['set'], x['direction'], x['q'], x['set'] == prog] for x in pw[:10]]}],
            'plots': [{'kind': 'volcano', 'title': 'Donor-level pseudobulk, keratinocytes', 'points': [v[:3] for v in r['volcano']], 'highlight': sorted(planted), 'xLabel': 'log2 fold change (carcinoma vs normal)'},
                      {'kind': 'embedding', 'title': 'UMAP · true cell type', 'x': r['embedding']['x'], 'y': r['embedding']['y'], 'groups': r['embedding']['cellType']}],
            'model': 'counts ~ gamma-Poisson (dispersion 0.3) around cell-type profiles; donor shift N(0, donorSd) per gene; planted program up in carcinoma keratinocytes only; 5 % mitochondrial reads',
            'method': 'Demo D code unchanged: per-donor QC, Harmony, Leiden, donor pseudobulk Welch and moderated t, Hallmark rank test'}


# ---------------------------------------------------------------- Demo F · metabolism what-if (COBRA runtime)
def metabolism(p, root):
    import csv
    import cobra
    import metabolism as MB
    d = pathlib.Path(root) / 'oncology' / 'metabolism' / 'Human-GEM-v2.1.1'
    if not (d / 'Human-GEM.json').is_file():
        raise SystemExit('Install Human-GEM in the Metabolism tab first.')
    m = cobra.io.load_json_model(str(d / 'Human-GEM.json'))
    sym = {}
    with open(d / 'genes.tsv') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            s = (row.get('geneSymbols') or '').split(';')[0]
            if s:
                sym.setdefault(s.upper(), []).append(row['genes'])
    ko = [g.strip().upper() for g in p['knockouts'].replace(';', ',').split(',') if g.strip()][:10]
    unknown = [g for g in ko if g not in sym or not any(gid in m.genes for gid in sym[g])]
    o2 = 1000.0 if p['oxygen'] >= 1000 else float(p['oxygen'])
    def run(block):
        with m:
            MB.set_medium(m, MB.HAMS + MB.SERUM, glucose=p['glucose'], oxygen=o2)
            for g in block:
                for gid in sym.get(g, []):
                    if gid in m.genes:
                        m.genes.get_by_id(gid).knock_out()
            m.objective = MB.BIOMASS; sol = m.optimize()
            growth = sol.objective_value if sol.status == 'optimal' else 0.0
            ex = {r.name.replace('Exchange of ', ''): float(sol.fluxes[r.id]) for r in m.exchanges if sol.status == 'optimal' and abs(sol.fluxes[r.id]) > 1e-6}
            dead = [r.id for r in m.reactions if r.bounds == (0.0, 0.0)]
        return growth, ex, dead
    wt, wex, wdead = run([]); kg, kex, kdead = run([g for g in ko if g not in unknown])
    each = []
    for g in ko:
        if g in unknown:
            continue
        gr, _, dd = run([g]); each.append([g, len(set(dd) - set(wdead)), gr, gr / wt if wt > 0 else None])
    flux_rows = sorted({k for k in list(wex) + list(kex)}, key=lambda k: -abs(wex.get(k, 0) - kex.get(k, 0)))[:15]
    checks = [check('Wild type grows in this medium', 'growth > 0', f'{wt:.4f}', wt > 1e-6, 'Glucose and oxygen bounds are relative units (glucose = 1 is the default).'),
              check('Genes found in Human-GEM', ', '.join(ko) or 'none', 'all found' if not unknown else 'not in model: ' + ', '.join(unknown), not unknown if ko else None)]
    return {'title': f'Human-GEM what-if · glucose {p["glucose"]} · O₂ {"unlimited" if o2 >= 1000 else o2} · KO {", ".join(ko) or "none"}', 'checks': checks,
            'truth': None, 'evidenceOverride': 'Mechanistic simulation (stoichiometric constraint model; no planted answer)',
            'summary': {'wildTypeGrowth': wt, 'knockoutGrowth': kg, 'ratio': kg / wt if wt > 0 else None},
            'tables': [{'title': 'Knockouts, one at a time', 'columns': ['gene', 'reactions blocked', 'growth', 'relative to wild type'], 'rows': each},
                       {'title': 'Exchange fluxes that change most (negative = uptake)', 'columns': ['metabolite', 'wild type', 'all knockouts'], 'rows': [[k, wex.get(k, 0.0), kex.get(k, 0.0)] for k in flux_rows]}],
            'plots': [{'kind': 'bars', 'title': 'Growth relative to wild type', 'labels': ['wild type', *[r[0] for r in each], *(['all together'] if len(each) > 1 else [])],
                       'series': [{'name': 'growth', 'values': [1.0, *[r[3] or 0 for r in each], *([kg / wt if wt > 0 else 0] if len(each) > 1 else [])]}]}],
            'model': "Human-GEM v2.1.1; Ham's F-12 + serum vitamins; organic uptake ≤ 0.1, glucose and O₂ as set; gene–reaction rules decide which reactions a knockout blocks",
            'method': 'flux balance analysis maximising biomass (COBRApy); a knockout blocks a reaction only when no isoenzyme remains'}


SPEC = {
    'atlas': {'title': 'Synthetic CRISPR screen', 'runtime': 'core', 'params': [
        {'key': 'lineages', 'label': 'Lineages', 'kind': 'int', 'min': 3, 'max': 12, 'default': 8},
        {'key': 'perLineage', 'label': 'Patients per lineage', 'kind': 'int', 'min': 10, 'max': 60, 'default': 25},
        {'key': 'genes', 'label': 'Genes', 'kind': 'int', 'min': 300, 'max': 4000, 'step': 100, 'default': 1500},
        {'key': 'effect', 'label': 'Planted effect (gene-effect units)', 'kind': 'float', 'min': 0.1, 'max': 1.5, 'step': 0.05, 'default': 0.5},
        {'key': 'sisterShare', 'label': 'Extra sister lines (share)', 'kind': 'float', 'min': 0, 'max': 0.5, 'step': 0.05, 'default': 0.15},
        {'key': 'seed', 'label': 'Seed', 'kind': 'int', 'min': 0, 'max': 999999, 'default': 1}]},
    'drugs': {'title': 'Synthetic drug screen', 'runtime': 'core', 'params': [
        {'key': 'lines', 'label': 'Cell lines', 'kind': 'int', 'min': 120, 'max': 900, 'step': 20, 'default': 400},
        {'key': 'biomarkers', 'label': 'Biomarker genes', 'kind': 'int', 'min': 1, 'max': 20, 'default': 5},
        {'key': 'r2', 'label': 'Planted R² (non-lineage part)', 'kind': 'float', 'min': 0, 'max': 0.9, 'step': 0.05, 'default': 0.4},
        {'key': 'seed', 'label': 'Seed', 'kind': 'int', 'min': 0, 'max': 999999, 'default': 1}]},
    'synergy': {'title': 'Synthetic combination plates', 'runtime': 'core', 'params': [
        {'key': 'interaction', 'label': 'Planted interaction', 'kind': 'choice', 'options': ['synergy', 'none', 'antagonism', 'sham'], 'default': 'synergy'},
        {'key': 'delta', 'label': 'Bliss excess (pp)', 'kind': 'float', 'min': 0, 'max': 30, 'step': 1, 'default': 12},
        {'key': 'plates', 'label': 'Plates', 'kind': 'int', 'min': 2, 'max': 8, 'default': 3},
        {'key': 'noise', 'label': 'Well noise (pp SD)', 'kind': 'float', 'min': 0, 'max': 15, 'step': 0.5, 'default': 4},
        {'key': 'seed', 'label': 'Seed', 'kind': 'int', 'min': 0, 'max': 999999, 'default': 1}]},
    'signatures': {'title': 'Synthetic mutation catalogues', 'runtime': 'core', 'params': [
        {'key': 'scenario', 'label': 'Scenario', 'kind': 'choice', 'options': list(SIG_SCENARIOS), 'default': 'lung-smoking'},
        {'key': 'samples', 'label': 'Samples', 'kind': 'int', 'min': 20, 'max': 300, 'step': 10, 'default': 60},
        {'key': 'snvs', 'label': 'Median SNVs per sample', 'kind': 'int', 'min': 30, 'max': 3000, 'step': 10, 'default': 250},
        {'key': 'seed', 'label': 'Seed', 'kind': 'int', 'min': 0, 'max': 999999, 'default': 1}]},
    'genomics': {'title': 'Synthetic patient cohort', 'runtime': 'core', 'params': [
        {'key': 'patients', 'label': 'Patients', 'kind': 'int', 'min': 100, 'max': 2000, 'step': 50, 'default': 500},
        {'key': 'hr', 'label': 'Planted STK11 hazard ratio', 'kind': 'float', 'min': 0.5, 'max': 3, 'step': 0.1, 'default': 1.6},
        {'key': 'seed', 'label': 'Seed', 'kind': 'int', 'min': 0, 'max': 999999, 'default': 1}]},
    'singlecell': {'title': 'Synthetic single-cell study', 'runtime': 'singlecell', 'params': [
        {'key': 'program', 'label': 'Planted program', 'kind': 'choice', 'options': list(SC_PROGRAMS), 'default': 'proliferation (E2F targets)'},
        {'key': 'donors', 'label': 'Donors per arm', 'kind': 'int', 'min': 3, 'max': 12, 'default': 6},
        {'key': 'cells', 'label': 'Cells per donor', 'kind': 'int', 'min': 100, 'max': 1500, 'step': 50, 'default': 400},
        {'key': 'effect', 'label': 'Planted log2 fold change', 'kind': 'float', 'min': 0, 'max': 3, 'step': 0.1, 'default': 1.0},
        {'key': 'donorSd', 'label': 'Donor variability (log SD)', 'kind': 'float', 'min': 0, 'max': 1.2, 'step': 0.05, 'default': 0.35},
        {'key': 'seed', 'label': 'Seed', 'kind': 'int', 'min': 0, 'max': 999999, 'default': 1}]},
    'metabolism': {'title': 'Human-GEM what-if', 'runtime': 'singlecell', 'params': [
        {'key': 'glucose', 'label': 'Glucose uptake bound (relative)', 'kind': 'float', 'min': 0, 'max': 4, 'step': 0.25, 'default': 1},
        {'key': 'oxygen', 'label': 'Oxygen bound (1000 = unlimited)', 'kind': 'float', 'min': 0, 'max': 1000, 'step': 0.5, 'default': 1000},
        {'key': 'knockouts', 'label': 'Gene knockouts (symbols, comma-separated)', 'kind': 'text', 'default': 'SDHA, LDHA'}]},
}


def validate(demo, params):
    if demo not in SPEC:
        raise ValueError('Unknown in-silico demo.')
    out = {}
    for f in SPEC[demo]['params']:
        v = params.get(f['key'], f['default'])
        if f['kind'] == 'int':
            v = int(v)
        elif f['kind'] == 'float':
            v = float(v)
        elif f['kind'] == 'choice' and v not in f['options']:
            raise ValueError(f'{f["label"]}: choose one of {", ".join(f["options"])}.')
        elif f['kind'] == 'text':
            v = str(v)[:200]
        if f['kind'] in ('int', 'float') and not (f['min'] <= v <= f['max']):
            raise ValueError(f'{f["label"]} must be between {f["min"]} and {f["max"]}.')
        out[f['key']] = v
    return out


def run_id(demo, params):
    return demo + '-' + hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:10]


def main(root, demo, rid):
    import warnings; warnings.filterwarnings('ignore')
    d = _dir(root, demo, rid); p = json.loads((d / 'params.json').read_text()); t0 = time.time()
    print(f'{demo}: {json.dumps(p)}', flush=True)
    fn = {'atlas': lambda: atlas(p), 'drugs': lambda: drugs(p), 'synergy': lambda: synergy(p), 'signatures': lambda: signatures(p, root),
          'genomics': lambda: genomics(p), 'singlecell': lambda: singlecell(p, root, d), 'metabolism': lambda: metabolism(p, root)}[demo]
    r = fn()
    r.update({'id': rid, 'demo': demo, 'params': p, 'synthetic': demo != 'metabolism', 'evidence': r.pop('evidenceOverride', ILLUSTRATIVE), 'seconds': round(time.time() - t0, 1),
              'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'software': {'python': sys.version.split()[0], 'numpy': np.__version__}})
    (d / 'result.json').write_text(json.dumps(_clean(r)))
    print(f'done in {r["seconds"]} s', flush=True)


if __name__ == '__main__':
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    main(*sys.argv[1:4])
