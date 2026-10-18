"""Pinned VHH framework/CDR preparation and immutable snapshot contracts."""
import json,os,unittest,zipfile
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures,w

class ScaffoldCampaignTests(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def vhh_config(self):return {k:v for k,v in {**self.config,'modality':'VHH'}.items() if k!='binderLengths'}
 def prepared(self):return self.s.dispatch('bindcraft_prepare',self.vhh_config())
 def test_original_cdr_preset_and_scaffold_are_snapshotted(self):
  j=self.prepared();prep=j['data']['preparation'];folder=self.s.root/'jobs'/j['id'];preset=json.loads((w.fold_engine.UPSTREAM/'settings/modality/VHH.json').read_text())
  self.assertEqual(prep['config']['mutate_positions'],preset['mutate_positions']);self.assertEqual(prep['config']['paratope_conformations'],preset['paratope_conformations']);self.assertEqual(prep['config']['min_scaffold_sequence_retained_final'],1.)
  self.assertEqual(w.fold_engine.checksum((folder/'scaffold.cif').read_bytes()),prep['scaffold']['sha256']);self.assertEqual((folder/'scaffold.cif').read_bytes(),(w.fold_engine.UPSTREAM/'scaffolds/VHH.cif').read_bytes())
 def test_free_length_controls_cannot_silently_change_vhh_cdr_choices(self):
  with self.assertRaisesRegex(ValueError,'CDR edit choices'):self.s.dispatch('bindcraft_validate',{**self.vhh_config(),'binderLengths':[15,20]})
 def test_project_export_retains_both_inputs_and_scaffold_provenance(self):
  j=self.prepared();archive=self.base/'scaffold-project.zip';self.s.export_project({'id':self.project['id'],'path':str(archive)})
  with zipfile.ZipFile(archive) as z:
   prefix='jobs/'+j['id']+'/';self.assertEqual(w.fold_engine.checksum(z.read(prefix+'scaffold.cif')),j['data']['preparation']['scaffold']['sha256']);self.assertIn(prefix+'input.pdb',z.namelist());provenance=json.loads(z.read(prefix+'provenance.json'));self.assertEqual(provenance['scaffold'],j['data']['preparation']['scaffold'])
 def test_tampered_scaffold_refuses_execution_before_model_loading(self):
  j=self.prepared();(self.s.root/'jobs'/j['id']/'scaffold.cif').write_text('changed')
  with patch.dict(os.environ,{'FOLD_BINDCRAFT_PYTHON':os.sys.executable}),patch.object(self.s,'spawn') as spawn:
   with self.assertRaisesRegex(ValueError,'Prepared scaffold changed'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':j['id'],'profile':'experimental-cpu-float32-single-model'})
   spawn.assert_not_called()
  self.assertEqual(self.s.job(j['id'])['state'],'prepared')
 def test_arp_repeat_edits_and_framework_criteria_are_original(self):
  config={**self.vhh_config(),'modality':'ARP'};job=self.s.dispatch('bindcraft_prepare',config)
  prep=job['data']['preparation'];preset=json.loads((w.fold_engine.UPSTREAM/'settings/modality/ARP.json').read_text())
  for key in ('mutate_positions','min_scaffold_sequence_retained_final','max_scaffold_framework_rmsd_final','aa_bias'):
   self.assertEqual(prep['config'][key],preset[key])
  self.assertEqual((self.s.root/'jobs'/job['id']/'scaffold.cif').read_bytes(),(w.fold_engine.UPSTREAM/'scaffolds/ARP.cif').read_bytes())
  with self.assertRaisesRegex(ValueError,'repeat edit choices'):self.s.dispatch('bindcraft_prepare',{**config,'binderLengths':[30]})
del Fixtures
