"""Two original trained-model optimizer updates; a small technical parity case.

This does not shorten a Fab campaign or assert Fab acceptance. Separate worker
processes compare the original optimizer/model path with the reusable AMME tape.
"""
import argparse
import contextlib
import hashlib
import json
import os
import pathlib
import sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'vendor/bindcraft2')]
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['reference','amme'],required=True)
p.add_argument('--parameters',required=True);p.add_argument('--target',required=True);p.add_argument('--output',required=True)
p.add_argument('--subbatch-size',type=int,choices=[1,2,4],default=1)
p.add_argument('--prevent-cse',action='store_true')
p.add_argument('--attention-only',action='store_true')
p.add_argument('--reference-inputs',help='Diagnostic only: compare local derivatives/updates at each saved original input; not an independent continuous trajectory.')
p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS);a=p.parse_args()
output=pathlib.Path(a.output).resolve()
from amme_campaign import FabSession,atomic_json
if not a.worker:
    if output.exists():raise SystemExit('Choose a new parity report.')
    output.parent.mkdir(parents=True,exist_ok=True)
    from amme_worker import run_guarded
    result=run_guarded([os.path.abspath(sys.executable),'-I','-B',str(pathlib.Path(__file__).resolve()),
        *sys.argv[1:],'--worker'],env=os.environ,folder=output.parent)
    raise SystemExit(result.returncode)

import jax
import numpy as np
from af2_native import model_class,float32_states
from bindcraft.settings import load_settings,campaign_over_presets,build_design_settings
from bindcraft.protein_preparation import initialize_design_trajectory
from bindcraft.trajectory import build_stage_plan,run_gradient_design_stage
from bindcraft.target_schedule import FixedTargetSchedule
from campaign_profile import ensemble_models
import fold_engine as fe

source=fe.verify_source();target=pathlib.Path(a.target).resolve();target_sha=hashlib.sha256(target.read_bytes()).hexdigest()
settings=load_settings(campaign_over_presets({'modality':'binder','binder_lengths':[8],'design_models':3,
    'subbatch_size':a.subbatch_size,'campaign_seed':42,'attention_backend':'stock','use_cueq':False,
    'targets':[{'name':'target','target_path':str(target),'chains':'A'}]}))
design=build_design_settings(settings)
states,_,losses=initialize_design_trajectory(design,jax.random.PRNGKey(42));states=float32_states(states)
selection=ensemble_models(os.path.abspath(sys.executable),settings,fe.UPSTREAM)
pins=json.loads((ROOT/'scientific/af2-parameters.json').read_text())['models']
for model in selection['designModels']:
    with (pathlib.Path(a.parameters)/('params_'+model+'.npz')).open('rb') as stream:
        assert hashlib.file_digest(stream,'sha256').hexdigest()==pins[model]
identity={'source':source,'targetSha256':target_sha,'checkpointSha256':{m:pins[m] for m in selection['designModels']}}
session=FabSession(os.environ['FOLD_AMME_SCRATCH'],identity=identity,stage_path=output.with_suffix('.stage.json'),prevent_cse=a.prevent_cse,attention_only=a.attention_only) if a.mode=='amme' else None
base=model_class();cls=session.model_type(base) if session else base
model=cls(presets=tuple(selection['designModels']),models=tuple(selection['designModels']),
    data_dir=str(pathlib.Path(a.parameters).resolve()),key=jax.random.PRNGKey(42),max_cache_size=1,
    num_recycle=settings['design_recycles'],subbatch_size=a.subbatch_size,attention_backend='stock',use_cueq=False,length_bucket_size=32)
arrays={};steps=[];original=model.sequence_gradients
reference_inputs=None
if a.reference_inputs:
    reference_path=pathlib.Path(a.reference_inputs)
    reference_report=json.loads(reference_path.with_suffix('.json').read_text())
    assert reference_report['source']==source and reference_report['targetSha256']==target_sha
    assert reference_report['seed']==42 and reference_report['selection']==selection
    reference_inputs=np.load(reference_path,allow_pickle=False)
def observed(*args,**kwargs):
    index=len(steps)
    if reference_inputs is not None:
        # Re-anchor ONLY this diagnostic. This isolates the derivative and the
        # original local optimizer update from previous-step input drift. Keep
        # the separate free-running failure report; this is not its replacement.
        for state,chains in args[0].items():
            for chain,protein in list(chains.items()):
                value=reference_inputs[f'input_{index}_{state}_{chain}']
                assert value.shape==protein.sequence.shape
                chains[chain]=protein.replace(sequence=jax.numpy.asarray(value))
    for state,chains in args[0].items():
        for chain,protein in chains.items():arrays[f'input_{index}_{state}_{chain}']=np.asarray(protein.sequence)
    result=original(*args,**kwargs);predictions,gradients,loss=result;jax.block_until_ready(gradients)
    for chain,value in gradients.items():arrays[f'gradient_{index}_{chain}']=np.asarray(value)
    for state,prediction in predictions.items():
        for chain,protein in prediction.protein_complex.items():arrays[f'positions_{index}_{state}_{chain}']=np.asarray(protein.atoms)
        for metric,value in prediction.metrics.items():arrays[f'metric_{index}_{state}_{metric}']=np.asarray(value)
    steps.append({'loss':float(loss),'keyAfterSelection':jax.random.key_data(model.key).tolist(),
                  'ssdLiveBytesAfterStep':session.tape.live_bytes if session else None})
    return result
model.sequence_gradients=observed
try:
    optimizer=build_stage_plan(design,losses,(),model,states)[0].sequence_optimizer
    final,_=run_gradient_design_stage(states,model,losses,optimizer,FixedTargetSchedule(2),select_best_round=False)
    assert optimizer.sequence_update_count==2
    for state,chains in final.items():
        for chain,protein in chains.items():arrays[f'updated_{state}_{chain}']=np.asarray(protein.sequence)
    for index,value in enumerate(jax.tree.leaves(optimizer.optimizer_state)):arrays[f'optimizer_{index}']=np.asarray(value)
    assert all(np.isfinite(value).all() for value in arrays.values())
    if session:assert session.completed_gradients==2 and session.tape.live_bytes==0
    assert fe.verify_source()==source
    np.savez(output.with_suffix('.npz'),**arrays)
    atomic_json(output,{'state':'two_matched_input_steps_passed' if a.reference_inputs else 'two_updates_passed','scope':'Two original local optimizer calculations at saved reference inputs; not a continuous trajectory or Fab run.' if a.reference_inputs else 'Two genuine original binder optimizer updates on a small technical input, not Fab or a full trajectory.',
        'subbatchSize':a.subbatch_size,'mode':a.mode,'referenceInputReanchoring':bool(a.reference_inputs),'source':source,'targetSha256':target_sha,'selection':selection,'seed':42,'steps':steps,
        'optimizerUpdates':optimizer.sequence_update_count,'originalOptimizerIterations':optimizer.iterations,
        'ssdCheckpoints':session.tape.checkpoints if session else 0,'ssdPeakBytes':session.tape.peak_live_bytes if session else 0})
finally:
    if session:jax.effects_barrier();session.tape.close()
    if reference_inputs is not None:reference_inputs.close()
