"""Large synthetic logs exercise native progress transport, not model outputs."""
import json
import unittest
from test_project_metal import ProjectMetalTests as Fixtures


class CampaignProgressWindow(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 prepared=Fixtures.prepared

 def read(self,text):
  job=self.prepared();path=self.s.root/'jobs'/job['id']/'execution.log';path.write_text(text)
  return self.s.job_read({'id':job['id']})

 def test_long_fab_telemetry_keeps_trajectory_context_beyond_visible_log(self):
  update={'stage':'screen','sequenceUpdates':20,'metrics':{'fixture':.5}}
  text='FOLD_CAMPAIGN_RUN {"fixture":true}\n=== trajectory 1 | protocol_only | accepted 0/1 ===\n'
  text+=('FOLD_AMME '+json.dumps({'stage':'gradient_execution','scope':'synthetic telemetry padding'})+'\n')*500
  text+='FOLD_PROGRESS '+json.dumps(update)+'\n'
  result=self.read(text);progress=result['data']['executionProgress']
  self.assertNotIn('=== trajectory',result['log']);self.assertLessEqual(len(result['log'].encode()),30000)
  self.assertEqual(progress['trajectory'],1);self.assertEqual(progress['lastObservedUpdate'],update)
  self.assertIsNone(progress['percent'])

 def test_new_run_marker_does_not_reuse_an_older_trajectory_after_recovery(self):
  text='FOLD_CAMPAIGN_RUN {}\n=== trajectory 2 | spent | accepted 0/1 ===\nrejected at anneal design stage\n'
  text+='synthetic padding\n'*2500+'FOLD_CAMPAIGN_RUN {"recoveryNumber":1}\ninitializing original models\n'
  result=self.read(text)['data']['executionProgress']
  self.assertNotIn('trajectory',result);self.assertNotIn('lastReportedStage',result)

 def test_unavailable_context_beyond_bound_is_unreported_instead_of_inferred(self):
  text='=== trajectory 1 | beyond_bound | accepted 0/1 ===\n'+('bounded noise\n'*90000)
  result=self.read(text)
  self.assertNotIn('trajectory',result['data']['executionProgress']);self.assertLessEqual(len(result['log'].encode()),30000)


del Fixtures
