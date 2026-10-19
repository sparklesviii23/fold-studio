"""Real upstream campaign interruption/next-trajectory recovery; no filter changes."""
import argparse,csv,hashlib,json,os,pathlib,subprocess,sys,time
sys.dont_write_bytecode=True
REPOSITORY=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--python',required=True);p.add_argument('--parameters',required=True);p.add_argument('--report',required=True);p.add_argument('--engine-root');p.add_argument('--attempts',type=int,default=4);p.add_argument('--cancel-after-updates',type=int);a=p.parse_args();ROOT=pathlib.Path(a.engine_root).resolve() if a.engine_root else REPOSITORY;sys.path.insert(0,str(ROOT/'scientific'));from worker import Service
root=pathlib.Path(a.directory).resolve()
if root.exists():raise SystemExit('Use a new isolated campaign recovery root.')
s=Service(root);s.setting_set({'key':'bindcraftPython','value':os.path.abspath(a.python)});s.setting_set({'key':'af2Parameters','value':str(pathlib.Path(a.parameters).resolve())});project=s.project_create({'name':'Authentic BindCraft2 recovery QA'});source=ROOT/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb';source_sha=hashlib.sha256(source.read_bytes()).hexdigest();record=s.import_structure({'projectId':project['id'],'path':str(source),'name':'Official hPDL1 reference · original source'});shared=s.dispatch('fold_structure',{'projectId':project['id'],'structureId':record['id']});fragment=s.dispatch('fold_fragment',{'projectId':project['id'],'structureId':record['id'],'residues':[r['id'] for r in shared['structure']['residues'] if r['chain']=='A'][:12],'name':'Explicit 12-residue reference fragment · technical recovery QA only'});print('Fragment result',fragment,flush=True)
if 'record' in fragment:fragment=fragment['record']
job=s.dispatch('bindcraft_prepare',{'projectId':project['id'],'structureId':fragment['id'],'name':'Real interrupted 24-residue campaign · recovery QA','modality':'binder','targetChains':['A'],'hotspots':[],'coldspots':[],'binderLengths':[12],'candidates':1,'attempts':a.attempts,'seed':2718});folder=root/'jobs'/job['id'];state={'state':'running','scope':'Bounded genuine upstream CPU campaign on explicit 12-residue official-target derivative and 12-residue binder. Original loss/stage/filter settings; tests recovery, not biological design quality.','root':str(root),'engineRoot':str(ROOT),'projectId':project['id'],'jobId':job['id'],'sourceSha256':source_sha};report=pathlib.Path(a.report);report.write_text(json.dumps(state,indent=2)+'\n');job=s.dispatch('bindcraft_start',{'projectId':project['id'],'id':job['id'],'profile':'experimental-cpu-float32-single-model'});deadline=time.monotonic()+1200
try:
 table=folder/'output/1_Trajectories/!_Trajectories.csv'
 while True:
  current=s.job(job['id'])
  if a.cancel_after_updates:
   from bindcraft_cpu import progress_from_log
   log=folder/'execution.log';observed=progress_from_log(log.read_text() if log.is_file() else '')
   if observed.get('lastObservedUpdate',{}).get('sequenceUpdates',0)>=a.cancel_after_updates:break
  elif table.is_file() and list(csv.DictReader(table.open())):break
  if current['state'] not in ('queued','running'):raise ValueError('Campaign ended before the interruption acceptance point; inspect without rerunning.')
  if time.monotonic()>deadline:raise TimeoutError('Inspect active job before further action.')
  time.sleep(.1)
 cancelled=s.dispatch('job_cancel',{'id':job['id']})
 if cancelled['state']!='cancelled':raise ValueError('Campaign completed before cancellation; no recovery claimed.')
 state_path=folder/'output/.campaign_state.json';progress=json.loads(state_path.read_text());before={str(f.relative_to(folder/'output')):hashlib.sha256(f.read_bytes()).hexdigest() for f in (folder/'output').rglob('*') if f.is_file()};state.update(state='cancelled_pending_recovery',beforeRecovery=progress);report.write_text(json.dumps(state,indent=2)+'\n')
 for _ in range(100):
  try:resumed=s.dispatch('bindcraft_resume',{'projectId':project['id'],'id':job['id']});break
  except ValueError as error:
   if 'still stopping' not in str(error):raise
   time.sleep(.1)
 else:raise ValueError('Original worker group did not stop; no duplicate computation launched.')
 state.update(state='resuming');report.write_text(json.dumps(state,indent=2)+'\n')
 while True:
  current=s.job(job['id'])
  if current['state'] not in ('queued','running'):break
  if time.monotonic()>deadline:raise TimeoutError('Inspect active resumed job; do not restart.')
  time.sleep(.5)
 if current['state']!='completed':raise ValueError('Resumed campaign failed: '+str(current['data'].get('error')))
 rows=list(csv.DictReader(table.open()));numbers=[int(row['trajectory']) for row in rows]
 if len(set(numbers))!=len(numbers) or max(numbers)<=progress['trajectories']:raise AssertionError('Recovery did not continue at a new upstream trajectory.')
 saved=current['data']['recoveryHistory'][-1];receipt=json.loads((folder/saved['folder']/'receipt.json').read_text())
 if {name:entry['sha256'] for name,entry in receipt['outputManifest'].items()}!=before:raise AssertionError('Archived pre-recovery manifest differs.')
 if hashlib.sha256(source.read_bytes()).hexdigest()!=source_sha:raise AssertionError('Official target source changed.')
 state.update(state='passed',afterRecovery=json.loads(state_path.read_text()),trajectoryNumbers=numbers,outcome=current['data'].get('outcome'),outputs=current['data'].get('outputs'),recoveryHistory=current['data']['recoveryHistory'],sourceUnchanged=True,originalFiltersPreserved=True);report.write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(state,indent=2),flush=True)
except Exception as error:
 state.update(state='failed',error=str(error));report.write_text(json.dumps(state,indent=2)+'\n');raise
finally:s.db.close()
