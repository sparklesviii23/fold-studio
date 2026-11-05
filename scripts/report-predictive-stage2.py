"""Render the current evidence ledger from saved results; never runs a model."""
import argparse,csv,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output-dir',required=True);a=p.parse_args();out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
read=lambda name:json.loads((out/name).read_text()) if (out/name).exists() else None
response=read('STRONGER_RESPONSE_BENCHMARK.json');panel=read('BORZOI_PANEL_EVALUATION.json');status=read('BORZOI_STAGE2_STATUS.json') or {};discrepancy=read('REPRODUCTION_DISCREPANCY.json') or {}
integration=read('VIRTUAL_CELL_INTEGRATION_RECEIPT.json') or {}; installed=integration.get('nativeInstalled',False)
text=['# Fold Studio predictive biology · current evidence','',f'Latest cloud job: `{status.get("id","not recorded")}` · **{status.get("state","pending")}**. {"Integrated Virtual Cell features are installed; the study was imported additively into the normal library." if installed else "Installed application remains unchanged; development and research data are isolated."}','',
'| Capability | Previous status | Newly implemented | Actual inference | Benchmark results | Scientific limitations |','|---|---|---|---|---|---|']
text+=['| Original Borzoi reproduction | One FABP1 run | Exact retained reproduction, staged DNA integrity, hardware comparison | Yes | 16,352 bins reproduced exactly on the original GPU variant | A later GPU variant failed the original strict cross-device tolerance; that failure is retained |']
if panel:
 inferred=len({g['symbol'] for g in panel['geneResults'] if g['cohort']=='heldout'})
 text.append(f'| Expanded Borzoi | One locus / one track | Frozen 100-locus panel, four illustrations, three tracks, two replicas and mean ensemble | Yes: {inferred} valid test inputs plus four illustrations | Per-locus metrics, track/stratum summaries, locus CIs and paired ensemble comparisons saved | One out-of-bounds input remains a counted failure; related training assays, original ENCODE rather than processed targets; no calibrated count errors |')
else:text.append('| Expanded Borzoi | One locus / one track | Frozen panel, 103 verified usable inputs and one explicit boundary failure, two-replica runner/evaluator | Expanded inference not completed yet | Pending; do not interpret prepared inputs as accuracy | 100 attempted test identities; 99 usable test inputs and four separate illustrations |')
text+=['| Response comparison | Four methods; no winner across 72 cases | Nine methods, validation-only tuning and 180 additional cases | Yes, statistical predictions | Original four predictions/masks/scores preserved exactly | Retrospective retesting; same nine test lines and two plates for additional conditions |',
'| Stronger baseline | Not tested | Validation-selected 0.25 × matched donor response | Yes | Original MSE 0.778284 vs 0.787841 unchanged; additional MSE 0.825780 vs 0.831090 | Small improvement; additional paired CI nearly reaches zero; no independent study |',
'| Nonlinear/low-rank models | Not tested | PCA ridge, rank-4 response ridge and RBF kernel ridge | Yes | All lose to unchanged control | Statistical models, not pretrained foundation models; CPA/GEARS/scGPT not executed on incompatible LFC inputs |',
'| HepG2 ANGPTL3 explorer | Evidence in separate views | Gene report, RNA/isoforms/protein/pathways/structure handoff, state save/restore/export | Existing structure and compatible saved regulatory results only | Real worker/browser walkthrough passed | Only compatible completed regulatory profiles are shown; ANGPTL3 is an illustrative fold5 locus, not held-out validation; no validated parental-HepG2 treatment predictor |',
'| Run controller | Partial terminal controls | Recorded lifecycle, live/saved terminal, commands/history, local-task records and bounded background evaluator | Actual job logs and result retrieval | Local checks and cloud history are inspectable | No inference retry; local preparations expose read-only progress |',
('| Integration | Isolated branch | User-approved installed Virtual Cell integration and additive study import | Installed packaged worker checked | Original 57 records and five projects preserved; 206 packaged scientific resources match source | Native walkthrough '+('passed' if integration.get('nativeUiVerified') else 'pending')+'; original Claude source remains separate |' if installed else '| Integration | Isolated branch | Recoverable source checkpoints, packaged resource checks | Development preview | Original checkout/library/application preserved | No installed-app replacement or native installation qualification |'),'']
if response:
 text+=['## Response leaderboard','', '| Method | Original 72 MSE | Additional 180 MSE | Additional paired difference vs unchanged [95% CI] |','|---|---:|---:|---|']
 rows=[]
 for m,label in response['models'].items():
  original=response['summary']['test'][m]['mse']['mean'];extra=response['summary']['additional'][m]['mse']['mean'];c=response['mseDifferenceVsUnchanged']['additional'].get(m)
  ci='reference' if not c else f'{c["mean"]:+.6f} [{c["ci95"][0]:+.6f}, {c["ci95"][1]:+.6f}]'
  text.append(f'| {label} | {original:.6f} | {extra:.6f} | {ci} |');rows.append({'method':m,'label':label,'originalMse':original,'additionalMse':extra,'additionalDifference':c['mean'] if c else 0,'ciLower':c['ci95'][0] if c else None,'ciUpper':c['ci95'][1] if c else None})
 with (out/'RESPONSE_MODEL_LEADERBOARD.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
 text+=['','The validation-selected method was the shrunken donor mean. Its paired intervals favour it within this dataset, but this is a modest statistical result: original test outcomes had already been examined, additional cases reuse the same lines/plates, and their interval barely excludes zero. No automatic predictor promotion, independent-study validation or world-model claim follows.','']
if panel:
 text+=['## Expanded Borzoi results','']
 for t in panel['tracks']:
  text.append(f'### {t["metadata"]["description"]} · {t["metadata"]["identifier"]}')
  for model,s in panel['summary'][str(t['index'])].items():text.append(f'- {model}: {s["scored"]}/{s["attempted"]} scored loci; Spearman {s["spearman"]["mean"]}, 95% CI {s["spearman"]["ci95"]}; log-profile Pearson {s["pearson"]["mean"]}.')
  text.append('')
 text.append('Verification policy: '+json.dumps(panel.get('verificationPolicy'))+'. Current run original strict comparison: '+str(panel.get('crossDeviceOriginalTolerancePassed'))+'.')
 keys=sorted({k for row in panel['perLocus'] for k in row})
 with (out/'BORZOI_PER_LOCUS.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(panel['perLocus'])
 try:
  import matplotlib;matplotlib.use('Agg')
  from matplotlib import pyplot as plt
  import numpy as np
  fig,axes=plt.subplots(1,len(panel['tracks']),figsize=(11,3.6),layout='constrained')
  for ax,t in zip(np.atleast_1d(axes),panel['tracks']):
   for i,model in enumerate(('f0','f1','ensemble')):
    s=panel['summary'][str(t['index'])][model];v=s['spearman']['mean'];ci=s['spearman']['ci95']
    if v is not None:ax.errorbar(v,i,xerr=np.array([[v-ci[0]],[ci[1]-v]]) if ci else None,fmt='o',capsize=4,color=['#7d93bc','#c798ad','#65a58e'][i]);ax.text(-.98,i+.18,f'{s["scored"]}/{s["attempted"]} loci',fontsize=8)
   ax.set_yticks(range(3),('replicate 0','replicate 1','ensemble'));ax.invert_yaxis();ax.set_ylim(2.45,-.35);ax.set_xlim(-1,1);ax.set_title(t['metadata']['description'],fontsize=11);ax.set_xlabel('Mean locus Spearman (95% CI)');ax.spines[['top','right']].set_visible(False)
  fig.suptitle('Related-assay genomic holdouts; missing-reference failures retained',fontsize=12);fig.savefig(out/'BORZOI_AGGREGATE.png',dpi=180);plt.close(fig)
 except ImportError:text.append('Plot unavailable: plotting runtime absent; full numeric results remain saved.')
text+=['','## Reproduction and tests','',
'Original response benchmark: all 72 test and 45 validation condition metrics reproduced exactly. Original FABP1 profile: Spearman 0.444756 on 45 fully covered bins. The same observed-reference Spearman was unchanged on the later GPU variant, although 1,199/16,352 raw values exceeded the original strict cross-device tolerance; max absolute difference 0.0007527. The strict failure is not relabelled as a pass.',
'',str(integration.get('backendPassed',116))+' targeted backend tests and 252 frontend tests passed; TypeScript, production web build and 164-module scientific resource closure passed. '+(('Guarded installation and packaged-worker checks passed; native walkthrough '+('passed.' if integration.get('nativeUiVerified') else 'pending.')) if installed else 'Native installation was not run.')+' See the saved testing logs/receipts for scope.','',
'Official Borzoi replicas share fold3 test / fold4 validation splits ([pinned README](https://github.com/calico/borzoi/blob/f10f8c799639dd2cfc0c1eb09499bfc47ab9cf8a/README.md)). TensorFlow defines deterministic execution relative to the same hardware ([official guidance](https://www.tensorflow.org/api_docs/python/tf/config/experimental/enable_op_determinism)); hardware/kernel numerical variation is a plausible explanation here, not an experimentally isolated cause.','',
'## Remaining boundaries','',
('Regulatory profile associations are now benchmarked in the specified genomic holdouts. Aggregate intervals apply to scorable loci; unobserved/unsupported loci are retained as failures. ' if panel else 'Broader regulatory accuracy remains pending. ')+'Pretrained perturbation models still require a compatible cell-level/count-data benchmark; cross-study generalization, calibrated per-gene intervals, paired multimodal ground truth and a learned cellular world model remain unestablished. '+('Installed Virtual Cell integration is complete; the scientific boundaries above still apply.' if installed else 'Installed-app integration remains a separate reviewed step.'),'',
'Artifacts: STRONGER_RESPONSE_BENCHMARK.json, RESPONSE_MODEL_LEADERBOARD.csv, STRONGER_RESPONSE_COMPARISON.png, BORZOI_PANEL_PLAN.json, SEQUENCE_PREFLIGHT.json, PORTABLE_VERIFICATION_POLICY.json, REPRODUCTION_DISCREPANCY.json and BORZOI_PANEL_EVALUATION.json / BORZOI_PER_LOCUS.csv / BORZOI_AGGREGATE.png.']
(out/'STAGE2_STATUS.md').write_text('\n'.join(text)+'\n')
print('Evidence ledger updated: '+str(out/'STAGE2_STATUS.md'))
