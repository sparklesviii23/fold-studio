"""Experimental CPU reverse-mode checkpoints on disk, never enabled implicitly.

This is an execution adapter, not a model implementation. It recomputes the
original function during the reverse pass using lossless saved inputs. Actual
I/O uses io_callback (not pure_callback); JAX's host offload only targets RAM.
Only first-order reverse-mode is supported. Call effects_barrier before close.
"""
import contextlib
import hashlib
import itertools
import json
import os
import pathlib
import shutil
import tempfile
import threading
import types

import numpy as np

_TRACE_LOCK = threading.Lock()


class DiskTape:
    def __init__(self, directory, *, max_bytes, reserve_bytes=2 * 1024**3, identity=None):
        parent = pathlib.Path(directory).expanduser().resolve(strict=True)
        if not parent.is_dir() or max_bytes <= 0 or reserve_bytes < 0:
            raise ValueError('Choose an existing SSD directory and positive tape budget.')
        self._temporary = tempfile.TemporaryDirectory(prefix='fold-tape-', dir=parent)
        self.path = pathlib.Path(self._temporary.name)
        self.path.chmod(0o700)
        self.max_bytes = int(max_bytes)
        self.reserve_bytes = int(reserve_bytes)
        self._counter = itertools.count(1)
        self._records = {}
        self._lock = threading.RLock()
        self.bytes_written = 0
        self.bytes_read = 0
        self.live_bytes = 0
        self.peak_live_bytes = 0
        self.checkpoints = 0
        self.closed = False
        # Diagnostic manifests do not resume partial autodiff graphs. Only the
        # live worker owns the handles and a completed-gradient boundary can
        # release them. Identity is immutable, JSON-serializable provenance.
        self.identity = json.loads(json.dumps(identity or {}, allow_nan=False))
        self._metadata = {}

    def _manifest(self):
        pending = self.path / 'manifest.pending'
        try:
            with pending.open('w') as stream:
                json.dump({'schemaVersion': 1, 'identity': self.identity,
                           'scope': 'Ephemeral exact layer inputs for first-order reverse replay; not a resumable optimizer checkpoint.',
                           'liveBytes': self.live_bytes, 'maximumBytes': self.max_bytes,
                           'reloadPolicy': 'One layer checkpoint at a time; exact inputs, recompute internal activations.',
                           'records': self._metadata}, stream, allow_nan=False)
                stream.flush(); os.fsync(stream.fileno())
            os.replace(pending, self.path / 'manifest.json')
        finally:
            pending.unlink(missing_ok=True)

    def save(self, *arrays):
        with self._lock:
            if self.closed:
                raise RuntimeError('SSD tape is closed.')
            size = sum(np.asarray(array).nbytes + 512 for array in arrays)
            if self.live_bytes + size > self.max_bytes:
                raise RuntimeError('SSD checkpoint budget exceeded; calculation stopped.')
            if shutil.disk_usage(self.path).free - size < self.reserve_bytes:
                raise RuntimeError('SSD free-space reserve reached; calculation stopped.')
            token = next(self._counter)
            file = self.path / (str(token) + '.npy')
            pending = file.with_suffix('.pending')
            try:
                arrays = tuple(np.asarray(array) for array in arrays)
                with pending.open('xb') as stream:
                    for array in arrays:
                        array = np.asarray(array)
                        if array.dtype.hasobject or array.dtype.kind == 'V':
                            raise ValueError('SSD tape requires non-object NumPy numeric dtypes.')
                        np.save(stream, array, allow_pickle=False)
                    stream.flush(); os.fsync(stream.fileno())
                actual = pending.stat().st_size
                with pending.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                os.replace(pending, file)
                self._records[token] = (len(arrays), actual, digest)
                self.live_bytes += actual
                self._metadata[str(token)] = {'file': file.name, 'bytes': actual, 'sha256': digest,
                    'tensors': [{'shape': list(array.shape), 'dtype': str(array.dtype), 'bytes': array.nbytes}
                                for array in arrays], 'residence': 'disk', 'mustPreserveExactly': True,
                    'dependency': 'Original layer input carry and per-layer operands, replayed by this VJP handle.',
                    'expectedNextUse': 'Original reverse scan order; not a wall-clock estimate.'}
                self._manifest()
                self.bytes_written += actual
                self.peak_live_bytes = max(self.peak_live_bytes, self.live_bytes)
                self.checkpoints += 1
                return np.asarray(token, dtype=np.uint32)
            except BaseException:
                if token in self._records:
                    self.live_bytes -= self._records.pop(token)[1]
                    self._metadata.pop(str(token), None)
                file.unlink(missing_ok=True)
                pending.unlink(missing_ok=True)
                raise

    def load(self, token):
        with self._lock:
            token = int(token)
            if self.closed or token not in self._records:
                raise RuntimeError('Unknown or expired SSD checkpoint.')
            count, size, digest = self._records[token]
            file = self.path / (str(token) + '.npy')
            with file.open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                    raise RuntimeError('SSD checkpoint checksum mismatch.')
                stream.seek(0)
                values = tuple(np.load(stream, allow_pickle=False) for _ in range(count))
            expected = self._metadata[str(token)]['tensors']
            if any(list(value.shape) != spec['shape'] or str(value.dtype) != spec['dtype']
                   for value, spec in zip(values, expected)):
                raise RuntimeError('SSD checkpoint shape or dtype mismatch.')
            self.bytes_read += size
            return values

    def close(self):
        with self._lock:
            self.closed = True
            self._temporary.cleanup()

    def release(self):
        """After effects_barrier, discard only this completed gradient's tape.

        Compiled callbacks can reuse this store for the next gradient. Handles
        remain monotonic: stale residuals fail instead of reading another step.
        """
        with self._lock:
            if self.closed:
                raise RuntimeError('SSD tape is closed.')
            for token in self._records:
                (self.path / (str(token) + '.npy')).unlink()
            self._records.clear()
            self._metadata.clear()
            self.live_bytes = 0
            self._manifest()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def disk_checkpoint(function, tape, *example_args):
    """Recompute function from SSD inputs in its first-order VJP.

    Captured differentiable values are explicit operands, preserving their
    derivatives. Shared closed-over constants remain loop invariant. Integer
    RNG state is serialized with the same dtype and value as floating inputs.
    """
    import jax
    from jax.experimental import io_callback
    from jax.extend import core

    # closure_convert only hoists potentially differentiable captures. AlphaFold
    # also closes over dynamically traced integer/bool masks, which must become
    # operands too; retaining those as literal constants breaks nested JIT.
    closed, output_shapes = jax.make_jaxpr(function, return_shape=True)(*example_args)
    constants = closed.consts
    output_structure = jax.tree.structure(output_shapes)
    def converted(*args):
        ordinary, captured = args[:len(example_args)], args[len(example_args):]
        values = core.jaxpr_as_fun(core.ClosedJaxpr(closed.jaxpr, captured))(*jax.tree.leaves(ordinary))
        return jax.tree.unflatten(output_structure, values)
    leaves, structure = jax.tree.flatten(example_args)
    specs = tuple(jax.ShapeDtypeStruct(value.shape, value.dtype) for value in leaves)
    token_spec = jax.ShapeDtypeStruct((), np.uint32)

    @jax.custom_vjp
    def wrapped(*args):
        return converted(*args)

    def forward(*args):
        ordinary = args[:len(example_args)]
        token = io_callback(tape.save, token_spec, *jax.tree.leaves(ordinary), ordered=True)
        result = converted(*args)
        return result, (token, args[len(example_args):])

    def backward(residual, cotangent):
        token, captured = residual
        flat = io_callback(tape.load, specs, token, ordered=True)
        ordinary = jax.tree.unflatten(structure, flat)
        _, pullback = jax.vjp(converted, *ordinary, *captured)
        return pullback(cotangent)

    wrapped.defvjp(forward, backward)

    def call(*args):
        return wrapped(*args, *constants)
    return call


@contextlib.contextmanager
def alphafold_disk_tape(tape):
    """Scope the adapter to original Haiku AlphaFold layer-stack scans only.

    Scientific workers are isolated, single-campaign processes. This scoped
    hook must surround compilation AND execution and must not be used alongside
    another tracing thread. Other scans, inference and vendor files are intact.
    """
    import jax
    from bindcraft import af2
    if any(device.platform != 'cpu' for device in jax.devices()):
        raise ValueError('Experimental SSD checkpoints currently require the CPU runtime.')
    original = jax.lax.scan
    original_recycle = af2.recycled_alphafold_outputs

    def recycled(runner, parameters, key, inputs, num_recycle):
        # Upstream stops gradients AFTER each preliminary recycle. Stopping its
        # inputs too is algebraically identical and prevents side-effecting SSD
        # writes for a pass whose derivative is explicitly discarded. The
        # original function still owns keys, outputs and recycling semantics.
        calls = 0
        def apply(*args):
            nonlocal calls
            preliminary = calls < num_recycle
            calls += 1
            if preliminary:
                args = jax.tree.map(jax.lax.stop_gradient, args)
            return runner.apply(*args)
        result = original_recycle(types.SimpleNamespace(apply=apply), parameters, key, inputs, num_recycle)
        if calls != num_recycle + 1:
            raise RuntimeError('Original AlphaFold recycle protocol changed; refusing SSD adapter.')
        return result

    def scan(function, initial, xs=None, length=None, reverse=False, unroll=1, **kwargs):
        if (getattr(function, '__module__', '') ==
                'bindcraft.af.alphafold.model.layer_stack' and
                getattr(function, '__name__', '') == 'layer'):
            example = jax.tree.map(lambda array: array[0], xs)
            function = disk_checkpoint(function, tape, initial, example)
        return original(function, initial, xs, length, reverse, unroll=unroll, **kwargs)

    if not _TRACE_LOCK.acquire(blocking=False):
        raise RuntimeError('Only one isolated SSD tracing context may run at a time.')
    jax.lax.scan = scan
    af2.recycled_alphafold_outputs = recycled
    try:
        yield tape
    finally:
        try:
            jax.effects_barrier()
        finally:
            jax.lax.scan = original
            af2.recycled_alphafold_outputs = original_recycle
            _TRACE_LOCK.release()
