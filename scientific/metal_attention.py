"""Experimental PyTorch CPU/Metal attention matching BindCraft2 af/accel.py.

Independent tensor implementation of its stock/chunked equations. This is one
kernel, NOT an AlphaFold model or a functional binder-design backend. Float32
only for the initial validation; scaling is upstream's scale=1, not 1/sqrt(d).
"""
def attend(q, k, v, bias, nonbatched_bias=None, chunk_size=0):
    import torch
    values = [q, k, v, bias] + ([] if nonbatched_bias is None else [nonbatched_bias])
    if any(t.dtype != torch.float32 or t.device != q.device for t in values):
        raise ValueError('Initial Metal attention requires float32 tensors on one device.')
    if q.ndim != 4 or k.ndim != 4 or v.shape[:3] != k.shape[:3] or q.shape[0] != k.shape[0] or q.shape[2:] != k.shape[2:]:
        raise ValueError('Expected compatible batch, query/key, head, channel tensors.')
    if type(chunk_size) is not int or chunk_size < 0:
        raise ValueError('chunk_size must be a nonnegative integer.')
    def part(start, end):
        logits = torch.einsum('bqhc,bkhc->bhqk', q[:, start:end], k)
        def sliced(t):
            return t if t.shape[-2] == 1 else t[..., start:end, :]
        logits = logits + sliced(bias)
        if nonbatched_bias is not None:
            logits = logits + sliced(nonbatched_bias).unsqueeze(0)
        weights = torch.softmax(torch.clamp(logits, -1e8, 1e8), dim=-1)
        return torch.einsum('bhqk,bkhc->bqhc', weights, v)
    step = chunk_size or q.shape[1]
    return torch.cat([part(i, min(i + step, q.shape[1])) for i in range(0, q.shape[1], step)], dim=1)
