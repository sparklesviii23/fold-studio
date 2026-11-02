"""Tumor Microenvironment Lab: reads PhysiCell results returned by Cloud GPU Tasks and analyses them locally.

The simulation itself is PhysiCell (agent-based cells + BioFVM reaction–diffusion) run on the user's server.
Here we only check physical consistency of what came back and fit population growth laws; every output
carries its evidence category so simulated, fitted and checked quantities are never mixed.
"""
import json
import math

import numpy as np

# Phase codes from PhysiCell 1.14.2 core/PhysiCell_constants.cpp.
PHASE = {0: 'Ki67+ premitotic', 1: 'Ki67+ postmitotic', 2: 'Ki67+', 3: 'Ki67−', 4: 'G0/G1', 5: 'G0', 6: 'G1', 7: 'G1a', 8: 'G1b', 9: 'G1c', 10: 'S', 11: 'G2/M', 12: 'G2', 13: 'M',
         14: 'live', 15: 'G1pm', 16: 'G1ps', 17: 'cycling', 18: 'quiescent', 100: 'apoptotic', 101: 'necrotic swelling', 102: 'necrotic lysed', 103: 'necrotic', 104: 'debris'}
NECROTIC = {101, 102, 103}


def _folder(s):
    import gpu_tasks
    return gpu_tasks._folder(s)


def runs(s):
    out = []
    for d in sorted(_folder(s).iterdir(), reverse=True):
        f = d / 'task.json'
        if not f.is_file():
            continue
        rec = json.loads(f.read_text())
        if rec.get('recipe') != 'physicell':
            continue
        out.append({k: rec.get(k) for k in ('id', 'state', 'created', 'inputs', 'error', 'phase')} | {'ready': (d / 'outputs' / 'physicell' / 'tme.json').is_file()})
    return out


def _fit(t, n):
    """Least-squares exponential, logistic and Gompertz fits to a simulated population curve; AIC ranks them."""
    from scipy.optimize import curve_fit
    n0 = max(n[0], 1.0)
    models = {
        'exponential': (lambda t, r: n0 * np.exp(r * t), [0.3], 'N(t) = N₀·e^{rt}'),
        'logistic': (lambda t, r, K: K / (1 + (K / n0 - 1) * np.exp(-r * t)), [0.3, max(n) * 2], 'N(t) = K / (1 + (K/N₀ − 1)·e^{−rt})'),
        'Gompertz': (lambda t, a, b: n0 * np.exp(a / b * (1 - np.exp(-b * t))), [0.3, 0.05], 'N(t) = N₀·exp[(a/b)(1 − e^{−bt})]'),
    }
    out = []
    for name, (f, p0, eq) in models.items():
        try:
            p, cov = curve_fit(f, t, n, p0=p0, maxfev=20000)
            rss = float(((f(t, *p) - n) ** 2).sum())
            aic = len(t) * math.log(max(rss, 1e-12) / len(t)) + 2 * len(p)
            se = np.sqrt(np.clip(np.diag(cov), 0, None)) if np.all(np.isfinite(cov)) else [None] * len(p)
            out.append({'model': name, 'equation': eq, 'params': [float(v) for v in p], 'se': [None if v is None else float(v) for v in se], 'rss': rss, 'aic': aic})
        except Exception as e:
            out.append({'model': name, 'equation': eq, 'error': type(e).__name__})
    ok = [m for m in out if 'aic' in m]
    best = min(m['aic'] for m in ok) if ok else None
    for m in ok:
        m['deltaAic'] = m['aic'] - best
    return out


def checks(d):
    subs, grid, frames = d['substrates'], d['grid'], d['frames']
    out = []
    # 1. Bookkeeping: per-type counts add up to the total population in every saved frame.
    bad = [f['t'] for f in frames if sum(c['live'] + c['dead'] for c in f['counts'].values()) != f['total']]
    out.append({'check': 'Population bookkeeping', 'passed': not bad, 'detail': f'{len(frames)} frames; per-type live + dead equals the total in every frame' if not bad else f'mismatch at t = {bad[:3]} min'})
    # 2. Maximum principle: oxygen is only consumed, so it must stay within [0, boundary value].
    for k, sub in enumerate(subs):
        if sub['name'].lower() != 'oxygen':
            continue
        vals = np.array([v for f in frames for v in f['fields'][k] if v is not None])
        lo, hi = float(vals.min()), float(vals.max())
        ok = lo >= -1e-6 and hi <= sub['dirichlet'] * (1 + 1e-3)
        out.append({'check': 'Oxygen maximum principle', 'passed': ok, 'detail': f'range {lo:.3g}–{hi:.3g} {sub["units"]} vs boundary {sub["dirichlet"]:g}; consumption-only diffusion cannot exceed the boundary or go negative'})
        # 3. Hypoxia–necrosis consistency on the final frame (cells in the plotted slice only).
        f = frames[-1]
        xs, ys = np.array(grid['x']), np.array(grid['y'])
        field = np.array([np.nan if v is None else v for v in f['fields'][k]]).reshape(len(ys), len(xs))
        dz = (xs[1] - xs[0]) if len(xs) > 1 else 20
        c = np.array(f['cells']) if f['cells'] else np.zeros((0, 8))
        sel = np.abs(c[:, 2] - grid['z0']) <= dz if len(c) else np.zeros(0, bool)
        if sel.sum():
            ix = np.clip(np.searchsorted(xs, c[sel, 0]), 0, len(xs) - 1); iy = np.clip(np.searchsorted(ys, c[sel, 1]), 0, len(ys) - 1)
            o2 = field[iy, ix]; ph = c[sel, 6].astype(int)
            nec = np.isin(ph, list(NECROTIC)); live = c[sel, 5] < 0.5
            if nec.sum() >= 10 and live.sum() >= 10:
                a, b = float(np.nanmean(o2[nec])), float(np.nanmean(o2[live]))
                out.append({'check': 'Necrosis sits in low oxygen', 'passed': a < b, 'detail': f'mean O₂ at necrotic cells {a:.3g} vs live cells {b:.3g} ({int(nec.sum())} necrotic, {int(live.sum())} live in the mid-plane)'})
            else:
                out.append({'check': 'Necrosis sits in low oxygen', 'passed': None, 'detail': f'not assessable: {int(nec.sum())} necrotic cells in the mid-plane (needs ≥ 10)'})
    return out


def load(s, p):
    import gpu_tasks
    tid = gpu_tasks._safe_id(p.get('taskId'))
    f = _folder(s) / tid / 'outputs' / 'physicell' / 'tme.json'
    if not f.is_file():
        raise ValueError('This run has no returned PhysiCell results yet.')
    d = json.loads(f.read_text())
    t = np.array([fr['t'] / 1440 for fr in d['frames']])
    series = {}
    for tid_, name in d['types'].items():
        series[name] = {'live': [fr['counts'].get(tid_, {}).get('live', 0) for fr in d['frames']], 'dead': [fr['counts'].get(tid_, {}).get('dead', 0) for fr in d['frames']]}
    tumor = next((n for n in series if 'cancer' in n.lower() or 'tumor' in n.lower()), next(iter(series), None))
    fits = _fit(t, np.array(series[tumor]['live'], float)) if tumor and len(t) >= 5 else []
    return {**d, 'taskId': tid, 'days': t.tolist(), 'series': series, 'growthFits': {'population': tumor, 'fits': fits}, 'checks': checks(d), 'phases': PHASE,
            'evidence': {'simulation': 'Mechanistic simulation · PhysiCell reference model with published parameters; not calibrated to any patient or cell line',
                         'fits': 'Statistical fit to simulated counts (describes this run, not a measured tumor)',
                         'checks': 'Numerical/physical consistency of the returned output'}}


def dispatch(s, action, p):
    if action == 'tme_runs':
        return runs(s)
    if action == 'tme_load':
        return load(s, p)
    raise ValueError('Unsupported tumor microenvironment action.')
