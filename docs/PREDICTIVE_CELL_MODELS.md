# Predictive model implementations and candidates

5 November 2026. Do not infer availability from an entry in this document.

## Executed local predictors

`virtual_cell_benchmarks.py`, protocol `tahoe-line-plate-holdout/1`:

- `unchanged`: zero DESeq2 log2 fold change, the unchanged-control baseline.
- `training_mean`: average of up to 128 metadata-selected training rows per training line, then an equal mean over lines. Never uses validation/test lines or plates.
- `drug_dose_mean`: average replicate training plates within each donor line at the same drug/dose, then equal mean over available training lines (at least 10 donors).
- `nearest_context`: nearest available training donor in 256 untreated DepMap bulk RNA features. Variance selection, means and standard deviations are fitted on training lines only. This is a simple statistical predictor, not a foundation model.

Every evaluation condition uses the identical finite gene mask for all four models. No zero filling of missing targets. Constant-vector Pearson is null. All four models are retained; none is promoted automatically.

## Borzoi recovery

Official code `calico/borzoi` at `f10f8c799639dd2cfc0c1eb09499bfc47ab9cf8a`; Baskerville-TF at `b06950be1be704ab09ab23ffb6f5102d9e2a63a0`. Existing recipe `bio_borzoi` uses TensorFlow 2.15 GPU on Modal A100-80GB, a 524,288 bp UCSC hg38 window and one human track. Human checkpoint: `https://storage.googleapis.com/seqnn-share/borzoi/f0/model0_best.h5`, 744,112,468 bytes, official GCS object MD5 `ef83ad59b43765413f73767d87a717df` (HEAD checked 5 November local date). SHA-256 is computed after download. Cached files must pass size and MD5 before use; downloads are locked and atomically installed under `/cache/models/predictive-cell-borzoi/<MD5>/`. Existing older cache is untouched.

`params_pred.json` crops 16 bins on either side: 16,352 output bins, 32 bp each; output starts 512 bp after input start. This differs from the training configuration's central 6,144 bins. Metadata, track ordering, tensor shape, nonnegative values, coordinates, code and checkpoint identity are retained. Track 6226 is `ENCFF065PJM+`, `RNA:HepG2`, `sum_sqrt`, scale 0.3, soft clip 384, clip 768. Raw values are not TPM or calibrated read counts. One forward-strand replicate provides no calibrated predictive uncertainty. Code licence: Apache-2.0; original checkpoint/data notices retained, no broader commercial clearance asserted.

No Borzoi installation was found in the inspected local scientific runtimes or configured local model store; the existing integration was a remote recipe, not an already qualified predictor. The official checkpoint endpoint and metadata are accessible. A single paid attempt completed with real model output. SHA-256 `7661c8d8541ae39293b1bf25392a4ec7b97b76114be5ddf82764644c3094eb9f`; see `PREDICTIVE_CELL_BORZOI_EXECUTION.md` for the limited held-out comparison and domain restrictions.

## Candidate selection review

| Candidate | Verified primary source and real semantics | Access/licence boundary | Stage decision |
|---|---|---|---|
| Enformer | [Official code/docs](https://github.com/google-deepmind/deepmind-research/tree/master/enformer): 128 bp tracks, 5,313 human targets, distinct target order/input cropping | TensorFlow Hub checkpoint documented; local checkpoint not verified; model predictions CC BY 4.0 per README | Deferred, no download/inference. Compare only matching assays after assembly and scale reconciliation; never average raw Borzoi outputs with it |
| AlphaGenome | [Official API](https://github.com/google-deepmind/alphagenome) and linked research implementation; up to 1 Mb sequence, multiple assay-specific outputs | API key needed; noncommercial API terms and output-training restrictions; commercial Google Cloud route separate | Accessible research candidate, no configured key or checked checkpoint in this stage; not marked permanently unavailable |
| SpliceAI | [Official release](https://github.com/Illumina/SpliceAI): splice donor/acceptor variant delta scores; GRCh37/38 annotation | Current README: source PolyForm Strict 1.0.0, weights CC BY-NC 4.0; commercial licence separate | Deferred; no model run or isoform-abundance claim |
| GEARS | [Official implementation](https://github.com/snap-stanford/GEARS): genetic-perturbation response; example Norman fitting/pretrained workflow | Requires PyTorch Geometric and dataset-specific configuration; checkpoint and licence audit still needed before integration | Authors explicitly say cross-cell-type training/transfer is not supported. Do not route it as a cross-context Tahoe predictor |
| CPA | [Official implementation](https://github.com/theislab/cpa): dose/condition/covariate response modelling; context-transfer tutorials | Public source; exact release, checkpoint, dataset licence and task fit still need qualification | Stronger follow-up candidate for drug response, after a raw/count-data benchmark and matched controls are established |
| scVI tools | [Official project](https://github.com/scverse/scvi-tools): probabilistic single-cell representations, BSD-3-Clause code | A representation model alone is not a perturbation predictor; data/checkpoint provenance is separate | Deferred; no installation or performance inferred |
| scGen, scGPT, Geneformer, scFoundation | Candidate families from the master request; existing Geneformer plugin entry is not a functioning adapter | Release/checkpoint/licence/task audits not completed in this stage | Deferred, not silently substituted for the executed statistical predictors |
| GB.Cell | Existing `virtual_cell_gbcell.py`, optional licensed plugin | Existing documented ranking test underperformed PCA; not rerun | Preserve evidence; not a recommended downstream-response default |

Primary methodological comparison: [Ahlmann-Eltze et al., Nature Methods 2025](https://www.nature.com/articles/s41592-025-02772-6). The new pilot is independently implemented and does not reproduce that paper's exact experiment or claim its scores.
