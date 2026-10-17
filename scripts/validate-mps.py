#!/usr/bin/env python3
"""Reproducible real Boltz-2 acceptance test. Downloads upstream weights if absent."""
import argparse, importlib.util, json, pathlib, time
repo=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('worker',repo/'scientific/worker.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
p=argparse.ArgumentParser();p.add_argument('--library',required=True);p.add_argument('--python',required=True);p.add_argument('--timeout',type=int,default=1800);args=p.parse_args()
s=w.Service(args.library);s.setting_set({'key':'enginePython','value':str(pathlib.Path(args.python).resolve())})
project=s.project_create({'name':'MPS technical acceptance'})
job=s.prediction_start({'projectId':project['id'],'name':'MPS technical acceptance · 10 residues','fasta':'>technical_test\nACDEFGHIKL\n','msa':'single','recycles':1,'steps':20,'samples':1,'seed':42,'origin':{'purpose':'Technical smoke test; not a validated scientific prediction.'}})
print('Running real inference:',job['id'],flush=True)
start=time.time()
while time.time()-start<args.timeout:
    current=s.job_read({'id':job['id']})
    if current['state'] not in ['queued','running']:
        print(json.dumps(current,indent=2));assert current['state']=='completed',current['data'].get('error',current['state'])
        output=next(r for r in s.library({})['records'] if r['id']==current['data']['outputs'][0]);assert '_atom_site.' in s.asset_read({'asset':output['data']['asset']})
        print('PASS: genuine coordinate output imported. Open it in the native Mol* viewer.');break
    time.sleep(3)
else:
    s.job_cancel({'id':job['id']});raise TimeoutError('Inference acceptance timed out and was cancelled.')
