# Oncology Universe · Tumor Microenvironment (first slice)

Status date: 2026-10-31. This is the first working slice of the Oncology Universe directive (Demo G / Demo H).

## What runs
- **Engine:** PhysiCell 1.14.2 (BSD-3; agent-based cells + BioFVM reaction–diffusion), built from the official release on the user's
  server by the `physicell` Cloud GPU Tasks recipe (CPU, 16 cores). This Mac has no GCC/OpenMP, so production runs are remote.
- **Reference models (published parameters, unmodified apart from run length and output cadence):**
  - `cancer_immune`: 3D tumor with heterogeneous immunogenicity, oxygen + immunostimulatory factor; immune cells seeded at day 14
    (Ozik et al., BMC Bioinformatics 2018;19(Suppl 18):483).
  - `heterogeneity`: 2D oxygen-limited tumor with inherited oncoprotein level (Ghaffarizadeh et al., PLoS Comput Biol 2018;14:e1005991).
- **Edits the recipe makes to the shipped config:** `max_time` = days × 1440 min; full output every ≈ run/60 (≥ 60 min); SVG output off;
  16 OpenMP threads. The edited config is returned with the results.
- **Returned:** `tme.json` (≤ 61 frames; every cell's counts; up to 5000 drawn cells per frame, uniform sample with seed 0; each substrate on
  the mesh mid-plane), the config, and the final full PhysiCell snapshot.

## Local analysis (`scientific/tumor_tme.py`)
- Checks on the returned output (evidence: numerical/physical consistency):
  population bookkeeping; oxygen maximum principle (0 ≤ O₂ ≤ Dirichlet value); necrotic cells sit at lower O₂ than live cells
  (mid-plane cells; reported "not assessable" below 10 necrotic cells).
- Growth-law fits to the simulated tumor count: exponential, logistic, Gompertz by least squares, ranked by AIC (evidence: statistical
  fit to simulated counts).

## Verification done
- Pipeline tested end to end on this Mac with a 2-day `heterogeneity` run of PhysiCell 1.14.2 compiled locally against a single-thread
  OpenMP stub (test only; not used for results): settings editor, simulation, converter and analysis all ran on real output
  (49 frames, 957 cells, O₂ 5.1–38 against boundary 38; Gompertz ≈ logistic ≪ exponential by AIC).
- `tests/test_tumor_tme.py` (format/analysis tests on a small synthetic file in the recipe's format) and `tests/test_gpu_tasks.py`.
- Not yet done: a full run on the server; `cancer_immune` conversion on real 3D output.

## Limits
Reference scenarios, not patient- or cell-line-calibrated digital twins. The checks test internal physics, not agreement with tumors.
