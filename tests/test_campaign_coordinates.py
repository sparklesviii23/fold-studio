"""Stage-preview protocol fixtures; no computed or accepted campaign claim.

The full molecular file is a genuine gradient diagnostic. The stage rows and
terminal states here are explicitly synthetic transport fixtures.
"""
import csv,io,json,pathlib,subprocess,sys,unittest,zipfile
from test_project_metal import ProjectMetalTests as Fixtures,w

class CampaignCoordinateContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 prepared=Fixtures.prepared

 def source(self,stage='candidates',saved=True):
  job=self.prepared();output=self.s.root/'jobs'/job['id']/'output';design='transport_fixture';raw=(pathlib.Path(w.__file__).parents[1]/'reports/amme-fab-memory-scheduler-gradient_target.cif').read_bytes()
  if stage=='trajectories':
   folder=output/'1_Trajectories'/design;file=folder/(design+'_trajectory.cif');table=output/'1_Trajectories/!_Trajectories.csv';row={'design':design,'terminated':'screen'}
  else:
   folder=output/'2_Refolded/Complexes';file=folder/(design+'.cif');table=output/'2_Refolded/!_Refolded.csv';row={'design':design,'outcome':'rejected','failed_filters':'i_pTM','i_pTM':'0.99'}
  folder.mkdir(parents=True);buffer=io.StringIO();writer=csv.DictWriter(buffer,fieldnames=list(row));writer.writeheader();writer.writerow(row);table.write_text(buffer.getvalue())
  if saved:file.write_bytes(raw)
  self.s.job_update(job['id'],'failed',{'error':'Synthetic stopped-state transport fixture; not a calculation.'})
  payload={'projectId':self.project['id'],'id':job['id']};reading=self.s.dispatch('bindcraft_results',payload)
  entries=reading['tables'][stage]['coordinates'].get(design,[])
  request={**payload,'operation':'save_coordinates','table':stage,'design':design,**({'file':entries[0]['file'],'sha256':entries[0]['sha256']} if entries else {})}
  return job,output,file,raw,request,reading

 def test_genuine_full_coordinates_are_saved_once_without_changing_acceptance(self):
  for stage in ('trajectories','candidates'):
   job,output,file,raw,request,_=self.source(stage)
   before=self.s.job(job['id']);source={str(p.relative_to(output)):p.read_bytes() for p in output.rglob('*') if p.is_file()}
   result=self.s.dispatch('bindcraft_review',request);record=result['record'];info=record['data']
   self.assertIn('not accepted',record['name']);self.assertEqual(info['metadata']['campaignStagePreview']['computationalAcceptance'],'not_asserted')
   self.assertIsNone(info['confidenceKind']);self.assertNotIn('nativeRun',info['metadata'])
   self.assertEqual((self.s.root/'assets'/info['asset']).read_bytes(),raw);self.assertEqual(set(info['metadata']['chainRoles']),{'A','B','C'})
   self.assertEqual(self.s.job(job['id']),before);self.assertEqual(source,{str(p.relative_to(output)):p.read_bytes() for p in output.rglob('*') if p.is_file()})
   repeat=self.s.dispatch('bindcraft_review',request);self.assertEqual(repeat['record']['id'],record['id']);self.assertEqual(repeat['state'],'already_saved')
   archive=self.base/(stage+'.zip');self.s.export_project({'id':self.project['id'],'path':str(archive)})
   with zipfile.ZipFile(archive) as saved:self.assertEqual(saved.read('assets/'+info['asset']),raw)

 def test_no_coordinate_file_means_no_invented_preview(self):
  *_,request,reading=self.source(saved=False)
  self.assertEqual(reading['tables']['candidates']['coordinates'],{})
  with self.assertRaisesRegex(ValueError,'unavailable'):self.s.dispatch('bindcraft_review',request)

 def test_changed_coordinates_refuse_stale_ui_receipt(self):
  job,_,file,raw,request,_=self.source();before=self.s.library({})['records'];file.write_bytes(raw+b'\n# changed\n')
  with self.assertRaisesRegex(ValueError,'changed'):self.s.dispatch('bindcraft_review',request)
  self.assertEqual(before,self.s.library({})['records'])

 def test_live_campaign_and_ranked_stage_are_not_stage_preview_imports(self):
  job,_,_,_,request,_=self.source()
  with self.assertRaisesRegex(ValueError,'ranked designs'):self.s.dispatch('bindcraft_review',{**request,'table':'accepted'})
  self.s.job_update(job['id'],'running')
  with self.assertRaisesRegex(ValueError,'Finish or stop'):self.s.dispatch('bindcraft_review',request)

 def test_symlinks_and_unknown_file_requests_are_refused(self):
  _,_,file,_,request,_=self.source();file.unlink();file.symlink_to(self.file)
  with self.assertRaises(ValueError):self.s.dispatch('bindcraft_review',request)
  _,_,_,_,request,_=self.source()
  with self.assertRaisesRegex(ValueError,'unavailable'):self.s.dispatch('bindcraft_review',{**request,'file':'../../input.pdb'})

 def test_an_orphan_scientific_child_still_stopping_blocks_the_snapshot(self):
  job,_,_,_,request,_=self.source()
  child=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)',job['id']],start_new_session=True)
  try:
   self.s.job_metadata(job['id'],{'pid':child.pid})
   with self.assertRaisesRegex(ValueError,'still stopping'):self.s.dispatch('bindcraft_review',request)
  finally:child.terminate();child.wait(timeout=5)

 def test_unbound_files_are_not_mistaken_for_a_target_complex(self):
  _,_,file,raw,request,_=self.source();monomer=file.with_name(file.stem+'_monomer.cif');file.unlink();monomer.write_bytes(raw)
  with self.assertRaisesRegex(ValueError,'unavailable'):self.s.dispatch('bindcraft_review',request)

 def test_persistence_failure_rolls_back_record_assignment_and_coordinate_asset(self):
  _,_,_,_,request,_=self.source();before=self.s.library({})['records'];assets={p.name:p.read_bytes() for p in (self.s.root/'assets').iterdir() if p.is_file()}
  self.s.db.execute("CREATE TRIGGER refuse_preview BEFORE INSERT ON records WHEN NEW.name LIKE '%preview%' BEGIN SELECT RAISE(FAIL,'injected preview persistence failure'); END")
  with self.assertRaisesRegex(Exception,'injected preview persistence failure'):self.s.dispatch('bindcraft_review',request)
  self.assertEqual(self.s.library({})['records'],before)
  self.assertEqual({p.name:p.read_bytes() for p in (self.s.root/'assets').iterdir() if p.is_file()},assets)
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM intelligence_assignments').fetchone()[0],0)


del Fixtures
