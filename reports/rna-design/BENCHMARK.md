# RNA Design benchmark · 16 November 2026

Solver remains the app default. At 32 candidates and 2 s, it succeeds in 52/54 target-seed runs. Qwen with constraint repair succeeds in 15/54. Qwen plus the solver succeeds in 51/54. Direct Qwen generation succeeds in 0/54. This pilot does not show a useful overall quality, speed, or cost gain from Qwen.

These are computational predictions. No measurement labels or experimental outcomes are present. Installed UI and real Modal completion/import/save/reopen passed. Real Modal cancellation retained 522 evaluations. A later resume failed at container startup; its source fix passed local checks. See `CHECKPOINT.md` for the remaining paid retry.

## Frozen comparison

The v2 protocol uses 24 train, 9 validation, and 27 fresh test targets. Test lengths span 10–70 nt. There are 6 coarse topology families. Unary-loop relatives, mirrors, and sibling/exterior permutations stay together. Equal-length pair F1 ≥0.8 groups are merged before the split. No v1 target string is reused. Entire related families remain in one split.

Protocol SHA-256: `3a65f2487c5ac486e95adaa06548948adfe75a420dd8dbdc78eeb9353ccb8aa0`. The protocol, seeds, training parameters and scoring rules were sealed before v2 training. Seeds: 17 and 29 for comparison, 20261116 for training. Two seeds on one target are correlated; 54 runs are 27 target structures, not 54 independent structures.

Qualification requires exact ViennaRNA 2.7.2 MFE target agreement plus all sequence constraints. Settings: Turner 2004, 37 °C, dangles=2, noLP=false. MFE ties can pass. The RNA Lab reduced Turner model checks top distinct candidates. Its agreement is reported separately; it is not experimental truth.

## Same time and candidate limits

Both arms use identical targets, masks, locks, final checks, and 2 s search limits. Search stops after 3 qualifying sequences or its limit. Near misses and failures remain in the case files. Qwen and Hybrid share the same sequence-domain and canonical-pair repair as the solver seeds. This is separate from the raw direct-generation audit.

| Candidate limit | Method | Success | Mean distinct qualifying | Median first success, s | Mean warm wall, s | Independent agreement |
|---:|---|---:|---:|---:|---:|---:|
| 8 | Solver | 49/54 | 2.667 | 0.012151 | 0.229804 | 32.6% |
| 8 | Qwen + constraint repair | 8/54 | 0.259 | 0.001588 | 0.106411 | 71.4% |
| 8 | Qwen + solver | 48/54 | 2.500 | 0.009780 | 0.326444 | 41.5% |
| 32 | Solver | 52/54 | 2.889 | 0.019411 | 0.296091 | 30.1% |
| 32 | Qwen + constraint repair | 15/54 | 0.630 | 0.010845 | 0.263929 | 70.6% |
| 32 | Qwen + solver | 51/54 | 2.759 | 0.010766 | 0.492299 | 38.3% |

First-success medians include successful runs only. They cannot support a general speed claim when the success rates differ. Warm wall time excludes model load and target-feature work. Independent agreement is conditional on the checked, primary-qualified candidates. Different candidate sets prevent a causal quality claim from the agreement rates. Final candidate constraint violations: 0 in all arms. Raw proposal violations are reported below.

## Matched explicit evaluation counts

A sealed supplement disables early success stopping and runs to exactly 8 explicit final scores. All 54 target-seeds reach 8 in every arm. No case is time-censored.

| Method | Success rate | Mean distinct qualifying | Mean search, s |
|---|---:|---:|---:|
| Solver | 90.7% | 5.926 | 0.440414 |
| Qwen + constraint repair | 14.8% | 0.278 | 0.264751 |
| Qwen + solver | 88.9% | 5.148 | 0.561310 |

An explicit evaluation is one sequence MFE/partition-function target score. Independent-model checks are counted separately. `solverCalls` counts ViennaRNA inverse-fold calls. Their internal energy evaluations are not exposed. These are matched final-score counts, not matched total internal solver work. Complete counts are in `pilot-v2/{benchmark,matched-count}.json`.

## Wins, ties and failures

Primary success at the 32-candidate limit, compared with Solver:

| Method | Wins | Ties | Losses | Both fail within ties | Warm first-success wins / ties / losses on shared successes |
|---|---:|---:|---:|---:|---|
| Qwen + constraint repair | 0 | 17 | 37 | 2 | 4 / 0 / 11 |
| Qwen + solver | 0 | 53 | 1 | 2 | 27 / 0 / 24 |

Warm first-success wins occur on some targets. They exclude Qwen startup and feature extraction, and do not outweigh the lower primary success rate and longer overall search time. Exact winning, losing and failed cases are retained in `comparison-outcomes.json` and the full case report.

## Results by structure and length

The original protocol difficulty label is a light heuristic. The table below uses an audited annotation from the actual target: a node with 2 or more children is a branch; multiple exterior stems form a separate class. No prediction or checkpoint is changed by this annotation.

| Structural class | Method | Successful target-seeds | Mean warm wall, s |
|---|---|---:|---:|
| Branched | Solver | 28/30 | 0.489893 |
| Branched | Qwen + constraint repair | 0/30 | 0.369964 |
| Branched | Qwen + solver | 27/30 | 0.837957 |
| Single stem-tree | Solver | 24/24 | 0.053837 |
| Single stem-tree | Qwen + constraint repair | 15/24 | 0.131385 |
| Single stem-tree | Qwen + solver | 24/24 | 0.060227 |

| Length, nt | Solver success | Qwen + repair success | Hybrid success |
|---|---:|---:|---:|
| 8–20 | 8/8 | 7/8 | 8/8 |
| 21–40 | 18/20 | 5/20 | 18/20 |
| 41–64 | 22/22 | 3/22 | 21/22 |
| 65–128 | 4/4 | 0/4 | 4/4 |

## Direct generation and training

The inverse head has 271188 trainable parameters. It uses frozen Qwen2.5-Coder-3B-Instruct target features. No Qwen backbone or old folding head was trained or overwritten. The base files matched their preserved official checksums before v2 training. Frozen parameter mutation counters stayed unchanged. Initial, selected, and final weights remain separate.

Training labels: `{"train": {"nearMissOrFailure": 120, "success": 163}, "validation": {"nearMissOrFailure": 79, "success": 48}}`. Successes use base cross-entropy. Near misses and failures use a small pair-error-weighted unlikelihood loss. Label source: ViennaRNA solver; `measurement:false`. Selected epoch: 1. Total recorded training/load/feature time: 42.312 s on cpu. Base-file preflight hashing is outside that timer. Training configuration, exact command, seeds, versions, and label/protocol hashes are in the checkpoint.

The raw audit samples 32 sequences per target-seed with repair disabled. Result: 0/54 target-seeds succeed. 1724/1728 raw samples violate a target-pair or sequence constraint. Valid direct samples are refolded by the same primary engine. This independent-base output head does not establish useful direct RNA generation.

## Startup and cost

Qwen model startup in the frozen comparison: 11.693 s. Per-target feature times are in every case. They are excluded from warm search time and must be added for a cold single-target use. The model is loaded once in the benchmark campaign. The real local runtime smoke check also reports supervisor wall time separately.

| Method at 32 candidates | Warm wall seconds per successful target-seed | Campaign seconds per successful target-seed, including one model load and one feature pass per target | Billed cost per success |
|---|---:|---:|---|
| Solver | 0.307479 | 0.307479 | Not measured |
| Qwen + constraint repair | 0.950144 | 2.900869 | Not measured |
| Qwen + solver | 0.521258 | 1.095001 | Not measured |

Local power cost is unmeasured. No GPU trial is justified by these results. The proposed 4-run Modal CPU qualification has a 630 s aggregate container limit and estimated compute of US$0.0332388, plus an allowance for image build and storage. The estimate uses [Modal Sandbox rates](https://modal.com/pricing), checked 2026-11-16. It is not billed cost. The original trial and one supplement were approved. Five containers were allocated: three initial runs, one cancelled extension, and one failed resume. Keep estimates separate from billed cost. Current receipts: `MODAL_VERIFICATION.json` and `modal-recovery-verification/verification.json`. The next single-container retry is specified in `MODAL_RECOVERY_RETRY.json`; approval is pending.

## Operational evidence and remaining work

33 backend checks and 12 existing interface checks pass after the recovery fixes. TypeScript, frontend build and source package closure pass. Real jobs using the installed Python produced 3 qualifying sequences for a 12 nt target and 3 for a 38 nt held-out target. Two distinct candidates from each were saved and reopened with identical result seals. A real owned-process signal cancellation retained 7 candidates; resume reached 24 distinct saved candidates without repeating them. These source/runtime checks are retained. The installed app later passed both targets, distinct-candidate comparison, and exact Library save/reopen; see `DESKTOP_VERIFICATION.json`.

The first 30 nt held-out demonstration (`g07-v0` from v1) failed and is retained in `runtime-library` and `local-runtime.log`. The successful 38 nt demonstration is also from the preserved v1 held-out family. It was selected for operational testing after the benchmark; it is not a fresh scientific test.

Installed packaging and desktop verification passed in the later release phase. Real Modal simple-target completion, import, save and reopen passed. Cloud cancellation extended the saved 30 nt run from 128 to 522 evaluations and retained all prior candidate fields. Its next resume failed before scientific work with `[dumb-init] bash: Argument list too long`. The source fix uploads the request to a task-specific Volume file. A 334694-byte local file-resume check reached 560 evaluations at 60.004061347 s, kept every partial candidate unchanged, and added exactly 38 new evaluations. This local check mocks only remote `sync`; it is not a passed cloud resume. A separate UI fix restarts polling explicitly after resume. Do not repeat training or benchmark cases to verify these operational fixes.

## Evidence files

- `pilot-v2/protocol.json`: frozen targets, splits and limits.
- `pilot-v2/labels.json`: source labels, failures and measurement flags.
- `pilot-v2/benchmark.json`: all 324 time/candidate-limit cases.
- `pilot-v2/matched-count.json`: all 162 exact-count cases.
- `pilot-v2/raw-qwen.json`: all 1728 direct proposals and checks.
- `pilot-v2/source/`, `SOURCE_RECEIPT.json`: exact benchmark code snapshots and hashes.
- `pilot-v2/{collect,training,comparison,matched-count,raw-qwen}.log`: full logs.
- Shared library `engine/models/rna-design/pilot-v2/{initial,selected,final}.safetensors` and `checkpoint.json`: trained artifacts.
- `local-runtime.json`, `runtime-library-v3`: real source-job save/reopen/cancel/resume evidence.
- `backend-tests.log`, `interface-tests.log`, `typescript.log`, `frontend-build.log`, `package.log`: checks.
- `main-before.txt`, `research-before.txt`, `research-after.txt`: preservation evidence.

`pilot-v1` remains development evidence. Its split did not merge mirror/unary-loop relatives. Its scores are not used as final family-held-out results. Neither pilot proves general RNA design quality beyond the synthetic targets. Qwen pretraining contamination is unknown.
