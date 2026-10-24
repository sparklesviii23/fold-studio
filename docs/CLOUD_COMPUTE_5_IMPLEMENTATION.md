# Cloud Compute 5 — implemented increment and qualification boundary

The current increment replaces the Modal campaign screen with a persistent seven-section workstation. The actual saved second campaign is available immediately; the screenshot example is not used as a simulated live feed. All local Metal workflows and the existing molecular viewer are retained. This increment is not completion of the full Sections 1–79 directive.

## Working implementation

- `src/components/CloudMissionControl.tsx`: overview, immediately visible terminal, actual current candidate, candidate selection, ancestry/mutations, separate analysis/performance evidence, separate 24-component readiness view, and configuration destination.
- `src/components/RapidLiveTerminal.tsx`, `src/lib/cloudTerminal.ts`: independently scrolling virtualized output, fixed command input, bounded/deduplicated cursor history, search, engine/severity/stage filtering, timestamps, clear-visible-only, pause/follow, fullscreen, loaded-log export, deterministic command history and completion. Original archive line timestamps are unknown and shown as unavailable.
- `scientific/cloud_monitor.py`: real archived subprocess logs and official `FunctionCall.logs.fetch()` transport, persistent SQLite cursors/events, saved candidate/metric readback, exact upstream rank-table reconciliation without rewriting the old scientific journal, coordinate SHA verification and existing viewer import. New deployable workers publish small immutable candidate previews during later stages; larger structures retain their original committed artifact references.
- `scientific/cloud_shell.py`: explicitly reviewed commands through the official Modal `container exec --no-pty` in an existing app-owned container. Each operation uses the campaign's original credentials. No local-shell fallback, new GPU container, arbitrary app selection or implicit deployment. This is a bounded command session, not a persistent PTY. Modal CLI discovery and argv behavior were verified against installed SDK 1.6.2. No real remote shell command was executed during this update. Vast.ai retains its previous SSH implementation; a new interactive Vast PTY is not connected to this terminal.
- `scientific/cloud_accounts.py`, `ModalAccounts.tsx`: named Keychain token pairs, profile metadata, save/rename/switch/remove, separate future deployment configuration, immutable campaign owner binding, refusal to remove an account owning saved research, and no fallback to another account when its credentials are missing. Browser connection uses official temporary isolated Modal profiles. Two real account sign-ins/switches have not been exercised. Workspace identity/credits are unavailable until a supported authenticated verification is implemented; the UI states this rather than fabricating them.
- `remote_worker/fold_rapid/gpu_profiles.py`, `CloudGPUProfiles.tsx`: eleven explicit GPU profiles and an engine-by-GPU evidence matrix. Prices/catalog/capabilities were checked against official Modal/NVIDIA pages on 24 October 2026. Modal lists the shipping B200 at180GB; this is used for the capacity card. These are a dated snapshot with a direct current-pricing review link, not live catalog discovery. Hardware fit and optimal cost remain unqualified outside the recorded A100 experiment. B300 is refused for the pinned CUDA13.0.2 recipe because Modal requires13.1+. T4's SM7.5 meets JAX's CUDA13 architecture floor; memory/model execution remains untested.
- `remote_worker/fold_rapid/events.py`, `store.py`, `unified.py`: hash-linked append-only stage/campaign presentation journals, separate from mutable status snapshots. Raw scientific files remain intact. Secret and ANSI redaction apply to displayed/forwarded text.
- `runner.py`, `telemetry.py`, `watchdog.py`, `unified_modal.py`: all child log lines forwarded (including process-exit tail), actual device-wide utilization/VRAM sampling separate from PID-attributed memory, observed host RSS, explicit missing-measurement errors, literal failure signatures, preserved artifacts, fail-fast continuation and approval-only paid recovery. New worker changes are not deployed yet.
- `adapters.py`, `contracts.py`, `biology_contract.py`, `unified.py`, `engine_tasks.py`: upstream ranked acceptance differs from passing refolds and final independent qualification; only reviewed-count ranked winners enter the next paid frontier while other passing outputs remain retained. Actual seed-dependent AF2 design/evaluation pools propagate through descendants. Unknown legacy exposure is diagnostic, not asserted held-out. Evaluators overlapping known gradient-design models are refused.

## Actual second campaign

`9c99e7870a19bd621c67ccf7bc8aefa1` ended PARTIALLY_COMPLETE, with its writer lease released. Original BindCraft rank1 is `DPDLERIRSGEWMAEVQAAL` (20aa, upstream i_pTM0.90/pLDDT0.91, no original all-atom/backbone clashes). Its original design pool is models1/3/4, validation pool2/5. Three upstream passing variants and four separate ProteinMPNN/SolubleMPNN outputs are retained. The original wrapper incorrectly reported no qualified candidates; display reconciliation now uses the original ranked table and does not mutate that historical record.

The additional AF2 stage on the older reference produced model2 coordinates but exceeded480s before finishing its second model. No complete additional ensemble or physics-qualified finalist exists. The best ranked sequence was not subsequently validated by that unfinished additional stage. Eight immutable lineage records, 103 downloaded hash-verified scientific artifacts (12,278,541 bytes), and the separately verified original ranked CIF remain saved. Estimated charges are not invoices. No new cloud compute was started for this increment.

## Performance questions: evidence and missing measurements

The same scientific process passed the real JAX CUDA forward/gradient probe in2.15s and produced actual molecular outputs on an A10080GB. A recorded device observation was4603MiB/81920MiB at100% utilization; this is neither a task peak nor a smaller-GPU fit benchmark. BindCraft's supervised duration was718.75s. Four separate MPNN calls completed. The additional AF2 numerical CUDA startup passed and one model output exists; silent CPU fallback is refused in the task. These observations support CUDA execution but do not constitute complete scientific numerical qualification.

Missing child peak memory resulted from absent PID attribution (host/container PID namespaces may differ); the exact namespace cause is not proven. The new instrumentation reports device totals and attribution separately. Loading/compilation/inference subphase durations and the effect of2physical CPU cores were not measured. No evidence establishes24GB/40GB fit, best CPU/RAM allocation, warm20–45s AF2,1–3s SolubleMPNN, or lowest-cost GPU. Raising AF2's selectable cold allowance to900s is a timeout option, not a measured speedup or automatically approved run.

The added paid-dispatch guard compares the original account/app and exact source-release manifest with the deployed receipt. A cloud writer lease prevents deployment while scientific storage is owned. These final client-side guards are staged for idle installation; the app was reopened before their installation.

## Still required

- Deploy this source under a separately reviewed CPU deployment allowance; verify genuine live SDK logging/preview delivery against an authorized run.
- Authenticate two real accounts, verify workspace identities and account-specific deployment/model readiness, reconcile supported billing data, and test old-campaign reconnection after switching.
- Dynamic catalog/price refresh; measured stage-specific resource routing; independently billed profiles; qualified shared-worker/cache strategy. Existing workers remain isolated/sequential; recommendations are provisional.
- A persistent detachable native terminal window and Vast PTY; full original-log downloads beyond the bounded loaded view.
- Complete safe recovery preparation/relaunch from the failed AF2 parent without regenerating successful designs. Current recovery guidance does not execute a replay or claim optimizer resume.
- Stable/experimental cloud channels, compatible deployment snapshots/rollback and measured performance benchmark storage/routing.
- Complete biology/accessibility validation, independent quality gates/disagreement comparisons, real Rosetta licensing/runtime qualification, missing ESM/Boltz checkpoints/RFdiffusion handoffs/ESMC execution, calibrated experimental/control datasets and controlled multi-engine comparisons.
- Fully qualified adaptive multi-round scientific controller and the remaining comparison/report/visualization work in Sections49–79. Existing discrete feedback/Pareto modules are retained; they are not a trained learned policy or proof of better binders.

Offline tests validate contracts and regressions. They do not substitute for genuine model qualification or experimental binding evidence. No new paid GPU experiments or external molecular API calls are authorized here.

## Official references

- Modal FunctionCall logging: https://modal.com/docs/reference/modal.FunctionCall
- Modal GPU identifiers and B300 requirement: https://modal.com/docs/guide/gpu
- Modal resource rates/CPU units: https://modal.com/pricing
- NVIDIA compute capabilities: https://developer.nvidia.com/cuda/gpus
- JAX CUDA architecture/runtime requirements: https://docs.jax.dev/en/latest/installation.html
