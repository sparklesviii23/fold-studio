# Qwen RNA engine — checkpoint, 15 November 2026

Native secondary prediction, numerical training/evaluation and the app path are implemented. **This small pilot has poor accuracy and loses to every baseline below.** No paid compute, model download, base-layer unfreezing or automatic promotion occurred. A 5.53 MB reference-data archive was acquired. Preserve all existing worktree changes and older checkpoints.

## Worktrees and recovered engine

Main: `/Users/vii/Documents/FoldStudio-MetalPort/fold-studio`, branch `project-omega/ultimate-completion`, initially `2862128`. It already had dirty Cell Explorer, Virtual Cell, native admission, app and documentation changes. This integration adds Qwen files and additive navigation/dispatch/resource/registry edits. Do not reset unrelated work.

Research: `/Users/vii/.codex/worktrees/predictive-cell-research/fold-studio`, `codex/predictive-cell-stage2`, initially `a56a766`. Read its `AGENTS.md`, `docs/QWEN_CELL_PREDICTOR.md`, `QWEN_CELL_HYBRID.md`, `CELL_AI_GROUNDED_TRAINING.md` and current checkpoint. Its ten dirty training/UI files were left untouched. Inventories: `reports/qwen-rna/{main,research}-status-at-integration.txt`. Its existing training workspace/code remains in that worktree; it was not silently merged into the main app.

Shared live library: `/Users/vii/Documents/FoldStudio-MetalPort/validation/bindcraft-fab-amme-native`. It is real research, never disposable. Paths below are relative to that library:

| Asset | Path |
|---|---|
| Base Qwen2.5-Coder-3B-Instruct | `engine/models/qwen-cell/Qwen2.5-Coder-3B-Instruct` |
| First direct-Qwen adapters, predictions and receipts | `gpu_tasks/658cf0d2a1584e34b7ee0aab5718e799/outputs` |
| Embedded-expert hybrid checkpoints | `gpu_tasks/dafcf258a2ee4ded918f293574071858/outputs` |
| Expanded hybrid and evaluation | `gpu_tasks/97f9f92971d64821a19a4319bdcc5ef4/outputs` |
| Grounded selected weights and final evaluations | `gpu_tasks/dfb6534e0b404ae0be906f5f827de952/outputs` |
| Grounded frozen manifest/data | `virtualcell/training/experiments/d7c94cee78eb4bcda08d0f94b55c074b/{SPLIT_MANIFEST.json,cloud-inputs}` |
| New folding weights and full neural benchmark | `engine/models/qwen-rna/pilot-v1` |

Base revision `488639f1ff808d1d3d0ba301aef8c11461451ec5`; all four artifact hashes matched the saved official receipt and are recorded in the new `checkpoint.json`. Existing provider terms apply; do not redistribute these weights as unrestricted assets.

`scripts/reproduce-qwen-cell.py` reloads the original model from the research worktree. New MPS inference reproduced **26 × 2,132 saved values exactly, maximum difference 0**, development MSE `0.009166055037339011`. Evidence: `reports/qwen-rna/recovery/{reproduction.json,reproduced-predictions.npz}`, full `recovery.log`. The source data is `/Users/vii/Documents/Codex/2026-11-05/files-pasted-by-the-user-fold/outputs/stage4/qwen-cell-data`. The exact arguments/weights are recorded in `reproduction.json`.

That engine predicts calibrated K562 paired CRISPRa **mean gene-expression changes**, using known measured single-activation responses; it does not fold RNA. Later hybrids contain a genuine frozen RNA-response expert and full-gene correction heads. Grounded study results remain preserved: pair development MSE improved 5.47% versus that internal expert, but this is reused development evidence. Ridge won final inhibition; Qwen drug branches selected epoch zero. Only A498, not SW48, appears in the scored context holdouts. No whole-cell or RNA-sequence-to-cell behavior was established. Consumed cloud attempts must not be resubmitted.

## Architecture and contracts

| Integration | Responsibility and I/O | Runtime/evidence | Verification |
|---|---|---|---|
| `scientific/qwen_rna_model.py` | Exactly one token per nucleotide → local Qwen hidden states → symmetric scientific pair/unpaired heads. Compact control uses two 1D convolutions. | Existing `runtimes/gbcell`: Torch 2.14.1, Transformers 4.57.6. Rank-8 query/value adapters in final two layers; no prose parsing. | Genuine tiny Qwen gradient/freeze/reload test; real selected-weight reload reproduces complete matrices exactly. |
| `qwen_rna_contract.py` | 8–128 ACGU bases → canonical nested fold, pair marginals, base/region uncertainty. Public indices **1 based**. | Standard library, maximum-weight noncrossing decoder, ≥3 unpaired hairpin bases; threshold chosen on validation. | Position, invalid input, probability and decoder tests. |
| `qwen_rna_runtime.py` | Owned offline child, immutable request/result, existing job updates, 180 s limit. | External qualified Torch environment, local Safetensors only; no network/install fallback. MPS qualified; CPU performance not qualified. | Real asynchronous pretrained inference and installed worker checks. |
| `qwen_rna.py`, `qwen_rna_actions.py` | Existing `jobs` table and `jobs/<uuid>`; exact inputs, phases, failures and logs; explicit idempotent Library save. Later outcomes stay separate. | Bundled standard-library supervisor and `qwen_rna_install.json` local receipt. | Project isolation, tamper refusal, outcome preservation and native admission tests. |
| Existing `rna_lab_fold.Builtin` | Optional check of identical sequence → independent MFE fold, energy in kcal/mol, pair disagreement. | Reduced Turner nearest-neighbour solver, `rna-lab.fold/1.0.0`, 37 °C. | Existing RNA Lab validation and matched 24-case comparison. |
| Existing `virtual_cell_registry.CAPABILITIES` | Declares `qwen.rna.secondary`: input/output, runtime, evidence, limits and app routes. | Secondary prediction, not a cell-transition model. | Registry/native/resource closure checks. |

`fold.qwen-rna-result/1` includes the exact sequence, dot-bracket fold, all nonzero canonical `[i,j,p]` marginals, per-base partner/unpaired probability/entropy/confidence, 10-base regional entropy, optional reference accuracy, decoder version/threshold, weight/split hashes, software versions and contributing engines. No atomic coordinates, Qwen free energies or cellular outcomes are invented. `sha256` seals every field except itself.

The numerical head is trained with categorical partner cross-entropy (self = unpaired). Inference symmetrizes partner probabilities and conservatively projects pair row mass to ≤1; the remainder is unpaired. These are **uncalibrated constrained marginals**, not a thermodynamic ensemble or experimental confidence intervals. `reports/qwen-rna/uncertainty-evaluation.json` reports partner NLL, categorical Brier, ECE and calibration bins.

Actions:

- `qwen_rna_start {projectId,sequence,reference?,engine,verify:false}` returns an existing-style job. `engine` is `qwen_adapter`, `qwen_frozen` or `compact`.
- `qwen_rna_run {projectId,id}` polls its phase/result. Generic `job_cancel` checks the recorded process identity before stopping it.
- `qwen_rna_save {projectId,id,name?}` creates an analysis linked to that exact run/hash, `hasAtomicCoordinates:false`; repeat saves return the same item.
- `qwen_rna_history {projectId}` lists project experiments.
- `qwen_rna_measure {projectId,id,structure,source}` saves an unverified user outcome independently, never mutates predictions or trains weights.

Native mode never imports/calls a folding engine during prediction. Verification is explicitly opt-in: a **rule-based**, versioned policy checks when Qwen's mean partner entropy >1 bit. It is not a learned tool router. The baseline structure/energy and disagreement are added separately, with exact inputs and engine version; native probabilities/fold stay unchanged. No specialist targets were used for training. Cloud Mode refuses `qwen_rna_start` without a local fallback.

## Frozen data and actual benchmark

Source: authors' [ArchiveII release](https://github.com/marcellszi/dl-rna/releases/tag/Data), archive SHA-256 `a8661c99b49563826f9bef88767b5d8db2907cb8392793d5c39be7a4173c07de`; preserved at `reports/qwen-rna/source/archiveII.tar.gz`. Cite Szikszai et al., Bioinformatics 2022, doi:10.1093/bioinformatics/btac415, and underlying ArchiveII sources. These include comparative/reference annotations; do not call every label a direct experimental measurement.

Frozen before training: `reports/qwen-rna/data-v1/split.json`, seal `122735c1f4c10edacd18db561ef629a0bf3eeec1e416793c2f695dec16a16f56`. **48 5S train, 16 tRNA validation, 24 SRP test**, 24–128 nt, no truncation. Entire families stay together. Exact sequence duplicates are filtered; cross-split SequenceMatcher similarity ≥0.8 and equal-length reference pair F1 ≥0.8 are excluded before selection. This lightweight screen does not replace family labels/alignment tools. Invalid/noncanonical/pseudoknotted annotations are excluded with source identities recorded. This is a small compute-bounded pilot, not full ArchiveII. Qwen pretraining contamination is unknown.

Three epochs, seed 20261115, AdamW; Qwen heads/adapters LR 0.0003, compact LR 0.001. Validation exact pair F1 selects epoch and decoder threshold. `selection.json` is sealed before test scoring. Both selected and final-step weights remain. Arms share pair-head architecture/schedule, but adapter initialization consumes RNG before head initialization: **initial head tensors differ**. One seed and this confound prevent attributing differences solely to adapters/pretraining. Correct common initialization in a new preregistered study, then use a fresh final comparison; do not tune on the observed SRP outcomes.

| Method | Held-out mean exact pair F1 ↑ | Trainable parameters | Selected epoch |
|---|---:|---:|---:|
| Native Qwen + adapters | 0.045416 | 213,322 (102,400 inside Qwen) | 2 |
| Frozen Qwen + trained head | 0.088871 | 110,922 | 3 |
| Compact RNA-only control | 0.107464 | 62,218 | 2 |
| Current RNA Lab baseline | 0.608029 | 0 | — |
| ViennaRNA 2.7.2 | 0.583242 | 0 | — |

Same 24 exact sequences/references, canonical nested predictions, no position tolerance/alignment rescue. **Native Qwen loses all comparisons.** The built-in baseline's narrow lead over ViennaRNA on this subset is not a general ranking. Complete case-level folds, missed/extra pairs: `reports/qwen-rna/baseline-comparison.json`. Full native probabilities/worst cases: checkpoint `*-test-predictions.json`, `benchmark.json`. No checkpoint was promoted as validated.

Both numerical baselines use 37 °C isolated-RNA assumptions. Reference annotations do not provide uniformly matched assay temperature, modifications or intracellular conditions; this is a matched sequence/reference protocol, not a matched physiological experiment. The app offers the new Qwen path explicitly as a research candidate; the prior thermodynamic and cell-response engines retain their separate responsibilities.

Whole training/evaluation completed in ~85 s on Apple M4 Pro MPS. Compact optimizer/validation ~8.26 s; frozen-head stage ~5.31 s; adapter stage ~38.56 s. Base load/frozen-feature caching are outside those per-arm times: use full `events.jsonl` and `training-v1.log` for accounting. Mutation counters of frozen Qwen tensors were unchanged, and original base files matched official hashes. Safetensors/tensor-name receipts record changes. No result justified base-layer unfreezing.

Opt-in verification triggers all 24 checks and exposes disagreements in all 24. This checks disagreement, not proven error without a reference. The independent baseline is more accurate on average; verified workflow does not relabel its output as native Qwen or claim improved native accuracy. Probability calibration is not established.

## Reproduction and environment

Run from the main repository; exact absolute training command/environment are in `reports/qwen-rna/TRAINING_COMMAND.json` and `BUILD_COMMAND.json`. Output directories must be new; never overwrite prior evidence.

```bash
../runtimes/gbcell/bin/python -B scripts/train-qwen-rna.py \
  --archive reports/qwen-rna/source/archiveII.tar.gz --data /tmp/qwen-rna-new-data
../runtimes/gbcell/bin/python -B scripts/train-qwen-rna.py \
  --data reports/qwen-rna/data-v1 \
  --base ../validation/bindcraft-fab-amme-native/engine/models/qwen-cell/Qwen2.5-Coder-3B-Instruct \
  --out /tmp/qwen-rna-new-checkpoint --epochs 3 --maximum-seconds 1500
../runtimes/rna-vienna/bin/python -B scripts/benchmark-qwen-rna.py \
  --checkpoint ../validation/bindcraft-fab-amme-native/engine/models/qwen-rna/pilot-v1 \
  --data reports/qwen-rna/data-v1 --out /tmp/qwen-rna-baseline-report.json
../runtimes/gbcell/bin/python -B -m unittest tests.test_qwen_rna tests.test_native_allowlist
node node_modules/vitest/vitest.mjs run --configLoader runner src/lib/qwenRna.test.ts src/lib/rnaLab.test.ts src/lib/jobs.test.ts
node node_modules/typescript/bin/tsc -b
python3 scripts/check-scientific-package.py --sources
```

Context Mode's local subprocess had MPS available here; ordinary shell subprocess reported it unavailable. Recheck runtime/device before another experiment. No paid run is authorized by this checkpoint. The CLI is offline-only and preserves existing outputs. Packaging uses the guarded `bash scripts/build-local-app.sh` with existing Node 22/Cargo/Rustup toolchain in `BUILD_COMMAND.json`, only when the app/workers are idle; retain one installed app.

`qwen_rna_install.json` pins local absolute paths and checkpoint hash; **this is a local installation contract, not portable distribution**. Another machine must explicitly qualify its own existing Torch runtime and models. The base is shared outside the app bundle. Never silently install dependencies, download a replacement base, or fall back to another predictor under the Qwen label.

## App routes, limits and next action

**Biological Models → Model workbench**: Qwen checkpoint/benchmark card. **Genome & RNA Engineering → RNA Engineering → Open RNA Lab**: existing RNA Lab destination. **RNA Lab → Predict**: enter sequence, Predict fold, inspect bases/pairs, compare reference, Save result. Reference/engine settings and provenance/history are drawers; specialist verification is off by default. The base inspector collapses independently; no top-level sidebar destinations were added.

**Open fold** opens that exact run in **Molecular Viewer**, clearly labelled 2D secondary topology with no atomic coordinates. Research Library → Explore reopens the same run/version. Saved coordinate structures keep the existing atomic viewer and Add to Cell paths. Do not manufacture coordinates or send an unsupported secondary fold into cell dynamics.

Existing Ensemble, folding kinetics and Translation remain separately declared solvers, not automatically Qwen evidence. Exact kinetic enumeration accepts 8–24 nt; never silently substitute its demo for a saved long RNA. HeLa EM geometry, Hep G2 baseline and K562 perturbations are distinct contexts.

Continue in milestone order:

1. **Secondary prediction:** broaden family coverage; freeze a fresh family/structure-aware final split before learning. Fix common head initialization, compare multiple seeds/matched budgets, calibrate on validation. Current compact and thermodynamic baselines win. Keep present test outcomes out of tuning and preserve every checkpoint.
2. **3D:** need licensed/versioned sequence–coordinate training corpus, chain/modification mapping, geometry head and homology-aware holdouts. One local 1EHZ reference and prior specialist receipts are insufficient. Existing specialist coordinates are not native Qwen 3D predictions.
3. **Design:** need target-conditioned sequence decoder or explicitly declared search, source-labelled supervision, native refolding, target success/coverage/diversity metrics and frozen target-family holdouts. No inverse-trained checkpoint exists here. Coding RNA also needs frame/version-aware existing translation/protein analysis; random canonical sampling is not learned Qwen design.
4. **Sequence → cell outcome:** need one exact RNA, defined cell line, matched measured persistence-time or partner-engagement assay, units and controls. Existing calibrated gene-activation response is a different contract. Existing molecule/timeline/result links remain; no sequence-dependent binding/decay parameter is invented.
5. **Experiment learning:** exact inputs, failures, predictions/checks/disagreements and separate later outcomes already persist. Curation, challenger training and preservation gates precede promotion. No automatic history ingestion or learned router is claimed. Keep phage work in Biological Models → Phage & biology research.

## Context Mode and verification

Context Mode remained enabled for recovery, source/data audit and long logs. `ctx_doctor` passed **every row**, version 2.2.0: Node, host config, hooks, MCP, worktree, database, index, enforcement and shell. Fresh session: `ctx_resume`, then `ctx_doctor` / `context-mode doctor --agents codex`. Use `ctx_execute` for bulky files/logs/datasets; index recurring sources once, retrieve original equations/units/failures with `ctx_search`. No Context Mode configuration or tool-loading changes were made.

Initial tests caught the existing hyphenated job UUID contract and a temporary Vite config write through symlinked dependencies. Repaired; failed logs remain, passing logs use `*-fixed.log`. Use Vitest `--configLoader runner`. Focused checks: **14 backend/native-admission, 12 interface**, TypeScript and source closure pass. Real pretrained asynchronous native inference and exact idempotent Library save pass; `native-smoke.json` and isolated `smoke-library` contain evidence. No test writes went into the live library.

Desktop build/click-through findings are appended after qualification. Resume from the final handoff, inspect result/model seals, then strengthen secondary prediction before broadening claims.

### Desktop runtime correction

First native launch showed workers blocked in SQLite file opening and the first external-venv inference blocked before Python initialization completed (`getpath_readlines` / `pyvenv.cfg`), before any model computation. Samples and cancelled run evidence are retained in `reports/qwen-rna/native-*-sample.txt` and the isolated Library. No scientific job was killed as a workaround: only owned blocked RPC initializers were stopped, and the queued inference was cancelled through its ordinary Stop action.

The app was relaunched with the existing guarded `scripts/open-local-app.py --data-root <isolated-library>`; native catalogue, existing Library and local compute then loaded. Inference now uses **bundled CPython 3.12 with explicit qualified existing `gbcell` and `runtime-boltz` site-package paths** recorded in `qwen_rna_install.json`. Torch 2.14.1 / Transformers 4.57.6 / MPS imports passed through this bridge. Python startup variables are sanitized only for this owned child. No security settings, macOS privacy database, model weights or package installations were changed.

An independent bundled-Python supervisor bounds interpreter startup/imports as well as computation (180 s plus 5 s termination), and generic cancellation owns the supervisor's process group. The numerical child also retains its alarm. This closes the original gap where a venv startup stall occurred before the in-process alarm. Runtime paths remain an explicit local dependency, not a portable app promise.

Timing qualification: the supervisor's **own OS/Python bootstrap is outside its Python timeout**. The completed first desktop run took **154.09 s wall time**, including cold initialization, versus **16.25 s inside the numerical worker**. App badges show the latter, not end-to-end latency. The child timeout begins once supervisor Python starts. Do not claim an absolute 180-second OS-level wall bound. Samples show kernel file opens; TCC logged an AllFiles preflight denial, but this does not by itself establish that Full Disk Access is needed. The run completed without changing privacy/security settings. A host-level bootstrap deadline and more precise cold-start status remain follow-up work.

The RNA Lab grid now aligns content at the top instead of distributing empty space across rows. Catalogue arrival no longer overwrites input typed while metadata was loading. Backend/native-admission and interface tests are now 14/12 passing after these corrections; full bridge logs are retained.

### Completed desktop walkthrough

Installed desktop run **`6eb9b678-8220-44d7-af02-1665be527ff7`** completed through the actual native RPC admission path on MPS, Torch 2.14.1 / Transformers 4.57.6. External engines and teacher signals are empty. Its full pair matrix reproduces the frozen benchmark exactly (maximum difference **0**). It emits 21 valid nested pairs for the deterministic 105-nt held-out SRP example; this representative failure has F1 **0**, 30 missed and 21 extra pairs, explicitly shown in the app.

Entered sequence and reference → Predict → inspected bases G1/G2 and selected partner C98 → toggled reference overlay → Save result → Open fold → Research Library → Explore the saved result. Both reopen paths showed the same run ID and prediction. Saved Library item **`542e2796-04f7-404b-9fa3-eef8db674efe`**, SHA-256 `344c243c941820219d1ba8b3c118589899e16b2a7c4b8feeab84e730eaa261ff`. Exact receipt: `reports/qwen-rna/desktop-run-final.json`; test Library: `reports/qwen-rna/smoke-library`. No research/test records were inserted in the live Library.

Visual inspection covered the default **1440 × 960** laptop window and native full screen, sidebar open/collapsed, one focused base inspector, native/reference topology and pair matrix. Both views keep the same immutable molecule/experiment; atomic coordinates are explicitly unavailable. The Model workbench displayed all five actual F1 values (4.5%, 8.9%, 10.7%, 60.8%, 58.3%) and an operational Predict entry. A final visual correction adds reference outlines to the probability matrix as well as the topology view. Native schema: `docs/schemas/qwen-rna-result.schema.json`.

Eight installed Qwen scientific resources matched source byte-for-byte; `installed-resources-final.json` records the check. Packaging, signatures and the 166-module closure passed. Full build evidence is retained in `build-*.log`; earlier failed/stalled attempts and cancellations remain visible, rather than being relabelled successes. The last app packaging log is `build-release.log`.

Final visual pass after that packaging confirmed reference outlines in the matrix and inspector collapse/reopen. Original live Library `/Users/vii/Documents/FoldStudio-MetalPort/validation/bindcraft-fab-amme-native` and project `fef08806-d3ac-4846-8143-60a76b8c1e63` are restored. The existing **Modal/Cloud Mode is preserved**: choose **Settings → Compute servers → This Mac** explicitly before native local Qwen execution. Read/open/save of previous results is still available in Cloud Mode; scientific execution never falls back silently.

Known navigation caveat: changing project while an RNA run is open can retain its previous run reference in app state. The backend refuses cross-project access. Open RNA Lab from Genome & RNA Engineering, or reopen an item in the new project's Library; clear the RNA route state on project change in a follow-up UI patch. No cross-project values are returned. Read `reports/qwen-rna/HANDOFF.md` / `HANDOFF.json` for the concise final checkpoint.
