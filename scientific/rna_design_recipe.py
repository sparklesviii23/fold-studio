"""Bounded CPU recipe for the existing Modal sandbox system."""
RECIPE = {
    'title': 'RNA Design · Modal CPU', 'demo': None,
    'purpose': 'Find distinct RNA sequences for a nested target fold.',
    'evidence': 'Computational prediction. ViennaRNA primary score and RNA Lab independent check.',
    'source': 'ViennaRNA 2.7.2 and fold RNA Design 1.0.0',
    'reference': {'citation': 'Lorenz et al. ViennaRNA Package 2.0. Algorithms for Molecular Biology 2011;6:26.', 'doi': '10.1186/1748-7188-6-26'},
    'license': 'ViennaRNA Package licence; fold source licence.',
    'gpu': None, 'cpu': 1, 'memory': 2048, 'timeout': 180,
    'image': {'registry': 'python:3.12-slim', 'apt': [], 'run': [], 'pip': ['ViennaRNA==2.7.2']},
    'inputs': {'design': {'type': 'rna_design_request'}},
    'script': '''set -euo pipefail
export OUT=/cache/out/$FOLD_TASK_ID
mkdir -p "$OUT" /work
cd /work
python - <<'PY'
import json, os
from pathlib import Path
body = json.loads(json.loads(Path(os.environ['FOLD_INPUT_FILE']).read_text())['design'])
for name, content in body['files'].items():
    Path(name).write_text(content)
PY
python -u rna_design_cloud.py
''',
}
