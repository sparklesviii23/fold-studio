"""Stage inspection, snapshot and mutation guards; fixture rows are not computations."""
import json,os,pathlib,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures,w
from campaign_review import manifest
import campaign_review
class CampaignReviewContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 prepared=Fixtures.prepared
 result_folder=Fixtures.result_folder
 def source(self):
  self.s.setting_set({'key':'bindcraftPython','value':os.sys.executable});job=self.prepared();output=self.s.root/'jobs'/job['id']/'output';(output/'1_Trajectories').mkdir(parents=True);(output/'1_Trajectories/!_Trajectories.csv').write_text('design,trajectory,terminated\nsynthetic1,1,screen\n');(output/'.campaign_state.json').write_text(json.dumps({'trajectories':2,'accepted':0}));return job,output
 def payload(self,job,**extra):return {'projectId':self.project['id'],'id':job['id'],**extra}
 def test_claimed_interrupted_attempt_and_completed_row_are_distinct(self):
  job,output=self.source();r=self.s.dispatch('bindcraft_results',self.payload(job));self.assertEqual(r['tables']['trajectories']['count'],1);self.assertEqual(r['claimedProgress']['trajectories'],2);self.assertEqual(r['tables']['candidates']['count'],0);self.assertEqual(r['tables']['trajectories']['rows'][0]['terminated'],'screen');self.assertNotIn('pLDDT',r['tables']['trajectories']['rows'][0]);self.assertIn('synthetic1',r['tables']['trajectories']['csv'])
 def test_unknown_fields_missing_rows_or_live_campaign_cannot_review(self):
  job,_=self.source()
  with patch.object(campaign_review.subprocess,'run') as proc:
   for extra in ({'operation':'invent'},{'operation':'rank','table':[]},{'operation':'filter','ignore_filters':True},{'operation':'rank','metrics':['bad\nmetric']},{'operation':'rank','metrics':[]}):
    with self.subTest(extra=extra),self.assertRaises(ValueError):self.s.dispatch('bindcraft_review',self.payload(job,**extra))
   with self.assertRaisesRegex(ValueError,'Finish or stop'):self.s.dispatch('bindcraft_review',self.payload(job,operation='rank'))
   self.s.job_update(job['id'],'failed')
   with self.assertRaisesRegex(ValueError,'no recorded rows'):self.s.dispatch('bindcraft_review',self.payload(job,operation='rank'))
   proc.assert_not_called()
 def test_snapshot_or_table_symlinks_are_refused(self):
  job,output=self.source();(output/'escape').symlink_to(self.file)
  with self.assertRaisesRegex(ValueError,'symlinks'):manifest(output)
  path=output/'1_Trajectories/!_Trajectories.csv';path.unlink();path.symlink_to(self.file)
  with self.assertRaisesRegex(ValueError,'symlink'):self.s.dispatch('bindcraft_results',self.payload(job))
 def test_an_active_compute_job_prevents_a_review_child_or_partial_analysis(self):
  job,_=self.source();self.s.job_update(job['id'],'failed');self.s.job_new({'projectId':self.project['id']},'bindcraft2','running')
  with patch.object(campaign_review.subprocess,'run') as proc:
   with self.assertRaisesRegex(ValueError,'Another local compute'):self.s.dispatch('bindcraft_review',self.payload(job,operation='rank',table='trajectories'))
   proc.assert_not_called()
  self.assertFalse(self.s.db.in_transaction)
 def test_later_ranking_batches_reuse_existing_coordinate_identity(self):
  job=self.prepared();root=self.result_folder();payload=self.payload(job,directory=str(root));first=self.s.dispatch('bindcraft_import',payload);old=first['records'][0];(root/'3_Ranked/other.pdb').write_text(self.file.read_text().replace('1.450','1.451'));table=root/'3_Ranked/!_Ranked.csv';table.write_text('rank,design,i_pTM\n2,candidate,0.81\n1,other,0.82\n');second=self.s.dispatch('bindcraft_import',payload);self.assertIn(old,second['records']);self.assertEqual(len(second['records']),2);self.assertEqual(len(self.s.job(job['id'])['data']['outputs']),2);self.assertEqual(len(self.s.library({})['records']),3)
  record=next(r for r in self.s.library({})['records'] if r['id']==old);(self.s.root/'assets'/record['data']['asset']).write_bytes(b'corrupt prior coordinate asset');table.write_text(table.read_text().replace('0.82','0.83'))
  with self.assertRaisesRegex(ValueError,'earlier imported campaign coordinate asset changed'):self.s.dispatch('bindcraft_import',payload)
 def test_native_ipc_and_resources_register_actual_original_code_bridge(self):
  root=pathlib.Path(w.__file__).parents[1];native=(root/'src-tauri/src/main.rs').read_text();resources=json.loads((root/'src-tauri/tauri.conf.json').read_text())['bundle']['resources']
  for action in ('bindcraft_results','bindcraft_review'):self.assertIn('"'+action+'"',native)
  for name in ('campaign_review.py','campaign_review_runner.py'):self.assertIn('../scientific/'+name,resources)
del Fixtures
