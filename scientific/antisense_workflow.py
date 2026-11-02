"""Bundled evidence and portable remote recipe for the controller's PNA stage."""
import hashlib
import json
from pathlib import Path
import antisense_engine as engine

FILES = {'pna-2022.json': '3ad2f2732f33e810fe77b2cb947b53dc0dc68175c7d16380f20b47e626acc185',
         'pna-2025.json': 'dcdcbaede326799d77f2f1158bdcc0e4b10f338507197779aee2b150dac7b331'}


def data():
    out = []
    for name, expected in FILES.items():
        raw = (Path(__file__).with_name('antisense_data') / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected: raise ValueError('Bundled PNA evidence checksum mismatch: ' + name)
        out.append(json.loads(raw))
    return out


def catalog():
    evidence = data(); rows = [r for d in evidence for r in d['records']]
    return {'measurementRows': len(rows), 'uniqueSequences': len({r['sequence'] for r in rows}), 'files': FILES,
            'strains': engine.STRAINS, 'preparations': engine.PREPARATIONS, 'version': engine.VERSION,
            'sources': [d['source'] for d in evidence], 'remoteQualification': 'integration_unvalidated',
            'borzoi': 'Predicts RNA-seq/regulatory tracks from human or mouse DNA. The installed recipe is human hg38; not a bacterial activity engine.'}


def recipe():
    source = Path(engine.__file__).read_text()
    script = "set -euo pipefail\nOUT=/cache/out/$FOLD_TASK_ID; mkdir -p \"$OUT\"\npython -u - <<'FOLD_PNA_PY'\n" + source
    script += '\nimport os\nfrom pathlib import Path\nDATA = ' + repr(data()) + '\n'
    script += """inputs = json.loads(os.environ['FOLD_INPUT'])
analysis = run(inputs['request'], DATA, log=lambda message: print(message, flush=True))
analysis['execution'] = {'backend':'modal_cpu'}
result = {'schema':'fold-studio.biological-model-result.v1','recipe':'bio_antisense','model':VERSION,
 'inputsSha256':hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest(),
 'recipeSha256':os.environ.get('FOLD_RECIPE_SHA256'), 'analysis':analysis,
 'note':'Exploratory PNA baseline and complementary drafts; no experimentally validated activity prediction.'}
out = Path('/cache/out') / os.environ['FOLD_TASK_ID']
(out/'result.json').write_text(json.dumps(result,allow_nan=False))
print('[fold] Complete: all PNA computational stages ran on Modal CPU.',flush=True)
FOLD_PNA_PY
"""
    return {'title': 'PNA · complete exploratory workflow', 'purpose': 'Published evidence → baseline training and held-out testing → supplied-molecule/complementary-draft analysis → report, entirely on Modal CPU.',
            'source': 'Fold Studio ' + engine.VERSION + '; published data DOI 10.1093/nar/gkac362 and 10.1002/advs.202504284',
            'license': '2022 data CC BY-NC 4.0; 2025 article CC BY 4.0. Research prototype; retain source attribution.',
            'gpu': None, 'cpu': 2, 'memory': 2048, 'timeout': 600, 'demo': 'Biological Models',
            'image': {'registry': 'python:3.12-slim', 'apt': [], 'run': [], 'pip': ['numpy==2.2.6']},
            'inputs': {'request': {'type': 'antisense_request'}}, 'script': script,
            'qualification': 'integration_unvalidated', 'evidence': 'Exploratory baseline; not a validated activity predictor'}
