# Virtual Cell deferred work (Workstream B and blocked items)

Each item: what is missing · question it answers · why not now · what is needed · interface that will accept it ·
validation that would establish it · review needed.

0. **Done in stage 3 (kept for history):** items 1 (PaxDb Geiger 2012), 2 (cpg0036 subset), 4 (structure adapter) and 6
   (Cell Physics + RNA lab result adapters) are now implemented; remaining parts are listed under each item.

1. **Hep G2 protein abundance — remaining.** Replicate-level values (PRIDE/ProteomeXchange raw or MaxQuant tables for
   Geiger 2012), a second independent Hep G2 dataset, and an explanation for ALB's absence (likely contaminant filtering;
   unverified). Original text: Question: how much of each protein is present. Not now: no line-matched proteomics
   dataset verified in this session (candidates to check: CCLE/Gygi proteomics coverage of Hep G2, PaxDb Hep G2 sets,
   PRIDE deposits). Needs: accession, quantification method, units, licence. Interface: `DATASETS` row + `coverage()`
   modality "protein abundance" + protein panel block (category measured). Validation: replicate agreement; RNA–protein
   correlation reported, never used to impute. Review: none beyond data licence.
2. **Cell Painting — remaining.** Benchmark the SciPy segmentation and features against CellProfiler (or Cellpose) on the
   same 24 images; illumination correction from the dataset's `illum` files; µm calibration (needs objective and binning);
   compound-treated wells. Original text: Question: observed morphology. Not now: RxRx1 (has HepG2, CC BY-NC-SA)
   ships as one ≈46 GB archive — needs your approval to download; JUMP cpg0016 is U2OS only (would be a different
   cell line and must be labelled so). Needs: image subset, channel metadata, segmentation (e.g. CellProfiler / Cellpose)
   and a feature reference. Interface: `image` provider, coverage modality "microscopy / morphology", existing
   MicrographStage stays illustrative. Validation: feature agreement with published CellProfiler outputs on the same images.
3. **Generative microscopy — CellFlux installed (2 Nov 2026, user request, research use)** as an experimental plugin;
   in-domain BBBC021 benchmark done for seen compounds / held-out cells (see validation); remaining: the unseen-compound
   test on the 8 held-out BBBC021 compounds (needs the 2.3 GB `bbbc021_all` crops), a cpg0000 benchmark (crops not public), the true cpg0000
   channel order and normalisation (undocumented), and a Hep G2-trained model before any Hep G2 interpretation.
   Earlier assessment: CellFlux (ICML 2025) code is MIT and
   checkpoints are public (huggingface.co/suyc21/CellFlux: BBBC021, RxRx1, cpg0000), but the weights' licence is not
   stated, RxRx1 data are CC BY-NC-SA, inputs are IMPA-preprocessed 96 px crops with dataset-specific perturbation
   embeddings, and inference needs PyTorch (not in the app runtime). The integrated Hep G2 EU-OS images are out of its
   training domain. Needs: licence confirmation, approval for the checkpoint download / GPU, and a held-out evaluation in
   its own domain before any display. Interface: `vcell.microscopy.generative` (`prediction` category). Validation: held-out FID/feature-distance
   per training domain. Review: scientific; outputs must never be shown as observations.
4. **Molecular Laboratory results — remaining.** Records imported without provenance (AlphaFold-DB- and ColabFold-named
   files) show origin "unknown"; recording provenance at import would let them display their pLDDT. Original text: Question: which saved Boltz / AlphaFold / complex predictions exist
   for the selected protein. Not now: needs a read-only adapter over the Molecular Laboratory project store and a route
   into the existing viewer that returns to Virtual Cell; not inspected this session (dependency: `src/App.tsx` routing
   and the structure store in `scientific/worker.py`). Interface: `structure` provider keyed by UniProt accession.
   Validation: chain/residue mapping checks; confidence metrics shown per model, never merged.
5. **Structure comparison (RMSD, TM-score) inside Virtual Cell.** Depends on 4. Use existing comparison code
   (`comparison_run`) rather than new implementations.
6. **Physics adapters — remaining.** Blood transport, multiscale and Mechanistic Lab run records (different schemas) are
   not yet read. Original text: **Cellular physics result adapters** (Brownian dynamics, diffusion, kinetics, RNA translation). Not now: those labs
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
