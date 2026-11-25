#!/usr/bin/env python3
"""Check direct Qwen samples without pair or constraint repair. No tuning."""
import argparse
import hashlib
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
from rna_design_core import Cache,Scorer,atomic,digest,violations


def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--checkpoint',type=Path,required=True);a=p.parse_args()
    protocol=json.loads((a.data/'protocol.json').read_text())
    plan={'protocolSha256':protocol['sha256'],'checkpointSha256':hashlib.sha256(a.checkpoint.read_bytes()).hexdigest(),
          'samplesPerTargetSeed':32,'seeds':protocol['seeds'],'repair':False,'tuning':False,
          'rules':'Reject constraint and target-pair violations. Refold valid direct samples. Same exact MFE target rule and independent checker.'}
    if (a.data/'raw-qwen-plan.json').exists():
        raise ValueError('Use the saved audit. Do not overwrite evidence.')
    atomic(a.data/'raw-qwen-plan.json',plan)
    from rna_design_qwen import Proposer
    began=time.monotonic();proposer=Proposer(a.checkpoint);startup=time.monotonic()-began
    cache=Cache(a.data/'raw-qwen-cache.sqlite');scorer=Scorer(cache);rows=[]
    for target in protocol['splits']['test']:
        began=time.monotonic();proposer.set_target(target['request']['target']);feature_seconds=time.monotonic()-began
        for seed in protocol['seeds']:
            samples=[];seen=set()
            for index in range(32):
                sequence=proposer(index,random.Random(seed+index*104729));errors=violations(sequence,target['request'])
                row={'sequence':sequence,'constraintViolations':errors,'qualifies':False,'duplicate':sequence in seen}
                seen.add(sequence)
                if not errors:
                    value=scorer.score(sequence,target['request']['target']);row.update(value);row['qualifies']=value['structure']==target['request']['target']
                    if row['qualifies']:row['independent']=scorer.second(sequence)
                samples.append(row)
            rows.append({'target':target['id'],'seed':seed,'length':target['length'],'difficulty':target['difficulty'],
                         'success':any(s['qualifies'] for s in samples),'rawConstraintViolations':sum(bool(s['constraintViolations']) for s in samples),
                         'distinctQualifying':len({s['sequence'] for s in samples if s['qualifies']}),'targetFeatureSeconds':feature_seconds,'samples':samples})
            print(json.dumps({k:v for k,v in rows[-1].items() if k!='samples'}),flush=True)
    report={'plan':plan,'startupSeconds':startup,'cases':rows,'successRate':sum(r['success'] for r in rows)/len(rows),
            'rawConstraintViolationRate':sum(r['rawConstraintViolations'] for r in rows)/(len(rows)*32),
            'explicitEvaluations':scorer.evaluations,'independentEvaluations':scorer.secondary_evaluations,
            'scope':'Direct generation audit. This is separate from the frozen Qwen arm, which includes shared canonical-pair and sequence-constraint repair.'}
    report['sha256']=digest(report);atomic(a.data/'raw-qwen.json',report);cache.db.close()


if __name__=='__main__':main()
