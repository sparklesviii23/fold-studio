# fold RAPID Cloud Engine

The local Metal backend and standalone Linux NVIDIA backend are separate execution paths. Cloud campaigns are self-contained remote jobs; a Mac client does not advance their model stages. The complete cloud directive remains unfinished until genuine remote model execution and multi-engine acceptance succeed.

## Actual deployment

On 24 October 2026 the source-only engine was deployed as `fold-rapid-cloud-engine` on Modal. A genuine remote CPU inventory request passed. No GPU or model calculation was started. The first attempt exposed an unhydrated Modal Dict serialization error; explicit SDK resource hydration fixed the second deployment. See `reports/cloud-deployment-attempts.json` and `reports/cloud-engine-status.json`.

The app is constructed by `remote_worker/cloud_engine.py` / `fold_rapid.modal_provider.build_app`. `fold_rapid.cloud_image` builds the reviewed `rapid-cuda13-core-v1` recipe from an immutable NVIDIA CUDA base, hashed core requirements, pinned scientific source and a full deployment integrity manifest. No macOS application, Metal executable, local checkpoint, research database or credential file is uploaded with the source release. Remote model installations are separate explicit operations into the persistent model Volume.

Deployment is an asynchronous client-side management operation (`cloud_deployment.py`); its durable local status prevents a 100-second RPC timeout from silently killing or replaying a long image build. This deployment helper never advances scientific campaigns. The scientific controller lives in Modal's CPU function or the detached Linux SSH worker. A campaign persists its manifest, stage claims, Modal call IDs, candidate lineage and report remotely before handing off model work.

## Enforced boundary

`execution_policy.py` rejects native scientific actions while a cloud backend is selected, before native engine dispatch. A request cannot override that choice by adding `executionMode: local`. Switching backends is refused while a local scientific worker is active. Client library editing, file preparation, molecular rendering and synchronization remain available.

Each cloud manifest also contains `execution: {mode: cloud, provider: modal|vast, localFallback: false}`. The worker verifies Linux and the matching actual deployment/SSH context before starting its controller. Model supervisors require genuine CUDA where appropriate. Missing runtimes, checkpoints, licenses or external services produce blockers; none invokes a Mac fallback. The shared native analysis code is copied as platform-neutral source into the standalone cloud package and runs on the remote CPU.

The updated source offers an explicit LOCAL Apple Metal / CLOUD Modal / CLOUD Vast/SSH selector. Latest interface and dispatch-policy changes will be packaged after the cloud worker milestone; the Mac app is not being rebuilt repeatedly during backend qualification.

## Scope still requiring implementation or execution

Runtime presence and model hashes are not scientific readiness. Authentic GPU inference, reference comparisons, complete compatible handoffs, remote evolution decisions, client-disconnect recovery and final native import/viewer checks remain required. RF target-aware scaffolding, genuine ESMC design, automatic separately billed BoltzProt integration, chemical/counterfactual cloud strategies, optional cloud research agent and broader local-physics feature coverage are incomplete. Licensed Rosetta still needs an authorized runtime and qualification.

The CPU deployment check passed. The user subsequently approved up to $1 more for pinned remote runtime installation and the official BindCraft AF2/MPNN plus SolubleMPNN checkpoints. The single durable bootstrap request `01b7ff232a7b4896b3847915dc9231b2` / Modal call `fc-01M5P5E7FPNXJMVNA2NTKQ7HRD` completed successfully remotely, with a 30-minute provider timeout, a 28-minute work deadline, two CPU cores and an 8 GiB hard memory limit. It preserves committed progress, does not retry automatically, and does not allocate a GPU. ESM and BoltzGen trained weights are excluded. A separate workload/cost approval is still required for genuine GPU computation. Modal workspace credits do not include external Boltz API charges. Actual provider billing has not been read or certified.

The cancelled Fab campaign and original peptide remain unchanged. No local MPNN result is counted as cloud acceptance. Notarization remains deferred.

## Approved CPU setup result

The remote setup completed all four steps in approximately 21 minutes. BindCraft 1.0.3 / JAX 0.11.2, BoltzGen 0.3.2 / Torch 2.9.1, and ESM 3.4.1.post1 / Torch 2.11.0 passed their genuine Linux import probes. All seven original AF2 checkpoints, the three original MPNN variants, and SolubleMPNN were downloaded and matched to the pinned model catalog. Full receipts are in `reports/cloud-model-setup.json`. ESM and BoltzGen trained weights were not downloaded, and no GPU/model inference ran. The spawning client exited and subsequent clients recovered the remote result and Volume receipts. This establishes CPU setup continuity, not scientific campaign qualification.

A concrete first GPU workload is saved as a prepared, unsubmitted request. Its review (`reports/first-cloud-gpu-workload-review.json`) covers the saved 154-residue ANGPTL3/8 fragment target and 20-residue peptide, one original-filter BindCraft attempt, both MPNN branches, held-out AF2 2/4, and remote assessment. It requires separate approval: up to $6 allowance, at most 90 minutes of campaign wall time, A100-80GB. The reviewed GPU stage reservations total $3.123; CPU, memory, storage and startup charges are additional. This is an approval allowance, not a Modal-enforced billing cap. No ESM weights, Rosetta, external paid APIs or full-Fab work are included.

After the setup worker returned and released its lease, the staged process-tree timeout protection and atomic deployment guard were deployed. The post-update CPU inventory confirmed all eleven checkpoints remain available for the four initial model operations. No GPU function was invoked. Latest deployed cloud source commit: `5232e16`; 612 backend and 100 frontend tests pass.
