"""Saved-source correspondence and objective contracts, not design results."""
import json,os,unittest,zipfile
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures,pdb,w
from campaign_inputs import verify,ranked_target

class MultipleTargetInputs(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def extra(self,**fields):
  file=self.base/'second.pdb';file.write_text(pdb().replace('1.450','1.451'))
  record=self.s.import_structure({'projectId':self.project['id'],'path':str(file)})
  return {'structureId':record['id'],'targetChains':['A'],**fields}
 def test_explicit_positive_negative_targets_retain_original_weights_and_numbering(self):
  extra=self.extra(objective='detarget',weight=.5,hotspots=['["A",1,""]'])
  checked=self.s.dispatch('bindcraft_validate',{**self.config,'additionalTargets':[extra]})
  target=checked['config']['targets'][1]
  self.assertEqual((target['name'],target['target_path'],target['objective'],target['weight'],target['hotspots']),('target2','target2.pdb','detarget',-.5,'A1'))
  self.assertEqual(checked['targetSources'][1]['source']['structureId'],extra['structureId']);self.assertFalse(checked['executionReady'])
 def test_secondary_snapshot_tampering_blocks_native_receipt_and_execution(self):
  job=self.s.dispatch('bindcraft_prepare',{**self.config,'additionalTargets':[self.extra()]});folder=self.s.root/'jobs'/job['id'];prep=job['data']['preparation']
  self.assertEqual(len(verify(folder,prep)),2);(folder/'target2.pdb').write_text('changed input')
  with self.assertRaisesRegex(ValueError,'Prepared source changed'):verify(folder,prep)
 def test_duplicate_or_contradictory_source_state_is_not_silently_counted_twice(self):
  for objective in ('target','detarget'):
   with self.assertRaisesRegex(ValueError,'Duplicate target'):self.s.dispatch('bindcraft_validate',{**self.config,'additionalTargets':[{'structureId':self.record['id'],'targetChains':['A'],'objective':objective}]})
 def test_invalid_objectives_weights_unknown_fields_and_cross_project_are_refused(self):
  extra=self.extra()
  for field,value in (('objective','induced_fit'),('weight',float('nan')),('weight',True),('weight',0),('file','/external.pdb')):
   with self.subTest(field=field),self.assertRaises(ValueError):self.s.dispatch('bindcraft_validate',{**self.config,'additionalTargets':[{**extra,field:value}]})
  other=self.s.project_create({'name':'Other'});file=self.base/'other.pdb';file.write_text(pdb());record=self.s.import_structure({'projectId':other['id'],'path':str(file)})
  with self.assertRaisesRegex(ValueError,'another project'):self.s.dispatch('bindcraft_validate',{**self.config,'additionalTargets':[{**extra,'structureId':record['id']}]})
 def test_zip_contains_all_immutable_target_inputs_and_manifest(self):
  job=self.s.dispatch('bindcraft_prepare',{**self.config,'additionalTargets':[self.extra()]});archive=self.base/'multi.zip';self.s.export_project({'id':self.project['id'],'path':str(archive)})
  with zipfile.ZipFile(archive) as z:
   prefix='jobs/'+job['id']+'/'
   for item in job['data']['preparation']['targetSources']:self.assertEqual(w.fold_engine.checksum(z.read(prefix+item['file'])),item['source']['sha256'])
   self.assertEqual(len(json.loads(z.read(prefix+'provenance.json'))['targetSources']),2)
 def test_preparation_requires_its_explicit_multi_state_execution_profile(self):
  job=self.s.dispatch('bindcraft_prepare',{**self.config,'additionalTargets':[self.extra()]})
  with self.assertRaisesRegex(ValueError,'explicit multi-target CPU profile'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':job['id'],'profile':'experimental-cpu-float32-single-model'})
  self.assertEqual(self.s.job(job['id'])['state'],'prepared')
 def test_larger_or_scaffold_combinations_cannot_bypass_tested_scope(self):
  job=self.s.dispatch('bindcraft_prepare',self.config)
  with self.assertRaisesRegex(ValueError,'two or three'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':job['id'],'profile':'experimental-cpu-float32-multitarget'})
  request={k:v for k,v in {**self.config,'modality':'VHH','additionalTargets':[self.extra()]}.items() if k!='binderLengths'}
  job=self.s.dispatch('bindcraft_prepare',request)
  with self.assertRaisesRegex(ValueError,'two or three'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':job['id'],'profile':'experimental-cpu-float32-multitarget'})
 def test_changed_secondary_input_refuses_launch_before_model_loading(self):
  job=self.s.dispatch('bindcraft_prepare',{**self.config,'additionalTargets':[self.extra()]})
  (self.s.root/'jobs'/job['id']/'target2.pdb').write_text('changed secondary input')
  with patch.dict(os.environ,{'FOLD_BINDCRAFT_PYTHON':os.sys.executable}),patch.object(self.s,'spawn') as spawn:
   with self.assertRaisesRegex(ValueError,'Prepared source changed'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':job['id'],'profile':'experimental-cpu-float32-multitarget'})
   spawn.assert_not_called()
 def test_ranked_state_mapping_uses_original_writer_suffixes(self):
  job=self.s.dispatch('bindcraft_prepare',{**self.config,'additionalTargets':[self.extra(objective='detarget')]});prep=job['data']['preparation']
  self.assertEqual(ranked_target(prep,'design_target2.cif','design')['objective'],'detarget')
  self.assertEqual(ranked_target(prep,'design_target.cif','design')['source']['structureId'],self.record['id'])
  for file in ('design.cif','design_target3.cif','another_target.cif'):
   with self.assertRaises(ValueError):ranked_target(prep,file,'design')
 def test_changed_queued_secondary_is_rechecked_before_any_scientific_process(self):
  import bindcraft_cpu
  job=self.s.dispatch('bindcraft_prepare',{**self.config,'additionalTargets':[self.extra()]});folder=self.s.root/'jobs'/job['id']
  settings=job['data']['preparation']['config'];(folder/'execution-settings.json').write_text(json.dumps(settings))
  self.s.job_update(job['id'],'queued',{'runtime':os.sys.executable,'parameters':'unused','executionSettingsSha256':w.fold_engine.checksum(w.fold_engine.canonical(settings).encode())})
  (folder/'target2.pdb').write_text('changed after queueing')
  with patch.object(bindcraft_cpu.subprocess,'run') as run:bindcraft_cpu.run(self.s,job['id']);run.assert_not_called()
  self.assertEqual(self.s.job(job['id'])['state'],'failed');self.assertIn('Prepared source changed',self.s.job(job['id'])['data']['error'])
del Fixtures
