"""Resolve the original upstream model ensemble in an isolated scientific process."""
import json,os,subprocess

def ensemble_models(python,config,source):
 code="""
import sys,json
sys.path.insert(0,sys.argv[2])
from bindcraft.settings import load_settings,select_design_and_validation_models
from bindcraft.af2 import MULTIMER_POOL,MONOMER_POOL
selection=select_design_and_validation_models(load_settings(json.loads(sys.argv[1])),MULTIMER_POOL,MONOMER_POOL)
print(json.dumps({'designModels':list(selection.design_models),'validationModels':list(selection.validation_models),'validationPoolExhausted':selection.validation_pool_exhausted}))
"""
 env={**os.environ,'JAX_PLATFORMS':'cpu','PYTHONDONTWRITEBYTECODE':'1'}
 proc=subprocess.run([python,'-B','-c',code,json.dumps(config),str(source)],env=env,capture_output=True,text=True,timeout=45)
 if proc.returncode:raise ValueError('Upstream ensemble selection failed: '+proc.stderr[-4000:])
 selection=json.loads(proc.stdout.splitlines()[-1]);design=selection['designModels'];validation=selection['validationModels']
 if not design or not validation or set(design)&set(validation):raise ValueError('Upstream design and held-out validation pools must be distinct.')
 return selection
