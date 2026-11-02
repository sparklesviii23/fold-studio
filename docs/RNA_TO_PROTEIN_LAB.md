# RNA-to-Protein Laboratory — Demo 3 (RNA folding ensemble) and Demo 4 (translation)

Analyse › **RNA-to-Protein Lab**. Every number shown comes from one of two declared computations below; the
illustrated Gene → Protein story (`src/cell/GeneStory.tsx`) stays available as a third mode labelled **E · Illustrative**.

| | Demo 3 · Folding ensemble | Demo 4 · Translation |
|---|---|---|
| Evidence | **C · Statistically predicted / thermodynamic model** | **B · Stochastic kinetic simulation**; initiation and termination rates are **D · hypothetical** |
| Engine | `scientific/rna_lab_fold.py` | `scientific/rna_lab_translate.py` |
| Method | Zuker MFE, McCaskill partition function + outside pair probabilities, stochastic backtracking | Gillespie direct method, extended-particle TASEP |
| Demo input | Yeast tRNA-Phe, 76 nt, PDB 1EHZ | Human ANGPTL3 CDS, 460 sense codons + UGA |
| Record | `<library>/rna_lab/runs/<id>.json` (`kind: rna_fold_ensemble`) | same folder (`kind: translation_tasep`) |

## Tool audit (2026-10-30)

- **ViennaRNA is not installed in any local interpreter.** Checked `/usr/bin/python3` (3.9.6, used by the dev bridge), Homebrew
  `python3`, and all bundled runtimes under `runtimes/` (`biology-services`, `jax-cpu`, `jax-metal`, `jax-metaljax`, `openmm-cpu`).
  `import RNA` fails in each. The only ViennaRNA in the project is the Modal cloud worker image
  (`remote_worker/fold_rapid/editcraft_core.py`, ViennaRNA 2.7.2), which is what the docs referred to.
- **RNAstructure is not installed** (no `efn2`/`partition` executables), so there is no second-package comparison. The app
  reports both facts in the workspace (`rna_lab_catalog → tools`).
- `rna_lab_fold.analyse` uses ViennaRNA automatically (`backend: viennarna`) whenever `import RNA` succeeds; otherwise it
  runs the built-in model below. Nothing was installed into the bundled runtimes.
- **Validation runtime (user-approved, 2026-10-30): `../runtimes/rna-vienna`.** A standalone venv holding only the ViennaRNA
  2.7.2 binary wheel. It uses the same Python 3.12.14 base as the other development runtimes, is 24 MB, and keeps its pip report
  in `install-report.json`. Recreate it with:
  `<python3.12> -m venv ../runtimes/rna-vienna && ../runtimes/rna-vienna/bin/pip install --only-binary=:all: ViennaRNA==2.7.2`.
  It is **not** part of the packaged app runtime. Use it for the RNA lab tests
  (`../runtimes/rna-vienna/bin/python -B -m unittest tests/test_rna_lab.py`) or for a dev-bridge worker
  (`../runtimes/rna-vienna/bin/python -B scientific/worker.py --serve …`). Pointing the native app's `FOLD_PYTHON` at it would
  move *every* scientific action onto an interpreter without NumPy/SciPy, so that is not recommended.

## Demo 3 — RNA folding and structural ensemble

**Built-in model (`builtin-nn`).** Dependency-free Python (runs under Python 3.9 without NumPy). Energy model: a stated subset of
the Turner 1999 nearest-neighbour parameters — WC/GU stacking, hairpin/bulge/interior initiation (log extrapolation > 30 nt),
Ninio asymmetry, terminal AU/GU penalty, linear multiloop (a = 3.4, b = 0, c = 0.4 kcal/mol). **Omitted:** terminal mismatches,
dangling ends, special hairpins, 1×1/1×2/2×2 loop tables, coaxial stacking, temperature/salt dependence, modified nucleotides,
pseudoknots. 37 °C only; limit 160 nt (O(N³) pure Python; 76 nt takes ≈1.5 s).

Outputs: MFE structure and energy, ensemble free energy, P(MFE), base-pair probability matrix (arc diagram + dot plot), per-base
unpaired probability, centroid (p > 0.5), ensemble diversity, 1,000 seeded stochastic samples clustered into alternative states,
and — when a reference is given — sensitivity, PPV and F1 for MFE and centroid, expected sensitivity, and the reference's own
energy and Boltzmann probability.

**Reference.** Cloverleaf of yeast tRNA-Phe (21 canonical pairs: acceptor 1–7:66–72, D 10–13:22–25, anticodon 27–31:39–43,
T 49–53:61–65), sequence from 1EHZ `_entity_poly.pdbx_seq_one_letter_code_can`. Sources: Shi & Moore 2000; Sprinzl et al. 1998.
The engine also checks that every reference pair is present in the bundled 1EHZ coordinates (C1′–C1′ distance within 1.5 Å
of 10.5 Å; worst deviation 0.43 Å).

**Validation (`rna_lab_validate {demo: 'fold'}`, all pass):**

| Check | Result |
|---|---|
| Exhaustive enumeration, 3 sequences (20, 795 and 1,810 structures; the last one includes multiloops) | MFE, Z and every pair probability match the DP to ≤ 8 × 10⁻¹⁶ |
| Reference pairs present in 1EHZ | 21/21, max \|C1′–C1′ − 10.5 Å\| = 0.43 Å |
| Sampling vs Boltzmann (GGGGAAAACCCC, 4,000 samples) | 0.9750 vs 0.9785 exact (1.5 SE) |
| *(ViennaRNA present)* Built-in tables vs ViennaRNA 2.7.2's loaded Turner 1999 set | stacking, hairpin, bulge, interior, Ninio, terminal AU, multiloop, lxc identical (the interior-loop values for 13–30 nt were corrected from a rounded transcription by 1–5 dcal/mol in this check) |
| *(ViennaRNA present)* Same model in ViennaRNA: Turner 1999 file reduced to exactly the built-in model (mismatch tables → terminal AU, 1×1/2×1/2×2 tables → generic formula, dangles 0, no special hairpins), tRNA-Phe + 8 random 20–70-nt sequences | max \|ΔMFE\| 9.5e-8, \|ΔG_ens\| 4.0e-7 kcal/mol, \|Δp\| 3.1e-8, \|Δeval\| 7.6e-7 (ViennaRNA returns float32); an earlier run over 25 random sequences gave ≤ 6e-7 |

The second comparison runs a different implementation of the same energy model, so it checks the loop-energy rules as well as
the dynamic programming. Without ViennaRNA the app shows this check as skipped, not as passed.

**Result on tRNA-Phe (built-in model, seed 1):** MFE −17.5 kcal/mol, ensemble −18.34 kcal/mol, P(MFE) = 0.25.
Against the cloverleaf: **MFE sensitivity 0.333, PPV 0.304, F1 0.318**; centroid the same; expected sensitivity 0.339. The
acceptor stem (7 pairs) is recovered; the D, anticodon and T arms are not. The cloverleaf scores −13.5 kcal/mol in this model
(Boltzmann probability 3.9 × 10⁻⁴). This is a model limitation, not a bug: the omitted mismatch/dangle terms stabilise each of
the cloverleaf's four helix ends, and unmodified tRNA-Phe is a known hard case for MFE prediction. For context, the recorded
ViennaRNA 2.7.2 cloud run on the same sequence (`reports/editcraft/rna-3d-validation.json`, not re-executed) gave
MFE −22.4 kcal/mol.

**Result with ViennaRNA 2.7.2 (Turner 2004, dangles = 2), `../runtimes/rna-vienna`:** MFE −22.4 kcal/mol and **MFE structure identical
to the cloverleaf (sensitivity = PPV = F1 = 1.0)**; ensemble free energy −24.127 kcal/mol; P(MFE) = 0.061; centroid F1 0.452
(sensitivity 0.333, PPV 0.70); expected sensitivity 0.504; ensemble diversity 23.4 bp. This reproduces the recorded Modal receipt
(−22.4 / −24.127) on a second machine. The ensemble is broad: sampled alternative states within 0.3–1.2 kcal/mol of the MFE
differ from it by 21–32 base pairs. When both engines are available, a fold run shows them side by side (`comparison`). On
tRNA-Phe the two MFE structures differ by 30 base pairs, which comes from the energy terms the built-in model omits.

## Demo 4 — stochastic translation

Lattice: ribosome identified by its A-site codon x, covering x − ℓ + 1 … x. Initiation at rate α when the upstream-most
ribosome has x ≥ ℓ; hop at rate k when the next ribosome's A site is more than ℓ codons ahead; termination at rate β from the
last sense codon. Outputs: A-site density per codon (time-averaged after burn-in), cumulative proteins over time, steady
protein output with batch-means SE (20 batches), mean ribosome load, mean transit time vs isolated-ribosome value, contact events
(a ribosome closing up directly behind another; each re-closure counted) and the fraction of ribosome-time spent blocked, plus
up to 900 exact state snapshots for playback. **Animation between snapshots is visual interpolation** and is labelled so.

Parameters and provenance:

| Parameter | Default | Source |
|---|---|---|
| Elongation k | 5.6 codons/s, **uniform at every codon** | Ingolia, Lareau & Weissman 2011 (mouse ES cells run-off). No per-codon rate set with a citable source is bundled, so codon-dependent rates are not used. |
| Footprint ℓ | 9 codons | ~28-nt protected fragment, Ingolia et al. 2009; same exclusion as rSNAPsim |
| Initiation α | 0.033 s⁻¹ | **Hypothetical** scenario value |
| Termination β | 5.6 s⁻¹ | **Hypothetical** (set equal to k) |

**Validation (`rna_lab_validate {demo: 'translate'}`, all pass, fixed seeds):**

| Check | Simulated | Reference | Statistic |
|---|---|---|---|
| ℓ = 1, low density, L = 100, α = 0.2, β = 1 | J = 0.1585 ± 0.0025 | α(1−α) = 0.1600 (exact, Derrida et al. 1993) | 0.62 SE (limit 3) |
| ℓ = 9, low density, L = 200, α = 0.05 | J = 0.0334 ± 0.0006 | α(1−α)/(1+α(ℓ−1)) = 0.0339 (mean field) | 1.7 % (limit 6 %) |
| ℓ = 9, maximal current, α = β = 1 | J = 0.0641 ± 0.0003 | 1/(1+√ℓ)² = 0.0625 | 2.6 % (limit 6 %; finite-L excess) |
| Isolated ribosome, non-uniform rates, 1,564 transits | 114.88 s | Σ 1/kᵢ + 1/β = 114.78 s (exact) | 0.34 SE (limit 3) |

**ANGPTL3 scenario (defaults, 7,200 s, burn-in 600 s, seed 1):** 0.031 ± 0.002 proteins/s per mRNA (≈111 h⁻¹; mean field
0.031 s⁻¹, low-density phase), 2.53 ribosomes per mRNA, transit 82.6 s vs 82.1 s isolated, ribosomes blocked 0.43 % of the
time, 103,580 events in 0.17 s. This number is conditional on the hypothetical α; the Mechanistic Biology Lab turnover demo's
k_tl = 50 h⁻¹ is likewise hypothetical, and the workspace shows the two side by side rather than feeding one into the other.

## Wiring

- `scientific/rna_lab_vienna.py` — reduced-parameter generator and the two ViennaRNA cross-checks (imported only when ViennaRNA is present).
- `scientific/rna_lab_actions.py` — dependency-free action names; `scientific/worker.py` imports `rna_lab` lazily.
- Actions: `rna_lab_catalog`, `rna_lab_fold`, `rna_lab_translate`, `rna_lab_validate`, `rna_lab_runs` — allowlisted in
  `src-tauri/src/main.rs`; engine files and `scientific/rna_lab_reference.json` added to `src-tauri/tauri.conf.json` resources.
- UI: `src/components/rna-lab/RnaLab.tsx`, `rna-lab.css`; pure view helpers in `src/lib/rnaLab.ts`. Reuses `TimeChart`,
  `SERIES`, `fmt` from `MechCharts.tsx` and the mechanistic panel/check styles.
- Tests: `tests/test_rna_lab.py` (13 tests: all pass with `../runtimes/rna-vienna`; 10 pass with 3 ViennaRNA tests skipped under
  `/usr/bin/python3` 3.9.6 and `runtimes/biology-services` 3.12),
  `src/lib/rnaLab.test.ts` (4 tests).

## Operational vs planned

**Operational:** both demos end to end from the UI (verified in the Vite dev preview through the worker bridge); validation
panels in each mode; seeded, recorded runs with SHA-256; tool-availability reporting.

**Not done / planned:**
- ViennaRNA is available in the development runtime `../runtimes/rna-vienna` but not in the packaged app runtime, so the
  installed app still uses the built-in model. Using ViennaRNA in the app would mean either adding the wheel to the packaged
  runtime (`scripts/build-local-app.sh`) or calling `rna-vienna` as a subprocess for folding only. Neither is done.
- RNAstructure is not installed; ViennaRNA vs built-in is the only inter-method comparison.
- Fuller energy model (mismatches, dangles, special loops) for the built-in engine.
- Codon-dependent elongation rates from a cited dataset (e.g. tRNA-abundance–derived), drop-off, recycling, mRNA decay.
- Saving records into the SQLite library; Native-app (Tauri) run not exercised — the dev bridge was used.
- Linking a TASEP rate into a Mechanistic Lab model as an explicit, provenance-tracked parameter.

## References

- Zuker & Stiegler 1981, *Nucleic Acids Res* 9:133 — doi:10.1093/nar/9.1.133
- McCaskill 1990, *Biopolymers* 29:1105 — doi:10.1002/bip.360290621
- Ding & Lawrence 2003, *Nucleic Acids Res* 31:7280 — doi:10.1093/nar/gkg938
- Mathews, Sabina, Zuker & Turner 1999, *J Mol Biol* 288:911 — doi:10.1006/jmbi.1999.2700
- Lorenz et al. 2011, ViennaRNA Package 2.0 — doi:10.1186/1748-7188-6-26
- Shi & Moore 2000, *RNA* 6:1091 (1EHZ) — doi:10.1017/S1355838200000364
- Sprinzl et al. 1998, *Nucleic Acids Res* 26:148 — doi:10.1093/nar/26.1.148
- Gillespie 1977, *J Phys Chem* 81:2340 — doi:10.1021/j100540a008
- MacDonald, Gibbs & Pipkin 1968, *Biopolymers* 6:1 — doi:10.1002/bip.1968.360060102
- Derrida, Evans, Hakim & Pasquier 1993, *J Phys A* 26:1493 — doi:10.1088/0305-4470/26/7/011
- Lakatos & Chou 2003, *J Phys A* 36:2027 — doi:10.1088/0305-4470/36/8/302
- Shaw, Zia & Lee 2003, *Phys Rev E* 68:021910 — doi:10.1103/PhysRevE.68.021910
- Aguilera et al. 2019, rSNAPsim, *PLoS Comput Biol* — doi:10.1371/journal.pcbi.1007425
- Ingolia et al. 2009, *Science* 324:218 — doi:10.1126/science.1168978
- Ingolia, Lareau & Weissman 2011, *Cell* 147:789 — doi:10.1016/j.cell.2011.10.002

DOIs for the above were checked against OpenAlex on 2026-10-30 (Zuker 1981, Lorenz 2011 and Gillespie 1977 were not re-checked).
