"""Explicit float32 execution policy around unmodified BindCraft2 AF2 algorithms.

Half-precision sequence VJPs failed Metal/CPU comparison. This adapter keeps
sequence optimization states and model internals in float32; it never substitutes
model layers, objectives, gradients or scientific rejection criteria.
Import only inside an isolated scientific runtime.
"""
def float32_states(states):
 import jax.numpy as jnp
 return {state:{chain:p.replace(sequence=p.sequence.astype(jnp.float32),atoms=p.atoms.astype(jnp.float32)) for chain,p in proteins.items()} for state,proteins in states.items()}

def model_class():
 from bindcraft.af2 import AlphaFoldDesignModel
 class Float32AlphaFoldDesignModel(AlphaFoldDesignModel):
  def _alphafold_runner(self,*args,**kwargs):
   runner=super()._alphafold_runner(*args,**kwargs);runner.config.model.global_config.bfloat16=False;return runner
  def predict(self,protein_states,*args,**kwargs):return super().predict(float32_states(protein_states),*args,**kwargs)
  def sequence_gradients(self,protein_states,*args,**kwargs):return super().sequence_gradients(float32_states(protein_states),*args,**kwargs)
 return Float32AlphaFoldDesignModel

def install_trajectory_policy():
 """Process-local source adapter. Original vendor files remain checksum-identical.
 Initialization casts ensure upstream optimizers preserve float32 when updating
 shared sequence states. Configuration and loss/filter logic remain upstream.
 """
 from bindcraft import trajectory,campaign
 original=getattr(trajectory.initialize_design_trajectory,'_fold_original',trajectory.initialize_design_trajectory)
 def initialize(*args,**kwargs):
  states,groups,losses=original(*args,**kwargs);return float32_states(states),groups,losses
 initialize._fold_original=original
 trajectory.initialize_design_trajectory=initialize;campaign.initialize_design_trajectory=initialize
 cls=model_class();campaign.AlphaFoldDesignModel=cls;return cls
