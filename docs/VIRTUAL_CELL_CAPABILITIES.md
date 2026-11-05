# Virtual Cell capabilities

Updated 2 November 2026 (stage 3). Source of truth for statuses: `scientific/virtual_cell_registry.py` (`CAPABILITIES`), served by the
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
| Cell-cycle timeline | `virtual_cell_cycle.py` (Mechanistic Lab solver) | Integrated but not scientifically benchmarked | simulation | Gérard & Goldbeter 2009, generic mammalian, not calibrated to any line. Phase labels are a documented proxy. 3D cell: one documented visualization rule (see below), no geometry. |
| Protein abundance (Hep G2) | `virtual_cell_proteomics.py` | Operational and tested | measured | PaxDb (CC BY 4.0) Geiger 2012 iBAQ (6,739 proteins) and spectral counting (3,546), ppm, one value per protein (no replicates published); "not reported" ≠ zero. ALB absent from both source files. Generic TSV/CSV importer. RNA–protein Spearman view. |
| Cell Painting (Hep G2) | `virtual_cell_microscopy.py`, `CellPainting.tsx` | Integrated but not scientifically benchmarked | measured image / computed features | cpg0036 EU-OS Bioactives (CC0), FMP plate B1001_R1, DMSO wells A23/B24, sites 1/5/9 (24 images, 4 channels). SciPy segmentation (local adaptive threshold; nearest-nucleus cells); features in pixels. Not yet compared with CellProfiler on the same images. |
| Generative microscopy (CellFlux) | `virtual_cell_cellflux.py`, `cellflux_runner.py`, `CellFluxPanel.tsx` | Partially implemented (runs; not valid for Hep G2) | prediction | Added at the user's request for research use. CellFlux commit 041c4c0, JUMP cpg0000 checkpoint (U2OS-trained, epoch 79), authors' sampling settings, local Apple MPS in `runtimes/gbcell` (≈ 18 s per cell). Hep G2 inputs are out of domain; channel slots and normalisation assumed (RNA slot ← ER); every run reports an identity check (first DMSO test: nuclei partly kept but distorted, nucleus Dice 0.53–0.75, DNA intensity ×1.9). cpg0000 not benchmarkable (crops not public); the method in its own BBBC021 domain: effect cosine 0.82 vs 0.58 baseline, closer to treated than untreated for 4/5 compounds; on the 8 compounds held out of training no better than a compound-agnostic baseline (cosine 0.61 vs 0.62, distance 1.82 vs 1.77). |
| Saved library structures | `virtual_cell_structures.py` | Operational and tested | per record | Read-only over library structure records; chains matched to UniProt by sequence; origin from record provenance only; declared confidence only; Cα RMSD / TM-score lower bound on shared UniProt positions; opens in the Molecular Viewer with return to the same cell and protein. |
| Saved lab results | `virtual_cell_results.py`, `SimulationResult.tsx` | Operational and tested | simulation | Cell Physics (Brownian diffusion, binding) and RNA lab (ViennaRNA ensembles, TASEP) research records; integrity re-checked with each lab's recipe; series / profiles / scalars with units; not mapped onto the cell. |
| Cell-cycle → 3D cell | `virtual_cell_cycle.VISUAL` | Integrated (visualization rule) | illustrative | DNA-layer brightness = 0.6 + 1.6 × normalised Cdk1/cyclin B; phase badge = phase proxy; synchronised with scrubbing, playback and snapshot restore; stored in snapshots. |
| Research report export | `vcell_report` | Operational and tested | — | Context, cell history, coverage, missing modalities, dataset manifest with checksums, capability statuses, snapshots. |
| Virtual Cell jobs on Modal | `gpu_tasks.py` (existing) | Partially implemented | — | All current Virtual Cell workloads run locally in ≤ 10 s (measured), so runtime selection is local; no remote Virtual Cell recipe and no paid run this session. Remote path = existing cost-gated `gpu_tasks` lifecycle. |

## Interface entry points (Analyse › Virtual Cell)

Home: context selector (K-562, Hep G2 parental, 50 Tahoe lines incl. HepG2/C3A), data-and-models list with install / build
buttons. Studio: Simulations (knockout, protein & pathways, cell-cycle timeline, signature, design, history & saved states),
3D cell (illustrative) with HPA-driven channels and per-protein compartment filter, Data coverage panel, readouts.

## Predictive biology Stage 2 · 5 November 2026

Observed-versus-predicted gene explorer now reuses Protein & pathways and the existing state engine. Exact context/gene/coordinate checks, typed provenance and explicit unsupported responses are operationally tested. Expanded Borzoi science remains pending; no new predictor is validated.
