# Expanded biological Qwen experiment

Prepared locally on 6 November 2026. No cloud upload, image build, GPU allocation or new model download has started. The project requires explicit approval before a paid attempt.

The model retains its internal frozen RNA expert and adds a Qwen correction over all 2,132 genes. New activation, inhibition and drug heads share Qwen's biological representation while retaining their own numerical units. The original 3B Qwen base stays frozen; internal attention adapters, the numerical input projection and biological heads are trained. This does not expand all of Qwen's original weights or create a whole-cell simulator.

## Data

- Full descriptions, without truncation: primary descriptions need at most 128 tokens; cell descriptions at most 283. The actual supported context is 32,768 positions, with five reserved for numerical/query inputs. Oversized descriptions fail during local preparation. Padding follows the longest actual input rather than filling unused context.
- Exactly 2,000 distinct measured cells: 1,000 Norman K562 activation cells and 1,000 Replogle K562 inhibition cells. Old Norman development/test pairs and new held-out inhibition targets are excluded from cell selection. Twenty percent of measured profile entries are masked; only the visible genes enter ranked text and numerical features.
- 102 existing activation calibrations, 128 inhibition training targets, and 128 drug training conditions from 32 drugs. New inhibition validation/test groups have 32 targets each. New drug validation/test groups have eight whole drug identities each, four conditions per drug. Drug identities remain disjoint across cell lines, doses and plates.
- Gene masks preserve missing measurements. Inhibition masks exclude the directly targeted gene. Drug DESeq2 log2 fold change and source-centered log1p RNA counts are separate objectives with training-only scales. Plates are aggregated within a drug/line/dose condition; conditions from the same drug are not independent drug replicates.
- New inhibition and drug test answers stay outside the cloud input folder. Cloud code can see test inputs/masks, and generates their predictions only after checkpoint selection. The local observer seals selected weights/predictions before loading answer arrays. The old 26 Norman test outcomes remain unopened by this experiment.

The underlying public screens were already available in the library. These are within-dataset holdouts, not independent-study validation. The primary 77 training / 26 reused development cases and RNA expert remain unchanged. Repeated use of those 26 development cases limits interpretation.

## Fixed experiment and cost

Three seeds (20261106–20261108), one full foundation pass per seed over all prepared examples, then paired activation learning in two matched versions: further Qwen adapter learning versus fixed Qwen adapters. Numerical inputs/readout can learn in both versions. Each version gets at most 12 full epochs, batch eight, early stopping after three unimproved epochs. Primary correction begins at exactly zero, retaining the expert reference. Seed summaries and all selected epochs are reported; the lowest primary development error selects one checkpoint. Auxiliary validation/test results are reported separately, not pooled across unlike units.

One Modal A100-80GB sandbox, eight CPU cores, 32 GiB requested host memory, 2,700-second container limit. A 2,670-second in-process alarm leaves shutdown time. Local staging/build supervision is limited to 90 minutes and does not allocate a GPU until upload commits and remote file sizes match. A lightweight local observer fetches completed outputs and scores new local holdouts; it never submits another run. One durable attempt claim prevents repeat submission with the same prepared plan, including after failure. No automatic retry or app predictor promotion.

Estimated **$4–$7**, not a dollar cap. At the checked [Modal prices](https://modal.com/pricing), maximum GPU time is about $1.87; sandbox CPU and requested memory add about $1.43 at their non-preemptible rates. Image building, actual memory consumption, persistent storage and transfer may add charges. Allowances/credits are not assumed. Existing approved Qwen weights are uploaded, not downloaded again. No paid fallback or larger GPU substitution.

The official PyTorch 2.7.1 / CUDA 12.8 runtime image was verified in Docker's registry and pinned by digest. Transformers 4.57.6, NumPy 2.2.6 and Safetensors 0.6.2 are pinned. Actual CUDA qualification is pending the approved experiment.

## Controller and sealed preparation

The existing native Virtual Cell → Runs & terminal controller can show the staging log, image build, GPU log, stop control and returned files. No app replacement is needed for that existing controller. Source adds a prepared-only recipe and hides it from the generic task form, so an empty form cannot bypass data staging. Future packaging includes its standard-library recipe module. The new training source itself runs in the prepared cloud job, not the app's default scientific runtime.

`scripts/run-qwen-cell-cloud.py` requires the exact plan, an existing project and `--approved-once`. It creates the task record and consumes the one-attempt claim before staging. Uploads use only explicitly named source, data, warm weights and the already approved checkpoint; no whole-library upload or credential files. Source and input files are hashed locally, committed to the existing account's volume and checked before allocation. All staged bytes are hashed again before model loading.

Prepared artifacts: task `outputs/stage9/expanded-data` and `outputs/stage9/cloud-study/PLAN.json`. Dataset SHA256: `3fc9a231c6d08513d12861f7779ee0299bd4f256c9cc61296bd6d2aaded10124`. Asset manifest SHA256: `7bff9e9d5ffa3568250155ce073704227eb61220790f11383543d854990b1253`. Upload list totals 6,233,846,292 bytes (about 6.23 GB), dominated by existing approved weights; test answers are absent.

Verification: 13 new offline engineering checks, 10 existing hybrid checks including MPS, 10 GPU-manager regressions and six run-controller checks pass (39 total). TypeScript and scientific resource closure pass. Real-data audit confirms distinct cells, disjoint intervention groups, finite inputs, complete trailing context and warm checkpoint/expert compatibility using a shape-only Qwen skeleton. Synthetic tests exercise the complete worker, two arms, preserved expert buffers, saved-weight reload, bfloat16/SDPA gradients and padding, upload-before-launch failures and local answer sealing. None establishes CUDA execution, biological improvement or independent generalization.
