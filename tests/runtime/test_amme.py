"""Real original attention/subbatch equivalence; synthetic tensors are not Fab designs."""
import pathlib
import sys
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scientific'));sys.path.insert(0,str(ROOT/'vendor/bindcraft2'))
import jax
import jax.numpy as jnp
import numpy as np
import haiku as hk
from ml_collections import ConfigDict
from amme import graph_memory,rematerialized_subbatches
from bindcraft.af.alphafold.model import mapping,modules


class AMME(unittest.TestCase):
    def test_original_attention_masks_ragged_chunks_rng_gradients_and_updates(self):
        def function(q,m,bias):
            attention=modules.Attention(ConfigDict({'num_head':2,'gating':True}),ConfigDict({'zero_init':False,'attention_backend':'stock'}),8)
            def chunk(q,m,bias):
                value=attention(q,m,bias)
                return value*jax.random.bernoulli(hk.next_rng_key(),.8,value.shape)/.8
            return jnp.sin(mapping.inference_subbatch(chunk,3,[q,m,bias],[])).sum()
        transformed=hk.transform(function);key=jax.random.PRNGKey(42)
        q=jax.random.normal(key,(7,11,8))*.1;m=jax.random.normal(jax.random.PRNGKey(43),(7,13,8))*.1
        bias=jnp.where(jnp.arange(13)<9,0.,-1e9)[None,None,None,:]+jnp.zeros((7,1,11,13))
        params=transformed.init(key,q,m,bias)
        baseline=jax.jit(jax.value_and_grad(transformed.apply,argnums=(0,2,3)))
        expected=baseline(params,key,q,m,bias);jax.block_until_ready(expected)
        original=mapping.inference_subbatch
        with rematerialized_subbatches() as stats:
            optimized=jax.jit(jax.value_and_grad(transformed.apply,argnums=(0,2,3)))
            actual=optimized(params,key,q,m,bias);jax.block_until_ready(actual)
            self.assertGreater(stats['tracedSubbatchCalls'],0)
            for reference,value in zip(jax.tree.leaves(expected),jax.tree.leaves(actual)):
                self.assertTrue(np.isfinite(value).all());np.testing.assert_allclose(value,reference,rtol=2e-6,atol=2e-6)
            for index in (1,2):np.testing.assert_allclose((q if index==1 else m)-.01*actual[1][index],(q if index==1 else m)-.01*expected[1][index],rtol=2e-6,atol=2e-6)
        self.assertIs(mapping.inference_subbatch,original)

    def test_hook_restores_after_failure_and_refuses_concurrent_use(self):
        original=mapping.inference_subbatch;original_scan=hk.scan
        with self.assertRaisesRegex(ValueError,'test failure'):
            with rematerialized_subbatches(structure=True):
                with self.assertRaisesRegex(RuntimeError,'one isolated'):
                    with rematerialized_subbatches():self.fail('Nested hooks must fail.')
                raise ValueError('test failure')
        self.assertIs(mapping.inference_subbatch,original)
        self.assertIs(hk.scan,original_scan)

    def test_graph_contributors_are_labeled_logical_not_resident_memory(self):
        graph=jax.make_jaxpr(lambda x:jnp.sin(x)+x)(jax.ShapeDtypeStruct((512,1024),jnp.float32))
        report=graph_memory(graph);self.assertTrue(report['fiveLargestIdentifiableLogicalContributors'])
        self.assertEqual(report['fiveLargestIdentifiableLogicalContributors'][0]['bytes'],2*1024**2)
        self.assertIn('not measure',report['limitations']);self.assertIn('logicalLifetime',report['fiveLargestIdentifiableLogicalContributors'][0])


if __name__=='__main__':unittest.main()
