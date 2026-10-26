# Explicit-background pathway enrichment

The Systems Biology workspace now implements gene-set membership over-representation with an explicit measured/testable background, attributed GMT gene sets and BH or BY multiple-testing adjustment. It does not complete the requested Systems Biology Explorer.

## Implementation and controls

`remote_worker/fold_rapid/editcraft_pathways.py` calculates the one-sided hypergeometric upper tail in logarithmic space, using the finite distribution support and recurrence. BH/BY correction retains the entire supplied hypothesis family, including non-significant and zero-testable-member sets. Extreme probabilities retain log values and explicit underflow flags; the native table does not present numerical underflow as an exact zero probability.

All selected identifiers must belong to the declared measured/testable universe. Duplicate identifiers, missing attribution, invalid thresholds and unsupported sizes fail before scientific execution. Identifier case/versions are retained; there is no silent alias conversion or inferred genome-wide universe. The bounded profile permits 50,000 background identifiers, 5,000 selected genes, 1,000 sets, 200,000 total memberships and a 3-MiB complete input.

The native form accepts attributed GMT text and explicit lists, records organism/namespace/version/source/license, and prepares the existing editable CPU workflow. An optional saved Scanpy cluster can supply its returned top-marker subset. That is explicitly exploratory, with a provenance snapshot of the source dataset/pipeline/cluster; it does not invent the missing tested-gene background or a complete differential-expression result. Manual editing resets the provenance to explicit user selection.

Production calculations use the existing isolated EditCraft cloud service, two CPUs and 4 GiB RAM. Review and separate transfer/workload approvals remain mandatory. No new scientific dependency, collection or model download is performed by this feature.

## Numerical verification

Six offline tests compare finite-population tails with independent enumeration of all sample combinations, check BH/BY against a hand-computed family, preserve non-significant hypotheses and reject inappropriate implicit inputs. A separate 111-case comparison against the already installed official SciPy 1.14.0 `hypergeom.logsf` includes extreme tails and a population of 50,000. Maximum absolute log-probability difference: **2.1101e−10**, below the declared 2e−8 tolerance. No scientific dependency was installed on the Mac; these are synthetic mathematical tests, not local biological research execution.

Primary method documentation: [SciPy hypergeometric distribution](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.hypergeom.html) and [statsmodels multiple-testing methods](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html). The implementation is original source; these document its numerical references rather than granting biological validation.

`fixtures/editcraft/pathways/finite-null-reference.json` specifies an independent ten-item population. One of C(10,3)=120 samples contains all three selected items. With three retained hypotheses, the expected raw p is 1/120, BH-adjusted p is 3/120 and BY-adjusted p is 11/240. `scripts/qualify-editcraft-pathways.py` requires fresh $1.25 approval, refuses an existing attempt, retains the real job and runs one bounded cloud calculation containing both correction stages. Numerical cloud results are recorded separately in `reports/editcraft/pathway-cloud-reference.json`; a pending or failed attempt is not acceptance.

## Remaining requirements

No Reactome/GO/STRING/BioGRID collection has been downloaded or independently verified through this feature. Attributed user-supplied text is retained as supplied, not labelled externally curated by the app. A real versioned biological collection/reference case remains necessary for biological qualification.

Enrichment is conditional on the supplied universe and selection process. BH requires independence or suitable positive dependence; BY is conservative under arbitrary dependence. Correlated gene sets are not independent replication. Statistical membership enrichment does not establish pathway activation/direction, mechanistic dynamics, causality, efficacy or cell identity. Experimental donor replication and perturbation analysis remain separate.

The wider scope still needs curated-data ingestion/qualification, interaction graphs, network analyses, perturbation context, mechanistic models and complete native/scientific acceptance. Full EditCraft completion remains false.


Cloud numerical reference completed: job `f0a38cbf98454007acef24005d7cb4bb`, one 300-second workload with both BH/BY stages, estimated reserve $0.1126. Raw/adjusted probabilities, exact overlap identities, outside-background handling and complete hypothesis-family retention passed. The separately approved scope allows up to $1.25 including source update/health; actual provider charges remain unknown. No scientific or numerical run is repeated automatically. Native results are tracked in `reports/editcraft/native-pathway-workflow.json`.

Final native check passed: both BH and BY tables are independently selectable, raw p and adjusted p match the saved reference, the five original cluster-5 Scanpy markers transfer unchanged into a draft, and the measured background stays explicit/empty. The original Scanpy result was restored for the user; no additional analysis ran during UI inspection.
