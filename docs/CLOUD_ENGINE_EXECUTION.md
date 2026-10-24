# Fold Studio RAPID Cloud Engine

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

Only the approved CPU image/deployment check has run. A separate approval is required for remote runtime installation/model downloads and another workload/cost approval for genuine GPU computation. Modal workspace credits do not include external Boltz API charges. Actual provider billing has not been read or certified.

The cancelled Fab campaign and original peptide remain unchanged. No local MPNN result is counted as cloud acceptance. Notarization remains deferred.
