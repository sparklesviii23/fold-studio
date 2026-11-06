# Qwen continuation: full passes and RNA teaching

The user authorized the next Qwen training step. This is one bounded local study with three prespecified controlled continuations, not a hyperparameter search or a new independent benchmark. It reuses the already downloaded official 3B checkpoint and existing protected training bundle. It never downloads models, allocates cloud compute, reopens the old test outcomes, retries automatically or promotes a model into the default app engine.

All three versions start from the same saved update-20 Qwen pilot, whose development MSE is 0.00916606. The original Qwen base parameters remain frozen. Architecture, input features, response basis, seed, batch order, learning rate, weight decay, stopping rule and validation cases are shared.

| Version | Further Qwen adapter training | RNA teacher loss weight | Purpose |
| --- | --- | ---: | --- |
| measured | Yes | 0 | Effect of more training on real outcomes |
| teacher | Yes | 0.2 | Incremental effect of teaching from the RNA predictor |
| frozen_qwen | No | 0.2 | Whether further Qwen adapter training helps beyond numerical layers |

The frozen-Qwen control retains the pilot's already adapted Qwen computation; it freezes those internal adapters and trains only the numerical input/query/readout layers. It tests the value of **further** adapter learning, not the value of language pretraining or Qwen versus a random backbone.

Each version gets up to 20 complete passes over 77 training conditions, with batch size seven (11 updates per full pass). The order is deterministically reshuffled each pass, identically across versions. AdamW uses learning rate 0.0001 and weight decay 0.01, gradient clipping at one. Development validation and measured training MSE are recorded every epoch. Stop after five epochs without a development-MSE improvement of at least 0.000001; preserve both the best selected and final-step added weights. Selection may retain the initial pilot if further training makes it worse.

Teacher targets are the frozen RNA predictor's outputs for the 77 training conditions, already stored separately from measured outcomes. Measured RNA loss remains the primary term; teacher loss is additional. No teacher or other engine is needed to compute the trained Qwen model's predictions. Validation is always scored against measured outcomes, excluding the two directly activated genes.

The existing training-only 12-dimensional output basis has a development-only oracle projection floor of about 0.00234614 MSE, versus the RNA predictor's 0.00261446. This is a representation diagnostic using validation outcomes, not an attainable forecast or a fitted model: the oracle codes never enter training or inference. It indicates that the current output space does not by itself rule out matching the RNA model on these particular development cases.

The maximum budget is **900 seconds for the whole three-version worker**, plus at most five seconds for stopping. A separate supervisor owns the worker process group, preserves partial evidence and updates the existing native Runs & terminal controller on success, stop, timeout or failure. No next attempt is submitted automatically. All selected checkpoint files are reloaded and their stored development predictions reproduced before the comparison is marked complete.

The comparison uses the same previously reused 26 development-validation conditions. A winner on this set is a development candidate, not independent evidence of generalization, whole-cell simulation or AIDO equivalence. Original RNA predictions remain the default. Preserved references are the previous Qwen pilot, scaled additive and the existing RNA prototype. Report whether teacher loss and further internal adapter training helped on development; do not assume that either must improve accuracy.

Implemented in `scientific/qwen_cell_curriculum.py`, launched through `scripts/run-qwen-cell-curriculum.py`. Seven new checks plus nine existing Qwen checks pass using tiny genuine Qwen architecture fixtures on CPU and Apple GPU. They cover full-pass coverage/reshuffling, matching starts, teacher versus measured controls, frozen weights, validation-gradient isolation, corrupted warm starts and failure cleanup. They are engineering tests, not biological accuracy results.
