"""Isolated entry points for genuine upstream scientific classes."""
import json
import pathlib
import sys
from .contracts import canonical
from .molecules import inspect

def main():
    operation=sys.argv[1];job=pathlib.Path(sys.argv[2]);m=json.loads((job/'manifest.json').read_text())
    target=job/('target.'+m['target']['format']);out=job/'output'
    if operation=='screen':
        mapping=inspect(target.read_bytes(),m['target']['format'])
        (out/'structure-screen.json').write_text(canonical({'operation':'observed_structure_screen','mapping':mapping,'prediction':False,'bindingClaim':False}))
        return
    import jax
    import jax.numpy as jnp
    import numpy as np
    if any(d.platform!='gpu' for d in jax.devices()):raise ValueError('CUDA execution required; CPU fallback refused.')
    from bindcraft.protein import Protein,ResidueFlags,AMINO_ACIDS,write_structure
    from bindcraft.model_weights import proteinmpnn_weights,alphafold_parameters
    proteins=Protein.from_structure(str(target));design=m['design']['designChains']
    # A library complex can contain additional chains. Only explicitly selected
    # target/context and binder chains participate in this operation.
    selected=set(m['target']['chains'])|set(design)
    proteins={ch:p for ch,p in proteins.items() if ch in selected}
    def sequence(p):return ''.join(AMINO_ACIDS[int(i)] for i in np.asarray(p.sequence).argmax(-1))
    biology=m.get('biology',{});constraints=biology.get('constraints',{})
    for ch,seq in biology.get('sequences',{}).items():
        if ch not in proteins or len(seq)!=len(proteins[ch]):raise ValueError('Biological sequence does not match the explicit chain mapping.')
        proteins[ch]=proteins[ch].replace(sequence=jax.nn.one_hot(jnp.asarray([AMINO_ACIDS.index(a) for a in seq]),20,dtype=proteins[ch].sequence.dtype))
    before={ch:sequence(p) for ch,p in proteins.items()}
    if operation=='proteinmpnn':
        from bindcraft.proteinmpnn import ProteinMPNNSequenceModel
        masks={ch:constraints.get(ch,{'mutable':list(range(1,len(p)+1)) if ch in design else []}) for ch,p in proteins.items()}
        proteins={ch:p.replace(flags=jnp.asarray([int(ResidueFlags.DESIGN) if i in masks[ch]['mutable'] else 0 for i in range(1,len(p)+1)],dtype=jnp.uint8)) for ch,p in proteins.items()}
        model=ProteinMPNNSequenceModel(proteinmpnn_weights(),key=jax.random.PRNGKey(m['seed']),temperature=m['design'].get('temperature',0.1),length_bucket_size=1)
        if constraints:
            from bindcraft.sequence_optimization import OMITTED_AMINO_ACID_LOGIT
            bias=jnp.broadcast_to(model.redesigned_amino_acid_bias,(sum(len(p) for p in proteins.values()),20));offset=0
            for ch in sorted(proteins):
                for i in range(len(proteins[ch])):
                    for aa in masks[ch].get('preferred',{}).get(str(i+1),''):bias=bias.at[offset,AMINO_ACIDS.index(aa)].add(1.)
                    for aa in masks[ch].get('excluded',{}).get(str(i+1),''):bias=bias.at[offset,AMINO_ACIDS.index(aa)].set(OMITTED_AMINO_ACID_LOGIT)
                    offset+=1
            model.redesigned_amino_acid_bias=bias
        result=model.predict_candidates({'source':proteins},candidate_count=m['design']['count']);rows=[]
        for i,prediction in enumerate(result):
            pred=prediction['source'];chains={ch:sequence(p) for ch,p in pred.protein_complex.items()}
            if constraints:
                from .biology_contract import validate_outputs
                validate_outputs(chains,before,masks)
            for ch,p in pred.protein_complex.items():
                if ch not in design and chains[ch]!=before[ch]:raise ValueError('Fixed context sequence changed.')
                if not np.array_equal(np.asarray(p.atoms),np.asarray(proteins[ch].atoms)):raise ValueError('Fixed backbone changed.')
            rows.append({'chains':chains,'metrics':{k:float(v) for k,v in pred.metrics.items()}})
            with (out/f'sequence-{i}.fasta').open('w') as f:
                for ch in design:f.write(f'>candidate_{i}|chain={ch}|fixed_backbone\n{chains[ch]}\n')
        (out/'mpnn.json').write_text(canonical({'candidates':rows,'fixedBackbone':True,'predictedBinding':False}))
    elif operation=='af2_multimer':
        from bindcraft.af2 import AlphaFoldDesignModel
        names={ch:'binder_'+str(design.index(ch)) if ch in design else 'target_'+ch for ch in proteins}
        reverse={v:k for k,v in names.items()}
        inputs={names[ch]:p.replace(flags=jnp.full(len(p),int(ResidueFlags.DESIGN) if ch in design else int(ResidueFlags.TEMPLATE),dtype=jnp.uint8)) for ch,p in proteins.items()}
        models=('model_2_multimer_v3','model_4_multimer_v3')
        model=AlphaFoldDesignModel(presets=models,data_dir=alphafold_parameters(download=False),key=jax.random.PRNGKey(m['seed']),num_recycle=3,dropout=False)
        rows=[]
        for name in models:
            pred=model.predict({'evaluation':inputs},model=name)['evaluation']
            chains={reverse[ch]:p for ch,p in pred.protein_complex.items()}
            if any(sequence(p)!=before[ch] for ch,p in chains.items()):raise ValueError('Evaluation changed an input sequence.')
            from .serialization import write_prediction
            write_prediction(target,chains,out/(name+'.cif'),design,m['target']['chains'],pred.metrics.get('plddt'))
            # Confidence vectors/matrices are preserved in numerical form rather
            # than incorrectly cast to scalar scores or enormous JSON lists.
            arrays={k:np.asarray(v) for k,v in pred.metrics.items()}
            np.savez_compressed(out/(name+'-metrics.npz'),**arrays)
            rows.append({'model':name,'metrics':{k:float(v) for k,v in arrays.items() if v.ndim==0},'arrayMetricsArtifact':name+'-metrics.npz','plddtMean':float(arrays['plddt'].mean()) if 'plddt' in arrays else None})
            jax.clear_caches()
        (out/'evaluation.json').write_text(canonical({'predictions':rows,'recycles':3,'independent':'Held-out models2/4 within AF2 family; not independent experimental validation.'}))
    else:raise ValueError('Unsupported scientific task.')

if __name__=='__main__':main()
