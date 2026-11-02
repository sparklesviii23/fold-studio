"""Model-specific, source-pinned cloud recipes. No downloads happen on import."""
from pathlib import Path
import antisense_workflow
EVO = '53f195997257c56c00e5ef8d33a54f5baad143a6'
BORZOI = 'f10f8c799639dd2cfc0c1eb09499bfc47ab9cf8a'
BASKERVILLE = 'b06950be1be704ab09ab23ffb6f5102d9e2a63a0'
ESM = '8f0834cbc350aeaf507f755475873f7c61fa44a1'
DNA = {'type': 'dna', 'max': 4000}
PROTEIN = {'type': 'protein', 'max': 1000}


def recipes():
    runner = Path(__file__).with_name('biological_model_runner.py').read_text()
    models = {
        'bio_evo2': {'title': 'Evo 2 · DNA scores & embeddings', 'purpose': 'Score reference and optional alternate DNA, and export reference embeddings. No sequence generation.',
            'source': 'https://github.com/ArcInstitute/evo2/tree/' + EVO, 'license': 'Apache-2.0 (Evo 2 code and published weights); upstream use conditions apply.',
            'gpu': 'A100-80GB', 'image': {'registry': 'pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel', 'apt': ['git', 'build-essential'],
                'run': ['pip install flash-attn==2.8.0.post2 --no-build-isolation', 'pip install git+https://github.com/ArcInstitute/evo2.git@' + EVO], 'pip': []},
            'inputs': {'sequence': DNA, 'alternate': {'type': 'dna_optional', 'max': 4000}}, 'limits': '7B base checkpoint; 4,000 bases per sequence. Likelihood differences are not calibrated variant effects.'},
        'bio_borzoi': {'title': 'Borzoi · human regulatory tracks', 'purpose': 'Predict one annotated track over a 524,288-base hg38 reference window retrieved from UCSC.',
            'source': 'https://github.com/calico/borzoi/tree/' + BORZOI, 'license': 'Apache-2.0 (Borzoi repository); retain the upstream code, data and checkpoint notices.',
            'gpu': 'A100-80GB', 'image': {'registry': 'tensorflow/tensorflow:2.15.0-gpu', 'apt': ['git'], 'run': [
                'git clone https://github.com/calico/borzoi.git /opt/borzoi && cd /opt/borzoi && git checkout ' + BORZOI,
                'pip install git+https://github.com/calico/baskerville-tf.git@' + BASKERVILLE,
                'pip install --no-deps /opt/borzoi'], 'pip': []},
            'inputs': {'chromosome': {'type': 'choice', 'options': ['chr'+str(i) for i in range(1,23)]+['chrX','chrY'], 'default': 'chr1'},
                'start': {'type': 'int', 'min': 0, 'max': 248432134, 'default': 1000000}, 'track': {'type': 'int', 'min': 0, 'max': 7610, 'default': 0}},
            'limits': 'Human reference only. Raw transformed values; single replicate, forward strand. Not a phage model.'},
        'bio_esmc': {'title': 'Biohub ESMC · protein embeddings', 'purpose': 'Export residue-level ESMC-300M representations for a supplied protein.',
            'source': 'https://github.com/Biohub/esm/tree/' + ESM, 'license': 'MIT (current Biohub ESM release); upstream model use conditions apply.',
            'gpu': 'A10G', 'image': {'registry': 'pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime', 'apt': ['git'], 'run': ['pip install git+https://github.com/Biohub/esm.git@' + ESM], 'pip': []},
            'inputs': {'sequence': PROTEIN}, 'limits': 'Canonical amino acids; up to 1,000 residues. Embedding similarity is not biological activity.'},
        'bio_esmfold2': {'title': 'Biohub ESMFold2 · protein structure', 'purpose': 'Predict one protein structure and retain mmCIF coordinates and confidence.',
            'source': 'https://github.com/Biohub/esm/tree/' + ESM, 'license': 'MIT (current Biohub ESM release); upstream model use conditions apply.',
            'gpu': 'A100-80GB', 'image': {'registry': 'pytorch/pytorch:2.11.0-cuda12.8-cudnn9-runtime', 'apt': ['git'], 'run': ['pip install git+https://github.com/Biohub/esm.git@' + ESM], 'pip': []},
            'inputs': {'sequence': {'type': 'protein', 'max': 600}, 'loops': {'type': 'int', 'min': 1, 'max': 20, 'default': 4},
                'steps': {'type': 'int', 'min': 20, 'max': 100, 'default': 100}, 'seed': {'type': 'int', 'min': 0, 'max': 2147483647, 'default': 0}},
            'limits': 'Single protein, no supplied MSA. Reduced loops by default; not maximum-accuracy qualification.'},
    }
    for key, r in models.items():
        r.update(demo='Biological Models', evidence='Model prediction · GPU qualification pending', timeout=3600, qualification='integration_unvalidated')
        r['script'] = 'set -euo pipefail\nexport HF_HOME=/cache/models/huggingface\nexport FOLD_BIO_RECIPE=' + key + '\nOUT=/cache/out/$FOLD_TASK_ID; mkdir -p "$OUT"\npython - <<\'FOLD_BIO_PY\'\n' + runner + '\nFOLD_BIO_PY\n'
    models['bio_antisense'] = antisense_workflow.recipe()
    return models
