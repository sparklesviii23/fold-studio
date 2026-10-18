"""Explicit, version-pinned experimental Metal runtime. Never falls back to CPU."""
import json,os,pathlib,subprocess

# Governor remains enabled. Small numerical checks used 4 GiB; the 175-residue
# campaign repeatedly stalled at that cap. A bounded 6 GiB profile is under
# full-campaign validation on this 24 GiB host, not a large-system guarantee.
ENV={'JAX_PLATFORMS':'metal','METALJAX_MEM_GOVERNOR':'1','METALJAX_MEM_BUDGET_MB':'6144','METALJAX_MEM_SYS_MB':'23552','METALJAX_LOOP_INFLIGHT_MB':'128','METALJAX_MATMUL_PRECISION':'highest','XLA_PYTHON_CLIENT_PREALLOCATE':'false','PYTHONDONTWRITEBYTECODE':'1'}
PINS={'jax':'0.11.2','jaxlib':'0.11.2','metaljax':'0.11.9'}

def runtime(service):
 import fold_engine as fe
 return os.path.abspath(os.path.expanduser(os.environ.get('FOLD_BINDCRAFT_METAL_PYTHON') or service.setting('bindcraftMetalPython') or str(fe.BASE/'runtime-metal/bin/python3.12')))

def probe(service):
 python=runtime(service)
 if not pathlib.Path(python).is_file():return {'state':'unavailable','error':'Experimental Metal runtime is not installed. CPU remains available.'}
 script="import json,importlib.metadata as md,jax,platform,subprocess;print(json.dumps({'versions':{n:md.version(n) for n in ('jax','jaxlib','metaljax')},'architecture':platform.machine(),'memoryBytes':int(subprocess.check_output(['/usr/sbin/sysctl','-n','hw.memsize'])),'devices':[{'platform':d.platform,'kind':d.device_kind} for d in jax.devices()]}))"
 try:
  result=subprocess.run([python,'-B','-c',script],capture_output=True,text=True,env={**os.environ,**ENV},timeout=25)
  if result.returncode:return {'state':'failed','error':result.stderr[-4000:]}
  info=json.loads(result.stdout.splitlines()[-1])
  if info['versions']!=PINS:raise ValueError('Experimental Metal package versions differ from validated pins.')
  if info['architecture']!='arm64' or info['memoryBytes']<24*1024**3:raise ValueError('This bounded experimental Metal profile currently requires Apple Silicon with at least 24 GiB unified memory.')
  if not info['devices'] or any(d['platform'].lower()!='metal' for d in info['devices']):raise ValueError('No actual Metal device; CPU fallback refused.')
  return {'state':'experimental','runtime':python,**info,'precision':'float32','environment':ENV}
 except (OSError,ValueError,KeyError,subprocess.TimeoutExpired) as error:return {'state':'failed','error':str(error)}
