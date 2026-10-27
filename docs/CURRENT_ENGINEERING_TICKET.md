# Current engineering batch · 2026-10-27

**Fab remains fully deferred.** User requested parallel independent features and one consolidated installation near batch end. No paid compute or downloads were performed.

## Implemented and tested

- Pathway TSV: every tested set; exact saved probabilities/logs/underflow flags and provenance. Shared exporter now accepts `.tsv`; native check caught this missing format and justified one correction install before the batch strategy changed.
- Trajectory gyration: per-frame equal-mass observed Cα radius in Å, source-pinned and calculated before alignment, with analytical and child-process tests.
- Ligand results: actual saved RDKit properties, conformer energy/convergence and preparation provenance; checksum-verifying SDF and summary JSON exports.
- Project archives: read-only bounded CRC/SHA-256 review and record/SDF/ChimeraX scene-reference checks; no extraction, import or job launch.
- Unit cells: actual mmCIF cell lengths/angles, lattice vectors/volume, nominal uncertainties and reported symmetry, source identity and JSON export.

## Verification

18 focused backend tests, 21 focused interface tests and TypeScript pass. Consolidated guarded installation/signing passed, checking 61 scientific modules. Native QA passed for archive review, genuine 1BNA cell geometry, actual saved ethanol inspection/SDF export and an explicitly artificial trajectory with both gyration values equal to sqrt(1.125) Å. The isolated QA library preserved original genuine ligand bytes; no fixture entered real research data.

## Native acceptance complete for this batch

The original EditCraft research project reopened after Documents permission. The installed TSV export wrote all three saved tested sets with exact numeric probabilities, overlap identities, collection attribution and all four hashes. Its SHA-256 exactly matched the independently generated local reference. No synthetic fixture entered the real library. The app remains open on the original research root.

## Scope and evidence

`reports/ultimate/implementation-batch.json` and `reports/ultimate/consolidated-native-acceptance.json` record the batch. Updated requirement scopes: VII-14-C004, VII-22-C003, VII-25-C003, UL-MAT-062-C004. Each broad requirement remains partial; arithmetic/technical references do not establish biological validation or full platform acceptance. The next independent package is project archive re-import with explicit identity remapping and no archived job execution.
