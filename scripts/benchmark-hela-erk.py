#!/usr/bin/env python3
"""Reproducible benchmark of the HeLa EGF–ERK experiment (scientific/hela_erk.py).

Calibrates on two positions of dish 04-03, chooses the structure on its other two positions, and scores the four positions
of dish 02-01 and the four non-responding dishes once. Deterministic. Writes reports/hela-erk-benchmark.json.

  "<app>/Contents/Resources/runtime/bin/python3.12" -B scripts/benchmark-hela-erk.py
"""
import json, pathlib, platform, sys, time, types
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scientific'))
import numpy as np, scipy
import hela_erk as he

t0 = time.time(); fit = he.train(); t_fit = time.time() - t0
bench = he.benchmark(fit); he.fitted = lambda service: (fit, bench)
svc = types.SimpleNamespace(root=None); r3 = lambda v: None if v is None else round(float(v), 4)
runs = {'held-out series': he.simulate(svc, {'series': he.SPLIT['test'][0]}), '60 min, 10 ng/ml (extrapolated in time)': he.simulate(svc, {'durationMin': 60}),
        '60 min, MEK inhibited 80 % (simulation)': he.simulate(svc, {'durationMin': 60, 'mekInhibition': 0.8}), '60 min, 0.1 ng/ml (simulation)': he.simulate(svc, {'durationMin': 60, 'egfNgPerMl': 0.1})}
numerical = [{'run': name, 'name': c['name'], 'value': c['value'], 'threshold': c['threshold'], 'passed': c['passed']} for name, r in runs.items() for c in r['checks'] if c['applicable']]
rows = []
for role, rs in bench['schedules'].items():
    for r in rs:
        m = r['models']['mechanistic']
        rows.append({'id': r['id'], 'role': role, 'cells': r['cells'], 'onsetMin': r['onset']['t0'], 'onsetDetected': r['onset']['detected'],
                     'cellRmseRelative': {k: r3(v['pooledRmseRelative']) for k, v in r['models'].items()}, 'rmseOfMeanRelative': {k: r3(v['rmseOfMeanRelative']) for k, v in r['models'].items()},
                     'amplitude': {k: r3(m['features']['amplitude'][k]) for k in ('measured', 'predicted')}, 'halfRiseMin': {k: r3(m['features']['halfRiseMin'][k]) for k in ('measured', 'predicted')},
                     'peakTime': 'not reached by the measurement', 'recovery': 'not reached by the measurement', 'intervalCoverage': [m['interval']['inside'], m['interval']['total']]})
report = {'schema': 'fold.benchmark/2', 'engine': {'id': he.ENGINE['id'], 'version': he.VERSION, 'state': {'schema': he.STATE['schema'], 'version': he.STATE['version'], 'interface': he.STATE['interface']}},
          'dataset': {'sha256': he.dataset()['sha256'], **he.dataset()['source'], 'archives': [{k: s.get(k) for k in ('id', 'archiveSha256', 'usable', 'reason', 'dropped')} | {'cells': len(s['cells'])} for s in he.dataset()['series']]},
          'specimens': {'liveCell': he.dataset()['specimen'], 'geometryReference': he.EM_REFERENCE}, 'resolution': he.RESOLUTION, 'split': he.SPLIT, 'unexplainedDishes': he.UNEXPLAINED,
          'runtime': f'Python {platform.python_version()} · NumPy {np.__version__} · SciPy {scipy.__version__} · {platform.machine()}', 'fitSeconds': round(t_fit, 1),
          'experimental': {'metric': bench['metric'], 'status': bench['status'], 'statement': bench['statement'], 'onsetNote': bench['onsetNote'], 'summary': bench['summary'], 'intervalCoverage': bench['intervalCoverage'],
                           'holdouts': bench['holdouts'], 'failures': bench['failures'], 'gate': bench['gate'], 'structure': fit['structure'], 'selection': fit['selection'], 'series': rows},
          'numerical': numerical, 'parameters': [{k: p.get(k) for k in ('key', 'value', 'unit', 'ci95', 'determined')} | {'source': p['provenance']['kind']} for p in he.parameter_table(fit)],
          'fitSha256': he._sha({'theta': fit['theta'], 'structure': fit['structure'], 'gain': fit['gain'], 'noise': fit['noise']})}
out = ROOT / 'reports' / 'hela-erk-benchmark.json'; out.write_text(json.dumps(report, indent=1, default=float))
s = bench['summary']; show = lambda role: {m: r3(v['pooledCellRmseRelative']) for m, v in s[role].items()}
print('Status:', bench['status'], '· structure', fit['structure']['name'], '· kc', r3(fit['theta']['kc']), '/min · G', r3(fit['theta']['G']))
print('Held-out dish, single-cell error (relative C/N):', show('test'), '· of the mean:', {m: r3(v['rmseOfMeanRelative']) for m, v in s['test'].items()})
print('Held-out dish, 90 % interval coverage:', r3(bench['intervalCoverage']['test']['coverage']))
print('Non-responding dishes:', show('unexplained'), '· coverage', r3(bench['intervalCoverage']['unexplained']['coverage']))
print('Hold-outs:', {k: v['status'] for k, v in bench['holdouts'].items()})
print('Failures:', len(bench['failures']), '·', sorted({w for f in bench['failures'] for w in f['why']}))
print('Numerical:', sum(c['passed'] for c in numerical), 'of', len(numerical), 'checks pass')
print('Wrote', out.relative_to(ROOT), '· fit', report['fitSha256'][:16])
sys.exit(0 if all(c['passed'] for c in numerical) else 1)
