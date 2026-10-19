"""Resolve the original upstream model ensemble in an isolated scientific process."""
import json,os,subprocess

def resource_estimate(python,config,source):
 code="""
import sys,json
sys.path.insert(0,sys.argv[2])
from bindcraft.settings import load_settings,build_design_settings
from bindcraft.protein_preparation import design_residue_count
from bindcraft.preflight import design_input_problems,feature_problems
settings=load_settings(json.loads(sys.argv[1]))
design=build_design_settings(settings)
problems=design_input_problems(design)+feature_problems(design)
if problems:raise ValueError('; '.join(problems))
print(json.dumps({'paddedResidues':int(design_residue_count(settings))}))
"""
 result=subprocess.run([python,'-B','-c',code,json.dumps(config),str(source)],env={**os.environ,'JAX_PLATFORMS':'cpu','PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=45)
 if result.returncode:raise ValueError('Upstream scaffold resource check failed: '+result.stderr[-4000:])
 estimate=json.loads(result.stdout.splitlines()[-1])
 if type(estimate.get('paddedResidues')) is not int or estimate['paddedResidues']<1:raise ValueError('Invalid upstream resource estimate.')
 return estimate

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

def property_catalog(source):
 import hashlib,pathlib
 return [{'name':path.stem,'description':json.loads(path.read_text()).get('description',''),'source':str(path.relative_to(source)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'status':'integrated_unvalidated'} for path in sorted((pathlib.Path(source)/'settings/property').glob('*.json'))]

def property_preset(service,modality,names,source):
 """Use original core/modality/property precedence, never a local preset merger."""
 import pathlib
 from mpnn import runtime
 catalog=property_catalog(source);known={entry['name']:entry for entry in catalog}
 if not isinstance(names,list) or len(names)>len(known) or any(not isinstance(name,str) or name not in known for name in names) or len(names)!=len(set(names)):raise ValueError('Choose distinct property presets supplied by the pinned BindCraft2 source.')
 if not names:return None,[]
 python=os.path.abspath(os.path.expanduser(runtime(service)))
 if not pathlib.Path(python).is_file():raise ValueError('The scientific runtime is required to resolve authentic property presets.')
 code="import sys,json;sys.path.insert(0,sys.argv[2]);from bindcraft.settings import campaign_over_presets;print(json.dumps(campaign_over_presets(json.loads(sys.argv[1]))))"
 request={'modality':modality,**{name:True for name in names}};result=subprocess.run([python,'-I','-B','-c',code,json.dumps(request),str(source)],capture_output=True,text=True,env={**os.environ,'JAX_PLATFORMS':'cpu','PYTHONDONTWRITEBYTECODE':'1'},timeout=45)
 if result.returncode:raise ValueError('Original preset resolution refused: '+result.stderr[-2000:])
 return json.loads(result.stdout.splitlines()[-1]),[known[name] for name in sorted(names)]

def property_conflicts(service,config,source,scaffold=None):
 """Refuse original feature conflicts before a prepared campaign is created."""
 from mpnn import runtime
 request={**config}
 if scaffold:request['binder_scaffold']=str(source/scaffold['source'])
 code="""
import sys,json
sys.path.insert(0,sys.argv[2])
from bindcraft.settings import load_settings,conflicting_campaign_features
settings=load_settings(json.loads(sys.argv[1]))
conflicts=conflicting_campaign_features(settings)
if conflicts:raise ValueError('; '.join(f'{a} and {b}: {reason}' for a,b,reason in conflicts))
print('compatible')
"""
 process=subprocess.run([os.path.abspath(os.path.expanduser(runtime(service))),'-I','-B','-c',code,json.dumps(request),str(source)],capture_output=True,text=True,env={**os.environ,'JAX_PLATFORMS':'cpu','PYTHONDONTWRITEBYTECODE':'1'},timeout=45)
 if process.returncode:raise ValueError('Original property compatibility refused: '+process.stderr[-2000:])
