"""Teardown of a scientific group created with start_new_session=True."""
import os,signal,subprocess,time
def terminate_owned_group(child,grace_seconds=5):
 def exists():
  child.poll() # Reap an exited leader before probing a possibly dead group.
  try:os.killpg(child.pid,0);return True
  except ProcessLookupError:return False
 if not exists():child.wait();return
 try:os.killpg(child.pid,signal.SIGTERM)
 except ProcessLookupError:pass
 deadline=time.monotonic()+grace_seconds
 while exists() and time.monotonic()<deadline:
  child.poll();time.sleep(.025)
 if exists():
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 child.wait()
