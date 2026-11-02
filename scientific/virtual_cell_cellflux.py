"""CellFlux generated Cell Painting (experimental research plugin; added at the user's request for research use).

Model: CellFlux (Zhang et al., ICML 2025; github.com/yuhui-zh15/CellFlux, pinned commit 041c4c0), JUMP cpg0000 checkpoint
from huggingface.co/suyc21/CellFlux (epoch 79, SHA-256 in status()). Repository licence MIT; several source files carry
a CC-BY-NC header (Meta flow_matching heritage); the weights' licence is not stated. Treated as non-commercial research use.
Runs locally on Apple MPS through scientific/cellflux_runner.py in runtimes/gbcell (PyTorch 2.14) with flow-matching
1.0.10 and torchdiffeq 0.2.5 from the plugin's own deps folder; no app runtime is modified.

What the outputs are — and are not
  * Generated images (evidence category `prediction`), never observations.
  * The checkpoint was trained on U2OS cells (JUMP cpg0000), 96 × 96 crops in five channels with an undocumented
    per-crop normalisation and channel order. Hep G2 EU-OS images have four channels (no RNA), another microscope and
    another cell line. Inputs are therefore built with ASSUMED choices, stated on every result: slot order
    DNA, ER, RNA, AGP, Mito (the JUMP convention); RNA slot filled with the ER image; each channel scaled to 8 bits by its
    0.5–99.8th percentile over the field.
  * Every run reports an identity check between each input crop and its generated crop: per-channel Pearson r over the
    whole crop (dominated by the cell-versus-background footprint) and within the cell, the Dice overlap of Otsu nucleus
    masks in the DNA slot with the nuclear-area fractions, and the DNA intensity ratio. Under DMSO a faithful model keeps
    the cell. First Hep G2 test (2 Nov 2026, DMSO, 4 cells): whole-crop DNA r 0.83, in-cell r 0.82, nucleus Dice
    0.53–0.75, nuclear-area fraction changed (0.18 → 0.33, 0.26 → 0.11), mean DNA intensity ×1.9 — nuclei partly kept
    but distorted. Outputs are out of domain and not interpretable as Hep G2 perturbation responses.
  * An in-domain benchmark (generation from held-out JUMP controls vs real treated cells) is not possible here: the
    cpg0000 crops are not in the public IMPA archive.
"""
import hashlib, json, os, pathlib, subprocess, time, uuid

import numpy as np

PLUGIN = ('virtualcell', 'plugins', 'cellflux')
SLOTS = ['DNA', 'ER', 'RNA', 'AGP', 'Mito']
FILL = {'RNA': 'ER'}
SETTINGS = {'nfe': 50, 'cfg': 0.2, 'noiseLevel': 1.0, 'method': 'heun2', 'timeGrid': 'EDM', 'start': 'control', 'weights': 'EMA'}
MODEL = {'name': 'CellFlux', 'checkpoint': 'cpg0000 (JUMP, U2OS)', 'commit': '041c4c071056896316338872145cef164b07a5fc', 'citation': 'Zhang Y et al. CellFlux: Simulating Cellular Morphology Changes via Flow Matching. ICML 2025.',
         'licence': 'Code MIT (repository) with CC-BY-NC headers in some files; weights licence not stated — research use only', 'trainingDomain': 'U2OS, JUMP cpg0000 crops (96 px, 5 channels)'}


def folder(root):
    return pathlib.Path(root).joinpath(*PLUGIN)


def python(service=None):
    for c in ((service.setting('cellfluxPython') if service else None), os.environ.get('FOLD_CELLFLUX_PYTHON')):
        if c and pathlib.Path(c).is_file():
            return pathlib.Path(c)
    for parent in pathlib.Path(__file__).resolve().parents:
        p = parent / 'runtimes' / 'gbcell' / 'bin' / 'python'
        if p.is_file():
            return p
    return None


def _sha_file(f):
    cache = f.with_suffix(f.suffix + '.sha256')
    if cache.is_file() and cache.stat().st_mtime >= f.stat().st_mtime:
        return cache.read_text().strip()
    h = hashlib.sha256()
    with open(f, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 22), b''):
            h.update(b)
    cache.write_text(h.hexdigest()); return h.hexdigest()


def status(root, service=None):
    d = folder(root); ck = d / 'checkpoints' / 'cpg0000.pth'
    parts = {'code': (d / 'src' / 'models' / 'unet.py').is_file(), 'deps': (d / 'deps' / 'flow_matching').is_dir() and (d / 'deps' / 'torchdiffeq').is_dir(),
             'checkpoint': ck.is_file(), 'embeddings': (d / 'data' / 'cpg0000_combined_embeddings.csv').is_file(),
             'metadata': (d / 'data' / 'metadata_large_gene2vec_subset.csv').is_file(), 'runtime': python(service) is not None}
    return {'installed': all(parts.values()), 'parts': parts, 'model': MODEL, 'settings': SETTINGS, 'checkpointSha256': _sha_file(ck) if ck.is_file() else None,
            'inputs': {'slots': SLOTS, 'fill': FILL, 'scaling': '8-bit by 0.5–99.8th percentile per channel over the field', 'crop': '96 × 96 px centred on each segmented nucleus'},
            'warning': 'Generated images. Trained on U2OS (JUMP); Hep G2 inputs are out of domain and the channel slots are assumed.'}


_PERT = {}


def perturbations(root, query='', limit=40):
    d = folder(root) / 'data'; key = str(d)
    if key not in _PERT:
        import csv
        emb = {line.split(',', 1)[0] for line in (d / 'cpg0000_combined_embeddings.csv').read_text().splitlines()[1:]}
        out = {}
        with open(d / 'metadata_large_gene2vec_subset.csv', newline='') as fh:
            for r in csv.DictReader(fh):
                b = r['BROAD_SAMPLE']
                if b in emb and b not in out:
                    out[b] = {'id': b, 'type': r['PERT_TYPE'], 'name': r['CPD_NAME'] if r['PERT_TYPE'] == 'Compound' else r['GENE'], 'state': r['STATE']}
        _PERT.clear(); _PERT[key] = sorted(out.values(), key=lambda x: (x['state'] != 'control', x['type'], x['name']))
    q = str(query or '').lower()
    rows = [p for p in _PERT[key] if not q or q in p['name'].lower() or q in p['id'].lower()]
    return {'total': len(_PERT[key]), 'rows': rows[:limit]}


def crops(root, key, n=4):
    """96 × 96 crops around segmented nuclei of one observed field, in the assumed cpg0000 slot order (uint8)."""
    import virtual_cell_microscopy as VM
    from scipy import ndimage as ndi
    fov = next((x for x in VM.images(root) if x['key'] == key), None)
    if fov is None:
        raise ValueError('Unknown field of view.')
    VM.analyse(root, key)
    nuc = np.load(VM.folder(root) / 'features' / f'{key}.masks.npz')['nuclei']
    u8 = {}
    for c, m in fov['channels'].items():
        a = VM._load(root, m).astype(float); lo, hi = np.percentile(a, [0.5, 99.8])
        u8[c] = (np.clip((a - lo) / max(hi - lo, 1), 0, 1) * 255).astype(np.uint8)
    centres = [tuple(int(v) for v in ndi.center_of_mass(nuc == i)) for i in range(1, int(nuc.max()) + 1)]
    h, w = nuc.shape; centres = [(y, x) for y, x in centres if 48 <= y < h - 48 and 48 <= x < w - 48][:n]
    if not centres:
        raise ValueError('No nuclei far enough from the image border for a 96 px crop.')
    arr = np.stack([np.stack([u8[FILL.get(s, s)][y - 48:y + 48, x - 48:x + 48] for s in SLOTS]) for y, x in centres])
    return arr, centres


def _jobs(root):
    d = folder(root) / 'runs'; d.mkdir(parents=True, exist_ok=True)
    return d


def start(root, service, key, perturbation, n=4, seed=0):
    st = status(root, service)
    if not st['installed']:
        raise ValueError('CellFlux is not fully installed: ' + ', '.join(k for k, v in st['parts'].items() if not v))
    if perturbation not in {p['id'] for p in perturbations(root, '', 10 ** 6)['rows']}:
        raise ValueError('Unknown cpg0000 perturbation.')
    n = max(1, min(int(n), 8)); arr, centres = crops(root, key, n)
    rid = hashlib.sha256(json.dumps([hashlib.sha256(arr.tobytes()).hexdigest(), perturbation, int(seed), SETTINGS, st['checkpointSha256']]).encode()).hexdigest()[:24]
    d = _jobs(root) / rid
    if (d / 'out.npy').is_file() or (d / 'pid').is_file() and _alive(d):
        return job(root, rid)
    d.mkdir(exist_ok=True); np.save(d / 'in.npy', arr)
    p = folder(root)
    req = {'src': str(p / 'src'), 'deps': str(p / 'deps'), 'checkpoint': str(p / 'checkpoints' / 'cpg0000.pth'), 'embeddings': str(p / 'data' / 'cpg0000_combined_embeddings.csv'),
           'perturbation': perturbation, 'inputs': str(d / 'in.npy'), 'output': str(d / 'out.npy'), 'seed': int(seed), 'nfe': SETTINGS['nfe'], 'cfg': SETTINGS['cfg'], 'noiseLevel': SETTINGS['noiseLevel']}
    (d / 'request.json').write_text(json.dumps(req))
    (d / 'meta.json').write_text(json.dumps({'id': rid, 'field': key, 'centres': centres, 'perturbation': next(x for x in perturbations(root, perturbation, 10 ** 6)['rows'] if x['id'] == perturbation),
                                             'started': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'model': MODEL, 'checkpointSha256': st['checkpointSha256'], 'inputs': st['inputs'], 'settings': SETTINGS}))
    with open(d / 'log.txt', 'w') as log:
        proc = subprocess.Popen([str(python(service)), '-I', str(pathlib.Path(__file__).with_name('cellflux_runner.py')), str(d / 'request.json')], stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True)
    (d / 'pid').write_text(str(proc.pid))
    return job(root, rid)


def _alive(d):
    try:
        pid = int((d / 'pid').read_text()); os.kill(pid, 0)
        try:
            os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            pass
        os.kill(pid, 0); return True
    except (OSError, ValueError):
        return False


def _png(a):
    import base64, io
    from PIL import Image
    buf = io.BytesIO(); Image.fromarray(a).save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


def _rgb(x):
    """Display composite of one 5-slot crop in [0, 1]: DNA blue, AGP orange, Mito red, ER green (display only)."""
    s = {k: x[i] for i, k in enumerate(SLOTS)}
    r = np.clip(0.9 * s['Mito'] + 0.6 * s['AGP'], 0, 1); g = np.clip(0.55 * s['ER'] + 0.35 * s['AGP'], 0, 1); b = np.clip(0.95 * s['DNA'], 0, 1)
    return (np.dstack([r, g, b]) * 255).astype(np.uint8)


def job(root, rid):
    if not all(c in '0123456789abcdef' for c in str(rid)) or len(str(rid)) != 24:
        raise ValueError('Invalid CellFlux run.')
    d = _jobs(root) / rid
    if not (d / 'meta.json').is_file():
        raise ValueError('That CellFlux run no longer exists.')
    meta = json.loads((d / 'meta.json').read_text())
    if not (d / 'out.npy').is_file():
        running = _alive(d)
        return {**meta, 'state': 'running' if running else 'failed', 'log': (d / 'log.txt').read_text(errors='replace')[-1500:] if (d / 'log.txt').is_file() else ''}
    x = np.load(d / 'in.npy').astype(float) / 255.0; y = np.load(d / 'out.npy')
    run = json.loads((d / 'out.npy.json').read_text())
    import virtual_cell_microscopy as VM
    ident = {s: float(np.mean([np.corrcoef(x[i, k].ravel(), y[i, k].ravel())[0, 1] for i in range(len(x))])) for k, s in enumerate(SLOTS)}
    cell = [(x[i, SLOTS.index('ER')] + x[i, SLOTS.index('AGP')]) > 0.15 for i in range(len(x))]
    in_cell = {s: float(np.mean([np.corrcoef(x[i, k][cell[i]], y[i, k][cell[i]])[0, 1] for i in range(len(x)) if cell[i].sum() > 10])) for k, s in enumerate(SLOTS)}
    nuclei = []
    for i in range(len(x)):
        a, b = x[i, 0], y[i, 0]; ma, mb = a > VM.otsu(a), b > VM.otsu(b)
        nuclei.append({'dice': float(2 * (ma & mb).sum() / max(ma.sum() + mb.sum(), 1)), 'areaFractionIn': float(ma.mean()), 'areaFractionOut': float(mb.mean())})
    dna_ratio = float(y[:, 0].mean() / max(x[:, 0].mean(), 1e-9))
    return {**meta, 'state': 'completed', 'run': run, 'identity': ident, 'identityInCell': in_cell, 'nuclei': nuclei, 'dnaIntensityRatio': dna_ratio,
            'identityNote': 'Input vs generated crop. Whole-crop r is dominated by the cell footprint; in-cell r and the nucleus-mask Dice (Otsu, DNA slot) '
                            'test internal structure. Under DMSO a faithful model keeps the cell (Dice near 1, area fractions unchanged, intensity ratio near 1).',
            'cells': [{'input': _png(_rgb(x[i])), 'generated': _png(_rgb(y[i]))} for i in range(len(x))],
            'evidence': 'C · AI prediction (generated image; not an observation)'}
