# Virtual Cell capabilities

Updated 2 November 2026. Source of truth for statuses: `scientific/virtual_cell_registry.py` (`CAPABILITIES`), served by the
`vcell_registry` action. Status vocabulary: **Operational and tested · Integrated but not scientifically benchmarked ·
Partially implemented · Data available, integration incomplete · Model unavailable · Deferred · Blocked**.

| Capability | Module | Status | Evidence class | Notes / limits |
|---|---|---|---|---|
| Cell state, replay, branching | `virtual_cell.py` | Operational and tested | inherits | History replay is deterministic; SHA-256 per cell. |
| Snapshots, comparison, export/import | `virtual_cell_state.py` | Operational and tested | per value block | Six evidence categories, never merged; bundle checksum; cross-context import refused. |
| Dataset registry + integrity | `virtual_cell_registry.py` | Operational and tested | — | SHA-256 for files ≤ 200 MB (cached by size+mtime); larger files recorded by size/mtime only. |
| Per-context coverage | `virtual_cell_registry.coverage` | Operational and tested | — | available / not_downloaded / unmeasured / unsupported / pending / unvalidated. |
| Expression baseline (K-562, Tahoe lines, Hep G2) | `virtual_cell.py` | Operational and tested | measured | Hep G2 = DepMap 24Q4 bulk RNA (single profile). |
| Perturbation transitions | `virtual_cell.py`, `perturb_model.py` | Operational and tested (benchmarks in `VIRTUAL_CELL.md`) | measured / prediction | K-562 genetic; Tahoe drugs. None for parental Hep G2. |
| Knockout fitness | `virtual_cell.py` | Operational and tested | measured | DepMap Chronos. |
| Metabolism, signalling readouts | `virtual_cell_metabolism.py`, `virtual_cell_signalling.py` | Integrated but not scientifically benchmarked | simulation | Generic network / MCF10A parameters. |
| Protein identity, localization, PDB references | `virtual_cell_annotations.py` | Operational and tested | annotation | HPA + UniProt general annotation, not line-specific. Ensembl gene IDs come from HPA only (UniProt's field lists transcripts). |
| Reactome pathways, members, enrichment | `virtual_cell_annotations.py` | Operational and tested | annotation / statistic | Membership is not activity. |
| Hep G2 transcript isoforms | `virtual_cell_transcripts.py` | Operational and tested | measured / annotation | ENCODE ENCSR000CPE, 2 biological replicates, RSEM, GENCODE V29 primary assembly. Parental Hep G2 only. |
| Cell-cycle timeline | `virtual_cell_cycle.py` (Mechanistic Lab solver) | Integrated but not scientifically benchmarked | simulation | Gérard & Goldbeter 2009, generic mammalian, not calibrated to any line. Phase labels are a documented proxy. 3D cell not driven. |
| Protein abundance | — | Deferred | — | No verified line-matched proteomics dataset integrated. UI states "not available". |
| Cell Painting / microscopy | — | Deferred | — | See deferred work. Existing micrograph stage stays illustrative. |
| Generative microscopy | — | Model unavailable | — | MorphoDiff plugin: weights, licence, evaluation pending. |
| Saved Boltz / AlphaFold results in Virtual Cell | — | Partially implemented | — | PDB cross-references shown and linked to RCSB; Molecular Laboratory results not yet resolvable by protein. |
| Cellular physics result adapters | — | Deferred | — | Cell Physics / Blood / RNA-to-Protein labs untouched. |
| Virtual Cell jobs on Modal | `gpu_tasks.py` (existing) | Partially implemented | — | Tahoe atlas recipe only; no Virtual Cell provider routed through the shared job manager yet. |

## Interface entry points (Analyse › Virtual Cell)

Home: context selector (K-562, Hep G2 parental, 50 Tahoe lines incl. HepG2/C3A), data-and-models list with install / build
buttons. Studio: Simulations (knockout, protein & pathways, cell-cycle timeline, signature, design, history & saved states),
3D cell (illustrative) with HPA-driven channels and per-protein compartment filter, Data coverage panel, readouts.
