#!/usr/bin/env python3
"""One explicitly approved checkpoint retrieval + local pilot, with durable app logs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
import urllib.request
import uuid
sys.dont_write_bytecode=True
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO/'scientific'))
import gpu_tasks as G
from qwen_cell_data import sha,verify_bundle,write
from qwen_cell_training import validate_checkpoint


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['library','data','out','metadata','checkpoint']:parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--project',required=True);parser.add_argument('--approved-download-and-pilot',action='store_true')
    parser.add_argument('--child');a=parser.parse_args();s=SimpleNamespace(root=a.library.resolve())
    if not a.child:
        if not a.approved_download_and_pilot:parser.error('Explicit model download and one local pilot approval is required.')
        verify_bundle(a.data)
        if a.out.exists():raise ValueError('One attempt is already recorded here; no automatic retry.')
        a.out.mkdir(parents=True);job=uuid.uuid4().hex
        write(a.out/'PILOT_ATTEMPT.json',{'jobId':job,'modelDownloadApproved':True,'localPilotApproved':True,
              'model':'Qwen/Qwen2.5-Coder-3B-Instruct','maximumTrainingSeconds':900,'maximumSteps':30,'automaticRetry':False})
        rec={'id':job,'projectId':a.project,'provider':'local','recipe':'qwen_cell_prediction_pilot','state':'local_running','gpu':None,
             'title':'Qwen · direct cell prediction training','created':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
             'timeout':900,'phase':'Approved checkpoint download; then one local 30-step training pilot'}
        G._write(s,rec);folder=G._folder(s)/job
        with (folder/'stdout.txt').open('w') as log:
            child=subprocess.Popen([sys.executable,'-B',__file__,*sys.argv[1:],'--child',job],stdout=log,stderr=subprocess.STDOUT,
                                   start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2'))
        print(json.dumps({'jobId':job,'supervisorPid':child.pid,'log':str(folder/'stdout.txt'),'app':'Virtual Cell → Runs & terminal'}));return
    rec=G._read(s,a.child);rec['localPid']=os.getpid();rec['launched']=time.time();G._write(s,rec)
    metadata=json.loads(a.metadata.read_text());process=None;code=0;stopped=False
    def expired(*_):raise TimeoutError('Checkpoint retrieval exceeded its 30-minute wall limit; no automatic retry.')
    def stop(*_):raise KeyboardInterrupt('Stop requested.')
    signal.signal(signal.SIGALRM,expired);signal.signal(signal.SIGTERM,stop);signal.alarm(1800)
    try:
        print('[fold] explicit approval: official 6.17 GB checkpoint + one local 30-step / 15-minute training pilot',flush=True)
        print('[fold] no cloud job, data upload, automatic retry, legacy test evaluation or predictor promotion',flush=True)
        if metadata['model']!='Qwen/Qwen2.5-Coder-3B-Instruct' or metadata['revision']!='488639f1ff808d1d3d0ba301aef8c11461451ec5':raise ValueError('Unexpected approved model.')
        if shutil.disk_usage(a.library).free<metadata['totalBytes']+8*1024**3:raise ValueError('Insufficient free disk space for the checkpoint and working memory.')
        a.checkpoint.mkdir(parents=True,exist_ok=True)
        for row in metadata['files']:
            name=row['rfilename']
            if name not in ['config.json','model.safetensors.index.json','model-00001-of-00002.safetensors','model-00002-of-00002.safetensors']:raise ValueError('Unexpected checkpoint filename.')
            target=a.checkpoint/name
            if target.exists():
                if target.stat().st_size==row['size'] and (not row.get('lfs') or sha(target)==row['lfs']['sha256']):continue
                raise ValueError('An existing checkpoint file differs; preserved without overwriting.')
            partial=target.with_suffix(target.suffix+'.partial')
            if partial.exists():raise ValueError('Partial download preserved; no automatic retry.')
            url='https://huggingface.co/'+metadata['model']+'/resolve/'+metadata['revision']+'/'+name
            size=0;h=hashlib.sha256();next_progress=128<<20
            print('[fold] downloading '+name+' ('+str(row['size'])+' bytes)',flush=True)
            with urllib.request.urlopen(url,timeout=120) as response,partial.open('xb') as output:
                while True:
                    block=response.read(8<<20)
                    if not block:break
                    size+=len(block)
                    if size>row['size']:raise ValueError('Unexpected checkpoint response size.')
                    output.write(block);h.update(block)
                    if size>=next_progress:print('[fold] '+name+': '+str(round(size/row['size']*100,1))+'%',flush=True);next_progress+=128<<20
            if size!=row['size'] or (row.get('lfs') and h.hexdigest()!=row['lfs']['sha256']):raise ValueError('Downloaded checkpoint integrity failed.')
            partial.replace(target);print('[fold] verified '+name,flush=True)
        checks=validate_checkpoint(a.checkpoint,metadata);write(a.out/'CHECKPOINT_RECEIPT.json',{'model':metadata['model'],'revision':metadata['revision'],'files':checks})
        signal.alarm(0);rec['phase']='Verified checkpoint; local Qwen adapter and numerical-layer training';G._write(s,rec)
        command=[sys.executable,'-B',str(REPO/'scripts/train-qwen-cell.py'),'--checkpoint',str(a.checkpoint),'--metadata',str(a.metadata),
                 '--data',str(a.data),'--out',str(a.out/'training'),'--steps','30','--maximum-seconds','900','--device','mps']
        print('[fold] starting direct Qwen prediction training; original base frozen, attention adapters and numerical layers trainable',flush=True)
        process=subprocess.Popen(command,start_new_session=True);code=process.wait()
        if code:raise ValueError('The one local training attempt exited with code '+str(code)+'. No retry.')
        print('[fold] training finished; review receipt for actual adapter updates and development-only scores',flush=True)
    except KeyboardInterrupt:
        stopped=True;code=130;rec['error']='Stopped by the user.'
    except BaseException as error:
        import traceback;traceback.print_exc();code=1;rec['error']=str(error)
    finally:
        signal.alarm(0)
        if process is not None and process.poll() is None:
            try:os.killpg(process.pid,signal.SIGTERM);process.wait(timeout=7)
            except (ProcessLookupError,subprocess.TimeoutExpired):
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
        dest=G._folder(s)/a.child/'outputs';dest.mkdir(exist_ok=True)
        for source in a.out.rglob('*'):
            if source.is_file():
                name=str(source.relative_to(a.out)).replace('/','-');shutil.copy2(source,dest/name)
        rec['outputs']=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in dest.iterdir() if p.is_file()]
        rec.update(state='stopped' if stopped else 'done' if code==0 else 'failed',returncode=code,
                   phase='Local direct-Qwen pilot completed' if code==0 else 'Local pilot stopped or failed; no automatic retry',finished=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
        G._write(s,rec);print('[fold] '+rec['state'],flush=True)


if __name__=='__main__':main()
