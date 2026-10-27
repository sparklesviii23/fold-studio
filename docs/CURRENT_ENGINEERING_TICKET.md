# Current engineering ticket

- ID: VII-14-C004, bounded pathway membership view.
- Objective: make a completed enrichment result's exact tested-set/observed-gene overlaps inspectable in the native app.
- Modules: `src/components/EditCraftPathways.tsx`, `src/components/PathwayMembership.tsx`, focused component tests. The scientific calculation and source coordinates are unchanged.
- Implementation: derive graph edges only from saved `overlapGenes`; bound the display to eight sets and 32 genes, disclose omissions, preserve the complete table and original result, and label membership separately from interactions and causation.
- Acceptance: a saved result shows exact edges and selection; no result shows no invented graph; every omitted item is counted.
- Tests: `PathwayMembership.test.tsx`, `EditCraftPathways.test.tsx`, TypeScript, guarded package and native inspection. Existing exact combinatorial and Modal reference evidence remains `reports/editcraft/pathway-numerical-reference.json` and `reports/editcraft/pathway-cloud-reference.json`.
- Dependencies/blockers: saved real enrichment output is needed to inspect the graph in the user's app. No new dataset download, model or cloud job is needed. The wider clause remains partial until curated sources, biological qualification and true interaction topology exist.

## Verification

Focused interface tests (4) and TypeScript passed. The guarded native build succeeded. In the saved finite-population reference, the app displayed exactly three edges (`selected` to `g1`, `g2`, `g3`) and selecting the set exposed those three identifiers. This is mathematical fixture evidence, not biological pathway validation.

## Closely related follow-up: exact result export

- Objective: export the selected completed pathway stage in full without inventing missing background identifiers.
- Modules: `src/components/EditCraftPathways.tsx` and its focused test.
- Acceptance: stage selection controls the exported JSON; the original saved stage remains byte-for-byte equivalent after JSON round-trip; the report states that a background hash is not the full background list. No calculation starts.
- Verified: focused interface tests and TypeScript pass; final guarded app build and signing passed; export button was not clicked in the native app. No new cloud or biological evidence claimed.

## Completed ticket: SVG membership export

- Modules: `src/components/PathwayMembership.tsx`, `src/components/EditCraftPathways.tsx`, their focused tests.
- Acceptance: exact bounded edges; escaped labels; original input/source/collection/background hashes and omitted counts in metadata; vector export clearly disclaims interaction and causality.
- Verified: six focused interface tests and TypeScript pass. Guarded build and signing passed. Native export of the saved finite-population reference produced valid SVG XML with the exact three displayed edges and four original hashes; zero nodes were omitted. The companion JSON retained all three tested rows and matching source/input hashes.

## Current ticket: local GMT import

- Objective: choose a local GMT file for pathway enrichment while keeping its exact text, file name and SHA-256 in the research record.
- Modules: `scientific/editcraft.py`, `src/components/EditCraft.tsx`, `src/components/EditCraftPathways.tsx`, focused tests.
- Acceptance: bounded `.gmt` import through the existing native chooser; case-preserving GMT parse; source checksum retained only while the imported text is unchanged; user must supply collection source, organism, namespace and license; no analysis starts on import.
- Verified: one focused backend test, five focused interface tests, TypeScript and guarded app package/signature checks. Native inspection confirmed the saved project, import button, native chooser and safe cancellation. The file preservation test used isolated data.
- Dependencies: user-selected local file. No cloud, model download or paid compute.
