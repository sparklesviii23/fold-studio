"""Controlled full AF2 gradient without retaining a separate prediction executable.

Reuses an existing exact CPU reference recipe and trained checkpoint. No model,
gradient, filter or application resource limit is changed by this experiment.
"""
import argparse,hashlib,json,os,pathlib,resource,sys,time
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--parameters',required=True);p.add_argument('--target');p.add_argument('--reference',required=True);p.add_argument('--output',required=True);a=p.parse_args();reference_path=pathlib.Path(a.reference).resolve();baseline=json.loads(reference_path.read_text());output=pathlib.Path(a.output).resolve()
if output.exists() or output.with_suffix('.npz').exists():raise SystemExit('Use a new experiment output path.')
if baseline['backend']!='cpu' or baseline['precision']!='float32' or baseline['state']!='executed_not_reference_validated':raise ValueError('A completed real float32 CPU reference is required.')
if os.environ.get('METALJAX_MEM_GOVERNOR')!='1' or not 1<=int(os.environ.get('METALJAX_MEM_BUDGET_MB','0'))<=8192:raise ValueError('This experiment requires the enabled Metal governor and a budget no larger than 8 GiB.')
os.environ['JAX_PLATFORMS']='metal';os.environ['XLA_PYTHON_CLIENT_PREALLOCATE']='false'
sys.path.insert(0,str(ROOT/'scientific'));sys.path.insert(0,str(ROOT/'vendor/bindcraft2'))
import fold_engine as fe
fe.verify_source()
import jax,jax.numpy as jnp,numpy as np
from bindcraft.af2 import AlphaFoldDesignModel
from bindcraft.protein import Protein,write_structure
from bindcraft.loss import DesignLoss,plddt_loss
if any(device.platform.lower()!='metal' for device in jax.devices()):raise ValueError('Actual Metal device required; CPU fallback refused.')
model_name=baseline['model'];checkpoint=pathlib.Path(a.parameters)/('params_'+model_name+'.npz');checksum=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
if checksum(checkpoint)!=baseline['parameterSha256']:raise ValueError('Reference checkpoint differs.')
if bool(a.target)!=bool(baseline['targetResidues']) or (a.target and checksum(pathlib.Path(a.target))!=baseline['targetSha256']):raise ValueError('Reference target differs.')
start=time.monotonic();model=AlphaFoldDesignModel(presets=model_name,data_dir=a.parameters,key=jax.random.PRNGKey(baseline['seed']),num_recycle=baseline['recycles'],dropout=False,length_bucket_size=1,attention_backend='stock',use_cueq=False,subbatch_size='auto',max_cache_size=1)
for runner in model.alphafold_runners.values():runner.config.model.global_config.bfloat16=False
if not all(r.config.model.global_config.use_remat for r in model.alphafold_runners.values()):raise ValueError('Upstream recomputation policy differs.')
protein=Protein.empty(baseline['residues'],jax.random.PRNGKey(baseline['seed']));protein=protein.replace(sequence=jnp.asarray(np.random.default_rng(baseline['seed']).normal(0,.01,(baseline['residues'],20)).astype(np.float32)));state='binder_alone';states={state:{'binder':protein}}
if a.target:
 target=next(iter(Protein.from_structure(a.target).values()));target=target.replace(sequence=target.sequence.astype(jnp.float32),atoms=target.atoms.astype(jnp.float32));state='complex';states={state:{'target':target,'binder':protein}}
input_sha=hashlib.sha256(np.asarray(protein.sequence).tobytes()).hexdigest()
if input_sha!=baseline['inputSha256']:raise ValueError('Exact reference sequence input differs.')
report={key:baseline[key] for key in ('seed','residues','recycles','model','precision','parameterSha256','inputSha256','targetResidues','targetSha256')};report.update(state='gradient_pending',backend='metal',jax=jax.__version__,devices=[str(d) for d in jax.devices()],sourceRevision=fe.PIN,reference=str(reference_path),referenceSha256=checksum(reference_path),standaloneForwardExecuted=False,gradientIncludesFullForward=True,useRemat=True,compileCacheSize=1,budgetMiB=int(os.environ['METALJAX_MEM_BUDGET_MB']),scope='Genuine full trained-model sequence gradient, with no separately retained standalone-prediction executable. Resource experiment and narrow CPU comparison only; not a design trajectory or biological validation.')
output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n');print('Executing full-model gradient directly; no standalone prediction first.',flush=True)
try:
 predictions,grads,loss=model.sequence_gradients(states,{'plddt_loss':DesignLoss(plddt_loss,1.,frozenset({state}))});jax.block_until_ready(grads);gradient=np.asarray(grads['binder']);positions=np.asarray(predictions[state].protein_complex['binder'].atoms);value=float(loss)
 if not np.isfinite(gradient).all() or not np.isfinite(positions).all() or not np.isfinite(value):raise ValueError('Nonfinite full-model output.')
 arrays={'gradient':gradient,'gradientPositions':positions,'inputSequence':np.asarray(protein.sequence)}
 if a.target:arrays['gradientTargetPositions']=np.asarray(predictions[state].protein_complex['target'].atoms)
 np.savez(output.with_suffix('.npz'),**arrays);write_structure(predictions[state].protein_complex,str(output.with_suffix('.cif')));cpu=np.load(reference_path.with_suffix('.npz'),allow_pickle=False);comparison={}
 for key in arrays:
  left=np.asarray(cpu[key],dtype=np.float64);right=np.asarray(arrays[key],dtype=np.float64)
  if left.shape!=right.shape:raise ValueError('Reference shape differs: '+key)
  delta=right-left;norm=np.linalg.norm(left);other=np.linalg.norm(right);comparison[key]={'rmsError':float(np.sqrt(np.mean(delta**2))),'relativeL2Error':float(np.linalg.norm(delta)/max(norm,1e-12)),'cosine':float(np.sum(left*right)/max(norm*other,1e-12))}
 passed=comparison['gradient']['relativeL2Error']<=.05 and comparison['gradient']['cosine']>=.99 and abs(value-baseline['loss'])<=.005 and all(v['rmsError']<=.1 for key,v in comparison.items() if 'Positions' in key)
 report.update(state='scoped_comparison_passed' if passed else 'scoped_comparison_failed',loss=value,lossAbsoluteError=abs(value-baseline['loss']),comparisons=comparison,thresholds={'gradientRelativeL2':.05,'gradientCosineMinimum':.99,'coordinateRmsAngstrom':.1,'lossAbsoluteError':.005},totalSeconds=time.monotonic()-start,peakProcessRSSBytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
 output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
 if not passed:raise SystemExit(1)
except Exception as error:
 report.update(state='resource_exhausted' if any(word in str(error).lower() for word in ('memory','budget','resource_exhausted')) else 'failed',error=str(error),totalSeconds=time.monotonic()-start,peakProcessRSSBytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss);output.write_text(json.dumps(report,indent=2)+'\n');raise
