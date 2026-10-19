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
| Model and dependency management | IN DEVELOPMENT | Official AF2 member pins; publisher Boltz pin, atomic acquisition and native integrity controls; `boltz_resources.py`, `PredictionResources.tsx` | Extend managed downloads/status to other weights, recovery/unload/storage |
| Hardware/GPU resources | IN DEVELOPMENT | `fold_compute.py`; actual MPS diagnostic/attention evidence | Memory-aware scheduling, GPU allocation, peak-memory/throughput benchmarks |
| BindCraft2 pinned source/dependency inventory | TESTED | `vendor/bindcraft2-source.json`, `reports/bindcraft-audit.json` | Maintain pin and attribution; source presence is not feature parity |
| Campaign configuration | TESTED | `fold_engine.py`; upstream input checks on hPDL1/ANGPTL3 | Other modalities/constraints, full upstream preflight and live campaign execution |
| AF2 model parameters | TESTED | Seven authentic model checkpoints acquired as bounded official archive members, source/archive/checksum receipts; real models executed | AF2 digests are locally computed against official source, not independently published hashes; maintain provenance and attribution |
| AF2 complete forward and structure module | TESTED | `validate-af2-full.py`; genuine monomer/multimer CPU and Metal forward reports | 12/24-residue and 175-residue comparisons; real full ensemble binder accepted; broader modality/reference acceptance remains |
| AF2 loss, backpropagation and optimization | TESTED | `af2_native.py`; full-model monomer/multimer gradients, recycling and four real optimizer stages compared | Float32 model/optimizer comparisons and full ensemble campaign; upstream surrogate gradients require reference comparisons, not naive finite differences; broader coverage pending |
| Metal-compatible AF2 execution | IN DEVELOPMENT | MetalJAX 0.11.9, `af2_native.py`, monomer/multimer/optimizer comparison reports | Float32 narrow comparisons pass; original Apple plugin incompatible; full-size 6 GiB campaign under validation, no whole-engine parity claim |
| Metal attention | SCIENTIFICALLY VALIDATED | `metal_attention.py`, `reports/metal-attention.json` | Narrow float32 kernel parity only; no full-model validation implied |
| ProteinMPNN fixed-backbone redesign | TESTED | `mpnn.py`, `mpnn_runner.py`, `reports/proteinmpnn-validation.json`, `packaged-mpnn.json` | Full-model exact upstream parity and seed repeatability on two cases; CPU; folding/binding not validated |
| ProteinMPNN multistate/ties/residue constraints | IN DEVELOPMENT | `mpnn_constraints.py`, `mpnn_runner.py`, explicit sites/ties/omissions/biases; exact trained-model decoder comparison | Shared workflow/export and packaged acceptance; multistate redesign still incomplete |
| Genuine local BindCraft2 trajectory | IN DEVELOPMENT | `bindcraft_cpu.py`, `bindcraft_runner.py`; actual full-parameter CPU and Metal campaigns finished | Full single-model CPU/Metal campaigns correctly rejected candidates; original 5-design/2-held-out-model Metal ensemble produced one accepted computational prediction, not biological validation |
| Binder and linear peptide generation | IN DEVELOPMENT | Configuration/import works | End-to-end actual generation, filtering, comparison, provenance |
| Cyclic peptide, VHH, ARP, scFv, Fab and scaffold workflows | IN DEVELOPMENT | Original presets/snapshots; cyclic closure, VHH/ARP CPU/Metal narrow comparisons; paired scFv CPU stages with fixed frameworks preserved | Full-target VHH campaign and scFv full diagnostic pipeline active; Fab and broad scientific acceptance remain |
| Multitarget, detarget, fold switch, induced-fit and oligomers | IN DEVELOPMENT | `campaign_inputs.py`; explicit multi-target snapshots, objectives, native target-state import links; small CPU workflows | Small positive/negative technical pipelines pass; original-filter small campaign finished with no accepted candidates; large multi-target, scaffold combinations, fold switch, induced-fit and oligomers remain incomplete |
| Candidate import and reproducibility | TESTED | Ranked importer, raw CSV/metadata and coordinate checksums; M2 sequence records | Folding validation and automatic full-trajectory import |
| ChimeraX command architecture | IN DEVELOPMENT | Existing `observatory.py`, native inventory, console, capability audit | Exhaustive versioned command matrix and measured expansion; no universal claim |
| Coloring, selection, styles, surfaces and camera | IMPLEMENTED | Existing native scene/command/viewer adapters | Expand operation-equivalence and supported-argument tests |
| Measurements, contacts, H bonds, alignment, RMSD | TESTED | Existing MI/ChimeraX implementations, 4.3 tests and reference checks | Broaden chemistry and command-specific scientific evidence |
| Volumes, maps, trajectories, advanced editing | IN DEVELOPMENT | Explicit coordinate-ensemble import, native frame controls, scoped scene/coordinate checks; existing native map surfaces | Native ensemble UI/viewport acceptance, broader formats and verified maps/editing remain |
| Molecular Architect full workflow | IN DEVELOPMENT | Shared campaign/redesign dialog, observed hotspot IDs, immutable inputs, exact target fragments, real sequence/campaign results | Broader modalities and design-specific comparative/scientific acceptance |
| Protein Intelligence / X-Ray / interface explorer | IN DEVELOPMENT | Existing `MolecularIntelligence.tsx`, `intelligence.py` | Clearer evidence/UI, expanded chemistry and mutation analysis |
| Structural Comparison Observatory | IMPLEMENTED | Existing aligned views, RMSD/contact comparison and confidence | More reference cases, mutation/campaign comparison and transparent ranking |
| Boltz prediction | TESTED | Existing Boltz MPS pipeline and saved outputs | Broader end-to-end model acceptance and managed runtime packaging |
| BoltzGen / RFdiffusion / additional generators | NOT STARTED | No new adapter | Source/license/runtime audit followed by real computation |
| Drug Design Studio / RDKit / ligand preparation | IN DEVELOPMENT | `ligand.py`, `ligand_runner.py`, shared jobs/records, explicit graph + CIF/SDF; five small-molecule chemistry/interchange cases | Packaged runtime and native form/viewport acceptance pending; no docking, protonation enumeration or broader force-field validation |
| AutoDock Vina / GNINA / screening / pharmacophores | NOT STARTED | No integrated adapter | Native engines, reference cases and scientifically justified scoring |
| Dynamics Lab / OpenMM | IN DEVELOPMENT | `dynamics.py`, `dynamics_runner.py`, shared CPU pilots, genuine force-field/trajectory outputs, native panel | Packaged/native pilot acceptance, explicit solvent/general ligands, equilibrated sampling and broader RMSD/RMSF scientific acceptance |
| Free-energy / OpenFE | NOT STARTED | No integrated adapter | Validated preparation/sampling/uncertainty and reproducibility |
| Quantum chemistry / Psi4 | NOT STARTED | No integrated adapter | Feasible macOS engine, scientifically explicit methods and numerical checks |
| Fold Intelligence assistant | IN DEVELOPMENT | Existing deterministic evidence explanations | Real structure-aware tool execution and grounded interpretation; no local LLM installed |
| Research Observatory / project histories | TESTED | Existing SQLite/project ZIPs, raw scientific records | Migrations/snapshots/re-import and unified history across new engines |
| Publication figures | IMPLEMENTED | Existing PNG/SVG/PDF reports, native scene save | Publication QA, legends and reusable layouts |
| Molecular Cinema / video | IN DEVELOPMENT | Existing pose crossfade of fixed structures | Camera keyframes, timeline, real video export; never label illustrative animation as dynamics |
| Biological databases | IMPLEMENTED | Existing UniProt/PDB/AlphaFold DB retrieval | Domains/variants/interactions/Foldseek, retrieval provenance and validation |
| Self-contained macOS runtime | IN DEVELOPMENT | Four included CPU-JAX/MetalJAX/Boltz/OpenMM runtimes; real relocated AF2/MPNN/Boltz execution and app seals pass; native bundled-runtime/model status | Permitted ChimeraX embedding, fresh-machine/upgrade acceptance, broader engines and first-run resources |
| Signing, relocatability and data integrity | IN DEVELOPMENT | Existing signed builds and packaged IPC tests | Full standalone relocated launch, runtime dylibs and upgrade/data acceptance |
| ANGPTL3–ANGPTL8–APOA5 complete research workflow | IN DEVELOPMENT | Existing MI analysis and genuine packaged ANGPTL3 ProteinMPNN redesign | Actual binder trajectory, generated complex, comparative analysis and report |

## Current execution loop

1. Full-target VHH original-filter CPU job `966989db-84d8-4e50-8f24-efaba599995b`
   finished with no accepted designs (original final i_pTM rejection). Do not
   restart it. The paired-domain full technical pipeline also finished; outputs
   stay quarantined because its QA gates were permissive.
2. Native fragment, repeat, ligand form/export/connected viewport and coordinate-
   ensemble import/slider/playback acceptance passed on relocated sealed builds.
   Do not rerun completed model campaigns. The bounded 10 GiB Metal gradient
   remains memory-blocked; limits stay unchanged. Source tests pass 258 Python
   checks and 72 frontend checks, with no skipped visual fixture test now that
   the bundled public ANGPTL3 reference supplies the full XYZ clipping sweep.
   Relocated sealed motion/checkpoint acceptance and native analysis/export controls now pass; see latest checkpoint below. Next: bounded gradient-only AF2 memory experiment and shared checkpoint continuation.
3. Continue the full roadmap: broader modality/reference acceptance, native
   ChimeraX command coverage, shared workflows, remaining scientific engines and
   standalone runtime management. Respect current measured memory limits.
4. Preserve recoverable commits and precise evidence. A build, commit or passing
   check is a checkpoint, never completion of this assignment.

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

### Native chemical hydrogen-bond integration

`intelligence.py` analysis schema 1.1.0 calls original installed ChimeraX
`hbonds.find_hbonds` with strict zero distance/angle slack on the explicitly
selected cross-partner atoms. Results retain donor/acceptor identities, independent
coordinate-distance checks, criteria and source hash in the shared analysis job.
No hydrogens are added or protonation inferred by Fold. Native missing-H donor
geometry can be inferred by the original algorithm and is explicitly distinguished
from the existing explicit-hydrogen screens. Native clashes now use exactly the
selected source atoms, avoiding accidentally including omitted waters.

`MolecularIntelligence.tsx` adds a labeled table using the existing controls and
viewer selection. JSON/CSV/Markdown exports preserve native chemistry and criteria.
An actual native-command comparison on a clearly artificial SER–ALA test fixture
returned the same donor/acceptor pair and independently verified 2.8 Å distance.
Unselected water exclusion, temporary model cleanup, unchanged saved coordinates,
shared background task, result persistence and three exports passed.
`reports/native-hbonds-validation.json`; `scripts/validate-native-hbonds.py`.

The measured command inventory now has 11 narrowly scoped tested commands out of
591, three with fixture-level numerical checks. No comprehensive command/argument
parity or biological validation is claimed. 176 Python + 64 frontend tests passed.
Next native integration build includes VHH preparation, padded-resource checks and
strict native chemistry; all further roadmap requirements remain active.

### Latest native-window and Boltz packaging work

The 3.94 GiB scaffold/chemistry app was relocated using APFS copies and passed
full Metal forward/backprop plus strict native hydrogen-bond analysis through its
own bundled Python/source, with signatures intact afterward. The native window
was opened in an isolated QA library: VHH selection correctly hides free-length
controls and compute diagnostics reported its app-owned Metal backend. Screenshot:
`reports/native-scaffold-controls.png`; native analysis evidence:
`reports/packaged-native-hbonds-validation.json`. Original user data were not used.

A third runtime is now staged from the existing tested Boltz environment
(Boltz Community 2.10.12 / PyTorch 2.14.1), retaining Python/dependency licenses.
The native-library audit distinguished library install IDs from dependencies and
found 18 genuine absolute OpenMP links into the old development directory. Only
the owned staging copy was relinked to its identical internal libomp, then signed.
The repaired audit reports 490 Mach-O files, zero external absolute dependencies
and zero missing loader-relative dependencies. @rpath entries remain candidate
checks and are not blanket proof of loader resolution. The relocated runtime
actually passed Boltz imports, MPS forward/backprop, compiled scikit-learn fitting
and RDKit 3D embedding. Full packaged Boltz inference remains pending.

Source now discovers runtime-boltz automatically and uses explicit -B flags on
compute/inference children. Model cache remains managed in application data;
first use can acquire needed resources internally without a manual tool install.
The confidence model is pinned to publisher repository commit
55fa4a71318b7fc4cd8431b85bc3cf7449803d1b and Git LFS SHA-256
090e82ac8c92f5e943fa1b39e7410a44027bea7243c0bbb3caa67a77fc1428e1.
The existing local 2,286,561,469-byte checkpoint matches that independently
published checksum. Pin source: https://huggingface.co/boltz-community/boltz-2/commit/55fa4a71318b7fc4cd8431b85bc3cf7449803d1b .

`boltz_resources.py` acquires/verifies that exact model before deserialization,
records actual checkpoint/available canonical CCD hashes, and refuses unexpected
resource changes during a calculation. Downloaded empty/LFS placeholders are
handled separately from usable existing caches. Unused affinity weights and the
whole extracted chemical dictionary are not asserted as independently verified.
Boltz runtime/resource source changes need a native build and real packaged
inference acceptance; do not describe the full platform as standalone yet.
The full ensemble hPDL1 research job remains active under original criteria.

### Full original-ensemble binder and shared-library acceptance

The full 115-residue hPDL1 target / 60-residue binder campaign completed locally
on Metal in 2251.546 seconds, retaining the original five multimer-v3 design
models, two held-out pTM validation models and all original scientific gates.
Job `31e1b01b-1aa9-48e9-94df-b267adbf0a50` accepted its first trajectory and
imported one ranked prediction, `298e17cc-d2c9-4fd1-a8b7-3a358af240b8`, into
the isolated validation library. Raw upstream i_pTM 0.82, pLDDT 0.91 and binder
RMSD 0.35 Å are preserved with their upstream scale/definitions. This is a
computationally accepted design, not demonstrated binding or inhibition.
`reports/bindcraft-ensemble-outcome.json` retains the actual job and metrics.

`bindcraft_provenance.py` verifies exact job/output/settings/runtime, immutable
target/scaffold, source-manifest and checkpoint receipt correspondence before
labeling an import native. External results stay unverified. Explicit upstream
CIF target/binder chain IDs become shared chain roles; user edits are preserved.
Existing imports can be enriched idempotently without modifying coordinate assets
or creating duplicates. Original and reported campaign revisions are separately
labeled. True upstream pLDDT encoded in B factors is recognized on a 0–100 scale.

The generated complex then completed shared Molecular Intelligence analysis,
including installed ChimeraX strict hydrogen bonds, with its original coordinates
unchanged: 161 heavy-atom contact pairs at 4 Å, per-interface sampled SASA
873.952 Å² and three strict native hydrogen bonds under the saved criteria.
The independent analysis also identifies severe side-chain overlaps; upstream
acceptance is not represented as clash-free geometry. Full original PAE is not
available and no matrix was inferred. Integration/analysis receipts are
`reports/native-binder-library-integration.json`,
`reports/native-binder-interface-analysis.json` and the paired Markdown report.

Earlier entries reporting this ensemble job active are historical checkpoints;
it has completed and must not be restarted. Continue standalone Boltz acceptance,
remaining scaffold/multistate modalities and other unfinished platform requirements.

Integration checkpoint: 189 Python and 64 frontend tests passed; one existing
private frontend fixture skipped. Native build with the third runtime is underway.

### Boltz seal correction and ankyrin-repeat scaffold

The first real bundled Boltz prediction completed but correctly failed the final
seal check: Numba wrote four feature-compilation cache files inside the signed
runtime despite Python -B. No original sealed file hashes changed. Failure
evidence/copy is retained. `worker.py` now sets NUMBA_CACHE_DIR under the isolated
application-data engine cache before import and records it in provenance. A
process-boundary regression covers this setting. A new build and relocated copy
then completed another actual 35-residue MPS prediction with the publisher-pinned
checkpoint, saved coordinates/confidence and an unchanged valid app seal.
`reports/embedded-boltz-runtime-acceptance.json`,
`reports/embedded-boltz-first-seal-failure.json`. This is same-host packaging
acceptance, not biological accuracy or fresh-machine validation.

ARP now uses its original upstream scaffold, repeat edit choices and framework
retention criteria through the shared preparation/runtime and existing design
controls. Free length inputs are refused for scaffold formats. Real trained AF2
CPU and Metal trajectories on an explicit 12-residue technical target completed
one update per screen/refine/anneal/harden stage, keeping all 125 fixed framework
residues unchanged in the 171-residue designed scaffold. Resolved coordinate RMS
difference was 0.0000468644 Å; all predefined comparison checks passed. These
permissive diagnostic gates establish constrained optimizer execution only, not
a full-target or accepted research-quality ARP. The 256 padded-residue launch
boundary still applies. `reports/arp-trajectory-metal-comparison.json`.

### Explicit ProteinMPNN residue and chain constraints

`mpnn_constraints.py` maps explicit shared residue IDs to immutable source
positions, rejects contradictory fixed masks/chain ties, requires equal chain
lengths and compatible fixed residues, validates amino-acid omissions and finite
log-odds biases. `mpnn_runner.py` verifies exact upstream residue-number/sequence
correspondence, applies original decoder options, and independently checks fixed
residues, ties, omitted amino acids and unchanged coordinates on output. Whole
chain redesign remains backward compatible. Existing controls now expose residue
selection, corresponding-chain ties and optional amino-acid exclusions.

Actual full trained-model execution on two duplicated 12-residue technical
fragments exactly matched a separately constructed original decoder in sequences
and scores, and repeated models with the same seed reproduced both candidates.
The geometry is explicit algorithm QA, not a biological dimer or valid design.
`reports/mpnn-constraints-validation.json`. Shared jobs/records/project exports
retain the complete constraints and source snapshot. Packaged constrained-decoder
acceptance and remaining multistate/full scaffold workflows continue.

The ARP preparation check measured 224 padded residues for the technical fragment
and 320 for full hPDL1; the latter launch was correctly refused while keeping the
campaign prepared (`reports/arp-preparation-resources.json`). Do not silently
crop the target or weaken scaffold constraints. Full 320-residue trained-model
CPU/Metal memory/numerical validation is the next dependency for larger profiles.

Shared constrained ProteinMPNN job `65510b0a-c2e8-4a8f-b1a7-f3cf75b2b306`
completed and saved four sequence records matching direct inference; actual
project ZIP retained exact source and complete constraints. Integration suite:
195 Python and 64 frontend tests passed; one existing private fixture skipped.

### Packaged constraints and native job-routing correction

The relocated 5.05 GiB app completed constrained ProteinMPNN using its own runtime,
source and trained checkpoint with development overrides removed. Direct original
decoder parity/repeatability passed, all four sequence records and full project
archive constraints passed, and the final deep/strict app signature passed.
`reports/packaged-mpnn-constraints-validation.json`.

An actual native-button submission then reproduced an existing integration defect:
the global job-completion handler treated every output as a coordinate structure.
Sequence redesign therefore closed Architect, changed the viewer title to a
sequence and reported a missing source. `src/lib/jobs.ts` now routes by saved
record kind/project, `App.tsx` retains Architect on sequence completion and loads
the workbench sequence without replacing the coordinate scene, and activity
result buttons open sequences in Sequence Workbench. Coordinate loading rejects
non-structure records. Home/history use accurate local ProteinMPNN/BindCraft2
labels rather than the old ColabFold fallback. The Job type includes both engines.
Four regression cases cover sequence/coordinate routing, unrelated/missing output
refusal and accurate local/cloud labels. Native repeat acceptance is underway.

The 320-residue full trained CPU forward/backpropagation executed (280.626 s,
10.19 GB peak process RSS). Metal completed forward but the memory governor
refused gradients at 6 GiB and 8 GiB process caps, respectively observing 6.5/8.3
GiB demand. These are retained failures, not backend-parity passes. The app still
limits campaigns to 256 padded residues. The next experiment uses the original
upstream attention subbatching at an 8 GiB cap; it does not change model weights
or scientific gates. `reports/af2-320-memory-investigation.json`.

Native result-routing repeat passed: the actual app ran tied-chain redesigns,
including precisely A18/B18 as the only editable sites, saved four sequences
with all other positions unchanged, and kept Architect open. Its activity result
button then opened the real 12-residue sequence in Sequence Workbench. The source
coordinate record/hash stayed unchanged and the app seal passed. Evidence:
`reports/native-mpnn-result-routing.json` and two paired screenshots.
Integration checks: 195 Python and 68 frontend tests passed before the additional
larger-CPU profile guard; targeted guard checks passed afterward.

The original VHH scaffold with the complete 115-residue hPDL1 target completed
four real diagnostic optimizer updates on CPU in 201.271 s (8.73 GB peak RSS),
preserving all 88 fixed framework and 115 target sequence positions.
`reports/vhh-full-target-cpu-trajectory.json`; raw arrays/CIF retained under
`../validation/vhh-full-target-f32-cpu`. Diagnostic confidence gates do not imply
research acceptance. Original upstream attention subbatching also exceeded the
8 GiB Metal cap, so larger Metal campaigns remain unavailable.

A separately labeled `experimental-cpu-float32-scaffold` profile now permits up
to 320 padded positions only for original scaffold campaigns; other profiles keep
256. Full trained 320-residue CPU execution and full-target VHH diagnostic stages
provide resource evidence; complete default-filter campaign acceptance is still
pending. The previously prepared full-target VHH job
`966989db-84d8-4e50-8f24-efaba599995b` now runs under its original scientific
criteria, one design model and a distinct held-out multimer. Inspect its live
callbacks in `../validation/vhh-preparation/jobs/<id>/execution.log`; do not
restart it. `reports/vhh-full-target-live-cpu-job.json`. Current native app build
precedes the larger-CPU profile controls; those source additions need a later
integration build. Continue remaining multitarget/scaffold/platform requirements.

### Multi-target and negative-target shared workflow

`campaign_inputs.py` adds up to three additional observed structures to campaign
preparation. Every state reuses the same canonical-backbone/chain/site/project
checks; keeps its own immutable coordinate snapshot, checksum and residue map;
and records explicit target/detarget objective and signed upstream weight.
Duplicate or contradictory coordinate/chain states are refused. All snapshots,
including the scaffold, are rechecked before launch, again after queueing, and
in native import receipts. Old single-target preparations remain compatible.

`CampaignTarget.tsx` extends the existing design dialog with saved structure,
chain, site, binding/avoidance and weight controls; no styles/viewer replacement.
`bindcraft_provenance.py` retains all target inputs. Ranked native imports match
the pinned original writer's exact state suffixes, require all target-state
coordinate outputs for each candidate and retain the corresponding source state.
The existing accepted full-ensemble binder idempotently reimported with the same
record ID and unchanged coordinate hash after these changes.

Real quarantined CPU AF2/ProteinMPNN/held-out folding pipelines passed for two
positive peptide states (39.22 s), two positive plus one negative peptide state
(51.58 s), and binder positive/negative states (68.44 s). A further binder case
using original 32-residue bucketing passed (94.14 s). Exact input-target sequences
and one shared designed sequence across every written state were independently
verified against saved inputs. All cases use explicit permissive QA filters and
small update budgets; their low-confidence results remain quarantined and zero
generated records were imported. They establish real pathway execution, not
scientific cross-reactivity, specificity or default-filter acceptance. Reports:
`reports/multitarget-{positive-pair,negative-selection,binder-negative,binder-padded}-validation.json`.

An initial diagnostic harness used an integer where original
multitarget_rounds_per_target requires a stage-name list; upstream preflight
refused it before computation. The corrected harness retains that failed case
and supplies enough updates to visit every target. No vendored source changed.

The explicit `experimental-cpu-float32-multitarget` profile supports only two or
three binder/linear-peptide states and at most 192 aggregate padded positions.
Metal, ensembles and multi-target scaffold combinations remain refused. The
initial 128-position guard correctly refused the three-state native fixture;
the 192 profile was enabled only after the actual original padded pipeline
passed. The same prepared job was resumed, not duplicated. Native original-filter
job `1c1f58e4-9920-468c-8369-cada84b95a59` now runs in
`../validation/native-multitarget-cpu` on explicit 12-residue technical fragments.
Original upstream scientific gates and stage budgets are retained. Inspect its
existing receipts/logs; do not restart it.

Latest integration: 206 Python and 68 frontend tests passed; one existing private
frontend fixture skipped. Full-target VHH CPU job
`966989db-84d8-4e50-8f24-efaba599995b` is also active, with actual optimizer
callbacks retained. New larger-CPU and multi-target source/UI require the next
combined native build/relocation acceptance. Continue full roadmap work.

### Model integrity and native workflow feedback — current checkpoint

The combined native build from `ff6c2e8` passed its relocated three-state
positive/negative technical pipeline in 118.603 s using only app-owned Python,
source and weights. Exact state/output/sequence correspondence passed; no
research records were imported from permissive diagnostic outputs. Native GUI
preparation preserved explicit avoidance objective, weight 0.5, source chains,
all input hashes and export bytes. Evidence: `packaged-multitarget-validation.json`
and `native-multitarget-preparation.json` in reports. App seals passed afterward.

The original-filter small three-state CPU campaign
`1c1f58e4-9920-468c-8369-cada84b95a59` has finished with
`no_accepted_designs`, zero imported outputs. This is scientific rejection,
not a runtime error or evidence of biological specificity. Its full outcome and
execution log are recorded in `reports/native-multitarget-cpu-outcome.json`.
Do not restart it. The full-target original-filter VHH CPU campaign remains
active; inspect the existing job before any recovery action.

Local Compute now identifies the bundled Boltz runtime and avoids offering an
unnecessary separate Python installation. `PredictionResources.tsx`,
`boltz_resources.status`, `worker.prediction_resources` and the native allowlist
provide fast model presence/partial-download status plus explicit publisher
checksum verification without downloading, replacing or deserializing cache
files. The real 2,286,561,469-byte checkpoint matched the independently published
Git LFS SHA-256 (`reports/prediction-model-integrity-status.json`). Six synthetic
file-integrity tests cover mismatch, incomplete and changed-during-check states.
Chemical dictionary, affinity weights and prediction quality are outside this
integrity check. A combined build/native UI acceptance is in progress.

Campaign feedback now reports preparation, live computation, original-filter
rejection, failure and imported results separately, even when a job retains its
original preparation metadata. `src/lib/jobs.ts` and `DesignCampaigns.tsx`;
frontend status regression test included. This is feedback only; scientific
criteria and molecular rendering remain unchanged.

Current integration checks: 212 Python and 69 frontend tests passed (one existing
private frontend fixture skipped). The next scaffold investigation exercises the
original paired scFv variable domains on an explicitly small technical target;
its native controls remain blocked pending real execution and fixed-framework
verification. The full hPDL1 target plus original scFv/Fab presets requires 416/608
padded positions by the original upstream estimate, beyond currently validated
native memory limits. Do not silently truncate these antibody domains.

### Ordered native geometry and relocated model controls

The relocated `857f167` app's native Local Compute panel correctly distinguishes
bundled runtime availability, cached models, completed inference and publisher
file integrity. The actual Verify button hashed the real 2.29 GB checkpoint,
showed publisher verification and preserved the app signature. Evidence:
`reports/native-model-integrity.json`, `.png` and `-ax.txt`. This build precedes
the following scene measurement change; do not claim that change is packaged yet.

`scene_bridge.SceneBridge.measure` now refuses duplicate/stale atom handles,
nonfinite points, zero-length angle bonds and collinear torsion planes instead
of reporting misleading numerical angles. Distinct coincident distance and a
straight 180-degree bond angle remain valid. Ordered atom identities, scene
coordinates and signed native calculation remain unchanged. Six contract tests
pass. `scripts/validate-native-measurements.py` independently checks analytic
sqrt(3) Å distance, 90-degree angle and mirrored -90/+90-degree torsions against
actual native functions plus original angle/torsion commands. Source and native
coordinates remain unchanged (`reports/native-ordered-measurements.json`).
Earlier harness failures are retained in the validation directories: field-name
mismatch, reversed analytic sign, and an incorrect assumption that the native
four-atom angle command means dihedral. Original source inspection established
that angle measures two bond vectors, while torsion measures signed dihedrals;
the corrected harness explicitly uses torsion. No engine math was changed to
match a mistaken expectation. Command inventory now has 13 narrowly tested
entries, five with scoped numerical evidence; no comprehensive parity claim.

Native campaign feedback acceptance also passed on the saved original-filter
three-state job: the completed card shows zero imported structures and explicitly
says no candidate passed the original scientific filters. No calculation was
restarted. `reports/native-campaign-outcome.json` / `.png` / `-ax.txt`.
Integration ran 218 Python checks; only two command-evidence inventory expectations
needed updating for the two newly measured commands; those targeted checks now
pass with exact live-report hash linkage. The existing frontend suite was already
verified for the unchanged UI at 69 passing checks.

### Paired antibody domains and explicit observed target fragments

The original scFv heavy/light variable-domain scaffold completed four genuine
float32 CPU optimizer stages on a 12-residue technical target in 603.968 s
(7.26 GB peak process RSS). All 100 + 99 fixed framework positions and all 12
target positions remained unchanged; output chain lengths are 123/107/12.
`reports/scfv-cpu-trajectory.json`. These permissive diagnostic gates establish
execution and framework retention only, not original-filter antibody acceptance.
The native preparation/UI now includes scFv, preserving complete upstream
frameworks, CDR choices and held-out multimer validation; no VH–VL linker is
designed. Original padded resource estimates require 320 positions even with the
small target, so use the separately validated larger CPU profile. Full-target
scFv (416) and Fab (608; 512 even with the small target) exceed tested limits;
Fab remains blocked. Full scFv optimization → MPNN → held-out AF2 diagnostic
pipeline is active at `../validation/scfv-cpu-pipeline`; inspect it before any
recovery action and do not claim it has completed.

`target_fragment.py`, `Engine.fold_fragment`, native IPC and `TargetFragment.tsx`
add explicit target-segment extraction to the existing campaign panel. A new
structure retains exact parsed coordinates, atom identities, author numbering,
occupancies and the original per-atom confidence interpretation. Parent PAE,
pTM/ipTM and interface metrics are not copied. Original files remain unchanged.
Segments must be continuous canonical backbone-complete observed residues with
resolved occupancies and no ambiguous model/numbering/alternate conformers.
No sequence completion, artificial joins, added atoms, capping or inferred domain
identity. Every selection/source hash and removed-context limitation is recorded.
Seven contracts cover exact CIF precision, malformed selections, source integrity,
project boundaries, chain roles and project archive hashes.

Actual bundled ANGPTL3 reference residues 240–300 produced a separate 61-residue,
487-atom input with exact coordinates/author IDs and passed original-preset binder
preparation. Both original and derived asset hashes survived project export.
`reports/angptl3-target-fragment.json`. This is input preparation, with no folding,
binding or domain-boundary validation. Native UI acceptance/build remains pending.

Combined source checks pass: 229 Python and 69 frontend tests, plus TypeScript
compilation; one existing private frontend fixture skipped. Native integration
build now batches the verified geometry fix, paired-domain controls and target
fragment workflow. UI and packaged source acceptance still need to finish.

### Completed scaffold calculations and current Metal investigation

The full-target original VHH CPU campaign completed all optimization stages but
failed the original final i_pTM criterion (reported 0.66, pLDDT 0.90); it imported
zero structures. `reports/vhh-full-target-cpu-outcome.json`. Do not relabel its
rejection or silently weaken the filters. The paired scFv technical full pipeline
finished in 764.946 s, with 126/107-residue domains and the original 12-residue
target. Genuine MPNN held 199 framework residues, verified independently against
the saved trajectory sequences and the exact written editable-site stamp.
`reports/scfv-cpu-pipeline.json`, `scfv-output-correspondence.json`. Raw absent
interface scores remain -inf/blank upstream; no score is synthesized. Diagnostic
output is not original-filter acceptance, binding evidence or a designed linker.

The native full-target scFv launch correctly refuses its 416 padded positions
against the 320 CPU profile and leaves the full prepared input unchanged
(`reports/scfv-native-resource-guard.json`). After earlier CPU jobs finished, a
separate 10 GiB-governed Metal technical case is probing genuine 320-residue
forward/backpropagation against the existing CPU reference. Existing failed
6/8 GiB cases remain evidence; no app memory or residue limit was raised.

Native combined `db6b80f` acceptance passed: actual form extracted ANGPTL3
A240–251 (12 residues / 89 atoms), selected it as the new target and saved the
original paired-domain scaffold campaign. Source/fragment coordinates, author
numbers and project/scaffold export hashes all match. The existing viewer
rendered the real fragment and synchronized its native scene; app seal passed.
Evidence: `reports/native-scaffold-fragment.json`, `native-scaffold-fragment.png`
and `native-fragment-viewport.png`. An earlier WebGL initialization attempt
failed; isolated relaunch later initialized and rendered correctly. Root cause
is not established; do not claim a renderer-code fix. Packaged angle/torsion
checks also passed (`reports/packaged-ordered-measurements.json`). No native
scFv campaign was started by the form acceptance; diagnostic model execution
was separately recorded and quarantined.

The governed 10 GiB larger Metal attempt completed forward inference. Its 2,672
written atomic positions match the saved CPU forward output with coordinate RMS
0.000912 Å (max component difference 0.0625 Å). Backpropagation then failed with
RESOURCE_EXHAUSTED at 10.2 GiB process footprint / 9.5 GiB live MLX arrays and only
0.3 GiB reported machine free memory. Preserve this partial result and failure;
do not claim gradient parity or raise app limits. `reports/af2-320-metal-10g.json`
and the updated memory investigation retain the evidence. Larger CPU scaffolds
remain supported; larger Metal needs a lower-memory execution solution.

### Auditable campaign repeats

`campaign_repeat.py`, `Engine.bindcraft_repeat`, native IPC and
`CampaignRepeat.tsx` allow a completed, rejected, failed, cancelled or imported
campaign to prepare another run from its immutable saved inputs. This does not
execute a calculation. A repeat records its parent campaign and original/new
seed; only an explicitly supplied seed changes scientific settings. Source pin,
settings, every target snapshot and any scaffold are verified before copying;
original results/errors remain unchanged. The new prepared card offers the
existing explicit backend choices, so a failed Metal run can be retried on CPU
without rebuilding scientific selections or weakening filters. Seven contracts
cover exact inputs, seed-only changes, multi-target/scaffold export, tampering,
project/revision guards and absence of a compute spawn. Native UI acceptance is
next; no repeat calculation is automatically scheduled.

Combined repeat workflow checks: 236 Python and 69 frontend tests plus TypeScript
compilation passed. The next build also normalizes campaign numeric fields on
blur (removing observed leading zeros) and requires fragment end points to exist
in the source. Scientific settings and coordinates remain unchanged.

### Original two-copy oligomer workflow

The next original BindCraft2 preset, `homo_oligomer`, now prepares two identical
binder-chain copies with length bounds explicitly per copy. It retains original
filters and symmetric sequence tying; other copy-count/symmetry overrides remain
refused. Resource checks count both copies. Inspection also found that native
single-model selection had only checked an explicit validation_model field;
upstream chooses held-out multimer by default for multiple binder chains. The
adapter now preserves that original rule and rejects an invalid explicit pool.
Four contracts cover exact preset fields, held-out pool choice, both-copy memory
counting and unsupported overrides. A small original algorithm trajectory has
executed on CPU; CPU full diagnostic pipeline and narrow Metal trajectory are
being checked before native integration acceptance. No biological oligomer,
symmetry or binding validation is asserted from a technical case.

Trajectory harness correction: the direct diagnostic model constructor now
passes original symmetric multi-chain groups and amino-acid biases, matching the
production campaign constructor. Earlier direct trajectory CPU/Metal comparisons
used matching backend inputs but omitted those constructor options; treat those
as narrow, identically configured model/optimizer comparisons, not complete
original campaign policy equivalence. Fixed-framework checks remain observations
of those runs. Production `bindcraft_runner → launch_campaign` always used the
original constructor; its full scFv and original-filter binder/VHH campaign
receipts are unaffected. New paired-copy CPU/Metal checks explicitly record and
compare modelPolicy. Earlier harness outputs remain retained separately.

The corrected-policy 12+12-residue homodimer / 12-residue target completed all
four real optimizer stages on CPU and Metal. Sequences and masks are identical;
maximum resolved-coordinate RMS across chains is 0.001851 Å. The full CPU
optimization → actual tied ProteinMPNN → held-out multimer pipeline completed in
19.940 s; both output binder chains have the same 12-residue sequence and the
target sequence is retained. `reports/homodimer-cpu-metal-comparison.json`,
`homodimer-cpu-trajectory.json`, `homodimer-metal-trajectory.json` and
`homodimer-cpu-pipeline.json`. Gates are explicitly diagnostic; no biological
symmetry, physical oligomerization or binding is validated. Native integration
remains next. Current source checks: 240 Python and 69 frontend tests plus
TypeScript passed (one existing private frontend fixture skipped).

### Native repeat and original-filter homodimer acceptance

The actual `e917fc6` native repeat button saved three byte-identical target
snapshots, changed only campaign_seed 42→43, and left the completed parent
scientific rejection intact. New child `2d203664-74d8-42b8-b537-a32ba775ad6f`
is prepared, with no calculation started (`reports/native-campaign-repeat.json`
and `.png`). The native homodimer form then prepared and started job
`546062e5-be0a-4da6-b410-b6acb2367373` using only app-owned CPU runtime/source/
weights. Original 96-position padded execution retained the full original
scientific filters and held-out model_2_multimer_v3. It completed with no accepted
designs; zero structures imported, signature passed. `native-homodimer-outcome.json`.
A final native screenshot could not be captured because the Mac locked; no UI
completion screenshot is claimed. Do not restart these completed calculations.

### Ligand preparation — genuine RDKit integration in development

`ligand_runner.py` uses the included RDKit 2026.09.1 (wheel metadata 2026.9.1):
ETKDGv3, explicit seed, one CPU thread, MMFF94s, up to eight conformers, strict
convergence and finite-energy checks. Specified charge/3D stereochemistry and
SDF chemical graph are retained; no protonation, neutralization, salt stripping,
tautomer or docking inference. Coordinate transport has an exact atom map;
SDF's decimal rounding is checked within 0.0001 Å. Unsupported isotope/radical
transport, disconnected input, unassigned potential stereo and missing MMFF
parameters are refused. Native ligand records preserve chemical graph, original
SMILES, methods, runtime, input/output hashes and SDF assets in the common
SQLite/jobs/export model. Existing compute lock, cancellation and reconciliation
are reused; no parallel research database or molecular viewer is added.

`LigandPreparation.tsx` adds a collapsed preparation form to the existing campaign
panel; Research Library adds checksum-checked SDF export. Engine/job labels and
native IPC/resources include RDKit. Seven workflow contracts cover bounded input,
compute lock, cancellation, input tampering, export hashes/projects and native
registration. Real small-molecule chemistry/round-trip/repeatability acceptance
is in progress. An early export test exposed the missing SDF extension in the
shared export allowlist; corrected there. The initial coverage fixture assumed
Zn2+ lacked MMFF parameters, but the original library supports that ion; the
negative coverage test now uses Xe after directly checking its absent parameters.
No force-field behavior was changed to fit that incorrect test expectation.
Mac is locked; native ligand form/viewport acceptance remains pending.

The chemistry checks now pass on ethanol, benzene, explicitly chiral alanine,
methylammonium and an explicitly specified alkene. Formula/charge/explicit-H
counts, geometry-derived stereochemistry, same-seed coordinates/energy and SDF
round trips agree with recorded inputs. Invalid connectivity, unspecified stereo,
missing MMFF coverage and unsupported isotopic transport are refused without a
saved ligand. `reports/ligand-chemistry-acceptance.json`. Existing completed cases
were resumed to test archive changes, with no calculation resubmitted.

Project ZIP testing exposed that extra SDF assets were omitted by the old
single-coordinate-asset exporter. The shared exporter now includes coordinate,
ligand-SDF and saved native-session assets with streamed SHA-256 verification and
an asset manifest. It builds a temporary archive and atomically replaces the
requested destination only after success; failed integrity checks preserve any
existing archive. Tests cover both coordinate and SDF corruption. The original
source/assets remain unchanged. Eight ligand workflow contracts pass; native
RDK atom/bond transport checks pass on the saved cases, independent of screen
unlock. Full packaged ligand acceptance and native UI remain next.

Shared job bookkeeping now attaches process metadata in a write transaction
without rewriting state. A fast completed worker cannot be resurrected as queued
by the parent's PID attachment; completed output metadata is retained. State
updates also acquire the write lock before reading JSON. Two regression checks
cover this behavior and rollback on invalid metadata; all 250 Python tests pass.
The frontend suite passes 69 tests (one existing visual test skipped) and TypeScript
compilation passes. Packaged chemistry remains the next integration check.

### Packaged RDKit and expanded native command acceptance

Relocated `f2527f7` app executes all five chemistry cases plus same-seed repeat
and four refusals using automatic bundled runtime discovery, no configured Python
override. All coordinate/SDF project archive hashes match and the app signature
passes after calculations (`reports/packaged-ligand-chemistry.json`). With the Mac
unlocked, the actual native ligand form prepared ethanol and the native save
dialog exported its exact SDF. Initial viewport inspection caught missing bonds:
the renderer adapter supplied 1e8 as each expected bond length. Mol* checks that
field against real coordinates within 0.3 Å, so it rejected every bond. The adapter
now supplies measured lengths only for native displayed bond pairs. A test using
the actual Mol* CIF parser and structure graph fails with the original placeholder
and passes with the fix; it also refuses to infer absent or hidden bonds. The
original geometry/materials/viewer remain in place. Rebuilt viewport acceptance
is pending; the initial missing-bond screenshot is retained as evidence.

Eight further original ChimeraX commands pass scoped native scene checks:
show/hide author-residue atoms, cartoon flags, transparency alpha, unfitted 3 Å
RMSD (unequal counts refused), analytic 90° model rotation, camera zoom factor 2,
and original native molecular surface vertex/index buffers. Source assets stay
unchanged. `scripts/validate-native-scene-commands.py`,
`reports/native-scene-commands.json`. The earlier fixture tried to reopen an
already linked model, which correctly reused its identity; an explicitly separate
private reference record now supplies the second RMSD model. Inventory evidence
is now 21 scoped commands, eight numerical checks, never complete ChimeraX parity.

### Native ligand fix accepted; supplied coordinate ensembles in development

The relocated `f7a9280` viewer now visibly renders the native ethanol bonds.
`reports/native-ligand-bonds-fixed.png`, `native-ligand-viewer-ax.txt` and
`native-ligand-acceptance.json` retain actual form/job/export/viewport evidence.
Original saved coordinates and exact native SDF export hashes agree; signature
verification after native use passed. The new build was initially opened before
Launch Services recognized the test process, producing a duplicate default dev
window. That duplicate was closed before research actions; the private library
was verified before form/export/viewer work. Original production data untouched.

`coordinate_ensemble.py` validates explicit multi-MODEL PDB topology and metadata,
retains all raw bytes, pins frame IDs and rejects unresolved/mismatched frames.
The existing unified import/open architecture reads these as real native
coordinate sets; no separate research state or viewer. Research Library offers
an explicit import button. Existing trajectory controls now stop playback when
models change and disable overlapping slider requests. Native real single-frame
coordset commands preserve exact artificial coordinates, persistent atom handles,
original nonconsecutive MODEL IDs and repeatable geometry fingerprints through
five switches. Analytic raw RMSDs 0/3/2 Å agree; project ZIP preserves the full
source. Eight contracts pass, 258 Python tests passed at the integration checkpoint,
TypeScript compilation passes. Evidence registry now contains 22 scoped commands,
nine numerical checks. No dynamics/time/force-field claim. Packaged/native ensemble
import and frame controls remain next (`docs/COORDINATE_ENSEMBLES.md`).

### Coordinate ensemble native acceptance and portable clipping test

Relocated sealed `59c3664` app passes actual native import, trajectory slider
(frame 3) and ordered Play (3→7→11), with synchronized visual receipts and exact
final coordinates. `reports/native-coordinate-ensemble.json`, two screenshots
and AX trees. Source asset unchanged; seal passes after native playback. Separate
app-owned Python/native acceptance also passes on five frame changes and exact
raw project ZIP bytes (`packaged-coordinate-ensemble.json`). Backend validation
is not substituted for the native form checks; both now have evidence.

The old full-orbit clipping test skipped on checkouts lacking a private complex
fixture. It now uses the actual bundled public ANGPTL3 mmCIF and real Mol* camera:
360° about all XYZ axes, centered and offset selection pivots. All 72 frontend
tests pass with no skips. This checks depth slabs for the stated reference, not
rasterization or a new ANGPTL3–ANGPTL8 complex validation. Settings/about wording
is being corrected to reflect local protein design, ligand preparation and
supplied-coordinate playback rather than describing them as future work.

OpenMM 8.6.1 official universal2 wheel acquired with publisher PyPI SHA-256,
14,082,674 bytes. Pinned upstream revision b399af4725573963b46d6c1083fdcf7a37615857.
Wheel omits license files; exact release license notices retained separately in
`vendor/licenses/openmm` (MIT CPU/reference; GPU plugin LGPL and third-party
notices). Isolated dependency/runtime audit is in progress. No OpenMM simulation,
ForceField workflow, Metal backend or packaged OpenMM support claimed yet.

### OpenMM short protein pilot — actual implementation and numerical evidence

`dynamics.py`/`dynamics_runner.py` integrate original OpenMM 8.6.1 through the
shared compute lock, jobs, cancellation, SQLite records and project archive.
Strict 1–64-residue protein preflight, pinned input/runner hashes, standard pH-7
hydrogens with original heavy atoms fixed during preparation, Amber ff14SB/OBC2,
nonperiodic NoCutoff, bounded minimization, Langevin-middle 300 K / 1 fs / 1 per ps,
HBond constraints. Original source is immutable; separately saved prepared,
minimized and real multi-frame trajectory models have no prediction confidence.
PDB interchange preserves heavy-atom identity with measured rounding ≤0.001 Å.
Every frame has an explicit MODEL/step/ps map; complete System/Integrator/State XML,
parameter-file hashes and execution logs are retained. No equilibration,
stability, binding, free-energy or Metal claim.

`openmm-protein-pilot.json`: 582 atoms / 35 residues, real 20 steps / 0.02 ps /
five frames; analytic harmonic energy/forces and original Reference-versus-CPU
force/energy comparisons at prepared and minimized coordinates pass. Two real
common-job pipelines and exact project exports pass on PDB and mmCIF sources
(`openmm-shared-workflow*.json`). Source fixture is the OpenMM test protein with
water/chloride removed in a private QA derivative. Its blank author chain was
explicitly named A in another QA copy to meet the documented initial input
scope; original fixture unchanged. OpenMM PDBxFile writes occupancy 0 by default,
correctly refused by preflight. A separate mmCIF transport retaining original PDB
occupancies was used. Testing then exposed the reader convention '' vs ' ' for
absent insertion codes; canonical blank normalization fixes interchange while
preserving actual insertion IDs. Failed jobs/roots remain as diagnostic evidence.

The runtime has been assembled separately with only CPU/Reference platforms;
OpenCL plugins omitted from the product copy. ARM64 import/calculation and 42
Mach-O dependency checks pass with no external absolute or missing loader links.
Licenses/third-party notices remain; scientific credits include the Rice notice.
macOS minimum is 14 for the pinned NumPy ARM64 wheel. Full relocated sealed
OpenMM execution/native form acceptance is next. `DynamicsPilot.tsx` adds a
collapsed form in the existing Trajectories panel with real runtime status,
compute/cancel/history and saved-trajectory opening. No viewer/interface redesign.

All 268 Python contracts and 73 frontend tests pass; TypeScript compilation passes.
A shared cancellation regression now preserves a completed transaction/results
when the worker finishes while cancellation locates its process. See
`docs/DYNAMICS_PILOTS.md`. The entire Project Metal specification remains active
and incomplete; this is a recoverable checkpoint before package acceptance.

### OpenMM packaged/native acceptance; motion and checkpoint implementation

Relocated sealed `077dc19` app discovers its own fourth scientific runtime and
completes the actual 20-step protein pilot/import/export workflow with no runtime
setting override (`packaged-openmm-workflow.json`). Actual native form then ran
100 steps / 0.1 ps on the same immutable 35-residue saved source, saved three
outputs and opened all eleven frames in the existing viewer. Separate native
cancellation job stopped before publishing outputs; original worker no longer
running. Source unchanged and app seal passes after native use.
`native-openmm-acceptance.json`, native screenshot and AX tree. Completed parent
jobs must not be resubmitted merely for further renderer/analysis acceptance.

`trajectory_metrics.py` and `trajectory_analysis.py` now implement saved Cα
RMSD/RMSF through a bounded isolated calculation and the shared research history.
Source/runner hashes, exact atom/frame correspondence, optional proper rigid fit,
population-moment convention and no inferred physical times. Shared write
reservation prevents overlap with active local jobs. Five analytic geometry and
four actual child-process/persistence contracts pass. On the existing real native
pilot, raw metrics match original ChimeraX directly and fitted RMSD/RMSF differ
by at most 9.5e-13 / 1.8e-15 Å (`trajectory-motion-reference.json`). This is narrow
numerical agreement, not biological flexibility or equilibrium validation. A
collapsed native panel exposes fitting, per-frame RMSD, per-residue RMSF and
complete JSON export. Native/packaged motion acceptance remains next.

Pilots now also save original OpenMM binary checkpoints with internal stochastic
integration state. Updated common-job workflow, exact archive bytes and same-
platform restoration pass (`openmm-checkpoint-workflow.json`,
`openmm-checkpoint-restoration.json`): positions/velocities/time restored exactly,
then two independent contexts have zero measured differences after five steps.
No cross-version/platform/hardware restart claim. Existing completed `077dc19`
outputs retain their original six-artifact receipts; later jobs add a seventh
checkpoint artifact with a new runner hash. All 277 Python tests pass; 73 frontend
tests and TypeScript pass. Next integration build includes motion/checkpoints.

### Relocated motion/checkpoint acceptance

Sealed `f7caaae` app discovers the bundled OpenMM runtime after relocation.
Saved motion measurement agrees with the original ChimeraX reference, preserving
the existing 11-frame / 35-Cα / 0.1 ps native pilot without rerunning dynamics.
Native fitted measurement, displayed numerical tables and complete JSON export
pass (`native-motion-acceptance.json`, screenshot and AX tree). Source and
analysis identity match the stored research entry; JSON floating transport differs
by at most 2.78e-17 Å, within the explicit 1e-12 tolerance. App signature remains
valid. Numerical table headings received scoped spacing for readability.

`packaged-openmm-checkpoint.json` and `packaged-openmm-checkpoint-restoration.json`
verify the relocated runtime's seven-artifact export and exact same-platform
checkpoint restoration, followed by zero measured difference in two independently
continued contexts. This does not yet expose shared-job checkpoint continuation.
The next memory experiment computes the full 320-residue AF2 gradient directly
without retaining a separate standalone prediction executable, with the governor
still enabled at 8 GiB. No production resource limit or model behavior changed.

### Shared checkpoint continuation; bounded AF2 memory result

`dynamics_continue` now forks a completed pilot through the common job queue.
`dynamics.py` pins the parent receipt, original input and seven artifacts;
`dynamics_runner.py` restores the original binary checkpoint with strict host/OS/
runtime provenance and checks the recorded final state before any step. No
repreparation, minimization, reseeding, velocity or time reset occurs. A separate
trajectory and continuation receipt retain absolute times, parent/checkpoint
identities and exact snapshot bytes. Chained continuation, cancellation, source/
parent preservation, corruption refusal and project ZIP export are covered.
The native existing pilot panel offers continuation with the chosen additional
step count; older pilots lacking provenance remain preserved and unavailable
for this action. `docs/DYNAMICS_PILOTS.md` documents the contract.

Actual 35-residue 20-step parent followed by 20- and 10-step continuations matches
an independently restored and continued original OpenMM CPU context with zero
measured position, velocity, time and potential-energy difference at both stops.
`openmm-continuation-workflow.json`. A deliberately corrupted private snapshot
fails with no partial records; parent untouched. This is narrow numerical and
workflow evidence, not equilibrium or biological validation. 282 Python and
73 frontend tests pass; TypeScript passes. Relocated/native continuation acceptance
is next; no previous completed model campaign was rerun.

The 320-residue full AF2 gradient still exceeds the enabled 8 GiB governor when
computed directly without first running or retaining a standalone prediction
executable. Upstream rematerialization remains enabled, compiled cache size one.
The actual Metal failure reports 8.8 GB process footprint / 8.4 GB live MLX arrays
and 0.3 GB machine free. `af2-320-metal-gradient-only.json` and updated memory
investigation retain this negative result; no CPU fallback or model/precision/
filter change. Larger Metal profiles remain disabled. Further progress requires
validated allocation/liveness or recomputation work; increasing limits is not
supported by this experiment.

### Native continuation acceptance and new exclusive BindCraft2 directive

Relocated signed `88a64e9` passes real checkpoint continuation/reference, snapshot
corruption refusal and exact export (`packaged-openmm-continuation.json`). Native
button then completes a distinct 100-step segment, automatically opens its eleven
frames and measures absolute 0.020–0.120 ps times in the existing viewer. Parent
snapshot bytes and app seal remain intact. `native-checkpoint-continuation.json`,
AX and screenshots include readable motion table headings. No further OpenMM or
Vina work is active.

The user supplied Project Metal Ω on 2026-10-19, explicitly restricting the
current task to complete authentic BindCraft2 integration. Existing unrelated
engines remain preserved. New priority is upstream-compatible campaign recovery,
filter/rank operations, full outcomes inspection, parity accounting and packaged
BindCraft2 acceptance. Core accepted 175-residue ensemble evidence is reused; no
completed model campaign will be rerun merely to re-establish existing evidence.

### BindCraft2 Ω: real recovery, original filter/rank and complete stage readings

`campaign_recovery.py`, `bindcraft_cpu.py` and native `bindcraft_resume` continue
an interrupted/failed/cancelled campaign using the original profile, model hashes,
JAX versions, numerical adapter, seed, scientific settings and remaining budget.
Live old process groups are refused. Prior job/settings/runtime/log receipts and
complete output hashes are archived; claimed interrupted trajectories stay spent
under the original upstream CampaignProgress behavior. Progress parsing resets at
a new execution marker. This is next-trajectory recovery, not optimizer checkpoint
restoration. An actual 24-residue CPU recovery campaign records trajectories
1, 3, 4 after cancelling claimed trajectory 2, then completes its original four-
attempt budget with zero accepted designs under original filters.
`bindcraft-campaign-recovery.json`. No original completed model campaign rerun.

`campaign_review.py` / runner execute authentic upstream `refilter_campaign` and
`rerank_campaign` on distinct byte-pinned snapshots and save original tables and
review provenance in the shared research database/project archive. Native
`CampaignResults.tsx` exposes all recorded trajectory/refold/rank rows, original
CSV export, metric ranking and saved-filter review. Missing metrics remain
unreported, and omitted filters are disclosed by upstream. Post-hoc passing rows
never acquire original campaign acceptance. Existing imported coordinate IDs are
reused across later ranking batches, with asset-integrity checks.

On the existing genuine accepted 175-residue ensemble case, all 1 / 3 / 1 stage
rows are read and both review results exactly match direct original functions
(`bindcraft-campaign-review.json`). The filter review keeps three rows and explicitly
reports unrecorded Receptor_Chains_Contacted; the original one-design acceptance
is preserved. No model inference was rerun for this review. Source/parent outputs
and raw metric values remain unchanged. 295 Python tests pass; frontend copy
assertion was updated to the equivalent scoped execution disclosure. Native
packaged recovery/review controls are the next acceptance step.

### Original property presets and native packaged vertical slice

Native `097a912` reads the genuine prior 1/3/1 trajectory/refold/accepted case and
executes original upstream ranking/filtering with its own bundled CPU runtime.
Native buttons create recorded reviews and show actual results; original
acceptance remains unchanged (`packaged-bindcraft-review.json`,
`native-bindcraft-review.json`, screenshot/AX). The relocated runtime also runs a
new actual 24-residue two-attempt cancellation/recovery case: interrupted claimed
trajectory 1 stays spent and trajectory 2 executes under original filters
(`packaged-bindcraft-recovery.json`). No CPU/runtime development override.

To close the full native packaged acceptance gap, one bounded original-ensemble
repeat was launched through native controls: job
`ce12298c-739e-47d3-bb9c-91794ff80ec5`, isolated root
`../validation/bindcraft-campaign-review`. Five original design multimers, two
held-out monomers, seed 42, full hPDL1 115 + binder 60, request one accepted design,
maximum three attempts. Interpreter, all checkpoints and source belong to the
relocated app; no inference fallback. Genuine Metal optimizer events are being
emitted. `native-bindcraft-ensemble-job.json` and screenshot record launch, not
completion. Do not duplicate, cancel or restart this acceptance computation.

Additive property controls now call original `campaign_over_presets`; they do not
merge property values behind explicit already-expanded modality overrides. All
nine property presets, a combined selection and VHH/humanize exactly match
original resolution and pass original input/feature preflight. VHH/mixed-topology
is refused by original conflict logic before creating a job. Preset hashes and
selection are retained. These are configuration/input checks, not property-
specific gradient, generation or biological validation. Default no-property
preparations remain identical. `bindcraft-property-presets.json`.

300 Python tests, 73 frontend tests and TypeScript pass. Property source/UI changes
are not in the active `097a912` bundle yet; packaging is deferred while the real
full ensemble calculation runs. `BINDCRAFT_FEATURE_PARITY.json` inventories every
shipped modality/property and explicit campaign-setting name with scope/status.
Full option/modality parity remains incomplete, including dynamic loss/metric
parameters and unavailable native modality/sequence-target routes.


### Extended formats and unbound-output transport

Original large_binder and multidomain presets now have additive native format
controls and immutable input preparation. Real upstream preflight/ensemble
resolution passes on explicitly identified 12-residue hPDL1 derivatives at
250/120 binder residues (288/160 padded). No extended-format model trajectory
is claimed. An explicit fixed-length CPU320 profile requires Apple Silicon
with at least 24 GiB; the measured CPU320 forward/gradient evidence supports
this bounded experimental route, without extending the failed Metal320 limit.

Unbound binder outputs now require explicit original CIF roles and exact
accepted-row sequence correspondence. They cannot satisfy missing bound target
outputs or inherit target coordinates/interface confidence. Own-coordinate
pLDDT remains distinct from parent-complex raw metrics. Seven synthetic
protocol tests exercise these contracts; no conformational design is claimed.
312 Python tests pass. Existing 73 frontend tests/TypeScript passed after format
controls. The original native ensemble job ce12298c continues refinement; no
competing model job or app rebuild was started.


### Original conformational and core profile integration

induced_fit/fold_switch now resolve their implicit binder layer through the
actual upstream resolver. Their original losses, 5 Å interface/0.6 TM-score
acceptance checks, bound/unbound schedules and final-state requirements passed
real input/state preflight. A separate single-model CPU profile is fixed-length,
one observed target/one binder copy, at most 192 aggregate padded residues
(96 counted twice conservatively). No conformation-generating trained-model
trajectory is claimed. Native imports require both accepted states and keep
unbound confidence separate. Exact evidence: bindcraft-conformational-presets.

Original benchmark core selection is additive in the current form and is
resolved below modality/properties and explicit campaign fields. Source-based
binder and VHH/humanize precedence/preflight passed; reserved default/reference
core names are not falsely offered as layers. bindcraft-core-profiles.json.
323 Python tests, 73 frontend tests pass; TypeScript checked. These source
changes are not in the running 097a912 bundle; no competing model was started.


### Dynamic source feature inventory

The pinned original runtime reports 239 known settings, 37 registered losses
and 79 filter metrics with actual parameters/defaults. Nine source commands
and literal flags are inventoried separately from native equivalents. Every
entry retains explicit exposure/scope; source presence is not full validation.
The reproducible inventory script verifies the pinned source manifest before
writing strict JSON. Full port completion remains false.


### Immutable FASTA target path

Saved canonical sequences can now be selected as native campaign inputs. Their
FASTA bytes, plain sequence hash and source identity are preserved separately
from observed coordinate inputs. No fake structure is produced. The original
disordered-target crop sampler and validation flanks were exercised on the
official hPDL1 sequence as technical QA, without claiming biological disorder.
Actual source settings/loss cutoff/target-pLDDT defaults and unresolved atom
masks passed, with exact source-index sequence matches on two seeds.

A dedicated CPU192 fixed-length binder/peptide profile is exposed, with one
FASTA target and no observed-residue hotspots, mixed targets or multiple crop
states. Full trained-model sequence-target validation is pending. Predicted
crops must match the saved sequence at exact original positions and retain
predicted-coordinate provenance. Repeat/recovery/export preserve FASTA inputs.
331 backend tests, 73 frontend tests and TypeScript pass. No app rebuild or
competing high-memory job occurred; ce12298c remains in annealing.


### Original scientific option exposure

An additive advanced JSON field now resolves explicit original scientific
settings beneath the native campaign controls, using actual upstream preset
precedence and strict load_settings/metric validation. Unknown keys, metrics
and nested parameters fail before a job is created. Input/path/lifecycle/model
controls remain separate; measured recycle/step/subbatch/checkpoint envelopes
and custom-state limits remain enforced. External filter files and implicit
filter disabling are unavailable. Custom recipes retain explicit option hashes
and are not labelled as original-default-filter campaigns.

Three real upstream comparisons/preflights (recycles/dropout, ProteinMPNN
settings, bias/loss parameters) and three source refusals passed. Every QA case
kept default acceptance filters unchanged; no threshold was relaxed to obtain
a result. 337 Python tests and 73 frontend tests pass, with TypeScript checked.
Full model-specific option parity remains unverified. ce12298c remains the
sole model job in annealing; the active app is unchanged at 097a912.


### Original coordinate scoring on saved complexes

The existing native outcome inspector now calls original score_design on an
immutable review snapshot. Scope: 1–4 accepted complex CIFs, one model and at
most 384 residues each; explicit original binder/target roles required. Site
metrics whose source-to-written site mapping is not reconstructed are omitted.
Missing unbound/confidence evidence is unavailable, and recorded validation
model readings remain separately labelled. Original acceptance is unchanged.

The genuine accepted 175-residue hPDL1 complex yields 57 exported fields whose
source-computed values exactly match a separate direct original invocation.
All source outputs remain unchanged and the project ZIP contains the review
and receipts. bindcraft-campaign-scoring.json. 342 backend tests, 73 frontend
tests and TypeScript pass. Native full-ensemble job ce12298c remains running,
near the end of annealing. A live vmmap sample reports 9.1G process peak physical
footprint; system-wide GPU sample 93% cannot be attributed exclusively to it.
