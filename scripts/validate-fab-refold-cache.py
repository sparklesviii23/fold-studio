"""Real held-out Fab fixture checks and trained-model parity for cache eviction.

The full fixture is an actual rejected ProteinMPNN refold. No production attempt
is resumed, and a separate held-out probe never overrides the source rejection.
"""
import argparse, gc, hashlib, json, os, pathlib, sys, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'scientific'), str(ROOT/'vendor/bindcraft2')]
sys.dont_write_bytecode = True
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--small-parity', action='store_true')
parser.add_argument('--folder', required=True, type=pathlib.Path)
parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
a = parser.parse_args(); folder = a.folder.absolute()
from amme_campaign import FabSession, atomic_json, environment
if not a.worker:
    from amme_worker import run_guarded
    if folder.exists(): raise SystemExit('Choose a new report directory.')
    folder.mkdir(parents=True)
    result = run_guarded([os.path.abspath(sys.executable), '-I', '-u', '-B',
        str(pathlib.Path(__file__).resolve()), *sys.argv[1:], '--worker'],
        env=environment(os.environ), folder=folder,
        scratch_parent=ROOT.parent/'validation/architect-fab-ssd',
        timeout_seconds=900 if a.small_parity else 2400)
    raise SystemExit(result.returncode)

import jax
import numpy as np
from af2_native import model_class, float32_states
from bindcraft.protein import Protein, ResidueFlags, has_residue_flag, write_structure
from bindcraft.protein_preparation import initialize_design_trajectory
from bindcraft.settings import load_settings, build_design_settings
from bindcraft.filters import design_stage_filters, evaluate_design_filters
from bindcraft.MPNN_stage import predict_validation_ensemble
import fold_engine as fe
started = time.monotonic(); source = fe.verify_source()
baseline = json.loads((ROOT/'reports/amme-fab-memory-scheduler-gradient.json').read_text())
assert source == baseline['source']
settings = load_settings(baseline['settings']); design = build_design_settings(settings)
original, _, _ = initialize_design_trajectory(design, jax.random.PRNGKey(42))
original = float32_states(original)
fixture = ROOT/'reports/architect-fab-components-v2/COMPONENT_OUTPUT/2_Refolded/Complexes/engineering_full_fab_fixture_candidate1.cif'
observed = Protein.from_structure(str(fixture)); mapping={'target_target':'A','binder_0':'B','binder_1':'C'}
complex_ = {}
for name, protein in original['target'].items():
    known = observed[mapping[name]]; assert len(protein) == len(known)
    fixed = ~np.asarray(has_residue_flag(protein.flags, ResidueFlags.DESIGN))
    np.testing.assert_array_equal(np.asarray(protein.sequence).argmax(-1)[fixed], np.asarray(known.sequence).argmax(-1)[fixed])
    complex_[name] = protein.replace(sequence=known.sequence, atoms=known.atoms, atom_mask=known.atom_mask)
assert {k:len(p) for k,p in complex_.items()} == {'binder_0':231,'binder_1':213,'target_target':115}
if a.small_parity:
    # Only this labelled technical parity fixture is truncated. The separate
    # full-size validation retains every residue and both complete domains.
    complex_ = {name:p.trimmed_to(12 if name=='target_target' else 8) for name,p in complex_.items()}
states = float32_states({'target':complex_, 'binder_alone':{k:p for k,p in complex_.items() if k.startswith('binder_')}})
models = tuple(baseline['originalModelSelection']['validationModels'])
pins = json.loads((ROOT/'scientific/af2-parameters.json').read_text())['models']
parameters = ROOT.parent/'models/alphafold'
for name in models:
    with (parameters/('params_'+name+'.npz')).open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == pins[name]
identity = {'source':source,'fixtureSha256':hashlib.sha256(fixture.read_bytes()).hexdigest(),
            'checkpointSha256':{m:pins[m] for m in models}}
session = FabSession(os.environ['FOLD_AMME_SCRATCH'], identity=identity, stage_path=folder/'cache-stage.json')
base = model_class(); options = dict(presets=models, models=models, data_dir=str(parameters),
    key=jax.random.PRNGKey(42), num_recycle=settings['validation_recycles'],
    dropout=False, subbatch_size=4, attention_backend='stock', use_cueq=False,
    max_cache_size=1, length_bucket_size=32)
inferences=[]; arrays={}
def capture(predictions, prefix):
    for state, prediction in predictions.items():
        for name,p in prediction.protein_complex.items():
            for field in ('sequence','atoms','atom_mask','flags','residue_index'):
                arrays[f'{prefix}/{state}/{name}/{field}'] = np.asarray(getattr(p,field))
        for name,value in prediction.metrics.items(): arrays[f'{prefix}/{state}/metrics/{name}']=np.asarray(value)
try:
    if a.small_parity:
        reference=base(**options)
        for heldout in models: capture(reference.predict(states,model=heldout),'reference/'+heldout)
        expected_key=np.asarray(reference.key); del reference; jax.clear_caches(); gc.collect()
    class Observed(session.model_type(base)):
        def predict(self, protein_states, *args, **kwargs):
            atomic_json(folder/'progress.json',{'stage':'predicting','model':kwargs.get('model'),'completed':inferences,'elapsedSeconds':time.monotonic()-started})
            before=time.monotonic(); result=super().predict(protein_states,*args,**kwargs)
            for value in result.values(): jax.block_until_ready([p.atoms for p in value.protein_complex.values()])
            inferences.append({'model':kwargs.get('model'),'seconds':time.monotonic()-before,'states':list(protein_states),'cacheReleases':session.prediction_cache_releases})
            atomic_json(folder/'progress.json',{'stage':'prediction_completed','completed':inferences,'elapsedSeconds':time.monotonic()-started})
            print('FOLD_COMPONENT '+json.dumps(inferences[-1]),flush=True)
            return result
    model=Observed(**options)
    if a.small_parity:
        for heldout in models: capture(model.predict(states,model=heldout),'bounded/'+heldout)
        np.testing.assert_array_equal(model.key,expected_key)
        comparisons={}
        for key,value in list(arrays.items()):
            if not key.startswith('reference/'):continue
            other=arrays[key.replace('reference/','bounded/',1)]
            assert np.isfinite(value).all() and np.isfinite(other).all()
            np.testing.assert_allclose(other,value,rtol=1e-4,atol=1e-5)
            comparisons[key]={'shape':list(value.shape),'exactEqual':bool(np.array_equal(value,other)),'maxAbsoluteDifference':float(np.abs(value.astype(float)-other.astype(float)).max(initial=0))}
        np.savez(folder/'arrays.npz',**arrays)
        result={'state':'passed','scope':'Small32-residue trained multimer bound/unbound fixture, original3validationrecycles; originalfloat32 vs boundedcache2/4 sequentialinference. Not a fullFab run.','comparisons':comparisons,'rngEqual':True,'tolerance':{'rtol':1e-4,'atol':1e-5}}
    else:
        filters=design_stage_filters(design,states,'final',campaign_filters=design.filters)
        ensemble=predict_validation_ensemble(model,states,models,filters)
        original_outcome,metrics=evaluate_design_filters(filters,states,ensemble.predictions)
        probes=[]
        for heldout in models:
            if heldout in ensemble.model_predictions:continue
            predicted=model.predict(states,model=heldout)
            outcome,measured=evaluate_design_filters(filters,states,predicted)
            probes.append({'model':heldout,'filterOutcome':True if outcome is True else list(outcome),'scope':'Separate held-out probe on the exact same fixture inputs after the source short-circuit. Does not override original rejection.'})
            write_structure(predicted['target'].protein_complex,str(folder/(heldout+'.cif')),metadata={'scope':'Engineering fixture probe; computational acceptance not asserted'})
        assert {i['model'] for i in inferences}==set(models)
        assert not model.prediction_compile_cache.compiled_functions
        assert not model.gradient_compile_cache.compiled_functions
        from bindcraft.rank import rerank_campaign
        output=fixture.parents[2]
        _,ranked,directions=rerank_campaign(str(output),['i_pDAE'],'candidates',output=str(folder/'engineering-candidate-rank.csv'))
        assert ranked and all(row['outcome']=='rejected' for row in ranked)
        from worker import Service
        library=Service(folder/'INSPECTION_LIBRARY'); project=library.project_create({'name':'Full Fab engineering components · not production'})
        record=library.import_structure({'projectId':project['id'],'path':str(fixture),'name':'Engineering Fab refold · rejected by original filter','source':'Real full Fab component test · not an accepted production design','metadata':{'engineeringValidation':identity,'computationalAcceptance':'not_asserted','originalCandidateOutcome':'rejected'}})
        assert (library.root/'assets'/record['data']['asset']).read_bytes()==fixture.read_bytes()
        archive=folder/'component-inspection-project.zip';library.export_project({'id':project['id'],'path':str(archive)});library.db.close()
        import zipfile
        with zipfile.ZipFile(archive) as z: assert z.read('assets/'+record['data']['asset'])==fixture.read_bytes()
        result={'state':'passed','scope':'Two actual full559-residue multimer bound/unbound model2/4 fixture refolds with original3recycles. Same-process cache-release regression. Genuine earlier mutation/MPNN outputs ranked/imported as rejected inspection artifacts. Not an accepted or completed production Fab campaign.','inputChainLengths':{k:len(p) for k,p in complex_.items()},'originalEnsembleModelsExecuted':list(ensemble.model_predictions),'originalConfidenceRejection':ensemble.failed_confidence,'originalFilterOutcome':True if original_outcome is True else list(original_outcome),'separateHeldoutProbes':probes,'rankedRejectedCandidateRows':len(ranked),'rankingDirections':directions,'inspectionRecordId':record['id'],'libraryAndProjectBytesExact':True,'fullOriginalScientificRunCompleted':False,'fullNewEngineeringTrajectoryExecuted':False}
    result.update(identity=identity,validationModels=list(models),originalValidationRecycles=settings['validation_recycles'],inferences=inferences,cacheReleaseCount=session.prediction_cache_releases,wallSeconds=time.monotonic()-started,cacheAdapterSha256=hashlib.sha256((ROOT/'scientific/amme_campaign.py').read_bytes()).hexdigest())
    assert fe.verify_source()==source
    atomic_json(folder/'result.json',result); print(json.dumps({'state':'passed','wallSeconds':result['wallSeconds'],'report':str(folder/'result.json')}),flush=True)
finally:
    jax.effects_barrier(); session.tape.close()
