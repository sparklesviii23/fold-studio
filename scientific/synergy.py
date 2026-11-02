"""Drug-combination analysis on NCI ALMANAC (Holbeck SL et al., Cancer Res 2017;77:3564) measured combination matrices.

Reference models (each answers a different question; none alone "proves" synergy):
  HSA    excess over the stronger single agent at the same concentrations (Berenbaum 1989)
  Bliss  excess over independent action, E_A + E_B − E_A·E_B (Bliss 1939)
  Loewe  excess over dose additivity, solved from fitted single-agent Hill curves (Loewe 1953); undefined where the
         expected effect exceeds what either drug reaches alone (reported, never extrapolated)
  ZIP    delta from the zero-interaction-potency surface (Yadav B et al., Comput Struct Biotechnol J 2015)
  NCI ComboScore  the screen's own expected growth, recomputed independently and checked against the published values

Effects: fraction inhibited E = (100 − percent growth)/100 clipped to [0, 1]; percent growth < 0 (net cell kill) is clipped
and counted. Replicates are plates (independent experiments); scores are summarised over plates with a 95 % t-interval.
Evidence: Experimental observation (growth) → Statistical/model-based synergy estimates under the named reference model.
"""
import csv
import hashlib
import io
import json
import math
import pathlib
import time
import zipfile

import numpy as np

EVIDENCE = 'Model-based estimate from an experimental combination screen (NCI ALMANAC, NCI-60 cell lines, 48 h SRB growth)'
RELEASE = '2017-11'


def _root(s):
    return pathlib.Path(s.root) / 'oncology' / 'almanac' / RELEASE


def install(s, log=print):
    """Parse the ALMANAC CSV once into compact arrays (original percent-growth values unchanged)."""
    d = _root(s); raw = d / 'original'
    z = raw / 'ComboDrugGrowth_Nov2017.zip'
    if not z.is_file():
        import urllib.request
        raw.mkdir(parents=True, exist_ok=True)
        for f in ('ComboDrugGrowth_Nov2017.zip', 'ComboCompoundNames_small.txt'):
            urllib.request.urlretrieve('https://wiki.nci.nih.gov/download/attachments/338237347/' + f, raw / f); log(f'downloaded {f}')
    sha = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in raw.iterdir() if f.is_file()}
    cells, plates, cols = {}, {}, {k: [] for k in ('cell', 'plate', 'nsc1', 'conc1', 'nsc2', 'conc2', 'pg', 'expected', 'score')}
    with zipfile.ZipFile(z) as zf, zf.open('ComboDrugGrowth_Nov2017.csv') as fh:
        for i, r in enumerate(csv.DictReader(io.TextIOWrapper(fh, 'utf-8'))):
            if r['VALID'] != 'Y':
                continue
            cols['cell'].append(cells.setdefault(r['CELLNAME'], len(cells)))
            cols['plate'].append(plates.setdefault(r['SCREENER'] + '|' + r['PLATE'] + '|' + r['TESTDATE'], len(plates)))
            cols['nsc1'].append(int(r['NSC1'])); cols['conc1'].append(float(r['CONC1']))
            cols['nsc2'].append(int(r['NSC2']) if r['NSC2'] else 0); cols['conc2'].append(float(r['CONC2']) if r['CONC2'] else 0.0)
            cols['pg'].append(float(r['PERCENTGROWTH']))
            cols['expected'].append(float(r['EXPECTEDGROWTH']) if r['EXPECTEDGROWTH'] else np.nan)
            cols['score'].append(float(r['SCORE']) if r['SCORE'] else np.nan)
            if i % 500000 == 0:
                log(f'{i:,} rows')
    np.savez_compressed(d / 'almanac.npz', cell=np.array(cols['cell'], np.int16), plate=np.array(cols['plate'], np.int32), nsc1=np.array(cols['nsc1'], np.int32),
                        conc1=np.array(cols['conc1']), nsc2=np.array(cols['nsc2'], np.int32), conc2=np.array(cols['conc2']), pg=np.array(cols['pg']),
                        expected=np.array(cols['expected']), score=np.array(cols['score']))
    names = {}
    for line in (raw / 'ComboCompoundNames_small.txt').read_text(errors='replace').splitlines():
        p = line.split('\t')
        if len(p) >= 2 and p[0].strip().isdigit():
            names.setdefault(int(p[0]), p[1].strip())
    (d / 'index.json').write_text(json.dumps({'cells': sorted(cells, key=cells.get), 'names': names, 'plates': sorted(plates, key=plates.get)}))
    m = {'source': 'NCI ALMANAC', 'release': RELEASE, 'rows': len(cols['pg']), 'files': {k: {'sha256': v, 'verified': False, 'note': 'no checksum is published; SHA-256 recorded'} for k, v in sha.items()},
         'citation': 'Holbeck SL et al. The National Cancer Institute ALMANAC: a comprehensive screening resource for the detection of anticancer drug pairs with enhanced therapeutic activity. Cancer Res 2017;77:3564–3576.',
         'licence': 'US Government work (NCI DTP), public', 'installed': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (d / 'manifest.json').write_text(json.dumps(m, indent=1))
    log(f'ALMANAC ready: {m["rows"]:,} valid wells, {len(cells)} cell lines, {len(names)} named compounds')
    return m


_DATA = {}


def _load(s):
    d = _root(s)
    if not (d / 'almanac.npz').is_file():
        raise ValueError('Install NCI ALMANAC first (Oncology › Synergy).')
    if 'a' not in _DATA:
        z = np.load(d / 'almanac.npz'); _DATA['a'] = {k: z[k] for k in z.files}; _DATA['i'] = json.loads((d / 'index.json').read_text())
        _DATA['m'] = json.loads((d / 'manifest.json').read_text())
    return _DATA['a'], _DATA['i'], _DATA['m']


def catalog(s):
    a, idx, m = _load(s)
    combo = a['nsc2'] > 0
    pairs = np.unique(np.c_[np.minimum(a['nsc1'][combo], a['nsc2'][combo]), np.maximum(a['nsc1'][combo], a['nsc2'][combo])], axis=0)
    drugs = sorted({int(x) for x in np.unique(a['nsc1'])} | {int(x) for x in np.unique(a['nsc2'][combo])})
    return {'manifest': m, 'cells': idx['cells'], 'drugs': [{'nsc': n, 'name': idx['names'].get(str(n), f'NSC {n}')} for n in drugs], 'pairs': len(pairs)}


def nci_expected(ga, gb):
    """NCI ALMANAC expected growth (Holbeck 2017): product of the single-agent growth fractions when both are positive,
    otherwise the lower growth. Single-agent growth above 100 % is truncated to 100 %."""
    ga, gb = min(ga, 100.0), min(gb, 100.0)
    return ga * gb / 100.0 if ga > 0 and gb > 0 else min(ga, gb)


def _hill(c, ec50, h, top):
    return top * c ** h / (ec50 ** h + c ** h)


def _fit_hill(conc, e):
    from scipy.optimize import curve_fit
    conc, e = np.asarray(conc, float), np.asarray(e, float)
    try:
        p, _ = curve_fit(_hill, conc, e, p0=[np.median(conc), 1.0, max(min(e.max(), 1.0), 0.05)], bounds=([conc.min() / 1e3, 0.3, 0.01], [conc.max() * 1e3, 5.0, 1.0]), maxfev=20000)
        return p
    except Exception:
        return None


def _loewe_expected(a, b, pa, pb):
    """Solve a/A⁻¹(E) + b/B⁻¹(E) = 1 for E by bisection, inside the effect range both curves reach."""
    if pa is None or pb is None:
        return np.nan
    inv = lambda E, p: p[0] * (E / (p[2] - E)) ** (1 / p[1])
    hi = min(pa[2], pb[2]) * (1 - 1e-6)
    f = lambda E: a / inv(E, pa) + b / inv(E, pb) - 1
    lo_, hi_ = 1e-9, hi
    if f(hi_) > 0:
        return np.nan          # additivity would need an effect beyond what a single agent reaches
    for _ in range(80):
        mid = (lo_ + hi_) / 2
        lo_, hi_ = (mid, hi_) if f(mid) > 0 else (lo_, mid)
    return (lo_ + hi_) / 2


def _zip_delta(ca, cb, E, pa, pb):
    """ZIP: refit each row/column with a Hill curve whose baseline is the other drug's single-agent effect; δ = fitted − ZIP reference."""
    from scipy.optimize import curve_fit
    if pa is None or pb is None:
        return None
    ya, yb = _hill(ca, *pa), _hill(cb, *pb)
    ref = ya[:, None] + yb[None, :] - ya[:, None] * yb[None, :]
    fa = np.full(E.shape, np.nan); fb = np.full(E.shape, np.nan)
    for j in range(len(cb)):                         # vary A at fixed B
        base = yb[j]; f = lambda c, ec, h: base + (1 - base) * c ** h / (ec ** h + c ** h)
        try:
            p, _ = curve_fit(f, ca, E[:, j], p0=[pa[0], pa[1]], bounds=([ca.min() / 1e3, 0.3], [ca.max() * 1e3, 5]), maxfev=20000); fa[:, j] = f(ca, *p)
        except Exception:
            pass
    for i in range(len(ca)):
        base = ya[i]; f = lambda c, ec, h: base + (1 - base) * c ** h / (ec ** h + c ** h)
        try:
            p, _ = curve_fit(f, cb, E[i, :], p0=[pb[0], pb[1]], bounds=([cb.min() / 1e3, 0.3], [cb.max() * 1e3, 5]), maxfev=20000); fb[i, :] = f(cb, *p)
        except Exception:
            pass
    return np.nanmean([fa, fb], 0) - ref


def score_plates(per, pa, pb):
    """Per-plate HSA, Bliss, Loewe, ZIP and NCI scores; mean over plates with a 95 % t-interval and a call."""
    from scipy.stats import t as T
    models = {'HSA': [], 'Bliss': [], 'Loewe': [], 'ZIP': [], 'NCI ComboScore': []}; loewe_undefined = 0; surfaces = {}
    for r in per:
        ca, cb, E, Ea, Eb = np.array(r['ca']), np.array(r['cb']), r['E'], r['Ea'], r['Eb']
        hsa = E - np.maximum(Ea[:, None], Eb[None, :]); bliss = E - (Ea[:, None] + Eb[None, :] - Ea[:, None] * Eb[None, :])
        lo = np.array([[E[i, j] - _loewe_expected(ca[i], cb[j], pa, pb) for j in range(len(cb))] for i in range(len(ca))]); loewe_undefined += int(np.isnan(lo).sum())
        zp = _zip_delta(ca, cb, E, pa, pb)
        for k, M in (('HSA', hsa), ('Bliss', bliss), ('Loewe', lo), ('ZIP', zp), ('NCI ComboScore', r['nci'] / 100)):
            if M is not None and np.isfinite(M).any():
                models[k].append(float(np.nanmean(M)) * 100); surfaces.setdefault(k, []).append(M)
    summary = {}
    for k, v in models.items():
        v = np.array(v)
        if len(v):
            se = v.std(ddof=1) / math.sqrt(len(v)) if len(v) > 1 else float('nan'); h = T.ppf(0.975, len(v) - 1) * se if len(v) > 1 else float('nan')
            summary[k] = {'mean': float(v.mean()), 'ci': [float(v.mean() - h), float(v.mean() + h)], 'plates': len(v), 'perPlate': v.tolist(),
                          'call': 'not determined (one plate)' if len(v) < 2 else 'synergy' if v.mean() - h > 0 else 'antagonism' if v.mean() + h < 0 else 'consistent with no interaction'}
    mean_surface = {k: np.nanmean(np.array([x for x in v if x.shape == v[0].shape]), 0).round(4).tolist() for k, v in surfaces.items()}
    return summary, mean_surface, loewe_undefined


def analyse(s, cell, a_nsc, b_nsc):
    from scipy.stats import t as T
    A, idx, m = _load(s)
    if cell not in idx['cells']:
        raise ValueError('Choose an NCI-60 cell line.')
    ci = idx['cells'].index(cell); a_nsc, b_nsc = int(a_nsc), int(b_nsc)
    on = A['cell'] == ci
    fwd = on & (A['nsc1'] == a_nsc) & (A['nsc2'] == b_nsc); rev = on & (A['nsc1'] == b_nsc) & (A['nsc2'] == a_nsc)
    if not fwd.any() and not rev.any():
        raise ValueError('This pair was not screened in this cell line.')
    plates = np.unique(A['plate'][fwd | rev]); per, nci_check, clipped, same_exp = [], [], 0, [0]
    exp_of = lambda k: '|'.join(idx['plates'][k].split('|')[::2])          # screener|test date
    cell_plates = np.unique(A['plate'][on]); sibs = {pl: [q for q in cell_plates if exp_of(q) == exp_of(pl)] for pl in plates}
    pool_a, pool_b = ([], []), ([], [])
    for pl in plates:
        P = on & (A['plate'] == pl)
        def single(nsc):
            # Same plate first; otherwise the same experiment (screener and test date), as the screen itself pairs them.
            sel = P & (A['nsc1'] == nsc) & (A['nsc2'] == 0)
            if not sel.any():
                sel = on & np.isin(A['plate'], sibs[pl]) & (A['nsc1'] == nsc) & (A['nsc2'] == 0); same_exp[0] += 1
            out = {}
            for c, g in zip(A['conc1'][sel], A['pg'][sel]):
                out.setdefault(round(c, 12), []).append(g)
            return {k: float(np.mean(v)) for k, v in out.items()}
        sa, sb = single(a_nsc), single(b_nsc)
        cmb = {}
        for sel, flip in ((P & (A['nsc1'] == a_nsc) & (A['nsc2'] == b_nsc), False), (P & (A['nsc1'] == b_nsc) & (A['nsc2'] == a_nsc), True)):
            for c1, c2, g, ex in zip(A['conc1'][sel], A['conc2'][sel], A['pg'][sel], A['expected'][sel]):
                ka, kb = (round(c2, 12), round(c1, 12)) if flip else (round(c1, 12), round(c2, 12))
                cmb[(ka, kb)] = (g, ex)
        ca, cb = sorted({k[0] for k in cmb}), sorted({k[1] for k in cmb})
        if not all(c in sa for c in ca) or not all(c in sb for c in cb):
            continue
        G = np.array([[cmb.get((x, y), (np.nan, np.nan))[0] for y in cb] for x in ca])
        for x in ca:
            for y in cb:
                if (x, y) in cmb and np.isfinite(cmb[(x, y)][1]):
                    nci_check.append(abs(nci_expected(sa[x], sb[y]) - cmb[(x, y)][1]))
        clipped += int((G < 0).sum())
        eff = lambda g: np.clip((100 - np.asarray(g, float)) / 100, 0, 1)
        Ea, Eb, E = eff([sa[x] for x in ca]), eff([sb[y] for y in cb]), eff(G)
        pool_a[0].extend(ca); pool_a[1].extend(Ea); pool_b[0].extend(cb); pool_b[1].extend(Eb)
        nciexp = np.array([[nci_expected(sa[x], sb[y]) for y in cb] for x in ca])
        per.append({'plate': int(pl), 'ca': ca, 'cb': cb, 'E': E, 'Ea': Ea, 'Eb': Eb, 'G': G, 'nci': nciexp - G})
    if not per:
        raise ValueError('No plate has complete single-agent data for both drugs.')
    pa, pb = _fit_hill(*pool_a), _fit_hill(*pool_b)
    summary, mean_surface, loewe_undefined = score_plates(per, pa, pb)
    first = per[0]
    nm = lambda n: idx['names'].get(str(n), f'NSC {n}')
    return {'cell': cell, 'a': {'nsc': a_nsc, 'name': nm(a_nsc), 'hill': None if pa is None else {'ec50M': pa[0], 'slope': pa[1], 'emax': pa[2]}},
            'b': {'nsc': b_nsc, 'name': nm(b_nsc), 'hill': None if pb is None else {'ec50M': pb[0], 'slope': pb[1], 'emax': pb[2]}},
            'plates': len(per), 'concA': first['ca'], 'concB': first['cb'], 'observed': np.nanmean([p['E'] for p in per if p['E'].shape == first['E'].shape], 0).round(4).tolist(),
            'singleA': [list(map(float, x)) for x in zip(*pool_a)], 'singleB': [list(map(float, x)) for x in zip(*pool_b)],
            'scores': summary, 'surfaces': mean_surface, 'loeweUndefined': loewe_undefined, 'clippedWells': clipped, 'singleAgentFromSameExperiment': same_exp[0],
            'nciCheck': {'wells': len(nci_check), 'maxAbsDiff': float(max(nci_check)) if nci_check else None, 'meanAbsDiff': float(np.mean(nci_check)) if nci_check else None},
            'units': 'scores in percentage points of fraction inhibited (positive = more effect than the reference model predicts)',
            'method': 'per-plate HSA, Bliss, Loewe (Hill fits pooled over plates) and ZIP; mean over plates with 95 % t-interval; NCI ComboScore recomputed from single agents',
            'evidence': EVIDENCE, 'caveat': 'A score is defined only relative to its reference model, in this cell line, at these concentrations and 48 h. It is not a clinical recommendation.',
            'manifest': m}


if __name__ == '__main__':
    import sys, types
    install(types.SimpleNamespace(root=sys.argv[1]))
