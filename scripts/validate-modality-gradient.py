"""Bounded authentic source-preset CPU gradient; never run alongside another model job.
No standalone forward executable is retained. Outputs are technical predictions,
not optimized/accepted designs. Parent macOS task-footprint ceiling includes compressed memory.
"""
import argparse,datetime,hashlib,json,os,pathlib,signal,sqlite3,subprocess,sys,time
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
from process_memory import process_memory,exceeds_footprint_budget
p=argparse.ArgumentParser();p.add_argument('--modality',required=True);p.add_argument('--parameters',required=True);p.add_argument('--target',required=True);p.add_argument('--target-chains',default='A');p.add_argument('--output',required=True);p.add_argument('--binder-length',type=int);p.add_argument('--seed',type=int,default=42);p.add_argument('--subbatch-size',type=int,choices=[1,2,4]);p.add_argument('--max-footprint-gib','--max-rss-gib',dest='max_footprint_gib',type=float,default=14);p.add_argument('--timeout-seconds',type=int,default=1800);p.add_argument('--idle-root',required=True);p.add_argument('--preflight-only',action='store_true');p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);a=p.parse_args();output=pathlib.Path(a.output).resolve()
if not a.worker:
 if output.exists():raise SystemExit('Choose a new gradient report path.')
 db=sqlite3.connect('file:'+str(pathlib.Path(a.idle_root).resolve()/'library.sqlite3')+'?mode=ro',uri=True);active=db.execute("SELECT id FROM jobs WHERE state IN ('queued','running')").fetchall();db.close()
 if active and not a.preflight_only:raise SystemExit('Wait for the existing native model job to finish; no competing model process will be launched.')
 if not 1<=a.max_footprint_gib<=14:raise SystemExit('This experiment permits a positive footprint ceiling no larger than 14 GiB.')
 output.parent.mkdir(parents=True,exist_ok=True);started=time.monotonic();maximum=0;maximum_footprint=0;process_identity=None;failure=None
 with output.with_suffix('.log').open('w') as log:
  child=subprocess.Popen([os.path.abspath(sys.executable),'-I','-B',str(pathlib.Path(__file__).resolve()),*sys.argv[1:],'--worker'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env={**os.environ,'JAX_PLATFORMS':'cpu','PYTHONDONTWRITEBYTECODE':'1'})
  print(json.dumps({'state':'running','pid':child.pid,'report':str(output)}),flush=True)
  while child.poll() is None:
   try:
    reading=process_memory(child.pid);maximum=max(maximum,reading['residentBytes']);maximum_footprint=max(maximum_footprint,reading['physicalFootprintBytes'])
    if process_identity is None:process_identity=reading['processStartAbstime']
    if reading['processStartAbstime']!=process_identity:failure='The monitored process identity changed.'
    if exceeds_footprint_budget(reading,a.max_footprint_gib*1024**3):failure='Measured macOS task footprint, including compressed allocations, crossed the '+str(a.max_footprint_gib)+' GiB experiment ceiling; not a claim of exhausting all physical memory.'
   except OSError as error:
    if child.poll() is None:failure='Cannot verify the macOS task footprint; stopping rather than continuing without a memory guard: '+str(error)
   if time.monotonic()-started>a.timeout_seconds:failure='The bounded experiment exceeded its '+str(a.timeout_seconds)+' second timeout.'
   if failure:
    os.killpg(child.pid,signal.SIGTERM)
    try:child.wait(timeout=5)
    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
    break
   time.sleep(.1)
 report=json.loads(output.read_text()) if output.exists() else {};report.update(observedParentPeakRSSBytes=maximum,observedParentPeakFootprintBytes=maximum_footprint,experimentFootprintCeilingGiB=a.max_footprint_gib,memoryMeasurement="macOS proc_pid_rusage ri_phys_footprint, including compressed allocations",parentWallSeconds=time.monotonic()-started,processExitCode=child.returncode)
 if failure:report.update(state='bounded_resource_refusal',error=failure)
 elif child.returncode:report.update(state='failed',error='Original gradient worker failed; see preserved log.')
 output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps({key:report.get(key) for key in ('state','error','maximumPaddedResidues','parentWallSeconds','observedParentPeakRSSBytes')}),flush=True);raise SystemExit(0 if child.returncode==0 and not failure else 1)
os.environ['JAX_PLATFORMS']='cpu';os.environ['XLA_PYTHON_CLIENT_PREALLOCATE']='false';sys.path.insert(0,str(ROOT/'scientific'));sys.path.insert(0,str(ROOT/'vendor/bindcraft2'))
import fold_engine as fe
from af2_native import model_class,float32_states
from bindcraft.settings import campaign_over_presets,load_settings,build_design_settings,DEFAULT_SETTINGS,resolve_cyclic_offset_mode
from bindcraft.protein_preparation import initialize_design_trajectory,design_residue_count,prepare_targets
from bindcraft.design_workers import campaign_subbatch_size
from bindcraft.af2 import campaign_length_bucket,padded_prediction_length,pad_design_chains
from bindcraft.protein import write_structure,ResidueFlags
from bindcraft.preflight import design_input_problems,feature_problems
from bindcraft.campaign_output import json_compatible
import jax,numpy as np,resource,importlib.metadata
source=fe.verify_source();target=pathlib.Path(a.target).resolve();target_sha=hashlib.sha256(target.read_bytes()).hexdigest();request={'modality':a.modality,'campaign_seed':a.seed,'targets':[{'name':'target','target_path':str(target),'chains':a.target_chains}],'attention_backend':'stock','use_cueq':False}
if a.binder_length is not None:request['binder_lengths']=[a.binder_length]
if a.subbatch_size is not None:request['subbatch_size']=a.subbatch_size
settings=load_settings(campaign_over_presets(request));design=build_design_settings(settings);problems=design_input_problems(design)+feature_problems(design)
if problems:raise ValueError('; '.join(problems))
states,_,losses=initialize_design_trajectory(design,jax.random.PRNGKey(a.seed));states=float32_states(states);padded=design_residue_count(settings);checkpoint=pathlib.Path(a.parameters).resolve()/'params_model_1_multimer_v3.npz';checkpoint_sha=hashlib.file_digest(checkpoint.open('rb'),'sha256').hexdigest();assert checkpoint_sha==json.loads((ROOT/'scientific/af2-parameters.json').read_text())['models']['model_1_multimer_v3'];assert all(device.platform=='cpu' for device in jax.devices())
report={'state':'input_preflight_passed' if a.preflight_only else 'gradient_pending','scope':'Original complete modality preset, input preparation and losses; single genuine model_1_multimer_v3 CPU float32 gradient including its full forward. No separately retained standalone prediction executable, trajectory optimization, ProteinMPNN, held-out refold, acceptance or biological claim. No original thresholds changed.','source':source,'targetSha256':target_sha,'settings':json_compatible(settings),'settingsSha256':fe.checksum(fe.canonical(json_compatible(settings)).encode()),'model':'model_1_multimer_v3','parameterSha256':checkpoint_sha,'seed':a.seed,'maximumPaddedResidues':padded,'inputChainLengths':{state:{chain:len(protein) for chain,protein in values.items()} for state,values in states.items()},'executionOverrides':{'subbatch_size':a.subbatch_size} if a.subbatch_size is not None else {},'backend':'cpu','precision':'float32','jax':jax.__version__,'jaxlib':importlib.metadata.version('jaxlib'),'scaffoldSha256':hashlib.sha256(pathlib.Path(design.binder.scaffold).read_bytes()).hexdigest() if design.binder.scaffold else None,'activeLosses':list(losses),'standaloneForwardExecuted':False,'gradientIncludesFullForward':True,'compileCacheSize':1};output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps({'stage':'preflight','padded':padded,'inputChainLengths':report['inputChainLengths']}),flush=True)
if a.preflight_only:raise SystemExit(0)
try:
 started=time.perf_counter();bucket=campaign_length_bucket(settings);target_lengths={len(protein) for protein in prepare_targets(design,longest_crop=True).values()};target_pad=padded_prediction_length(max(target_lengths),bucket) if len(target_lengths)>1 else 0;groups=(design.binder_chains,) if design.binder.copies>1 and design.oligomer_tie=='symmetric' else ();padded_states=pad_design_chains(states,bucket,target_pad);report['actualGradientStatePaddedResidues']={name:padded_prediction_length(sum(len(protein) for protein in chains.values()),bucket) for name,chains in padded_states.items()};report['effectiveSubbatchSize']=campaign_subbatch_size(settings,padded);output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');model=model_class()(presets=('model_1_multimer_v3',),models=('model_1_multimer_v3',),data_dir=str(checkpoint.parent),key=jax.random.PRNGKey(a.seed),max_cache_size=1,num_recycle=settings.get('design_recycles',DEFAULT_SETTINGS['design_recycles']),cyclic_offset_mode=resolve_cyclic_offset_mode(settings),subbatch_size=report['effectiveSubbatchSize'],attention_backend='stock',use_cueq=False,length_bucket_size=bucket,multi_chain_binders=groups,target_pad_length=target_pad,amino_acid_bias=design.binder.amino_acid_bias);report['useRemat']=all(runner.config.model.global_config.use_remat for runner in model.alphafold_runners.values());assert report['useRemat'];loaded=time.perf_counter();predictions,grads,loss=model.sequence_gradients(states,losses);jax.block_until_ready(grads);value=float(loss);assert np.isfinite(value)
 arrays={};norms={}
 for name,gradient in grads.items():
  values=np.asarray(gradient);assert np.isfinite(values).all();arrays['gradient_'+name]=values;norms[name]=float(np.linalg.norm(values))
 assert any(value>0 for name,value in norms.items() if name in design.binder_chains)
 for name,prediction in predictions.items():
  for chain,protein in prediction.protein_complex.items():assert np.isfinite(np.asarray(protein.atoms)).all();arrays[name+'_'+chain+'_positions']=np.asarray(protein.atoms)
  write_structure(prediction.protein_complex,str(output.with_name(output.stem+'_'+name+'.cif')),plddt=prediction.metrics.get('plddt'))
 np.savez(output.with_suffix('.npz'),**arrays);assert fe.verify_source()==source and hashlib.sha256(target.read_bytes()).hexdigest()==target_sha;report.update(state='full_gradient_passed',loadSeconds=loaded-started,firstGradientIncludingCompilationSeconds=time.perf_counter()-loaded,loss=value,gradientNorms=norms,peakProcessRSSBytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss);output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');print(json.dumps({key:report[key] for key in ('state','loss','gradientNorms','peakProcessRSSBytes')}),flush=True)
except BaseException as error:
 report.update(state='failed',error=str(error));output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');raise
