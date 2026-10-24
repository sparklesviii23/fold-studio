"""Persistent-cache routing only; these tests do not claim measured CUDA hits."""
import copy,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'remote_worker'),str(ROOT/'tests')]
from test_rapid_worker import fixture
from fold_rapid.adapters import compilation_cache,prepare
from fold_rapid.registry import ENGINES

class CompileCacheTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
  self.runtime={'python':sys.executable,'source':str(ROOT/'vendor/bindcraft2'),'dependencyLockSha256':'fixture-lock'}
 def tearDown(self):self.tmp.cleanup()
 def test_bindcraft_and_refolding_share_compatible_runtime_namespace(self):
  shared=self.root/'persistent/compile-cache';paths=[]
  for engine in ('bindcraft2','af2_multimer'):
   m=fixture();m.update(engine=engine,operation='design' if engine=='bindcraft2' else 'evaluate')
   if engine=='af2_multimer':m['design']['designChains']=['B']
   job=self.root/engine;job.mkdir()
   with patch('fold_rapid.adapters.verified_runtime',return_value=(self.runtime,{})),patch('fold_rapid.adapters.selected_target',return_value={'chains':{'A':{},'B':{}}}):
    result=prepare(self.root/engine,job,m,cache_root=shared)
   paths.append(result['environment']['JAX_COMPILATION_CACHE_DIR'])
   self.assertFalse(pathlib.Path(paths[-1]).is_relative_to(job))
   if engine=='bindcraft2':
    settings=json.loads((job/'execution-settings.json').read_text())
    self.assertEqual(settings['max_trajectories'],m['design']['attempts'])
    self.assertEqual(settings['campaign_seed'],m['seed'])
  self.assertEqual(paths[0],paths[1])
 def test_incompatible_runtime_source_or_image_uses_different_directory(self):
  root=self.root/'cache';revision=ENGINES['bindcraft2']['revision']
  first=compilation_cache(root,self.runtime,revision)
  changed={**self.runtime,'dependencyLockSha256':'another-lock'}
  self.assertNotEqual(first,compilation_cache(root,changed,revision))
  self.assertNotEqual(first,compilation_cache(root,self.runtime,'another-source'))
  with patch.dict('os.environ',{'RAPID_IMAGE_DIGEST':'different-image'}):
   self.assertNotEqual(first,compilation_cache(root,self.runtime,revision))
 def test_stage_runner_uses_campaign_independent_root(self):
  from fold_rapid.unified import LocalStages
  m=fixture();campaign=self.root/'campaigns/example';campaign.mkdir(parents=True)
  with patch('fold_rapid.runner.execute') as execute:
   result=LocalStages(self.root,campaign)({'stageId':'a'*32},m,lambda _:None,lambda:False)
  self.assertEqual(execute.call_args.kwargs['cache_root'],self.root/'compile-cache')
  self.assertEqual(result['job']['state'],'queued')

 def test_cache_snapshot_counts_executables_without_locks(self):
  from fold_rapid.adapters import cache_snapshot
  folder=self.root/'cache';folder.mkdir();(folder/'a-cache').write_bytes(b'1234');(folder/'compile.lock').write_bytes(b'ignored')
  self.assertEqual(cache_snapshot(folder),{'files':1,'bytes':4,'truncated':False})
  self.assertIsNone(cache_snapshot(None))
