"""Experimental SSD tape: lossless replay, actual JIT reverse scan and cleanup."""
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scientific'))
import jax
import jax.numpy as jnp
import numpy as np
from ssd_checkpoint import DiskTape, disk_checkpoint, alphafold_disk_tape


class SSDCheckpoint(unittest.TestCase):
    def test_lossless_checksum_budget_and_owned_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            neighbor = pathlib.Path(directory) / 'keep'; neighbor.write_text('keep')
            with DiskTape(directory, max_bytes=4096, reserve_bytes=0) as tape:
                location = tape.path
                arrays = (np.arange(5, dtype=np.float32), np.array([1, 7], np.uint32))
                token = tape.save(*arrays)
                for expected, actual in zip(arrays, tape.load(token)):
                    np.testing.assert_array_equal(actual, expected)
                    self.assertEqual(actual.dtype, expected.dtype)
                with self.assertRaisesRegex(RuntimeError, 'budget'):
                    tape.save(np.zeros(4096, np.float32))
                file = location / (str(int(token)) + '.npy')
                file.write_bytes(file.read_bytes()[:-1] + b'x')
                with self.assertRaisesRegex(RuntimeError, 'checksum'):
                    tape.load(token)
            self.assertFalse(location.exists()); self.assertEqual(neighbor.read_text(), 'keep')

    def test_free_space_guard_precedes_write(self):
        with tempfile.TemporaryDirectory() as directory, DiskTape(directory, max_bytes=4096) as tape:
            with patch('ssd_checkpoint.shutil.disk_usage') as usage:
                usage.return_value.free = 1
                with self.assertRaisesRegex(RuntimeError, 'reserve'):
                    tape.save(np.ones(4, np.float32))
            self.assertEqual(list(tape.path.iterdir()), [])

    def test_completed_gradient_release_reuses_budget_but_not_handles(self):
        with tempfile.TemporaryDirectory() as directory, DiskTape(directory, max_bytes=2048, reserve_bytes=0) as tape:
            old = tape.save(np.ones(100, np.float32)); written = tape.bytes_written
            tape.release()
            self.assertEqual(tape.live_bytes, 0)
            with self.assertRaisesRegex(RuntimeError, 'expired'):
                tape.load(old)
            new = tape.save(np.zeros(100, np.float32))
            self.assertNotEqual(int(new), int(old)); self.assertGreater(tape.bytes_written, written)
            self.assertLessEqual(tape.peak_live_bytes, 2048)

    def test_jit_reverse_scan_matches_original_including_captured_gradients(self):
        with tempfile.TemporaryDirectory() as directory, DiskTape(directory, max_bytes=1024**2, reserve_bytes=0) as tape:
            def loss(x, weight, offload):
                def body(carry, step):
                    value, key = carry
                    key, subkey = jax.random.split(key)
                    value = jnp.tanh(value * weight + jax.random.normal(subkey, value.shape) * .01 + step)
                    return (value, key), jnp.sum(value)
                initial = (x, jax.random.PRNGKey(42))
                steps = jnp.arange(7, dtype=jnp.float32) * .01
                function = disk_checkpoint(body, tape, initial, steps[0]) if offload else body
                (last, _), values = jax.lax.scan(function, initial, steps)
                return jnp.sum(last) + jnp.sum(values)
            x = jnp.arange(12, dtype=jnp.float32) * .03
            reference = jax.jit(jax.value_and_grad(lambda x, w: loss(x, w, False), argnums=(0, 1)))(x, jnp.float32(.7))
            compiled = jax.jit(jax.value_and_grad(lambda x, w: loss(x, w, True), argnums=(0, 1)))
            actual = compiled(x, jnp.float32(.7))
            jax.block_until_ready(actual); jax.effects_barrier()
            for expected, value in zip(jax.tree.leaves(reference), jax.tree.leaves(actual)):
                np.testing.assert_allclose(value, expected, rtol=2e-6, atol=2e-6)
            self.assertEqual(tape.checkpoints, 7); self.assertGreater(tape.bytes_read, 0)
            tape.release()
            next_x = x + .11
            expected = jax.jit(jax.value_and_grad(lambda x, w: loss(x, w, False), argnums=(0, 1)))(next_x, jnp.float32(.6))
            repeated = compiled(next_x, jnp.float32(.6))
            jax.block_until_ready(repeated); jax.effects_barrier()
            for value, reference in zip(jax.tree.leaves(repeated), jax.tree.leaves(expected)):
                np.testing.assert_allclose(value, reference, rtol=2e-6, atol=2e-6)
            self.assertEqual(tape.checkpoints, 14)

    def test_original_haiku_layer_stack_transformation(self):
        sys.path.insert(0, str(ROOT / 'vendor/bindcraft2'))
        import haiku as hk
        from bindcraft.af.alphafold.model import layer_stack
        def function(x, mask):
            def block(value):
                return jnp.where(mask, jnp.tanh(hk.Linear(8)(value)), value)
            return jnp.sum(layer_stack.layer_stack(4)(hk.remat(block))(x))
        model = hk.transform(function)
        x = jnp.ones((2, 8), dtype=jnp.float32)
        mask = jnp.arange(8) % 3 != 0
        key = jax.random.PRNGKey(1)
        params = model.init(key, x, mask)
        nested = jax.jit(model.apply)
        def loss(params, x, mask):
            return nested(params, key, x, mask)
        expected = jax.jit(jax.value_and_grad(loss, argnums=1))(params, x, mask)
        with tempfile.TemporaryDirectory() as directory, DiskTape(directory, max_bytes=1024**2, reserve_bytes=0) as tape:
            with alphafold_disk_tape(tape):
                # A fresh inner trace exercises dynamic closed-over parameters.
                nested.clear_cache()
                actual = jax.jit(jax.value_and_grad(loss, argnums=1))(params, x, mask)
                jax.block_until_ready(actual)
            for reference, value in zip(jax.tree.leaves(expected), jax.tree.leaves(actual)):
                np.testing.assert_allclose(value, reference, rtol=2e-6, atol=2e-6)
            self.assertEqual(tape.checkpoints, 4)

    def test_context_restores_hooks_after_error_and_refuses_nested_use(self):
        sys.path.insert(0, str(ROOT / 'vendor/bindcraft2'))
        from bindcraft import af2
        original_scan, original_recycle = jax.lax.scan, af2.recycled_alphafold_outputs
        with tempfile.TemporaryDirectory() as directory, DiskTape(directory, max_bytes=4096, reserve_bytes=0) as tape:
            with self.assertRaisesRegex(ValueError, 'example'):
                with alphafold_disk_tape(tape):
                    with self.assertRaisesRegex(RuntimeError, 'one isolated'):
                        with alphafold_disk_tape(tape):
                            self.fail('Nested adapter should be refused.')
                    value, _ = jax.lax.scan(lambda x, y: (x + y, None), jnp.float32(0), jnp.ones(2))
                    self.assertEqual(float(value), 2)
                    self.assertEqual(tape.checkpoints, 0)
                    raise ValueError('example')
        self.assertIs(jax.lax.scan, original_scan); self.assertIs(af2.recycled_alphafold_outputs, original_recycle)


if __name__ == '__main__':
    unittest.main()
