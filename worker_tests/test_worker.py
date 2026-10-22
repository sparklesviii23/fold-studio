"""Broker races, actual sandbox boundaries, bounded repair, cancellation and isolation."""
import threading
import concurrent.futures, hashlib, json, os, pathlib, sqlite3, subprocess, sys, tempfile, time, unittest
from unittest.mock import patch as mock
from local_worker.core import Broker, REPO, validate, admission, digest
from local_worker.daemon import execute
from local_worker.executor import sandbox, scoped, patch, Blocked, ollama_request

NORMAL={'memoryPressureLevel':1,'estimatedAvailableMiB':20000,'scientificWorkloads':[],'telemetryError':None}
def spec(**kw):
    d={'schemaVersion':1,'type':'deterministic','instructions':'Bounded test','authorizedPaths':[],'acceptanceCriteria':['Approved check exits zero'],'operations':['fixture-check'],'timeoutSeconds':20,'retryLimit':0,'resourceBudget':{'memoryMiB':256,'minAvailableMiB':1024,'maxLogMiB':1}};d.update(kw);return d

class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.repo=self.root/'repo';self.repo.mkdir();self.file=self.repo/'worker_fixture.txt';self.file.write_text('wrong\n')
        for args in [['init','-q'],['add','worker_fixture.txt'],['-c','user.name=Worker Test','-c','user.email=worker@localhost','commit','-qm','fixture']]:
            subprocess.run(['/usr/bin/git',*args],cwd=self.repo,check=True,capture_output=True)
        self.b=Broker(self.root/'state',self.repo,resource_domain=self.root/'governor');self.b.set('notifications',False)
    def tearDown(self):self.b.db.close();self.tmp.cleanup()
    def dispatch(self,s):
        id=self.b.submit(s)['id'];return self.b.claim()
    def execute(self,s):
        task=self.dispatch(s)
        with mock('local_worker.daemon.resources',return_value=NORMAL):return execute(self.b,task)
    def test_concurrent_claim_is_atomic(self):
        id=self.b.submit(spec())['id']
        def claim(_):
            b=Broker(self.b.home,self.repo)
            try:r=b.claim();return r['id'] if r else None
            finally:b.db.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:claims=list(pool.map(claim,range(6)))
        self.assertEqual(claims.count(id),1)
    def test_crash_recovery_blocks_and_explicit_resume_survives_restart(self):
        task=self.dispatch(spec());self.b.recover();self.assertEqual(self.b.task(task['id'])['status'],'blocked');self.b.resume(task['id']);self.assertEqual(self.b.task(task['id'])['status'],'queued')
        other=Broker(self.b.home,self.repo);self.assertEqual(other.task(task['id'])['status'],'queued');other.db.close()
    def test_terminal_cancel_does_not_reexecute(self):
        id=self.b.submit(spec())['id'];self.b.cancel(id);self.assertIsNone(self.b.claim());self.assertEqual(self.b.task(id)['status'],'cancelled')
    def test_capabilities_reject_shell_unknown_fields_and_traversal(self):
        for kwargs in [{'operations':['rm -rf /']},{'authorizedPaths':['../secret']},{'authorizedPaths':['.git/config']},{'authorizedPaths':['.env.local']},{'command':'whoami'},{'retryLimit':20},{'resourceBudget':{'memoryMiB':-1}}]:
            with self.assertRaises((ValueError,TypeError)):validate(spec(**kwargs),self.repo)
    def test_symlink_escape_is_refused(self):
        (self.repo/'link').symlink_to(self.root)
        with self.assertRaises(ValueError):scoped(self.repo,'link/secret')
    def test_patch_checksum_mismatch_changes_nothing(self):
        with self.assertRaises(Blocked):patch(self.repo,[{'path':'worker_fixture.txt','sha256':'0'*64,'before':'wrong','after':'correct'}])
        self.assertEqual(self.file.read_text(),'wrong\n')
    def test_scientific_contention_and_pressure_yield_without_termination(self):
        s=validate(spec(),self.repo)
        for snapshot in [{**NORMAL,'scientificWorkloads':[{'pid':123}]},{**NORMAL,'memoryPressureLevel':4},{**NORMAL,'estimatedAvailableMiB':10}]:self.assertTrue(admission(s,snapshot))
        self.assertIsNone(admission(s,NORMAL))
    def test_reasoning_and_sensitive_ai_escalate(self):
        self.assertIn('Tier 3',admission(validate(spec(type='reasoning',operations=[]),self.repo),NORMAL))
        s=validate(spec(type='local-ai',authorizedPaths=['scientific/metal.py'],model='local:test'),self.repo);self.assertIn('Tier 3',admission(s,NORMAL))
    def test_actual_sandbox_denies_personal_file_write_and_network(self):
        secret=self.root/'personal-secret';secret.write_text('private');folder=self.root/'job';folder.mkdir()
        code='import pathlib,socket; p=pathlib.Path('+repr(str(secret))+'); denied=0\ntry:p.read_text()\nexcept PermissionError:denied+=1\ntry:p.write_text("bad")\nexcept PermissionError:denied+=1\ntry:socket.create_connection(("1.1.1.1",443),timeout=1)\nexcept OSError:denied+=1\nassert denied==3,denied\nprint("all three boundaries enforced")'
        from local_worker.executor import PYTHON
        p=subprocess.run(['/usr/bin/sandbox-exec','-p',sandbox(self.repo,folder),str(PYTHON),'-B','-c',code],cwd=self.repo,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(secret.read_text(),'private')
    def test_exact_repair_runs_in_worktree_leaves_active_source_unchanged(self):
        repair={'path':'worker_fixture.txt','sha256':digest(self.file),'before':'wrong\n','after':'correct\n'}
        r=self.execute(spec(type='patch',authorizedPaths=['worker_fixture.txt'],retryLimit=1,repairs=[[repair]]))
        self.assertEqual(r['status'],'completed',r);self.assertEqual([x['returncode'] for x in r['checks']],[1,0]);self.assertEqual(self.file.read_text(),'wrong\n');self.assertEqual(r['changedFiles'],['worker_fixture.txt']);self.assertTrue(pathlib.Path(r['worktree']).joinpath('worker_fixture.txt').read_text()=='correct\n')
    def test_failed_check_is_not_reported_as_pass(self):
        r=self.execute(spec());self.assertEqual(r['status'],'failed');self.assertNotEqual(r['checks'][0]['returncode'],0)
    def test_dirty_source_is_preserved_and_blocked(self):
        self.file.write_text('user edit\n');r=self.execute(spec(type='patch',authorizedPaths=['worker_fixture.txt']));self.assertEqual(r['status'],'blocked');self.assertEqual(self.file.read_text(),'user edit\n')
    def test_cancel_before_command_prevents_owned_execution(self):
        task=self.dispatch(spec());self.b.cancel(task['id'])
        with mock('local_worker.daemon.resources',return_value=NORMAL):r=execute(self.b,task)
        self.assertEqual(self.b.task(task['id'])['status'],'cancelled')
    def test_model_missing_is_blocked_without_network_fallback(self):
        r=self.execute(spec(type='local-ai',authorizedPaths=['worker_fixture.txt'],model='not-installed:test'));self.assertEqual(r['status'],'blocked');self.assertEqual(r['modelCalls'],0);self.assertEqual(self.file.read_text(),'wrong\n')

    def test_timeout_stops_only_owned_child(self):
        from local_worker.executor import PYTHON
        with mock('local_worker.daemon.command',return_value=[str(PYTHON),'-B','-c','import time; time.sleep(20)']):
            r=self.execute(spec(timeoutSeconds=1))
        self.assertEqual(r['status'],'failed');self.assertIn('TimeoutError',r['error']);self.assertLess(r['wallSeconds'],5)
    def test_live_cancellation_is_persistent(self):
        from local_worker.executor import PYTHON
        task=self.dispatch(spec())
        def cancel():
            b=Broker(self.b.home,self.repo);b.cancel(task['id']);b.db.close()
        timer=threading.Timer(.3,cancel);timer.start()
        with mock('local_worker.daemon.command',return_value=[str(PYTHON),'-B','-c','import time;time.sleep(20)']),mock('local_worker.daemon.resources',return_value=NORMAL):r=execute(self.b,task)
        timer.join();self.assertEqual(r['status'],'cancelled');self.assertLess(r['wallSeconds'],5)

    def test_global_resource_slot_prevents_competing_execution(self):
        import fcntl
        lock=(self.b.resource_domain/'execution.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            r=self.execute(spec());self.assertEqual(r['status'],'blocked');self.assertIn('global resource slot',r['error']);self.assertEqual(r['checks'],[])
        finally:lock.close()
    def test_remote_models_are_rejected_before_provider_launch(self):
        from local_worker.provider import LocalProvider
        folder=self.root/'provider';folder.mkdir();store=self.root/'models';store.mkdir()
        self.b.set('localAI',{'aider':'/usr/bin/true','ollama':'/usr/bin/true','modelStore':str(store)})
        with self.assertRaises(Blocked):LocalProvider(self.b,{'model':'qwen:cloud'},folder).__enter__()

if __name__=='__main__':unittest.main()
