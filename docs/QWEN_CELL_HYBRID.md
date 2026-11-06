# Integrated biological Qwen model

The user explicitly requested an internal RNA expert, meaningful biological input, reuse of Cell2Sentence/GEARS code, staged training and removal of the fixed 12-pattern output restriction. This implements one bounded research model version. It does not automatically replace the app's validated default predictions.

## Actual combined architecture

`HybridCellModel` contains an `ExpertBank` with the frozen learned RNA predictor as a real PyTorch module. Its single-response calibration, encoder, neural weights, decoder and scaling live inside the combined model state. Inference does not invoke the former NumPy predictor, a subprocess or a language-model tool call.

The model computes the internal expert's numerical prediction plus a learned residual. The residual's full per-gene head and graph query start at zero; the real-model preflight verifies equivalence to the RNA predictor at initialization. Every candidate retains its zero-correction reference as an eligible selected checkpoint. Further fitting can still worsen unseen predictions, so this construction is not a guarantee of generalization improvement.

The output is an independent learned numerical channel for every one of the 2,132 measured genes. There is no global fixed rank-12 response decoder for the Qwen correction. Gene-output width is constructed from the supplied panel. It is finite; adding genes requires compatible expression/calibration data and weights. No unlimited hardware, parameter count or coverage is claimed. The existing RNA expert internally retains its original learned low-rank component; the new full-gene correction can express changes outside that component.

`ExpertBank` supports explicit registration/fusion of compatible experts with matching gene order, cell/intervention context and units. Registration does not prove an additional model helps. Additional modalities require their own adapters, training targets, provenance and evaluation. Arbitrary unrelated weights are not concatenated into Qwen.

## Biological input and reused source

The same approved Qwen checkpoint is used with its supporting official tokenizer assets (about 11.5 MB; no additional pretrained model). Inputs combine quantitative single-response features with gene-labelled text describing K562, CRISPR activation, the two target genes, expression-ranked baseline/single-activation genes and training-profile correlated neighbors. Numeric input remains separate from text so language generation does not substitute for numerical values.

The actual Cell2Sentence `generate_sentences` function is reused unchanged, along with its direct imports. Gene ranks are generated from the existing condition-mean expression profiles; this is not full single-cell C2S model training or reproduction of C2S results.

The actual GEARS `np_pearson_cor` function is reused unchanged. Correlations of known single calibrations and the 77 training-pair profiles define four positive neighbors plus self for each gene. A trainable graph-conditioned term accompanies the full-gene readout. These edges are associations, not causal regulatory measurements. Validation responses never define text, graph edges or foundation examples.

Licenses, NOTICE, pinned source revisions, function names and original file hashes are preserved in `vendor/cell-ai/PROVENANCE.json`, `c2s-LICENSE`, `c2s-NOTICE` and `gears-LICENSE`. Complete upstream dependencies/models are not installed or claimed reproduced.

## Staged learning

A small proof-of-pipeline curriculum precedes paired prediction:

1. Masked expression reconstruction on 16 existing training/calibration profiles, with hidden genes omitted from text and numeric inputs.
2. Known single-activation practice on 16 measured calibrations using baseline context plus the activation identity.
3. Full-pass paired-activation residual training on the same 77 training conditions.

The first two stages update Qwen adapters/numerical input and a separate auxiliary head; the pair-correction head remains zero/frozen. Thus biological representation practice preserves the internal RNA predictor's response until paired training begins. This is 32 calibration examples, not large-scale foundation pretraining.

Three versions are compared: a compact correction network receiving pooled frozen token embeddings, an adapted Qwen correction, and a matched Qwen correction whose internal adapters are frozen after the common foundation stages. The small correction receives the same input facts and foundation examples, with a smaller numerical architecture. All retain the internal RNA expert. The Qwen branches inherit the previous best attention adapters/numerical prefix, then share identical foundation weights before pair training.

Up to six full passes per version, batch size two, fixed learning rate 0.00002, correction-size penalty 0.1, validation early stopping after three non-improving passes. The entire three-version worker has a 900-second supervisor limit, plus at most five seconds to stop. No retry, cloud allocation or new model checkpoint download. The former 26 test outcomes stay excluded. The current 26 reused development cases choose checkpoints; they are not a fresh independent test.

Selected hybrid Safetensors files include internal expert buffers/weights, graph, numerical heads and Qwen adapters. The original frozen 3B backbone is shared. Genes and tokenized data are returned with the model package. Saved-weight reproduction, initial RNA equivalence, stage/freeze checks and full-gene output coverage are required. No automatic model promotion occurs, even if a development score improves.


The first execution (0a111538f81d44daa500e3532e165fc0) stopped after the small control's foundation stage, before pair training: a bitwise zero-correction check compared batch-two hybrid predictions against a single batch-26 expert call. MPS GEMM rounding differed by at most 1.1920929e-7. The failed record is preserved. The repaired check uses identical batching and retains exact equality; a new full-panel MPS regression check and real 26-context preflight pass. All 26 Qwen engineering checks pass. This repairs verification without loosening the numerical criterion.
