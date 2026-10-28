# Genome-first implementation · 2026-10-28

User explicitly prohibits every kind of subagent. No agents remain active. Fab and visual redesign are excluded.

## Implemented source

- Local Genome & RNA Laboratory in existing Genome Explorer: attributed FASTA/GFF3 import (32 MiB each), source-byte SHA-256 preservation, explicit replicon topology, annotation lookup, both-strand exact DNA search, 1-based inclusive/circular-origin interval extraction, immutable interval saving, JSON/FASTA export and existing RNA-ensemble review handoff. Gene annotations are supplied, never inferred; RNA alphabet conversion does not establish mature transcripts.
- Genome references and original sources are included in project ZIP export and validated by the archive inspector.
- Prior uncommitted notebook, assay and crystal functionality is preserved. Source tests pass; full native acceptance is still pending. No new agents were invoked after the prohibition.
- Archive Library-copy backend and basic button implemented: new IDs/assets, mapped record relationships, duplicates handled idempotently, transactional rollback, exact original ZIP retained and carried into subsequent exports. Archived jobs/domain state stay inert in the original snapshot, not live execution tables. This is not complete operational restoration of every scientific domain.

## Evidence

`reports/ultimate/genome-reference-validation.json`: genuine NCBI NC_000913.3 (4,641,652 bases) and ASM584v2 GFF3 (9,523 rows), supplied thrA gene 337–2799 (+), exact 2,463-base interval saved and verified. Qualification used isolated temporary libraries, not the real research root. No essentiality, RNA interaction or antimicrobial efficacy is claimed.

Focused verification: 23 backend cases discovered, 22 passed and one optional SciPy reference skipped; two additional archive restore tests passed; 13 interface tests and TypeScript passed. Guarded consolidated packaging/signing passed (64 scientific modules); the single installed app was replaced. Native genome controls passed: genuine reference counts, thrA search, exact 2,463-base interval and save to Library with a matching SHA-256. See `reports/ultimate/genome-first-status.json`.

## Remaining priority-zero scope

Genuine transcript/CDS assembly across annotation segments and phase handling; GenBank/EMBL/compressed imports; authoritative organism/assembly search; essentiality evidence with conditions; RNA interaction models and real execution qualification; broader genome formats/large-genome indexing. Current GFF selection extracts an exact interval only. Public FASTA/GFF reference files are under /tmp, not trained model downloads. No paid compute was started.

No subagents were used after the latest prohibition; collaboration inventory confirmed none active. The app is open on `Genome Reference · E. coli K-12 MG1655` in Genome Explorer. Existing assay CSV follow-up remains unfinished; no operative CSV import is claimed. Transcript/CDS phase assembly and real RNA interaction execution are the next priority tasks.
