# Full Fab integration: measured status

Current Architect implementation: `5024281`; plain workspace title: `233e9c8`.
Pinned, unmodified scientific source: `c0ee638d11bc010817c2c97ee58ed5c323e664e2`.

Full Fab is connected to the native app as an experimental protected CPU
workflow on Apple Silicon. Complete original Fab design is **not yet certified**.
This path needs no NVIDIA hardware or remote computation; it does not establish
full GPU-resident Metal Fab execution. Notarization remains deferred for local use.

## Original production campaign — cancelled

The native campaign `b981bc11-4606-43be-a3f2-000f1d6406dd` completed **five**
genuine original screen optimizer updates. Its sixth gradient was interrupted at
the user's request. Peak task footprint was 11,588,593,360 bytes (10.79 GiB), below
the unchanged 14 GiB ceiling. Each completed step released its live SSD tape.
The worker, supervisor and idle-sleep assertion exited, and owned scratch was
removed. The campaign remains cancelled; automatic continuation remains paused.
No complete trajectory, accepted Fab or downstream result is claimed for this run.

Saved gradient execution times were 1260.715, 984.598, 929.180, 971.928 and 962.152
seconds. Initial recorded compilation was 8.271 seconds, then 0.139–0.300 seconds
per call. Execution, rather than recompilation, dominates these observations.
The source log reports a 437-residue binder assembly and complete 115-residue
target (552 residues); this differs from the matched 559-residue fixture below.
See `reports/architect-fab-performance-profile.json`.

## Full-size memory and speed measurements

A genuine original Fab scaffold retains both constant domains. The matched fixture
has heavy/light chains of 231/213 residues plus the full 115-residue hPDL1 target:
559 actual residues. Per-chain padding gives a 595-residue gradient graph; the
conservative admission estimate is 608. Original design models 1/3/5 remain in the
pool, and original RNG selects model 5. Models 2/4 are held out for validation.

| Measurement | Subbatch 1 | Subbatch 4 |
|---|---:|---:|
| Genuine forward + backward execution | 1135.702 s | 633.887 s |
| Recorded compilation | 1.341 s | 1.473 s |
| Peak task footprint, including compression | 10.331 GiB | 10.682 GiB |
| Worker ceiling | 14 GiB | 14 GiB |
| Lossless SSD tape quota | 10 GiB | 10 GiB |

Subbatch 4 is **1.79165× faster for this matched full gradient**. Source, complete
input, seed, model pool, sampled model, checkpoint and settings were verified equal
except for subbatch size. Coordinates are identical; loss and all gradients pass
unchanged `rtol=1e-4`, `atol=1e-5`. Largest gradient difference is approximately
1.69e-7. New automatic native Fab execution selects 4; frozen recovery settings
retain 1 and explicit 1 remains available. Unsupported native choices are refused.

The original memory improvement combines fine original subbatch rematerialization,
lossless SSD tape and the installed CPU memory scheduler. At subbatch 1 the latter
reduced compiled temporary heap from 12,641,092,472 to 7,148,896,184 bytes (43.45%).
Subbatch 4's compiled temporary heap is approximately 7.45 GB. These compiler
estimates are not total resident-memory measurements. The matched full gradient
wrote/read 54 checkpoints totalling 9,665,972,632 bytes in each direction; owned
scratch cleanup passed. The task ceiling, 10 GiB tape quota and 2 GiB reserve remain.

These observations do not establish production steady-state speedup or full-run
longevity. Forward/backward, triangle attention, triangle multiplication,
structure-module and SSD I/O wall-time fractions were not separately measured.
Logical graph reports identify large tensor values and local program-order
lifetimes, not physical overlap or exact runtime attribution. Energy and thermal
measurements are unavailable. Earlier SSD-only executions exceeded the task cap;
they are not successful timing baselines.

Evidence: `reports/architect-fab-chunk-comparison.json`,
`reports/architect-fab-subbatch4-gradient.json`,
`reports/amme-fab-memory-scheduler-gradient.json`.

## Scientific comparisons

Small trained-model single gradients and matched-input two-update optimizer tests
pass the original tolerances, including arrays, coordinates, RNG and optimizer
state. Independent two-update trajectories still drift beyond tolerance after an
initial input difference of approximately 7.45e-8. Unmodified source reproduces
that downstream drift at the perturbed inputs, including float16 coordinate
rounding. Matched-input controls do not certify independent continuous-trajectory
identity. The original failed independent report is preserved.

See `reports/amme-two-update-parity.json`,
`reports/amme-matched-update-parity.json`,
`reports/amme-reference-perturbation-control.json`, and
`reports/architect-chunk4-numerical-comparison.json`.

## Short engineering workflow

The native Architect now offers separate **Engineering Validation** and
**Original Scientific Run** modes. The former records one round per gradient
stage, two mutation evaluations (one proposed mutation), one candidate/attempt,
and zero beta-sheet extra rounds. It preserves the complete scaffold/target,
original model pools, recycles, losses and filters. Original-recipe hash and
explicit workload overrides distinguish engineering outputs. Preparation and
immutability tests pass; a complete new shortened trajectory has not been run.

Separate original downstream components were exercised on the genuine full
559-residue gradient fixture. The corrected harness calls the original mutation
function directly: two evaluations plus final recheck, one proposal, unchanged
fixed sequence, and genuine rejection at its original i_pTM gate. ProteinMPNN
holds 407 framework residues. The actual model-2 bound/unbound refold completed at the original three recycles and rejected at i_pTM. Its genuine rejected candidate passed original ranking and exact-byte library/project export checks (`reports/architect-fab-component-artifacts.json`). Starting model 4 then crossed the 14 GiB guard. A cache-cleanup policy passes two JAX lifecycle tests and 78 bitwise-identical small trained-model arrays/RNG; its full-size retry ended with SIGTERM after approximately 604 seconds, without a recorded cause or completed refold. Thus full-size cache cleanup remains unverified; rejection is never promoted to acceptance. An earlier test-only sampler mismatch was caught, stopped
and marked unvalidated; its output is not counted as evidence.

## Native interface, persistence and recovery

The rebuilt, locally signed BindCraft Architect replaces the oversized modal
with five sections, versioned project drafts, clear residue/exclusion controls,
original settings and compact saved campaigns. Both named user campaigns remain
accessible. Failed/cancelled progress says last observed rather than computing.
Current packaged modules pass three genuine standard-binder snapshot imports and
project exports with exact coordinate bytes, plus two original Fab output-choice
preparations with unchanged design identity.

Native Fab result transport retains the existing full-chain checks: both antibody
chains must match original reported sequences, and target chains must match the
complete prepared input. Missing/truncated results are refused before writes.
Synthetic acceptance receipts used by protocol tests are explicitly labelled and
do not constitute accepted Fab generation.

Original campaign recovery resumes at the **next original trajectory** when
claimed attempt budget remains. Interrupted attempts remain spent. Exact
mid-trajectory optimizer/RNG/mutation restoration is unavailable; temporary SSD
tape is not a restart checkpoint. The native UI explains this and does not offer
Resume for the exhausted cancelled one-attempt campaign.

The guarded local launcher and active-bundle seal checks prevent the previous
conflicting ad-hoc signing identities from being run or mutated concurrently.
The old app/worker exited before the new native update was activated. All 46
scientific Python resources match source; deep/strict local signature verification,
TypeScript, frontend and native release builds pass. Current regression evidence:
428 backend and 87 frontend tests in the combined Cloud foundation, plus retained real AMME/SSD runtime checks. The separate current Cloud scope is documented in `docs/RAPID_FOUNDATION.md`.

## Remaining scientific acceptance

Full original trajectory completion, accepted full-Fab generation, independent
continuous-trajectory parity and exact optimizer-step recovery remain unverified
or unavailable. Do not claim full Fab completion from a full gradient, a shortened
run, a rejected fixture or exact-byte transport. See the A–G report in
`docs/BINDCRAFT_ARCHITECT_REPORT.md` and current machine-readable state in
`docs/PROJECT_METAL_EXECUTION_STATE.json` and `reports/amme-integration-status.json`.
