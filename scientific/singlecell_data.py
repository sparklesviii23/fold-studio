"""CELLxGENE Discover datasets for the tumor single-cell lab: download one public H5AD with its curation metadata.

Stored in <library>/oncology/singlecell/<dataset_id>/ (dataset.h5ad, cellxgene_metadata.json, manifest.json with SHA-256).
CELLxGENE publishes no file checksums; SHA-256 is recorded at download. Also fetches MSigDB Hallmark v2025.1 (CC BY 4.0).
"""
import hashlib
import json
import os
import pathlib
import re
import sys
import time
import urllib.request

API = 'https://api.cellxgene.cziscience.com/curation/v1/datasets/'
HALLMARK = 'https://data.broadinstitute.org/gsea-msigdb/msigdb/release/2025.1.Hs/h.all.v2025.1.Hs.symbols.gmt'
CURATED = [{'id': '14363b6e-3428-45b0-8704-10fd5d6316df', 'title': 'Basal cell carcinoma vs normal skin epithelium (PNAS 2023)', 'cellType': 'hair follicular keratinocyte',
            'case': 'basal cell carcinoma', 'control': 'normal', 'site': 'face', 'expected': 'Hedgehog pathway activation (GLI1, PTCH1, HHIP) in BCC'}]


def root(lib, *p, kind='singlecell'):
    d = pathlib.Path(lib) / 'oncology' / kind / pathlib.Path(*p)
    d.mkdir(parents=True, exist_ok=True)
    return d


def python(s):
    """The isolated single-cell runtime: setting, environment, then a 'runtimes/singlecell' folder above the app."""
    for c in (s.setting('singlecellPython'), os.environ.get('FOLD_SINGLECELL_PYTHON')):
        if c and pathlib.Path(c).is_file():
            return pathlib.Path(c)
    for parent in pathlib.Path(__file__).resolve().parents:
        p = parent / 'runtimes' / 'singlecell' / 'bin' / 'python'
        if p.is_file():
            return p
    return None


CANCER = re.compile(r'carcinoma|cancer|tumou?r|neoplasm|melanoma|glioma|glioblastoma|lymphoma|leukemia|sarcoma|blastoma|adenoma|myeloma|mesothelioma', re.I)
SPATIAL_ASSAYS = ('Visium', 'Slide-seq')


def catalog(lib, refresh=False):
    """Every public human cancer spatial dataset on CELLxGENE Discover (Visium and Slide-seq), cached for a day."""
    f = root(lib, kind='spatial') / 'catalog.json'
    if f.is_file() and not refresh and time.time() - f.stat().st_mtime < 86400:
        return json.loads(f.read_text())
    every = json.loads(urllib.request.urlopen(API.rstrip('/'), timeout=180).read())
    rows = []
    for x in every:
        assay = [a['label'] for a in x.get('assay', [])]
        disease = [z['label'] for z in x.get('disease', []) if CANCER.search(z['label'])]
        if not disease or not any(k in a for a in assay for k in SPATIAL_ASSAYS):
            continue
        h5 = next((a for a in x['assets'] if a['filetype'] == 'H5AD'), {})
        rows.append({'id': x['dataset_id'], 'title': x['title'], 'collection': x.get('collection_name'), 'citation': x.get('citation'), 'doi': x.get('collection_doi'),
                     'disease': disease, 'tissue': [t['label'] for t in x.get('tissue', [])], 'assay': assay[0], 'spots': x.get('cell_count'),
                     'sizeMB': round((h5.get('filesize') or 0) / 1e6, 1), 'organism': [o['label'] for o in x.get('organism', [])], 'published': (x.get('published_at') or '')[:10]})
    out = {'retrieved': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'source': API.rstrip('/'), 'datasets': sorted(rows, key=lambda r: (r['disease'][0], r['title']))}
    f.write_text(json.dumps(out)); return out


def fetch(lib, dataset_id, kind='singlecell'):
    if not re.fullmatch(r'[0-9a-f-]{36}', dataset_id):
        raise SystemExit('Invalid CELLxGENE dataset id.')
    d = root(lib, dataset_id, kind=kind)
    # The curation API serves a dataset through its version list; the newest published version is used and recorded.
    versions = json.loads(urllib.request.urlopen(API + dataset_id + '/versions', timeout=120).read())
    meta = max(versions, key=lambda v: v.get('published_at') or '')
    (d / 'cellxgene_metadata.json').write_text(json.dumps(meta, indent=1))
    url = next(a['url'] for a in meta['assets'] if a['filetype'] == 'H5AD')
    print(f'downloading {meta["title"]} ({meta.get("cell_count")} cells)', flush=True)
    urllib.request.urlretrieve(url, d / 'dataset.h5ad.part'); (d / 'dataset.h5ad.part').replace(d / 'dataset.h5ad')
    g = pathlib.Path(lib) / 'oncology' / 'genesets'; g.mkdir(parents=True, exist_ok=True)
    if not (g / 'h.all.v2025.1.Hs.symbols.gmt').is_file():
        urllib.request.urlretrieve(HALLMARK, g / 'h.all.v2025.1.Hs.symbols.gmt')
    sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
    m = {'source': 'CZ CELLxGENE Discover', 'datasetId': dataset_id, 'datasetVersionId': meta.get('dataset_version_id'), 'title': meta['title'], 'citation': meta.get('citation'),
         'collectionDoi': meta.get('collection_doi'), 'url': url, 'sha256': sha(d / 'dataset.h5ad'), 'checksumPublished': False, 'hallmark': {'url': HALLMARK, 'sha256': sha(g / 'h.all.v2025.1.Hs.symbols.gmt'), 'licence': 'CC BY 4.0'},
         'licence': 'CELLxGENE Discover data are CC BY 4.0 unless the collection states otherwise', 'installed': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (d / 'manifest.json').write_text(json.dumps(m, indent=1)); print('ready', m['sha256'], flush=True)


if __name__ == '__main__':
    fetch(sys.argv[1], sys.argv[2], *sys.argv[3:4])
