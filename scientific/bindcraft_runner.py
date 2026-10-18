"""Native CPU execution of the pinned upstream campaign, without altered scientific filters."""
import json,os,pathlib,sys
os.environ['JAX_PLATFORMS']='cpu';os.environ['XLA_PYTHON_CLIENT_PREALLOCATE']='false';sys.dont_write_bytecode=True
BASE=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'vendor/bindcraft2'))
if __name__=='__main__':
 from bindcraft.campaign import launch_campaign
 from bindcraft.model_weights import proteinmpnn_weights
 # CPU path calls real upstream orchestration; one worker, no remote invocation.
 status=launch_campaign(sys.argv[1],af2_weights=sys.argv[2],mpnn_weights=proteinmpnn_weights())
 raise SystemExit(status)
