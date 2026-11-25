"""Position-preserving numerical RNA heads on the local, offline Qwen2 backbone.

This is a separate task adapter. Cell-response checkpoints are never modified.
Pair scores are constrained marginals, not thermodynamic ensemble probabilities.
"""
import math
import torch
from torch import nn
from torch.nn import functional as F

BASES = 'ACGU'
PAIRS = {'AU', 'UA', 'GC', 'CG', 'GU', 'UG'}


class LoRALinear(nn.Module):
    """Same rank-8 attention adaptation as predictive-cell-research/qwen_cell_model."""
    def __init__(self, base, rank=8):
        super().__init__()
        self.base = base
        for p in base.parameters():
            p.requires_grad_(False)
        self.lora_a = nn.Parameter(torch.empty(rank, base.in_features, device=base.weight.device))
        self.lora_b = nn.Parameter(torch.zeros(base.out_features, rank, device=base.weight.device))
        nn.init.kaiming_uniform_(self.lora_a, a=math.sqrt(5))

    def forward(self, x):
        return self.base(x) + F.linear(F.linear(x.float(), self.lora_a), self.lora_b).to(x.dtype)


class PairHead(nn.Module):
    def __init__(self, width):
        super().__init__()
        self.project = nn.Sequential(nn.LayerNorm(width), nn.Linear(width, 48), nn.GELU())
        self.distance = nn.Embedding(129, 8)
        self.pair = nn.Sequential(nn.Linear(48 * 3 + 8, 48), nn.GELU(), nn.Linear(48, 1))
        self.unpaired = nn.Linear(48, 1)

    def forward(self, hidden, sequence):
        h = self.project(hidden.float())[0]
        n = len(sequence)
        a, b = h[:, None, :].expand(n, n, -1), h[None, :, :].expand(n, n, -1)
        idx = torch.arange(n, device=h.device)
        distance = (idx[:, None] - idx[None, :]).abs()
        features = torch.cat([a + b, (a - b).abs(), a * b, self.distance(distance)], -1)
        scores = self.pair(features).squeeze(-1)
        allowed = torch.tensor([[abs(i-j) > 3 and sequence[i] + sequence[j] in PAIRS
                                 for j in range(n)] for i in range(n)], device=h.device)
        scores = scores.masked_fill(~allowed, -10000.)
        return scores + torch.diag(self.unpaired(h).squeeze(-1) + 10000.)


class RNAModel(nn.Module):
    def __init__(self, backbone=None, token_ids=None, adapters=False):
        super().__init__()
        self.backbone = backbone
        self.token_ids = token_ids
        if backbone is None:
            self.embedding = nn.Embedding(4, 48)
            self.encoder = nn.Sequential(nn.Conv1d(48, 64, 7, padding=3), nn.GELU(),
                                         nn.Conv1d(64, 64, 7, padding=3), nn.GELU())
            self.head = PairHead(64)
        else:
            for p in backbone.parameters():
                p.requires_grad_(False)
            if adapters:
                for layer in backbone.layers[-2:]:
                    for name in ('q_proj', 'v_proj'):
                        setattr(layer.self_attn, name, LoRALinear(getattr(layer.self_attn, name)))
            self.head = PairHead(backbone.config.hidden_size)

    def hidden(self, sequence):
        device = next(self.parameters()).device
        if self.backbone is None:
            ids = torch.tensor([[BASES.index(c) for c in sequence]], device=device)
            return self.encoder(self.embedding(ids).transpose(1, 2)).transpose(1, 2)
        ids = torch.tensor([[self.token_ids[c] for c in sequence]], device=device)
        # Each nucleotide is exactly one token. No BPE merging, truncation, or BOS.
        return self.backbone(input_ids=ids, use_cache=False).last_hidden_state

    def forward(self, sequence, cached=None):
        return self.head(self.hidden(sequence) if cached is None else cached, sequence)

    def added_state(self):
        return {n: v.detach().cpu().contiguous() for n, v in self.state_dict().items()
                if not n.startswith('backbone.') or '.lora_' in n}

    def restore(self, state):
        current = self.state_dict()
        if set(state) != set(self.added_state()):
            raise ValueError('RNA checkpoint architecture mismatch.')
        with torch.no_grad():
            for n, v in state.items():
                if v.shape != current[n].shape or not bool(torch.isfinite(v).all()):
                    raise ValueError('Invalid RNA checkpoint tensor: ' + n)
                current[n].copy_(v.to(current[n].device))


def marginals(logits):
    p = logits.softmax(-1)
    p = (p + p.T) / 2
    p = p - torch.diag(torch.diag(p))
    # Conservative projection: symmetric, nonnegative, at most one partner/base.
    p = p / p.sum(-1).max().clamp(min=1.)
    return p


def detach_adapters(backbone):
    for layer in backbone.layers:
        for name in ('q_proj', 'v_proj'):
            value = getattr(layer.self_attn, name)
            if isinstance(value, LoRALinear):
                setattr(layer.self_attn, name, value.base)
