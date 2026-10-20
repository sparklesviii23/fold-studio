"""FASTA transport and provenance contracts; synthetic coordinate fixtures are not predictions."""
import json,pathlib,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures
from sequence_targets import fasta,predicted_crop,verify_preparation
from fold_engine import checksum
class SequenceTargetContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def sequence(self):return self.s.sequence_save({'projectId':self.project['id'],'name':'Synthetic canonical sequence fixture','sequence':'ACDEFGHIKLMNPQRSTVWY'})
 def payload(self,record):return {**self.config,'structureId':record['id'],'modality':'binder','targetChains':['A'],'hotspots':[],'coldspots':[],'binderLengths':[60]}
 def test_sequence_inspection_has_no_fabricated_structure_or_atom_array(self):
  record=self.sequence();info=self.s.dispatch('fold_target',self.payload(record));self.assertEqual(info['sequence'],record['data']['sequence']);self.assertNotIn('structure',info);self.assertEqual(info['reference']['format'],'fasta');self.assertEqual(info['reference']['sequenceSha256'],record['data']['sha256'])
 def test_prepare_snapshots_exact_canonical_fasta_without_coordinates_or_compute(self):
  record=self.sequence()
  with patch.object(self.s,'spawn') as process:job=self.s.dispatch('bindcraft_prepare',self.payload(record));process.assert_not_called()
  folder=self.s.root/'jobs'/job['id'];self.assertEqual((folder/'input.fasta').read_bytes(),fasta(record['data']['sequence']));self.assertEqual(job['data']['preparation']['residueMap'],[]);self.assertFalse((folder/'input.pdb').exists());self.assertEqual(job['data']['preparation']['config']['targets'][0]['target_path'],'input.fasta')
  self.assertEqual(self.s.dispatch('bindcraft_repeat',{'projectId':self.project['id'],'id':job['id']})['data']['preparation']['sequenceTarget'],job['data']['preparation']['sequenceTarget'])
 def test_unknown_observed_sites_or_multiple_inputs_cannot_be_applied_to_sequence(self):
  record=self.sequence()
  for changes in ({'hotspots':['["A",1,""]']},{'coldspots':['["A",1,""]']},{'targetChains':['B']},{'modality':'homo_oligomer'},{'additionalTargets':[{}]}):
   with self.subTest(changes=changes),self.assertRaisesRegex(ValueError,'Sequence-target preparation'):self.s.dispatch('bindcraft_prepare',{**self.payload(record),**changes})
 def test_tampered_or_cross_project_sequence_is_refused(self):
  record=self.sequence();other=self.s.project_create({'name':'Other'})
  with self.assertRaisesRegex(ValueError,'another project'):self.s.dispatch('fold_target',{**self.payload(record),'projectId':other['id']})
  data={**record['data'],'sequence':'A'*20};self.s.db.execute('UPDATE records SET data=? WHERE id=?',(json.dumps(data),record['id']));self.s.db.commit()
  with self.assertRaisesRegex(ValueError,'Sequence checksum changed'):self.s.dispatch('bindcraft_prepare',self.payload(record))
 def test_sequence_input_cannot_bypass_its_dedicated_cpu_profile(self):
  record=self.sequence();job=self.s.dispatch('bindcraft_prepare',self.payload(record))
  for profile in ('experimental-metal-float32-single-model','experimental-cpu-float32-ensemble','experimental-cpu-float32-320'):
   with self.subTest(profile=profile),self.assertRaisesRegex(ValueError,'Sequence-only targets require'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':job['id'],'profile':profile})
  plain=self.s.dispatch('bindcraft_prepare',self.config)
  with self.assertRaisesRegex(ValueError,'profile requires a saved FASTA'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':plain['id'],'profile':'experimental-cpu-float32-sequence'})
 def test_predicted_crop_requires_exact_source_positions_and_explicit_roles(self):
  sha=checksum(b'ACDE');prep={'source':{'format':'fasta','sequenceSha256':sha,'sha256':checksum(fasta('ACDE'))},'residueMap':[],'sequenceTarget':{'sequence':'ACDE','sequenceSha256':sha}};roles={'B':{'role':'target'},'A':{'role':'candidate'}};st={'residues':[{'chain':'B','polymer':True,'ins':'','num':2,'one':'C'},{'chain':'B','polymer':True,'ins':'','num':3,'one':'D'}]};result=predicted_crop(prep,st,roles);self.assertEqual((result['start'],result['end']),(2,3));self.assertEqual(result['basis'],'predicted_sequence_target')
  for structure,assignment in [(st,None),({**st,'residues':[dict(st['residues'][0],one='A')]},roles),({**st,'residues':[st['residues'][0],dict(st['residues'][1],num=4,one='E')]},roles)]:
   with self.assertRaises(ValueError):predicted_crop(prep,structure,assignment)
 def test_changed_sequence_metadata_cannot_relabel_a_saved_fasta_prediction(self):
  record=self.sequence();job=self.s.dispatch('bindcraft_prepare',self.payload(record));prep=job['data']['preparation'];prep['sequenceTarget']['sequence']='A'*20
  with self.assertRaisesRegex(ValueError,'immutable FASTA receipt'):verify_preparation(prep)
 def test_packaging_and_native_ipc_include_sequence_adapter(self):
  root=pathlib.Path(__file__).parents[1];self.assertIn('"fold_target"',(root/'src-tauri/src/main.rs').read_text());self.assertIn('../scientific/sequence_targets.py',json.loads((root/'src-tauri/tauri.conf.json').read_text())['bundle']['resources'])
 def test_crop_count_is_contextual_bounded_and_requires_real_cropping(self):
  from campaign_options import validate
  import fold_engine as fe
  values={'idr_crop_count':2,'crop_fasta_sequence':[5,10]}
  self.assertEqual(validate(values,fe.UPSTREAM,'peptide','sequence'),values)
  with self.assertRaisesRegex(ValueError,'Use native'):validate(values,fe.UPSTREAM,'peptide','structure')
  for count in (0,4,True,1.5,'2'):
   with self.subTest(count=count),self.assertRaises(ValueError):validate({'idr_crop_count':count},fe.UPSTREAM,'peptide','sequence')
  for disabled in (None,False):
   with self.subTest(disabled=disabled),self.assertRaisesRegex(ValueError,'require original sequence cropping'):validate({'idr_crop_count':2,'crop_fasta_sequence':disabled},fe.UPSTREAM,'peptide','sequence')
 def test_virtual_crop_outputs_map_to_one_physical_input_without_filename_guessing(self):
  from campaign_inputs import snapshots,prediction_targets,ranked_target,verify
  record=self.sequence();job=self.s.dispatch('bindcraft_prepare',self.payload(record));prep=job['data']['preparation'];prep['config'].update(idr_crop_count=2,crop_fasta_sequence=5)
  folder=self.s.root/'jobs'/job['id'];verify(folder,prep)
  self.assertEqual(len(snapshots(prep)),1);states=prediction_targets(prep);self.assertEqual([state['name'] for state in states],['target_epitope_1','target_epitope_2'])
  for state in states:
   self.assertEqual(state['source'],prep['source']);self.assertEqual(state['file'],'input.fasta');self.assertEqual(state['sourceTargetName'],'target')
   self.assertEqual(ranked_target(prep,'candidate_'+state['name']+'.cif','candidate'),state)
  for filename in ('candidate.cif','candidate_target.cif','candidate_target_epitope_3.cif'):
   with self.subTest(filename=filename),self.assertRaisesRegex(ValueError,'unique prepared target'):ranked_target(prep,filename,'candidate')
 def test_crop_resource_budget_counts_every_state_and_checks_original_state_names(self):
  from campaign_profile import sequence_resources
  record=self.sequence();job=self.s.dispatch('bindcraft_prepare',self.payload(record));prep=job['data']['preparation'];prep['config'].update(idr_crop_count=2,crop_fasta_sequence=5)
  estimate={'paddedResidues':96,'targetPredictionStates':['target_epitope_1','target_epitope_2']}
  self.assertEqual(sequence_resources(estimate,prep)['aggregatePaddedResidues'],192)
  with self.assertRaisesRegex(ValueError,'192 aggregate'):sequence_resources({**estimate,'paddedResidues':128},prep)
  with self.assertRaisesRegex(ValueError,'state mapping'):sequence_resources({**estimate,'targetPredictionStates':['target']},prep)
 def test_multiple_crop_states_cannot_relabel_an_observed_input(self):
  from campaign_inputs import prediction_targets
  job=self.s.dispatch('bindcraft_prepare',self.config);prep=job['data']['preparation'];prep['config']['idr_crop_count']=2
  with self.assertRaisesRegex(ValueError,'one immutable FASTA'):prediction_targets(prep)
 def crop_outputs(self,complete):
  from test_unbound_predictions import cif
  record=self.s.sequence_save({'projectId':self.project['id'],'name':'Synthetic A-only sequence transport fixture','sequence':'AAAA'})
  job=self.s.dispatch('bindcraft_prepare',self.payload(record));prep=job['data']['preparation'];prep['config'].update(idr_crop_count=2,crop_fasta_sequence=1);self.s.job_update(job['id'],'prepared',{'preparation':prep})
  root=self.s.root/'jobs'/job['id']/'output';ranked=root/'3_Ranked';ranked.mkdir(parents=True);(root/'campaign_metadata.json').write_text(json.dumps({'settings':{}}));(ranked/'!_Ranked.csv').write_text('design,Binder_Sequence,i_pTM\nsynthetic,A,0.99\n')
  for index in range(1,3 if complete else 2):(ranked/f'synthetic_target_epitope_{index}.cif').write_text(cif(True))
  return {'projectId':self.project['id'],'id':job['id'],'directory':str(root)}
 def test_missing_virtual_crop_output_blocks_the_whole_native_import(self):
  payload=self.crop_outputs(False);before=len(self.s.library({})['records'])
  with patch('bindcraft_provenance.native_receipt',return_value={'state':'native_receipts_verified','execution':'cpu','scope':'Synthetic transport fixture, no prediction'}):
   with self.assertRaisesRegex(ValueError,'missing a prepared target'):self.s.dispatch('bindcraft_import',payload)
  self.assertEqual(len(self.s.library({})['records']),before)
 def test_all_virtual_crop_outputs_retain_individual_states_and_shared_input_receipt(self):
  payload=self.crop_outputs(True)
  with patch('bindcraft_provenance.native_receipt',return_value={'state':'native_receipts_verified','execution':'cpu','scope':'Synthetic transport fixture, no prediction'}):result=self.s.dispatch('bindcraft_import',payload)
  self.assertEqual(len(result['records']),2);records=[self.engine.lab.intelligence_inspect({'structureId':id}) for id in result['records']];states=[record['record']['data']['metadata']['nativeTargetState'] for record in records]
  self.assertEqual({state['name'] for state in states},{'target_epitope_1','target_epitope_2'});self.assertEqual(states[0]['source'],states[1]['source']);self.assertTrue(all(state['sourceTargetName']=='target' for state in states))
  for record in records:self.assertEqual(record['record']['data']['metadata']['sequenceTargetPrediction']['basis'],'predicted_sequence_target')
 def test_fixed_crop_header_compatibility_preserves_the_saved_scalar_recipe(self):
  from bindcraft_cpu import execution_config
  original={'targets':[{'target_path':'input.fasta'}],'crop_fasta_sequence':16};config,_=execution_config(original,self.base)
  self.assertEqual(original['crop_fasta_sequence'],16);self.assertEqual(config['crop_fasta_sequence'],[16,16])
  original['crop_fasta_sequence']=[12,16];config,_=execution_config(original,self.base);self.assertEqual(config['crop_fasta_sequence'],[12,16])
del Fixtures
