# FOLD STUDIO

FOLD STUDIO is an experimental macOS research application for protein design,
molecular analysis, RNA design, cell simulation and cancer data analysis. It runs
on Apple Silicon. Heavy jobs can run on this Mac or on a cloud server you connect.

Version 4.3.0. Research software: every result is a computational prediction or
simulation, not an experimental measurement. Each screen labels what kind of
evidence it shows.

## Contents

- [What's inside](#whats-inside)
- [How it works](#how-it-works)
- [Getting started](#getting-started)
- [Project Metal · current macOS scope](#project-metal--current-macos-scope)
- [Requirements and build](#requirements-and-build)
- [Current limitations](#current-limitations)

## What's inside

The app is organised into areas: **Research**, **Design**, **Analyse** and
**Visualise**. Each item below links to its detailed document.

### Protein structures and design

- **Structure viewer and library.** Import PDB and mmCIF files and view them with
  Mol* (atoms, cartoons, surfaces, chain and residue colours, measurements). A
  saved research library keeps names, notes and projects.
- **BindCraft2 binder design on Apple Silicon.** The original BindCraft2 pipeline
  runs locally without an NVIDIA GPU: AlphaFold2 design, ProteinMPNN sequence
  redesign, independent AlphaFold2 refolding, then the original filters and
  ranking. Campaigns can be paused, continued, reranked and exported. See
  [Project Metal](#project-metal--current-macos-scope).
- **Boltz-2 structure prediction** on the Mac GPU (PyTorch/MPS), with affinity
  prediction.
- **Molecular Intelligence Lab.** Contacts, clashes, buried surface area,
  hotspots and interface reports for saved structures.
  [Details](docs/MOLECULAR_INTELLIGENCE_4_3.md)
- **Ligand preparation.** Turn a SMILES string into 3D conformers with RDKit and
  export SDF. [Details](docs/LIGAND_PREPARATION.md)
- **Short protein dynamics.** OpenMM simulations of saved proteins, and a
  reference molecular-dynamics demo on Trp-cage.
  [Pilots](docs/DYNAMICS_PILOTS.md) · [Reference](docs/MD_REFERENCE.md)
- **Molecular cinema.** Rendered movies of designed complexes.

### RNA

- **RNA Design.** Give a target secondary structure in dot-bracket notation and
  get candidate RNA sequences that fold into it, scored with ViennaRNA.
  [Details](docs/RNA_DESIGN.md)
- **Qwen RNA engine.** An experimental RNA structure predictor built on
  Qwen2.5-Coder-3B. It is a research pilot and currently scores below the
  classical baselines. [Details](docs/QWEN_RNA_ENGINE.md)
- **RNA-to-Protein Lab.** RNA folding ensembles, exact folding kinetics and
  translation. [Lab](docs/RNA_TO_PROTEIN_LAB.md) ·
  [Kinetics](docs/RNA_FOLDING_KINETICS.md)
- **EditCraft.** Genome and RNA engineering workspace: a versioned biological
  registry, a workflow editor (gene context → coding-sequence analysis → RNA
  folding), and off-target, pathway and single-cell engines.
  [Details](docs/EDITCRAFT_IMPLEMENTATION.md)

### Cells

- **Virtual Cell.** Persistent model cells (K-562, Hep G2 and Tahoe-100M cell
  lines) that you can perturb, observe, branch and compare, modelled on the AIDO
  Cell interface. Uses Replogle 2022, Norman 2019, Tahoe-100M, C2S-Pythia and
  CellFlux. [Overview](docs/VIRTUAL_CELL.md) ·
  [Capabilities and status](docs/VIRTUAL_CELL_CAPABILITIES.md)
- **Cell Explorer workspace.** Open a real HeLa cell from electron microscopy
  (OpenOrganelle `jrc_hela-2`) or an illustrative E. coli. Explore it in 3D, run
  Brownian-dynamics experiments with binding, synthesis and decay, run
  light-pulse gene-expression experiments, and compare runs side by side.
  See `AGENTS.md` and [Living Cell physics](docs/LIVING_CELL_PHYSICS.md).
- **Mechanistic Biology Lab.** Runs published SBML kinetic models with SciPy and
  shows inspectable, exportable results.
  [Details](docs/MECHANISTIC_BIOLOGY_LAB.md)
- **Multiscale experiments.** One-way coupled molecule-to-cell simulations,
  spatial reaction-diffusion, and blood-vessel transport.
  [Kernel](docs/MULTISCALE_KERNEL.md) · [Spatial](docs/SPATIAL_SOLVER.md) ·
  [Living Biology Lab](docs/LIVING_BIOLOGY_LAB.md)

### Oncology

- **Oncology Universe.** DepMap 24Q4, GDSC, Sanger, NCI ALMANAC and TCGA
  (cBioPortal) data with gene-dependency, drug-response and mutation analyses,
  perturbation models and pathology segmentation (NuInsSeg).
  [Data and analysis](docs/ONCOLOGY_DATA_AND_ANALYSIS.md)
- **Tumor microenvironment.** PhysiCell agent-based tumour simulations, run on a
  connected server. [Details](docs/ONCOLOGY_TUMOR_MICROENVIRONMENT.md)

### Compute

- **Compute servers.** One picker for the whole app: this Mac, your Modal
  account, or a saved SSH/Vast GPU host. Remote jobs show a cost estimate and need
  your approval before they start. [Details](docs/CLOUD_GPU_TASKS.md) ·
  [RAPID cloud engine](docs/RAPID_FOUNDATION.md)
- **Local worker.** A background macOS service for bounded development tasks.
  [Details](docs/LOCAL_WORKER.md)

Each engine's tested status is listed in the
[engine registry](docs/ENGINE_REGISTRY.md).

## How it works

```
React + TypeScript interface (src/)
        │  Tauri IPC
Rust desktop shell (src-tauri/)  ── admits only listed scientific actions
        │  one Python process per action
Python scientific service (scientific/worker.py → scientific/*.py)
        │
        ├─ local runtimes: JAX/Metal (AlphaFold2, BindCraft2), PyTorch/MPS (Boltz-2, Qwen),
        │                  OpenMM, ViennaRNA, single-cell tools
        ├─ research library: SQLite + files (projects, structures, jobs, saved results)
        └─ remote jobs: Modal or your server (remote_worker/)
```

- **Interface.** React 19 and TypeScript, with Mol* for molecules and WebGL2 for
  cell volumes.
- **Desktop shell.** Tauri 2 in Rust. It opens files, runs the Python service and
  refuses any scientific action that is not on its allow list.
- **Scientific service.** Python modules, one per lab. Each action runs in its
  own process, so no state is kept in memory between actions.
- **Runtimes.** Separate Python environments per engine, so their dependencies
  do not conflict. The packaged app carries its own copies.
- **Research library.** A folder with a SQLite database plus saved files. Every
  saved result keeps its inputs, model versions and a checksum, so it can be
  reopened and checked.
- **Models and data.** Large files live outside the repository and are pinned by
  revision and SHA-256. See [ASSETS.md](ASSETS.md).

## Getting started

You need a Mac with Apple Silicon, Python 3.12, pnpm, and Rust (for building the
desktop app).

```sh
brew install python@3.12 pnpm
curl https://sh.rustup.rs -sSf | sh
git clone https://github.com/sparklesviii23/fold-studio.git
cd fold-studio
bash scripts/setup.sh            # app dependencies + Python runtimes
bash scripts/setup.sh --models   # model weights, about 18 GB, checksum-verified
pnpm desktop                     # run the app in development mode
pnpm bundle                      # or build the .app
```

`setup.sh` puts runtimes and models in the folder that contains the clone (set
`FOLD_WORKSPACE` to use another). Datasets for Virtual Cell and Oncology download
inside the app the first time you use them.

Some features need files that are not public: the trained Qwen RNA and RNA
design checkpoints, and a separately installed UCSF ChimeraX for
ChimeraX-specific tools. Those features say so when the file is missing.

## Project Metal · current macOS scope

The core BindCraft2 pipeline runs locally on Apple Silicon without CUDA or NVIDIA:
original differentiable AlphaFold2 design → ProteinMPNN → independent AlphaFold2
refolding → original filters/ranking → native structure import, viewing and export.
A genuine packaged 175-residue hPDL1 campaign completed with one trajectory,
three passed independent refolds and one retained computational prediction.
Accepted coordinates and FASTA were exported through the native app and reopened.
This establishes software execution, not experimental binding.

The development app includes four private scientific runtimes and seven original
AlphaFold2 checkpoints. Its BindCraft2 core does not require a separate Python,
ChimeraX installation, NVIDIA GPU or cloud service. Existing ChimeraX-dependent
laboratory operations continue to require that separately installed runtime.

Native campaign tools include immutable preparation, original optimization,
remaining-budget continuation, interruption handling, scientific histories,
saved/custom filter reviews, multi-metric reranking, original metric listings,
coordinate scoring, statistics, and lossless trajectory compression/restoration.
Storage conversion checks logical file hashes and uses an atomic macOS stage
exchange; settings and acceptance decisions are preserved.

Sequence-only FASTA campaigns can use up to three distinct original crop states
from one immutable input. Native CPU checks include the combined padded size.
A fixed numeric crop length is normalized to the identical fixed range for a
pinned upstream logging compatibility issue; the saved recipe and adjustment
remain recorded. This is experimental support, not a biological disorder claim.

Eleven modality adapters are connected at explicitly bounded experimental scope.
**Fab is unavailable and explicitly deferred.** Larger dimensions, individual
property-specific workflows and unrestricted CLI options are not all validated.
SSD checkpointing remains a separate experiment and is not enabled in the app.
See [the measured feature inventory](docs/BINDCRAFT_FEATURE_PARITY.json) and
[the implementation tracker](docs/PROJECT_METAL_MASTER_PROGRESS.md). Historical
[M1](docs/PROJECT_METAL_M1.md)/[M2](docs/PROJECT_METAL_M2.md) reports describe earlier
checkpoints. The full port is not declared complete.

## Technology and sources

| Component | Technology and source |
| --- | --- |
| Desktop application | [Tauri 2](https://github.com/tauri-apps/tauri), Rust, native file dialogs and IPC |
| Custom interface | [React 19](https://github.com/facebook/react), TypeScript, CSS, liquid-glass panels and research workflows |
| Molecular viewport | [Mol*](https://github.com/molstar/molstar): WebGL atoms, cartoons, ribbons and surface presentation |
| Scientific engine adapter | Original FOLD Python code communicating with the user's separately installed [UCSF ChimeraX](https://www.rbvi.ucsf.edu/chimerax/) 1.12 |
| Research storage | Python standard-library SQLite and local coordinate assets |
| Local prediction | Optional [Boltz](https://github.com/jwohlwend/boltz) / boltz-community environment; tested requirements are in scientific/ |
| Cloud prediction handoff | The official [ColabFold](https://github.com/sokrypton/ColabFold) notebook; results can be imported |
| Scientific reference data | [UniProt](https://www.uniprot.org/), [AlphaFold DB](https://alphafold.ebi.ac.uk/), [RCSB PDB](https://www.rcsb.org/) and the [wwPDB CCD](https://www.wwpdb.org/data/ccd) |
| Icons and build tools | [Lucide](https://github.com/lucide-icons/lucide), Vite, pnpm, Cargo and Vitest |

FOLD's interface, project handling, service bridge, state synchronization, library editing and molecular-workflow code are application-specific code developed with AI-assisted coding. Mol* provides its existing graphics implementation; ChimeraX provides its own installed scientific algorithms. FOLD does not implement or train those upstream engines from scratch.

## Molecular Intelligence Lab · 4.3.0

Research → Molecular Intelligence provides six workspaces sharing saved structures and analyses: Structure Inspector, Interface Analyzer, Reproducibility Lab, Peptide Screening, Molecular Explorer and Research Reports. It calculates actual contacts, steric overlaps, conservative interaction geometry, sampled accessible/buried surface areas, verified confidence summaries, hotspot proximity and symmetry-aware target-aligned peptide RMSD. Candidate/control sequences, screening jobs and versioned analyses persist locally. Reports export as PDF, CSV, JSON and Markdown; original coordinate files are retained.

The new numerical code uses Python's standard library. Scientific methods are attributed to Bondi, Shrake–Rupley and Horn. Native atom typing, clash criteria and optional preparation use the separately installed ChimeraX APIs. No AI model supplies scientific measurements. Read [the usage guide, methods, tests and limitations](docs/MOLECULAR_INTELLIGENCE_4_3.md) before interpreting research results. No new paid computing service was added; new multi-seed inference was not run as part of this implementation.

## Requirements and build

For development, install Node.js/pnpm, Rust and the macOS/Xcode command-line
build tools. Scientific tests additionally need the tested Python dependencies;
model/runtime integration tests use their explicit isolated environments.
An installed compatible ChimeraX runtime remains necessary for ChimeraX-specific
laboratory functions. Boltz model resources are separately managed.

The packaged BindCraft2 core owns its Python interpreters, dependencies and model
checkpoints. Source builds must stage the four runtime folders and the AlphaFold2
model folder referenced in `src-tauri/tauri.conf.json`; these large resources are
outside the Git source checkout. `scripts/prepare-scientific-runtime.py` stages a
relocatable copy of an existing tested environment and retains dependency notices.
The local runtime/model paths and pinned versions are recorded in
[the execution state](docs/PROJECT_METAL_EXECUTION_STATE.json).

New machine: run `bash scripts/setup.sh` (add `--models` for weights); see
[ASSETS.md](ASSETS.md).

```sh
pnpm install --frozen-lockfile
pnpm test
python3 -B -m unittest discover -s tests -v
pnpm desktop
```

For an ad-hoc signed local macOS development application:

```sh
pnpm bundle
```

Default output: `src-tauri/target/release/bundle/macos/FOLD STUDIO Metal Dev.app`
(or the corresponding `CARGO_TARGET_DIR` location). The build script signs locally
ad hoc and verifies the bundle. This is not a notarized Developer ID release.
Fresh-machine and broader macOS-version acceptance remain outstanding. The main
validated host is an Apple M4 Pro with 24 GiB unified memory, macOS 26.4.1.

## Repository layout

- `src/`: React interface, Mol* viewer, scientific panels and molecular construction tools.
- `src-tauri/`: Rust shell, native capabilities, icons and package configuration.
- `scientific/`: Python service, ChimeraX adapters, peptide/graph logic and public reference chemistry.
- `fixtures/`: attributed public protein/reference records and an AlphaFold reference structure.
- `tests/`, `scripts/`: service tests, validation and build utilities.

## Current limitations

This is research software under active development. Complete ChimeraX feature parity is not achieved: some Qt-only tools, clipping effects, specialist graphics and extension interfaces still need custom adapters. Native surface picking, specialist imaging and exhaustive hardware/extension acceptance remain incomplete. The BindCraft2 core executes as described above; full upstream scope and large-model memory support remain incomplete. PS5 compute workers are not implemented. Prediction confidence and computed geometry do not establish biological binding or experimental accuracy.

The existing Mol* viewer remains in place. Renderer regression checks use the
attributed public ANGPTL3 reference; integration scripts require their documented
runtime and fixture paths. Scientific acceptance and computational reproducibility
are separate from biological or experimental validation.

## Privacy and included files

The development checkout contains source, lockfiles, tests, attribution and local
validation receipts. Runtime environments, model weights, databases, build caches
and packaged apps are stored outside the Git checkout. Application research data
belongs in its data directory; automated acceptance uses isolated validation roots.
A public source package requires a deliberate selection of validation artifacts;
the local development checkout is not itself a published release.

## Credits and licensing

FOLD application code includes an MIT license. Third-party libraries, reference data, models and external programs retain their own terms; preserve `LICENSE` and `THIRD_PARTY_NOTICES.md`. ChimeraX executables, its Qt application and upstream scientific implementation are not included. A user's license to run ChimeraX does not itself grant permission to redistribute that runtime. See the installed runtime's license and upstream terms before distributing any external components.
