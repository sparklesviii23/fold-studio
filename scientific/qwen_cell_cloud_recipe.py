"""Fixed prepared experiment; never a generic empty-input training button."""
RECIPE_ID='qwen_cell_cloud_training'
REVISION='488639f1ff808d1d3d0ba301aef8c11461451ec5'

RECIPE={
    'title':'Qwen · expanded biological training', 'demo':'Virtual Cell',
    'purpose':'One reviewed study: complete context, 2,000 distinct training cells, typed biological response heads, three seeds and matched fixed-Qwen controls.',
    'evidence':'Experimental model training; reused development cases; no automatic promotion',
    'source':'Local reviewed Fold Studio study; official Qwen2.5-Coder-3B-Instruct at '+REVISION,
    'license':'Qwen Apache-2.0; public Norman, Replogle and Tahoe-derived research inputs; provenance retained in the data manifest.',
    'gpu':'A100-80GB','timeout':2700,'memory':32768,'preparedOnly':True,
    'image':{'registry':'pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime@sha256:c16f4c749e2d9e96878875cdf6cc45cddda1d1a36fddd371dd6f2360f1b6e2a2','apt':[], 'run':[],
             'pip':['transformers==4.57.6','numpy==2.2.6','safetensors==0.6.2']},
    'inputs':{'files':{'type':'files'}},
    'script':r'''set -euo pipefail
export OUT=/cache/out/$FOLD_TASK_ID
mkdir -p "$OUT"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
python - <<'PY'
import hashlib,json,os,re,sys
from pathlib import Path
request=json.loads(json.loads(os.environ['FOLD_INPUT'])['files']['launch.json'])
key=request['studyKey'];expected=request['manifestSha256']
if not all(re.fullmatch('[0-9a-f]{64}',s) for s in [key,expected]):raise ValueError('Invalid sealed study identity.')
root=Path('/cache/qwen-cell-studies')/key
manifest=root/'ASSET_MANIFEST.json'
if hashlib.sha256(manifest.read_bytes()).hexdigest()!=expected:raise ValueError('Staged manifest changed.')
files=json.loads(manifest.read_text())['files']
entry=next(f for f in files if f['path']=='code/qwen_cell_cloud_entry.py')
if hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Entry source changed.')
sys.path.insert(0,str(root/'code'))
from qwen_cell_cloud_entry import main
main(root,Path(os.environ['OUT']),Path('/cache/qwen-cell-archive')/os.environ['FOLD_TASK_ID'])
PY
''',
}
