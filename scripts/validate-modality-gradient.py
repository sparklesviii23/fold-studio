"""Bounded authentic source-preset CPU gradient; never run alongside another model job.
No standalone forward executable is retained. Outputs are technical predictions,
not optimized/accepted designs. Parent macOS task-footprint ceiling includes compressed memory.
"""
import argparse,atexit,contextlib,datetime,hashlib,json,os,pathlib,signal,sqlite3,subprocess,sys,tempfile,time
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
from process_memory import process_memory,exceeds_footprint_budget
p=argparse.ArgumentParser();p.add_argument('--modality',required=True);p.add_argument('--parameters',required=True);p.add_argument('--target',required=True);p.add_argument('--target-chains',default='A');p.add_argument('--output',required=True);p.add_argument('--binder-length',type=int);p.add_argument('--seed',type=int,default=42);p.add_argument('--subbatch-size',type=int,choices=[1,2,4]);p.add_argument('--max-footprint-gib','--max-rss-gib',dest='max_footprint_gib',type=float,default=14);p.add_argument('--timeout-seconds',type=int,default=1800);p.add_argument('--idle-root',required=True);p.add_argument('--preflight-only',action='store_true');p.add_argument('--graph-profile',action='store_true');p.add_argument('--compile-profile',action='store_true');p.add_argument('--compiler-dump-directory');p.add_argument('--remat-subbatches',action='store_true');p.add_argument('--remat-structure',action='store_true');p.add_argument('--remat-triangles',action='store_true');p.add_argument('--remat-prevent-cse',action='store_true');p.add_argument('--full-design-pool',action='store_true');p.add_argument('--ssd-directory');p.add_argument('--ssd-max-gib',type=float,default=10);p.add_argument('--ssd-owned-directory',help=argparse.SUPPRESS);p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);a=p.parse_args();output=pathlib.Path(a.output).resolve()
def save_report(data):
 with tempfile.NamedTemporaryFile(mode='w',prefix=output.name+'.',suffix='.pending',dir=output.parent,delete=False) as stream:
  temporary=pathlib.Path(stream.name)
  try:stream.write(json.dumps(data,indent=2,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
  except BaseException:temporary.unlink(missing_ok=True);raise
 try:os.replace(temporary,output)
 finally:temporary.unlink(missing_ok=True)
if (a.remat_structure or a.remat_triangles) and not a.remat_subbatches:p.error('Structure rematerialization requires the AMME subbatch policy.')
if not a.worker:
 if output.exists():raise SystemExit('Choose a new gradient report path.')
 db=sqlite3.connect('file:'+str(pathlib.Path(a.idle_root).resolve()/'library.sqlite3')+'?mode=ro',uri=True);active=db.execute("SELECT id FROM jobs WHERE state IN ('queued','running')").fetchall();db.close()
 if active and not a.preflight_only:raise SystemExit('Wait for the existing native model job to finish; no competing model process will be launched.')
 if not 1<=a.max_footprint_gib<=14:raise SystemExit('This experiment permits a positive footprint ceiling no larger than 14 GiB.')
 output.parent.mkdir(parents=True,exist_ok=True);started=time.monotonic();maximum=0;maximum_footprint=0;process_identity=None;failure=None;samples=[];last_sample=0
 scratch=None;extra=[]
 if a.ssd_directory:
  if not 0<a.ssd_max_gib<=12:raise SystemExit('Choose an SSD tape budget greater than zero and no larger than 12 GiB.')
  scratch=tempfile.TemporaryDirectory(prefix='fold-gradient-',dir=pathlib.Path(a.ssd_directory).resolve(strict=True));atexit.register(scratch.cleanup);extra=['--ssd-owned-directory',scratch.name]
 def supervisor_stop(signum,frame):raise KeyboardInterrupt('Supervisor received '+signal.Signals(signum).name)
 signal.signal(signal.SIGTERM,supervisor_stop)
 with output.with_suffix('.log').open('w') as log:
  child=subprocess.Popen([os.path.abspath(sys.executable),'-I','-B',str(pathlib.Path(__file__).resolve()),*sys.argv[1:],*extra,'--worker'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env={**os.environ,'JAX_PLATFORMS':'cpu','PYTHONDONTWRITEBYTECODE':'1'})
  print(json.dumps({'state':'running','pid':child.pid,'report':str(output)}),flush=True)
  try:
   while child.poll() is None:
    try:
     reading=process_memory(child.pid);maximum=max(maximum,reading['residentBytes']);maximum_footprint=max(maximum_footprint,reading['physicalFootprintBytes'])
     if process_identity is None:process_identity=reading['processStartAbstime']
     if reading['processStartAbstime']!=process_identity:failure='The monitored process identity changed.'
     if exceeds_footprint_budget(reading,a.max_footprint_gib*1024**3):failure='Measured macOS task footprint, including compressed allocations, crossed the '+str(a.max_footprint_gib)+' GiB experiment ceiling; not a claim of exhausting all physical memory.'
     if time.monotonic()-last_sample>=1:
      last_sample=time.monotonic();sample={**reading,'elapsedSeconds':last_sample-started}
      try:sample['stage']=json.loads(output.read_text()).get('currentStage','input_preparation')
      except (OSError,ValueError):sample['stage']='input_preparation'
      pressure=subprocess.run(['/usr/sbin/sysctl','-n','kern.memorystatus_vm_pressure_level'],capture_output=True,text=True,timeout=2)
      if pressure.returncode==0:
       sample['systemMemoryPressureLevel']=int(pressure.stdout.strip())
       if sample['systemMemoryPressureLevel']>=4:failure='macOS reports critical system memory pressure; worker stopped under the unchanged safety policy.'
      sample['swapUsage']=subprocess.run(['/usr/sbin/sysctl','-n','vm.swapusage'],capture_output=True,text=True,timeout=2).stdout.strip();samples.append(sample)
    except OSError as error:
     if child.poll() is None:failure='Cannot verify the macOS task footprint; stopping rather than continuing without a memory guard: '+str(error)
    if time.monotonic()-started>a.timeout_seconds:failure='The bounded experiment exceeded its '+str(a.timeout_seconds)+' second timeout.'
    if failure:
     os.killpg(child.pid,signal.SIGTERM)
     try:child.wait(timeout=5)
     except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
     break
    time.sleep(.1)
  except BaseException as error:
   failure='Guard supervisor interrupted or failed: '+type(error).__name__+': '+str(error)
  finally:
   if child.poll() is None:
    os.killpg(child.pid,signal.SIGTERM)
    try:child.wait(timeout=5)
    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
 report=json.loads(output.read_text()) if output.exists() else {};report.update(memorySamples=samples,observedParentPeakRSSBytes=maximum,observedParentPeakFootprintBytes=maximum_footprint,experimentFootprintCeilingGiB=a.max_footprint_gib,memoryMeasurement="macOS proc_pid_rusage ri_phys_footprint, including compressed allocations",parentWallSeconds=time.monotonic()-started,processExitCode=child.returncode)
 if scratch:
  report['ssdRemainingBytesBeforeCleanup']=sum(file.stat().st_size for file in pathlib.Path(scratch.name).rglob('*') if file.is_file());scratch.cleanup();report['ssdOwnedScratchRemoved']=not pathlib.Path(scratch.name).exists()
 if failure:report.update(state='bounded_resource_refusal',error=failure)
 elif child.returncode:report.update(state='failed',error=report.get('error') or 'Original gradient worker failed; see preserved log.')
 save_report(report);print(json.dumps({key:report.get(key) for key in ('state','error','maximumPaddedResidues','parentWallSeconds','observedParentPeakRSSBytes')}),flush=True);raise SystemExit(0 if child.returncode==0 and not failure else 1)
if a.compiler_dump_directory:
 dump=pathlib.Path(a.compiler_dump_directory).resolve()
 if any(character.isspace() for character in str(dump)):raise ValueError('Compiler diagnostic directory must not contain whitespace.')
 dump.mkdir(parents=True,exist_ok=True);os.environ['XLA_FLAGS']=os.environ.get('XLA_FLAGS','')+' --xla_dump_to='+str(dump)+' --xla_dump_hlo_as_text'
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
report={'state':'input_preflight_passed' if a.preflight_only else 'gradient_pending','scope':'Original complete modality preset, input preparation and losses; one original-sampled CPU float32 model gradient including its full forward; the complete original design pool is loaded when requested. No separately retained standalone prediction executable, trajectory optimization, ProteinMPNN, held-out refold, acceptance or biological claim. No original thresholds changed.','source':source,'targetSha256':target_sha,'settings':json_compatible(settings),'settingsSha256':fe.checksum(fe.canonical(json_compatible(settings)).encode()),'model':'model_1_multimer_v3','parameterSha256':checkpoint_sha,'seed':a.seed,'maximumPaddedResidues':padded,'inputChainLengths':{state:{chain:len(protein) for chain,protein in values.items()} for state,values in states.items()},'executionOverrides':{'subbatch_size':a.subbatch_size} if a.subbatch_size is not None else {},'backend':'cpu','precision':'float32','compilerEnvironment':{'XLA_FLAGS':os.environ.get('XLA_FLAGS',''),'JAX_ENABLE_COMPILATION_CACHE':os.environ.get('JAX_ENABLE_COMPILATION_CACHE','default')},'jax':jax.__version__,'jaxlib':importlib.metadata.version('jaxlib'),'scaffoldSha256':hashlib.sha256(pathlib.Path(design.binder.scaffold).read_bytes()).hexdigest() if design.binder.scaffold else None,'activeLosses':list(losses),'standaloneForwardExecuted':False,'gradientIncludesFullForward':True,'compileCacheSize':1};save_report(report);print(json.dumps({'stage':'preflight','padded':padded,'inputChainLengths':report['inputChainLengths']}),flush=True)
if a.preflight_only:raise SystemExit(0)
try:
 tape=None
 if a.ssd_directory:
  from ssd_checkpoint import DiskTape,alphafold_disk_tape
  tape=DiskTape(a.ssd_owned_directory or a.ssd_directory,max_bytes=int(a.ssd_max_gib*1024**3));report['ssdOffload']={'state':'experimental','backend':'cpu','maximumTapeBytes':tape.max_bytes,'reserveBytes':tape.reserve_bytes};save_report(report)
 started=time.perf_counter();bucket=campaign_length_bucket(settings);target_lengths={len(protein) for protein in prepare_targets(design,longest_crop=True).values()};target_pad=padded_prediction_length(max(target_lengths),bucket) if len(target_lengths)>1 else 0;groups=(design.binder_chains,) if design.binder.copies>1 and design.oligomer_tie=='symmetric' else ();padded_states=pad_design_chains(states,bucket,target_pad);report['actualGradientStatePaddedResidues']={name:padded_prediction_length(sum(len(protein) for protein in chains.values()),bucket) for name,chains in padded_states.items()};report['gradientGraphResidues']={name:sum(len(protein) for protein in chains.values()) for name,chains in padded_states.items()};report['shapeAccountingNote']='actualGradientStatePaddedResidues is the rounded bucket estimate; gradientGraphResidues counts the actual original per-chain padded gradient inputs.';report['effectiveSubbatchSize']=campaign_subbatch_size(settings,padded);save_report(report);model=model_class()(presets=('model_1_multimer_v3',),models=('model_1_multimer_v3',),data_dir=str(checkpoint.parent),key=jax.random.PRNGKey(a.seed),max_cache_size=1,num_recycle=settings.get('design_recycles',DEFAULT_SETTINGS['design_recycles']),cyclic_offset_mode=resolve_cyclic_offset_mode(settings),subbatch_size=report['effectiveSubbatchSize'],attention_backend='stock',use_cueq=False,length_bucket_size=bucket,multi_chain_binders=groups,target_pad_length=target_pad,amino_acid_bias=design.binder.amino_acid_bias);report['useRemat']=all(runner.config.model.global_config.use_remat for runner in model.alphafold_runners.values());assert report['useRemat'];loaded=time.perf_counter()
 report['currentStage']='model_parameters_loaded';report['parameterLogicalBytes']=sum(int(value.nbytes) for value in jax.tree.leaves(model.model_parameters));save_report(report)
 if a.full_design_pool:
  from campaign_profile import ensemble_models
  selection=ensemble_models(os.path.abspath(sys.executable),settings,fe.UPSTREAM);report['originalModelSelection']=selection
  model=model_class()(presets=tuple(selection['designModels']),models=tuple(selection['designModels']),data_dir=str(checkpoint.parent),key=jax.random.PRNGKey(a.seed),max_cache_size=1,num_recycle=settings.get('design_recycles',DEFAULT_SETTINGS['design_recycles']),cyclic_offset_mode=resolve_cyclic_offset_mode(settings),subbatch_size=report['effectiveSubbatchSize'],attention_backend='stock',use_cueq=False,length_bucket_size=bucket,multi_chain_binders=groups,target_pad_length=target_pad,amino_acid_bias=design.binder.amino_acid_bias)
  report['parameterLogicalBytes']=sum(int(value.nbytes) for value in jax.tree.leaves(model.model_parameters));report['residentDesignModels']=list(model.models)
 class ProfileComplete(Exception):pass
 if a.graph_profile or a.compile_profile:
  original_compile=model._compiled_sequence_gradients
  def capture(*args,**kwargs):
   compiled=original_compile(*args,**kwargs)
   class Captured:
    def lower(self,*operands):
     from amme import graph_memory
     report['currentStage']='abstract_gradient_trace';save_report(report)
     report['gradientGraph']=graph_memory(jax.make_jaxpr(compiled)(*operands));report['state']='gradient_graph_profiled_not_executed'
     if a.compile_profile:
      report['currentStage']='gradient_compilation';save_report(report);before=time.perf_counter();executable=compiled.lower(*operands).compile();analysis=executable.memory_analysis();report['compileSeconds']=time.perf_counter()-before;report['compiledMemoryAnalysis']={name:getattr(analysis,name) for name in ('argument_size_in_bytes','output_size_in_bytes','temp_size_in_bytes','alias_size_in_bytes')};report['state']='gradient_compiled_not_executed'
     report['currentStage']='profile_complete';save_report(report);raise ProfileComplete()
   return Captured()
  model._compiled_sequence_gradients=capture
 else:
  original_compile=model._compiled_sequence_gradients
  def measured_compile(*args,**kwargs):
   compiled=original_compile(*args,**kwargs)
   class Measured:
    def lower(self,*operands):
     report['currentStage']='gradient_compilation';save_report(report);lowered=compiled.lower(*operands)
     class Plan:
      def compile(self):
       before=time.perf_counter();executable=lowered.compile();report['compileSeconds']=time.perf_counter()-before
       try:
        analysis=executable.memory_analysis();report['compiledMemoryAnalysis']={name:getattr(analysis,name) for name in ('argument_size_in_bytes','output_size_in_bytes','temp_size_in_bytes','alias_size_in_bytes')}
       except Exception as error:report['compiledMemoryAnalysisUnavailable']=str(error)
       report['currentStage']='gradient_execution';save_report(report);return executable
     return Plan()
    def __call__(self,*operands):return compiled(*operands)
   return Measured()
  model._compiled_sequence_gradients=measured_compile
 original_resolve=model._resolve_model_name
 def observed_model_selection(value):
  chosen=original_resolve(value);report['model']=chosen;report['modelKeyAfterSelection']=jax.random.key_data(model.key).tolist()
  selected_checkpoint=checkpoint.parent/('params_'+chosen+'.npz')
  with selected_checkpoint.open('rb') as stream:report['parameterSha256']=hashlib.file_digest(stream,'sha256').hexdigest()
  assert report['parameterSha256']==json.loads((ROOT/'scientific/af2-parameters.json').read_text())['models'][chosen]
  save_report(report);return chosen
 model._resolve_model_name=observed_model_selection
 from amme import rematerialized_subbatches
 report['modelSelectionProtocol']='upstream_sampling_with_original_rng_advance';report['currentStage']='gradient_compilation_and_execution';save_report(report)
 with (rematerialized_subbatches(structure=a.remat_structure,triangles=a.remat_triangles,prevent_cse=a.remat_prevent_cse) if a.remat_subbatches else contextlib.nullcontext()) as remat_stats:
  with (alphafold_disk_tape(tape) if tape else contextlib.nullcontext()):
   try:predictions,grads,loss=model.sequence_gradients(states,losses);jax.block_until_ready(grads)
   except ProfileComplete:
    if remat_stats:report['amme']=remat_stats
    save_report(report);raise SystemExit(0)
  if remat_stats:report['amme']=remat_stats
 if tape:
  report['ssdOffload'].update(checkpoints=tape.checkpoints,bytesWritten=tape.bytes_written,bytesRead=tape.bytes_read);assert tape.checkpoints>0,'SSD adapter did not intercept original layer-stack scans.'
  tape.close()
 value=float(loss);assert np.isfinite(value)
 arrays={};norms={}
 for name,gradient in grads.items():
  values=np.asarray(gradient);assert np.isfinite(values).all();arrays['gradient_'+name]=values;norms[name]=float(np.linalg.norm(values))
 assert any(value>0 for name,value in norms.items() if name in design.binder_chains)
 for name,prediction in predictions.items():
  for chain,protein in prediction.protein_complex.items():assert np.isfinite(np.asarray(protein.atoms)).all();arrays[name+'_'+chain+'_positions']=np.asarray(protein.atoms)
  write_structure(prediction.protein_complex,str(output.with_name(output.stem+'_'+name+'.cif')),plddt=prediction.metrics.get('plddt'))
 np.savez(output.with_suffix('.npz'),**arrays);assert fe.verify_source()==source and hashlib.sha256(target.read_bytes()).hexdigest()==target_sha;report.update(state='full_gradient_passed',loadSeconds=loaded-started,firstGradientIncludingCompilationSeconds=time.perf_counter()-loaded,loss=value,gradientNorms=norms,peakProcessRSSBytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss);save_report(report);print(json.dumps({key:report[key] for key in ('state','loss','gradientNorms','peakProcessRSSBytes')}),flush=True)
except BaseException as error:
 if isinstance(error,SystemExit) and error.code==0:raise
 report.update(state='failed',error=str(error));save_report(report);raise
finally:
 if tape and not tape.closed:
  report['ssdOffload'].update(checkpoints=tape.checkpoints,bytesWritten=tape.bytes_written,bytesRead=tape.bytes_read);tape.close();save_report(report)
