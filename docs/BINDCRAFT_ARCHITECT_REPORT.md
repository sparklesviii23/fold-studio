# BindCraft Architect — engineering report

Architect implementation: `5024281`; plain title: `233e9c8`; inference-cache policy: `95c7f27`. The subsequent Cloud Compute foundation is developed on `project-omega/rapid-cloud-foundation`.
Scientific source remains unmodified at
`c0ee638d11bc010817c2c97ee58ed5c323e664e2`.
The locally signed native update is open. Notarization remains deferred.

## A. UI redesign

The former Molecular Architect game and oversized configuration modal have been
replaced by a five-section BindCraft Architect workspace: Overview, Target &
Design, Scientific Settings, Compute & Run, and Campaign Library. Midnight navy
glass surfaces, native system typography, compact campaign rows, responsive
layouts, keyboard focus states and reduced-motion support preserve Fold Studio's
visual identity. The molecular viewer and other scientific modules are retained.

Configuration survives section navigation and reopening through a versioned,
project-specific draft. Target inspection opens the existing molecular viewer.
Original property/core presets, scientific JSON options, target states, output
settings and separate preparation/start actions remain connected to the backend.
Advanced controls offer preset-preserving overrides; clearing restores the source
preset rather than substituting a new numerical default.

Both original campaigns remain present: `ANGPTL3_Peptide_Pilot` and
`Full Fab · original hPDL1 · protected CPU`. Failed/cancelled runs display last
observed progress rather than claiming to be computing. Exhausted attempts do
not offer a misleading Resume action. No campaign automatically restarted.

Native screenshots: `reports/architect-native-overview.png` and
`reports/architect-native-exclusions.png`.

## B. Linear-peptide error

The original job `1d0dc714-2456-4bf7-935e-c3501787fa16` ended with
`jax.errors.JaxRuntimeError: RESOURCE_EXHAUSTED`: Metal execution would hold
**6.2 GB against its 6.0 GB protected budget**. The saved configuration had
passed peptide validation. Its target required 256 padded residues. This was a
runtime resource failure, not evidence that linear-peptide format mapping or
residue serialization was invalid.

The Metal launch adapter now refuses gradients above its measured 192-padded-
residue envelope before spawning a worker. It explains the exact limitation and
offers explicit CPU selection or a separately saved smaller target. It does not
raise the governor, change the saved target or silently fall back to another
backend. Failed-job reads derive a useful diagnostic while retaining the original
traceback and history.

A controlled run retained the original saved target bytes, chains and peptide
length bounds on explicit CPU, using a clearly labelled one-round engineering
schedule and unchanged scientific filters. It **completed in 76.968 seconds**,
recording one trajectory rejected at the original screen pLDDT gate, zero refolds
and zero accepted designs. The proper outcome is `no_accepted_designs`, not a
crash or fabricated success. A controlled launch replay also verifies refusal
before process spawn for the unsafe Metal case.

Evidence: `reports/architect-linear-peptide.json`. Original user settings, input
and execution log were verified unchanged.

## C. Amino-acid and residue selectors

The old residue multiselect made clearing difficult; the exclusion text field
did not clearly communicate its meaning. An empty omission string already meant
no amino-acid identities excluded. Omitted redesign residues meant all eligible
positions in selected chains, with other chains and explicit fixed constraints
retained. These are separate controls.

The new 20-amino-acid grid displays one/three-letter codes and explicit Allowed
or Excluded states. Click again to allow, remove an individual chip, or use Clear
All Exclusions. It serializes the original canonical uppercase omission string,
for example `CW`. All 20 excluded is invalid. Searchable residue checkboxes have
a genuine Clear action, preserving source chain/residue numbering.

Backend normalization now treats an explicit empty redesign list `[]` exactly
like omitted/`None`; previously that explicit API form could produce an empty
mask. UI clearing omits the field. Tests verify exact default masks, explicit
subsets, fixed chains, tied-position compatibility and invalid inputs. Existing
real upstream masked/tied decoder evidence remains applicable: the decoder and
omission semantics were not replaced.

Native/browser checks covered C and W exclusions, individual removal, clearing,
section navigation and draft reopening. The native draft was restored to no
exclusions after inspection. Evidence also includes
`reports/mpnn-constraints-validation.json` and its packaged counterpart.

## D. Fab integration and engineering validation

The complete heavy/light scaffold, constant domains and full target remain
intact. The original design models 1/3/5 and held-out multimer models 2/4,
recycles, losses and acceptance filters remain unchanged. Fab uses a local
float32 CPU backend on Apple Silicon with rematerialization and bounded lossless
SSD tape; it needs neither NVIDIA hardware nor remote computation. This is not
a claim of a fully GPU-resident Metal Fab calculation.

Native preparation now distinguishes **Original Scientific Run** from
**Engineering Validation**. Engineering mode records one gradient round per
stage, two mutation evaluations (one proposed mutation), one sequence candidate
and attempt, and zero extra beta-sheet rounds. It stamps an original-recipe hash
and workload overrides. Full target/scaffold, model pools, recycles, losses and
filters are retained. Names and imported artifacts explicitly identify this
mode. Preparation/immutability checks pass; a complete new short-mode trajectory
has not been executed.

The original production campaign was cancelled by the user after **five genuine
full-size screen optimizer updates**; its sixth gradient was interrupted. Its
scratch and idle-sleep assertion were released. It remains cancelled and the
background continuation automation remains paused.

Separate real full-Fab downstream tests use the genuine 559-residue gradient
prediction fixture rather than promoting an unfinished trajectory. The original
mutation function has completed two evaluations, one proposal and its final
recheck; the original i_pTM mutation gate rejected it. Fixed framework/target
sequences remained intact. ProteinMPNN then held 407 framework residues for the
explicit downstream fixture test. The actual model-2 bound/unbound refold completed with three original recycles and rejected at i_pTM. The genuine rejected candidate passed original ranking and exact-byte library/project export checks. Model 4 crossed the 14 GiB guard; cache cleanup passes small trained parity, but its full-size retry ended with SIGTERM before completion. No accepted Fab or complete full-size cache fix is asserted.

Interruption retains valid output/history and uses the original **next-trajectory
boundary** when attempt budget remains. Exact mid-trajectory optimizer/RNG/
mutation restoration is not implemented. SSD intermediates are temporary
backpropagation data, not restart checkpoints. The UI states this limitation.

## E. Measured performance

Saved native subbatch-1 gradient execution times were 1260.715, 984.598, 929.180,
971.928 and 962.152 seconds. Recorded compilation was 8.271 seconds initially and
0.139–0.300 seconds for subsequent calls. The principal measured delay is
execution, not repeated compilation.

A matched full-559-residue gradient comparison measured:

| Measurement | Subbatch 1 | Subbatch 4 |
|---|---:|---:|
| Forward plus backward execution | 1135.702 s | 633.887 s |
| Recorded compilation | 1.341 s | 1.473 s |
| Peak task footprint | 10.331 GiB | 10.682 GiB |
| Worker ceiling | 14 GiB | 14 GiB |
| SSD tape quota | 10 GiB | 10 GiB |

This is a **1.79165× speedup for one matched full gradient**. Loss, coordinates
and all sequence gradients pass the unchanged `rtol=1e-4`, `atol=1e-5` tolerances.
The largest reported gradient difference is about `1.69e-7`; coordinates are
identical. Source, seed, original model pool, selected model, checkpoint, target
and settings were checked equal except for subbatch size. A matched two-update
small trained-model test also passes for outputs, gradients, optimizer arrays and
RNG. New automatic Fab execution uses 4; existing frozen recovery recipes retain
1, and explicit 1 is still available.

This is not a steady-state production speedup guarantee. The native repeated-step
run and matched fixture use different shapes. Operator-level forward/backward,
triangle/structure-module and SSD I/O wall-time fractions were not separately
measured. Existing logical memory graphs identify large arrays, not physical
overlap or operator runtime. The earlier independent two-update trajectory drift
remains documented; matched-input parity does not establish independent continuous
trajectory identity.

Evidence: `reports/architect-fab-performance-profile.json`,
`reports/architect-fab-chunk-comparison.json`,
`reports/architect-chunk4-numerical-comparison.json`, and the retained
`reports/amme-two-update-parity.json`.

## F. Testing and native build

- Architect baseline: 407 backend tests and 85 frontend tests passed.
- Combined Cloud Compute foundation: 428 backend and 87 frontend tests pass.
- Inference-cache cleanup: two JAX lifecycle tests and 78 bitwise-identical small trained-model array/RNG comparisons pass; full-size retry remains unverified.
- TypeScript, Vite and native release build passed.
- The original Architect package verified 46 scientific Python resources. The
  final combined Cloud package verifies 48 resources; deep/strict ad-hoc signature
  and native profile lifecycle checks passed. See `reports/rapid-native-package.json`.
- Current packaged modules passed three genuine saved-stage imports and project
  exports with exact coordinate bytes, and two original Fab output-setting
  preparations with unchanged scientific design identity.
- Native UI inspection verified navigation, original campaign persistence,
  selectors, meaningful failures and truthful cancelled progress. The update was
  launched through the guarded local launcher after the old app/worker exited.

Package evidence: `reports/architect-native-package.json` and
`reports/architect-packaged-coordinates.json`.

## G. Remaining work and limits

Full original Fab trajectory completion, the full-size inference-cache cleanup and scientifically accepted Fab generation
remain unverified. They are separate from the shorter engineering/component
checks, and the cancelled production run has not been resumed. A full newly
prepared Engineering Validation trajectory has not been executed. Independent
continuous-trajectory numerical parity and exact optimizer-step recovery remain
limitations. Further operator-level profiling and full GPU-resident Fab execution
are future performance work, not claims of this update. Developer ID signing and
notarization remain deferred for local use.

The first downstream harness attempt was stopped after detecting a test-only
mutation-weighting mismatch; it is explicitly marked unvalidated and is not
counted as scientific evidence. The corrected test calls the original mutation
stage directly. No production algorithm or acceptance threshold was loosened.
