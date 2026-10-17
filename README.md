# FOLD STUDIO

FOLD STUDIO is an experimental macOS application for exploring protein structures, organizing molecular research and working with peptide-design and prediction workflows. It combines a custom React/TypeScript interface with a Rust/Tauri desktop shell, a Python scientific service, and interactive molecular graphics from Mol*. A separately installed UCSF ChimeraX runtime supplies compatible scientific commands and calculations through an original FOLD adapter, without exposing its original Qt interface.

Version: 4.3.0. Primary target: Apple Silicon macOS.

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

Install Node.js/pnpm, Rust and the macOS/Xcode command-line build tools. Install your own compatible, licensed ChimeraX 1.12 application to use the scientific laboratory. Boltz inference is optional and requires a separate environment and model downloads; the normal Python service uses the system Python standard library.

```sh
pnpm install --frozen-lockfile
pnpm test
python3 -B -m unittest discover -s tests -v
pnpm desktop
```

For a production macOS application:

```sh
pnpm bundle
```

Output: `src-tauri/target/release/bundle/macos/FOLD STUDIO.app`. The build script signs locally ad hoc; this is not a notarized Developer ID release. Other platforms have not been validated.

## Repository layout

- `src/`: React interface, Mol* viewer, scientific panels and molecular construction tools.
- `src-tauri/`: Rust shell, native capabilities, icons and package configuration.
- `scientific/`: Python service, ChimeraX adapters, peptide/graph logic and public reference chemistry.
- `fixtures/`: attributed public protein/reference records and an AlphaFold reference structure.
- `tests/`, `scripts/`: service tests, validation and build utilities.

## Current limitations

This is research software under active development. Complete ChimeraX feature parity is not achieved: some Qt-only tools, clipping effects, specialist graphics and extension interfaces still need custom adapters. Native surface picking, specialist imaging and exhaustive hardware/extension acceptance remain incomplete. BindCraft execution and PS5 compute workers are plans, not completed engines. Prediction confidence and computed geometry do not establish biological binding or experimental accuracy.

The 4.2.2 renderer update corrects full-scene camera depth bounds and separates status badges from panel tabs. Automated camera-depth sweeps passed; full interactive GPU rotation acceptance remains incomplete. The private ANGPTL3/8 test fixture and private acceptance reports are omitted from this public package, so its optional rotation-fixture test skips unless you supply your own authorized file. Integration-validation scripts require their documented external fixtures/runtime.

## Privacy and included files

This archive contains application source, dependency lockfiles, build configuration, tests, icons and attributed public reference data. It excludes private research structures/results/screenshots, local databases, credentials, model weights, application binaries, dependency folders, build caches and Git history. Runtime-generated project data belongs outside the repository. Historical local release notes were replaced with this current introduction.

## Credits and licensing

FOLD application code includes an MIT license. Third-party libraries, reference data, models and external programs retain their own terms; preserve `LICENSE` and `THIRD_PARTY_NOTICES.md`. ChimeraX executables, its Qt application and upstream scientific implementation are not included. A user's license to run ChimeraX does not itself grant permission to redistribute that runtime. See the installed runtime's license and upstream terms before distributing any external components.
