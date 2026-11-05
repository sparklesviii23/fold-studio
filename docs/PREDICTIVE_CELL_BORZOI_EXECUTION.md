# Authentic Borzoi execution and reference check

5 November 2026 (Europe/Bucharest). Exactly one paid attempt was explicitly approved by the user and submitted through the existing Modal task manager. No retry, second inference or training run was launched.

- Job `af2b5ce1548e4fac95abd2781049c7c9`: completed, exit 0; retrieved artifacts pass the existing task manifest checks and the new read-only Virtual Cell bridge.
- GPU: NVIDIA A100-SXM4-80GB, TensorFlow 2.15.0; actual environment/GPU receipts are saved with the task. Model: official Borzoi human replicate 0. Code/Baskerville pins are in `PREDICTIVE_CELL_MODELS.md` and the result.
- Official checkpoint MD5 `ef83ad59b43765413f73767d87a717df`, size 744,112,468, verified against the public GCS object. Downloaded checkpoint SHA-256 `7661c8d8541ae39293b1bf25392a4ec7b97b76114be5ddf82764644c3094eb9f`.
- Checkpoint persisted remotely at `fold-gpu-cache:/models/predictive-cell-borzoi/ef83ad59b43765413f73767d87a717df/model0_best.h5`. It was not downloaded into the application/repository or bundled with a release.
- Real reference: hg38 chr2:87859497–88383785, 0-based half-open, 524,288 UCSC bases. Sequence SHA-256 `a4e613b77ef4074c7034cca690eb23afefe8edeab18a114e6d46926d8937d580`; cloud result equals the independently prepared local reference hash.
- Output: 16,352 nonnegative finite bins, 32 bp, chr2:87860009–88383273; track 6226 `ENCFF065PJM+`, RNA:HepG2; raw transformed assay coverage (`sum_sqrt`, scale 0.3, soft clip 384, clip 768). CSV SHA-256 is in the retrieved manifest.

## Held-out locus reference comparison

Prespecified central window: chr2:88023337–88219945, official **fold3 test region**, containing FABP1 (`ENSG00000163586.9`). ENCODE ENCFF065PJM is a released GRCh38 plus-strand signal track for parental HepG2 (Cellosaurus CVCL_0027), experiment ENCSR000CPE. Assembly, assay, experiment, strand, cell identity, coordinate alignment and file metadata are checked.

45 of 6,144 32-bp bins have complete finite ENCODE signal. Uncovered bases are not imputed as zero. Spearman correlation between raw model prediction and summed observed plus-strand signal over these **45 covered bins** is **0.4447560901**. No count-scale MSE or independent-bin confidence interval is reported. The score is conditional on reference coverage and does not quantify accuracy over the uncovered region.

The author training pipeline used reprocessed `.w5` coverage and target transforms; this check uses the original ENCODE signal. It is a genuine held-out-locus, rank-based assay-reference check, **not exact reproduction of the authors' benchmark**, genome-wide validation, unseen-assay transfer, proof of phenotype prediction, or superiority over another predictor.

Initial libBigWig opening through ENCODE's download redirect failed. Resolving that same official public-data redirect with urllib and passing its destination to libBigWig worked. Only byte ranges were read; no full 167 MB download or full-file MD5 verification is claimed. The published source MD5 and hashes of metadata, official split BED and extracted reference arrays are retained. Signed/expiring redirect URLs are never persisted.

## Integration and reproducibility

The real track was opened in Virtual Cell → HepG2 → Genomic regulation through the real worker. The viewer retains separate predicted and observed units/scales and reports missing coverage. `vcell_snapshot_save` with `regulatoryRun` stores the full verified track in the existing evidence-typed state history as **prediction** with checkpoint, assay, coordinate and comparison provenance. It does not overwrite the cell's measured expression or operation history. Existing export/import provides checksummed persistence.

Local comparison command (does not launch inference):

```sh
<comparison-python> scripts/benchmark-borzoi-reference.py --library <isolated-library> --reference-dir <reference-cache> --run af2b5ce1548e4fac95abd2781049c7c9 --expected-sequence-sha256 a4e613b77ef4074c7034cca690eb23afefe8edeab18a114e6d46926d8937d580
```

Comparison runtime: existing NumPy/SciPy accessed read-only plus pyBigWig 0.3.25 installed in a separate local environment. Metadata/split cache and result artifacts are independent of the active research library. Comparison JSON and CSV are checksummed and tied to the exact original job result/checkpoint. Replaying saved output and reference is not a second model execution; inference repeatability across GPU/library versions remains untested.

## Resources and limits

The single cloud attempt had a 900-second runtime bound. Container/image build time was additional. No total dollar cap or final billed amount is available through the existing account API; the initial planning GPU line item was about $0.63 at the 15-minute GPU-task list rate, with CPU/memory/build/storage extra. This is not a billing receipt, and execution used the existing Modal Sandbox-based infrastructure. No further paid runs are authorised by this receipt.

Demonstration A is fulfilled as authentic, identified reference inference displayed with a suitable, explicitly limited observed-track comparison. Broad scientific model validation, chromatin-task evaluation, ensembles, reverse-complement averaging, calibrated expression and cross-model superiority remain incomplete.

## Stage 2 pending execution

No new Modal job has been submitted. The proposed single job repeats Stage 1 first, then runs the frozen 100-test-locus / four-illustration / three-track / two-replica panel. One new 744 MB f1 checkpoint is required; f0 cache reuse is verified on use. The scoped request estimates $2–$5, A100-80GB, 45-minute execution limit, one attempt and no automatic retry. At the current listed GPU rate, the runtime limit corresponds to $1.8738 GPU time, plus CPU, memory, image-build and storage charges. A time limit is not a dollar cap or a final bill. The project AGENTS.md requires explicit approval before paid runs/model downloads; Stage 1 permission does not authorize this expanded run.

The job reads the prior remote CSV from the existing Volume, verifies its known SHA-256, repeats the exact sequence/track/checkpoint and compares all bins at rtol 1e-4 / atol 1e-6. Failure stops before expanded inference. Artifact retrieval and cancellation reuse `gpu_tasks`. A durable one-attempt claim must be written before submission to prevent a duplicate after ambiguous launch. Local observed-reference extraction is complete, but is not model execution or a benchmark result.

### Authorized continuation · 5 November 2026

The first Stage 2 request (`8d4ecd336dad4d9bb7ce4b1e6b521535`) was rejected before allocation: Modal limits a secret/configuration value to 32,768 bytes; the serialized input was 38,785 bytes. No sandbox identifier or inference output was created. The prior Linux environment-size preflight was insufficient. The immutable failed claim is retained.

After the user requested continuation including starting the pending process, one corrected request (`7751fc7a5bb7483e906538dc28b29daa`) was submitted under the same panel, cost estimate and 2,700-second runtime limit. Its deterministic gzip/base64 transport is 9,808 serialized bytes in the execution runtime. Decoding is bounded, rejects truncated/concatenated/oversized streams and preserves the exact frozen manifest. A separate durable claim links the rejected request; neither claim is reset. No automatic retry is enabled. Execution/reproduction results remain pending until retrieved.

The user requested idle behavior while cloud execution proceeds, to conserve chat usage. Stop active work once launch is confirmed; do not continuously poll or create a usage-consuming monitor. On the next user continuation, inspect this same job, retrieve its artifacts through the existing task manager, verify the reproduction gate, and resume the remaining scientific evaluation.

### Retrieved outcome

Job `7751fc7a5bb7483e906538dc28b29daa` ended with exit code 1 during subsequent UCSC reference-sequence acquisition (HTTP 400). Before that failure, fresh Stage 1 reproduction **passed exactly**: all 16,352 values and CSV bytes match, max absolute difference 0.0; checkpoint SHA-256 remains `7661c8d8541ae39293b1bf25392a4ec7b97b76114be5ddf82764644c3094eb9f`. The reproduction gate is now satisfied. Four retrieved partial artifacts are retained; expanded inference/accuracy remain incomplete. No rerun has been submitted. The new Run control interface makes this distinction and saved process output inspectable.
