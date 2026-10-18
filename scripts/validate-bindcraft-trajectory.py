"""Real upstream design stages on a tiny explicit technical target fragment.
Not a research campaign: four optimization updates, permissive diagnostic gates,
no accepted-binder claim. Uses genuine trained AF2 parameters and upstream losses.
"""
import argparse,hashlib,json,os,pathlib,resource,sys,time,uuid
os.environ['JAX_PLATFORMS']='cpu';os.environ['XLA_PYTHON_CLIENT_PREALLOCATE']='false';sys.dont_write_bytecode=True
BASE=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'vendor/bindcraft2'))
p=argparse.ArgumentParser();p.add_argument('--parameters',required=True);p.add_argument('--directory',required=True);a=p.parse_args()
import jax,numpy as np
from bindcraft.settings import load_settings,build_design_settings
from bindcraft.af2 import AlphaFoldDesignModel
from bindcraft.trajectory import run_trajectory
from bindcraft.protein import write_structure
folder=pathlib.Path(a.directory).resolve();folder.mkdir(parents=True,exist_ok=True)
source=BASE/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb';lines=source.read_text().splitlines();numbers=[];kept=[]
for line in lines:
 if line.startswith('ATOM  ') and line[21]=='A':
  n=int(line[22:26])
  if n not in numbers:numbers.append(n)
  if numbers.index(n)<12:kept.append(line)
fragment=folder/'technical_target_fragment.pdb';fragment.write_text('\n'.join(kept)+'\nEND\n')
settings=load_settings({'targets':[{'name':'technical_fragment','target_path':str(fragment),'chains':'A'}],'binder_lengths':[12],'campaign_seed':2718,'design_models':['model_1_multimer_v3'],'validation_model':'monomer','validation_models':['model_1_ptm'],'design_recycles':0,'design_dropout':False,'length_bucket_size':1,'attention_backend':'stock','use_cueq':False,'autotune':False,'filters':[],'screen_steps':1,'refine_steps':1,'anneal_steps':1,'harden_steps':1,'mutate_steps':0,'min_plddt_screen':0.0,'min_plddt_refine':0.0,'min_plddt_anneal':0.0,'min_plddt_harden':0.0,'min_plddt_final':0.0,'save_design_sequences':True})
(folder/'settings.json').write_text(json.dumps(settings,indent=2))
start=time.perf_counter();model=AlphaFoldDesignModel(presets='model_1_multimer_v3',data_dir=a.parameters,key=jax.random.PRNGKey(2718),num_recycle=0,dropout=False,length_bucket_size=1,attention_backend='stock');print('Starting genuine upstream screen/refine/anneal/harden stages.',flush=True)
states,predictions,failed=run_trajectory(build_design_settings(settings),model,jax.random.PRNGKey(2718),trajectory_directory=str(folder/('trajectory-'+str(uuid.uuid4()))))
outputs=[]
for state,prediction in predictions.items():
 for chain,protein in prediction.protein_complex.items():
  if not np.isfinite(np.asarray(protein.atoms)).all():raise ValueError('Nonfinite trajectory coordinates.')
 path=folder/(state.replace('/','_')+'.cif');write_structure(prediction.protein_complex,str(path),plddt=prediction.metrics.get('plddt'));outputs.append(path.name)
report={'state':'technical_execution_finished','failedStage':failed,'outputs':outputs,'upstreamRevision':'c0ee638d11bc010817c2c97ee58ed5c323e664e2','execution':'cpu','seconds':time.perf_counter()-start,'peakProcessRSSBytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'sourceSha256':hashlib.sha256(fragment.read_bytes()).hexdigest(),'settings':settings,'limitations':['Technical target fragment and 12-residue binder only.','One update per stage; permissive diagnostic confidence gates. No claim of a valid binder, research-quality design or default campaign acceptance.','No Metal acceleration or experimental binding/inhibition validation.']}
(folder/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='settings'},indent=2))
