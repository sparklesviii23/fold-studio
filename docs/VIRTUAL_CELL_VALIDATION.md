# Virtual Cell validation record

2 November 2026. Software tests check that code behaves as specified; scientific checks compare against data or
published behaviour. Neither alone establishes biological accuracy.

## Software tests

| Suite | Result |
|---|---|
| `tests/test_virtual_cell.py`, `test_virtual_cell_annotations.py`, `test_virtual_cell_state.py` (`runtimes/singlecell` Python, unittest) | 50 passed |
| Interface: `vitest run` (all 65 files) | 239 passed |
| TypeScript `tsc -b` | passed |
| Full backend suite (1,111 tests) | 3 failures + 60 errors, all outside Virtual Cell: 61 × missing `gemmi` in the test runtime, one SciPy 2.6e-10 precision difference, one network-sandbox assertion, one tumour-microenvironment recipe field mismatch from earlier work. Not caused by this work. |
| Packaging pre-check / licence guard | 154 modules; 0 files blocked |

## Data integrity

- ENCODE ENCFF416RHJ / ENCFF938LTW: md5 equal to the ENCODE file records; GRCh38; GENCODE V29; biological replicates 1 and 2 of ENCSR000CPE.
- GENCODE 29 primary-assembly GTF: MD5 equal to GENCODE's MD5SUMS. All 206,761 quantified transcripts present (the
  chromosome-only GTF lacked 67 scaffold transcripts; the primary-assembly file is the one ENCODE used).
- 746 non-GENCODE rows per RSEM file (spike-in / tRNA numeric IDs) excluded and counted.
- Annotation index: 20,542 genes, 13,603 with HPA calls, 2,889 human Reactome pathways (release 98) — reproduced in this session.
- Hep G2 identity: DepMap ACH-000739 carries RRID CVCL_0027; mismatching RRIDs are refused (tested).

## Scientific checks

| Check | Result | Limits |
|---|---|---|
| Hep G2 hepatocyte markers (DepMap RNA) | ALB 13.96, APOA1 11.78, AFP 11.49 log2(TPM+1); PTPRC, HBB ≈ 0 | Identity sanity check, not a benchmark |
| Two independent RNA sources agree on markers | ENCODE: ALB ≈ 16,900 TPM, APOA1 1,495–1,896, GAPDH ≈ 9,500, PTPRC 0 per replicate | Different labs/years; not a correlation study |
| RSEM interval semantics | pme_TPM lies inside its 95 % credible interval for 413,522 / 413,522 replicate values; TPM does not always (so the interval is labelled as pme_TPM's) | — |
| UniProt isoform linkage | 43,292 GENCODE transcripts linked; ALB-201 (CCDS, APPRIS principal) → P02768-1 | ENST versions may differ between GENCODE 29 and current UniProt |
| Cell-cycle model numerics | LSODA, rtol 1e-8; tolerance sensitivity 6.5e-7; reliable; no negative values | — |
| Cell-cycle published behaviour | Period 25.65 ± 0.15 h at GF 1; Cdk2/E → Cdk2/A → Cdk1/B → Cdc20 order; strictly ordered phase proxies (G1 4.9 h, G1/S 5.0 h, S–G2 10.3 h, G2/M 5.0 h); GF 0 → steady state; GF 0.05 → small-amplitude cycle (peaks 0.008 vs 0.433), phases not assigned | Generic model; not compared with Hep G2 data (none integrated) |
| Phase-rule review | "Highest relative module activity" rejected: produced G1 → G1/S → S–G2 → G1 → G2/M because cyclin D/Cdk4–6 stays high | Replaced by forward-only half-maximum rule |

## Stage 3 (2 November 2026)

| Check | Result |
|---|---|
| Full backend suite, intended runtime (`runtimes/jax-cpu`: gemmi 0.7.5, SciPy 1.18.1) | 1,124 run: 2 failures, 0 errors, 10 skipped before fixes. The 61 earlier `gemmi` errors were caused by running under `runtimes/singlecell`, which lacks gemmi. Failures: bundle manifest missing the new `virtual_cell_structures.py` (fixed by registering it); `test_tumor_tme.test_recipe_inputs` stale after the PhysiCell recipe gained immune parameters (test updated to the recipe defaults and now also checks the new bound). Final full-suite count: see the checkpoint entry. |
| Virtual Cell backend / interface | 61 / 242 passed; TypeScript passed |
| Proteomics identifiers | iBAQ 6,740/6,740 rows resolved (ENSP via GENCODE V29), spectral counting 3,546/3,547 (one ambiguous) |
| Proteomics identity | Hepatocyte proteins present (APOA1 209 ppm, AFP 213, APOB, SERPINA1, FGB, TTR); ALB absent from both PaxDb files (shown as not reported) |
| RNA–protein (rank only) | Spearman ρ 0.487 (n 6,737, iBAQ) and 0.447 (n 3,538, spectral counting) vs ENCODE gene TPM; detected proteins only |
| Cell Painting pixels | 24 TIFFs, SHA-256 verified on every load; 16-bit raw values unchanged |
| Cell Painting reproducibility | Medians across 6 fields / 2 wells: nucleus 773–1,124 px², cell 1,794–2,314 px², ratio 0.46–0.50, eccentricity 0.69–0.77 |
| Segmentation method choice | Global Otsu fragmented nuclei into chromatin speckles; distance-transform watershed produced axis-aligned fragments; local adaptive threshold adopted (visual inspection). Synthetic disks: count exact, area within 15 %. No reference masks for these images → not benchmarked |
| Structures | 13 saved records map to ANGPTL3 (Q9Y5C1) at 100 % identity; Boltz-2 vs BindCraft Cα RMSD 0.17 Å over UniProt 36–85 |
| Lab results | 12/12 records pass integrity with their lab's own hash recipe |
| Cell-cycle → 3D | Scrub to 60 h: DNA layer ×2.19 (Cdk1/B peak), unlabelled (before first mitotic exit); 70 h: G1/S, ×0.65 |
| CellFlux (cpg0000) | Loads with a strict state-dict match; 50-step Heun sampling on MPS (6 cells 112 s, 4 cells 70 s). From pure noise it generates cell-free texture (not its training mode). From 4 Hep G2 DMSO crops conditioned on DMSO it keeps each cell's footprint; in the assumed DNA slot whole-crop r 0.83 and in-cell r 0.82, but the nucleus-mask Dice is only 0.53–0.75, nuclear-area fractions shift (0.18 → 0.33, 0.26 → 0.11) and mean DNA intensity rises ×1.9: nuclei partly kept but distorted (visual: cell-wide haze). Pearson r alone overstated faithfulness, so the structural measures were added → out of domain. In-domain benchmark not possible (no public cpg0000 crops) |
| Interface walkthrough (dev bridge, real worker, QA copy of the library) | Cell Painting view; ANGPTL3 → saved structures → Molecular Viewer (Boltz-2 model, 5,022 atoms) → Return to Virtual Cell restored the same cell and protein; cell-cycle scrubbing changed the 3D badge and DNA gain |

## Interface validation (real worker, not the Tauri shell)

The dev bridge (`worker.py --serve` + Vite, token-gated, isolated QA library with read-only links to the reference
data) was driven in the in-app browser: Hep G2 selection; baseline; coverage panel; protein search by UniProt accession;
HPA layers filtering the 3D cell (ER/Golgi for ALB); Reactome graph; protein → pathway navigation (R-HSA-159418, 18/18
members measured); unknown-identifier message; cell-cycle run, scrub to 70 h (G1/S), snapshot save, restore (70 h, G1/S);
transcript table for ALB. Bugs found and fixed: stale compartment filter after a failed search; chart playhead given a
time instead of an index. Native Tauri window interaction is not possible from this environment; the installed app's
packaged backend was exercised directly in the previous session.
