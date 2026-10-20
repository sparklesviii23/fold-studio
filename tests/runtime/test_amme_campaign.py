"""Real JIT/SSD lifecycle on tiny original Haiku scans; not model/Fab outputs."""
import json
import pathlib
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'vendor/bindcraft2')]
import haiku as hk
import jax
import jax.numpy as jnp
import numpy as np
from bindcraft.af.alphafold.model import layer_stack
from amme_campaign import FabSession


class SessionLifecycle(unittest.TestCase):
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
