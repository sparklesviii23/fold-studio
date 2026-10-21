"""Real trained AF2 forward/VJP fixture, explicitly CPU reference or CUDA test.

This fixed 16-residue unit test is not a binder campaign or trajectory-equivalence
claim. Qualification compares every output at the existing 1e-4/1e-5 tolerance.
"""
import argparse,json,os,pathlib
def main():
    p=argparse.ArgumentParser();p.add_argument('--parameters',required=True);p.add_argument('--backend',choices=['cpu','cuda'],required=True);p.add_argument('--output',required=True);a=p.parse_args()
    os.environ['JAX_PLATFORMS']=a.backend;os.environ['XLA_PYTHON_CLIENT_PREALLOCATE']='false'
    import jax,jax.numpy as jnp,numpy as np
    from bindcraft.af2 import AlphaFoldDesignModel
    from bindcraft.protein import Protein
    from bindcraft.loss import DesignLoss,plddt_loss
    expected='gpu' if a.backend=='cuda' else 'cpu'
    if any(d.platform!=expected for d in jax.devices()):raise ValueError('Requested numerical test device was not used.')
    model=AlphaFoldDesignModel(presets='model_1_multimer_v3',data_dir=a.parameters,key=jax.random.PRNGKey(42),num_recycle=1,dropout=False,length_bucket_size=1,attention_backend='stock',use_cueq=False,max_cache_size=1)
    for runner in model.alphafold_runners.values():runner.config.model.global_config.bfloat16=False
    protein=Protein.empty(16,jax.random.PRNGKey(42));protein=protein.replace(sequence=jnp.asarray(np.random.default_rng(42).normal(0,.01,(16,20)).astype(np.float32)))
    states={'binder_alone':{'binder':protein}}
    pred,grad,loss=model.sequence_gradients(states,{'plddt_loss':DesignLoss(plddt_loss,1.,frozenset({'binder_alone'}))});jax.block_until_ready(grad)
    values={'loss':np.asarray(loss),'gradient':np.asarray(grad['binder']),'positions':np.asarray(pred['binder_alone'].protein_complex['binder'].atoms),'input':np.asarray(protein.sequence)}
    if not all(np.isfinite(v).all() for v in values.values()):raise ValueError('Nonfinite trained numerical result.')
    np.savez_compressed(a.output,**values)
    print(json.dumps({'state':'executed','backend':a.backend,'jax':jax.__version__,'devices':[str(d) for d in jax.devices()],'residues':16,'model':'model_1_multimer_v3','recycles':1,'precision':'float32','scope':'Matched-input unit forward/gradient, not continuous-trajectory identity.'}))
if __name__=='__main__':main()
