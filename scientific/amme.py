"""Opt-in AlphaFold memory diagnostics and original-operation rematerialization.

Graph tensor sizes are logical compiler values, not measured allocator peaks.
No model settings, checkpoints, precision or acceptance criteria are changed.
"""
import contextlib
import math
import threading

_LOCK = threading.Lock()


def graph_memory(closed):
    """Inspect nested JAX graphs without executing full-size model activations."""
    import numpy as np
    rows = []
    seen = set()

    def visit(graph, scope):
        graph = getattr(graph, 'jaxpr', graph)
        if id(graph) in seen:
            return
        seen.add(id(graph))
        last_use = {}
        for index, equation in enumerate(graph.eqns):
            for value in equation.invars:
                last_use[id(value)] = index
        for value in graph.outvars:
            last_use[id(value)] = len(graph.eqns)
        for index, equation in enumerate(graph.eqns):
            name = str(equation.source_info.name_stack)
            for value in equation.outvars:
                aval = getattr(value, 'aval', None)
                if not hasattr(aval, 'shape') or not hasattr(aval, 'dtype'):
                    continue
                try:
                    shape = [int(dimension) for dimension in aval.shape]
                    size = math.prod(shape) * np.dtype(aval.dtype).itemsize
                except (TypeError, ValueError):
                    continue
                if size >= 1024**2:
                    rows.append({'bytes': size, 'shape': shape, 'dtype': str(aval.dtype),
                                 'primitive': equation.primitive.name, 'sourceScope': name,
                                 'graphScope': scope, 'logicalLifetime': {'producedAtEquation': index,
                                 'lastConsumedAtEquation': last_use.get(id(value), index)},
                                 'attributionConfidence': 'exact logical shape; allocator overlap/reuse unmeasured'})
            for key, item in equation.params.items():
                nested = item if isinstance(item, (tuple, list)) else (item,)
                for child_index, child in enumerate(nested):
                    if hasattr(child, 'jaxpr') or hasattr(child, 'eqns'):
                        visit(child, scope + '/' + str(index) + ':' + equation.primitive.name + ':' + key + ':' + str(child_index))

    visit(closed, 'gradient')
    rows.sort(key=lambda row: row['bytes'], reverse=True)
    contributors = []
    signatures = set()
    for row in rows:
        if row['primitive'] in ('jit','pjit','remat2','custom_vjp_call','closed_call','call','reshape','transpose','broadcast_in_dim'):
            continue  # Call boundaries/views can alias the same underlying value.
        signature = (tuple(row['shape']), row['dtype'], row['primitive'], row['sourceScope'])
        if signature not in signatures:
            signatures.add(signature)
            contributors.append(row)
        if len(contributors) == 5:
            break
    return {'method': 'Abstract original JAX gradient graph, no model activations executed',
            'limitations': 'Logical program-order lifetimes are local to each nested graph. They do not measure compiler scheduling, aliases, resident peak or simultaneous allocation; values may be optimized away.',
            'nestedGraphs': len(seen), 'valuesAtLeastOneMiB': len(rows),
            'fiveLargestIdentifiableLogicalContributors': contributors, 'largestValues': rows[:30]}


@contextlib.contextmanager
def rematerialized_subbatches(*,structure=False,triangles=False,prevent_cse=False,attention_only=False):
    """Recompute original subbatch bodies and optionally structure iterations.

    Apply only in one isolated CPU scientific worker around fresh tracing and
    execution. Original sharding, masks, PRNG, weights and operation order stay
    owned by the pinned source. Not enabled for native jobs by default.
    """
    import jax
    import haiku as hk
    from bindcraft.af.alphafold.model import mapping,modules
    if any(device.platform != 'cpu' for device in jax.devices()):
        raise ValueError('AMME subbatch rematerialization currently requires CPU validation.')
    if not _LOCK.acquire(blocking=False):
        raise RuntimeError('Only one isolated AMME tracing context may run at a time.')
    original = mapping.inference_subbatch
    original_scan = hk.scan
    triangle_type=modules.TriangleMultiplication
    triangle_methods={name:getattr(triangle_type,name) for name in ('_triangle_multiplication','_fused_triangle_multiplication')}
    stats = {'policy': 'rematerialized_subbatches', 'tracedSubbatchCalls': 0,
             'structureRematerialization':structure,'tracedStructureScans':0,
             'triangleRematerialization':triangles,'tracedTriangleCalls':0,
             'preventCommonSubexpressionElimination':prevent_cse,'triangleAttentionOnly':attention_only}

    def apply(module, *args, **kwargs):
        if attention_only and 'triangle_attention' not in getattr(module,'module_name',''):
            return original(module,*args,**kwargs)
        stats['tracedSubbatchCalls'] += 1
        return original(hk.remat(module, prevent_cse=prevent_cse), *args, **kwargs)

    def scan(function,*args,**kwargs):
        if structure and getattr(function,'__module__','') in ('bindcraft.af.alphafold.model.folding','bindcraft.af.alphafold.model.folding_multimer') and getattr(function,'__name__','')=='fold_iter':
            stats['tracedStructureScans']+=1
            function=hk.remat(function,prevent_cse=prevent_cse)
        return original_scan(function,*args,**kwargs)

    def triangle_method(original_method):
        # The original private methods are Haiku-transparent; preserve the
        # caller's module/parameter scope while checkpointing their exact body.
        def apply(self,left_act,left_mask):
            stats['tracedTriangleCalls']+=1
            return hk.remat(lambda act,mask:original_method(self,act,mask),prevent_cse=prevent_cse)(left_act,left_mask)
        return apply

    mapping.inference_subbatch = apply
    if structure:hk.scan=scan
    if triangles:
        for name,method in triangle_methods.items():setattr(triangle_type,name,triangle_method(method))
    try:
        yield stats
    finally:
        try:
            jax.effects_barrier()
        finally:
            mapping.inference_subbatch = original
            hk.scan=original_scan
            for name,method in triangle_methods.items():setattr(triangle_type,name,method)
            _LOCK.release()
