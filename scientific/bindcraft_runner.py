"""Pinned upstream campaign, explicit backend/precision, unchanged scientific filters."""
import json,os,pathlib,sys,platform,hashlib,importlib.metadata,time
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
  install_trajectory_policy()
 from bindcraft.campaign import launch_campaign
 from bindcraft.model_weights import proteinmpnn_weights
 # Real upstream orchestration; one worker, no remote invocation.
 import jax
 settings=pathlib.Path(sys.argv[1]);started=time.perf_counter()
 if not jax.devices() or any(d.platform.lower()!=backend for d in jax.devices()):raise RuntimeError('Requested backend unavailable; fallback refused.')
 provenance={'python':sys.version,'jax':jax.__version__,'jaxlib':importlib.metadata.version('jaxlib'),'architecture':platform.machine(),'macOS':platform.mac_ver()[0],'devices':[str(d) for d in jax.devices()],'execution':backend,'precision':precision,'executionSettingsSha256':hashlib.sha256(settings.read_bytes()).hexdigest(),'runnerSha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()}
 provenance['upstreamSource']=source
 if precision=='float32':provenance['precisionAdapterSha256']=hashlib.sha256(pathlib.Path(__file__).with_name('af2_native.py').read_bytes()).hexdigest()
 if backend=='metal':provenance.update(metaljax=importlib.metadata.version('metaljax'),memoryEnvironment=envelope,precisionAdapterSha256=hashlib.sha256(pathlib.Path(__file__).with_name('af2_native.py').read_bytes()).hexdigest())
 (settings.parent/'runtime-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 print('Scientific runtime: '+json.dumps(provenance),flush=True)
 try:
  status=launch_campaign(sys.argv[1],af2_weights=sys.argv[2],mpnn_weights=proteinmpnn_weights());provenance['exitCode']=status;provenance['state']='finished'
 except BaseException as error:
  provenance.update(state='failed',error=str(error));raise
 finally:
  provenance['totalSeconds']=time.perf_counter()-started
  (settings.parent/'runtime-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 raise SystemExit(status)
