# Molecular Intelligence Lab · FOLD STUDIO 4.3.0

This release extends the existing application. It uses the same React/TypeScript interface, Tauri/Rust shell, Mol* renderer, separately installed ChimeraX 1.12 scientific runtime, Python service, SQLite library and Boltz MPS runner. No new external computation service or language-model dependency was added.

## Repository inspection and integration

| Existing component | Integration |
| --- | --- |
| `src/App.tsx` navigation and local library | Adds Research → Molecular Intelligence and selects saved structures from the current project. |
| `MolecularViewer.tsx` | Same Mol* component and authoritative ChimeraX atoms, colours and meshes. Side-by-side comparison reuses this component with read-only scene snapshots; it does not start another scientific session or register another main scene sink. |
| `scientific/worker.py`, Rust scientific IPC | Whitelisted Intelligence actions reuse the existing service and app data directory. Production has no new HTTP listener. |
| `scientific/observatory.py` | Existing authenticated headless ChimeraX transport supplies chemical atom radii, native clash checking, overlays, optional AddH preparation and native session saving. |
| Existing structure importer | PDB/mmCIF assets remain immutable and checksum verified. Predictions already in the library can be analysed without rerunning inference. |
| Existing prediction jobs | Sequential screening submits the existing `prediction_start` operation, uses its MPS capability/memory checks, stores its normal raw outputs, and supports cancellation/retry. Public MSA is an explicit screening setting; no paid backend is introduced. |
| Existing SQLite database | Adds assignments, versioned task/results, candidate/control sequences, confidence mappings and hotspot sets. Project archives include Intelligence metadata and result files. |
| Rendering technology | Mol* WebGL in the macOS webview. This application has no separate Metal/SceneKit renderer to replace. |
| Confidence storage | Existing Boltz jobs retain raw output directories and original filenames; existing pickle-free NPZ parsing is reused. |

## Using the workspaces

1. Open **Research → Molecular Intelligence** and select/import a structure.
2. In **Structure Inspector**, identify target and candidate/control chains explicitly. Save identities and roles. Optionally provide reference sequences and the biological number of reference position 1.
3. Choose contact/clash thresholds, radius method, surface resolution and a saved hotspot set. Click **Analyze prediction**. Calculations run in a separate worker; the task drawer exposes progress, errors, cancellation and retries.
4. **Interface Analyzer** separates atom contacts from unique residue pairs and atom clashes from clashing residue pairs. Clicking a row selects actual source-matched atoms, reveals nearby side chains and draws its measured distance. Ring-centroid approaches remain identified as centroid measurements.
5. **Reproducibility Lab** compares selected completed analyses after target fitting. It reports chain mappings, mapped residues, target RMSD, peptide positional versus internal RMSD, reference-interface RMSD, contact Jaccard, recurring contacts and complete-linkage pose clusters. Overlay and side-by-side views use the original renderer. Remove the overlay to restore previous model visibility.
6. **Peptide Screening** registers immutable sequences, imports/exports FASTA, imports explicitly assigned peptide chains from saved structures, and stores composition-matched scrambled controls with the seed and algorithm. Existing controls are not regenerated. Review the workload before starting a local batch.
7. Batch completion can queue analyses and per-candidate reproducibility comparisons automatically. The separate future-prediction toggle snapshots user-confirmed roles, reference sequences and analysis settings. Missing or conflicting input correspondence pauses automatic analysis with an explicit error instead of guessing a peptide from its filename.
8. **Molecular Explorer** exposes chain colours/visibility, representations, surfaces and contact selection. **Save view** creates an actual ChimeraX session that can be restored through the existing workspace controls.
9. **Research Reports** exports saved analysis JSON, CSV, Markdown and PDF, confidence/contact figures, molecular PNGs with provenance and whole-project candidate/control reports. The offline evidence assistant explains deterministic saved measurements and exposes supporting data. No AI model supplies numerical results.

## Scientific definitions

- Coordinates are in Å. Only one coordinate model is analysed per task; the default is the first model. Zero-occupancy atoms and waters are omitted. Alternate conformers use a consistent residue-level choice by summed occupancy, with a deterministic tie break.
- Sequence, chain composition, residue/atom counts, missing standard heavy atoms, numbering gaps, peptide C–N discontinuities and deviations from CCD ideal heavy-atom bond lengths are inspected. Unknown polymer identities remain explicit and disable automatic correspondence. Full-length/mature status is not inferred without reference metadata.
- Contacts are cross-partner heavy-atom Euclidean distances at or below the saved cutoff. Both atom-pair and unique residue-pair counts are preserved. Oversized analyses fail clearly rather than silently truncating results.
- Native clash mode uses fresh source-specific ChimeraX chemical atom radii and `clashes.find_clashes`, a four-bond exclusion and the saved overlap/hydrogen-bond allowance. Offline mode uses documented Bondi elemental radii without that allowance. Moderate/severe labels reflect the saved numeric overlap cutoffs. Counts from different criteria are not interchangeable.
- Potential H-bonds require supported donor/acceptor chemistry and explicit template-bonded hydrogen geometry. Missing-hydrogen approaches remain tentative. Hydrogen-bond networks are connected components of those geometric residue interactions, not energetic networks. Histidine/protonation ambiguities are not resolved by assuming every N–O proximity is a hydrogen bond.
- Salt bridges, nonpolar carbon approaches, planar aromatic-ring and cation–π screens retain their geometric criteria and tentative status. These are screens, not interaction energies. Electrostatic complementarity remains unavailable without a validated charge/protonation model.
- Optional ChimeraX AddH preparation imports a separate derived structure. Existing heavy atoms must survive within export precision. Native terminal-oxygen completion is recorded. Artificial crop termini, histidine and other protonation assumptions require review; confidence is carried forward only with verified residue lineage. Original assets are unchanged.
- SASA uses a deterministic Shrake–Rupley/Fibonacci implementation, elemental Bondi radii and a 1.4 Å default probe. The total area loss is SASA(target) + SASA(peptide) − SASA(complex). The conventional interface area is half that loss. Resolution is configurable and convergence matters. It is not an affinity estimate.
- pLDDT is extracted only from known prediction-confidence fields or explicitly imported arrays. Ordinary crystallographic B factors are not relabelled pLDDT. Boltz PAE token order must match saved input sequences and residue labels. Imported JSON requires an explicitly confirmed residue/token order. Directional summaries preserve source rows and columns. Missing arrays remain unavailable.
- Numbering correspondence uses a unique exact fragment or a unique global alignment (+2 match/−1 mismatch/−2 gap), retaining identical residues at ≥90% observed identity. Repeats/ambiguities are refused. A user may explicitly assert an individual hotspot correspondence; that assertion and the amino-acid check remain in the report. Precursor versus mature numbering is never silently conflated.
- Rigid fitting uses Horn unit quaternions with a symmetric Jacobi eigensolver and no reflection. Identical target-chain assignments are enumerated. Unique gapped correspondences are allowed; ambiguous/low-identity mappings are refused. Partial correspondence and symmetry alternatives must be reviewed. Reference-interface RMSD uses reference contacting residues after target fitting; it is not a symmetric docking quality score.
- Pose clustering uses deterministic complete linkage on target-aligned peptide positional Cα RMSD at the saved threshold. Multiple diffusion samples are not independent random seeds.
- Candidate/control summaries retain separate dimensions and source analysis IDs, deduplicate derived coordinate lineages, list known seeds and warn about incompatible criteria, comparable confidence/target contacts, shared hotspots, severe clashes and inconsistent pose clusters. No undocumented composite binding score is used.

## Persistence and recovery

Every analysis snapshots source SHA-256, atom/residue identities, assignments, thresholds, confidence sources, mappings, timestamps and calculation version. Reanalysis/retry creates a new result ID. Completed results are not rerun in place; modified result checksums are refused. Interrupted screen attempts retain the last prediction job, cursor and raw outputs. Cancellation is cooperative at safe boundaries; a native command already running finishes before cancellation is observed. Retrying a failed prediction starts a new existing-engine job and preserves the old files.

Project ZIP export includes Intelligence tables, result JSON, imported confidence assets and normal job output directories. Existing archive re-import is not implemented by this release; use ordinary structure/confidence imports or restore the original app data directory. Raw source files and old results are not silently overwritten.

## Verification

- The Python suite covers distances/cutoffs, residue-pair deduplication, clash overlaps, explicit-H angles, missing data, crop/deletion mapping, alternate conformers/models, Horn fitting, identical target-chain swaps, gapped fits, directional PAE, scalar confidence, permanent scrambling, source/result checksums, immutable results, actual background worker launch, retries, project exports and batch orchestration through the existing prediction interface.
- Frontend regression tests cover empty-startup safety alongside the existing sequence, geometry, engine-scene and camera-clipping tests.
- Optional reproducible reference check: run `python scripts/validate-intelligence-reference.py --structure your-structure.cif --points 960` in an environment with NumPy and Biopython. It records library versions and source SHA-256 and compares numerical algorithms on identical selected atoms.
- Thirty independent rigid fits agreed with NumPy SVD to approximately 1.8×10⁻¹⁵ Å RMSD in the checked cases. At 960 samples, sampled SASA differed from Biopython by approximately 0.10% for the checked complex; this is a bounded numerical cross-check, not universal scientific validation.
- Three private saved research outputs were checked against previously reported contact/hotspot measurements and installed ChimeraX clash criteria. Private coordinates, confidence files, screenshots and numeric acceptance reports remain outside the source repository.
- The macOS package was built, ad-hoc signed and launch-tested with a disposable library; the scientific helper remained GUI-free and source bytes/signature remained intact. This is not Developer ID notarization.
- UI checks exercised the Analyze action, interaction selection/measurement, saved comparison, aligned side-by-side views and report generation. Exhaustive hardware acceptance and all native extensions are not claimed.
- Fresh multi-seed Boltz inference was not started as part of this update. Queue orchestration is tested independently; real existing outputs were analysed. Screening still depends on the separately installed, working Boltz/MPS environment and adequate memory/model assets.

## Scope limits

Noncanonical chemical preparation, exhaustive protonation/tautomer assignment, free-energy/affinity prediction, experimentally established specificity and validated electrostatic complementarity are not supplied. Standard-residue interaction screens are conservative and disclose missing chemistry. Cross-model correspondence and permutation searches are bounded; comparisons support up to 20 analyses and 720 chain assignments. Pose transitions crossfade fixed aligned models; coordinate morphing, molecular-dynamics pathways and arbitrary upstream-tool parity are not supplied. No unavailable measurement is replaced with a synthetic value.

## Method sources

- Bondi (1964), van der Waals Volumes and Radii: https://doi.org/10.1021/j100785a001
- Shrake & Rupley (1973), solvent exposure of protein atoms: https://doi.org/10.1016/0022-2836(73)90011-9
- Horn (1987), absolute orientation using unit quaternions: https://doi.org/10.1364/JOSAA.4.000629
- Installed ChimeraX 1.12 supported `Atoms.default_radii`, `clashes.find_clashes`, AddH and geometry/model APIs; runtime separately licensed.
