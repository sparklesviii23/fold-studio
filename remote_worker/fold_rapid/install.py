"""Approved, isolated runtime installation; never replaces a host Python stack."""
import argparse
import fcntl
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys
from .contracts import canonical,digest
from .registry import config

def update_config(root,section,key,value):
    root=pathlib.Path(root);root.mkdir(parents=True,exist_ok=True)
    with (root/'configuration.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        cfg=config(root);cfg.setdefault(section,{})[key]=value
        temp=root/'config.pending.json';temp.write_text(canonical(cfg));os.replace(temp,root/'config.json')

def install_one(root,engine,approved):
    if not approved:raise ValueError('Approve the isolated runtime dependency download before installation.')
    if engine not in ('bindcraft2','boltzgen','esmfold2'):raise ValueError('Unknown scientific runtime.')
    if platform.system()!='Linux' or platform.machine() not in ('x86_64','amd64'):raise ValueError('This release installs scientific environments only on Linux AMD64.')
    root=pathlib.Path(root);release=pathlib.Path(os.environ.get('RAPID_RELEASE_DIR','/opt/fold-rapid-release'))
    index=json.loads((release/'release.json').read_text())
    for name,expected in index['files'].items():
        path=release/name
        if path.is_symlink() or release.resolve() not in path.resolve().parents or digest(path.read_bytes())!=expected:raise ValueError('Release integrity mismatch: '+name)
    if shutil.disk_usage(root).free<15*1024**3:raise ValueError('Keep at least 15 GiB free before installing an isolated CUDA runtime.')
    prefix=root/'runtimes'/engine;prefix.parent.mkdir(exist_ok=True)
    lockpath=root/'installation.lock'
    with lockpath.open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        existing=config(root).get('runtimes',{}).get(engine)
        if existing and pathlib.Path(existing['python']).is_file():return existing
        if not (prefix/'bin/python').is_file():subprocess.run([sys.executable,'-m','venv',str(prefix)],check=True)
        python=str(prefix/'bin/python')
        try:
            for requirements in (release/'worker/environments/core.lock',release/f'worker/environments/{engine}.lock'):
                subprocess.run([python,'-m','pip','install','--no-cache-dir','--require-hashes','-r',str(requirements)],check=True)
            if engine!='esmfold2':subprocess.run([python,'-m','pip','install','--no-deps','--no-build-isolation',str(release/'sources'/engine)],check=True)
            # Route B must exercise the same real imports as a prebuilt image;
            # a successful pip exit alone is not usable runtime evidence.
            probe=subprocess.check_output([python,'-I','-B',str(release/'worker/fold_rapid/runtime_probe.py'),'--engine',engine],text=True)
            imports=json.loads(probe.splitlines()[-1])
            packages=subprocess.check_output([python,'-m','pip','freeze','--all'],text=True)
            receipt={'python':python,'source':str(release/'sources'/('boltzgen' if engine=='esmfold2' else engine)),'dependencyLockSha256':digest((release/f'worker/environments/{engine}.lock').read_bytes()),'installedPackages':packages,'importProbe':imports,'cudaQualified':False}
            update_config(root,'runtimes',engine,receipt)
            return receipt
        except BaseException:
            # Keep logs and failed prefix for inspection; never call it installed.
            raise

def install(root,engine,approved):
    receipt=install_one(root,engine,approved)
    if engine=='boltzgen':
        esm=install_one(root,'esmfold2',approved)
        receipt['esmfold2Python']=esm['python'];update_config(root,'runtimes','boltzgen',receipt)
    return receipt

def background(root,engine):
    root=pathlib.Path(root);status=root/('install-'+engine+'.json')
    current=json.loads(status.read_text()) if status.is_file() else {}
    if current.get('state')=='running':
        try:os.kill(current['pid'],0);return current
        except ProcessLookupError:pass
    with (root/('install-'+engine+'.log')).open('ab') as log:
        child=subprocess.Popen([sys.executable,'-m','fold_rapid.install','--root',str(root),'--engine',engine,'--approve'],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
    value={'state':'running','pid':child.pid,'engine':engine,'modelsDownloaded':False}
    status.write_text(canonical(value));return value

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',default=os.environ.get('RAPID_ROOT','/data/rapid'));parser.add_argument('--engine',choices=['bindcraft2','boltzgen'],required=True);parser.add_argument('--approve',action='store_true');args=parser.parse_args();root=pathlib.Path(args.root);root.mkdir(parents=True,exist_ok=True)
    status=root/('install-'+args.engine+'.json')
    try:
        result=install(root,args.engine,args.approve);value={'state':'installed','runtime':result,'cudaQualified':False,'modelsDownloaded':False}
    except Exception as error:value={'state':'failed','error':str(error),'cudaQualified':False}
    status.write_text(canonical(value));print(canonical(value))
    if value['state']=='failed':raise SystemExit(1)

if __name__=='__main__':main()
