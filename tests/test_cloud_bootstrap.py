"""Bounded setup dispatch fixtures; never download weights or call a provider."""
import pathlib,sys,tempfile,unittest,subprocess
from unittest.mock import patch,Mock
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'remote_worker'))
from fold_rapid import bootstrap

class BootstrapTests(unittest.TestCase):
    def test_timeout_reaps_installer_process_group_before_returning(self):
        child=Mock(pid=54321);child.wait.side_effect=[subprocess.TimeoutExpired('fixture',1),-9]
        with patch.object(bootstrap.subprocess,'Popen',return_value=child) as spawn,patch.object(bootstrap.os,'killpg') as kill:
            with self.assertRaises(subprocess.TimeoutExpired):bootstrap.execute(['fixture'],Mock(),1)
            self.assertTrue(spawn.call_args.kwargs['start_new_session']);kill.assert_called_once_with(child.pid,bootstrap.signal.SIGKILL)
            self.assertEqual(child.wait.call_count,2)
    def test_reviewed_plan_never_downloads_esm_or_boltzgen_weights(self):
        plan=bootstrap.describe(bootstrap.PLAN)
        self.assertFalse(plan['gpuComputation'])
        self.assertEqual([e for k,e in bootstrap.STEPS if k=='models'],['bindcraft2','solublempnn'])
        with self.assertRaises(ValueError):bootstrap.describe('everything')
    def test_approval_precedes_any_subprocess(self):
        with tempfile.TemporaryDirectory() as root,patch.object(bootstrap,'require_cloud'),patch.object(bootstrap,'execute') as execute:
            with self.assertRaises(ValueError):bootstrap.run(root,bootstrap.PLAN,'stable')
            execute.assert_not_called();self.assertFalse(list(pathlib.Path(root).iterdir()))
    def test_stops_at_first_failure_and_reconnect_does_not_resubmit(self):
        with tempfile.TemporaryDirectory() as root,patch.object(bootstrap,'require_cloud'),patch.object(bootstrap,'execute',return_value=1) as execute:
            row=bootstrap.run(root,bootstrap.PLAN,'stable',True)
            self.assertEqual(row['state'],'failed');self.assertEqual(len(row['steps']),1)
            self.assertFalse(row['automaticRetry']);self.assertTrue((pathlib.Path(root)/row['steps'][0]['logArtifact']).is_file())
            self.assertEqual(bootstrap.run(root,bootstrap.PLAN,'stable',True),row);self.assertEqual(execute.call_count,1)
    def test_timeout_is_recorded_before_provider_deadline(self):
        with tempfile.TemporaryDirectory() as root,patch.object(bootstrap,'require_cloud'),patch.object(bootstrap,'execute',side_effect=bootstrap.subprocess.TimeoutExpired('fixture',1)) as execute:
            row=bootstrap.run(root,bootstrap.PLAN,'stable',True)
            self.assertEqual(row['state'],'failed');self.assertEqual(row['steps'][0]['state'],'failed')
            self.assertLessEqual(execute.call_args.kwargs['timeout'],1680)
    def test_sequential_plan_commits_each_finished_step(self):
        observations=[]
        with tempfile.TemporaryDirectory() as root,patch.object(bootstrap,'require_cloud'),patch.object(bootstrap,'execute',return_value=0) as execute,patch('fold_rapid.registry.inventory',return_value={'fixture':True}):
            row=bootstrap.run(root,bootstrap.PLAN,'stable',True,lambda r:observations.append(r['state']))
            self.assertEqual(row['state'],'models_cached_gpu_validation_pending');self.assertFalse(row['scientificQualified'])
            self.assertEqual(execute.call_count,4);self.assertEqual(observations[-1],row['state'])
            self.assertTrue(all(s['state']=='installed' for s in row['steps']))
    def test_fresh_provider_child_loads_portable_contract_before_dispatch(self):
        code="""
import pathlib,sys,tempfile,os
sys.path.insert(0,sys.argv[1]+'/scientific')
from worker import Service
with tempfile.TemporaryDirectory() as folder:
 s=Service(pathlib.Path(folder));project=s.project_create({'name':'Fixture'})['id']
 s.dispatch('biology_modal_configure',{'projectId':project,'configuration':{'appName':'fixture','imageRecipe':'rapid-cuda13-core-v1','gpu':'A100-80GB','maxSeconds':600,'hourlyEstimateUSD':2.4984}})
 sys.path.remove(sys.argv[1]+'/remote_worker')
 for name in list(sys.modules):
  if name=='fold_rapid' or name.startswith('fold_rapid.'):del sys.modules[name]
 os.environ['FOLD_PROVIDER_CHILD']='1'
 try:s.dispatch('biology_cloud_prepare_models',{'projectId':project,'plan':'unreviewed','approvedCPUSetup':True,'approvedModelDownloads':True,'maxApprovedUSD':1})
 except ValueError as exc:assert 'Unknown reviewed' in str(exc),str(exc)
 else:raise AssertionError('Unknown plan must never dispatch')
 assert not s.rows('SELECT * FROM biology_modal_jobs');s.db.close()
"""
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(ROOT)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
