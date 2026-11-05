# Virtual Cell integration contracts

How modules share one cell. Read with `VIRTUAL_CELL_CAPABILITIES.md`.

## Data flow

```
library datasets ──► virtual_cell_registry (identity, release, licence, integrity, coverage)
        │
context reference (K562 Reference | LineContext | DepMapContext)  ◄── cell record (context + operation history)
        │ replay()  (deterministic)
        ▼
state ──► readouts (expression, fitness, metabolism, signalling)
      ──► protein / pathway / transcripts (annotations index, ENCODE index)
      ──► simulations (cell cycle via Mechanistic Lab solver)
      ──► virtual_cell_state.create() ──► snapshot (evidence-typed blocks + simulation block + dataset manifest)
                                          ──► compare / export bundle / import (identity + checksum checked)
```

Worker routing: all actions are listed in `scientific/virtual_cell_actions.py` (NumPy-free); `virtual_cell.dispatch`
handles them, `state_dispatch` handles `STATE_ACTIONS`. The frontend calls them with `rpc()`; nothing large is bundled.

## Shared identifiers

| Kind | Key | Resolver |
|---|---|---|
| Cell context | Cellosaurus RRID (`CVCL_0027` Hep G2, `CVCL_1098` HepG2/C3A, `CVCL_0004` K-562) | `virtual_cell.context_reference`; Hep G2 identity checked against DepMap `Model.csv` RRID |
| Gene / protein | HGNC symbol; UniProt accession; Ensembl gene | `virtual_cell_annotations.resolve` (ambiguity explicit) |
| Transcript | GENCODE V29 `ENST….v`; UniProt isoform | `virtual_cell_transcripts.gene` |
| Pathway | Reactome stable ID `R-HSA-…` | annotations index |
| Model | BioModels ID + SBML SHA-256 (CRLF-normalised) | `virtual_cell_cycle.model` |
| Cell / snapshot | 32-hex UUIDs, `<cellId>/<snapshotId>` | `virtual_cell.load`, `virtual_cell_state.load` |

## Snapshot schema (`fold.virtualcell.state/1`)

`{id, cellId, label, kind (baseline|perturbed|simulation|imported), created, seq, parent, context{name, cellosaurus, depmap…},
cell{name, history, sha256, reference, steps}, blocks{name: block}, simulation|null, datasets[manifest rows], sha256}`.

Block: `{category, categoryLabel, source, version, unit, context, uncertainty, note, values}` with category one of
`measured, annotation, statistic, prediction, simulation, illustrative`. Blocks are compared only with the same
category and unit. Simulation block: `{model, solver, parameters, hours, runKey, diagnostics, time, timeUnit, phase,
regime, phaseRule, variables, category: 'simulation', calibration}`.

## Provider contract

Every provider (cell_state, dataset, model, simulation, structure, image, compute, evidence) registers a row in
`CAPABILITIES`: `id, provider, module, inputs, outputs, context, runtime, evidence, validation, ui, dependencies`.
A provider that cannot run returns `virtual_cell_registry.unsupported(cap_id, reason, needs)` — `{supported: false,
values: null}` — and the UI shows the reason. To add a provider: implement the action in a module, add it to
`virtual_cell_actions.ACTIONS`, add the capability row (and a `DATASETS` row for new data, a `RESOURCES` row for its
licence), extend `coverage()` if it adds a modality, package the module in `src-tauri/tauri.conf.json`, add tests.
The renderer and state system need no change.

## Stage 3 contracts

- Structure provider `vcell_structures {accession}` → `{structures: [{id, kind ∈ experimental|predicted|designed|illustrative|unknown,
  origin, chains: [{chain, uniprotStart, uniprotEnd, identity}], confidence: {metric, meanByChain, ptm, iptm} | null}], skipped}`;
  `vcell_structure_compare {accession, a, b}` → Cα RMSD, TM-score (RMSD-superposition lower bound), per-position deviations.
  The App opens a record with `VirtualCellLab.onOpenStructure(id, label)`; the cell and protein are restored from
  sessionStorage `fold-vcell-return` on return.
- Simulation results `vcell_results_list`, `vcell_result_get {source, result}` → `fold.virtualcell.simulation-result/1`
  (model, evidence, inputs with units, solver, time, series, profiles, scalars, convergence, assumptions, limitations, integrity).
  New sources: add an entry to `virtual_cell_results.SOURCES` with the writing lab's hash recipe.
- Proteomics `vcell_rna_protein`; abundance appears in `vcell_protein.abundance` and pathway members. New datasets:
  `virtual_cell_proteomics.import_table(root, path, spec)` (unit, method, RRID, citation, licence required).
- Microscopy `vcell_microscopy_list`, `vcell_microscopy_view {key}` → display PNGs (percentile-scaled copies), outlines,
  per-field feature summary and per-cell rows; raw pixels and masks stay in the library.
- Report `vcell_report` → `fold.virtualcell.report/1` with SHA-256.

## Rendering mappings (documented, not inferred)

- Channel brightness = 2^(3 × mean change in the compartment's genes), clipped 0.2–3 (display only).
- Compartment gene sets: HPA Enhanced/Supported/Approved calls via `virtual_cell_annotations.LAYERS`; Human-GEM fallback.
- Protein selection hides layers the protein is not annotated to; nothing implies a position inside a compartment.
- Cell-cycle timeline open: nucleus/DNA-layer brightness = 0.6 + 1.6 × (Cdk1/cyclin B ÷ its run maximum); category
  illustrative; recorded in simulation snapshots as `visualization`. No geometry is driven (the model has none).

## Predictive biology Stage 2 · 5 November 2026

Stage 2 remains isolated on codex/predictive-cell-stage2, based on 6d0b3f7. Claude’s original branch remains at 2862128 with its pre-existing report changes untouched. No new Claude commit was found, but its development process remains active. Do not merge into that live checkout. Once Claude is idle, recheck HEAD/status, preserve its dirty files, review only predictive additions and use a fast-forward only if the original HEAD remains an ancestor; otherwise merge/rebase in a separate review worktree and resolve narrowly. Rerun focused tests and the source-resource check. Desktop packaging is a separate final approval step using only scripts/build-local-app.sh; the installed app and research library have not been replaced.


### Installed continuation

User approval for integration was subsequently received. The canonical app now contains the predictive branch's Virtual Cell workspace and controller, with an additive import of the completed study into the normal library. Actual native walkthrough and installed-resource checks passed. The active Claude checkout was not merged or modified. Future packaging must use this predictive implementation or a reviewed integration containing it, rather than replacing the app with the older canonical checkout. See the latest implementation checkpoint and PREDICTIVE_CELL_USER_GUIDE.md.
