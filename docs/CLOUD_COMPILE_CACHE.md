# Persistent compilation cache

Implemented in source; not yet deployed or measured on CUDA.

The worker previously left JAX's cache location unset. The pinned BindCraft2 CLI
selects a campaign-output cache before its home cache, so those entries cannot
be reused by another stage's isolated job directory.

Unified stages now explicitly pass the stable worker cache root into the adapter:
`/data/rapid/compile-cache/<runtime-source-image-identity>`. Standalone workers use
`<worker-root>/compile-cache`. The existing data Volume commit at stage exit
persists entries, including rejected scientific trajectories. Future stages reload
that Volume before execution. This avoids making model storage mutable merely to
save executables. Cached files remain outside individual job result archives.

BindCraft design, AF2 refolding and upstream JAX ProteinMPNN use the explicit
`JAX_COMPILATION_CACHE_DIR` before imports. Compatible runtime receipts, source
pins and image identities share a namespace. JAX's own cache keys still determine
graph, compiler-option and accelerator compatibility. A shared directory does not
imply that a gradient executable can serve a forward-only refold or another shape.
Provenance records the directory with `reuseMeasured: false`.

No seeds, model pools, filters, precision, trajectory counts, time limits, resource
approvals or accelerator selections change. Existing campaigns are not restarted.
Activation requires an idle app update and approved idle cloud deployment.

The supplied analysis for campaign c38f508cebd56e3f38d227f4eb876efb is a useful
hypothesis, not a speed benchmark. Its approximately six minutes of low GPU use
can include preparation/loading/compilation; telemetry alone does not separate
those costs. The saved snapshot inspected during this change already contains
three completed AF2 stages, so its earlier log cutoff is not a current job status.

Outstanding verification: compare cold and warm jobs with identical shapes,
model pools, seeds, hardware and runtime; record cache reads/misses and phase
elapsed times; compare numerical outputs and immutable scientific outcomes.
No guaranteed 3x speedup or 90-second runtime is established. Sampling VRAM in
one short run does not establish safe L4/A10 capacity or equivalent performance.
Multiple trajectories require an explicit workload choice and revised quote.

## Approved paired benchmark

The user approved a total $4.50 allowance: up to $1 CPU deployment and two
BindCraft-only trials up to $1.75 each (estimated resource reservation $1.479
per trial). Both use source campaign c38f508cebd56e3f38d227f4eb876efb's
A100-40GB profile, seed 42 and original generator configuration. Each retains
its 900-second scientific limit. No redesign/refolding stages or retries are
included in this timing experiment.

Workflow purpose `compilation_benchmark` admits exactly one BindCraft generator
and no downstream engines; it never performs candidate selection or promotes
outputs to qualified candidates. Normal campaigns still require fresh prediction.
The first local admission attempt was refused before remote submission; its
receipt is retained in reports/cache-benchmark/admission-error.json.

scripts/run-cache-benchmark.py owns the approved pair, writes durable submission
intent, polls existing identities and submits the second only after the first
stage completes. It cannot restart an existing result record. Cache provenance
includes bounded file/byte counts before and after execution; these are cache
population evidence, not proof that any particular graph was read from disk.
Actual paired timings are recorded in reports/cache-benchmark/results.json.
