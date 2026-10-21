# RAPID / Cloud Compute foundation

This milestone implements the connection foundation requested after the larger
RAPID directive. No GPU server is currently available; no instance was rented,
provider account accessed, model weight downloaded, or research input uploaded.
This is not completion of the expanded multi-engine platform.

## Existing application preserved

The repository remains Tauri 2 / React 19 / TypeScript / Vite with the existing
Mol* viewer, Python scientific service, SQLite research library, original
BindCraft2 source, local Metal/CPU runtimes and trained-model provenance.

The five-section BindCraft Architect remains intact. Its landing title is
**Your design workspace.** The original peptide failure was a protected Metal
memory refusal; a genuine controlled CPU peptide run finished with a scientific
rejection. The cancelled production Fab remains cancelled, with five actual
optimizer updates. Its continuation automation remains paused.

The current work is on `project-omega/rapid-cloud-foundation`, branched from the
preserved `project-metal/apple-silicon-engine` history at `95c7f27`.

## Implemented now

Cloud Compute is a native sidebar workspace. It can save/edit connection profiles,
parse ordinary Vast.ai SSH connection strings, select an existing private-key
file or use an already unlocked SSH agent/Keychain identity, check a server's
fingerprint, explicitly trust the first identity, authenticate, transfer the
small reviewed worker and request actual health / CUDA numerical checks.

Connections use the maintained system OpenSSH client, launched by Python with
structured arguments and strict host verification. Unrecognized options, remote
commands and invalid host/user/port inputs are rejected. Provider-provided port
forwarding flags are not opened. A changed host key blocks connection; replacing
an existing trust record is deliberately unavailable in this first milestone.

Profiles and known hosts are private to the local application data directory,
with owner-only permissions. They are excluded from scientific settings and
project ZIPs. A private key's local path can be saved; its contents are never
copied into a profile, worker upload, log or project. This foundation offers no
API-token/password input or storage. Provider API token storage through Keychain
is a later milestone. Existing macOS OpenSSH Keychain support remains available.

## Worker protocol

The dependency-free worker implements protocol v1 over authenticated SSH stdin;
it opens no public network listener. Requests carry an API version and request
ID. The bootstrap installs a content-addressed, checksum-verified copy of the
reviewed worker. The native client verifies response version/request identity and
worker hash. No scientific code, model package or checkpoint is downloaded by
Prepare Worker.

Supported worker operations are health, engine inventory and small real CUDA
forward/gradient probes. PyTorch and JAX probes execute sequentially in isolated
processes, explicitly require CUDA and release each CUDA context on process exit.
An NVIDIA device name alone cannot establish readiness. Missing CUDA or an
incompatible environment produces a refusal; CPU fallback is disabled.

Scientific engines remain Not installed / Not configured, with remote campaign
submission unavailable. Even a successful tiny GPU probe is labelled as a GPU
check with scientific engines still required. Resource readings come from the
worker; unknown GPU, spending and provider information stay unavailable.

## Actual verification

A disposable OpenSSH server bound only to 127.0.0.1 was tested with generated test
keys. The client independently compared the generated host fingerprint, rejected
a changed host key and incorrect authentication key, then authenticated correctly.
The same encrypted connection transferred the reviewed worker to an isolated
temporary home, verified its hash, queried its health, and received the expected
real CUDA refusal on macOS. Test keys/listener were removed. The system SSH
service, Remote Login settings and user credentials were not changed.

This is genuine SSH/bootstrap/protocol evidence, not RTX 5090, Linux CUDA or
scientific engine execution evidence. See `reports/rapid-loopback-ssh.json` and
`scripts/validate-rapid-local-ssh.py`.

21 connection/worker tests cover input injection, identity/authentication errors,
timeouts, request/version mismatch, approval before code transfer, private-store
permissions, readiness invalidation and export boundaries. Frontend tests cover
honest readiness labels and the explicit foundation scope. The real worker
health/CPU-refusal path executes in subprocesses rather than mocked GPU success.
Native build and visual verification are recorded separately in the status matrix.

## Using the connection workspace

1. Open Cloud Compute and select Connect Your GPU.
2. Paste the provider's SSH connection and fill its details, or enter the fields.
3. Choose a local key if it is not already available through your SSH agent.
4. Save the profile, then Check server identity.
5. Independently compare the fingerprint before choosing Trust server.
6. Test Connection, then Prepare Worker for the small reviewed code transfer.
7. Check worker / Test GPU to inspect actual environment and numerical results.

No available server is needed to inspect the workspace or save a profile. Removing
an app profile does not stop an instance or change provider billing.

## Remaining RAPID milestones

Live RTX 5090/Linux testing, pinned CUDA scientific environments, remote original
BindCraft2 execution, result transfer/import, provider API/Keychain integration,
approved provisioning/shutdown/billing controls, durable job reconnection,
common cross-engine candidate representation, BoltzGen/other generators,
independent remote complex evaluation, scheduling and measured two-hour campaigns
remain unimplemented or unverified. No performance target is asserted as achieved.

The Anthropic optimization collection has been inspected as a future source. Its
individual tool kits have different supported modes and pinned upstream versions;
its README describes a static reference release rather than a maintained package.
No optimization kit is installed or claimed compatible with RTX 5090 here.

Primary references reviewed:

- [Vast.ai SSH connections](https://docs.vast.ai/guides/instances/connect/ssh)
- [Vast.ai instances API](https://docs.vast.ai/api-reference/instances/show-instances)
- [JAX installation and CUDA requirements](https://docs.jax.dev/en/latest/installation.html)
- [Anthropic optimization collection](https://github.com/anthropics/uplifting-biomolecular-modeling)

## Fab verification remains separate

The new inference-cache cleanup passes two actual JAX lifecycle tests and 78
bitwise-identical small trained-model array comparisons plus RNG, using original
three-recycle held-out models 2/4. The first downstream full-Fab test completed
original mutation, genuine ProteinMPNN and model-2 refolding, retaining the
original i_pTM rejection, then crossed the 14 GiB safety cap at model 4. A later
full-size retry ended with SIGTERM after approximately 604 seconds, without a
recorded terminating cause or completed refold. Thus the complete full-size cache
fix is **not yet verified**. No successful full original or accepted Fab is claimed.
