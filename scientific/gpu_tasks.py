"""Remote GPU tasks: anything that needs a GPU (or a big CPU node) runs on the user's active compute server.

The Mac is the interface. A task is a declared recipe (container image + command + inputs + outputs); it runs in a
Modal Sandbox on the active Modal account, writes its outputs to the account's `fold-gpu-cache` Volume, and the app
downloads them into <library>/gpu_tasks/<id>/outputs. Nothing runs locally as a fallback, nothing is started without
an explicit cost approval, and every task keeps a record (recipe, resolved inputs, account, sandbox id, logs, files).

Provider calls run in the isolated provider SDK process (biology_providers) with the selected account's Keychain
credentials. Image builds can take minutes, so launching happens in a detached provider process that reports
through files in the task folder.
"""
import hashlib, json, os, pathlib, re, subprocess, sys, time, uuid
from gpu_tasks_actions import ACTIONS
from biological_model_recipes import recipes as biological_recipes
from qwen_cell_cloud_recipe import RECIPE as QWEN_CLOUD_RECIPE, RECIPE_ID as QWEN_CLOUD_ID
from cell_training_recipe import RECIPE as CELL_TRAINING_RECIPE, RECIPE_ID as CELL_TRAINING_ID

APP_NAME = 'fold-gpu-tasks'
VOLUME = 'fold-gpu-cache'
GPUS = ('T4', 'L4', 'A10G', 'L40S', 'A100-40GB', 'A100-80GB', 'H100')
NETWORK = {'gpu_task_launch', 'gpu_task_poll', 'gpu_task_fetch', 'gpu_task_cancel_remote', 'gpu_task_exec_remote', 'gpu_task_terminal_remote'}
PROVIDERS = [
    {'id': 'modal', 'name': 'Modal', 'state': 'available', 'note': 'Sign in with the official browser login; credentials stay in the macOS Keychain.'},
    {'id': 'vast', 'name': 'Vast.ai / SSH hosts', 'state': 'available', 'note': 'Saved SSH GPU profiles from Cloud Compute.'},
    {'id': 'runpod', 'name': 'RunPod', 'state': 'planned', 'note': 'Not configured yet.'},
    {'id': 'lambda', 'name': 'Lambda Cloud', 'state': 'planned', 'note': 'Not configured yet.'},
    {'id': 'coreweave', 'name': 'CoreWeave', 'state': 'planned', 'note': 'Not configured yet.'},
    {'id': 'aws', 'name': 'AWS (EC2 / SageMaker)', 'state': 'planned', 'note': 'Not configured yet.'},
    {'id': 'gcp', 'name': 'Google Cloud (Vertex / GCE)', 'state': 'planned', 'note': 'Not configured yet.'},
    {'id': 'azure', 'name': 'Microsoft Azure', 'state': 'planned', 'note': 'Not configured yet.'},
]

RECIPES = {
    'rhofold': {
        'title': 'RhoFold+ · RNA 3D structure', 'demo': 'Demo 9',
        'purpose': 'Predict an RNA tertiary structure from sequence with the RNA-FM language model and RhoFold+ (single-sequence mode).',
        'evidence': 'Statistically predicted (deep-learning structure prediction)',
        'source': 'https://github.com/ml4bio/RhoFold @ 6bdfbda720184409eb682ce08c05d258162ddc48',
        'reference': {'citation': 'Shen T et al. Accurate RNA 3D structure prediction using a language model-based deep learning approach. Nat Methods 2024;21:2287–2298.', 'doi': '10.1038/s41592-024-02487-0'},
        'license': 'Code Apache-2.0. Checkpoint from huggingface.co/cuhkaih/rhofold: licence of the weights not stated there; the associated dataset is non-commercial only. Treat as research use.',
        'gpu': 'A10G', 'timeout': 3600,
        'image': {'registry': 'pytorch/pytorch:2.1.2-cuda12.1-cudnn8-runtime', 'apt': ['git', 'wget'],
                  'run': ['git clone https://github.com/ml4bio/RhoFold /opt/RhoFold && cd /opt/RhoFold && git checkout 6bdfbda720184409eb682ce08c05d258162ddc48',
                          # setup.py lists 'Bio' (not Biopython), so install the package without its declared deps and add them explicitly.
                          'cd /opt/RhoFold && pip install --no-deps -e .',
                          # RhoFold imports the pre-8.0 `simtk.*` namespace; point it at `openmm` so any OpenMM 8.x works.
                          "cd /opt/RhoFold && sed -i -e 's/simtk\\.openmm/openmm/g' -e 's/simtk\\.unit/openmm.unit/g' -e 's/import simtk\\.openmm as mm/import openmm as mm/' rhofold/relax/relax.py"],
                  # From RhoFold's setup.py and inference.py imports at the pinned commit. OpenMM with its CUDA 12 plugin, so the
                  # Amber relaxation (explicit water, no cutoff) runs on the GPU instead of falling back to a slow CPU path.
                  'pip': ['huggingface_hub', 'matplotlib', 'biopython', 'python-box', 'dm-tree', 'ml-collections', 'einops', 'tqdm', 'openmm[cuda12]==8.3.1']},
        'inputs': {'sequence': {'type': 'rna', 'max': 400}, 'relaxSteps': {'type': 'int', 'min': 0, 'max': 5000, 'default': 1000}},
        'script': r'''set -euo pipefail
OUT=/cache/out/$FOLD_TASK_ID; mkdir -p $OUT /cache/models/rhofold
python -c "import json,os;d=json.loads(os.environ['FOLD_INPUT']);open('/tmp/in.fasta','w').write('>query\n'+d['sequence']+'\n')"
[ -s /cache/models/rhofold/RhoFold_pretrained.pt ] || wget -q -O /cache/models/rhofold/RhoFold_pretrained.pt https://huggingface.co/cuhkaih/rhofold/resolve/main/rhofold_pretrained_params.pt
sha256sum /cache/models/rhofold/RhoFold_pretrained.pt > $OUT/checkpoint.sha256
cd /opt/RhoFold
RELAX=$(python -c "import json,os;print(int(json.loads(os.environ['FOLD_INPUT']).get('relaxSteps',1000)))")
python -c "import openmm;print('[fold] OpenMM platforms:',[openmm.Platform.getPlatform(i).getName() for i in range(openmm.Platform.getNumPlatforms())])"
python inference.py --input_fas /tmp/in.fasta --single_seq_pred True --output_dir $OUT/rhofold --ckpt /cache/models/rhofold/RhoFold_pretrained.pt --device cuda:0 --relax_steps $RELAX
''',
    },
    'boltz_rna': {
        'title': 'Boltz-2 · RNA structure ensemble', 'demo': 'Demo 9',
        'purpose': 'Sample several RNA 3D structures with Boltz-2 diffusion (independent samples, not a trajectory).',
        'evidence': 'Statistically predicted (generative structure model)',
        'source': 'https://github.com/jwohlwend/boltz (PyPI package boltz, major version 2)',
        'reference': {'citation': 'Passaro S et al. Boltz-2: towards accurate and efficient binding affinity prediction. bioRxiv 2025.', 'doi': '10.1101/2025.06.14.659707'},
        'license': 'MIT (code and weights).',
        'gpu': 'A10G', 'timeout': 3600,
        'image': {'registry': 'pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime', 'apt': ['git'], 'run': [], 'pip': ['boltz>=2,<3']},
        'inputs': {'sequence': {'type': 'rna', 'max': 600}, 'samples': {'type': 'int', 'min': 1, 'max': 25, 'default': 5}},
        'script': r'''set -euo pipefail
OUT=/cache/out/$FOLD_TASK_ID; mkdir -p $OUT /cache/models/boltz
python -c "
import json,os;d=json.loads(os.environ['FOLD_INPUT'])
open('/tmp/query.yaml','w').write('version: 1\nsequences:\n  - rna:\n      id: A\n      sequence: '+d['sequence']+'\n')"
N=$(python -c "import json,os;print(int(json.loads(os.environ['FOLD_INPUT']).get('samples',5)))")
boltz predict /tmp/query.yaml --out_dir $OUT/boltz --cache /cache/models/boltz --diffusion_samples $N --output_format pdb
''',
    },
    'hemocell': {
        'title': 'HemoCell · deformable blood-cell flow', 'demo': 'Demo 7',
        'purpose': 'Build HemoCell (lattice Boltzmann + immersed boundary, Palabos) and run its pipe-flow example with deformable red blood cells.',
        'evidence': 'Physics-simulated (cell-resolved blood flow)',
        'source': 'https://github.com/UvaCsl/HemoCell',
        'reference': {'citation': 'Závodszky G, van Rooij B, Azizi V, Hoekstra A. Cellular level in-silico modeling of blood rheology with an improved material model for red blood cells. Front Physiol 2017;8:563.', 'doi': '10.3389/fphys.2017.00563'},
        'license': 'AGPL-3.0. Runs only on your own server; the app does not redistribute HemoCell.',
        'gpu': None, 'cpu': 16, 'timeout': 6 * 3600,
        'image': {'registry': 'ubuntu:22.04', 'apt': ['build-essential', 'cmake', 'git', 'libopenmpi-dev', 'openmpi-bin', 'libhdf5-openmpi-dev', 'python3', 'python3-pip'],
                  'run': ['git clone --recursive https://github.com/UvaCsl/HemoCell /opt/HemoCell',
                          'cd /opt/HemoCell/examples/pipeflow && mkdir -p build && cd build && cmake .. && make -j16'],
                  'pip': ['h5py', 'numpy']},
        'inputs': {'ranks': {'type': 'int', 'min': 1, 'max': 16, 'default': 8}},
        'script': r'''set -euo pipefail
OUT=/cache/out/$FOLD_TASK_ID; mkdir -p $OUT
R=$(python3 -c "import json,os;print(int(json.loads(os.environ['FOLD_INPUT']).get('ranks',8)))")
cd /opt/HemoCell/examples/pipeflow
mpirun --allow-run-as-root --oversubscribe -n $R ./build/pipeflow config.xml
cp -r tmp $OUT/hemocell_output
''',
    },
    'physicell': {
        'title': 'PhysiCell · tumor microenvironment', 'demo': 'Oncology Demo G/H',
        'purpose': 'Build PhysiCell (agent-based cells + BioFVM diffusion) and run a published reference tumor model: 3D tumor–immune (cancer_immune) or 2D oxygen-limited heterogeneous tumor (heterogeneity). Returns cell positions, states and substrate fields for the 3D viewer.',
        'evidence': 'Mechanistic simulation (published reference parameters; not patient-specific)',
        'source': 'https://github.com/MathCancer/PhysiCell (release 1.14.2)',
        'reference': {'citation': 'Ghaffarizadeh A, Heiland R, Friedman SH, Mumenthaler SM, Macklin P. PhysiCell: An open source physics-based cell simulator for 3-D multicellular systems. PLoS Comput Biol 2018;14(2):e1005991. Tumor–immune model: Ozik J et al. BMC Bioinformatics 2018;19(Suppl 18):483.', 'doi': '10.1371/journal.pcbi.1005991'},
        'license': 'BSD-3-Clause (PhysiCell, BioFVM). Built on your server from the official release.',
        'gpu': None, 'cpu': 16, 'timeout': 6 * 3600,
        'image': {'registry': 'ubuntu:22.04', 'apt': ['build-essential', 'git'],
                  'run': ['git clone --depth 1 --branch 1.14.2 https://github.com/MathCancer/PhysiCell /opt/PhysiCell'],
                  'pip': ['numpy', 'scipy']},
        'inputs': {'sample': {'type': 'choice', 'options': ['cancer_immune', 'heterogeneity'], 'default': 'cancer_immune'},
                   'days': {'type': 'int', 'min': 1, 'max': 45, 'default': 21},
                   'immuneScale': {'type': 'float', 'min': 0, 'max': 5, 'default': 1.0},       # × number of immune cells seeded (cancer_immune only)
                   'immuneStartDay': {'type': 'float', 'min': -1, 'max': 45, 'default': -1.0},  # day immune cells are seeded; −1 keeps the sample's value
                   'killScale': {'type': 'float', 'min': 0, 'max': 5, 'default': 1.0}},        # × immune attack / kill rates
        'script': r'''set -euo pipefail
OUT=/cache/out/$FOLD_TASK_ID; mkdir -p $OUT/physicell
PY=$(command -v python3 || command -v python)
export SAMPLE=$($PY -c "import json,os;print(json.loads(os.environ['FOLD_INPUT'])['sample'])")
DAYS=$($PY -c "import json,os;print(int(json.loads(os.environ['FOLD_INPUT'])['days']))")
cp -r /opt/PhysiCell /work/pc && cd /work/pc
echo "[fold] PhysiCell $(cat VERSION.txt 2>/dev/null || echo 1.14.2) · sample $SAMPLE · $DAYS simulated days · $(nproc) cores"
make ${SAMPLE//_/-}-sample
make -j$(nproc) > build.txt 2>&1 || { tail -60 build.txt; exit 1; }
BIN=""; for f in $(ls -t); do if [ -f "$f" ] && [ -x "$f" ] && head -c4 "$f" | grep -q ELF; then BIN=$f; break; fi; done
echo "[fold] built ./$BIN"
$PY - "$DAYS" <<'PY'
import json, os, re, sys
days = int(sys.argv[1]); f = 'config/PhysiCell_settings.xml'; x = open(f).read()
x = re.sub(r'(<max_time[^>]*>)[^<]*', lambda m: m.group(1) + str(days * 1440), x, 1)
x = re.sub(r'(<omp_num_threads>)[^<]*', r'\g<1>16', x, 1)
x = re.sub(r'(<full_data>\s*<interval[^>]*>)[^<]*', lambda m: m.group(1) + str(max(60, round(days * 1440 / 60 / 60) * 60)), x, 1)
x = re.sub(r'(<SVG>\s*<interval[^>]*>[^<]*</interval>\s*<enable>)[^<]*', r'\g<1>false', x, 1)
inp = json.loads(os.environ['FOLD_INPUT']); sc, start, kill = float(inp.get('immuneScale', 1)), float(inp.get('immuneStartDay', -1)), float(inp.get('killScale', 1))
changed = []
def scale(pattern, factor, label):
    global x
    if factor == 1:
        return
    n = [0]
    def f(m):
        n[0] += 1; v = float(m.group(3)) * factor; s = str(int(round(v))) if 'type="int"' in m.group(2) else f'{v:.6g}'
        changed.append(f'{m.group(1)} {m.group(3)} -> {s}'); return f'<{m.group(1)}{m.group(2)}>{s}</{m.group(1)}>'
    x = re.sub(pattern, f, x)
    if factor != 1 and not n[0]:
        names = sorted(set(re.findall(r'<([A-Za-z_]+)[^>]*type="(?:double|int)"', x)))
        sys.exit(f'[fold] {label}: no matching parameter in this PhysiCell sample; user parameters are: {", ".join(names)}')
if (sc != 1 or start >= 0 or kill != 1) and os.environ.get('SAMPLE') != 'cancer_immune':
    sys.exit('[fold] immune settings apply only to the cancer_immune sample')
scale(r'<((?:number_of_)?immune_cells?\w*)([^>]*)>([0-9.eE+-]+)</\1>', sc, 'immune cell number')
if start >= 0:
    x, k = re.subn(r'<(immune_activation_time)([^>]*)>[^<]*</\1>', lambda m: f'<{m.group(1)}{m.group(2)}>{start * 1440:g}</{m.group(1)}>', x)
    if not k:
        sys.exit('[fold] immune start day: no immune_activation_time parameter in this sample')
    changed.append(f'immune_activation_time -> {start * 1440:g} min')
scale(r'<(\w*(?:attack|kill)_rate\w*)([^>]*)>([0-9.eE+-]+)</\1>', kill, 'immune kill rate')
open(f, 'w').write(x)
print('[fold] settings: max_time', days * 1440, 'min; full output every', max(60, round(days * 1440 / 60 / 60) * 60), 'min; SVG off')
print('[fold] immune settings changed:', '; '.join(changed) if changed else 'none (sample defaults)')
PY
mkdir -p output
./$BIN || { echo "[fold] PhysiCell exited with an error"; exit 1; }
echo "[fold] simulation finished; converting $(ls output/*.xml | wc -l) snapshots"
$PY /dev/stdin <<'PY'
import glob, json, os, xml.etree.ElementTree as ET
import numpy as np, scipy.io as sio
out = os.path.join(os.environ['OUT'], 'physicell')
files = sorted(glob.glob('output/output*.xml'))
step = max(1, len(files) // 60); keep = files[::step]
if keep[-1] != files[-1]: keep.append(files[-1])
def mat(fn):
    m = sio.loadmat(os.path.join('output', fn)); return [v for k, v in m.items() if not k.startswith('__')][0]
cfg = ET.parse('config/PhysiCell_settings.xml').getroot()
subs = [{'name': v.get('name'), 'units': v.get('units'), 'dirichlet': float(v.find('.//Dirichlet_boundary_condition').text),
         'diffusion': float(v.find('.//diffusion_coefficient').text), 'decay': float(v.find('.//decay_rate').text)} for v in cfg.iter('variable') if v.find('.//diffusion_coefficient') is not None]
rng = np.random.default_rng(0); frames = []; grid = None; types = {}; total_cells = []
for f in keep:
    r = ET.parse(f).getroot()
    t = float(r.find('.//current_time').text)
    ci = r.find('.//cellular_information')
    labels = {l.text.strip(): (int(l.get('index')), int(l.get('size'))) for l in ci.iter('label')}
    for ty in ci.iter('type'):
        if ty.get('ID') is not None: types[ty.get('ID')] = ty.text.strip()
    C = mat(next(e.text for e in ci.iter('filename') if '_cells' in e.text))
    col = lambda n, i=0: C[labels[n][0] + i] if n in labels else None
    n = C.shape[1]; total_cells.append(n)
    x, y, z = col('position', 0), col('position', 1), col('position', 2)
    rad = np.cbrt(3 * col('total_volume') / (4 * np.pi)); ty = col('cell_type').astype(int); ph = col('current_phase').astype(int)
    dead = col('dead') if 'dead' in labels else (ph >= 100).astype(float)
    extra = col('oncoprotein')
    counts = {}
    for k in np.unique(ty):
        sel = ty == k; counts[str(int(k))] = {'live': int((sel & (dead < 0.5)).sum()), 'dead': int((sel & (dead >= 0.5)).sum())}
    idx = np.arange(n) if n <= 5000 else np.sort(rng.choice(n, 5000, replace=False))
    cells = np.stack([x, y, z, rad, ty, dead, ph, extra if extra is not None else np.zeros(n)], 1)[idx]
    me = r.find('.//microenvironment'); M = mat(next(e.text for e in me.iter('filename') if 'microenvironment' in e.text))
    xs, ys, zs = np.unique(M[0]), np.unique(M[1]), np.unique(M[2]); z0 = zs[np.argmin(abs(zs))]
    sl = M[:, M[2] == z0]; ix = np.searchsorted(xs, sl[0]); iy = np.searchsorted(ys, sl[1])
    fields = []
    for s in range(len(subs)):
        g = np.full((len(ys), len(xs)), np.nan); g[iy, ix] = sl[4 + s]; fields.append([None if not np.isfinite(v) else round(float(v), 4) for v in g.ravel()])
    grid = {'x': xs.tolist(), 'y': ys.tolist(), 'z0': float(z0), 'nz': int(len(zs)), 'voxels': int(M.shape[1])}
    frames.append({'t': t, 'total': int(n), 'sampled': int(len(idx)), 'counts': counts, 'cells': np.round(cells, 2).tolist(), 'fields': fields})
    print(f'[fold] frame t={t/1440:.2f} d · {n} cells')
json.dump({'engine': 'PhysiCell', 'version': open('VERSION.txt').read().strip() if os.path.exists('VERSION.txt') else '1.14.2', 'sample': os.environ.get('SAMPLE', ''),
           'substrates': subs, 'types': types, 'grid': grid, 'frames': frames, 'snapshots': len(files), 'sampling': 'up to 5000 cells per frame, uniform without replacement, seed 0; counts use every cell'},
          open(os.path.join(out, 'tme.json'), 'w'), separators=(',', ':'))
PY
cp config/PhysiCell_settings.xml $OUT/physicell/
LAST=$(ls output/output*.xml | tail -1); B=${LAST%.xml}; cp $B* $OUT/physicell/ 2>/dev/null || true
echo "[fold] done: tme.json $(du -h $OUT/physicell/tme.json | cut -f1)"
''',
    },
    'tahoe_atlas': {
        'title': 'Tahoe-100M drug atlas · filter and pack', 'demo': 'Virtual Cell',
        'purpose': 'Download all 1,026 Tahoe-100M pseudobulk differential-expression files (≈ 89 GB) at datacenter speed, keep the virtual cell gene panel and pack one log2FC and SE row per cell line × drug × dose × plate (scientific/virtual_cell_tahoe.py, parallel mode).',
        'evidence': 'Experimental observation (DESeq2 fold changes of measured cells; no model)',
        'source': 'https://huggingface.co/datasets/tahoebio/Tahoe-100M (pseudobulk_differential_expression)',
        'reference': {'citation': 'Tahoe-100M: Mapping drug-induced molecular phenotypes at single-cell resolution. Cell 2026.', 'doi': None},
        'license': 'CC0 1.0 (dataset).',
        'gpu': None, 'cpu': 16, 'memory': 32768, 'timeout': 3 * 3600,
        'image': {'registry': 'python:3.11-slim', 'apt': ['curl'], 'run': [], 'pip': ['numpy==2.2.6', 'pyarrow==21.0.0']},
        'inputs': {'files': {'type': 'files'}},
        'script': r'''set -euo pipefail
OUT=/cache/out/$FOLD_TASK_ID; mkdir -p $OUT /work
# files ending in .gz.b64 are gzip+base64 (one environment string is capped at 128 KB on Linux)
python -c "
import base64,gzip,json,os
for n,c in json.loads(os.environ['FOLD_INPUT'])['files'].items():
    open('/work/'+n[:-7],'wb').write(gzip.decompress(base64.b64decode(c))) if n.endswith('.gz.b64') else open('/work/'+n,'w').write(c)"
cd /work && python virtual_cell_tahoe.py parallel /work $OUT 14
ls -la $OUT
''',
    },
    'custom': {
        'title': 'Custom model or command', 'demo': None,
        'purpose': 'Run any public container image or pip-installable model with your own command. Put results in $OUT.',
        'evidence': 'Depends on the model you run: label it when you import the results.',
        'source': 'User-defined', 'reference': None, 'license': 'Your responsibility: check the licence of the image, code and weights you run.',
        'gpu': 'L4', 'timeout': 3600,
        'image': None,
        'inputs': {'registry': {'type': 'image'}, 'pip': {'type': 'list'}, 'apt': {'type': 'list'}, 'command': {'type': 'command'}, 'files': {'type': 'files'}},
        'script': None,
    },
}

RECIPES.update(biological_recipes())
RECIPES[QWEN_CLOUD_ID]=QWEN_CLOUD_RECIPE
RECIPES[CELL_TRAINING_ID]=CELL_TRAINING_RECIPE

def _folder(s):
    f = pathlib.Path(s.root) / 'gpu_tasks'
    f.mkdir(parents=True, exist_ok=True)
    return f


def _safe_id(v):
    v = str(v or '')
    if not re.fullmatch('[a-f0-9]{32}', v):
        raise ValueError('Invalid task identifier.')
    return v


def _clean_inputs(recipe_id, raw):
    r = RECIPES[recipe_id]
    out = {}
    for k, spec in r['inputs'].items():
        v = raw.get(k, spec.get('default'))
        t = spec['type']
        if t == 'antisense_request':
            import antisense_engine
            v = antisense_engine.clean(v)
        elif t in ('dna', 'dna_optional', 'protein'):
            v = ''.join(str(v or '').split()).upper()
            alphabet = 'ACDEFGHIKLMNPQRSTVWY' if t == 'protein' else 'ACGT'
            if (not v and t != 'dna_optional') or set(v) - set(alphabet) or len(v) > spec['max']:
                raise ValueError(f'{k}: use {alphabet}, up to {spec["max"]} symbols.')
        elif t == 'rna':
            v = ''.join(str(v or '').split()).upper().replace('T', 'U')
            if not v or set(v) - set('ACGU') or len(v) > spec['max']:
                raise ValueError(f'Enter an RNA sequence of A, C, G, U up to {spec["max"]} nt.')
        elif t == 'int':
            if recipe_id.startswith('bio_') and (isinstance(v, bool) or not isinstance(v, (int, float, str)) or not float(v).is_integer()):
                raise ValueError(f'{k} must be an integer.')
            v = int(v)
            if not spec['min'] <= v <= spec['max']:
                raise ValueError(f'{k} must lie in {spec["min"]}–{spec["max"]}.')
        elif t == 'float':
            v = float(v)
            if not spec['min'] <= v <= spec['max']:
                raise ValueError(f'{k} must lie in {spec["min"]}–{spec["max"]}.')
        elif t == 'choice':
            v = str(v)
            if v not in spec['options']:
                raise ValueError(f'{k} must be one of {", ".join(spec["options"])}.')
        elif t == 'image':
            v = str(v or '').strip()
            if not re.fullmatch(r'[a-z0-9][a-z0-9._/:@-]{1,200}', v):
                raise ValueError('Enter a public container image such as pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime.')
        elif t == 'list':
            v = [str(x).strip() for x in (v or []) if str(x).strip()]
            if len(v) > 40 or any(not re.fullmatch(r'[A-Za-z0-9._<>=!~+\-\[\],@/:]{1,120}', x) for x in v):
                raise ValueError(f'{k}: use up to 40 plain package specifiers.')
        elif t == 'command':
            v = str(v or '')
            if not v.strip() or len(v) > 8000 or '\0' in v:
                raise ValueError('Enter a command of up to 8,000 characters.')
        elif t == 'files':
            v = {str(n): str(c) for n, c in (v or {}).items()}
            if any(not re.fullmatch(r'[A-Za-z0-9._-]{1,80}', n) for n in v) or sum(len(c) for c in v.values()) > 2_000_000:
                raise ValueError('Input files: simple names, 2 MB in total.')
        out[k] = v
    return out


def _gpu(recipe_id, raw):
    r = RECIPES[recipe_id]
    g = raw.get('gpu', r['gpu'])
    if g is None:
        return None
    if g not in GPUS:
        raise ValueError('Choose a GPU type: ' + ', '.join(GPUS))
    return g


# ------------------------------------------------------------------ provider process helpers

def _provider(s):
    import biology_providers as bp
    from cloud_accounts import get, environment
    python = bp.interpreter(s)
    if not python or not bp.status(s)['installed']:
        raise ValueError('Install the pinned provider SDK runtime first (Cloud Compute › Modal).')
    account = get(s).get('activeId')
    if not account:
        raise ValueError('Sign in to a Modal account in Settings › Compute servers first.')
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'MODAL_TOKEN_ID', 'MODAL_TOKEN_SECRET', 'MODAL_PROFILE', 'MODAL_CONFIG_PATH')}
    if sys.platform == 'darwin':
        env.update(environment(s, account))
    env.update(FOLD_PROVIDER_CHILD='1', PYTHONDONTWRITEBYTECODE='1', PYTHONUNBUFFERED='1')
    return python, env, account


def _rpc(s, action, payload, timeout=100):
    python, env, _ = _provider(s)
    r = subprocess.run([str(python), '-B', str(pathlib.Path(__file__).with_name('worker.py')), '--root', str(s.root)],
                       input=json.dumps({'action': action, 'payload': payload}), text=True, capture_output=True, env=env, timeout=timeout)
    try:
        body = json.loads(r.stdout)
    except ValueError:
        raise ValueError('The provider process returned an invalid response: ' + r.stderr[-600:]) from None
    if body.get('error'):
        raise ValueError(body['error'])
    return body['result']


def _image(spec):
    import modal
    img = modal.Image.from_registry(spec['registry'], add_python='3.11' if spec['registry'].startswith('ubuntu') else None)
    if spec.get('apt'):
        img = img.apt_install(*spec['apt'])
    for cmd in spec.get('run', []):
        img = img.run_commands(cmd)
    if spec.get('pip'):
        img = img.pip_install(*spec['pip'])
    return img


LIVE_LOG = '/tmp/fold-run.log'


def _header():
    # Resource monitor: tagged [gpu]/[cpu] lines every 5 s so the app can filter hardware activity from the science.
    monitor = r"""(while true; do
  nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader 2>/dev/null | sed 's/^/[gpu] util, mem used, mem total, temp, power: /'
  echo "[cpu] load $(cut -d' ' -f1-3 /proc/loadavg) | mem $(free -m | awk '/Mem/{print $3"/"$2" MB"}') | top: $(ps -eo comm,pcpu --sort=-pcpu --no-headers | head -3 | tr -s ' ' | paste -sd'|')"
  sleep 5; done) &
"""
    return f'exec > >(tee -a {LIVE_LOG}) 2>&1\necho "[fold] container started on $(hostname) at $(date -u +%H:%M:%SZ)"\n(nvidia-smi -L 2>/dev/null || echo "[fold] no GPU attached")\n' + monitor


def _footer():
    return '\npip freeze > $OUT/environment.txt 2>/dev/null || true\n(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv > $OUT/gpu.txt) 2>/dev/null || true\nsync\n'


def _remote(action, p):
    """Runs inside the provider process (FOLD_PROVIDER_CHILD) with the account's credentials."""
    import modal
    if action == 'gpu_task_terminal_remote':
        import modal_terminal
        return modal_terminal.remote(p)
    if action == 'gpu_task_launch':
        rec = p['task']
        r = RECIPES[rec['recipe']]
        if rec['recipe'] == 'custom':
            i = rec['inputs']
            spec = {'registry': i['registry'], 'apt': i['apt'], 'run': [], 'pip': i['pip']}
            files = ''.join(f"python -c \"import json,os;open('/work/{n}','w').write(json.loads(os.environ['FOLD_INPUT'])['files']['{n}'])\"\n" for n in i['files'])
            script = 'set -euo pipefail\nOUT=/cache/out/$FOLD_TASK_ID; mkdir -p $OUT /work; export OUT\n' + files + 'cd /work\n' + i['command'] + '\n'
        else:
            spec, script = r['image'], r['script']
        app = modal.App.lookup(APP_NAME, create_if_missing=True)
        vol = modal.Volume.from_name(VOLUME, create_if_missing=True)
        # GPU containers get 8 cores too: several tools (e.g. relaxation, data prep) still run CPU stages.
        kw = {'gpu': rec['gpu'], 'cpu': 8.0} if rec['gpu'] else {'cpu': float(r.get('cpu', 4))}
        if r.get('memory'):
            kw['memory'] = int(r['memory'])
        # Stream Modal's image-build output to stderr (launch.log) so the app can show build progress.
        with modal.enable_output():
            sb = modal.Sandbox.create('bash', '-lc', _header() + script + _footer(), app=app, image=_image(spec), timeout=int(rec['timeout']), volumes={'/cache': vol},
                                      env={'FOLD_TASK_ID': rec['id'], 'FOLD_INPUT': json.dumps(rec['inputs']), 'FOLD_RECIPE_SHA256': rec['recipeSha256']}, **kw)
        return {'sandboxId': sb.object_id, 'appName': APP_NAME, 'launched': time.time()}
    if action == 'gpu_task_poll':
        sb = modal.Sandbox.from_id(p['sandboxId'])
        code = sb.poll()
        out = {'running': code is None, 'returncode': code}
        if code is None:
            try:
                t = sb.exec('tail', '-n', '1500', LIVE_LOG, timeout=20)
                t.wait()
                out['liveLog'] = t.stdout.read()[-150000:]
            except Exception as e:
                out['liveLog'] = f'[fold] live log unavailable: {type(e).__name__}'
        if code is not None:
            out['stdout'] = sb.stdout.read()[-60000:]
            out['stderr'] = sb.stderr.read()[-60000:]
        return out
    if action == 'gpu_task_fetch':
        vol = modal.Volume.from_name(VOLUME)   # client-side reads see committed data; reload() is container-only
        base = 'out/' + p['taskId']
        files, total = {}, 0
        # Entry types are an IntEnum (str() gives '2'), so compare against the enum itself; only regular files are read.
        for e in vol.listdir(base, recursive=True):
            if e.type != modal.volume.FileEntryType.FILE:
                continue
            name = e.path.lstrip('/')
            data = b''.join(vol.read_file(name))
            total += len(data)
            if total > 400 * 1024 ** 2:
                raise ValueError('Outputs exceed 400 MB; download them from the Volume directly.')
            files[name[len(base) + 1:]] = data.hex()
        return {'files': files}
    if action == 'gpu_task_cancel_remote':
        modal.Sandbox.from_id(p['sandboxId']).terminate()
        return {'terminated': True}
    if action == 'gpu_task_exec_remote':
        sb = modal.Sandbox.from_id(p['sandboxId'])
        if sb.poll() is not None:
            raise ValueError('The task container has finished; commands run only in a live container.')
        proc = sb.exec('bash', '-lc', p['command'], timeout=60)
        proc.wait()
        return {'stdout': proc.stdout.read()[-60000:], 'stderr': proc.stderr.read()[-20000:], 'exitCode': proc.returncode}
    if action == 'compute_server_probe':
        modal.Client.from_env()
        return {'authenticated': True}
    raise ValueError('Unsupported remote task action.')


# ------------------------------------------------------------------ local task management

def _read(s, tid):
    f = _folder(s) / _safe_id(tid) / 'task.json'
    if not f.is_file():
        raise ValueError('Unknown task.')
    return json.loads(f.read_text())


def _write(s, rec):
    d = _folder(s) / rec['id']
    d.mkdir(exist_ok=True)
    temp=d/('task.'+uuid.uuid4().hex+'.partial');temp.write_text(json.dumps(rec));temp.replace(d/'task.json')


def submit(s, p):
    rid = str(p.get('recipe'))
    if rid not in RECIPES:
        raise ValueError('Unknown task recipe.')
    if RECIPES[rid].get('preparedOnly'):
        raise ValueError('This training study requires a verified data upload and its prepared launcher before GPU allocation.')
    if p.get('approvedRemoteCost') is not True:
        raise ValueError('Approve running this task on your server account; GPU time and image builds are billed by the provider.')
    r = RECIPES[rid]
    inputs = _clean_inputs(rid, p.get('inputs') or {})
    python, env, account = _provider(s)
    timeout = int(p.get('timeout', r['timeout']))
    if not 60 <= timeout <= 24 * 3600:
        raise ValueError('Timeout must lie between 1 minute and 24 hours.')
    rec = {'id': uuid.uuid4().hex, 'recipe': rid, 'title': r['title'], 'inputs': inputs, 'gpu': _gpu(rid, p), 'timeout': timeout, 'accountId': account,
           'inputSource': p.get('inputSource'), 'projectId': p.get('projectId'), 'provider': 'modal', 'state': 'launching', 'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'evidence': r['evidence'], 'source': r['source'],
           'license': r['license'], 'label': str(p.get('label') or '')[:120]}
    rec['recipeSha256'] = hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()
    rec['inputsSha256'] = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    _write(s, rec)
    d = _folder(s) / rec['id']
    (d / 'launch-request.json').write_text(json.dumps({'action': 'gpu_task_launch', 'payload': {'task': rec}}))
    with open(d / 'launch-request.json') as fin, open(d / 'launch.json', 'w') as fout, open(d / 'launch.log', 'w') as ferr:
        # The child keeps its own copies of these descriptors; ours close when the block ends.
        proc = subprocess.Popen([str(python), '-B', str(pathlib.Path(__file__).with_name('worker.py')), '--root', str(s.root)],
                                stdin=fin, stdout=fout, stderr=ferr, env=env, start_new_session=True)
    rec['launcherPid'] = proc.pid
    _write(s, rec)
    return rec


def _alive(pid):
    try:
        done, _ = os.waitpid(pid, os.WNOHANG)
        if done == pid:
            return False
    except ChildProcessError:
        pass
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def status(s, p):
    import fcntl
    d=_folder(s)/_safe_id(p.get('taskId'))
    if not d.is_dir():raise ValueError('Unknown task.')
    with (d/'status.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return {**_read(s,p.get('taskId')),'phase':'A status update is already in progress'}
        return _status(s,p)


def _status(s, p):
    rec = _read(s, p.get('taskId'))
    if rec.get('provider') == 'local':
        # Local scientific checks use the same record/log viewer, without provider calls.
        return dispatch(s, 'gpu_task_record', p)
    d = _folder(s) / rec['id']
    if p.get('retryFetch') and rec.get('fetchError') and rec.get('sandboxId'):
        # The run finished but its download failed: ask the server again instead of re-running (and re-paying).
        rec['state'] = 'running'
        rec.pop('fetchError', None); rec.pop('error', None)
    if rec['state'] == 'launching':
        body = (d / 'launch.json').read_text(errors='replace') if (d / 'launch.json').is_file() else ''
        lines = [l for l in body.splitlines() if l.strip()]
        res = None
        if lines and lines[-1].lstrip().startswith('{'):
            try:
                res = json.loads(lines[-1])
            except ValueError:
                res = None
        build = '\n'.join(l for l in (lines[:-1] if res is not None else lines) if 'token' not in l.lower())
        if build:
            (d / 'build.log').write_text(build)
        if res is not None:
            if res.get('error'):
                rec.update(state='failed', error=res['error'])
            else:
                rec.update(state='running', **res['result'])
        elif _alive(rec['launcherPid']):
            log = (d / 'launch.log').read_text(errors='replace') if (d / 'launch.log').is_file() else ''
            out = {k: v for k, v in rec.items() if k != 'launcherPid'}
            text = '\n'.join(l for l in (build + '\n' + log).splitlines() if l.strip() and 'token' not in l.lower())
            return {**out, 'phase': 'Building the container image on your server' if 'Building image' in text else 'Contacting your server',
                    'serverLog': text[-12000:] or '[fold] waiting for the first message from Modal…'}
        else:
            log = (d / 'launch.log').read_text(errors='replace') if (d / 'launch.log').is_file() else 'no log'
            rec.update(state='failed', error='The launcher stopped: ' + '\n'.join(l for l in log.splitlines() if 'token' not in l.lower())[-1500:])
        _write(s, rec)
    if rec['state'] == 'running':
        try:
            poll = _rpc(s, 'gpu_task_poll', {'sandboxId': rec['sandboxId']})
        except (ValueError, subprocess.TimeoutExpired) as e:
            # A slow or dropped connection is not a task failure: keep the task and retry on the next poll.
            return {**{k: v for k, v in rec.items() if k != 'launcherPid'}, 'phase': 'Server not reachable right now · retrying',
                    'serverLog': f'[fold] could not reach the server: {str(e)[-400:]}'}
        if poll['running']:
            (d / 'live.log').write_text(poll.get('liveLog') or '')
            _write(s, rec)
            return {**{k: v for k, v in rec.items() if k != 'launcherPid'}, 'phase': 'Running on ' + (rec.get('gpu') or 'CPU'), 'serverLog': poll.get('liveLog') or ''}
        if not poll['running']:
            (d / 'stdout.txt').write_text(poll.get('stdout') or '')
            (d / 'stderr.txt').write_text(poll.get('stderr') or '')
            rec['returncode'] = poll['returncode']
            rec['finished'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            try:
                got = _rpc(s, 'gpu_task_fetch', {'taskId': rec['id']}, timeout=600)
            except ValueError as e:
                got = {'files': {}}
                rec['fetchError'] = str(e)[-800:]
            out = d / 'outputs'
            out.mkdir(exist_ok=True)
            manifest = []
            for name, hexdata in got['files'].items():
                target = (out / name).resolve()
                if out.resolve() not in target.parents:
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                data = bytes.fromhex(hexdata)
                target.write_bytes(data)
                manifest.append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
            rec['outputs'] = manifest
            rec['state'] = 'done' if poll['returncode'] == 0 and not rec.get('fetchError') else 'failed'
            if rec.get('stopRequested'):
                rec['state'] = 'stopped'
                rec['error'] = f'Stopped by you; {len(manifest)} file(s) written before the stop were kept.'
            elif poll['returncode'] != 0:
                rec['error'] = f'Exit code {poll["returncode"]}. ' + '\n'.join(l for l in (poll.get('stderr') or '').splitlines() if 'token' not in l.lower())[-800:]
            elif rec.get('fetchError'):
                rec['error'] = 'The task finished but its outputs could not be downloaded: ' + rec['fetchError']
        _write(s, rec)
    return {k: v for k, v in rec.items() if k != 'launcherPid'}


def dispatch(s, action, p):
    if os.environ.get('FOLD_PROVIDER_CHILD') and action in NETWORK | {'compute_server_probe'}:
        return _remote(action, p)
    if action == 'gpu_tasks_catalog':
        return {'recipes': {k: {f: v for f, v in r.items() if f not in ('script',)} for k, r in RECIPES.items()}, 'gpus': list(GPUS), 'app': APP_NAME, 'volume': VOLUME}
    if action == 'gpu_task_submit':
        return submit(s, p)
    if action == 'gpu_task_terminal':
        import modal_terminal
        return modal_terminal.dispatch(s, p)
    if action == 'gpu_task_launch':
        raise ValueError('Launch runs only in the provider process.')
    if action == 'gpu_task_status':
        return status(s, p)
    if action == 'gpu_task_record':
        rec = _read(s, p.get('taskId'))
        d = _folder(s) / rec['id']
        rec['stdout'] = (d / 'stdout.txt').read_text()[-20000:] if (d / 'stdout.txt').is_file() else ''
        rec['stderr'] = (d / 'stderr.txt').read_text()[-20000:] if (d / 'stderr.txt').is_file() else ''
        rec['buildLog'] = (d / 'build.log').read_text(errors='replace')[-20000:] if (d / 'build.log').is_file() else ''
        if rec['state'] == 'running':
            rec['serverLog'] = (d / 'live.log').read_text(errors='replace')[-60000:] if (d / 'live.log').is_file() else ''
        rec['commandHistory'] = []
        history = d / 'terminal.jsonl'
        if history.is_file():
            with history.open('rb') as f:
                f.seek(max(0, history.stat().st_size - 512000)); raw = f.read(512000)
            for line in raw.splitlines():
                try:
                    row = json.loads(line)
                    if isinstance(row, dict) and isinstance(row.get('command'), str): rec['commandHistory'].append(row)
                except (ValueError, UnicodeDecodeError): pass
            rec['commandHistory'] = rec['commandHistory'][-50:]
        return rec
    if action == 'gpu_tasks_list':
        rows = []
        project = p.get('projectId')
        for d in sorted((x for x in _folder(s).iterdir() if (x / 'task.json').is_file()), key=lambda x: x.stat().st_mtime, reverse=True):
            r = json.loads((d / 'task.json').read_text())
            if project and r.get('projectId') != project:
                continue
            rows.append({k: r.get(k) for k in ('id', 'recipe', 'title', 'state', 'created', 'finished', 'gpu', 'label', 'error', 'projectId')})
            if len(rows) == 60:
                break
        return rows
    if action == 'gpu_task_cancel':
        rec = _read(s, p.get('taskId'))
        if rec.get('provider') == 'local':raise ValueError('Local scientific checks expose read-only progress in this controller.')
        if rec.get('sandboxId') and rec['state'] == 'running':
            _rpc(s, 'gpu_task_cancel_remote', {'sandboxId': rec['sandboxId']})
            rec['stopRequested'] = True     # the next status poll downloads whatever the task already wrote
            _write(s, rec)
            return status(s, {'taskId': rec['id']})
        rec['state'] = 'cancelled'
        _write(s, rec)
        return rec
    if action == 'gpu_task_exec':
        rec = _read(s, p.get('taskId'))
        if rec.get('provider') == 'local': raise ValueError('Local preparation and test runs expose read-only logs here.')
        command = str(p.get('command') or '')
        if not command.strip() or len(command) > 4000 or '\0' in command:
            raise ValueError('Enter a command of up to 4,000 characters.')
        if p.get('approvedRemoteCommand') is not True:
            raise ValueError('Approve running this command inside your task container.')
        if rec.get('state') != 'running':
            raise ValueError('Commands run only while the task container is running.')
        try:
            out = _rpc(s, 'gpu_task_exec_remote', {'sandboxId': rec['sandboxId'], 'command': command}, timeout=90)
        except (ValueError, subprocess.TimeoutExpired) as error:
            with (_folder(s) / rec['id'] / 'terminal.jsonl').open('a') as f:
                f.write(json.dumps({'time': time.time(), 'command': command, 'exitCode': None, 'status': 'unknown', 'error': str(error)[-2000:]}) + '\n')
            raise
        with (_folder(s) / rec['id'] / 'terminal.jsonl').open('a') as f:
            f.write(json.dumps({'time': time.time(), 'command': command, 'exitCode': out['exitCode'], 'status': 'completed',
                               'stdout': (out.get('stdout') or '')[-16000:], 'stderr': (out.get('stderr') or '')[-16000:]}) + '\n')
        return out
    if action == 'gpu_task_rna3d_compare':
        import rna3d_compare
        rec = _read(s, p.get('taskId'))
        return rna3d_compare.compare_task(_folder(s) / rec['id'] / 'outputs', p)
    if action == 'compute_servers':
        from cloud_accounts import get
        import execution_policy
        accounts = get(s)
        try:
            import biology_providers as bp
            sdk = bp.status(s)
        except Exception as e:
            sdk = {'installed': False, 'error': str(e)}
        return {'providers': PROVIDERS, 'modal': {'activeId': accounts.get('activeId'), 'profiles': [{k: v for k, v in a.items() if k != 'configuration'} for a in accounts.get('profiles', [])],
                'sdkInstalled': sdk.get('installed', False)}, 'backend': execution_policy.selected(s), 'gpuTasks': {'app': APP_NAME, 'volume': VOLUME}}
    if action == 'compute_server_select':
        import execution_policy
        return execution_policy.dispatch(s, 'execution_backend_select', p)
    raise ValueError('Unsupported GPU task action.')
