"""Exercise genuine full AF2 model and sequence gradients, never random model weights."""
import argparse,functools,hashlib,json,os,pathlib,resource,sys,time
os.environ['JAX_PLATFORMS']='cpu';os.environ['XLA_PYTHON_CLIENT_PREALLOCATE']='false';sys.dont_write_bytecode=True
BASE=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE/'vendor/bindcraft2'))
p=argparse.ArgumentParser();p.add_argument('--parameters',required=True);p.add_argument('--output',required=True);p.add_argument('--gradient',action='store_true');args=p.parse_args()
import jax,jax.numpy as jnp,numpy as np
from bindcraft.af2 import AlphaFoldDesignModel
from bindcraft.protein import Protein,write_structure
from bindcraft.loss import DesignLoss,plddt_loss
start=time.perf_counter();print('Loading trained model_1_ptm on CPU.',flush=True)
model=AlphaFoldDesignModel(data_dir=args.parameters,key=jax.random.PRNGKey(2718),num_recycle=0,dropout=False,length_bucket_size=1,attention_backend='stock',use_cueq=False)
loaded=time.perf_counter();protein=Protein.empty(12,jax.random.PRNGKey(2718));states={'binder_alone':{'binder':protein}}
report={'scope':'Genuine full model technical input, not a validated binder','jax':jax.__version__,'devices':[str(d) for d in jax.devices()],'seed':2718,'residues':12,'recycles':0,'model':'model_1_ptm','parameterSha256':hashlib.sha256((pathlib.Path(args.parameters)/'params_model_1_ptm.npz').read_bytes()).hexdigest(),'loadSeconds':loaded-start}
print('Executing complete AlphaFold forward; first compilation may be slow.',flush=True)
prediction=model.predict(states)['binder_alone'];jax.block_until_ready(prediction.protein_complex['binder'].atoms);forward=time.perf_counter();positions=np.asarray(prediction.protein_complex['binder'].atoms)
if not np.isfinite(positions).all():raise RuntimeError('Nonfinite full-model coordinates.')
report.update(forwardSeconds=forward-loaded,coordinateShape=list(positions.shape),resolvedAtoms=int(np.asarray(prediction.protein_complex['binder'].atom_mask).sum()))
output=pathlib.Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);write_structure(prediction.protein_complex,str(output.with_suffix('.cif')));output.write_text(json.dumps({**report,'state':'forward_passed_gradient_pending'},indent=2)+'\n')
if args.gradient:
 print('Executing full-model sequence backpropagation.',flush=True)
 losses={'plddt_loss':DesignLoss(plddt_loss,1.0,frozenset({'binder_alone'}))}
 predictions,grads,loss=model.sequence_gradients(states,losses);jax.block_until_ready(grads);gradient=np.asarray(grads['binder']);value=float(loss)
 if not np.isfinite(gradient).all() or not np.isfinite(value):raise RuntimeError('Nonfinite loss/gradient.')
 report.update(gradientSeconds=time.perf_counter()-forward,loss=value,gradientShape=list(gradient.shape),gradientNorm=float(np.linalg.norm(gradient)))
 np.savez(output.with_suffix('.npz'),gradient=gradient)
report.update(state='executed_not_reference_validated',totalSeconds=time.perf_counter()-start,peakProcessRSSBytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss);output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)
