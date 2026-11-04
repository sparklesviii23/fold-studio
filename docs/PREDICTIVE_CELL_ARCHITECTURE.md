# Predictive integration contracts

5 November 2026. Extends existing Virtual Cell, does not create another cell context manager or latent world model.

## Worker and persistence

`virtual_cell_actions.ACTIONS` routes new actions through existing `virtual_cell.state_dispatch` after the existing selected cell/context has been loaded:

- `vcell_benchmarks {id}`: per-library, integrity-checked run summaries and selected-context split role. Global test scores are not reinterpreted as scores for the selected cell.
- `vcell_benchmark_run {id, seed=17, conditionsPerLine=8}`: bounded local evaluation, strict integer limits 1–12 conditions per line, no data/model download, no paid launch. Runs take a few local seconds on the inspected atlas. Saves an independent UUID directory and publishes `result.json` atomically after arrays are complete. Cancelled/incomplete directories do not appear as completed reports.
- `vcell_benchmark_get {id, run}`: verifies report checksum and prediction artifact checksum before returning full reproducibility metadata.
- `vcell_regulatory_runs {id}`: reads existing `gpu_tasks` job metadata. Does not poll or launch cloud work.
- `vcell_regulatory_track {id, run}`: accepts only completed retrieved `bio_borzoi` artifacts, verifies job/result/input/artifact identity, hg38 reference geometry and CSV bins, and requires an explicitly matching HepG2/K-562 assay. C3A is not HepG2. Unknown contexts abstain with `supported:false, values:null`.

`vcell_report` includes benchmark summaries alongside the existing cell history/snapshots/evidence. Scientific registry rows retain `partial` for unqualified Borzoi; successful software contracts do not change model scientific status. New Python modules are registered in the existing desktop resource manifest. No installed app bundle is overwritten during concurrent development.

## Interface

Existing Virtual Cell View controls add Scientific benchmarking and Genomic regulation. The former shows saved scores, null correlations, intervals, validation scores, paired differences, failure examples, context exclusions, model non-promotion and JSON export. The latter shows genomic coordinates, assay identity, raw unit semantics, source/checkpoint provenance and bounded min/max/mean envelopes from the verified full-resolution CSV. Observations are not fabricated when a job is missing. Existing Biological Models remains the inference/cost/cancellation entry point.

## Compute

Reuses `gpu_tasks`/`biology_providers`/`cloud_accounts`; account secrets stay in the existing Keychain path. The approved single attempt uses an independent research database and job directories and a content-identified, locked checkpoint cache in the existing Modal Volume. Model source revisions and actual environment receipts are retained. One 900-second execution bound is not a total monetary cap; image-build time/CPU/memory are additional. No automatic resubmission after failure or ambiguous launch.

## Deliberately deferred architecture

No universal confidence percentage, arbitrary cross-modal average, RNA-to-protein abundance conversion, shared latent state, learned temporal transition, full foundation-model training, new molecular-design workflow or causal regulation graph. These require compatible data and independently held-out improvement over simpler baselines first.
