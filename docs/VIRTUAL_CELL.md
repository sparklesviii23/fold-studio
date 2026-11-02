# Virtual Cell

1 November 2026. Analyse › Virtual Cell. Persistent cells modelled on the AIDO Cell interface (GenBio AI whitepaper,
2026): perturb, observe, branch and design. Research-only (decision of 1 Nov 2026). Every readout states its evidence
category and the licences of the data it used.

## Cells and contexts

A cell is its context plus the ordered history of operations (`<library>/virtualcell/cells/<id>.json`, SHA-256 of
context + history + reference identity). States are never edited: they are rebuilt by replaying the history, so every
state is reproducible. Branching copies a history prefix into a new cell.

| Context | Baseline | Perturbations |
|---|---|---|
| K-562 | Norman 2019 control cells (CRISPRa machinery, non-targeting guides), 2,085-gene panel | over-express, knock down, knock out, drugs (transferred) |
| 50 Tahoe-100M lines | DepMap 24Q4 bulk RNA-seq of the line, ≈ 19,300 genes | drugs (measured / interpolated), knock out |

## Transitions and their held-out accuracy

| Operation | Source | Evidence | Held-out accuracy |
|---|---|---|---|
| Over-express a measured gene / pair | Norman 2019 means | A | noise ceiling r 0.83 |
| Other over-expression combinations | sum of single effects | C | unseen pairs r 0.88 (top-20 genes 0.97) |
| Over-express an unperturbed panel gene | linear model (Ahlmann-Eltze 2025) | C | r 0.49; average-effect baseline 0.52 |
| Knock down a measured gene | Replogle 2022 K-562 essential CRISPRi (2,021 genes) | A | median target mRNA left 14 %; half-split ceiling r 0.38 |
| Knock down an unmeasured panel gene | linear model | C | r 0.30; average-effect baseline 0.29 |
| Knock out | expression **not modelled**; DepMap Chronos fitness | A | — |
| Drug, measured line and dose | Tahoe-100M DESeq2 log2FC vs DMSO | A | — |
| Drug, dose between measured doses | per-gene linear in log10(dose) | C | Tahoe benchmark (atlas card) |
| Drug in K-562 (not in Tahoe) | mean response of the Tahoe lines | C | leave-one-line-out benchmark |
| Combinations involving drugs or knockdowns | additive | C | not benchmarked (stated) |

Tahoe benchmarks (`virtual_cell_drugs.benchmark`, all 50 lines, 65,218 conditions) score active conditions (≥ 30 genes
with |log2FC/SE| > 4) on the 200 most significant genes: **transfer to an unseen line r 0.79** (800 tests) against a
generic drug-response baseline (mean of random conditions) of r 0.49, so transfer carries drug-specific information;
**dose interpolation r 0.70** (265); single replicate plates r 0.46 (genes chosen on one plate, scored on the other:
not a ceiling for averaged predictions). Gene selection by |log2FC| alone picked noise (replicate plates r 0.09).

## Readouts

- **Expression**: panel genes, largest changes, held-out accuracy of the transition used, on-target knockdown efficiency.
- **Fitness**: DepMap Chronos for knocked-out / knocked-down genes (knockdowns flagged as milder than knockout).
- **Metabolism**: Human-GEM flux balance with knockout GPR rules (`virtual_cell_metabolism.py`, B), cross-checked against
  DepMap; disagreement reported (DHODH: model essential, K-562 Chronos −0.48).
- **Signalling**: SPARCED (914 species, 2,434 reactions; MCF10A parameters, so D for K-562) integrated for 24 h by the
  Mechanistic Lab compiler, with its mRNA inputs scaled by this cell's predicted fold changes (knockouts → 0, measured
  knockdown efficiency where known). `virtual_cell_signalling.py`; solver tolerance and conservation checks on every run.
- **Compartment programmes** drive the cell view: mean change of each compartment's panel genes (Human-GEM SwissProt /
  DeepLoc2 annotations of metabolic genes; RPL/RPS for ribosomes). Display brightness = 2^(3 × score). Geometry is
  illustrative (E).

## Design

Searches every measured over-expression and knockdown, every Tahoe drug–dose condition (measured on the line, or
transferred to K-562), all over-expression pairs and pairs among the best 40 singles — about 8,000–9,000 candidates in
under a second. Each candidate's effect is the true transition from the current state (history replayed with the
candidate appended), so completing a measured pair uses that measurement.

## Plugins and their benchmarks

**GB.Cell-3M** (`virtual_cell_gbcell.py`, runtimes/gbcell, CPU: Metal attention fails at 19k tokens). Benchmark: for
11 strong Replogle knockdowns, target = knockdown cells with the target gene reset to its control level, so ranking the
true gene first requires predicting its downstream programme; 37 candidates, 24 cells per condition. Mean reciprocal
rank: **GB.Cell 0.066, co-expression (PCA) 0.156, chance 0.114**. GB.Cell's in-silico knockout did not carry
downstream information in this test; it is not used for design.

## Compute

Local: reference build (≈ 2 min), metabolism (≈ 7 s), SPARCED (≈ 35 s), design (< 1 s), GB.Cell (≈ 2.3 s per cell).
Modal (gpu_tasks recipe `tahoe_atlas`, 16 CPU, 32 GB): all 1,026 Tahoe files filtered in parallel; the ≈ 5 GB result is
streamed from the `fold-gpu-cache` Volume (the app's 400 MB fetch limit does not apply).

## Licences and release

`scientific/virtual_cell_plugins.py` lists every resource with licence, verification, non-commercial status and
attribution; status() also returns saved plugin benchmarks. Restricted resources are optional plugins fetched from their
source into the library. `python3 scripts/check-release-licenses.py` blocks weights, single-cell data and library
content from the repository.

## Tests

`tests/test_virtual_cell.py` (25): transitions and labels, refusals, replay, branching, knockdowns, SPARCED coupling,
drugs (transfer, measured, interpolated, refused), Tahoe contexts, design over all perturbation kinds, dispatch, JSON
safety, registry, NOTICE, release check.

## Proteome annotations and Hep G2 (2 November 2026)

`scientific/virtual_cell_annotations.py` builds one index (`<library>/virtualcell/data/annotations`, manifest with SHA-256 per
original file, Reactome release 98) from HPA subcellular (CC BY 4.0), UniProt reviewed human (CC BY 4.0) and Reactome (data
CC0); licences read on the provider pages. 20,542 genes, 13,603 with HPA calls, 2,889 human pathways.

- **Identifiers**: symbol, alias, UniProt (isoforms folded), Ensembl gene; shared aliases are reported as ambiguous, never guessed.
- **Localization**: HPA terms with reliability and cell-cycle dependency; UniProt locations with ECO evidence (ECO:0000269 =
  experimental); Human-GEM kept. HPA is a general human annotation, not a measurement in the viewed line. Renderer layers
  follow the documented `LAYERS` mapping (Uncertain calls excluded); other terms are listed, not drawn. Cell-view channels
  now use HPA for all proteins when installed (Human-GEM fallback otherwise).
- **Reactome**: lowest-level pathways per UniProt accession with evidence code, hierarchy, member tables with this context's
  expression, and over-representation of a cell's largest modelled changes (hypergeometric, BH, context gene universe).
  The protein graph reuses the Mechanistic Lab `KnowledgeGraph`; BioModels candidates load on request via `mech_discover`.
- **Hep G2 (CVCL_0027, DepMap ACH-000739)**: `DepMapContext`, identity checked against the DepMap model RRID. Measured
  DepMap 24Q4 RNA (19,193 protein-coding genes, single profile), Chronos fitness, knockout readouts. No drugs (Tahoe measured
  HepG2/C3A, CVCL_1098, a separate derivative context). Sanity check on real data: ALB 13.96, APOA1 11.78, AFP 11.49
  log2(TPM+1); PTPRC and HBB ≈ 0.
- Not available, stated in the UI: protein abundance (no proteomics installed), isoform expression, microscopy.

Tests: `tests/test_virtual_cell_annotations.py` (12), `src/components/virtualcell/ProteinWorkspace.test.tsx` (3).

## Next

Borzoi / Flashzoi variant readouts on Modal GPU (point mutations); Geneformer as a second knockout ranking; VirTues
tissue context; per-line genetic data (X-Atlas/Orion) for Tahoe contexts.
