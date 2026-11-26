# Living Cell physics — Demos 1 and 2

30 October 2026. Visualise › Cell Explorer › **Physics · simulated**. The first vertical slice of
the Living Cell laboratory: two Brownian-dynamics demos whose every drawn position and curve
comes from the engine below, validated against analytical or independent results on every run.

Evidence category **B · Physics simulation** (`src/lib/engineContract.ts`): numerical solutions of
stated equations for an idealised model. Demo 2's kon, koff, D, receptor count and geometry are
**hypothetical generic values** (flagged in the UI and in every exported record); no physiological
claim is made.

## Solver choice (engine registry)

| | |
|---|---|
| Evaluated | **Smoldyn** (Andrews & Bray 2004), LGPL-3.0-or-later. PyPI on 30 Oct 2026: 2.76 publishes a Linux x86-64 wheel and a `py3-none-any` wheel only; the last macOS wheels are `universal2` for CPython 3.10/3.11 (≤ 2.73). No wheel for the bundled CPython 3.12 on Apple silicon; not installed in any local runtime (`runtime/`, `runtimes/*`). |
| Chosen | In-house NumPy Brownian-dynamics engine, `scientific/cell_physics_bd.py` (NumPy 2.5.4, SciPy 1.18.1 already in the bundled runtime). |
| Why | Adding Smoldyn means building it from source into the runtime every build copies — a decision for the user, not this slice. The physics needed (free/bounded diffusion, specular reflection on spheres, Doi reversible binding) is small enough to implement and test directly. |
| Later | If Smoldyn is added to a runtime, run both demos through it and compare MSD and equilibrium occupancy within the same tolerances. |

The descriptor (`ENGINE` in `scientific/cell_physics.py`, returned by `cell_physics_catalog`) mirrors
`EngineDescriptor`: method, equations, assumptions, validated domain, limits, benchmarks, uncertainty.

## Engine

- **Diffusion.** Euler–Maruyama, x ← x + √(2DΔt)·ξ, ξ ~ N(0, I₃). Exact for free diffusion.
- **Walls.** Concentric spheres (inside / outside). A step that would cross a wall is reflected
  specularly at the hit point; repeated until the step lies in the domain (≤ 16 reflections; the
  count of fallback radial projections is reported and is 0 in every validated run).
- **Binding (Doi).** A free ligand inside an empty receptor's reaction volume binds with probability
  λΔt per step, λ = kon / V_rx; a complex dissociates with probability koffΔt, placing the ligand
  uniformly in the reaction volume (rejection sampling). Binding and unbinding are decided from the
  same state. With these linear probabilities the discrete chain satisfies detailed balance, so the
  equilibrium constant is exactly K = kon/koff for any Δt with λΔt, koffΔt ≤ 0.2 (enforced).
  V_rx = 4/3 πσ³ − πσ³(8R − 3σ)/(12R) is the part of the σ-ball outside the cell (tested against
  Monte Carlo). Receptors are fixed on a golden-angle spiral; overlapping reaction volumes are refused.
- **Units.** µm, s, µm²/s, µm³/s per molecule pair (1 µm³/s = 6.022×10⁸ M⁻¹s⁻¹).
- **Randomness.** NumPy PCG64, explicit seed; the record stores the seed and a SHA-256 of
  inputs + solver + outputs (bit-for-bit repeatable with the same seed, NumPy version and platform).
- **Admission.** Inputs outside the declared bounds are rejected, never clamped. Step limits:
  √(2DΔt) ≤ 0.05 R (sphere), ≤ σ and ≤ 5 % of the shell thickness (binding); ≤ 3×10⁸ particle-steps.

## Demo 1 · bounded diffusion in a virtual cell

2000 particles, D = 10 µm²/s, start at the centre, Δt = 1 ms, 3 s; once in free space and once in a
reflecting sphere R = 5 µm. Checks (|z| < 4 means two-sided p ≈ 6×10⁻⁵ per check):

| Check | Reference | Result (seed 20261030) |
|---|---|---|
| Free: fitted D (10 independent groups, origin-constrained LSQ) | D | 9.827 ± 0.21 µm²/s, z = −0.80 |
| Free: MSD(3 s) | 6Dt = 180 µm² | 176.7 ± 3.2 µm², z = −1.01 |
| Free: Gaussian displacements | N(0, 2Dt) per axis | KS p = 0.57 |
| Sphere: containment | r ≤ R | max r = 4.99961 µm; 186,328 reflections, 0 projections |
| Sphere: early MSD (√(6Dt) ≤ 0.4 R) | 6Dt | max \|z\| = 0.72 over 2 times |
| Sphere: plateau (t_end ≥ 10 τ₀, τ₀ = R²/(20.19 D)) | 3/5 R² = 15 µm² | 15.12 ± 0.15 µm², z = 0.82 |
| Sphere: radial uniformity | (r/R)³ ~ U(0, 1) | KS p = 0.65 |

If t_end < 10 τ₀ the plateau and uniformity checks are reported as **not applicable**, not passed.

## Demo 2 · reversible membrane receptor binding

Pericellular shell 5–7 µm (V = 913.2 µm³); 600 ligands, 200 receptors on the membrane; D = 20 µm²/s,
σ = 0.1 µm, kon = 1 µm³/s (6.0×10⁸ M⁻¹s⁻¹), koff = 1 s⁻¹ (K_D = 1.66 nM) — all hypothetical;
Δt = 0.2 ms, 8 s, 6 replicates.

References for the equilibrium (both computed on every run):

- **Exact ideal ensemble**: P(n) ∝ C(N_R, n)·N_L!/(N_L − n)!·(K/V)ⁿ.
- **Well-mixed ODE from the Mechanistic Biology Lab**: the `binding` component is composed into SBML
  (nM, litres, seconds; concentrations from copy numbers and V) and integrated with SciPy LSODA by
  `mechanistic_sim.simulate`; its C(t_end) must equal the analytic mass-action root to 10⁻³.

The BD occupancy is time-averaged after relaxation, from 6/k + (R_out − R_cell)²/D with
k = koff + (kon/V)(L_eq + R_eq), and the comparison is **not applicable** if less than 2/k remains.
Standard error: the larger of the between-replicate SE and the fluctuation-theory SE
√(Var(n)·2τ/(T·replicates)), τ = 1/k (few replicates make the empirical SE itself noisy).

| Check | Result (seed 20261031) |
|---|---|
| Bookkeeping (events, receptor/ligand records) | 3715 binding − 3272 unbinding = 443 complexes at the end (6 replicates) |
| Mechanistic ODE converged | 73.171 vs analytic 73.171 complexes |
| BD vs exact ensemble (3.7–8 s) | 75.23 ± 1.8 vs 73.20 complexes, z = 1.14 → occupancy 37.6 % ± 0.9 vs 36.6 % |
| BD vs well-mixed ODE | z = 1.15; exact − mean-field = 0.027 complexes |

**koff sweep** (0.5, 1, 2, 4, 8 s⁻¹; 3 replicates; t_end extended per point so each has an averaging
window; ≈ 1 min): BD occupancy 0.501 ± 0.011 / 0.368 ± 0.011 / 0.217 ± 0.009 / 0.139 ± 0.006 /
0.075 ± 0.003 vs ODE 0.521 / 0.366 / 0.233 / 0.136 / 0.074; z = −1.75, 0.17, −1.72, 0.62, 0.45 — all pass.

**Kinetics are not validated.** Association in BD is diffusion-influenced (Collins–Kimball factor
kD/(kD + kon) ≈ 0.93 with kD ≈ 2πDσ), so the transient differs from the well-mixed ODE (largest gap
≈ 9 % of equilibrium); it is shown for information. The equilibrium does not depend on this.

## Interface

`src/cell/physics/` — `CellPhysicsLab.tsx` (inputs with units and bounds, run/sweep, results),
`ParticleStage.tsx` (canvas, orthographic, drag to rotate), `geometry.ts` (+ tests), `physics.css`
(midnight glass). The stage draws **only computed frames** of a labelled sample ("Sampled 40 of 600
computed ligands"); bound ligands sit on their receptor, receptors turn amber when occupied; playback
steps through recorded frames and moves the playhead on the synchronised charts (MSD ± SE with
6Dt / 3/5 R², occupancy ± SE with ODE and exact equilibrium, sweep with error bars). Badges:
"Physics-simulated · B" and, for Demo 2, "Hypothetical parameters"; scale bar in µm. Each result can be
exported as a `fold.research-record` JSON; every run is also stored under
`<library>/cell_physics/runs/<id>.json` (`cell_physics_runs` lists them).

## Wiring

Actions `cell_physics_catalog | _diffusion | _binding | _sweep | _runs` (`scientific/cell_physics_actions.py`,
NumPy-free) are routed lazily by `scientific/worker.py`, allowlisted in `src-tauri/src/main.rs` and
bundled through `src-tauri/tauri.conf.json`. They run synchronously (Demo 1 < 1 s, Demo 2 ≈ 25 s,
sweep ≈ 1 min) and are not registered as heavy jobs.

## Tests

- `tests/test_cell_physics.py` (23): reflection containment and path length, shell walls, free domain,
  reaction volume vs Monte Carlo, unit conversion, exact/mean-field equilibria, rejected inputs and step
  limits, both demos' validations, record contract, seeded reproducibility, not-applicable cases, sweep,
  worker routing + Rust allowlist + bundled resources, stored records.
  ```bash
  PYTHONDONTWRITEBYTECODE=1 "<app>/Contents/Resources/runtime/bin/python3.12" -B -m unittest tests.test_cell_physics
  ```
- `src/cell/physics/geometry.test.ts` (4): projection, scale bar, interpolation without extrapolation, extent.

## Operational vs planned

| Item | Status |
|---|---|
| NumPy BD engine with spherical walls and Doi binding, seeded, unit-aware | Operational |
| Demo 1 (free + bounded diffusion) with 7 analytical checks | Operational |
| Demo 2 (membrane receptor binding) validated against exact ensemble and Mechanistic Lab ODE; koff sweep | Operational |
| Physics tab in Cell Explorer with sampled trajectories, synchronised charts, evidence badge, scale bar, record export | Operational |
| Records stored as files under the library; not yet rows in `records`/Research Projects | Planned |
| Validated binding kinetics (Δt/σ convergence study, comparison with Smoluchowski/Collins–Kimball rates) | Planned |
| Smoldyn cross-check | Planned (needs a runtime decision) |
| Receptor diffusion in the membrane, crowding, organelles as obstacles, internalisation, signalling coupling | Research goal |
| Long runs as cancellable background jobs with progress | Planned |
| Any comparison with measured (category A) data | Research goal |
