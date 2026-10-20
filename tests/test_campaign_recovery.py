"""Recovery persistence/guard contracts; fixture states are explicitly synthetic."""
import json,os,pathlib,unittest,zipfile
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures,w
import campaign_recovery as cr
import fold_engine as fe
from bindcraft_cpu import execution_config,progress_from_log

class CampaignRecoveryContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def parent(self):
  job=self.prepared();folder=self.s.root/'jobs'/job['id'];config,_=execution_config(job['data']['preparation']['config'],folder);(folder/'execution-settings.json').write_text(json.dumps(config));(folder/'output').mkdir();(folder/'output/.campaign_state.json').write_text(json.dumps({'trajectories':1,'accepted':0,'attempted':['synthetic-claimed-recipe']}));(folder/'execution.log').write_text('Synthetic log only\n');(folder/'runtime-provenance.json').write_text(json.dumps({'execution':'cpu','precision':'upstream','jax':'fixture','jaxlib':'fixture','upstreamSource':fe.verify_source()}));self.s.job_update(job['id'],'cancelled',{'executionSettingsSha256':fe.checksum(fe.canonical(config).encode()),'profile':'experimental-cpu-single-model','execution':'cpu','precision':'upstream','outputs':[]});return self.s.job(job['id'])
 prepared=Fixtures.prepared
 def payload(self,job,**extra):return {'id':job['id'],'projectId':self.project['id'],**extra}
 def test_archive_keeps_exact_receipts_job_state_and_output_manifest(self):
  job=self.parent();folder=self.s.root/'jobs'/job['id'];before={str(p.relative_to(folder)):p.read_bytes() for p in folder.rglob('*') if p.is_file()};recovery=cr.prepare(self.engine,self.payload(job));cr.verify_manifest(folder,recovery);saved=cr.archive(folder,recovery);receipt=folder/saved['folder']/'receipt.json';self.assertEqual(fe.checksum(receipt.read_bytes()),saved['receiptSha256']);self.assertEqual(json.loads(receipt.read_text())['job'],job);self.assertEqual(self.s.job(job['id']),job)
  for name,raw in before.items():self.assertEqual((folder/name).read_bytes(),raw)
  self.assertEqual((receipt.parent/'execution-settings.json').read_bytes(),before['execution-settings.json']);archive=self.base/'recovery.zip';self.s.export_project({'id':self.project['id'],'path':str(archive)})
  with zipfile.ZipFile(archive) as z:self.assertEqual(z.read('jobs/'+job['id']+'/'+saved['folder']+'/receipt.json'),receipt.read_bytes())
 def test_unknown_options_changed_settings_or_wrong_project_are_refused(self):
  job=self.parent()
  for extra in ({'seed':12},{'ignore_filters':True},{'profile':'metal'},{'projectId':self.s.project_create({'name':'Other'})['id']}):
   with self.subTest(extra=extra),self.assertRaises(ValueError):cr.prepare(self.engine,self.payload(job,**extra))
  (self.s.root/'jobs'/job['id']/'execution-settings.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'settings changed'):cr.prepare(self.engine,self.payload(job))
 def test_finished_or_exhausted_attempts_and_missing_progress_never_restart(self):
  job=self.parent();folder=self.s.root/'jobs'/job['id']
  for state in ({'trajectories':4,'accepted':0},{'trajectories':1,'accepted':2},{'trajectories':True,'accepted':0}):
   (folder/'output/.campaign_state.json').write_text(json.dumps(state))
   with self.subTest(state=state),self.assertRaises(ValueError):cr.prepare(self.engine,self.payload(job))
  (folder/'output/.campaign_state.json').unlink()
  with self.assertRaisesRegex(ValueError,'No upstream campaign progress'):cr.prepare(self.engine,self.payload(job))
  self.s.job_update(job['id'],'completed')
  with self.assertRaisesRegex(ValueError,'interrupted, cancelled or failed'):cr.prepare(self.engine,self.payload(job))
 def test_live_original_process_group_prevents_output_writes(self):
  job=self.parent();self.s.job_metadata(job['id'],{'pid':4242})
  with patch.object(cr.subprocess,'check_output',return_value=' 8888 4242 python bindcraft_runner.py /jobs/'+job['id']+'/execution-settings.json'):
   with self.assertRaisesRegex(ValueError,'still stopping'):cr.prepare(self.engine,self.payload(job))
  self.assertFalse((self.s.root/'jobs'/job['id']/'recovery').exists())
 def test_output_tampering_or_symlinks_cannot_enter_resume(self):
  job=self.parent();folder=self.s.root/'jobs'/job['id'];recovery=cr.prepare(self.engine,self.payload(job));(folder/'output/new.csv').write_text('changed')
  with self.assertRaisesRegex(ValueError,'output changed'):cr.verify_manifest(folder,recovery)
  (folder/'output/escape').symlink_to(self.file)
  with self.assertRaisesRegex(ValueError,'symlinks'):cr.prepare(self.engine,self.payload(job))
 def test_new_run_marker_does_not_show_old_stage_as_current(self):
  log='=== trajectory 1 | first | accepted 0/2 ===\n passed screen design stage\nFOLD_CAMPAIGN_RUN {"recoveryNumber":1}\n'
  self.assertNotIn('trajectory',progress_from_log(log));self.assertNotIn('lastReportedStage',progress_from_log(log));self.assertEqual(progress_from_log(log+'=== trajectory 3 | third | accepted 0/2 ===\n')['trajectory'],3)
 def test_registration_keeps_recovery_available_to_the_packaged_app(self):
  root=pathlib.Path(w.__file__).parents[1];self.assertIn('bindcraft_resume',fe.ACTIONS);self.assertIn('"bindcraft_resume"',(root/'src-tauri/src/main.rs').read_text());self.assertIn('../scientific/campaign_recovery.py',json.loads((root/'src-tauri/tauri.conf.json').read_text())['bundle']['resources'])
 def test_original_package_startup_flags_are_compared_after_import(self):
  from amme_campaign import environment,SCHEDULER_FLAG
  before=dict(os.environ);env={k:v for k,v in before.items() if k not in ('XLA_FLAGS','BC2_XLA_EXTRA')}
  flags=cr.effective_fab_compiler_flags(os.path.abspath(os.sys.executable),fe.UPSTREAM,env)
  self.assertEqual(flags,SCHEDULER_FLAG+' --xla_gpu_enable_triton_gemm=false')
  self.assertEqual(dict(os.environ),before)
  changed=cr.effective_fab_compiler_flags(os.path.abspath(os.sys.executable),fe.UPSTREAM,{**env,'BC2_XLA_EXTRA':'--xla_cpu_parallel_codegen_split_count=2'})
  self.assertNotEqual(changed,flags)
  self.assertTrue(changed.endswith('--xla_cpu_parallel_codegen_split_count=2'))
del Fixtures
