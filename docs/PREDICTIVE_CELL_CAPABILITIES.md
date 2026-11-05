# Predictive Cell capability audit

5 November 2026. Baseline `28621281feee447605233761f0ea4d451adf6ca8`. This is an incremental research stage, **not completion of the master directive**. Historical functioning claims below come from inspected adapters and recorded project evidence; this stage re-executed the new Tahoe evaluation and shared-worker evidence retrieval. It did not requalify every existing model.

Scope: `virtual_cell_registry.py`, `virtual_cell*.py` adapters named below, `biological_model_{recipes,runner}.py`, `perturb_model.py`; existing `VIRTUAL_CELL_{CAPABILITIES,INTEGRATION,VALIDATION}.md`, `BIOLOGICAL_MODELS.md`, `EDITCRAFT_SINGLECELL_ENGINE.md`, `RNA_TO_PROTEIN_LAB.md`. Focused inspection; no exhaustive repository-wide implementation search. Optional model names in the plugin catalogue are not counted as functioning models.

Statuses are cumulative evidence, not synonyms: available, installed, executing, integrated, benchmarked, validated within a defined domain, out-of-domain, partially implemented, deferred, unavailable. A software test alone never establishes scientific validation.

| Capability | Existing foundation | New implementation | Real inference | Independent benchmark | Scientific limitations |
|---|---|---|---|---|---|
| Regulatory genomics | Pinned official Borzoi remote recipe; no previous real run recorded | Verified immutable checkpoint cache; shape/track/provenance checks; Virtual Cell genomic-track reader/viewer | Completed official human replicate 0 on A100; 16,352 real bins | FABP1 fold3: Spearman 0.444756 on 45 covered bins; not a validated genome-wide domain | ANGPTL3 overlaps training fold5; human head hg38 only; raw transformed assay coverage |
| Chromatin and transcription regulation | Borzoi track catalogue; generic genome reference workspace | Assay metadata retained with genomic output | No new chromatin assay inference | Not executed | No integrated enhancer–promoter or TF causal-network predictor |
| RNA expression prediction | K-562 statistical transitions and Tahoe response adapters | Strict line-and-plate holdout response evaluation | Four simple predictors executed on real installed data | 72 test conditions, 9 lines; negative MSE results | Pseudobulk response, not a complete expression distribution |
| Alternative splicing | RSEM isoform measurements; RNA folding lab is a separate task | SpliceAI/AlphaGenome access review only | Not executed | Not executed | No working splicing predictor qualified; isoform TPM is not splice probability |
| Cellular-response prediction | Norman/Replogle effects; additive/ridge; drug transfer | Reproducible training-only mean and nearest-context predictor | Executed locally | Benchmarked under the new explicit protocol | All tested predictors lose to unchanged control on mean test MSE |
| Single-cell state modelling | GB.Cell plugin and existing embedding tests; independent Scanpy lab | None promoted | Historical GB.Cell evidence only | Existing ranking MRR 0.066 vs PCA 0.156, not rerun | No validated transferable multimodal state; no proprietary AIDO access |
| Small-molecule response | Complete local Tahoe pseudobulk atlas; interpolation and transfer | Same-condition donor prediction, three relevant simple comparisons | Executed | Entire lines and plates held out; no unseen-compound claim | Only 8 prespecified test drug/dose conditions per line; 2 test plates |
| Protein abundance | PaxDb measured ppm; RNA–protein rank view | Evidence preserved | No predictive protein model | No matched-pair predictive evaluation | Different experiments/years; not paired RNA/protein training data |
| Protein localization | HPA/UniProt annotations; Human-GEM fallback | Preserved | Annotation lookup, not new predictive inference | No new evaluation | General annotation, not line-specific localization measurement |
| Protein structure | Existing Boltz/AlphaFold saved structures and mapping | Preserved read-only integration | Historical saved outputs; not rerun | No new independent structure benchmark | Structural confidence does not establish cellular interaction/activity |
| Protein interaction evidence | Complex structures, Reactome membership, saved evidence | No new causal interaction predictor | Not executed | Not executed | Pathway membership and structural confidence are different evidence types |
| Cellular morphology | Actual Cell Painting; CellFlux and committed benchmarks | Existing benchmark kept unchanged | Historical completed CellFlux runs | Eight-compound BBBC021 result verified in committed report | MCF7 held-out cosine 0.61 vs baseline 0.62; no HepG2 validation |
| Temporal dynamics | Cell-cycle ODE; SPARCED; physics/RNA labs; replay | Preserved | Existing simulation evidence, not rerun | No new line-calibrated temporal benchmark | Generic mechanisms; static images do not establish trajectories |
| Uncertainty | RSEM credible intervals, solver diagnostics, model-specific checks | Crossed line/compound bootstrap for score uncertainty | Computed on real held-out errors | 1,000 draws; recorded null correlations | No calibrated per-gene predictive intervals; only two test plates |
| Cross-modal consistency | Identifier/context/unit checks and typed snapshot blocks | Explicit assay/cell refusal; train/test provenance | Real ANGPTL3 RNA/evidence retrieval | Software consistency tests; no new paired multiomics benchmark | No false RNA=protein constraint; missing measurements stay missing |
| Training and adaptation | Existing statistical ridge fits; optional model recipes | Training-only baseline fitting and reproducible nearest-context features | Statistical fitting only | New held-out evaluation | No foundation-model training, fine-tuning or shared-latent training |
| Independent benchmarking | Existing Norman, Tahoe, GB.Cell, CellFlux studies | Integrated dashboard, immutable saved predictions, full input hashes, exact metric replay | Executed through actual worker | 45 validation + 72 test conditions; all 117 replay exactly | New pilot differs from older selected-active-gene score; cannot compare values as the same task |
| Hypothesis generation | Research dossiers, evidence registry, deterministic controller | Failure and missing-data reports | Evidence retrieval only | No validated discovery engine | Computational hypotheses are not experimentally validated discoveries |

HepG2/C3A, COLO 205 and hTERT-HPNE are excluded from this nearest-context benchmark because no matching untreated DepMap RNA profile is present. Parental HepG2 is not a replacement for C3A. SNU-423 is an actual test context; the worker and UI demonstrations use it.

No shared learned cellular state, cross-modal decoder, aging predictor or foundation-model adaptation is represented as complete. Demonstration B/E are bounded statistical response comparisons; A completed as a limited held-out locus check (see `PREDICTIVE_CELL_BORZOI_EXECUTION.md`); C is partial evidence retrieval; D is deferred.

## Stage 2 status checkpoint

- **Integrated and operationally tested:** observed-versus-predicted gene reports inside the existing Protein & pathways workspace; measured RNA/transcripts, protein/localization, Reactome and saved-structure handoff, existing state-history save/restore/export. Actual HepG2 ANGPTL3 worker/browser walkthrough passed. Regulatory and cellular-response prediction are explicitly unsupported when no compatible completed result exists.
- **Reproduced:** original four-method 72-test/45-validation response benchmark and saved FABP1 reference correlation. This does not complete fresh inference reproduction.
- **Implemented, not executed or scientifically benchmarked:** frozen 100-locus Borzoi panel, three-track reference extraction, authentic two-replica cloud runner, ensemble/profile evaluator and dashboard reader.
- **Diagnosed:** original response failure with original all-gene metrics retained, sample/batch/signal summaries and independent-other-plate gene-selection diagnostic; technical versus biological causes remain partly unresolved.
- **Deferred behind the fresh inference gate:** stronger statistical model fitting and advanced-model comparison. No new response predictor is promoted. No multimodal world model, mechanistic cross-modal abundance conversion or independent-study validation is claimed.

Checks in this checkpoint: 104 backend tests (72 existing Virtual Cell, 12 Stage 2 invariants, 10 Biological Models, 10 GPU lifecycle), 15 Virtual Cell interface tests, TypeScript, production Vite build and scientific source-resource closure (164 modules) pass. Existing nonfatal RNA/protein SVG title warnings remain. No native Tauri build/install was performed.

## Latest Stage 2 evidence and approved continuation

Current checks: 116 targeted backend and 252 frontend tests (70 files) pass, plus TypeScript, production web build and 164-module resource closure. Local test/response tasks now appear in the existing run controller. The full response comparison and all negative results are saved. Expanded Borzoi completion remains pending until the newly approved job is evaluated; installed app remains unchanged.

## Completed expanded evaluation · 5 November 2026

Completed job 168711aa3e4c48c592bba62636a8763c: 100 attempted held-out loci, 99 valid inferred test inputs plus four separate illustrations, three tracks, f0/f1 and mean ensemble. Ensemble mean locus Spearman: HepG2 RNA 0.549361 (77/100 scored, CI 0.504003–0.593526); HepG2 DNase 0.722433 (99/100, CI 0.693813–0.749814); K-562 RNA 0.464252 (73/100, CI 0.418502–0.507656). Aggregates condition on scorable loci; missing coverage and the boundary failure remain explicit. Current original-tolerance comparison and same-device repeat both pass; prior SXM4 cross-device failure is retained. This is related-assay genomic holdout evidence, not independent-study validation, count calibration, protein prediction or a world model.
