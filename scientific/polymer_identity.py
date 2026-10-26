"""Chemical identity helpers for display only; never edit source residue names.

Explicit mmCIF entity/component annotations take precedence over residue aliases.
Unresolved identities remain unresolved, including unusual modified nucleotides.
"""
DNA={'DA':'A','DC':'C','DG':'G','DT':'T','DI':'I','DU':'U'}
RNA={'A':'A','C':'C','G':'G','U':'U','I':'I'}
PROTEIN=dict(zip(('ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL').split(),'ARNDCQEGHILKMFPSTWYV'))

def chemical_identity(name,component_type='',parent='',entity_type='',atom_names=()):
 name=name.upper();kind=component_type.lower();entity=entity_type.lower();parents=[p.strip().upper() for p in parent.split(',') if p.strip() not in ('','.','?')]
 if 'hybrid' in entity:polymer='DNA/RNA hybrid'
 elif 'polydeoxyribonucleotide' in entity:polymer='DNA'
 elif 'polyribonucleotide' in entity:polymer='RNA'
 elif 'polypeptide' in entity:polymer='Protein'
 elif 'dna' in kind:polymer='DNA'
 elif 'rna' in kind:polymer='RNA'
 elif 'peptide' in kind:polymer='Protein'
 elif len(parents)==1 and parents[0] in DNA:polymer='DNA'
 elif len(parents)==1 and parents[0] in RNA:polymer='RNA'
 elif len(parents)==1 and parents[0] in PROTEIN:polymer='Protein'
 elif name in DNA:polymer='DNA'
 elif name in RNA:polymer='RNA'
 elif name in PROTEIN:polymer='Protein'
 elif "O2'" in atom_names and ("C1'" in atom_names or 'P' in atom_names):polymer='RNA'
 elif {"C1'","C3'","C4'"}.issubset(atom_names):polymer='Nucleic acid (unresolved)'
 else:polymer='Unclassified'
 aliases=PROTEIN if polymer=='Protein' else {**DNA,**RNA}
 letter=aliases.get(name)
 if letter is None and len(parents)==1:letter=aliases.get(parents[0])
 return {'polymerType':polymer,'canonicalSymbol':letter,'originalComponent':name,'parentComponent':parents[0] if len(parents)==1 else None,'modified':name not in aliases,'identityEvidence':'mmCIF entity/component annotations' if component_type or entity_type else 'explicit standard residue alias or positive ribose atom evidence','identityResolved':letter is not None}
