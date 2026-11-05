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

## Stage 2 implementation checkpoint · 5 November 2026

The fresh Borzoi reproduction gate is awaiting a new, scoped cloud approval. No Stage 2 cloud job has been submitted. The earlier one-attempt approval was consumed by Stage 1. New response-model fitting is deliberately pending this gate; reference preparation, diagnostics and interface work do not establish model accuracy.

The existing selected-cell dispatcher now also supports `vcell_gene_explore`, `vcell_gene_snapshot` and `vcell_borzoi_panel_get`. `vcell_benchmarks` includes checksummed expanded-panel summaries and saved response diagnostics. Missing completed panels produce an explicit empty state. Panel reports share the existing benchmark interface, with separate coverage and response metrics, no composite score. Gene reports reuse `virtual_cell.protein`, transcript readers, regulatory readers and `virtual_cell_state`; no second state engine or cloud-account system is introduced.

Gene matching requires exact Cellosaurus identity, overlapping hg38 coordinates and compatible Ensembl identity when available. ANGPTL3 lacks a UniProt-to-Ensembl link in the installed annotations: the report explicitly records symbol-only matching to GENCODE, rather than claiming a verified identifier join. Measurements, annotations, computed summaries, predicted tracks and unsupported responses retain separate labels. Saved state bundles include the full typed gene report as provenance.

## Latest Stage 2 evidence and approved continuation

Existing task records now also carry local scientific-check/preparation logs through provider=local, with read-only status and no provider RPC. Atomic task writes and a nonblocking per-task status lock prevent overlapping UI/background fetches. The bounded Borzoi observer never submits/retries inference; it saves evaluation JSON, per-locus CSV, aggregate plot and STAGE2_STATUS.md after successful retrieval. Nine-method response results use the existing benchmark schema/storage and dashboard.
