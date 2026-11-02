# Scientific Engine Registry

Status as of 30 October 2026, using the directive's vocabulary. Nothing here is rated above what was actually run.

## Running inside Fold Studio

| Engine | Version / source | Purpose | Licence | Status | Evidence of status |
|---|---|---|---|---|---|
| ViennaRNA | 2.7.2, pinned cp312 arm64 wheel, SHA-256 checked | MFE, partition function, subopt enumeration, findpath | ViennaRNA licence, see THIRD_PARTY_NOTICES | Integrated, numerically tested | RNA lab tests; Demo 10 partition-function identity |
| NumPy Brownian dynamics (in-house) | `cell_physics_bd.py` | Free and bounded diffusion, Doi binding | Project | Integrated, numerically tested | MSD and equilibrium-occupancy benchmarks |
| RDME next-subvolume method (in-house, Elf & Ehrenberg 2004) | `spatial_rdme.py` | Spatial stochastic reaction–diffusion on voxel meshes | Project | Integrated, scientifically benchmarked | Demo 11: 5 benchmarks (lattice MSD, exact CME, analytical gradient with mesh refinement, finite-volume agreement, conservation) |
| Finite-volume reaction–diffusion (in-house) | `spatial_rdme.py` | Deterministic mean and steady state for first-order networks | Project | Integrated, numerically tested | Demo 11 convergence check |
| Exact RNA kinetics (in-house, Kinfold/treekin model) | `rna_kinetics.py` | Master equation on the full secondary-structure landscape | Project | Integrated, scientifically benchmarked | Demo 10: 6 checks including an independent SSA |
| TASEP (in-house, exact Gillespie) | `rna_lab_translate.py` | Ribosome traffic | Project | Integrated, numerically tested | Mean-field and maximal-current checks |
| SBML / SciPy LSODA | `mechanistic_*.py` | Biochemical ODE networks | SciPy BSD | Integrated, numerically tested | BIOMD0000000010 tests |
| Axisymmetric advection–diffusion | `blood_transport.py` | Vessel transport | Project | Integrated, numerically tested | Taylor–Aris dispersion, mass balance |
| Multiscale kernel | `multiscale_*.py` | Units, contracts, one-way coupling, trace, uncertainty | Project | Integrated, numerically tested | Demo 5 and Demo 8 checks |
| OpenMM | 8.6.1, bundled `runtime-openmm` (CPU) | Molecular dynamics | MIT/LGPL | Integrated, scientifically benchmarked | Demo 12: CPU vs Reference forces, NVE conservation, thermostat, reproducibility |

## Evaluated, not integrated

| Engine | Finding | Status | What it would take |
|---|---|---|---|
| Smoldyn 2.76 | Licence LGPL-3.0+. On PyPI, the only macOS binary (inside the `py3-none-any` wheel) is built for CPython 3.14 arm64; the bundled runtime is 3.12. No CMake for a source build. | Available, unsupported in the bundled runtime | A separate CPython 3.14 runtime (like `runtime-metal`), or a CMake source build; then cross-check against Demo 11 |
| ReaDDy 2 | Distributed through conda only; no 3.12 arm64 wheel was found | Research candidate | A conda-based side runtime |
| Virtual Cell 8 / SpringSaLaD | Java desktop and server application | Research candidate | Model exchange via SBML/VCML, not embedding |
| SMART / FEniCS | Needs DOLFINx (PETSc, MPI) | Research candidate | A conda side runtime |
| Lattice Microbes / 4DWCM | CUDA GPU required | Blocked by hardware (no NVIDIA GPU on this Mac) | Remote GPU, or import of published trajectories |
| Barriers / treekin | C tools; not bundled | Research candidate | Needed only for RNAs beyond about 24 nt; Demo 10 solves the same model exactly for short RNAs |
| RhoFold+, Boltz-2 (RNA) | GPU models | Remote recipes written (Cloud GPU Tasks); comparison with 1EHZ implemented locally; not yet executed on a server | First approved run on your Modal account |
| RNAbpFlow, DRfold, NuFold, RoseTTAFoldNA | GPU models; RNAbpFlow is GPL | Research candidate; runnable through the Custom recipe | — |
| HemoCell | Licence AGPL-3.0; C++ with MPI and HDF5 | Remote recipe written (Cloud GPU Tasks, 16-core Modal sandbox); not yet executed | First approved run, then the HDF5 playback adapter (Demo 7) |
| SimVascular, OpenFOAM, CRIMSON | Large C++ toolchains | Research candidate | File-level interoperability (VTK) |
| PK-Sim / MoBi | .NET desktop | Research candidate | Import of PKML/SBML exports |
| BioNetGen | Perl/C++ | Research candidate | Network generation to SBML, then the existing engine |
| Simularium, Molecular Nodes, cellPACK, MolViewStories | Visualization tools | Research candidate | Simularium trajectory export is the cheapest first step |
