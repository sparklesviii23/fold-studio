# Virtual Cell roadmap

Start each session here, then `VIRTUAL_CELL_CAPABILITIES.md` (what works) and `VIRTUAL_CELL_DEFERRED_WORK.md` (what is missing).

## Done

1. Contexts and replay (K-562, Tahoe lines, parental Hep G2 with RRID check; HepG2/C3A kept separate).
2. Proteome annotations: identifiers, HPA/UniProt localization, Reactome pathways and enrichment, compartment-filtered 3D view.
3. Shared state: evidence-typed snapshots, branching, comparison, export/import; dataset and capability registries; coverage.
4. Hep G2 transcript isoforms (ENCODE, 2 replicates, GENCODE V29 structure).
5. Cell-cycle timeline on the Mechanistic Lab solver with documented phase proxies and snapshots.

## Next, in dependency order

| Step | Depends on | Independent? |
|---|---|---|
| A. Molecular Laboratory structure adapter (deferred item 4) and return-to-cell navigation | inspect App routing + structure store | yes |
| B. Hep G2 proteomics dataset (item 1) | dataset verification | yes |
| C. Cell Painting subset (item 2) | your approval for RxRx1 size, or a labelled non-HepG2 set | yes |
| D. Structure comparison in Virtual Cell (item 5) | A | no |
| E. Physics result adapters (item 6) | inspection of each lab's result format | yes |
| F. Calibrated Hep G2 cell-cycle (item 8) | phase-duration data | yes |
| G. Shared job manager routing for Virtual Cell workloads (item 7) | a workload that needs it | yes |

Independent validation still required for: every simulation output, any future predictive model, and any claim that
combining models improves accuracy (held-out benchmark against single-model baselines).
