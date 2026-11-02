# Multiscale Simulation Kernel, Demo 5 and Demo 8

30 October 2026. Analyse › Multiscale Experiments.

## What the kernel is

| Module | Role |
|---|---|
| `scientific/multiscale_units.py` | Dimensional analysis over (amount, count, mass, length, time). Amount and molecule count are separate dimensions; crossing them needs Avogadro's constant (and a volume for concentrations) through explicit functions whose description is recorded. Incompatible conversions raise. |
| `scientific/multiscale_kernel.py` | Data contracts: `Param` (value, unit, kind = literature / database / derived / hypothetical / assumption, source with DOI and verbatim quote; literature without a source is refused), `Entity`, `Compartment`, `Contract` (family, equations, input/output units, scale, timescale, assumptions, limitations, evidence category), `Link`, `Stage`. `run_chain` executes one-way coupling and records every transfer with its unit conversion; `trace` rebuilds the causal chain from any output to equations, parameters and sources; `uncertainty` runs seeded Latin-hypercube propagation over hypothetical/assumed parameters and ranks only causally upstream parameters (Spearman). |
| `scientific/multiscale_demos.py` | The albumin reference system and the six stages. |
| `scientific/multiscale.py`, `multiscale_actions.py` | RPC actions; every run is saved as one JSON record under `<library>/multiscale/runs` and can be reopened without recomputation. |
| `src/components/multiscale/` | Workspace: identity check, stage chain with transfers, stage detail (chart, equations, parameters with provenance, editable hypothetical values), measured-vs-model table, calibration panel, uncertainty, causal-chain explorer, saved runs. |

Only one-way coupling is implemented. Iterative and strong coupling were deliberately not attempted.

## Reference system

Human serum albumin — a well-characterised, non-hazardous secreted plasma protein.
- mRNA: NCBI RefSeq NM_000477.7 (2,285 nt, CDS 42..1871), retrieved 30 Oct 2026, stored in `fixtures/reference/human_albumin.json`.
- Protein: UniProt P02768 (609 aa; signal peptide 1–18, propeptide 19–24, mature 25–609).
- Identity check (runs before anything else): the CDS translates exactly to the UniProt sequence.
- Mature average mass computed from sequence: 66,472.2 Da (no disulfide correction; 17 disulfides would subtract ≈34 Da).

## Stages and sources

| Stage | Engine | Evidence | Key inputs |
|---|---|---|---|
| RNA: start-codon region (5′ UTR + 90 nt) | ViennaRNA 2.7.2 partition function (bundled) | Statistically predicted / thermodynamic | Sequence only. **Not coupled** to initiation: no calibrated model maps accessibility to an initiation rate. |
| Translation | Exact Gillespie TASEP (`rna_lab_translate`) | Parameterised hypothesis | Elongation 5.6 codons/s — Ingolia et al. 2011, doi:10.1016/j.cell.2011.10.002, *mouse ES cells* (applied to human hepatocytes: an explicit assumption). Initiation α hypothetical (0.01–0.2 /s). Footprint 10 codons, β = ε (assumptions). |
| Cell | SBML composed network, SciPy LSODA | Parameterised hypothesis | mRNA copies per hepatocyte and secretion half-time hypothetical. |
| Body | Linear one-pool turnover, SciPy | Parameterised hypothesis | Half-time 17.3 d and 40 % intravascular — Levitt & Levitt 2016, doi:10.2147/IJGM.S102819 (verbatim quotes stored). Hepatocyte number hypothetical; plasma volume 2.85 L assumed. |
| Capillary | Axisymmetric advection–diffusion (`blood_transport`) | Physics-simulated | Sinusoid geometry, velocity, diffusivity assumed; albumin wall permeability hypothetical. |
| Binding | SBML composed network, SciPy LSODA | Parameterised hypothesis | Hypothetical ligand, Kd and kon. |

## Results (seed 1, defaults)

Numerical checks — all pass (7/7):
- TASEP output 0.0435 ± 0.0021 /s vs extended-TASEP low-density mean field 0.0459 /s.
- Cell ER pool vs analytical solution: 5.1·10⁻¹¹; mass balance residual 3.7·10⁻¹⁶.
- Body turnover ODE vs analytical: 1.8·10⁻¹¹.
- Literature self-consistency: 10.5 g/day × 17.3 d / ln 2 = 262 g vs reported 280 g (−6.4 %), both Levitt & Levitt.
- Transport mass budget residual 3.2·10⁻¹⁴.
- Binding equilibrium vs exact quadratic: 9.9·10⁻⁸.

Scientific finding from the chain: with the placeholder 1,000 ALB mRNA copies per hepatocyte, predicted whole-body synthesis is 0.083 g/day, ≈126× below the measured 10.5 g/day. Reaching 10.5 g/day needs 5.5 proteins/s per mRNA, above the exclusion-limited maximal current (0.32 /s at 5.6 codons/s, ℓ = 10). Hence ≥17,000 ALB mRNA copies per hepatocyte are required even at maximal ribosome traffic, or ≈126,500 at the simulated rate (under the assumed 2·10¹¹ hepatocytes).

Calibrated scenario (mRNA copies set so synthesis = 10.5 g/day — calibration, not validation):

| Quantity | Model | Reference | Difference |
|---|---|---|---|
| Whole-body synthesis | 10.5 g/day | 10.5 g/day | calibrated |
| Body pool | 262 g | 280 g | −6.4 % |
| Plasma albumin | 36.8 g/L | 44.5 g/L (study baseline cited in Levitt & Levitt) | −17.3 % |

The pool and plasma comparisons use independent literature values (half-time, intravascular fraction) but also the assumed plasma volume, so they are consistency checks, not held-out validation.

Uncertainty (32 Latin-hypercube samples): ALB mRNA copy number dominates every downstream output (Spearman ρ ≈ 0.87 for plasma albumin).

## Tests

`tests/test_multiscale.py` (10): unit conversions and refusals, literature-without-source refusal, CDS ↔ UniProt identity, all numerical checks, transfer units, causal trace reaching the DOI, infeasible-default and calibrated-scenario behaviour, seeded and causal uncertainty, save/reopen, worker routing without NumPy/SciPy.

## Status against the completion directive

| Area | Status |
|---|---|
| Mechanistic engine, Cell physics (BD), Blood transport, RNA lab (ViennaRNA 2.7.2, TASEP) | Existing and verified (their own test suites pass; numerically verified, not biologically validated) |
| Shared units, contracts, provenance, events, one-way coupling, causal trace, uncertainty | Implemented and tested (this document) |
| Demo 5 — protein biogenesis | Implemented: RNA → translation → synthesis/secretion with checks; ER/Golgi processing is a single lumped secretion step |
| Demo 8 — cross-laboratory chain | Implemented end to end with unit-checked transfers, mass balances, comparison with literature and a labelled calibration; shown in its own workspace, not yet in the 3D Cell Explorer |
| Iterative / strong coupling | Not implemented (deliberately) |
| Demo 7 (HemoCell deformable cells), 3D CFD (SimVascular/OpenFOAM/CRIMSON) | Not implemented; evaluation only in `docs/BLOOD_LAB_ENGINES.md` |
| Demo 10 (RNA folding kinetics) | Implemented: exact master equation on the full secondary-structure landscape, 6/6 checks — see `docs/RNA_FOLDING_KINETICS.md` |
| Demo 9 (RNA 3D ensemble: RhoFold+, RNAbpFlow…) | Not implemented (GPU models; see `docs/ENGINE_REGISTRY.md`) |
| Demo 11 (established spatial solver) | Implemented: RDME with the next-subvolume method plus a finite-volume reference, membrane-kinase/phosphatase gradient in a cell with a nucleus, 5/5 benchmarks — see `docs/SPATIAL_SOLVER.md`. Smoldyn not integrated (its macOS build targets CPython 3.14) |
| Demo 12 (MD reference trajectory) | Implemented: OpenMM Trp-cage (1L2Y) implicit-solvent run with real frames, RMSD/RMSF, cage-contact persistence vs the NMR ensemble, 5/5 checks — see `docs/MD_REFERENCE.md` |
| Ribosome structural cinematography, scale-aware zoom, scene generator, movie export | Not implemented |
| BioNetGen, PK-Sim/MoBi, SABIO-RK, EMDB, HPA, single-cell priors | Not implemented |
| Research assistant over these records | Not implemented |
