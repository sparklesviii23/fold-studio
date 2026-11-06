"""One explicitly approved grounded cell experiment; reusable native controller."""
import argparse,json,os,signal,subprocess,sys,time,uuid
from pathlib import Path
sys.dont_write_bytecode=True
import gpu_tasks as G
import cell_training_cloud as J


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',required=True,type=Path);p.add_argument('--plan',required=True,type=Path);p.add_argument('--project')
    p.add_argument('--approved-once',action='store_true');p.add_argument('--approve-encoder-download',action='store_true');p.add_argument('--stage');p.add_argument('--observe');a=p.parse_args()
    plan=json.loads(a.plan.read_text());from worker import Service
    service=Service(a.library.resolve())
    try:
        if a.stage:
            import modal
            rec=G._read(service,a.stage);folder=G._folder(service)/a.stage;attempt=json.loads((a.plan.parent/'ATTEMPT.json').read_text())
            if attempt.get('jobId')!=a.stage or attempt.get('approvedOnce') is not True or attempt.get('manifestSha256')!=plan['manifestSha256'] or rec['state']!='launching' or rec['recipe']!=J.RECIPE_ID:raise ValueError('Matching explicit approval and unstarted task required.')
            with (folder/'STAGING_STARTED.json').open('x') as f:json.dump({'pid':os.getpid(),'maximumLaunches':1},f)
            def event(phase,**kw):print('[fold] '+phase+' '+json.dumps(kw),file=sys.stderr,flush=True)
            def cancelled():return G._read(service,a.stage)['state'] in ['cancelled','stopped']
            def expired(*_):raise TimeoutError('Fixed 90-minute preparation/build limit reached; no retry.')
            signal.signal(signal.SIGALRM,expired);signal.alarm(5400)
            try:
                if cancelled():raise InterruptedError('Stopped before download/allocation.')
                J.download_encoder(plan,attempt.get('encoderDownloadApproved') is True,event)
                volume=modal.Volume.from_name(G.VOLUME,create_if_missing=True)
                result=J.stage_and_launch(plan,volume,lambda:G._remote('gpu_task_launch',{'task':rec}),cancelled,event);J.write(folder/'PROVIDER_RECEIPT.json',result)
                latest=G._read(service,a.stage);stop=latest['state'] in ['cancelled','stopped'];latest.update(state='running',**result)
                if stop:latest['stopRequested']=True
                G._write(service,latest)
                if stop:modal.Sandbox.from_id(result['sandboxId']).terminate()
                print(json.dumps({'result':result}),flush=True);return 0
            except BaseException as error:
                import traceback;traceback.print_exc(file=sys.stderr);print(json.dumps({'error':str(error),'automaticRetry':False}),flush=True);return 1
            finally:signal.alarm(0)
        if a.observe:
            from cell_training_evaluation import evaluate
            deadline=time.monotonic()+4*3600
            while time.monotonic()<deadline:
                _,_,account=G._provider(service)
                if account!=G._read(service,a.observe)['accountId']:raise ValueError('Return to the original Modal account to collect this run.')
                r=G.status(service,{'taskId':a.observe});print(json.dumps({k:r.get(k) for k in ['id','state','phase','error']}),flush=True)
                if r['state'] not in ['launching','running']:
                    if r['state']=='done':
                        out=G._folder(service)/a.observe/'outputs';evaluate(out,plan['experiment']);latest=G._read(service,a.observe)
                        for name in ['SELECTION_SEAL.json','FINAL_EVALUATION.json','RESULTS_EXPLAINED.md']:
                            latest['outputs']=[row for row in latest['outputs'] if row['path']!=name];latest['outputs'].append({'path':name,'bytes':(out/name).stat().st_size,'sha256':J.digest(out/name),'origin':'local post-run evaluation'})
                        latest['phase']='Grounded training finished; sealed local final tests scored; no automatic promotion';G._write(service,latest)
                    return 0 if r['state']=='done' else 1
                time.sleep(20)
            raise TimeoutError('Observer deadline reached; no new run submitted. The original task remains recorded.')
        if not a.approved_once or not a.project:p.error('Explicit paid approval and a project are required; nothing started.')
        J.verify_plan(plan,allow_missing_biology=True)
        missing=any(not Path(x['local']).is_file() for x in plan['assets'] if x['path'].startswith('biology/'))
        if missing and not a.approve_encoder_download:raise ValueError('Approve the official Cell2Sentence download before submitting this combined experiment.')
        if not service.db.execute('SELECT 1 FROM projects WHERE id=?',(a.project,)).fetchone():raise ValueError('Unknown project.')
        python,env,account=G._provider(service);job=uuid.uuid4().hex
        with (a.plan.parent/'ATTEMPT.json').open('x') as f:
            json.dump({'jobId':job,'manifestSha256':plan['manifestSha256'],'approvedOnce':True,'encoderDownloadApproved':a.approve_encoder_download,'automaticRetry':False},f);f.flush();os.fsync(f.fileno())
        request={'files':{'launch.json':json.dumps(plan['request'])}}
        rec={'id':job,'recipe':J.RECIPE_ID,'title':J.RECIPE['title'],'projectId':a.project,'provider':'modal','accountId':account,'inputs':request,
             'recipeSha256':plan['recipeSha256'],'gpu':plan['gpu'],'timeout':plan['timeout'],'state':'launching','launcherPid':os.getpid(),
             'created':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'source':J.RECIPE['source'],'license':J.RECIPE['license'],'evidence':J.RECIPE['evidence'],
             'label':plan['label'],'preparedManifestSha256':plan['manifestSha256'],'automaticRetry':False}
        G._write(service,rec);folder=G._folder(service)/job;common=[str(Path(__file__).resolve()),'--library',str(a.library.resolve()),'--plan',str(a.plan.resolve())]
        with (folder/'launch.json').open('w') as output,(folder/'launch.log').open('w') as log:
            child=subprocess.Popen([str(python),'-B',*common,'--stage',job],stdout=output,stderr=log,env=env,start_new_session=True)
        rec['launcherPid']=child.pid;G._write(service,rec)
        with (folder/'observer.log').open('w') as log:observer=subprocess.Popen([sys.executable,'-B',*common,'--observe',job],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        result={'jobId':job,'launcherPid':child.pid,'observerPid':observer.pid,'maximumGpuSeconds':5400,'automaticRetry':False};J.write(a.plan.parent/'LAUNCH_RECEIPT.json',result);print(json.dumps(result));return 0
    finally:service.db.close()


if __name__=='__main__':raise SystemExit(main())
