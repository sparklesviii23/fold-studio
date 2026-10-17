"""Probe experimental Apple PJRT in an isolated process. Timeout/crash is evidence, not success."""
import argparse,json,os,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--python',required=True);p.add_argument('--output',required=True);args=p.parse_args()
code='''import jax,jax.numpy as j, json
print('JAX',jax.__version__,flush=True)
devices=jax.devices();print(devices,flush=True)
metal=[d for d in devices if d.platform.lower() in ('metal','gpu') and 'cpu' not in str(d).lower()]
if not metal:raise RuntimeError('No Metal device. CPU fallback is not a Metal test.')
x=jax.device_put(j.array([1.,2.,3.],dtype=j.float32),metal[0]);f=jax.jit(lambda v:j.sum(j.sin(v)*v))
y=f(x);g=jax.jit(jax.grad(f))(x);jax.block_until_ready(g)
print(json.dumps({'forward':float(y),'gradient':g.tolist(),'device':str(y.device)}))'''
report={'scope':'JAX Metal forward/gradient compatibility probe','attempts':[]}
for compat in ('0','1'):
 env={**os.environ,'JAX_PLATFORMS':'METAL','ENABLE_PJRT_COMPATIBILITY':compat,'XLA_PYTHON_CLIENT_PREALLOCATE':'false'}
 try:
  r=subprocess.run([args.python,'-c',code],capture_output=True,text=True,timeout=30,env=env)
  report['attempts'].append({'compatibilityFlag':compat,'state':'executed' if r.returncode==0 else 'failed','exitCode':r.returncode,'stdout':r.stdout[-8000:],'stderr':r.stderr[-8000:]})
 except subprocess.TimeoutExpired as e:report['attempts'].append({'compatibilityFlag':compat,'state':'timeout','error':str(e)})
report['state']='executed' if any(x['state']=='executed' for x in report['attempts']) else 'blocked'
pathlib.Path(args.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
