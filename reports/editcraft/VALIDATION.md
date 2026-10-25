# EditCraft: first cloud validation

This validates a bounded CPU workflow, not the complete EditCraft directive.

## Public ANGPTL3 reference

- Gene: ANGPTL3 (ENSG00000132855)
- Assembly: GRCh38
- Locus: 1:62597464-62607699, strand 1
- Selected transcript: ENST00000371129.4
- CDS-derived RNA: 1383 nucleotides
- Translation: 460 residues, exactly matches the separately retrieved Ensembl protein sequence (terminal stop excluded)
- ViennaRNA 2.7.2 at 37 °C: MFE -296.27 kcal/mol

This is an isolated CDS thermodynamic prediction. It omits native UTRs, cellular
RNA-binding proteins and modifications; it does not establish transcript stability
or observed cellular structure.

## Synthetic reference checks

- ATGGCC translates to MA.
- CDS 6C>T changes GCC to GCT and retains MA (synonymous).
- GGGAAACCC produces (((...))) with MFE approximately -1.2 kcal/mol.
- NGG in AAGGCC is found at forward-sequence positions 2–4.
- BED chr1:[0,3) normalizes to 1-based inclusive positions 1–3.

The initial verifier incorrectly expected the motif at position 1. The assertion
was corrected against the preserved output; no calculation was resubmitted.

## Provenance

Cloud application: fold-editcraft-engine, separate from the protein engine.
Python: 3.12.10; platform: Linux-4.19.0-gvisor-x86_64-with-glibc2.36.
Packages: {'biopython': '1.85', 'ViennaRNA': '2.7.2'}.
No GPU, trained checkpoints or private protein dataset was used.
The approved maximum was $1.50 including deployment. Estimates are recorded;
actual provider billing is not connected and is not asserted here.

Experiments: 0191d378cb8844a992d4bc5e848216f0, cd67dd85178840a0ba6b6399a0e6ff9d.
Results were retrieved through checksum-checked control responses, linked into
the Research Library and accompanied by immutable notebook receipts.

## Reference molecular structure

PDB 4V9D biological assembly 1 was downloaded from the RCSB archive (about 17.5 MB
uncompressed), with original coordinates and checksum retained. This is an
experimental bacterial ribosome structure, not an ANGPTL3 translation trajectory
or an atomistic simulation. Native view validation is recorded separately.

## Remaining scope

Trained CRISPR/base/prime/RNA-editing models, broad genomic foundation models,
single-cell/perturbation/pathway pipelines, full genome/CDS/structure mapping,
large datasets and independent scientific benchmarking remain unfinished.
See docs/EDITCRAFT_IMPLEMENTATION.md and docs/EDITCRAFT_EXECUTION_STATE.json.
