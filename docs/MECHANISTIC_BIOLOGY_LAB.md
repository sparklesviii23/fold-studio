# Mechanistic Biology Lab

29 October 2026. Analyse › Mechanistic Biology Lab. A general-purpose engine that connects
molecular identity → curated knowledge → published or composed kinetic models → executed
numerical experiments → inspectable, exportable results. No target is hard-coded.

**Integrity rules.** Every number on screen comes from SciPy integrating a compiled SBML
model. Nothing is estimated from a sequence or structure; structure-prediction confidence
(pLDDT, ipTM, interface scores) is never converted into Kd, Ki, kon or koff. Numerical
diagnostics describe the calculation only — a converged, conservation-respecting solution
says nothing about whether the model describes the biology.

## Architecture

| Layer | File | What it does |
|---|---|---|
| SBML compiler | `scientific/mechanistic_sbml.py` | Reads SBML L2/L3 core (compartments, species, global + local parameters, function definitions, initial assignments, assignment and rate rules, reactions with MathML kinetic laws) and compiles one Python right-hand side. Species are integrated as amounts; species symbols mean concentrations unless `hasOnlySubstanceUnits`. Writes SBML back with changed values. |
| Numerical engine | `scientific/mechanistic_sim.py` | SciPy `solve_ivp` (LSODA, BDF, Radau, RK45, DOP853). Time courses with diagnostics; 1-D and 2-D scans; Latin-hypercube uncertainty with Spearman global sensitivity; normalised local sensitivity; steady state (relaxation + root polish within the conservation class + linear stability); least-squares fitting with approximate standard errors. |
| Mechanism library | `scientific/mechanistic_library.py` | Reusable components (binding, mass-action enzyme, Michaelis–Menten, competitive inhibition, synthesis, templated and repressed synthesis, degradation, reversible modification, compartment exchange). Each declares its rate law, required units, assumptions and source; `compose` enforces units and declared symbols and writes standard SBML L3. |
| Knowledge | `scientific/mechanistic_knowledge.py` | UniProt, Reactome and BioModels adapters with an on-disk cache (URL, retrieval time, stale-cache fallback); model discovery and ranking; knowledge graph with per-edge source and evidence. |
| Demonstrations | `scientific/mechanistic_demos.py` | Four validated examples (below). |
| Actions | `scientific/mechanistic.py` | `mech_*` RPC actions, per-run manifests under `<library>/mechanistic/runs`, COMBINE (.omex) export. |
| Interface | `src/components/mechanistic/` | Workspace, charts, reaction network and knowledge graph. |

Why SciPy and not libRoadRunner/COPASI today: SciPy 1.18 is already in the bundled, tested
scientific runtime; libSBML and libRoadRunner are not. Adding them changes the runtime every
build copies, which needs an explicit decision. Integrators sit behind one call
(`_integrate`), so a libRoadRunner backend can be added and cross-checked against SciPy.

## What the solver checks on every run

- Integrator status and evaluation counts.
- Conserved moieties from the left null space of the stoichiometry matrix, and their drift.
- Tolerance sensitivity: the run is repeated 100× tighter; a large change is flagged.
- Negative concentrations beyond round-off.
- Absolute tolerance is scaled to the model's own magnitudes (SBML amounts can be ~10⁻⁹ or ~10⁶).
  The independent-integrator check found a real error here during development: a fixed floor
  made tolerances 1000× too loose for the EGFR model.

## Validated demonstrations

| Demo | Model | Independent checks (all pass) | Parameter provenance |
|---|---|---|---|
| A · Enzyme kinetics | Composed: competitive inhibition rate law; full mass-action mechanism for comparison | Lambert-W closed form (Schnell & Mendoza 1997), max error 2·10⁻¹⁰ of S₀ with and without inhibitor; mass action vs quasi-steady state 6·10⁻⁵; conservation 10⁻¹⁵ | **Hypothetical**, chosen to exercise the mathematics |
| B · Receptor signalling | BIOMD0000000048, Kholodenko 1999 EGFR, unmodified | LSODA/BDF/Radau agree to 5·10⁻¹⁰; 6 conserved moieties hold to 10⁻¹⁴; transient PLCγ phosphorylation (peak at 30 s). Curators report the file reproduces the paper's figures | From the publication (curated BioModels file, CC0) |
| B′ · Feedback cascade | BIOMD0000000010, Kholodenko 2000 MAPK, unmodified | Integrators agree to 9·10⁻⁸; 3 moieties conserved; the published key result — sustained oscillations of MAPK-PP — persists (period ≈ 21.7 min) | From the publication |
| C · mRNA/protein turnover | Composed: two-stage expression, copy numbers, hours | Analytical solution to 10⁻¹⁰; steady state k_tl·k_tx/(d_m·d_p) exact; protein reaches half steady state at 60 h | Half-lives: medians from Schwanhäusser et al. 2011 (doi:10.1038/nature10098), 9 h mRNA, 46 h protein, NIH3T3; synthesis rates **hypothetical** |

Not yet done for B: point-by-point comparison with digitised figure data from the papers.

## Operational now

- Search UniProt (reviewed, human by default); Reactome pathways for an accession; BioModels search.
- Discovery: downloads candidate SBML, compiles it, reports executability and the exact unsupported
  features, missing parameters, and whether the model's own annotations cite the target accession.
  Ranked by annotation evidence, executability and curation. Tested live for EGFR: six curated
  models annotated with P00533, all executable (up to 504 species / 1,490 reactions).
- Load demos, BioModels models or your own SBML; inspect reactions, rate laws, ODEs, parameters
  (value, units, provenance, which reactions use them), units and cross-references.
- Run time courses, scans, 2-D scans, uncertainty and sensitivity; edit parameters for hypothetical
  variants; play the network back with node size and colour driven by computed concentrations.
- Export any run as a COMBINE archive: SBML with the run's values, SED-ML time course (KiSAO solver
  and tolerances), CSV results and a JSON record (request, model hash, source, software versions).
- "Open in Mechanistic Biology Lab" from any Protein Explorer entry.
- Tests: `tests/test_mechanistic.py` (13 tests: maths semantics, unsupported-feature refusal,
  overrides, SBML round trip, all validations, analytic sensitivities, seeded reproducibility,
  steady state, fit recovery, unit enforcement, archive contents).

## Partial or planned

- SBML events, delays, algebraic rules, fast reactions, variable stoichiometry, conversion factors
  and non-constant compartments are detected and refused rather than approximated.
- Units: library components enforce units by role; imported models' units are displayed but full
  dimensional analysis of arbitrary kinetic laws is not done.
- Global sensitivity is rank correlation on Latin-hypercube samples, not Sobol indices.
- No stochastic (Gillespie), rule-based (BioNetGen), constraint-based, spatial, PK/PD or PBPK solvers yet.
- SABIO-RK (endpoint redirected during integration), ChEMBL, IUPHAR/BPS, Rhea and BindingDB adapters
  are planned and listed in the sources catalogue; no data from them is shown.
- Fitting works on supplied data points; there is no data-import screen for it yet.
- SED-ML export covers uniform time courses; scans and uncertainty are exported as CSV + JSON only.
- The Cell Explorer is not yet driven by these models; the network view is the quantitative scene.
