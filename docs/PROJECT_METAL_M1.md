# Project Metal — milestone 1

Development date: 18 October 2026 (Europe/Bucharest). This is working foundation
code and a narrowly validated numerical port, **not a completed BindCraft2 port**.

## Recovery and isolation

The authoritative development repository is the existing `outputs/fold-studio`,
clean on `fix/main-app-tools` at `460c2ae` (Fold Studio 4.3). The existing
`~/Documents/FoldStudio-MetalPort/fold-studio` was a byte-matching public 4.3 export,
with its private fixture deliberately omitted. It was preserved as baseline
commit `d121311` before changes. New work is on `project-metal/apple-silicon-engine`.
The original source, research database, compiled applications and release ZIPs
were not replaced. Baseline frontend source is recoverable from that commit.

Actual architecture: React 19, TypeScript 5.8, Vite 6, Tauri 2/Rust; Mol* 5.13.1;
stdlib Python JSON IPC and SQLite WAL. Existing tools include Boltz-2 MPS
prediction, GUI-free ChimeraX 1.12 integration, command history/registered native
command introspection, peptide construction and Molecular Intelligence interface
analysis, confidence, comparisons, screening and exports. Earlier rendering
clipping fixes and all existing viewer/material/lighting code are preserved.
Public export evidence does not assert full native command validation.

The development app has a separate bundle identity `org.foldstudio.metalport`
and name `FOLD STUDIO Metal Dev`, isolating its default application data. Preview
uses ports 1424/1425, separate from the original preview. Existing interface CSS,
renderer, materials, camera controls, navigation and Molecular Intelligence UI
are unchanged. Architect has one additional button opening an existing glass
dialog pattern. No ChimeraX/BindCraft user interface is embedded.

## Working implementation

- `scientific/fold_engine.py`: central engine/operation registry exposed through
  the existing Python and Rust allowlists. Shared structure references include
  existing project/structure IDs, coordinate checksum and model identity. Atoms,
  residues and chains use the same parser/IDs as Molecular Intelligence. The
  module does not maintain a second coordinate database.
- Existing SQLite jobs are used for campaign state (`preparing`, `prepared`,
  `failed`, `imported`). Settings, source bytes, residue correspondence, seed and
  upstream digest are saved in the existing project jobs directory; restart and
  project archive export work. Failed preparation is recorded and never starts
  computation. Existing Boltz/Molecular Intelligence queues remain intact.
- `vendor/bindcraft2`: 187 unmodified upstream tracked files pinned to
  `c0ee638d11bc010817c2c97ee58ed5c323e664e2`, including original notices and shipped
  ProteinMPNN/HyperMPNN checkpoints. `vendor/bindcraft2-source.json` checks every
  source/checkpoint. No model download occurs during inspection or preparation.
- Campaign validation supports the upstream binder and linear peptide presets:
  explicit saved target, one-letter chains, observed hotspot/coldspot identities,
  binder length range, desired count, attempt bound and integer random seed.
  Unknown fields, invalid/conflicting sites, wrong projects, missing backbone,
  altered source checksums, unresolved alternate conformers, multiple models,
  insertion codes and unsupported modalities fail explicitly. Initial selection
  requires canonical residues with N/CA/C/O and positive source numbering.
  There is no inferred biological/full-length residue correspondence.
- The generated upstream configuration uses stock attention, disables cuEq and
  multi-GPU execution, and preserves genuine preset defaults. Config files are
  prepared; full upstream preflight/model execution is not implied by validation.
- Ranked output import understands upstream `3_Ranked`, `!_Ranked.csv` and
  `campaign_metadata.json`. Real coordinate parsing happens before database
  writes. It retains raw scores/settings/revision and source SHA-256 checksums;
  idempotent imports are transactional. Failed/rejected trajectories are not
  imported as accepted candidates. Symlink escapes and ambiguous design IDs are
  refused, with size/count limits. Imported structures use the normal Research
  Library and existing Molecular Intelligence/viewer. Coordinate B factors are
  not automatically relabelled as pLDDT. Imported provenance is explicitly
  `external_unverified`; no correspondence to a prepared target is assumed.
- `scientific/fold_compute.py`: bounded subprocess discovery of isolated JAX and
  existing PyTorch runtimes; actual device reports; explicit blocked design state;
  no implicit installation, no remote execution, no upload.
- `scientific/metal_attention.py`: genuine experimental float32 PyTorch CPU/MPS
  implementation of upstream stock/chunked attention, with gradients. It preserves
  upstream scale=1, clipped logits, bias broadcasting and fully masked-row
  behavior. This is one kernel, not a replacement AlphaFold model. Large
  activations/checkpointed memory management remain future work.

## Dependency and accelerator audit

`reports/bindcraft-audit.json` includes the exact upstream dependency declaration,
all 53 imported module roots with source locations, 29 accelerator-related source
references, and every shipped modality/property preset. CUDA13/CUDA12 optional
extras, cuDNN fused attention, cuEquivariance fused triangle updates, multi-GPU
worker selection and NVIDIA hardware tuning are not a macOS backend. Upstream
also has stock JAX attention/triangle paths; these are the reference rather than
rewriting the scientific objective. JAX 0.11 is required by this pinned revision.

Isolated runtimes under `../runtimes/` were created for development only. The
existing Boltz environment was used read-only to execute the MPS kernel check;
its packages were not changed. Complete diagnostic environment pins are retained
in `reports/requirements-jax-cpu.txt` and `requirements-jax-metal.txt`.

## Measured numerical validation

`reports/metal-attention.json` compares upstream JAX 0.11.2/JAXlib 0.11.2 CPU JIT
against PyTorch 2.14.1 CPU and real `mps:0`, with CPU fallback disabled. Three
synthetic cases cover odd query/key lengths, multi-head batches, broadcast biases
and a fully masked row. Both unchunked and chunk-size-3 outputs plus reverse-mode
gradients with respect to Q, K, V, bias and nonbatched bias were compared.
Upstream's actual checkpointed/chunked gradients were also compared to its stock
path. All comparisons pass atol 3e-5 / rtol 3e-4. Largest absolute discrepancy on
MPS across these cases: **2.9802322387695312e-8**. This establishes local kernel
parity on these small cases, not a full model's accuracy, speed or memory fit.

`reports/upstream-input-validation.json` runs the actual upstream settings and
protein preparation loaders on hPDL1 and the bundled ANGPTL3 reference, for both
binder and peptide presets. Observed residue counts, hotspot/coldspot flags and
backbone atom identities agree. Maximum backbone coordinate difference is below
4e-6 Å, consistent with upstream float32 conversion. No AlphaFold weights or
prediction are used in this test.

`reports/jax-metal.json` records real attempts with JAX/JAXlib 0.11.2 and Apple's
jax-metal 0.1.1, both with and without ENABLE_PJRT_COMPATIBILITY. Without it:
PJRT plugin API 0.47 vs framework 0.115. With it: M4 Pro enumerates, but the first
array operation fails with `unknown attribute code: 22`, bytecode version 6,
StableHLO_v1.16.2. Thus a direct current-upstream JAX Metal forward/gradient test
is blocked before a forward calculation. The compatibility flag does not make
this stack functional.

Apple labels its plugin experimental and lists incomplete operation/dtype support:
https://developer.apple.com/metal/jax/
JAX installation reference: https://docs.jax.dev/en/latest/installation.html
Do not silently downgrade JAX below upstream's declared requirement or describe
CPU JAX execution as Metal acceleration.

Timing records in the attention report include process/kernel initialization:
MPS tiny-case forward+backward took approximately 0.23–1.52 seconds, while CPU
cases took 0.0007–0.035 seconds. These are diagnostics, **not a speedup benchmark**.
No full model peak-memory or sustained design-throughput measurement was made.

## Scope / parity matrix

| Component | Configuration/import | Native design execution |
|---|---|---|
| binder | Implemented; tested against upstream input preparation | Blocked |
| peptide | Implemented; tested against upstream input preparation | Blocked |
| cyclic_peptide | Not started | Blocked |
| VHH | Not started | Blocked |
| scFv | Not started | Blocked |
| Fab | Not started | Blocked |
| ARP | Not started | Blocked |
| large_binder | Not started | Blocked |
| multidomain | Not started | Blocked |
| homo_oligomer | Not started | Blocked |
| fold_switch | Not started | Blocked |
| induced_fit | Not started | Blocked |
| ProteinMPNN redesign | Shipped source/weights retained; integration not started | Blocked |
| Multitarget/negative design, scaffolds, property constraints | Presets inventoried; adapter not started | Blocked |
| AF2 attention | Experimental MPS port; small reference forward/gradient tests pass | Full model blocked |
| AF2 Evoformer triangles, IPA, recycle/loss/optimizer/model weights | Source audited; no complete native port | Blocked |
| Ranked result import | Implemented and software-tested | External computation only |

Existing ChimeraX command dispatch, native command inventory, parameter schemas,
shared scene and Mol* renderer remain in place. This milestone adds **zero new
validated ChimeraX commands** and makes no full-coverage claim. Qt-dependent tools,
advanced scene synchronization/undo and expanded command compatibility remain
tracked by the existing capability audit. No restricted ChimeraX source or
executable is vendored. Source permission/attribution and standalone packaging
are handled separately from numerical backend readiness.

## Reproducing checks

From this source directory (use installed pnpm and a Python 3.12 runtime):

```sh
python3 -m unittest discover -s tests -v
pnpm test
pnpm build
python3 scripts/audit-bindcraft.py
../runtimes/jax-cpu/bin/python scripts/validate-bindcraft-inputs.py
../runtimes/jax-cpu/bin/python scripts/validate-metal-attention.py \
  --torch-python '/path/to/existing/torch/python' --output reports/metal-attention.json
python3 scripts/probe-jax-metal.py --python ../runtimes/jax-metal/bin/python \
  --output reports/jax-metal.json
pnpm bundle
```

Set `FOLD_BINDCRAFT_PYTHON` to the isolated CPU runtime to expose its diagnostics.
A normal development app uses its own data directory. `FOLD_DATA_DIR` can point
to a disposable validation library. No automatic expensive job resumption exists.
`bindcraft_start` always returns an explanatory error and spawns nothing.

The desktop build includes the versioned BindCraft2 source; it **does not yet
include a relocatable Python/JAX/PyTorch runtime, AlphaFold parameters, or bundled
ChimeraX**. Users still need existing prerequisites for those tools. A single
self-contained installer remains unfinished. Existing engine functions remain
usable independently when their usual runtimes are present.

Next computational milestone: choose/build a JAX 0.11-compatible PJRT backend or
extend the verified MPS primitive path through Evoformer triangle operations and
IPA, then check small complete AF2 forward/loss/gradients and memory against the
same pinned CPU implementation before enabling genuine design campaigns.

## Final milestone acceptance

142 Python tests and 64 frontend tests pass (206 total); one existing private
rotation-fixture test is skipped in this public-source workspace. TypeScript and
Vite production build pass. The arm64 Tauri app builds and its ad-hoc code
signature verifies. Packaged resource IPC, full pinned-source checksums, isolated
bundle identity and ANGPTL3 input-byte preservation pass. Native UI testing saved
a real ANGPTL3 prepared campaign; it appears in the saved campaign list. The
original source repository remains clean. See `reports/milestone-summary.json`,
`packaged-smoke.json` and `native-campaign-saved.png`. No real binder-design or
AF2 full-model forward/gradient run has completed in this milestone.
