"""Relocated app GPU acceptance with app-owned interpreter, source and parameters."""
import argparse,json,os,pathlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--app',required=True);p.add_argument('--root',required=True);a=p.parse_args()
ROOT=pathlib.Path(__file__).resolve().parents[1];app=pathlib.Path(a.app).resolve();resources=app/'Contents/Resources';folder=pathlib.Path(a.root).resolve();folder.mkdir(parents=True,exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('FOLD_','PYTHON','DYLD_','METALJAX_')) and k!='JAX_PLATFORMS'}
cpu=resources/'runtime/bin/python3.12';metal=resources/'runtime-metal/bin/python3.12'
request={'action':'fold_compute','payload':{}}
proc=subprocess.run([str(cpu),'-I','-B',str(resources/'scientific/worker.py'),'--root',str(folder/'library'),'--fixtures',str(resources/'fixtures')],input=json.dumps(request),capture_output=True,text=True,env=env,timeout=60)
reply=json.loads(proc.stdout)
if 'error' in reply:raise RuntimeError(reply['error'])
detected=reply['result']['bindcraftMetalRuntime']
if detected['state']!='experimental' or pathlib.Path(detected['runtime'])!=metal:raise RuntimeError('App failed to discover its own pinned Metal runtime: '+json.dumps(detected))
env.update(detected['environment'])
output=folder/'af2-full-metal.json'
command=[str(metal),'-I','-B',str(ROOT/'scripts/validate-af2-full.py'),'--engine-root',str(resources),'--parameters',str(resources/'models/alphafold'),'--output',str(output),'--gradient','--backend','metal','--precision','float32','--controlled-input']
result=subprocess.run(command,capture_output=True,text=True,env=env,timeout=180)
(folder/'af2-execution.log').write_text(result.stdout+'\n'+result.stderr)
if result.returncode:raise RuntimeError(result.stderr[-4000:])
model=json.loads(output.read_text())
if model['backend']!='metal' or model['engineRoot']!=str(resources):raise RuntimeError('Unexpected scientific execution source/backend.')
check=subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],capture_output=True,text=True)
if check.returncode:raise RuntimeError('App seal failed after inference: '+check.stderr)
report={'state':'passed','scope':'Same-host relocated app-owned Metal runtime, pinned upstream source and trained monomer checkpoint; real full forward/backprop on 12-residue technical input. Not full campaign/biological validation or fresh-machine acceptance.','app':str(app),'externalRuntimeEnvironmentRemoved':True,'runtimeDiscovery':detected,'modelExecution':model,'signatureAfterInference':'passed'}
(ROOT/'reports/embedded-metal-runtime-acceptance.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
