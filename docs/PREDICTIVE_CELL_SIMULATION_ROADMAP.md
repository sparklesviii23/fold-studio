# From the current Virtual Cell workspace to a validated simulation engine

5 November 2026. This is a proposed research and engineering plan, not a claim that these capabilities are implemented or that GenBio's internal architecture can be reproduced from public information.

A useful bounded simulator is feasible in principle. A generally reliable, unrestricted human whole-cell simulator is not established by our results. We cannot assign an honest percentage of the way to AIDO or promise success before training and external validation.

GenBio describes AIDO Cell as a persistent, intervention-conditioned world model with shared multimodal readouts and repeated experiments. Its public overview distinguishes the current closed-alpha simulator from the older open-source GB.Cell foundation model. Connecting GB.Cell or another individual model would not establish equivalent capabilities.

Primary sources: [AIDO Cell announcement](https://genbio.ai/aido-cell-simulator/), [GenBio model availability and naming](https://github.com/genbio-ai/Research-Overview), [virtual-cell world-model perspective](https://www.sciencedirect.com/science/article/pii/S0092867426010159).

## Current evidence

- Persistent cell identities, intervention histories, saved states, provenance and branching exist.
- Measured RNA, transcript isoforms, protein references, pathways, structures and microscopy are available within their documented contexts. These are often from separate experiments.
- Authentic Borzoi predicts specific reference-sequence assay profiles. Expanded evaluation covers 100 attempted genomic loci, 99 valid inputs, three assays and two replicas. It does not validate a drug-to-whole-cell transition.
- Nine treatment-response methods were evaluated. A validation-selected shrunken donor baseline modestly beats unchanged controls within this dataset; stronger statistical models do not. This is not an independently validated learned cell simulator.
- Mechanistic models simulate their specified equations. Their outputs do not establish an integrated learned human-cell model.

## Exact missing components and proposed implementation

| Component | What must be built | Required evidence before enabling it as a prediction |
|---|---|---|
| Dataset contract | `CellObservation`: stable cell/context ID, study, donor/clone, batch, assay, gene IDs, value units, control, perturbation target or compound, dose, time, replicate and missingness. Raw/count data and derived values remain separate. | Identity, units, control matching and source integrity checked; no outcome-driven selection or silent imputation. |
| Experimental split service | A frozen split manifest separating training, tuning and untouched tests; group by perturbation, combination and experimental batch/study according to the claimed task. | No matched experiment, duplicate or replicate leaks across the claimed holdout. A later independent-study test remains necessary. |
| State encoder | `encode(observations, context) -> state`: initially RNA only, then modality-specific encoders with explicit observed/imputed masks. Train or adapt a compact model on compatible data. | Reconstruction alone is insufficient; the representation must improve held-out intervention predictions beyond matched simple baselines. |
| Intervention transition | `transition(state, intervention, dose, elapsed_time) -> next_state_distribution`. Encode perturbation type, gene/target, compound representation and supported conditions. | Each intervention family passes its own untouched test. A knockout model does not automatically support drugs, overexpression or arbitrary sequences. |
| RNA decoder | Decode next-state gene measurements with an observation model appropriate to the data. Counts may use a count likelihood; precomputed log-fold changes need an appropriate continuous model. | Per-condition expression and response errors, differential-gene ranking and effect direction compared with unchanged, donor and additive controls. Avoid high absolute-expression correlation hiding weak response accuracy. |
| Additional readout decoders | Add protein abundance or morphology only where intervention-linked data support training. Later add chromatin or transcript usage where supported. | Each modality has its own truth, units and tests. Agreement between two predicted modalities is not proof of accuracy. Separate-cohort atlas measurements cannot be treated as paired observations. |
| Multimodal consistency | Shared-state training with explicit correspondence between paired observations; gene/transcript/protein identifiers and sample/time relationships retained. Permit modality-specific residuals rather than forcing exact correspondence. | Predict multiple measured outcomes for a held-out intervention; test cross-modal consistency and accuracy against actual paired outcomes. Show missing readouts rather than inventing a value. |
| Combination and sequence operator | Support multiple interventions with a defined state update and record whether updates are simultaneous or sequential. Retain state ancestry and supported elapsed-time range. | Hold out combinations and test interaction effects against additive models. Validate order effects on sequential experiments; endpoint-only data cannot validate treatment order or time evolution. |
| Temporal dynamics | Learn transition/dynamics from multiple measured time points, distinguishing treatment duration from time after treatment. Introduce known mechanistic constraints only when applicable. | Untouched time points and trajectories; stable rollouts, order effects and error growth checked. A smooth interpolation or illustrative animation is not temporal validation. |
| Calibrated uncertainty and domain checks | Predictive distributions or calibrated intervals; context and perturbation domain checks; abstention when unsupported. | Interval coverage and width on untouched data, including unfamiliar conditions. Model disagreement and graphical confidence scores are insufficient. |
| Engine runtime and registry | Versioned weights, preprocessing, dataset/split hashes, hardware/runtime receipt, supported-domain declaration, reproducible inference and resource/cost estimates. Preserve existing run controller and approval controls. | Clean-runtime reproduction; no hidden data fetches or automatic paid jobs; prior receipts remain interpretable after updates. |
| Prospective validation | Freeze new predictions before new measurements become available; compare with those measurements. | Success on independently produced measurements, including failed predictions, before stronger biological claims or experimental prioritization claims. |

## A concrete first implementation

**Scope:** K-562 genetic perturbation to RNA response, at supported experimental conditions. Begin by auditing the available Norman/Replogle inputs for usable cell-level measurements, controls, perturbation identities and licences. Existing derived reference matrices may support baselines but are not automatically adequate training inputs for a new model.

1. Build the dataset contract and a frozen experiment manifest. Inventory what is already local before downloading anything. Define a held-out task that the available data can actually support.
2. Reproduce unchanged, measured-response, additive and simple regression baselines on identical inputs and masks. Keep an untouched test sealed while selecting models on validation data.
3. Train a compact RNA encoder plus an intervention-conditioned response predictor. A residual transition in the learned representation is a reasonable initial design to test, not a proven solution. Select model complexity from actual training sample size and validation results.
4. Evaluate response magnitude, per-condition errors, correlations, effect directions and differential-gene ranking. Use grouped uncertainty estimates appropriate to the experimental sampling. Publish negative results.
5. Require a prespecified improvement over the relevant strongest simple baseline on the primary metric, without a material failure on key secondary metrics. Set that protocol before inspecting the test; do not choose a universal numerical improvement threshold after seeing results.
6. Repeat in an independent study or experimental batch suited to the generalization claim. Report limitations when only within-study tests are possible.
7. If RNA prediction passes, add one genuinely linked second readout. Compare a shared-state model with separate predictors to test whether joint learning helps.
8. Add drug conditioning, combinations and time only through separate data audits, training experiments and validation gates.

The first successful release should say exactly which context, intervention type, measurements and time conditions it supports. It should not expose unsupported combinations as if they were experimentally validated simulations.

## What the application would do

A user opens a supported cell, inspects measured baseline evidence, clones it, chooses an eligible intervention and sees the supported prediction domain and computation cost. A completed run produces a versioned predicted state. Readouts show source, units, intervals and validation domain. A further intervention is permitted only when sequential composition is supported by the registered engine. Unsupported readouts remain explicit.

The existing Virtual Cell identity, snapshot, report, structure handoff, benchmark and run-control systems can serve this workflow. The scientific engine, suitable linked data and predictive validation are the substantial remaining work.

## Boundaries for the next development stage

The current app integration does not train this engine, download new weights, launch paid runs, or claim AIDO equivalence. A compute estimate requires a dataset inventory and a small measured training/inference probe. Broad multimodal capability will require substantial research, data engineering and experimental validation; interface completion cannot substitute for that evidence.
