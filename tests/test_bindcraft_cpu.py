"""CPU campaign launch guards; no mock model outputs presented as calculations."""
import os,pathlib,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures
class CPUCampaignGuards(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 prepared=Fixtures.prepared
 # Reuse isolated fixtures, not the other class's complete test methods.
 def test_requires_explicit_experimental_profile(self):
  j=self.prepared()
  with self.assertRaisesRegex(ValueError,'blocked'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':j['id']})
  self.assertEqual(self.s.job(j['id'])['state'],'prepared')
 def test_refuses_missing_parameters_without_spawning(self):
  j=self.prepared()
  with patch.dict(os.environ,{'FOLD_BINDCRAFT_PYTHON':os.sys.executable,'FOLD_AF2_PARAMETERS':str(self.base/'missing')}),patch.object(self.s,'spawn') as spawn:
   with self.assertRaisesRegex(ValueError,'Missing genuine'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':j['id'],'profile':'experimental-cpu-single-model'})
   spawn.assert_not_called()
  self.assertEqual(self.s.job(j['id'])['state'],'prepared')
 def test_finished_campaign_cannot_rerun(self):
  j=self.prepared();self.s.job_update(j['id'],'completed')
  with self.assertRaisesRegex(ValueError,'unexecuted'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':j['id'],'profile':'experimental-cpu-single-model'})
 def test_unsupported_launch_options_refused(self):
  j=self.prepared()
  with self.assertRaisesRegex(ValueError,'Unsupported'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':j['id'],'profile':'experimental-cpu-single-model','ignore_filters':True})
del Fixtures

class UpstreamProgress(unittest.TestCase):
 def test_no_fake_percent_or_stage_from_starting_text(self):
  from bindcraft_cpu import progress_from_log
  p=progress_from_log('Starting computation...');self.assertIsNone(p['percent']);self.assertNotIn('lastReportedStage',p)
 def test_stage_and_trajectory_are_derived_from_actual_events(self):
  from bindcraft_cpu import progress_from_log
  log='=== trajectory 2 | design_l60_abc | accepted 0/1 ===\n passed screen design stage  i_pTM=0.2\n rejected at anneal design stage i_pTM=0.01 due to [i_pTM]\n'
  p=progress_from_log(log);self.assertEqual(p['trajectory'],2);self.assertEqual(p['lastReportedStage'],'anneal');self.assertEqual(p['stageOutcome'],'rejected');self.assertIsNone(p['percent'])
 def test_new_trajectory_does_not_reuse_old_stage_result(self):
  from bindcraft_cpu import progress_from_log
  p=progress_from_log('=== trajectory 1 | design_a | accepted 0/1 ===\n passed screen design stage\n=== trajectory 2 | design_b | accepted 0/1 ===\n')
  self.assertEqual(p['trajectory'],2);self.assertNotIn('lastReportedStage',p)
