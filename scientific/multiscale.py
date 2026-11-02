"""Multiscale experiment actions: run Demo 5 / Demo 8, keep reproducible records, reopen them.

Every run is stored under <library>/multiscale/runs as one JSON record holding the reference
identity, contracts, parameters with provenance, transfers with unit conversions, events,
checks, causal traces, uncertainty, calibration and software versions.
"""
import json, pathlib, platform, time, uuid
import numpy as np, scipy
import multiscale_demos as demos
import multiscale_kernel as K
from multiscale_actions import ACTIONS


def _folder(service):
    f = pathlib.Path(service.root) / 'multiscale' / 'runs'
    f.mkdir(parents=True, exist_ok=True)
    return f


def environment():
    env = {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__, 'machine': platform.machine()}
    try:
        import RNA
        env['viennarna'] = RNA.__version__
    except ImportError:
        env['viennarna'] = None
    return env


def dispatch(service, action, p):
    try:
        if action == 'multiscale_catalog':
            return {'demos': {k: {f: v for f, v in d.items()} for k, d in demos.DEMOS.items()}, 'evidence': K.EVIDENCE, 'identity': demos.reference_identity(), 'environment': environment()}
        if action == 'multiscale_run':
            demo = str(p.get('demo', 'demo5'))
            if demo not in demos.DEMOS:
                raise ValueError('Unknown experiment.')
            samples = int(p.get('samples', 0))
            if not 0 <= samples <= 128:
                raise ValueError('Use 0–128 uncertainty samples.')
            overrides = {str(k): float(v) for k, v in (p.get('overrides') or {}).items()}
            started = time.time()
            r = demos.run(demo, overrides, int(p.get('seed', 1)), samples)
            r.update(id=uuid.uuid4().hex, created=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), seconds=time.time() - started, environment=environment(),
                     label=str(p.get('label') or ''))
            r['sha256'] = K.sha({k: r[k] for k in ('demo', 'overrides', 'seed', 'model')})
            (_folder(service) / (r['id'] + '.json')).write_text(json.dumps(r, default=float))
            return r
        if action == 'multiscale_runs':
            rows = []
            for f in sorted(_folder(service).glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:40]:
                r = json.loads(f.read_text())
                rows.append({'id': r['id'], 'demo': r['demo'], 'title': r['title'], 'created': r['created'], 'label': r.get('label'), 'overrides': r['overrides'],
                             'passed': all(c['passed'] for c in r['checks']), 'checks': len(r['checks'])})
            return rows
        if action == 'multiscale_record':
            rid = str(p.get('id', ''))
            if not rid.isalnum():
                raise ValueError('Invalid record identifier.')
            return json.loads((_folder(service) / (rid + '.json')).read_text())
        raise ValueError('Unsupported multiscale action.')
    except (K.CouplingError, ValueError, KeyError) as e:
        raise ValueError(str(e))
