# Biological Models and Phage Research

Added 1 November 2026. Open **Discover → Biological Models**.

## Implemented scope

Four source-pinned remote inference integrations use the existing Modal GPU task lifecycle:

| Integration | Input | Output |
|---|---|---|
| Evo 2 7B base | Canonical DNA; optional alternate DNA, each ≤4,000 bases | Mean autoregressive log-likelihood scores, optional score difference, reference DNA embeddings (.npy) |
| Borzoi human replicate 0 | hg38 chromosome and zero-based start; one annotated human track | Raw regulatory track values (.csv), source sequence, assay metadata, envelope preview |
| Biohub ESMC-300M | Canonical protein, ≤1,000 residues | Residue embeddings (.npy), pooled representation |
| Biohub ESMFold2 | One canonical protein, ≤600 residues, seed and sampling settings | mmCIF structure, raw confidence; import into the molecular viewer |

Each submitted run includes project identity, input source, input SHA-256, recipe SHA-256 and account identity. The model runner writes strict JSON and artifact hashes. Retrieved result identity/checksum is verified before display; individual artifact export checks hashes again. Inference is remote only; no local fallback. The interface includes result metrics, a bounded Borzoi track preview, logs, refresh, cancellation and exports.

Predictions can be attached to a selected dossier as model evidence, retaining the run identity, input/recipe hashes and artifact manifest.

The existing cloud task pipeline keeps the container environment and provider GPU report on successful runs. Code revisions are pinned in `scientific/biological_model_recipes.py`. ESM checkpoint revisions, Evo loaded-checkpoint SHA-256 and Borzoi checkpoint SHA-256 are retained in model outputs. Source pins do not make every transitive dependency immutable; the actual environment receipt remains necessary.

## Runtime and limits

All integrations are explicitly **integration_unvalidated** until a real GPU run and comparison against upstream reference outputs is completed. Software tests do not establish model accuracy. No model weights were downloaded and no paid model run was initiated for this implementation.

Runs require an explicit in-app approval to upload inputs, download model assets and incur provider charges. The default provider is Modal. First image builds, downloads and inference can be substantial. A one-hour default runtime is an execution bound, not a price estimate; image-build charges are separate. No cost quote or numerical budget enforcement is claimed.

Borzoi fetches exactly 524,288 bases from UCSC hg38; malformed, truncated or boundary-crossing responses fail rather than pad. It uses one forward-strand replicate and reports raw transformed values with full assay metadata; no count calibration, reverse-complement ensemble, expression diagnosis or bacterial/phage inference is claimed. Track indices follow the pinned `targets_human.txt` order.

Evo likelihood differences are uncalibrated sequence statistics. ESMC representations do not establish biological activity. ESMFold2 predicts a single protein without supplied MSA and defaults to four refinement loops, not maximum-accuracy settings. All outputs are research predictions.

## Research dossiers

The **Phage & biology research** tab saves an organism/strain, reference accession and research question as an analysis record in the selected project's Research Library. Evidence entries are append-only through this feature, with source, category, timestamp and content hash. Categories distinguish research notes, literature, model predictions and laboratory reports; all user-supplied entries remain explicitly unverified by fold. Optimistic conflict detection prevents concurrent evidence additions from overwriting one another.

Dossiers survive application restart and can be exported as JSON. Existing Library removal/restoration applies. Generic project archive storage includes their analysis records; remote task artifact packaging into project archives is not implemented by this change. Raw laboratory attachment import, automated phage matching/design and clinical recommendations are outside this implementation.

## Verification

- 10 focused Biological Models control-plane checks: catalogue, remote script syntax, input alphabets/integer validation, cost gate, four-recipe submission through simulated provider, project isolation, dossier persistence/conflicts, tamper rejection, output identity/checksum and exact artifact exports.
- 10 existing GPU-task regression checks pass, including simulated lifecycle and retrieval path safety.
- TypeScript check, production frontend build and guarded desktop packaging are checked separately in the implementation session.
- Native interface acceptance uses a separate synthetic QA library; no artificial test record is inserted into the user's research library.

No scientific accuracy, clinical efficacy, phage susceptibility or Omnii-1 equivalence is established by these integrations.

## Primary references

- https://github.com/ArcInstitute/evo2
- https://github.com/calico/borzoi
- https://github.com/calico/baskerville-tf
- https://github.com/Biohub/esm

## Research overview controller · 1 November follow-up

The default **Research overview** tab creates immutable, source-attributed reference-analysis plans. The research question is recorded verbatim; deterministic routing follows input types rather than pretending to interpret arbitrary requests. Existing DNA fragments route to Evo 2; existing proteins route to ESMC and optionally an independent ESMFold2 analysis. For microbial reference studies, Borzoi is explicitly inapplicable.

The plan graph distinguishes local input-identity checks from remote predictions. Each remote engine needs its own upload/cost approval. Plans never generate or alter biological sequences, infer infectivity, calculate a joint efficacy score, or automatically fan out or retry remote requests. The overview combines verified engine outputs in one report without treating agreement as experimental evidence. Phage-host compatibility remains `not_modelled`, even if all engine predictions return.

Plans are saved as standard analysis records. A separate SQLite submission-claim table prevents repeated submissions of a plan step. Uncertain launch failures require review instead of an automatic billed retry. Restoring an archived plan does not resume jobs; task artifacts and submission claims are not included in portable project archives by this feature. Per-engine run details and artifact handling reuse the existing workbench.

Eight focused controller tests cover routing, input boundaries, approval without side effects, duplicate-submission exclusion, uncertain-launch handling, result integrity, project isolation, plan restoration after restart and the distinction between available predictions and unknown biological activity. Provider outputs in these tests are synthetic; they do not qualify model inference.
