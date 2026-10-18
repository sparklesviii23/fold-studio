"""Synthetic receipt/role protocol tests; these fixtures are not executed designs."""
import json,unittest
from test_project_metal import ProjectMetalTests as Fixtures,w
from bindcraft_provenance import native_receipt,chain_roles

class NativeReceiptContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 prepared=Fixtures.prepared
 def receipts(self):
  j=self.prepared();folder=self.s.root/'jobs'/j['id'];path=folder/'execution-settings.json';config=j['data']['preparation']['config'];path.write_text(json.dumps(config));source=w.fold_engine.verify_source()
  runtime={'state':'finished','exitCode':0,'execution':'cpu','precision':'float32','executionSettingsSha256':w.fold_engine.checksum(path.read_bytes()),'upstreamSource':source}
  (folder/'runtime-provenance.json').write_text(json.dumps(runtime));self.s.job_update(j['id'],'prepared',{'execution':'cpu','precision':'float32','executionSettingsSha256':w.fold_engine.checksum(w.fold_engine.canonical(config).encode()),'checkpointSha256':{'model_1_ptm':'receipt-fixture'}})
  metadata={'settings_path':str(path),'checkpoints':{'/test/params_model_1_ptm.npz':'receipt-fixture'},'revision':'reported test revision'}
  return self.s.job(j['id']),folder,metadata
 def test_external_output_cannot_acquire_native_provenance(self):
  j,folder,metadata=self.receipts();self.assertIsNone(native_receipt(self.s,j,self.base/'external',metadata))
 def test_changed_settings_refuse_receipt_upgrade(self):
  j,folder,metadata=self.receipts();(folder/'execution-settings.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'settings receipt'):native_receipt(self.s,j,folder/'output',metadata)
 def test_checkpoint_correspondence_is_required(self):
  j,folder,metadata=self.receipts();metadata['checkpoints']={}
  with self.assertRaisesRegex(ValueError,'checkpoint receipt mismatch'):native_receipt(self.s,j,folder/'output',metadata)
 def test_changed_target_refuses_receipt_upgrade(self):
  j,folder,metadata=self.receipts();(folder/'input.pdb').write_text('changed source')
  with self.assertRaisesRegex(ValueError,'target snapshot changed'):native_receipt(self.s,j,folder/'output',metadata)
 def test_explicit_cif_roles_must_match_disjoint_written_chains(self):
  st={'chains':[{'id':'A'},{'id':'B'}]};raw=b'data_test\n_bindcraft.binder_chains B\n_bindcraft.target_chains A\n'
  self.assertEqual(chain_roles(raw,st)['B']['role'],'candidate');self.assertEqual(chain_roles(raw,st)['A']['role'],'target')
  for altered in (raw.replace(b'binder_chains B',b'binder_chains C'),raw.replace(b'binder_chains B',b'binder_chains A')):
   with self.assertRaises(ValueError):chain_roles(altered,st)
del Fixtures
