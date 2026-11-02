"""RNA folding-kinetics actions (Demo 10): run, list and reopen saved records under <library>/rna_kinetics/runs."""
import hashlib, json, pathlib, time, uuid
import numpy as np
import rna_kinetics_demo as demo


def _plain(obj):
    return json.loads(json.dumps(obj, default=lambda o: o.item() if isinstance(o, np.generic) else o.tolist() if isinstance(o, np.ndarray) else str(o)))


def _folder(service):
    f = pathlib.Path(service.root) / 'rna_kinetics' / 'runs'
    f.mkdir(parents=True, exist_ok=True)
    return f


def dispatch(service, action, p):
    if action == 'rna_kinetics_run':
        seed = int(p.get('seed', 1))
        r = _plain(demo.run(str(p.get('sequence') or demo.DEFAULT), float(p.get('temperature', 37.0)), seed))
        r.update(recordId=uuid.uuid4().hex, created=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), label=str(p.get('label') or ''))
        r['sha256'] = hashlib.sha256(json.dumps({k: r[k] for k in ('sequence', 'temperature', 'seed', 'landscape')}, sort_keys=True).encode()).hexdigest()
        (_folder(service) / (r['recordId'] + '.json')).write_text(json.dumps(r))
        return r
    if action == 'rna_kinetics_runs':
        rows = []
        for f in sorted(_folder(service).glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:40]:
            r = json.loads(f.read_text())
            rows.append({'id': r['recordId'], 'created': r['created'], 'label': r.get('label'), 'sequence': r['sequence'], 'temperature': r['temperature'],
                         'passed': all(c['passed'] for c in r['checks']), 'checks': len(r['checks']), 'states': r['landscape']['states']})
        return rows
    if action == 'rna_kinetics_record':
        rid = str(p.get('id', ''))
        if not rid.isalnum():
            raise ValueError('Invalid record identifier.')
        return json.loads((_folder(service) / (rid + '.json')).read_text())
    raise ValueError('Unsupported RNA kinetics action.')
