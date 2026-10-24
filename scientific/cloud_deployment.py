"""Durable, approved client-side image deployment; never scientific orchestration."""
import fcntl
import json
import os
import pathlib
import subprocess
import sys
import time

ACTIONS={'cloud_engine_deploy','cloud_engine_deployment_status'}


def write(path,value):
    temp=path.with_suffix('.pending');temp.write_text(json.dumps(value,allow_nan=False));temp.replace(path)


def dispatch(s,action,p):
    s.project(p['projectId']);folder=s.root/'cloud-engine-deployment';folder.mkdir(mode=0o700,exist_ok=True);path=folder/'status.json'
    if action=='cloud_engine_deployment_status':return json.loads(path.read_text()) if path.is_file() else {'state':'not_deployed','scientificCloudQualified':False}
    if p.get('approvedDeployment') is not True or type(p.get('maxApprovedUSD'))not in(int,float) or not 0<p['maxApprovedUSD']<=1:raise ValueError('Approve the source-only CPU deployment check with a finite allowance up to 1 USD; no GPU/model execution is included.')
    import biology_pipeline,biology_providers,rapid_remote
    biology_pipeline.common()
    from fold_rapid.modal_provider import configuration
    from fold_rapid.cloud_image import prepare_release
    cfg=configuration(p['configuration'])
    if cfg.get('imageRecipe')!='rapid-cuda13-core-v1':raise ValueError('This bounded deployment action uses the reviewed standalone core recipe only.')
    python=biology_providers.interpreter(s)
    if not python or not biology_providers.status(s)['installed']:raise ValueError('The official pinned provider SDK is unavailable.')
    with (folder/'deployment.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if path.exists():
            old=json.loads(path.read_text())
            if old['state'] in ('queued','building','checking'):
                try:os.kill(old['pid'],0);return old
                except (ProcessLookupError,KeyError):raise ValueError('Previous deployment outcome is uncertain; inspect its remote application before explicitly updating again.')
        release=prepare_release(folder/'source',rapid_remote.artifact()[0]);(folder/'configuration.json').write_text(json.dumps(cfg))
        env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
        from provider_credentials import environment
        env.update(environment());env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1')
        value={'state':'queued','started':time.time(),'appName':cfg['appName'],'maximumApprovedUSD':p['maxApprovedUSD'],'gpuStarted':False,'modelDownloads':False,'scientificCloudQualified':False,'sourceManifestSha256':__import__('hashlib').sha256((release/'release.json').read_bytes()).hexdigest()}
        write(path,value)
        with (folder/'deployment.log').open('ab') as log:
            child=subprocess.Popen([str(python),'-B',str(pathlib.Path(__file__).resolve()),'--deploy',str(folder)],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True)
        value['pid']=child.pid;write(path,value);return value


def deploy(folder):
    path=folder/'status.json';value=json.loads(path.read_text());value['pid']=os.getpid();value['state']='building';write(path,value)
    release=folder/'source/release';sys.path.insert(0,str(release/'worker'))
    from fold_rapid.modal_provider import build_app,deploy_app
    cfg=json.loads((folder/'configuration.json').read_text())
    try:
        app=build_app(cfg,worker_source=release/'worker');deploy_app(app);value.update(state='checking',appId=app.app_id);write(path,value)
        import modal
        result=modal.Function.from_name(cfg['appName'],'unified_control').remote('inventory',{})
        value.update(state='deployed',health=result,deploymentVerified=True,finished=time.time())
    except Exception as exc:
        message=str(exc)
        for key in ('MODAL_TOKEN_ID','MODAL_TOKEN_SECRET','BOLTZ_API_KEY'):
            if os.environ.get(key):message=message.replace(os.environ[key],'[redacted]')
        value.update(state='failed',exceptionType=type(exc).__name__,error=message[:2000],finished=time.time(),resubmitAutomatically=False)
    write(path,value)


if __name__=='__main__' and len(sys.argv)==3 and sys.argv[1]=='--deploy':deploy(pathlib.Path(sys.argv[2]))
