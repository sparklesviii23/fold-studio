# First real Modal scientific campaign

Recorded 2026-10-24T11:40:06.621256+00:00. Campaign `06ea1581738361f2fe2ebd21146c4dd1`; terminal state **CANCELLED**. One new predicted peptide was generated, but no accepted candidate or complete cross-engine validation was obtained.

## Target and source

The unchanged saved ANGPTL3/8 fragment complex contains target chains A/B/C (50/50/54 residues), with the earlier20-residue peptide D as a reference. These are predicted fragment coordinates, not experimentally validated full-length biology. Reference SHA-256: `3e7ad918b6ec96f5234f993cd97a4836f3aebd59b20b41158fcfaede7492a0f0`. Source/config/checkpoint receipts accompany the stage. BindCraft2 revision `c0ee638d11bc010817c2c97ee58ed5c323e664e2`; original models1/3/5 and original scientific filters retained. Campaign seed42.

## Genuine generated result

Sequence: **MFDRNGPTPEELQEVLREVI** (20 residues). Design `design_l20_107b4fa0b79e0d0d`. New structure imported in the native Research Library under **bindcraft2 · design_l20_107b4fa0b79e0d0d** with the source label **rejected**. Unified candidate `3a471caca775a25805be32f2304ef0afb50a8918d6d91ed05ef5e163cedcd49a`. Coordinate SHA-256 `6c60951dd4428bad41d142342db6edbc45709a57280928ebaf8a44755d205736`.

The original optimizer passed screen, refine, anneal, harden and mutate stage gates; the final original confidence filters rejected the trajectory for i_pTM and pLDDT. Final optimizer log readings are rounded to i_pTM0.67/pLDDT0.66. These are **not** fresh held-out prediction scores, binding probabilities or evidence of biological suitability. Raw loss/sequence arrays, frames, CSV and original logs are preserved; no final filter was relaxed.

## Downstream stages and stopping reason

ProteinMPNN and SolubleMPNN each failed a separate120-second CUDA numerical startup check before model inference. A later diagnostic ProteinMPNN stage passed the CUDA check but was cancelled before producing sequences. I cancelled the campaign to stop additional paid startup failures. No ProteinMPNN/SolubleMPNN descendants, held-out AF2 predictions, independent predictor comparisons or remote geometry assessments were produced. There is no qualified frontier or successful evolution loop from this run.

The supervisor update now uses one cancellable process for framework initialization and the unchanged model entry point, an explicit engine/framework selection, a120-second startup bound, and a circuit breaker after the first failed model stage. Five offline process/contract tests plus two native resource/account guards passed. This mitigation has **not yet been tested on a real GPU**; the original startup timeout's underlying driver/import cause remains unresolved.

## Hardware, time and spending

Actual NVIDIA A10080GB PCIe, compute capability8.0, driver580.95.05; real JAX0.11.2 CUDA forward/gradient probe passed. BindCraft supervisor wall580.963seconds, remote stage591.753seconds. Campaign wall between persisted creation/terminal timestamps was about963seconds. GPU child PID attribution was unavailable: the old zero reading must not be interpreted as a measured peak.

Approved allowance$6. Preflight complete-resource reservation$5.3680568. Dispatched conservative resource reservations$2.367322; last elapsed estimate including safety$1.635310. These are estimates/reservations, **not actual Modal billing**. No provider invoice has been retrieved. The remote writer lease was checked released and the campaign remains cancelled. No second campaign was launched.

## Reproducibility and files

222 transferred artifacts / 30,325,062bytes were hash verified in `/Users/vii/Documents/FoldStudio-MetalPort/validation/bindcraft-fab-amme-native/cloud-qualification/06ea1581738361f2fe2ebd21146c4dd1`. `campaign.json` contains immutable IDs and exact settings; `stages/` contains authentic source/model provenance, raw outputs and diagnostics; `candidates/` distinguishes the unchanged reference from the rejected new sequence. Regenerable graph caches and duplicate archives were excluded from the local copy and retained remotely. The original saved research and cancelled Fab evidence remain intact.

## Native controls and remaining scope

Cloud Compute provides local review, explicit launch, saved-campaign refresh, cancellation, verified import and molecular viewing. The next interface revision adds shortcuts, installed-pipeline defaults and full-resource quotes. A10040GB and80GB are deployment choices; changing the selector does not alter an already-running GPU. Account reconnect replaces the current Keychain credentials only when requests are idle; named multi-account profiles are not implemented.

The full engine remains incomplete. The detailed24-component/seven-strategy assessment is in `docs/RAPID_COMPLETE_ENGINE_AUDIT.md`. BoltzGen/ESM/RFdiffusion model execution, ESMC design, licensed Rosetta, target-aware motif/chemistry/counterfactual handoffs and a fully qualified feedback frontier remain open. Another GPU campaign requires a new reviewed allowance; there is no promise that any fixed number of design attempts will yield an accepted or experimentally active binder.
