# Full Fab integration: measured status

Implementation: `4e23650`, followed by recovery correction `5b63a6e` on
`project-metal/apple-silicon-engine`. Pinned scientific source:
`c0ee638d11bc010817c2c97ee58ed5c323e664e2`.

Follow-up `07a7839` adds full Fab chain-transport checks and a bounded wider
progress-log window. The locally signed staged package passes its bundled-runtime
backend checks; activation waits for the running old-identity calculation to end.

Full Fab is connected to the native app as an experimental, protected CPU
workflow. Complete Fab design is **not yet certified**. This path needs no NVIDIA
hardware, remote compute or external Python installation; it does not execute
the full Fab calculation on the Metal GPU.

## Completed full-size calculation

The genuine original Fab scaffold retained both constant domains. Original
editable-loop sampling produced heavy/light chains of 231/213 residues, alongside
the entire 115-residue hPDL1 target: 559 actual residues. Per-chain padding gave a
595-residue gradient graph; the conservative admission estimate was 608.

The original three-model design pool (1/3/5) remained resident. Original RNG
sampling selected model 5 for this calculation. Models 2/4 remain the intended
held-out validation pool. No scientific losses, filters, model counts or recycle
counts were reduced.

| Measurement | Observed result |
|---|---|
| Full forward plus backward | Passed; finite loss and all three sequence gradients |
| Combined wall time | 1,139.625 seconds |
| Peak task footprint, including compressed allocations | 10.33 GiB |
| Unchanged worker ceiling | 14 GiB |
| SSD payload written/read | 9,665,972,632 bytes each; 54 checkpoints |
| Largest individual serialized checkpoint payload | 182,479,396 bytes |
| Owned scratch cleanup | Passed |
| Baseline compiled temporary heap | 12,641,092,472 bytes |
| Optimized compiled temporary heap | 7,148,896,184 bytes; 43.45% reduction |

The improvement combines fine original subbatch rematerialization, lossless SSD
checkpoints and the installed CPU memory scheduler. Compiler heap estimates are
not total resident-memory measurements. Earlier SSD-only execution exceeded the
worker ceiling; it provides no successful baseline runtime for an overhead ratio.
Forward/backward times are not separately measured. Reliable energy/thermal
measurements are unavailable. Graph reports identify logical tensor lifetimes,
not exact overlapping physical allocations.

## Native application validation

The ad-hoc signed native bundle contains its CPU interpreter and all seven pinned
AF2 checkpoints. The actual native Start button launched an original full Fab
campaign. The viewer rendered the genuine 559-residue diagnostic, explicitly
named as a diagnostic rather than an optimized or accepted design.

Project export preserved exact scaffold, target and diagnostic coordinates while
excluding live SSD scratch. Quitting and reopening the original controller, then
opening the updated recovery controller, retained the same scientific process.
The controller displays live footprint, peak, limit and completed-gradient count.
The actual native campaign has now completed its first original screen optimizer
update and started its second full gradient. Peak task footprint at that point was
approximately 9.93 GiB; subsequent peak during the second gradient is 10.02 GiB.
The first tape was released before the second step.
Multiple completed full-size steps remain unverified.

The updated controller and older scientific worker caused macOS to alternate
between their different ad-hoc signing identities under the same app identifier,
repeatedly asking for Documents access. The matching original controller was
restored; a subsequent three-minute privacy-log check contains no new prompt or
identity-mismatch events. The recovery update remains ready for activation after
current workers finish. Their original bundle must remain available until then.

For subsequent local updates, use `pnpm open:local /absolute/path/to/app.app`
(with optional `--data-root /absolute/development/root`). This guarded launcher
reuses the build owning a live window or scientific child. Ordinary Finder
launches bypass this development guard. Package sealing now refuses an active
bundle before changing any resources or signing identity. No privacy protection
or signing requirement was weakened.

Native Fab result transport now requires two antibody chains matching the original
reported sequences and target chains matching the complete prepared input.
Missing or truncated chains are refused before any record/asset write. A successful
check records chain identities and lengths in result metadata, without asserting
new scientific acceptance. Nine tests cover the genuine diagnostic, corrupted
assembly cases and isolated import/export with explicitly synthetic completion
receipts. Accepted Fab generation remains untested.

Progress parsing now reads at most 1 MiB of log context while keeping the visible
log limited to 30,000 bytes. This retains trajectory information after many memory
events. A new recovery marker clears old trajectory context; unavailable context
beyond the bound remains unreported. Three focused native-service tests pass.

Recovery now compares effective compiler flags after the pinned original package
applies its startup settings. The actual packaged runtime comparison passes.
This check did not interrupt the Fab calculation and is not an end-to-end Fab
resume demonstration. Original campaign recovery resumes at a subsequent claimed
trajectory boundary, not midway through an optimizer step.

## Scientific comparison and remaining acceptance checks

Small genuine trained-model single-gradient comparisons pass the original
`rtol=1e-4`, `atol=1e-5` thresholds. Repeated local comparisons also pass at
bitwise-identical input states. An independent two-update trajectory comparison
exceeds those thresholds after a first input difference of approximately
`7.45e-8`. Unmodified source reproduces the downstream drift at those perturbed
inputs, including its float16 coordinate rounding. The failed independent report
is preserved; matched-input controls do not certify independent trajectory identity.

| Requirement | Status |
|---|---|
| Original full scaffold and constraints | Verified working |
| Full-length forward prediction | Verified working |
| Full-length backward calculation | Verified working |
| Multiple optimization steps | Partially verified: first native update completed, second gradient running; small matched-input repeated checks pass |
| Complete original Fab trajectory | Partially verified: actual native campaign running |
| Fab ProteinMPNN redesign | Not tested |
| Fab held-out multimer validation | Not tested |
| Original Fab filtering/ranking | Partially verified: criteria preserved; completed case pending |
| Accepted Fab generation | Not tested; none generated |
| Native integration/export | Partially verified: launch/viewer/project/reopen pass; accepted Fab pending |

Current regression evidence: 390 backend tests, 76 frontend tests, four AMME runtime
tests and seven SSD runtime tests pass. Native/frontend build and local deep
signature verification pass. Notarization remains deferred for local use.

Machine-readable evidence: `reports/amme-integration-status.json`,
`reports/amme-native-package.json`, `reports/amme-fab-memory-scheduler-gradient.json`,
`reports/amme-two-update-parity.json`, `reports/amme-matched-update-parity.json`
and `reports/amme-reference-perturbation-control.json`.
The follow-up package/backend evidence is in `reports/amme-packaged-transport.json`
and `reports/amme-fab-transport.json`.
