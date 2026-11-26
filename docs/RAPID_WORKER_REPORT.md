# RAPID Compute Worker 0.2.0 — software release candidate

> Historical implementation snapshot. Current cloud readiness, actual execution and unresolved architecture are audited in [RAPID_COMPLETE_ENGINE_AUDIT.md](RAPID_COMPLETE_ENGINE_AUDIT.md); this older document is not the current deployment status.

This implements a scientific worker beyond the earlier connection foundation.
It is **not a CUDA production qualification**. No rented instance, paid service,
large model download or new CUDA model prediction has been used in development.
The original local Fab production campaign remains cancelled after five updates;
its paused continuation and documented independent-trajectory drift are retained.

## Worker and transport

`remote_worker/fold_rapid/` is an installable Python application, with the
`fold-rapid` entry point and a versioned API v2. It uses authenticated OpenSSH
stdin/stdout rather than an unauthenticated HTTP execution service. The existing
connection worker's API v1 remains available for compatibility.

The worker implements strict scientific manifests, target snapshots and hashes,
observed author/label residue mapping, a SQLite job/event database, idempotent
submissions, detached scientific supervisors, one accelerator lease, timed and
estimated-cost deadlines, real process-group cancellation, sampled GPU memory,
logs, immutable candidate records, checksummed result archives, paged candidate
discovery and bounded artifact transfer. Client disconnection does not own the
scientific process. Missing supervisors are marked interrupted, with outputs
retained. **Exact optimizer/RNG-step restart is not implemented.**

Deadlines request process termination and allow up to eight seconds for graceful
exit before forced termination. GPU memory is sampled; reported observations
are not a claim that every transient allocation peak was captured. Terminating
a job or shutting down the stdio worker does not stop provider billing.

## Genuine scientific execution paths

| Engine | Actual implementation | Qualification |
|---|---|---|
| BindCraft2 | Pinned original CLI, target/chains/hotspots, modality/lengths, seed and attempt/final budgets; original gradient stages, losses, screening, ProteinMPNN, held-out refolding, filters and ranking | Original settings/target translation and authentic saved output tested; CUDA execution NOT RUN |
| BoltzGen | Pinned official `run` pipeline: generation, SolubleMPNN inverse folding, Boltz complex folding, ESMFold2 scoring, analysis, filters and diversity selection | Input/command contracts and isolated dependencies tested; model execution and actual generated-output comparison NOT RUN |
| ProteinMPNN | Original `ProteinMPNNSequenceModel`, explicit redesign chains, fixed context/backbone checks and FASTA output | New CUDA path NOT RUN; no folding or binding inferred from sequence redesign |
| AF2 multimer evaluation | Original `AlphaFoldDesignModel`, held-out models 2/4, three recycles, explicit chain roles, preserved original numbering, scalar and array confidence artifacts | New CUDA path NOT RUN; within-family held-out evaluation is distinct from experimental validation |
| Structure screen | Executable observed-coordinate/sequence inspection | Actual standalone and SSH/container jobs passed; no model prediction |

Scientific job submission never downloads weights or falls back to CPU. It
checks source/checkpoint hashes and actual CUDA numerical operation before
starting a molecular model. A reference qualification run remains necessary.
Unknown operations and unimplemented cross-engine transformations fail explicitly.
Candidates retain raw engine-specific metrics and rejection reasons; confidence
scales are not averaged across engines. A failed or rejected design is not
converted to an accepted result. Zero qualified candidates is a valid outcome.

BindCraft2 source: `PacesaLab/BindCraft2`, revision
`c0ee638d11bc010817c2c97ee58ed5c323e664e2`, package version `1.0.3`.
BoltzGen source: `HannesStark/boltzgen`, revision
`a07fea1153111ef453aaea7a15697ee05de9291f`, package version `0.3.2`.
The upstream scientific source is not modified. Original license notices ship
with the private source release; nothing has been pushed to a public registry.

## Isolated scientific environments

The dependency sets are independently resolved for **Linux AMD64 / Python 3.12**,
with exact versions and distribution hashes in `remote_worker/environments/`.

| Environment | Principal pins |
|---|---|
| Core | Gemmi 0.7.5; worker 0.2.0 |
| BindCraft2 | JAX/jaxlib/CUDA13 plugin 0.11.2; cuEquivariance JAX/ops 0.11.1; pinned CUDA13.0 family |
| BoltzGen | Torch 2.9.1 / CUDA12.8 wheels; NumPy 2.2.6; numba 0.61.2; cuEquivariance 0.11.0 |
| ESMFold2 | Original upstream runtime pins, esm 3.4.1.post1; Torch 2.11.0 / CUDA13; NumPy 2.0.2; cuEquivariance 0.12.0 |

The container base is NVIDIA CUDA `13.0.2-runtime-ubuntu24.04`, pinned to
`sha256:6a0e31b59e70890446f2c17356d6efc0d54260090a8c63d6ca7c2ad049db95d2`.
Model-specific runtime images build without any model checkpoint. Package imports
on a no-GPU machine are distinct from CUDA initialization and scientific execution.

Optional BoltzGen fused kernels and ESMFold2 acceleration are explicitly disabled
for the first reference path. No H100 optimization, mixed precision speedup or
RTX5090 performance target is certified. Native Metal offload/rematerialization
code has not been copied into CUDA. CUDA optimization needs real forward,
gradient, scientific-output, memory and timing comparisons.

## Deployment and native app integration

The native Cloud Compute page can inspect, install/update and launch/check the
scientific worker, inspect engine/model availability, approve isolated runtime
and model installations separately, choose a Research Library target, preserve
its chain selection, enter author-numbered hotspots, set format/length/seed/time
and estimated cost, submit an idempotent job, reconnect to saved jobs, read actual
progress, cancel, receive structures into the existing library/viewer and export
the full scientific package. Existing local compute/viewer interfaces are kept.

Two installation routes are implemented:

1. A prebuilt private NVIDIA CUDA worker image. SSH public-key authentication is
   required; no password login or public scientific API is opened. Persist
   `/data/rapid` and provide the instance's normal SSH public key.
2. An existing Linux AMD64 instance. The existing strict SSH connection transfers
   a roughly 1.2 MB source-only release, verifies the archive and member hashes,
   installs a private core environment and atomically activates it. Older host
   Python installations use a hash-pinned uv bootstrap and an isolated CPython
   3.12.14 without replacing host Python. Docker-in-Docker is not required.

Activation preserves the existing research-data root and earlier worker prefixes.
Scientific environments and checkpoints are separate, explicit installation
actions. BindCraft's archive/member hashes and MPNN pins are recorded; BoltzGen,
ESMFold2 and ESMC repositories have immutable revisions and file hashes.
The AlphaFold member checksums originate from the earlier TLS-fetched official
archive, not independently published provider member checksums.

The updated native app was installed **in place**, then connected through its
actual Cloud Compute controls to the current Linux AMD64 worker. It reported
worker 0.2.0/x86_64 and correctly unqualified CUDA. The real 154-residue library
target was parsed locally as A50/B50/C54 without transfer. ProteinMPNN's explicit
chain-role controls were checked. Its sequence-only results now import as
separate, checksummed library sequence records per chain; they are not mislabeled
as newly predicted structures. The temporary SSH profile/container/key were removed.

BoltzGen output collection now selects the native `refold_cif` stage rather than
whichever same-named backbone a filesystem traversal returns first. Conflicting
outputs are refused. Failure and interruption diagnostics remain exportable with
checksums; hashing streams large artifacts without reading each whole file into RAM.

The current AMD64 artifact also passed the **managed CPython 3.12.14** bootstrap
route, with its actual interpreter prefix verified, preserving the existing job
database through activation. No host Python was replaced. This extends the earlier
system-Python bootstrap evidence.

Full BoltzGen includes approximately 33 GB of checkpoints/data plus its separate
environments; keep at least 50 GiB free before its model installation. BindCraft
model installation requires at least 16 GiB free. **These model downloads were
not executed on the Mac.** No API-token/provider provisioning or billing controls
are claimed. Registry publication remains an explicit authorized distribution step.

## Evidence and limits

Actual evidence is recorded in:

- `reports/rapid-container-validation.json`: final AMD64 image, authenticated SSH,
  host fingerprint, persistent real-coordinate job, reconnect/idempotency,
  result archive and existing-instance activation.
- `reports/rapid-angptl3-reference-contract.json`: the real private 154-residue
  construct is **A50 + B50 + C54**, with an explicit 20-residue peptide, seed42,
  original settings resolver and original model pools/schedule. Input bytes are
  unchanged. This is not the full physiological ANGPTL3/ANGPTL8 assembly.
- `reports/rapid-gpu-qualification.json`: NVIDIA-dependent tests are **NOT RUN**.
- `reports/rapid-boltzgen-imports.json` and `reports/rapid-esmfold2-imports.json`: actual Linux AMD64 scientific image built; fresh-container entry-point imports passed without checkpoints.
- `reports/rapid-bindcraft-imports.json`: earlier actual Linux AMD64 BindCraft2 runtime imports passed with the same upstream source/dependency pins; CUDA initialization on the no-GPU host was unavailable.
- `reports/rapid-scientific-release.json`: final image/package versions, digests,
  tests, native package and remaining acceptance items.
- `reports/rapid-current-container-validation.json`: current source commit's
  actual AMD64 SSH/bootstrap, managed Python, persistent job and archive tests.
- `reports/rapid-scientific-native-package.json`: installed current app,
  all 48 Python resources and source-only worker archive match; saved 1 project,
  11 structures and 7 jobs; actual native SSH and local 154-residue target selection.
- `reports/rapid-coordinate-transport.json`: genuine existing 559-residue
  coordinates through actual upstream Protein arrays; original sequence and
  author numbering retained, serialization error below 1e-5. No new inference.

Current regression: **466 backend tests, 88 interface tests, TypeScript and
native release compilation passed**. Process-control fixtures additionally ran
real sleeping subprocesses and verified active cancellation/deadline termination
and diagnostic archives; these are not substitute molecular predictions.

One compressed deployable core image is retained at
`/Users/vii/Documents/FoldStudio-MetalPort/artifacts/RAPID-cloud-current.tar.gz`,
with its neighboring SHA-256 receipt. Its current image digest and source archive
digest are in `reports/rapid-scientific-release.json`. It includes the worker,
pinned source and approved installer, **not trained checkpoints or preinstalled
scientific environments**. Those install explicitly on the server. Heavy local
scientific image validation finished successfully; its VM and all temporary images
were deleted. It does not become another Mac release.
The native app stays at `../current/fold Metal Dev.app`.

A genuine previously computed 559-residue full-Fab rejected refold is used only
as an output-parser/transport fixture. Its original i_pTM rejection is retained.
It is not reported as a new GPU result. The public 115-residue hPDL1 coordinates
are used for actual no-GPU worker jobs. Private research is excluded from images.

Reference mode executes one original engine under the chosen bounds. The Rapid,
Exploration and Precision labels currently retain this same single-engine policy,
which is stated in the UI and receipts. **Adaptive cross-engine scheduling based
on measured GPU costs/yields remains unfinished**, as do additional engine families
and verified cross-engine refinement. No unsupported two-hour performance claim
or optimistic global completion percentage is made.

## Repeating development checks

From `/Users/vii/Documents/FoldStudio-MetalPort/fold`:

```sh
../runtimes/openmm-cpu/bin/python -m unittest discover -s tests -p 'test_*.py'
node node_modules/vitest/vitest.mjs run
node node_modules/typescript/bin/tsc -b
python3 -m build remote_worker --outdir /path/to/release/python-packages
python3 scripts/build-rapid-release.py --output /path/to/release
sh scripts/build-rapid-image.sh /path/to/release
python3 scripts/validate-rapid-container.py --managed-python
../runtimes/jax-cpu/bin/python -B scripts/validate-rapid-coordinate-transport.py
```

The source-only release is approximately 1.2 MB. The current core image archive is
approximately 1.6 GiB. The default build helper avoids automatic multi-GB image
exports; use an explicit requested export when replacing the one current cloud
deployment artifact. Local packaging automatically removes generated runtime
staging and Cargo build products, including directories Finder is observing.

For a scientific runtime image, use the same generated context with
`docker buildx build --platform linux/amd64 --target bindcraft2` or
`--target boltzgen`. Models are excluded. The manual CI workflow
`.github/workflows/rapid-worker.yml` builds/tests the AMD64 artifact and uploads
an explicit workflow artifact; it does not push a public registry image.

On an authorized NVIDIA worker, after approved checkpoint installation:

```sh
fold-rapid --root /data/rapid health
python3 /opt/fold-rapid-release/scripts/qualify-rapid-gpu.py \
  --root /data/rapid --output /data/rapid/qualification/report.json
# The command above writes NOT RUN. Actual execution must be explicit:
python3 /opt/fold-rapid-release/scripts/qualify-rapid-gpu.py \
  --root /data/rapid --output /data/rapid/qualification/report.json --execute \
  --bindcraft-manifest /data/private/bindcraft-reference.json \
  --boltzgen-manifest /data/private/boltzgen-reference.json \
  --complex-manifest /data/private/bound-complex-reference.json
```

The explicit suite runs real CUDA framework checks, checkpoint verification,
matched trained CPU/CUDA forward/gradient comparisons at `rtol=1e-4, atol=1e-5`,
original BindCraft, ProteinMPNN, held-out AF2 and full BoltzGen jobs. The final real
Mac-to-GPU result transfer and native inspection remain separate required checks.
Even a passing 16-residue numerical fixture does not certify independent full
trajectory equivalence or experimental binding.

Primary technical sources:

- [Pinned BindCraft2 source](https://github.com/PacesaLab/BindCraft2/tree/c0ee638d11bc010817c2c97ee58ed5c323e664e2)
- [Pinned BoltzGen source](https://github.com/HannesStark/boltzgen/tree/a07fea1153111ef453aaea7a15697ee05de9291f)
- [JAX CUDA installation](https://docs.jax.dev/en/latest/installation.html)
- [PyTorch versioned CUDA wheels](https://pytorch.org/get-started/previous-versions/)
- [Vast SSH connection guidance](https://docs.vast.ai/guides/instances/connect/ssh)

## Final no-GPU checkpoint

The core image and full BoltzGen/ESMFold2 image built for Linux AMD64. Both
scientific entry points imported again in fresh containers. The optional
cuEquivariance library reported missing `libcuda.so.1` on this no-GPU host;
imports passed, but no CUDA compatibility or scientific calculation is certified.
No checkpoints were loaded. The single retained core archive passed gzip
integrity validation. The temporary VM/images and native build staging are gone.

Next required hardware task: connect an authorized NVIDIA worker, explicitly
install approved remote checkpoints, and execute the prepared reference suite
above, starting with actual framework/GPU and matched trained forward/gradient
checks. Authentic engine campaigns and Mac result recovery must then pass before
CUDA readiness is announced. Adaptive multi-engine scheduling remains unfinished.
