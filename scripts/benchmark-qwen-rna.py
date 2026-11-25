#!/usr/bin/env python3
"""Score frozen native predictions against the existing baseline and ViennaRNA.

No training or checkpoint selection. Preserve the original neural benchmark.
"""
import argparse
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
from qwen_rna_contract import accuracy, digest, pairs
from rna_lab_fold import Builtin, to_dotbracket

p=argparse.ArgumentParser();p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
if a.out.exists():raise ValueError('Preserve existing benchmark evidence; choose a new output.')
manifest=json.loads((a.data/'split.json').read_text());cases=manifest['splits']['test'];started=time.monotonic()
benchmark=json.loads((a.checkpoint/'benchmark.json').read_text());rows=[]
try:
    import RNA
except ImportError:
    RNA=None
native={r['caseId']:r for r in json.loads((a.checkpoint/'qwen_adapter-test-predictions.json').read_text())}
for row in cases:
    seq,ref=row['sequence'],row['structure'];solver=Builtin(seq);fold=to_dotbracket(solver.mfe_pairs,len(seq));n=native[row['id']]
    entry={'id':row['id'],'sequenceSha256':digest(seq),'reference':ref,'native':n['comparison'],
           'builtin':{'structure':fold,'energyKcalMol':solver.mfe_energy,**accuracy(fold,ref)},
           'verification':{'triggered':sum(x['entropyBits'] for x in n['bases'])/len(seq)>1,
                           'pairDisagreement':len(set(pairs(fold))^set(pairs(n['structure']))),
                           'nativeUnchanged':True}}
    if RNA:
        structure,energy=RNA.fold(seq)
        entry['vienna']={'structure':structure,'energyKcalMol':energy,**accuracy(structure,ref)}
    rows.append(entry)
def mean(key):return sum(r[key]['f1'] for r in rows)/len(rows)
summary={**{arm:r['meanF1'] for arm,r in benchmark['arms'].items()},'builtin':mean('builtin')}
if RNA:summary['vienna']=mean('vienna')
report={'schema':'fold.qwen-rna-comparison/1','splitSha256':manifest['sha256'],'cases':len(rows),'families':['srp'],
        'metric':'Mean per-RNA exact canonical pair F1; same sequences/reference; nested folds; no alignment/tolerance rescue',
        'summaryF1':summary,'viennaVersion':RNA.__version__ if RNA else None,'builtinVersion':'rna-lab.fold/1.0.0',
        'nativeExternalEngines':False,'verification':{'enabled':True,'policy':'Native mean partner entropy > 1 bit',
        'checksTriggered':sum(r['verification']['triggered'] for r in rows),
        'disagreementsCaught':sum(r['verification']['triggered'] and r['verification']['pairDisagreement']>0 for r in rows),
        'interpretation':'Verification exposes independent structures and disagreements. It does not improve or replace the native fold, calibrate uncertainty, or establish a learned Qwen router.'},
        'rows':rows,'trainingOrTuningPerformed':False,'seconds':time.monotonic()-started,
        'conclusion':'Research candidates only. No checkpoint promotion; no established-engine win on this pilot.'}
a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'summaryF1':summary,'cases':len(rows),'seconds':report['seconds']}))
