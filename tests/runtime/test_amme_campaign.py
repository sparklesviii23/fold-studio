"""Real JIT/SSD lifecycle on tiny original Haiku scans; not model/Fab outputs."""
import json
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'vendor/bindcraft2')]
import haiku as hk
import jax
import jax.numpy as jnp
import numpy as np
from bindcraft.af.alphafold.model import layer_stack
from amme_campaign import FabSession
from bindcraft.prediction import CompiledModelCache


class SessionLifecycle(unittest.TestCase):
    def test_multistate_prediction_releases_executables_preserves_output_and_rng(self):
        class PredictionCalculation:
            def __init__(self, **kwargs):
                self.prediction_compile_cache = CompiledModelCache(kwargs['max_cache_size'])
                self.gradient_compile_cache = CompiledModelCache(kwargs['max_cache_size'])
                self.key = jax.random.PRNGKey(7)
            def predict(self, protein_states, model=None):
                self.key, key = jax.random.split(self.key)
                result = {}
                for name, value in protein_states.items():
                    operation = jax.jit(lambda x: jnp.sin(x) + jax.random.uniform(key, x.shape))
                    self.prediction_compile_cache.set(name, operation)
                    atoms = operation(value)
                    protein = SimpleNamespace(atoms=atoms,atom_mask=jnp.ones_like(atoms),sequence=value)
                    result[name] = SimpleNamespace(protein_complex={'chain':protein},metrics={'mean':atoms.mean()})
                return result
        states={'target':jnp.ones((8,3)), 'binder_alone':jnp.ones((5,3))}
        reference=PredictionCalculation(max_cache_size=1)
        with tempfile.TemporaryDirectory() as directory:
            path=pathlib.Path(directory)
            session=FabSession(path,identity={'scope':'prediction cache lifecycle'},stage_path=path/'stage.json')
            model=session.model_type(PredictionCalculation)()
            try:
                for heldout in ('model_2_multimer_v3','model_4_multimer_v3'):
                    expected=reference.predict(states,model=heldout)
                    actual=model.predict(states,model=heldout)
                    for state in states:
                        np.testing.assert_array_equal(actual[state].protein_complex['chain'].atoms,expected[state].protein_complex['chain'].atoms)
                    np.testing.assert_array_equal(model.key,reference.key)
                    self.assertFalse(model.prediction_compile_cache.compiled_functions)
                    self.assertFalse(model.gradient_compile_cache.compiled_functions)
                self.assertEqual(session.prediction_cache_releases,4)
            finally:session.tape.close()

    def test_original_scan_repeated_gradients_expire_only_completed_step(self):
        def function(x):
            return layer_stack.layer_stack(4)(hk.remat(lambda value:jnp.tanh(hk.Linear(8)(value))))(x).sum()
        transformed=hk.without_apply_rng(hk.transform(function))
        key=jax.random.PRNGKey(5);x=jnp.ones((2,8),jnp.float32)*.1
        params=transformed.init(key,x)
        class TechnicalCalculation:
            def __init__(self,**kwargs):
                self.cache_size=kwargs['max_cache_size']
                self.operation=jax.jit(jax.value_and_grad(lambda x:transformed.apply(params,x)))
            def _compiled_sequence_gradients(self):return self.operation
            def sequence_gradients(self,value,compile_only=False):
                compiled=self._compiled_sequence_gradients();compiled.lower(value).compile()
                loss,gradient=compiled(value)
                return {},{'x':gradient},loss
        reference=jax.jit(jax.value_and_grad(lambda x:transformed.apply(params,x)))
        with tempfile.TemporaryDirectory() as directory:
            path=pathlib.Path(directory)
            session=FabSession(path,identity={'scope':'technical test'},stage_path=path/'stage.json')
            cls=session.model_type(TechnicalCalculation);model=cls(max_cache_size=16)
            self.assertEqual(model.cache_size,1)
            try:
                previous=0
                for value in (x,x+.07):
                    expected=reference(value);actual=model.sequence_gradients(value)
                    np.testing.assert_allclose(actual[2],expected[0],rtol=2e-6,atol=2e-6)
                    np.testing.assert_allclose(actual[1]['x'],expected[1],rtol=2e-6,atol=2e-6)
                    self.assertEqual(session.tape.live_bytes,0)
                    self.assertGreater(session.tape.bytes_read,previous);previous=session.tape.bytes_read
                    self.assertFalse(list(session.tape.path.glob('*.npy')))
                self.assertEqual(session.completed_gradients,2)
                self.assertEqual(session.tape.checkpoints,8)
                self.assertEqual(json.loads((path/'stage.json').read_text())['stage'],'gradient_completed')
            finally:jax.effects_barrier();session.tape.close()


if __name__=='__main__':unittest.main()
