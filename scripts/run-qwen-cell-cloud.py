#!/usr/bin/env python3
"""One explicitly approved expanded Qwen job, visible in Virtual Cell's controller."""
import argparse,json,os,signal,subprocess,sys,time,uuid
from pathlib import Path
sys.dont_write_bytecode=True
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO/'scientific'))
import gpu_tasks as G
import qwen_cell_cloud_job as J


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library',required=True,type=Path);p.add_argument('--plan',required=True,type=Path);p.add_argument('--project')
    p.add_argument('--approved-once',action='store_true');p.add_argument('--stage');p.add_argument('--observe')
    a=p.parse_args();plan=json.loads(a.plan.read_text())
    from worker import Service
    service=Service(a.library.resolve())
    try:
        if a.stage:
            import modal
            folder=G._folder(service)/a.stage;rec=G._read(service,a.stage)
            attempt=json.loads((a.plan.parent/'ATTEMPT.json').read_text())
            if not (attempt.get('approvedOnce') is True and attempt.get('jobId')==a.stage and attempt.get('manifestSha256')==plan['manifestSha256']
                    and rec.get('preparedManifestSha256')==plan['manifestSha256'] and rec.get('state')=='launching' and rec.get('recipe')==J.RECIPE_ID):
                raise ValueError('Staging requires the matching explicitly approved, unstarted task.')
            with (folder/'STAGING_STARTED.json').open('x') as f:
                json.dump({'pid':os.getpid(),'maximumLaunches':1},f);f.flush();os.fsync(f.fileno())
            def cancelled():return G._read(service,a.stage)['state'] in ('cancelled','stopped')
            def event(phase,**values):print('[fold] '+phase+' '+json.dumps(values),file=sys.stderr,flush=True)
            def expired(*_):raise TimeoutError('Preparation/build time limit reached; no retry.')
            signal.signal(signal.SIGALRM,expired);signal.alarm(5400)
            try:
                volume=modal.Volume.from_name(G.VOLUME,create_if_missing=True)
                result=J.stage_and_launch(plan,volume,lambda:G._remote('gpu_task_launch',{'task':rec}),cancelled,event)
                J.write(folder/'PROVIDER_RECEIPT.json',result)
                # Cancellation during image creation may race allocation. Immediately
                # stop any returned sandbox and retain its ID; never hide a paid job.
                latest=G._read(service,a.stage);stop=latest['state'] in ('cancelled','stopped')
                latest.update(state='running',**result)
                if stop:latest['stopRequested']=True
                G._write(service,latest)
                if stop:
                    modal.Sandbox.from_id(result['sandboxId']).terminate();event('Stopped newly returned sandbox after cancellation')
                print(json.dumps({'result':result}),flush=True);return 0
            except BaseException as error:
                import traceback;traceback.print_exc(file=sys.stderr)
                print(json.dumps({'error':str(error),'automaticRetry':False}),flush=True);return 1
            finally:signal.alarm(0)
        if a.observe:
            # A separate lightweight process, not an active chat or another GPU job.
            deadline=time.monotonic()+3*3600
            while time.monotonic()<deadline:
                _,_,account=G._provider(service)
                if account!=G._read(service,a.observe)['accountId']:raise ValueError('Active Modal account changed; return to the original account to fetch results.')
                r=G.status(service,{'taskId':a.observe});print(json.dumps({k:r.get(k) for k in ['id','state','phase','error']}),flush=True)
                if r['state'] not in ['launching','running']:
                    if r['state']=='done':
                        from qwen_cell_cloud_evaluation import evaluate
                        report=evaluate(G._folder(service)/a.observe/'outputs',a.plan.parent.parent/'expanded-data')
                        print(json.dumps(report),flush=True)
                        latest=G._read(service,a.observe);outputs=G._folder(service)/a.observe/'outputs'
                        for name in ['SELECTION_SEAL.json','LOCAL_TEST_EVALUATION.json']:
                            latest['outputs']=[row for row in latest['outputs'] if row['path']!=name]
                            latest['outputs'].append({'path':name,'bytes':(outputs/name).stat().st_size,'sha256':J.digest(outputs/name),'origin':'local post-run evaluation'})
                        latest['phase']='Training completed; new local test answers evaluated after model selection; no automatic promotion'
                        G._write(service,latest)
                    return 0 if r['state']=='done' else 1
                time.sleep(20)
            raise TimeoutError('Local observer stopped after three hours; the bounded GPU job is not resubmitted. Its record remains available.')
        if not a.approved_once or not a.project:p.error('A paid submission requires explicit approval for this exact plan and an existing project. Nothing started.')
        J.verify_plan(plan)
        if not service.db.execute('SELECT 1 FROM projects WHERE id=?',(a.project,)).fetchone():raise ValueError('Unknown project.')
        python,env,account=G._provider(service);job=uuid.uuid4().hex
        claim=a.plan.parent/'ATTEMPT.json'
        with claim.open('x') as f:
            json.dump({'jobId':job,'approvedOnce':True,'manifestSha256':plan['manifestSha256'],'maximumAttempts':1,'automaticRetry':False},f);f.flush();os.fsync(f.fileno())
        request={'files':{'launch.json':json.dumps(plan['request'],sort_keys=True)}}
        rec={'id':job,'recipe':J.RECIPE_ID,'title':J.RECIPE['title'],'projectId':a.project,'provider':'modal','accountId':account,
             'inputs':request,'inputsSha256':__import__('hashlib').sha256(json.dumps(request,sort_keys=True).encode()).hexdigest(),
             'recipeSha256':plan['recipeSha256'],'gpu':'A100-80GB','timeout':2700,'state':'launching','launcherPid':os.getpid(),
             'created':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'source':J.RECIPE['source'],'license':J.RECIPE['license'],
             'evidence':J.RECIPE['evidence'],'label':'2,000 cells · complete context · activation / inhibition / drug · 3 seeds · one attempt',
             'preparedManifestSha256':plan['manifestSha256'],'automaticRetry':False}
        G._write(service,rec);folder=G._folder(service)/job
        common=[str(Path(__file__).resolve()),'--library',str(a.library.resolve()),'--plan',str(a.plan.resolve())]
        with (folder/'launch.json').open('w') as output,(folder/'launch.log').open('w') as log:
            child=subprocess.Popen([str(python),'-B',*common,'--stage',job],stdout=output,stderr=log,env=env,start_new_session=True)
        rec['launcherPid']=child.pid;G._write(service,rec)
        with (folder/'observer.log').open('w') as log:
            observer=subprocess.Popen([sys.executable,'-B',*common,'--observe',job],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        result={'jobId':job,'launcherPid':child.pid,'observerPid':observer.pid,'log':str(folder/'launch.log'),'maximumGpuSeconds':2700,'automaticRetry':False}
        J.write(a.plan.parent/'LAUNCH_RECEIPT.json',result);print(json.dumps(result));return 0
    finally:service.db.close()


if __name__=='__main__':raise SystemExit(main())
