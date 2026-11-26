"""Virtual Cell resource registry: every outside dataset and model the virtual cell uses or plans to use, with its licence.

Rules (docs/VIRTUAL_CELL.md):
  * No third-party weights, datasets or outputs derived from them are ever committed to the repository
    (scripts/check-release-licenses.py enforces this). Each resource is fetched from its original source into the
    user's library, after the user has seen its licence.
  * The core virtual cell works without any resource marked plugin=True; a missing plugin makes its readout
    "not available", never an error.
  * fold is research-only (decision of 1 Nov 2026), so non-commercial resources are allowed. Their terms are
    still recorded on every result that used them, and NOTICE text is generated from this table.

licenceVerified is True only where the licence text or dataset card was read; otherwise the licence must be checked
before installation and the UI says so.
"""
import pathlib

RESOURCES = {
    'norman2019': {
        'name': 'Norman 2019 CRISPRa Perturb-seq (K-562)', 'kind': 'dataset', 'plugin': False,
        'provides': ['gene_overexpression transition', 'pair additivity benchmark'],
        'licence': 'CC BY 4.0', 'licenceVerified': True, 'nonCommercial': False, 'redistribution': 'allowed with attribution',
        'source': 'https://zenodo.org/records/7041849',
        'citation': 'Norman TM et al. Science 2019;365:786–793; scPerturb: Peidli S et al. Nat Methods 2024.',
        'localPath': 'oncology/perturbseq/norman2019/NormanWeissman2019_filtered.h5ad', 'install': 'Oncology Universe › Perturbation model (already downloaded)'},
    'depmap24q4': {
        'name': 'DepMap 24Q4 CRISPR gene effect and expression', 'kind': 'dataset', 'plugin': False,
        'provides': ['knockout fitness readout', 'bulk expression baseline'],
        'licence': 'CC BY 4.0', 'licenceVerified': True, 'nonCommercial': False, 'redistribution': 'allowed with attribution',
        'source': 'https://doi.org/10.25452/figshare.plus.27993248.v1',
        'citation': 'DepMap, Broad (2024). DepMap 24Q4 Public. Figshare+.',
        'localPath': 'oncology/depmap/24Q4/gene_effect.npy', 'install': 'Oncology Universe › Data (already downloaded)'},
    'humangem': {
        'name': 'Human-GEM v2.1.1 genome-scale metabolic model', 'kind': 'model', 'plugin': False,
        'provides': ['metabolism readout (flux balance)'],
        'licence': 'CC BY 4.0', 'licenceVerified': True, 'nonCommercial': False, 'redistribution': 'allowed with attribution',
        'source': 'https://github.com/SysBioChalmers/Human-GEM',
        'citation': 'Robinson JL et al. Sci Signal 2020;13:eaaz1482.',
        'localPath': 'oncology/metabolism/Human-GEM-v2.1.1/Human-GEM.json', 'install': 'Oncology Universe › Metabolism (already downloaded)'},
    'replogle2022': {
        'name': 'Replogle 2022 CRISPRi Perturb-seq, K-562 essential genes', 'kind': 'dataset', 'plugin': False,
        'provides': ['gene_knockdown transition (2,021 measured knockdowns)', 'on-target knockdown efficiency'],
        'licence': 'CC BY 4.0 (scPerturb record)', 'licenceVerified': True, 'nonCommercial': False, 'redistribution': 'allowed with attribution',
        'source': 'https://zenodo.org/records/7041849 (ReplogleWeissman2022_K562_essential.h5ad, MD5 d8cba175…)',
        'citation': 'Replogle JM et al. Cell 2022;185:2559–2575; scPerturb: Peidli S et al. Nat Methods 2024.',
        'localPath': 'virtualcell/data/replogle2022/ReplogleWeissman2022_K562_essential.h5ad', 'install': 'Downloaded (1.55 GB)'},
    'tahoe100m': {
        'name': 'Tahoe-100M drug perturbation atlas (50 lines, ~1,100 drug-dose conditions)', 'kind': 'dataset', 'plugin': False,
        'provides': ['small_molecule transition with dose: measured in 50 lines, interpolated, transferred to K-562'],
        'licence': 'CC0 1.0', 'licenceVerified': True, 'nonCommercial': False, 'redistribution': 'allowed',
        'source': 'https://huggingface.co/datasets/tahoebio/Tahoe-100M',
        'citation': 'Tahoe-100M: Mapping drug-induced molecular phenotypes at single-cell resolution. Cell 2026.',
        'localPath': 'virtualcell/data/tahoe100m/conditions.json', 'install': 'Streamed and filtered to the gene panel (89 GB source)'},
    'xatlas_orion': {
        'name': 'X-Atlas/Orion genome-wide Perturb-seq (HCT116, HEK293T)', 'kind': 'dataset', 'plugin': True,
        'provides': ['knockdown transitions in two more cell lines (planned)'],
        'licence': 'non-commercial (reported; check before download)', 'licenceVerified': False, 'nonCommercial': True, 'redistribution': 'unverified',
        'source': 'https://www.biorxiv.org/content/10.1101/2025.06.11.659105v1',
        'citation': 'X-Atlas/Orion: Genome-wide Perturb-seq Datasets via a Scalable Fix-Cryopreserve Platform. bioRxiv 2025. doi:10.1101/2025.06.11.659105',
        'localPath': 'virtualcell/plugins/xatlas_orion', 'install': 'Needs your approval: download from the authors\' Figshare'},
    'gbcell': {
        'name': 'GB.Cell (formerly AIDO.Cell) 3M / 10M / 100M', 'kind': 'model', 'plugin': True,
        'provides': ['in-silico knockout target ranking (embedding shift toward a target state)'],
        'licence': 'GenBio AI Community License', 'licenceVerified': True, 'nonCommercial': True,
        'redistribution': 'non-commercial only, with licence copy and NOTICE; outputs (embeddings, molecules) inherit the terms; no distillation',
        'attribution': 'Powered by GenBio AI. This is licensed under the GenBio AI Community License Agreement, Copyright © GENBIO.AI, INC. All Rights Reserved.',
        'source': 'https://huggingface.co/collections/genbio-ai/aidocell-6750f409bb20d8cd2cf14a25',
        'citation': 'Scaling Dense Representations for Single Cell with Transcriptome-Scale Context. bioRxiv 2024. doi:10.1101/2024.11.28.625303',
        'localPath': 'virtualcell/plugins/gbcell/benchmark.json', 'install': 'Runs locally on CPU (runtimes/gbcell) or on Modal GPU'},
    'borzoi': {
        'name': 'Borzoi / Flashzoi sequence-to-coverage models', 'kind': 'model', 'plugin': True,
        'provides': ['chromatin and RNA coverage readouts from DNA (planned, Phase 3)'],
        'licence': 'Apache-2.0 (Borzoi); MIT code and weights (Flashzoi)', 'licenceVerified': True, 'nonCommercial': False, 'redistribution': 'allowed',
        'source': 'https://github.com/calico/borzoi', 'citation': 'Linder J et al. Nat Genet 2025; Hingerl JC et al. Bioinformatics 2025.',
        'localPath': 'virtualcell/plugins/borzoi', 'install': 'Needs your approval: weights download; NVIDIA GPU (Modal)'},
    'alphagenome': {
        'name': 'AlphaGenome', 'kind': 'model', 'plugin': True,
        'provides': ['variant-effect and regulatory track readouts (optional cross-check)'],
        'licence': 'AlphaGenome Model Terms of Use (non-commercial; code Apache-2.0)', 'licenceVerified': True, 'nonCommercial': True,
        'redistribution': 'weights not redistributable; outputs must not be shared with commercial organisations',
        'source': 'https://storage.googleapis.com/alphagenome/terms/AlphaGenome-Model-Terms-of-Use.pdf', 'citation': 'Google DeepMind. AlphaGenome.',
        'localPath': 'virtualcell/plugins/alphagenome', 'install': 'You request access from Google DeepMind; never bundled'},
    'virtues': {
        'name': 'VirTues spatial proteomics foundation model', 'kind': 'model', 'plugin': True,
        'provides': ['tissue-niche context (planned, Phase 4)'],
        'licence': 'code MIT; weights CC BY-NC 4.0', 'licenceVerified': True, 'nonCommercial': True, 'redistribution': 'weights non-commercial with attribution',
        'source': 'https://github.com/bunnelab/virtues', 'citation': 'Wenckstern J et al. Nature 2026. doi:10.1038/s41586-026-10884-y',
        'localPath': 'virtualcell/plugins/virtues', 'install': 'Needs your approval: weights download'},
    'proteintalks': {
        'name': 'ProteinTalks perturbation proteomics (PTDS) and model', 'kind': 'dataset', 'plugin': True,
        'provides': ['time-resolved protein abundance transitions (planned)'],
        'licence': 'not yet checked', 'licenceVerified': False, 'nonCommercial': None, 'redistribution': 'unverified',
        'source': 'https://doi.org/10.1038/s41586-026-11001-9', 'citation': 'Sun R et al. Nature 2026. doi:10.1038/s41586-026-11001-9',
        'localPath': 'virtualcell/plugins/proteintalks', 'install': 'Check the paper\'s data and code availability first'},
    'geneformer': {
        'name': 'Geneformer (in-silico perturbation)', 'kind': 'model', 'plugin': True,
        'provides': ['second, independent in-silico knockout ranking'],
        'licence': 'not yet checked', 'licenceVerified': False, 'nonCommercial': None, 'redistribution': 'unverified',
        'source': 'https://huggingface.co/ctheodoris/Geneformer', 'citation': 'Theodoris CV et al. Nature 2023;618:616–624.',
        'localPath': 'virtualcell/plugins/geneformer', 'install': 'Needs your approval: weights download and GPU time'},
    'sparced': {
        'name': 'SPARCED proliferation and death signalling model', 'kind': 'model', 'plugin': False,
        'provides': ['signalling readout (ERK, AKT, cyclin D, E2F, p53, cleaved PARP over 24 h)'],
        'licence': 'GPL-2.0 (repository marcbirtwistle/SPARCED)', 'licenceVerified': True, 'nonCommercial': False,
        'redistribution': 'GPL-2.0: fetched into the library, never committed to fold',
        'source': 'https://github.com/marcbirtwistle/SPARCED (Demo/SPARCED.xml, commit a957f960)', 'citation': 'SPARCED. Nat Commun 2022. doi:10.1038/s41467-022-31138-1; Bouhaddou M et al. PLoS Comput Biol 2018.',
        'localPath': 'virtualcell/models/sparced/SPARCED.xml', 'install': 'Downloaded (2 MB SBML)'},
    'hpa_subcellular': {
        'name': 'Human Protein Atlas subcellular resource', 'kind': 'dataset', 'plugin': False,
        'provides': ['protein localization (immunofluorescence calls with reliability)', 'cell view compartment gene sets', 'cell-cycle dependency annotations'],
        'licence': 'CC BY 4.0', 'licenceVerified': True, 'nonCommercial': False, 'redistribution': 'allowed with attribution',
        'source': 'https://www.proteinatlas.org/download/tsv/subcellular_location.tsv.zip', 'citation': 'Thul PJ et al. Science 2017;356:eaal3321. Human Protein Atlas, proteinatlas.org.',
        'localPath': 'virtualcell/data/annotations/original/subcellular_location.tsv.zip', 'install': 'Virtual Cell › Install annotations (0.3 MB)'},
    'uniprot_human': {
        'name': 'UniProtKB/Swiss-Prot reviewed human proteome', 'kind': 'dataset', 'plugin': False,
        'provides': ['identifier mapping (UniProt, HGNC, Ensembl, aliases)', 'curated subcellular location with ECO evidence', 'PDB cross-references'],
        'licence': 'CC BY 4.0', 'licenceVerified': True, 'nonCommercial': False, 'redistribution': 'allowed with attribution',
        'source': 'https://rest.uniprot.org/uniprotkb/stream (organism 9606, reviewed)', 'citation': 'The UniProt Consortium. Nucleic Acids Res. 2025;53:D609.',
        'localPath': 'virtualcell/data/annotations/original/uniprot_human_reviewed.tsv.gz', 'install': 'Virtual Cell › Install annotations (2.6 MB)'},
    'reactome': {
        'name': 'Reactome pathway knowledgebase (human)', 'kind': 'dataset', 'plugin': False,
        'provides': ['pathway membership and hierarchy', 'pathway enrichment of modelled changes'],
        'licence': 'CC0 (data)', 'licenceVerified': True, 'nonCommercial': False, 'redistribution': 'public domain dedication',
        'source': 'https://reactome.org/download-data', 'citation': 'Milacic M et al. Nucleic Acids Res. 2024;52:D672.',
        'localPath': 'virtualcell/data/annotations/original/UniProt2Reactome.txt', 'install': 'Virtual Cell › Install annotations (45 MB)'},
    'encode_hepg2_rna': {
        'name': 'ENCODE Hep G2 polyA+ RNA-seq transcript quantifications (ENCSR000CPE)', 'kind': 'dataset', 'plugin': False,
        'provides': ['transcript isoform abundance (2 biological replicates)', 'GENCODE V29 transcript structure'],
        'licence': 'ENCODE data release policy: no restrictions on use; cite the ENCODE Project Consortium', 'licenceVerified': False, 'nonCommercial': False,
        'redistribution': 'allowed with citation', 'source': 'https://www.encodeproject.org/experiments/ENCSR000CPE/ (ENCFF416RHJ, ENCFF938LTW); GENCODE 29 primary assembly GTF',
        'citation': 'ENCODE Project Consortium. Nature 2012;489:57–74; Luo Y et al. Nucleic Acids Res 2020;48:D882. Data: Gingeras lab, CSHL. Frankish A et al. Nucleic Acids Res 2019;47:D766 (GENCODE).',
        'localPath': 'virtualcell/data/encode_hepg2/transcripts.sqlite', 'install': 'Virtual Cell › Build transcript index (≈100 MB download, md5-checked)'},
    'paxdb_hepg2': {
        'name': 'PaxDb Hep G2 protein abundance (Geiger et al. 2012: iBAQ and spectral counting)', 'kind': 'dataset', 'plugin': False,
        'provides': ['measured protein abundance (ppm)', 'RNA–protein comparison'],
        'licence': 'CC BY 4.0 (PaxDb)', 'licenceVerified': True, 'nonCommercial': False, 'redistribution': 'allowed with attribution',
        'source': 'https://pax-db.org/downloads/latest/datasets/9606/ (9606-iBAQ_HepG2_Geiger_2012_uniprot.txt, 9606-HepG2_Geiger_2012.txt)',
        'citation': 'Geiger T et al. Mol Cell Proteomics 2012;11:M111.014050; Huang Q et al. Proteomics 2023 (PaxDb 5).',
        'localPath': 'virtualcell/data/paxdb_hepg2/proteomics.sqlite', 'install': 'Virtual Cell › Build proteomics index (0.4 MB download)'},
    'cellpainting_hepg2': {
        'name': 'Cell Painting Gallery cpg0036 (EU-OPENSCREEN Bioactives), Hep G2 DMSO subset', 'kind': 'dataset', 'plugin': False,
        'provides': ['observed Cell Painting images', 'segmentation and morphology'],
        'licence': 'CC0 1.0 (Cell Painting Gallery)', 'licenceVerified': True, 'nonCommercial': False, 'redistribution': 'public domain dedication; cite the publication',
        'source': 's3://cellpainting-gallery/cpg0036-EU-OS-bioactives/FMP/ (plate B1001_R1, wells A23/B24, sites 1/5/9)',
        'citation': 'Wolff C et al. iScience 2025;28:112445. Weisbart E et al. Nat Methods 2024 (Cell Painting Gallery).',
        'localPath': 'virtualcell/data/cellpainting_hepg2/original/subset.json', 'install': 'Downloaded subset (24 images, 40 MB)'},
    'gerard2009': {
        'name': 'Gérard & Goldbeter 2009 mammalian cell-cycle model (BIOMD0000000730)', 'kind': 'model', 'plugin': False,
        'provides': ['cell-cycle timeline (Cdk network ODEs)'],
        'licence': 'CC0 (BioModels curated)', 'licenceVerified': False, 'nonCommercial': False, 'redistribution': 'public domain dedication',
        'source': 'https://www.ebi.ac.uk/biomodels/BIOMD0000000730', 'citation': 'Gérard C, Goldbeter A. PNAS 2009;106:21643–21648.',
        'localPath': 'mechanistic/cache', 'install': 'Fetched by the Mechanistic Lab on first run (SBML, < 1 MB)'},
    'cellflux': {
        'name': 'CellFlux (flow-matching Cell Painting generator), JUMP cpg0000 checkpoint', 'kind': 'model', 'plugin': True,
        'provides': ['generated Cell Painting crops for a JUMP perturbation (experimental; out of domain for Hep G2)'],
        'licence': 'Code MIT (repository; some files carry CC-BY-NC headers); weights licence not stated', 'licenceVerified': False, 'nonCommercial': True,
        'redistribution': 'not redistributed: fetched into the library for research use',
        'source': 'https://github.com/yuhui-zh15/CellFlux (041c4c0); https://huggingface.co/suyc21/CellFlux',
        'citation': 'Zhang Y, Su Y, et al. CellFlux: Simulating Cellular Morphology Changes via Flow Matching. ICML 2025.',
        'localPath': 'virtualcell/plugins/cellflux/checkpoints/cpg0000.pth', 'install': 'Installed at the user\'s request (≈ 0.9 GB checkpoint; runs on Apple MPS)'},
    'morphodiff': {
        'name': 'MorphoDiff / MorphGen Cell Painting generators', 'kind': 'model', 'plugin': True,
        'provides': ['cell morphology images (planned, last)'],
        'licence': 'not yet checked', 'licenceVerified': False, 'nonCommercial': None, 'redistribution': 'unverified',
        'source': 'https://arxiv.org/abs/2510.01298', 'citation': 'Navidi Z et al. ICLR 2025; MorphGen, arXiv 2510.01298.',
        'localPath': 'virtualcell/plugins/morphodiff', 'install': 'Needs your approval: weights and GPU time'},
}

REQUIRED = ('name', 'kind', 'plugin', 'provides', 'licence', 'licenceVerified', 'nonCommercial', 'redistribution', 'source', 'citation', 'localPath', 'install')


def status(root):
    """Registry rows with an 'installed' flag resolved against the library root, plus any saved plugin benchmark."""
    import json
    root = pathlib.Path(root); rows = []
    for k, r in RESOURCES.items():
        row = dict(r, id=k, installed=(root / r['localPath']).exists())
        bm = root / 'virtualcell' / 'plugins' / k / 'benchmark.json'
        if bm.is_file():
            b = json.loads(bm.read_text())
            row['benchmark'] = {x: b[x] for x in ('mrr', 'chanceMrr', 'top1', 'targets', 'candidates', 'cellsPerCondition', 'device') if x in b}
        rows.append(row)
    return rows


def terms(ids):
    """The licence terms a result inherits from the resources it used (attached to every readout)."""
    return [{'id': i, 'name': RESOURCES[i]['name'], 'licence': RESOURCES[i]['licence'], 'nonCommercial': RESOURCES[i]['nonCommercial'],
             'citation': RESOURCES[i]['citation']} for i in ids]


def notice(root):
    """NOTICE text for the resources installed in this library."""
    lines = ['fold Virtual Cell: third-party resources used by this installation', '']
    for r in status(root):
        if r['installed']:
            lines += [f"{r['name']}", f"  Licence: {r['licence']}", f"  Source: {r['source']}", f"  Cite: {r['citation']}"]
            if r.get('attribution'):
                lines.append('  ' + r['attribution'])
            lines.append('')
    return '\n'.join(lines)
