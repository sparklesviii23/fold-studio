"""Isolated Fab execution policy; never changes the scientific campaign recipe.

Install before fresh model tracing. Float32 precision is supplied by the existing
validated adapter, not by this memory policy. Original models, sampling, losses,
optimizers, filters, and rejection decisions remain owned by BindCraft2.
"""
import contextlib
import json
import os
import pathlib
import time

POLICY = 'fab-cpu-ssd-v1'
NATIVE_ENABLED = True  # Experimental: full gradient + matched-input repeated-step validation; complete trajectory validation remains pending.
SCHEDULER_FLAG = '--xla_cpu_scheduler_type=CPU_SCHEDULER_TYPE_MEMORY_OPTIMIZED'
FOOTPRINT_LIMIT = 14 * 1024**3
SSD_QUOTA = 10 * 1024**3
DISK_RESERVE = 2 * 1024**3


def atomic_json(path, value):
    path = pathlib.Path(path)
    pending = path.with_suffix(path.suffix + '.pending')
    try:
        with pending.open('w') as stream:
            json.dump(value, stream, allow_nan=False, indent=2)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def environment(existing):
    """Set the tested CPU compiler schedule before importing JAX in the worker."""
    flags = existing.get('XLA_FLAGS', '').split()
    schedulers = [flag for flag in flags if flag.startswith('--xla_cpu_scheduler_type=')]
    if schedulers and schedulers != [SCHEDULER_FLAG]:
        raise ValueError('AMME requires the tested CPU memory scheduler; conflicting compiler override refused.')
    if not schedulers:
        flags.append(SCHEDULER_FLAG)
    return {**existing, 'JAX_PLATFORMS': 'cpu', 'XLA_FLAGS': ' '.join(flags),
            'XLA_PYTHON_CLIENT_PREALLOCATE': 'false', 'PYTHONDONTWRITEBYTECODE': '1'}


class FabSession:
    """One live tape reused across gradients; no replay of interrupted AD graphs."""
    def __init__(self, directory, *, identity, stage_path, prevent_cse=False, attention_only=False):
        from ssd_checkpoint import DiskTape
        self.tape = DiskTape(directory, max_bytes=SSD_QUOTA,
                             reserve_bytes=DISK_RESERVE, identity=identity)
        self.stage_path = pathlib.Path(stage_path)
        self.gradient_calls = 0
        self.completed_gradients = 0
        self.last_model = None
        self.prevent_cse = prevent_cse
        self.attention_only = attention_only

    def stage(self, stage, **details):
        value = {'policy': POLICY, 'stage': stage, 'monotonicSeconds': time.monotonic(),
                 'gradientCalls': self.gradient_calls, 'completedGradients': self.completed_gradients,
                 'lastModel': self.last_model, 'ssdLiveBytes': self.tape.live_bytes,
                 'ssdPeakBytes': self.tape.peak_live_bytes, 'ssdBytesWritten': self.tape.bytes_written,
                 'ssdBytesRead': self.tape.bytes_read, **details}
        atomic_json(self.stage_path, value)
        print('FOLD_AMME ' + json.dumps(value, allow_nan=False), flush=True)

    def model_type(self, base):
        session = self

        def synchronize_predictions(predictions):
            import jax
            # Upstream prediction dataclasses are not registered JAX pytrees.
            # Synchronize their arrays explicitly before recording a boundary.
            values=[]
            for prediction in predictions.values():
                values.extend(prediction.metrics.values())
                for protein in prediction.protein_complex.values():
                    values.extend((protein.atoms,protein.atom_mask,protein.sequence))
            jax.block_until_ready(values)

        class MemoryBoundModel(base):
            def __init__(self, *args, **kwargs):
                # Shape/family compile caches do not change scientific settings.
                kwargs['max_cache_size'] = 1
                super().__init__(*args, **kwargs)
                if hasattr(self,'model_parameters'):
                    import jax
                    session.stage('model_parameters_loaded',modelPool=list(self.models),
                        parameterLogicalBytes=sum(int(value.nbytes) for value in jax.tree.leaves(self.model_parameters)))

            def _resolve_model_name(self, value):
                chosen = super()._resolve_model_name(value)
                session.last_model = chosen
                return chosen

            def _compiled_sequence_gradients(self, *args, **kwargs):
                original = super()._compiled_sequence_gradients(*args, **kwargs)

                class Measured:
                    def lower(self, *operands):
                        session.stage('gradient_compilation')
                        lowered = original.lower(*operands)

                        class Plan:
                            def compile(self):
                                before = time.monotonic()
                                executable = lowered.compile()
                                analysis = executable.memory_analysis()
                                memory = {name: int(getattr(analysis, name)) for name in
                                          ('argument_size_in_bytes', 'output_size_in_bytes',
                                           'temp_size_in_bytes', 'alias_size_in_bytes')}
                                # Reject known unsafe whole-heap allocations before
                                # execution. Runtime task footprint remains guarded.
                                if memory['temp_size_in_bytes'] > 10 * 1024**3:
                                    raise RuntimeError('Fab compiler working buffer exceeds the validated AMME allocation envelope.')
                                session.stage('gradient_execution', compileSeconds=time.monotonic() - before,
                                              compiledMemoryAnalysis=memory)
                                return executable
                        return Plan()

                    def __call__(self, *operands):
                        return original(*operands)
                return Measured()

            def sequence_gradients(self, *args, **kwargs):
                import jax
                from amme import rematerialized_subbatches
                from ssd_checkpoint import alphafold_disk_tape
                session.gradient_calls += 1
                try:
                    with rematerialized_subbatches(prevent_cse=session.prevent_cse,attention_only=session.attention_only) as stats, alphafold_disk_tape(session.tape):
                        result = super().sequence_gradients(*args, **kwargs)
                        jax.block_until_ready((result[1],result[2]))
                        synchronize_predictions(result[0])
                    # Effects must complete before expiring handles; compiled
                    # callbacks retain this tape for the next original step.
                    jax.effects_barrier()
                    if not kwargs.get('compile_only', False):
                        session.completed_gradients += 1
                    session.tape.release()
                    session.stage('gradient_compiled_only' if kwargs.get('compile_only',False) else 'gradient_completed', rematerialization=stats)
                    return result
                except BaseException:
                    session.stage('gradient_failed')
                    raise

            def predict(self, *args, **kwargs):
                import jax
                session.stage('structure_prediction')
                result = super().predict(*args, **kwargs)
                synchronize_predictions(result)
                session.stage('structure_prediction_completed')
                return result

        return MemoryBoundModel

    @contextlib.contextmanager
    def install(self, base):
        from bindcraft import campaign
        original = campaign.AlphaFoldDesignModel
        campaign.AlphaFoldDesignModel = self.model_type(base)
        try:
            self.stage('campaign_initialization')
            yield self
        finally:
            import jax
            try:
                jax.effects_barrier()
            finally:
                campaign.AlphaFoldDesignModel = original
                self.tape.close()

