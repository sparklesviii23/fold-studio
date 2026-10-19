"""Compare native benchmark hierarchy against the authentic original resolver."""
import argparse,hashlib,json,os,pathlib,sys
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'));sys.path.insert(0,str(ROOT/'vendor/bindcraft2'))
from worker import Service
from bindcraft.settings import campaign_over_presets
from campaign_profile import resource_estimate
from bindcraft_cpu import execution_config
p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--report',required=True);a=p.parse_args();root=pathlib.Path(a.directory).resolve()
if root.exists():raise SystemExit('Use a new isolated core-profile root.')
s=Service(root);python=os.path.abspath(sys.executable);s.setting_set({'key':'bindcraftPython','value':python});project=s.project_create({'name':'Original core precedence QA'});source=ROOT/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb';original=hashlib.sha256(source.read_bytes()).hexdigest();record=s.import_structure({'projectId':project['id'],'path':str(source)});cases=[]
try:
 for mode,properties in [('binder',[]),('VHH',['humanize'])]:
  payload={'projectId':project['id'],'structureId':record['id'],'targetChains':['A'],'name':'Benchmark '+mode,'modality':mode,'core':'benchmark','properties':properties,'candidates':1,'attempts':1,'seed':42}
  if mode=='binder':payload['binderLengths']=[60]
  job=s.dispatch('bindcraft_prepare',payload);prep=job['data']['preparation'];config=prep['config'];expected=campaign_over_presets({'core':'benchmark','modality':mode,**{name:True for name in properties}})
  for key,value in expected.items():
   if key not in ('binder_lengths','binder_scaffold','campaign_seed'):assert config[key]==value,(key,config[key],value)
  assert config['autotune'] is False and config['desperation'] is False and config['campaign_seed']==42
  assert prep['corePresets'][0]['name']=='benchmark';folder=root/'jobs'/job['id'];run_config,_=execution_config(config,folder);estimate=resource_estimate(python,run_config,ROOT/'vendor/bindcraft2');assert (folder/'input.pdb').read_bytes()==source.read_bytes();cases.append({'modality':mode,'properties':properties,'jobId':job['id'],'originalHierarchyMatches':True,'explicitSeed':42,'coreReceipt':prep['corePresets'],'estimate':estimate,'state':'prepared_not_executed'})
 assert hashlib.sha256(source.read_bytes()).hexdigest()==original
 report={'state':'passed','scope':'Original benchmark/core -> modality -> properties -> explicit native fields precedence and real input/feature preflight. Configuration/state validation only; no new neural model computation.','root':str(root),'sourceUnchanged':True,'sourceSha256':original,'cases':cases};pathlib.Path(a.report).write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'state':'passed','cases':len(cases)}))
finally:s.db.close()
