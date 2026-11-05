# Predictive datasets and provenance

5 November 2026. New results live in a separate development library, never the active research root. Large Tahoe numeric arrays are opened through read-only NumPy memory maps; metadata is copied; SQLite reference indices have independent copies. Mutable caches, job records, result directories and the library database are separate. Provider account metadata references the existing Keychain identity; no token enters a research report.

## Executed response pilot

- Source: [Tahoe-100M](https://huggingface.co/datasets/tahoebio/Tahoe-100M), `pseudobulk_differential_expression`, CC0-1.0 (current official data card checked). The source's `train` partition is not itself an independent scientific split.
- Installed compact atlas: 65,218 rows × 19,336 fixed panel genes, `lfc.f16`; complete ETL receipt identifies Modal job `437ef0bd9258411a928c5a61d383e0d3`. Original export lacks a pinned Hugging Face revision; this stage records full SHA-256 of actual inputs and does not invent the missing upstream revision.
- Metadata: Cellosaurus, DepMap identity, cell-line name, drug, uM concentration, plate, treated/control counts. Exposure duration, donor identity and exact well/specimen linkage are not retained. Do not silently infer these fields or claim specimen-level independent validation.
- Independent input modality: installed DepMap 24Q4 untreated bulk RNA (`expression.json`, `expression.npy`), CC BY 4.0 according to existing source registry. 47 of 50 Tahoe lines have exact matching profiles. No parent/derivative substitution.
- Full hashes are computed for the LFC matrix, genes, conditions, ETL manifest/progress and DepMap expression files; no shared writable hash cache. Standard-error matrix is not used by this protocol.
- Fixed external gene panel; no feature selection from held-out responses. Float16 precision is a limitation, not a preprocessing improvement.

## Regulatory reference preparation

Official pinned `targets_human.txt`, `params_pred.json`, `sequences_human.bed.gz` were fetched and hashed. Official test fold = fold3, validation = fold4. FABP1 (`ENSG00000163586.9`, GENCODE V29) lies inside `chr2:88023337-88219945` fold3 (0-based half-open). Input = `chr2:87859497-88383785`, hg38, exactly 524,288 real UCSC reference bases, sequence hash in the execution plan. No assembly conversion or synthetic padding.

[ENCODE ENCFF065PJM](https://www.encodeproject.org/files/ENCFF065PJM/) is released GRCh38 bigWig, plus-strand signal of unique reads, experiment ENCSR000CPE, 167,109,347 bytes. It is compatible as an assay reference for track 6226; the model authors reprocessed RNA coverage, so original ENCODE signal is not automatically identical to the training target transform. A rank-based locus check must retain this limitation. The two existing ENCODE RSEM transcript files remain separate TPM evidence; they are not used as per-bin genomic track truth.

ANGPTL3 (`chr1:62597486-62606159` after GTF conversion) overlaps fold5 training regions. It is suitable for an evidence walkthrough, not an independent Borzoi holdout score. ALB is fold0 and GAPDH fold4 in the inspected intervals; these were not relabelled as test genes.

## Deferred datasets

Existing Norman 2019 and Replogle 2022 pack hashes/benchmarks were inspected, not redownloaded. The partial Nadig HepG2 file is untouched. scPerturb, Perturb-seq, Arc Virtual Cell Challenge, LINCS/L1000, matched RNA/protein, longitudinal aging and matched multimodal data require task-specific release/licence/split checks before additional downloads or training. Their names do not establish an implemented pipeline.

## Stage 2 independent data snapshot and reference extraction

Stage 2 uses an independent SQLite backup and copy-on-write numeric input snapshots; mutable jobs, results and caches are separate from the original library and Stage 1. Reference annotation, BED split, target catalog and array checksums are retained. Reference manifest schema is `fold.borzoi.panel-reference/1`; observed arrays hash is `58e07916bb68fcc641ab3d488165b99350180b049ff3cc512fc9aa39bcfcd328`.

Additional matched assays: [ENCFF136DBS](https://www.encodeproject.org/files/ENCFF136DBS/) is GRCh38 HepG2 DNase read-depth-normalized signal, official target 1303; [ENCFF980ZHM](https://www.encodeproject.org/files/ENCFF980ZHM/) is GRCh38 K-562 plus-strand unique-read RNA signal, target 6122. Original [ENCFF065PJM](https://www.encodeproject.org/files/ENCFF065PJM/) remains HepG2 RNA 6226. Cellosaurus/assembly/output-type metadata is checked. DNase bins use mean signal; RNA bins use sums. All 32 bases must be covered; missing data is not zero-filled. Provider MD5 and retrieved metadata hashes are recorded, but full bigWig MD5s were not independently verified because extraction uses remote byte ranges. No full bigWig or new checkpoint was downloaded.

ENCODE transcript TPM, DepMap log2(TPM+1), original genomic coverage and PaxDb ppm remain separate quantities. No simultaneous, paired multimodal dataset or raw Tahoe single-cell/control matrix has been established by this stage.
