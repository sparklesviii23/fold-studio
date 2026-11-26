# Large assets (not in git)

Model weights, datasets and Python runtimes are not committed. They total about
45 GB, and several carry research-only or non-commercial terms that forbid
redistribution. This repository commits the pins (source URL, revision, size,
SHA-256) instead. Fetch the files from the original providers.

## Quick start on a new Mac

```sh
git clone https://github.com/sparklesviii23/fold.git
cd fold
bash scripts/setup.sh            # pnpm install + Python runtimes from runtimes-lock/
bash scripts/setup.sh --models   # pinned model weights, about 18 GB, checksum-verified
```

Requires macOS on Apple Silicon, Python 3.12 (`brew install python@3.12`), pnpm,
and Rust for the desktop build. The workspace is the folder that contains the
clone; set `FOLD_WORKSPACE` to use another one. Datasets download on first use.

## Pin files (source of truth)

| Asset | Pin file | Fetch |
|---|---|---|
| AlphaFold 2 params (`params_model_*_{ptm,multimer_v3}.npz`) | `scientific/af2-parameters.json` | `python3 scripts/fetch-af2-parameter.py --model model_1_ptm --directory <models>/alphafold` |
| Boltz-2 (`boltz2_conf.ckpt`, `boltz2_aff.ckpt`) | `scientific/boltz-parameters.json` | Hugging Face `boltz-community/boltz-2` at the pinned revision |
| Remote-worker models (AlphaFold, BoltzGen, ProteinMPNN, SolubleMPNN, ESMFold2) | `remote_worker/fold_rapid/model-catalog.json` | Remote worker acquires them on approval |
| Qwen2.5-Coder-3B, C2S-Pythia-410m, CellFlux, Boltz-2 (incl. `boltz2_aff.ckpt`, `mols.tar`) | `scientific/model-assets.json` | `python3 scripts/fetch-models.py` |
| Python runtimes | `runtimes-lock/<name>.txt` (full `pip freeze`) | `bash scripts/setup.sh` |
| BindCraft2 source + ProteinMPNN weights | `vendor/bindcraft2-source.json` | Committed in `vendor/bindcraft2` (upstream `PacesaLab/BindCraft2`, pinned revision) |

## Datasets

Data loaders in `scientific/` download and cache these on first use. See
`docs/ONCOLOGY_DATA_AND_ANALYSIS.md`, `docs/VIRTUAL_CELL_INTEGRATION.md` and
`docs/VIRTUAL_CELL_VALIDATION.md` for sources and licenses.

- Oncology: DepMap 24Q4, GDSC 8.5, Sanger essentiality, NCI ALMANAC, cBioPortal TCGA PanCan, NuInsSeg (`scientific/oncology_data.py`, `scientific/oncology.py`)
- Virtual cell: Tahoe-100M, Replogle 2022, Norman 2019, CELLxGENE, CellFlux checkpoints (`scientific/virtual_cell_*.py`, `scientific/cellflux_runner.py`)
- Cell EM: OpenOrganelle `jrc_hela-2` (written under `reports/rna-design/release-library/cell_em/data/`, ignored)

## Local workspace layout

On the development machine these live in the parent workspace folder, outside this repo:

```
<workspace>/
  fold/   this repository
  models/        AlphaFold params
  runtimes/      Python venvs (jax-metal, jax-cpu, openmm-cpu, singlecell, ...)
  upstream/      BindCraft2, boltzgen, metaljax checkouts (separate git repos)
  validation/    engine runs, model caches, downloaded datasets
```

Rebuild the runtimes with `bash scripts/setup.sh` (or `--only <name>` for one).
Do not copy the venv folders. Install receipts such as
`scientific/qwen_rna_install.json` write paths as `${FOLD_WORKSPACE}/...`;
`scientific/workspace.py` resolves them.

The packaged app bundles its own runtimes (`runtime`, `runtime-boltz`, ...),
built by `scripts/build-local-app.sh` from an existing tested environment.

## Outputs you cannot download again

Trained checkpoints (`validation/**/gpu_tasks/*/outputs/*.safetensors`, the
Qwen RNA and RNA-design heads under `engine/models/qwen-rna` and
`engine/models/rna-design`) and benchmark predictions exist only on the
original machine. Without them, features that need them report the checkpoint
as missing. For a durable copy, upload
them to a private Hugging Face repo or Zenodo, then add the URL and SHA-256 here.
