"""Cell-cycle timeline: the Gérard & Goldbeter (2009) mammalian Cdk network, run by the Mechanistic Lab solver.

Model: BioModels BIOMD0000000730 (curated, CC0), fetched through mechanistic_knowledge's cache into
<library>/mechanistic/cache and compiled by mechanistic_sbml; integrated by mechanistic_sim.simulate (LSODA, with the
100× tighter re-solve that reports tolerance sensitivity). Nothing in the model is rewritten.

What the model is and is not
  * A generic mammalian network of the four cyclin/Cdk modules, the pRB/E2F switch, APC (Cdh1, Cdc20), p27, Wee1/Cdc25,
    DNA-replication checkpoint (Pol, Cdc45, Primer, ATR, Chk1) and growth factor (GF) signalling through AP1.
    It is not calibrated to Hep G2 or any line; parameters are the published ones.
  * It has no cell size, volume, nuclear geometry or division event: the 3D cell is therefore not driven by it.
  * Phase vocabulary follows the authors' sequential activation of the modules: Cdk2/cyclin E (G1/S), Cdk2/cyclin A
    (S–G2), Cdk1/cyclin B (G2/M). Labels come from a forward-only rule on half-maximum crossings (each maximum taken
    after the initial transient): G1 → G1/S when Cdk2/E rises above half-maximum, → S–G2 when Cdk2/A does, → G2/M when
    Cdk1/B does, → G1 at "mitotic exit" when Cdk1/B falls below half-maximum. Before the first mitotic exit the
    trajectory is unlabelled (initial conditions are arbitrary). These are model-derived proxies, not measured phase
    boundaries, and no division is modelled. Cdk4–6/cyclin D is reported but not used: in this model it stays active
    through S phase, so "highest relative activity" gives a non-physiological order (tested and rejected).
  * Below the GF threshold the network stops oscillating; a run whose Cdk1/B varies by < 1 % of its maximum over the
    last 48 h is reported as quiescent (G0-like in the model).
"""
import hashlib, json, pathlib

import numpy as np

MODEL_ID = 'BIOMD0000000730'
MODULES = [('Md', 'Cdk4–6 / cyclin D', 'G1'), ('Me', 'Cdk2 / cyclin E', 'G1/S'), ('Ma', 'Cdk2 / cyclin A', 'S–G2'), ('Mb', 'Cdk1 / cyclin B', 'G2/M')]
PHASES = ['G1', 'G1/S', 'S–G2', 'G2/M']
SHOWN = ['Md', 'Me', 'Ma', 'Mb', 'E2F', 'Cdh1a', 'Cdc20a', 'p27', 'Primer', 'Chk1']
# The only link from this model to the 3D cell. A visualization rule, not a model prediction: the model has no
# chromatin, size or organelle variables. Brightness of the nucleus/DNA layer = base + scale × (Cdk1/cyclin B ÷ its
# maximum over the run); the phase badge shows the forward-only phase proxy. Nothing else in the cell view changes.
VISUAL = {'variable': 'Mb', 'layer': 'dna', 'base': 0.6, 'scale': 1.6, 'category': 'illustrative',
          'rule': 'Nucleus/DNA-layer brightness = 0.6 + 1.6 × normalised Cdk1/cyclin B activity (visualization rule; the model has no geometric or chromatin variables). '
                  'Phase badge = forward-only half-maximum phase proxy.'}
LIMITS = {'hours': (24.0, 240.0), 'gf': (0.0, 5.0)}
METHOD = {'rtol': 1e-8, 'atol': 1e-10, 'method': 'LSODA', 'step': 0.1}


def _cache_dir(root, *p):
    d = pathlib.Path(root).joinpath('virtualcell', 'cache', 'cellcycle', *p); d.mkdir(parents=True, exist_ok=True)
    return d


def model(root):
    """The published SBML compiled by the Mechanistic Lab, from its own BioModels cache."""
    import mechanistic_knowledge as kb, mechanistic_sbml as sbml
    text, src = kb.biomodels_fetch(kb.Cache(pathlib.Path(root) / 'mechanistic' / 'cache'), MODEL_ID)
    # The first network fetch keeps CRLF line ends that the cached copy loses; normalise so the model hash is stable.
    return sbml.Model(text.replace('\r\n', '\n'), src)


def describe(m):
    d = m.describe()
    return {'id': MODEL_ID, 'name': m.name, 'sha256': m.sha256, 'sbml': f'Level {m.level} Version {m.version}', 'source': m.source,
            'species': len(m.state), 'parameters': len(m.param_ids), 'units': d.get('units') or 'dimensionless concentrations; time in hours (as published)',
            'calibration': 'Generic mammalian parameters (Gérard & Goldbeter 2009). Not calibrated to Hep G2 or any cell line.',
            'notModelled': ['cell size and volume', 'nuclear morphology', 'division / daughter cells', 'transcript or protein levels of named genes'],
            'licence': 'BioModels curated model: CC0'}


def _peaks(x, t, frac=0.1):
    from scipy.signal import find_peaks
    p, _ = find_peaks(x, prominence=frac * (x.max() - x.min() + 1e-12))
    return [float(t[i]) for i in p]


def analyse(t, series, transient=48.0):
    """Phase proxies, oscillation period, mitotic exits and quiescence from the solved series (rule in the module docstring)."""
    t = np.asarray(t); keep = t >= min(transient, t[-1] / 2)
    act = {k: np.asarray(series[k]) for k, _, _ in MODULES}; half = {k: 0.5 * act[k][keep].max() for k in act}
    mb = act['Mb']; tail = t >= t[-1] - 48
    quiescent = bool(np.ptp(mb[tail]) < 0.01 * max(mb.max(), 1e-12))
    from scipy.signal import find_peaks
    idx, _ = find_peaks(mb, prominence=0.1 * (mb.max() - mb.min() + 1e-12)); heights = [float(mb[i]) for i in idx if t[i] >= t[keep][0]]
    sustained = not quiescent and len(heights) >= 2 and min(heights[-3:]) >= 0.95 * max(heights[-3:])
    regime = 'steady state (quiescent, G0-like)' if quiescent else 'sustained oscillation (limit cycle)' if sustained else \
             'damped or irregular oscillation (not settled within the run); phases not assigned' if heights else 'no oscillation detected'
    exits = [float(t[i]) for i in range(1, len(t)) if mb[i - 1] >= half['Mb'] > mb[i] and t[i] >= t[keep][0]]
    labels, phase = [], None                          # index into PHASES; None = unlabelled
    for i in range(len(t)):
        if sustained:
            if phase is None:
                phase = 0 if (exits and t[i] >= exits[0]) else None
            elif phase == 0 and act['Me'][i] >= half['Me']: phase = 1
            elif phase == 1 and act['Ma'][i] >= half['Ma']: phase = 2
            elif phase == 2 and act['Mb'][i] >= half['Mb']: phase = 3
            elif phase == 3 and act['Mb'][i] < half['Mb']: phase = 0
        labels.append(phase)
    segs = []
    for i, l in enumerate(labels):
        if l is None:
            continue
        if not segs or segs[-1]['phase'] != PHASES[l] or segs[-1]['end'] < float(t[i - 1]):
            segs.append({'phase': PHASES[l], 'start': float(t[i]), 'end': float(t[i])})
        segs[-1]['end'] = float(t[i])
    if sustained and not segs:
        regime += '; half-maximum crossings never completed a cycle, so phases are not assigned'
    pk = [p for p in _peaks(mb, t) if p >= t[keep][0]]
    first = {k: (_peaks(act[k][keep], t[keep]) or [None])[0] for k in ('Me', 'Ma', 'Mb')}
    return {'quiescent': quiescent, 'regime': regime, 'sustained': sustained, 'peakHeights': heights, 'labels': labels, 'segments': segs, 'phases': PHASES,
            'period': float(np.mean(np.diff(pk))) if sustained and len(pk) > 1 else None, 'periodSd': float(np.std(np.diff(pk))) if len(pk) > 2 else None,
            'cyclesAnalysed': max(len(pk) - 1, 0), 'mitoticExit': exits, 'transientExcluded': float(t[keep][0]), 'firstPeaks': first,
            'rule': 'Forward-only half-maximum crossings: G1 → G1/S (Cdk2/E) → S–G2 (Cdk2/A) → G2/M (Cdk1/B) → G1 when Cdk1/B falls below half-maximum '
                    '(mitotic exit). Unlabelled before the first mitotic exit. Assigned only for a sustained limit cycle (last three Cdk1/B peaks within 5 %); '
                    'quiescent when Cdk1/B varies < 1 % of its maximum over the last 48 h.'}


def run(root, gf=1.0, hours=120.0):
    gf, hours = float(gf), float(hours)
    if not LIMITS['gf'][0] <= gf <= LIMITS['gf'][1] or not LIMITS['hours'][0] <= hours <= LIMITS['hours'][1]:
        raise ValueError(f"Growth factor must be within {LIMITS['gf']} and duration within {LIMITS['hours']} h.")
    import mechanistic_sim as sim
    m = model(root); points = min(2000, int(round(hours / METHOD['step'])) + 1)          # solver output cap: 2,000 points
    key = hashlib.sha256(json.dumps([m.sha256, gf, hours, points, METHOD], sort_keys=True).encode()).hexdigest()[:24]
    f = _cache_dir(root) / f'{key}.json'
    if f.is_file():                                           # the display rule is attached on read: it is not part of the numerical result
        return {**json.loads(f.read_text()), 'visual': VISUAL, 'cached': True}
    r = sim.simulate(m, hours, points=points, method=METHOD['method'], rtol=METHOD['rtol'], atol=METHOD['atol'], overrides={'GF': gf}, check=True)
    out = {'key': key, 'model': describe(m), 'gf': gf, 'hours': hours, 'time': r['time'], 'series': {k: r['series'][k] for k in r['series']},
           'shown': SHOWN, 'visual': VISUAL, 'modules': [{'id': k, 'name': n, 'phase': p} for k, n, p in MODULES], 'solver': r['solver'], 'diagnostics': r['diagnostics'],
           'analysis': analyse(r['time'], r['series']), 'evidence': 'Mechanistic simulation output (generic mammalian model)',
           'interpretation': 'Numerical output of the published model with the stated growth factor. Convergence says nothing about whether it describes Hep G2.'}
    f.write_text(json.dumps(out))
    return {**out, 'cached': False}


def load_run(root, key):
    f = _cache_dir(root) / f'{key}.json'
    if not (len(key) == 24 and all(c in '0123456789abcdef' for c in key)) or not f.is_file():
        raise ValueError('That simulation is no longer cached; run it again (same settings reproduce it).')
    return json.loads(f.read_text())


def at(r, time):
    """State of every species at the stored time point nearest `time`, with the module label there."""
    t = np.asarray(r['time']); i = int(np.abs(t - float(time)).argmin())
    lab = r['analysis']['labels'][i]
    return {'time': float(t[i]), 'index': i, 'variables': {k: float(v[i]) for k, v in r['series'].items()},
            'phase': 'quiescent (G0-like)' if r['analysis']['quiescent'] else None if lab is None else PHASES[lab], 'regime': r['analysis']['regime'],
            'phaseRule': r['analysis']['rule'], 'quiescent': r['analysis']['quiescent'], 'visual': visual(r, i)}


def visual(r, i):
    v = np.asarray(r['series'][VISUAL['variable']]); x = float(v[i] / max(float(v.max()), 1e-12))
    return {**VISUAL, 'normalised': x, 'gain': VISUAL['base'] + VISUAL['scale'] * x}
