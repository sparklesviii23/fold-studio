"""Queue/lineage failure contracts only; synthetic receipts are not dynamics evidence."""
import hashlib,json,os,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures
import dynamics
from dynamics_runner import checkpoint_host

class DynamicsContinuationContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def parent(self):
  self.s.setting_set({'key':'openmmPython','value':os.sys.executable})
  with patch.object(self.s,'spawn',side_effect=lambda job,mode:job):job=self.s.dispatch('dynamics_start',{'projectId':self.project['id'],'structureId':self.record['id'],'steps':20,'reportInterval':5})
  folder=self.s.root/'jobs'/job['id'];artifacts={}
  for name in ('prepared.pdb','minimized.pdb','trajectory.pdb','system.xml','integrator.xml','final-state.xml','checkpoint.chk'):
   raw=('Synthetic queue receipt fixture · '+name).encode();(folder/name).write_bytes(raw);artifacts[name]=hashlib.sha256(raw).hexdigest()
  receipt={'state':'completed_pilot','requestSha256':job['data']['requestSha256'],'runnerSha256':job['data']['runnerSha256'],'inputSha256':job['data']['source']['sha256'],'checkpointHost':checkpoint_host(),'artifacts':artifacts};(folder/'result.json').write_text(json.dumps(receipt));self.s.job_update(job['id'],'completed',{'receiptSha256':hashlib.sha256((folder/'result.json').read_bytes()).hexdigest()});return self.s.job(job['id'])
 def payload(self,parent,**extra):return {'projectId':self.project['id'],'parentJobId':parent['id'],'steps':20,'reportInterval':5,**extra}
 def submit(self,payload):
  with patch.object(self.s,'spawn',side_effect=lambda job,mode:job):return self.s.dispatch('dynamics_continue',payload)
 def test_snapshot_pins_exact_parent_and_queue_is_separate_and_cancellable(self):
  parent=self.parent();folder=self.s.root/'jobs'/parent['id'];before={p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()};child=self.submit(self.payload(parent));self.assertNotEqual(parent['id'],child['id']);self.assertEqual(child['data']['parentJobId'],parent['id']);self.assertNotIn('seed',child['data']['request']);snap=self.s.root/'jobs'/child['id']/'restart'
  for name,digest in child['data']['request']['restartFiles'].items():self.assertEqual((snap/name).read_bytes(),before[name]);self.assertEqual(hashlib.sha256((snap/name).read_bytes()).hexdigest(),digest)
  self.assertEqual(self.s.job(parent['id']),parent);self.assertEqual({p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()},before)
  with self.assertRaisesRegex(ValueError,'Another local compute'):self.submit(self.payload(parent))
  self.s.dispatch('job_cancel',{'id':child['id']});self.assertEqual(self.s.job(child['id'])['state'],'cancelled');self.assertEqual(self.s.job(parent['id']),parent);self.assertEqual(len(self.s.library({})['records']),1)
 def test_changed_artifact_or_request_is_refused_without_another_job(self):
  for name in ('checkpoint.chk','system.xml','request.json','input.pdb','result.json'):
   with self.subTest(name=name):
    parent=self.parent();folder=self.s.root/'jobs'/parent['id'];(folder/name).write_bytes(b'altered');count=len(self.s.library({})['jobs'])
    with self.assertRaisesRegex(ValueError,'checksum.*changed'):self.submit(self.payload(parent))
    self.assertEqual(len(self.s.library({})['jobs']),count)
 def test_methods_seed_bad_bounds_and_cross_project_are_refused(self):
  parent=self.parent();other=self.s.project_create({'name':'Other'})
  for extra in ({'seed':7},{'temperature':300},{'platform':'Metal'},{'steps':True},{'steps':5001},{'steps':20,'reportInterval':3},{'name':'bad\nname'},{'projectId':other['id']}):
   with self.subTest(extra=extra),self.assertRaises(ValueError):self.submit(self.payload(parent,**extra))
  self.assertEqual(len(self.s.library({})['jobs']),1)
 def test_old_or_different_host_provenance_is_not_invented(self):
  parent=self.parent();path=self.s.root/'jobs'/parent['id']/'result.json';receipt=json.loads(path.read_text());receipt.pop('checkpointHost');path.write_text(json.dumps(receipt));self.s.job_update(parent['id'],'completed',{'receiptSha256':hashlib.sha256(path.read_bytes()).hexdigest()})
  with self.assertRaisesRegex(ValueError,'provenance is absent or differs'):self.submit(self.payload(parent))
 def test_snapshot_corruption_fails_with_no_partial_outputs(self):
  parent=self.parent();child=self.submit(self.payload(parent));request=self.s.root/'jobs'/child['id']/'request.json';request.write_text('{}')
  with patch.object(dynamics.subprocess,'run') as process:dynamics.run(self.s,child['id']);process.assert_not_called()
  self.assertEqual(self.s.job(child['id'])['state'],'failed');self.assertEqual(self.s.job(parent['id']),parent);self.assertEqual(len(self.s.library({})['records']),1)

del Fixtures
