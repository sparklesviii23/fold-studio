# Fold Studio — implementation and evidence audit

**Audit date:** 26 October 2026, Europe/Bucharest.
**Source reviewed:** `project-editcraft/native-cloud-laboratory`, commit `c02caf608074cc1ae2f2813b76f79a6a7642a82a`.
**Scope:** the existing Fold Studio application, Project Metal, molecular intelligence/research/cinema, cloud molecular engines, development worker and EditCraft. Historical directives remain in scope; a feature appearing in a menu or registry is not counted as a completed integration.

## 1. Overall finding

Fold Studio is a working macOS molecular research application with a shared library, interactive molecular viewer, genuine local prediction/design calculations, molecular measurements, research records, movie export, cloud campaign controls and several executing genome/RNA/single-cell methods.

It is **not yet the complete platform described across all the master directives**. The largest unfinished areas are full model/strategy qualification, accepted full-Fab generation, complete adaptive BindCraft–BoltzGen coordination, several additional scientific engines, broad EditCraft coverage and fresh-machine distribution acceptance.

The macOS application can run its interface and supported local CPU/Metal/MPS workflows without NVIDIA hardware. That does **not** mean every requested scientific engine has been fully ported to an NVIDIA-free Mac. Some complete workflows still depend on separately qualified cloud CUDA execution, additional checkpoints, licensed software or unimplemented scientific handoffs.

### Audit method and limits

This audit reviewed source, current package contents, implementation reports, genuine saved calculations and explicit remaining-work records. It did not launch a molecular campaign, rerun the regression suites, contact a paid provider, retrieve invoices or perform a new biological benchmark. Test totals below refer to the latest recorded completed runs.

Evidence levels used here:

- **Working, scoped:** actual execution or native workflow evidence exists for the stated scope.
- **Implemented/tested:** source and software-contract or numerical tests exist; the full scientific workflow is not necessarily qualified.
- **Partial:** useful integration exists, with material missing functions or qualification.
- **Missing/blocked:** source, assets, licensed runtime or required execution evidence is absent.

Numerical agreement, model inference, upstream filter acceptance, independent biological validation and experimental binding are separate claims throughout this audit.

## 2. Current installation and verified inventory

| Item | Audit finding |
|---|---|
| Source repository | `/Users/vii/Documents/FoldStudio-MetalPort/fold-studio` |
| Canonical current app | `/Users/vii/Documents/FoldStudio-MetalPort/current/FOLD STUDIO Metal Dev.app` |
| Packaging policy | One current installed app, replaced through the guarded build script; no automatic versioned backup apps or ZIP releases |
| Live research root | `/Users/vii/Documents/FoldStudio-MetalPort/validation/bindcraft-fab-amme-native` |
| Recorded backend regression run | **742 passed**, zero failed |
| Recorded interface regression run | **143 passed** across 34 files, zero failed |
| TypeScript/build/signatures | Passed in the latest package receipts |
| Additional package review performed for this audit | **121 Python/JSON scientific source files checked; all 121 match the current app; no top-level scientific Python file missing** |
| Literal scientific action inventory | 243 distinct action names across 29 source modules; this is an implementation inventory, not 243 individually accepted workflows |
| EditCraft executable operations | **21** registered operations, listed in section 12 |
| ChimeraX historical command inventory | 591 entries: **22 scoped tested**, 569 not command-specifically validated in that CSV |
| Existing molecular research integrity | Latest preservation receipt retains all 16 baseline structure records, identical metadata digest and matching original coordinate-asset hashes |
| Notarization | Deferred for local use; local signing is available |
| Full-platform completion | **False** |

The new machine-readable companion, `reports/fold-studio-implementation-audit.json`, records source/package hashes, operation contracts, literal action sets and the exact audit baseline. It does not contain credentials or claim live provider availability.

## 3. Architecture and source origins

| Layer | Actual implementation |
|---|---|
| macOS desktop shell | Tauri 2 with Rust IPC, native dialogs, process supervision and packaged resources |
| Interface | React 19, TypeScript 5.8, Vite 6, CSS/glass components and Lucide icons |
| Molecular rendering | Existing **Mol\* 5.13.1 WebGL** viewer inside the macOS webview; this is not a separate SceneKit/Metal renderer |
| Scientific application service | Python, allowlisted JSON IPC, SQLite/WAL research storage, background workers and immutable/checksummed assets |
| ChimeraX bridge | Authenticated headless UCSF ChimeraX 1.12 integration, authoritative atoms/models/commands/session state; extensive command parity and fully self-contained redistribution are not certified |
| Local molecular computation | Pinned BindCraft2/AlphaFold2/ProteinMPNN paths, CPU JAX and a scoped MetalJAX execution path; PyTorch/MPS Boltz-2; RDKit and OpenMM CPU workflows |
| Cloud computation | Portable RAPID worker, SSH transport and independent Modal molecular/EditCraft services, persistent volumes/journals and model-specific workers |
| Local optional AI | Approved Ollama/Aider integration with a pinned Qwen2.5-Coder 3B model; bounded development/retrieval tasks, not validated autonomous biological reasoning |
| Genome/RNA/cellular methods | Ensembl/Biopython, ViennaRNA, Rule Set 3, BE-DICT, PRIDICT2, Cas-OFFinder, Scanpy/AnnData and original explicit-background enrichment code |

Third-party projects remain distinct from Fold Studio's orchestration/interface code. Relevant source pins, original notices, asset checksums and runtime manifests are retained under `vendor/`, the scientific manifests and the remote worker. Source availability or project permission does not by itself resolve every dependency's redistribution terms; licensed Rosetta remains gated.

## 4. Application, library and shared molecular state

### Implemented

- Existing PlayStation/Apple-inspired glass interface and molecular viewer are retained, with research, computation and specialized scientific workspaces. Home/discovery, Sequence Workbench, Settings, Local Compute and the existing Molecular Arcade navigation remain present; gameplay is not counted as scientific engine validation.
- Project-scoped research libraries, structure/sequence records, job history, settings and versioned analyses use the same persistent application service.
- PDB/mmCIF structure import, public structure/sequence retrieval, checksummed coordinate assets and ordinary viewer opening are connected.
- Library record editing/renaming and removal/restoration actions exist; originals are not silently overwritten by analyses.
- Structure, chain, residue and atom identities link the viewer, command system, sequence tools and analysis results. Derived records preserve source/parent correspondence and provenance.
- Existing project/coordinate/result exports are connected. Project archive **re-import is not generally complete**; an archive export is not proof of a complete round-trip project importer.
- Compute jobs retain status, logs, seeds/settings, source hashes, errors, cancellation and supported recovery boundaries.

### Evidence boundary

The current package passes source/import checks, and real saved research has been reopened and checked natively. Fresh-machine installation, every migration, universal undo/redo and one common recovery protocol across every scientific engine remain unfinished.

**Sources:** `scientific/worker.py`, `fold_engine.py`, `evolution.py`, `scene_bridge.py`, `observatory.py`; `docs/STORAGE_POLICY.md`; `reports/editcraft/preservation-current.json`.

## 5. Viewer, ChimeraX and molecular observatories

### Working or implemented capabilities

- Protein cartoon/ribbon, atom/bond and surface views; per-chain colour assignment and visibility; atom/residue selection, camera interaction and measurement overlays.
- Source-matched interaction selection, aligned overlays and side-by-side comparisons reuse the existing viewer.
- ChimeraX command execution/history, model/selection/camera synchronization and actual session saving/restoration are connected through the scientific bridge.
- Bounding-sphere-aware clipping protection and full-axis orbit regressions address geometry loss during rotation. Recorded cinema checks include 96 actual larger-complex XYZ views; this does not certify every hardware/representation combination.
- DNA/RNA/protein polymer identity, modified nucleotide identity and author/label numbering are preserved rather than forced into protein-only assumptions.
- Saved RNA diagrams, stems and base-pair/probability selections can select corresponding observed 3D residues when an exact mapping exists.
- Native DNA and tRNA inspection, representation/visibility checks and complete ribosome loading have genuine evidence.
- The 4V9D ribosome assembly rendered **146,921 atoms**. Recorded coordinate comparison preserves the source identities with maximum difference approximately **3.26e−14 Å**.

### Still incomplete

The detailed native camera/pan/multi-atom-measurement acceptance matrix is not fully closed. The historical ChimeraX CSV validates only 22 scoped commands, not the entire 591-command inventory or all ChimeraX features. Full source-compatible embedding/distribution and broad fresh-machine acceptance remain separate work.

A rendered ribosome is **not** an atomistically simulated translation system. No implemented result establishes complete mRNA passage, ribosome chemistry, whole-cell behavior or a tumor-microenvironment simulation.

**Sources:** `MolecularViewer.tsx`, `MolecularBiologyPanel.tsx`, `molecular_observatory.py`, `polymer_identity.py`; `docs/CHIMERAX_COMMAND_COMPATIBILITY.csv`; nucleic/native coordinate receipts under `reports/editcraft/`.

## 6. Local prediction, BindCraft Architect and the macOS port

### Local Boltz-2

The existing local Boltz-2 PyTorch/MPS route has setup/resource checks, model/asset integrity handling, prediction jobs, retained outputs and confidence import. It is a genuine local prediction integration. Broad input-chemistry coverage, every target size and universally reliable memory fit are not established.

### BindCraft2 / AlphaFold2

- Pinned upstream BindCraft2 source is preserved at revision `c0ee638d11bc010817c2c97ee58ed5c323e664e2` with source and model provenance.
- Native campaign preparation, original presets, explicit chains/sites/lengths/seeds, advanced settings, job control and ranked-result import exist.
- Original filtering/ranking semantics are retained; rejected outputs are not relabelled accepted.
- Genuine AF2 monomer/multimer forward, loss, gradient and optimizer comparisons were executed in scoped CPU/Metal paths.
- A narrow float32 Metal attention implementation has reference output/gradient comparisons. A compatible MetalJAX path subsequently demonstrated scoped full-model execution; the original Apple JAX plugin incompatibility is not silently described as solved by that separate path.
- A genuine **175-residue original-ensemble local campaign** completed with ProteinMPNN and held-out AF2 checks, retaining one upstream-accepted computational design. This is not experimental binding evidence or universal port parity.
- Larger Metal gradients remain memory-limited. The recorded launch policy refuses unsafe sizes instead of raising limits or silently changing the target/backend.

### Architect controls and additional workflows

The five-section Architect provides Overview, Target & Design, Scientific Settings, Compute & Run and Campaign Library. Project drafts persist. Amino-acid exclusions and residue selections have explicit clear/default behavior. Failed/cancelled jobs show their last real progress.

Scoped implementations include fixed/protected residues, chain constraints, tied-chain cases, original property presets, sequence targets/crops, multi-target/negative-target preparation, conformational-state workflows, scoring, campaign repeat/recovery, summary/rank/filter utilities and lossless trajectory archiving. Their individual acceptance levels vary: some have genuine rejected trajectories, others preparation/transport tests. No blanket claim covers every modality, option, CLI flag or arbitrary multistate graph.

**Sources:** `docs/BINDCRAFT_ARCHITECT_REPORT.md`, `PROJECT_METAL_MASTER_PROGRESS.md`, `PROJECT_METAL_EXECUTION_STATE.json`, `BINDCRAFT_FEATURE_PARITY.json`; AF2/Metal/MPNN/campaign reports.

## 7. ProteinMPNN, SolubleMPNN and full Fab

### Sequence redesign

Genuine ProteinMPNN encoder/decoder/checkpoint inference runs locally, with selected chains, fixed context, seed, score/sequence persistence and coordinate preservation. Tested CPU examples match direct pinned-upstream sequence and score outputs exactly. This is integration parity, not independent validation of the trained model's biological accuracy.

SolubleMPNN is a separately identified genuine redesign branch with an approved verified checkpoint and actual local CPU inference. Later cloud evidence records separate ProteinMPNN/SolubleMPNN outputs. A solubility-oriented model's sequence is **not a measured solubility result**. New sequences do not inherit old side-chain coordinates as if they had been refolded.

### Fab memory engineering: actual result

- Complete heavy/light chains and observed target were retained: **231 + 213 + 115 residues**.
- Fine-grained recomputation, a memory-oriented CPU scheduler, a **14 GiB task ceiling** and bounded **10 GiB SSD tape** were implemented.
- A real full forward/backward calculation completed in approximately **1,139.6 seconds**, with observed peak footprint approximately **10.33 GiB**.
- The original native campaign completed **five real optimizer updates**; the sixth was interrupted by the user's cancellation. Its saved observed peak was approximately **10.79 GiB**.
- Scoped matched-input output/loss/gradient/local-update comparisons pass the stated tolerances. Independent continuous trajectories drift beyond them; the limitation is preserved, not waived.

### Fab conclusion

**Full Fab generation is not complete.** No complete original production trajectory, full final redesign/held-out evaluation sequence or accepted Fab design has been established. SSD tape is not an exact optimizer checkpoint. Component mutation/MPNN/model-2 refold evidence does not establish the entire campaign; a full-size cache-fix refold attempt was interrupted before verification. The original cancelled campaign has not been automatically restarted.

**Sources:** `docs/FAB_AMME_VALIDATION.md`; `reports/amme-integration-status.json`, matched-update/gradient/native progress and Fab component receipts.

## 8. Molecular Intelligence and research analysis

### Implemented and supported by scoped calculations

- Structure completeness, atom/residue/chain inspection, numbering gaps and explicit target/candidate/control assignments.
- Cross-partner atom contacts and unique residue contacts; chemistry-aware native clashes or explicitly identified offline criteria.
- Explicit-hydrogen geometric H-bond checks where supported, tentative missing-hydrogen contacts, salt-bridge/nonpolar/aromatic/cation–π screens and interaction networks with stated scope.
- SASA and interface-area calculations, retaining probe/radii/resolution and source provenance.
- Confidence import and mapping for actual pLDDT/PAE arrays; missing values remain unavailable and crystallographic B factors are not automatically relabelled confidence.
- Hotspot mapping, exact/uniquely aligned sequence correspondence, target fitting, symmetry alternatives, positional/internal/interface RMSD, contact recurrence/Jaccard and pose clustering.
- Immutable candidate/control registration, composition-matched seeded scrambled controls, existing-engine screening orchestration and saved comparison reports.
- JSON/CSV/Markdown/PDF and figure exports within the implemented Intelligence scope.

Numerical reference checks include rigid-fit agreement with NumPy and bounded SASA comparison with Biopython. These are scoped algorithm comparisons, not universal affinity validation. Contacts, surface burial and geometric H-bonds do not supply binding free energy, experimentally established inhibition or a calibrated universal binder score.

### Research Suite additions

Versioned candidate evidence, measurements/notes, assay readings with units/conditions, descriptive liabilities, explicit single-mutant proposals, full-target mapping and a separately identified larger-complex pose scene are implemented. The derived ANGPTL3/8 pose is a structural hypothesis, not a new validated full-complex binding prediction.

Guided complete repair/protonation, validated docking/selectivity panels, calibrated developability, converged simulations, free-energy methods, pharmacophores/QSAR, complete assay fitting and the unified publication/study graph remain incomplete.

**Sources:** `docs/MOLECULAR_INTELLIGENCE_4_3.md`, `RESEARCH_SUITE_ACCEPTANCE.md`, `RESEARCH_SUITE_EXECUTION_STATE.json`; `scientific/intelligence.py`, `research.py`, `biology_assessment.py`.

## 9. Chemistry, coordinate ensembles and dynamics

| Capability | Implemented scope | Remaining boundary |
|---|---|---|
| Canonical peptide building | Existing sequence/build/atom-identity workflows and source-linked records | Arbitrary modified chemistry and complete force-field coverage |
| RDKit ligand preparation | Isomeric SMILES, ETKDGv3 conformers, MMFF94s minimization, explicit charge/stereochemistry, checksum-checked SDF and viewer transport | Not docking, pH titration, exhaustive tautomer/salt handling or binding energy |
| Peptide chemistry | Real scoped cyclic/disulfide/stereochemistry/conformer operations with atom/residue mapping | Generic staples, full noncanonical support and validated modified-peptide bound predictions |
| Coordinate ensembles | Same-topology multi-MODEL PDB import, original frame IDs/metadata, slider/play/pause and raw export | Supplied frames are not newly generated MD; physical time is not guessed |
| Motion measurements | Raw/fitted Cα RMSD and population RMSF, preserved coordinates and saved reports | Equilibration, convergence and biological flexibility are not established |
| OpenMM pilots | Bounded short CPU/Reference protein pilots, trajectories, positions/velocities/time checkpoints and tested same-machine continuation | Not a full explicit-solvent/ligand/general MD suite or Metal MD engine; no universal cross-platform checkpoint portability |

**Sources:** `docs/LIGAND_PREPARATION.md`, `COORDINATE_ENSEMBLES.md`, `DYNAMICS_PILOTS.md`; RDKit/OpenMM/ensemble/trajectory receipts.

## 10. Molecular Cinema

### Working implementation

The existing viewer supports a saved presentation scene/timeline, camera framing and transitions, per-chain colours, cartoon/matte/translucent/outlined styles, light editorial and dark observatory figures, anchored labels, peptide approach, ghost pose, geometric contact overlays and a binding-site close-up.

The recorded ANGPTL3/8 demonstration used the original peptide **APAEPSWEELIEMMKKENLI** and a separately saved **1,085-residue larger-complex pose-hypothesis scene**. Native verification recorded 96 larger-complex views and decoded all **450 frames** of an exported **30-second, 1920×1080, 15-fps H.264 movie**. Source integrity and temporary-frame cleanup were checked.

Movie artifact: `/Users/vii/Documents/FoldStudio-MetalPort/artifacts/ANGPTL3-8-peptide-approach.mp4`.

### Interpretation

The peptide's approach is **illustrative presentation motion** toward a saved predicted pose. It is not a physically simulated association trajectory, binding free-energy path, experimental observation, whole-cell model or complete ribosome simulation. A polished movie does not validate a candidate.

**Sources:** `scientific/cinema.py`, viewer/presentation modules; `docs/RESEARCH_SUITE_EXECUTION_STATE.json`; `reports/cinema-native-validation.json`.

## 11. Cloud Compute, RAPID and multi-engine molecular evolution

### Working infrastructure and interface

- Portable versioned worker and authenticated SSH path; native preparation/connection and detached execution/reconnection controls.
- Modal authentication with Keychain-backed named profiles, campaign account ownership and account-specific credentials/configuration.
- Cloud campaign prepare/review/explicit upload/launch, monitoring, stop/cancel, saved results and verified import into the existing library/viewer.
- Seven-section Cloud Compute workstation: overview, terminal, current candidate, lineage, analysis/performance, engine readiness and configuration.
- Real archived/live child-log transport, search/filter/follow/pause/visible-clear/export, fixed command input and persistent event cursors.
- Reviewed bounded remote commands through an existing owned Modal container. This is not a fully persistent PTY or a newly connected Vast interactive terminal.
- GPU profiles and evidence-aware readiness, source/account/deployment checks, leases preventing conflicting writes/deployments, stage reservations and explicit failure recovery boundaries.
- Separate generator/redesign/refold/assessment tasks, candidate lineage, fresh predictions after sequence changes, original filters and bounded discrete/Pareto coordination.

Not every account-switching scenario or GPU profile has been exercised. Catalog/rate snapshots are dated, provider balance/invoices are not reconciled, and estimated allowances are not provider-enforced billing caps. Exact mid-optimizer resume and a fully adaptive scientifically qualified controller remain absent.

### Genuine cloud molecular result

The later saved A100-80GB campaign `9c99e7870a19bd621c67ccf7bc8aefa1` supplies stronger evidence than the earlier failed campaign:

- Actual BindCraft generation and separate MPNN outputs exist.
- Original upstream rank 1 is **DPDLERIRSGEWMAEVQAAL**, 20 residues, reported upstream **i_pTM 0.90 / pLDDT 0.91**.
- Eight immutable lineage records and original ranked output were recovered, with scientific artifact checksums.
- The campaign is **PARTIALLY_COMPLETE**, not a fully scientifically qualified final pipeline.
- An additional AF2 stage on an older reference produced one model's coordinates but did not finish its additional ensemble. It must not be presented as complete extra validation of the rank-1 candidate.

The first cloud campaign's genuine rejected design, cancellation and downstream failures remain preserved. Later success does not rewrite them.

### Engine-by-engine status

| Engine/component | Strongest established scope | Material unfinished work |
|---|---|---|
| BindCraft2 | Genuine local and A100 execution; original rejected and upstream-accepted outputs preserved | Broad option/modality parity and full strategy qualification |
| ProteinMPNN / SolubleMPNN | Genuine local inference and later cloud output records; distinct descendant identities | Complete fresh-prediction/independent-quality validation of descendants |
| AF2 held-out evaluation | Genuine local use and upstream evaluation; additional cloud stage remains incomplete | Complete additional cloud ensembles and broader numerical/reference qualification |
| BoltzGen | Authentic adapter, source/runtime/import and transport paths | Trained assets and genuine qualified generation; no complete complementary BindCraft–BoltzGen campaign |
| ESMFold2 Fast/full | Authentic inference invocation and typed data contracts | Trained assets, actual inference and hardware/scientific qualification |
| RFdiffusion | Motif/scaffold adapter and input/output contracts | Source/model installation, genuine generation and verified target-aware downstream assembly |
| ESMC design | Official approach investigated | Executable authentic optimization pathway remains missing |
| Rosetta | License/runtime admission and conditional task path | Licensed runtime and real relaxation/energy/reference execution |
| Hosted BoltzProt / library screen | Official SDK/contract and quote/payment/identity gates | Authenticated separately approved provider execution; not a self-hosted Modal model |
| Shared evolution controller | Bounded discrete coordination, immutable branches, fresh-evaluation requirements and Pareto selection | Complete scientific multi-round/seven-strategy acceptance and adaptive operation choice |

This is **not a single jointly differentiable BindCraft–BoltzGen model**. CLI/task/serialization boundaries and discrete choices remain. Full de novo, sequence, motif, hotspot, iterative, chemical and counterfactual mode acceptance is incomplete.

### Performance

The local paired cache-benchmark receipt reports approximately 816.31 → 662.73 seconds, **1.23× runner wall-time speedup**, not 3×. That receipt is currently untracked and measures complete paired runner time, not isolated compile time or scientific numerical equivalence. It does not establish an optimal GPU/RAM profile or universal performance gain.

**Sources:** `docs/CLOUD_COMPUTE_5_IMPLEMENTATION.md`, `RAPID_COMPLETE_ENGINE_AUDIT.md`, `RAPID_UNIFIED_IMPLEMENTATION.md`, `BGMEE_IMPLEMENTATION.md`, `CLOUD_COMPILE_CACHE.md`; native/cloud/campaign receipts.

## 12. EditCraft: exact executable operation inventory

The application now registers the following **21 executable operations**. Their evidence differs; registration alone is not acceptance of every scientific use case.

| Operation | Implemented function / evidence boundary |
|---|---|
| `gene_context` | Ensembl gene/transcript/exon/CDS/protein retrieval; real public ANGPTL3 reference consistency |
| `sequence_analyze` | Sequence inspection, standard-code translation, reverse complement, codon/frame mapping; reference and synthetic checks |
| `annotated_import` | Biopython annotated-sequence/GenBank parsing with preserved annotations |
| `annotation_parse` | Explicit BED/GFF3/VCF coordinate normalization; not a complete genome browser |
| `motif_find` | Exact IUPAC motif enumeration; no editing-activity inference |
| `coordinate_map` | Assembly/strand/exon-aware genomic-to-transcript mapping; no guessed protein coordinate |
| `sequence_align` | Explicit sequence alignment and correspondence |
| `variant_cds` | Reference-checked coding-sequence variant comparison |
| `variant_vep` | Assembly/reference-allele-checked original Ensembl VEP SNV annotation |
| `rna_fold` | ViennaRNA minimum-free-energy secondary structure |
| `rna_ensemble` | Partition function, centroid/MEA, base-pair probabilities and marginal unpaired accessibility |
| `rs3_activity` | Genuine pinned Rule Set 3 sequence-only activity inference |
| `bedict_per_base` | Genuine BE-DICT five-run per-base classifier outputs |
| `pridict2_design` | Genuine original PRIDICT2 design/prediction with both model groups and all folds |
| `cas_offinder` | Pinned Cas-OFFinder sequence-match enumeration against explicit verified reference |
| `reference_window` | Exact pinned assembly window with strand-aware coordinates |
| `fastq_qc` | Bounded FASTQ/read-quality parsing and summaries; not full editing-outcome sequencing analysis |
| `experimental_compare` | Explicit matched-context numerical comparisons; not a universal causal/efficacy model |
| `literature` | PubMed evidence retrieval; search results are not automatically curated biological truth |
| `scanpy_analysis` | Actual raw-count QC, normalization, PCA, UMAP, Leiden and exploratory cluster markers |
| `pathway_enrichment` | Explicit-background hypergeometric over-representation, full-family BH/BY adjustment and retained provenance |

Production EditCraft computation is routed to its independent Modal CPU service. The Mac renders results and performs bounded preparation/validation; no silent local model fallback is supplied.

### Genome, RNA, guide/base/prime methods

Native forms, ordered typed workflow cards, local dry review, separate transfer/cost approvals, job refresh/cancel/results, versioned entities, notebook/report links, source provenance and private explicit failure diagnostics are implemented.

Actual evidence includes:

- Public ANGPTL3 CDS translation consistent with the separately retrieved **460-aa** protein.
- Rule Set 3 reference values reproduced for tested examples; this is not an independent genome-editing accuracy benchmark.
- BE-DICT retains every original run's class probabilities; these are **not measured conversion fractions or haplotype distributions**.
- PRIDICT2's official example produced **765 complete candidate rows**, preserving HEK/K562 contexts and original model/fold distinctions.
- Genuine ViennaRNA MFE/ensemble outputs, including public tRNA secondary-structure-to-observed-3D selection. Canonical parent bases do not model modification thermodynamics.
- Cas-OFFinder stable **2.4.1**, a pinned complete E. coli reference and **four real CPU reference calculations**, including strand/mismatch and circular-origin checks. Human whole-genome qualification remains incomplete.
- One assembly/allele-checked public VEP SNV reference returned **three original transcript rows**. These are annotations, not pathogenicity, clinical significance or demonstrated functional effects.

**Sources:** `docs/EDITCRAFT_COMPLETION_REPORT.md`, `EDITCRAFT_MODAL_QUALIFICATION.md`, `EDITCRAFT_OFFTARGET_ENGINE.md`; model/RNA/off-target/VEP/native receipts under `reports/editcraft/`.

## 13. Single-Cell & Perturbation Laboratory

### Working Scanpy slice

- Exact original H5AD import and separately approved cloud preparation, keyed by size/SHA-256 and account.
- Isolated pinned Scanpy/AnnData runtime: **two CPUs, 8 GiB**, bounded execution, no GPU or automatic scientific retry.
- Explicit raw-count validation, metadata preservation, QC filters, normalization, variable genes, scaled PCA, neighbor graph, seeded UMAP/Leiden and exploratory Wilcoxon cluster markers.
- Actual UMAP display, gene/provided-metadata colours, selection/zoom/barcode search, expression heatmap/histograms, population sizes and separate user annotation evidence.
- Complete processed H5AD with original-count layer, source metadata archives, parameters/package freeze and reopen/round-trip checks.
- Optional native Save-dialog export, checksum verified before destination replacement. Display sampling is declared and does not change the full analysis.

### Genuine public reference

PBMC3k contained **2,700 cells × 32,738 features**. Completed job `aa4aef6fb37c4d4e8f41b1d6e9273f5c` retained **2,638 cells × 13,714 features**, producing seven computational clusters: **1,176 / 342 / 153 / 486 / 432 / 36 / 13** cells.

Actual UMAP/cell/expression alignment, QC thresholds, full-population means and exact H5AD raw-count/identity/metadata round trips passed. The **15,278,743-byte** processed file exported through the app matched its original SHA-256.

The first legacy-H5AD format failure remains preserved. A separately approved corrected attempt completed; a later mounted-volume path guard fix verified the saved file without repeating the analysis.

### Unfinished

scvi-tools, Pertpy, CELLxGENE ingestion, real perturbation datasets/contrasts, donor-aware differential expression, batch correction/diagnostics, inferred cell types, multimodal workflows and independent biological benchmarks remain incomplete. This one healthy-donor dataset is not a tumor microenvironment or replicated perturbation study.

**Sources:** `docs/EDITCRAFT_SINGLECELL_ENGINE.md`; `singlecell-validation.json`, `native-singlecell-workflow.json` and format/data-integrity receipts.

## 14. Systems Biology / pathway analysis

The new workspace accepts selected genes, an explicit measured/testable background and attributed GMT collections. It preserves namespace/case/version, records source/license attribution, refuses implicit backgrounds/duplicate identities, retains non-significant hypotheses and exposes both BH/BY result stages.

Its log-space hypergeometric implementation passed finite-population enumeration tests and **111 independent SciPy numerical cases**, with maximum absolute log-probability difference approximately **2.11e−10**. A separately approved real cloud job completed both correction methods on a clearly labelled synthetic mathematical reference.

Native verification switched between raw p **0.008333…**, BH-adjusted **0.025**, and BY-adjusted **0.045833…**. The exact five saved Scanpy cluster-5 markers transferred into a draft while the testable background remained empty/explicit.

**This is mathematical execution qualification, not biological pathway qualification.** No externally verified Reactome/GO/STRING/BioGRID collection or biological benchmark was supplied by this feature. Curated ingestion, pathway/network graphs, perturbation context, mechanistic simulations and broad systems biology remain unfinished. Enrichment does not measure pathway activation or causation.

**Sources:** `docs/EDITCRAFT_PATHWAY_ENGINE.md`; pathway numerical/cloud/native receipts.

## 15. Research records, intelligence and development automation

### Scientific research records and assistants

Versioned sequences, evidence, notes, analyses, experiments, workflow definitions and reports are connected to the shared library. Evidence labels distinguish observations, annotations, predictions and hypotheses. Existing biological evidence retrieval and a bounded local language-model tool path have actual scoped execution.

The original EditCraft Intelligence Core remains partial. There is no validated original learned intervention model, calibrated therapeutic ranking, autonomous experimentally grounded research agent or complete multiscale consequence graph. An ordered workflow editor is not yet a complete branching study graph with universal replay. Rich collaborative notebooks and full publication packages remain incomplete, despite existing specialized report/figure exports.

### Independent local development worker

Implemented in `local_worker/`, separate from molecular calculations:

- launchd/FIFO-backed service; SQLite durable tasks, atomic claims, bounded logs/results and ownership-aware cancellation;
- deterministic checks, exact-hash patches and optional bounded local Aider/Ollama edits in isolated review worktrees;
- path/operation restrictions, concurrency/memory/timeout governors, blocked/escalated states and retained failure diagnostics;
- review-only patches, explicit resume/rollback and no automatic merge, push, app installation or scientific campaign restart.

A real local Qwen coding fixture completed its acceptance checks; an existing peptide test task also passed. This does not establish general autonomous coding accuracy, biology expertise or measured Codex allowance savings. The service's present running state was not polled for this audit.

**Sources:** `docs/LOCAL_WORKER.md`, `BGMEE_IMPLEMENTATION.md`; `reports/local-worker-validation.json` and local-agent receipts.

## 16. Explicit gaps and issues that must remain visible

1. **Full macOS port/parity:** every upstream engine, option, modality and large-model size is not certified; a complete native NVIDIA-free port is not finished.
2. **Full Fab:** cancelled after five original updates; no accepted complete Fab campaign, exact optimizer resume or continuous-trajectory identity proof.
3. **Unified cloud science:** full BindCraft–BoltzGen complementarity, adaptive multi-round/seven-mode validation and independent-family/physics gates remain unfinished.
4. **Additional engines:** BoltzGen/ESM/RFdiffusion execution qualification, ESMC design and licensed Rosetta still have missing assets, code, handoffs or evidence.
5. **Compute operations:** true provider billing/balance reconciliation, all-account/all-GPU acceptance, persistent terminal work and broader recovery remain partial.
6. **Molecular research:** general docking, selectivity, calibrated developability, electrostatics/free energies, converged MD and complete assay/statistical workflows remain incomplete.
7. **EditCraft breadth:** additional CRISPR/editor/RNA/foundation models, human genome searches, CRISPResso2/MAGeCK-style outcomes, perturbation/scvi/Pertpy and systems networks remain incomplete.
8. **Intelligence and reporting:** original validated research intelligence, full workflow/causal graph, collaborative publishing and complete end-to-end demonstrations remain incomplete.
9. **Native observatory acceptance:** complete camera/selection/measurement/representation regression and extensive ChimeraX command parity remain open.
10. **Distribution:** local signed app works on this Mac; full clean-machine independence, all licensing/embedding checks and notarized distribution are not established. Notarization remains intentionally deferred.
11. **Documents permission:** changed local signing hashes have triggered repeated macOS privacy prompts. The safe launcher/guard prevents conflicting updates, but does not prove prompts can never recur after a new signature.
12. **Biological validation:** computational outputs, upstream acceptance, attractive figures and movies do not establish experimental binding, cellular efficacy or clinical suitability.

## 17. Completion accounting and stale-record corrections

The detailed EditCraft audit retains **130 sections and 1,933 original acceptance paragraphs**, including 1,349 paragraphs from the earlier specifications. Current clause review records **81 reviewed**, **19 narrowly fully accepted**, **zero whole sections fully accepted**; 1,852 paragraphs still await explicit clause review.

Those are review-accounting figures, **not a platform completion percentage**. Unreviewed clauses do not prove no implementation exists; grouped requirements can contain several large missing systems. A credible global percentage cannot be derived from test totals, menu counts, model imports or these clause counts.

Historical documents must be read with their dates:

- Early “no CUDA execution” records precede the actual later A100 campaigns. They cannot erase that later evidence; nor does one A100 campaign qualify every engine or GPU.
- Early reports of absent cloud MPNN outputs precede the later four saved MPNN outputs.
- Earlier Cinema “timeline/export missing” entries precede the verified movie milestone.
- Older “Scanpy discovery only” entries are superseded by the genuine PBMC3k workflow. scvi/Pertpy remain unfinished.
- Older “pathway methods missing” statements are superseded only for the explicit-background numerical operation, not curated systems biology as a whole.
- Older backend/interface counts describe earlier checkpoints. Current recorded totals are 742/143.

The source snapshot and operation-specific receipts take precedence over an older generic status sentence. No paid provider was contacted to establish live deployment health or current credit balance during this audit.

## 18. Evidence map and audit conclusion

| Area | Principal local evidence |
|---|---|
| Current package/tests/inventory | `reports/fold-studio-implementation-audit.json`; `reports/editcraft/integration-checks.json` |
| Original research preservation | `reports/editcraft/preservation-current.json` |
| Local AF2/BindCraft/Metal | `docs/PROJECT_METAL_MASTER_PROGRESS.md`; `docs/PROJECT_METAL_EXECUTION_STATE.json`; operation-specific reports |
| Fab memory/cancellation/drift | `reports/amme-integration-status.json`; `docs/FAB_AMME_VALIDATION.md` |
| Molecular Intelligence | `docs/MOLECULAR_INTELLIGENCE_4_3.md`; native H-bond/reference receipts |
| RDKit/OpenMM/ensembles | Ligand, dynamics and coordinate-ensemble documents and associated numerical/native reports |
| Cinema | `docs/RESEARCH_SUITE_EXECUTION_STATE.json`; `reports/cinema-native-validation.json` |
| Cloud engine | `docs/CLOUD_COMPUTE_5_IMPLEMENTATION.md`; `docs/RAPID_COMPLETE_ENGINE_AUDIT.md`; campaign/native receipts |
| EditCraft model/RNA/Cas/VEP | `docs/EDITCRAFT_COMPLETION_REPORT.md`; `reports/editcraft/model-validation.json`; off-target/RNA/VEP receipts |
| Single-cell | `reports/editcraft/singlecell-validation.json`; `native-singlecell-workflow.json` |
| Pathways | `reports/editcraft/pathway-numerical-reference.json`; `pathway-cloud-reference.json`; `native-pathway-workflow.json` |
| Full EditCraft scope | `docs/EDITCRAFT_FULL_COMPLETION_AUDIT.json`; `reports/editcraft/requirement-closure.json` |
| Development worker | `reports/local-worker-validation.json`; `docs/LOCAL_WORKER.md` |

**Conclusion:** substantial genuine implementations, saved molecular outputs, native controls and numerical references exist. Fold Studio is usable as a scoped research platform. The complete multi-engine, full-Fab, systems-biology and EditCraft vision is still unfinished, and no implemented feature should be promoted beyond the exact evidence recorded here.
