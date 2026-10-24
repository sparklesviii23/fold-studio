"""Readiness requires real isolated CUDA forward/gradient checks."""
import json
import os
import platform
import shutil
import subprocess
import csv

def inventory():
    if not shutil.which('nvidia-smi'):return {'detected':False,'reason':'NVIDIA driver tools unavailable','devices':[]}
    p=subprocess.run(['nvidia-smi','--query-gpu=index,name,uuid,driver_version,compute_cap,memory.total,memory.free','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=8)
    columns=['index','name','uuid','driverVersion','computeCapability','totalMemoryMiB','freeMemoryMiB'];devices=[]
    if p.returncode==0:
        for row in csv.reader(p.stdout.splitlines()):
            if len(row)!=len(columns):raise ValueError('Invalid NVIDIA capability inventory response.')
            device=dict(zip(columns,[v.strip() for v in row]));device['totalMemoryMiB']=float(device['totalMemoryMiB']);device['freeMemoryMiB']=float(device['freeMemoryMiB']);devices.append(device)
    return {'detected':bool(devices),'devices':devices,'cudaQualified':False}

def framework(engine):
    if engine in ('bindcraft2','proteinmpnn','af2_multimer'):return 'jax'
    if engine in ('boltzgen','solublempnn','esmfold2','esmfold2_fast','rfdiffusion'):return 'torch'
    raise ValueError('No CUDA numerical contract for this engine.')

NUMERICS="""import json
if cuda_framework=='jax':
 import jax,jax.numpy as j
 d=jax.devices('gpu');assert d
 y,g=jax.jit(jax.value_and_grad(lambda x:(x*x).sum()))(j.arange(1,10,dtype=j.float32));y.block_until_ready();g.block_until_ready();assert float(y)==285 and bool(j.array_equal(g,2*j.arange(1,10)))
 probe={'framework':'jax','version':jax.__version__,'device':str(d[0]),'forward':285,'gradientChecked':True}
else:
 import torch
 assert torch.cuda.is_available();x=torch.arange(1,10,device='cuda',dtype=torch.float32,requires_grad=True);y=(x*x).sum();y.backward();torch.cuda.synchronize();assert y.item()==285 and torch.equal(x.grad,2*x)
 probe={'framework':'torch','version':torch.__version__,'capability':list(torch.cuda.get_device_capability()),'device':torch.cuda.get_device_name(),'forward':285,'gradientChecked':True}
"""

def numerical_probe(engine):
    scope={'cuda_framework':framework(engine)}
    exec(NUMERICS,scope)
    return scope['probe']

def require_cuda(python,env,timeout=120,engine='bindcraft2'):
    if platform.system()!='Linux' or not inventory()['detected']:raise ValueError('Scientific execution requires a real Linux NVIDIA GPU; no CPU fallback.')
    code='cuda_framework='+repr(framework(engine))+'\n'+NUMERICS+'\nprint(json.dumps(probe))'
    result=subprocess.run([python,'-c',code],capture_output=True,text=True,timeout=timeout,env={**os.environ,**env,'JAX_PLATFORMS':'cuda','XLA_PYTHON_CLIENT_PREALLOCATE':'false'})
    if result.returncode:raise ValueError('CUDA numerical probe failed: '+result.stderr[-2000:])
    return json.loads(result.stdout.splitlines()[-1])
