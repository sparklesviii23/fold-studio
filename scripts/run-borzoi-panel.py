#!/usr/bin/env python3
"""One explicitly approved panel job through Fold Studio's existing GPU manager.

Use --status JOB_ID to inspect an existing job without submitting another one.
A consumed submission claim is never reset automatically, including on failure.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library',required=True); p.add_argument('--plan'); p.add_argument('--project')
    p.add_argument('--approved-once',action='store_true',help='Only after a human has explicitly approved this exact paid job.')
    p.add_argument('--status',metavar='JOB_ID')
    a=p.parse_args()
    if not a.status and not (a.approved_once and a.plan and a.project):p.error('Submission requires --plan, --project and explicit --approved-once; no job launched.')
    from worker import Service
    import gpu_tasks as GPU
    from virtual_cell_benchmarks import _hash
    service=Service(Path(a.library).resolve())
    try:
        if a.status:
            result=GPU.status(service,{'taskId':a.status})
            print(json.dumps({k:result.get(k) for k in ('id','state','phase','returncode','error','fetchError','serverLog')},indent=1));return
        panel=json.loads(Path(a.plan).read_text()); digest=panel.get('sha256')
        if digest!='179527fa38a666ae7204e46f1c19c96fd0d7469656740a9033d693caac1bdf2d' or panel.get('schema')!='fold.borzoi.panel/1' or panel.get('testLoci')!=100 or len(panel.get('loci',[]))!=104 or len(panel.get('tracks',[]))!=3 or _hash({k:v for k,v in panel.items() if k!='sha256'})!=digest:raise ValueError('Only the exact frozen Stage 2 panel is admitted.')
        raw=json.dumps(panel,separators=(',',':'),allow_nan=False)
        if len(json.dumps({'files':{'panel.json':raw}}).encode())>100000:raise ValueError('Panel exceeds the bounded process environment.')
        if not service.db.execute('SELECT 1 FROM projects WHERE id=?',(a.project,)).fetchone():raise ValueError('Choose an existing project in this isolated library.')
        folder=Path(a.library)/'virtualcell/borzoi-panels';folder.mkdir(parents=True,exist_ok=True)
        claim=folder/f'submission-{digest}.json'
        rec={'panelSha256':digest,'attempt':1,'maxAttempts':1,'timeoutSeconds':2700,'gpu':'A100-80GB','approvedOnce':True,'created':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'state':'claimed_before_submit'}
        with open(claim,'x') as f:
            json.dump(rec,f,indent=1);f.flush();os.fsync(f.fileno())
        # Any error after the claim requires inspection; it never authorizes a retry.
        result=GPU.submit(service,{'projectId':a.project,'recipe':'bio_borzoi_panel','inputs':{'files':{'panel.json':raw}},'timeout':2700,'approvedRemoteCost':True,
                                  'label':'Stage 2 · frozen 100-locus evaluation','inputSource':{'panelSha256':digest,'approvalScope':'one job; no automatic retry'}})
        rec.update(jobId=result['id'],state=result['state']);temp=claim.with_suffix('.partial');temp.write_text(json.dumps(rec,indent=1));temp.replace(claim)
        print(json.dumps(rec,indent=1))
    finally:service.db.close()

if __name__=='__main__':main()
