# Oncology Universe · data foundation, Demo A and Demo C

Status date: 2026-10-31. Code: `scientific/oncology_data.py`, `oncology_stats.py`, `drug_response.py`, `oncology.py`;
UI: `src/components/oncology/OncologyUniverse.tsx`. Data live in `<research library>/oncology/<source>/<release>/`.

## Connected datasets (installed and checksum-verified on this machine)
| Source | Release | Files | Verification | Licence |
|---|---|---|---|---|
| DepMap (Broad) | 24Q4 Public, Figshare+ DOI 10.25452/figshare.plus.27993248.v1 | Model, CRISPRGeneEffect (1178 × 17916), hotspot (1929 × 540) and damaging (1929 × 17847) mutation matrices, protein-coding expression (1673 × 19193), README | Published MD5 for every file | CC BY 4.0 |
| GDSC (Sanger) | 8.5 | GDSC1 + GDSC2 fitted dose–response (575,197 curves, 697 drug–screen pairs), screened compounds | Object-store MD5 (ETag) | GDSC terms (academic/non-commercial) |

**DepMap 26Q3:** depmap.org now serves downloads behind a browser verification page, which the app does not bypass, and no
scriptable mirror of 26Q3 exists (Figshare+ stops at 24Q4). Download it in a browser and use *Data › Import a release*;
its checksums are recorded (not verifiable, as none are published there).

Identifiers: DepMap ModelID ↔ GDSC SANGER_MODEL_ID via DepMap `Model.csv` SangerModelID; genes as HGNC symbol + Entrez ID.
Original values are kept unchanged (float32 copies); originals are retained alongside.

## Demo A · dependency statistics (Statistical association)
- One model per DepMap PatientID (sister lines collapsed: pseudoreplication control).
- Lineage scan: Welch t per gene, BH-FDR, mean difference + 95 % CI + Cohen's d.
- Mutation scan: OLS gene effect ~ mutation + lineage fixed effects (Frisch–Waugh–Lovell), BH-FDR, β + 95 % CI.
- Expression link: lineage-adjusted partial correlation, Fisher-z CI.
- Chronos already corrects copy-number cutting toxicity; growth-rate and screen-quality covariates are not yet modelled.

**Controls on real 24Q4 data (pre-specified thresholds):** 7 / 8 pass. KRAS, BRAF, NRAS, PIK3CA each rank #1 in their own
hotspot-mutant models (q from 1e-55 to 3e-208); SOX10 #1 in Skin; RPL11 mean −2.34; OR2T4 mean −0.02.
**Fails:** SPI1 in Myeloid ranks #107 (Δ −0.48, q 2.5e-3) against the top-25 threshold; reported, threshold not moved.

## Demo C · drug-response benchmark (AI prediction vs experimental observation)
Real results (GDSC2, DepMap 24Q4 expression, top 500 variable genes chosen inside each training fold):
- Dabrafenib, held-out cell lines (702 lines, 5-fold grouped by patient): mean r −0.04 · lineage-mean r 0.58 · ridge r 0.63
  (RMSE 1.44 vs 1.52 for the lineage baseline) · elastic net r 0.63; 90 % prediction-interval coverage 93–94 %.
- Held-out compounds (286 compounds / 295 GDSC2 screens, compound identity by normalised name): global r −0.12 ·
  pathway mean r 0.29 · pathway + cell-line general sensitivity r 0.43; mean within-drug Spearman 0.63.
- Leakage checks reported with every run: patients/compounds shared across folds (0), fold-internal feature selection,
  standardisation and penalty choice.
- Not yet: random forest / gradient boosting (no scikit-learn in the bundled runtimes), drug-structure features,
  external-study validation (e.g. CTRP/PRISM), calibration curves beyond interval coverage.

## Tests
`tests/test_oncology.py` (planted-signal recovery, BH, grouped folds, leakage), `tests/test_tumor_tme.py`, `tests/test_gpu_tasks.py`.

## Demo B · cancer genomics workspace (cBioPortal, TCGA PanCancer Atlas)
Code: `scientific/cancer_genomics.py`; UI: Oncology Universe › Patient genomics. Any of the 32 PanCancer Atlas studies can be
downloaded; each API response is stored as returned with URL, request body, retrieval time and SHA-256.

Installed and checked: **Lung Adenocarcinoma (TCGA, PanCancer Atlas)** — 566 samples (511 profiled for mutation and copy
number), cBioPortal 7.2.3, study imported 2026-06-04; genes = DepMap hotspot panel + Sanchez-Vega 2018 pathway core genes.

Results on the real cohort (agree with published TCGA LUAD genomics):
- Alteration frequency: TP53 52 %, KRAS 33 %, KEAP1 19 %, CDKN2A 21 % (85 of 105 by deep deletion), EGFR 15 %.
- Driver-enriched sort (recurrent protein positions) ranks TP53, KRAS, EGFR, STK11, KEAP1 first; long passenger genes (TTN,
  MUC16, USH2A) rank high only by raw frequency — flagged in the UI.
- KRAS–EGFR mutual exclusivity (log2 OR −2.7, q 8e-7); KRAS–STK11 and STK11–KEAP1 co-occurrence (q ≤ 2e-4).
- CDKN2A mRNA tracks GISTIC level (Spearman 0.35; median z −1.27 in deep deletions).
- OS, Cox with age: STK11 HR 1.64 (1.12–2.40), log-rank p 0.042; TP53 HR 1.36 (1.00–1.85); KEAP1 HR 1.25 (0.88–1.76).
- Reference build labels are mixed (GRCh37 12,805; GRCh38 2; not stated 1); analyses are gene-level and say so.

Methods: alteration = non-silent mutation or GISTIC ±2 (direction by oncogene/other role); Fisher exact + BH; Spearman for
expression ~ copy number; Kaplan–Meier, log-rank, Cox PH (Newton–Raphson, Breslow ties) with age; survival is patient-level.
Limits: no curated oncogenicity (OncoKB is licence-restricted), no stage/treatment adjustment, single cohort, no external validation.
Tests: `tests/test_cancer_genomics.py` (KM by hand, Cox recovers a simulated HR of 2, log-rank null/effect, BH).

## Drug-combination synergy (NCI ALMANAC)
Code: `scientific/synergy.py`; UI: Oncology Universe › Synergy. Data: NCI ALMANAC `ComboDrugGrowth_Nov2017` (Holbeck 2017,
Cancer Res 77:3564; US Government work). 3,686,475 valid wells, 61 NCI-60 lines, 105 named drugs, 5,242 pairs. No checksum
is published; SHA-256 of every file is recorded. (DrugComb, the planned second source, was offline on 2026-10-31.)

Models: HSA, Bliss, Loewe (bisection on pooled single-agent Hill fits; undefined where additivity needs more effect than a
single agent reaches — counted, never extrapolated), ZIP (Yadav 2015), and the NCI ComboScore recomputed independently.
Replicates are plates; each model's mean excess comes with a 95 % t-interval and a call (synergy / antagonism / consistent
with no interaction / not determined for one plate). Single agents come from the same plate, else the same experiment
(screener + test date), as the screen pairs them; this is counted per analysis.

Validation on real data: recomputed NCI expected growth matches the published `EXPECTEDGROWTH` on 591 wells across 60 random
pair–cell combinations (max |Δ| 0.0014, mean 0.00014 percentage points). Sham-like pair idarubicin + epirubicin (same drug class)
in SR: HSA +0.5 (−2.5 to 3.5), Loewe −0.6 (−0.8 to −0.4) — near dose-additive, as expected.
Unit tests: Loewe is exact for a drug combined with itself; Loewe undefined beyond the weaker drug's Emax; Bliss is not neutral
for a sham pair (sign changes with dose when the Hill slope ≠ 1 — a documented Bliss pitfall); NCI expected-growth rule.

## Mutational signatures (COSMIC v3.4 SBS)
Code: `scientific/mutational_signatures.py`; UI: Oncology Universe › Signatures. Exome SNVs from cBioPortal (GRCh37 calls only);
trinucleotide context from Ensembl GRCh37 REST, with the reference base checked against the genome (mismatches and
unavailable contexts counted separately); SBS96 in pyrimidine convention; reference COSMIC_v3.4_SBS_GRCh37_exome
(SigProfilerAssignment, BSD-2-Clause; git blob hash verified). Fit: NNLS → backward elimination (Δcosine < 0.01), COSMIC
artefact signatures excluded, 100 multinomial bootstraps per sample; samples with < 50 SNVs not fitted.
Reference check: SBS4 (tobacco) share in smokers vs lifelong never-smokers (one-sided Mann–Whitney; Alexandrov 2016 Science).
Not SigProfilerAssignment itself (not installed); results are comparable in method but not identical.

Real results, TCGA LUAD PanCancer Atlas: 151,309 SNVs; every context fetched; 0 reference-base mismatches (after mapping
cBioPortal chromosome 23/24 to X/Y — the first build lost all X-chromosome contexts until this was fixed); 476 tumors fitted,
85 below 50 SNVs; median reconstruction cosine 0.925. Most frequent: SBS4 tobacco (301 tumors, median share 46 %),
SBS13 and SBS2 APOBEC (231, 186). Reference check passes: SBS4 share median 37 % in 386 smokers vs 0 % in 35 lifelong
never-smokers (one-sided Mann–Whitney p 2.7e-6); smoking history joined from cBioPortal `luad_tcga` (same TCGA patients;
the PanCancer release omits it). Caveats shown in the app: SBS4/SBS29 split, SBS7a calls in lung likely misattribution.

## Demo D · single-cell tumor atlas (CZ CELLxGENE Discover)
Code: `scientific/singlecell_tumor.py` (runs in the isolated runtime `runtimes/singlecell`; packages pinned in
`scientific/singlecell_runtime.lock.txt`: Scanpy 1.12.5, AnnData 0.13.4, SciPy 1.15.3, scikit-learn 1.9.1, harmonypy 2.1.0),
`scientific/singlecell_data.py` (download + manifest); UI: Oncology Universe › Single-cell. The app's bundled runtime is untouched.
Licence decision: harmonypy is GPL-3.0; it is used only inside the separate local runtime and is not redistributed with the app.
Runtime fixes recorded: scanpy 1.11.4 failed with AnnData 0.13 sparse arrays (upgraded to 1.12.5); `seurat_v3` HVG needs
scikit-misc (used `seurat` dispersion instead); harmonypy 2.x output orientation differs from scanpy's wrapper (called directly).

Dataset: "Epithelial bcc and normal_scRNAseq" (PNAS 2023, doi 10.1073/pnas.2313326120), 9,841 cells, 35 donors (8 BCC, 27
normal), 10x; SHA-256 9e1ae6f5…f76 recorded (CELLxGENE publishes no checksum). Only CELLxGENE dataset meeting: primary data,
tumor + normal, ≥ 8 donors, < 450 MB.

Results (hair follicular keratinocytes; BCC vs normal **face** skin — all BCC samples are facial, so site is controlled):
- QC per donor (3 MAD): 9,841 → 9,663 cells. Harmony on donor: single-donor clusters 5 → 0; median donor dominance 54 % → 35 %.
- Annotation review: ARI 0.04 between Leiden clusters and author ontology labels (states vs anatomical labels); exploratory markers listed.
- Pseudoreplication: 11,043 of 13,435 genes "significant" cell-level vs 88 donor-level (Welch, pre-specified) / 182 (moderated t).
- Hedgehog targets (expected up in BCC): GLI1 log2FC 3.5 (Welch q 0.056; moderated q 0.024), PTCH1 4.4 (0.13; 0.062),
  HHIP 5.2 (0.081; 1.5e-4). Large effects; with 5 vs 7 donors the pre-specified Welch test does not reach q < 0.05 for any;
  the moderated test (added after seeing that result, labelled as such) does for GLI1 and HHIP, not PTCH1.
- Hallmark Hedgehog signalling up in BCC (competitive test, q 0.0076).
Tests: `tests/test_singlecell_tumor.py` (MAD QC, runtime lookup, synthetic end-to-end run in the Scanpy runtime with donor
variation: planted genes found at donor level; cell-level testing inflates significance).

## Demo E · spatial tumor explorer (10x Visium, CZ CELLxGENE Discover)
Code: `scientific/spatial_tumor.py` (single-cell runtime); downloader shared with Demo D (`singlecell_data.py`, now via the
curation API's `/datasets/{id}/versions`, newest published version — the earlier `/datasets/{id}` path returned 404, which
would have broken in-app downloads for Demo D too; fixed). UI: Oncology Universe › Spatial.

Dataset: TNBC Visium section GSM6592049_M2 (Lab Invest 2023, doi 10.1016/j.labinv.2023.100258), 1,848 in-tissue spots;
H&E image, measured spot coordinates, pathologist annotation per spot, authors' stereoscope deconvolution. SHA-256 recorded.
Layers keep their evidence type: H&E and counts (observation), pathologist labels (expert annotation), stereoscope
fractions (AI prediction). One 2D section; no 3D reconstruction; spots are 55 µm and contain several cells.

Results:
- Neighbourhood enrichment (500 label permutations): every compartment strongly self-adjacent (z 30–70); tumor nests and
  inflamed stroma avoid each other (z −19.9).
- Moran's I (2,000 variable genes, 200 coordinate permutations): immunoglobulins (plasma-cell zones) and COL11A1 most patterned;
  MALAT1/MT- genes flagged as technical. Null calibrated: shuffled-coordinate median I −0.002.
- Tumor–immune interface: predicted T-cell fraction inside tumor 0.028 vs 0.021 within 300 µm (ratio 1.34, p 2e-4) — no
  exclusion by this readout; measured CD8A peaks within 150 µm. The two readouts disagree; both are shown. Bins < 20 spots dimmed.
- Agreement with the pathologist (pre-set bar AUC 0.8, not met): stereoscope cancer-epithelial fraction 0.76, EPCAM 0.71,
  KRT8 0.67, KRT18 0.70 — moderate, consistent with multi-cell spots and region-level annotation.
Tests: `tests/test_spatial_tumor.py` (hex neighbours, Moran's I gradient vs random and vectorised = scalar, neighbourhood
enrichment for segregated vs shuffled labels).

### Library, other datasets and in-silico sections

- **Catalog.** The Spatial tab lists every public human cancer spatial dataset on CZ CELLxGENE Discover measured with 10x Visium or Slide-seqV2: 88 on 2026-10-31. They cover renal cell carcinoma, colorectal cancer, breast cancer, basal cell carcinoma and metastatic melanoma. The list is read from the curation API and cached for a day. Each dataset can be downloaded, opened and deleted. Deleting removes the H5AD, the result and the logs.
- **Any deposit.** The analysis handles each deposit as it is:
  - Every author categorical column (2–40 levels) becomes an annotation layer, plus Leiden expression clusters labelled as computed.
  - Numeric author columns, usually deconvolution, become score layers.
  - Visium uses hexagonal neighbours. Bead arrays use the six nearest beads.
  - The tumor label is matched by name, so "Tumor stroma …" is not counted as tumor.
  - The tumor-marker panel is chosen by disease: PMEL/MLANA for melanoma, CA9/NDUFA4L2 for renal, EPCAM/KRT8/KRT18 otherwise.
  - Slide-seq deposits don't state position units, so no scale bar or µm distances are shown for them.
- **Moran's I p-values.** These now come from a normal approximation using the moments of the permutation null. With 200 permutations the raw permutation p cannot go below 1/201. On small gene panels that floor made every q-value at least 0.067.
- **In-silico sections** (`spatial_sim.py`, illustrative/hypothetical):
  - Visium layout, 3,600 spots.
  - Gaussian tumor nests and fixed compartment fractions.
  - A planted T-cell pattern: infiltrated, excluded or desert.
  - Negative-binomial counts, with cell-type profiles that have equal totals so library size carries no spatial signal.
  - 12 planted spatial genes and 300 pattern-free genes.
  - Each run is scored against the truth. Seeds 1–2 for all three patterns:
    - all 12 of 12 planted genes were found;
    - 0–4 of 300 pattern-free genes were falsely called;
    - exclusion was recovered (CD8A inside/rim ratio 0.44) and infiltration was recovered (0.96–0.97).
  - A unit test caught an early flaw. Cell types had different numbers of markers, so the share of pattern-free genes followed tissue composition (r = 0.56 with tumor). Every type now carries the same marker mass.
  - A desert reads as "infiltrated" by the ratio. An inside/rim ratio cannot tell a desert from infiltration without an absolute immune reference, and this is reported, not hidden.

## Demo F · tumor metabolic model (Human-GEM v2.1.1 × COBRApy 0.32.1)
Code: `scientific/metabolism.py` (science runtime; COBRApy + GLPK via optlang, pinned in the lock file); UI: Oncology Universe ›
Metabolism. Model: Human-GEM v2.1.1 (Robinson 2020 Sci Signal; CC BY 4.0), 12,748 reactions, 8,374 metabolites, 2,870 genes;
`Human-GEM.xml`, `genes.tsv`, `reactions.tsv` verified by git blob SHA-1; JSON copy derived for speed.

Medium: Ham's F-12 (Human-GEM task medium) + retinol, α- and γ-tocopherol. Without these serum vitamins biomass is 0 — found by
testing every biomass precursor (the cofactor pool needs retinoids and tocopherols). Bounds: glucose ≤ 1, other organics ≤ 0.1,
inorganic ions/water/gases unlimited (relative units; growth is relative, not a doubling time). The shipped model has all
1,654 exchanges open both ways (default optimum 138, meaningless), so every analysis sets the medium explicitly.

Checks (all pass): E. coli core optimum 0.87392 (published 0.8739) and anaerobic 0.2117; no nutrients → 0 ATP (no energy-
generating cycles); ATP/glucose aerobic 31.5 (textbook 30–33), glycolysis only 2.0. Unconstrained anaerobic optimum is 2.44
via succinate secretion (fumarate as electron acceptor, complex II reversed — reported in ischaemia, Chouchani 2014 Nature);
reported, and the textbook check blocks succinate export.
Oxygen sweep: the model secretes succinate, never lactate, as O2 falls — stoichiometry alone does not produce Warburg aerobic
glycolysis (needs enzyme/proteome constraints, not modelled). pFBA central-carbon fluxes with FVA at ≥ 95 % optimum (±1000 ranges
= reversible internal loops; no loopless constraint). Growth grid over glucose × O2 supply.
Essentiality vs DepMap 24Q4: 156 of 2,870 genes essential in silico; of 2,773 shared genes, AUC 0.82 against DepMap mean
effect, odds ratio 20 (Fisher p 2e-42), precision 39 %, recall 43 % for DepMap common-essentials (effect < −0.5 in ≥ 90 % of
lines). Agree: aminoacyl-tRNA synthetases; model-only: CoQ synthesis (medium lacks CoQ); DepMap-only: ATP synthase / V-ATPase
subunits (complex redundancy in gene rules).
Tests: `tests/test_metabolism.py` (E. coli core aerobic/anaerobic optima, no-nutrient ATP, medium-closing semantics).

## Demo K · cancer evidence graph (KRAS in lung adenocarcinoma)
Code: `scientific/evidence_graph.py`; GDSC biomarker scan added to `drug_response.py`; UI: Oncology Universe › Evidence graph.
Every edge: relation, origin (experimental · curated · computed · text-mined · predicted), strength, database + version,
citation, species, context. Raw responses saved with SHA-256 under `<library>/oncology/evidence/KRAS/raw/`; failed sources
become visible "unavailable" nodes. Duplicate facts from overlapping queries collapse to one edge.

Sources (18/18 answered on 2026-10-31): UniProtKB/Swiss-Prot (P01116), Reactome release 98 pathways, STRING 12.5 (score ≥ 0.7;
origin from evidence channels — experimental ≥ 0.4, else curated database, else text-mined), Open Targets Platform 26.09
(KRAS–lung adenocarcinoma 0.70; literature, affected pathway, somatic mutation), CIViC accepted evidence items (CC0; e.g. KRAS
G12C → sotorasib, level A, Skoulidis 2021), Europe PMC (22,083 records, 244 preprints flagged), BioModels.
Computed here: DepMap 24Q4 (KRAS rank 1 dependency in KRAS-mutant lines, β −1.07), GDSC2 lineage-adjusted biomarker scan
(MEK inhibitors PD0325901, trametinib, refametinib, selumetinib sensitise KRAS-mutant lines; osimertinib resistance; without
lineage adjustment haematological-lineage drugs dominated — confounding shown and corrected), TCGA LUAD (33 % altered;
co-occurrence/exclusivity partners; age-adjusted OS hazard ratio).
Trace: patient observation → CRISPR screen → cell-line pharmacology → curated clinical evidence → literature, each labelled with
its evidence category; explicit gaps: normal-tissue selectivity, patient causality, allele-specific effects, independent replication.
Fixes during build: Reactome version endpoint needs `Accept: text/plain` (406 with JSON); edge de-duplication.
Tests: `tests/test_evidence_graph.py` (STRING text-mined vs experimental classification, failed source visible, de-duplication).

## In-silico runs for every demo (`scientific/insilico.py`)
Each demo page except the tumor microenvironment (already a PhysiCell simulation) and the evidence graph has a **Real data | In
silico** switch. An in-silico run generates synthetic data from a stated model with a planted answer, passes it through that
demo's own analysis functions unchanged, and scores the output against what was planted. Results are labelled "Synthetic data ·
tests the method against a planted answer; not an observation" and saved as experiment records. Runs live in
`oncology/insilico/<demo>/<id>/` (parameters, log, result; the single-cell run also keeps its H5AD) and can be opened or deleted
from the page. The run id is a hash of the parameters, so the same parameters and seed give the same run.

| Demo | Planted | Scored |
|---|---|---|
| Dependency atlas | common essentials; 3 lineage-selective genes; 4 genes dependent on SIMMUT_A; SIMMUT_B enriched in a lineage with its own dependencies; sister lines | sisters collapsed; hits recovered and false calls; SIMMUT_B calls with vs without lineage adjustment |
| Drug response | expression with latent factors and lineage; response = biomarker signal (planted R²) + lineage + patient noise shared by sisters; a null compound | no patient split across folds; ridge vs noise ceiling; beats lineage baseline; null compound has no skill; ungrouped split (informational) |
| Synergy | Hill single agents; Bliss excess (synergy/none/antagonism), or a drug with itself (sham); well noise | each model's interval covers its noise-free value; Bliss call; Loewe calls a sham additive |
| Signatures | COSMIC v3.4 mixtures (lung smoking, MMR-deficient, UV, APOBEC/HRD); SBS4 only in smokers | signatures ≥ 10 % recovered; exposure on absent signatures; interval coverage; smoking check |
| Patient genomics | KRAS–EGFR exclusivity, KRAS–STK11 co-occurrence, MYC amplification → mRNA, STK11 hazard ratio, ATM age-confounded | each association recovered; null pairs not called; Cox intervals; age adjustment removes ATM |
| Single-cell | a Hallmark program up in carcinoma keratinocytes; donor-to-donor variability | Welch and moderated power; false discoveries; pathway rank; naive cell-level over-calling |
| Metabolism | nothing planted: Human-GEM under user medium and knockouts | wild-type growth, knockout growth, exchange fluxes (mechanistic simulation) |

What the runs showed on the default parameters (seed 1), reported as found:
- Atlas: all planted dependencies found with no false calls; SIMMUT_B had 0 calls after lineage adjustment and 4 without.
- Drug response: ridge Pearson 0.63 against a noise ceiling of 0.70; null compound −0.13; splitting by cell line instead of patient
  changed nothing here (0.62 vs 0.63), because the shared patient noise is not predictable from expression.
- Synergy (12 pp Bliss excess, 3 plates): all four model intervals covered their noise-free values. The first shape for the planted
  excess was clipped at 100 % inhibition, so the noise-free Bliss score was 6.5 pp, not 12; the shape now vanishes at 0 and 100 %.
- Signatures (60 samples, median 250 SNVs): **fails** the 80 % recovery bar (63 %); 9 % of exposure goes to absent signatures and
  bootstrap intervals cover the truth 64 % of the time. This is the expected weakness of exome-scale counts with flat signatures
  (SBS5); recovery improves with burden (table in the run). The smoking check passes (p = 3e-7).
- Genomics: all eight checks pass; the planted STK11 HR 1.6 was estimated at 1.62 (1.19–2.19).
- Single-cell (6 + 6 donors, log2FC 1): the pathway is found (rank 1, q = 1e-44) but the per-gene Welch test finds 4 of 120 planted
  genes and the moderated test 23 (2 false). The naive cell-level test calls 1,790 genes. These are reported as power, not pass/fail.
Code changes so the analyses accept synthetic inputs, with no change in behaviour on real data: `drug_response.held_out_cell_lines(d=)`,
`cancer_genomics.summary/pairs/expression_by_cna/survival(c=)`, `synergy.score_plates` (extracted from `analyse`), and the
single-cell volcano now carries the moderated q as a 4th element.
Tests: `tests/test_insilico.py`.

## Perturbation lab (`scientific/perturbation.py`)
One experiment, every engine that can represent it. A **system** is a cancer lineage (DepMap/GDSC) and an optional patient cohort;
up to four **perturbations** are applied together: inhibit a gene (fraction), scale a protein–protein interaction, administer a GDSC
compound (assumed fraction of target inhibition; exposure not modelled), or scale effector immune influx.

| Engine | Type | Evidence class | Reached by |
|---|---|---|---|
| EGFR signalling, Kholodenko 1999 (BIOMD0000000048) | simulator | Mechanistic simulation | EGFR, PLCG1, GRB2, SOS1, SHC1; 6 interactions |
| MAPK cascade with feedback, Kholodenko 2000 (BIOMD0000000010) | simulator | Mechanistic simulation | KRAS/NRAS/HRAS (input rate, analogy), BRAF/RAF1 (MAPKKK slot, analogy), MAP2K1/2, MAPK1/3; RAF–MEK, MEK–ERK, ERK⊣RAF feedback |
| Tumor–effector dynamics, Kuznetsov et al. 1994 | simulator | Mechanistic simulation | immune influx (σ) |
| Human-GEM flux balance | simulator | Mechanistic simulation | any metabolic gene (reactions losing all catalysts scaled by the inhibition) |
| DepMap CRISPR | measured data | Experimental observation | any screened gene; compound targets |
| GDSC | measured data | Experimental observation | compounds |
| Ridge response model | AI model | AI prediction | compounds; shown with its held-out-lineage score |
| Patient cohort | statistical | Statistical association | gene alteration and survival (direction opposite to inhibition, stated) |
| Evidence graph | curated knowledge | Curated evidence | genes with a built graph (KRAS) |

Rules: engines never pass numbers to each other; each card says which perturbations it represented, how (the exact model terms and
factors), which it ignored, and its caveats. A matrix shows perturbation × engine coverage; a final list names what no engine
represents (pharmacokinetics, toxicity, resistance, spatial immune biology, the structural cause of an interaction change).
Paralog targets of one compound (trametinib → MEK1, MEK2) scale a shared model term once. Partial inhibition is representable in the
simulators only; DepMap is a knockout and GDSC uses the assay's own doses, and both say so.
First runs: erlotinib 90 % in lung → phospho-EGFR dimer −89 %, phospho-PLCγ peak −36 %; GDSC lung median LN_IC50 3.11 vs 2.77
elsewhere; the ridge model transfers poorly to lung (r = 0.24). Trametinib 90 % → mean ERK-PP −43 %; measured skin lines far more
sensitive (median LN_IC50 −4.64 vs −0.67) while the ridge model has no skill there (r = 0.01). KRAS loss shuts the MAPK cascade off
in the model; LDHA knockout leaves Human-GEM growth unchanged because LDHB catalyses the same reactions.
Tests: `tests/test_perturbation.py`.

### More mechanistic models in the perturbation lab
Six more curated BioModels, bundled under `fixtures/biomodels/` (CC0, SHA-256 in each `.json`) and run unmodified by the Mechanistic
Biology Lab engine. Each was checked to compile within the supported SBML subset and to pass the solver's tolerance and conservation
checks. Genes follow each model's species-level UniProt annotations; curated exceptions are stated on the page.

| Model | Organism / context | Genes mapped | Interactions | Headline readout |
|---|---|---|---|---|
| Schoeberl 2002, EGF→RAS→ERK (BIOMD0000000019) | human HeLa | 14 (EGFR, GRB2, SOS1, RASA1, H/K/NRAS, SHC1, RAF1, BRAF, MEK1/2, ERK1/2) | 5 | ERK-PP, MEK-PP, Ras-GTP |
| Hatakeyama 2003, heregulin→ErbB→PI3K/AKT + ERK (BIOMD0000000146) | MCF-7 breast; mapped by name (model barely annotated) | 16 | 4 | AKT-PP, ERK-PP |
| Albeck 2008, TRAIL extrinsic apoptosis (BIOMD0000000220) | human HeLa | 14 (BCL2, BAX, BID, XIAP, caspases 3/6/8/9, CFLAR, …) | 9 | time to 50 % PARP cleavage (death) |
| Lee 2003, Wnt/β-catenin (BIOMD0000000658) | Xenopus extract; human orthologs | APC, AXIN1, GSK3B, CTNNB1, DVL2 | 5 | free and TCF-bound β-catenin |
| Zi 2007, TGF-β→SMAD (BIOMD0000000163) | receptor trafficking; TGFBR1 mapped although annotated ACVR1C | TGFB1, TGFBR1/2, SMAD2, SMAD4 | 1 | nuclear SMAD2–SMAD4 |
| Yamada 2003, IFN→JAK→STAT1 (BIOMD0000000093) | mouse; IFNGR1 mapped although annotated Cntfr | IFNGR1, JAK1, JAK2, STAT1, PTPN11 | 5 | nuclear phospho-STAT1 dimer |

Gene inhibition in these models scales the protein's starting pool (knockdown-like), stated on every card. Not included: p53–Mdm2
models (BIOMD0000000154/155/188) and NF-κB (BIOMD0000000140) need delays or events, which the engine does not support yet.
Deliberately not mapped: PARP1 in the apoptosis model (PARP is its death reporter; PARP inhibitors act on DNA repair, absent here).
Reach: 82 of 542 GDSC compound names now hit at least one simulator through their annotated targets.
Checked directions (tests): APC 90 % → free β-catenin ×3; BCL2 90 % → death 3.6 h → 1.8 h; XIAP 90 % → 2.9 h; CASP8 90 % → no death
in 6 h; SMAD4 loss → no nuclear complex; JAK1 90 % → nuclear STAT1 −95 %; PI3K 90 % → AKT-PP −84 % with ERK unchanged.
The Schoeberl cascade is strongly ultrasensitive (25 % less Ras halves peak ERK-PP; 50 % less removes > 99 %); that is the model's
behaviour, reported as such. The card headline is the readout that changed most, or the event time where the model defines one.

## Demo L · integrated discovery workflow (`scientific/discovery.py`, Discovery workflow tab)
A driver gene (hotspot for oncogenes, damaging otherwise), a lineage and an optional cohort. Six steps, each its own evidence class,
none feeding numbers to the next (a step only proposes which genes the next looks at): (1) patients — alteration frequency and
age-adjusted survival HR; (2) DepMap dependencies more essential in mutant lines (lineage fixed effects, BH, one model per patient);
(3) GDSC compounds whose response differs with the driver (lineage-adjusted, BH) and whether their target is a candidate;
(4) mechanistic models — each model's main pathway output under 90 % knockdown of each candidate, with the largest change elsewhere
shown separately (feedback release); (5) curated evidence-graph records; (6) a side-by-side table with no composite score.
Positive control (test): BRAF in skin recovers BRAF itself (Δ −0.78, q 3e-116), MAP2K1 and MAPK1 as dependencies, and dabrafenib
(Δ LN_IC50 −3.06, q 2e-31), PLX-4720, selumetinib, PD0325901 and an ERK inhibitor matching those candidates. KRAS in lung recovers
KRAS (oncogene addiction) and RAF1; MEK inhibitors are more potent in KRAS-mutant lines although MEK is not a top-5 dependency.
The mechanistic models agree on direction but not size: BRAF 90 % → ERK-PP −12 % (Schoeberl), −54 % (Hatakeyama), −100 % (Kholodenko 2000).

## Dose → target engagement (`scientific/chembl_potency.py`)
In the Perturbation lab a compound can be given as a free concentration instead of an assumed % inhibition. ChEMBL (CC BY-SA 3.0)
biochemical activities against single human proteins give a median pChEMBL per gene; inhibition = C / (C + IC50), Hill slope 1.
Every target ≥ 20 % engaged goes to the other engines, labelled annotated target or off-target; data are cached with retrieval
time and SHA-256. Examples at 100 nM: trametinib MEK1/2 98 %; navitoclax BCL2 91 %, BCL-xL 73 %; dabrafenib BRAF 99 %, RAF1 95 %,
CDK16 89 %, CDK2 84 %. Ignored and stated: permeability, intracellular ATP, protein binding, tumour exposure.
Two concentration-mode compounds on one target compete for the site: occupancy = Σ(C/IC50) / (1 + Σ(C/IC50)), applied once
(test: two equipotent compounds at C equal one at 2C).

## SBML events and delays (Mechanistic Biology Lab engine)
Events: triggers fire on false → true (initialValue honoured), the time is located by bisection on the integrator's dense output,
delayed events are queued, values come from trigger time by default, non-persistent triggers are re-checked; parameters changed by
events are tracked per output time. Priorities are still unsupported and block execution. Delays: `delay(x, τ)` on a state
variable, method of steps (chunks ≤ the shortest delay) with history from stored dense output; history before t = 0 is the initial
state. Exact-solution tests: decay with a reset (error 6e-9); dx/dt = −x(t − 1) (error 1e-12). Newly runnable and added to the lab:
Hoffmann 2002 NF-κB (BIOMD0000000140), Proctor & Gray 2008 p53/MDM2 with an irradiation pulse (BIOMD0000000188), Geva-Zatorsky
2006 delayed p53 feedback (BIOMD0000000155). Checked: MDM2–p53 binding × 0.1 (nutlin-like) → total p53 ×2; IKK 90 % → nuclear
NF-κB −27 %; IκBα loss barely changes peak nuclear NF-κB (IκBβ/ε compensate in this model).

## Combinations, and the check against NCI ALMANAC
With two or more perturbations, every simulator reports its main output combined vs the Bliss-independent expectation from the
single perturbations. With two compounds screened together in ALMANAC, a measured-data card scores the pair with the Synergy demo's
code in every NCI-60 line. Only three ALMANAC pairs have both compounds inside one model (all EGFR inhibitors; 105 ALMANAC drugs,
mostly chemotherapy). Results at 50 nM each:

| Pair | ALMANAC measured (mean over lines) | EGFR model, combined ÷ Bliss | Schoeberl, combined ÷ Bliss |
|---|---|---|---|
| gefitinib + lapatinib | Bliss +1.0, Loewe +3.2 pp (59 lines) | 2.38 | 0.82 |
| erlotinib + lapatinib | Bliss −0.0, Loewe +1.2 pp (58) | 2.03 | 0.82 |
| gefitinib + erlotinib | Bliss +1.9, Loewe +3.4 pp (60) | 1.81 | 0.80 |

Measured growth interaction is near additive, as expected for same-target pairs. The two models disagree with each other (the
receptor model predicts sub-Bliss signalling, the ultrasensitive Schoeberl cascade supra-Bliss), and they model signalling, not
growth. Three pairs cannot establish predictive accuracy; none is claimed. Cross-pathway pairs (EGFR × JAK) have no common model.

## PhysiCell immune settings
The PhysiCell recipe accepts, for the 3D cancer_immune sample: immune cells seeded × factor (`number_of_immune_cells`, 7500 by
default), the seeding day (`immune_activation_time`, day 14 by default) and kill rate × factor (`kill_rate`, inherited by immune
cells). The run log lists every changed value; a requested change with no matching parameter, or on the heterogeneity sample, stops
the run instead of silently using defaults. Tested against the PhysiCell 1.14.2 cancer_immune settings file.

## New data sources and baselines
- **Random forest and gradient boosting** in the held-out-patient drug benchmark (science runtime, scikit-learn): fixed settings
  (forest 300 trees, √p features, ≥ 5 per leaf; boosting 200 iterations, lr 0.05, ≤ 15 leaves, L2 1, no early stopping), same
  fold-internal feature selection, nothing tuned so nothing leaks. Erlotinib, 701 lines: ridge r 0.46, forest 0.43, enet 0.43,
  boosting 0.40, lineage mean 0.35 — the trees do not beat the linear model here. Without the science runtime they are skipped and
  the result says so.
- **NCI GDC** (Patient genomics): any open project with ≥ 30 cases installs as a mutation-only cohort (`gdc_<project>`), canonical-
  transcript consequences mapped to MAF classes, survival from vital status, days to death or the latest follow-up record, age at
  diagnosis. Copy number and expression are not imported (stated in the cohort caption). Cross-check on TCGA-LUAD against the
  cBioPortal PanCancer cohort: KRAS mutated 26.5 % vs 30.7 %, TP53 50.3 % vs 51.5 %; 500 vs 502 patients with survival; KRAS OS HR
  1.12 (0.78–1.61) vs 1.32 (0.96–1.81).
- **Sanger Project Score** (Data tab; Behan et al., Nature 2019): CRISPRcleanR-corrected log fold changes and binary calls for 324
  lines, 316 matched to DepMap by normalised name. Demo L tests every DepMap dependency for replication there (Δ mutant − wild
  type, same lineage fixed effects, sisters collapsed). BRAF in skin: BRAF (p 1e-19), MAP2K1, MAPK1 and PEA15 replicate, DUSP4 does
  not; GAPDH (common-essential control) does not. KRAS: KRAS (p 2e-36), RAF1, DOCK5, MAP3K2 replicate; MAPK7 does not.
- **BindingDB** (Perturbation lab, concentration mode): the same compound is found through EBI UniChem (ChEMBL → BindingDB IDs; no
  structure matching) and its measurements against each annotated target's UniProt entry are summarised next to ChEMBL's. The two
  databases import each other's curated values, so agreement is partly by construction (dabrafenib–BRAF 1.0 vs 1.0 nM; trametinib–
  MEK1 13 vs 1.8 nM); the card says so.
- **Not connected:** PRISM (figshare and the DepMap portal answer scripted downloads with a browser verification, which the app does
  not bypass), HTAN, OmniPath.

## Synthetic lethality (`scientific/synthetic_lethality.py`, Synthetic lethality tab)
Four labels are kept apart: statistical co-dependency (lineage-residualised correlation of gene effects), context-specific
dependency (more essential where a gene is lost — damaging mutation, or no expression log2(TPM+1) < 1, which also catches
deletion and silencing), predicted synthetic lethality (a context dependency that also replicates in Sanger Project Score), and
experimentally demonstrated synthetic lethality (a cited reference set: SMARCA4–SMARCA2, ARID1A–ARID1B, VPS4B–VPS4A, ENO1–ENO2,
MTAP–PRMT5, BRCA1/2–PARP1). Paralogy from Ensembl Compara. No combinatorial knockout data are installed, so genetic-interaction
scores are not computed. Benchmark: SMARCA4→SMARCA2 rank 1 (q 3e-21), ARID1A→ARID1B rank 2, MTAP→PRMT5 rank 3 by expression loss
(196 lines); BRCA1/2→PARP1 not recovered — expected, since PARP inhibitor lethality depends on PARP trapping, which a knockout
does not reproduce; VPS4B and ENO1 have too few loss lines to test. SMARCA4 loss also shows replicated mitochondrial dependencies
(DYNLL1, POLG, TFAM), labelled predicted.

## Clonal populations (`scientific/clonal.py`, Clonal evolution tab)
Observed: relative clonality from read counts (copy-neutral genes, depth ≥ 30, reference = median of each tumor's three highest
allele fractions, Wilson intervals); no purity or ploidy is available, so these are rankings, not cancer-cell fractions. LUAD:
KRAS 96 %, TP53 90 %, KEAP1 100 % clonal-like vs TTN 67 %; melanoma: NRAS 87 %, BRAF 80 % vs LRP1B 47 %. Projection (labelled
Hypothetical): sensitive and resistant clones with shared capacity and a drug window; every rate is the user's assumption.

## Cell–cell communication (`scientific/cellcomm.py`, Cell communication tab)
OmniPath ligand–receptor pairs in ≥ 2 dedicated resources with ≥ 1 expert-curated (CellPhoneDB, CellChatDB, ICELLNET); no complexes.
Per donor: mean(ligand, sender) × mean(receptor, receiver), both in ≥ 10 % of cells, 200 within-donor label permutations; called
where significant in ≥ half the donors with both types; tumor vs normal compared by donor counts. An earlier, looser resource
filter let ribosomal and ubiquitin genes through as "ligands"; the expert-curated requirement removed them. On the BCC atlas
(mostly epithelial): AREG/HBEGF→EGFR, KITLG→KIT, ephrin–Eph and SOSTDC1→LRP6 among the calls. Labelled inferred, never measured.
Test: a planted ligand–receptor pair is called and a flat pair is not.

## Evidence graphs beyond KRAS
EGFR, STK11, KEAP1 (lung adenocarcinoma) and BRAF, NRAS (cutaneous melanoma, MONDO_0005012 checked in Open Targets) with a gene
picker. BRAF: 61 nodes, 106 edges, 22/22 sources answered; EGFR: 68 nodes, 152 edges.

## Scorecard and trace (Demo L)
Each candidate gets the ten scorecard dimensions as evidence text — support, replication, model quality, plausibility,
alternatives (Δ with vs without lineage adjustment), normal-tissue relevance (share of all cancer models depending on it; no normal
screen installed), uncertainty, contradictions, novelty (Europe PMC co-mentions), missing validation — and no overall score.
Clicking a candidate shows its chain from patients to remaining uncertainty, each link with its evidence class.

## Model comparison laboratory (`scientific/model_comparison.py`, Model comparison tab)
DepMap vs Sanger in 300 shared lines: median per-gene Spearman 0.60 (IQR 0.49–0.68) over 4,070 variable genes; common essentials
953 vs 455, 438 shared (Jaccard 0.45). Drug predictors on identical held-out patients with a patient-level bootstrap: erlotinib —
ridge better than forest (Δ MSE +0.060, 0.016–0.105), elastic net (+0.056) and boosting (+0.114). Three ERK pathway models under
the same 90 % knockdowns agree on direction for every shared gene but not on size (rank correlations −0.26 to −0.73).

## Immune checkpoint signalling
Theinmozhi 2018 (BIOMD0000000724) added to the Perturbation lab: PD-1 → SHP2 inhibition of TCR and CD28 signalling; PD-L1 is not
in the model, so a PD-1/PD-L1 antibody is represented as less PD-1 or a weaker PD-1–SHP2 interaction. PD-1–SHP2 × 0.1 raises
CD28-bound PI3K ×4.8; LAT phosphorylation is saturated at baseline. Engine fix found here: the conservation check now judges drift
against the size of the species in each law, not its total, so laws whose total is zero no longer raise false alarms.
Not implemented: antigen presentation and HLA binding prediction (needs MHCflurry or NetMHCpan, neither installed).

## Research assistant (`scientific/oncology_assistant.py`, Research assistant tab)
Answers only from computations on installed data and named databases; each claim carries its evidence class and source, and gaps
are listed. A question is routed by keywords to one of eight supported questions (the directive's examples) and the
interpretation is shown. No language model is used (the local Ollama server is installed but not running, and no model is
pulled). Questions: datasets supporting a dependency (DepMap, Sanger agreement, GDSC targets); replication in another screen
(Sanger, lineage-adjusted); effect of lineage adjustment (Δ with vs without); normal-tissue evidence (pan-cancer dependency share,
GTEx v8 normal-tissue expression with cultured cells excluded, and what is missing); interaction origin (evidence graph or STRING
channels); earliest indexed paper (Europe PMC by first publication date, flagged as not necessarily the first report); model
equations (rate laws from the published models plus the BioFVM transport equation); generalisation (held-out lineage benchmark).

## Visualization modes
A mode row groups the Oncology Universe tabs as in directive §75 (Atlas, Cellular, Tumor physics, Spatial omics, Immune,
Uncertainty, Comparison); Pathology says plainly that no pathology view exists yet; Molecular and Cinematic point to the main
workspace and Cinema. "All" keeps every tab.

## Demo I · pathology analysis (`scientific/pathology.py`, Pathology tab)
Dataset: NuInsSeg (Mahbod et al., Sci Data 2024; CC BY 4.0; Zenodo 10518968), downloaded in full (1.63 GB) and MD5-verified:
665 H&E images from 31 human and mouse tissues (12 human melanoma), expert instance masks, and "vague area" masks that are
excluded from scoring. Pipeline (NumPy/SciPy only, no new packages): 256 px tiling with 32 px overlap (objects kept in the tile
holding their centroid), Ruifrok–Johnston colour deconvolution, image-wide Otsu threshold on smoothed hematoxylin, opening and
hole filling, distance-transform watershed; morphology per nucleus; QC (focus, tissue fraction, stain strength). Scored with
pixel Dice, detection F1 at IoU ≥ 0.5 and AJI against a threshold-only baseline.
Results (all 665 images, 97 s): human 472 images — Dice 0.70, F1 0.26, AJI 0.34; mouse 193 — Dice 0.33, F1 0.06, AJI 0.15.
Splitting touching nuclei raises AJI by 0.033 (95 % CI 0.027–0.039) over thresholding alone. Best tissue: human cerebellum (AJI
0.64); worst: sparse-nucleus tissues (fat, muscle, brain, umbilical cord, AJI ≤ 0.11) where one threshold separates tissue from
background rather than nuclei from tissue. Precision is low (many small fragments), visible in the overlays.
Two bugs found on the way, with synthetic tests: per-tile thresholds turned background-only tiles into noise "nuclei" (now one
threshold per image), and a background seed in the watershed shrank every nucleus to about half (now rims are returned to the
nearest nucleus in the same blob).
Method development, reported as it happened: four variants were compared with mouse images as the development set and human held
out. A three-class threshold was best on mouse (AJI 0.15 → 0.20) but worse on human (0.34 → 0.30); the pre-specified rule is
kept rather than choosing on the held-out set. Deep models (HoVer-Net, StarDist) are not run; this is a transparent classical
baseline. Areas are in pixels (resolution differs by tissue); boundary-pixel perimeters make circularity exceed 1 for small nuclei.

## Demo J · cellular perturbation model (`scientific/perturb_model.py`, Perturbation model tab)
Benchmark: Norman et al., Science 2019 CRISPRa Perturb-seq in K562 (scPerturb file, Zenodo 7041849, CC BY 4.0; 700 MB downloaded
in full and MD5-verified). 111,445 cells (11,855 controls); 102 single and 129 paired activations with ≥ 20 cells; 2,085 genes
scored (top-2,000 variable plus targets; targets excluded from scoring). 5-fold splits over perturbations; models fitted on
training perturbations only. Linear model: Ahlmann-Eltze, Huber & Anders, Nat Methods 2025 (K = 10, λ = 0.1).
Unseen pairs (Pearson all genes / top-20 changed genes): additive 0.88 / 0.97, linear model 0.71 / 0.77, mean training pair
0.61 / 0.65; additive beats the linear model by 0.19 (95 % CI 0.15–0.25) on the top-20 metric. Unseen singles: mean training
effect 0.52 / 0.51, linear model 0.49 / 0.51, no difference (0.001, CI −0.04 to 0.04). Noise ceiling (half vs half of the cells)
0.83 / 0.98, conservative because each half has half the cells. Pairs are mostly sub-additive (median scaling 0.83); largest
departures from additivity: BCL2L11+BAK1, BCL2L11+TGFBR2, CEBPE+KLF1. This reproduces the published finding that simple
baselines are hard to beat. Not run: the State model (Arc Institute) — it needs GPU time on the user's server, and its command
line and licence must be checked before a recipe is added. Predicted expression change is never labelled as cell killing.
