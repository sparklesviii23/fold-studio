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
| AF2 complete forward and structure module | TESTED | `validate-af2-full.py`; genuine monomer/multimer CPU and Metal forward reports | Narrow 12/24-residue cases; full-size campaign acceptance running |
| AF2 loss, backpropagation and optimization | TESTED | `af2_native.py`; full-model monomer/multimer gradients, recycling and four real optimizer stages compared | Narrow float32 comparisons; upstream surrogate gradients require reference comparisons, not naive finite differences; full campaign acceptance pending |
| Metal-compatible AF2 execution | IN DEVELOPMENT | MetalJAX 0.11.9, `af2_native.py`, monomer/multimer/optimizer comparison reports | Float32 narrow comparisons pass; original Apple plugin incompatible; full-size 6 GiB campaign under validation, no whole-engine parity claim |
| Metal attention | SCIENTIFICALLY VALIDATED | `metal_attention.py`, `reports/metal-attention.json` | Narrow float32 kernel parity only; no full-model validation implied |
| ProteinMPNN fixed-backbone redesign | TESTED | `mpnn.py`, `mpnn_runner.py`, `reports/proteinmpnn-validation.json`, `packaged-mpnn.json` | Full-model exact upstream parity and seed repeatability on two cases; CPU; folding/binding not validated |
| ProteinMPNN multistate/ties/residue constraints | NOT STARTED | Upstream retained | Add adapter configuration and reference tests |
| Genuine local BindCraft2 trajectory | IN DEVELOPMENT | `bindcraft_cpu.py`, `bindcraft_runner.py`; actual full-parameter CPU campaign running | Technical fragment optimization reached anneal and was correctly rejected by upstream i_pTM gate; default-filter full-size CPU and float32 Metal campaigns running; no accepted binder yet |
| Binder and linear peptide generation | IN DEVELOPMENT | Configuration/import works | End-to-end actual generation, filtering, comparison, provenance |
| Cyclic peptide, VHH, ARP, scFv, Fab and scaffold workflows | IN DEVELOPMENT | Cyclic original preset preparation and technical optimizer execution; other presets inventoried | Cyclic closure/reference checks in progress; VHH/scaffold adapters and end-to-end scientific validation remain |
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
| Self-contained macOS runtime | IN DEVELOPMENT | Relocated CPython/JAX runtime imports and gradients pass; native app now being built with CPU runtime and AF2 checkpoints; Metal runtime staged with licenses | Relocatable Python/native libraries, permitted ChimeraX embedding, first-run weight management |
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

### Native-window acceptance

The app was launched with `FOLD_PYTHON`, `FOLD_BINDCRAFT_PYTHON`,
`FOLD_AF2_PARAMETERS`, `PYTHONPATH` and `PYTHONHOME` removed, using its bundled
interpreter selected by Rust. Native UI actions selected the bundled ANGPTL3
reference and chain A and submitted real ProteinMPNN redesign. The UI showed
completed and two saved sequences (~3.12 s model time under concurrent CPU load).
Signature verification still passed after this native UI calculation. Original
interface/navigation remain intact. Validation root: `../validation/native-embedded-library`.
Polling now refreshes the displayed job receipt as well as the shared job list,
so a submission's queued state cannot contradict its completed live state.

### Scoped command compatibility evidence

The live ChimeraX regression suite passed all 25 checks when driven by the
bundled Python runtime. `reports/chimerax-current-acceptance.json` retains
assertions; `scripts/update-command-evidence.py` promotes only named passing
checks into `scientific/validation-evidence-current.json`. The capability
audit consumes this scoped evidence. `docs/CHIMERAX_COMMAND_COMPATIBILITY.csv`
accounts for all 591 pinned commands, with ten narrowly tested command entries
and two numerical-output checks (distance and Matchmaker). Registration alone
is NOT VALIDATED; whole-command argument coverage and complete rendering/UI
parity remain unverified. This is preserved upstream command execution, not a
superficial alternative parser.

### Scientific progress reporting and runtime provenance

CPU campaign progress now derives trajectory number, accepted count at trajectory
start and last explicitly emitted stage outcome from upstream log events. No
percentage or current iteration is invented while the upstream stage is silent.
The live job receipt and list share the same observed state. Three parser tests
cover empty logs, actual outcomes and invalidating a previous trajectory's stage.
Campaign runner startup records actual Python/JAX/JAXlib, architecture/macOS,
device and execution-settings hash in the job directory. The already-running
acceptance predates this added startup artifact; do not claim it produced one.

### New Metal backend investigation (not promoted to production)

A different Apache-2.0 backend, `metaljax==0.11.9`, targets JAX 0.11.2 / PJRT
0.115. Source inspected at `../upstream/metaljax`, revision recorded in
`reports/metaljax-investigation.json`; isolated environment
`../runtimes/jax-metaljax` leaves CPU and bundled runtimes unchanged. Its actual
Metal forward/gradient vector test passed against analytic derivatives.

Full trained monomer AF2 forward and backpropagation both EXECUTED through the
Metal backend. Default mixed-precision output/gradients failed numerical
comparison. Disabling hidden bfloat16 improved coordinates/confidence strongly
but gradients still failed (float16 input/gradient accumulation is being isolated).
Identical explicit float32 input logits and float32 hidden execution are now
being tested. Preserve all failed comparison reports; no Metal design launch
is enabled based on execution alone. The CPU default-filter hPDL1 campaign is
still running and must not be restarted on context recovery.

### Full-model Metal numerical result

With identical float32 input logits and hidden float32 execution, complete
trained `model_1_ptm` forward and backpropagation on Metal passed the predefined
small-input numerical comparison against CPU: gradient relative L2 error
0.0010897, cosine 0.9999994; confidence max absolute error 1.43e-6; coordinate
RMS error ~0.000170 Å. Evidence: `reports/af2-metaljax-all-f32-comparison.json`.
This is the full model on one 12-residue technical input with zero recycles,
not an isolated attention kernel and not full BindCraft scientific acceptance.
The half-input gradient failures remain retained.

Next validation already running: real `model_1_multimer_v3`, 12-residue source
target fragment + 12-residue designed chain, one recycle, full forward and
backpropagation on CPU then Metal. See current `reports/af2-multimer-f32-*` logs.
The production/bundled app still defaults to the tested CPU profile.

### Float32 Metal execution path and modality correctness

- Full multimer forward/backprop with one recycle passed the predefined CPU/Metal
  comparison: gradient relative L2 0.0008662, cosine 0.9999996. Reports and arrays
  are retained. These are 12 target + 12 designed residues, not large-complex parity.
- Actual screen/refine/anneal/harden optimizer updates passed a separate CPU/Metal
  output comparison. Diagnostic gates were explicitly permissive; no accepted
  research-quality binder is claimed. Report: `bindcraft-trajectory-metal-comparison.json`.
- Full upstream negative ProteinMPNN checkpoint produced identical two sequences
  on the 460-residue ANGPTL3 source on CPU and Metal, score differences <=1.2e-7:
  `reports/mpnn-metal-comparison.json`. No folding/binding validation implied.
- Explicit `experimental-metal-float32-single-model` profile runs the original
  campaign with float32 hidden execution and optimizer initialization, pinned
  JAX/JAXlib 0.11.2 + MetalJAX 0.11.9, actual Metal device requirement, no CPU
  fallback, memory governor enabled. Default CPU profile remains available.
- The 175-residue campaign repeatedly stalled at the 4 GiB process cap. That
  attempt was cancelled and retained as resource evidence, then retried with a
  bounded 6 GiB cap on this 24 GiB Mac. Current GPU job:
  `1e97164b-3ce0-4a2b-bfd6-4b507adf2d6b`, root `../validation/bindcraft-native-metal`.
  CPU job `8a87bd72-ee6d-4289-89d0-5cb3f38320b9` remains running unchanged.
  Inspect both before resuming; do not restart simply because no stage log appeared.
- Peptide/cyclic profiles retain bound multimer validation instead of incorrectly
  forcing the binder monomer path. Official `model_2_multimer_v3` checkpoint
  acquired separately, local SHA pinned, distinct from design model_1_multimer_v3.
  Original cyclic preset and cyclic offset mode now flow through preparation.
- `campaign_progress.py` observes actual upstream recorder callbacks and emits
  stage/update/metric events without changing optimizers or criteria. UI displays
  observed updates, no guessed percentage. Existing running jobs predate this
  observer; no update-level telemetry is claimed for them.
- Separate relocatable MetalJAX runtime staged at `../runtime-build/python-metaljax`
  and passed isolated import/device/gradient probe. App packaging acceptance for
  this second runtime is next. CPU runtime/build remains the previously validated
  baseline until the new app is built and tested.
- Last complete integration suite: 165 Python + 64 frontend passed; three newer
  peptide/progress tests also passed in the targeted 10-test campaign suite.

Next: finish cyclic closure/backend checks, seal and relocate the app containing
both runtimes, execute real GPU calculations from it, inspect full campaigns,
then continue original modality and engine roadmap. No top-level completion.

Cyclic technical execution and CPU/Metal output comparison passed using the
original `direction` cyclic offset mode. Both upstream closure measurements were
1.5984154 Å. Arrays and reports are retained under `reports/cyclic-trajectory-*`.
This diagnostic used permissive gates and is not an accepted research binder.

### Packaged GPU acceptance and full-size results

The native 2.55 GiB build was relocated and automatically discovered its own
MetalJAX interpreter with development overrides removed. Genuine trained AF2
forward/backprop executed from app-owned source/parameters and the app seal
remained valid (`reports/embedded-metal-runtime-acceptance.json`). The CPU
460-residue ProteinMPNN regression also passed after relocation.

A complete diagnostic peptide path then executed inside the relocated app:
original AF2 optimizers → negative ProteinMPNN redesign → held-out model_2
multimer validation → real CIF/metric tables. Confidence/filter gates were
explicitly permissive for technical coverage; all outputs remain quarantined,
zero research records imported. This is not an accepted scientific binder.
Report: `reports/embedded-diagnostic-pipeline-acceptance.json`. A validation
harness bytecode write was discovered and corrected; the repeated final test
verified signatures before and after the calculation.

Both earlier 175-residue default-filter single-model campaigns finished with
zero accepted designs, correctly rejected at anneal (CPU: pLDDT; Metal: i_pTM).
The original CPU mixed-precision and Metal float32 trajectories are different
precision profiles, not paired trajectory-parity evidence. Both outcomes, logs
and summaries are preserved in `reports/bindcraft-fullsize-*-outcome.json`.
A controlled 175-residue, one-recycle float32 full-model comparison separately
passed: gradient relative L2 0.0042348 / cosine 0.9999919; all returned target and
binder coordinate RMS differences <0.001 Å; pLDDT max error 7.2e-7.
`reports/af2-175-metal-comparison.json` records thresholds and arrays.

Seven official AF2 checkpoints are now pinned (5 multimer v3 + 2 pTM) for the
original upstream model pools. Range extraction and local hashes retained; no
provider-published checksum is claimed. `campaign_profile.py` asks the actual
upstream selector for design/held-out pools, preserving original settings and
filters. A tiny real three-design/two-held-out-model diagnostic pipeline completed
on Metal (`reports/diagnostic-ensemble-pipeline-acceptance.json`); this establishes
execution only. CPU float32 profiles and explicit original-ensemble profiles are
now available in source. Full model scientific/modalities parity remains pending.

A real full-ensemble hPDL1 job is running with the original upstream PD-1 interface
hotspots A54,A56,A66,A115, original filters/stage budgets, seed 42, up to three
attempts for one accepted prediction. Job `31e1b01b-1aa9-48e9-94df-b267adbf0a50`,
root `../validation/bindcraft-ensemble-metal`. It uses a bounded experimental
8 GiB process envelope for seven checkpoint residency, 23 GiB system bound and
governor enabled on the 24 GiB host. Observed optimizer callbacks are appearing.
Do not restart during recovery. `reports/bindcraft-live-ensemble-job.json`.

172 Python + 64 frontend tests passed at this integration checkpoint (one existing
private frontend fixture skipped). The last native build precedes ensemble UI/
profiles and four additional checkpoint resources; rebuild/relocated acceptance
for those changes remains necessary. Continue expanding scientific workflows.

### Ensemble app and VHH scaffold continuation

The rebuilt 3.94 GiB app includes all seven pinned model files and both scientific
runtimes. A relocated copy passed CPU redesign, full Metal forward/backprop, and
a complete diagnostic three-design/two-held-out-model peptide pipeline with
signature checks. `reports/embedded-ensemble-pipeline-acceptance.json` retains
actual tables, runtime details and upstream checkpoint identities. Diagnostics
remain quarantined, with no research acceptance or automatic import.

VHH original scaffold execution now passes the CPU/Metal diagnostic optimizer
comparison: 125-residue sampled scaffold plus 12-residue target, all 88 fixed
sequence positions unchanged, resolved-coordinate RMS difference <=0.000324 Å.
`reports/vhh-trajectory-metal-comparison.json` and source arrays retained. The
earlier generic CPU log caption saying 12-residue binder was corrected in report
metadata from unchanged saved arrays; raw execution log remains unchanged.

`fold_engine.py` now prepares VHH with the original preset CDR edit choices,
paratope conformations and framework-retention criteria. Scaffold coordinates are
copied byte-for-byte to an immutable job input with a SHA pin; launch rechecks
that pin. Free binder-length controls are refused for VHH because its scaffold
edit choices determine length. `DesignCampaigns.tsx` exposes this format using
the existing interface controls, without styling/viewer changes.

`campaign_profile.resource_estimate` calls the original upstream maximum padded
residue estimator, including variable scaffold lengths. All launches now enforce
the 256 padded-residue experimental boundary. Real VHH preparation cases measured
192 padded residues for the technical fragment and 288 for full hPDL1; actual
launch of the latter was correctly refused while leaving the campaign prepared.
No silent target crop occurs. Full-target VHH/scaffold quality acceptance and
larger resource profiles remain incomplete. `reports/vhh-preparation-resources.json`.

Four scaffold contract tests cover original presets, byte-identical snapshots,
changed-input refusal and complete project ZIP provenance. Latest integration
suite: 176 Python + 64 frontend tests passed (one existing private fixture skipped).
The 3.94 GiB app precedes VHH preparation/UI additions and the generalized padded
resource check. Those source changes need a later integration rebuild/acceptance.
The full-ensemble hPDL1 campaign remains active; inspect its observed callbacks
before taking recovery action. Continue the next scientific requirement.
