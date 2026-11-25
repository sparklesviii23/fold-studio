# RNA Design release checkpoint

Desktop verification passed in the installed app. Real Modal CPU completion, import, save and reopen passed. Cancellation and resume remain open. Use the current build. No rebuild is required.

## Installed evidence

- Guarded build: `release-build-wal.log`. Package closure: 170 modules. Installed RNA resources match source: 9/9 in `release-resource-hashes.json`.
- Deep strict signature passed after cache quarantine and saved-result reopen: `release-signature-after-reopen.log`. The earlier check failed only for 450 added bytecode caches. Their hashes and reversible paths are in `signature-cache-quarantine.json`. No signed files were changed or re-signed.
- WAL Library selection passed in the app. Scratch Library: `release-library`; project `78483e09-5775-4f91-8444-9baca455d197`.
- This Mac / Solver stayed selected for local design. Native default layout: 1440 × 960; observed screenshots: 2880 × 1920 pixels. Candidate selection, comparison, scrolling, save and reopen passed.
- Simple target: `((((....))))`. Run `ca623920-f6ef-46bd-a373-35d6c64953c9`. Three qualifying candidates. Compared `GCAGAUUUCUGU` with `GACGUAUUUGUC`. The second model disagrees for the latter by 4 pairs.
- Simple saved record: `5ba3098f-16fc-4fe8-8bc1-8ec33d40104f`. Saved sequence: `GACGUAUUUGUC`. Reopen preserved target, scores, run ID and result seal `d8f85b360dc0537f6cfeb56dd055e792c0cdbaa35565ad4b155f250f996f7742`.
- Hard target: `(((..(((.......)))..(((.......)))..)))` (38 nt). Run `104fe9cd-b70d-4b44-a443-e3cdb54dddbf`. Three qualifying candidates from 9 evaluations and 9 solver calls. Search: 0.304 s; supervisor wall: 0.507 s. Inspected near misses with 1 extra pair and 3 missed pairs; highlights and failure reasons were correct.
- Hard saved record: `fef20a45-833b-4598-902c-8a44a6defef9`. Saved sequence: `CGGAACAGCACAUUACUGAACUCUUCUACUGAGACCCG`. Library reopen preserved the exact candidate and scores.
- Full structured evidence: `DESKTOP_VERIFICATION.json`, `RELEASE_VERIFICATION.json`, and `HANDOFF.json`. Both model scores remain computational predictions.

## Modal trial

The user approved the original 4-container trial in `MODAL_TRIAL.json`: 1 CPU core, 2048 MiB, no GPU, 630 s aggregate container cap. Compute estimate: US$0.0332388 plus a US$0.06 build/storage allowance. Three containers have completed. Billed cost is unavailable.

- Simple cloud run `9560a009-3a0f-4c99-aea4-5b7b7fe0eab4`, task `21a15c53904d4c15a712ff6ea249d03d`: 3 qualifiers, 3 evaluations, 4 solver calls. Search 0.06484707 s; worker runtime 0.106202471 s. Same inputs and sequences as local; maximum score difference 0.0. Imported, saved, and reopened record `4d8016cd-bb3f-4b1d-9a81-4541fdd6c913` in RNA Design.
- Held-out 30 nt run `1271ac85-c2fe-469e-91a5-327d0c5bf757`, task `5de12b3d4bd84b2b991c012aafab8db7`: 0 qualifiers, 128 evaluations, 196 solver calls, 7.410129092 s search. Completed near misses imported. Keep this negative result.
- Cancellation input run `324e25c9-3a32-4cb4-9003-ff47d7a7d343`, task `30fe6b04adbc47ca9d72ee524ebb39d9`: 20 qualifiers from 26 evaluations in 0.80980557 s. It completed before cancellation. Recovery is not yet qualified.
- The old account token expired before a sandbox was allocated. Routine browser renewal connected the same Modal workspace, `sparklesviii`. New public profile ID: `be145cdf8e4f45779da0123407f64971`. Credentials stay in macOS Keychain. Old owner profiles remain.

Exact next action: obtain approval for `MODAL_TRIAL_SUPPLEMENT.json`. Resume the existing 30 nt run from its 128 saved evaluations. Use total limits of 4096 candidates and 60 s, wanted 20, seed 1. Cancel after new batches and resume the same logical run. This needs the remaining original container plus one extra, each capped at 180 s. Added compute estimate: US$0.0094968; revised total compute estimate: US$0.0427356. Keep the US$0.06 build/storage allowance separate. Do not repeat saved evaluations. Complete snapshots are in `modal-completed-snapshots`; receipts are in `MODAL_VERIFICATION.json`.

## Preservation and restoration

Solver stays the default. Preserve `BENCHMARK.md`, `pilot-v2`, both inverse-head checkpoints, all older Qwen folding/cell weights, and the research worktree. The held-out synthetic results remain Solver 52/54, Hybrid 51/54, raw Qwen 0/54. No benchmark or training run was repeated for release verification.

Current app context is the scratch Library. Restore the original context after the trial or if approval remains pending: Library `/Users/vii/Documents/FoldStudio-MetalPort/validation/bindcraft-fab-amme-native`; project `fef08806-d3ac-4846-8143-60a76b8c1e63` (Predictive biology · independent evaluation); compute mode `modal`. Original state: `release-original-state.json`.

## Build fixes retained

The build uses the existing recorded Cargo/Rustup/Node environment when Cargo is absent from PATH. Native children inherit `PYTHONDONTWRITEBYTECODE=1`. The native workspace validator uses an existing-file connection with query-only SQL to read closed WAL libraries. Header, schema, process and signature guards remain. Four focused workspace/native checks passed. Earlier failures remain in full logs; their stale pending-rebuild notes are archived in `CHECKPOINT-before-desktop.md`.

Context Mode remains enabled. Fresh session: call `ctx_resume`, then `ctx_doctor`; use `ctx_execute` and `ctx_search` for bulky logs. No host configuration changed.

## Recovery audit (2026-11-18)
The previously approved Modal supplement is in progress. The installed app resumed logical run `1271ac85-c2fe-469e-91a5-327d0c5bf757` in task `6f288558510745e1896237cdb1dc0bd3`. Cancellation passed: 522 evaluations and 1200 solver calls persisted at 56.957495055 s cumulative search. All 128 initial candidates and their fields remain. Partial snapshots and checks are in `modal-recovery-verification`. Next: resume this same run to its remaining total 60 s budget, then restore the original Library/project/Modal mode. Do not repeat previous batches or launch another test run.

## Resume transport correction (2026-11-18)
The final approved sandbox `sb-01M7QDP2G9JFJ65ZJTVK0S04XP` failed before science with `[dumb-init] bash: Argument list too long`. All 522 partial evaluations remain. Source fixes use a task-specific Volume input file and restart UI polling with an explicit version counter. The core solver source and its resume seal are unchanged. Regression checks passed: 33 backend tests, 12 interface tests, and TypeScript. No benchmark or training was repeated. App is closed. Next: guarded packaging and local installed resume verification. A single 180 s CPU retry is prepared in `MODAL_RECOVERY_RETRY.json`; approval is pending. Do not launch it until approved.
Context Mode MCP tools work. Fresh doctor reports modified hooks; `context-mode setup --agents codex --yes` is blocked by EPERM at `/Users/vii/.context-mode/setup.lock`. No host setup was changed. Keep the report and repair command in the final handoff.
