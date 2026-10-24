"""Pinned upstream campaign, explicit backend/precision, unchanged scientific filters."""
import contextlib,json,os,pathlib,sys,platform,hashlib,importlib.metadata,time
backend=sys.argv[3] if len(sys.argv)>3 else 'cpu'
if backend not in ('cpu','metal'):raise ValueError('Unknown execution backend.')
precision=sys.argv[4] if len(sys.argv)>4 else ('float32' if backend=='metal' else 'upstream')
if precision not in ('upstream','float32') or (backend=='metal' and precision!='float32'):raise ValueError('Metal requires the validated float32 execution policy.')
os.environ['JAX_PLATFORMS']=backend;os.environ['XLA_PYTHON_CLIENT_PREALLOCATE']='false';sys.dont_write_bytecode=True
BASE=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'vendor/bindcraft2'))
if __name__=='__main__':
 from fold_engine import verify_source
 source=verify_source()
 if backend=='metal':
  from metal_runtime import PINS,environment
  envelope=environment(sys.argv[5] if len(sys.argv)>5 else 'single')
  os.environ.update(envelope)
  if any(importlib.metadata.version(k)!=v for k,v in PINS.items()):raise RuntimeError('Metal runtime version mismatch.')
 from campaign_progress import install as install_progress
 install_progress()
 if precision=='float32':
  from af2_native import install_trajectory_policy
  precision_model=install_trajectory_policy()
 from bindcraft.campaign import launch_campaign
 from bindcraft.model_weights import proteinmpnn_weights
 # Real upstream orchestration; one worker, no remote invocation.
 import jax
 settings=pathlib.Path(sys.argv[1]);started=time.perf_counter()
 if not jax.devices() or any(d.platform.lower()!=backend for d in jax.devices()):raise RuntimeError('Requested backend unavailable; fallback refused.')
 provenance={'python':sys.version,'jax':jax.__version__,'jaxlib':importlib.metadata.version('jaxlib'),'architecture':platform.machine(),'macOS':platform.mac_ver()[0],'devices':[str(d) for d in jax.devices()],'execution':backend,'precision':precision,'executionSettingsSha256':hashlib.sha256(settings.read_bytes()).hexdigest(),'runnerSha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
 provenance['upstreamSource']=source
 session=None
 if os.environ.get('FOLD_AMME_POLICY'):
  from amme_campaign import FabSession,POLICY,SCHEDULER_FLAG
  if os.environ['FOLD_AMME_POLICY']!=POLICY or backend!='cpu' or precision!='float32':raise ValueError('AMME requires the explicit CPU float32 Fab worker policy.')
  if jax.__version__!='0.11.2' or importlib.metadata.version('jaxlib')!='0.11.2' or SCHEDULER_FLAG not in os.environ.get('XLA_FLAGS','').split():raise RuntimeError('AMME requires the validated JAX0.11.2 CPU memory scheduler.')
  config=json.loads(settings.read_text());scaffold=pathlib.Path(config.get('binder_scaffold',''))
  if not scaffold.is_file() or hashlib.sha256(scaffold.read_bytes()).hexdigest()!=hashlib.sha256((BASE/'vendor/bindcraft2/scaffolds/Fab.cif').read_bytes()).hexdigest():raise ValueError('This AMME campaign policy requires the complete pinned Fab scaffold.')
  if config.get('auto_multi_gpu') is not False or config.get('design_workers')!=1:raise ValueError('Protected Fab execution requires the single native CPU worker; process fan-out refused.')
  pins=json.loads(pathlib.Path(__file__).with_name('af2-parameters.json').read_text())['models'];checked={}
  for name in (*config['design_models'],*config['validation_models']):
   with (pathlib.Path(sys.argv[2])/('params_'+name+'.npz')).open('rb') as stream:checked[name]=hashlib.file_digest(stream,'sha256').hexdigest()
   if checked[name]!=pins[name]:raise ValueError('Fab checkpoint differs from its pinned identity: '+name)
  identity={'source':source,'executionSettingsSha256':provenance['executionSettingsSha256'],
            'checkpointSha256':checked,
            'parameterManifestSha256':hashlib.sha256(pathlib.Path(__file__).with_name('af2-parameters.json').read_bytes()).hexdigest()}
  session=FabSession(os.environ['FOLD_AMME_SCRATCH'],identity=identity,stage_path=settings.parent/'amme-stage.json')
  provenance['amme']={'policy':POLICY,'compilerEnvironment':os.environ.get('XLA_FLAGS',''),
      'adapterSha256':hashlib.sha256(pathlib.Path(__file__).with_name('amme_campaign.py').read_bytes()).hexdigest(),
      'ssdAdapterSha256':hashlib.sha256(pathlib.Path(__file__).with_name('ssd_checkpoint.py').read_bytes()).hexdigest(),
      'scope':'Original complete Fab campaign, exact SSD replay and recomputation;14GiB supervised task limit. No intra-trajectory optimizer-state resume.'}
 if precision=='float32':provenance['precisionAdapterSha256']=hashlib.sha256(pathlib.Path(__file__).with_name('af2_native.py').read_bytes()).hexdigest()
 if backend=='metal':provenance.update(metaljax=importlib.metadata.version('metaljax'),memoryEnvironment=envelope,precisionAdapterSha256=hashlib.sha256(pathlib.Path(__file__).with_name('af2_native.py').read_bytes()).hexdigest())
 (settings.parent/'runtime-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 print('Scientific runtime: '+json.dumps(provenance),flush=True)
 seed_context=contextlib.nullcontext()
 protocol=settings.parent/'seed-protocol.json'
 if protocol.is_file():
  remote=BASE/'remote_worker';sys.path.insert(0,str(remote if remote.is_dir() else pathlib.Path(__file__).parent))
  from fold_rapid.seeded_bindcraft import install as install_seed
  seed_context=install_seed(json.loads(protocol.read_text()))
  provenance['biologySeedProtocolSha256']=hashlib.sha256(protocol.read_bytes()).hexdigest()
 try:
  with seed_context, (session.install(precision_model) if session else contextlib.nullcontext()):
   status=launch_campaign(sys.argv[1],af2_weights=sys.argv[2],mpnn_weights=proteinmpnn_weights())
  provenance['exitCode']=status;provenance['state']='finished'
 except BaseException as error:
  provenance.update(state='failed',error=str(error));raise
 finally:
  provenance['totalSeconds']=time.perf_counter()-started
  (settings.parent/'runtime-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 raise SystemExit(status)
