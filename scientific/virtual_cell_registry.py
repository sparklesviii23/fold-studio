"""Virtual Cell dataset registry, capability registry and per-context modality coverage.

Datasets extend virtual_cell_plugins.RESOURCES (licence, source, citation, local path) with what a scientist needs to
judge compatibility: organism, cell lines, modality, units, release, and integrity (SHA-256, cached by size + mtime;
files above HASH_LIMIT are recorded by size and modification time only, and say so).

Capabilities are the provider contract (docs/VIRTUAL_CELL_INTEGRATION.md): every module, working or not, is listed with
inputs, outputs, context requirements, runtime, evidence class, validation and integration status, UI entry and
dependencies. `unsupported(cap_id, reason)` is the only allowed answer from a provider that cannot run: it never carries
values.

Coverage states for one modality in one cell context (shown in the interface, never collapsed):
  available       data present and integrated for this context
  not_downloaded  integrated, but the dataset is not in this library
  unmeasured      the integrated source exists but has no measurement for this context
  unsupported     no integrated source covers this modality for this context
  pending         a computation for it is running
  unvalidated     only model output, not benchmarked for this context
"""
import hashlib, json, os, pathlib

import virtual_cell_plugins as plugins

HASH_LIMIT = 200 * 1024 * 1024
COVERAGE = ('available', 'not_downloaded', 'unmeasured', 'unsupported', 'pending', 'unvalidated')
VALIDATION = {'operational_tested': 'Operational and tested', 'integrated_unbenchmarked': 'Integrated but not scientifically benchmarked',
              'partial': 'Partially implemented', 'data_only': 'Data available, integration incomplete', 'model_unavailable': 'Model unavailable',
              'deferred': 'Deferred', 'blocked': 'Blocked by a specified dependency'}
PROVIDERS = ('cell_state', 'dataset', 'model', 'simulation', 'structure', 'image', 'compute', 'evidence')

DATASETS = {
    'norman2019': {'organism': 'Homo sapiens', 'cellLines': ['CVCL_0004'], 'modality': 'single-cell RNA (CRISPRa Perturb-seq)', 'unit': 'log1p(counts per 10,000)', 'release': 'scPerturb Zenodo 7041849'},
    'replogle2022': {'organism': 'Homo sapiens', 'cellLines': ['CVCL_0004'], 'modality': 'single-cell RNA (CRISPRi Perturb-seq)', 'unit': 'log1p(counts per 10,000)', 'release': 'scPerturb'},
    'depmap24q4': {'organism': 'Homo sapiens', 'cellLines': 'DepMap 24Q4 models (incl. CVCL_0027 Hep G2, CVCL_1098 C3A, CVCL_0004 K-562)', 'modality': 'bulk RNA-seq; CRISPR knockout fitness', 'unit': 'log2(TPM+1); Chronos gene effect', 'release': '24Q4'},
    'tahoe100m': {'organism': 'Homo sapiens', 'cellLines': '50 cancer lines (incl. CVCL_1098 HepG2/C3A; not parental HepG2)', 'modality': 'single-cell RNA drug response', 'unit': 'DESeq2 log2 fold change vs DMSO', 'release': 'Tahoe-100M'},
    'humangem': {'organism': 'Homo sapiens', 'cellLines': 'generic (not cell-line specific)', 'modality': 'genome-scale metabolic model', 'unit': 'flux (mmol/gDW/h)', 'release': 'v2.1.1'},
    'sparced': {'organism': 'Homo sapiens', 'cellLines': 'MCF10A parameters', 'modality': 'mechanistic signalling ODE model', 'unit': 'nM', 'release': 'commit a957f960'},
    'gbcell': {'organism': 'Homo sapiens', 'cellLines': 'pretrained on many tissues', 'modality': 'single-cell foundation model', 'unit': 'embedding', 'release': 'GB.Cell-3M'},
    'hpa_subcellular': {'organism': 'Homo sapiens', 'cellLines': 'several HPA imaging lines; general annotation', 'modality': 'protein subcellular localization (immunofluorescence)', 'unit': 'location call + reliability', 'release': 'HPA download (see manifest retrieved date)'},
    'uniprot_human': {'organism': 'Homo sapiens', 'cellLines': 'not cell-line specific', 'modality': 'protein identifiers and curated annotations', 'unit': None, 'release': 'UniProtKB/Swiss-Prot (see manifest retrieved date)'},
    'reactome': {'organism': 'Homo sapiens', 'cellLines': 'not cell-line specific', 'modality': 'pathway membership and hierarchy', 'unit': None, 'release': 'see annotations manifest (release number)'},
    'encode_hepg2_rna': {'organism': 'Homo sapiens', 'cellLines': ['CVCL_0027'], 'modality': 'bulk RNA-seq transcript quantification (RSEM)', 'unit': 'TPM (RSEM); IsoPct', 'release': 'ENCODE ENCSR000CPE, GENCODE V29'},
    'gerard2009': {'organism': 'Mammalian (generic)', 'cellLines': 'not calibrated to any cell line', 'modality': 'mechanistic cell-cycle ODE model', 'unit': 'dimensionless concentrations (µM scale), time in h', 'release': 'BioModels BIOMD0000000730'},
}

CAPABILITIES = [
    {'id': 'vcell.state', 'provider': 'cell_state', 'module': 'virtual_cell.py, virtual_cell_state.py', 'inputs': ['context', 'operation history'], 'outputs': ['replayed state', 'snapshots', 'comparison', 'bundle'],
     'context': 'any', 'runtime': 'local CPU', 'evidence': 'inherits from each value block', 'validation': 'operational_tested', 'ui': 'Virtual Cell › History & snapshots', 'dependencies': []},
    {'id': 'vcell.expression.baseline', 'provider': 'dataset', 'module': 'virtual_cell.py', 'inputs': ['context'], 'outputs': ['gene expression baseline'], 'context': 'K-562, Tahoe lines, Hep G2',
     'runtime': 'local', 'evidence': 'measured', 'validation': 'operational_tested', 'ui': 'Readouts › Expression', 'dependencies': ['norman2019 | depmap24q4']},
    {'id': 'vcell.transitions', 'provider': 'model', 'module': 'virtual_cell.py, perturb_model.py', 'inputs': ['over-expression', 'knockdown', 'drug'], 'outputs': ['expression change'],
     'context': 'K-562 (genetic); Tahoe lines (drugs)', 'runtime': 'local', 'evidence': 'measured / prediction', 'validation': 'operational_tested', 'ui': 'Simulations', 'dependencies': ['norman2019', 'replogle2022', 'tahoe100m'],
     'benchmark': 'held-out Pearson r per transition (docs/VIRTUAL_CELL.md)'},
    {'id': 'vcell.fitness', 'provider': 'dataset', 'module': 'virtual_cell.py', 'inputs': ['knocked-out genes'], 'outputs': ['Chronos gene effect'], 'context': 'DepMap-screened lines',
     'runtime': 'local', 'evidence': 'measured', 'validation': 'operational_tested', 'ui': 'Readouts › Fitness', 'dependencies': ['depmap24q4']},
    {'id': 'vcell.metabolism', 'provider': 'simulation', 'module': 'virtual_cell_metabolism.py', 'inputs': ['knockouts'], 'outputs': ['flux-balance growth'], 'context': 'generic network',
     'runtime': 'local', 'evidence': 'simulation', 'validation': 'integrated_unbenchmarked', 'ui': 'Readouts › Metabolism', 'dependencies': ['humangem']},
    {'id': 'vcell.signalling', 'provider': 'simulation', 'module': 'virtual_cell_signalling.py', 'inputs': ['expression changes'], 'outputs': ['24 h signalling trajectories'], 'context': 'MCF10A parameters (hypothesis elsewhere)',
     'runtime': 'local', 'evidence': 'simulation', 'validation': 'integrated_unbenchmarked', 'ui': 'Readouts › Signalling', 'dependencies': ['sparced']},
    {'id': 'vcell.protein', 'provider': 'evidence', 'module': 'virtual_cell_annotations.py', 'inputs': ['symbol | UniProt | Ensembl'], 'outputs': ['identifiers', 'localization', 'pathways', 'PDB references'],
     'context': 'any (annotations are not cell-line specific)', 'runtime': 'local', 'evidence': 'annotation', 'validation': 'operational_tested', 'ui': 'Protein & pathways', 'dependencies': ['hpa_subcellular', 'uniprot_human', 'reactome']},
    {'id': 'vcell.pathways', 'provider': 'evidence', 'module': 'virtual_cell_annotations.py', 'inputs': ['pathway id | changed genes'], 'outputs': ['members with expression', 'enrichment'],
     'context': 'any', 'runtime': 'local', 'evidence': 'annotation / statistic', 'validation': 'operational_tested', 'ui': 'Protein & pathways', 'dependencies': ['reactome']},
    {'id': 'vcell.transcripts', 'provider': 'dataset', 'module': 'virtual_cell_transcripts.py', 'inputs': ['gene'], 'outputs': ['transcript TPM per replicate', 'exon structure'],
     'context': 'Hep G2 (parental) only', 'runtime': 'local', 'evidence': 'measured / annotation', 'validation': 'operational_tested', 'ui': 'Protein & pathways › Transcripts', 'dependencies': ['encode_hepg2_rna']},
    {'id': 'vcell.cellcycle', 'provider': 'simulation', 'module': 'virtual_cell_cycle.py (Mechanistic Lab solver)', 'inputs': ['growth-factor level', 'duration'], 'outputs': ['44-species time series', 'Cdk-module labels'],
     'context': 'generic mammalian; not calibrated to any line', 'runtime': 'local CPU (≈10 s for 200 h)', 'evidence': 'simulation', 'validation': 'integrated_unbenchmarked', 'ui': 'Cell-cycle timeline', 'dependencies': ['gerard2009']},
    {'id': 'vcell.proteomics', 'provider': 'dataset', 'module': None, 'inputs': ['protein'], 'outputs': ['measured abundance'], 'context': 'needs a line-matched proteomics dataset',
     'runtime': None, 'evidence': 'measured', 'validation': 'deferred', 'ui': 'Protein panel (shows unavailable)', 'dependencies': ['a verified HepG2 proteomics dataset (docs/VIRTUAL_CELL_DEFERRED_WORK.md)']},
    {'id': 'vcell.microscopy', 'provider': 'image', 'module': None, 'inputs': ['context'], 'outputs': ['multichannel images', 'morphology features'], 'context': 'needs line-matched imaging',
     'runtime': None, 'evidence': 'measured', 'validation': 'deferred', 'ui': None, 'dependencies': ['RxRx1 (HepG2, 46 GB single archive, needs approval) or another HepG2 Cell Painting set']},
    {'id': 'vcell.microscopy.generative', 'provider': 'image', 'module': None, 'inputs': ['perturbation'], 'outputs': ['generated images'], 'context': 'model training domain only',
     'runtime': 'GPU', 'evidence': 'prediction', 'validation': 'model_unavailable', 'ui': None, 'dependencies': ['morphodiff plugin: weights, licence and held-out evaluation']},
    {'id': 'vcell.structures', 'provider': 'structure', 'module': 'virtual_cell_annotations.py (PDB cross-references)', 'inputs': ['protein'], 'outputs': ['PDB identifiers'], 'context': 'any',
     'runtime': 'local', 'evidence': 'annotation', 'validation': 'partial', 'ui': 'Protein panel › Structures', 'dependencies': ['opening saved Boltz / AlphaFold results from the Molecular Laboratory is not connected yet']},
    {'id': 'vcell.compute', 'provider': 'compute', 'module': 'gpu_tasks.py (existing Modal lifecycle)', 'inputs': ['recipe'], 'outputs': ['cost-gated remote job'], 'context': 'n/a',
     'runtime': 'Modal', 'evidence': 'n/a', 'validation': 'partial', 'ui': 'Discover › Cloud GPU tasks', 'dependencies': ['no Virtual Cell recipe is routed through it yet']},
]


def unsupported(cap_id, reason, needs=None):
    """The structured answer of a provider that cannot run. Carries no values by construction."""
    return {'supported': False, 'capability': cap_id, 'reason': reason, 'needs': needs or [], 'values': None}


def _checksums(root):
    f = pathlib.Path(root) / 'virtualcell' / 'registry' / 'checksums.json'
    return f, (json.loads(f.read_text()) if f.is_file() else {})


def integrity(root, path):
    """SHA-256 of a file (directories: of their sorted file listing with sizes), cached by size and mtime."""
    p = pathlib.Path(root) / path
    if not p.exists():
        return {'present': False}
    target = p if p.is_file() else None
    st = p.stat(); key = f'{path}|{st.st_size}|{int(st.st_mtime)}'
    cf, cache = _checksums(root)
    if key in cache:
        return cache[key]
    if target is None:
        listing = sorted((str(q.relative_to(p)), q.stat().st_size) for q in p.rglob('*') if q.is_file())
        out = {'present': True, 'kind': 'directory', 'files': len(listing), 'sha256': hashlib.sha256(json.dumps(listing).encode()).hexdigest(), 'hashed': 'listing (names + sizes)'}
    elif st.st_size > HASH_LIMIT:
        out = {'present': True, 'kind': 'file', 'bytes': st.st_size, 'sha256': None, 'hashed': f'not hashed: larger than {HASH_LIMIT // 2**20} MB (size and mtime recorded)'}
    else:
        h = hashlib.sha256()
        with open(p, 'rb') as fh:
            for b in iter(lambda: fh.read(1 << 20), b''):
                h.update(b)
        out = {'present': True, 'kind': 'file', 'bytes': st.st_size, 'sha256': h.hexdigest(), 'hashed': 'full file'}
    out['modified'] = int(st.st_mtime)
    cache[key] = out; cf.parent.mkdir(parents=True, exist_ok=True); cf.write_text(json.dumps(cache, indent=1))
    return out


def datasets(root, verify=False):
    rows = []
    for k, r in plugins.RESOURCES.items():
        meta = DATASETS.get(k, {})
        present = (pathlib.Path(root) / r['localPath']).exists()
        row = {'id': k, 'name': r['name'], 'kind': r['kind'], 'source': r['source'], 'citation': r['citation'], 'licence': r['licence'], 'licenceVerified': r['licenceVerified'],
               'nonCommercial': r['nonCommercial'], 'localPath': r['localPath'], 'status': 'available' if present else 'not_downloaded', **meta}
        if verify and present:
            row['integrity'] = integrity(root, r['localPath'])
        rows.append(row)
    return rows


def manifest(root, ids):
    """Dataset provenance attached to a snapshot or export: identity, release and integrity of each dataset used."""
    by = {r['id']: r for r in datasets(root)}
    return [{'id': i, 'name': by[i]['name'], 'release': by[i].get('release'), 'licence': by[i]['licence'], 'source': by[i]['source'],
             'integrity': integrity(root, by[i]['localPath']) if by[i]['status'] == 'available' else {'present': False}} for i in ids if i in by]


def coverage(root, ref, jobs=None):
    """Modality → coverage state for one cell context. ref is a virtual_cell context reference."""
    kind, rrid = ref.kind, getattr(ref, 'cellosaurus', 'CVCL_0004')
    ds = {r['id']: r['status'] for r in datasets(root)}
    has = lambda i: ds.get(i) == 'available'
    out = {}

    def put(mod, state, source=None, note=None):
        assert state in COVERAGE
        out[mod] = {'state': state, 'source': source, 'note': note}
    put('gene expression (baseline)', 'available', 'Norman 2019 controls' if kind == 'k562' else 'DepMap 24Q4 bulk RNA-seq')
    put('knockout fitness', 'available' if ref.depmap else ('not_downloaded' if not has('depmap24q4') else 'unmeasured'), 'DepMap 24Q4 Chronos')
    if rrid == 'CVCL_0027':
        put('transcript isoforms', 'available' if has('encode_hepg2_rna') else 'not_downloaded', 'ENCODE ENCSR000CPE (RSEM, 2 replicates)')
    else:
        put('transcript isoforms', 'unsupported', None, 'No integrated transcript-level dataset for this line.')
    put('protein localization', 'available' if has('hpa_subcellular') else 'not_downloaded', 'HPA / UniProt (general human annotation)')
    put('pathways', 'available' if has('reactome') else 'not_downloaded', 'Reactome')
    put('protein abundance', 'unsupported', None, 'No verified proteomics dataset integrated for this line.')
    put('microscopy / morphology', 'unsupported', None, 'No line-matched imaging dataset integrated (see deferred work).')
    put('cell-cycle dynamics', 'unvalidated' if has('gerard2009') else 'not_downloaded', 'Gérard & Goldbeter 2009 (generic mammalian model)', 'Not calibrated to this line.')
    put('drug response', 'available' if kind in ('tahoe', 'k562') and has('tahoe100m') else 'unsupported', 'Tahoe-100M' + (' (transferred to K-562)' if kind == 'k562' else ''),
        'Parental Hep G2 is not in Tahoe-100M; HepG2/C3A is a separate context.' if rrid == 'CVCL_0027' else None)
    for name in (jobs or []):
        if name in out:
            out[name]['state'] = 'pending'
    return out


def capabilities():
    return [{**c, 'validationLabel': VALIDATION[c['validation']]} for c in CAPABILITIES]
