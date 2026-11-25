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
    'paxdb_hepg2': {'organism': 'Homo sapiens', 'cellLines': ['CVCL_0027'], 'modality': 'protein abundance (mass spectrometry)', 'unit': 'ppm (PaxDb)', 'release': 'PaxDb latest; Geiger et al. 2012 iBAQ and spectral counting'},
    'cellpainting_hepg2': {'organism': 'Homo sapiens', 'cellLines': ['CVCL_0027'], 'modality': 'Cell Painting fluorescence microscopy (4 channels: DNA, ER, AGP, Mito)', 'unit': 'raw 16-bit intensity; pixels', 'release': 'Cell Painting Gallery cpg0036 (EU-OS Bioactives), FMP batch 2021_09_03'},
    'cellflux': {'organism': 'Homo sapiens', 'cellLines': 'trained on U2OS (JUMP cpg0000)', 'modality': 'generative Cell Painting model', 'unit': 'generated 8-bit-normalised crops', 'release': 'commit 041c4c0; HF suyc21/CellFlux cpg0000 checkpoint (epoch 79)'},
    'gerard2009': {'organism': 'Mammalian (generic)', 'cellLines': 'not calibrated to any cell line', 'modality': 'mechanistic cell-cycle ODE model', 'unit': 'dimensionless concentrations (µM scale), time in h', 'release': 'BioModels BIOMD0000000730'},
}

CAPABILITIES = [
    {'id': 'rna.design.secondary', 'provider': 'model', 'module': 'rna_design.py, rna_design_core.py',
     'inputs': ['8–128 nt nested dot-bracket target', 'RNA IUPAC mask and locked bases', 'run limits'],
     'outputs': ['distinct sequences', 'predicted folds and pair errors', 'independent check', 'sealed result and run ID'],
     'context': 'isolated RNA at 37 °C; no cell context', 'runtime': 'ViennaRNA 2.7.2; This Mac CPU or bounded Modal CPU sandbox',
     'evidence': 'computational prediction; solver labels; experimental evidence absent', 'validation': 'partial',
     'ui': 'RNA Lab › Design; Research Library › Explore', 'dependencies': ['ViennaRNA 2.7.2', 'RNA Lab reduced Turner model'],
     'limits': 'Nested structures only. No atomic coordinates or cell outcomes. Inverse Qwen is a research pilot.'},
    {'id': 'qwen.rna.secondary', 'provider': 'model', 'module': 'qwen_rna.py, qwen_rna_runtime.py, qwen_rna_model.py',
     'inputs': ['8–128 ACGU sequence', 'optional reference dot-bracket'], 'outputs': ['pair marginals', 'nested fold', 'per-base and region entropy', 'immutable experiment'],
     'context': 'isolated RNA; no cell context', 'runtime': 'qualified external PyTorch/Transformers runtime; Apple MPS or CPU',
     'evidence': 'reference-annotation-trained prediction; uncalibrated uncertainty', 'validation': 'partial',
     'ui': 'Biological Models › Model workbench; RNA Lab › Predict; Molecular Viewer › RNA fold',
     'dependencies': ['local Qwen2.5-Coder-3B pinned checkpoint', 'qwen-rna/pilot-v1', 'qwen_rna_install.json'],
     'benchmark': '24 family-held-out ArchiveII SRP cases; low F1, no superiority; docs/QWEN_RNA_ENGINE.md'},
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
    {'id': 'vcell.proteomics', 'provider': 'dataset', 'module': 'virtual_cell_proteomics.py (PaxDb importer + generic TSV/CSV importer)', 'inputs': ['protein', 'context'],
     'outputs': ['measured abundance (ppm) with rank', 'pathway member abundance', 'RNA–protein rank correlation'], 'context': 'Hep G2 (Geiger 2012 via PaxDb); others need a dataset',
     'runtime': 'local', 'evidence': 'measured', 'validation': 'operational_tested', 'ui': 'Protein panel › Abundance; RNA vs protein', 'dependencies': ['paxdb_hepg2']},
    {'id': 'vcell.microscopy', 'provider': 'image', 'module': 'virtual_cell_microscopy.py (SciPy segmentation; per-cell morphology)', 'inputs': ['context', 'field of view'],
     'outputs': ['observed multichannel images', 'nucleus / cell masks', 'per-cell shape, intensity, texture'], 'context': 'Hep G2 DMSO controls (cpg0036 FMP subset)',
     'runtime': 'local CPU (≈1 s per field)', 'evidence': 'measured image; computed features', 'validation': 'integrated_unbenchmarked', 'ui': 'View › Cell Painting',
     'dependencies': ['cellpainting_hepg2'], 'benchmark': 'not yet compared with CellProfiler outputs for the same images'},
    {'id': 'vcell.microscopy.generative', 'provider': 'image', 'module': 'virtual_cell_cellflux.py + cellflux_runner.py (CellFlux cpg0000, local MPS)', 'inputs': ['observed field', 'JUMP perturbation'],
     'outputs': ['generated crops (prediction)', 'identity check'], 'context': 'trained on U2OS (JUMP); Hep G2 inputs out of domain, channel slots assumed',
     'runtime': 'local Apple MPS (≈ 18 s per cell) in runtimes/gbcell', 'evidence': 'prediction', 'validation': 'partial', 'ui': 'View › Cell Painting › CellFlux',
     'dependencies': ['cellflux plugin (code, deps, checkpoint)'], 'benchmark': 'BBBC021 (MCF7) in-domain, seen compounds, held-out cells: effect cosine 0.82 vs baseline 0.58; closer to treated than untreated for 4/5 compounds (vincristine overshoots). cpg0000 not benchmarkable (crops not public); Hep G2 DMSO identity: nuclei partly kept but distorted'},
    {'id': 'vcell.structures', 'provider': 'structure', 'module': 'virtual_cell_structures.py (read-only over library structure records; Molecular Intelligence parser, map_sequence, confidence, fit)',
     'inputs': ['UniProt accession'], 'outputs': ['saved structures with chain mapping, origin, declared confidence', 'Cα RMSD / TM-score on shared UniProt positions', 'PDB cross-references'],
     'context': 'any (structures are not cell-line specific)', 'runtime': 'local', 'evidence': 'annotation / prediction / measured (per record)', 'validation': 'operational_tested', 'ui': 'Protein panel › Structures › Open in Molecular Viewer', 'dependencies': []},
    {'id': 'vcell.em.volume', 'provider': 'image', 'module': 'cell_em.py (OpenOrganelle jrc_hela-2 FIB-SEM level s4 + COSEM segmentations; Brownian dynamics on the class grid)',
     'inputs': ['hydrodynamic radius', 'release compartment or point', 'optional binding target'], 'outputs': ['measured EM volume in 3D', 'compartment classes', 'streamed particle trajectories', 'encounters per compartment', 'MSD'],
     'context': 'HeLa (CVCL_0030), one fixed cell; not the Hep G2 context', 'runtime': 'local CPU (≈ 0.6 s per 48 frames)', 'evidence': 'measured image; ML segmentation; physics simulation',
     'validation': 'operational_tested', 'ui': 'Cell Explorer › Real cell · EM', 'dependencies': ['jrc_hela-2 install (≈ 39 MB, user-initiated)'],
     'benchmark': 'kernel free-diffusion control against 6Dt and confinement check on every run; segmentation accuracy is COSEM\'s, not re-evaluated here'},
    {'id': 'vcell.helaerk', 'provider': 'simulation', 'module': 'hela_erk.py (Tany et al. 2022 single-cell ERK-KTR trajectories from SSBD; receptor binding, ERK cascade, reporter transport; SciPy LSODA cross-check)',
     'inputs': ['EGF dose', 'time of addition', 'MEK or EGFR inhibition', 'resting C/N'], 'outputs': ['receptor occupancy, ERK activity, nuclear and cytoplasmic reporter, C/N', 'single-cell uncertainty band', 'held-out dish benchmark', 'reporter split in the 3D reference cell'],
     'context': 'HeLa cells of the live-cell experiment; the EM HeLa cell is a geometry reference only', 'runtime': 'local CPU (≈ 1 s per run; ≈ 20 s once to fit)', 'evidence': 'mechanistic model fitted to measurements', 'validation': 'operational_tested',
     'ui': 'Cell Explorer › Experiment › EGF → ERK', 'dependencies': ['bundled dataset (fixtures/hela_erk, CC BY)', 'jrc_hela-2 install for the 3D view'],
     'benchmark': 'another dish held out: single-cell error of C/N against no response and against the mean calibration response; four non-responding dishes reported as failures; dose and inhibitor hold-outs blocked (no public single-cell series)'},
    {'id': 'vcell.lightpulse', 'provider': 'simulation', 'module': 'light_pulse.py (Olson et al. 2017 CcaSR time courses and action spectra; mechanistic chain with per-LED photoconversion, learned and combined predictors; Mechanistic Lab solver cross-check)',
     'inputs': ['green light program', 'red or other LED programs', 'duration', 'predictor'], 'outputs': ['regulator activity, transcription drive, reporter time courses', 'uncertainty band', 'response features', 'held-out benchmark'],
     'context': 'E. coli BW29655 with the CcaSR reporter only', 'runtime': 'local CPU (≈ 1 s per run; ≈ 15 s once to fit)', 'evidence': 'mechanistic model fitted to measurements', 'validation': 'operational_tested',
     'ui': 'Cell Explorer › Experiment › Light pulse', 'dependencies': ['bundled dataset (fixtures/light_pulse, CC BY 4.0)'],
     'benchmark': 'whole schedules held out from fitting: log10 RMSE and response features against a static dose-response baseline, the green-only chain and the published model; mixed-colour schedules are a retrospective final test'},
    {'id': 'vcell.results', 'provider': 'simulation', 'module': 'virtual_cell_results.py (read-only over cell_physics/runs, cell_em/runs and rna_lab/runs research records)',
     'inputs': ['saved record id'], 'outputs': ['time series with units', 'profiles', 'scalars', 'solver, benchmark checks, assumptions, limitations', 'integrity re-check'],
     'context': 'the idealised system in each record (not mapped onto the selected cell)', 'runtime': 'local', 'evidence': 'simulation', 'validation': 'operational_tested',
     'ui': 'Simulations › Saved lab results', 'dependencies': ['Living Cell Physics', 'RNA-to-Protein Lab']},
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
    import virtual_cell_proteomics as VP
    prot = VP.available(root, rrid) if (pathlib.Path(root) / 'virtualcell' / 'data' / 'paxdb_hepg2' / 'proteomics.sqlite').is_file() else []
    if prot:
        put('protein abundance', 'available', ' · '.join(f"{m['id']} ({m['counts']['resolved']:,} proteins)" for m in prot), 'PaxDb ppm; one value per protein, no replicates published.')
    else:
        put('protein abundance', 'unsupported', None, 'No verified proteomics dataset integrated for this line.')
    if rrid == 'CVCL_0027' and (pathlib.Path(root) / 'virtualcell' / 'data' / 'cellpainting_hepg2' / 'original' / 'subset.json').is_file():
        put('microscopy / morphology', 'available', 'cpg0036 EU-OS Bioactives, FMP, plate B1001_R1, DMSO wells (24 images)', 'Observed images; morphology computed in pixels.')
    else:
        put('microscopy / morphology', 'unsupported', None, 'No line-matched imaging dataset integrated (see deferred work).')
    put('cell-cycle dynamics', 'unvalidated' if has('gerard2009') else 'not_downloaded', 'Gérard & Goldbeter 2009 (generic mammalian model)', 'Not calibrated to this line.')
    put('drug response', 'available' if kind in ('tahoe', 'k562') and has('tahoe100m') else 'unsupported', 'Tahoe-100M' + (' (transferred to K-562)' if kind == 'k562' else ''),
        'Parental Hep G2 is not in Tahoe-100M; HepG2/C3A is a separate context.' if rrid == 'CVCL_0027' else None)
    for name in (jobs or []):
        if name in out:
            out[name]['state'] = 'pending'
    return out


# ------------------------------------------------------------------ cell contexts

EXPERIMENTS = {
    'expression_perturbation': 'Gene and drug perturbation readouts (Virtual Cell)',
    'spatial_diffusion': 'Molecules diffusing, binding, exchanging and turning over in 3D (Cell Explorer)',
    'light_pulse': 'Light-pulse reporter response with held-out validation',
    'egf_erk': 'EGF → ERK reporter response in single cells with a held-out dish',
}
QUALIFY = 'An experiment qualifies in a context when that context has its own measurements to calibrate it, a model that uses them, and a validation result. Anything missing is listed, and the experiment stays unavailable there.'


def cell_contexts(root):
    """Every cell context with what it is, what was measured in it, which models and experiments it supports and how each
    was validated. Contexts never borrow each other's measurements: a readout exists only where it was measured."""
    import cell_em, light_pulse
    root = pathlib.Path(root) if root else None
    ds = {r['id']: r['status'] for r in datasets(root)} if root else {}
    em = cell_em.meta(root) if root else None
    fit_file = light_pulse._fit_file(root) if root else None
    bench = None
    if fit_file is not None and fit_file.is_file():
        try:
            bench = json.loads(fit_file.read_text())['benchmark']
        except (ValueError, KeyError):
            bench = None
    lp = light_pulse.dataset()
    rod = cell_em.geometry(None, cell_em.ECOLI)[2]
    state = lambda ok: 'available' if ok else 'not_downloaded'
    held = bench and bench['summary']['heldOut']
    contexts = [
        {'id': cell_em.HELA, 'name': 'HeLa · whole-cell electron microscopy', 'role': 'EM specimen', 'species': 'Homo sapiens', 'cellType': 'HeLa, cervical adenocarcinoma line (CVCL_0030)',
         'state': 'Interphase; one high-pressure-frozen, freeze-substituted, resin-embedded cell (a static snapshot)',
         'geometry': {'kind': 'measured_em', 'label': 'Measured EM volume', 'detail': 'OpenOrganelle jrc_hela-2 FIB-SEM, 48 × 6.4 × 33.4 µm; 64 × 64 × 83.84 nm voxels installed, 4 × 4 × 5.24 nm acquired and loadable by region',
                      'segmentation': 'COSEM machine-learning segmentations of 13 compartments', 'installed': em is not None},
         'measurements': [{'name': 'EM volume', 'state': state(em is not None), 'evidence': 'measured', 'source': 'Xu et al. 2021, doi:10.1038/s41586-021-03992-4'},
                          {'name': 'Compartment segmentation', 'state': state(em is not None), 'evidence': 'machine-learning segmentation', 'source': 'Heinrich et al. 2021, doi:10.1038/s41586-021-04061-2'},
                          {'name': 'Molecular readouts (expression, abundance, reporters)', 'state': 'unmeasured', 'evidence': None, 'source': None},
                          {'name': 'ERK-KTR single-cell trajectories after EGF (other HeLa specimens, live imaging)', 'state': 'available', 'evidence': 'measured in other cells', 'source': 'Tany et al. 2022, doi:10.1042/BCJ20220021; SSBD ssbd-repos-000232'}],
         'models': [{'id': 'fold.hela-erk.egf-ktr', 'name': 'EGF binding, ERK cascade and reporter transport', 'calibration': 'Fitted to single cells of one dish; tested on another dish; receptor and feedback constants assumed'},
                    {'id': 'fold.cell-em.brownian', 'name': 'Brownian dynamics with binding, exchange, synthesis and decay', 'calibration': 'Geometry measured; diffusion slowdown and every rate are assumptions'},
                    {'id': 'fold.cell-em.painting', 'name': 'Synthetic Cell Painting forward model', 'calibration': 'Stain weights assumed'}],
         'experiments': {'spatial_diffusion': {'supported': em is not None, 'missing': [] if em is not None else ['Install the EM volume (about 40 MB)']},
                         'light_pulse': {'supported': False, 'missing': ['No measurement of a light-responsive reporter exists for this cell', 'No calibrated parameters']},
                         'egf_erk': {'supported': True, 'missing': [], 'note': 'Calibrated on live HeLa cells of another experiment (Tany et al. 2022). This EM cell supplies the nucleus and cytosol geometry only; no signalling was measured in it.'},
                         'expression_perturbation': {'supported': False, 'missing': ['No expression baseline is integrated for this specimen']}},
         'validation': [{'what': 'Diffusion kernel', 'result': 'Free-diffusion control against 6Dt on every run', 'kind': 'numerical'},
                        {'what': 'Permeable boundaries, synthesis, decay, conversion', 'result': 'Closed-form benchmarks in the test suite', 'kind': 'numerical'},
                        {'what': 'Intracellular diffusion or binding against experiment', 'result': 'Not validated: no measurement in this cell', 'kind': 'experimental'}]},
        {'id': 'CVCL_0027', 'name': 'Hep G2 · molecular baseline', 'role': 'Molecular baseline', 'species': 'Homo sapiens', 'cellType': 'Hep G2, hepatocellular carcinoma line (CVCL_0027, ACH-000739)',
         'state': 'Unperturbed culture (DepMap, ENCODE, PaxDb and Cell Painting control wells)',
         'geometry': {'kind': 'none', 'label': 'No 3D geometry', 'detail': 'No volume image of this line is integrated. The Cell · 3D tab draws an illustrative cell for orientation only.', 'installed': False},
         'measurements': [{'name': 'Gene expression (bulk RNA-seq)', 'state': state(ds.get('depmap24q4') == 'available'), 'evidence': 'measured', 'source': 'DepMap 24Q4'},
                          {'name': 'Transcript isoforms', 'state': state(ds.get('encode_hepg2_rna') == 'available'), 'evidence': 'measured', 'source': 'ENCODE ENCSR000CPE'},
                          {'name': 'Protein abundance', 'state': state(ds.get('paxdb_hepg2') == 'available'), 'evidence': 'measured', 'source': 'PaxDb, Geiger et al. 2012'},
                          {'name': 'Knockout fitness', 'state': state(ds.get('depmap24q4') == 'available'), 'evidence': 'measured', 'source': 'DepMap 24Q4 Chronos'},
                          {'name': 'Cell Painting images', 'state': state(ds.get('cellpainting_hepg2') == 'available'), 'evidence': 'measured', 'source': 'Cell Painting Gallery cpg0036'}],
         'models': [{'id': 'vcell.cellcycle', 'name': 'Cell-cycle model (Gérard & Goldbeter 2009)', 'calibration': 'Generic mammalian; not calibrated to this line'}],
         'experiments': {'expression_perturbation': {'supported': ds.get('depmap24q4') == 'available', 'missing': [] if ds.get('depmap24q4') == 'available' else ['DepMap 24Q4 is not in this library']},
                         'spatial_diffusion': {'supported': False, 'missing': ['No 3D geometry for this line']},
                         'light_pulse': {'supported': False, 'missing': ['No measurement of a light-responsive reporter exists for this cell', 'No calibrated parameters']}},
         'validation': [{'what': 'Measured baselines', 'result': 'Dataset integrity checks; replicate agreement where replicates exist', 'kind': 'data'},
                        {'what': 'Cell-cycle timing', 'result': 'Not validated for this line', 'kind': 'experimental'}]},
        {'id': light_pulse.CONTEXT, 'name': 'E. coli · light-responsive reporter', 'role': 'Reporter experiment', 'species': 'Escherichia coli', 'cellType': lp['system']['strain'],
         'state': 'Exponential growth in M9 glucose with casamino acids at 37 °C, low density',
         'geometry': {'kind': 'illustrative', 'label': 'Illustrative geometry', 'detail': f"A drawn rod, {rod['sizeUm'][0]:.1f} µm box at 20 nm voxels, from typical E. coli dimensions. It is not an image of this strain. The reporter model itself is a compartment model and needs no geometry.", 'installed': True},
         'measurements': [{'name': 'Reporter time courses under light programs', 'state': 'available', 'evidence': 'measured', 'source': f"{lp['source']['authors']}, {lp['source']['journal']}, doi:{lp['source']['doi']} ({len(lp['schedules'])} schedules)"},
                          {'name': 'Growth rate', 'state': 'available', 'evidence': 'measured', 'source': '37.4 min per doubling, same paper'},
                          {'name': 'Protein diffusion in cytoplasm', 'state': 'available', 'evidence': 'measured (literature, not this strain)', 'source': 'Elowitz et al. 1999, J Bacteriol 181:197-203'},
                          {'name': 'Cell-to-cell spread of the reporter', 'state': 'available', 'evidence': 'measured', 'source': 'Robust CV per sample, same dataset; not predicted by the model'},
                          {'name': 'Spatial distribution of any component', 'state': 'unmeasured', 'evidence': None, 'source': None}],
         'models': [{'id': 'fold.light-pulse.ccasr', 'name': 'Light → regulator → transcription → reporter chain', 'calibration': 'Nine parameters fitted to 12 training schedules; mRNA turnover assumed'},
                    {'id': 'fold.cell-em.brownian', 'name': 'Brownian dynamics in the illustrative rod', 'calibration': 'Diffusion slowdown set to the measured GFP diffusion coefficient; other rates assumed'}],
         'experiments': {'light_pulse': {'supported': True, 'missing': []},
                         'spatial_diffusion': {'supported': True, 'missing': [], 'note': 'Runs in illustrative geometry; results are labelled so.'},
                         'expression_perturbation': {'supported': False, 'missing': ['No genome-wide expression baseline is integrated for this strain']}},
         'validation': [{'what': 'Reporter response on held-out light schedules', 'kind': 'experimental',
                         'result': (f"{bench['selected']} model: {10 ** held[bench['selected']]:.2f}-fold root-mean-square error on {len(light_pulse.SPLIT['heldOut'])} held-out schedules; static baseline {10 ** held['baseline']:.2f}-fold" if bench else 'Computed the first time the experiment is opened')},
                        {'what': 'Schedules with red light', 'kind': 'experimental', 'result': 'Fails by design: red light is not an input of the model (shown as the failure case)'},
                        {'what': 'Integrator', 'kind': 'numerical', 'result': 'Agreement with SciPy LSODA through the Mechanistic Lab solver on every saved run'}]},
        {'id': 'K562', 'name': 'K-562 · perturbation baseline', 'role': 'Perturbation baseline', 'species': 'Homo sapiens', 'cellType': 'K-562, chronic myeloid leukaemia line (CVCL_0004)', 'state': 'Unperturbed controls of the Perturb-seq screens',
         'geometry': {'kind': 'none', 'label': 'No 3D geometry', 'detail': 'No volume image of this line is integrated.', 'installed': False},
         'measurements': [{'name': 'Single-cell expression under genetic perturbation', 'state': state(ds.get('norman2019') == 'available'), 'evidence': 'measured', 'source': 'Norman 2019; Replogle 2022'}],
         'models': [{'id': 'vcell.transitions', 'name': 'Perturbation response model', 'calibration': 'Fitted to Perturb-seq; held-out Pearson r per transition'}],
         'experiments': {'expression_perturbation': {'supported': ds.get('norman2019') == 'available', 'missing': [] if ds.get('norman2019') == 'available' else ['Norman 2019 is not in this library']},
                         'spatial_diffusion': {'supported': False, 'missing': ['No 3D geometry for this line']}, 'light_pulse': {'supported': False, 'missing': ['No measurement of a light-responsive reporter exists for this cell']}},
         'validation': [{'what': 'Expression change under held-out perturbations', 'kind': 'experimental', 'result': 'See Virtual Cell › Simulations (docs/VIRTUAL_CELL.md)'}]},
    ]
    for c in contexts:
        c['qualified'] = [k for k, v in c['experiments'].items() if v['supported']]
    return {'contexts': contexts, 'experiments': EXPERIMENTS, 'rule': QUALIFY,
            'identity': 'The EM specimen is HeLa and the molecular baseline is Hep G2. They are different cell lines; no readout is transferred between any two contexts.'}


def capabilities():
    return [{**c, 'validationLabel': VALIDATION[c['validation']]} for c in CAPABILITIES]
