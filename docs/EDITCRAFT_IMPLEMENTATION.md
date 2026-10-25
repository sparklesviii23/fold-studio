# EditCraft implementation and evidence

This is a working first vertical slice, not completion of either master directive.
Full requested scope is retained in EDITCRAFT_EXECUTION_STATE.json. Missing
scientific implementations are not disguised as completed catalogue entries.

## Implemented

One Genome & RNA Engineering workspace inside the existing native Tauri app,
using the established navigation, Molecular Laboratory, Research Library, Modal
account credentials and file-export controls. No independent browser client.

A project-scoped Biological Registry with immutable versions, parent-version
conflict checks, preserved imports and linked Library records. Notebook versions
and automatic experiment/result receipts use that registry. Research exports are
JSON and Markdown; sequence export is FASTA. Rich-text notebooks and PDF/DOCX
publishing are not yet implemented.

An executable ordered workflow editor with typed gene-context → CDS-analysis →
RNA-folding handoffs. Unknown methods, forward dependencies and unregistered
conversions are rejected. Explicit parameter input remains available for each
implemented operation. It is an ordered pipeline editor, not a general graph UI.

Separate Modal CPU application `fold-editcraft-engine`, independent named Volume
and Dict, pinned Python 3.12, numpy 2.2.6, Biopython 1.85 and ViennaRNA 2.7.2.
No genome-editing trained models are installed in the macOS application.
Production scientific operations run in an isolated cloud subprocess with a
hard per-plan deadline, cancellation, deterministic request identity and no
automatic scientific retries. Dataset transfers and CPU cost require explicit
approval. Status logs contain operation identities/states rather than genomic
inputs. Result contents are checksum-verified before import. Model access and
account identity are retained independently of protein campaigns.

Scientific operation implementations:

- Ensembl gene/transcript/exon and canonical CDS/protein retrieval, attributed
  URLs, retrieval dates and checksums. Expression and clinical annotations are
  absent unless separately supplied, never inferred.
- Biopython sequence validation, reverse complement, standard-code translation,
  codon positions, bounded global affine-gap alignment and GenBank annotations.
- Both-strand IUPAC DNA motif maps. No activity or specificity score is inferred.
- Assembly-checked, strand-aware inclusive genomic→transcript exon mapping.
  Protein coordinates are not invented when CDS mapping is missing.
- Reference-checked CDS substitutions/indels and translated sequence consequences.
  This is sequence consequence analysis, not splicing or pathogenicity prediction.
- Explicit BED/GFF3/VCF coordinate normalization and bounded FASTQ quality summaries.
- ViennaRNA MFE secondary structure and predicted base-pair arc rendering.
- Paired observed/predicted descriptive MAE/RMSE/correlation, with matching species,
  assay, editor, cell type, endpoint and units required.
- NCBI PubMed citation retrieval with PMID/source links; no generated citations.

## Validation so far

666 backend tests and 107 interface tests pass, including 13 new offline
EditCraft tests. These validate registry/library linkage, immutable notebook
versions, cross-project isolation, positive/negative strand boundaries, assembly
mismatch rejection, workflow typing, local-only preparation and honest catalogue
readiness. They do NOT establish genuine Biopython/ViennaRNA cloud execution;
that requires the separately authorized CPU deployment and reference checks.

An old CUDA-cancellation test fixture was updated to accept the cache-root
keyword introduced in the previous cache implementation; no scientific runtime
behavior was substituted to pass the test.

## Primary sources reviewed

- Ensembl REST lookup: https://rest.ensembl.org/documentation/info/symbol_lookup
- ViennaRNA methods: https://doi.org/10.1186/1748-7188-6-26
- ViennaRNA distribution/license: https://www.tbi.univie.ac.at/RNA/
  and https://www.tbi.univie.ac.at/RNA/ViennaRNA/refman/license.html
- CRISPResso2: https://github.com/pinellolab/CRISPResso2
  and https://doi.org/10.1038/s41587-019-0032-3
- crisprVerse scoring: https://github.com/crisprVerse/crisprScore
- AlphaGenome: https://deepmind.google/science/alphagenome/
  and https://doi.org/10.1038/s41586-025-10014-0
- PRIDICT2: https://doi.org/10.1038/s41596-025-01244-7
- Pertpy: https://github.com/scverse/pertpy
  and https://doi.org/10.1038/s41592-025-02909-7
- scvi-tools: https://scvi-tools.org/

These sources establish task/scope and available implementations, not completion
of license auditing, checkpoint admission or model benchmarking. API availability
and published checkpoint access must be verified separately for each method.

## Still required for the complete directives

Source/version/checkpoint and assay applicability audits for the remaining
catalogue; genuine CRISPR activity/off-target, base/prime editing, Cas13, ADAR,
siRNA/ASO, RNA-FM, SpliceAI/Pangolin and genomic foundation-model adapters;
large FASTQ/BAM/CRAM/H5AD dataset streaming; CRISPResso2/MAGeCK/Scanpy/scvi/Pertpy
execution and held-out validation; expression/disease/pathway atlas integrations;
full assembly/CDS/isoform-to-structure mapping; IGV/JBrowse integration; authentic
ribosome demonstration/annotations; rich notebook/construct editing; visual DAG
editing; live RAPID domain commands; graph navigation and provenance-aware edge
editing; uncertainty/calibration/counterfactual benchmarks; report figures/PDF/
DOCX; complete data governance/access auditing; and broad end-to-end acceptance.

The initial catalogue is deliberately broad and unqualified. Missing versions,
checkpoints, organisms, editor contexts and performance fields remain null rather
than invented. No model is substituted under another model's name.

## Genuine cloud checks

The approved CPU deployment and both reference experiments completed. The public
ANGPTL3 CDS translates exactly to its separately retrieved 460-residue protein.
ViennaRNA 2.7.2 folded the 1,383-nt CDS-derived RNA at 37 °C. Short synthetic
translation, synonymous substitution, motif, BED coordinate and RNA stem examples
passed. See reports/editcraft/VALIDATION.md and its JSON provenance. This does not
qualify trained editing models or complete the full directives.
