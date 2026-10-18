"""Shared job bookkeeping must preserve independently completed worker results."""
import types,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures,w

class JobMetadataContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def test_fast_child_completion_is_preserved_when_spawn_attaches_pid(self):
  job=self.s.job_new({'projectId':self.project['id'],'name':'Fast child fixture'},'rdkit','queued')
  def completed_child(*args,**kwargs):
   peer=w.Service(self.s.root)
   try:peer.job_update(job['id'],'completed',{'outputs':['synthetic-result'],'finished':'test-finish'})
   finally:peer.db.close()
   return types.SimpleNamespace(pid=12345)
  statements=[];self.s.db.set_trace_callback(statements.append)
  with patch.object(w.subprocess,'Popen',side_effect=completed_child):result=self.s.spawn(job,'--ligand-job')
  self.assertEqual(result['state'],'completed');self.assertEqual(result['data']['outputs'],['synthetic-result']);self.assertEqual(result['data']['finished'],'test-finish');self.assertEqual(result['data']['pid'],12345)
  updates=[q for q in statements if q.startswith('UPDATE jobs')]
  self.assertEqual(len(updates),1);self.assertNotIn('state=',updates[0]);self.assertIn('BEGIN IMMEDIATE',statements)
 def test_invalid_metadata_rolls_back_and_leaves_job_usable(self):
  job=self.s.job_new({'projectId':self.project['id']},'rdkit','completed')
  with self.assertRaises(TypeError):self.s.job_metadata(job['id'],{'bad':object()})
  self.assertFalse(self.s.db.in_transaction);self.assertNotIn('bad',self.s.job(job['id'])['data']);self.s.job_metadata(job['id'],{'pid':7});self.assertEqual(self.s.job(job['id'])['state'],'completed')
del Fixtures
