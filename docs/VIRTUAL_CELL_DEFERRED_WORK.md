# Virtual Cell deferred work (Workstream B and blocked items)

Each item: what is missing · question it answers · why not now · what is needed · interface that will accept it ·
validation that would establish it · review needed.

1. **Hep G2 protein abundance.** Question: how much of each protein is present. Not now: no line-matched proteomics
   dataset verified in this session (candidates to check: CCLE/Gygi proteomics coverage of Hep G2, PaxDb Hep G2 sets,
   PRIDE deposits). Needs: accession, quantification method, units, licence. Interface: `DATASETS` row + `coverage()`
   modality "protein abundance" + protein panel block (category measured). Validation: replicate agreement; RNA–protein
   correlation reported, never used to impute. Review: none beyond data licence.
2. **Cell Painting / microscopy for Hep G2.** Question: observed morphology. Not now: RxRx1 (has HepG2, CC BY-NC-SA)
   ships as one ≈46 GB archive — needs your approval to download; JUMP cpg0016 is U2OS only (would be a different
   cell line and must be labelled so). Needs: image subset, channel metadata, segmentation (e.g. CellProfiler / Cellpose)
   and a feature reference. Interface: `image` provider, coverage modality "microscopy / morphology", existing
   MicrographStage stays illustrative. Validation: feature agreement with published CellProfiler outputs on the same images.
3. **Generative microscopy (MorphoDiff / CellFlux class).** Not now: weights, licence and supported conditions unverified;
   GPU cost. Interface: `vcell.microscopy.generative` (`prediction` category). Validation: held-out FID/feature-distance
   per training domain. Review: scientific; outputs must never be shown as observations.
4. **Molecular Laboratory results in Virtual Cell.** Question: which saved Boltz / AlphaFold / complex predictions exist
   for the selected protein. Not now: needs a read-only adapter over the Molecular Laboratory project store and a route
   into the existing viewer that returns to Virtual Cell; not inspected this session (dependency: `src/App.tsx` routing
   and the structure store in `scientific/worker.py`). Interface: `structure` provider keyed by UniProt accession.
   Validation: chain/residue mapping checks; confidence metrics shown per model, never merged.
5. **Structure comparison (RMSD, TM-score) inside Virtual Cell.** Depends on 4. Use existing comparison code
   (`comparison_run`) rather than new implementations.
6. **Cellular physics result adapters** (Brownian dynamics, diffusion, kinetics, RNA translation). Not now: those labs
   were not inspected; their numerical engines must not be altered. Interface: `simulation` provider with model identity,
   units, time domain, solver diagnostics (same shape as the cell-cycle block).
7. **Virtual Cell compute through the shared Modal job manager.** Not now: no Virtual Cell workload currently needs a
   GPU; the existing `gpu_tasks` lifecycle (cost estimate, approval, cancel, logs) is the integration point. No new job manager.
8. **Hep G2-calibrated cell-cycle model.** Needs Hep G2 cell-cycle phase durations (e.g. FUCCI or flow cytometry) and a
   fitting/evaluation protocol (Mechanistic Lab `fit` exists). Until then the model is labelled generic.
9. **Cellular age / senescence.** No validated predictor integrated; stays unavailable.
10. **Unified multimodal predictor research** (mixture of experts, shared latent spaces, calibrated ensembles). Research
    only; requires held-out benchmarks against single-model baselines before any claim.

Blocked by approval: RxRx1 download (item 2); any paid GPU run. Partial Nadig 2025 Hep G2 Perturb-seq download
(1.65 GB `.partial` in the library) was left untouched; resuming it needs your approval.
