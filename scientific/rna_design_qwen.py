"""Frozen Qwen target features and a separately trained inverse sequence head."""
import hashlib
import json
from pathlib import Path


def head(width):
    from torch import nn
    return nn.Sequential(nn.LayerNorm(width), nn.Linear(width, 64), nn.GELU(), nn.Linear(64, 4))


def load_backbone(base):
    import torch
    from transformers import AutoTokenizer, Qwen2Model
    torch.set_num_threads(8)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    tokenizer = AutoTokenizer.from_pretrained(base, local_files_only=True, trust_remote_code=False)
    tokens = {c: tokenizer.encode(c, add_special_tokens=False) for c in '.()'}
    if any(len(v) != 1 for v in tokens.values()):
        raise ValueError('Dot-bracket symbols must each map to one Qwen token.')
    model = Qwen2Model.from_pretrained(base, local_files_only=True, trust_remote_code=False,
                                     use_safetensors=True, dtype=torch.float16, attn_implementation='sdpa').to(device).eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    return model, {k:v[0] for k,v in tokens.items()}, device


def features(backbone, tokens, target, device):
    import torch
    from rna_design_core import pairs
    n = len(target)
    with torch.no_grad():
        ids = torch.tensor([[tokens[c] for c in target]], device=device)
        hidden = backbone(input_ids=ids, use_cache=False).last_hidden_state[0].float()
        partner = list(range(n))
        for i,j in pairs(target):
            partner[i],partner[j] = j,i
        structural = [[float(c==symbol) for symbol in '.()'] + [i/max(1,n-1),partner[i]/max(1,n-1),n/128.,(partner[i]-i)/128.,float(partner[i]!=i)] for i,c in enumerate(target)]
        return torch.cat([hidden,hidden[partner],torch.tensor(structural,device=device)],-1)


class Proposer:
    def __init__(self, checkpoint, target=None):
        import torch
        from safetensors.torch import load_file
        self.config = json.loads(Path(checkpoint).read_text())
        self.provenance = {'version': self.config['version'], 'checkpointSha256': hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest(),
                           'weightsSha256': self.config['weights']['sha256'], 'protocolSha256': self.config['protocolSha256'],
                           'baseCheckpoint': self.config['baseCheckpoint'], 'trained': self.config['trained']}
        weights = Path(checkpoint).parent / self.config['weights']['file']
        if hashlib.sha256(weights.read_bytes()).hexdigest() != self.config['weights']['sha256']:
            raise ValueError('Inverse Qwen checkpoint integrity check failed.')
        self.backbone,self.tokens,self.device = load_backbone(self.config['baseCheckpoint'])
        self.provenance.update(device=self.device, torch=torch.__version__, transformers=__import__('transformers').__version__, samplingTemperature=1.0)
        self.head = head(self.config['featureWidth']).to(self.device).eval()
        self.head.load_state_dict(load_file(str(weights)))
        self.target = None
        if target:
            self.set_target(target)

    def set_target(self, target):
        import torch
        if target != self.target:
            with torch.no_grad():
                self.probabilities = self.head(features(self.backbone,self.tokens,target,self.device)).softmax(-1).cpu().tolist()
            self.target = target

    def __call__(self, index, rng):
        if self.target is None:
            raise ValueError('Set the target before sampling Qwen proposals.')
        return ''.join(rng.choices('ACGU',weights=row,k=1)[0] for row in self.probabilities)
