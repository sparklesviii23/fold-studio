# FOLD STUDIO

FOLD STUDIO is an experimental macOS application for exploring protein structures, organizing molecular research and working with peptide-design and prediction workflows. It combines a custom React/TypeScript interface with a Rust/Tauri desktop shell, a Python scientific service, and interactive molecular graphics from Mol*. A separately installed UCSF ChimeraX runtime supplies compatible scientific commands and calculations through an original FOLD adapter, without exposing its original Qt interface.

Version: 4.3.0. Primary target: Apple Silicon macOS.

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

Eleven modality adapters are connected at explicitly bounded experimental scope.
**Fab is unavailable and explicitly deferred.** Larger dimensions, individual
property-specific workflows and unrestricted CLI options are not all validated.
SSD checkpointing remains a separate experiment and is not enabled in the app.
See [the measured feature inventory](docs/BINDCRAFT_FEATURE_PARITY.json) and
[the implementation tracker](docs/PROJECT_METAL_MASTER_PROGRESS.md). Historical
[M1](docs/PROJECT_METAL_M1.md)/[M2](docs/PROJECT_METAL_M2.md) reports describe earlier
checkpoints. The full port is not declared complete.

## How it is made

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

## Features

- Protein structure import from PDB and mmCIF, a saved research library, editable names/notes, and recoverable removal.
- Interactive molecular viewing, chain and residue colours, selections, native surfaces and measurements.
- A native-command console and a separate trusted scientific Python editor.
- Research projects, sequence and peptide workspaces, prediction handoffs and experimental molecular construction tools.
- Genuine ChimeraX session saving and scientific provenance where supported.

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
