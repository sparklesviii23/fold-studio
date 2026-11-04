# Independent predictive benchmarks

5 November 2026. Real completed local pilot: `30b27d8e63e940a997163fe84fa8bcf4`; protocol `tahoe-line-plate-holdout/1`, seed 17. A prior development run is retained separately; metrics agree. Saved arrays reproduce all 117 validation/test condition metrics exactly.

## Protocol

47 exact-matched cell contexts: 29 training, 9 validation, 9 test. Whole lines are disjoint. Training plates 1–10; validation 11–12; test 13–14. Training-only untreated expression selects/normalises the nearest-context features. Training-only response rows fit every predictor and the compound-agnostic comparison. Validation does not tune hyperparameters in this fixed pilot. Eight drug/dose keys are sampled for test from metadata via SHA-256, without looking at response activity; five compatible keys exist for validation. Same-drug/same-dose response transfer is deliberate; this is not unseen-drug prediction.

72 test conditions, 45 validation conditions. All models score the identical finite eligible genes in each condition; no outcome-selected top-gene primary metric. Missing targets are not zero-filled. Each condition contributes one MAE/MSE/Pearson value; scores are macro-averages. Pearson for the zero-response predictor is undefined. 95% intervals use 1,000 crossed line/compound bootstrap draws, never cells or genes as independent replicates. Results are conditional on only two test plates; the atlas lacks well/specimen IDs for a complete leakage audit.

| Predictor | Test MAE | Test MSE (95% CI) | Effect Pearson r |
|---|---:|---:|---:|
| Unchanged control | 0.567673 | 0.787841 [0.638080, 0.957678] | undefined |
| Compound-agnostic training mean | 0.570236 | 0.799810 [0.654637, 0.963615] | 0.097200 |
| Matched drug/dose donor mean | 0.577209 | 0.809824 [0.658194, 0.976907] | 0.114403 |
| Nearest untreated RNA context | 0.809531 | 1.540653 [1.257286, 1.843899] | 0.041658 |

Donor-mean minus generic-mean paired test MSE = +0.010014, 95% CI [−0.006314, +0.023716]. Nearest-context difference = +0.740842 [+0.487451, +1.024329]. No tested predictor beats unchanged control on mean MSE. A small increase in correlation does not reverse that finding. No model is promoted.

This is a different task from the earlier active-condition/top-200-gene Tahoe r≈0.79 report. The new pilot changes split, target selection, weighting and scoring. The difference cannot be attributed exclusively to leakage or used as a controlled ablation.

## Preserved CellFlux external record

Committed source `2862128`, `cellflux_benchmark.py --ood`, BBBC021 MCF7, original checkpoint and IMPA `bbbc021_all` crops, authors' test split/8-compound exclusion list, 12 generated cells per compound. Final committed validation report says effect-direction cosine 0.61 vs trained-compound average baseline 0.62; distance 1.82 vs 1.77, compared with 2.21 untreated. No aggregate advantage over the baseline. Per-compound failure and dose limitations remain in `VIRTUAL_CELL_VALIDATION.md`. This stage read the committed report, not every original image archive/result artifact, and did not rerun or modify the study. It does not establish HepG2 accuracy.

## Regulatory test

Single approved Borzoi job `af2b5ce1548e4fac95abd2781049c7c9` completed successfully: 16,352 real predicted bins. FABP1 fold3 comparison against ENCODE ENCFF065PJM: Spearman 0.444756 on 45 of 6,144 bins with complete reference coverage. Missing regions were not filled with zero. Original ENCODE signal differs from author preprocessing, so this is a limited held-out locus check, not exact author-target benchmark reproduction, genome-wide validation or AIDO parity. See `PREDICTIVE_CELL_BORZOI_EXECUTION.md`.

## Reproduction

With NumPy and the existing completed atlas/DepMap inputs in an isolated library:

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 <science-python> scientific/virtual_cell_benchmarks.py <isolated-library> --seed 17 --conditions-per-line 8
```

Output `<isolated-library>/virtualcell/benchmarks/<UUID>/{result.json,predictions.npz}`. The JSON carries input hashes, exact donor/target/baseline row IDs, split identities, selected keys, feature fitting parameters, software identity, score intervals and limitations. Prediction arrays retain float64 values and explicit masks; no pickle. Load/export rechecks both JSON and array hashes. Run IDs/timestamps differ on repetition; metrics should reproduce exactly in the same numerical environment.
