"""Real packaged-resource IPC -> background inference -> SQLite -> archive acceptance."""
import argparse,hashlib,json,os,pathlib,subprocess,time,zipfile
p=argparse.ArgumentParser();p.add_argument('--app',required=True);p.add_argument('--runtime',required=True);p.add_argument('--root',required=True);a=p.parse_args();repo=pathlib.Path(__file__).resolve().parents[1];app=pathlib.Path(a.app).resolve();root=pathlib.Path(a.root).resolve();worker=app/'Contents/Resources/scientific/worker.py';env={**os.environ,'FOLD_BINDCRAFT_PYTHON':a.runtime}
def call(action,payload={}):
 r=subprocess.run(['/usr/bin/python3','-B',str(worker),'--root',str(root),'--fixtures',str(app/'Contents/Resources/fixtures')],input=json.dumps({'action':action,'payload':payload}),capture_output=True,text=True,env=env,timeout=45);v=json.loads(r.stdout)
 if 'error' in v:raise RuntimeError(v['error'])
 return v['result']
library=call('library');structure=next(r for r in library['records'] if r['kind']=='structure');project=structure['project_id'];source=root/'assets'/structure['data']['asset'];before=hashlib.sha256(source.read_bytes()).hexdigest()
job=call('mpnn_start',{'projectId':project,'structureId':structure['id'],'designChains':['A'],'count':2,'seed':2718})
deadline=time.monotonic()+60
while job['state'] in ('running','queued'):
 if time.monotonic()>deadline:raise RuntimeError('Timed out waiting for model inference.')
 time.sleep(.5);job=call('job_read',{'id':job['id']})
assert job['state']=='completed',job
library=call('library');outputs=[r for r in library['records'] if r['id'] in job['data']['outputs']];assert len(outputs)==2;assert all(len(r['data']['sequence'])==460 for r in outputs);assert hashlib.sha256(source.read_bytes()).hexdigest()==before
archive=root/'acceptance.zip';call('export_project',{'id':project,'path':str(archive)})
with zipfile.ZipFile(archive) as z:
 for name in ('result.json','request.json','sequences.fasta','execution.log'):assert f'jobs/{job["id"]}/{name}' in z.namelist()
assert subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],capture_output=True).returncode==0
report={'state':'passed','fixture':'Bundled ANGPTL3 AlphaFold DB reference','residuesPerOutput':460,'savedSequenceRecords':2,'sourceCoordinatesUnchanged':True,'archiveContainsRawEvidence':True,'signature':'passed','execution':'cpu','upstreamRevision':job['data']['upstreamRevision'],'resultSummary':job['data']['resultSummary'],'jobId':job['id']}
(repo/'reports/packaged-mpnn.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
