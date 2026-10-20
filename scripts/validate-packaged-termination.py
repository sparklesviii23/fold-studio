"""Synthetic lifecycle acceptance in the signed bundled runtime; no model executes."""
import argparse,json,os,pathlib,subprocess,sys
sys.dont_write_bytecode=True
p=argparse.ArgumentParser();p.add_argument('--app',required=True);p.add_argument('--root',required=True);p.add_argument('--report',required=True);p.add_argument('--source-commit',required=True);a=p.parse_args();app=pathlib.Path(a.app).resolve();root=pathlib.Path(a.root).resolve();report=pathlib.Path(a.report).resolve();resources=app/'Contents/Resources'
if root.exists():raise SystemExit('Choose a new isolated lifecycle-test root.')
check=subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],capture_output=True,text=True);assert check.returncode==0,check.stderr
source=pathlib.Path(__file__).resolve().parents[1]/'scientific/bindcraft_cpu.py';assert source.read_bytes()==(resources/'scientific/bindcraft_cpu.py').read_bytes()
code='''
import json,pathlib,signal,sys,types
from unittest.mock import patch
resources=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(resources/'scientific'))
from worker import Service
from bindcraft_cpu import execution_config,run
import bindcraft_cpu,fold_engine as fe
s=Service(pathlib.Path(sys.argv[2]));project=s.project_create({'name':'Packaged lifecycle-only QA · no model executed'});record=s.import_structure({'projectId':project['id'],'path':str(resources/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb'),'name':'Unchanged original hPDL1 input for lifecycle contract only'})
try:
 job=s.dispatch('bindcraft_prepare',{'projectId':project['id'],'structureId':record['id'],'name':'SIGTERM lifecycle simulation · no scientific calculation','modality':'binder','targetChains':['A'],'binderLengths':[60],'candidates':1,'attempts':1,'seed':42});folder=s.root/'jobs'/job['id'];config,_=execution_config(job['data']['preparation']['config'],folder);(folder/'execution-settings.json').write_text(json.dumps(config,indent=2));s.job_update(job['id'],'queued',{'runtime':str(resources/'runtime/bin/python3.12'),'parameters':str(resources/'models/alphafold'),'executionSettingsSha256':fe.checksum(fe.canonical(config).encode()),'profile':'experimental-cpu-float32-single-model'});before={path.name:path.read_bytes() for path in folder.iterdir() if path.is_file()}
 with patch.object(bindcraft_cpu.subprocess,'run',return_value=types.SimpleNamespace(returncode=-signal.SIGTERM)) as mocked:run(s,job['id']);mocked.assert_called_once()
 result=s.job(job['id']);assert result['state']=='interrupted';assert result['data']['termination']['signal']=='SIGTERM';assert not result['data']['outputs'];assert 'outcome' not in result['data'];assert before=={path.name:path.read_bytes() for path in folder.iterdir() if path.is_file()}
 report={'state':'passed','scope':'Synthetic subprocess termination response tested through the actual signed bundled scientific module and interpreter. No AlphaFold/ProteinMPNN calculation was executed; no scientific result or acceptance is claimed.','jobId':job['id'],'root':str(s.root),'interpreter':sys.executable,'projectId':project['id'],'recordedState':result['state'],'termination':result['data']['termination'],'inputsAndFilesUnchanged':True,'acceptedOutputs':0};pathlib.Path(sys.argv[3]).write_text(json.dumps(report,indent=2)+'\\n')
finally:s.db.close()
'''
env={key:value for key,value in os.environ.items() if key not in ('FOLD_PYTHON','FOLD_BINDCRAFT_PYTHON','FOLD_AF2_PARAMETERS','PYTHONPATH','PYTHONHOME','DYLD_LIBRARY_PATH')}
result=subprocess.run([str(resources/'runtime/bin/python3.12'),'-I','-B','-c',code,str(resources),str(root),str(report)],capture_output=True,text=True,env=env,timeout=60)
if result.returncode:raise RuntimeError(result.stderr)
check=subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],capture_output=True,text=True);assert check.returncode==0,check.stderr
evidence=json.loads(report.read_text());evidence.update(app=str(app),sourceCommit=a.source_commit,signatureAfterLifecycleTest='passed',nativeVisualStatus='pending');report.write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,indent=2))
