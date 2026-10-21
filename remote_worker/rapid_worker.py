"""Fold Studio RAPID worker protocol v1. Transport: authenticated SSH stdin.

No public network listener, automatic installs, model downloads or CPU fallback.
The foundation reports engine execution unavailable until separately validated.
"""
import csv, hashlib, importlib.metadata, json, math, os, pathlib, platform
import shutil, subprocess, sys, time
API_VERSION = 1
WORKER_VERSION = '0.1.0'
MAX_REQUEST = 65536
OPERATIONS = {'health', 'gpu_selftest', 'engine_inventory'}

def package_version(name):
    try: return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: return None

def gpu_inventory():
    executable = shutil.which('nvidia-smi')
    if not executable: return {'state':'unavailable','devices':[],'reason':'NVIDIA driver tools are not installed.'}
    columns = ['index','uuid','name','driver_version','memory.total','memory.free','utilization.gpu','temperature.gpu','power.draw']
    result = subprocess.run([executable,'--query-gpu='+','.join(columns),'--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=12)
    if result.returncode: return {'state':'unavailable','devices':[],'reason':'The NVIDIA driver could not access a GPU.'}
    devices=[]
    for row in csv.reader(result.stdout.splitlines()):
        if len(row)!=len(columns): raise ValueError('Invalid NVIDIA inventory response.')
        device = dict(zip(columns,[v.strip() for v in row]))
        for key in columns[4:]:
            try: device[key]=float(device[key])
            except ValueError: device[key]=None
        devices.append(device)
    return {'state':'detected' if devices else 'unavailable','devices':devices,'numericalSelftestRequired':True}

def engine_inventory():
    # Import detection is not a scientific execution certificate. Environment
    # installation/execution are separate, future worker capabilities.
    return {'engines':[
        {'id':'bindcraft2','name':'BindCraft2','status':'not_installed','cudaExecutionTested':False,'scientificReferenceValidated':False,'reason':'A pinned isolated scientific environment and reference run are required.'},
        {'id':'boltzgen','name':'BoltzGen','status':'not_installed','cudaExecutionTested':False,'scientificReferenceValidated':False},
        {'id':'proteinmpnn','name':'ProteinMPNN / SolubleMPNN','status':'not_installed','cudaExecutionTested':False,'scientificReferenceValidated':False},
        {'id':'independent_complex','name':'Independent complex evaluation','status':'not_configured','cudaExecutionTested':False,'scientificReferenceValidated':False}],
        'campaignSubmissionAvailable':False}

def health():
    disk=shutil.disk_usage(pathlib.Path.home())
    try: ram=os.sysconf('SC_PHYS_PAGES')*os.sysconf('SC_PAGE_SIZE')
    except (ValueError,OSError): ram=None
    return {'state':'worker_available','apiVersion':API_VERSION,'workerVersion':WORKER_VERSION,
        'workerSha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
        'platform':platform.system(),'architecture':platform.machine(),'python':platform.python_version(),
        'systemRamBytes':ram,'diskFreeBytes':disk.free,'gpu':gpu_inventory(),
        'packages':{p:package_version(p) for p in ('torch','jax','jaxlib')},
        'ready':False,'readinessReason':'Run real CUDA numerical checks, then install and validate a scientific engine.',
        'transport':'SSH-authenticated versioned stdin protocol; no public HTTP port',**engine_inventory()}

PROBES = {
 'torch': """import json,torch
assert torch.cuda.is_available(),'CUDA device unavailable'
d=torch.device('cuda:0');x=torch.arange(1,10,device=d,dtype=torch.float32).reshape(3,3).requires_grad_()
y=(x*x).sum();y.backward();torch.cuda.synchronize()
assert y.item()==285.0 and torch.equal(x.grad,2*x)
p=torch.cuda.get_device_properties(0)
print(json.dumps({'state':'passed','framework':'torch','version':torch.__version__,'cudaRuntime':torch.version.cuda,'device':p.name,'computeCapability':list(torch.cuda.get_device_capability(0)),'totalMemoryBytes':p.total_memory,'forwardValue':y.item(),'gradientChecked':True,'peakAllocatedBytes':torch.cuda.max_memory_allocated(0)}))
""",
 'jax': """import json,jax,jax.numpy as jnp
from jax.extend import backend
devices=jax.devices('gpu');assert devices,'CUDA device unavailable'
with jax.default_device(devices[0]):
 x=jnp.arange(1,10,dtype=jnp.float32).reshape(3,3)
 y,g=jax.jit(jax.value_and_grad(lambda a:jnp.square(a).sum()))(x)
 y.block_until_ready();g.block_until_ready()
 assert float(y)==285.0 and bool(jnp.array_equal(g,2*x))
print(json.dumps({'state':'passed','framework':'jax','version':jax.__version__,'device':str(devices[0]),'platformVersion':backend.get_backend('gpu').platform_version,'forwardValue':float(y),'gradientChecked':True}))
"""}

def gpu_selftest():
    inventory=gpu_inventory()
    if platform.system()!='Linux' or inventory['state']!='detected':
        return {'state':'blocked','ready':False,'reason':'A Linux NVIDIA CUDA worker is required; no CPU fallback was executed.','gpu':inventory,'frameworks':[]}
    results=[]
    for framework,code in PROBES.items():
        try:
            # Separate processes release each framework's CUDA context before
            # the next one. Never load model checkpoints in these tiny probes.
            result=subprocess.run([sys.executable,'-I','-B','-c',code],capture_output=True,text=True,timeout=90,
                env={**os.environ,'JAX_PLATFORMS':'cuda','XLA_PYTHON_CLIENT_PREALLOCATE':'false'})
            if result.returncode: raise ValueError('CUDA forward/gradient probe did not pass.')
            probe=json.loads(result.stdout.splitlines()[-1]);assert probe['state']=='passed'
            results.append(probe)
        except (ValueError,AssertionError,IndexError,subprocess.TimeoutExpired):
            results.append({'state':'failed','framework':framework,'reason':'CUDA import, allocation, forward or gradient validation failed. Verify the isolated environment and driver.'})
    passed=all(r['state']=='passed' for r in results)
    return {'state':'numerically_verified' if passed else 'blocked','ready':False,
        'cudaNumericsPassed':passed,'frameworks':results,'gpu':inventory,
        'reason':'Scientific engines still require pinned installation and reference validation.' if passed else 'At least one required CUDA framework failed; CPU fallback is disabled.'}

def dispatch(request):
    if not isinstance(request,dict) or set(request)-{'apiVersion','requestId','operation','payload'}: raise ValueError('Invalid request fields.')
    if type(request.get('apiVersion')) is not int or request.get('apiVersion')!=API_VERSION: raise ValueError('Unsupported worker API version.')
    if not isinstance(request.get('requestId'),str) or not 1<=len(request['requestId'])<=80: raise ValueError('Invalid request ID.')
    if request.get('operation') not in OPERATIONS: raise ValueError('Unsupported worker operation; campaign execution is not yet installed.')
    if request.get('payload',{})!={}: raise ValueError('This operation takes no arguments.')
    started=time.monotonic()
    operation={'health':health,'gpu_selftest':gpu_selftest,'engine_inventory':engine_inventory}[request['operation']]
    return {'apiVersion':API_VERSION,'requestId':request['requestId'],'result':operation(),'wallSeconds':time.monotonic()-started}

def main():
    try:
        raw=sys.stdin.buffer.read(MAX_REQUEST+1)
        if len(raw)>MAX_REQUEST: raise ValueError('Worker request exceeds limit.')
        result=dispatch(json.loads(raw))
    except Exception as error:
        # Unexpected exception text can include environment paths or secrets.
        result={'apiVersion':API_VERSION,'error':str(error) if isinstance(error,ValueError) else 'Worker operation failed; inspect the verified environment.','errorType':type(error).__name__}
    print(json.dumps(result,allow_nan=False))
if __name__=='__main__': main()
