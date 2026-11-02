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

## Interface validation (real worker, not the Tauri shell)

The dev bridge (`worker.py --serve` + Vite, token-gated, isolated QA library with read-only links to the reference
data) was driven in the in-app browser: Hep G2 selection; baseline; coverage panel; protein search by UniProt accession;
HPA layers filtering the 3D cell (ER/Golgi for ALB); Reactome graph; protein → pathway navigation (R-HSA-159418, 18/18
members measured); unknown-identifier message; cell-cycle run, scrub to 70 h (G1/S), snapshot save, restore (70 h, G1/S);
transcript table for ALB. Bugs found and fixed: stale compartment filter after a failed search; chart playhead given a
time instead of an index. Native Tauri window interaction is not possible from this environment; the installed app's
packaged backend was exercised directly in the previous session.
