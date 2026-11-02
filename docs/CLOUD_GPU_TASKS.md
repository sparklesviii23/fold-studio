# Compute Servers and Cloud GPU Tasks

30 October 2026.

## Settings › Compute servers

- **Server picker** for the whole app:
  - This Mac;
  - your Modal account;
  - any saved SSH/Vast GPU host.

  It uses the existing `execution_backend_select` firewall: in cloud mode, local scientific stages are refused rather than silently run on the Mac.
- **Modal accounts** reuse the existing account system (`cloud_accounts.py`, `modal_account.py`):
  - **Sign in:** the official browser sign-in.
  - **Save account:** stores separate token pairs in the macOS Keychain.
  - **Switch account:** applies to new runs.
  - **Rename account.**
  - **Sign out:** removes a saved account from the Keychain. Accounts that own saved campaigns are kept, so their results stay recoverable.
- **Other providers** (RunPod, Lambda, CoreWeave, AWS, Google Cloud, Azure) are listed as *coming later*. Nothing about them is implemented or stored.

## System › Cloud GPU Tasks

Every GPU workload is a declared **recipe**: a container image, a command, validated inputs, outputs, a licence and an evidence label (`scientific/gpu_tasks.py`). A run works like this:

1. You approve the cost. Nothing launches without approval.
2. A detached provider process, running with the active account's Keychain credentials, builds the image. Builds can take minutes, and the provider caches them.
3. It starts a **Modal Sandbox** in the app `fold-gpu-tasks` with the Volume `fold-gpu-cache` mounted at `/cache`.
4. The task writes its results to `/cache/out/<task id>`, plus `environment.txt` (`pip freeze`) and `gpu.txt`.
5. The app polls the sandbox. When the task finishes, it downloads the outputs into `<library>/gpu_tasks/<id>/outputs`, with a SHA-256 for each file, and keeps stdout and stderr.
6. **Terminal:** while a task runs, commands can be executed *inside that container* (`sandbox.exec`). Each command needs approval and is logged to `terminal.jsonl`.
7. A task can be stopped (terminated) at any time.

There is no local fallback: a remote failure is reported as a failure.

| Recipe | For | Licence | Status |
|---|---|---|---|
| RhoFold+ (ml4bio/RhoFold @ 6bdfbda) | Demo 9: RNA 3D from sequence | Code Apache-2.0. The weights' licence is not stated on the model page, and the dataset is non-commercial: treat as research use | **Recipe written, not yet executed.** The first run validates the image build. |
| Boltz-2 (`boltz>=2,<3`) | Demo 9: RNA structure ensemble (independent diffusion samples) | MIT | **Recipe written, not yet executed.** |
| HemoCell (UvaCsl/HemoCell, pipe-flow example, 16 CPU cores) | Demo 7: deformable red-cell flow | AGPL-3.0; runs only on your server | **Recipe written, not yet executed.** The playback adapter needs its real HDF5 output format. |
| Custom | Any public image or pip model with your command | Yours to check | Ready |

**Demo 9 analysis** (`scientific/rna3d_compare.py`, runs locally on returned PDB files):
- C1′ RMSD to the tRNA-Phe crystal structure 1EHZ (bundled mmCIF);
- pairwise RMSD between predicted models, i.e. model disagreement, which is not a trajectory;
- steric clashes;
- whether the cloverleaf base pairs from the reference secondary structure are geometrically present.

Checked on the crystal itself: RMSD 0, 0 clashes, 100 % base-pair geometry.

## Verification so far

`tests/test_gpu_tasks.py` (7 tests) covers:
- recipe catalogue and input validation, including image names, file names and GPU types;
- refusal without cost approval;
- the full launch → poll → download → record lifecycle against a simulated provider, including a path-traversal guard on returned files;
- failed-launch reporting;
- the RNA 3D analysis on 1EHZ;
- worker routing without the provider SDK.

Modal SDK 1.6.2 (the pinned provider runtime) was checked to provide every call used:
- `Sandbox.create` with `gpu`, `volumes` and `env`;
- `Sandbox.from_id`, `poll`, `exec` and `terminate`;
- `Volume.listdir` and `Volume.read_file`.

**Not yet done:** no task has run on a real Modal account. That needs your approval, because image builds and GPU time are billed to you.
