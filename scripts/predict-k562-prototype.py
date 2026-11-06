"""Portable NumPy-only inference for the research K562 paired-activation prototype."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def predict(model, pairs):
    with np.load(model,allow_pickle=False) as archive:
        z={k:archive[k] for k in archive.files}
    ix={str(g):i for i,g in enumerate(z['singleGenes'])};labels=[];left=[];right=[]
    for pair in pairs:
        genes=sorted(pair.replace('_','+').split('+'))
        if len(genes)!=2 or len(set(genes))!=2 or not set(genes)<=set(ix):
            raise ValueError('Each pair needs two distinct genes with measured single-activation calibration. This model does not support other interventions or cell types.')
        labels.append('+'.join(genes));left.append(z['singleEffects'][ix[genes[0]]]);right.append(z['singleEffects'][ix[genes[1]]])
    left,right=np.array(left),np.array(right);a,b=left@z['encoder'],right@z['encoder']
    features=(np.concatenate([a+b,np.abs(a-b),a*b],axis=1)-z['featureCenter'])/z['featureScale']
    hidden=np.tanh(features@z['w1']+z['b1']);codes=(hidden@z['w2']+z['b2'])*z['codeScale']
    result=float(z['alpha'])*(left+right)+codes@z['decoder'].T+z['residualCenter']
    return labels,z['genes'],result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('pairs',nargs='+');p.add_argument('--model',type=Path,default=Path(__file__).with_name('MODEL.npz'));p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    labels,genes,values=predict(a.model,a.pairs)
    np.savez_compressed(a.output,conditions=np.array(labels),genes=genes,predicted=values)
    print(json.dumps({'output':str(a.output),'conditions':labels,'genes':len(genes),'unit':'difference of mean log1p(counts per 10000), matched controls','context':'K562 CRISPRa, measured-single calibration required','status':'research prototype; not whole-cell simulation'}))
