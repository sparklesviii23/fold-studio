# Demo 12 — Molecular Interaction Dynamics

30 October 2026. Analyse › Multiscale Experiments › Demo 12 · Molecular dynamics.

## What runs

- **System:** Trp-cage TC5b (NLYIQWLKDGGPSSGRPPPS), PDB 1L2Y, NMR model 1, with 304 atoms including hydrogens. The file in `fixtures/md/1L2Y.pdb` came from RCSB on 30 Oct 2026 (SHA-256 `5d1bbb54…4438`, checked before every run). The structure paper is Neidigh, Fesinmeyer & Andersen 2002 (doi:10.1038/nsb798).
- **Engine:** OpenMM 8.6.1 in the bundled `runtime-openmm`, CPU platform, as a background process (`scientific/md_reference.py`).
- **Force field and solvent:** Amber ff14SB (doi:10.1021/acs.jctc.5b00255) with GBn2 implicit solvent (doi:10.1021/ct3010485).
- **Integration:** no cutoff, hydrogen-bond constraints, 2 fs Langevin middle integrator at 300 K with γ = 1/ps. The run minimises, equilibrates for 10 ps, then produces 50 ps with a frame every 0.25 ps (200 frames).
- **Jobs:** `scientific/md_demo.py` starts, polls, cancels, records and lists runs (`md_reference_*` actions). Records are kept under `<library>/md_reference/<id>/` with input, log, raw trajectory and record.
- **UI:** `src/components/multiscale/MdLab.tsx` contains:
  - a ball-and-stick viewer of the real frames, with drag to rotate, play and scrub, an NMR model-1 overlay and optional hydrogens;
  - charts of RMSD, per-residue Cα fluctuation (RMSF) against the NMR ensemble spread, contact distances and kinetic temperature;
  - contact persistence, the checks, sources and saved runs.

**Evidence:**
- The trajectory is physics-simulated: a classical force field in implicit solvent.
- The NMR ensemble is experimentally observed. It is used only as a flexibility reference: its spread reflects restraint satisfaction, not measured motion.

## Results (50 ps, seed 1; 62 ns/day on this Mac)

| Quantity | MD | NMR ensemble (38 models) |
|---|---|---|
| Backbone RMSD to model 1 | mean 1.26 Å, max 1.96 Å | max 1.38 Å |
| Trp6–Pro12 ring centroid distance | 5.57 Å, formed 99 % | 5.53 Å, formed 100 % |
| Trp6–Pro18 ring centroid distance | 4.96 Å, formed 99.5 % | 4.28 Å, formed 100 % |
| Trp6–Pro19 ring centroid distance | 5.56 Å, formed 86 % | 5.79 Å, formed 100 % |
| Trp6–Tyr3 ring centroid distance | 6.11 Å, formed 78 % | 5.51 Å, formed 100 % |
| Asp9–Arg16 salt bridge (CG–CZ < 5 Å) | 6.28 Å, formed 27 % | 6.58 Å, formed 45 % |

**Per-residue fluctuation:** in both the MD and the NMR spread, the termini fluctuate most and residues 2–7 (the helix) least. MD values are larger overall, as expected for thermal motion compared with an NMR restraint ensemble.

**Interpretation:** the cage around Trp6 stays intact over 50 ps. This shows local stability under this force field. It does not demonstrate folding, which takes microseconds.

## Checks (5/5 pass)

1. **Independent platform:** CPU forces agree with the Reference platform (max relative difference 1.3·10⁻⁶; identical potential energy).
2. **Minimisation:** −2516 → −2730 kJ/mol.
3. **Reproducibility:** two seeded Reference-platform runs are bit-identical. CPU production runs are statistically, not bit-for-bit, reproducible, because GB force summation across threads varies; this was tested and is stated in the record.
4. **Temperature:** mean kinetic temperature 299.1 ± 14.4 K, against an expected canonical spread of 15.4 K.
5. **Energy conservation:** a 2 ps constant-energy run at 0.5 fs gives σ(E_total)/σ(E_kin) = 0.003 and a drift of −0.02 kJ/mol/ps.

## Limitations

- Tens of picoseconds sample only local motion.
- Implicit solvent has no explicit water or ions.
- This is molecular dynamics, not docking or structure prediction.
- Viewing is ball-and-stick on a 2D canvas; loading the trajectory into the Mol* viewer is not yet wired.

## Tests

`tests/test_md_demo.py` covers:
- routing without NumPy, SciPy or OpenMM;
- the PDB checksum;
- a full 5 ps run through start, status, record and list, with all checks passing, frame and atom counts verified, and the structure staying folded.

These tests caught and fixed an un-reaped child process that left finished jobs looking "running".
