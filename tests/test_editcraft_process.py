"""Real harmless process-group cleanup, no scientific computations."""
import os,pathlib,signal,subprocess,sys,time,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'remote_worker'))
from fold_rapid.editcraft_process import terminate_owned_group
@unittest.skipUnless(os.name=='posix','POSIX scientific worker process groups')
class ProcessTests(unittest.TestCase):
 def test_running_worker_is_reaped(self):
  child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],start_new_session=True)
  terminate_owned_group(child,grace_seconds=.1);self.assertIsNotNone(child.poll())
 def test_exited_leader_cannot_leave_term_ignoring_scientific_child(self):
  code="import os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); print(os.getpid(),flush=True); time.sleep(30)"
  parent="import subprocess,sys; p=subprocess.Popen([sys.executable,'-u','-c',"+repr(code)+"],stdout=subprocess.PIPE,text=True); print(p.stdout.readline().strip(),flush=True)"
  child=subprocess.Popen([sys.executable,'-u','-c',parent],start_new_session=True,stdout=subprocess.PIPE,text=True);grandchild=int(child.stdout.readline());child.wait(timeout=5)
  try:
   terminate_owned_group(child,grace_seconds=.1);deadline=time.monotonic()+2
   while time.monotonic()<deadline:
    state=subprocess.run(['/bin/ps','-p',str(grandchild),'-o','stat='],capture_output=True,text=True).stdout.strip()
    if not state or state.startswith('Z'):break
    time.sleep(.025)
   self.assertTrue(not state or state.startswith('Z'),'Owned grandchild is still running after group teardown.')
  finally:
   child.stdout.close()
   try:os.kill(grandchild,signal.SIGKILL)
   except ProcessLookupError:pass
