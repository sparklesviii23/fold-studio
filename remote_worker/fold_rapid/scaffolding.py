"""Verified RFdiffusion CLI handoff for one atomic motif with fixed-length flanks.

Only real model output is collected. Generated backbone glycine identities are
never presented as a sequence-designed or independently folded candidate.
"""
import pathlib
from .contracts import canonical
from .molecules import inspect
from .biology_contract import validate


def prepare(job,m,runtime,models):
    import gemmi
    mapping=inspect((job/('target.'+m['target']['format'])).read_bytes(),m['target']['format'])
    bio=validate(m.get('biology',{}),mapping);motif=bio.get('motif')
    if not motif:raise ValueError('Specify an observed atomic motif and explicit flank lengths.')
    if bio.get('chemistry'):raise ValueError('This RFdiffusion motif adapter does not silently translate chemical modifications.')
    structure=gemmi.read_structure(str(job/('target.'+m['target']['format'])))
    pdb=job/'motif-input.pdb';structure.write_pdb(str(pdb))
    contig='/'.join(([str(motif['prefix'])+'-'+str(motif['prefix'])] if motif['prefix'] else [])+[motif['chain']+str(motif['start'])+'-'+str(motif['end'])]+([str(motif['suffix'])+'-'+str(motif['suffix'])] if motif['suffix'] else []))
    entry=pathlib.Path(runtime['source'])/'scripts/run_inference.py'
    if not entry.is_file():raise ValueError('Configured RFdiffusion source has no official inference entry point.')
    (job/'scaffold-contract.json').write_text(canonical({'sourceMotif':motif,'contig':contig,'outputMotifStart':motif['prefix']+1,'targetConditioning':False,'reason':'Single motif scaffolding; target-conditioned scaffolding requires an explicit separate assembly mapping.'}))
    return [runtime['python'],str(entry),'inference.input_pdb='+str(pdb),'inference.output_prefix='+str(job/'output/scaffold'),'inference.num_designs='+str(m['design']['count']),'inference.ckpt_override_path='+models['rfdiffusion-base']['path'],'inference.deterministic=True','inference.design_startnum='+str(m['seed']),'contigmap.contigs=['+contig+']']


def motif_rmsd(reference,mobile):
    import numpy as np
    a=np.asarray(reference,dtype=float);b=np.asarray(mobile,dtype=float)
    if a.shape!=b.shape or len(a)<3 or a.shape[1:]!=(3,) or not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError('Motif comparison requires at least three matched finite C-alpha coordinates.')
    a=a-a.mean(0);b=b-b.mean(0);u,_,v=np.linalg.svd(b.T@a);fix=np.eye(3);fix[-1,-1]=np.linalg.det(u@v);rotation=u@fix@v
    return float(np.sqrt(np.mean(np.sum((b@rotation-a)**2,axis=1))))


def collect(job,m):
    import gemmi
    motif=m['biology']['motif'];source=gemmi.read_structure(str(job/'motif-input.pdb'))
    reference=[r for r in source[0][motif['chain']] if motif['start']<=r.seqid.num<=motif['end']]
    length=motif['end']-motif['start']+1
    if len(reference)!=length:raise ValueError('Source motif mapping changed.')
    rows=[]
    for file in sorted((job/'output').glob('scaffold_*.pdb')):
        structure=gemmi.read_structure(str(file))
        if len(structure)!=1 or len(structure[0])!=1:raise ValueError('RFdiffusion output violates the single-scaffold contract.')
        chain=structure[0][0];residues=list(chain)
        if len(residues)!=motif['prefix']+length+motif['suffix']:raise ValueError('RFdiffusion scaffold length differs from the fixed contig contract.')
        matched=residues[motif['prefix']:motif['prefix']+length]
        rmsd=motif_rmsd([list(r.find_atom('CA','*').pos) for r in reference],[list(r.find_atom('CA','*').pos) for r in matched])
        rows.append(({'design':file.stem,'outcome':'backbone_only_requires_sequence_design' if rmsd<=motif['maxRmsd'] else 'rejected_motif_drift','metrics':{'motifCaRmsdAngstrom':rmsd},'chainRoles':{'binder':[chain.name],'target':[]},'motifOutputPositions':list(range(motif['prefix']+1,motif['prefix']+length+1)),'targetConditioning':False},file,'design','sequence'))
    return rows
