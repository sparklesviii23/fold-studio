# RNA Design checkpoint · 16 November 2026

Source and local runtime checks pass. Installed UI and real Modal checks are incomplete.

- Entry points and contracts: `../../docs/RNA_DESIGN.md`, `../../AGENTS.md`.
- Full benchmark and verdict: `BENCHMARK.md`; exact file and model seals: `HANDOFF.json`.
- Default: Solver. At 32 candidates / 2 s on 27 held-out targets × 2 seeds: Solver 52/54, Qwen + constraint repair 15/54, Hybrid 51/54. Direct Qwen: 0/54. No overall Qwen quality, speed, or cost benefit was shown.
- Strict v2 split: 24 train / 9 validation / 27 test, 6 coarse families. Mirrors, permutations and unary-loop relatives stay together. Fresh strings exclude all v1 targets. Protocol SHA-256: `3a65f2487c5ac486e95adaa06548948adfe75a420dd8dbdc78eeb9353ccb8aa0`.
- v1 stays as development evidence. Its split did not merge mirror/unary relatives. Do not use it for a strong family-generalization claim. Do not tune on either observed test set.
- New inverse head: 271188 trained parameters on frozen Qwen features. Initial, selected and final weights: shared Library `engine/models/rna-design/pilot-v2`. The prior inverse head and Qwen folding/cell weights remain. Base hashes and frozen tensor counters passed. The research worktree dirty inventory is unchanged.
- Checks: 32 backend tests, 12 existing interface tests, TypeScript, frontend build and source resource closure pass. Full logs stay here.
- Real local source jobs used the installed Python. The 12 nt and 38 nt examples each returned 3 qualifying candidates. Two distinct candidates from each were saved and reopened with the same seals. Signal cancellation retained 7 candidates; resume retained 24 distinct candidates. Evidence: `local-runtime.json`, `runtime-library-v3`. Generic desktop cancellation and UI comparison still need installed-app checks.
- The earlier 30 nt near-miss run is preserved in `runtime-library` and `local-runtime.log`. It was not hidden after failure.
- Modal uses the existing account/task lifecycle, 1 bounded CPU core, 2048 MiB, no GPU. Mocked tests cover import, cancellation during launch, partial recovery and resume. They do not prove real Modal operation.
- Paid workload: `MODAL_TRIAL.json`. Four sandboxes, aggregate container limit 630 s, estimated compute US$0.0332388 plus build/storage. Approval is pending. No paid run was launched. Billed cost is unavailable.
- Context Mode doctor passed all checks. No host configuration changed. Fresh sessions: `ctx_resume`, then `ctx_doctor`; large logs/data: `ctx_execute` and `ctx_search`.

## Release verification update

The first user Terminal build reached Tauri and failed because Cargo was not on PATH. Full log: `release-build-missing-cargo.log`. The build script now restores the existing recorded Cargo/Rustup/Node environment when Cargo is absent. The toolchain probe passed. Process and signature guards remain unchanged. No toolchain or model download was added.

The old installed bundle signature fails only because 3 Python cache files were added under `runtime/lib/python3.12/encodings/__pycache__`. The release seal script already removes such caches. New native workers and their children now inherit `PYTHONDONTWRITEBYTECODE=1`. Recheck the signature after the new app runs.

The agent cannot open Terminal: `Computer Use is not allowed to use the app 'com.apple.Terminal' for safety reasons.` A user Terminal rerun is pending. Wait for the prompt to return. Read `release-build.log`, then verify installed resources, signature, and the desktop workflow. The new scratch Library is in `release-scratch.json`. Original Library/project/backend are in `release-original-state.json`. No live Library setting was changed. Modal approval remains pending.

## Native workspace selector fix

The first installed build passed resource and signature checks. Scratch selection then failed because system `sqlite3 -readonly` cannot open a closed WAL library. The native selector now uses an existing-file `mode=rw` connection with `PRAGMA query_only=ON`. Header, schema and active-process guards remain. Four focused checks pass: closed WAL/DELETE access, unchanged research data, blocked writes, and no creation of missing files. Full evidence: `sqlite-probe`, `release-workspace-tests.log`.

The native fix needs the requested guarded rebuild. Read `release-build-wal.log` after the Terminal prompt returns. Repeat installed hash/signature checks, scratch selection and both RNA targets. No paid Modal run has started.

## Exact next action

1. Close fold after checking that its workers are idle. Run from a user Terminal:

   ```sh
   cd /Users/vii/Documents/FoldStudio-MetalPort/fold
   bash scripts/build-local-app.sh > reports/rna-design/build-user.log 2>&1
   ```

   The session sandbox blocks `/bin/ps`, so the guarded build cannot run here. Local preview binding is also blocked by `EPERM`. Do not remove the process/signature guard. The installed bundle was not replaced. The final existing-app observation showed `Opening your workspace…`; no Design UI run was executed.

2. Open the one current installed app with `python3 scripts/open-local-app.py`. Use a scratch Research Library. Select This Mac in Settings → Compute servers. In RNA Lab → Design, run `((((....))))` and the 38 nt held-out example `(((..(((.......)))..(((.......)))..)))`. Compare 2 distinct candidates, inspect second-model disagreements, save one exact candidate, and reopen it from Research Library. Recheck installed source hashes and signatures.
3. After explicit approval, execute only `MODAL_TRIAL.json` through the selected existing Modal account. Verify completed import, a cancelled partial result, remote resume without repeated completed work, task history, runtime usage and quote history. Keep estimates separate from billed cost. Restore the user's original Library/project/backend after qualification.
4. Update this checkpoint and `HANDOFF.json` with the actual installed and cloud evidence. Mark the request complete only after these checks pass.
