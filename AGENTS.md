# RNA Design current checkpoint
Use the current installed app. Recovery fixes are installed and verified. Do not rebuild, retrain, or repeat the frozen benchmark for the next action. Read [RNA Design checkpoint](reports/rna-design/CHECKPOINT.md), [runtime contracts](docs/RNA_DESIGN.md), [benchmark](reports/rna-design/BENCHMARK.md), and [handoff](reports/rna-design/HANDOFF.md).
Installed simple and 38 nt design, distinct-candidate comparison, second-model disagreement, and exact Library save/reopen passed. UI resume now restarts polling explicitly. The 38 nt run added a fourth qualifier automatically, evaluations 9→10; saved record `85353cac-d830-4a38-81f4-6722b8a1c938` reopened exactly. Older saved snapshots remain unchanged. Installed resources match source 9/9; deep strict signature after app use passed. Checks: 33 backend tests, 12 interface tests, TypeScript, 173-module package closure. Full logs: `reports/rna-design/recovery-fix-*`.
Real Modal CPU completion/import/save/reopen and cancellation passed. Logical 30 nt run `1271ac85-c2fe-469e-91a5-327d0c5bf757` retains 522 evaluations and 1200 solver calls at 56.957495055 s. Its next resume failed before science with `[dumb-init] bash: Argument list too long`. The installed fix uploads saved state as a task-specific Volume JSON file through `FOLD_INPUT_FILE`; other recipes keep their transport. A local 334694-byte state-file check retained every old candidate and added exactly 38 evaluations. The solver core and resume seal did not change. Receipts: `reports/rna-design/modal-recovery-verification` and `MODAL_VERIFICATION.json`.
Exact next action requires approval of `reports/rna-design/MODAL_RECOVERY_RETRY.json`: one additional Modal container, 1 CPU core, 2048 MiB, no GPU, 180 s cap; resume the same state with total 4096-candidate / 60 s search limits, wanted 20, seed 1. Only about 3.043 s search remains. Added compute estimate US$0.0094968; billed cost unavailable. Five containers were allocated under prior approvals. Do not launch a sixth without approval. Verify automatic completion and no repeated evaluations, then restore the original context.
The original Library `/Users/vii/Documents/FoldStudio-MetalPort/validation/bindcraft-fab-amme-native`, project `fef08806-d3ac-4846-8143-60a76b8c1e63`, and Modal mode are restored. Scratch results stay in `reports/rna-design/release-library`; no scratch jobs are active. Keep Solver as default: 27 synthetic targets and 2 seeds give Solver 52/54, Qwen + Solver 51/54, direct Qwen 0/54. Qwen shows no useful overall gain. Preserve both inverse heads, prior Qwen folding/cell weights, labels, reports, and the research worktree. Labels and scores are computational predictions, not measurements.
Integration: `scientific/rna_design*.py`, `scientific/gpu_tasks.py`, `src/components/rna-lab/RnaDesignWorkspace.tsx`, native admission/resources, shared jobs, compute selector and capability registry. Contract `fold.rna-design-result/1` uses 1-based pairs, kcal/mol, s, and dimensionless scores. Research records retain exact inputs, scores, model/settings versions, run ID and result seal; no atomic coordinates or cell outcomes are implied. Reproducible commands, cache/resume rules and data/model paths: `docs/RNA_DESIGN.md` and the checkpoint.
Context Mode remains enabled. Fresh session: `ctx_resume`, then `ctx_doctor`; large logs/data: `ctx_execute`/`ctx_search`. First 18 November doctor failed on modified hooks and setup was blocked by EPERM; recheck passed all functional checks. Version 2.2.0 has a 2.2.1 update warning. No host setup or plugin upgrade was performed.
# Local build and storage policy

- Keep exactly one installed current fold build, at `../current/fold Metal Dev.app`. The current directory is a symlink to the existing app location; do not duplicate the bundle to a new release directory.
- Use `bash scripts/build-local-app.sh` for packaging. It guards running app/worker identities, replaces the existing app only when idle, verifies signatures, removes the prior bundle, and removes disposable build products. Do not create dated/versioned backup apps or automatic ZIP exports.
- Packaging runtime inputs in `../runtime-build` are disposable. The build script recreates them from the tested standalone runtimes inside the current app, then removes them. Keep independently configured development environments in `../runtimes` only when needed for scientific validation.
- Preserve source, Git history, trained model files, required runtimes, saved research, settings, and private credentials. The live research root is `../validation/bindcraft-fab-amme-native`; its name does not make it disposable test data.
- Keep one shared Boltz model store at that live root's `engine/models`. Other validation roots may link to it. Never remove a differing model on the assumption that it is a duplicate.
- GPU CUDA images and build virtual machines are optional developer artifacts, not local app dependencies. Build these only for explicit deployment/qualification work and remove temporary local images, environments and caches when finished. Do not download models or export multi-GB image archives automatically.
- Keep genuine scientific result evidence; do not claim that storage cleanup validates model accuracy or completes the unfinished GPU/Fab work.

# Current development strategy

For native Qwen RNA, start at `docs/QWEN_RNA_ENGINE.md`: worktree ownership, recovered cell-response engine, model/data paths, reproducible training/evaluation, contracts, benchmark failures, routes and current handoff. New code is `scientific/qwen_rna_{model,contract,runtime}.py` and `qwen_rna.py` (existing-style jobs/evidence/Library saves). Native Qwen loses to the compact and thermodynamic baselines on the frozen 24-SRP pilot; do not promote it or claim native 3D, inverse design or cellular behavior. Keep the research worktree and all prior checkpoints intact. The local installation receipt uses the existing external Torch runtime and shared base store.

Desktop inference uses bundled CPython 3.12 with qualified existing `gbcell` / `runtime-boltz` site-packages pinned in `qwen_rna_install.json`; it does not depend on launching the venv executable. A supervisor bounds its child's startup/imports/computation to 180 seconds plus 5 seconds termination; its own OS/Python bootstrap is outside that bound. Cancellation owns its process group. The verified desktop run took 154.09 seconds wall time, including cold startup, and 16.25 seconds inside the numerical worker. Preserve Python environment isolation. Use the guarded `scripts/open-local-app.py` launcher for native qualification; file-opening stalls and the actual completed run are recorded in the report. Reverify installed resource hashes after packaging, not just source tests.

Verify with `../runtimes/gbcell/bin/python -B -m unittest tests.test_qwen_rna tests.test_native_allowlist`, `node node_modules/vitest/vitest.mjs run --configLoader runner src/lib/qwenRna.test.ts src/lib/rnaLab.test.ts src/lib/jobs.test.ts`, and `node node_modules/typescript/bin/tsc -b`. Synchronize native action admission, resources, execution firewall and capability registry. Logs/data/failures: `reports/qwen-rna`; weights: shared library `engine/models/qwen-rna/pilot-v1`. Use scratch libraries for tests. Preserve Context Mode: fresh sessions call `ctx_resume`, then `ctx_doctor`; long logs/data use `ctx_execute`/`ctx_search`. No host tool/configuration changes were made.

Final handoff: `reports/qwen-rna/HANDOFF.md` (short) and `HANDOFF.json` (file hashes/evidence). The installed desktop sequence→native prediction→base/pair inspection→reference comparison→Library save/reopen walkthrough passed; its numeric matrix exactly matches the frozen benchmark. Original live Library and project are restored, with the user's **Modal/Cloud Mode preserved**. Local Qwen requires an explicit Settings → Compute servers → This Mac selection; do not bypass the existing cloud-only firewall. Qualification records remain in the separate `reports/qwen-rna/smoke-library`. No native 3D/design/cell-outcome capability is claimed.

Read `docs/CURRENT_IMPLEMENTATION_CHECKPOINT.md` before continuing. Full Fab is deferred by explicit user instruction: no local optimization, numerical debugging, memory profiling, porting, further cloud execution or automatic retries until the user explicitly resumes Fab. Preserve all code, outputs and research data.

Complete one small, independently testable feature per task. Reuse existing code, inspect only relevant files and run focused tests. Do not download models, launch paid compute or run large benchmarks without explicit approval. Record blockers and move to an independent task. Keep checkpoints concise; do not interpret the master specification as permission to work indefinitely on one subsystem.

# Experiment workspace (Cell Explorer › Workspace · real cell)

One workspace for opening a cell, exploring it, running an experiment in it, following what happens and comparing runs. It replaces the earlier Real cell · EM tab. Read this before changing `src/cell/workspace/`, `src/cell/em/`, `scientific/cell_em.py` or `scientific/light_pulse.py`.

## What the user does

`Open → Explore → Run → Inspect → Compare`, shown in the top bar.

- **Open.** Choose a cell context (top left). HeLa is the measured EM volume; E. coli is an illustrative rod that needs no download. Contexts without 3D geometry are listed and point to Virtual Cell.
- **Explore.** Orbit, zoom from cell to atoms, slice (X/Y/Z), clip box, per-compartment visibility, opacity and isolate, EM density, Cell Painting, volume bounds, scale bar, axis triad. Click a compartment or a molecule to select it; the inspector shows what is selected. Layers › Finer detail loads a region of the same dataset at 32–4 nm; it appears on the slice.
- **Run.** Two experiments. *Molecules in 3D*: up to four species, binding to a compartment, pair binding, boundary crossing with a permeability, synthesis, decay, conversion. *Light pulse* (E. coli only): a pulse editor or a measured schedule.
- **Inspect.** One timeline for the view and the plots. Click a chart, an event tick or an event row to go to that time and place. Follow a molecule; click an atom for chain, residue and atom.
- **Compare.** Branch keeps a run as baseline. Compare side by side replays the baseline in a second view under the same camera, slice, layers and clock.

Drawers (top right): Parameters, Solver, Provenance, Diagnostics. Shortcuts: `?` lists them.

## Files

| Path | Role |
| --- | --- |
| `scientific/cell_em.py` | Spatial engine 3.0: contexts and geometry, dataset install, finer regions, registration check, Brownian dynamics with binding, exchange, synthesis, decay, conversion, replicates, sweeps, crowding benchmark, painting, saved runs, comparison |
| `scientific/light_pulse.py` | Light-pulse experiment: dataset, mechanistic chain, learned and combined predictors, held-out benchmark, runs, sweeps, comparison, closed loop |
| `scientific/*_actions.py` | Action names only, so `worker.py` can route without NumPy |
| `scientific/virtual_cell_registry.py` | `cell_contexts`: species, cell type, state, geometry, measurements, models, experiments, validation per context |
| `scientific/virtual_cell_results.py` | Shared result adapter; sources `cell_em` and `light_pulse` |
| `fixtures/light_pulse/olson2017_ccasr.json` | Bundled measurements (CC BY 4.0) with source and SHA-256 |
| `src/cell/workspace/CellWorkspace.tsx` | The shell: context, panels, viewport, inspector, timeline, drawers, shortcuts |
| `src/cell/workspace/useSpatialRun.ts` | One streamed spatial run; two instances drive the side-by-side comparison |
| `src/cell/workspace/useLightPulse.ts`, `LightPulsePanels.tsx` | Light-pulse state, inputs, dock and drawers |
| `src/cell/workspace/SyncChart.tsx` | Chart with the shared time cursor, click to seek, event ticks |
| `src/cell/workspace/spatial.ts`, `spatialSetup.ts` | Picking, density field, units; setup ↔ engine request |
| `src/cell/workspace/workspace.css` | Styles, all under `.ws` |
| `src/cell/em/VolumeStage.tsx`, `volumeShader.ts`, `emGeometry.ts`, `molecules.ts` | WebGL2 stage, shaders, coordinates, structure models |
| `scripts/benchmark-light-pulse.py` | Reproducible benchmark → `reports/light-pulse-benchmark.json` |
| `tests/test_cell_em.py`, `test_light_pulse.py`, `test_native_allowlist.py`, `src/cell/**/*.test.ts` | Tests |

Wiring in `src/App.tsx`: `addToCell(item)` sets `cellRequest {item}`; Open 3D Run sets `{run, event}`; Open Experiment sets `{lightRun}`; View Results sets `cellResult {id, source}` for `VirtualCellLab`. `n` is a timestamp so the same request can fire twice.

## Adding a scientific action

Four places, or it fails in the installed app only: the `*_actions.py` set; `dispatch` in the module (and the routing block plus `ACTIONS |=` in `worker.py` for a new module); the `ACTIONS` array in `src-tauri/src/main.rs`; `bundle.resources` in `src-tauri/tauri.conf.json` (new files only). The native host refuses any other name with "Unsupported scientific action"; the development preview cannot show this. `tests/test_native_allowlist.py` fails when the interface names an action the host does not admit.

## Contexts and geometry

`cell_em.CONTEXTS`: `hela-jrc_hela-2` (measured) and `ecoli-bw29655-ccasr` (illustrative). `geometry(root, context)` returns the class grid, voxel size, meta and hash. Each context carries its own default slowdown with provenance: HeLa 3.2 (assumed); E. coli about 15.3, set so GFP diffuses at 7.7 µm²/s (Elowitz et al. 1999). A run records its context; runs from different contexts are not compared.

- **HeLa.** OpenOrganelle `jrc_hela-2` (CC BY 4.0), level `s4`: 750 × 100 × 398 voxels of 64 × 64 × 83.84 nm. About 40 MB, on request. Originals byte for byte with SHA-256 under `<library>/cell_em/data/jrc_hela-2/original`; derived grids under `derived` (rebuilt when `DATA_VERSION` changes, not when the engine version does). Cite Xu et al. 2021 (doi:10.1038/s41586-021-03992-4) and Heinrich et al. 2021 (doi:10.1038/s41586-021-04061-2).
- **Finer regions.** `cell_em_region` fetches the image at `s3`–`s0` for at most 256 × 128 × 256 voxels and 60 MB, stores blocks and manifest under `regions/<id>`, and places the region with that level's own voxel size and translation. No segmentation is loaded at fine levels.
- **Registration.** `cell_em_registration` reads every array's attributes. Result on the installed data: 64 × 64 × 83.84 nm everywhere, same grid, axes z, y, x; the foreground mask is offset by 2, 2, 2.62 nm (3.1 % of a voxel) and is used unshifted. The frame's origin is the corner of the first image voxel, (−2, −2, −2.62) nm in dataset coordinates.
- **E. coli rod.** Drawn on a 20 nm grid, 2.4 µm long, 0.9 µm wide: envelope shell, cytoplasm, nucleoid region. It reuses class ids `pm`, `cytosol`, `chromatin` with illustrative names. There is no image; the stage shows flat class colours and `cell_em_volume kind 'em'` is refused.

Classes: 0 outside, 1 cytosol, 2 plasma membrane, 3 ER, 4 nucleus, 5 mitochondria, 6 Golgi, 7 endosomes, 8 lysosomes, 9 lipid droplets, 10 vesicles, 11 chromatin, 12 nucleolus, 13 nuclear envelope; `EDGE` (14) is the edge of the volume. Segmentations are machine-learning predictions. Cytosol means inside a cell and in no segmentation.

Coordinates: micrometres along the dataset's x, y, z from the volume corner. The stage maps this to a world box whose longest edge spans −1…1; data y is world up. `toWorld`/`toUm` convert. The cut removes the side the camera looks from (`viewOf`), not the side the eye is on.

## Spatial engine

Category B. Overdamped Brownian dynamics of point particles on the class grid; the step is 0.35 of the smallest voxel edge for the fastest molecule; moves into a forbidden class are rejected.

- **Compartment binding, pair binding.** As before: per-encounter probability and release rate; Doi reactivity checked every 16 steps.
- **Pool of copies.** With any kinetic process a species has `capacity` slots; absent copies have state 3 in frames and do not move, bind or count.
- **Synthesis, decay, conversion.** Poisson(k·Δt) copies per step uniform in a compartment; first-order removal; A → B at the same place. A product may exist wherever it is made.
- **Permeable boundary.** A move stopped by the boundary class crosses with P = κ·√(πΔt/D) and lands in the nearest voxel of the far side within 5 voxels. P above 0.5 is refused. Complexes and bound copies do not cross.
- **Checks on every run.** Free-diffusion control, confinement, step length, and with kinetics: copies present = copies before + events.
- **Benchmarks (tests).** Two boxes equilibrate at κ·A·(1/V₁ + 1/V₂) within 15 %; synthesis and decay reach k_syn/k_decay with Poisson spread; conversion follows exp(−kt) and conserves copies; crowding matches Maxwell obstruction 1/(1 + φ/2).
- **RNG.** Extra draws are made only when a kinetic process is on, so a run without kinetics is the same stream as engine 2.

Every binding, permeability, synthesis, decay and conversion value is a user hypothesis. A structure enters the dynamics only through its radius.

Actions: `cell_em_catalog`, `_install`, `_volume`, `_simulate`, `_structure`, `_paint`, `_runs`, `_run_get`, `_compare`, `_replicates`, `_sweep`, `_crowding`, `_region`, `_registration`. Inputs out of bounds are rejected, never clamped. A chunk is 48 frames and returns frames (µm), `owner`, `bound`, `paired`, `absent`, per-species series including `present` and `occupancySeries`, `pairEvents`, `kinEvents`, checks and `state`. Saved runs: `<library>/cell_em/runs/<id>.json`.

## Light-pulse experiment

Data: Olson, Tzouanas & Tabor, Mol Syst Biol 2017;13:926 (doi:10.15252/msb.20167456), Dataset EV2, CC BY 4.0. E. coli BW29655 with CcaS/CcaR driving sfGFP; flow-cytometry means in MEFL. One 24-well plate is one schedule. 20 schedules: 8 step-on, 8 step-off, 4 dynamic programs with three runs each.

Model: light → regulator activity → transcription drive → mRNA → immature reporter → reporter, nine fitted parameters, mRNA turnover assumed. Each measured point is simulated with its own recorded 480-minute program. Predictors: mechanistic, learned (ridge on filtered light), combined, and a static dose-response baseline. The mechanistic chain is kept unless another predictor is more than 5 % better on the held-out schedules.

Split (`SPLIT`, fixed): 12 training schedules; held out: step-on 1.25 and 20, step-off 0.625 and 10, dynamic-green; missing input: the two schedules with red light; unsupported: the 380 nm schedule (no prediction).

Result (`reports/light-pulse-benchmark.json`, `scripts/benchmark-light-pulse.py`): held-out fold error 1.17 mechanistic, 1.92 learned, 1.17 combined, 3.79 baseline. Dynamic-green 1.26 against a run-to-run spread of 1.23. Red-light schedules 2.8 (amplitude over-predicted by 169 %): the failure case, shown, not hidden. Fitted doubling time 40.6 min against 37.4 measured and unused. The 90 % interval covers 82 % of held-out points.

Uncertainty: 200 parameter sets drawn from the fit covariance and kept only when the training error stays in the joint 95 % region. Do not sample the covariance directly; it overstates the poorly determined directions (k2).

Every saved run is recomputed by the Mechanistic Lab solver from generated SBML (rate rules, one event per light change) and must agree within 0.5 %. Runs are deterministic; `light_pulse_run_get` recomputes a saved run and reports whether every plotted value is identical. Closed loop is simulation only and is enabled when the open-loop gate passes (held-out error ≤ 10^0.15 on every schedule and at least twice better than baseline).

The fit is computed once per library and cached at `<library>/light_pulse/fit-<version>-<dataset>.json` (about 15 s). The native host starts a new Python process for each action, so nothing may rely on in-memory state.

Spatial meaning: none was measured. The rod shows where components sit (regulator at the envelope, transcription at the nucleoid, reporter in the cytoplasm) and paints model quantities on them, labelled Predicted response on Illustrative geometry.

## Rendering

- **Volume.** Ray-march over two R8 3-D textures (image linear, classes nearest), plus an optional coarse field texture and an optional detail-region texture. The image is sampled from the detail texture inside its box.
- **Selection and activity.** The selected class gets a rim glow; `activity[class]` adds emission. These are the only glows.
- **Molecules.** Far: one disc per copy with a trail. Near (model larger than 5 px): every atom as a sphere impostor, nearest first, within 1.4 million atoms. Absent copies are skipped.
- **Overlays.** Event rings from `playback.markers`; path of the followed molecule; bounds of the acquired volume; concentration field from the last 24 frames with a colour bar in copies/µm³ and nM.
- **Not simulated, only drawn.** Orientation, the side-by-side pose of a complex, atoms. Molecules are not occluded by the volume.
- **Cameras.** `onCamera`/`setCamera` mirror two stages. The stage is keyed by context: a context switch mounts a new canvas (reusing one loses the WebGL context).
- **Layout.** Panels are grid columns, not overlays; container queries on `.ws` shorten labels and slim panels. Below 1000 px opening one side panel closes the other.

Cell Painting (category D): each channel is a weighted sum of classes integrated along y and blurred (250 nm FWHM). Pixels are 64 × 83.84 nm; the dock draws images at the physical ratio (48.0 / 33.4 = 1.44) with a 10 µm bar, and merges the channels that are switched on.

## Evidence labels

Each has a word and a symbol as well as a colour: Measured EM, ML segmentation, Illustrative geometry, Simulated motion, Modelled concentration, Predicted response, Synthetic image; inputs are tagged fitted, literature or assumed. The EM specimen is HeLa; the Virtual Cell baseline is Hep G2. No readout is transferred between contexts.

## Testing and verifying

```bash
PYTHONDONTWRITEBYTECODE=1 "../current/fold Metal Dev.app/Contents/Resources/runtime/bin/python3.12" -B -m unittest tests.test_cell_em tests.test_light_pulse tests.test_native_allowlist tests.test_virtual_cell
```

```bash
node node_modules/vitest/vitest.mjs run src/cell
```

```bash
node node_modules/typescript/bin/tsc -b
```

Preview: start the worker on port 1425 (`worker.py --root <scratch library> --fixtures fixtures --serve 1425` with `FOLD_DEV_TOKEN`) and Vite on 5176 with the same `VITE_FOLD_DEV_TOKEN`. Restart the worker after any Python change. Headless Chrome with `--use-angle=metal` renders the stage and can be driven over the DevTools protocol for screenshots.

Do not write test runs into the live library: `cell_em_simulate`, `cell_em_paint`, `cell_em_region` and `light_pulse_simulate` save on every call. Use a scratch root, or pass `classes` with `root=None`.

## Known limits

- No model links structure to binding. Two designs with the same radius and rules give identical dynamics.
- Point particles: no shape, excluded volume or hydrodynamics. Crowding is a separate benchmarked capability that hands over one slowdown factor.
- Permeable boundaries are passive with one permeability; on a curved boundary the two faces differ in area, so equilibrium concentrations differ by that ratio.
- One static cell per context; organelles do not move. Fine detail regions carry no segmentation.
- The light-pulse model takes green light only, one strain, one medium, 37 °C, population mean. Red light is the stated next input.
- Local molecular dynamics is not connected to this workspace.
- The spatial and the light-pulse experiment share the workspace, the timeline and the result record, not a simulation: reporter abundance does not drive particle numbers.
