# Project Metal M2 — real ProteinMPNN sequence inference

Continuation of `3c64d55` on `project-metal/apple-silicon-engine`, 18 October 2026.
The original source/research data and existing interface remain preserved.

## Implemented

`scientific/mpnn_runner.py` runs the complete pinned upstream
`ProteinMPNNSequenceModel`: checkpoint loading, geometric input features, encoder,
autoregressive decoder, random sampling and upstream sequence scores. There are
no approximated neural layers or fabricated outputs. JAX runs explicitly on CPU.
This bypasses the incompatible JAX Metal stack for this subsystem without
claiming Metal acceleration or solving AlphaFold's accelerator incompatibility.

`scientific/mpnn.py` connects that model to existing structure IDs, coordinate
checksums, jobs, logs, cancellation, project export and sequence records. The
normal `mpnn_start` operation snapshots immutable coordinates, parameters,
selected design chains, fixed context sequences and the pinned upstream revision.
A background worker runs the isolated runtime. Successful results and all output
sequence records commit together; failures do not create successful outputs.
Source coordinates and fixed context sequences are checked inside inference.
Only selected-chain sequences are saved. No old sidechains are relabelled as a
new predicted molecular structure.

Existing local compute locking now includes ProteinMPNN, preventing concurrent
Boltz setup/prediction jobs. Cancel uses the existing verified process-group
ownership checks. Explicit restart creates a new experiment; cancelled/completed
jobs cannot be executed again by the model worker. No automatic costly retry.

The existing Architect design dialog now offers ProteinMPNN sequence redesign,
its own sample count, status polling and cancellation. All other chain sequences
are held fixed. Results refresh the shared library and remain available in
Sequence Workbench, normal job history and project ZIP exports. Navigation,
viewer, materials, lighting, CSS and camera behavior are unchanged.

## Files

- `scientific/mpnn.py`, `scientific/mpnn_runner.py`: workflow and real model runner.
- `scientific/worker.py`: allowlist, background worker, compute lock, runtime setting.
- `scientific/fold_engine.py`: registered ProteinMPNN adapter.
- `src-tauri/src/main.rs`, `src-tauri/tauri.conf.json`: native IPC/resource packaging.
- `src/components/DesignCampaigns.tsx`: additive controls in existing glass dialog.
- `tests/test_mpnn.py`, `src/components/DesignCampaigns.test.tsx`: workflow checks.
- `scripts/validate-proteinmpnn.py`: complete-model reference inference comparisons.

## Measured validation

`reports/proteinmpnn-validation.json` records full inference on the real upstream
hPDL1 (115 residues, neutral checkpoint) and hIL2R beta/gamma complex (387 residues,
negative checkpoint). The latter redesigns A while holding B fixed. Two samples
are generated per case with seed 2718 and temperature 0.1.

Adapter sequences and upstream scores match direct pinned-upstream invocation
**exactly**. A newly initialized model with the same seed reproduces the same
samples and scores exactly in the tested CPU environment. Fixed-chain sequences
and every input coordinate remain unchanged. This establishes integration parity
and reproducibility on these cases, not biological validity or independent
validation of the trained model. No comparison with an original PyTorch
ProteinMPNN implementation is claimed.

Full-model timings from the test process: approximately 1.02 s for hPDL1 and
1.34 s for the complex, including the measured inference call and checkpoint
loading. Peak process RSS approximately 521 MB and 771 MB respectively. These
figures exclude Python process startup and may benefit from existing JAX caches;
they are not cold-start or end-to-end binder-generation benchmarks.

A separate real background job completed for hPDL1 through `mpnn_start`, saved two
sequence records, and persisted its request, raw result, checkpoint hash, FASTA
and logs. `reports/mpnn-live-job.json` contains its isolated validation IDs.

Run:

```sh
python3 -B -m unittest discover -s tests
pnpm test
pnpm build
../runtimes/jax-cpu/bin/python -B scripts/validate-proteinmpnn.py
pnpm bundle
```

149 Python and 64 frontend tests pass (213 total); the existing private rotation
fixture remains skipped in this public-source workspace. Software tests include
invalid input rejection, absent runtime, compute locking, persistent job listing,
failed-runtime handling and cancelled-job execution refusal.

## Runtime and scope

Use the existing isolated JAX 0.11 environment via `FOLD_BINDCRAFT_PYTHON`, or the
persisted `bindcraftPython` setting. The relocatable engine location is
`<app data>/engine/bindcraft/bin/python`. Missing runtime errors are explicit;
no implicit dependency installation occurs. The development environment created
in M1 is reused without modifying Boltz's environment. The application bundles
source and ProteinMPNN checkpoints, but not the full Python/JAX runtime yet.

Initial UI workflow supports canonical, complete N/CA/C/O backbones with a single
model, resolved conformers, positive source numbering, one-letter chains, at
most 600 total observed residues and 1–8 samples. Unsupported input is refused,
not silently altered. Backend supports neutral/negative/positive shipped
checkpoints; UI currently exposes neutral at temperature 0.1. Other upstream
features (tied residues, arbitrary per-residue sequence constraints, multistate
redesign) are not exposed by this adapter yet.

Output is fixed-backbone sequence redesign. It does not generate a new binder
backbone, refold a candidate, predict binding/inhibition, or calculate affinity.
ProteinMPNN is operational on CPU; full BindCraft2/AlphaFold trajectories are
still blocked. No new ChimeraX command compatibility or standalone installer is
claimed. The prior PJRT/StableHLO blockers are unchanged and were not retried.

Next: validate full AlphaFold forward/loss/gradient pathways and parameter loading
with a compatible accelerator, integrate redesign constraints and folding
validation, and package a relocatable scientific runtime. The remaining broader
roadmap is still open; this milestone does not mark the platform complete.

## Packaged ANGPTL3 acceptance

The signed app resources executed a real background ProteinMPNN job on the
bundled 460-residue ANGPTL3 reference. Two sequence records were saved; source
coordinate bytes remained identical. Project export included request, raw model
result, FASTA and log. Measured model load/inference time was approximately 1–2 s, excluding
Python startup, with peak process RSS approximately 677 MB. This remains a cached-runtime
measurement, not a cold-start benchmark. See `reports/packaged-mpnn.json`.

Upstream `score` is mean negative log likelihood over resolved CA positions,
including fixed context where present; `seqid` is sequence recovery over those
positions. Neither is a calibrated binding score.

A packaged acceptance run caught and fixed interpreter-symlink resolution that
would bypass a Python virtual environment. The workflow preserves the venv
interpreter path; a regression test protects this behavior.
