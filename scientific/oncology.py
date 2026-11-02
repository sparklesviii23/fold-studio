"""Oncology Universe dispatcher: data installs run detached; every analysis is saved as an experiment record."""
import json
import os
import pathlib
import platform
import subprocess
import sys
import time
import uuid

import oncology_data as D


def _dir(s, *p):
    d = pathlib.Path(s.root) / 'oncology' / pathlib.Path(*p)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _finite(x):
    """JSON has no NaN/Infinity: undefined values (e.g. Loewe outside a drug's reach) become null."""
    import math
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: _finite(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_finite(v) for v in x]
    return x


def _record(s, kind, params, result, question):
    import numpy as np
    result = _finite(json.loads(json.dumps(result, default=float)))
    rid = uuid.uuid4().hex
    rels = {src: [m['release'] for m in D.releases(s, src)][:1] for src in ('depmap', 'gdsc')}
    rec = {'id': rid, 'kind': kind, 'question': question, 'params': params, 'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'datasets': rels, 'software': {'python': platform.python_version(), 'numpy': np.__version__, 'module': kind.split('.')[0]}, 'result': result}
    (_dir(s, 'records') / f'{rid}.json').write_text(json.dumps(rec, default=float))
    return {**result, 'recordId': rid}


def _install(s, p):
    src = p.get('source')
    if src not in ('depmap', 'gdsc', 'sanger'):
        raise ValueError('Choose DepMap, GDSC or Sanger Project Score.')
    log = _dir(s, 'install') / f'{src}.log'
    script = 'sanger_score.py' if src == 'sanger' else 'oncology_data.py'
    args = [sys.executable, '-B', '-u', str(pathlib.Path(__file__).with_name(script)), str(s.root)] + ([] if src == 'sanger' else [src])
    if p.get('folder'):
        args += [p['folder'], p.get('release', '')]
    with open(log, 'w') as f:
        proc = subprocess.Popen(args, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
    (_dir(s, 'install') / f'{src}.pid').write_text(str(proc.pid))
    return _status(s)


def _status(s):
    import sanger_score as SS
    out = {'releases': {src: D.releases(s, src) for src in ('depmap', 'gdsc')}, 'installs': {}, 'sanger': SS.installed(s.root)}
    for src in ('depmap', 'gdsc', 'sanger'):
        log, pid = _dir(s, 'install') / f'{src}.log', _dir(s, 'install') / f'{src}.pid'
        if log.is_file():
            alive = False
            if pid.is_file():
                try:
                    os.kill(int(pid.read_text()), 0); alive = True
                    os.waitpid(int(pid.read_text()), os.WNOHANG)
                except (OSError, ValueError, ChildProcessError):
                    pass
            out['installs'][src] = {'running': alive, 'log': log.read_text(errors='replace')[-4000:]}
    out['available'] = {'depmap': {k: v['citation'] for k, v in D.DEPMAP.items()}, 'gdsc': {k: v['citation'] for k, v in D.GDSC.items()},
                        'note': 'DepMap 26Q3 is served only through depmap.org, which blocks scripted downloads with a browser verification page; download it in your browser and import the folder here.'}
    return out


def _detached(s, name, script, *args):
    log = _dir(s, 'install') / f'{name}.log'
    with open(log, 'w') as f:
        proc = subprocess.Popen([sys.executable, '-B', '-u', str(pathlib.Path(__file__).with_name(script)), str(s.root), *args], stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
    (_dir(s, 'install') / f'{name}.pid').write_text(str(proc.pid))


def _job(s, name):
    log, pid = _dir(s, 'install') / f'{name}.log', _dir(s, 'install') / f'{name}.pid'
    if not log.is_file():
        return None
    running = False
    try:
        os.kill(int(pid.read_text()), 0); running = True; os.waitpid(int(pid.read_text()), os.WNOHANG)
    except (OSError, ValueError, ChildProcessError):
        pass
    return {'running': running, 'log': log.read_text(errors='replace')[-3000:]}


def _syn_sig(s, action, p):
    import re
    import synergy as Y
    import mutational_signatures as M
    if action == 'onc_syn_status':
        try:
            return {'installed': True, **Y.catalog(s), 'job': _job(s, 'almanac')}
        except ValueError:
            return {'installed': False, 'job': _job(s, 'almanac')}
    if action == 'onc_syn_install':
        _detached(s, 'almanac', 'synergy.py'); return _syn_sig(s, 'onc_syn_status', p)
    if action == 'onc_syn_analyse':
        a, b = int(p.get('a', 0)), int(p.get('b', 0))
        return _record(s, 'synergy.analyse', {'cell': p.get('cell'), 'a': a, 'b': b}, Y.analyse(s, p.get('cell'), a, b), 'Does this pair interact beyond the reference models?')
    study = str(p.get('study', ''))
    if not re.fullmatch(r'[a-z0-9_]{3,80}', study):
        raise ValueError('Choose a study.')
    if action == 'onc_sig_status':
        f = M._dir(s, study) / 'sbs96.json'
        return {'built': f.is_file(), 'job': _job(s, 'sig_' + study)}
    if action == 'onc_sig_build':
        _detached(s, 'sig_' + study, 'mutational_signatures.py', study); return _syn_sig(s, 'onc_sig_status', p)
    if action == 'onc_sig_analyse':
        return _record(s, 'mutational_signatures.analyse', {'study': study}, M.analyse(s, study), 'Which mutational processes shaped these tumors?')
    if action == 'onc_sig_smoking':
        return _record(s, 'mutational_signatures.smoking_check', {'study': study}, M.smoking_check(s, study), 'Does the tobacco signature track smoking history?')


def _singlecell(s, action, p):
    import hashlib
    import re
    import singlecell_data as SD
    did = str(p.get('datasetId') or SD.CURATED[0]['id'])
    if not re.fullmatch(r'[0-9a-f-]{36}', did):
        raise ValueError('Invalid CELLxGENE dataset id.')
    d = SD.root(s.root, did)
    if action == 'onc_sc_status':
        runs = sorted(d.glob('result_*.json'), key=lambda f: f.stat().st_mtime, reverse=True)
        return {'curated': SD.CURATED, 'datasetId': did, 'installed': (d / 'manifest.json').is_file(), 'manifest': json.loads((d / 'manifest.json').read_text()) if (d / 'manifest.json').is_file() else None,
                'runtime': str(SD.python(s) or ''), 'runtimeReady': SD.python(s) is not None, 'download': _job(s, 'scfetch_' + did), 'job': _job(s, 'sc_' + did), 'results': [f.stem[7:] for f in runs]}
    if action == 'onc_sc_install':
        _detached(s, 'scfetch_' + did, 'singlecell_data.py', did); return _singlecell(s, 'onc_sc_status', p)
    if action == 'onc_sc_run':
        py = SD.python(s)
        if not py:
            raise ValueError('The single-cell runtime (Scanpy) is not installed: create runtimes/singlecell from scientific/singlecell_runtime.lock.txt, or set singlecellPython.')
        if not (d / 'dataset.h5ad').is_file():
            raise ValueError('Download the dataset first.')
        cur = next((c for c in SD.CURATED if c['id'] == did), {})
        args = [str(p.get(k) or cur.get(k) or dflt) for k, dflt in (('cellType', 'hair follicular keratinocyte'), ('case', 'basal cell carcinoma'), ('control', 'normal'))]
        site = str(p.get('site') if p.get('site') is not None else cur.get('site', ''))
        key = hashlib.sha256(json.dumps([*args, site]).encode()).hexdigest()[:12]
        log = _dir(s, 'install') / f'sc_{did}.log'
        with open(log, 'w') as f:
            proc = subprocess.Popen([str(py), '-W', 'ignore', str(pathlib.Path(__file__).with_name('singlecell_tumor.py')), str(d / 'dataset.h5ad'), str(d / f'result_{key}.json'),
                                     str(pathlib.Path(s.root) / 'oncology' / 'genesets' / 'h.all.v2025.1.Hs.symbols.gmt'), args[0], 'disease', args[1], args[2], *([site] if site else [])],
                                    stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        (_dir(s, 'install') / f'sc_{did}.pid').write_text(str(proc.pid))
        (d / f'params_{key}.json').write_text(json.dumps({'cellType': args[0], 'case': args[1], 'control': args[2], 'site': site or None}))
        return {**_singlecell(s, 'onc_sc_status', p), 'started': key}
    if action == 'onc_sc_result':
        key = str(p.get('key', ''))
        f = d / f'result_{key}.json'
        if not re.fullmatch(r'[0-9a-f]{12}', key) or not f.is_file():
            raise ValueError('No such result.')
        r = json.loads(f.read_text()); r['params'] = json.loads((d / f'params_{key}.json').read_text()) if (d / f'params_{key}.json').is_file() else None
        r['manifest'] = json.loads((d / 'manifest.json').read_text())
        return _record(s, 'singlecell_tumor', {'datasetId': did, **(r['params'] or {})}, r, 'Which programs differ between tumor and normal cells, with donors as replicates?')


SPATIAL_CURATED = [{'id': 'b0d9408e-f02f-4ee4-9ab4-98d92cf290f1', 'title': 'Triple-negative breast carcinoma · 10x Visium section M2 (Lab Invest 2023)',
                    'note': 'H&E image, measured spot coordinates, pathologist annotation and authors\' stereoscope deconvolution'}]


def _cellcomm(s, action, p):
    """Inferred cell–cell communication (scientific/cellcomm.py) on an installed single-cell dataset; OmniPath cached with its SHA-256."""
    import hashlib
    import re
    import urllib.request
    import singlecell_data as SD
    did = str(p.get('datasetId') or SD.CURATED[0]['id'])
    if not re.fullmatch(r'[0-9a-f-]{36}', did):
        raise ValueError('Invalid dataset id.')
    d = SD.root(s.root, did); out = d / 'cellcomm.json'
    if action == 'onc_cc_status':
        return {'datasetId': did, 'installed': (d / 'dataset.h5ad').is_file(), 'job': _job(s, 'cc_' + did), 'done': out.is_file(), 'runtimeReady': SD.python(s) is not None}
    if action == 'onc_cc_run':
        py = SD.python(s)
        if not py or not (d / 'dataset.h5ad').is_file():
            raise ValueError('Needs the science runtime and the dataset downloaded in the Single-cell tab.')
        lr = _dir(s, 'omnipath') / 'ligrec.json'
        if not lr.is_file():
            url = 'https://omnipathdb.org/interactions?datasets=ligrecextra&genesymbols=yes&fields=sources,references,curation_effort&license=academic&format=json'
            raw = urllib.request.urlopen(url, timeout=120).read(); lr.write_bytes(raw)
            (lr.parent / 'manifest.json').write_text(json.dumps({'url': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'retrieved': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                                                                'licence': 'OmniPath, academic licence subset; each interaction keeps its original resources'}))
        cur = next((c for c in SD.CURATED if c['id'] == did), {}); case, control = str(p.get('case') or cur.get('case', '')), str(p.get('control') or cur.get('control', 'normal'))
        log = _dir(s, 'install') / f'cc_{did}.log'
        with open(log, 'w') as f:
            proc = subprocess.Popen([str(py), '-W', 'ignore', str(pathlib.Path(__file__).with_name('cellcomm.py')), str(d / 'dataset.h5ad'), str(lr), str(out), 'disease', case, control],
                                    stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        (_dir(s, 'install') / f'cc_{did}.pid').write_text(str(proc.pid))
        return _cellcomm(s, 'onc_cc_status', p)
    if action == 'onc_cc_result':
        if not out.is_file():
            raise ValueError('Run the analysis first.')
        r = json.loads(out.read_text()); m = _dir(s, 'omnipath') / 'manifest.json'
        r['resource'] = json.loads(m.read_text()) if m.is_file() else None
        return _record(s, 'cellcomm', {'datasetId': did}, r, 'Which ligand–receptor pairs are co-expressed between cell types, consistently across donors?')
    raise ValueError(f'Unknown action {action}.')


def _pathology(s, action, p):
    """Demo I (scientific/pathology.py): NuInsSeg installed under oncology/pathology/nuinsseg; one analysis of every image."""
    d = _dir(s, 'pathology', 'nuinsseg'); z = d / 'NuInsSeg.zip'; res = d / 'run' / 'result.json'
    def spawn(name, *args):
        with open(_dir(s, 'install') / f'{name}.log', 'w') as f:
            proc = subprocess.Popen([sys.executable, '-B', '-u', '-W', 'ignore', str(pathlib.Path(__file__).with_name('pathology.py')), *args], stdout=f, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        (_dir(s, 'install') / f'{name}.pid').write_text(str(proc.pid))
    if action == 'onc_path_status':
        return {'installed': (d / 'manifest.json').is_file(), 'bytes': z.stat().st_size if z.is_file() else 0, 'download': _job(s, 'path_install'), 'job': _job(s, 'path_run'), 'done': res.is_file()}
    if action == 'onc_path_install':
        spawn('path_install', 'install', str(d)); return _pathology(s, 'onc_path_status', p)
    if action == 'onc_path_run':
        if not (d / 'manifest.json').is_file():
            raise ValueError('Download and verify NuInsSeg first.')
        spawn('path_run', str(z), str(d / 'run')); return _pathology(s, 'onc_path_status', p)
    if action == 'onc_path_result':
        if not res.is_file():
            raise ValueError('Run the analysis first.')
        r = json.loads(res.read_text()); r['perImage'] = [{k: x[k] for k in ('image', 'organ', 'species', 'nuclei', 'medianArea')} | {'aji': x['watershed']['aji'], 'f1': x['watershed']['f1'], 'flags': x['qc']['flags']} for x in r['perImage']]
        return _record(s, 'pathology', {'dataset': 'NuInsSeg'}, r, 'How accurately does classical segmentation find nuclei in H&E images, by tissue?')
    raise ValueError(f'Unknown pathology action {action}.')


def _perturbseq(s, action, p):
    """Demo J (scientific/perturb_model.py) on Norman 2019 Perturb-seq, run in the science runtime."""
    import singlecell_data as SD
    d = _dir(s, 'perturbseq', 'norman2019'); res = d / 'result.json'; py = SD.python(s)
    def spawn(name, *args):
        with open(_dir(s, 'install') / f'{name}.log', 'w') as f:
            proc = subprocess.Popen([str(py or sys.executable), '-B', '-u', '-W', 'ignore', str(pathlib.Path(__file__).with_name('perturb_model.py')), *args], stdout=f, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        (_dir(s, 'install') / f'{name}.pid').write_text(str(proc.pid))
    if action == 'onc_pm_status':
        f = d / 'NormanWeissman2019_filtered.h5ad'
        return {'installed': (d / 'manifest.json').is_file(), 'bytes': f.stat().st_size if f.is_file() else 0, 'download': _job(s, 'pm_install'), 'job': _job(s, 'pm_run'), 'done': res.is_file(), 'runtimeReady': py is not None}
    if action == 'onc_pm_install':
        spawn('pm_install', 'install', str(d)); return _perturbseq(s, 'onc_pm_status', p)
    if action == 'onc_pm_run':
        if not py or not (d / 'manifest.json').is_file():
            raise ValueError('Needs the science runtime and the verified Norman 2019 file.')
        spawn('pm_run', str(d / 'NormanWeissman2019_filtered.h5ad'), str(res)); return _perturbseq(s, 'onc_pm_status', p)
    if action == 'onc_pm_result':
        if not res.is_file():
            raise ValueError('Run the benchmark first.')
        return _record(s, 'perturb_model', {'dataset': 'Norman 2019'}, json.loads(res.read_text()), 'How well can transcriptional responses to unseen perturbations be predicted, and by what?')
    raise ValueError(f'Unknown action {action}.')


def _spatial(s, action, p):
    import re
    import shutil
    import singlecell_data as SD
    base = SD.root(s.root, kind='spatial')
    if action == 'onc_sp_catalog':
        c = SD.catalog(s.root, bool(p.get('refresh')))
        have = {d.name for d in base.iterdir() if (d / 'dataset.h5ad').is_file()}
        return {**c, 'datasets': [{**r, 'installed': r['id'] in have} for r in c['datasets']]}
    if action == 'onc_sp_library':
        out = []
        for d in sorted(base.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True):
            if d.is_dir() and (d / 'manifest.json').is_file():
                m = json.loads((d / 'manifest.json').read_text())
                out.append({'id': d.name, 'title': m.get('title'), 'synthetic': bool(m.get('synthetic')), 'params': m.get('params'), 'installed': m.get('installed'),
                            'analysed': (d / 'result.json').is_file(), 'sizeMB': round(sum(f.stat().st_size for f in d.iterdir() if f.is_file()) / 1e6, 1)})
        busy = [f.stem.split('_', 1)[1] for f in _dir(s, 'install').glob('sp*_*.pid') if (_job(s, f.stem) or {}).get('running')]
        return {'datasets': out, 'curated': SPATIAL_CURATED, 'downloading': busy, 'runtimeReady': SD.python(s) is not None}
    if action == 'onc_sp_simulate':
        py = SD.python(s)
        if not py:
            raise ValueError('The single-cell runtime is not installed (runtimes/singlecell).')
        ph, nests, seed = str(p.get('phenotype') or 'excluded'), int(p.get('nests') or 3), int(p.get('seed') or 0)
        if ph not in ('infiltrated', 'excluded', 'desert') or not 1 <= nests <= 8 or not 0 <= seed < 10 ** 6:
            raise ValueError('Phenotype must be infiltrated, excluded or desert; 1–8 nests; seed 0–999999.')
        did = f'sim-{ph}-{nests}n-s{seed}'; d = base / did
        script = f'import subprocess,sys; r=subprocess.run([sys.argv[1],"-W","ignore",sys.argv[2],sys.argv[4],sys.argv[5],sys.argv[6],sys.argv[7]]); r.returncode or subprocess.run([sys.argv[1],"-W","ignore",sys.argv[3],sys.argv[4]+"/dataset.h5ad",sys.argv[4]+"/result.json","500"])'
        here = pathlib.Path(__file__)
        log = _dir(s, 'install') / f'sp_{did}.log'
        with open(log, 'w') as f:
            proc = subprocess.Popen([str(py), '-c', script, str(py), str(here.with_name('spatial_sim.py')), str(here.with_name('spatial_tumor.py')), str(d), ph, str(nests), str(seed)],
                                    stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        (_dir(s, 'install') / f'sp_{did}.pid').write_text(str(proc.pid))
        return {**_spatial(s, 'onc_sp_status', {'datasetId': did}), 'datasetId': did}
    did = str(p.get('datasetId') or SPATIAL_CURATED[0]['id'])
    if not (re.fullmatch(r'[0-9a-f-]{36}', did) or re.fullmatch(r'sim-[a-z0-9-]{1,40}', did)):
        raise ValueError('Invalid dataset id.')
    d = base / did
    if action == 'onc_sp_status':
        return {'curated': SPATIAL_CURATED, 'datasetId': did, 'installed': (d / 'dataset.h5ad').is_file(), 'manifest': json.loads((d / 'manifest.json').read_text()) if (d / 'manifest.json').is_file() else None,
                'runtimeReady': SD.python(s) is not None, 'download': _job(s, 'spfetch_' + did), 'job': _job(s, 'sp_' + did), 'result': (d / 'result.json').is_file()}
    if action == 'onc_sp_install':
        if did.startswith('sim-'):
            raise ValueError('Synthetic sections are generated, not downloaded.')
        _detached(s, 'spfetch_' + did, 'singlecell_data.py', did, 'spatial'); return _spatial(s, 'onc_sp_status', p)
    if action == 'onc_sp_delete':
        if any((_job(s, n + did) or {}).get('running') for n in ('spfetch_', 'sp_')):
            raise ValueError('This section is still downloading or being analysed.')
        if d.is_dir():
            shutil.rmtree(d)
        for n in ('spfetch_', 'sp_'):
            for ext in ('.log', '.pid'):
                (_dir(s, 'install') / f'{n}{did}{ext}').unlink(missing_ok=True)
        return _spatial(s, 'onc_sp_library', p)
    if action == 'onc_sp_run':
        py = SD.python(s)
        if not py:
            raise ValueError('The single-cell runtime is not installed (runtimes/singlecell).')
        if not (d / 'dataset.h5ad').is_file():
            raise ValueError('Download the dataset first.')
        log = _dir(s, 'install') / f'sp_{did}.log'
        with open(log, 'w') as f:
            proc = subprocess.Popen([str(py), '-W', 'ignore', str(pathlib.Path(__file__).with_name('spatial_tumor.py')), str(d / 'dataset.h5ad'), str(d / 'result.json'), '500'],
                                    stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        (_dir(s, 'install') / f'sp_{did}.pid').write_text(str(proc.pid))
        return _spatial(s, 'onc_sp_status', p)
    if action == 'onc_sp_result':
        if not (d / 'result.json').is_file():
            raise ValueError('Run the analysis first.')
        r = json.loads((d / 'result.json').read_text()); r['manifest'] = json.loads((d / 'manifest.json').read_text())
        if 'annotations' not in r:
            raise ValueError('This section was analysed by an earlier version of the explorer. Press Re-run analysis (about 10 s).')
        img = r.pop('image'); out = _record(s, 'spatial_tumor', {'datasetId': did}, r, 'How are tumor, stroma and immune cells arranged in this section?'); out['image'] = img
        return out
    raise ValueError(f'Unknown spatial action {action}.')


def _metabolism(s, action, p):
    import singlecell_data as SD
    d = _dir(s, 'metabolism', 'Human-GEM-v2.1.1'); py = SD.python(s)
    def spawn(name, *args):
        log = _dir(s, 'install') / f'{name}.log'
        with open(log, 'w') as f:
            proc = subprocess.Popen([str(py), '-W', 'ignore', str(pathlib.Path(__file__).with_name('metabolism.py')), *args], stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        (_dir(s, 'install') / f'{name}.pid').write_text(str(proc.pid))
    if action == 'onc_met_status':
        return {'installed': (d / 'Human-GEM.json').is_file(), 'manifest': json.loads((d / 'manifest.json').read_text()) if (d / 'manifest.json').is_file() else None,
                'runtimeReady': py is not None, 'download': _job(s, 'met_install'), 'job': _job(s, 'met_run'), 'result': (d / 'result.json').is_file()}
    if not py:
        raise ValueError('The science runtime (runtimes/singlecell, with COBRApy) is not installed.')
    if action == 'onc_met_install':
        spawn('met_install', 'install', str(d)); return _metabolism(s, 'onc_met_status', p)
    if action == 'onc_met_run':
        if not (d / 'Human-GEM.json').is_file():
            raise ValueError('Install Human-GEM first.')
        dep = D.root(s, 'depmap', (D.releases(s, 'depmap') or [{}])[0].get('release', '24Q4'))
        extra = [str(dep / 'gene_effect.npy'), str(dep / 'gene_effect.json')] if (dep / 'gene_effect.npy').is_file() else []
        spawn('met_run', str(d / 'Human-GEM.json'), str(d / 'genes.tsv'), str(d / 'result.json'), *extra); return _metabolism(s, 'onc_met_status', p)
    if action == 'onc_met_result':
        if not (d / 'result.json').is_file():
            raise ValueError('Run the analysis first.')
        r = json.loads((d / 'result.json').read_text()); r['manifest'] = json.loads((d / 'manifest.json').read_text()) if (d / 'manifest.json').is_file() else None
        return _record(s, 'metabolism', {'model': 'Human-GEM v2.1.1'}, r, 'What can a genome-scale model say about tumor energy metabolism and metabolic dependencies?')


def _genomics(s, action, p):
    import re
    import cancer_genomics as G
    study = str(p.get('study', ''))
    if action != 'onc_studies' and action != 'onc_cohorts' and not re.fullmatch(r'[a-z0-9_]{3,80}', study):
        raise ValueError('Choose a study.')
    if action == 'onc_studies':
        import gdc
        out = G.studies()
        try:                                             # GDC projects install as mutation-only cohorts (study id gdc_<project>)
            out += [{'id': gdc.study_id(x['id']), 'name': f'{x["id"]} · {x["name"]} (GDC, mutations only)', 'gdc': x['id'], 'samples': x['cases']} for x in gdc.projects() if (x['cases'] or 0) >= 30]
        except Exception:
            pass
        return out
    if action == 'onc_cohorts':
        out = {'installed': G.installed(s)}
        log = _dir(s, 'install') / 'cbioportal.log'
        if log.is_file():
            out['log'] = log.read_text(errors='replace')[-3000:]
            pid = _dir(s, 'install') / 'cbioportal.pid'
            try:
                os.kill(int(pid.read_text()), 0); out['running'] = True; os.waitpid(int(pid.read_text()), os.WNOHANG)
            except (OSError, ValueError, ChildProcessError):
                out['running'] = False
        return out
    if action == 'onc_cohort_install':
        log = _dir(s, 'install') / 'cbioportal.log'
        project = str(p.get('gdc') or '')
        if project and not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{2,40}', project):
            raise ValueError('Invalid GDC project id.')
        cmd = [str(pathlib.Path(__file__).with_name('gdc.py')), str(s.root), project] if project else [str(pathlib.Path(__file__).with_name('cancer_genomics.py')), str(s.root), study]
        with open(log, 'w') as f:
            proc = subprocess.Popen([sys.executable, '-B', '-u', *cmd], stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        (_dir(s, 'install') / 'cbioportal.pid').write_text(str(proc.pid))
        return _genomics(s, 'onc_cohorts', p)
    if action == 'onc_cohort_summary':
        r = G.summary(s, study)
        return _record(s, 'cancer_genomics.summary', {'study': study}, r, f'What is altered in {study}?')
    if action == 'onc_cohort_pairs':
        genes = [str(g).upper() for g in (p.get('genes') or [])][:20]
        return _record(s, 'cancer_genomics.pairs', {'study': study, 'genes': genes}, G.pairs(s, study, genes), 'Which alterations co-occur or exclude each other?')
    if action == 'onc_cohort_expression':
        g = str(p.get('gene', '')).upper()
        return _record(s, 'cancer_genomics.expression_by_cna', {'study': study, 'gene': g}, G.expression_by_cna(s, study, g), f'Does {g} copy number track its expression?')
    if action == 'onc_cohort_survival':
        g, ep = str(p.get('gene', '')).upper(), p.get('endpoint', 'OS')
        if ep not in ('OS', 'PFS', 'DSS', 'DFS'):
            raise ValueError('Endpoint must be OS, PFS, DSS or DFS.')
        return _record(s, 'cancer_genomics.survival', {'study': study, 'gene': g, 'endpoint': ep}, G.survival(s, study, g, ep), f'Is {g} alteration associated with {ep}?')


def _insilico(s, action, p):
    """In-silico runs for every demo (scientific/insilico.py): one folder per run with params, log, pid and result."""
    import re
    import shutil
    import insilico as I
    import singlecell_data as SD
    demo = str(p.get('demo', ''))
    if action == 'onc_sim_spec':
        return {k: {**v, 'runtimeReady': v['runtime'] == 'core' or SD.python(s) is not None} for k, v in I.SPEC.items()}
    if demo not in I.SPEC:
        raise ValueError('Unknown in-silico demo.')
    base = I._dir(s.root, demo); base.mkdir(parents=True, exist_ok=True)
    def state(d):
        running = False
        try:
            pid = int((d / 'run.pid').read_text()); os.kill(pid, 0); running = True; os.waitpid(pid, os.WNOHANG)
        except (OSError, ValueError, ChildProcessError):
            pass
        r = json.loads((d / 'result.json').read_text()) if (d / 'result.json').is_file() else None
        log = (d / 'run.log').read_text(errors='replace')[-2500:] if (d / 'run.log').is_file() else ''
        return {'id': d.name, 'params': json.loads((d / 'params.json').read_text()), 'running': running, 'done': r is not None, 'failed': not running and r is None,
                'title': r['title'] if r else None, 'passed': sum(c['passed'] is True for c in r['checks']) if r else None, 'failedChecks': sum(c['passed'] is False for c in r['checks']) if r else None,
                'created': (r or {}).get('created'), 'log': log if not r else '', 'sizeMB': round(sum(f.stat().st_size for f in d.iterdir() if f.is_file()) / 1e6, 2)}
    if action == 'onc_sim_list':
        runs = [d for d in sorted(base.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True) if d.is_dir() and (d / 'params.json').is_file()]
        return {'demo': demo, 'runs': [state(d) for d in runs]}
    if action == 'onc_sim_run':
        params = I.validate(demo, p.get('params') or {})
        py = sys.executable if I.SPEC[demo]['runtime'] == 'core' else SD.python(s)
        if not py:
            raise ValueError('This simulation needs the science runtime (runtimes/singlecell, with Scanpy and COBRApy).')
        rid = I.run_id(demo, params); d = base / rid
        if d.is_dir() and state(d)['running']:
            raise ValueError('This run is already in progress.')
        shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True)
        (d / 'params.json').write_text(json.dumps(params))
        with open(d / 'run.log', 'w') as f:
            proc = subprocess.Popen([str(py), '-B', '-u', '-W', 'ignore', str(pathlib.Path(__file__).with_name('insilico.py')), str(s.root), demo, rid],
                                    stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        (d / 'run.pid').write_text(str(proc.pid))
        return {**_insilico(s, 'onc_sim_list', p), 'started': rid}
    rid = str(p.get('id', ''))
    if not re.fullmatch(r'[a-z]+-[0-9a-f]{10}', rid) or not rid.startswith(demo + '-') or not (base / rid).is_dir():
        raise ValueError('No such in-silico run.')
    d = base / rid
    if action == 'onc_sim_delete':
        if state(d)['running']:
            raise ValueError('Wait for this run to finish before deleting it.')
        shutil.rmtree(d)
        return _insilico(s, 'onc_sim_list', p)
    if action == 'onc_sim_result':
        if not (d / 'result.json').is_file():
            raise ValueError('This run has no result yet.')
        r = json.loads((d / 'result.json').read_text())
        return _record(s, 'insilico.' + demo, {'demo': demo, **r['params']}, r, f'Does the {demo} analysis recover a planted answer?' if r.get('synthetic') else 'What does the model predict under these conditions?')
    raise ValueError(f'Unknown in-silico action {action}.')


def _perturbation(s, action, p):
    """Perturbation lab (scientific/perturbation.py): experiments stored under oncology/perturbation/<id>/."""
    import hashlib
    import re
    import shutil
    import oncology_stats as S
    import perturbation as P
    import singlecell_data as SD
    base = _dir(s, 'perturbation')
    def state(d):
        running = False
        try:
            pid = int((d / 'run.pid').read_text()); os.kill(pid, 0); running = True; os.waitpid(pid, os.WNOHANG)
        except (OSError, ValueError, ChildProcessError):
            pass
        r = json.loads((d / 'result.json').read_text()) if (d / 'result.json').is_file() else None
        return {'id': d.name, 'experiment': json.loads((d / 'experiment.json').read_text()), 'running': running, 'done': r is not None, 'title': (r or {}).get('title'),
                'failed': not running and r is None, 'log': '' if r else ((d / 'run.log').read_text(errors='replace')[-2500:] if (d / 'run.log').is_file() else ''), 'created': (r or {}).get('created')}
    if action == 'onc_pl_spec':
        out = {**P.catalog(), 'runtimeReady': SD.python(s) is not None}
        try:
            rel = D.Release(s); out['lineages'] = [l for l, n in S.lineages(rel) if n >= 10]
        except ValueError:
            out['lineages'] = []
        try:
            import drug_response as R
            out['drugs'] = [{k: d[k] for k in ('key', 'name', 'target', 'dataset')} for d in R.drugs(s)]
        except ValueError:
            out['drugs'] = []
        import cancer_genomics as G
        out['studies'] = [{'id': m.get('study'), 'name': m.get('name')} for m in G.installed(s)]
        return out
    if action == 'onc_pl_list':
        runs = [d for d in sorted(base.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True) if d.is_dir() and (d / 'experiment.json').is_file()]
        return {'runs': [state(d) for d in runs]}
    if action == 'onc_pl_run':
        exp = {'system': {k: str(v)[:80] for k, v in (p.get('system') or {}).items() if k in ('lineage', 'study') and v}, 'perturbations': P._norm_perturbations(p.get('perturbations') or [])}
        eid = 'pl-' + hashlib.sha256(json.dumps(exp, sort_keys=True).encode()).hexdigest()[:10]; d = base / eid
        if d.is_dir() and state(d)['running']:
            raise ValueError('This experiment is already running.')
        shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True); (d / 'experiment.json').write_text(json.dumps(exp))
        py = SD.python(s) or sys.executable                      # the science runtime adds COBRApy for Human-GEM; without it that engine reports unavailable
        with open(d / 'run.log', 'w') as f:
            proc = subprocess.Popen([str(py), '-B', '-u', '-W', 'ignore', str(pathlib.Path(__file__).with_name('perturbation.py')), str(s.root), eid],
                                    stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        (d / 'run.pid').write_text(str(proc.pid))
        return {**_perturbation(s, 'onc_pl_list', p), 'started': eid}
    eid = str(p.get('id', ''))
    if not re.fullmatch(r'pl-[0-9a-f]{10}', eid) or not (base / eid).is_dir():
        raise ValueError('No such experiment.')
    d = base / eid
    if action == 'onc_pl_delete':
        if state(d)['running']:
            raise ValueError('Wait for this experiment to finish before deleting it.')
        shutil.rmtree(d); return _perturbation(s, 'onc_pl_list', p)
    if action == 'onc_pl_result':
        if not (d / 'result.json').is_file():
            raise ValueError('This experiment has no result yet.')
        r = json.loads((d / 'result.json').read_text())
        return _record(s, 'perturbation', json.loads((d / 'experiment.json').read_text()), r, 'What happens to this system under these perturbations, according to each engine that can represent them?')
    raise ValueError(f'Unknown perturbation-lab action {action}.')


def _discovery(s, action, p):
    """Demo L (scientific/discovery.py): questions stored under oncology/discovery/<id>/."""
    import hashlib
    import re
    import shutil
    base = _dir(s, 'discovery')
    def state(d):
        running = False
        try:
            pid = int((d / 'run.pid').read_text()); os.kill(pid, 0); running = True; os.waitpid(pid, os.WNOHANG)
        except (OSError, ValueError, ChildProcessError):
            pass
        r = json.loads((d / 'result.json').read_text()) if (d / 'result.json').is_file() else None
        return {'id': d.name, 'question': json.loads((d / 'question.json').read_text()), 'running': running, 'done': r is not None, 'title': (r or {}).get('title'),
                'candidates': (r or {}).get('candidates'), 'failed': not running and r is None, 'log': '' if r else ((d / 'run.log').read_text(errors='replace')[-2500:] if (d / 'run.log').is_file() else '')}
    if action == 'onc_dx_list':
        return {'runs': [state(d) for d in sorted(base.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True) if d.is_dir() and (d / 'question.json').is_file()]}
    if action == 'onc_dx_run':
        gene = str(p.get('gene', '')).strip().upper()
        if not re.fullmatch(r'[A-Z0-9-]{2,15}', gene):
            raise ValueError('Give the driver gene symbol (e.g. KRAS).')
        kind = p.get('kind') or None
        if kind not in (None, 'hotspot', 'damaging'):
            raise ValueError('Mutation kind must be hotspot or damaging.')
        q = {'gene': gene, 'kind': kind, 'study': str(p.get('study') or '')[:80] or None, 'lineage': str(p.get('lineage') or '')[:80] or None, 'candidates': max(1, min(10, int(p.get('candidates', 5))))}
        rid = 'dx-' + hashlib.sha256(json.dumps(q, sort_keys=True).encode()).hexdigest()[:10]; d = base / rid
        if d.is_dir() and state(d)['running']:
            raise ValueError('This question is already running.')
        shutil.rmtree(d, ignore_errors=True); d.mkdir(parents=True); (d / 'question.json').write_text(json.dumps(q))
        with open(d / 'run.log', 'w') as f:
            proc = subprocess.Popen([sys.executable, '-B', '-u', '-W', 'ignore', str(pathlib.Path(__file__).with_name('discovery.py')), str(s.root), rid],
                                    stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
        (d / 'run.pid').write_text(str(proc.pid))
        return {**_discovery(s, 'onc_dx_list', p), 'started': rid}
    rid = str(p.get('id', ''))
    if not re.fullmatch(r'dx-[0-9a-f]{10}', rid) or not (base / rid).is_dir():
        raise ValueError('No such discovery run.')
    d = base / rid
    if action == 'onc_dx_delete':
        if state(d)['running']:
            raise ValueError('Wait for this run to finish before deleting it.')
        shutil.rmtree(d); return _discovery(s, 'onc_dx_list', p)
    if action == 'onc_dx_result':
        if not (d / 'result.json').is_file():
            raise ValueError('This run has no result yet.')
        r = json.loads((d / 'result.json').read_text())
        return _record(s, 'discovery', r['question'], r, f'Which targets does the evidence suggest for {r["question"]["gene"]}-altered cancer, and how strong is each line?')
    raise ValueError(f'Unknown discovery action {action}.')


def dispatch(s, action, p):
    if action == 'onc_data_status':
        return _status(s)
    if action == 'onc_data_install':
        return _install(s, p)
    if action == 'onc_data_import':
        return _install(s, {'source': 'depmap', 'folder': p.get('folder'), 'release': p.get('release')})
    if action in ('onc_studies', 'onc_cohorts', 'onc_cohort_install', 'onc_cohort_summary', 'onc_cohort_pairs', 'onc_cohort_expression', 'onc_cohort_survival'):
        return _genomics(s, action, p)
    if action in ('onc_graph_build', 'onc_graph'):
        import evidence_graph as EG
        gene = str(p.get('gene') or 'KRAS').upper()
        if gene not in EG.CONTEXT:
            raise ValueError(f'No evidence context is defined for {gene} yet.')
        f = pathlib.Path(s.root) / 'oncology' / 'evidence' / gene / 'graph.json'
        if action == 'onc_graph_build' or not f.is_file():
            r = EG.build(s, gene)
        else:
            r = json.loads(f.read_text())
        r = {**r, 'available': {g: c['disease'] for g, c in EG.CONTEXT.items()}, 'built': r.get('built'), 'cached': [g for g in EG.CONTEXT if (pathlib.Path(s.root) / 'oncology' / 'evidence' / g / 'graph.json').is_file()]}
        return _record(s, 'evidence_graph', {'gene': gene}, r, f'What evidence connects {gene} to {EG.CONTEXT[gene]["disease"]}, and how strong is each link?')
    if action.startswith('onc_dx_'):
        return _discovery(s, action, p)
    if action.startswith('onc_pl_'):
        return _perturbation(s, action, p)
    if action.startswith('onc_sim_'):
        return _insilico(s, action, p)
    if action.startswith('onc_met_'):
        return _metabolism(s, action, p)
    if action.startswith('onc_pm_'):
        return _perturbseq(s, action, p)
    if action.startswith('onc_path_'):
        return _pathology(s, action, p)
    if action.startswith('onc_cc_'):
        return _cellcomm(s, action, p)
    if action.startswith('onc_sp_'):
        return _spatial(s, action, p)
    if action.startswith('onc_sc_'):
        return _singlecell(s, action, p)
    if action.startswith('onc_syn_') or action.startswith('onc_sig_'):
        return _syn_sig(s, action, p)
    if action in ('onc_clonal', 'onc_clonal_projection'):
        import re
        import clonal as CL
        if action == 'onc_clonal':
            study = str(p.get('study', ''))
            if not re.fullmatch(r'[a-z0-9_]{3,80}', study):
                raise ValueError('Choose an installed cohort.')
            return _record(s, 'clonal.observed', {'study': study}, CL.observed(s, study), 'Which driver mutations look clonal in this cohort?')
        lim = {'r_s': (0, 1), 'r_r': (0, 1), 'kill': (0, 2), 'resistant0': (1e-6, 0.5), 'start': (0, 3650), 'stop': (0, 3650), 't_end': (1, 3650)}
        q = {k: float(p[k]) for k in lim if p.get(k) is not None}
        for k, v in q.items():
            if not lim[k][0] <= v <= lim[k][1]:
                raise ValueError(f'{k} must lie in {lim[k][0]}–{lim[k][1]}.')
        return _record(s, 'clonal.projection', q, CL.projection(**q), 'Under these assumed rates, when would a resistant clone take over?')
    if action == 'onc_records':
        out = []
        for f in sorted(_dir(s, 'records').glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:100]:
            r = json.loads(f.read_text()); out.append({k: r[k] for k in ('id', 'kind', 'question', 'params', 'created', 'datasets')})
        return out
    if action == 'onc_record':
        rid = str(p.get('id', ''))
        if not rid.isalnum():
            raise ValueError('Invalid record.')
        return json.loads((_dir(s, 'records') / f'{rid}.json').read_text())
    import oncology_stats as S
    rel = D.Release(s, p.get('release'))
    if action == 'onc_lineages':
        return {'release': rel.release, 'manifest': rel.manifest, 'lineages': S.lineages(rel), 'genes': rel.matrix('gene_effect')[2]}
    if action == 'onc_gene':
        g = str(p.get('gene', '')).upper().strip()
        r = S.gene_profile(rel, g)
        try:
            r['expressionLink'] = S.expression_link(rel, g)
        except ValueError as e:
            r['expressionLink'] = {'error': str(e)}
        return _record(s, 'oncology_stats.gene_profile', {'gene': g}, r, f'How essential is {g} across cancer lineages?')
    if action == 'onc_lineage_scan':
        return _record(s, 'oncology_stats.lineage_scan', {'lineage': p.get('lineage')}, S.lineage_scan(rel, p.get('lineage')), f'Which genes are selectively essential in {p.get("lineage")}?')
    if action == 'onc_mutation_scan':
        g, kind = str(p.get('gene', '')).upper().strip(), p.get('kind', 'hotspot')
        if kind not in ('hotspot', 'damaging'):
            raise ValueError('kind must be hotspot or damaging.')
        return _record(s, 'oncology_stats.mutation_scan', {'gene': g, 'kind': kind}, S.mutation_scan(rel, g, kind), f'Which dependencies are associated with {kind} {g} mutation, beyond lineage?')
    if action in ('onc_sl', 'onc_sl_benchmark'):
        import synthetic_lethality as SL
        if action == 'onc_sl_benchmark':
            return _record(s, 'synthetic_lethality.benchmark', {}, SL.benchmark(s.root, rel), 'Does the statistical scan recover experimentally demonstrated synthetic-lethal pairs?')
        g, kind = str(p.get('gene', '')).upper().strip(), p.get('kind', 'damaging')
        if kind not in ('damaging', 'expression', 'hotspot'):
            raise ValueError('Loss must be damaging, expression or hotspot.')
        out = {'gene': g, 'loss': SL.loss_context(s.root, rel, g, kind), 'reference': [dict(zip(('lost', 'dependency', 'mechanism', 'citation'), r)) for r in SL.REFERENCE]}
        try:
            out['coDependency'] = SL.co_dependency(rel, g)
        except ValueError as e:
            out['coDependency'] = {'error': str(e)}
        return _record(s, 'synthetic_lethality', {'gene': g, 'kind': kind}, out, f'What becomes essential when {g} is lost, and which links are demonstrated rather than predicted?')
    if action == 'onc_ask':
        import drug_response as R
        import oncology_assistant as OA
        if p.get('question'):
            q, args = str(p['question']), {k: (str(v).strip() if k == 'lineage' else str(v).upper().strip()) for k, v in (p.get('arguments') or {}).items() if v}
            if q == 'generalize' and args.get('drug'):
                args['drug'] = p['arguments']['drug']
        else:
            try:
                drugs = R.drugs(s)
            except ValueError:
                drugs = []
            q, args = OA.route(str(p.get('text', ''))[:500], rel, drugs, [l for l, _ in S.lineages(rel)])
        r = OA.answer(s, rel, q, args)
        return _record(s, 'assistant', {'question': r['question'], 'arguments': args, 'text': p.get('text')}, {**r, 'questions': {k: v[0] for k, v in OA.QUESTIONS.items()}}, r['question'])
    if action in ('onc_mc_dependency', 'onc_mc_drugs', 'onc_mc_signalling'):
        import model_comparison as MC
        if action == 'onc_mc_dependency':
            g = str(p.get('gene') or '').upper().strip() or None
            return _record(s, 'model_comparison.dependency', {'gene': g}, MC.dependency(s.root, rel, g), 'Do two independent CRISPR screens agree?')
        if action == 'onc_mc_signalling':
            return _record(s, 'model_comparison.signalling', {}, MC.signalling(), 'Do published ERK pathway models agree on the effect of the same knockdown?')
        bench = dispatch(s, 'onc_drug_cells', {'drug': p.get('drug')})       # held-out predictions of every model on the same folds
        return _record(s, 'model_comparison.drugs', {'drug': p.get('drug')}, {**MC.drugs(bench), 'benchmarkRecord': bench.get('recordId')}, 'Is one drug-response model really better than another on the same held-out patients?')
    if action == 'onc_controls':
        return _record(s, 'oncology_stats.controls', {}, {'controls': S.controls(rel), 'release': rel.release}, 'Do known dependencies reproduce in this release?')
    import drug_response as R
    if action == 'onc_drugs':
        return R.drugs(s)
    if action == 'onc_drug_cells':
        import singlecell_data as SD
        py = SD.python(s)
        if py:                                           # science runtime: adds random-forest and boosting baselines (scikit-learn)
            r = subprocess.run([str(py), '-B', '-W', 'ignore', str(pathlib.Path(__file__).with_name('drug_response.py')), 'cells', str(s.root), str(p.get('drug'))], capture_output=True, text=True, timeout=1800)
            if r.returncode:
                raise ValueError((r.stderr.strip().splitlines() or ['benchmark failed'])[-1])
            res = json.loads(r.stdout.strip().splitlines()[-1])
        else:
            res = R.held_out_cell_lines(s, p.get('drug'))
        return _record(s, 'drug_response.held_out_cell_lines', {'drug': p.get('drug')}, res, 'How well do expression models predict response in unseen cell lines?')
    if action == 'onc_drug_compounds':
        return _record(s, 'drug_response.held_out_compounds', {'dataset': 'GDSC2'}, R.held_out_compounds(s), 'Can responses to unseen compounds be predicted?')
    if action == 'onc_drug_lineage':
        return _record(s, 'drug_response.held_out_lineage', {'drug': p.get('drug'), 'lineage': p.get('lineage')}, R.held_out_lineage(s, p.get('drug'), p.get('lineage')), 'Does the model transfer to an unseen lineage?')
    raise ValueError('Unsupported oncology action.')
