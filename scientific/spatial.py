"""Spatial solver actions (Demo 11): run the RDME gradient experiment, keep records, reopen them.

Every run is stored under <library>/spatial/runs as one JSON record holding parameters with
provenance, mesh, checks, profiles, slices and software versions.
"""
import json, pathlib, platform, time, uuid
import numpy as np, scipy
import multiscale_kernel as K
import spatial_demos as demo
from spatial_actions import ACTIONS


def _plain(obj):
    # Results go to the UI as JSON: NumPy scalars (bool_, int64, float64) become native types.
    return json.loads(json.dumps(obj, default=lambda o: o.item() if isinstance(o, np.generic) else o.tolist() if isinstance(o, np.ndarray) else str(o)))


def _folder(service):
    f = pathlib.Path(service.root) / 'spatial' / 'runs'
    f.mkdir(parents=True, exist_ok=True)
    return f


def dispatch(service, action, p):
    if action == 'spatial_catalog':
        return _plain({**{k: demo.DEMO[k] for k in demo.DEMO}, 'parameters': [{**q.__dict__, 'range': list(q.range) if q.range else None, 'editable': q.name in demo.LIMITS} for q in demo.PARAMS],
                'limits': demo.LIMITS})
    if action == 'spatial_run':
        overrides = {str(k): float(v) for k, v in (p.get('overrides') or {}).items()}
        seed = int(p.get('seed', 1))
        if not 1 <= seed <= 2 ** 31:
            raise ValueError('Seed must be a positive integer.')
        r = demo.run(overrides, seed)
        r.update(created=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), label=str(p.get('label') or ''), recordId=uuid.uuid4().hex,
                 environment={'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__, 'machine': platform.machine()})
        r = _plain(r)
        r['sha256'] = K.sha({'overrides': r['overrides'], 'seed': seed, 'parameters': r['parameters']})
        (_folder(service) / (r['recordId'] + '.json')).write_text(json.dumps(r))
        return r
    if action == 'spatial_runs':
        rows = []
        for f in sorted(_folder(service).glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:40]:
            r = json.loads(f.read_text())
            rows.append({'id': r['recordId'], 'created': r['created'], 'label': r.get('label'), 'overrides': r['overrides'], 'seed': r['seed'],
                         'passed': all(c['passed'] for c in r['checks']), 'checks': len(r['checks']), 'nucleusToMembrane': r['outputs']['nucleusToMembrane']['value']})
        return rows
    if action == 'spatial_record':
        rid = str(p.get('id', ''))
        if not rid.isalnum():
            raise ValueError('Invalid record identifier.')
        return json.loads((_folder(service) / (rid + '.json')).read_text())
    raise ValueError('Unsupported spatial action.')
