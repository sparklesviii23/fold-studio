"""Offline contracts and real saved-output readback; no paid model execution."""
import base64,copy,hashlib,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'remote_worker'),str(ROOT/'tests')]
from worker import Service
from fold_rapid.events import normalize,redact,append
from fold_rapid.watchdog import diagnose
from fold_rapid.gpu_profiles import catalog
from fold_rapid.unified import model_manifest
from test_unified_campaign import fixture
from test_biology_pipeline import complex_pdb
import cloud_monitor,cloud_accounts,biology_modal

class CloudCompute5(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.s=Service(self.root);self.project=self.s.project_create({'name':'Cloud synthetic control fixture'})['id'];self.p={'projectId':self.project};biology_modal.table(self.s)
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def row(self):
  row={'id':'r','projectId':self.project,'campaignId':'a'*32,'created':'2026-10-24T10:00:00+00:00','state':'PARTIALLY_COMPLETE','manifest':{},'remote':{'stages':[]},'configuration':{'appName':'fixture-cloud','gpu':'A100-80GB'}};biology_modal.save(self.s,row);return row
 def test_display_never_submits_or_executes_shell(self):
  row=self.row()
  with patch('subprocess.run',side_effect=AssertionError('No subprocess')):
   r=self.s.dispatch('cloud_console',{**self.p,'id':row['id'],'command':'gpu status'});self.assertFalse(r['gpuStarted'])
   for command in ['rm -rf /','$(uname)','campaign stop','cuda validate']:
    with self.assertRaises(ValueError):self.s.dispatch('cloud_console',{**self.p,'id':row['id'],'command':command})
 def test_archive_backfill_cursor_and_no_duplicate(self):
  row=self.row();folder=self.root/'cloud-qualification'/row['campaignId'];job=folder/'stages'/('b'*32)/'jobs'/('c'*32);job.mkdir(parents=True)
  (folder/'campaign.json').write_text(json.dumps({'stages':[{'stageId':'b'*32,'jobId':'c'*32,'engine':'proteinmpnn','started':row['created']}]}));(job/'execution.log').write_text('real fixture line\nAPI_KEY=secret123\nlast line')
  p={**self.p,'id':'r'};r=self.s.dispatch('cloud_campaign_events',p);self.assertEqual(len(r['events']),3);self.assertNotIn('secret123',json.dumps(r));again=self.s.dispatch('cloud_campaign_events',{**p,'after':r['nextCursor']});self.assertEqual(again['events'],[])
 def test_hash_chain_and_redaction(self):
  p=self.root/'events.jsonl';a=append(p,normalize({'message':'token_secret=badsecret'}));b=append(p,normalize({'message':'second'}));self.assertEqual(b['previousHash'],a['eventHash']);self.assertNotIn('badsecret',p.read_text());self.assertEqual(len(p.read_text().splitlines()),2)
 def test_large_unicode_blackbox_tail_keeps_hash_links(self):
  p=self.root/'unicode.jsonl';previous=None
  for i in range(15):
   value=append(p,normalize({'message':str(i)+' Ω'*16000}));self.assertEqual(value['previousHash'],previous);previous=value['eventHash']
  self.assertGreater(p.stat().st_size,262144);self.assertEqual(len(p.read_text().splitlines()),15)
 def test_unknown_vram_and_timeout_do_not_invent_cpu_fallback(self):
  result=diagnose('deadline_exceeded','',probe={'passed':True});self.assertEqual(result['observations'][0]['category'],'stage_timeout');self.assertFalse(result['scientificModelReferenceQualified']);self.assertFalse(result['automaticRetry']);self.assertNotIn('cpu_fallback',json.dumps(result))
 def test_explicit_gpu_catalog_and_b300_incompatibility(self):
  data=catalog();self.assertEqual(len(data['profiles']),11);self.assertIsNone(data['lowestMeasuredCostGPU']);self.assertTrue(all(e['measuredPeakVRAMMiB'] is None for p in data['profiles'] for e in p['engines']));b=next(p for p in data['profiles'] if p['id']=='B300');self.assertEqual(b['engines'][0]['state'],'requires_different_runtime');t=next(p for p in data['profiles'] if p['id']=='T4');self.assertNotEqual(t['engines'][0]['state'],'incompatible')
 def test_seed_dependent_held_out_pool_is_explicit(self):
  v=fixture();node={'candidateId':'d'*64,'sequences':{'A':'ACDE','B':'ACDE'},'binderChains':['B'],'coordinates':v['target'],'af2ModelExposure':{'gradientDesignModels':['model_1_multimer_v3','model_3_multimer_v3','model_4_multimer_v3'],'validationModels':['model_2_multimer_v3','model_5_multimer_v3']}}
  m=model_manifest({'manifest':v},node,'af2_multimer');self.assertEqual(m['biology']['af2']['models'],['model_2_multimer_v3','model_5_multimer_v3'])
  node['af2ModelExposure']['validationModels']=['model_2_multimer_v3','model_4_multimer_v3']
  with self.assertRaisesRegex(ValueError,'overlaps'):model_manifest({'manifest':v},node,'af2_multimer')
 def test_account_switch_preserves_campaign_owner_and_profile(self):
  a='a'*32;b='b'*32;value={'activeId':a,'profiles':[{'id':a,'name':'A','configuration':{'appName':'account-a'}},{'id':b,'name':'B','configuration':None}]};cloud_accounts.write(self.s,value)
  row=self.row();self.assertEqual(row['accountId'],a)
  with patch('provider_credentials.access',return_value='fixture-keychain-value'):
   self.s.dispatch('cloud_account_switch',{**self.p,'accountId':b});self.assertEqual(cloud_accounts.owner(self.s,{**self.p,'id':'r'}),a);self.assertIsNone(self.s.setting('biologyModal'))
   self.assertNotIn('fixture-keychain-value',json.dumps(self.s.dispatch('cloud_accounts',self.p)))
  with self.assertRaisesRegex(ValueError,'owns saved campaigns'):self.s.dispatch('cloud_account_remove',{**self.p,'accountId':a})
 def test_legacy_request_does_not_acquire_selected_account_on_refresh(self):
  row=self.row();row.pop('accountId',None)
  with self.s.db:self.s.db.execute('UPDATE biology_modal_jobs SET data=? WHERE id=?',(json.dumps(row),'r'))
  cloud_accounts.write(self.s,{'activeId':'b'*32,'profiles':[{'id':'b'*32,'name':'B'}]})
  biology_modal.save(self.s,row);self.assertIsNone(row['accountId']);self.assertEqual(cloud_accounts.owner(self.s,{**self.p,'id':'r'}),'legacy')
 def test_missing_original_credentials_never_fall_back(self):
  a='a'*32;cloud_accounts.write(self.s,{'activeId':a,'profiles':[{'id':a,'name':'A'}]})
  with patch('provider_credentials.access',return_value=None):
   with self.assertRaisesRegex(ValueError,'No fallback'):cloud_accounts.environment(self.s,a)
 def test_paid_launch_refuses_stale_source_or_another_account(self):
  from cloud_deployment import require_current_engine
  import tarfile,io
  manifest=b'{"fixture":true}';archive=self.root/'source.tar.gz'
  with tarfile.open(archive,'w:gz') as f:
   info=tarfile.TarInfo('release/release.json');info.size=len(manifest);f.addfile(info,io.BytesIO(manifest))
  folder=self.root/'cloud-engine-deployment';folder.mkdir();cfg={'appName':'fixture-cloud'};record={'state':'deployed','appName':cfg['appName'],'sourceManifestSha256':'wrong','accountId':'a'}
  (folder/'status.json').write_text(json.dumps(record))
  with patch('rapid_remote.artifact',return_value=(archive.read_bytes(),hashlib.sha256(archive.read_bytes()).hexdigest())):
   with self.assertRaisesRegex(ValueError,'differs'):require_current_engine(self.s,cfg,'a')
   record['sourceManifestSha256']=hashlib.sha256(manifest).hexdigest();(folder/'status.json').write_text(json.dumps(record))
   with self.assertRaisesRegex(ValueError,'differs'):require_current_engine(self.s,cfg,'b')
   self.assertTrue(require_current_engine(self.s,cfg,'a'))
 def test_shell_requires_exact_review_and_existing_owner(self):
  import cloud_shell
  row=self.row()
  with patch.dict('os.environ',{'FOLD_PROVIDER_CHILD':'1'}),patch.object(cloud_shell,'containers',return_value={'containers':[{'Container ID':'ta-abc'}],'appId':'ap-abc'}),patch.object(cloud_shell,'cli') as execute:
   with self.assertRaisesRegex(ValueError,'Review'):self.s.dispatch('cloud_shell_execute',{**self.p,'id':'r','command':'pwd','containerId':'ta-abc'})
   with self.assertRaisesRegex(ValueError,'changed after review'):self.s.dispatch('cloud_shell_execute',{**self.p,'id':'r','command':'pwd','containerId':'ta-abc','approvedRemoteCost':True,'approvedSystemAccess':True,'reviewedCommandSha256':'wrong'})
   execute.assert_not_called()

if __name__=='__main__':unittest.main()
