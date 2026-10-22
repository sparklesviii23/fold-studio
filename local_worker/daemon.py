"""One independent, low-idle-cost daemon. Work is not involved in its execution loop."""
from __future__ import annotations
import contextlib, fcntl, json, os, pathlib, re, select, signal, sqlite3, subprocess, sys, time
from .core import Broker, REPO, admission, now, proc, resources, run
from .executor import Blocked, Cancelled, PYTHON, environment, command, worktree, patch, changes, local_agent, child_plan, ollama_request

STOP=False

def notify(broker,id,status):
    if not broker.setting('notifications',True):return {'state':'disabled'}
    script='on run argv\n display notification (item 2 of argv) with title (item 1 of argv)\nend run'
    try:
        p=run(['/usr/bin/osascript','-e',script,'Fold Studio Worker',status+': '+id[:8]+'. Inspect the local task report.'],timeout=3)
        return {'state':'requested' if p.returncode==0 else 'unavailable','deliveryVerified':False,'note':'Delivery depends on macOS notification settings; no Work callback was sent.'}
    except (OSError,subprocess.TimeoutExpired):return {'state':'unavailable','deliveryVerified':False}

def execute_command(broker,task,repo,folder,name,argv,deadline,ai=False,provider=None):
    spec=task['spec'];ordinal=len(list(folder.glob('plan-*.json')));log=folder/('command-%02d.log'%ordinal);receipt=folder/('receipt-%02d.json'%ordinal)
    policy_command=child_plan(argv,repo,folder,spec,ai,broker.repo);plan=folder/('plan-%02d.json'%ordinal)
    plan.write_text(json.dumps({'argv':policy_command,'cwd':str(repo),'env':{**environment(folder),**({'OLLAMA_API_BASE':'http://127.0.0.1:'+str(provider.port)} if provider else {})},'log':str(log),'receipt':str(receipt),'maxLogBytes':spec['resourceBudget']['maxLogMiB']*1048576}))
    child=subprocess.Popen([sys.executable,'-B',str(REPO/'local_worker/runner.py'),str(plan)],start_new_session=True,cwd=REPO,env=environment(folder),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    identity=proc(child.pid);broker.db.execute('UPDATE tasks SET runner_pid=?,runner_identity=? WHERE id=?',(child.pid,identity,task['id']));peak=0;why=None;last_resource=0
    try:
        while child.poll() is None:
            if STOP or broker.setting('emergency',False) or broker.task(task['id'])['status']=='cancelled':raise Cancelled('Stopped by explicit local control.')
            if time.monotonic()>deadline:raise TimeoutError('Task execution timeout reached.')
            if sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())>128*1048576:raise RuntimeError('Task artifact storage exceeded 128 MiB.')
            if log.exists() and log.stat().st_size>spec['resourceBudget']['maxLogMiB']*1048576:raise RuntimeError('Log budget exceeded.')
            # Sum RSS of the owned process tree; conservative due to shared pages.
            p=run(['/bin/ps','-axo','pid=,ppid=,rss=']);rows=[tuple(map(int,l.split())) for l in p.stdout.splitlines() if len(l.split())==3];owned={child.pid}|({provider.child.pid} if provider else set())
            for _ in range(5):owned.update(pid for pid,ppid,rss in rows if ppid in owned)
            rss=sum(rss for pid,ppid,rss in rows if pid in owned)/1024;peak=max(peak,rss)
            if rss>spec['resourceBudget']['memoryMiB']:raise Blocked('Owned command RSS exceeded memory budget; only this task was stopped.')
            if time.monotonic()-last_resource>5:
                snap=resources(broker.repo);last_resource=time.monotonic()
                if snap['scientificWorkloads'] or snap['memoryPressureLevel'] not in (1,):raise Blocked('Scientific workload or memory pressure appeared; this development task yielded.')
            broker.db.execute('UPDATE tasks SET heartbeat=? WHERE id=?',(time.time(),task['id']));time.sleep(.5)
    except BaseException:
        if child.poll() is None:
            # PID reuse is excluded by this unreaped direct child handle.
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=3)
        raise
    finally:
        (folder/('monitor-%02d.json'%ordinal)).write_text(json.dumps({'operation':name,'peakProcessTreeRssMiB':round(peak,2)}))
        broker.db.execute('UPDATE tasks SET runner_pid=NULL,runner_identity=NULL WHERE id=?',(task['id'],))
    data=json.loads(receipt.read_text()) if receipt.exists() else {'returncode':child.returncode,'seconds':None}
    tail=b''
    if log.exists():
        with log.open('rb') as f:f.seek(max(0,log.stat().st_size-4000));tail=f.read()
    return {'operation':name,**data,'peakProcessTreeRssMiB':round(peak,2),'log':str(log),'diagnostic':tail.decode(errors='replace')[-3000:] if data['returncode'] else '', 'successExcerpt':tail.decode(errors='replace')[-500:] if data['returncode']==0 else ''}

def execute(broker,task):
    id=task['id'];spec=task['spec'];folder=broker.home/'tasks'/id;folder.mkdir(parents=True,exist_ok=True,mode=0o700);started=time.monotonic();result={'id':id,'instructions':spec['instructions'],'acceptanceCriteria':spec['acceptanceCriteria'],'checks':[],'changedFiles':[],'modelCalls':0,'workInterventionsDuringExecution':0,'workAllowanceUsed':None,'cloudInference':'disabled','resourceAdmission':resources(broker.repo),'artifacts':[]};status='failed';error=None;repo=broker.repo;provider=None;execution_lock=None
    try:
        execution_lock=(broker.resource_domain/'execution.lock').open('a')
        try:fcntl.flock(execution_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise Blocked('Another local development executor owns the global resource slot.')
        reason=admission(spec,result['resourceAdmission'])
        if reason:raise Blocked(reason)
        result['tier']=1 if spec['type']=='local-ai' else 0
        if spec['type'] in ('patch','local-ai'):
            repo,revision=worktree(broker,task,folder);result.update(worktree=str(repo),baseRevision=revision,patchReadyForReview=False)
        else:result['baseRevision']=run(['/usr/bin/git','rev-parse','HEAD'],cwd=repo).stdout.strip()
        deadline=started+spec['timeoutSeconds']
        if spec['type']=='local-ai':
            from .provider import LocalProvider
            provider=LocalProvider(broker,spec,folder).__enter__()
        if spec['type']=='patch':patch(repo,spec['patches'])
        for attempt in range(spec['retryLimit']+1):
            if spec['type']=='local-ai':
                if result['modelCalls']>=spec['maxModelCalls']:raise Blocked('Local model-call budget exhausted; review diagnostics in Work.')
                diagnostic='\nPrevious checks: '+json.dumps(result['checks'][-8:])[-6000:] if attempt else ''
                argv=local_agent(broker,spec,repo,folder,diagnostic);result['modelCalls']+=1
                check=execute_command(broker,task,repo,folder,'local-aider',argv,deadline,provider.port,provider);result['checks'].append(check)
                if check['returncode']:raise Blocked('Local coding agent failed; review the compact diagnostic.')
                changes(repo,spec['authorizedPaths'],folder)
            passed=True
            for op in spec['operations']:
                check=execute_command(broker,task,repo,folder,op,command(op,repo),deadline);check['attempt']=attempt+1;result['checks'].append(check)
                if check['returncode']!=0:passed=False;break
            if passed:break
            if attempt>=spec['retryLimit']:raise RuntimeError('Executable acceptance failed; bounded attempts exhausted.')
            if spec['type']=='patch' and attempt<len(spec['repairs']):patch(repo,spec['repairs'][attempt])
            elif spec['type']!='local-ai':raise Blocked('No authorized deterministic repair; review failure in Work.')
        if spec['type'] in ('patch','local-ai'):
            result['changedFiles']=changes(repo,spec['authorizedPaths'],folder);result['patchReadyForReview']=True
            result['artifacts'].append(str(folder/'changes.patch'))
        result['acceptance']='All approved executable checks passed. Prose criteria and scientific claims require human/Work review.';status='completed'
    except Cancelled as e:status='cancelled';error=str(e)
    except Blocked as e:status='blocked';error=str(e)
    except Exception as e:status='failed';error=type(e).__name__+': '+str(e)
    finally:
        if provider:
            provider.__exit__(None,None,None);result['modelInvocations']=result['modelCalls'];result['modelCalls']=provider.calls;result['localInferenceMetrics']=provider.metrics;result['providerStopped']=provider.child.poll() is not None
        if repo!=broker.repo:
            try:
                result['changedFiles']=changes(repo,spec['authorizedPaths'],folder)
                result['artifacts'].append(str(folder/'changes.patch'))
            except Exception as e:result['patchAuditError']=str(e);status='blocked';error='Patch audit requires review: '+str(e)
        result.update(status=status,error=error,finished=now(),wallSeconds=round(time.monotonic()-started,3),maximumObservedCommandRssMiB=max([json.loads(p.read_text())['peakProcessTreeRssMiB'] for p in folder.glob('monitor-*.json')] or [0]))
        if execution_lock:execution_lock.close()
        result['notification']=notify(broker,id,status)
        broker.finish(id,status,result,error);result['status']=broker.task(id)['status']
        (folder/'report.json').write_text(json.dumps(result,indent=2)+'\n')
        compact={k:result.get(k) for k in ['id','status','error','changedFiles','baseRevision','patchReadyForReview','modelCalls','wallSeconds','maximumObservedCommandRssMiB','workAllowanceUsed']};compact['checks']=[{k:c.get(k) for k in ['operation','attempt','returncode','diagnostic','successExcerpt']} for c in result['checks']];compact['report']=str(folder/'report.json');(folder/'summary.json').write_text(json.dumps(compact,indent=2)+'\n')
    return result

def serve(broker):
    global STOP
    lock=(broker.home/'daemon.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('A worker already owns the daemon lock.')
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:(globals().__setitem__('STOP',True),broker.wake()))
    fifo=broker.home/'wake'
    if not fifo.exists():os.mkfifo(fifo,0o600)
    if not __import__('stat').S_ISFIFO(fifo.lstat().st_mode):raise RuntimeError('Unsafe wake path; expected a private FIFO.')
    fd=os.open(fifo,os.O_RDWR|os.O_NONBLOCK);broker.recover();broker.set('daemon',{'pid':os.getpid(),'identity':proc(os.getpid()),'started':now()})
    try:
        while not STOP:
            broker.set('daemonHeartbeat',time.time())
            task=None if broker.setting('emergency',False) else broker.claim()
            if task:execute(broker,task);continue
            if select.select([fd],[],[],15)[0]:
                try:os.read(fd,4096)
                except BlockingIOError:pass
    finally:os.close(fd);broker.set('daemonStopped',now());lock.close()
