"""Quarantined diagnostic pipeline: real AF2 optimization, MPNN, held-out AF2.
Permissive QA gates are explicit. Nothing is imported into a research library.
Ranked files here are technical outputs, never accepted scientific binders.
"""
import argparse,csv,hashlib,json,os,pathlib,subprocess,sys,time
sys.dont_write_bytecode=True
p=argparse.ArgumentParser();p.add_argument('--engine-root',required=True);p.add_argument('--python',required=True);p.add_argument('--directory',required=True);p.add_argument('--backend',choices=['cpu','metal'],required=True);p.add_argument('--ensemble',action='store_true');p.add_argument('--parameters');p.add_argument('--length-bucket-size',type=int,choices=[1,32],default=1);p.add_argument('--modality',choices=['binder','peptide'],default='peptide');p.add_argument('--target-mode',choices=['single','positive_pair','negative_control'],default='single');a=p.parse_args()
root=pathlib.Path(a.engine_root).resolve();folder=pathlib.Path(a.directory).resolve()
app=root.parents[1] if root.name=='Resources' and root.parent.name=='Contents' else None
def verify_seal():
 if app:
  check=subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],capture_output=True,text=True)
  if check.returncode:raise RuntimeError('App signature verification failed: '+check.stderr)
verify_seal()
if folder.exists():raise SystemExit('Choose a new diagnostic directory.')
folder.mkdir(parents=True);source=root/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb';kept=[];residues=[]
for line in source.read_text().splitlines():
 if line.startswith('ATOM  ') and line[21]=='A':
  number=int(line[22:26])
  if number not in residues:residues.append(number)
  if residues.index(number)<12:kept.append(line)
target=folder/'DIAGNOSTIC_target_fragment.pdb';target.write_text('\n'.join(kept)+'\nEND\n')
preset=root/('vendor/bindcraft2/settings/modality/'+a.modality+'.json');config=json.loads(preset.read_text());config.pop('description',None)
config.update(targets=[{'name':'diagnostic','target_path':str(target),'chains':'A'}],campaign_name='DIAGNOSTIC ONLY — permissive QA gates; no research acceptance',binder_name='DIAGNOSTIC',binder_lengths=[12],campaign_seed=2718,project_folder=str(folder/'QUARANTINED_OUTPUT'),number_of_final_designs=1,max_trajectories=1,design_models=['model_1_multimer_v3'],validation_model='multimer',validation_models=['model_2_multimer_v3'],design_recycles=0,validation_recycles=1,design_dropout=False,length_bucket_size=a.length_bucket_size,attention_backend='stock',use_cueq=False,auto_multi_gpu=False,design_workers=1,autotune=False,resume=False,filters=[],screen_steps=1,refine_steps=1,anneal_steps=1,harden_steps=1,mutate_steps=0,sequence_candidates=2,kept_sequences=1,enough_passing_sequences=1,save_design_sequences=True)
if a.modality=='binder':config.update(validation_model='monomer',validation_models=['model_1_ptm'],min_monomer_plddt_final=0.)
prepared_inputs=None
if a.target_mode!='single':
 sys.path.insert(0,str(root/'scientific'))
 from worker import Service
 from campaign_inputs import verify
 from bindcraft_cpu import execution_config
 service=Service(folder/'PREPARATION_ONLY_LIBRARY');project=service.project_create({'name':'Quarantined multi-state algorithm QA'})
 primary=service.import_structure({'projectId':project['id'],'path':str(target)})
 extras=[]
 for name,objective,weight in [('mPDL1','target',1.)]+([('hPD1','detarget',.5)] if a.target_mode=='negative_control' else []):
  lines=[];numbers=[]
  for line in (root/f'vendor/bindcraft2/settings/target/structures/{name}.pdb').read_text().splitlines():
   if line.startswith('ATOM  ') and line[21]=='A':
    number=int(line[22:26])
    if number not in numbers:numbers.append(number)
    if numbers.index(number)<12:lines.append(line)
  file=folder/('DIAGNOSTIC_'+name+'_fragment.pdb');file.write_text('\n'.join(lines)+'\nEND\n')
  record=service.import_structure({'projectId':project['id'],'path':str(file)})
  extras.append({'structureId':record['id'],'targetChains':['A'],'objective':objective,'weight':weight})
 job=service.dispatch('bindcraft_prepare',{'projectId':project['id'],'structureId':primary['id'],'targetChains':['A'],'additionalTargets':extras,'modality':a.modality,'binderLengths':[12],'candidates':1,'attempts':1,'seed':2718})
 prep=job['data']['preparation'];job_folder=service.root/'jobs'/job['id'];prepared_inputs=verify(job_folder,prep)
 native,_=execution_config(prep['config'],job_folder);config['targets']=native['targets']
 config.update(multitarget_steps=1,multitarget_rounds_per_target=[],multitarget_swap_patience=1,multitarget_warmup_patience=1,max_detarget_rounds=1,detarget_check_interval=1,max_detarget_iptm=1.,max_detarget_interface_residues_final=1000)
 for stage in ('screen','refine','anneal','harden'):config[stage+'_steps']=len(config['targets'])
 service.db.close()
if a.ensemble:
 config.pop('design_models');config.pop('validation_models')
for stage in ('screen','refine','anneal','harden','mutate','final'):
 config['min_plddt_'+stage]=0.;config['min_iptm_'+stage]=0.
 if a.target_mode=='negative_control':config['max_detarget_iptm_'+stage]=1.
settings=folder/'DIAGNOSTIC_settings.json';settings.write_text(json.dumps(config,indent=2)+'\n')
env={**{k:v for k,v in os.environ.items() if not k.startswith(('FOLD_','PYTHON','DYLD_','METALJAX_'))},'PYTHONUNBUFFERED':'1','PYTHONDONTWRITEBYTECODE':'1','JAX_PLATFORMS':a.backend}
if a.backend=='metal':
 sys.path.insert(0,str(root/'scientific'))
 from metal_runtime import ENV
 env.update(ENV)
start=time.perf_counter()
with (folder/'execution.log').open('w') as log:
 proc=subprocess.run([a.python,'-B',str(root/'scientific/bindcraft_runner.py'),str(settings),str(pathlib.Path(a.parameters).resolve() if a.parameters else root/'models/alphafold'),a.backend,'float32'],env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
ranked=folder/'QUARANTINED_OUTPUT/3_Ranked';files=sorted(ranked.glob('*.cif'));tables={str(f.relative_to(folder)):list(csv.DictReader(f.open())) for f in (folder/'QUARANTINED_OUTPUT').rglob('*.csv')}
passed=proc.returncode==0 and bool(files) and any(name.endswith('2_Refolded/!_Refolded.csv') and rows for name,rows in tables.items())
verify_seal()
report={'state':'technical_pipeline_completed' if passed else 'technical_pipeline_failed','backend':a.backend,'engineRoot':str(root),'interpreter':os.path.abspath(a.python),'signatureAfterInference':'passed' if app else 'not_applicable','externalRuntimeEnvironmentRemoved':True,'targetMode':a.target_mode,'modality':a.modality,'preparedInputs':prepared_inputs,'diagnosticOnly':True,'researchAcceptance':False,'importedRecords':0,'seconds':time.perf_counter()-start,'sourceSha256':hashlib.sha256(target.read_bytes()).hexdigest(),'settingsSha256':hashlib.sha256(settings.read_bytes()).hexdigest(),'settings':config,'technicalStructures':{str(f.relative_to(folder)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},'tables':tables,'runtime':json.loads((folder/'runtime-provenance.json').read_text()),'limitations':['12 residues per target + 12 designed residues; exact diagnostic update budgets saved in settings; one held-out multimer recycle.','Multi-target technical cases give each stage at least as many updates as target states and bound swap/warmup/negative-selection rounds; production preparation does not change original budgets.','QA confidence/filter gates explicitly permissive; output is not a scientifically accepted binder or binding validation.','No generated-output research-library import; input records are preparation-only and all technical output structures remain quarantined.']}
(folder/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('settings','tables')},indent=2))
if not passed:raise SystemExit(1)
