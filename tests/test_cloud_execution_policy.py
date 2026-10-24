"""Cloud mode must fail before any local scientific function can run."""
import copy,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'remote_worker'),str(ROOT/'tests')]
import worker,execution_policy
from fold_rapid.execution import require_cloud
from fold_rapid.unified import CampaignStore,run
from fold_rapid.api import Worker
from test_unified_campaign import fixture

class ClientFirewallTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.s=worker.Service(pathlib.Path(self.tmp.name));self.s.dispatch('execution_backend_select',{'mode':'modal'})
    def tearDown(self):self.s.db.close();self.tmp.cleanup()
    def test_all_registered_scientific_actions_fail_before_local_dispatch(self):
        for action in execution_policy.LOCAL_SCIENCE & worker.ACTIONS:
            with self.subTest(action=action),self.assertRaisesRegex(ValueError,'prohibits local'):self.s.dispatch(action,{})
    def test_mpnn_never_receives_cloud_request(self):
        with patch('mpnn.dispatch',side_effect=AssertionError('Local model must never be reached')) as local:
            with self.assertRaisesRegex(ValueError,'Cloud Mode'):self.s.dispatch('mpnn_start',{'executionMode':'local'})
            local.assert_not_called()
    def test_no_provider_fallback_after_network_error(self):
        import biology_modal
        with patch.object(biology_modal,'dispatch',side_effect=ConnectionError('provider unavailable')),patch('mpnn.dispatch') as local:
            with self.assertRaises(ConnectionError):self.s.dispatch('biology_modal_submit',{})
            local.assert_not_called()
    def test_client_library_and_file_edits_still_allowed(self):
        self.assertIsInstance(self.s.dispatch('library',{}),dict);self.assertEqual(self.s.dispatch('fasta_parse',{'text':'>candidate\nACDE'}),[{'name':'candidate','sequence':'ACDE'}])
    def test_local_mode_explicitly_restores_native_dispatch(self):
        self.s.dispatch('execution_backend_select',{'mode':'local'})
        with patch('mpnn.dispatch',return_value={'native':True}) as local:self.assertTrue(self.s.dispatch('mpnn_start',{})['native']);local.assert_called_once()
    def test_cloud_payload_cannot_bypass_local_setting(self):
        self.s.dispatch('execution_backend_select',{'mode':'local'})
        with self.assertRaisesRegex(ValueError,'Cloud Mode'):self.s.dispatch('mpnn_start',{'executionMode':'cloud'})
    def test_switch_rejected_while_local_worker_active(self):
        with patch.object(self.s,'active',return_value=True),self.assertRaisesRegex(ValueError,'active local'):self.s.dispatch('execution_backend_select',{'mode':'local'})
    def test_native_rust_and_packaging_registration(self):
        rust=(ROOT/'src-tauri/src/main.rs').read_text();resources=json.loads((ROOT/'src-tauri/tauri.conf.json').read_text())['bundle']['resources']
        for action in execution_policy.ACTIONS:self.assertIn(action,worker.ACTIONS);self.assertIn('"'+action+'"',rust)
        self.assertIn('../scientific/execution_policy.py',resources)

class RemoteBoundaryTests(unittest.TestCase):
    def policy(self,**extra):return {'mode':'cloud','provider':'modal','localFallback':False,**extra}
    def test_mac_rejected_before_controller_science(self):
        with patch('platform.system',return_value='Darwin'),self.assertRaisesRegex(ValueError,'Mac'):require_cloud(self.policy())
    def test_different_provider_rejected(self):
        with patch('platform.system',return_value='Linux'),patch.dict('os.environ',{'FOLD_COMPUTE_PROVIDER':'vast'}),self.assertRaisesRegex(ValueError,'differs'):require_cloud(self.policy())
    def test_remote_location_receipt(self):
        with patch('platform.system',return_value='Linux'),patch.dict('os.environ',{'FOLD_COMPUTE_PROVIDER':'modal'}):
            receipt=require_cloud(self.policy());self.assertEqual(receipt['controllerLocation'],'remote');self.assertFalse(receipt['localFallback']);self.assertTrue(receipt['hostname'])
    def test_fallback_policy_rejected(self):
        with self.assertRaises(ValueError):require_cloud(self.policy(localFallback=True))
    def test_remote_submission_cannot_be_used_as_local_workaround(self):
        with tempfile.TemporaryDirectory() as folder:
            v=fixture();v['execution']=self.policy()
            with patch('platform.system',return_value='Darwin'),self.assertRaises(ValueError):Worker(folder).unified_submit({'manifest':v,'idempotencyKey':'x','approvedResearchTransfer':True,'approvedWorkload':True})
    def test_durable_controller_rejects_mac_without_calling_executor(self):
        with tempfile.TemporaryDirectory() as folder:
            v=fixture();v['execution']=self.policy();store=CampaignStore(folder);id=store.submit(v,'cloud-on-mac',True)['campaignId']
            with patch('platform.system',return_value='Darwin'),patch('fold_rapid.unified.LocalStages.__call__',side_effect=AssertionError('No native science')) as compute:
                out=run(folder,id);self.assertEqual(out['state'],'FAILED');compute.assert_not_called()

if __name__=='__main__':unittest.main()
