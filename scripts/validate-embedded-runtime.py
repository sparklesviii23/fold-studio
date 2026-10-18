"""Relocated app acceptance without system Python for scientific IPC or inference."""
import argparse,hashlib,json,os,pathlib,subprocess,time
p=argparse.ArgumentParser();p.add_argument('--app',required=True);p.add_argument('--root',required=True);a=p.parse_args();app=pathlib.Path(a.app).resolve();root=pathlib.Path(a.root).resolve();resources=app/'Contents/Resources';python=resources/'runtime/bin/python3.12';worker=resources/'scientific/worker.py';env={k:v for k,v in os.environ.items() if k not in ('FOLD_PYTHON','FOLD_BINDCRAFT_PYTHON','FOLD_AF2_PARAMETERS','PYTHONPATH','PYTHONHOME','DYLD_LIBRARY_PATH')}
def call(action,payload={}):
 proc=subprocess.run([str(python),'-I','-B',str(worker),'--root',str(root),'--fixtures',str(resources/'fixtures')],input=json.dumps({'action':action,'payload':payload}),capture_output=True,text=True,timeout=60,env=env)
 reply=json.loads(proc.stdout)
 if 'error' in reply:raise RuntimeError(reply['error'])
 return reply['result']
library=call('library');structure=next(r for r in library['records'] if r['kind']=='structure');project=structure['project_id'];job=call('mpnn_start',{'projectId':project,'structureId':structure['id'],'designChains':['A'],'count':1,'seed':2718});deadline=time.monotonic()+90
while job['state'] in ('running','queued'):
 if time.monotonic()>deadline:raise RuntimeError('Packaged inference timeout.')
 time.sleep(.5);job=call('job_read',{'id':job['id']})
if job['state']!='completed':raise RuntimeError(json.dumps(job))
assert pathlib.Path(job['data']['runtime']).is_relative_to(resources/'runtime')
records=call('library')['records'];output=next(r for r in records if r['id']==job['data']['outputs'][0]);assert len(output['data']['sequence'])==460
for name in ('model_1_ptm','model_1_multimer_v3'):
 params=resources/'models/alphafold'/('params_'+name+'.npz');provenance=json.loads(params.with_suffix('.provenance.json').read_text());assert hashlib.sha256(params.read_bytes()).hexdigest()==provenance['sha256']
assert subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],capture_output=True).returncode==0
report={'state':'passed','app':str(app),'scientificPython':str(python),'externalRuntimeEnvironmentRemoved':True,'realProteinMPNNJob':'completed','sourceResidues':460,'savedSequences':1,'modelParameterChecksums':'passed','signatureAfterInference':'passed','scope':'Relocated CPU scientific runtime and model resources; ChimeraX/Boltz are not bundled','jobId':job['id'],'resultSummary':job['data']['resultSummary']}
out=pathlib.Path(__file__).resolve().parents[1]/'reports/embedded-runtime-acceptance.json';out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
