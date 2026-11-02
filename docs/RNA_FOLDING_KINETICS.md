# Demo 10 — RNA Folding Kinetics

30 October 2026. Analyse › RNA-to-Protein Lab › Folding kinetics.

## Method

This is the elementary-step model used by Kinfold and treekin (Flamm et al. 2000, doi:10.1017/S1355838200992161; Wolfinger et al. 2004, doi:10.1088/0305-4470/37/17/005). It is solved exactly, with no sampling and no barrier-tree approximation.

1. **Enumerate every secondary structure.** ViennaRNA 2.7.2 `subopt` runs with unique multiloop decomposition and dangles = 0. The Boltzmann sum over the enumerated set reproduces ViennaRNA's partition function to within 10⁻⁶ kcal/mol. Dangles = 2 does not: its partition function differs from the enumeration by 0.016 kcal/mol, so it was not used.
2. **Define the moves.** A move opens or closes one base pair, with Metropolis rates k₀·min(1, e^(−ΔE/RT)).
3. **Solve the master equation.** dp/dt = Qᵀp is solved by eigen-decomposition of the generator symmetrised by detailed balance. This gives p(t) at any time, the relaxation spectrum, and mean first-passage times (from a sparse linear solve).
4. **Group states for display.** States are lumped into steepest-descent basins, as in Barriers. Exact minimax saddles between basins come from union–find over edges sorted by height.

Code:
- `scientific/rna_kinetics.py`: the engine;
- `rna_kinetics_demo.py`: the scenario and its checks;
- `rna_kinetics_actions(.py|_impl.py)`: actions `rna_kinetics_run`, `rna_kinetics_runs`, `rna_kinetics_record`, with records under `<library>/rna_kinetics/runs`;
- `src/components/rna-lab/KineticsView.tsx`: the UI.

**Evidence:**
- The kinetics are physics-simulated: a Markov model on a thermodynamic landscape.
- The energies are statistically predicted, from the nearest-neighbour model.
- **The time scale is not calibrated:** time is in units of 1/k₀.

## Default system

`GGCGGUGCCCGCCCGGCGGG` is a synthetic 20-nt switch. It was chosen in silico from 400 random sequences because it has two competing hairpins. No measured kinetics exist for it.

| Quantity | Value |
|---|---|
| Structures / moves / local minima | 5,317 / 17,562 / 69 |
| 5′ hairpin `(((((...))))).......` | −7.0 kcal/mol, 50.4 % at equilibrium |
| 3′ hairpin `.......(((((...)))))` | −7.0 kcal/mol, 48.9 % at equilibrium |
| Exact barrier between them | 10.4 kcal/mol (saddle +3.4) |
| Populations at t = 10³/k₀ (kinetic partitioning) | 22.5 % and 19.7 %; a trap basin `(.(((.(....)))).)...` holds 13 % although its equilibrium share is 0.16 % |
| Slowest relaxation | 1.17·10⁷ /k₀ |
| Mean first passage, open chain → MFE | 1.08·10⁷ /k₀ |

Runtime is about 14 s.

## Checks (6/6 pass)

1. Complete enumeration reproduces the ViennaRNA partition function: −7.453716 vs −7.453716 kcal/mol.
2. Boltzmann is stationary: relative max |Qᵀπ| is 1.8·10⁻¹⁹, and the largest eigenvalue is 4.6·10⁻¹⁶.
3. The long-time limit equals the Boltzmann ensemble: total-variation distance 8·10⁻⁸.
4. Probability is conserved: max |Σp − 1| is 1.6·10⁻⁷. This reflects double-precision eigen-solution error over a spectrum spanning 10⁹. The most negative raw probability is −2·10⁻¹⁴.
5. An independent Gillespie simulation agrees with the master equation: 400 trajectories, 5 times × 4 basins, largest |z| 1.73.
6. The exact saddle (3.40) lies at or below ViennaRNA findpath's direct-path estimate (4.50). Findpath gives an upper bound, so this is consistent.

These checks show that the kinetic model is solved correctly. They do not show that the model predicts real folding times.

## Limitations

- k₀ is uncalibrated.
- Only single-pair moves are allowed: no shift moves.
- No co-transcriptional growth, pseudoknots, Mg²⁺ or tertiary contacts.
- The exact solver is limited to about 6,000 structures (about 20–24 nt). Longer RNAs need truncated landscapes or macrostate rates (Barriers + treekin), which are not bundled here.

## Tests

`tests/test_rna_kinetics.py` covers:
- enumeration against the partition function;
- generator rows and stationarity;
- relaxation to equilibrium;
- saddle ordering;
- the full demo with save and reopen;
- input refusals;
- worker routing without NumPy, SciPy or RNA.
