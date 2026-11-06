"""Native training workspace: real local artifacts, preparation and reviewed launch."""
import argparse,json,os,re,subprocess,sys,time,uuid
from pathlib import Path
from types import SimpleNamespace
import gpu_tasks as G

ACTIONS={'vcell_training_status','vcell_training_prepare','vcell_training_launch'}


def read(path,default=None):return json.loads(Path(path).read_text()) if Path(path).is_file() else default
def write(path,obj):Path(path).write_text(json.dumps(obj,indent=2)+'\n')
def folder(root):return Path(root)/'virtualcell/training'


def experiment(root,identity):
    if not re.fullmatch('[a-f0-9]{32}',str(identity)):raise ValueError('Choose a saved training experiment.')
    p=folder(root)/'experiments'/str(identity)
    if not p.is_dir():raise ValueError('Unknown training experiment.')
    return p


def status(root):
    home=folder(root);rows=[]
    for p in sorted((home/'experiments').glob('*'),key=lambda p:p.stat().st_mtime,reverse=True)[:20]:
        m=read(p/'cloud-inputs/manifest.json')
        if not m:continue
        plan=read(p/'cloud-plan/PLAN.json');claim=read(p/'cloud-plan/ATTEMPT.json');task=None
        if claim:
            try:task=G._read(SimpleNamespace(root=Path(root)),claim['jobId'])
            except ValueError:pass
        results=read(Path(root)/'gpu_tasks'/claim['jobId']/'outputs/RESULTS.json') if claim else None
        final=read(Path(root)/'gpu_tasks'/claim['jobId']/'outputs/FINAL_EVALUATION.json') if claim else None
        rows.append({'id':p.name,'created':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(p.stat().st_mtime)),
                     'state':task['state'] if task else 'prepared' if plan else 'data_ready','data':m,'plan':{k:plan[k] for k in ['estimatedUsd','timeout','uploadBytes','label']} if plan else None,
                     'jobId':claim['jobId'] if claim else None,'error':task.get('error') if task else None,
                     'selection':results.get('validationWinnersIncludingBaselines') if results else None,
                     'finalSummary':{prefix:{arm:{'mse':r['mean']['mse'],'direction':r['mean']['topEffectDirectionAccuracy'],'selected':r['selectedOnValidation']} for arm,r in arms.items()} for prefix,arms in final['evaluations'].items()} if final else None})
    review=read(home/'sources/C2S_DOWNLOAD_REVIEW.json',{});chem=[read(p,{}) for p in (home/'compound-evidence').glob('*.json')]
    model=Path(root)/'engine/models/cell-training/c2s-pythia-410m';active=[]
    for p in (Path(root)/'gpu_tasks').glob('*/task.json'):
        r=read(p,{})
        if r.get('recipe')=='cell_training_prepare' and r.get('state')=='local_running':active.append({'id':r['id'],'state':r['state']})
    previous=Path(root)/'gpu_tasks/97f9f92971d64821a19a4319bdcc5ef4/outputs';old=read(previous/'RESULTS.json');old_test=read(previous/'LOCAL_TEST_EVALUATION.json')
    return {'schema':'fold.cell-training-workspace/2','experiments':rows,'preparationJobs':active,'sourcesReady':bool(read(home/'sources/SOURCES.json')),
            'compounds':{'available':len(chem),'resolved':sum(r.get('state')=='resolved' for r in chem)},
            'encoder':{'model':review.get('model'),'revision':review.get('revision'),'downloadBytes':review.get('totalBytes'),'license':review.get('license'),
                       'installed':(model/'MODEL_RECEIPT.json').is_file(),'attribution':review.get('attribution'),'downloadApprovalRequired':not (model/'MODEL_RECEIPT.json').is_file()},
            'previous':{'primaryBestMse':old['selected']['developmentMse'],'primaryReferenceMse':old['trials'][0]['baselineDevelopmentMse'],
                        'inhibition':old_test['inhibition'],'drug':old_test['drug'],'reusedDevelopment':True} if old and old_test else None,
            'automaticPromotion':False,'confidence':'Predictive calibration has not been established.'}


def python(root,name):
    p=Path(root).parent.parent/'runtimes'/name/'bin/python'
    if not p.is_file():raise ValueError('The '+name+' scientific runtime is unavailable.')
    return p


def dispatch(service,action,p):
    root=Path(service.root)
    if action=='vcell_training_status':return status(root)
    if action=='vcell_training_prepare':
        if not read(folder(root)/'sources/SOURCES.json'):raise ValueError('Register verified source data and the earlier exposure ledger first.')
        if status(root)['preparationJobs']:raise ValueError('A local preparation is already running; open its log.')
        identity=uuid.uuid4().hex;job=uuid.uuid4().hex
        rec={'id':job,'recipe':'cell_training_prepare','title':'Cell AI · prepare grounded training data','provider':'local','state':'local_running',
             'projectId':p.get('projectId'),'gpu':None,'timeout':1800,'created':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'phase':'Local data checks and preparation; no GPU or training'}
        G._write(service,rec);d=G._folder(service)/job
        with (d/'stdout.txt').open('w') as log:
            child=subprocess.Popen([str(python(root,'gbcell')),'-B',str(Path(__file__).resolve()),'--root',str(root),'--prepare',identity,'--job',job],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        rec['localPid']=child.pid;G._write(service,rec);return {'jobId':job,'experimentId':identity,'state':'preparing'}
    if action=='vcell_training_launch':
        exp=experiment(root,p.get('experimentId'));plan=exp/'cloud-plan/PLAN.json'
        if p.get('approvedRemoteCost') is not True:raise ValueError('Review and approve this single paid cloud attempt first.')
        if not plan.is_file():raise ValueError('Prepare and verify the cloud plan first.')
        command=[str(python(root,'jax-cpu')),'-B',str(Path(__file__).with_name('cell_training_runner.py')),'--library',str(root),'--plan',str(plan),'--project',str(p.get('projectId','')),'--approved-once']
        if p.get('approvedEncoderDownload') is True:command.append('--approve-encoder-download')
        result=subprocess.run(command,capture_output=True,text=True,timeout=120)
        if result.returncode:raise ValueError(result.stderr[-1500:] or 'The prepared attempt was not started.')
        return json.loads(result.stdout.strip().splitlines()[-1])
    raise ValueError('Unknown cell training action.')


def prepare_worker(root,identity,job):
    from cell_training_data import prepare
    from cell_training_cloud import prepare as prepare_cloud
    from cell_training_features import SEED
    service=SimpleNamespace(root=Path(root));record=G._read(service,job);source=read(folder(root)/'sources/SOURCES.json');exp=folder(root)/'experiments'/identity
    import signal
    def expired(*_):raise TimeoutError('Local preparation reached its 30-minute bound; no automatic retry.')
    signal.signal(signal.SIGALRM,expired);signal.alarm(1800)
    try:
        history=read(source['history'])
        for p in (folder(root)/'experiments').glob('*'):
            claim=read(p/'cloud-plan/ATTEMPT.json')
            if claim and (Path(root)/'gpu_tasks'/claim['jobId']/'outputs/FINAL_EVALUATION.json').is_file():
                old=read(p/'SPLIT_MANIFEST.json');history.setdefault('chemicalIdentityExposure',[]).extend(sum(old['groups']['drug'].values(),[]))
                history['groups']['inhibition']['train']+=sum(old['groups']['inhibition'].values(),[])
        merged=folder(root)/'sources'/('exposure-'+identity+'.json');write(merged,history)
        checkpoint=Path(root)/'engine/models/qwen-cell/Qwen2.5-Coder-3B-Instruct'
        prepare(root,source['seedData'],merged,checkpoint,exp,lambda phase,**kw:print(json.dumps({'phase':phase,**kw}),flush=True))
        prepare_cloud(Path(__file__).resolve().parent.parent,exp,checkpoint,Path(root)/'engine/models/cell-training/c2s-pythia-410m',source['encoderReview'],exp/'cloud-plan')
        record.update(state='done',returncode=0,phase='Grounded data and cloud review prepared; no training started');code=0
    except BaseException as error:
        import traceback;traceback.print_exc();record.update(state='failed',returncode=1,error=str(error));code=1
    finally:
        signal.alarm(0);record['finished']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());G._write(service,record)
    return code


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--prepare',required=True);p.add_argument('--job',required=True);a=p.parse_args();raise SystemExit(prepare_worker(a.root,a.prepare,a.job))
