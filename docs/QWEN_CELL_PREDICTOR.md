# Qwen as the cell prediction engine

The user's intended direction is a Qwen-based biological predictor. Qwen must participate in computing the numerical prediction and receive biological prediction gradients; merely asking Qwen to invoke a separate RNA model does not meet this objective.

This checkpoint implements the first **development training path**, not a trained biological Qwen model or a deployed Virtual Cell replacement. No new pretrained checkpoint, paid compute, model merging, app installation or full Fab work was performed.

## Implemented architecture

Measured single-activation RNA responses in a fixed K562 background → frozen 16-dimensional single-response projection → 48 symmetric pair features → trainable four-token numerical input projection → Qwen transformer and learned readout query → trainable numerical head → 12-dimensional training-fitted response basis → 2,132-gene mean RNA-response vector.

The learned readout directly decodes Qwen's final hidden state. There is no additive response bypass, external RNA-predictor call or generated numerical prose in inference. Numeric prefix training is an experimental way of adapting Qwen; language pretraining may or may not help this task. Gene names are used to identify the calibrated single responses, not tokenized as language in this first pilot. The background is fixed K562, not a general learned cell-state encoder.

The pinned Qwen2.5-Coder-3B-Instruct architecture has 3,085,938,688 original parameters. They stay frozen. We add 530,444 trainable parameters: 102,400 rank-8 LoRA parameters in the last two layers' query/value attention projections, plus 428,044 input/query/readout parameters. Adapters alter Qwen's attention computations and receive gradients from the biological prediction loss. This is genuine adapter weight training; it is not full fine-tuning of the original 3.09 billion parameters, an increase in Qwen's original width/depth, or evidence that pretrained Qwen is a good cell model.

The completed suite has **nine** checks, including the safe training-artifact lifecycle. Tests use tiny, randomly initialized genuine Qwen architecture fixtures, explicitly not pretrained biological models. CPU, Apple GPU, and half-precision Qwen with float32 adapters are exercised. Tests establish loss backpropagation into Qwen adapters, unchanged frozen parameters, output sensitivity to an internal adapter change, saved-state reproduction, masked targets, held-out aggregation refusal and training-only numerical transforms. They do not establish biological accuracy.

## Prepared biological supervision

`scientific/qwen_cell_data.py` verifies the existing source and frozen RNA-model artifacts. It streams only the 77 training and 26 development-validation response aggregates, matched to loading-group controls. The previous 26 evaluated test conditions are blocked from outcome aggregation. Raw source bytes include the whole screen, but excluded outcomes do not enter the training bundle. Existing public-screen results remain retrospective.

The original gene panel and single-response encoder are reused. New input normalization and the output basis/center/scale fit only on training pairs. The original two activated targets are excluded from primary loss and scoring. The output basis is a bottleneck: it cannot express arbitrary changes outside its learned span.

Frozen RNA-prototype predictions are included for **training conditions only**, separately labelled as synthetic teacher targets. Teacher loss is optional and **zero by default**. This first pilot learns directly from measured RNA outcomes. Any later distillation experiment must distinguish matching a teacher from matching experiments.

The task requires known measured single-activation responses. It does not establish prediction for unseen genes, knockout, drug, sequential interventions, time, other cell lines, proteins, morphology, or a whole cell.

## One proposed pretrained-model pilot

- Existing runtime: `runtimes/gbcell/bin/python`, PyTorch 2.14.1 / Transformers 4.57.6; Apple GPU is available. No new training dependency installation is required for this path.
- Exact checkpoint: `Qwen/Qwen2.5-Coder-3B-Instruct`, revision `488639f1ff808d1d3d0ba301aef8c11461451ec5`. Official metadata records two Safetensors shards, configuration and shard index: 6,171,963,242 bytes total. License is identified as `qwen-research` in the provider card.
- Checkpoint is not currently installed in this compatible format. The existing Ollama inference model is retained.
- Proposed destination: the original library's shared `engine/models/qwen-cell/Qwen2.5-Coder-3B-Instruct` directory. Preserve required research/model files; no app-bundle copies.
- One local attempt, at most 30 optimizer steps and 900 seconds, plus up to five seconds for shutdown. The supervisor can stop a blocked native operation by ending only its owned process group. No automatic retry or cloud allocation. Runtime/memory fit of the complete pretrained model is not yet qualified.
- One fixed rank-8 architecture, last two attention layers, batch size one, AdamW learning rate 0.0001. Initial validation and checks every ten steps select a development checkpoint. Preserve both selected and final-step trainable weights.
- Compare development RNA MSE against unchanged, training-pair mean, additive and scaled-additive references. Do not open the old 26 test outcomes or claim new independent improvement. A later comparison should include the existing RNA prototype, frozen-Qwen/head-only and randomized/smaller-backbone controls to assess whether Qwen pretraining and adapter training add value.
- Safetensors export contains trainable weights only; no executable/pickle checkpoint. Hashes, parameter identities, development predictions, events and receipt are saved. Original frozen tensor versions are checked in the pilot; exact tensor equality is checked in the small fixtures.
- The CLI is offline-only and loads an explicitly supplied local checkpoint with remote code disabled. It does not download a model or automatically promote a result into Virtual Cell. The real pretrained pilot remains pending download approval.

Preparation:

```sh
/path/to/runtimes/singlecell/bin/python -B scripts/prepare-qwen-cell.py --root /path/to/library --out /new/data-folder
```

After the compatible checkpoint is explicitly approved and present:

```sh
/path/to/runtimes/gbcell/bin/python -B scripts/train-qwen-cell.py \
  --checkpoint /path/to/verified/checkpoint --metadata /path/to/QWEN_CHECKPOINT_METADATA.json \
  --data /path/to/prepared/data --out /new/pilot-folder \
  --steps 30 --maximum-seconds 900 --device mps
```

## How the other engines can contribute

| Existing resource | Potential role inside the Qwen-based system | Work still needed |
| --- | --- | --- |
| Norman paired-activation data and RNA prototype | Measured supervision and separately labelled teacher predictions | This narrow data bridge is prepared; pretrained Qwen has not been trained |
| Replogle knockdown, Tahoe drugs, DepMap RNA/fitness | Additional intervention tasks and separate numerical heads | Harmonize contexts, perturbation type, units, controls and splits; deduplicate prior evaluations |
| GB.Cell or another biological foundation model | Connected biological embedding encoder, or teacher representations | Check applicable model/output terms; train alignment and evaluate the contribution; weights are not directly concatenated with Qwen |
| Completed Borzoi results | Genomic regulatory auxiliary task or external prediction tool | Match sequence, coordinates, assay and cell identity to the training target; small completed results are not a complete cell-training corpus |
| HepG2 RNA, proteomics and microscopy | New modality-specific encoders/heads | Establish sample alignment and supervision; different experiments are not paired cell outcomes by default |
| Human-GEM, SPARCED, cell-cycle equations | Tools or labelled synthetic supervision / constraints within their valid domain | Define valid input/output mappings and assess numerical agreement separately from biological accuracy |
| Localization/pathway annotations | Context features and constraints | Annotation membership is not a measured intervention response |

Knowledge distillation trains a student from teacher outputs or representations. It can transfer selected behavior; it neither guarantees the teacher's accuracy nor adds the teacher's parameter count to Qwen. Connecting an encoder/expert physically adds parameters to the combined architecture, but its interface and any router must be trained. Arbitrary model weight files cannot be added together to obtain the sum of their capabilities.

Expansion should follow evidence: train adapters first, collect more independent intervention conditions, then compare larger adapters/backbones or specialist modules on the same agreed evaluation protocol. More parameters alone are not an improvement. The present 77 training conditions are a pipeline pilot, not a sufficient basis for broad cell competence.

A local resource inventory is saved with the task outputs. File availability is distinguished from paired data, usable supervision, applicable terms and validated model capability. Nothing is automatically uploaded or indiscriminately mixed into training.

## Sources

- LoRA: https://arxiv.org/abs/2106.09685
- Knowledge distillation: https://arxiv.org/abs/1503.02531
- Pinned official checkpoint: https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct/tree/488639f1ff808d1d3d0ba301aef8c11461451ec5


## Completed first approved pilot

The user approved the checkpoint download and one local run; it completed with 30 updates and exit code zero. The downloaded checkpoint is verified and retained. Selected checkpoint 20 has development MSE 0.00916606 versus initialization 0.00961283, scaled additive 0.00317439 and the existing RNA prototype 0.00261446. It is less accurate than both established comparators on the reused 26-condition development set. Fresh offline loading reproduces saved predictions exactly. Internal adapters changed; original Qwen weights remained frozen. Teacher loss was zero. No old test-outcome aggregation, independent test, retry or promotion occurred. The earlier preparation sections describe the initial design; checkpoint acquisition and the first pilot are now complete. See task outputs/stage4/PILOT_RESULTS.md and POSTRUN_VERIFICATION.json.
