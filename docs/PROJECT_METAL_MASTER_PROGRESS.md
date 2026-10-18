# Project Metal — persistent master completion tracker

Full specification remains the assignment. Milestones are recoverable checkpoints,
not completion conditions. Branch: `project-metal/apple-silicon-engine`. Verified
starting point: `53423a4`. Original Fold Studio source, release ZIPs, molecular
viewer and research data remain preserved. Last update: 18 October 2026.

Status vocabulary: NOT STARTED / IN DEVELOPMENT / IMPLEMENTED / TESTED /
SCIENTIFICALLY VALIDATED / BLOCKED / COMPLETE. Tests do not establish scientific
validity. No top-level platform requirement is marked COMPLETE.

## Acceptance inventory

| Requirement | Status | Implementing sources / evidence | Dependencies, limitations and remaining acceptance |
|---|---|---|---|
| Existing app and visual baseline preservation | TESTED | Baseline `d121311`; existing CSS/viewer unchanged; M1 native screenshot; 4.3 source untouched | Continue visual/interaction regression checks for additions |
| Unified molecular-data model | IN DEVELOPMENT | `scientific/fold_engine.py`, `intelligence.py`, `scene_bridge.py`; shared structure/checksum/residue IDs | Extend topology, assemblies, ligands, solvent, trajectories without discarding metadata |
| Scientific engine registry | IMPLEMENTED | `fold_engine.py`; worker/Rust IPC allowlists | Versioned typed capability schemas, capability validation |
| Shared viewer/sequence/command state | IN DEVELOPMENT | Existing native scene bridge, console, viewer selection and Molecular Intelligence | Formal invalidation, shared edits and undo/redo across all adapters |
| Computational jobs and persistence | TESTED | `worker.py`, `mpnn.py`, `intelligence.py`; SQLite jobs; `test_mpnn.py` | Common priority/resource/cancel/recovery contract for every engine |
| Model and dependency management | IN DEVELOPMENT | M1 source checksum manifest, M2 checkpoint digests; `scripts/fetch-af2-parameter.py` | Managed UI downloads, independent checksums where provided, recovery/unload/storage |
| Hardware/GPU resources | IN DEVELOPMENT | `fold_compute.py`; actual MPS diagnostic/attention evidence | Memory-aware scheduling, GPU allocation, peak-memory/throughput benchmarks |
| BindCraft2 pinned source/dependency inventory | TESTED | `vendor/bindcraft2-source.json`, `reports/bindcraft-audit.json` | Maintain pin and attribution; source presence is not feature parity |
| Campaign configuration | TESTED | `fold_engine.py`; upstream input checks on hPDL1/ANGPTL3 | Other modalities/constraints, full upstream preflight and live campaign execution |
| AF2 model parameters | TESTED | Bounded official archive member acquisition script | Load authentic checkpoint; record provenance; no synthetic parameters substituted |
| AF2 complete forward and structure module | TESTED | Upstream `bindcraft/af2.py`; CPU execution being investigated | Actual trained-weight inference, reference comparison and artifacts |
| AF2 loss, backpropagation and optimization | IN DEVELOPMENT | Upstream sequence_gradients pathway | Finite-difference/reference checks, optimizer trajectory, model recycling |
| Metal-compatible AF2 execution | BLOCKED | `reports/jax-metal.json`: PJRT API mismatch; compatibility flag then StableHLO error | Alternative PJRT or full mathematically equivalent backend; single attention kernel is insufficient |
| Metal attention | SCIENTIFICALLY VALIDATED | `metal_attention.py`, `reports/metal-attention.json` | Narrow float32 kernel parity only; no full-model validation implied |
| ProteinMPNN fixed-backbone redesign | TESTED | `mpnn.py`, `mpnn_runner.py`, `reports/proteinmpnn-validation.json`, `packaged-mpnn.json` | Full-model exact upstream parity and seed repeatability on two cases; CPU; folding/binding not validated |
| ProteinMPNN multistate/ties/residue constraints | NOT STARTED | Upstream retained | Add adapter configuration and reference tests |
| Genuine local BindCraft2 trajectory | IN DEVELOPMENT | `bindcraft_cpu.py`, `bindcraft_runner.py`; actual full-parameter CPU campaign running | Technical fragment optimization reached anneal and was correctly rejected by upstream i_pTM gate; default-filter full-size campaign acceptance still running. Metal remains blocked |
| Binder and linear peptide generation | IN DEVELOPMENT | Configuration/import works | End-to-end actual generation, filtering, comparison, provenance |
| Cyclic peptide, VHH, ARP, scFv, Fab and scaffold workflows | NOT STARTED | All upstream presets inventoried in M1 | Adapter, native computation, modality-specific validation |
| Multitarget, detarget, fold switch, induced-fit and oligomers | NOT STARTED | Upstream source/presets retained | Constraint fidelity, actual generation and reference acceptance |
| Candidate import and reproducibility | TESTED | Ranked importer, raw CSV/metadata and coordinate checksums; M2 sequence records | Folding validation and automatic full-trajectory import |
| ChimeraX command architecture | IN DEVELOPMENT | Existing `observatory.py`, native inventory, console, capability audit | Exhaustive versioned command matrix and measured expansion; no universal claim |
| Coloring, selection, styles, surfaces and camera | IMPLEMENTED | Existing native scene/command/viewer adapters | Expand operation-equivalence and supported-argument tests |
| Measurements, contacts, H bonds, alignment, RMSD | TESTED | Existing MI/ChimeraX implementations, 4.3 tests and reference checks | Broaden chemistry and command-specific scientific evidence |
| Volumes, maps, trajectories, advanced editing | NOT STARTED | Some existing native commands may register | Verified unified state/render support and complete workflow tests |
| Molecular Architect full workflow | IN DEVELOPMENT | Existing sequence editor plus campaign/redesign dialog | Visual hotspot capture, actual generation, folding validation, candidate comparison |
| Protein Intelligence / X-Ray / interface explorer | IN DEVELOPMENT | Existing `MolecularIntelligence.tsx`, `intelligence.py` | Clearer evidence/UI, expanded chemistry and mutation analysis |
| Structural Comparison Observatory | IMPLEMENTED | Existing aligned views, RMSD/contact comparison and confidence | More reference cases, mutation/campaign comparison and transparent ranking |
| Boltz prediction | TESTED | Existing Boltz MPS pipeline and saved outputs | Broader end-to-end model acceptance and managed runtime packaging |
| BoltzGen / RFdiffusion / additional generators | NOT STARTED | No new adapter | Source/license/runtime audit followed by real computation |
| Drug Design Studio / RDKit / ligand preparation | NOT STARTED | RDKit exists in separate Boltz environment only | Shared ligand model, validated preparation/editing and exports |
| AutoDock Vina / GNINA / screening / pharmacophores | NOT STARTED | No integrated adapter | Native engines, reference cases and scientifically justified scoring |
| Dynamics Lab / OpenMM | NOT STARTED | No integrated simulation workflow | Force-field preparation, actual dynamics, trajectory state and RMSD/RMSF validation |
| Free-energy / OpenFE | NOT STARTED | No integrated adapter | Validated preparation/sampling/uncertainty and reproducibility |
| Quantum chemistry / Psi4 | NOT STARTED | No integrated adapter | Feasible macOS engine, scientifically explicit methods and numerical checks |
| Fold Intelligence assistant | IN DEVELOPMENT | Existing deterministic evidence explanations | Real structure-aware tool execution and grounded interpretation; no local LLM installed |
| Research Observatory / project histories | TESTED | Existing SQLite/project ZIPs, raw scientific records | Migrations/snapshots/re-import and unified history across new engines |
| Publication figures | IMPLEMENTED | Existing PNG/SVG/PDF reports, native scene save | Publication QA, legends and reusable layouts |
| Molecular Cinema / video | IN DEVELOPMENT | Existing pose crossfade of fixed structures | Camera keyframes, timeline, real video export; never label illustrative animation as dynamics |
| Biological databases | IMPLEMENTED | Existing UniProt/PDB/AlphaFold DB retrieval | Domains/variants/interactions/Foldseek, retrieval provenance and validation |
| Self-contained macOS runtime | IN DEVELOPMENT | Relocated CPython/JAX runtime imports and gradients pass; native app now being built with runtime and two AF2 checkpoints | Relocatable Python/native libraries, permitted ChimeraX embedding, first-run weight management |
| Signing, relocatability and data integrity | IN DEVELOPMENT | Existing signed builds and packaged IPC tests | Full standalone relocated launch, runtime dylibs and upgrade/data acceptance |
| ANGPTL3–ANGPTL8–APOA5 complete research workflow | IN DEVELOPMENT | Existing MI analysis and genuine packaged ANGPTL3 ProteinMPNN redesign | Actual binder trajectory, generated complex, comparative analysis and report |

## Current execution loop

1. Acquire only the required authentic AF2 parameter member, preserving provider
   ETag and local SHA-256; avoid downloading/extracting a 5.6 GB archive with only
   ~10 GiB disk free.
2. Exercise the unchanged full AF2 CPU forward/gradient pathway on a tiny explicit
   technical input. This is a CPU feasibility/reference route, not a Metal port.
3. Use evidence to enable actual supported inference/optimization paths, then
   continue the next actionable requirement. Do not stop because one check passes.
4. Maintain recoverable commits and update this tracker. On context recovery,
   inspect active processes/reports first; do not restart completed long work.

## Continuous execution checkpoint — after M2

- Official trained `model_1_ptm` and `model_1_multimer_v3` parameters acquired by
  exact HTTP ranges. ~373 MB each; checksums and archive ETag recorded. No random
  model weights substitute for these parameters. Official AF2 parameter licensing
  source: https://github.com/google-deepmind/alphafold#model-parameters-license .
- `scripts/validate-af2-full.py` ran the unchanged full monomer AF2 forward and
  sequence backpropagation on CPU, 12-residue technical input, zero recycles:
  ~10.09 s / ~1.91 GB peak RSS. `reports/af2-full-cpu.json` and CIF/gradient NPZ.
  Finite values establish execution, not independent scientific validation.
  Upstream sequence-feature processing includes straight-through estimators;
  ordinary finite differences must not be misrepresented as validation of those
  surrogate gradients.
- Actual `run_trajectory` for a 12-residue target fragment / 12-residue binder
  ran screen and refine, then was rejected at anneal by upstream i_pTM. Its
  predicted complex is retained under `../validation/af2-technical-trajectory`.
  This is rejected technical output, not an accepted/validated binder.
- A real default-filter, 60-residue binder / full 115-residue hPDL1 campaign is
  running via the shared jobs API, explicit `experimental-cpu-single-model`
  profile. Job `8a87bd72-ee6d-4289-89d0-5cb3f38320b9`, root
  `../validation/bindcraft-native-cpu`. Inspect `execution.log`, job SQLite row
  and `reports/bindcraft-live-cpu-job.json` before taking any recovery action.
  One trajectory attempt; original scientific filters and default stage budgets.
  No accepted-design result yet. Do not rerun or interrupt merely on compaction.
- `prepare-scientific-runtime.py` assembled CPython/JAX from the tested isolated
  environment with licenses/dist-info retained. A moved-directory, isolated-mode
  import/gradient check passed (`reports/runtime-relocation.json`). Known stale
  absolute man/pkgconfig links were converted to verified internal sibling links.
- Native source now selects the bundled Python runtime; ProteinMPNN discovers
  it automatically. CPU campaigns discover bundled parameters. Current build
  includes these resources. ChimeraX and Boltz runtimes remain separate; no
  claim that the entire platform is standalone.

Next loop: verify the runtime-containing app after relocation with all development
Python/runtime environment variables removed; run a real packaged ProteinMPNN
job; inspect the running full BindCraft campaign; extend scientific validation
and recoverable job/command coverage. Continue without treating this checkpoint
as the end of the assignment.

### Runtime and launch correctness updates

- The relocated app completed a genuine 460-residue ANGPTL3 ProteinMPNN job
  using its own bundled interpreter and dependencies, with all development
  runtime environment variables removed. Both bundled AF2 parameter hashes pass.
  `reports/embedded-runtime-acceptance.json` records signature verification after
  inference. CPython/JAX/ProteinMPNN are now self-contained for this tested path;
  ChimeraX/Boltz and all remaining engines are not yet bundled.
- The first relocation check exposed bytecode writes from a background worker
  before Python service initialization. `worker.py` now launches every such worker
  with `-B` and `PYTHONDONTWRITEBYTECODE=1`; a regression test covers these flags.
- Explicit CPU campaign launch checks the two checkpoint SHA-256 pins against
  `scientific/af2-parameters.json` and rechecks upstream source integrity. Other
  parameter versions are not silently accepted under the tested profile.
- 154 Python / 64 frontend tests currently pass; one existing private rotation
  fixture is skipped. The CPU launch guard tests cover explicit profile selection,
  absent parameters, invalid options and refusal to rerun completed jobs.
