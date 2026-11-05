"""Detached, read-only scientific preparation/checks with existing run records."""
import argparse,json,os,subprocess,sys,time,uuid
from pathlib import Path
sys.dont_write_bytecode=True
REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO/'scientific'))
import gpu_tasks as G
from types import SimpleNamespace
p=argparse.ArgumentParser();p.add_argument('--library',required=True);p.add_argument('--kind',choices=['tests','response']);p.add_argument('--source-run');p.add_argument('--child');a=p.parse_args();root=Path(a.library).resolve();service=SimpleNamespace(root=root)
if not a.child:
 if not a.kind:p.error('--kind required')
 rec={'id':uuid.uuid4().hex,'provider':'local','recipe':'predictive_'+a.kind,'kind':a.kind,'sourceRun':a.source_run,'title':'Predictive biology · '+('scientific regression checks' if a.kind=='tests' else 'stronger response benchmark'),'state':'local_running','created':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'gpu':None,'phase':'Running locally; no cloud allocation','projectId':'fef08806-d3ac-4846-8143-60a76b8c1e63'}
 G._write(service,rec);folder=G._folder(service)/rec['id']
 with (folder/'stdout.txt').open('w') as log:
  proc=subprocess.Popen([sys.executable,'-B',__file__,'--library',str(root),'--child',rec['id']],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1'))
 print(json.dumps({'jobId':rec['id'],'pid':proc.pid}));sys.exit(0)
rec=G._read(service,a.child);rec['launched']=time.time();G._write(service,rec);folder=G._folder(service)/rec['id'];code=0
try:
 if rec['kind']=='tests':
  for pattern in ['test_virtual_cell*.py','test_predictive_stage2.py','test_biological_models.py','test_gpu_tasks.py','test_gpu_run_controller.py','test_borzoi_reference.py','test_response_comparison.py']:
   print('[fold] checking '+pattern,flush=True)
   r=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','tests','-p',pattern,'-q'],cwd=REPO)
   if r.returncode:code=r.returncode
 elif rec['kind']=='response':
  import virtual_cell_response_research as R
  report,arrays=R.evaluate(root,rec['sourceRun']); import virtual_cell_benchmarks as B
  saved=B.save(root,report,arrays);(folder/'outputs').mkdir(exist_ok=True); (folder/'outputs/benchmark-result.json').write_text(json.dumps(saved,indent=1,allow_nan=False))
  print('[fold] response benchmark saved '+saved['id'],flush=True)
except Exception as error:
 import traceback;traceback.print_exc();code=1;rec['error']=str(error)
if (folder/'outputs').exists():
 import hashlib
 rec['outputs']=[{'path':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (folder/'outputs').iterdir() if p.is_file()]
rec.update(phase='Local task completed' if code==0 else 'Local task failed',state='done' if code==0 else 'failed',returncode=code,finished=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
if code and not rec.get('error'):rec['error']='Local scientific checks failed; see retained output.'
G._write(service,rec);print('[fold] local task '+rec['state'],flush=True)
