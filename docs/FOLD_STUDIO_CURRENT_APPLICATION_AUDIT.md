# Fold Studio — current application implementation audit

**29 October 2026 · Europe/Bucharest**  
**Application:** 4.3.0, FOLD STUDIO Metal Dev  
**Source baseline:** `a3258dd98adbb8a0a86adb26577e5ca75a63ffc5`  
**Branch:** `project-omega/ultimate-completion`

Fold Studio is a functioning macOS research application with an existing molecular viewer, persistent research library, real local calculations, cloud campaign controls, molecular cinema, and executing parts of genome/RNA, editing, single-cell and chemical research. **The full platform in the accumulated master specifications is unfinished.** Full NVIDIA-free parity, all requested scientific models and strategies, universal workflow integration and production distribution have not been demonstrated.

This audit covers the application as a whole, including the additions since the 26 October implementation audit. It distinguishes implemented code, actual scientific execution, native interaction checks and missing work. It does not treat a menu, adapter, passing import or attractive visualization as a completed scientific engine.

## 1. How to read the findings

| Status | Meaning |
|---|---|
| **Working within stated scope** | Saved execution or native acceptance exists for the specified inputs and method. Broader use remains subject to the stated limits. |
| **Implemented and tested** | Source and focused software/numerical evidence exist; complete native or biological qualification may still be missing. |
| **Partial** | Useful functionality exists, but a substantial part of the requested domain is missing or unqualified. |
| **Deferred / gated** | Work is deliberately excluded, or needs assets, licensing, independent validation or a separately approved calculation. |

This is an evidence reconciliation, not a fresh comprehensive regression run. Today’s checks reviewed repository/package metadata, existing receipts and exact hashes of **25 non-Fab scientific files**; all 25 match the installed app. No new model inference, model download, paid computation, provider-balance query or full test suite was started to write this audit. Fab code and research outputs were not reopened for investigation; its summary below is historical only.

Machine-readable current findings and exact file hashes: [current-application-audit.json](../reports/current-application-audit.json). Historical baseline: [26 October implementation audit](FOLD_STUDIO_IMPLEMENTATION_AUDIT.md). Requirement-level scope: [Ultimate audit JSON](FOLD_STUDIO_ULTIMATE_COMPLETION_AUDIT.json) and [EditCraft audit JSON](EDITCRAFT_FULL_COMPLETION_AUDIT.json).

## 2. Project folder and installed application

The parent folder opened in Finder is `/Users/vii/Documents/FoldStudio-MetalPort`.

| Location | Contents / policy |
|---|---|
| `fold-studio/` | Active source repository, interface, scientific services, cloud worker, tests, documentation and reports |
| `current/FOLD STUDIO Metal Dev.app` | The single current application; updates replace it through the guarded installer |
| `validation/` | Saved research, scientific validation evidence and the actual app location reached by `current` |
| `validation/bindcraft-fab-amme-native/` | The real research library, assets and settings; its historical name does not make it disposable |
| `artifacts/` | Exported deliverables, including the ANGPTL3/8 peptide movie |
| `runtimes/`, `models/`, `upstream/` | Development runtimes, model assets and upstream scientific source |
| `fold-studio/docs/`, `fold-studio/reports/` | Implementation records, requirement audits and execution evidence |

The latest build receipt records a **5.34 GiB application bundle**, successful import/resource checks for **80 local modules**, and valid local signatures. That size is the build-time bundle size, not a fresh measurement of total project disk use. Models, libraries and scientific data outside the bundle add storage. This audit did not rescan or clean storage.

The current path resolves to `validation/RAPID Foundation Engine/FOLD STUDIO Metal Dev.app`; it is the same canonical app, not an extra release. No new backup app or ZIP was created. No replacement or rebuild was necessary for this report.

**Evidence:** [latest build log](../reports/ultimate/bgzf-coverage-final-build.log), [storage policy](STORAGE_POLICY.md), [current checkpoint](CURRENT_IMPLEMENTATION_CHECKPOINT.md).

## 3. What the app is made from

| Layer | Actual implementation / origin |
|---|---|
| Desktop shell | Tauri 2 and Rust, native file dialogs, allowlisted service calls and child-process control |
| Interface | React 19, TypeScript 5.8, Vite 6, CSS/glass components, Lucide icons |
| Molecular renderer | The existing Mol* WebGL viewer in the macOS webview; it has not been replaced with a new Metal/SceneKit renderer |
| Scientific application service | Python, SQLite research storage, source/checksum receipts, shared jobs and engine-specific subprocesses |
| Molecular command backend | Authenticated headless UCSF ChimeraX bridge with model, atom, selection, camera and session synchronization |
| Protein science | Pinned BindCraft2/AF2/ProteinMPNN sources, CPU JAX and scoped MetalJAX paths; PyTorch/MPS Boltz-2 |
| Chemistry / physics | RDKit, OpenMM 8.6.1 CPU and PySCF 2.14.0 ARM CPU; h5py 3.16.0 for quantum runtime support |
| Genomics | Biopython and pysam 0.24.1 / SAMtools 1.24 |
| Editing / RNA / cells | Ensembl and public-reference adapters; ViennaRNA, Rule Set 3, BE-DICT, PRIDICT2, Cas-OFFinder, Scanpy/AnnData |
| Cloud | RAPID remote worker, SSH transport and independent Modal molecular/EditCraft services |
| Optional local coding assistant | Approved Ollama/Aider integration with a local Qwen coding model, separate from scientific validation |

Fold Studio supplies the interface, orchestration, record models, adapters and research workflows. It does not originate the trained models or underlying third-party methods. Pins, manifests and original notices live under `vendor/`, scientific manifests and `THIRD_PARTY_NOTICES.md`. Permission to use project source does not establish every dependency’s redistribution/license conditions. Rosetta remains license-gated.

## 4. Whole-application status at a glance

| Area | Current finding |
|---|---|
| Desktop, projects, library, import and ordinary exports | Working within scope |
| Molecular rendering, colouring, selections and command bridge | Working within scope; broad command/interaction parity partial |
| Local Boltz-2 prediction, AF2/BindCraft components, MPNN | Genuine execution exists; complete native engine parity unfinished |
| Cloud campaign control and real BindCraft result | Working within scope; complete multi-engine scientific qualification unfinished |
| BoltzGen / ESM / RFdiffusion / Rosetta | Adapters or preparation exist at differing levels; genuine full qualification incomplete |
| Molecular Intelligence, structural comparisons and research records | Working scoped analyses; complete drug-discovery suite unfinished |
| Molecular Cinema | Actual saved scenes and exported movie; illustrative approach motion |
| Genome/reference workflows | Working bounded formats, indexing, sequence products, observations and handoffs |
| EditCraft guide/base/prime and RNA operations | Several actual cloud methods qualified on reference examples; broad ecosystem partial |
| Single-cell / pathways | Genuine bounded Scanpy and numerical enrichment execution; broader biological workflows partial |
| Ligands / trajectories / crystal inspection | Working bounded calculations and inspectors |
| Quantum / periodic models | Actual small-system CPU methods; broad quantum/materials suite partial |
| General registry / notebook / workflow / publishing | Useful records and tools; complete research graph/replay/collaboration unfinished |
| Full Fab | Deferred by explicit user instruction; no work resumed |
| Public distribution | Locally signed app available; notarization deferred and fresh-machine acceptance incomplete |

## 5. Desktop, projects and research library

Implemented functions include Home/navigation, project selection/creation, research history, saved structure and sequence records, settings and engine status. PDB/mmCIF import, public structure retrieval, source-linked records, per-record editing/renaming and removal/restoration paths are present. Local jobs retain meaningful state, logs, failures, cancellation and supported recovery boundaries.

Project archives have progressed beyond export-only handling. Bounded CRC/SHA review and transactional import with new identities, checked assets, link remapping and rollback are implemented for supported records, including the recent genome and alignment-observation records. Archived jobs remain inert; import is not permission to resume computation. Notebook search, saved versions/history and export helpers exist.

**Remaining:** universal restoration of every historical record/engine, a complete cross-engine replay/undo system, all migration/fresh-machine cases, collaborative notebooks and publication packages. Passing supported archive round trips does not establish universal portability.

The latest preservation receipt retains **all 16 baseline structure records/assets**, unchanged metadata digest and coordinate hashes. The original library was reopened through the native Home screen, showing the B. subtilis project and saved 4V9D scene.

**Source/evidence:** `scientific/worker.py`, `project_archive.py`, `project_restore.py`, `src/components/EditCraftNotebook.tsx`; [latest preservation](../reports/ultimate/bgzf-coverage-preservation.json), [native library restoration](../reports/ultimate/bgzf-coverage-native-acceptance.json), [consolidated native checks](../reports/ultimate/consolidated-native-acceptance.json).

## 6. Molecular viewer, selection and ChimeraX

Implemented capabilities include cartoon/ribbon, atom/bond and surface representations; per-chain colours and visibility; atom/residue selection; camera controls; overlays, measurements, comparisons and source-linked identities. ChimeraX command execution/history and scene/session synchronization are connected behind the original viewer.

Recorded geometry/clipping work includes full-axis orbit checks and **96 views of the larger complex**. These address the observed rotation-dependent disappearance without replacing coordinates or redesigning the viewer. DNA/RNA/protein identities, modified nucleotides and author/label numbering are retained. Exact secondary-structure/probability selections can map to observed RNA 3D residues when correspondence exists.

The complete **4V9D ribosome assembly, 146,921 atoms**, has actual rendering and coordinate-preservation evidence. This is structural visualization, not a functional atomistic ribosome simulation.

**Remaining:** the full native camera/pan/multi-atom measurement/representation matrix; universal hardware acceptance; extensive ChimeraX feature parity and self-contained distribution qualification. The historical command CSV records **22 scoped tested entries out of 591**, not certification of all commands. No complete mRNA translation chemistry, whole-cell behavior or tumor-microenvironment simulation is implemented.

**Evidence:** [Molecular Intelligence documentation](MOLECULAR_INTELLIGENCE_4_3.md), [command compatibility CSV](CHIMERAX_COMMAND_COMPATIBILITY.csv), nucleic-acid receipts in `reports/editcraft/`, historical [implementation audit](FOLD_STUDIO_IMPLEMENTATION_AUDIT.md).

## 7. Local prediction and the Apple Silicon port

### Boltz-2

A genuine local PyTorch/MPS prediction route includes setup/resource checks, model integrity handling, jobs, output import and confidence handling. Broad input chemistry, arbitrary target sizes and universally safe memory fit are not established.

### BindCraft2 / AlphaFold2

Pinned upstream source, original settings/presets, explicit chains/sites/lengths/seeds, ranking/filter semantics, campaign preparation, jobs and result import are implemented. Scoped CPU/Metal forward, loss, gradient and optimizer comparisons have real evidence. A narrow float32 Metal attention implementation and a separate compatible MetalJAX path have been exercised; this does not establish full upstream parity or resolve every original Apple JAX limitation.

A historical **175-residue original-ensemble local campaign** completed with ProteinMPNN and held-out AF2 checks, preserving an upstream-accepted computational design. Larger sizes remain memory-limited. The app refuses unsafe cases rather than silently cropping targets, changing precision or claiming success.

### BindCraft Architect

The five-part workspace includes Overview, Target & Design, Scientific Settings, Compute & Run and Campaign Library. Draft persistence, selected/protected residues, chain constraints, amino-acid exclusions, property settings, sequence/fragment targets, campaign controls, ranked import and retained failed/cancelled progress are present. Advanced multi-state/negative-target/repeat/recovery/scoring options have differing evidence levels.

**Remaining:** every upstream option/modality, large-model memory envelope, broad numerical parity and end-to-end acceptance of every advanced strategy. The entire scientific platform is not fully ported to NVIDIA-free local macOS.

**Evidence:** [Project Metal progress](PROJECT_METAL_MASTER_PROGRESS.md), [Architect report](BINDCRAFT_ARCHITECT_REPORT.md), prior implementation audit. This audit did not rerun these models.

## 8. ProteinMPNN and SolubleMPNN

Genuine checkpoint inference exists for ProteinMPNN, with selected chains, fixed context, seed, sequences and scores retained. Tested local examples matched direct pinned-upstream sequence/score outputs. SolubleMPNN is a distinct genuine redesign branch with separately identified checkpoint and outputs, including cloud execution evidence.

New sequences retain lineage and require fresh structure/evaluation; old side chains are not rebranded as a newly predicted structure. SolubleMPNN output is not a measured solubility result.

**Remaining:** complete independent quality validation and fresh-prediction acceptance across every descendant, target and campaign modality.

## 9. Fab — deliberately deferred

Fab remains **cloud-only and deferred** under the user’s explicit instruction. Existing source, settings, cancelled attempts, research data and scientific limitations are preserved. No Fab implementation, local optimization, numerical investigation, memory profiling, model execution or new cloud attempt was performed for this audit.

Historical records establish component work and a cancelled local attempt after five optimizer updates; they do not establish a fully accepted Fab campaign. The documented independent-trajectory numerical drift limitation remains. Older documents saying a Fab job “is running” are dated records, not a current live-status assertion. No provider job inventory was queried here.

**Conclusion:** not finished and not resumed. This audit does not propose further Fab work.

## 10. Cloud Compute and RAPID controls

Implemented infrastructure includes authenticated SSH transport, a portable worker, Modal Keychain-backed named accounts, campaign ownership, preparation/review, separate upload/launch approvals, monitoring/cancellation, result retrieval and verified library import. GPU profiles, stage-resource estimates, deployment/source compatibility checks, leases and retained failure diagnostics are present.

The Cloud Compute workstation includes overview, terminal, current candidate, lineage, analysis/performance, readiness and configuration. Actual child logs, cursor-based recovery, search/filter/follow/pause/export and bounded remote command input exist. Bounded commands in an owned container are not a general persistent PTY or complete multi-provider terminal.

Local review/launch fixes addressed invisible preparation failures, malformed process arguments, deployed-source mismatch, stale allowance/rate handling and stopped-service diagnostics. Their source/test/deployment receipts are historical evidence; current provider availability and billing were not rechecked today. Account/profile controls exist, but every account/GPU combination has not been exercised.

Allowances and reservations are estimates, not provider-enforced billing caps or an automatically synchronized credit balance. Exact mid-optimizer resume, universal recovery and fully autonomous scientifically qualified resource/strategy choice remain incomplete.

### Actual cloud molecular result

Saved A100-80GB campaign `9c99e7870a19bd621c67ccf7bc8aefa1` contains actual BindCraft generation, separate MPNN outputs and eight lineage records. Its upstream rank-1 candidate is **DPDLERIRSGEWMAEVQAAL** (20 residues), with reported upstream **i_pTM 0.90 / pLDDT 0.91**.

Its recorded state is **PARTIALLY_COMPLETE**. An extra AF2 stage did not complete its additional ensemble; that must not be represented as completed extra validation of rank 1. These upstream metrics are not measured binding, affinity, cellular efficacy or full-complex qualification. Earlier rejections/failures remain preserved.

A recorded paired cache test showed approximately **816.31 → 662.73 seconds (1.23×)** runner speedup, not 3×. It is not a universal performance or numerical-equivalence benchmark.

**Evidence:** [Cloud Compute implementation](CLOUD_COMPUTE_5_IMPLEMENTATION.md), [RAPID engine audit](RAPID_COMPLETE_ENGINE_AUDIT.md), [compile cache](CLOUD_COMPILE_CACHE.md), historical campaign receipts.

## 11. Cloud model and complementary-engine readiness

| Component | Established implementation | Still missing / unqualified |
|---|---|---|
| BindCraft2 | Genuine local and A100 execution, preserved original acceptance/rejection | Broad modality and strategy qualification |
| ProteinMPNN / SolubleMPNN | Genuine separate inference/output paths | Complete descendant evaluation across workflows |
| AF2 held-out evaluation | Genuine local/upstream execution | Complete extra cloud ensembles and broad references |
| BoltzGen | Authentic adapter, runtime/source/import and transport paths | Qualified trained-model generation and complete complementary campaign |
| ESMFold2 Fast/full | Inference invocation and typed task contracts | Asset/execution/hardware/scientific qualification |
| RFdiffusion | Motif/scaffold adapter and I/O contracts | Complete runtime/models, real generation and target-aware downstream acceptance |
| ESMC design | Approach investigated | Authentic executable optimization pathway |
| Rosetta | Conditional task path and license/runtime gates | Licensed runtime and genuine relaxation/energy/reference evidence |
| Hosted BoltzProt / library screening | Provider SDK/contract and quote/payment gates | Separately approved authenticated provider execution |
| Shared evolution controller | Discrete bounded coordination, lineage, fresh-evaluation requirements and Pareto selection | Complete adaptive multi-round/seven-mode scientific acceptance |

BindCraft and BoltzGen are intended as complementary generators behind shared orchestration. They are not a single jointly differentiable model, and the complete complementary engine is not scientifically qualified. A registry entry is not proof its model ran.

## 12. Molecular Intelligence and candidate research

Working scoped analyses include chain/atom/residue completeness, partner assignments, contacts, chemistry-aware clashes, explicit-hydrogen geometric H-bonds where supported, tentative missing-hydrogen contacts, salt/nonpolar/aromatic screens, SASA/interface area, actual confidence-array import, hotspot mapping and interaction networks.

Structural comparisons include rigid fitting, exact/uniquely aligned correspondence, symmetry alternatives, positional/internal/interface RMSD, contact recurrence/Jaccard and pose clustering. Candidate/control registration, seeded composition-matched scrambled controls, immutable evidence and reports are implemented. Missing confidence remains unavailable; B factors are not silently relabelled pLDDT.

Research Suite includes candidate notes/measurements, descriptive liabilities, explicit mutation proposals, source-linked full-target mapping and a separately saved larger-complex pose hypothesis. The transferred pose is not a new validated full-complex binding prediction.

**Remaining:** general repair/protonation, qualified docking/selectivity, calibrated developability/ADMET, converged simulations and free energies, comprehensive statistical study design and the full publication graph. Contacts and buried surface do not establish binding free energy or inhibition.

**Evidence:** [Molecular Intelligence](MOLECULAR_INTELLIGENCE_4_3.md), [Research Suite acceptance](RESEARCH_SUITE_ACCEPTANCE.md), `scientific/intelligence.py`, `research.py`, prior numerical/native receipts.

## 13. Molecular Cinema

Saved scenes/timelines, camera framing/transitions, chain colours, matte/cartoon/translucent/outline styles, light/dark figures, anchored labels, peptide approach, ghost pose, geometric contacts and close-ups are implemented in the original viewer.

The recorded ANGPTL3/8 demonstration uses **APAEPSWEELIEMMKKENLI**, a separate peptide from the later cloud candidate, with a **1,085-residue larger-complex pose-hypothesis scene**. Evidence includes 96 larger-complex views and decoding all **450 frames** of a **30-second, 1920×1080, 15-fps H.264** export. The movie is at `artifacts/ANGPTL3-8-peptide-approach.mp4` in the parent project folder.

The approach animation is illustrative movement toward a saved predicted pose. It is not simulated molecular association, experimentally observed binding or a free-energy trajectory. Full video-editor/scene-effects breadth and every publication format remain incomplete.

**Evidence:** `reports/cinema-native-validation.json`, [Research Suite execution state](RESEARCH_SUITE_EXECUTION_STATE.json).

## 14. Peptide and small-molecule chemistry

Implemented peptide building/identity workflows and scoped cyclic/disulfide/stereochemistry/conformer operations preserve source mappings. Arbitrary staples, noncanonical chemistry and validated modified-peptide bound predictions are incomplete.

RDKit ligand preparation accepts explicit isomeric SMILES, creates ETKDGv3 conformers, minimizes with MMFF94s and retains stereochemistry/charge, actual conformer energies, checksummed SDF and receipts. The saved-result inspector and SDF/JSON exports have native evidence on an existing ethanol example.

A newer compound-table tool retains exact input CSV and calculates genuine RDKit canonical graphs, formula/mass, charge, H-bond counts, TPSA, logP, rotatable bonds, explicit SMARTS matches and optional chirality-aware Morgan/Tanimoto similarity. Native numerical examples include ethanol and propane.

**Remaining:** qualified docking, pharmacophore/QSAR, exhaustive pH/tautomer/salt handling, trained toxicity/ADMET, binding/selectivity and activity prediction. Vina 1.2.7 lacked an official macOS ARM wheel in the recorded availability check; this is not proof a native source build is impossible. A source build or approved Linux execution plus genuine redocking references is still required.

**Evidence:** [ligand preparation](LIGAND_PREPARATION.md), [compound tests](../reports/ultimate/chemical-screen-tests.log), [native chemistry evidence](../reports/ultimate/scientific-continuation-native-acceptance.json).

## 15. Coordinate ensembles, motion and protein dynamics

Supplied same-topology multi-MODEL PDB ensembles retain original bytes, MODEL identities and atom correspondence, with slider/play/pause/raw export. Imported frames do not acquire invented physical time.

Actual measurements include raw/fitted Cα RMSD, population RMSF and per-frame equal-mass observed-Cα radius of gyration, with explicit fitting/weight conventions and saved reports. Geometry comparisons include actual original ChimeraX/NumPy references. An artificial translation fixture verifies arithmetic, not biological dynamics.

OpenMM 8.6.1 CPU provides short bounded protein pilots with Amber ff14SB/OBC2 implicit solvent, preparation/minimization, retained parameters/system/integrator/state/checkpoint artifacts, trajectories and shared cancellation. Scope is canonical complete proteins within the documented small pilot bounds; missing heavy atoms are not silently repaired. Same-machine checkpoint continuation retains actual state and absolute time/steps and has reference evidence.

**Remaining:** general ligands/ions/explicit solvent, arbitrary force fields/protonation, long/converged sampling, general checkpoint portability, Metal MD and binding/free-energy qualification.

**Evidence:** [coordinate ensembles](COORDINATE_ENSEMBLES.md), [dynamics pilots and continuation](DYNAMICS_PILOTS.md), [native gyration check](../reports/ultimate/consolidated-native-acceptance.json).

## 16. Crystallographic and periodic inspection

Read-only mmCIF tools preserve reported cell parameters, symmetry text, source values and hashes. Implemented calculations include unit-cell geometry/volume, reciprocal-plane spacing, reported fractional-site inspection and bounded periodic neighbor images, including oblique cells via reciprocal-metric bounds.

A genuine 1BNA cell native check displayed **66,497.854 Å³** and reported `P 21 21 21`. Reported symmetry is not independently determined symmetry. Scoped geometric tests cover the calculations; some newer forms have numerical/source evidence without a separate native execution record.

**Remaining:** full symmetry expansion, complete crystal coordination, general bonding, diffraction/refinement, density/volume breadth and full materials/device workflows.

**Evidence:** `src/components/Crystal*.tsx`, `src/lib/crystalNeighbours.ts`, [consolidated native evidence](../reports/ultimate/consolidated-native-acceptance.json), [geometric tests](../reports/ultimate/quantum-genome-interface-tests.log).

## 17. Quantum chemistry — genuine bounded CPU implementation

The bundled **PySCF 2.14.0 / h5py 3.16.0 ARM CPU** backend provides explicit small-molecule geometry/units, charge/spin, supported basis sets, HF or PBE, SCF status, orbital/charge/dipole data and analytic gradients. Electron-density sampling and CUBE export are connected. Balanced electronic reaction-energy comparison checks stoichiometry, charge and compatible methods/bases.

Native H2 HF/STO-3G produced **−1.1167593073964255 Hartree**, density-overlap electron trace approximately **2**, and a saved **24×24×24** density grid/CUBE. HF/PBE/open-shell, gradients, density, balance/integrity/admission and actual subprocess cancellation have focused evidence. The reaction-energy form has backend/numerical checks but was not separately executed natively in the recorded batch.

**Remaining:** geometry optimization, thermal/ZPE/entropy/solvation/counterpoise, kinetics, general accuracy benchmarks, broad elements/methods and periodic electronic-structure methods. This is CPU execution, not Metal/GPU quantum chemistry.

**Evidence:** [quantum tests](../reports/ultimate/quantum-packaged-tests.log), [native quantum data](../reports/ultimate/scientific-continuation-native-acceptance.json), `reports/ultimate/quantum-cancellation-reference.json`.

## 18. Periodic particle simulations

A genuine **OpenMM CPU periodic Lennard-Jones model** supports fixed energy/forces or bounded Langevin trajectories for **2–64 explicitly supplied identical spherical particles**. Units, parameters, seed, coordinates and receipts are retained; the shared queue/cancellation is used. Pair-formula and PBC/translation checks passed. Native acceptance includes a **100-step trajectory with 11 frames**.

This qualifies the stated mathematical model only. General material force fields, chemical bonds, equilibration, barostats, bulk-property prediction, phonons, materials ML and full simulation visualization remain incomplete.

**Evidence:** [periodic tests](../reports/ultimate/periodic-dynamics-tests.log), [native periodic evidence](../reports/ultimate/genomic-periodic-native-acceptance.json).

## 19. Genome Explorer and annotated sequence workflows

### Implemented input and navigation

The attributed reference workspace accepts FASTA with optional GFF3/GTF/BED intervals, GenBank/EMBL and supported gzip inputs. Exact originals are retained with source/checksum identity. Organism/strain, assembly/version and accession/source are explicit. Tracks show supplied overlapping annotations and strands, bounded zoom/navigation and circular-origin segments. No genes or missing transcript structure are invented.

Implemented sequence products include phase/strand/order-checked CDS assembly, explicit-exon transcript assembly, annotated noncoding-RNA assembly and Biopython translation with explicit genetic codes **1, 2 or 11**. Complete/partial handling is explicit, conflicting CDS codes are rejected, and separate stop-codon rows are not silently appended. Six-frame complete ORF enumeration retains nested starts and coordinates without asserting gene/function identity.

Bounded public NCBI search/review and pinned GenBank retrieval are integrated. Attributed condition/strain/citation-preserving gene-evidence CSV supports explicit lookup; absence of evidence is not inferred essentiality.

### Real reference evidence

- E. coli **NC_000913.3** ThrA, **337–2799 (+), 2,463 bases → 820 residues**, matches independent Biopython/original protein references.
- B. subtilis 168 **NC_000964.3**, **4,215,606 circular bases / 9,076 converted annotation rows**, has exact upstream plus/minus CDS comparisons and native GenBank import evidence.
- Mitochondrial **NC_012920.1** retrieval reproduced an annotated **513-residue** code-2 translation and independently compared a **71-base tRNA** extraction.

Latest public-retrieval/RNA-product forms have source/backend reference evidence; not every added form has a separate native click-through receipt. This distinction is preserved in the current checkpoint.

**Remaining:** whole-human-genome qualification, indexed annotation attachment, broad assembly discovery, unsupported BED blocks/symbolic variation and authentic condition-specific essentiality datasets. Numerical/reference reproduction is not biological gene-function or efficacy validation.

**Evidence:** [genome continuation status](../reports/ultimate/genome-continuation-status.json), [VCF/ORF native checks](../reports/ultimate/genome-vcf-native-acceptance.json), [public reference](../reports/ultimate/genome-public-reference-validation.json), [RNA extraction](../reports/ultimate/genome-annotated-rna-reference.json).

## 20. Indexed large FASTA and BGZF

Managed plain/BGZF FASTA import streams validation and hashing before indexing, retaining exact originals and separately checksummed FAI/GZI. The **8 GiB original/expanded limit is an admission bound, not a whole-genome benchmark**. Indexing/fetching uses pysam/HTSlib; one query is at most **100,000 bases**, with explicit circular/reverse coordinates. Source stat checks and rehash after metadata changes protect identities; index checks occur per query.

BGZF creates no permanent expanded reference copy. Ordinary gzip is refused explicitly. Original export and supported operational archive restoration preserve bytes/index identities. References above the archive’s **100 MiB per-member** limit must be exported separately.

Native genuine E. coli BGZF extraction returned the expected 2,463-base ThrA interval. Multi-block, circular, index-tampering and archive checks passed. Indexed intervals can be saved with provenance and explicitly handed to Biopython alignment or RNA review.

**Remaining:** indexed GFF/other annotations, remote range/reference resolution, arbitrary assembly discovery and human-scale performance qualification.

**Evidence:** [BGZF reference](../reports/ultimate/bgzf-reference-validation.json), [latest native acceptance](../reports/ultimate/bgzf-coverage-native-acceptance.json), [BGZF tests](../reports/ultimate/bgzf-genomic-io-tests.log).

## 21. FASTQ, pairwise alignment and SAM/BAM observations

| Tool | Working scope | Boundary |
|---|---|---|
| FASTQ inspection | Streaming strict four-line Phred+33 FASTQ/gzip, original bytes, per-cycle/aggregate quality and supported archives | No inferred error rate, trimming, paired synchronization or general sequencing pipeline |
| Pairwise alignment | Genuine Biopython DNA/RNA/protein global/local affine alignment, explicit scoring/orientation and checked interval handoffs | No whole-genome/long-read mapper, orthology or significance certification |
| SAM/BAM inspection | Actual header/flags/MAPQ/CIGAR parsing, exact original bytes, up to 32 MiB / one million records | No CRAM, alignment generation, expression or variant calling |
| A/C/G/T observations | Explicit header window, MAPQ/base-quality thresholds, unavailable-MAPQ choice, per-base arrays, shared cancellation and saved/exported provenance | Both primary mates count independently; no unique-molecule/fragment depth or assembly attestation |

Observation counting excludes flagged unmapped, secondary, supplementary, duplicate and QC-failed records. Missing qualities/ambiguous bases are not counted. Insertions/soft clips/deletions/skipped spans do not create observations. Known CIGAR fixtures and an independent `pysam.count_coverage` call agree.

The latest native synthetic BAM check returned **nine accepted observations across seven positions** in `chr:1–100`, mean **0.09**. It verifies arithmetic and integration only. The saved job completed and its source/result hashes were retained.

**Evidence:** [read tests](../reports/ultimate/sequence-reads-tests.log), [alignment tests](../reports/ultimate/sequence-alignment-tests.log), [genomic observation reference](../reports/ultimate/genomic-base-observation-reference.json), [native count](../reports/ultimate/bgzf-coverage-native-acceptance.json).

## 22. Variants, guides, base editing and prime editing

Reference-checked explicit-allele VCF import retains originals, REF/ALT/filter/genotype fields and position tracks. Symbolic/structural interpretation and genotype inference are not supplied. Explicit-CDS consequences and assembly/allele-checked Ensembl VEP SNV annotations are connected; one public reference returned three original transcript rows. These are annotations, not clinical classifications.

Actual cloud methods include pinned **Rule Set 3** activity inference, **BE-DICT** original per-base classifier outputs, **PRIDICT2** original model/fold groups and **Cas-OFFinder 2.4.1** sequence matching against explicit references. The PRIDICT2 official example yielded **765 complete candidate rows** with original HEK/K562 distinctions. Four Cas-OFFinder CPU references cover strand/mismatch/circular cases on a pinned E. coli genome.

Native forms include typed inputs, local review, separate upload/cost approvals, result/error/cancel controls, provenance and notebooks. BE-DICT probabilities are not measured editing fractions or complete haplotype distributions.

**Remaining:** further guide/editor/foundation methods, human whole-genome off-target qualification, broad cell-context benchmarks, editing-outcome sequencing (including complete CRISPResso2/MAGeCK-style workflows) and experimentally validated intervention ranking.

**Evidence:** [EditCraft completion](EDITCRAFT_COMPLETION_REPORT.md), [off-target engine](EDITCRAFT_OFFTARGET_ENGINE.md), [Modal qualification](EDITCRAFT_MODAL_QUALIFICATION.md), `reports/editcraft/model-validation.json` and variant/off-target receipts.

## 23. RNA Engineering and ribosome links

Genuine ViennaRNA MFE folding, partition function, centroid/MEA, base-pair probabilities and marginal unpaired accessibility have actual CPU evidence. Supplied-pair cofold supports strand-specific pairs and explicit energy-availability handling. A finite-INF reporting bug was corrected; the original erroneous receipt is retained and labelled rather than overwritten. Corrected numerical examples report unavailable no-pair energy and **−19 kcal/mol / eight interstrand pairs** for a complementary pair.

A public **1EHZ 76-base canonical-parent tRNA** workflow tested real secondary-structure-to-observed-3D selection. Canonical parent bases do not model modified-base thermodynamics. Exact mappings are required for structural selection; no predicted counterpart is invented when absent.

**Remaining:** further RNA interaction/foundation models, independent biological benchmarks, complete design/therapeutic workflows, modification-aware thermodynamics, full ribosome translation dynamics and general mechanistic simulation.

**Evidence:** [genome/RNA status](../reports/ultimate/genome-continuation-status.json), RNA and nucleic-acid receipts in `reports/editcraft/`, full EditCraft audit.

## 24. Single-cell and perturbation analysis

The genuine Scanpy path retains original H5AD, explicit raw-count checks and metadata, QC filters, normalization, variable genes, PCA, neighbors, seeded UMAP/Leiden and exploratory Wilcoxon cluster markers. The native result viewer supports provided metadata/gene colours, barcode search, selection/zoom, distributions/heatmaps, population sizes and separate user annotations. Processed H5AD retains original counts, metadata, parameters and package identities, with checksum-checked export.

Public PBMC3k execution started with **2,700 cells × 32,738 features**, retained **2,638 × 13,714**, and produced seven computational clusters. Processed-file/identity/count round trips and the actual **15,278,743-byte** export passed. The original failed format attempt is preserved alongside the separately approved correction.

**Remaining:** scvi-tools/Pertpy, CELLxGENE ingestion, real perturbation studies, donor-aware contrasts, batch correction/diagnostics, inferred cell types, multimodal inputs and independent biological benchmarks. This reference is not a tumor-microenvironment simulation or replicated perturbation experiment.

**Evidence:** [single-cell engine](EDITCRAFT_SINGLECELL_ENGINE.md), `reports/editcraft/singlecell-validation.json`, `native-singlecell-workflow.json`.

## 25. Systems Biology and pathway analysis

Implemented over-representation analysis requires selected genes, an explicit measured/testable background and attributed GMT collections. It retains all hypotheses, source/license/version context, log probabilities, underflow flags and BH/BY full-family adjustments. Native results provide membership inspection, comparison/figures and complete TSV export with attribution/hash preservation and spreadsheet-text protection.

The hypergeometric implementation agrees with finite enumeration and **111 independent SciPy cases**; a real approved CPU run tested both corrections on a labelled synthetic mathematical reference. Native p/BH/BY values of **0.008333… / 0.025 / 0.045833…** were verified. Saved Scanpy markers can enter a draft without inventing the testable background.

**Remaining:** authenticated curated Reactome/GO/STRING/BioGRID collection qualification, biological benchmarks, complete interaction/network topology, perturbation context and dynamic mechanistic systems. Enrichment is not activation or causation.

**Evidence:** [pathway engine](EDITCRAFT_PATHWAY_ENGINE.md), `reports/editcraft/pathway-numerical-reference.json`, [native/export evidence](../reports/ultimate/consolidated-native-acceptance.json).

## 26. Assays and experimental evidence

Assay CSV ingestion retains exact bytes and explicit endpoint, dose/response units, condition, group, biological unit and technical replicate identities. Summaries average technical replicates within biological units and retain the statistical unit; incompatible input is rejected. Notes, citations and candidate-linked evidence are stored separately from prediction claims.

The descriptive four-parameter logistic tool fits one selected group/direction with balanced biological units, retains original readings, and withholds unreliable midpoint estimates. Focused references recovered a known **5 nM midpoint / Hill 1.2**. Latest fit controls have numerical/backend evidence; their separate native acceptance is not claimed.

**Remaining:** complete experimental study design, general mixed-effects/longitudinal inference, robust parameter confidence intervals, broader dose/kinetic models and independent affinity/efficacy validation. A fitted midpoint is not automatically a binding constant, clinical effect or causal result.

**Evidence:** `scientific/assay_csv.py`, `assay_statistics.py`, `assay_fit.py`; [fit reference](../reports/ultimate/assay-fit-reference.json), [fit tests](../reports/ultimate/assay-fit-tests.log).

## 27. Registry, notebook, workflows, intelligence and publishing

Versioned entities/sequences, analyses, notes, experiments, workflow definitions, reports, attributed literature retrieval and notebook links are implemented. Search/version/history/export helpers exist. Source-linked handoffs connect several independent workspaces, including indexed intervals → alignment/RNA review and single-cell markers → enrichment draft.

The ordered workflow editor and bounded evolution controller do not yet constitute universal branching execution, cross-engine replay, calibrated research reasoning or an experimentally grounded causal/consequence graph. A catalogue of life-science/materials interests is not an executable method for every category. Specialized JSON/CSV/TSV/Markdown/PDF/figure/movie exports do not complete a collaborative scientific publishing suite.

**Remaining:** full typed graph/recovery/replay, complete registry relationships and identity enforcement across all engines, collaboration, publication bundles and original scientifically validated intervention/intelligence models.

## 28. Local development worker

The independent local worker provides durable SQLite tasks, atomic ownership, bounded logs/results, launchd/FIFO service control, resource/time governors, owned cancellation, exact-hash patching and optional bounded Aider/Ollama editing in review worktrees. Review/resume/rollback gates prevent automatic merge/push/app replacement or scientific campaign restart.

A real local coding fixture and a peptide-test task have scoped acceptance. That does not establish general autonomous coding accuracy, biological reasoning quality or a measured reduction in agent usage. Its current daemon state was not polled for this audit.

**Evidence:** [local worker](LOCAL_WORKER.md), `reports/local-worker-validation.json`.

## 29. Verification ledger — what passed, and what was not rerun

These are dated recorded batches. They overlap and **must not be added into a claimed current full-suite total**.

| Evidence batch | Recorded result / qualification |
|---|---|
| 26 October broad integration baseline | 742 backend tests and 143 interface tests recorded as passed; historical, not rerun today |
| Consolidated research/inspection batch | 18 backend / 21 interface checks; native archive review, 1BNA cell, gyration, ligand inspector/SDF and pathway TSV |
| Genome continuation | 56 backend passed / one optional SciPy skip; 11 interface checks; genuine CDS/RNA/navigation/import evidence |
| VCF / ORF follow-up | 23 backend / four interface checks; native VCF track and two-strand ORF execution |
| Public reference / RNA / assay | 22 public-reference and 14 assay checks (one optional SciPy skip); public sequence/fit references; some forms not separately native-executed |
| Quantum / reads / alignment / compounds | 15 focused backend / five interface/geometry checks; actual native H2 density, FASTQ, alignment and compound table; separate cancellation evidence |
| Indexed I/O / periodic continuation | Five genomic, three periodic, four quantum-admission and four alignment regression checks; two interface checks |
| Latest BGZF / observation batch | Eight BGZF/genomic + four observation checks; two interface checks; native extraction and count passed |
| Latest packaging | TypeScript, guarded build, 80-module import/resource closure and local signing passed |
| Today’s audit | 25 selected non-Fab installed/source file hashes match; no scientific suite/model job rerun |

Actual examples exercise algorithms, references and integration; they are not independent biological model benchmarks. A passing program test does not validate arbitrary research conclusions.

**Evidence:** current checkpoint and linked batch logs; [today’s exact identity checks](../reports/current-application-audit.json).

## 30. Security, data integrity, deployment and distribution

The single-build guard refuses replacement while app windows/scientific workers are active. Shared job admission and atomic result publication prevent some cancellation/admission races. Assets, scientific parameters, runtime/source hashes and original failed/rejected receipts are preserved within implemented workflows. Cloud upload/spend approvals remain separate from local review.

macOS Documents prompts can recur when the local signing hash changes. The safe launcher/installer reduces conflicting identities but does not eliminate privacy prompts. The latest final build reopened the original library successfully after access was allowed.

**Remaining:** exhaustive security/restore/migration review, universal credential/account/provider acceptance, current deployment/billing reconciliation, complete license/redistribution qualification and clean-machine distribution. Notarization remains intentionally deferred for local use. No signing credential was invented or bypassed.

Existing unrelated modified historical logs/receipts are not automatically new science or part of this audit’s changes. Private credentials and raw research data are not copied into this report.

## 31. What remains before the full vision is finished

1. Complete independent scientific qualification of existing protein modes and descendants, additional cloud ensembles and complementary generator coordination.
2. Real qualified BoltzGen/ESM/RFdiffusion execution, authentic ESMC design and licensed Rosetta workflows where requested and approved.
3. Validated docking/selectivity, broader screening/developability, force-field/simulation coverage and free-energy methods.
4. Indexed genomic annotations, human-scale/reference qualification, additional RNA/editor/foundation models and genuine experimental sequencing pipelines.
5. Real perturbation/donor-aware single-cell methods, curated biological pathways/networks and independent biological benchmarks.
6. Universal workflow/registry/recovery/collaboration/publishing, broader observatory acceptance and full end-to-end study demonstrations.
7. Broader quantum/materials/periodic methods and their domain references; current small-model calculations do not close those domains.
8. Fresh-machine/licensing/distribution acceptance and wider provider/account/GPU operations. Notarization remains deferred.
9. Fab stays outside the development scope until the user explicitly resumes it.

The current authoritative inventory preserves **1,933 legacy acceptance paragraphs**, **40 additional reviewed requirements** and all **100 Ultimate sections**. Semantic reconciliation is incomplete. Historical clause-review counts measure review work, not product completion. Neither unreviewed clauses nor test totals support a credible global percentage.

**Final finding:** a substantial, usable, multi-domain research application exists, with genuine local/cloud calculations and preserved scientific results. The complete accumulated specification is not finished or scientifically certified. The remaining work is recorded explicitly rather than hidden behind menus, model names or presentation quality.
