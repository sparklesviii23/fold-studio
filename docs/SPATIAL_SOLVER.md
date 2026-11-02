# Demo 11 — Spatial Reaction–Diffusion Solver

30 October 2026. Analyse › Multiscale Experiments › Demo 11 · Spatial gradient.

## Method

| Module | Role |
|---|---|
| `scientific/spatial_rdme.py` | Voxel meshes (sphere cell with optional nucleus, box), reaction–diffusion master equation (RDME) simulated exactly with the **next-subvolume method** (Elf & Ehrenberg 2004, doi:10.1049/sb:20045021) — the algorithm behind MesoRD and URDME. First- and second-order reactions per voxel, diffusion jumps D/h², nuclear envelope as a series resistance 1/(h²/D + h/P). The same voxel generator gives the deterministic finite-volume system dn/dt = M n and its steady state. |
| `scientific/spatial_demos.py` | Demo 11 scenario, parameters with provenance, the five benchmarks. |
| `scientific/spatial.py`, `spatial_actions.py` | RPC actions `spatial_catalog`, `spatial_run`, `spatial_runs`, `spatial_record`; every run is saved under `<library>/spatial/runs`. |
| `src/components/multiscale/SpatialLab.tsx` | Workspace tab: outputs, radial profile (finite volume against RDME), central-slice maps, phosphatase sweep, RDME time course, equations, editable hypothetical parameters, assumptions, sources, benchmarks and saved runs. |

### Why not Smoldyn

Smoldyn 2.76 (LGPL-3.0-or-later) on PyPI ships a Linux x86-64 wheel and a `py3-none-any` wheel. Inspection of the latter, without executing it, showed that it contains `_smoldyn.cpython-314-darwin.so` (an arm64 build for CPython 3.14). The bundled scientific runtime is CPython 3.12, so the module cannot load there. The machine has no CMake for a source build. Adding Smoldyn therefore needs a separate CPython 3.14 runtime or a source build, which is a packaging decision left to the user. The RDME/NSM implemented here is an established method in its own right, not a stand-in.

## Biology (Parameterised hypothesis)

The model structure comes from Brown & Kholodenko 1999 (doi:10.1016/S0014-5793(99)01058-3) and Kholodenko 2006 (doi:10.1038/nrm1838):
- a membrane kinase phosphorylates a cytosolic protein (U → P, surface rate constant k_k);
- a phosphatase reverses it everywhere (P → U, k_p);
- the phospho-form decays over L = √(D/k_p).

Geometry:
- spherical cell R = 5 µm with a concentric nucleus of 2.5 µm;
- envelope permeability P_env;
- voxel h = 0.5 µm: 4,169 voxels, of which 978 are membrane voxels and 515 nuclear.

**All rate and transport values are hypothetical.** The papers supply equations, not numbers.

Defaults (D = 1 µm²/s, k_p = 0.25 /s, k_k = 0.3 µm/s, P_env = 0.5 µm/s, 1,000 molecules), seed 1:

| Output | Value |
|---|---|
| Gradient length √(D/k_p) | 2 µm |
| Phosphorylated fraction at the membrane | 0.482 |
| Phosphorylated fraction in the nucleus | 0.205 (RDME time average 0.203) |
| Nucleus ÷ membrane | 0.425 |

Sweeping k_p from 0.02 to 4 /s moves nucleus ÷ membrane from about 0.9 to under 0.01. This is the qualitative claim of the source papers, reproduced on this mesh; it is not a fit to any measured gradient.

## Benchmarks (numerical correctness, all pass)

| # | Benchmark | Result |
|---|---|---|
| 1 | Lattice diffusion: 2,000 molecules released from one voxel, MSD at t = 1 s against 6Dt | 5.85 vs 6.00 µm², z = −1.4 |
| 2 | A + B ⇌ C in one voxel against the exact stationary distribution of the chemical master equation | mean 2.722 vs 2.725, total-variation distance 0.013 |
| 3 | Finite volume against the analytical solution p(r) = A·sinh(r/L)/r (no nucleus) | relative L2 error 9.2 % → 4.6 % → 3.0 % for h = 1 → 0.5 → 0.25 µm (observed order 0.64, limited by the staircase boundary) |
| 4 | RDME time average against the finite-volume steady state on the same mesh (exact for first-order networks): 16 batches × 5 s after 30 s burn-in, 10 radial shells | largest \|t\| = 2.49 (df 15), Bonferroni p = 0.25 |
| 5 | Molecule conservation (RDME integer counts; finite-volume sum) | exact |

A run takes about 8 s and about 2.4 million events on Apple silicon.

## Limitations

- The staircase boundary limits convergence to below first order. Membrane voxels share the true sphere area, but their positions are still the staircase.
- Bimolecular RDME reactions lose meaning when voxels approach the reaction radius (Isaacson 2009, doi:10.1137/070705039). The scenario is first order, and the bimolecular benchmark uses a single voxel.
- The deterministic reference covers first-order networks only.
- Only spherical geometry is provided. There are no organelles, crowding or active transport, and no coupling to the Demo 8 chain.

## Tests

`tests/test_spatial.py` (10 tests):
- generator conservation;
- envelope rates;
- membrane area;
- seeded reproducibility;
- the three analytical/exact benchmarks;
- the full scenario with save/reopen and JSON-plain output;
- the monotone phosphatase effect;
- worker routing without NumPy/SciPy.
