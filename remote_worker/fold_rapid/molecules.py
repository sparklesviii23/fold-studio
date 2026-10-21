"""Lossless snapshots with observed author/label residue correspondence."""
import math
import pathlib
from .contracts import digest

def inspect(raw, fmt):
    import gemmi
    text=raw.decode('utf-8')
    structure=(gemmi.read_pdb_string(text) if fmt=='pdb' else gemmi.make_structure_from_block(gemmi.cif.read_string(text).sole_block()))
    if len(structure)!=1:raise ValueError('Select one explicit coordinate model before submission.')
    chains={}
    for chain in structure[0]:
        if chain.name in chains:raise ValueError('Repeated chain identity must be resolved before submission.')
        residues=[]
        for res in chain:
            aa=gemmi.find_tabulated_residue(res.name)
            if not aa.is_amino_acid():continue
            if not res.find_atom('CA','*'):raise ValueError('Polymer residue is missing its C-alpha coordinate.')
            if aa.one_letter_code.upper() not in 'ACDEFGHIKLMNPQRSTVWY':raise ValueError('Resolve noncanonical amino-acid identities before computation.')
            for atom in res:
                if not all(math.isfinite(v) for v in (atom.pos.x,atom.pos.y,atom.pos.z)):raise ValueError('Nonfinite coordinates.')
            residues.append({'authorNumber':res.seqid.num,'insertionCode':res.seqid.icode.strip(),'labelNumber':res.label_seq,'name':res.name,'aminoAcid':aa.one_letter_code.upper()})
        if residues:
            ids=[(r['authorNumber'],r['insertionCode']) for r in residues]
            if len(set(ids))!=len(ids):raise ValueError('Ambiguous author residue numbering.')
            chains[chain.name]={'sequence':''.join(r['aminoAcid'] for r in residues),'residues':residues}
    if not chains:raise ValueError('No protein coordinates found.')
    return {'sha256':digest(raw),'format':fmt,'chains':chains,'residueCount':sum(len(c['residues']) for c in chains.values()),'numberingPolicy':'Original bytes, author numbering and insertion codes preserved; label numbering recorded separately.'}

def selected_target(manifest):
    from .contracts import target_bytes
    result=inspect(target_bytes(manifest['target']),manifest['target']['format'])
    if not set(manifest['target']['chains'])<=set(result['chains']):raise ValueError('Requested target chain does not exist in the snapshot.')
    if manifest['engine'] in ('proteinmpnn','af2_multimer'):
        design=manifest['design'].get('designChains',[])
        if not design or not set(design)<=set(result['chains']):raise ValueError('Select existing binder/redesign chains in the coordinate snapshot.')
        if set(design)&set(manifest['target']['chains']):raise ValueError('Binder/redesign chains and fixed target chains must be disjoint.')
    hotspots=manifest['design'].get('hotspots',{})
    if not isinstance(hotspots,dict) or set(hotspots)-set(manifest['target']['chains']):raise ValueError('Hotspots must name selected target chains.')
    for chain,values in hotspots.items():
        valid={str(r['authorNumber'])+r['insertionCode'] for r in result['chains'][chain]['residues']}
        if not isinstance(values,list) or any(str(v) not in valid for v in values):raise ValueError('Hotspot does not correspond to an observed author residue.')
    return result

def confined(root, relative):
    root=pathlib.Path(root).resolve();path=root/relative
    if not isinstance(relative,str) or not relative or path.is_symlink() or root not in path.resolve().parents:
        raise ValueError('Artifact path escapes its immutable job directory.')
    return path
