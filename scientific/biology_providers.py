"""Isolated optional service SDKs; never modify a signed scientific runtime."""
import json
import os
import pathlib
import subprocess
import sys

PINS={'boltz-api':'0.50.0','modal':'1.6.2'}


def interpreter(s):
    configured=s.setting('biologyServicesPython')
    choices=[pathlib.Path(configured)] if configured else []
    choices += [pathlib.Path.home()/'Library/Application Support/FoldStudio/providers/bin/python',pathlib.Path(__file__).resolve().parents[2]/'runtimes/biology-services/bin/python']
    return next((p for p in choices if p.is_file()),None)


def status(s):
    python=interpreter(s)
    if not python:return {'installed':False,'versions':{},'authenticated':False,'modelsDownloaded':False}
    code="import json,importlib.metadata as m;print(json.dumps({k:m.version(k) for k in ['modal','boltz-api']}))"
    p=subprocess.run([str(python),'-I','-B','-c',code],capture_output=True,text=True,timeout=15)
    try:versions=json.loads(p.stdout) if p.returncode==0 else {}
    except ValueError:versions={}
    return {'installed':versions==PINS,'versions':versions,'python':str(python),'modelsDownloaded':False,'credentialLocation':'Official provider environment / account credential store; never project manifests'}


def rpc(s,action,payload):
    python=interpreter(s)
    if not python or not status(s)['installed']:raise ValueError('Install the pinned isolated provider SDK runtime first.')
    env={k:v for k,v in os.environ.items() if k not in ('PYTHONPATH','PYTHONHOME')}
    if sys.platform=='darwin':
        from provider_credentials import environment
        env.update(environment())
    env.update(FOLD_PROVIDER_CHILD='1',PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1')
    result=subprocess.run([str(python),'-B',str(pathlib.Path(__file__).with_name('worker.py')),'--root',str(s.root)],input=json.dumps({'action':action,'payload':payload}),text=True,capture_output=True,env=env,timeout=100)
    if len(result.stdout)>8*1024**2:raise ValueError('Isolated provider process failed or exceeded its response limit; no automatic resubmission.')
    try:body=json.loads(result.stdout)
    except ValueError:raise ValueError('Provider process returned an invalid response.') from None
    if body.get('error'):raise ValueError(body['error'])
    if result.returncode:raise ValueError('Isolated provider process failed; no automatic resubmission.')
    return body['result']
