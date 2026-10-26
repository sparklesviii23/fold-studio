# Single-cell engine — genuine cloud reference, 26 October 2026

The Scanpy workflow is implemented, deployed and executing on Modal CPU. This is a bounded raw-UMI workflow, not completion of the full Single-Cell & Perturbation Laboratory or EditCraft directive.

## Working path

In **Genome & RNA Engineering → Single-Cell & Perturbation**, select the public PBMC3k reference or import an original H5AD locally. Importing preserves bytes without uploading or running scientific analysis. Dataset preparation requires separate transfer and cost approval. Its receipt pins the original file's size and SHA-256 to the selected cloud account.

Prepare analysis to pass explicit filters, seed and observed genes into the editable workflow. Review shows the actual two-CPU, 8-GiB memory profile and estimate. Both separate approvals are required before launch. The isolated scientific environment has no GPU and no automatic scientific retries. Source updates retain existing model/tool runtimes and cloud assets.

The current workflow performs count QC, total-count normalization to 10,000, log1p transformation, Seurat highly variable genes, scaled PCA, neighbors, seeded UMAP and Leiden clustering. Original inputs and metadata are preserved. Actual per-phase events flow through the existing experiment controls. Failure details are retained privately with the owning experiment and retrieved explicitly; raw exception messages are not emitted to provider logs.

The native result displays genuine UMAP coordinates, observed gene or provided-metadata colours, barcode search, cluster/cell selection, full-population mean expression, exploratory markers and provenance. Expression histograms use returned observed values; if the display is sampled, that restriction is explicit. Full-population sizes remain separate from sampled presentation. User annotations are versioned evidence and do not replace source labels.

## Real reference

- Official Scanpy loader's original PBMC3k H5AD: 5,855,727 bytes; SHA-256 `89a96f1beaa2dd83a687666d3f19a4513ac27a2a2d12581fcd77afed7ea653a1`.
- Source matrix: 2,700 cells × 32,738 features, 2,286,884 stored entries. One healthy human donor; no perturbation labels or replicated donor groups.
- Completed job: `aa4aef6fb37c4d4e8f41b1d6e9273f5c`, seed 42. Retained 2,638 cells × 13,714 features; seven computational clusters of 1,176, 342, 153, 486, 432, 36 and 13 cells.
- Finite actual UMAP, unique barcodes, declared QC thresholds, expression/cell correspondence and population means all checked against the saved result.
- Complete H5AD was reopened remotely: shape, cell IDs, feature IDs, UMAP, original count layer and archived original cell/feature metadata match exactly.
- Exported processed H5AD: 15,278,743 bytes; SHA-256 `c20dfa432de3f58c43290feb27f56f37c9115284b6da09915839cdd7fe66a9a0`. The streamed copy matched the original byte receipt and checksum before destination replacement. The disposable transfer-check copy was removed; original source, processed artifact and scientific evidence remain in the research volume.

`reports/editcraft/singlecell-validation.json` retains original parameters, full result/provenance, package freeze, phase events, source identity and all previous attempts. `native-singlecell-workflow.json` records actual native observations. These are execution and integrity checks, not independent biological accuracy certification.

## Failures preserved and corrected

The first attempt, `b023bbe6c6214cf5834c78b97c9d051c`, failed before QC because the real public file uses legacy `h5sparse_format` / `h5sparse_shape` metadata. The parser now accepts verified legacy or modern CSR/CSC metadata, rejects conflicting layouts, and validates array dimensions, pointers and index bounds before scientific loading. Original source bytes were not rewritten. A separately approved second scientific attempt completed; no automatic retry was used.

The completed attempt then exposed an artifact-download guard defect: Modal's mounted research volume resolves through a symlink. The guard resolved only the artifact, so it rejected the legitimate resolved path. It now resolves both root and artifact, retains experiment containment/size/SHA checks and rejects external symlink escapes. The already saved artifact was verified after that source-only correction; the scientific calculation was not repeated.

The two approved scopes total up to $3.25, including runtime preparation, the failed attempt, the corrected attempt and output verification. Each scientific reservation was $0.1290. Reservations are conservative local estimates; actual provider charges remain unknown. No new work is automatically authorized by these receipts.

## Boundaries and remaining work

Input is bounded to 8 MiB, 10,000 cells, 40,000 features and 15 million sparse entries; dense matrices have a separate bound. Display defaults to 3,000 cells and a 3-MiB JSON limit. Deterministic display sampling never changes the full scientific analysis, full-population expression summaries or H5AD. Complete processed-file retrieval is optional and explicit, bounded to 128 MiB.

Supported inputs require raw nonnegative integer UMI counts in X, unique identifiers and an explicit mitochondrial feature prefix. External HDF5 links and unsupported compression are rejected. This is not a universal multimodal or million-cell ingestion engine.

Cluster markers are exploratory cell-level Wilcoxon comparisons of computed groups. They are not donor-replicate differential expression, perturbation response, causal mechanism, confirmed cell type or tumor microenvironment evidence. No measured uncertainty or biological effect is invented.

scvi-tools, Pertpy, CELLxGENE ingestion, perturbation datasets/contrasts, donor-aware statistics, batch correction/diagnostics, inferred cell types, pathway enrichment, multimodal support and independent benchmarks remain separate unfinished requirements. The complete directive remains false.
