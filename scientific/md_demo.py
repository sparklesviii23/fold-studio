"""Demo 12 actions: run the Trp-cage reference molecular dynamics in the OpenMM runtime as a background
job, then keep the full trajectory and analysis as a reproducible record under <library>/md_reference/<id>.

This module only manages processes and files; all physics runs in md_reference.py inside the OpenMM runtime.
"""
import hashlib, json, os, pathlib, signal, subprocess, sys, time, uuid
from md_demo_actions import ACTIONS

HERE = pathlib.Path(__file__).resolve().parent
PDB = HERE.parent / 'fixtures' / 'md' / '1L2Y.pdb'
PDB_SHA256 = '5d1bbb545a312dfff1ae1e64b6d8addecb2f561ddc4011aeb5bee9d1dfcd4438'
LIMITS = {'production_ps': (5, 200), 'temperature': (270, 360), 'seed': (1, 2 ** 31 - 1)}
REFS = {
    'structure': {'citation': 'Neidigh JW, Fesinmeyer RM, Andersen NH. Designing a 20-residue protein. Nat Struct Biol 2002;9:425–430 (PDB 1L2Y, NMR ensemble of 38 models).', 'doi': '10.1038/nsb798'},
    'forcefield': {'citation': 'Maier JA et al. ff14SB: improving the accuracy of protein side chain and backbone parameters from ff99SB. J Chem Theory Comput 2015;11:3696–3713.', 'doi': '10.1021/acs.jctc.5b00255'},
    'solvent': {'citation': 'Nguyen H, Roe DR, Simmerling C. Improved generalized Born solvent model parameters for protein simulations (GBn2). J Chem Theory Comput 2013;9:2020–2034.', 'doi': '10.1021/ct3010485'},
    'openmm': {'citation': 'Eastman P et al. OpenMM 8: molecular dynamics simulation with machine learning potentials. J Phys Chem B 2024;128:109–116.', 'doi': '10.1021/acs.jpcb.3c06662'},
}
ASSUMPTIONS = [
    'Amber ff14SB with GBn2 implicit solvent: no explicit water or ions; solvent friction is represented only by the Langevin thermostat (γ = 1/ps).',
    'Starting coordinates are NMR model 1 of 1L2Y, minimised; protonation states as deposited.',
    'Hydrogen-bond lengths constrained; 2 fs time step; 300 K.',
    'NMR ensemble spread is used as a reference for flexibility: it reflects restraint satisfaction and is not a measured dynamical fluctuation.',
]
LIMITATIONS = [
    'Tens of picoseconds sample fast local motion only; Trp-cage folds and unfolds on microsecond timescales, which this run does not reach.',
    'Implicit solvent removes water-mediated interactions and hydrodynamics; times are not directly comparable with experiment.',
    'This is molecular dynamics, not docking or structure prediction: it moves a given structure under a force field.',
]


def _folder(service):
    f = pathlib.Path(service.root) / 'md_reference'
    f.mkdir(parents=True, exist_ok=True)
    return f


def _runtime(service):
    import dynamics
    return dynamics.runtime(service)


def _alive(pid):
    # Reap the child if it is ours and has exited; otherwise a finished job would linger as a zombie and look alive.
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)
        if done == pid:
            return False
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start(service, p):
    cfg = {'temperature': 300.0, 'timestep_fs': 2.0, 'friction': 1.0, 'seed': 1, 'equilibration_ps': 10.0, 'production_ps': 50.0, 'frame_ps': 0.25}
    for k in ('production_ps', 'temperature', 'seed'):
        if k in p:
            v = float(p[k]); lo, hi = LIMITS[k]
            if not lo <= v <= hi:
                raise ValueError(f'{k} must lie in {lo}–{hi}.')
            cfg[k] = int(v) if k == 'seed' else v
    if hashlib.sha256(PDB.read_bytes()).hexdigest() != PDB_SHA256:
        raise ValueError('The bundled 1L2Y coordinates do not match their recorded checksum.')
    py = _runtime(service)
    if not pathlib.Path(py).is_file():
        raise ValueError('The OpenMM runtime is not installed.')
    rid = uuid.uuid4().hex
    d = _folder(service) / rid
    d.mkdir()
    cfg['pdb'] = str(PDB)
    (d / 'input.json').write_text(json.dumps(cfg))
    log = open(d / 'log.txt', 'w')
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
    proc = subprocess.Popen([py, '-I', '-B', str(HERE / 'md_reference.py'), str(d / 'input.json'), str(d / 'trajectory.json')],
                            stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
    (d / 'job.json').write_text(json.dumps({'pid': proc.pid, 'started': time.time(), 'label': str(p.get('label') or '')}))
    return {'id': rid, 'state': 'running', 'config': cfg}


def _finish(d, job):
    raw = json.loads((d / 'trajectory.json').read_text())
    cfg = json.loads((d / 'input.json').read_text())
    cfg.pop('pdb', None)
    rec = {'id': d.name, 'title': 'Demo 12 · Molecular interaction dynamics', 'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'label': job.get('label', ''),
           'question': 'How does the Trp-cage miniprotein move around its NMR structure, and do the contacts that build its hydrophobic cage persist?',
           'system': {'name': 'Trp-cage TC5b (NLYIQWLKDGGPSSGRPPPS)', 'pdb': '1L2Y', 'model': 1, 'sha256': PDB_SHA256, **raw['system']},
           'evidence': {'trajectory': 'Physics-simulated (classical force field, implicit solvent)', 'reference': 'Experimentally observed (NMR ensemble; flexibility proxy)'},
           'config': cfg, 'references': REFS, 'assumptions': ASSUMPTIONS, 'limitations': LIMITATIONS, **{k: v for k, v in raw.items() if k != 'system'}}
    rec['sha256'] = hashlib.sha256(json.dumps({'config': cfg, 'pdb': PDB_SHA256, 'software': raw['software']}, sort_keys=True).encode()).hexdigest()
    (d / 'record.json').write_text(json.dumps(rec))
    return rec


def status(service, p):
    rid = str(p.get('id', ''))
    if not rid.isalnum():
        raise ValueError('Invalid run identifier.')
    d = _folder(service) / rid
    if (d / 'record.json').is_file():
        return {'id': rid, 'state': 'done'}
    job = json.loads((d / 'job.json').read_text())
    if (d / 'trajectory.json').is_file():   # written atomically (rename) at the very end
        _finish(d, job)
        return {'id': rid, 'state': 'done'}
    if _alive(job['pid']):
        return {'id': rid, 'state': 'running', 'elapsed': time.time() - job['started']}
    tail = (d / 'log.txt').read_text()[-1500:] if (d / 'log.txt').is_file() else ''
    return {'id': rid, 'state': 'failed', 'log': tail}


def dispatch(service, action, p):
    if action == 'md_reference_start':
        return start(service, p)
    if action == 'md_reference_status':
        return status(service, p)
    if action == 'md_reference_record':
        rid = str(p.get('id', ''))
        if not rid.isalnum():
            raise ValueError('Invalid run identifier.')
        return json.loads((_folder(service) / rid / 'record.json').read_text())
    if action == 'md_reference_runs':
        rows = []
        for d in sorted((x for x in _folder(service).iterdir() if x.is_dir()), key=lambda x: x.stat().st_mtime, reverse=True)[:30]:
            if (d / 'record.json').is_file():
                r = json.loads((d / 'record.json').read_text())
                rows.append({'id': r['id'], 'created': r['created'], 'label': r.get('label'), 'productionPs': r['config']['production_ps'], 'temperature': r['config']['temperature'],
                             'seed': r['config']['seed'], 'passed': all(c['passed'] for c in r['checks']), 'checks': len(r['checks']), 'state': 'done'})
            elif (d / 'job.json').is_file():
                rows.append({'id': d.name, **status(service, {'id': d.name})})
        return rows
    if action == 'md_reference_cancel':
        rid = str(p.get('id', ''))
        if not rid.isalnum():
            raise ValueError('Invalid run identifier.')
        job = json.loads((_folder(service) / rid / 'job.json').read_text())
        if _alive(job['pid']):
            os.killpg(job['pid'], signal.SIGTERM)
        return {'id': rid, 'state': 'cancelled'}
    raise ValueError('Unsupported molecular dynamics action.')
