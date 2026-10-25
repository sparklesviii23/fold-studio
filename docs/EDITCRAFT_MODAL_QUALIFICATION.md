# EditCraft Modal qualification

Independent service: `fold-editcraft-engine`, app `ap-PUz8s2bH6RfRMDyzEf6x1q`. It uses `fold-editcraft-research` and `fold-editcraft-state`; the protein engine is not redeployed by this domain update.

Baseline core reference evidence is in `reports/editcraft/validation.json`. New release deployment evidence is in `reports/editcraft/model-deployment.json`. A healthy control function proves service availability and source identity, not scientific model execution or accuracy.

This session's authorization is **up to $3 total**: up to $1 isolated CPU build/deployment, $1 pinned model/source setup (~76 MiB retained), and $1 bounded public model/RNA reference calculations. No GPU and no private genomic or protein uploads. Actual provider billing remains separate from these allowances. No automatic retries or paid scope expansion.

Core runtime: Python 3.12, numpy 2.2.6, Biopython 1.85, ViennaRNA 2.7.2. Trained models execute through separate Python 3.10.18 environments defined in `editcraft_modal.py:trained_image`; original method dependencies are retained separately. CPU 2 cores/4GiB, per-plan deadline 30–600 seconds, one shared writer lease, retries zero, idle containers scale down. Child models remain in the owning scientific process group so cancellation/deadlines also stop nested upstream computations.

Setup is separately approved and idempotent by pinned content: matching assets are reused; differing existing assets are preserved and rejected. Checkpoint/source receipts retain every SHA-256, upstream revision and Git blob identity. The client cannot supply arbitrary installation URLs or commands. Preparation and molecular inference are distinct actions.

Qualification dimensions are tracked independently: adapter implemented; runtime built; assets installed/verified; genuine inference executed; published numeric reference agreement; independent benchmark reproduced; complete native workflow demonstrated. No method is globally qualified from a package import, a mock, an HTTP success or a health check.

Deployment/model preparation/model execution evidence must be read from the saved reports and actual result receipts. No inference outcome is assumed while its job is still running.

## Real reference outcomes

`reports/editcraft/model-validation.json` preserves the initial failed Rule Set 3 attempt, the missing legacy `pkg_resources` diagnosis and corrected runtime, then successful unchanged-input reproduction: −0.9003094354582534 and 1.1145162188484359 (published rounded values −0.90030944 and 1.11451622; tolerance 5e−6). BE-DICT ABEmax returned 15 supported bases with all five individual model runs. PRIDICT2 generated 765 candidate rows with two original model groups and five folds each. ViennaRNA ensemble checks passed expected MFE structure, ensemble-energy consistency and bounded unpaired marginals. Neither successful inference nor that numeric example establishes external scientific accuracy. Additional supported editor/tracrRNA reference checks are tracked in the same file.
