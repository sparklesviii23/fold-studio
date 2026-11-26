#!/usr/bin/env python3
"""Reproducible benchmark of the virtual light-pulse experiment (scientific/light_pulse.py).

Fits every predictor on the training schedules of the bundled dataset, scores them on whole schedules held out from
fitting, and runs the numerical checks of the integrator. Deterministic. Writes reports/light-pulse-benchmark.json.

  "<app>/Contents/Resources/runtime/bin/python3.12" -B scripts/benchmark-light-pulse.py
"""
import json, math, pathlib, platform, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scientific'))
import numpy as np, scipy
import light_pulse as lp

t0 = time.time(); fit = lp.train(); t_fit = time.time() - t0
bench = lp.benchmark(fit); held = bench['summary']['heldOut']
fold = lambda r: round(10 ** r, 3)
theta = fit['mechanistic']['theta']

# numerical checks, separate from the experimental results
prog = lp.pulses_to_program([{'start': 30, 'duration': 90, 'intensity': 5.0}, {'start': 200, 'duration': 20, 'intensity': 20.0}])
t = np.arange(0, 480.05, 0.1); light = lp.program_values(prog, t[:-1] + 0.05)[None, :]
g = lp.integrate(theta, light, 0.1, record=True)[0]
half = lp.integrate(theta, lp.program_values(prog, np.arange(0, 480, 0.05) + 0.025)[None, :], 0.05, record=True)[0]['g'][0][::2]
solver = lp.solver_check(theta, prog, 480.0, t, g['g'][0])
ss = float(lp.integrate(theta, np.full((1, 4000), 5.0), 1.0)[0]); a_ss = theta['k1'] * 5 / ((theta['k1'] + theta['k2']) * 5 + theta['kdr'] + theta['kg'])
numerical = [
    {'name': 'Independent solver (SBML through the Mechanistic Lab, SciPy LSODA)', 'value': solver['value'].get('maxRelativeDifference'), 'threshold': '< 5e-3', 'passed': solver['passed']},
    {'name': 'Step halving (0.1 → 0.05 min)', 'value': float(np.max(np.abs(half - g['g'][0]) / g['g'][0])), 'threshold': '< 2e-3', 'passed': bool(np.max(np.abs(half - g['g'][0]) / g['g'][0]) < 2e-3)},
    {'name': 'Steady state equals the closed form', 'value': abs(ss / float(lp.hill(theta, np.array(a_ss))) - 1), 'threshold': '< 1e-6', 'passed': bool(abs(ss / float(lp.hill(theta, np.array(a_ss))) - 1) < 1e-6)},
    {'name': 'Regulator activity stays within 0…1; reporter positive', 'value': [float(g['a'].min()), float(g['a'].max())], 'threshold': '0 ≤ a ≤ 1', 'passed': bool(g['a'].min() >= 0 and g['a'].max() <= 1 and g['g'].min() > 0)},
    {'name': 'Every optimiser start reaches the same optimum', 'value': max(fit['mechanistic']['startCosts']) - min(fit['mechanistic']['startCosts']), 'threshold': '< 1e-3 relative', 'passed': bool(max(fit['mechanistic']['startCosts']) - min(fit['mechanistic']['startCosts']) < 1e-3 * min(fit['mechanistic']['startCosts']) + 1e-6)},
]
rows = []
for role in ('heldOut', 'mixedColour', 'otherColour', 'train'):
    for s in bench['schedules'][role]:
        m = s['models'][bench['selected']]
        rows.append({'id': s['id'], 'role': role, 'runs': len(s['replicates']), 'foldError': {k: fold(v['rmseLog10']) for k, v in s['models'].items()}, 'replicateFold': fold(s['replicateSdLog10']) if s.get('replicateSdLog10') else None,
                     'features': {k: {x: (round(f[x], 3) if isinstance(f.get(x), float) else f.get(x)) for x in ('measured', 'predicted', 'relativeError', 'supported')} for k, f in m['features'].items()},
                     'intervalCoverage': m.get('interval') and [m['interval']['inside'], m['interval']['total']]})
# the display hand-off: molecule numbers of the red-perturbation schedule as particles
import types
dry = types.SimpleNamespace(root=None); lp.fitted = lambda service: (fit, bench)
part = lp.particles(dry, {'schedule': 'dynamic-green-red-perturbation', 'preMin': 480})
numerical += [{'name': c['name'] + ' (red-perturbation schedule)', 'value': c['value'], 'threshold': c['threshold'], 'passed': c['passed']} for c in part['checks']]
numerical.append({'name': 'Photostationary shortcut used for calibration', 'value': fit['calibrationCheck']['maxRelativeDifference'], 'threshold': fit['calibrationCheck']['threshold'], 'passed': fit['calibrationCheck']['passed']})
report = {'schema': 'fold.benchmark/2', 'engine': {'id': lp.ENGINE['id'], 'version': lp.VERSION, 'state': {'schema': lp.STATE['schema'], 'version': lp.STATE['version'], 'phi': lp.PHI}},
          'spectral': {'sha256': lp.spectral()['sha256'], 'memberSha256': lp.spectral()['source']['memberSha256']}, 'dataset': {'sha256': lp.dataset()['sha256'], **{k: lp.dataset()['source'][k] for k in ('authors', 'journal', 'doi', 'licence', 'dataset', 'archiveSha256')}},
          'split': lp.SPLIT, 'runtime': f'Python {platform.python_version()} · NumPy {np.__version__} · SciPy {scipy.__version__} · {platform.machine()}', 'fitSeconds': round(t_fit, 1),
          'experimental': {'metric': 'root-mean-square error of log10 fluorescence, shown as a fold error (1.00 is perfect)', 'pooledFoldError': {role: {k: fold(v) for k, v in bench['summary'][role].items()} for role in bench['summary']},
                           'selected': bench['selected'], 'best': bench['best'], 'selectionNote': bench['selectionNote'], 'gate': bench['gate'], 'intervalCoverage': bench['intervalCoverage'],
                           'success': next(r for r in rows if r['id'] == 'dynamic-green'), 'regressionCase': next(r for r in rows if r['id'] == 'dynamic-green-red-perturbation'), 'schedules': rows,
                           'stages': bench['stages'], 'regression': bench['regression'], 'publishedNote': bench['publishedNote'], 'greenOnlyNote': bench['greenOnlyNote'],
                           'channels': [{k: c[k] for k in ('led', 'centroidNm', 'structure', 'k1', 'k2', 'rmseLog10', 'cvRmseLog10', 'published')} for c in fit['channels'].values()], 'growthCheck': {'fittedDoublingMin': round(lp.LN2 / theta['kg'], 2), 'measuredDoublingMin': lp.MEASURED['doublingMin'], 'usedInFit': False}},
          'numerical': numerical, 'parameters': [{k: r.get(k) for k in ('key', 'value', 'unit', 'relativeSe', 'ci95', 'determined')} | {'source': r['provenance']['kind']} for r in lp.parameter_table(fit)],
          'fitSha256': lp._sha({'x': fit['mechanistic']['x'], 'l': fit['learned']['weights'], 'c': fit['combined']['weights'], 'ch': {led: [c['k1'], c['k2']] for led, c in fit['channels'].items()}})}
out = ROOT / 'reports' / 'light-pulse-benchmark.json'; out.write_text(json.dumps(report, indent=1, default=float))
print('Held out, pooled fold error:', report['experimental']['pooledFoldError']['heldOut'])
print('Red on green (final test, retrospective):', report['experimental']['pooledFoldError']['mixedColour'])
print('380 nm alone (final test, retrospective):', report['experimental']['pooledFoldError']['otherColour'])
print('Regression:', bench['regression']['statement'])
print('Final-test failures:', [(x['id'], round(x['foldError'], 2), {k: v['relativeError'] and round(v['relativeError'], 2) for k, v in x['features'].items()}) for x in bench['stages']['finalTest']['failures']])
print('Final-test coverage of the 90 % interval:', bench['stages']['finalTest']['coverage'])
print('Selected:', bench['selected'], '· gate passed:', bench['gate']['passed'])
print('Success  dynamic-green:', report['experimental']['success']['foldError'], 'run-to-run', report['experimental']['success']['replicateFold'], 'coverage', report['experimental']['success']['intervalCoverage'])
print('Red perturbation:', report['experimental']['regressionCase']['foldError'], 'amplitude', report['experimental']['regressionCase']['features']['amplitude'])
print('Numerical:', [(c['name'].split(' (')[0], c['passed']) for c in numerical])
print('Interval coverage:', {k: (round(v['coverage'], 2) if isinstance(v, dict) else v) for k, v in bench['intervalCoverage'].items()})
print('Wrote', out.relative_to(ROOT), '· fit', report['fitSha256'][:16])
sys.exit(0 if all(c['passed'] for c in numerical) else 1)
