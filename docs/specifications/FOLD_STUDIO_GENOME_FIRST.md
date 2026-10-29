# FOLD STUDIO Ω — GENOME-FIRST TOTAL IMPLEMENTATION DIRECTIVE
## ONE CONTINUOUS ENGINEERING SESSION
### Full Scientific Functionality First · Minimal UI · All Non-Fab Requirements · No Premature Stopping

# 0. YOUR MISSION

You are continuing development of Fold Studio Ω, an existing native macOS scientific research platform.

Repository:

`/Users/vii/Documents/FoldStudio-MetalPort/fold-studio`

**I want you to implement the entire remaining non-Fab scientific functionality of Fold Studio during one continuous execution session, as far as the available execution environment, permissions, dependencies and usage budget permit.**

This is an implementation mandate.

It is NOT a request for:

- Another comprehensive planning document.
- A beautiful interface.
- Animations.
- A visual redesign.
- Decorative dashboards.
- Placeholder scientific tools.
- Unnecessarily extensive architecture discussions.
- Repeated repository-wide audits.
- One tiny feature followed by a completion report.

**The priority is scientific functionality.**

I do not care if the unfinished interface looks ugly.

I would rather have 100 genuinely functional scientific operations with plain buttons, tables and text inputs than five beautifully designed features surrounded by unfinished systems.

Finish the underlying computational engines first.

Make them accessible through the minimum usable interface.

We will redesign and beautify Fold Studio later.

## The new implementation order

**Priority 0 — Genome & RNA Engineering Workspace**

**Priority 1 — Complete all existing scientific computational engines**

**Priority 2 — Connect all engines to minimally functional native controls**

**Priority 3 — Scientific validation, interoperability, workflow execution and research data integrity**

**Priority 4 — Production packaging and broad integration testing**

**Deferred — All visual redesign, aesthetics, animations and elaborate UI work**

**Excluded — All Fab-specific development**

Do not voluntarily stop when one batch is finished.

---

# 1. ABSOLUTE SCOPE EXCLUSIONS

## 1.1 No Fab development

Do not perform any Fab-specific:

- Local development.
- Cloud development.
- Gradient optimization.
- GPU benchmarking.
- Memory optimization.
- Model integration.
- Refolding.
- Debugging.
- Scientific evaluation.
- Execution.

Preserve all existing Fab code, historical experiments, checkpoints and data without modifying them.

General antibody sequence and structural analysis is permitted if independent of Fab-specific engineering.

Mark Fab requirements as `EXCLUDED_FROM_THIS_SESSION`, not complete or deleted.

## 1.2 No visual polish

Do not spend engineering time on:

- Liquid Glass.
- PS5-inspired visual effects.
- Apple TV-style transitions.
- Animated backgrounds.
- Glass shaders.
- Molecular cinematic decoration.
- Decorative icons.
- Typography redesign.
- Layout perfection.
- Custom theming.
- Animations unrelated to scientific data.
- Beautiful landing screens.

Preserve the existing UI without redesigning it.

Use ordinary HTML controls inside the existing React/Tauri app.

Acceptable interfaces include:

- Tabs.
- Lists.
- Tables.
- Textareas.
- Dropdowns.
- File selectors.
- Checkboxes.
- Plain forms.
- Basic charts.
- Basic interactive graphs.
- Raw scientific output panels.
- Buttons.
- Status logs.

If a scientific visualization is necessary to operate a feature, implement that visualization.

Scientific visualization is functionality; visual decoration is not.

Do not remove existing working graphical functionality merely because visual polish is deferred.

---

# 2. PRESERVE THE EXISTING APPLICATION

The codebase already contains substantial functioning infrastructure.

Preserve the existing:

- Tauri 2 native application.
- Rust IPC.
- React and TypeScript frontend.
- Python scientific backend.
- Mol* molecular viewer.
- ChimeraX integration.
- RDKit.
- OpenMM functionality.
- Existing protein-design engines.
- EditCraft scientific operations.
- Scanpy.
- Pathway analysis.
- SQLite Research Library.
- Modal cloud integration.
- RAPID infrastructure.
- Local worker.
- Scientific results.
- User projects.

Do not create a replacement application.

Do not replace functioning architectures unnecessarily.

Do not create multiple competing scientific registries.

Do not overwrite real research data.

Do not reimplement libraries merely to claim the functionality was written internally.

Reuse authentic, properly licensed, scientifically appropriate existing tools.

---

# 3. RESUME FROM THE CURRENT REPOSITORY STATE

Before modifying code, inspect:

`AGENTS.md`

`FOLD_STUDIO_IMPLEMENTATION_AUDIT.md`

`docs/CURRENT_IMPLEMENTATION_CHECKPOINT.md`

`reports/ultimate/implementation-batch.json`

`docs/EDITCRAFT_FULL_COMPLETION_AUDIT.json`

Other existing scientific implementation manifests and master specifications where relevant.

Inspect current Git HEAD and the working tree.

The latest reported implementation included:

- GMT collection import.
- Pathway membership graph.
- SVG pathway export.
- JSON pathway export.
- TSV pathway export.
- Trajectory Cα radius of gyration.
- Ligand/conformer inspection.
- SDF export.
- Read-only archive integrity checks.
- Crystallographic unit-cell inspection/export.

Previously reported commits include:

`01a9904`

`b706727`

Treat these as historical references, not proof of current HEAD.

Do not recreate already implemented functionality.

Do not discard unrelated uncommitted files.

Do not re-read the entire 1,933-requirement audit after every task.

Use the full existing specification as the authoritative backlog, reconcile newer addenda, and proceed directly into implementation.

---

# PART I — PRIORITY ZERO: COMPLETE GENOME WORKSPACE

# 4. BUILD A FULL GENOME RESEARCH LABORATORY

This is the most important new requirement.

I want to open Fold Studio, choose or import an organism, load its genome and conduct computational genomic research through a complete, working scientific workspace.

I want to study:

- Bacteria.
- Nonpathogenic model organisms.
- Eukaryotic organisms.
- Human reference genomes.
- DNA viruses and other supported reference sequences for legitimate comparative research.
- Microbial communities where supported.
- Organellar genomes.
- Plasmids.
- Individual chromosomes.
- Genes.
- Transcripts.
- Regulatory regions.
- RNA molecules.
- Proteins.
- Variants.
- Gene expression.
- Biological pathways.

The workspace must support real genome data, not simulated UI placeholders.

## 4.1 Organism selection

Create a minimally functional organism selector.

Support:

- Taxonomic name.
- Taxonomy identifier.
- Strain designation.
- Reference assembly.
- Assembly version.
- Chromosome/replicon identifiers.
- Genome length.
- Organism classification.
- Reference source.
- Assembly quality metadata.

Allow the user to search and retrieve supported public reference genomes from authoritative sources such as NCBI or Ensembl where available.

Allow local file import.

Make the scientific identity of the organism explicit.

## 4.2 Genome formats

Support appropriate genuine import and parsing for:

- FASTA.
- FASTQ where relevant.
- GenBank.
- EMBL.
- GFF3.
- GTF.
- BED.
- VCF.
- Relevant compressed formats.
- BAM/CRAM through appropriate genomic libraries where available.
- GFA or other appropriate assembly graph representations where supported.

Preserve original files and hashes.

Do not invent gene annotations for an unannotated sequence.

## 4.3 Bacterial genome support

Bacterial genomes require explicit handling of:

- Circular chromosomes.
- Linear chromosomes.
- Multiple replicons.
- Plasmids.
- Genes on both DNA strands.
- Overlapping coding sequences.
- Operons.
- Promoters.
- Transcription terminators.
- Ribosome-binding regions.
- Noncoding RNAs.
- Small regulatory RNAs.
- Antisense RNAs.
- RNA structures.
- Coding sequences.
- Protein products.
- Gene essentiality annotations where available.

Correctly handle coordinates spanning circular-genome boundaries.

Do not use assumptions that apply only to eukaryotic genomes.

## 4.4 Genome browser

Create a functional genome browser supporting:

- Chromosome selection.
- Zooming by genomic coordinates.
- Navigation to a gene.
- Search by gene name.
- Search by sequence.
- DNA strand display.
- Forward/reverse complement.
- Gene tracks.
- CDS tracks.
- RNA tracks.
- Regulatory annotations.
- Variant tracks.
- Sequence selection.
- Coordinate export.
- FASTA export.
- Feature inspection.

A simple, performant genome track viewer is sufficient.

It does not need to look beautiful.

Prioritize scientific correctness, large-sequence performance and responsive navigation.

## 4.5 Gene and transcript inspector

Selecting a gene must display:

- Gene identifier.
- Gene name.
- Organism.
- Assembly.
- Chromosome.
- Start/end positions.
- Strand.
- Gene function.
- DNA sequence.
- RNA transcript sequence where applicable.
- Coding sequence.
- Protein sequence where applicable.
- Feature annotations.
- Relevant public evidence.
- Gene essentiality evidence where available.
- Regulatory context.
- Relevant literature.

Support copying, exporting and saving selected entities.

## 4.6 Sequence engine

Implement genuine:

- DNA analysis.
- RNA analysis.
- Reverse complement.
- Translation.
- ORF detection.
- Sequence composition.
- GC content.
- Motif search.
- Sequence alignment.
- Local sequence search.
- Reference mapping.
- Coordinate conversion.
- Sequence annotation.
- Genomic region extraction.
- Protein sequence comparison.
- RNA secondary-structure analysis.

Reuse Biopython, appropriate alignment libraries and existing scientific dependencies.

Provide focused reference tests.

---

# 5. PRIORITY ZERO — BACTERIAL RNA RESEARCH WORKSPACE

## 5.1 Scientific objective

I want a research workflow where I can select a bacterial reference organism, inspect its genome and investigate whether RNA-targeting strategies might interfere with biologically important bacterial transcripts.

For example, I want to explore the scientific question:

**Which RNA targets and RNA-based interaction hypotheses might be relevant to investigating antibacterial effects in a particular nonpathogenic model bacterium?**

This is a computational research question.

The software must not confuse a predicted RNA interaction with demonstrated bacterial killing.

It must support rigorous target analysis, published evidence, nonpathogenic reference models, computational RNA interactions and clearly labeled experimental uncertainty.

Do not autonomously generate synthesis-ready lethal constructs for pathogenic organisms or provide operational delivery/experimental deployment workflows.

## 5.2 Reference organisms

Begin qualification with established nonpathogenic laboratory model references, such as:

- *Escherichia coli* K-12 MG1655.
- *Bacillus subtilis* 168.

Use genuine reference genome records, versions and available public annotations.

Do not fabricate genes or sequences.

## 5.3 Gene essentiality evidence

Build a research interface for examining:

- Genes with published essentiality evidence.
- Experimental knockout/fitness datasets.
- Gene function.
- Functional annotations.
- Pathway membership.
- Conservation.
- Organism/strain specificity.
- Experimental conditions.
- Source publications.
- Evidence uncertainty.

Distinguish experimentally measured essentiality from inferred importance.

Gene essentiality under one condition does not automatically establish essentiality under another.

## 5.4 RNA-target interaction analysis

Provide a computational laboratory for analyzing RNA sequences and their interactions with selected transcripts.

Support applicable:

- RNA sequence inspection.
- Secondary-structure prediction.
- Target-region accessibility analysis.
- RNA–RNA interaction prediction.
- Complementarity analysis.
- Thermodynamic estimates.
- RNA structural ensembles.
- Candidate interaction comparison.
- Sequence specificity analysis.
- Cross-organism sequence matching.
- Relevant off-target annotations.
- Literature-supported interaction evidence.

Investigate and integrate scientifically appropriate tools such as:

- ViennaRNA.
- RNAduplex.
- RNAcofold.
- IntaRNA.
- RNAhybrid.
- RNAstructure.
- Other properly validated RNA analysis tools.

Use actual calculations where the method is supported.

Do not combine incompatible thermodynamic scores.

## 5.5 RNA candidate research records

Create a functional workspace where a scientist can:

1. Select an approved nonpathogenic model organism.
2. Select a genomic region or transcript.
3. Inspect its annotation and essentiality evidence.
4. Import or reference an RNA interaction hypothesis.
5. Evaluate RNA secondary structure.
6. Evaluate predicted RNA–RNA interactions.
7. Compare candidate hypotheses.
8. Inspect relevant specificity and conservation evidence.
9. Record the limitations of each prediction.
10. Export a reproducible computational analysis report.

Candidate records must include:

- Organism and strain.
- Genome assembly.
- Transcript identity.
- Sequence source.
- Analysis method.
- Software version.
- Reference coordinates.
- Prediction output.
- Model assumptions.
- Uncertainty.
- Evidence type.
- Scientific limitations.

## 5.6 Biological interpretation

Explicitly distinguish:

**RNA complementarity**

**Predicted binding**

**Predicted target accessibility**

**Possible interference with gene expression**

**Measured transcript suppression**

**Measured growth inhibition**

**Experimentally demonstrated bactericidal activity**

These are not interchangeable endpoints.

Do not output an unsupported claim that an RNA sequence will kill a bacterium.

No computational score alone establishes antibacterial efficacy.

## 5.7 RNA biology distinctions

The application must distinguish:

- Bacterial small regulatory RNAs.
- Bacterial antisense RNAs.
- RNA interference mechanisms in organisms where applicable.
- CRISPR guide RNAs.
- Cas13-associated RNA targeting.
- ADAR-mediated RNA editing.
- General RNA secondary-structure prediction.
- RNA interaction analysis.

Do not apply mammalian RNAi assumptions directly to bacterial biology.

## 5.8 Minimal interface

Create one plain section named:

**Genome & RNA Laboratory**

Minimum tabs:

- Organisms.
- Genome Browser.
- Genes & Transcripts.
- Sequence Analysis.
- RNA Interactions.
- Target Evidence.
- Experiments.
- Saved Results.

No visual redesign is required.

Every tab must perform real operations.

---

# 6. GENOME WORKSPACE ACCEPTANCE TEST

The Priority Zero genome workspace is not complete until the following real workflow works:

1. Open Fold Studio.
2. Select a supported nonpathogenic bacterial reference.
3. Load or import its genuine genome.
4. Verify assembly identity and sequence length.
5. Inspect the chromosome and annotated genes.
6. Search for a gene by identifier.
7. Display its exact sequence and strand.
8. Display corresponding transcripts or coding sequences where annotated.
9. Display relevant published functional and essentiality evidence.
10. Inspect RNA secondary structure using a real calculation.
11. Analyze a supplied or literature-described RNA interaction hypothesis against an appropriately supported transcript.
12. Report actual predicted interaction metrics with units and limitations.
13. Save the result into the Research Library.
14. Reopen the saved result.
15. Export a reproducibility package with input hashes, assembly identity, method version and scientific outputs.

The native interface may be visually basic.

The underlying functionality must be real.

---

# PART II — COMPLETE EDITCRAFT

# 7. GENOME EDITING COMPUTATIONAL ENGINE

Preserve the current genuine EditCraft operations.

Finish suitable research workflows for:

- CRISPR-Cas9 analysis.
- Applicable Cas12 systems.
- Guide activity modeling.
- Off-target analysis.
- Genome assembly-aware interpretation.
- Sequence and PAM context.
- CRISPRi.
- CRISPRa.
- Regulatory sequence research.
- Base editing.
- Prime editing.
- RNA editing.
- Cas13-related analysis.
- ADAR-related analysis.
- Variant annotation.
- Gene regulation.
- Transcript effects.

Investigate scientifically supported methods, including:

- Rule Set 3.
- Cas-OFFinder.
- CRISPOR.
- CHOPCHOP.
- CRISPick.
- GuideScan2.
- Relevant published guide scoring models.
- BE-DICT.
- BE-Hive.
- DeepBE.
- PRIDICT2.
- PrimeDesign.
- DeepPrime.

Use verified model-specific interfaces.

Do not claim unavailable predictors are installed.

Do not generate actionable pathogen-directed constructs or harmful biological enhancement workflows.

## 7.1 Base editing

Implement proper handling of:

- Editor identity.
- Sequence context.
- Reference alleles.
- Predicted conversion patterns.
- Bystander outcomes.
- Compatible model scores.
- Reference data.
- Scientific uncertainty.

## 7.2 Prime editing

Implement:

- Reference validation.
- Variant identity.
- Editor-specific modeling.
- Compatible published predictors.
- Predicted outcome comparisons.
- Model provenance.
- Appropriate experimental reference validation.

## 7.3 RNA research

Complete:

- ViennaRNA integration.
- RNAstructure.
- NUPACK where accessible.
- IntaRNA.
- RNAhybrid.
- RNA-FM where genuinely available.
- RNA folding.
- RNA interaction analysis.
- RNA accessibility.
- Transcript annotations.
- Alternative splicing research.
- mRNA structure.
- RNA sequence conservation.

## 7.4 Genomic foundation models

Investigate legitimate access to:

- SpliceAI.
- Pangolin.
- Enformer.
- AlphaGenome.
- Suitable public genomic foundation models.

Implement genuine inference or explicitly labeled retrieval of precomputed model results.

Respect access restrictions.

## 7.5 Variant intelligence

Support:

- SNVs.
- Indels.
- Missense variants.
- Nonsense variants.
- Frameshifts.
- Splice-associated variation.
- Regulatory variation.
- HGVS where appropriate.
- VEP-compatible annotation.
- Transcript-specific consequences.
- Protein consequences.
- Public clinical evidence.

Do not equate predicted consequence with clinical pathogenicity.

## 7.6 Experimental genome analysis

Integrate scientifically appropriate:

- FASTQ QC.
- Read alignment.
- BAM/CRAM inspection.
- VCF interpretation.
- CRISPResso2.
- MAGeCK.
- Relevant experimental editing summaries.

Retain measured and predicted outcomes separately.

---

# PART III — COMPLETE BIOLOGICAL CONTEXT AND SYSTEMS BIOLOGY

# 8. BIOLOGICAL CONTEXT ATLAS

Integrate attributable data where available from:

- NCBI.
- Ensembl.
- UniProt.
- GTEx.
- Human Protein Atlas.
- Open Targets.
- ClinVar.
- gnomAD.
- CELLxGENE.
- Reactome.
- Gene Ontology.

Support:

- Gene identity.
- Transcript identity.
- Genome assembly.
- Protein function.
- Tissue expression.
- Cell-type expression.
- Variants.
- Biological pathways.
- Disease associations.
- Published experimental evidence.
- Organism context.

Every result must retain its source.

# 9. SINGLE-CELL LABORATORY

Preserve verified Scanpy and H5AD work.

Complete:

- Real UMI count analysis.
- Quality control.
- Normalization.
- Dimensionality reduction.
- PCA.
- UMAP.
- Clustering.
- Differential expression.
- Donor-aware comparisons.
- Batch analysis.
- Cell-type annotation.
- scvi-tools where supported.
- Pertpy where supported.
- Perturbation analysis.
- Multimodal data handling where supported.
- Export of processed datasets.

Minimum interface: datasets, parameters, run, results and basic plots.

# 10. PATHWAY LABORATORY

Preserve existing GMT and pathway exporters.

Complete:

- Reactome integration.
- Gene Ontology.
- STRING.
- BioGRID.
- Gene-set libraries.
- Enrichment statistics.
- Multiple-testing correction.
- Pathway networks.
- Gene-to-pathway membership.
- Interaction evidence.
- Experiment-linked pathways.
- Basic network visualization.
- Result export.

Do not equate enrichment with causality or pathway activation.

# 11. BIOLOGICAL CONSEQUENCE GRAPH

Implement a real evidence-aware graph connecting:

- Gene.
- Variant.
- Regulatory element.
- Transcript.
- RNA.
- Protein.
- Molecular interaction.
- Cell type.
- Tissue.
- Pathway.
- Experiment.
- Disease association.
- Observed result.
- Computational prediction.

Preserve edge provenance, evidence type, organism, context and uncertainty.

A plain interactive graph is sufficient.

---

# PART IV — PROTEIN ENGINEERING

# 12. PROJECT METAL

Complete supported non-Fab local calculations:

- Numerical parity.
- Model loading.
- Precision checks.
- Forward/backward validation.
- Resource admission.
- Memory guards.
- Cancellation.
- Reproducibility.
- Error handling.
- Result import.

No excluded Fab work.

# 13. BINDCRAFT ARCHITECT

Finish actual supported:

- Structure import.
- Target selection.
- Chain/residue selection.
- Hotspots.
- Fixed positions.
- Protected amino acids.
- Allowed/excluded amino acids.
- Design-length settings.
- Negative-target evaluation.
- Scientific strategies.
- Loss configuration.
- Candidate generation.
- Filters.
- Ranking.
- Campaign persistence.
- Result comparison.

No decorative UI development.

# 14. PROTEINMPNN AND SOLUBLEMPNN

Complete:

- Genuine model execution.
- Fixed-position redesign.
- Multichain handling.
- Candidate lineage.
- Model provenance.
- Independent redesign branches.
- Sequence/structure correspondence.
- Fresh structural evaluation.
- Reference tests.

# 15. ALPHAFOLD EVALUATION

Complete:

- Supported AF2 workflows.
- Monomer evaluation.
- Multimer evaluation.
- Held-out predictions.
- Confidence metrics.
- PAE.
- pLDDT.
- pTM.
- i_pTM.
- RMSD.
- Interface RMSD.
- Structural comparisons.
- Candidate clustering.
- Uncertainty-aware interpretation.

# 16. OTHER PROTEIN ENGINES

Complete technically accessible integrations of:

- BoltzGen.
- Relevant Boltz-family models.
- RFdiffusion.
- RFdiffusion3 where available.
- ESMFold2.
- ESMC-compatible methods.
- Rosetta where licensed.
- Appropriate independent evaluators.

Do not implement fake inference.

Do not automatically download large checkpoints.

# 17. MULTI-ENGINE DESIGN

Complete the RAPID non-Fab protein evolution system:

- Candidate identities.
- Immutable lineage.
- Generator handoffs.
- Sequence redesign.
- Fresh refolding.
- Independent evaluation.
- Structural filtering.
- Diversity analysis.
- Candidate clustering.
- Pareto selection.
- Model disagreement.
- Appropriate matched controls.
- Reproducible ranking.
- Resource-aware execution.

---

# PART V — MOLECULAR OBSERVATORY

# 18. FULL MOLECULAR VIEWER FUNCTIONALITY

Complete:

- Assembly hierarchy.
- Chain selection.
- Residue selection.
- Nucleotide selection.
- Atom inspection.
- Ligand inspection.
- Molecular isolation.
- Hide/show.
- Focus.
- Camera control.
- Measurement persistence.
- Structural export.

## 18.1 Representations

Support functional:

- Lines.
- Sticks.
- Ball-and-stick.
- Space filling.
- Ribbon.
- Cartoon.
- Backbone.
- Nucleic-acid representations.
- Molecular surfaces.
- Density overlays.
- Mixed representations.

## 18.2 Coloring

Support:

- Atom.
- Element.
- Chain.
- Residue.
- Nucleotide.
- B-factor.
- Occupancy.
- Model confidence.
- Secondary structure.
- Electrostatic property where calculated.
- User selection.

## 18.3 Molecular measurements

Implement:

- Distances.
- Angles.
- Dihedrals.
- RMSD.
- RMSF.
- Radius of gyration.
- Surface area.
- Molecular contacts.
- Interaction geometry.

## 18.4 Interactions

Support appropriate:

- Hydrogen bonds.
- Salt bridges.
- Hydrophobic contacts.
- Aromatic interactions.
- Steric clashes.
- Metal coordination.
- Protein–ligand contacts.
- Protein–DNA contacts.
- Protein–RNA contacts.

## 18.5 Ribosome

Preserve real PDB 4V9D representation.

Ensure:

- Protein-only viewing.
- RNA-only viewing.
- Subunit isolation.
- rRNA selection.
- tRNA selection.
- Individual nucleotide inspection.
- Structural metadata.
- Restoration of complete assembly.

## 18.6 Advanced viewing

Implement functioning:

- Structural superposition.
- Pose comparison.
- Density map import.
- MRC/CCP4 support.
- Isosurfaces.
- Clipping.
- Electrostatic maps.
- Crystal unit cells.
- Trajectory playback.
- DNA/RNA structure inspection.
- Ligand conformer inspection.
- ChimeraX-supported commands.

Only implement graphics enhancements required for scientific use.

---

# PART VI — SMALL-MOLECULE SCIENCE

# 19. CHEMICAL STRUCTURE LABORATORY

Complete RDKit-based:

- SMILES.
- InChI where supported.
- 2D structures.
- Chemical editing.
- Atom/bond changes.
- Stereochemistry.
- Conformer generation.
- Descriptors.
- Fingerprints.
- Substructure search.
- Similarity.
- Compound registration.
- SDF/MOL export.
- Identity validation.

# 20. MOLECULAR DOCKING

Investigate accessible:

- AutoDock Vina.
- Smina.
- Gnina.

Complete genuine:

- Receptor preparation.
- Ligand preparation.
- Docking box configuration.
- Pose generation.
- Scoring provenance.
- Pose inspection.
- Interaction analysis.
- Appropriate benchmark tests.

# 21. VIRTUAL SCREENING

Implement:

- Compound libraries.
- Structure validation.
- Duplicate filtering.
- Descriptor filters.
- Batch screening.
- Ranking.
- Diversity analysis.
- Candidate comparison.
- Result persistence.
- Export.

# 22. LEAD OPTIMIZATION

Implement:

- Molecular analog comparison.
- SAR.
- Matched molecular pairs.
- Property comparisons.
- Experimental assay evidence.
- Candidate lineage.
- Multi-objective analysis.

# 23. PHARMACOPHORES

Support genuine:

- Donor/acceptor features.
- Aromatic features.
- Charged features.
- Hydrophobic features.
- Spatial constraints.
- 3D feature inspection.
- Compatible screening.

# 24. ADMET AND PREDICTIVE TOXICOLOGY

Complete accessible:

- RDKit descriptors.
- Endpoint-specific QSAR.
- Structural alerts.
- Solubility modeling.
- Permeability-related prediction.
- Applicable toxicity endpoints.
- Model applicability domain.
- Uncertainty.
- Benchmarking.

Do not claim clinical safety from computational predictions.

---

# PART VII — MOLECULAR DYNAMICS AND PHYSICAL CHEMISTRY

# 25. MOLECULAR DYNAMICS

Complete relevant:

- OpenMM.
- GROMACS where accessible.
- Applicable LAMMPS workflows.

Implement:

- System setup.
- Topology validation.
- Force fields.
- Solvation.
- Minimization.
- Equilibration.
- Trajectory generation.
- Checkpointing.
- Trajectory import.
- RMSD.
- RMSF.
- Radius of gyration.
- Contacts.
- Hydrogen-bond occupancy.
- Conformational clustering.
- Convergence analysis.

# 26. FREE ENERGY

Implement scientifically supported:

- Molecular mechanics energy.
- MM/GBSA-like research.
- Thermodynamic integration.
- Appropriate alchemical methods.
- Uncertainty estimation.
- Convergence checks.
- Reference comparisons.

Do not represent docking scores as binding free energies.

# 27. QUANTUM CHEMISTRY

Investigate and integrate accessible:

- PySCF.
- CP2K.
- GPAW.
- Quantum ESPRESSO.

Support relevant:

- Electronic structure.
- Molecular orbitals.
- Electron density.
- Electrostatic potential.
- Energy calculations.
- Geometry optimization.
- Vibrational analysis.
- Molecular property calculations.

---

# PART VIII — BIOLOGICS, ENZYMES AND PEPTIDES

# 28. NON-FAB ANTIBODY RESEARCH

Complete:

- Sequence annotation.
- Chain identification.
- CDR numbering.
- Framework regions.
- Structural visualization.
- Antigen interface analysis.
- Candidate comparison.
- Stability/developability research.

# 29. BIOLOGICS

Support:

- Therapeutic proteins.
- Nanobodies.
- Fusion proteins.
- Enzymes.
- Peptides.
- Multimeric complexes.
- Protein interactions.
- Stability-related analysis.
- Experimental evidence.

# 30. ENZYME ENGINEERING

Complete:

- Active-site inspection.
- Catalytic residue annotation.
- Substrate interaction analysis.
- Sequence conservation.
- Protein mutation comparison.
- Structural analysis.
- Experimental activity comparisons.
- Relevant energetic analysis.

# 31. PEPTIDE RESEARCH

Complete:

- Linear peptides.
- Cyclic peptides.
- Disulfide-constrained peptides.
- Modified residue handling.
- Conformer analysis.
- Protein–peptide complexes.
- Candidate comparison.
- Chemical validity.
- Experimental evidence integration.

---

# PART IX — MATERIALS SCIENCE

# 32. MATERIALS LABORATORY

Implement real support for:

- Crystals.
- Unit cells.
- Periodicity.
- Polymers.
- Surfaces.
- Slabs.
- Interfaces.
- Defects.
- Materials trajectories.
- Atomic structures.
- Electronic structure outputs.

## 32.1 Scientific engines

Investigate and integrate:

- ASE.
- pymatgen.
- spglib.
- phonopy.
- LAMMPS.
- Quantum ESPRESSO.
- CP2K.
- GPAW.
- PySCF.
- AiiDA.
- atomate2.

## 32.2 Crystal operations

Complete:

- CIF import.
- Lattice parameters.
- Lattice vectors.
- Space groups.
- Symmetry.
- Unit-cell inspection.
- Periodic replication.
- Crystal comparison.
- Defect annotation.
- Slab structures.
- Materials export.

## 32.3 Materials simulation

Complete accessible:

- Classical atomistic simulation.
- Structural optimization.
- Electronic structure workflows.
- Phonon analysis.
- Surface research.
- Materials property analysis.
- Suitable molecular dynamics.

## 32.4 Materials machine learning

Support:

- Dataset import.
- Materials descriptors.
- Feature generation.
- Model training/inference where available.
- Cross-validation.
- Uncertainty.
- Applicability domains.
- Scientific provenance.

---

# PART X — ALL REQUESTED RESEARCH DOMAINS

# 33. LIFE SCIENCE CATEGORIES

Every previously requested category must have real functionality or an explicitly identified scientific dependency:

- Antibody Design, excluding Fab-specific development.
- Biologics Drug Discovery.
- Crystal Structure Prediction — Formulations.
- Drug Formulation — Biologics.
- Drug Formulation — Small Molecule.
- Enterprise Informatics and Team Collaboration.
- Enzyme Engineering.
- Hit Identification and Virtual Screening.
- Lead Optimization.
- Molecular Visualization.
- Peptide Design.
- Predictive Toxicology.
- Protein Engineering.
- PyMOL interoperability.
- RNA / DNA Design.
- Small Molecule Drug Discovery.
- Structural Prediction and Target Enablement.

Do not implement category labels alone.

# 34. MATERIALS SCIENCE CATEGORIES

Preserve and support:

- ALD / CVD / Etch.
- Batteries & Fuel Cells.
- Bio-based Materials.
- Catalysis & Reactivity.
- Cleaning Products.
- Crystal Structure Prediction — Formulations.
- Enzyme Engineering.
- Food & Beverage.
- High Energy Materials — safe, non-operational characterization only.
- Metals, Alloys & Ceramics.
- Organic Electronics.
- Packaging.
- Personal Care.
- Pharmaceutical Formulations.
- Photovoltaics.
- Polymeric Materials.
- Other.

Shared categories must retain both domain memberships.

# 35. MATERIALS DEVICES

Support appropriate research and import of evidence for:

- Batteries.
- Fuel cells.
- OLEDs.
- Solar cells.
- Thin films.
- Layered electronic devices.

Implement basic structural and property views rather than decorative illustrations.

---

# PART XI — RESEARCH INFRASTRUCTURE

# 36. RESEARCH LIBRARY

Complete:

- Versioned records.
- Scientific identities.
- Original asset preservation.
- Checksums.
- Metadata.
- Search.
- Associations.
- Import.
- Export.
- Project archives.
- Transactional re-import.
- Duplicate handling.
- Conflict resolution.
- Recovery.
- Referential integrity.

Safe archive re-import remains a priority.

Do not overwrite original user research.

# 37. SCIENTIFIC REGISTRY

Provide connected:

- Organism registry.
- Genome assembly registry.
- Gene registry.
- Transcript registry.
- Variant registry.
- RNA registry.
- Protein registry.
- Compound registry.
- Structure registry.
- Materials registry.
- Experiment registry.

Every entity must have stable identity, provenance and suitable version information.

# 38. SCIENTIFIC NOTEBOOK

Implement functional:

- Notes.
- Mathematics.
- Tables.
- Figures.
- Data references.
- Scientific citations.
- Saved analyses.
- Model parameters.
- Search.
- Tags.
- Project linking.
- Versioning.

Ugly but functional is acceptable.

# 39. VISUAL WORKFLOW STUDIO

Complete genuine:

- Workflow nodes.
- Typed ports.
- Directed connections.
- Dependency validation.
- Branching.
- Parallel stages.
- Scientific execution.
- Logs.
- Cancellation.
- Checkpoints.
- Recovery.
- Reproducible reruns.

A basic graph editor is enough.

# 40. SCIENTIFIC PUBLISHING

Provide genuine exports:

- PDF.
- DOCX.
- Markdown.
- CSV.
- TSV.
- JSON.
- Scientific figures.
- FASTA.
- GenBank where supported.
- Molecular structures.
- Materials files.
- Reproducibility manifests.
- Research archives.

# 41. COLLABORATION

Implement where realistically supported:

- Project sharing.
- Role-based access.
- Review status.
- Comments.
- Change history.
- Audit logs.
- Conflict-safe synchronization.

No fake multiuser claims.

---

# PART XII — SCIENTIFIC INTELLIGENCE CORE

# 42. SCIENTIFIC CAPABILITY ROUTER

Build a capability-aware router that knows which scientific engines are:

- Missing.
- Installed.
- Configured.
- Executable.
- Scientifically tested.
- Reference validated.
- Independently benchmarked.
- Available for native workflows.

Do not claim that package installation equals a working scientific capability.

# 43. SCIENTIFIC MODEL ORCHESTRATION

Support:

- Model-specific input validation.
- Scientific endpoint identity.
- Units.
- Source provenance.
- Uncertainty.
- Model disagreement.
- Compatible result comparison.
- Candidate histories.
- Experiment-linked predictions.
- Research controls.
- Appropriate resource selection.

# 44. BIOLOGICAL AND CHEMICAL INTELLIGENCE

Develop scientifically grounded integrations across:

- Genome.
- Transcript.
- RNA.
- Protein.
- Molecular structure.
- Chemical compound.
- Biological pathway.
- Cell type.
- Experiment.
- Materials structure.

Build actual analytical functionality, not speculative autonomous claims.

# 45. RESEARCH EVIDENCE AND UNCERTAINTY

Distinguish:

- Observation.
- Experimental measurement.
- Curated fact.
- Statistical association.
- Model prediction.
- Hypothesis.
- Independently reproduced result.

Preserve separate evidence identities.

Never combine incompatible confidence metrics into a universal scientific certainty score.

---

# PART XIII — CLOUD COMPUTING

# 46. COMPLETE RAPID CLOUD ENGINEERING

Preserve Modal.

Complete:

- Job creation.
- Authenticated execution.
- Runtime versions.
- Model assets.
- Persistent artifacts.
- Logs.
- Job status.
- Cancellation.
- Recovery.
- Resource estimates.
- Cost estimates.
- Actual billing attribution where available.
- Result import.
- Reproducibility records.

# 47. MULTI-PROVIDER INFRASTRUCTURE

Complete supported:

- Modal.
- Authorized SSH compute.
- Approved Vast infrastructure.
- Compatible cloud workers.
- Account isolation.
- Secret management.
- Scientific artifact transfer.

# 48. COMPUTE ECONOMY

Do not start paid compute without approval.

Do not download large models without authorization.

Reuse existing checkpoints.

Reuse verified cached assets.

Avoid unnecessary repeated inference.

Record actual costs separately from estimates.

---

# PART XIV — LOCAL ENGINEERING AND AGENTS

# 49. AGENT USAGE POLICY

Do not use GPT subagents.

If this session is running in Google Antigravity, use the selected Gemini model and its legitimate available Gemini-based worker capabilities.

Do not assume external agents are configured.

Do not launch paid third-party agents without authorization.

If multiple Gemini workers are available, delegate only genuinely independent tasks with non-overlapping file ownership.

Do not spend this session constructing an elaborate orchestration framework before implementing scientific features.

A single productive coding agent is preferable to many agents generating overlapping plans.

# 50. LOCAL WORKER

Preserve and complete:

- Bounded tasks.
- File ownership.
- Git worktrees.
- Focused tests.
- Patch review.
- Resource limits.
- Error reporting.
- Reproducibility.
- Safe rollback.
- Checkpoint records.

Avoid consuming laptop resources unnecessarily.

---

# PART XV — FUTURE SCIENTIFIC EXTENSIONS

# 51. PRESERVE THE PROJECT EXTENSION ROADMAP

Retain previously specified research directions:

- SwitchCraft Ω.
- EditCraft Ω.
- OptoCraft.
- VoltCraft.
- HIVE.
- MORPHEUS.
- CHRONOS.
- Related programmable biological systems.

Implement reusable scientific foundations, public data handling and legitimate supported analyses where feasible.

Do not claim speculative capabilities have been experimentally demonstrated.

Do not let these experimental modules displace the Genome Workspace or other core functioning laboratories.

Keep any experimental PS5 work separate from the core development priorities.

---

# PART XVI — SOFTWARE QUALITY AND SAFETY

# 52. RESEARCH DATA INTEGRITY

Never silently modify:

- Original genomes.
- Reference assemblies.
- FASTQ datasets.
- Experimental observations.
- Original molecular structures.
- Scientific campaign outputs.
- Model checkpoints.
- Research Library records.

Use versioned derived records.

Use checksums.

Use safe database transactions.

# 53. SCIENTIFIC CORRECTNESS

All calculations must preserve:

- Units.
- Reference assembly.
- Strand.
- Coordinate conventions.
- Scientific algorithm identity.
- Version.
- Parameters.
- Random seed.
- Model/checkpoint identity.
- Input hashes.
- Output hashes.
- Numerical precision where relevant.
- Relevant uncertainty.

# 54. SCIENTIFIC SAFETY

Apply appropriate safety controls to genome engineering, microbial research and biological sequence analysis.

Permit legitimate reference-genome inspection, nonpathogenic computational studies and evidence-based analysis.

Do not autonomously generate or optimize pathogen-directed lethal genetic constructs, harmful biological enhancement workflows or operational deployment instructions.

Flag biological risk and source uncertainty.

Do not label computational RNA-target hypotheses as demonstrated antimicrobial treatments.

# 55. SECURITY

Implement appropriate:

- Keychain integration.
- Secret isolation.
- Safe Rust IPC.
- Project-level permissions.
- Secure cloud authentication.
- Data access controls.
- Log redaction.
- Network request safety.
- Auditability.

# 56. LICENSING

Respect source and model restrictions.

Do not silently redistribute unavailable or restricted model weights.

# 57. APPLICATION RELIABILITY

Preserve the canonical installed Fold Studio application.

Complete relevant:

- Signing.
- Safe updates.
- Documents-access handling.
- Database migration.
- Application startup.
- Crash recovery.
- Dependency checks.
- Fresh installation where testable.
- Scientific regression testing.

---

# PART XVII — STRICT EXECUTION STRATEGY

# 58. DO NOT START BY REBUILDING THE UI

Begin with backend scientific implementation.

Build:

1. Genuine data import.
2. Scientific parsing and validation.
3. Scientific computation.
4. Result persistence.
5. Focused tests.
6. Minimal native control.

Only after those stages should a feature be considered implemented.

No decorative UI work.

# 59. FIRST IMPLEMENTATION BATCH

Begin with:

**Genome Workspace — bacterial reference import, assembly/replicon navigation, gene inspector and RNA transcript inspection.**

Implement the actual backend.

Write tests.

Connect basic UI.

Preserve original files.

Do not stop after this batch.

# 60. SECOND IMPLEMENTATION BATCH

Continue with:

**RNA Laboratory — secondary structure, RNA interaction analysis, scientific target-evidence review and saved research results.**

Use real calculations and a nonpathogenic reference fixture.

Do not stop afterward.

# 61. THIRD IMPLEMENTATION BATCH

Continue with:

**Genomic annotation, sequence search, variant interpretation and Biological Context Atlas integration.**

Then continue automatically through all other non-Fab requirements.

# 62. SUBSEQUENT EXECUTION ORDER

After the genome priority, process:

1. Existing EditCraft unfinished functionality.
2. Research Library and archive re-import.
3. Existing molecular analysis and visualization gaps.
4. Pathway and single-cell systems.
5. Small-molecule chemistry and docking.
6. Non-Fab protein engineering.
7. Materials science.
8. Molecular dynamics.
9. Quantum chemistry.
10. Scientific Notebook.
11. Workflow execution.
12. Scientific Intelligence.
13. Publishing and collaboration.
14. Cloud orchestration.
15. Advanced scientific integrations.
16. Other remaining non-Fab acceptance requirements.

This is a priority order, not a stopping rule.

If one subsystem is blocked by an unavailable external asset, move to another independent task.

---

# 63. DO NOT STOP AFTER A SMALL BATCH

The previous agent stopped after approximately five features.

Do not repeat that behavior.

A completed batch is an intermediate checkpoint.

After every completed batch:

- Save changes.
- Run focused tests.
- Record evidence.
- Update relevant requirement statuses.
- Select the next unblocked tasks.
- Continue implementing.

Do not ask permission to continue routine authorized development.

Do not deliver a final response merely because a commit was created.

Stop only when genuine session limits, resource limits, authorization boundaries, safety issues or the absence of feasible independent work require it.

Do not claim work will continue asynchronously after the session ends.

---

# 64. LIMIT INVESTIGATION OVERHEAD

Do not spend large amounts of usage on:

- Repeated full repository inspection.
- Repeated architecture reviews.
- Repeating the same failed test.
- Extensive status narration.
- Unnecessary dependency rewrites.
- Speculative engineering proposals.
- Repeated UI redesign.
- Multiple native installations.

Inspect only relevant files.

Implement the feature.

Run the relevant tests.

Continue.

---

# 65. INTEGRATION AND INSTALLATION POLICY

Do not rebuild the native app after every task.

Implement several related features.

Run focused tests.

Perform consolidated integration checks.

Use the guarded installer for a meaningful batch.

Preserve Documents access and the existing Research Library.

Do not bypass security prompts.

Do not damage the working application.

---

# 66. ACCEPTANCE CRITERIA FOR EVERY FEATURE

A feature is complete only if:

1. It has actual scientific or software functionality.
2. Its input is valid and explicitly defined.
3. Its calculation or operation executes.
4. Its output is correctly structured.
5. Errors are handled.
6. Results can be inspected.
7. Relevant tests pass.
8. Scientific provenance is preserved.
9. Saved results can be reopened where appropriate.
10. It is reachable through the appropriate minimal native interface, or has a clearly documented integration blocker.

A button alone is not a feature.

A Python package import alone is not a feature.

A model adapter without inference is not a completed scientific engine.

A simulated scientific result is not scientific validation.

---

# 67. FINAL SCIENTIFIC DEMONSTRATIONS

Before claiming broad completion, demonstrate as many genuine end-to-end workflows as available infrastructure permits.

Priority demonstrations:

1. Import a real nonpathogenic bacterial genome.
2. Inspect a real gene and its coordinates.
3. Extract a genuine sequence.
4. Inspect RNA transcripts and annotations.
5. Execute a real RNA secondary-structure calculation.
6. Execute a supported RNA interaction analysis using a documented reference hypothesis.
7. Display genuine functional/essentiality evidence.
8. Preserve and reopen the genomic analysis.
9. Export a reproducible scientific report.
10. Perform a genuine supported variant annotation.
11. Run an existing EditCraft reference operation.
12. Analyze a real H5AD dataset.
13. Run pathway enrichment.
14. Inspect a real protein complex.
15. Isolate RNA from the genuine ribosome structure.
16. Inspect a ligand conformer.
17. Run an appropriate small-molecule analysis.
18. Validate a real molecular docking reference where available.
19. Analyze a molecular trajectory.
20. Inspect a crystallographic structure.
21. Perform a supported materials calculation.
22. Run an accessible quantum chemistry reference.
23. Validate a safe Research Library archive round-trip.
24. Execute a typed scientific workflow.
25. Export scientific notebook/report results.
26. Verify the native application's research-data integrity.

Do not fabricate missing scientific evidence.

---

# 68. REQUIREMENTS ACCOUNTING

Maintain one authoritative implementation record.

For every non-Fab requirement:

- Requirement ID.
- Research module.
- Current implementation status.
- Source files.
- Scientific backend status.
- Native control status.
- Test evidence.
- Scientific validation evidence.
- Remaining work.
- Blocker, if any.

Avoid duplicate audit documents.

Use existing requirement identifiers.

Do not treat 1,933 acceptance paragraphs as 1,933 independent software features.

Calculate meaningful feature completion only from a deduplicated capability inventory.

---

# 69. FINAL REPORT

When execution genuinely ends, provide:

**Completed:** Real scientific functionality implemented.

**Verified:** Tests, native checks and numerical evidence.

**Genome Workspace:** Exact current capabilities and missing requirements.

**Scientific engines:** Operational, partial, unvalidated, unavailable.

**Requirement status:** Completed, partial, blocked and excluded.

**Research Library:** Confirm integrity.

**Application:** Installed build/version, if updated.

**Cloud:** Actual executions and costs, if any.

**Git:** Commits and remaining uncommitted changes.

**Remaining work:** Exact next unblocked requirements.

Do not falsely claim the entire platform is complete.

Do not imply an unexecuted model is scientifically qualified.

---

# 70. FINAL MANDATE

**MAKE FOLD STUDIO SCIENTIFICALLY FUNCTIONAL BEFORE MAKING IT BEAUTIFUL.**

The top priority is a complete Genome & RNA Laboratory.

I want to import and examine real organism genomes, particularly bacterial model systems, inspect genes and transcripts, analyze RNA biology, investigate RNA-target interactions and evaluate legitimate antimicrobial RNA research hypotheses with real scientific calculations.

Then continue implementing every other unfinished non-Fab requirement in the existing master specification.

Do not redesign the interface.

Do not spend time on visual polish.

Do not build placeholders.

Do not restart completed work.

Do not use GPT subagents.

Do not waste the session on long planning documents.

Do not stop after another small batch.

Do not launch unauthorized paid computation.

Do not alter original research data.

Do not compromise scientific validity.

**Use minimal functional UI, genuine scientific backends, real datasets, reference tests, reproducible calculations and persistent research results.**

Work continuously through all available non-Fab requirements within the active session's execution capacity.

If a dependency blocks one task, continue with independent work.

If a hard limit prevents completion, save the exact implementation checkpoint and report honestly what remains.

**BEGIN IMPLEMENTING THE GENOME WORKSPACE IMMEDIATELY. DO NOT STOP VOLUNTARILY AFTER THE FIRST BATCH.**