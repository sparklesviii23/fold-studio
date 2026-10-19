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
del Fixtures
