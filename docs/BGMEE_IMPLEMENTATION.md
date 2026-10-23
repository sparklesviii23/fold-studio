# Biology-Guided Molecular Evolution Engine

This extends the existing Fold Studio application. The complete master directive is **not finished**. Existing Metal BindCraft, RAPID/Vast, ProteinMPNN, AF2, library, viewer and cinema remain in place. No Fab trajectory was resumed, source coordinates changed, model downloaded or paid compute started.

## Working implementation

The Architect's **Biology-Guided Design** tab now supports:

- Separate FASTA references, saved sequence records, existing Molecular Intelligence candidates and one explicit observed structure chain per import.
- Reference groups, biological identity, species/accession/isoform/range and evidence/uncertainty notes. Multiple uncertain regions are never concatenated. Gapped structure numbering and insertion codes remain explicit.
- Immutable parent/descendant sequences, original-sequence hashes, fixed/mutable residue masks, preferred/excluded amino acids and motif/interface/exposed/core/linker/experimental annotations in the backend. The initial interface exposes fixed positions; other constraints remain typed service fields.
- Explicit substitutions with reference-residue checking and inherited hard constraints. A proposal has no inherited predicted coordinates or scores. Its parent backbone is only a reference; fresh prediction is required.
- Retain/reject/revert review events, without deleting prior evidence. Revert returns the interface selection to the parent.
- Raw result provenance, generation/optimization/refold/assessment roles and lineage-aware model-family conditioning checks. Different family names alone never establish independence.
- A Counterfactual Laboratory for supplied, explicitly mapped mutation evidence and matched parent/variant result observations. Model/version/context/seed/method/units must match. It reports raw deltas and directional disagreement; it does not calibrate probabilities, neutral-effect thresholds or effect-size associations.
- Saved/exportable 30/60/120-minute proposed protocols with target hashes, original controls, constraints, seeds, one-heavy-GPU intent and stopping rules. They are explicitly `prepared_not_executable`, not queued scientific campaigns.
- Persistence and inclusion in explicitly requested project exports. Project removal protects unresolved external jobs, then removes the new metadata with the project.

No supplied numerical observation becomes certified scientific evidence simply because its JSON validates or a checksum is recorded. Artifact content verification and independent predictor execution are separate unfinished operations.

## Official Boltz API adapter

`scientific/boltz_api_adapter.py` implements an optional SDK contract for `boltz-api==0.50.0`:

- Locally prepared sequence-only protein design and external protein-library-screen requests.
- Explicit approval before sequence upload for a cost quote, then separate paid-run approval with a maximum accepted **estimate**. Provider-side spending limits are still necessary; a quote is not a hard billing cap.
- Asynchronous submission with an idempotency key, saved remote ID, bounded result-page retrieval/reconnection and stop requests. Ambiguous submissions remain unresolved and cannot be automatically resubmitted.
- Raw response/metric preservation. No invented standalone Boltz-PPI endpoint, normalized peptide binding probability or self-hosted BoltzProt checkpoint.
- Credentials read only from `BOLTZ_API_KEY` in the service environment; never from project JSON. The SDK is lazy/optional and not installed into the signed app. Native isolated SDK-runtime provisioning remains unfinished; controls report installation/credentials missing.

The official SDK wheel was inspected in memory from PyPI, not installed:

```
version: 0.50.0
wheel SHA-256: b69c85ac4c01b8ca80724cadf2aa7b8b35e7dcdce138a2d6cb02ac3a1bc6b98b
repository: https://github.com/boltz-bio/boltz-api-python
```

Source contracts inspected: `resources/protein/{design,library_screen}.py`, `types/protein/design_start_params.py`, and design/screen estimate-response types. The adapter deliberately uses the SDK's still-supported legacy binder request shape rather than assuming the newer union has the same SDK signature. No API account/key or paid service result was available. Contract doubles test control flow, not molecular inference or production service compatibility. Structure-artifact download, checksum verification, result-to-candidate import and uncertain-submission reconciliation are not yet implemented.

Official references checked 2026-10-23:

- [Protein design](https://api.boltz.com/docs/api/guides/protein-design/)
- [Protein library screening](https://api.boltz.com/docs/api/guides/protein-library-screen/)
- [SDK and authentication](https://api.boltz.bio/docs/api/api/python/)
- [Biohub ESM source](https://github.com/Biohub/esm) and [ESMFold2 variants/design protocol](https://biohub.ai/esm/protein/get-started)

ESMFold2/Fast are genuine official models; the existing pinned ESM environment for legacy BoltzGen does not constitute a separately implemented predictor adapter. SolubleMPNN used inside that legacy pipeline is likewise not a qualified independent redesign branch.

## Remaining directive work

| Work package | Evidence-backed status |
| --- | --- |
| Shared candidates / constraints / lineage | Working first implementation; chemistry payload is canonical linear protein only |
| BoltzProt / external protein screen | Optional SDK adapter and billing gates; real authenticated service, native runtime provisioning and artifact import pending |
| ESMFold2-Fast/full and ESMC design | Official availability verified; separate execution, model installation and hardware/numerical qualification pending |
| Dual ProteinMPNN/SolubleMPNN descendants | Existing ProteinMPNN preserved; genuine dual execution and result ingestion pending |
| Rosetta / orthogonal physics | Existing independent geometry retained; licensed Rosetta runtime and refinement pending |
| Biology-guided design | References and controlled explicit evolution work; sequence-seeded BindCraft optimization and automated evaluation pending |
| RFdiffusion motif scaffolding | Not integrated |
| Stabilized/modified peptide chemistry | Existing app capabilities retained; new chemistry-aware evolution and sampling pending |
| Counterfactual intelligence | Mapped evidence and matched supplied-result comparisons work; automatic prediction, controls, held-out calibration and side-by-side structural assessment pending |
| Molecular Research Agent | Development coding worker is separate; no molecular research-agent inference/literature tool integration claimed |
| Modal / Vast | Existing Vast/RAPID preserved; Modal and real new-engine GPU qualification pending |
| Resource scheduler | New protocol budget/stopping-rule schema; adaptive scientific execution and measured runtime/cost admission pending |
| Matched scientific benchmark programme | Not run; no scientific hit-rate improvement claimed |

The APOA5/ANGPTL3/8 demonstrator still requires curated biological assembly/accessibility and species/isoform mappings, independent predictions, controls and measured campaigns. The previous peptide remains a computational hypothesis. The full Fab production campaign remains cancelled/incomplete, including its documented trajectory-drift limitation. Notarization stays deferred for local use.

## Validation scope

`tests/test_evolution.py` uses isolated temporary research libraries, preserved source fixtures and clearly synthetic model-result doubles. It checks reference separation, constraints, native numbering/insertion codes, ancestry, persistence/export, conditioning, matched counterfactuals, quotes, duplicate submission, ambiguous outcomes, cancellation and project deletion. No test uses the user's research directory as a disposable fixture.

The interface was also exercised against an isolated fixture library: two references imported independently, a D3A descendant retained its parent, reopening preserved ancestry, and preparing a remote screen left upload/billing gates disabled. Numerical engine/GPU success is not implied by these software tests. Exact completed validation and installation results are recorded in `reports/bgmee-integration-status.json`.
