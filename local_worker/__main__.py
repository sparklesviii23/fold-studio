"""Fold worker CLI: one submission dispatches an entire bounded task."""
from __future__ import annotations
import argparse, json, os, pathlib, plistlib, signal, subprocess, sys, time
from .core import Broker, DEFAULT_HOME, REPO, OPERATIONS, now, proc, resources, run
from .daemon import serve

LABEL='org.foldstudio.development-worker'
def output(value):print(json.dumps(value,indent=2,default=str))
def service_file():return pathlib.Path.home()/'Library/LaunchAgents'/f'{LABEL}.plist'
def target():return f'gui/{os.getuid()}/{LABEL}'
def install(broker):
    if sys.platform!='darwin':raise ValueError('launchd requires macOS.')
    p=service_file();p.parent.mkdir(parents=True,exist_ok=True)
    payload={'Label':LABEL,'ProgramArguments':[sys.executable,'-B','-m','local_worker','--home',str(broker.home),'serve'],'WorkingDirectory':str(REPO),'RunAtLoad':True,'KeepAlive':{'SuccessfulExit':False},'ThrottleInterval':15,'ProcessType':'Background','LowPriorityIO':True,'Nice':10,'StandardOutPath':str(broker.home/'service.log'),'StandardErrorPath':str(broker.home/'service-error.log'),'EnvironmentVariables':{'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1'}}
    if p.exists() and plistlib.loads(p.read_bytes()).get('WorkingDirectory')!=str(REPO):raise ValueError('Another installation owns the launchd label.')
    p.write_bytes(plistlib.dumps(payload));os.chmod(p,0o600);return p

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--home',type=pathlib.Path,default=DEFAULT_HOME)
    sub=p.add_subparsers(dest='action',required=True)
    for name in ['serve','start','stop','enable','disable','status','health','jobs','operations','emergency-stop','clear-emergency','benchmark']:sub.add_parser(name)
    submit=sub.add_parser('submit');submit.add_argument('file',help='JSON file, or - for stdin')
    for name in ['inspect','report','logs','cancel','resume','rollback']:
        q=sub.add_parser(name);q.add_argument('id')
    ai=sub.add_parser('configure-local-ai');ai.add_argument('--aider',required=True,type=pathlib.Path);ai.add_argument('--ollama',required=True,type=pathlib.Path)
    notifications=sub.add_parser('notifications');notifications.add_argument('state',choices=['on','off'])
    args=p.parse_args();os.umask(0o077);b=Broker(args.home)
    try:
        if args.action=='serve':serve(b);return
        if args.action=='operations':output({'operations':sorted(OPERATIONS),'arbitraryCommands':False});return
        if args.action=='submit':output(b.submit(json.loads(sys.stdin.read() if args.file=='-' else pathlib.Path(args.file).read_text())));return
        if args.action in ('enable','start'):
            path=install(b);run(['/bin/launchctl','enable',target()]);r=run(['/bin/launchctl','bootstrap',f'gui/{os.getuid()}',str(path)])
            if r.returncode and run(['/bin/launchctl','print',target()]).returncode:raise RuntimeError(r.stderr)
            if args.action=='start':run(['/bin/launchctl','kickstart',target()])
            output({'status':'requested','service':LABEL,'plist':str(path)});return
        if args.action in ('stop','disable'):
            # launchctl owns this exact registered worker, never the scientific app.
            b.wake();r=run(['/bin/launchctl','bootout',target()])
            for _ in range(30):
                if run(['/bin/launchctl','print',target()]).returncode:break
                time.sleep(.2)
            if args.action=='disable':run(['/bin/launchctl','disable',target()])
            output({'state':'disabled' if args.action=='disable' else 'stopped','queuedTasks':'preserved','serviceReply':r.stderr.strip()[:500]});return
        if args.action in ('status','health'):
            d=b.setting('daemon',{});pid=d.get('pid');alive=bool(pid and proc(pid)==d.get('identity'))
            rows=[dict(r) for r in b.db.execute('SELECT status,count(*) count FROM tasks GROUP BY status')]
            value={'running':alive,'daemon':d,'heartbeatAgeSeconds':round(time.time()-b.setting('daemonHeartbeat'),1) if b.setting('daemonHeartbeat') else None,'emergencyStop':b.setting('emergency',False),'tasks':rows,'home':str(b.home),'localAI':{'configured':bool(b.setting('localAI')),'inference':'local only, optional; installation not implied'},'workCallback':'not configured; reports persist for explicit retrieval'}
            if args.action=='health':value['resources']=resources(b.repo)
            output(value);return
        if args.action=='jobs':output([dict(r) for r in b.db.execute('SELECT id,status,created,started,finished,error FROM tasks ORDER BY created DESC LIMIT 30')]);return
        if args.action=='emergency-stop':b.set('emergency',True);b.wake();output({'emergencyStop':True,'effect':'Stops only owned development work; queued jobs remain paused.'});return
        if args.action=='clear-emergency':b.set('emergency',False);b.wake();output({'emergencyStop':False});return
        if args.action=='notifications':b.set('notifications',args.state=='on');output({'notifications':args.state});return
        if args.action=='configure-local-ai':
            binary=args.aider.expanduser().resolve()
            if not binary.is_file() or not os.access(binary,os.X_OK):raise ValueError('Aider must be an existing executable. This command installs nothing.')
            ollama=args.ollama.expanduser().resolve()
            if not ollama.is_file():raise ValueError('An installed Ollama executable is required.')
            b.set('localAI',{'aider':str(binary),'ollama':str(ollama),'modelStore':str(b.home/'models'),'configured':now()});output({'configured':True,'endpoint':'per-task owned loopback server + bounded gateway','remoteFallback':False,'qualification':'not implied; run a bounded task to qualify'});return
        if args.action=='benchmark':
            from .benchmark import benchmark
            output(benchmark(b));return
        task=b.task(args.id);folder=b.home/'tasks'/task['id']
        if args.action=='inspect':output(task)
        elif args.action=='report':
            summary=folder/'summary.json';output(json.loads(summary.read_text()) if summary.exists() else {'id':task['id'],'status':task['status'],'error':task['error'],'report':'not produced yet'})
        elif args.action=='logs':
            logs=[]
            for f in sorted(folder.glob('command-*.log')):
                with f.open('rb') as stream:stream.seek(max(0,f.stat().st_size-3000));excerpt=stream.read().decode(errors='replace')
                logs.append({'path':str(f),'last3000Bytes':excerpt})
            output(logs[-8:])
        elif args.action=='cancel':b.cancel(args.id);output({'id':args.id,'status':b.task(args.id)['status']})
        elif args.action=='resume':b.resume(args.id);output({'id':args.id,'status':'queued'})
        elif args.action=='rollback':
            if task['status'] not in ('completed','failed','blocked','cancelled'):raise ValueError('Finish or cancel the task before discarding its worktree.')
            if task['runner_pid'] and proc(task['runner_pid'])==task['runner_identity']:raise ValueError('Owned runner is still active.')
            path=b.home/'worktrees'/task['id']
            if not path.is_dir() or path.is_symlink():raise ValueError('No owned review worktree.')
            untracked=run(['/usr/bin/git','ls-files','--others','--exclude-standard'],cwd=path)
            if untracked.stdout.strip():raise ValueError('Untracked files require review; rollback refuses to erase them.')
            diff=run(['/usr/bin/git','diff','--no-ext-diff','--no-textconv','--binary','HEAD'],cwd=path)
            if diff.returncode or len(diff.stdout.encode())>1024**2:raise ValueError('Cannot safely retain rollback patch.')
            folder.mkdir(exist_ok=True,parents=True);(folder/'rollback.patch').write_text(diff.stdout)
            result=run(['/usr/bin/git','-c','core.hooksPath=/dev/null','worktree','remove','--force',str(path)],cwd=b.repo)
            if result.returncode:raise RuntimeError(result.stderr)
            b.event(args.id,'rollback','Owned worktree removed after patch preservation; active checkout unchanged.');output({'id':args.id,'worktreeRemoved':True,'patchPreserved':str(folder/'rollback.patch')})
    except Exception as e:output({'error':type(e).__name__+': '+str(e)});sys.exit(1)
    finally:b.db.close()
if __name__=='__main__':main()
