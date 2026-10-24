"""Bounded setup dispatch fixtures; never download weights or call a provider."""
import pathlib,sys,tempfile,unittest
from unittest.mock import patch,Mock
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'remote_worker'))
from fold_rapid import bootstrap

class BootstrapTests(unittest.TestCase):
    def test_reviewed_plan_never_downloads_esm_or_boltzgen_weights(self):
        plan=bootstrap.describe(bootstrap.PLAN)
        self.assertFalse(plan['gpuComputation'])
        self.assertEqual([e for k,e in bootstrap.STEPS if k=='models'],['bindcraft2','solublempnn'])
        with self.assertRaises(ValueError):bootstrap.describe('everything')
    def test_approval_precedes_any_subprocess(self):
        with tempfile.TemporaryDirectory() as root,patch.object(bootstrap,'require_cloud'),patch.object(bootstrap.subprocess,'run') as execute:
            with self.assertRaises(ValueError):bootstrap.run(root,bootstrap.PLAN,'stable')
            execute.assert_not_called();self.assertFalse(list(pathlib.Path(root).iterdir()))
    def test_stops_at_first_failure_and_reconnect_does_not_resubmit(self):
        with tempfile.TemporaryDirectory() as root,patch.object(bootstrap,'require_cloud'),patch.object(bootstrap.subprocess,'run',return_value=Mock(returncode=1)) as execute:
            row=bootstrap.run(root,bootstrap.PLAN,'stable',True)
            self.assertEqual(row['state'],'failed');self.assertEqual(len(row['steps']),1)
            self.assertFalse(row['automaticRetry']);self.assertTrue((pathlib.Path(root)/row['steps'][0]['logArtifact']).is_file())
            self.assertEqual(bootstrap.run(root,bootstrap.PLAN,'stable',True),row);self.assertEqual(execute.call_count,1)
    def test_timeout_is_recorded_before_provider_deadline(self):
        with tempfile.TemporaryDirectory() as root,patch.object(bootstrap,'require_cloud'),patch.object(bootstrap.subprocess,'run',side_effect=bootstrap.subprocess.TimeoutExpired('fixture',1)) as execute:
            row=bootstrap.run(root,bootstrap.PLAN,'stable',True)
            self.assertEqual(row['state'],'failed');self.assertEqual(row['steps'][0]['state'],'failed')
            self.assertLessEqual(execute.call_args.kwargs['timeout'],1680)
    def test_sequential_plan_commits_each_finished_step(self):
        observations=[]
        with tempfile.TemporaryDirectory() as root,patch.object(bootstrap,'require_cloud'),patch.object(bootstrap.subprocess,'run',return_value=Mock(returncode=0)) as execute,patch('fold_rapid.registry.inventory',return_value={'fixture':True}):
            row=bootstrap.run(root,bootstrap.PLAN,'stable',True,lambda r:observations.append(r['state']))
            self.assertEqual(row['state'],'models_cached_gpu_validation_pending');self.assertFalse(row['scientificQualified'])
            self.assertEqual(execute.call_count,4);self.assertEqual(observations[-1],row['state'])
            self.assertTrue(all(s['state']=='installed' for s in row['steps']))

if __name__=='__main__':unittest.main()
