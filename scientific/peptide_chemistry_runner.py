"""Explicit peptide topology and stereochemistry, real RDKit; no pose transfer."""
import hashlib
import json
import pathlib
import sys
from rdkit import Chem,rdBase
from rdkit.Chem import AllChem,Descriptors,rdMolDescriptors


def prepare(p,folder):
    if rdBase.rdkitVersion!='2026.09.1':raise ValueError('Use the pinned RDKit 2026.09.1 runtime.')
    sequence=p['sequence']
    if not 3<=len(sequence)<=60 or set(sequence)-set('ACDEFGHIKLMNPQRSTVWY'):raise ValueError('This chemistry profile supports 3–60 canonical starting residues.')
    if set(p)-{'sequence','headToTail','disulfides','dResidues','seed','conformers'}:raise ValueError('Unsupported peptide chemistry operation; arbitrary staples require an explicitly validated molecular graph.')
    if type(p.get('headToTail',False))is not bool:raise ValueError('Cyclization must be an explicit boolean.')
    mol=Chem.MolFromFASTA(sequence,flavor=0)
    if mol is None:raise ValueError('RDKit could not construct the canonical starting peptide.')
    def find(position,name):
        atoms=[a.GetIdx() for a in mol.GetAtoms() if a.GetPDBResidueInfo() and a.GetPDBResidueInfo().GetResidueNumber()==position and a.GetPDBResidueInfo().GetName().strip()==name]
        if len(atoms)!=1:raise ValueError('Unambiguous residue atom mapping required: '+str(position)+' '+name)
        return atoms[0]
    d=p.get('dResidues',[])
    if not isinstance(d,list) or len(set(d))!=len(d) or any(type(i)is not int or not 1<=i<=len(sequence) or sequence[i-1] in 'GIT' for i in d):raise ValueError('D substitutions require distinct alpha-chiral residues. Glycine is achiral; Ile/Thr require explicit side-chain stereo handling and are refused in this profile.')
    for pos in d:mol.GetAtomWithIdx(find(pos,'CA')).InvertChirality()
    links=p.get('disulfides',[])
    if not isinstance(links,list) or len(links)>8:raise ValueError('At most eight explicit disulfides are supported.')
    used=set();bonds=[]
    for pair in links:
        if not isinstance(pair,list) or len(pair)!=2 or len(set(pair))!=2 or any(type(i)is not int or not 1<=i<=len(sequence) or sequence[i-1]!='C' or i in used for i in pair):raise ValueError('Disulfides require disjoint cysteine pairs.')
        used.update(pair);bonds.append((find(pair[0],'SG'),find(pair[1],'SG')))
    edit=Chem.RWMol(mol)
    for a,b in bonds:
        edit.AddBond(a,b,Chem.BondType.SINGLE)
        for i in (a,b):edit.GetAtomWithIdx(i).SetNumExplicitHs(0);edit.GetAtomWithIdx(i).SetNoImplicit(False)
    if p.get('headToTail'):
        n,c=find(1,'N'),find(len(sequence),'C');acid=find(len(sequence),'OXT')
        # Remove only the terminal hydroxyl atom; form a chemically explicit amide.
        if edit.GetAtomWithIdx(acid).GetDegree()!=1:raise ValueError('C-terminal hydroxyl connectivity differs from the supported canonical peptide.')
        edit.AddBond(c,n,Chem.BondType.SINGLE);edit.GetAtomWithIdx(n).SetNumExplicitHs(0);edit.GetAtomWithIdx(n).SetNoImplicit(False);edit.RemoveAtom(acid)
    mol=edit.GetMol();Chem.SanitizeMol(mol);Chem.AssignStereochemistry(mol,cleanIt=True,force=True)
    if len(Chem.GetMolFrags(mol))!=1:raise ValueError('Chemical product is disconnected.')
    unspecified=[i for i in Chem.FindPotentialStereo(mol) if str(i.specified)=='Unspecified']
    if unspecified:raise ValueError('Chemical transformation introduced unresolved stereochemistry.')
    smiles=Chem.MolToSmiles(mol,isomericSmiles=True)
    roundtrip=Chem.MolFromSmiles(smiles)
    if roundtrip is None or Chem.MolToSmiles(roundtrip,isomericSmiles=True)!=smiles:raise ValueError('Chemical graph round-trip failed.')
    atoms=[]
    for atom in mol.GetAtoms():
        info=atom.GetPDBResidueInfo();atoms.append({'index':atom.GetIdx(),'element':atom.GetSymbol(),'residuePosition':info.GetResidueNumber() if info else None,'sourceAtomName':info.GetName().strip() if info else None,'formalCharge':atom.GetFormalCharge(),'cip':atom.GetProp('_CIPCode') if atom.HasProp('_CIPCode') else None})
    result={'schemaVersion':1,'engine':'RDKit','version':rdBase.rdkitVersion,'request':p,'canonicalIsomericSmiles':smiles,'formula':rdMolDescriptors.CalcMolFormula(mol),'molecularWeightDa':Descriptors.MolWt(mol),'formalCharge':Chem.GetFormalCharge(mol),'atoms':atoms,'bonds':[{'a':b.GetBeginAtomIdx(),'b':b.GetEndAtomIdx(),'order':str(b.GetBondType())} for b in mol.GetBonds()],'stereochemistry':'Explicit residue graph and CIP assignments; original L side-chain stereocentres retained, requested alpha chirality inverted.','conformers':[],'limitations':['Valence/stereochemistry validation is not binding, proteolytic stability or synthesizability validation.','No docking pose is inherited from the linear parent.','No implicit protonation, neutralization, D-residue folding support or predictor substitution.']}
    count=p.get('conformers',0)
    if type(count)is not int or not 0<=count<=3:raise ValueError('Choose zero to three conformers.')
    if count:
        if mol.GetNumHeavyAtoms()>256:raise ValueError('Conformer profile is limited to 256 heavy atoms; topology-only validation remains available.')
        hydrogenated=Chem.AddHs(mol);policy=AllChem.ETKDGv3();policy.randomSeed=p['seed'];policy.numThreads=1;policy.enforceChirality=True
        ids=list(AllChem.EmbedMultipleConfs(hydrogenated,numConfs=count,params=policy))
        if not ids:raise ValueError('Real ETKDGv3 macrocycle embedding failed; no coordinates fabricated.')
        # Export sampled conformers honestly, without claiming minimization or equilibrium.
        for id in ids:
            geometry=Chem.Mol(hydrogenated);Chem.RemoveStereochemistry(geometry);Chem.AssignStereochemistryFrom3D(geometry,confId=id,replaceExistingTags=True)
            if Chem.MolToSmiles(Chem.RemoveHs(geometry),isomericSmiles=True)!=smiles:raise ValueError('Sampled conformer changed chemical stereochemistry.')
            path=folder/('conformer-'+str(id)+'.sdf');writer=Chem.SDWriter(str(path));writer.write(hydrogenated,confId=id);writer.close();result['conformers'].append({'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'method':'RDKit ETKDGv3 sampled conformer; not energy-minimized or a bound pose'})
    (folder/'chemistry.json').write_text(json.dumps(result,indent=2,allow_nan=False));return result


if __name__=='__main__':
    folder=pathlib.Path(sys.argv[1]);prepare(json.loads((folder/'request.json').read_text()),folder)
