"""Bounded background job observer and local evaluator; never submits or retries inference."""
import argparse,json,os,sys,time,traceback,subprocess
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scientific'))
p=argparse.ArgumentParser();p.add_argument('--library',required=True);p.add_argument('--run',required=True);p.add_argument('--reference-dir',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args()
from worker import Service
import gpu_tasks as G
import borzoi_panel as P
root=Path(a.library);out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
claim=root/'gpu_tasks'/a.run/'observer.claim'
with claim.open('x') as f:f.write(str(os.getpid()))
service=Service(root);deadline=time.monotonic()+5400
try:
 while time.monotonic()<deadline:
  task=G.status(service,{'taskId':a.run});state=task['state']
  (out/'BORZOI_STAGE2_STATUS.json').write_text(json.dumps({k:task.get(k) for k in ('id','state','phase','returncode','error','fetchError')},indent=1))
  print('[fold] observer '+state,flush=True)
  if state=='done':
   result=P.evaluate(root,a.run,a.reference_dir);(out/'BORZOI_PANEL_EVALUATION.json').write_text(json.dumps(result,indent=1,allow_nan=False))
   print('[fold] expanded Borzoi evaluation saved; no additional inference launched',flush=True);break
  if state in ('failed','stopped','cancelled'):
   print('[fold] inference ended '+state+'; retained outputs available; no retry',flush=True);break
  time.sleep(30)
 else:print('[fold] observer reached its time limit; inspect the same job manually; no retry',flush=True)
except Exception:
 traceback.print_exc();raise
finally:
 service.db.close()
 subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('report-predictive-stage2.py')),'--output-dir',str(out)],check=True)
