# Blood & Circulation Laboratory — external engine evaluation

30 October 2026. **Evaluation only: nothing was downloaded, installed or run.** The question is which external blood-flow engines could extend the in-app Demo 6 solver (`scientific/blood_transport.py`, see `docs/LIVING_BIOLOGY_LAB.md` §7), what each would add, and what it would cost Fold Studio to bundle or bridge it on macOS arm64.

## What Demo 6 already covers (and does not)

Demo 6 solves dilute-tracer advection–diffusion in **one straight rigid tube of plasma** (hematocrit 0, Newtonian, steady Poiseuille) with a Robin permeable wall, verified to round-off mass balance, Taylor–Aris dispersion (0.04 %), a Bessel-series wall-loss benchmark and second-order grid convergence. It does not model patient geometry, branching networks, pulsatile or turbulent flow, wall compliance, non-Newtonian rheology or red cells. Each engine below would fill some of those gaps.

## Summary

| Engine | Licence (verified) | macOS arm64 | Adds | Main cost |
|---|---|---|---|---|
| **SimVascular** (+ svMultiPhysics solver) | BSD (svModel/svMesh/svPre/svPost), modified BSD (solver); third-party TetGen AGPL-3.0, MeshSim commercial | **Yes**: official macOS ARM installer since the September 2025 release; svMultiPhysics builds with CMake on macOS | Image → segmentation → mesh → 3-D Navier–Stokes, FSI (deformable wall), scalar transport, RCR/Windkessel outlets | Large GUI app (Qt/VTK/ITK); MPI solver; no Python-level API beyond scripting. Bridge by file exchange, not bundling. Watch the TetGen AGPL dependency if redistributed |
| **HemoCell** (on Palabos) | AGPL-3.0-or-later (repo `LICENSE`) | **Not documented**; builds from C++ source with MPI and HDF5; the quick-start page with platform requirements returned 404 | Cell-resolved blood: deformable red cells and platelets, so hematocrit, cell-free layer, Fåhræus effects, margination | AGPL copyleft covers anything linked into the app; HPC-scale cost (hours on many cores for µL-scale volumes); would need a separate process, never a linked library |
| **CRIMSON** | GUI AGPL-3.0; Flowsolver GPL-3.0 | **No**: GUI binaries for Windows 10; Flowsolver Windows/Linux. A source build needs up to ~55 GB of disk | Patient-specific 3-D haemodynamics with 0-D/1-D boundary networks (heart, Windkessel), deformable wall | No macOS route; it would have to run in a Linux VM or the cloud workers; copyleft licences |
| **OpenFOAM** (Foundation, openfoam.org) | GPL-3.0 | **Partly**: the Foundation's macOS route runs Ubuntu arm64 packages inside Multipass; a community app (openfoam-app) ships native Apple-silicon binaries built from official source; v2412 has been built natively with Homebrew dependencies | General finite-volume CFD: arbitrary 3-D geometry, pulsatile/turbulent flow, non-Newtonian viscosity models, passive scalars, multiphase Euler–Euler blood models | Very large toolchain; mesh generation and case setup expertise; runs as an external process (VM or native app), output exchanged as files |
| **Palabos** | AGPL-3.0 (`COPYING`) | Builds from C++ source with CMake/MPI on Unix-like systems; no official macOS package | Lattice-Boltzmann CFD in complex/porous geometry; the base HemoCell is built on | Same AGPL concern as HemoCell; LBM needs care to reach the low Mach/low Reynolds regime of microvessels |

## Per-engine notes

### SimVascular / svMultiPhysics
- **Would add:** real vessel geometry from images, 3-D velocity fields (Womersley pulsatile, stenoses, bifurcations), wall deformation, and an advection–diffusion equation on that field. The natural coupling is: SimVascular produces a velocity field → Fold Studio imports it (VTU) → a transport run with the same validation discipline as Demo 6.
- **Cost:** a separate install the user chooses; Fold Studio would read results, not bundle the app. The svMultiPhysics solver alone is the smallest piece worth evaluating for a headless bridge. Verification: reproduce Poiseuille and Womersley analytical solutions before accepting any vessel result.
- **Risk:** licence components differ; anything redistributed must respect TetGen's AGPL and exclude MeshSim.

### HemoCell
- **Would add:** the one thing no continuum model gives — explicit red cells, hence hematocrit-dependent viscosity, the cell-free layer, plasma skimming and platelet margination. This is what would be needed before Fold Studio could say anything about whole blood rather than plasma.
- **Cost:** AGPL means it must stay a separate executable (no linking into the Tauri app). Compute cost is HPC-scale; a small channel at physiological hematocrit is a cloud job, not a laptop job. macOS support is undocumented, so the realistic route is the existing cloud worker (Linux).
- **Validation needed:** apparent viscosity vs tube diameter (Fåhræus–Lindqvist; Pries et al. 1992 fits) before use.

### CRIMSON
- **Would add:** closed-loop 0-D/1-D/3-D models (heart, Windkessel outflows) that put a modelled vessel in a systemic context.
- **Cost:** Windows-centred; no macOS path. Only usable through a Linux cloud worker for the Flowsolver, and its GUI capabilities overlap SimVascular. **Lowest priority.**

### OpenFOAM
- **Would add:** the broadest CFD capability (any geometry, transient, non-Newtonian models such as Carreau–Yasuda, scalar transport, Euler–Euler two-phase blood).
- **Cost:** heavy setup and meshing; GPL-3.0 copyleft if redistributed, so call it as an external program. On Apple silicon the realistic routes are the community native app or a Multipass VM; both are user installs.

### Palabos
- **Would add:** LBM flows in complex geometry (porous/tissue-like media) and is the substrate of HemoCell.
- **Cost:** AGPL-3.0; source build only. Alone it adds little over OpenFOAM for Fold Studio; its value is as HemoCell's base.

## Recommendation

1. **Keep Demo 6 as the in-app, verified core.** It is fast (< 1 s), dependency-free beyond NumPy/SciPy and fully validated.
2. **Next external step: svMultiPhysics as an optional external solver** (permissive licence, native macOS ARM), starting with Womersley pulsatile flow in a straight tube as the acceptance test, then importing its velocity field into a 3-D transport run.
3. **Whole blood (hematocrit > 0): HemoCell on the Linux cloud worker**, kept as a separate AGPL process. Until then every Fold Studio blood result must say "plasma only".
4. **OpenFOAM** only if non-Newtonian or turbulent cases are needed that svMultiPhysics does not cover. **CRIMSON**: not pursued (no macOS path, overlaps SimVascular).

No engine above makes a modelled vessel equivalent to validated human circulation. That still requires comparison with measured (category A) data for the specific situation.

## Sources

- SimVascular licences and components: https://simvascular.github.io ; macOS ARM installer announcement: https://lists.simtk.org/pipermail/simvascular-news/2025-September/000042.html ; svMultiPhysics: https://github.com/SimVascular/svMultiPhysics
- HemoCell licence: https://raw.githubusercontent.com/UvaCsl/HemoCell/master/LICENSE ; repository: https://github.com/UvaCsl/HemoCell ; user guide: https://hemocell.eu/user_guide
- CRIMSON: https://pmc.ncbi.nlm.nih.gov/articles/PMC8148362 (licences, platforms) ; https://github.com/carthurs/CRIMSONGUI ; https://github.com/carthurs/CRIMSONFlowsolver
- OpenFOAM on macOS: https://openfoam.org/download/14-macos/ ; community Apple-silicon app: https://github.com/gerlero/openfoam-app
- Palabos licence: https://gitlab.com/unigespc/palabos/-/blob/master/COPYING
