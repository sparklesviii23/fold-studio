#!/usr/bin/env python3
"""One explicitly approved panel job through Fold Studio's existing GPU manager.

Use --status JOB_ID to inspect an existing job without submitting another one.
A consumed submission claim is never reset automatically, including on failure.
"""
import argparse
import base64
import gzip
import hashlib
import json
import os
import subprocess
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
    p.add_argument('--after-rejected-request',metavar='JOB_ID',help='A manually authorized replacement only after the provider rejected the oversized request before allocation.')
    p.add_argument('--after-reference-failure',metavar='JOB_ID',help='One newly approved continuation after the documented reference failure.')
    p.add_argument('--sequence-folder',help='Locally completed, hash-verified reference preflight; required for submission.')
    p.add_argument('--after-numerical-discrepancy',metavar='JOB_ID')
    p.add_argument('--verification-policy',help='Explicitly reviewed portable verification policy; original cross-device gate remains reported.')
    a=p.parse_args()
    if not a.status and not (a.approved_once and a.plan and a.project and a.sequence_folder):p.error('Submission requires --plan, --project, --sequence-folder and explicit --approved-once; no job launched.')
    if sum(bool(x) for x in (a.after_rejected_request,a.after_reference_failure,a.after_numerical_discrepancy))>1:p.error('Choose only one documented predecessor.')
    if bool(a.after_numerical_discrepancy)!=bool(a.verification_policy):p.error('Numerical-discrepancy continuation requires its reviewed verification policy.')
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
        inputs={'files':{'panel.json.gz.b64':base64.b64encode(gzip.compress(raw.encode(),mtime=0)).decode()}}
        seqfolder=Path(a.sequence_folder).resolve(); preflight=json.loads((seqfolder/'preflight.json').read_text())
        if _hash({k:v for k,v in preflight.items() if k!='sha256'})!=preflight.get('sha256') or preflight.get('panelSha256')!=digest or len(preflight.get('loci',[]))!=104:raise ValueError('Completed matching sequence preflight required.')
        for i,(locus,ref) in enumerate(zip(panel['loci'],preflight['loci'])):
            if (ref['index'],ref['symbol'],ref['chromosome'],ref['start'],ref['end'])!=(i,locus['symbol'],locus['chromosome'],locus['inputStart'],locus['inputStart']+524288):raise ValueError('Reference preflight coordinate mismatch.')
            if ref['status']=='unsupported_input_window':continue
            if ref['status']!='ready':raise ValueError('Unresolved sequence input.')
            source=seqfolder/f'{ref["chromosome"]}-{ref["start"]}-524288.txt'
            if hashlib.sha256(source.read_bytes()).hexdigest()!=ref['sequenceSha256']:raise ValueError('Local reference checksum failed.')
        inputs['files']['preflight.json.gz.b64']=base64.b64encode(gzip.compress(json.dumps(preflight,separators=(',',':')).encode(),mtime=0)).decode()
        if a.verification_policy:
            policy=json.loads(Path(a.verification_policy).read_text())
            from virtual_cell_regulatory import _artifact
            historical=GPU._read(service,policy['historicalRun']);historical_folder=Path(a.library)/'gpu_tasks'/policy['historicalRun']
            raw_receipt=_artifact(historical,historical_folder,'reproduction.json',2_000_000)
            if policy.get('schema')!='fold.borzoi.portable-verification/1' or hashlib.sha256(raw_receipt).hexdigest()!=policy.get('historicalReceiptSha256') or json.loads(raw_receipt).get('passed') is not True:raise ValueError('Historical exact reproduction policy failed verification.')
            inputs['files']['verification.json.gz.b64']=base64.b64encode(gzip.compress(json.dumps(policy,separators=(',',':')).encode(),mtime=0)).decode()
        if len(json.dumps(inputs).encode())>30000:raise ValueError('Panel exceeds the provider configuration limit (32,768 bytes).')
        if not service.db.execute('SELECT 1 FROM projects WHERE id=?',(a.project,)).fetchone():raise ValueError('Choose an existing project in this isolated library.')
        folder=Path(a.library)/'virtualcell/borzoi-panels';folder.mkdir(parents=True,exist_ok=True)
        claim=folder/f'submission-{digest}.json'
        if a.after_rejected_request:
            old=json.loads(claim.read_text()); task=GPU._read(service,a.after_rejected_request)
            if old.get('jobId')!=a.after_rejected_request or task.get('state')!='failed' or task.get('sandboxId') or task.get('returncode') is not None or task.get('error')!="Secret value for key 'FOLD_INPUT' is too long (max 32768)":raise ValueError('Replacement is restricted to the recorded pre-allocation size rejection.')
            claim=folder/f'submission-{digest}-after-{a.after_rejected_request}.json'
        if a.after_reference_failure:
            task=GPU._read(service,a.after_reference_failure)
            reproduction=Path(a.library)/'gpu_tasks'/a.after_reference_failure/'outputs/reproduction.json'
            if task.get('recipe')!='bio_borzoi_panel' or task.get('state')!='failed' or task.get('returncode')!=1 or not json.loads(reproduction.read_text()).get('passed'):raise ValueError('Expected the documented failed panel with successful reproduction.')
            claim=folder/f'submission-{digest}-reference-repair-after-{a.after_reference_failure}.json'
        if a.after_numerical_discrepancy:
            task=GPU._read(service,a.after_numerical_discrepancy)
            reproduced=json.loads((Path(a.library)/'gpu_tasks'/a.after_numerical_discrepancy/'outputs/reproduction.json').read_text())
            if task.get('state')!='failed' or task.get('recipe')!='bio_borzoi_panel' or reproduced.get('passed') is not False or reproduced['checkpointSha256']!=policy['checkpointSha256']:raise ValueError('Expected the documented numerical discrepancy.')
            claim=folder/f'submission-{digest}-portable-after-{a.after_numerical_discrepancy}.json'
        rec={'panelSha256':digest,'attempt':1,'maxAttempts':1,'replacesRejectedRequest':a.after_rejected_request,'replacesNumericalDiscrepancy':a.after_numerical_discrepancy,'serializedInputBytes':len(json.dumps(inputs).encode()),'timeoutSeconds':2700,'gpu':'A100-80GB','approvedOnce':True,'created':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'state':'claimed_before_submit'}
        with open(claim,'x') as f:
            json.dump(rec,f,indent=1);f.flush();os.fsync(f.fileno())
        # Stage verified reference files using the existing account/runtime before allocating a GPU.
        python,env,_=GPU._provider(service)
        staging="""import json,sys,pathlib,modal
folder=pathlib.Path(sys.argv[1]);manifest=json.loads((folder/'preflight.json').read_text())
volume=modal.Volume.from_name('fold-gpu-cache',create_if_missing=True)
with volume.batch_upload(force=True) as batch:
 for row in manifest['loci']:
  if row['status']=='ready':batch.put_file(str(folder/f"{row['chromosome']}-{row['start']}-524288.txt"),f"/models/predictive-cell-reference/verified/{row['sequenceSha256']}.txt")
print('Verified reference staging complete')
"""
        staged=subprocess.run([str(python),'-B','-c',staging,str(seqfolder)],env=env,capture_output=True,text=True,timeout=600)
        if staged.returncode:raise ValueError('Reference staging failed before GPU allocation: '+staged.stderr[-600:])
        rec['sequencePreflightSha256']=preflight['sha256'];rec['replacesReferenceFailure']=a.after_reference_failure
        # Any error after the claim requires inspection; it never authorizes a retry.
        result=GPU.submit(service,{'projectId':a.project,'recipe':'bio_borzoi_panel','inputs':inputs,'timeout':2700,'approvedRemoteCost':True,
                                  'label':'Stage 2 · frozen 100-locus evaluation','inputSource':{'panelSha256':digest,'approvalScope':'one job; no automatic retry'}})
        rec.update(jobId=result['id'],state=result['state']);temp=claim.with_suffix('.partial');temp.write_text(json.dumps(rec,indent=1));temp.replace(claim)
        print(json.dumps(rec,indent=1))
    finally:service.db.close()

if __name__=='__main__':main()
