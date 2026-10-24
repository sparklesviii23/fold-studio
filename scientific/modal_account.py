"""Official browser login with transient credentials promoted to macOS Keychain.
No CLI output, secrets, authentication URLs or TOML enter research records.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

ACTIONS={'biology_modal_auth_start','biology_modal_auth_status','biology_modal_connection_test'}


def state_path(s):
    folder=s.root/'provider-auth';folder.mkdir(mode=0o700,exist_ok=True)
    return folder/'modal.json'


def read(s):
    path=state_path(s)
    return json.loads(path.read_text()) if path.is_file() else {'state':'not_started'}


def dispatch(s,action,p):
    s.project(p['projectId'])
    import biology_providers as providers
    if action=='biology_modal_auth_status':return {**read(s),'sdk':providers.status(s)}
    if action=='biology_modal_connection_test':
        if not os.environ.get('FOLD_PROVIDER_CHILD'):return providers.rpc(s,action,p)
        import modal
        # Official authenticated SDK hello, without spawning a function or GPU.
        try:modal.Client.from_env()
        except Exception:raise ValueError('Modal authentication could not be verified. Connect your account; no GPU was started.') from None
        return {'authenticated':True,'gpuStarted':False,'scientificCloudQualified':False,'deploymentChecked':False}
    if action=='biology_modal_auth_start':
        if p.get('approvedBrowserLogin') is not True:raise ValueError('Approve opening official Modal login and saving the resulting credentials in macOS Keychain.')
        python=providers.interpreter(s)
        if not python or not providers.status(s)['installed']:raise ValueError('The pinned provider SDK is required.')
        old=read(s)
        if old.get('state')=='waiting_for_browser' and time.time()-old.get('started',0)<600:return old
        path=state_path(s);row={'state':'waiting_for_browser','started':time.time(),'credentialStorage':'macOS Keychain','gpuStarted':False};path.write_text(json.dumps(row))
        subprocess.Popen([sys.executable,'-B',str(pathlib.Path(__file__).resolve()),'--login',str(path),str(python)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)
        return row
    raise ValueError('Unsupported Modal account action.')


def login(path,python):
    import tomllib
    row=json.loads(path.read_text())
    try:
        with tempfile.TemporaryDirectory(prefix='fold-modal-auth-') as folder:
            config=pathlib.Path(folder)/'credentials.toml'
            env={k:v for k,v in os.environ.items() if not k.startswith('MODAL_') and k not in ('PYTHONPATH','PYTHONHOME')}
            env['MODAL_CONFIG_PATH']=str(config)
            result=subprocess.run([python,'-m','modal','token','new','--verify','--activate','--profile','foldstudio','--expires-in','7d'],env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=600)
            if result.returncode or not config.is_file():raise ValueError('Official browser login did not complete.')
            profile=tomllib.loads(config.read_text()).get('foldstudio',{})
            if not profile.get('token_id') or not profile.get('token_secret'):raise ValueError('Official SDK did not return a complete token pair.')
            from provider_credentials import access
            access('modal-token-id',profile['token_id']);access('modal-token-secret',profile['token_secret'])
            row.update(state='connected',temporaryCredentialFileRemoved=True)
    except Exception:
        row.update(state='failed',reason='Login did not complete or Keychain refused storage. Retry official browser login; credentials are never returned.')
    row['finished']=time.time();path.write_text(json.dumps(row))


if __name__=='__main__' and len(sys.argv)==4 and sys.argv[1]=='--login':login(pathlib.Path(sys.argv[2]),sys.argv[3])
