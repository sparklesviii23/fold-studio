#!/usr/bin/env python3
"""Exercise local jobs in a new scratch library with the selected Python runtime."""
import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
import rna_design
from rna_design_core import atomic


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
    if a.root.exists():
        raise ValueError('Use a new scratch library.')
    s=Service(a.root);project=s.project_create({'name':'RNA Design qualification'})['id']
    records=[]
    for name,target in [('simple','((((....))))'),('held-out g07-v1','(((..(((.......)))..(((.......)))..)))')]:
        request={'projectId':project,'target':target,'maxSeconds':10,'maxCandidates':64,'wanted':3,'seed':17}
        q=rna_design.quote(s,request)
        started=time.monotonic();job=rna_design.start(s,{**request,'quoteSha256':q['quoteSha256']})
        while s.job(job['id'])['state'] in ('running','queued') and time.monotonic()-started<45:
            time.sleep(.1)
        out=rna_design.poll(s,{'projectId':project,'id':job['id']})
        if out['job']['state']!='completed' or not out['result'] or out['result']['qualifyingCount']<2:
            raise ValueError('Local qualification failed: '+json.dumps(out))
        saved=[]
        for candidate in out['result']['candidates'][:2]:
            payload={'projectId':project,'id':job['id'],'candidateId':candidate['id']}
            record=rna_design.dispatch(s,'rna_design_save',payload)
            again=rna_design.dispatch(s,'rna_design_save',payload)
            assert record['id']==again['id']
            reopened=json.loads(s.rows('SELECT data FROM records WHERE id=?',(record['id'],))[0]['data'])
            assert reopened['candidate']==candidate and reopened['result']['sha256']==out['result']['sha256']
            saved.append(record['id'])
        records.append({'name':name,'runId':job['id'],'recordIds':saved,'qualifying':out['result']['qualifyingCount'],
                        'resultSha256':out['result']['sha256'],'wallSeconds':time.monotonic()-started,'job':s.job(job['id'])})
        print(json.dumps(records[-1]),flush=True)
    # Signal the exact process group created by this test. The desktop uses job_cancel.
    request={'projectId':project,'target':'((....))','maxSeconds':5,'maxCandidates':4096,'wanted':20,'seed':31}
    q=rna_design.quote(s,request);job=rna_design.start(s,{**request,'quoteSha256':q['quoteSha256']})
    folder=s.root/'jobs'/job['id'];deadline=time.monotonic()+20
    while not (folder/'result.json').is_file() and time.monotonic()<deadline:
        time.sleep(.05)
    os.killpg(s.job(job['id'])['data']['pid'],signal.SIGTERM)
    deadline=time.monotonic()+5
    while s.job(job['id'])['state'] in ('queued','running') and time.monotonic()<deadline:
        time.sleep(.05)
    partial=rna_design.result(folder)
    assert partial and partial['candidates']
    count=len(partial['candidates'])
    deadline=time.monotonic()+5
    while True:
        try:
            resumed=rna_design.dispatch(s,'rna_design_resume',{'projectId':project,'id':job['id'],'maxSeconds':6})
            break
        except ValueError as e:
            if 'still saving' not in str(e) or time.monotonic()>deadline:
                raise
            time.sleep(.1)
    deadline=time.monotonic()+40
    while s.job(job['id'])['state'] in ('queued','running') and time.monotonic()<deadline:
        time.sleep(.1)
    final=rna_design.result(folder)
    assert final and len(final['candidates'])>=count
    assert len({c['sequence'] for c in final['candidates']})==len(final['candidates'])
    records.append({'name':'cancel and resume','runId':job['id'],'partialCandidates':count,'finalCandidates':len(final['candidates']),
                    'resultSha256':final['sha256'],'job':s.job(job['id'])})
    atomic(a.root.parent/'local-runtime.json',{'python':sys.executable,'projectId':project,'library':str(a.root.resolve()),'runs':records,
                                            'scope':'Real source jobs with the installed Python runtime. UI and generic desktop cancellation need separate qualification.'})


if __name__=='__main__':main()
