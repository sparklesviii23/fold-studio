"""Model-pool orchestration guards; fixtures are metadata, never predictions."""
import json,unittest
from types import SimpleNamespace
from unittest.mock import patch
from test_project_metal import w
import campaign_profile

class CampaignProfileTests(unittest.TestCase):
 def result(self,design,validation):return SimpleNamespace(returncode=0,stdout=json.dumps({'designModels':design,'validationModels':validation,'validationPoolExhausted':False}),stderr='')
 def test_overlapping_validation_cannot_be_promoted(self):
  with patch.object(campaign_profile.subprocess,'run',return_value=self.result(['model_1_multimer_v3'],['model_1_multimer_v3'])):
   with self.assertRaisesRegex(ValueError,'distinct'):campaign_profile.ensemble_models('/test/python',{},'/test/source')
 def test_failed_upstream_resolution_is_explicit(self):
  with patch.object(campaign_profile.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='',stderr='upstream preflight error')):
   with self.assertRaisesRegex(ValueError,'Upstream ensemble selection failed'):campaign_profile.ensemble_models('/test/python',{},'/test/source')
 def test_metadata_probe_isolated_to_cpu_and_cannot_write_bytecode(self):
  config={'campaign_seed':2718,'filters':{'i_pTM':{'threshold':.7}}}
  with patch.object(campaign_profile.subprocess,'run',return_value=self.result(['model_1_multimer_v3'],['model_2_multimer_v3'])) as run:
   result=campaign_profile.ensemble_models('/test/python',config,'/test/source')
  self.assertEqual(result['validationModels'],['model_2_multimer_v3']);self.assertEqual(json.loads(run.call_args.args[0][-2]),config);self.assertEqual(run.call_args.kwargs['env']['JAX_PLATFORMS'],'cpu');self.assertEqual(run.call_args.kwargs['env']['PYTHONDONTWRITEBYTECODE'],'1')
