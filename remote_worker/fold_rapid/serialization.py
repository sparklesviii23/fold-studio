"""Prediction serialization with explicit original chain/residue correspondence."""
def write_prediction(template,proteins,path,binder_chains,target_chains,plddt=None):
    import gemmi
    import numpy as np
    from bindcraft.protein import ATOM_NAMES
    source=gemmi.read_structure(str(template));out=gemmi.Structure();model=gemmi.Model('1');offset=0
    for name,protein in proteins.items():
        original=[r for r in source[0][name] if gemmi.find_tabulated_residue(r.name).is_amino_acid()]
        positions=np.asarray(protein.atoms);mask=np.asarray(protein.atom_mask)
        if len(original)!=len(positions):raise ValueError('Prediction residue correspondence differs from original target snapshot.')
        chain=gemmi.Chain(name)
        for index,old in enumerate(original):
            residue=gemmi.Residue();residue.name=old.name;residue.seqid=old.seqid;residue.label_seq=old.label_seq;residue.het_flag='A'
            for atom_index,atom_name in enumerate(ATOM_NAMES):
                if not bool(mask[index,atom_index]):continue
                atom=gemmi.Atom();atom.name=atom_name;atom.element=gemmi.Element(atom_name[0]);atom.pos=gemmi.Position(*map(float,positions[index,atom_index]));atom.occ=1
                if plddt is not None:atom.b_iso=float(plddt[offset+index])*100
                residue.add_atom(atom)
            chain.add_residue(residue)
        model.add_chain(chain);offset+=len(original)
    out.add_model(model);out.setup_entities();doc=out.make_mmcif_document();block=doc.sole_block()
    block.set_pair('_bindcraft.binder_chains',gemmi.cif.quote(','.join(binder_chains)));block.set_pair('_bindcraft.target_chains',gemmi.cif.quote(','.join(target_chains)))
    doc.write_file(str(path))
