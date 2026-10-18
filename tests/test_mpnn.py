"""Contract tests for real-model workflow; no simulated model outputs."""
import json,os,pathlib,tempfile,unittest
from unittest.mock import patch
from test_project_metal import w,pdb
class MPNNTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=w.Service(self.tmp.name);self.project=self.s.project_create({'name':'MPNN'});f=pathlib.Path(self.tmp.name)/'source.pdb';f.write_text(pdb());self.record=self.s.import_structure({'projectId':self.project['id'],'path':str(f)});self.p={'projectId':self.project['id'],'structureId':self.record['id'],'designChains':['A'],'count':2,'seed':2718}
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def test_invalid_settings_and_chains_rejected(self):
  for key,value in [('designChains',[]),('designChains',['B']),('count',True),('seed',-1),('temperature',float('nan')),('variant','fake'),('unknown',1)]:
   with self.subTest(key=key),self.assertRaises(ValueError):self.s.dispatch('mpnn_start',{**self.p,key:value})
 def test_runtime_missing_explicit(self):
  with patch.dict(os.environ,{'FOLD_BINDCRAFT_PYTHON':'/missing/python'}),self.assertRaisesRegex(ValueError,'runtime unavailable'):self.s.dispatch('mpnn_start',self.p)
 def test_snapshot_and_queue_rejects_concurrent_prediction(self):
  with patch.dict(os.environ,{'FOLD_BINDCRAFT_PYTHON':os.sys.executable}),patch.object(self.s,'spawn',side_effect=lambda j,mode:j):
   job=self.s.dispatch('mpnn_start',self.p);self.assertEqual(job['engine'],'proteinmpnn');self.assertTrue(self.s.active());self.assertEqual((self.s.root/'jobs'/job['id']/'input.pdb').read_text(),pdb())
   with self.assertRaisesRegex(ValueError,'active'):self.s.dispatch('mpnn_start',self.p)
 def test_failed_runtime_cannot_import_or_complete(self):
  with patch.dict(os.environ,{'FOLD_BINDCRAFT_PYTHON':os.sys.executable}),patch.object(self.s,'spawn',side_effect=lambda j,mode:j):job=self.s.dispatch('mpnn_start',self.p)
  with patch.object(w.mpnn.subprocess,'run',side_effect=RuntimeError('runtime failure')):w.mpnn.run(self.s,job['id'])
  self.assertEqual(self.s.job(job['id'])['state'],'failed');self.assertFalse(self.s.job(job['id'])['data']['outputs']);self.assertEqual(len(self.s.library({})['records']),1)
 def test_cancelled_job_is_not_reexecuted(self):
  with patch.dict(os.environ,{'FOLD_BINDCRAFT_PYTHON':os.sys.executable}),patch.object(self.s,'spawn',side_effect=lambda j,mode:j):job=self.s.dispatch('mpnn_start',self.p)
  self.s.job_cancel({'id':job['id']})
  with self.assertRaises(ValueError):w.mpnn.run(self.s,job['id'])
 def test_jobs_persist_and_native_actions_are_registered(self):
  self.assertEqual(self.s.dispatch('mpnn_jobs',{'projectId':self.project['id']}),[])
  for a in w.mpnn.ACTIONS:self.assertIn(a,w.ACTIONS);self.assertIn('"'+a+'"',(pathlib.Path(w.__file__).parents[1]/'src-tauri/src/main.rs').read_text())

 def test_virtual_environment_interpreter_symlink_is_preserved(self):
  interpreter=pathlib.Path(self.tmp.name)/'venv/bin/python';interpreter.parent.mkdir(parents=True);interpreter.symlink_to(os.sys.executable)
  with patch.dict(os.environ,{'FOLD_BINDCRAFT_PYTHON':str(interpreter)}),patch.object(self.s,'spawn',side_effect=lambda j,mode:j):job=self.s.dispatch('mpnn_start',self.p)
  self.assertEqual(job['data']['runtime'],str(interpreter))
