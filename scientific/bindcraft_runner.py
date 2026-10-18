"""Native CPU execution of the pinned upstream campaign, without altered scientific filters."""
import json,os,pathlib,sys,platform,hashlib,importlib.metadata,time
os.environ['JAX_PLATFORMS']='cpu';os.environ['XLA_PYTHON_CLIENT_PREALLOCATE']='false';sys.dont_write_bytecode=True
BASE=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'vendor/bindcraft2'))
if __name__=='__main__':
 from bindcraft.campaign import launch_campaign
 from bindcraft.model_weights import proteinmpnn_weights
 # CPU path calls real upstream orchestration; one worker, no remote invocation.
 import jax
 settings=pathlib.Path(sys.argv[1]);started=time.perf_counter()
 provenance={'python':sys.version,'jax':jax.__version__,'jaxlib':importlib.metadata.version('jaxlib'),'architecture':platform.machine(),'macOS':platform.mac_ver()[0],'devices':[str(d) for d in jax.devices()],'execution':'cpu','executionSettingsSha256':hashlib.sha256(settings.read_bytes()).hexdigest()}
 (settings.parent/'runtime-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 print('Scientific runtime: '+json.dumps(provenance),flush=True)
 status=launch_campaign(sys.argv[1],af2_weights=sys.argv[2],mpnn_weights=proteinmpnn_weights())
 provenance['totalSeconds']=time.perf_counter()-started
 (settings.parent/'runtime-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
 raise SystemExit(status)
