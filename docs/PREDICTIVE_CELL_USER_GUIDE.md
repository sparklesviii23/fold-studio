# Virtual Cell · where to find everything

Open the installed Fold Studio app, select **Predictive biology · independent evaluation** in the project menu, then open **Virtual Cell** and **Predictive evidence · Hep G2**.

| Section | What it contains |
|---|---|
| Cell workspace | Cell visualization, supported interventions, measured/modelled readouts, data coverage, saved states and branching. The geometry remains illustrative. |
| Microscopy | Observed compatible Cell Painting images and the existing morphology tools, with their documented limits. |
| Genes & regulation | Search ANGPTL3, ALB or another resolvable gene. Inspect measured RNA, transcript isoforms, protein abundance, localization, pathways, saved structures and compatible Borzoi profiles. Save gene evidence to the cell's state history or export its report. |
| Benchmarks | Original and expanded response comparisons, additional evaluation cases and the completed Borzoi panel. Undefined metrics, failed cases and scientific limitations remain visible. |
| Runs & terminal | Run lifecycle, live/retained terminal, command history, returned files and existing approved-start/stop controls. Switch between this project and all library runs. Opening a result does not start a new computation. |

The saved study contains eight run records, including failures and the successful final evaluation; the library also retains its previous run history. The completed evaluation has 14 saved output files. Benchmarks compare nine response methods and include 180 additional conditions. The regulatory panel attempted 100 held-out loci: 99 valid inputs, plus four separate illustrative loci, across three assays and two model replicas.

ANGPTL3's saved regulatory profiles are **illustrations from fold5**, not held-out accuracy evidence. Different assay units and evidence types remain separate. The treatment predictor is not validated for parental Hep G2; HepG2/C3A is a different biological context.

The import preserved all 57 existing records, all five existing projects, their jobs/settings and original asset/cell files. The study was added as a new project; it did not replace the library. The source remains on the isolated `codex/predictive-cell-stage2` branch while the original Claude checkout is preserved.

For scientific results, see [the evidence ledger](STAGE2_STATUS.md). For the missing learned simulation engine and exact next research steps, see [the simulation roadmap](AIDO_SIMULATION_ROADMAP.md).
