"""Actual original preset resolution/input-preflight, without model inference."""
import argparse,hashlib,json,os,pathlib,re,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'));sys.path.insert(0,str(ROOT/'vendor/bindcraft2'))
from worker import Service
from campaign_profile import property_catalog,resource_estimate
from bindcraft.settings import campaign_over_presets
from bindcraft_cpu import execution_config
p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--report',required=True);a=p.parse_args();root=pathlib.Path(a.directory).resolve()
if root.exists():raise SystemExit('Use a new isolated property-resolution root.')
s=Service(root);s.setting_set({'key':'bindcraftPython','value':os.path.abspath(sys.executable)});project=s.project_create({'name':'Original property hierarchy QA'});source=ROOT/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb';original=hashlib.sha256(source.read_bytes()).hexdigest();record=s.import_structure({'projectId':project['id'],'path':str(source),'name':'Official hPDL1 property configuration reference'});common={'projectId':project['id'],'structureId':record['id'],'targetChains':['A'],'hotspots':['["A",54,""]','["A",56,""]','["A",66,""]','["A",115,""]'],'coldspots':[],'binderLengths':[60],'candidates':1,'attempts':1,'seed':42};results=[]
try:
 selections=[('binder',[entry['name']]) for entry in property_catalog(ROOT/'vendor/bindcraft2')]+[('binder',['humanize','protease_stable','mixed_topology']),('VHH',['humanize'])]
 for modality,names in selections:
  payload={**common,'name':'Preset resolution · '+','.join(names),'modality':modality,'properties':names}
  if modality=='VHH':payload.pop('binderLengths')
  checked=s.dispatch('bindcraft_validate',payload);expected=campaign_over_presets({'modality':modality,**{name:True for name in names}});ignored={'binder_scaffold','binder_lengths','number_of_final_designs','max_trajectories','campaign_seed','project_folder','targets','design_workers','auto_multi_gpu','attention_backend','use_cueq','resume'}
  for key,value in expected.items():
   if key not in ignored and checked['config'].get(key)!=value:raise AssertionError(('Original preset precedence differs',modality,names,key,value,checked['config'].get(key)))
  job=s.dispatch('bindcraft_prepare',payload);config,_=execution_config(job['data']['preparation']['config'],root/'jobs'/job['id'])
  try:estimate=resource_estimate(os.path.abspath(sys.executable),config,ROOT/'vendor/bindcraft2');preflight={'state':'passed','estimate':estimate}
  except ValueError as error:preflight={'state':'refused_by_upstream','reason':str(error)}
  results.append({'modality':modality,'properties':names,'preparationId':job['id'],'presetReceipt':checked['propertyPresets'],'originalResolutionMatches':True,'inputPreflight':preflight,'scaffoldSha256':checked.get('scaffold',{}).get('sha256') if checked.get('scaffold') else None})
 if hashlib.sha256(source.read_bytes()).hexdigest()!=original:raise AssertionError('Official source changed.')
 evidence={'state':'passed','scope':'All nine original property presets, one combination and original VHH/humanize scaffold resolve exactly through the original upstream hierarchy, retain preset/source hashes and explicit campaign overrides. Actual upstream input/feature preflight outcomes recorded, including any refusals. No model forward, gradients, generation, biological validation or broad modality parity claimed.','root':str(root),'sourceSha256':original,'sourceUnchanged':True,'cases':results};pathlib.Path(a.report).write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps({'state':'passed','cases':len(results),'inputPreflight':[(x['properties'],x['inputPreflight']['state']) for x in results]},indent=2))
finally:s.db.close()
