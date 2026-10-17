#!/usr/bin/env python3
"""Compare upstream JAX attention/gradients with FOLD PyTorch CPU and real MPS.
Run in isolated JAX env; --torch-python points to a separate installed torch env.
No model weights, research data, or external services are used.
"""
import argparse, importlib.util, json, os, pathlib, subprocess, sys, tempfile, time
os.environ['JAX_PLATFORMS']='cpu'
import jax, jax.numpy as jnp, numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--torch-python',required=True);p.add_argument('--output',required=True);args=p.parse_args()
sys.path.insert(0,str(ROOT/'scientific'))
from fold_engine import verify_source
source=verify_source()
spec=importlib.util.spec_from_file_location('bindcraft_upstream_attention',ROOT/'vendor/bindcraft2/bindcraft/af/accel.py');upstream=importlib.util.module_from_spec(spec);spec.loader.exec_module(upstream)
TORCH_RUN=r'''
import json, numpy as np, pathlib, sys, time, torch
sys.path.insert(0,sys.argv[1]);from metal_attention import attend
raw=np.load(sys.argv[2],allow_pickle=False);out={};report={}
for device in ('cpu','mps'):
 if device=='mps' and not torch.backends.mps.is_available():
  report[device]={'state':'unavailable'};continue
 for chunk in (0,3):
  values=[torch.tensor(raw[n],device=device,requires_grad=True) for n in ('q','k','v','bias','nonbatched')]
  start=time.perf_counter();result=attend(*values,chunk_size=chunk);loss=(result*torch.tensor(raw['cotangent'],device=device)).sum();grads=torch.autograd.grad(loss,values)
  if device=='mps':torch.mps.synchronize()
  prefix=device+str(chunk);out[prefix+'_output']=result.detach().cpu().numpy()
  for i,g in enumerate(grads):out[prefix+'_grad'+str(i)]=g.detach().cpu().numpy()
  report[prefix]={'state':'executed','seconds':time.perf_counter()-start,'device':str(result.device)}
np.savez(sys.argv[3],**out)
print(json.dumps({'torch':torch.__version__,'runs':report}))
'''
report={'scope':'Attention kernel only, not AlphaFold/campaign validation','upstream':source,'jax':jax.__version__,'jaxDevices':[str(d) for d in jax.devices()],'dtype':'float32','atol':3e-5,'rtol':3e-4,'cases':[]}
with tempfile.TemporaryDirectory() as folder:
 folder=pathlib.Path(folder);rng=np.random.default_rng(2718)
 for name,batch,queries,keys,heads,dim in [('odd_lengths',2,7,9,2,4),('masked_row',1,5,6,1,8),('broadcast_bias',1,8,8,2,4)]:
  shapes=[(batch,queries,heads,dim),(batch,keys,heads,dim),(batch,keys,heads,dim),(batch,heads,1 if name=='broadcast_bias' else queries,keys),(heads,queries,keys)]
  arrays=[rng.normal(0,.2,s).astype(np.float32) for s in shapes]
  if name=='masked_row':arrays[3][:,:,2,:]=-1e9
  cot=rng.normal(0,.2,(batch,queries,heads,dim)).astype(np.float32)
  def loss(*a):return jnp.sum(upstream.attend(*a,backend='stock')*cot)
  start=time.perf_counter();forward=jax.jit(lambda *a:upstream.attend(*a,backend='stock'))(*arrays);grads=jax.jit(jax.grad(loss,argnums=(0,1,2,3,4)))(*arrays);jax.block_until_ready(grads);seconds=time.perf_counter()-start
  # Also check actual upstream chunking/checkpoint backward before cross-backend comparison.
  chunked=jax.jit(lambda *a:upstream.attend(*a,backend='chunked',chunk_size=3))(*arrays)
  cgrads=jax.jit(jax.grad(lambda *a:jnp.sum(upstream.attend(*a,backend='chunked',chunk_size=3)*cot),argnums=(0,1,2,3,4)))(*arrays)
  for a,b in zip([forward,*grads],[chunked,*cgrads]):np.testing.assert_allclose(a,b,atol=3e-5,rtol=3e-4)
  np.savez(folder/'inputs.npz',**dict(zip(('q','k','v','bias','nonbatched'),arrays)),cotangent=cot)
  proc=subprocess.run([args.torch_python,'-c',TORCH_RUN,str(ROOT/'scientific'),str(folder/'inputs.npz'),str(folder/'torch.npz')],text=True,capture_output=True,timeout=60,env={**os.environ,'PYTORCH_ENABLE_MPS_FALLBACK':'0'})
  if proc.returncode:raise RuntimeError(proc.stderr)
  runtime=json.loads(proc.stdout.strip().splitlines()[-1]);values=np.load(folder/'torch.npz',allow_pickle=False);errors={}
  for prefix,run in runtime['runs'].items():
   if run['state']!='executed':continue
   compared=[values[prefix+'_output']]+[values[prefix+'_grad'+str(i)] for i in range(5)]
   errors[prefix]=[]
   for actual,expected in zip(compared,[forward,*grads]):
    np.testing.assert_allclose(actual,np.asarray(expected),atol=3e-5,rtol=3e-4)
    errors[prefix].append(float(np.max(np.abs(actual-np.asarray(expected)))))
  report['cases'].append({'name':name,'shape':shapes,'upstreamSeconds':seconds,'runtime':runtime,'maxAbsErrorsOutputThenQKVBiasNonbatchedGrad':errors})
report['state']='passed';pathlib.Path(args.output).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
