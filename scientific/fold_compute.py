"""FOLD COMPUTE: bounded, isolated resource probes; no implicit installation/upload."""
import json, os, pathlib, platform, subprocess, sys

PROBE = r'''
import importlib.metadata as md, importlib.util, json, platform, sys
out={'python':sys.version.split()[0], 'architecture':platform.machine(), 'versions':{}}
for name in ('jax','jaxlib','jax-metal','torch','dm-haiku','optax','biotite'):
    try: out['versions'][name]=md.version(name)
    except md.PackageNotFoundError: pass
if 'jax' in out['versions']:
    try:
        import jax
        out['jaxDevices']=[{'platform':d.platform,'kind':d.device_kind} for d in jax.devices()]
    except Exception as e: out['jaxError']=str(e)
if 'torch' in out['versions']:
    import torch
    out['mpsAvailable']=torch.backends.mps.is_available()
print(json.dumps(out))
'''

def probe(python, timeout=25):
    if not python or not pathlib.Path(python).is_file():
        return {'state':'unavailable','error':'No configured isolated runtime.'}
    env={**os.environ, 'XLA_PYTHON_CLIENT_PREALLOCATE':'false', 'PYTHONDONTWRITEBYTECODE':'1'}
    try:
        result=subprocess.run([str(python),'-B','-c',PROBE],capture_output=True,text=True,timeout=timeout,env=env)
        if result.returncode:
            return {'state':'failed','exitCode':result.returncode,'error':result.stderr[-6000:]}
        return {'state':'detected',**json.loads(result.stdout.splitlines()[-1])}
    except (OSError,ValueError,subprocess.TimeoutExpired) as e:
        return {'state':'failed','error':str(e)}

def diagnostic(service):
    # Development path supplied by launcher; never installed into another engine's env.
    runtime=os.environ.get('FOLD_BINDCRAFT_PYTHON')
    return {'name':'FOLD COMPUTE','schemaVersion':1,'host':{'architecture':platform.machine(),'macOS':platform.mac_ver()[0]},
            'bindcraftRuntime':probe(runtime), 'predictionRuntime':probe(service.engine_python()),
            'remote':{'enabled':False}, 'binderDesign':{'state':'experimental_cpu','metalState':'blocked','reason':'CPU single-model campaigns execute upstream algorithms; complete scientific/modalities acceptance is still in progress. JAX Metal remains incompatible.'},
            'metalAttention':{'state':'experimental','scope':'One float32 attention kernel; run validate-metal-attention.py for measured forward/gradient parity.'}}
