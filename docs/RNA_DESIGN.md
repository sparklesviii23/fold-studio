# RNA Design

RNA Lab → Design accepts one nested dot-bracket target. It returns distinct RNA sequences and computational folding predictions. It does not claim experimental function, atomic coordinates, or cell behaviour.

## Solver and constraints

`scientific/rna_design_core.py` validates 8–128 nt targets. It rejects pseudoknots, multiple strands, unmatched brackets, and hairpins with fewer than 3 unpaired bases. A lock string uses ACGU and dots. A sequence mask uses RNA IUPAC symbols. Optional limits set the GC fraction and maximum homopolymer length. The validator checks conflicts between locks, masks, target pairs, and GC limits. It also rejects fixed homopolymers that exceed the limit. Coupled constraints can still make a valid request infeasible. A bounded search reports that result.

ViennaRNA 2.7.2 inverse folding starts from distinct random or pair-error-guided seeds. Lowercase singleton domains keep bases fixed. A shared repair step enforces sequence domains and canonical AU, UA, GC, CG, GU, UG pairs. The search rejects remaining GC or homopolymer violations before final scoring. Duplicate sequences do not consume a new final score. Attempt limits also bound duplicate-heavy searches.

Final scoring uses ViennaRNA at 37 °C, Turner 2004 parameters, dangles=2, and noLP=false. A sequence qualifies when the returned MFE fold equals the target and all constraints pass. MFE ties can qualify. Target probability and normalized ensemble defect show competing-fold risk. Scores use kcal/mol for energies, seconds for time, and fractions for F1, probability, and defect. Public pair indices are 1 based.

The existing RNA Lab reduced Turner model checks the best candidates. It uses separate code and parameters. It is not experimental ground truth and can share thermodynamic biases with ViennaRNA. Qualification uses the primary model. Independent agreement is a separate field and a visible app label. An unchecked candidate is marked as such.

## Durable jobs and records

- `rna_design_actions.py` declares the action set. `rna_design.py` owns validation, quotes, jobs, project checks, resume, result import, and Library saves.
- `rna_design_runtime.py` runs an owned process group. The existing `job_cancel` control stops it. A supervisor bounds the child to the requested search limit plus 30 s for startup and shutdown. The supervisor's own OS/Python bootstrap remains outside this bound.
- Each run has immutable input identity in `jobs/<runId>/request.json`, a current `state.json`, sealed `result.json`, and full `execution.log`. Atomic replacement keeps the last complete snapshot. All evaluated candidates remain in the snapshot.
- The shared `<library>/rna_design/evaluations.sqlite` cache keys the sequence, target, primary model version, temperature, and settings. Independent checks also include the source hash. Resume retains seen sequences, counters, candidates, elapsed search time, and deterministic attempt seeds. A lock prevents concurrent local writers. Only candidate, time, and wanted-count limits can change on resume.
- A save stores the exact candidate, target, full scores, versions, run ID, result seal, and compute quote in an `analysis` record with `domain: rna_design`. Repeat saves of the same candidate and result seal are idempotent. A later resumed result does not mutate an earlier saved snapshot.
- Research Library → Explore opens the saved candidate snapshot. The record retains `sequence`, `structure`, `target`, and `hasAtomicCoordinates:false` for future 3D and Virtual Cell inputs. Those downstream computations are not implied by a save.

Contract: `fold.rna-design-result/1`; see `docs/schemas/rna-design-result.schema.json`. `sha256` seals every result field except itself. The input seal excludes only resume limits. The UI shows target and predicted fold side by side, missed and extra pairs, distinct sequences, and second-model disagreements.

## This Mac and Modal

Use the existing Settings → Compute servers selector. `rna_design_quote` shows hardware, uploads, limits, and the cost estimate before launch. `rna_design_start` requires the exact current quote seal. Modal also requires explicit cost approval. Cloud selection has no local science fallback.

Modal uses `gpu_tasks.py`, the active account, existing task history, cancellation, and output import. `rna_design_recipe.py` requests and limits 1 CPU core and 2048 MiB, with no GPU. A sandbox timeout bounds each launch. Candidate and total search-time limits also run in the core. No always-on worker is deployed. Only source, synthetic targets or user inputs, settings, and optional partial state are uploaded. Model weights are not uploaded for the solver path.

RNA Design inputs are uploaded as one task-specific JSON file on the existing Volume. `FOLD_INPUT_FILE` names that file inside the sandbox. Saved candidates stay outside environment variables, so large resumes do not hit the Linux per-string environment limit. Other compute recipes retain their existing input transport. The sandbox saves each candidate atomically and runs `sync /cache`. Modal also performs background and shutdown commits. See [Modal filesystem persistence](https://modal.com/docs/guide/sandbox-files). Cancellation during launch records a stop request and terminates the sandbox once its ID is available. Completed and cancelled outputs use the same import path. Failed downloads can be fetched again without relaunch. Remote resume uses a new bounded sandbox with the prior logical run's saved state; the task ID history remains attached to that run.

The estimate uses the [Modal Sandbox rate](https://modal.com/pricing), checked 2026-11-16: US$0.00003942 per core-second and US$0.00000667 per GiB-second. Image build and storage can add charges. The estimate is not an invoice. The workflow records wall/search time and available runtime usage. `billedCost` stays null when the provider invoice is unavailable. Local power cost is not measured.

The first paid trial and its approved supplement are recorded in `reports/rna-design/MODAL_TRIAL.json` and `MODAL_TRIAL_SUPPLEMENT.json`. Completion, import, save/reopen and cancellation passed. The failed large-state resume and the proposed retry remain explicit in `modal-recovery-verification/verification.json` and `MODAL_RECOVERY_RETRY.json`. Qwen GPU execution is not enabled; it needs measured evidence of a benefit first.

## Qwen research

The existing Qwen folding pilot remains unchanged. It scored 0.045416 mean pair F1 versus 0.608029 for the existing folding baseline. It does not judge design candidates.

`rna_design_qwen.py` uses the preserved Qwen2.5-Coder-3B-Instruct base to encode each dot-bracket symbol as one token. A new inverse head uses target and partner features to predict ACGU distributions. Training changes the inverse head only. The Qwen backbone and old folding heads are not changed. Initial, selected, and final inverse-head weights are separate files.

Solver successes train positive base cross-entropy. Near misses and failures contribute a small unlikelihood loss weighted by pair error. All labels name their solver source and set `measurement:false`. No measured labels are present in this pilot. Epoch selection uses validation positive-label base cross-entropy. No test score selects a checkpoint.

The three frozen arms are Solver, Qwen proposals with shared constraint repair, and Qwen proposals followed by the solver. A separate direct-generation audit disables repair. It must not be confused with the repaired Qwen arm.

`pilot-v1` is preserved as development evidence. Its exact topology grouping did not merge mirror and unary-loop relatives. Its scores cannot support a strong family-generalization claim. `pilot-v2` uses new target strings and whole coarse topology families: collapse unary loops, sort sibling and exterior stems, and merge equal-length target pair F1 ≥0.8. It has 24 train, 9 validation, and 27 test targets across 6 coarse families. The protocol seal is `3a65f2487c5ac486e95adaa06548948adfe75a420dd8dbdc78eeb9353ccb8aa0`. No prior target string is reused.

Benchmarks use 2 seeds, 2 s search budgets, and 8/32 candidate limits. A supplement runs to exactly 8 explicit final scores with early-success stopping disabled. Startup and per-target Qwen feature time are separate. `solverCalls` counts inverse-fold calls. ViennaRNA does not expose their internal energy-evaluation count. Matched explicit scores are therefore not matched total solver work. The report includes this limit.

Full reports and logs: `reports/rna-design/`. The pilot is small and synthetic. Qwen pretraining contamination is unknown. Two seeds on the same target are not two independent biological targets. Keep Solver as the app default unless verified quality, speed, or cost evidence supports a change.

## Commands and verification

Run from `fold-studio`:

```sh
PYTHONPATH=../runtimes/rna-vienna/lib/python3.12/site-packages ../runtimes/gbcell/bin/python -B -m unittest tests.test_rna_design tests.test_gpu_tasks tests.test_native_allowlist tests.test_qwen_rna
node node_modules/vitest/vitest.mjs run --configLoader runner src/lib/qwenRna.test.ts src/lib/rnaLab.test.ts src/lib/jobs.test.ts
node node_modules/typescript/bin/tsc -b
node node_modules/vite/bin/vite.js build --configLoader runner
python3 scripts/check-scientific-package.py --sources
bash scripts/build-local-app.sh
```

The `runner` config loader avoids Vite writes into a shared `node_modules/.vite-temp`. Packaging must still use the guarded build script. Do not remove its process or signature checks. This session's sandbox blocks `/bin/ps`, so the guarded package step needs a Terminal run outside this session.

`scripts/qualify-rna-design.py --root <new scratch path>` checks real local jobs with the selected Python. It saves and reopens 2 candidates for a simple and a harder target. It also signals its owned worker and checks partial recovery and resume. This is a runtime check, not an installed UI check.

Fresh sessions: call `ctx_resume`, then `ctx_doctor`. Use `ctx_execute` for long logs, data, and notebooks. Search indexed output with `ctx_search`. Preserve Context Mode and host configuration. The doctor passed all checks in this session.

Exact next action and qualification state: `reports/rna-design/CHECKPOINT.md`.

## Recovery checks (18 November 2026)
Run the focused backend suite with the command above. It includes a request larger than 128 KiB, a mocked provider upload, source extraction, and cloud-worker startup from the uploaded file. The check enforces unchanged CPU, memory, and time limits. The real local state-file smoke receipt is `reports/rna-design/modal-recovery-verification/local-file-smoke-verification.json`. UI resume uses an explicit polling revision and blocks another click while dispatch is pending. Verify automatic completion in the installed app after packaging.
Context Mode MCP tools remain available. The first 18 November doctor reported 4 modified host hooks; the attempted setup was blocked at `/Users/vii/.context-mode/setup.lock`. A subsequent doctor passed all functional checks, including hook round trip. No host setup was changed by this task. Keep the first report at `/Users/vii/.context-mode/reports/doctor-2026-11-18T13-26-43-611Z.md`. Version 2.2.0 has a 2.2.1 update warning; no upgrade was requested or performed. Fresh sessions still use `ctx_resume`, then `ctx_doctor`.
