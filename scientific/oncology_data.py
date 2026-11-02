"""Oncology data foundation: versioned, checksummed local copies of public cancer datasets.

Each dataset release lives in <library>/oncology/<source>/<release>/ with:
  manifest.json   source, release, licence, citation, every original file with its MD5 (verified) and the derived files
  models.json     cell-model metadata (DepMap Model.csv, original column values preserved)
  <matrix>.npy    float32 model × gene matrix (memory-mapped on read; NaN = not measured)
  <matrix>.json   row (ModelID) and column (symbol, Entrez) identifiers

Original values are preserved: matrices are converted to float32 without transformation. Files that cannot be fetched by
script (e.g. a portal behind a browser verification page) can be imported from a browser download; their checksums are
recorded, and verified when the source publishes them.
"""
import csv
import hashlib
import json
import pathlib
import re
import time
import urllib.request

# DepMap 24Q4 Public on Figshare+ (DOI 10.25452/figshare.plus.27993248.v1, CC BY 4.0): newest release downloadable by script.
DEPMAP = {
    '24Q4': {
        'doi': '10.25452/figshare.plus.27993248.v1', 'licence': 'CC BY 4.0',
        'citation': 'DepMap, Broad (2024). DepMap 24Q4 Public. Figshare+. Dataset. https://doi.org/10.25452/figshare.plus.27993248.v1',
        'files': {
            'Model.csv': ('https://ndownloader.figshare.com/files/51065297', '675210d17675f3517b0ce39a3c274f16'),
            'CRISPRGeneEffect.csv': ('https://ndownloader.figshare.com/files/51064667', '6edf7ade09b9b34199210b559d4745d3'),
            'OmicsSomaticMutationsMatrixHotspot.csv': ('https://ndownloader.figshare.com/files/51065750', 'a5aeb1deef897ead3c955c372148d840'),
            'OmicsSomaticMutationsMatrixDamaging.csv': ('https://ndownloader.figshare.com/files/51065747', 'cb20fdbe1cf3b9b0d8ed4f53e1f399b6'),
            'OmicsExpressionProteinCodingGenesTPMLogp1.csv': ('https://ndownloader.figshare.com/files/51065489', '71794802b750ce77c422dad0720a40af'),
            'README.txt': ('https://ndownloader.figshare.com/files/51065795', '54628c15a10b9ff6536db245cfed5231'),
        },
    },
}
MATRICES = {  # original file → (derived name, what it is, evidence category)
    'CRISPRGeneEffect.csv': ('gene_effect', 'Chronos CRISPR gene effect (copy-number and guide-efficacy corrected estimate; 0 = no effect, −1 ≈ median common-essential)', 'Statistical estimate from a measured CRISPR screen'),
    'OmicsSomaticMutationsMatrixHotspot.csv': ('mut_hotspot', 'Hotspot somatic mutation count per gene', 'Experimental observation (sequencing)'),
    'OmicsSomaticMutationsMatrixDamaging.csv': ('mut_damaging', 'Damaging somatic mutation count per gene', 'Experimental observation (sequencing)'),
    'OmicsExpressionProteinCodingGenesTPMLogp1.csv': ('expression', 'RNA expression, log2(TPM + 1)', 'Experimental observation (RNA-seq)'),
}
GENE = re.compile(r'^(.*?) \((\d+)\)$')


def root(s, source='depmap', release=None):
    p = pathlib.Path(s.root) / 'oncology' / source
    return p / release if release else p


def _md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def _fetch(url, md5, dest, log):
    if dest.is_file() and _md5(dest) == md5:
        log(f'{dest.name}: already present, MD5 verified')
        return
    part = dest.with_suffix(dest.suffix + '.part')
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'FoldStudio/oncology-data'}), timeout=120) as r, open(part, 'wb') as f:
        total, got, last = int(r.headers.get('Content-Length') or 0), 0, 0
        for b in iter(lambda: r.read(1 << 22), b''):
            f.write(b); got += len(b)
            if time.time() - last > 5:
                last = time.time(); log(f'{dest.name}: {got / 1e6:.0f}/{total / 1e6:.0f} MB')
    if _md5(part) != md5:
        part.unlink()
        raise ValueError(f'{dest.name}: MD5 mismatch against the published checksum; file discarded.')
    part.replace(dest)
    log(f'{dest.name}: downloaded, MD5 {md5} verified')


def _matrix(src, out, name):
    """CSV (first column = ModelID, columns = 'SYMBOL (Entrez)') → float32 .npy + identifiers. Values unchanged."""
    import numpy as np
    with open(src, newline='') as f:
        rd = csv.reader(f)
        head = next(rd)
        # Some releases add metadata columns before the genes; genes are the 'SYMBOL (Entrez)' columns.
        gcols = [i for i, h in enumerate(head) if GENE.match(h)]
        idcol = next((i for i, h in enumerate(head) if h in ('ModelID', '')), 0)
        rows, data = [], []
        for line in rd:
            mid = line[idcol]
            if not mid.startswith('ACH-'):
                continue
            rows.append(mid)
            data.append([float(line[i]) if line[i] not in ('', 'NA', 'nan') else float('nan') for i in gcols])
    M = np.asarray(data, dtype=np.float32)
    np.save(out / f'{name}.npy', M)
    genes = [GENE.match(head[i]).groups() for i in gcols]
    (out / f'{name}.json').write_text(json.dumps({'models': rows, 'genes': [g[0] for g in genes], 'entrez': [g[1] for g in genes]}))
    return M.shape


def _models(src, out):
    with open(src, newline='') as f:
        rows = list(csv.DictReader(f))
    (out / 'models.json').write_text(json.dumps(rows))
    return len(rows)


def depmap_install(s, release='24Q4', log=print):
    spec = DEPMAP[release]
    out = root(s, 'depmap', release); raw = out / 'original'; raw.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, (url, md5) in spec['files'].items():
        _fetch(url, md5, raw / name, log)
        files[name] = {'url': url, 'md5': md5, 'verified': True, 'bytes': (raw / name).stat().st_size}
    return _derive(s, out, 'depmap', release, files, spec, log)


def depmap_import(s, folder, release, log=print):
    """A release downloaded in the browser (e.g. 26Q3 from depmap.org, which blocks scripts): checksummed and converted."""
    if not re.fullmatch(r'\d\dQ[1-4]', release):
        raise ValueError('Release must look like 26Q3.')
    src = pathlib.Path(folder)
    out = root(s, 'depmap', release); raw = out / 'original'; raw.mkdir(parents=True, exist_ok=True)
    files = {}
    for name in ['Model.csv', *MATRICES]:
        f = src / name
        if not f.is_file():
            if name in ('Model.csv', 'CRISPRGeneEffect.csv'):
                raise ValueError(f'{name} is required in the chosen folder.')
            continue
        (raw / name).write_bytes(f.read_bytes())
        files[name] = {'url': 'imported from a browser download', 'md5': _md5(raw / name), 'verified': False, 'bytes': f.stat().st_size,
                       'note': 'Checksum recorded; the portal did not provide one to verify against.'}
    spec = {'doi': None, 'licence': 'See depmap.org terms (CC BY 4.0 for DepMap Public releases)', 'citation': f'DepMap, Broad. DepMap {release} Public. https://depmap.org/portal/'}
    return _derive(s, out, 'depmap', release, files, spec, log)


def _derive(s, out, source, release, files, spec, log):
    raw = out / 'original'
    n = _models(raw / 'Model.csv', out)
    derived = {'models.json': {'rows': n}}
    for name, (dname, what, evidence) in MATRICES.items():
        if (raw / name).is_file():
            log(f'converting {name}…')
            shape = _matrix(raw / name, out, dname)
            derived[dname] = {'from': name, 'shape': list(shape), 'description': what, 'evidence': evidence, 'transform': 'none (float32 copy of the published values)'}
    manifest = {'source': source, 'release': release, 'doi': spec.get('doi'), 'licence': spec['licence'], 'citation': spec['citation'],
                'installed': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'original': files, 'derived': derived}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1))
    log(f'DepMap {release} ready: ' + ', '.join(f'{k} {v.get("shape", v.get("rows"))}' for k, v in derived.items()))
    return manifest


def releases(s, source='depmap'):
    r = root(s, source)
    out = []
    for d in sorted(r.iterdir() if r.is_dir() else [], reverse=True):
        m = d / 'manifest.json'
        if m.is_file():
            out.append(json.loads(m.read_text()))
    return out


class Release:
    """Lazy, memory-mapped access to an installed release."""

    def __init__(self, s, release=None, source='depmap'):
        rel = release or next((m['release'] for m in releases(s, source)), None)
        if not rel:
            raise ValueError('No DepMap release is installed yet. Install one from Oncology › Data.')
        self.dir = root(s, source, rel); self.release = rel
        self.manifest = json.loads((self.dir / 'manifest.json').read_text())
        self.models = {m['ModelID']: m for m in json.loads((self.dir / 'models.json').read_text())}
        self._m = {}

    def matrix(self, name):
        import numpy as np
        if name not in self._m:
            if not (self.dir / f'{name}.npy').is_file():
                raise ValueError(f'{name} is not part of DepMap {self.release} as installed.')
            ids = json.loads((self.dir / f'{name}.json').read_text())
            self._m[name] = (np.load(self.dir / f'{name}.npy', mmap_mode='r'), ids['models'], ids['genes'], {g: i for i, g in enumerate(ids['genes'])}, ids['entrez'])
        return self._m[name]


# GDSC release 8.5 (Wellcome Sanger Institute; measured cell-line drug responses). Object-store ETags are the files' MD5s.
GDSC = {
    '8.5': {
        'licence': 'GDSC terms of use (free for academic and non-commercial research; see cancerrxgene.org/legal)',
        'citation': 'Iorio F et al. A landscape of pharmacogenomic interactions in cancer. Cell 2016;166:740–754; Yang W et al. Nucleic Acids Res 2013;41:D955. GDSC release 8.5.',
        'files': {
            'GDSC1_fitted_dose_response_27Oct23.csv': ('https://cog.sanger.ac.uk/cancerrxgene/GDSC_release8.5/GDSC1_fitted_dose_response_27Oct23.csv', 'b316e41cbc7c5294c0f52485ea2836f4'),
            'GDSC2_fitted_dose_response_27Oct23.csv': ('https://cog.sanger.ac.uk/cancerrxgene/GDSC_release8.5/GDSC2_fitted_dose_response_27Oct23.csv', '9fb8b4fa73dc57a80f0fd2ca2773b0fe'),
            'screened_compounds_rel_8.5.csv': ('https://cog.sanger.ac.uk/cancerrxgene/GDSC_release8.5/screened_compounds_rel_8.5.csv', '1f8a7c36e02f3298704063f104b5ff81'),
        },
    },
}


def gdsc_install(s, release='8.5', log=print):
    """Fitted dose–response (LN_IC50 in ln µM, AUC, curve RMSE, Z-score) kept exactly as published, one row per curve."""
    import numpy as np
    spec = GDSC[release]
    out = root(s, 'gdsc', release); raw = out / 'original'; raw.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, (url, md5) in spec['files'].items():
        _fetch(url, md5, raw / name, log)
        files[name] = {'url': url, 'md5': md5, 'verified': True, 'bytes': (raw / name).stat().st_size}
    cols = {k: [] for k in ('dataset', 'model', 'cosmic', 'drug', 'ln_ic50', 'auc', 'rmse', 'z', 'min_conc', 'max_conc')}
    drugs = {}
    for name in files:
        if 'fitted_dose_response' not in name:
            continue
        with open(raw / name, newline='') as f:
            for r in csv.DictReader(f):
                key = r['DATASET'] + ':' + r['DRUG_ID']
                drugs.setdefault(key, {'key': key, 'dataset': r['DATASET'], 'id': r['DRUG_ID'], 'name': r['DRUG_NAME'], 'target': r['PUTATIVE_TARGET'], 'pathway': r['PATHWAY_NAME']})
                cols['dataset'].append(r['DATASET']); cols['model'].append(r['SANGER_MODEL_ID']); cols['cosmic'].append(r['COSMIC_ID']); cols['drug'].append(key)
                for k, c in (('ln_ic50', 'LN_IC50'), ('auc', 'AUC'), ('rmse', 'RMSE'), ('z', 'Z_SCORE'), ('min_conc', 'MIN_CONC'), ('max_conc', 'MAX_CONC')):
                    cols[k].append(float(r[c]) if r[c] else float('nan'))
    np.savez_compressed(out / 'responses.npz', **{k: np.array(v, dtype=object if k in ('dataset', 'model', 'cosmic', 'drug') else np.float64) for k, v in cols.items()})
    (out / 'drugs.json').write_text(json.dumps(list(drugs.values())))
    manifest = {'source': 'gdsc', 'release': release, 'licence': spec['licence'], 'citation': spec['citation'], 'installed': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'original': files, 'derived': {'responses.npz': {'curves': len(cols['model']), 'units': 'LN_IC50 = natural log of IC50 in µM; AUC on the screened range (0–1)',
                                                                    'evidence': 'Experimental observation (fitted cell-viability dose–response curves)', 'transform': 'none'},
                                               'drugs.json': {'drugs': len(drugs)}},
                'identifiers': 'SANGER_MODEL_ID; mapped to DepMap ModelID through DepMap Model.csv SangerModelID'}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1))
    log(f'GDSC {release} ready: {len(cols["model"])} curves, {len(drugs)} drug–screen pairs')
    return manifest


if __name__ == '__main__':
    import sys, types
    lib, what = sys.argv[1], sys.argv[2]
    s = types.SimpleNamespace(root=lib)
    if what == 'gdsc':
        gdsc_install(s)
    elif len(sys.argv) > 4:
        depmap_import(s, sys.argv[3], sys.argv[4])
    else:
        depmap_install(s)
