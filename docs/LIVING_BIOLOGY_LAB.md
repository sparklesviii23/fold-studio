# Living Biology Laboratory — Priority 0 audit and Demo D

29 October 2026. Branch `project-omega/ultimate-completion`, starting HEAD `a3258dd`.

The Living Biology Laboratory is the long-term goal of letting a researcher design a molecule, place it in a modelled cell or bloodstream, run real solvers, compare scenarios and export reproducible records. **Almost all of that is still a research goal.** This document records what exists today (Priority 0), defines the engine contract every future solver must satisfy, and describes the first honest vertical slice: Demo D, a verified transport solver for a tracer in a capillary.

Integrity rules for everything under this heading:

- An illustration is never presented as a simulation. Every result shows its evidence category (A–E below).
- Docking scores, pLDDT, pTM/ipTM and similar confidence values are never converted into binding affinities, rates or concentrations.
- Every number shown or exported carries its unit. Every solver states its equations, method, assumptions, validated domain and limits.
- "Runs" is not "validated". An engine is validated only for the benchmark cases it has passed.

## 1. Evidence categories

| Category | Name | Meaning | Examples in fold today |
|---|---|---|---|
| **A** | Experimental | Measured on real samples; source data and protocol identity retained | Imported assay CSVs, PDB/mmCIF experimental structures, FASTQ/BAM reads, public GenBank references |
| **B** | Physics simulation | Numerical solution of stated physical equations for an idealised model; accurate only inside its model and validated domain | OpenMM implicit-solvent pilots, periodic Lennard-Jones, PySCF HF/PBE, **Demo D capillary transport** |
| **C** | AI prediction | Output of a trained statistical model; not a measurement | Boltz-2, AlphaFold2, BindCraft trajectories, ProteinMPNN/SolubleMPNN sequences, RNA guide scores |
| **D** | Parameterised hypothesis | A model whose parameters are chosen to represent a biological situation it has not been validated for | Demo D with capillary-like radius/velocity/diffusivity presets |
| **E** | Illustrative | Drawing or animation of known biology; shapes, counts and motion are schematic | Cell Explorer, micrograph "Illustrated" mode, Molecular Cinema approach motion |

The categories and their wording live in code at `src/lib/engineContract.ts` (`evidenceCategories`) so the interface and exported records cannot drift from this table. Cell Explorer already labels itself "Illustrative model · not simulated" (category E).

A result can move between categories only by evidence: a category-D scenario becomes something stronger only if it is compared with category-A data for that situation.

## 2. Priority 0 inventory — what runs today

Sources: `docs/FOLD_CURRENT_APPLICATION_AUDIT.md` (29 Oct, the authoritative evidence reconciliation), `docs/CURRENT_IMPLEMENTATION_CHECKPOINT.md`, the code paths named below, and a presence check of local runtimes. No model inference, download or paid compute was run for this audit.

### Works within a stated scope

| Engine | Code | Runtime | Category | Scope / evidence |
|---|---|---|---|---|
| OpenMM 8.6.1 CPU protein pilots | `scientific/dynamics.py`, `dynamics_runner.py` | `../runtimes/openmm-cpu`, bundled | B | Amber ff14SB/OBC2 implicit solvent, minimisation, short bounded trajectories, checkpoints, cancellation. `docs/DYNAMICS_PILOTS.md` |
| OpenMM periodic Lennard-Jones | `scientific/periodic_dynamics.py` | same | B | 2–64 identical particles; pair-formula and PBC invariance tests; mathematical model only |
| PySCF 2.14.0 CPU | `scientific/quantum_engine.py` | bundled | B | H₂ HF/STO-3G −1.11675930739643 Hartree reproduced; gradients, density, balanced reaction energies |
| Boltz-2 (PyTorch/MPS) | `scientific/worker.py` (`prediction_start`), `boltz_resources.py` | live root `engine/models` (`boltz2_conf.ckpt`, `boltz2_aff.ckpt` present) | C | Genuine local predictions with provenance JSON; confidence is pLDDT, not affinity |
| BindCraft2 / AF2 / ProteinMPNN / SolubleMPNN | `bindcraft_*.py`, `af2_native.py`, `mpnn*.py` | CPU JAX, scoped MetalJAX, cloud | C | Genuine local and A100 execution recorded; original filters preserved (one cloud trajectory rejected by its own filters) |
| RDKit compounds and ligands | `chemical_screen.py`, `ligand.py`, `molecular_graph.py` | bundled | B/descriptive | Descriptors, SMARTS, Morgan/Tanimoto; no docking/ADMET/activity |
| ChimeraX bridge | `chimerax_session.py`, `scene_bridge.py` | `/Applications/ChimeraX-1.12.app` | — (tooling) | Authenticated headless model/selection/camera/session sync |
| Genome / RNA / reads | `genome_*.py`, `genomic_io.py`, `sequence_*.py`, `editcraft.py` | Biopython, pysam/SAMtools, ViennaRNA | A inputs, B/C tools | Bounded formats, indexed FASTA/BGZF, alignment, base observations, ORFs, RNA cofold; scoped cloud EditCraft models |
| Assay statistics and 4PL fits | `assay_csv.py`, `assay_statistics.py`, `assay_fit.py` | NumPy/SciPy | A + descriptive | No affinity or confidence-interval claims |
| **Demo D capillary transport** | `src/lib/taylorAris.ts` | in-app TypeScript | B (benchmark) / D (capillary presets) | This document, §5 |

### Partial

- Molecular dynamics: no explicit solvent, ligands/ions, arbitrary force fields, long or converged sampling, free energies or Metal MD.
- Docking: no qualified engine (official Vina has no macOS ARM wheel; `reports/ultimate/docking-runtime-availability.json`).
- BoltzGen, ESMFold2, RFdiffusion, Rosetta: adapters or contracts exist; trained assets, licences or qualified runs are missing.
- Single-cell (Scanpy) and pathway enrichment: genuine bounded runs; broader biology unqualified.
- Research records: each engine writes its own provenance shape; there is no single cross-engine record schema yet (`ResearchRecord` in `engineContract.ts` is the proposed one; only Demo D uses it).

### Missing (the Living Biology Laboratory proper)

- Any cell-scale or tissue-scale solver: membrane transport, intracellular reaction–diffusion, compartment ODE/PK models, receptor occupancy, whole-cell models.
- Blood-flow models beyond a single idealised tube: networks, red-cell (two-phase/single-file) flow, pulsatile or non-Newtonian rheology, wall exchange.
- A coupling layer that passes typed quantities between engines (e.g. molecule → diffusivity estimate → transport solver) with unit and evidence checks.
- Scenario comparison and replay across engines; a project-level registry of research records.
- Validation against experimental transport data (category A) for any physiological claim.

### How jobs, provenance and records are stored

- **Native bridge.** `src-tauri/src/main.rs` exposes one Tauri command, `scientific(action, payload)`. Actions are allowlisted in `ACTIONS`; each call runs `scientific/worker.py` with the bundled Python (`runtime/bin/python3.12`) against the library root.
- **Frontend.** `src/lib/api.ts` `rpc(action, payload)` → Tauri `invoke('scientific', …)`; in Vite dev it posts to `/api/scientific` with a dev token. Viewer-mutating actions are serialised and followed by a visual-sync receipt.
- **Storage.** `worker.py` `Service` keeps `library.sqlite3` (WAL) in the library root with tables `projects`, `records` (JSON `data`), `jobs` (engine, state, JSON `data`), `settings`, `cache`, plus engine-specific tables. Files live under `assets/`, `jobs/<id>/`, `engine/`, `cache/`.
- **Jobs.** `job_new` / `job_update` / `job_metadata` with `BEGIN IMMEDIATE` transactions; `active()` enforces one heavy local job across engines (`boltz2`, `openmm`, `pyscf`, `periodic_lj`, …). Cancellation is shared.
- **Provenance.** Engine-specific: e.g. Boltz writes `provenance.json` with command, environment, input SHA-256 and model-resource fingerprints; genome tools keep original bytes and hashes; quantum/periodic results keep method, parameters, seed and code hash.

## 3. Engine interface design

Every Living Biology engine declares an `EngineDescriptor` and emits a `ResearchRecord` (`src/lib/engineContract.ts`). Python engines should mirror the same JSON shape so records are interchangeable.

| Field | Content | Rule |
|---|---|---|
| `id`, `name`, `version` | Stable engine identity | Version bumps whenever numerics change |
| `evidence` | A–E | Fixed per engine; a preset may lower it (B → D), never raise it |
| `inputs[]` | key, unit, description, bounds | Inputs are rejected outside bounds; no silent clamping |
| `spatialScale`, `timeScale` | min/max with units | The domain the method is meant for, not where it was validated |
| `numericalMethod`, `equations[]` | Discretisation, schemes, boundary conditions | Written so another person could re-implement it |
| `assumptions[]` | Physical/biological simplifications | Shown in the UI and exported |
| `validatedDomain[]` | Parameter ranges actually covered by passing benchmarks | Only what automated tests demonstrate |
| `limits[]` | Known invalid uses | Must include "no physiological accuracy" unless category-A comparison exists |
| `benchmarks[]` | name, reference, acceptance | Analytical or experimental reference with a numeric tolerance |
| `uncertainty` | What is and isn't quantified | Distinguish discretisation error, parameter uncertainty, model error |

`ResearchRecord` (schema `fold.research-record`, version 1) contains: engine identity and method; evidence category with a plain statement; creation time; every input with value, unit and description; full solver settings (grid, step, scheme, boundaries, initial condition); outputs with units; benchmark results; assumptions; limitations; reproducibility (`deterministic`, `seed` or `null` when no randomness is used, runtime, and a SHA-256 over inputs+solver+outputs).

Coupling between engines (future) passes `Quantity` values with units and the upstream record's hash and evidence category. The downstream record's category is the weakest of its inputs.

## 4. Demo D — tracer in a capillary

### Model

Passive dilute tracer in a straight rigid circular tube of radius R with steady Poiseuille flow u(r) = 2U(1 − r²/R²):

∂c/∂t + u(r) ∂c/∂z = D [ (1/r) ∂/∂r (r ∂c/∂r) + ∂²c/∂z² ]

with no flux at the wall, symmetry on the axis and closed axial ends. The initial condition is a cross-sectionally uniform Gaussian slug (σ₀), normalised to the injected amount.

### Numerical method (`src/lib/taylorAris.ts`)

- Axisymmetric finite volume on rings (Δr = R/N_r) × axial cells, in a frame moving with the mean velocity U. Reported positions are lab-frame (z = z′ + U t). The ring velocity is the exact area average of u(r) − U, so the discrete mean flux is exactly zero.
- Axial transport per ring: flux-limited Lax–Wendroff advection (van Leer limiter; Koren, MC and unlimited available as settings) plus explicit central axial diffusion.
- Radial diffusion: Crank–Nicolson (θ = ½, adjustable to backward Euler), solved with a pre-factorised Thomas algorithm.
- Strang splitting: radial ½Δt → axial Δt → radial ½Δt.
- Δt = min(Courant 0.4 · Δz/|w|max, 0.25 Δz²/D, 0.01 R²/D). Domain half-length = max(6√(σ₀² + 2KT), 4σ₀). Admission limit 3×10⁸ cell-steps.
- Deterministic: no random numbers, so there is no seed (`seed: null`).

### Benchmarks

- **Taylor–Aris dispersion.** Aris (1956) showed the long-time growth of the cross-sectional variance is exactly dσ²/dt = 2K with K = D(1 + Pe²/48), Pe = U R/D. The solver fits σ²(t) by least squares over t ≥ max(0.5 R²/D, 0.25 T) and reports |K_num − K_TA|/K_TA. Acceptance ≤ 1%. If T < R²/D the benchmark is reported as **not applicable** rather than passed.
- **Mass conservation.** Maximum relative drift ≤ 10⁻¹⁰.
- **Centroid speed.** Equals U (the ring-averaged moving-frame velocity has zero mean).
- **Domain adequacy.** Mass fraction in the outer 2% of the domain ≤ 10⁻⁶.

Measured on this machine (default resolutions):

| Preset | Pe | K/D | |ΔK|/K | Mass drift | Category |
|---|---|---|---|---|---|
| Benchmark (R 5 µm, U 4 mm/s, D 1000 µm²/s, 0.5 s) | 20 | 9.33 | 0.21% | 1.6×10⁻¹³ | B |
| Capillary-scale small solute (R 3 µm, U 0.5 mm/s, D 1000 µm²/s) | 1.5 | 1.05 | 0.02% | ~4×10⁻¹³ | D |
| Capillary-scale macromolecule (R 3 µm, U 0.5 mm/s, D 60 µm²/s) | 25 | 14.0 | 0.12% | ~1×10⁻¹³ | D |

Convergence: the residual falls with axial refinement (1.6% at 100 cells → 0.07% at 800) and is first-order in Δt with backward Euler (3.7% → 0.9% when Δt ÷ 4), which is why Crank–Nicolson is the default. Molecular diffusion alone (U = 0) is recovered within 1%.

Physical reading of the presets: in a capillary-sized vessel, Taylor dispersion barely changes small-solute spreading (K/D ≈ 1.05) but matters for macromolecules (K/D ≈ 14). That is a property of the idealised model. It has not been compared with in-vivo measurements.

### Tests

`src/lib/taylorAris.test.ts` (11 tests): Taylor–Aris at Pe 20 and 25, pure diffusion, axial convergence, Crank–Nicolson vs backward Euler, mass conservation and non-negativity, snapshot schedule, detector arrival at t ≈ z/U, "not applicable" before the radial transient decays, input rejection, deterministic record hash with units/evidence/limitations, and the analytical coefficient.

```bash
node node_modules/vitest/vitest.mjs run src/lib/taylorAris.test.ts
```

### Interface

Sidebar → **Analyse → Living Biology Lab** (`src/components/LivingBiologyLab.tsx`). Choose a preset or edit inputs (units shown on every field), run the solver, and inspect:

- tiles for K_num vs K_TA, benchmark residual with pass/fail/not-applicable, mass drift, centroid speed and boundary mass;
- cross-sectional mean concentration vs position at six times with the Taylor–Aris Gaussian overlay;
- σ²(t) against σ₀² + 2K_TA t;
- concentration vs time at a fixed detector (blank where the detector is outside the solved domain; no values are invented);
- the final c(r, z) field;
- solver settings, assumptions/limitations and a data table;
- **Export research record (JSON)**: inputs with units, solver settings, time series, profiles, benchmark, assumptions, limitations, evidence category and SHA-256.

The evidence badge shows **B · Physics simulation** for the benchmark preset and **D · Parameterised hypothesis** for the capillary-like presets.

### Limits of Demo D

Not valid for red-cell single-file flow, plasma skimming, the Fåhræus–Lindqvist effect, pulsatile or non-Newtonian blood, vessel branching, wall permeability, binding or tissue uptake. It makes no physiological or pharmacokinetic claim.

> **RNA-to-Protein Laboratory (Demos 3 and 4)** — thermodynamic RNA folding ensemble and stochastic translation, with validation, tool audit and operational-vs-planned status: see [RNA_TO_PROTEIN_LAB.md](RNA_TO_PROTEIN_LAB.md).

## 5. Operational vs research goal

| Item | Status |
|---|---|
| Evidence categories A–E defined in code and docs | Operational |
| Typed engine descriptor and research-record schema | Operational for Demo D only; other engines not yet migrated |
| Capillary advection–diffusion solver with analytical benchmark, tests, UI and record export | Operational (category B; D for capillary presets) |
| Exported record saved into the project library (SQLite) | Not done; export is a file via the native save dialog |
| Molecule → transport coupling (e.g. diffusivity from structure) | Research goal |
| Cell, tissue, bloodstream-network, PK/PD or whole-cell simulation | Research goal |
| Scenario comparison and replay across engines | Research goal |
| Physiological validation against measured data | Research goal |

## 6. Suggested next steps

1. Save Demo D records as project `records` (kind `research_record`) through a small rpc action, so they appear in Research Projects.
2. Migrate one Python engine (periodic LJ or quantum) to emit `ResearchRecord`, proving the contract crosses the TypeScript/Python boundary.
3. Add a second analytical benchmark to Demo D: plug-flow 1D advection–diffusion (exact Gaussian), and a wall-absorption case (Graetz-type eigenvalue).
4. Only after these, start a compartment/membrane model with its own analytical benchmark.

## 7. Demo 6 — Blood & Circulation Laboratory: plasma tracer transport

Added 30 October 2026. Sidebar → **Analyse → Living Biology Lab → Blood & Circulation · Demo 6**. Engine: `scientific/blood_transport.py` (Python, NumPy 2.5 / SciPy 1.18 in the bundled runtime), action names in `scientific/blood_transport_actions.py` (no numeric imports; the worker imports the engine lazily). Actions `blood_transport_describe`, `blood_transport_run`, `blood_transport_validate` are allowlisted in `src-tauri/src/main.rs` and bundled in `src-tauri/tauri.conf.json`. Client: `src/lib/bloodTransport.ts`; UI: `src/components/blood/BloodLab.tsx`, switched with Demo D through `src/components/livingLabSwitch.tsx` (append an entry there to add another laboratory). External engines are evaluated in `docs/BLOOD_LAB_ENGINES.md`.

**Why Python, not an extension of `taylorAris.ts`:** Demo D works in a frame moving with U and has closed ends, so it cannot represent an inlet, an outlet or wall loss. Demo 6 needs the laboratory frame, open boundaries with exact flux accounting, a Robin wall, Bessel-series and Stokes verification (SciPy `special`, `optimize`, `linalg`) and a seeded particle model; and it follows the engine pattern used by the other Python engines. Demo D is kept unchanged and is used as an independent cross-check.

### Model and assumptions
Dilute passive tracer in a straight rigid cylinder of radius R and length L, ∂c/∂t + u(r)∂c/∂z = D∇²c, with steady Poiseuille flow u = 2U(1 − r²/R²) (dp/dz = −8μU/R²). **Plasma only (hematocrit 0), Newtonian (μ = 1.2 mPa·s default), rigid wall**, no binding. Wall: impermeable or Robin −D∂c/∂r = Pc into a perfect sink. Inlet: step or Gaussian pulse carried by the advective flux u·c_in (Danckwerts), or closed for the validation slug; outlet: advective outflow.

### Numerics
Axisymmetric finite volume (rings × axial cells), lab frame; per-ring van Leer flux-limited Lax–Wendroff advection with explicit axial diffusion; Crank–Nicolson radial diffusion including the wall term (half-cell elimination of the wall concentration), pre-factorised LU; Strang splitting. Δt = min(0.4 Δz/u_max, 0.25 Δz²/D, σ_t/20 for pulses). Courant ≤ 0.9 and D Δt/Δz² ≤ 0.5 are enforced; Courant, axial and radial diffusion numbers, cell Péclet, Pe = UR/D, UL/D and Bi = PR/D are reported, with warnings when cell Pe > 2, when T < R²/D, or when radial resolution is thin. Every inlet, outlet and wall flux is accumulated exactly as applied, so M(t) − M₀ − in + out + wall closes to round-off. The velocity field is verified by a separate finite-volume Stokes solve on the same rings. Display frames are quantised to 16-bit levels of the run peak; benchmarks use full precision.

### Validation (automated; `blood_transport_validate`, also a button in the UI)

| Check | Metric | Measured | Tolerance |
|---|---|---|---|
| Mass conservation, closed tube, impermeable wall | max \|M(t) − M₀\|/M₀ | 5.4×10⁻¹⁴ | ≤ 10⁻¹² |
| Boundary budget, inlet pulse + permeable wall + open outlet | max relative budget residual | 1.3×10⁻¹³ | ≤ 10⁻¹² |
| Taylor–Aris, Pe = 20 (R 5 µm, U 4 mm/s, D 1000 µm²/s, 24 × 500) | \|K − D(1+Pe²/48)\|/K_TA | 0.042 % (9329.4 vs 9333.3 µm²/s) | ≤ 1 % |
| Cross-check vs in-app Demo D solver (same case) | K difference; mass-normalised profile L1 | 0.115 %; 0.20 % | ≤ 1 %; ≤ 2 % |
| Pure diffusion (U = 0) | max \|c̄ − Gaussian\| / peak | 2.5×10⁻⁵ | ≤ 5×10⁻³ |
| Permeable wall, Bi = 1, Dt/R² = 1 | retained mass vs Bessel series (λJ₁(λ) = Bi J₀(λ)) | 0.203379 vs 0.203347 (1.6×10⁻⁴) | ≤ 5×10⁻³ |
| Velocity: FV Stokes vs Poiseuille | max error / u_max at 24 rings | 1.3×10⁻³ (12 → 24 → 48 rings: 5.2e-3 → 1.3e-3 → 3.3e-4, order 2.00); flow rate 1.6×10⁻¹⁶ | ≤ 2×10⁻³, order ≥ 1.8 |
| Grid convergence, ratio 2, three grids | observed order (pure diffusion RMS error) | 2.00 (6.2e-4 → 1.6e-4 → 3.9e-5); Taylor–Aris residual 1.07 % → 0.11 % → 0.05 % | ≥ 1.5, monotone |

The whole suite runs in about 1.1 s. The arteriole-pulse preset reports cell Pe ≈ 333; refinement from 150 to 1200 axial cells changes the outlet peak by < 0.06 % and the mean arrival time by < 0.05 %, so that result is grid-independent despite the warning.

### Particle view (optional, labelled "Particle view · stochastic")
Seeded Lagrangian particles: z += u(r)Δt + √(2DΔt)ξ, x, y += √(2DΔt)ξ, specular reflection at the wall, Robin absorption with probability P√(πΔt/D) per wall hit (Erban & Chapman 2007), inlet particles released in proportion to the inlet flux history and radius (flux-weighted). Statistics (mass in vessel, centroid, variance) are compared with the continuum with Monte-Carlo standard errors; agreement is accepted within 3 standard errors. Measured with 4000 particles, seed 7: Taylor–Aris 0.61σ, arteriole pulse 1.21σ, permeable step 0.84σ (all pass).

### Interface
Vessel longitudinal section (computed c(r, z), mirrored about the axis, radial scale exaggeration stated) with inlet velocity profile, inlet/outlet fluxes, wall-loss arrows scaled by the computed wall concentration and optional particles; time scrubber with play; probe-able cross-section; velocity profile (analytic vs FV Stokes); boundary-flux, outlet breakthrough, variance and axial-profile charts (`MechCharts.TimeChart`); tiles for budget, boundary totals, stability and Taylor–Aris; live validation table; live Demo D cross-check; solver/stability details, assumptions and limits; JSON research record with SHA-256. Badges: **Physics-simulated** always; **Parameterised scenario · D** for plasma-like presets or edited inputs, with the statement that this is a modelled vessel, not validated human circulation, and that no physiological, clinical or dosing claim is made.

### Tests
`tests/test_blood_transport.py` (18 tests; run with the bundled Python, `-B`, `PYTHONDONTWRITEBYTECODE=1`) and `src/lib/bloodTransport.test.ts` (3 tests; compares Demo D in TypeScript against `fixtures/blood/python-taylor-aris-reference.json`, regenerated by `python3 scientific/blood_transport.py --reference fixtures/blood/python-taylor-aris-reference.json`).

### Limits
Not valid for whole blood (hematocrit > 0), single-file red-cell flow, non-Newtonian or pulsatile flow, networks, compliant walls, tissue compartments or convective filtration. Wall permeability is a model parameter, not a measured endothelial property.

## 8. Living Cell physics — Demo 1 (bounded diffusion) and Demo 2 (membrane receptor binding)

Visualise › Cell Explorer › **Physics · simulated**; full description in `docs/LIVING_CELL_PHYSICS.md`. Category **B** (Physics-simulated); Demo 2 parameters are hypothetical generic values and are badged as such.

- **Solver.** Smoldyn was evaluated (LGPL-3.0-or-later; no wheel for the bundled CPython 3.12 on Apple silicon, not installed in any runtime), so a NumPy Brownian-dynamics engine was written: `scientific/cell_physics_bd.py` (Euler–Maruyama, specular reflection at spherical walls, Doi binding in a detailed-balance-exact discrete form, PCG64 seeds). Recorded in the engine descriptor returned by `cell_physics_catalog`.
- **Demo 1** (D = 10 µm²/s, R = 5 µm, 2000 particles, 3 s): free D fit 9.827 ± 0.21 µm²/s (z −0.80); MSD(3 s) 176.7 ± 3.2 vs 6Dt = 180 µm² (z −1.01); sphere plateau 15.12 ± 0.15 vs 3/5 R² = 15 µm² (z 0.82); KS tests for Gaussian displacements (p 0.57) and uniform radial density (p 0.65); 0 particles escaped.
- **Demo 2** (shell 5–7 µm, 600 ligands, 200 receptors, kon 1 µm³/s ≈ 6×10⁸ M⁻¹s⁻¹, koff 1 s⁻¹): equilibrium 75.2 ± 1.8 complexes vs exact ensemble 73.20 (z 1.14) and the Mechanistic Biology Lab ODE (SBML → SciPy LSODA) 73.17 (z 1.15); koff sweep 0.5–8 s⁻¹ agrees at every point (|z| ≤ 1.75). Binding kinetics are shown but not validated.
- **Tests.** `tests/test_cell_physics.py` (23) and `src/cell/physics/geometry.test.ts` (4).
- **Planned.** Records into the project `records` table; Δt/σ convergence study for kinetics; Smoldyn cross-check; receptor mobility, crowding and organelle obstacles; background jobs with progress.

## References

- G. I. Taylor (1953). Dispersion of soluble matter in solvent flowing slowly through a tube. *Proc. R. Soc. Lond. A* 219, 186–203.
- R. Aris (1956). On the dispersion of a solute in a fluid flowing through a tube. *Proc. R. Soc. Lond. A* 235, 67–77.
- R. Erban and S. J. Chapman (2007). Reactive boundary conditions for stochastic simulations of reaction–diffusion processes. *Phys. Biol.* 4, 16–28.
