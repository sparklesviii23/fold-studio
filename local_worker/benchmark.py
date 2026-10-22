"""Small owned-fixture benchmarks; actual measurements, no invented Work savings."""
import hashlib,json,pathlib,subprocess,tempfile,time,uuid
from .core import Broker,admission,now,resources,run
from .daemon import execute

def benchmark(parent):
    root=parent.home/'benchmarks'/str(uuid.uuid4());repo=root/'fixture';repo.mkdir(parents=True);file=repo/'worker_fixture.txt';file.write_text('wrong\n');(repo/'worker_example.py').write_text('def add(a, b):\n    \"\"\"Return the sum of two numbers.\"\"\"\n    return a - b\n');(repo/'test_worker_fixture.py').write_text('import unittest\nfrom worker_example import add\nclass Addition(unittest.TestCase):\n def test_sum(self):\n  self.assertEqual(add(2, 3), 5)\n  self.assertEqual(add(-2, 3), 1)\n  self.assertEqual(add(0, 0), 0)\n')
    for args in [['init','-q'],['add','worker_fixture.txt','worker_example.py','test_worker_fixture.py'],['-c','user.name=Worker Benchmark','-c','user.email=worker@localhost','commit','-qm','Owned benchmark fixture']]:
        subprocess.run(['/usr/bin/git',*args],cwd=repo,check=True,capture_output=True)
    b=Broker(root/'broker',repo);b.set('notifications',False);b.set('localAI',parent.setting('localAI',{}));results=[]
    def task(name,**kw):
        spec={'schemaVersion':1,'type':'deterministic','instructions':name,'authorizedPaths':[],'acceptanceCriteria':['fixture-check exits 0'],'operations':['fixture-check'],'timeoutSeconds':30,'retryLimit':0,'resourceBudget':{'memoryMiB':256,'minAvailableMiB':1024,'maxLogMiB':1}};spec.update(kw)
        id=b.submit(spec)['id'];claimed=b.claim();r=execute(b,claimed);results.append({'category':name,'taskId':id,'status':r['status'],'error':r['error'],'seconds':r['wallSeconds'],'checks':[{'operation':c['operation'],'returncode':c['returncode']} for c in r['checks']],'peakProcessTreeRssMiB':r['maximumObservedCommandRssMiB'],'modelCalls':r['modelCalls'],'localInferenceMetrics':r.get('localInferenceMetrics',[]),'providerStopped':r.get('providerStopped'),'activeFixtureUnchanged':file.read_text()=='wrong\n','workInterventionsDuringExecution':None,'workerRequestedWorkTurns':0,'workAllowanceUsed':None});return spec
    task('deterministic operation',operations=['git-check'])
    patch={'path':'worker_fixture.txt','sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'before':'wrong\n','after':'correct\n'}
    task('routine exact edit; no AI',type='patch',authorizedPaths=['worker_fixture.txt'],patches=[patch])
    task('recoverable failure followed by one authorized correction',type='patch',authorizedPaths=['worker_fixture.txt'],retryLimit=1,repairs=[[patch]])
    s=task('medium complexity escalation',type='reasoning',operations=[])
    normal=resources(parent.repo);simulated={**normal,'telemetryError':None,'memoryPressureLevel':1,'estimatedAvailableMiB':20000,'scientificWorkloads':[{'simulated':True,'kind':'scientific memory demand; no real experiment launched'}]}
    s.update(type='deterministic',operations=['git-check']);reason=admission(s,simulated)
    results.append({'category':'safe simulated scientific contention','status':'passed' if reason else 'failed','reason':reason,'realScientificWorkloadLaunched':False})
    if parent.setting('localAI'):
        task('genuine local-AI coding in owned programming fixture',type='local-ai',authorizedPaths=['worker_example.py'],model='qwen2.5-coder:3b',instructions='Fix add(a, b) in worker_example.py so it returns the numeric sum for positive, negative and zero operands. Change only this file. Preserve its function signature and docstring. Do not modify tests or run commands.',operations=['coding-fixture-tests','git-check'],timeoutSeconds=180,retryLimit=1,maxModelCalls=2,maxContextBytes=48000,resourceBudget={'memoryMiB':4096,'minAvailableMiB':1024,'maxLogMiB':2})
    else:results.append({'category':'genuine local-AI coding','status':'not_run','reason':'No approved installed Aider/Ollama/model; exact-edit fixtures are not an AI coding benchmark.'})
    daemon=parent.setting('daemon',{});pid=daemon.get('pid');samples=[]
    if pid:
        for _ in range(4):
            ps=run(['/bin/ps','-p',str(pid),'-o','rss=,%cpu=,time='])
            if ps.stdout.strip():samples.append(ps.stdout.strip())
            time.sleep(2)
    report={'created':now(),'root':str(root),'categories':results,'idleWorkerSamples':samples,'idleSampleMethod':'four RSS KiB, recent CPU percent and cumulative CPU time observations, two seconds apart; only call while worker is idle','workAllowanceSavingsPercent':None,'baseline':'No matched historical per-task Work allowance telemetry. Account-wide percentages cannot attribute task cost.','cloudApiTokens':0,'localModelInferenceCalls':sum(r.get('modelCalls',0) for r in results),'measurementProtocol':{'design':'Prospective matched tasks with identical revision, acceptance checks and hardware conditions. Compare direct Work execution against one worker dispatch plus one report review. Alternate order and repeat.','record':['completion/pass rate','wall time','local peak RSS','Work interventions','Work tool calls','observable account window snapshots with concurrent-use caveats','local model/server timing and tokens where available'],'savingsRule':'Calculate only comparable directly observed quantities. Tool-call reductions or API tokens are not subscription allowance savings.'}}
    (root/'benchmark.json').write_text(json.dumps(report,indent=2)+'\n');b.db.close()
    return {**report,'report':str(root/'benchmark.json')}
