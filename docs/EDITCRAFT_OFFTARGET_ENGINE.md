# EditCraft off-target reference engine

The genuine Cas-OFFinder 2.4.1 CPU adapter is implemented and has passed four separately approved Modal reference calculations. This completes the tested adapter/reference workflow, not the wider CRISPR specification or human-genome qualification.

## Source and scientific meaning

- Original publication: Bae, Park and Kim, *Bioinformatics* (2014), DOI [10.1093/bioinformatics/btu048](https://doi.org/10.1093/bioinformatics/btu048). Its public full text was inspected through Europe PMC, PMC4016707.
- Official repository: [snugel/cas-offinder](https://github.com/snugel/cas-offinder), stable tag 2.4.1, commit `9816b94c20c4cba2e79b039e1e2a6dee684b7b66`. Upstream warns against production use of version 3; this integration does not silently substitute that version.
- The 25,345-byte source archive has SHA-256 `3505e2a6f37f4ca366cce0293c1ad1396ce2208ed44bfd2dde435df77dcc869b`. Cloud installation verifies it before compilation. BSD-3-Clause copyright, license and original README are retained beside the compiled tool in `/opt/editcraft-tools/`.
- CPU OpenCL is supplied by POCL. Only two CPU threads are allowed. There is no GPU allocation or local scientific-tool installation.
- This finds sequence matches, including intended sites. Counts are not cutting probabilities, measured editing, functional effects or safety scores. Rule Set 3 activity remains a separate result.

## Input, reference and coordinate contract

The supported adapter contract is 1–64 unique, explicit 20-base SpCas9 DNA spacers, a restrictive IUPAC 3′ PAM and 0–6 spacer mismatches. No bulges, Cas12-specific geometry or variant-aware/pangenome search is inferred. Bounded inline FASTA is labeled supplied-sequence-only even if its user-provided name resembles an assembly.

The first curated installed reference is NCBI `GCF_000005845.2` (E. coli K-12 MG1655, ASM584v2). Its published compressed MD5, exact full contig manifest (`NC_000913.3`, 4,641,652 bases), retained FASTA SHA-256 and per-contig sequence SHA-256 are checked. The cloud stores one reference copy. Preparing it requires a separate download/cost approval and does not start a search.

Circular reference searches append a disposable origin-overlap window; original reference bytes remain intact. Returned hits are independently checked against the original source sequence and strand. Output preserves the original zero-based position and raw TSV, and adds 1-based inclusive intervals. Origin-crossing hits use explicit split intervals. Upstream mismatch counts and PAMs must independently agree; duplicate, ambiguous or out-of-range sites are rejected. Excessive output fails with original artifacts preserved rather than presenting a partial search as complete.

Human whole-genome assembly preparation, larger resource profiles and qualification are still required. The bacterial whole-assembly run does not certify those cases.

## Real calculations

`reports/editcraft/offtarget-validation.json` records the approval, original setup failure, corrected guarded deployment, source/reference identities and full actual results:

| Job | Reference check | Outcome |
|---|---|---|
| `30f0e76b502743babaa9514993d0f0f9` | Forward exact site, reverse-strand one-mismatch site, absent guide | Two expected sites; complete equality with independent exhaustive synthetic oracle |
| `cbdf17aa8d2a43d39dbfdca656edf9a1` | Circular origin-crossing site | One expected site; exact source-coordinate/strand agreement |
| `881b5f7ca8084770995c26f2ba0baa00` | Original first 1,000 bases of NC_000913.3 | Exact assembly receipt and sequence window retained |
| `0f4f204ea2dd470b9efaf1528833bb2d` | Full circular 4.64 Mb reference, spacer from observed window | Expected exact site at original forward position 2 retained; full contig/reference receipt matches |

The four science-job reserves total $0.4252. That is an estimate, not actual provider charges. Authorization was $1 deployment, $0.50 public reference preparation and $0.50 for these four reference calculations, $2 total. No fifth calculation is covered by that scope. No independent biological activity benchmark is claimed.

## App integration

CRISPR Architect contains reference selection/preparation, explicit FASTA/assembly/topology input, spacer/PAM/mismatch controls and result tables. Inputs go through the same offline review, transfer approval, cost approval, saved job identity, refresh, cancellation, result retrieval and notebook paths as existing EditCraft analyses. The exact reference checksum is part of the approved plan. Preparing or viewing a form never uploads or executes it.

`reference_window` retrieves up to 10,000 observed reference bases with explicit strand; it does not infer a transcript or guide quality. Tool receipts are separate from `editcraft_assets.json`, preserving the existing RS3/BE-DICT/PRIDICT2 checkpoint receipts. Deployment uses the existing atomic writer-lease guard and refuses to replace an active scientific worker.

The current native build was inspected after the user allowed its renewed Documents permission. The verified assembly checksum, actual complete-reference hit and typed input-to-review path were displayed. Launch remained disabled with both approvals clear. Evidence: `reports/editcraft/native-offtarget-workflow.json`. Molecular-viewer acceptance remains a separate matrix.

## Variant annotation addition

`variant_vep` is also implemented and deployed, with separate native genomic-SNV controls. It selects the official GRCh37 or GRCh38 Ensembl host, verifies the host assembly and forward reference allele before submitting a variant, and checks the returned assembly/coordinate/strand/alleles. Original transcript consequences, transcript versions, HGVSc/HGVSp when returned, REST responses/checksums and Ensembl release information are preserved.

This is an explicit human-SNV contract. It does not implement indel normalization, liftover, structural-variant interpretation, calibrated pathogenicity or clinical advice. Six offline API contract tests passed. One separately approved $0.25 public Modal CPU reference completed: job `46479b605558401e84c5a1671cb84abe`, official example GRCh37 21:26960070 G>A. Its allele/assembly identity matches an independent curated dbSNP reference; all three original transcript annotations and four complete HTTP receipts are retained. Actual result rows were inspected in the installed app. Evidence: `reports/editcraft/vep-reference-review.json` and `reports/editcraft/native-vep-results.json`. The science reservation is $0.1126, not actual provider charges. The public documentation-example identity is independently retained in `fixtures/editcraft/vep/` from Ensembl's dbSNP reference endpoint; that curated-data retrieval is not a scientific model benchmark.
