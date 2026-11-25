#!/usr/bin/env python3
"""Read-only recovery of the existing direct-Qwen cell-response pilot."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
for name in ('source','data','weights','base','saved','out'):
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();sys.path.insert(0,str(a.source/'scientific'))
import numpy as np
import torch
from transformers import Qwen2Model
from safetensors.torch import load_file
from qwen_cell_model import QwenCellPredictor,load_trainable_state
torch.set_num_threads(2)
device='mps' if torch.backends.mps.is_available() else 'cpu'
data=np.load(a.data/'data.npz',allow_pickle=False)
base=Qwen2Model.from_pretrained(a.base,local_files_only=True,trust_remote_code=False,use_safetensors=True,
                               dtype=torch.float16 if device=='mps' else torch.float32,attn_implementation='eager').to(device)
model=QwenCellPredictor(base,data['trainX'].shape[1],data['decoder'],data['targetCenter'],data['targetScale']).to(device).eval()
load_trainable_state(model,load_file(str(a.weights)))
with torch.no_grad():
    prediction=np.concatenate([model(torch.as_tensor(x[None],device=device,dtype=torch.float32)).cpu().numpy() for x in data['validationX']])
saved=np.load(a.saved,allow_pickle=False)['prediction']
error=float(np.abs(prediction-saved).max())
np.testing.assert_allclose(prediction,saved,rtol=1e-4,atol=1e-5)
mask=data['validationMask'];mse=float((((prediction-data['validationY'])**2*mask).sum(-1)/mask.sum(-1)).mean())
a.out.mkdir(parents=True,exist_ok=False)
np.savez_compressed(a.out/'reproduced-predictions.npz',prediction=prediction,genes=data['genes'],conditions=data['validationConditions'])
report={'schema':'fold.recovered-qwen-cell/1','device':device,'shape':list(prediction.shape),'maxAbsDifference':error,'developmentMse':mse,
        'sourceWorktree':str(a.source),'data':str(a.data),'weights':str(a.weights),'base':str(a.base),
        'weightsSha256':hashlib.sha256(a.weights.read_bytes()).hexdigest(),'trainedAdditionalWeights':False,
        'scope':'Existing K562 calibrated paired CRISPRa response; mean log1p expression changes across 2,132 genes. Not RNA folding or individual-cell simulation.',
        'savedReference':str(a.saved),'passed':True}
(a.out/'reproduction.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
