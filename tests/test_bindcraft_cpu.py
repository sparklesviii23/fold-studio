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
