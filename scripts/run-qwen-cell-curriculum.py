#!/usr/bin/env python3
"""Launch one fixed offline training comparison, visible in the app's run controller."""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
import uuid
sys.dont_write_bytecode=True
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1';os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO/'scientific'))
import gpu_tasks as G
from qwen_cell_data import sha,write


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['library','plan','out']:parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--project',required=True);parser.add_argument('--supervisor');parser.add_argument('--worker');a=parser.parse_args()
    service=SimpleNamespace(root=a.library.resolve());plan=json.loads(a.plan.read_text())
    if a.worker:
        from qwen_cell_curriculum import run
        started=time.monotonic();events=(a.out/'events.jsonl').open('w')
        def event(phase,**values):
            row={'phase':phase,'seconds':time.monotonic()-started,**values};events.write(json.dumps(row,allow_nan=False)+'\n');events.flush();print(json.dumps(row),flush=True)
        def stop(*_):raise KeyboardInterrupt('Study stopped.')
        def expired(*_):raise TimeoutError('The local comparison reached its fixed 15-minute limit; no retry.')
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGALRM,expired);signal.alarm(900)
        try:
            event('study_started',automaticRetry=False,cloudJobs=0,legacyTestOutcomesAggregated=False)
            run(plan,a.out,event);return 0
        except BaseException as error:
            import traceback;traceback.print_exc();write(a.out/'FAILURE.json',{'state':'stopped' if isinstance(error,KeyboardInterrupt) else 'failed','reason':str(error),'automaticRetry':False})
            return 130 if isinstance(error,KeyboardInterrupt) else 1
        finally:signal.alarm(0);events.close()
    if not a.supervisor:
        from qwen_cell_curriculum import verify_dependencies
        verify_dependencies(plan)
        if a.out.exists():raise ValueError('A study attempt is already recorded here. No automatic retry.')
        a.out.mkdir(parents=True);write(a.out/'PLAN.json',plan);job=uuid.uuid4().hex
        write(a.out/'ATTEMPT.json',{'jobId':job,'maximumSeconds':900,'maximumArms':3,'maximumEpochsPerArm':20,'automaticRetry':False})
        rec={'id':job,'projectId':a.project,'provider':'local','recipe':'qwen_cell_curriculum','title':'Qwen · learn from RNA predictor',
             'state':'local_running','gpu':'Apple GPU (MPS)','created':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
             'timeout':900,'phase':'Three controlled continuations: full passes, RNA teacher, fixed-Qwen control'}
        G._write(service,rec);folder=G._folder(service)/job
        command=[sys.executable,'-B',__file__,'--library',str(a.library),'--plan',str(a.out/'PLAN.json'),'--out',str(a.out),'--project',a.project,'--supervisor',job]
        with (folder/'stdout.txt').open('w') as log:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                                   env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2'))
        print(json.dumps({'jobId':job,'supervisorPid':child.pid,'log':str(folder/'stdout.txt'),'maximumSeconds':900}));return 0
    job=a.supervisor;rec=G._read(service,job);rec['localPid']=os.getpid();rec['launched']=time.time();G._write(service,rec)
    command=[sys.executable,'-B',__file__,'--library',str(a.library),'--plan',str(a.plan),'--out',str(a.out),'--project',a.project,'--worker',job]
    child=subprocess.Popen(command,start_new_session=True);rec['trainingPid']=child.pid;G._write(service,rec);code=1
    def stop(*_):raise KeyboardInterrupt('Stop requested.')
    signal.signal(signal.SIGTERM,stop)
    try:code=child.wait(timeout=900)
    except (subprocess.TimeoutExpired,KeyboardInterrupt) as error:
        rec['error']='Stopped by the user.' if isinstance(error,KeyboardInterrupt) else 'Fixed 15-minute study budget reached; no retry.'
        try:os.killpg(child.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait()
        code=130 if isinstance(error,KeyboardInterrupt) else 124
    finally:
        target=G._folder(service)/job/'outputs';target.mkdir(exist_ok=True)
        for path in a.out.rglob('*'):
            if path.is_file():shutil.copy2(path,target/str(path.relative_to(a.out)).replace('/','-'))
        rec['outputs']=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in target.iterdir() if p.is_file()]
        rec.update(state='done' if code==0 else 'stopped' if code==130 else 'failed',returncode=code,
                   phase='Training comparison and saved-weight verification completed' if code==0 else 'Study ended; partial evidence retained; no retry',
                   finished=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
        if code and 'error' not in rec:
            failure=a.out/'FAILURE.json';rec['error']=json.loads(failure.read_text())['reason'] if failure.exists() else 'Study process exited with code '+str(code)
        G._write(service,rec);print('[fold] '+rec['state']+'; results are development-only; no default predictor replaced',flush=True)
    return code


if __name__=='__main__':raise SystemExit(main())
