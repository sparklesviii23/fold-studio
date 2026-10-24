"""Explicit sequence initialization around the unchanged upstream optimizer.

The pinned implementation initializes free binders with Protein.empty(). This
scoped adapter replaces only that initializer; fixed positions keep SEQUENCE
flags, mutable positions retain DESIGN flags, and upstream omission sentinels
carry position-specific exclusions through its optimizer. No fabricated atoms.
"""
import contextlib
import json
import os
import pathlib
import sys
from .biology_contract import validate


@contextlib.contextmanager
def install(protocol):
    import jax
    import jax.numpy as jnp
    from bindcraft.protein import Protein,ResidueFlags,AMINO_ACIDS
    from bindcraft.sequence_optimization import OMITTED_AMINO_ACID_LOGIT
    bio=validate(protocol)
    sequences=bio.get('sequences',{});parents=bio.get('parents',[])
    if len(sequences)!=1 or len(parents)!=1:raise ValueError('Sequence-seeded initialization requires one explicit biological reference per trajectory campaign.')
    chain,sequence=next(iter(sequences.items()));mask=bio.get('constraints',{}).get(chain,{'mutable':list(range(1,len(sequence)+1))})
    for key,codes in mask.get('excluded',{}).items():
        if sequence[int(key)-1] in codes:raise ValueError('The requested starting sequence contains an explicitly excluded residue; resolve the conflicting constraint.')
    if mask.get('preferred'):raise ValueError('Persistent position-specific preferences are not supported by the seeded optimizer.')
    exclusions=mask.get('excluded',{})
    if exclusions and (set(map(int,exclusions))!=set(mask['mutable']) or len(set(exclusions.values()))!=1):raise ValueError('Seeded optimizer requires identical omissions across mutable positions; use MPNN for per-position exclusions.')
    original=Protein.empty
    def seeded(length,key):
        if length!=len(sequence):raise ValueError('Seeded binder length differs from the original reference; random or truncated initialization refused.')
        empty=original(length,key)
        logits=jax.nn.one_hot(jnp.asarray([AMINO_ACIDS.index(a) for a in sequence]),len(AMINO_ACIDS),dtype=empty.sequence.dtype)
        flags=jnp.asarray([int(ResidueFlags.DESIGN) if i in mask['mutable'] else int(ResidueFlags.SEQUENCE) for i in range(1,length+1)],dtype=jnp.uint8)
        for pos,codes in mask.get('excluded',{}).items():
            for aa in codes:logits=logits.at[int(pos)-1,AMINO_ACIDS.index(aa)].set(OMITTED_AMINO_ACID_LOGIT)
        return empty.replace(sequence=logits,flags=flags)
    Protein.empty=staticmethod(seeded)
    try:yield
    finally:Protein.empty=staticmethod(original)


def main():
    from bindcraft.campaign import launch_campaign
    from bindcraft.model_weights import proteinmpnn_weights
    settings=pathlib.Path(sys.argv[1]);protocol=json.loads(pathlib.Path(sys.argv[2]).read_text())
    config=json.loads(settings.read_text())
    if config.get('binder_scaffold') or int(config.get('copies',1))!=1:raise ValueError('This sequence-seeded adapter cannot replace a scaffold or multichain initialization.')
    with install(protocol):
        status=launch_campaign(str(settings),af2_weights=os.environ['BINDCRAFT_AF2_PARAMS'],mpnn_weights=proteinmpnn_weights())
    raise SystemExit(status)


if __name__=='__main__':main()
