"""Executable NVIDIA qualification gate. Default is NOT RUN, never fake success.

Execute inside the deployed worker with approved, private scientific manifests.
No asset download, provider operation, fake candidate or threshold weakening.
"""
import argparse,json,os,pathlib,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1];CORE=ROOT/('remote_worker' if (ROOT/'remote_worker').is_dir() else 'worker');sys.path.insert(0,str(CORE))
from fold_rapid.api import Worker
from fold_rapid.contracts import digest
from fold_rapid.hardware import inventory,require_cuda
from fold_rapid.registry import config,verified_runtime
from fold_rapid.store import TERMINAL
p=argparse.ArgumentParser();p.add_argument('--root',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--execute',action='store_true');p.add_argument('--bindcraft-manifest',type=pathlib.Path);p.add_argument('--boltzgen-manifest',type=pathlib.Path);p.add_argument('--complex-manifest',type=pathlib.Path);a=p.parse_args()
names=['gpu_inventory','jax_cuda_forward_gradient','torch_cuda_forward_gradient','esmfold2_cuda','checkpoint_hashes','trained_cpu_cuda_parity','bindcraft2_original_trajectory','proteinmpnn','heldout_af2_multimer','boltzgen_complete_pipeline','end_to_end_result_recovery']
report={'state':'NOT RUN','cudaQualified':False,'tests':{n:{'state':'NOT RUN'} for n in names},'scope':'Scoped hardware qualification. Does not resolve the documented independent continuous-trajectory drift limitation.'}
a.output.parent.mkdir(parents=True,exist_ok=True)
def save():a.output.write_text(json.dumps(report,indent=2)+'\n')
def run_job(name,manifest):
    worker=Worker(a.root);value=worker.job_submit({'manifest':manifest,'idempotencyKey':'qualification-'+name+'-'+digest(json.dumps(manifest,sort_keys=True).encode()),'approvedResearchTransfer':True});id=value['jobId']
    expires=time.monotonic()+manifest['budget']['seconds']+180
    while time.monotonic()<expires:
        state=worker.job_status({'jobId':id})
        if state['state'] in TERMINAL:break
        time.sleep(2)
    else:worker.job_cancel({'jobId':id});raise ValueError('Qualification supervisor timed out; cancellation requested.')
    if state['state'] not in ('completed','no_qualified_candidates'):raise ValueError(name+': '+str(state.get('error') or state['state']))
    report['tests'][name]={'state':'passed','jobId':id,'scientificOutcome':state['state'],'result':state['result']};save()
    artifacts=worker.artifact_list({'jobId':id})['artifacts']
    if not any(v['path']=='results.zip' for v in artifacts):raise ValueError('Result package missing.')
    return id
save()
if not a.execute:print(json.dumps(report));raise SystemExit(0)
try:
    if not inventory()['detected']:raise ValueError('Real Linux NVIDIA GPU is required; no qualification executed.')
    report['tests']['gpu_inventory']={'state':'passed','inventory':inventory()};save()
    for engine,test in [('bindcraft2','jax_cuda_forward_gradient'),('boltzgen','torch_cuda_forward_gradient')]:
        runtime,models=verified_runtime(a.root,engine);probe=require_cuda(runtime['python'],{})
        report['tests'][test]={'state':'passed','actual':probe}
    esm=config(a.root)['runtimes']['esmfold2'];report['tests']['esmfold2_cuda']={'state':'passed','actual':require_cuda(esm['python'],{})}
    report['tests']['checkpoint_hashes']={'state':'passed','scope':'All selected source/weight files hashed by verified_runtime.'};save()
    runtime,models=verified_runtime(a.root,'bindcraft2');output=a.output.parent/'numeric';output.mkdir(exist_ok=True)
    env={**os.environ,'PYTHONPATH':os.pathsep.join([runtime['source'],str(CORE)])}
    for backend in ('cpu','cuda'):
        subprocess.run([runtime['python'],'-m','fold_rapid.numeric_probe','--parameters',str(pathlib.Path(models['model_1_multimer_v3']['path']).parent),'--backend',backend,'--output',str(output/(backend+'.npz'))],check=True,env=env,timeout=1200)
    compare="import json,numpy as n,sys;a=n.load(sys.argv[1],allow_pickle=False);b=n.load(sys.argv[2],allow_pickle=False);assert set(a.files)==set(b.files);r={k:bool(n.allclose(a[k],b[k],rtol=1e-4,atol=1e-5)) for k in a.files};print(json.dumps(r));assert all(r.values())"
    values=json.loads(subprocess.check_output([runtime['python'],'-c',compare,str(output/'cpu.npz'),str(output/'cuda.npz')],text=True))
    report['tests']['trained_cpu_cuda_parity']={'state':'passed','arrays':values,'rtol':1e-4,'atol':1e-5};save()
    if not all((a.bindcraft_manifest,a.boltzgen_manifest,a.complex_manifest)):raise ValueError('Supply genuine private BindCraft, BoltzGen and bound-complex fixture manifests; unexecuted stages remain NOT RUN.')
    run_job('bindcraft2_original_trajectory',json.loads(a.bindcraft_manifest.read_text()))
    complex_manifest=json.loads(a.complex_manifest.read_text())
    for engine,name,operation in [('proteinmpnn','proteinmpnn','redesign'),('af2_multimer','heldout_af2_multimer','evaluate')]:
        manifest={**complex_manifest,'engine':engine,'operation':operation};run_job(name,manifest)
    run_job('boltzgen_complete_pipeline',json.loads(a.boltzgen_manifest.read_text()))
    report['tests']['end_to_end_result_recovery']={'state':'NOT RUN','reason':'Run scripts/validate-rapid-container.py equivalent against the real server and verify native result import. Local job packages alone do not prove Mac transfer.'}
    report['state']='partially_verified';save()
except Exception as error:report['state']='blocked_or_failed';report['error']=str(error);save();print(json.dumps(report));raise SystemExit(1)
print(json.dumps(report))
