<h1 align="center">FOLD STUDIO</h1>

<p align="center"><i>A research workbench for proteins, RNA and cells, built for Apple Silicon.</i></p>

<p align="center">
  <img src="docs/screenshots/home.jpg" alt="FOLD STUDIO home screen" width="100%">
</p>

<p align="center">
  <a href="https://github.com/sparklesviii23/fold-studio/releases/latest"><b>Download for macOS</b></a> ·
  <a href="#gallery">Gallery</a> ·
  <a href="#whats-inside">What's inside</a> ·
  <a href="#how-it-works">How it works</a> ·
  <a href="#getting-started">Getting started</a>
</p>

---

FOLD STUDIO puts structure prediction, protein design, RNA folding, cell
simulation and cancer data analysis in one desktop app. Light work runs on your
Mac. Heavy models run in containers on your own [Modal](https://modal.com)
account, and the results come back into the same research library.

Every result keeps its inputs, model version, logs and checksums, so you can
reopen it and see how it was made. Every screen says what kind of evidence it
shows: a measurement, a model prediction, a simulation or an illustration.
Results are computational predictions, not experimental findings.

Version 4.3.0 · macOS on Apple Silicon · app code under the MIT licence.

## Highlights

- **Protein design without an NVIDIA GPU.** The original BindCraft2 pipeline
  (AlphaFold2 design, ProteinMPNN, AlphaFold2 refolding, filters) runs on Apple
  Silicon through JAX on Metal.
- **A real cell to experiment in.** Open a HeLa cell imaged by electron
  microscopy, release molecules into it, and watch them diffuse and bind.
- **Virtual cells.** Build a K-562 cell from public Perturb-seq and DepMap data,
  switch genes on or off, add drugs, and compare branches.
- **Cloud models on your own account.** Each run needs your approval; its files,
  logs and checksums return to your library.
- **RNA end to end.** Folding ensembles, exact folding kinetics, inverse design,
  and 3D prediction checked against crystal structures.
- **Cancer data you can query.** DepMap dependencies, GDSC drug response and
  TCGA cohorts in one workspace.

## Gallery

Every picture comes from the current app. The experiments were run to make
them: local ones on an M4 Pro, cloud ones on Modal.

### Proteins and structure

<table>
<tr>
<td width="50%"><img src="docs/screenshots/molecular-viewer.jpg" alt="ANGPTL3 in the Mol* viewer"><br><sub><b>Molecular Viewer.</b> ANGPTL3 from AlphaFold DB, drawn with Mol*.</sub></td>
<td width="50%"><img src="docs/screenshots/esmfold2-gfp.jpg" alt="GFP predicted by ESMFold2"><br><sub><b>ESMFold2 on Modal (A100).</b> Green fluorescent protein predicted from sequence; the barrel fold comes out.</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/bindcraft-architect.jpg" alt="BindCraft Architect"><br><sub><b>BindCraft Architect.</b> Binder design campaigns that run locally on Apple Silicon.</sub></td>
<td width="50%"><img src="docs/screenshots/protein-explorer.jpg" alt="Protein Explorer"><br><sub><b>Protein Explorer.</b> UniProt sequences, annotations and known structures.</sub></td>
</tr>
</table>

### Cells

<table>
<tr>
<td width="50%"><img src="docs/screenshots/cell-hela.jpg" alt="HeLa cell imaged by FIB-SEM"><br><sub><b>Cell Explorer.</b> A whole HeLa cell imaged by FIB-SEM (OpenOrganelle <code>jrc_hela-2</code>), with machine-learning organelle segmentation.</sub></td>
<td width="50%"><img src="docs/screenshots/cell-hela-experiment.jpg" alt="Molecules released into the HeLa cell"><br><sub><b>An experiment inside it.</b> 120 copies of a protein released into the cytoplasm, moving by Brownian dynamics, with live counts per compartment.</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/cell-light-pulse.jpg" alt="Light pulse experiment in E. coli"><br><sub><b>Light pulse.</b> Green-light pulses drive a CcaS/CcaR reporter in E. coli; the fitted chain predicts the response.</sub></td>
<td width="50%"><img src="docs/screenshots/virtual-cell.jpg" alt="Virtual K-562 cell with KLF1 activated"><br><sub><b>Virtual Cell.</b> A K-562 cell built from Norman 2019, Replogle 2022 and DepMap, with KLF1 switched on by CRISPRa.</sub></td>
</tr>
</table>

### RNA

<table>
<tr>
<td width="50%"><img src="docs/screenshots/rhofold-3d.jpg" alt="tRNA-Phe predicted by RhoFold+"><br><sub><b>RhoFold+ on Modal (A10G).</b> Yeast tRNA-Phe predicted from sequence: the L shape is there.</sub></td>
<td width="50%"><img src="docs/screenshots/rhofold-vs-crystal.jpg" alt="RhoFold+ prediction compared with crystal structure 1EHZ"><br><sub><b>Checked against the crystal.</b> 1.83 Å C1′ RMSD to 1EHZ, all base pairs correct, no clashes.</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/rna-ensemble.jpg" alt="RNA folding ensemble"><br><sub><b>Folding ensemble.</b> 1,000 ViennaRNA samples of tRNA-Phe, grouped into distinct states with a base-pair probability dot plot.</sub></td>
<td width="50%"><img src="docs/screenshots/rna-kinetics.jpg" alt="RNA folding kinetics"><br><sub><b>Folding kinetics.</b> Every secondary structure enumerated and the master equation solved exactly, no sampling.</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/rna-design.jpg" alt="RNA inverse design results"><br><sub><b>Inverse design on Modal CPU.</b> Sequences that fold into a branched target, each checked by a second model.</sub></td>
<td width="50%"><img src="docs/screenshots/boltz-trna.jpg" alt="Boltz-2 RNA ensemble"><br><sub><b>Boltz-2 on Modal (A10G).</b> Five independent diffusion samples of the same tRNA.</sub></td>
</tr>
</table>

### Genomes, cancer and mechanisms

<table>
<tr>
<td width="50%"><img src="docs/screenshots/evo2.jpg" alt="Evo 2 DNA scores"><br><sub><b>Evo 2 on Modal (A100).</b> Likelihood of the normal HBB sequence against the sickle-cell variant, plus DNA embeddings.</sub></td>
<td width="50%"><img src="docs/screenshots/borzoi.jpg" alt="Borzoi regulatory track"><br><sub><b>Borzoi on Modal (A100).</b> A predicted CAGE expression track across a 524 kb window at the HBB locus.</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/oncology-dependency.jpg" alt="Dependency atlas showing KRAS"><br><sub><b>Oncology Universe.</b> DepMap CRISPR knockouts across 1,178 cancer cell lines: which genes each cancer cannot live without.</sub></td>
<td width="50%"><img src="docs/screenshots/oncology-tumour.jpg" alt="Tumour microenvironment models"><br><sub><b>Tumour microenvironment.</b> PhysiCell agent-based tumour–immune models, run on your server.</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshots/mechanistic.jpg" alt="MAPK cascade reaction network"><br><sub><b>Mechanistic Biology Lab.</b> The Kholodenko 2000 MAPK cascade integrated with SciPy, drawn as a reaction network.</sub></td>
<td width="50%"><img src="docs/screenshots/multiscale.jpg" alt="Multiscale experiment from mRNA to plasma"><br><sub><b>Multiscale experiments.</b> One-way coupling from ribosome traffic on an mRNA to protein levels in plasma.</sub></td>
</tr>
</table>

### Compute

<table>
<tr>
<td width="50%"><img src="docs/screenshots/cloud-tasks.jpg" alt="Cloud GPU task recipes"><br><sub><b>Cloud GPU Tasks.</b> Ready-made recipes that run in containers on your Modal account.</sub></td>
<td width="50%"><img src="docs/screenshots/local-compute.jpg" alt="Local compute diagnostics"><br><sub><b>Local Compute.</b> What this Mac can run, and which model files are present and verified.</sub></td>
</tr>
</table>

## What's inside

The app is organised into **Research**, **Design**, **Analyse** and
**Visualise**. Each entry links to its detailed document.

### Proteins

| Feature | What it does |
| --- | --- |
| **Structure viewer and library** | Import PDB and mmCIF files; view atoms, cartoons and surfaces with Mol*; keep projects, names and notes in a persistent library. |
| **BindCraft2 binder design** | The original pipeline on Apple Silicon: AlphaFold2 design → ProteinMPNN → independent AlphaFold2 refolding → the original filters and ranking. Campaigns can be paused, resumed, reranked and exported. |
| **Boltz-2 prediction** | Structure and binding-affinity prediction on the Mac GPU (PyTorch/MPS), or on Modal. |
| [**Molecular Intelligence**](docs/MOLECULAR_INTELLIGENCE_4_3.md) | Contacts, clashes, buried surface area, hotspots and interface reports. |
| [**Ligand preparation**](docs/LIGAND_PREPARATION.md) | SMILES → 3D conformers with RDKit, exported as SDF. |
| [**Dynamics**](docs/DYNAMICS_PILOTS.md) | Short OpenMM simulations of saved proteins, plus a [reference run](docs/MD_REFERENCE.md) on Trp-cage. |
| **Molecular Cinema** | Rendered movies of designed complexes. |

### RNA

| Feature | What it does |
| --- | --- |
| [**RNA Design**](docs/RNA_DESIGN.md) | Give a target shape in dot-bracket notation; get sequences that fold into it, scored by ViennaRNA and checked by a second model. |
| [**Folding and kinetics**](docs/RNA_TO_PROTEIN_LAB.md) | Ensembles, [exact folding kinetics](docs/RNA_FOLDING_KINETICS.md) with no sampling, and translation. |
| **3D prediction** | RhoFold+ and Boltz-2 on Modal, with a built-in comparison against crystal structures. |
| [**Qwen RNA**](docs/QWEN_RNA_ENGINE.md) | An experimental predictor built on Qwen2.5-Coder. It is a pilot and currently scores below the classical baselines; the app says so. |
| [**EditCraft**](docs/EDITCRAFT_IMPLEMENTATION.md) | Genome and RNA engineering: a versioned registry, a workflow editor, and off-target, pathway and single-cell engines. |

### Cells

| Feature | What it does |
| --- | --- |
| [**Virtual Cell**](docs/VIRTUAL_CELL.md) | Persistent K-562, Hep G2 and Tahoe-100M cells you perturb, read out, branch and design against. [Capability status](docs/VIRTUAL_CELL_CAPABILITIES.md) is tracked per feature. |
| **Cell Explorer** | A measured HeLa cell from FIB-SEM or an illustrative E. coli. Brownian-dynamics experiments with binding, synthesis, decay and permeable boundaries; light-pulse gene expression; runs compared side by side. See `AGENTS.md` and [Living Cell physics](docs/LIVING_CELL_PHYSICS.md). |
| [**Mechanistic Biology Lab**](docs/MECHANISTIC_BIOLOGY_LAB.md) | Published SBML kinetic models integrated with SciPy; every number traceable to the equations. |
| [**Multiscale experiments**](docs/MULTISCALE_KERNEL.md) | One-way coupling across scales, [spatial reaction–diffusion](docs/SPATIAL_SOLVER.md) and blood transport ([Living Biology Lab](docs/LIVING_BIOLOGY_LAB.md)). |

### Oncology

| Feature | What it does |
| --- | --- |
| [**Oncology Universe**](docs/ONCOLOGY_DATA_AND_ANALYSIS.md) | DepMap 24Q4, GDSC, Sanger, NCI ALMANAC and TCGA via cBioPortal: gene dependencies, drug response, mutations, perturbation models and pathology segmentation. |
| [**Tumour microenvironment**](docs/ONCOLOGY_TUMOR_MICROENVIRONMENT.md) | PhysiCell agent-based tumour–immune simulations, run on a connected server. |

### Compute

| Feature | What it does |
| --- | --- |
| [**Cloud GPU Tasks**](docs/CLOUD_GPU_TASKS.md) | Ready-made recipes (RhoFold+, Boltz-2, ESMFold2, ESMC, Evo 2, Borzoi, PhysiCell, HemoCell, RNA Design) in containers on your Modal account. Each run is approved by you and returns files, logs and checksums. |
| **Compute servers** | One picker for the whole app: this Mac, your Modal account, or a saved SSH/Vast GPU host. In cloud mode local stages are refused rather than run silently. |
| [**Local worker**](docs/LOCAL_WORKER.md) | A background macOS service for bounded development tasks. |

Each engine's tested status is listed in the
[engine registry](docs/ENGINE_REGISTRY.md), and the 70-odd documents in
[`docs/`](docs/) cover every lab in detail.

## How it works

```
React + TypeScript interface (src/)
        │  Tauri IPC
Rust desktop shell (src-tauri/)      admits only listed scientific actions
        │  one Python process per action
Python scientific service (scientific/worker.py → scientific/*.py)
        │
        ├─ local runtimes   JAX/Metal (AlphaFold2, BindCraft2), PyTorch/MPS
        │                   (Boltz-2, Qwen), OpenMM, ViennaRNA, single-cell tools
        ├─ research library SQLite + files: projects, structures, jobs, results
        └─ remote jobs      Modal or your own server (remote_worker/)
```

- **Interface.** React 19 and TypeScript, Mol* for molecules, WebGL2 for cell
  volumes.
- **Desktop shell.** Tauri 2 in Rust. It owns file dialogs, starts the Python
  service, and refuses any scientific action not on its allow list.
- **Scientific service.** One Python module per lab. Each action runs in a fresh
  process, so nothing depends on state held in memory.
- **Runtimes.** A separate Python environment per engine, so their dependencies
  never collide. The packaged app carries its own copies.
- **Research library.** A folder with SQLite and files. Each saved result keeps
  its inputs, model versions and a checksum, so it reopens exactly.
- **Models and data.** Large files live outside the repository, pinned by
  revision and SHA-256. See [ASSETS.md](ASSETS.md).

## Getting started

### Download the app

The built app is on the
[releases page](https://github.com/sparklesviii23/fold-studio/releases/latest).
Download both `.part` files and follow the install steps there. It includes the
Python runtimes and the AlphaFold2 weights, so binder design works immediately.

### Build from source

Requires macOS on Apple Silicon, Python 3.12, pnpm and Rust.

```sh
brew install python@3.12 pnpm
curl https://sh.rustup.rs -sSf | sh
git clone https://github.com/sparklesviii23/fold-studio.git
cd fold-studio
bash scripts/setup.sh            # dependencies + Python runtimes
bash scripts/setup.sh --models   # pinned model weights, ~18 GB, checksum-verified
pnpm desktop                     # run in development
pnpm bundle                      # or build the .app
```

`setup.sh` puts runtimes and models in the folder containing the clone; set
`FOLD_WORKSPACE` to choose another. Datasets for Virtual Cell and Oncology
download inside the app the first time you open those labs.

To use cloud models, open **Settings → Compute servers** and add a Modal API
token. Jobs are billed to your account, and the app asks before each run.

### Tests

```sh
pnpm test                                   # interface
node node_modules/typescript/bin/tsc -b     # types
../runtimes/gbcell/bin/python -B -m unittest discover -s tests
```

## Repository layout

| Path | Contents |
| --- | --- |
| `src/` | React interface, Mol* viewer, cell rendering, lab workspaces |
| `src-tauri/` | Rust shell, native capabilities, action allow list, packaging |
| `scientific/` | Python service: one module per lab, plus model and data adapters |
| `remote_worker/` | Code that runs inside cloud containers |
| `docs/` | Per-lab documentation, validation reports and data provenance |
| `fixtures/`, `tests/`, `scripts/` | Reference data, tests, build and setup tools |

## Current limitations

- **Hardware.** Apple Silicon only. The tested machine is an M4 Pro with 24 GB
  of unified memory on macOS 26.4.1.
- **Not notarised.** The release is signed locally, so macOS needs
  `xattr -dr com.apple.quarantine` before first launch.
- **ChimeraX.** Some tools need a separately installed UCSF ChimeraX 1.12.
  Feature parity with it is not complete.
- **Fab is deferred** and not available in this build.
- **Trained checkpoints** for Qwen RNA and RNA design are not public; features
  that need them report the checkpoint as missing.
- **Scientific scope.** Prediction confidence and computed geometry do not
  establish binding or biological activity. Nothing here is clinical advice.

## Technology and credits

| Component | Built with |
| --- | --- |
| Desktop app | [Tauri 2](https://github.com/tauri-apps/tauri), Rust |
| Interface | [React 19](https://github.com/facebook/react), TypeScript, [Lucide](https://github.com/lucide-icons/lucide), Vite |
| Molecular graphics | [Mol*](https://github.com/molstar/molstar) |
| Structure prediction | [AlphaFold2](https://github.com/google-deepmind/alphafold), [Boltz](https://github.com/jwohlwend/boltz), [BindCraft2](https://github.com/PacesaLab/BindCraft2), [RhoFold+](https://github.com/ml4bio/RhoFold), [ESMFold2](https://github.com/evolutionaryscale/esm) |
| Genome and cell models | [Evo 2](https://github.com/ArcInstitute/evo2), [Borzoi](https://github.com/calico/borzoi), [Cell2Sentence](https://huggingface.co/vandijklab), [CellFlux](https://github.com/yuhui-zh15/CellFlux) |
| Simulation | [OpenMM](https://openmm.org/), [ViennaRNA](https://www.tbi.univie.ac.at/RNA/), [PhysiCell](https://github.com/MathCancer/PhysiCell), [HemoCell](https://github.com/UvaCsl/HemoCell), SciPy |
| Reference data | [UniProt](https://www.uniprot.org/), [AlphaFold DB](https://alphafold.ebi.ac.uk/), [RCSB PDB](https://www.rcsb.org/), [DepMap](https://depmap.org/), [OpenOrganelle](https://openorganelle.janelia.org/), [CELLxGENE](https://cellxgene.cziscience.com/) |
| Scientific adapter | Original FOLD Python code talking to an installed [UCSF ChimeraX](https://www.rbvi.ucsf.edu/chimerax/) |

FOLD STUDIO's interface, project handling, service bridge and workflow code are
application-specific code written with AI assistance. The upstream engines above
provide their own implementations; this project does not reimplement or retrain
them.

## Licence

App code is MIT ([LICENSE](LICENSE)). Third-party libraries, models and datasets
keep their own terms, including research-only and non-commercial ones; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [ASSETS.md](ASSETS.md).
ChimeraX is not included, and a licence to run it does not allow redistributing
it.
