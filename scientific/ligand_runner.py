"""Deterministic original RDKit conformers; no docking or protonation inference."""
import hashlib,json,math,pathlib,platform,sys,time
sys.dont_write_bytecode=True
from rdkit import Chem,rdBase
from rdkit.Chem import AllChem,Descriptors,rdMolDescriptors

VERSION='2026.09.1'
def digest(raw):return hashlib.sha256(raw).hexdigest()
def prepare(request,folder):
 if rdBase.rdkitVersion!=VERSION:raise ValueError('Ligand preparation requires the reviewed RDKit '+VERSION+' runtime.')
 params=Chem.SmilesParserParams();params.parseName=False;params.allowCXSMILES=False
 mol=Chem.MolFromSmiles(request['smiles'],params)
 if mol is None:raise ValueError('Enter a valid isomeric SMILES string.')
 if len(Chem.GetMolFrags(mol))!=1:raise ValueError('Prepare one connected molecule; salt stripping is not inferred.')
 if not 1<=mol.GetNumHeavyAtoms()<=128:raise ValueError('Ligand preparation supports 1–128 heavy atoms.')
 if any(a.GetIsotope() or a.GetNumRadicalElectrons() for a in mol.GetAtoms()):raise ValueError('Isotopic labels and radical states are not supported by this initial ligand transport.')
 unspecified=[info for info in Chem.FindPotentialStereo(mol) if str(info.specified)=='Unspecified']
 if unspecified:raise ValueError('Specify the potential stereocenters and double-bond stereochemistry explicitly in the SMILES.')
 smiles=Chem.MolToSmiles(mol,isomericSmiles=True);mol=Chem.AddHs(mol)
 if mol.GetNumAtoms()>512:raise ValueError('Ligand preparation supports at most 512 atoms after adding hydrogens.')
 if not AllChem.MMFFHasAllMoleculeParams(mol):raise ValueError('MMFF94s has no complete parameters for this molecule; no alternate force field was substituted.')
 policy=AllChem.ETKDGv3();policy.randomSeed=request['seed'];policy.numThreads=1;policy.enforceChirality=True;policy.pruneRmsThresh=-1.
 ids=list(AllChem.EmbedMultipleConfs(mol,numConfs=request['conformers'],params=policy))
 if not ids:raise ValueError('ETKDGv3 could not generate a conformer.')
 optimized=list(AllChem.MMFFOptimizeMoleculeConfs(mol,numThreads=1,maxIters=500,mmffVariant='MMFF94s'))
 candidates=[(float(energy),int(id)) for id,(status,energy) in zip(ids,optimized,strict=True) if status==0 and math.isfinite(energy)]
 if not candidates:raise ValueError('No generated conformer reached MMFF94s convergence within 500 iterations.')
 energy,best=min(candidates);conf=mol.GetConformer(best)
 if any(not math.isfinite(v) for p in conf.GetPositions() for v in p):raise ValueError('Non-finite ligand coordinates.')
 # Verify geometry-derived stereochemistry, independently of the retained tags.
 geometry=Chem.Mol(mol);Chem.RemoveStereochemistry(geometry);Chem.AssignStereochemistryFrom3D(geometry,confId=best,replaceExistingTags=True)
 if Chem.MolToSmiles(Chem.RemoveHs(geometry),isomericSmiles=True)!=smiles:raise ValueError('The optimized geometry does not retain the specified stereochemistry.')
 mol.SetProp('_Name',request['name']);mol.SetProp('FOLD_METHOD','ETKDGv3; MMFF94s; single CPU thread; no pH inference');mol.SetProp('FOLD_CANONICAL_SMILES',smiles);mol.SetIntProp('FOLD_SEED',request['seed']);mol.SetDoubleProp('MMFF94s_energy_kcal_mol',energy)
 sdf=folder/'ligand.sdf';writer=Chem.SDWriter(str(sdf));writer.write(mol,confId=best);writer.close()
 check=next(iter(Chem.SDMolSupplier(str(sdf),removeHs=False)))
 if check is None or Chem.MolToSmiles(Chem.RemoveHs(check),isomericSmiles=True)!=smiles:raise ValueError('SDF round trip changed molecular connectivity or stereochemistry.')
 if check.GetNumAtoms()!=mol.GetNumAtoms() or any(a.GetAtomicNum()!=b.GetAtomicNum() or a.GetFormalCharge()!=b.GetFormalCharge() for a,b in zip(mol.GetAtoms(),check.GetAtoms(),strict=True)):raise ValueError('SDF changed explicit atom identities or charges.')
 sdf_error=max((math.dist(conf.GetAtomPosition(i),check.GetConformer().GetAtomPosition(i)) for i in range(mol.GetNumAtoms())),default=0.)
 if sdf_error>0.0001:raise ValueError('SDF coordinate precision exceeded 0.0001 Å round-trip tolerance.')
 names=[atom.GetSymbol()+str(atom.GetIdx()+1) for atom in mol.GetAtoms()]
 lines=['data_fold_ligand','#',"_entity.id 1","_entity.type non-polymer","_chem_comp.id UNL","_chem_comp.type 'NON-POLYMER'",'#','loop_','_chem_comp_atom.comp_id','_chem_comp_atom.atom_id','_chem_comp_atom.type_symbol','_chem_comp_atom.charge']
 lines+=['UNL '+names[a.GetIdx()]+' '+a.GetSymbol()+' '+str(a.GetFormalCharge()) for a in mol.GetAtoms()]
 if mol.GetNumBonds():
  lines+=['#','loop_','_chem_comp_bond.comp_id','_chem_comp_bond.atom_id_1','_chem_comp_bond.atom_id_2','_chem_comp_bond.value_order','_chem_comp_bond.pdbx_aromatic_flag']
  order={'SINGLE':'SING','DOUBLE':'DOUB','TRIPLE':'TRIP','AROMATIC':'AROM'}
  for bond in mol.GetBonds():
   kind=str(bond.GetBondType())
   if kind not in order:raise ValueError('Unsupported ligand bond type: '+kind)
   lines.append('UNL '+names[bond.GetBeginAtomIdx()]+' '+names[bond.GetEndAtomIdx()]+' '+order[kind]+' '+('Y' if bond.GetIsAromatic() else 'N'))
 fields=['group_PDB','id','type_symbol','label_atom_id','label_alt_id','label_comp_id','label_asym_id','label_entity_id','label_seq_id','pdbx_PDB_ins_code','Cartn_x','Cartn_y','Cartn_z','occupancy','B_iso_or_equiv','auth_seq_id','auth_comp_id','auth_asym_id','auth_atom_id','pdbx_PDB_model_num','pdbx_formal_charge']
 lines+=['#','loop_']+['_atom_site.'+field for field in fields]
 graph_atoms=[]
 for atom in mol.GetAtoms():
  i=atom.GetIdx();xyz=list(map(float,conf.GetAtomPosition(i)));lines.append(' '.join(map(str,['HETATM',i+1,atom.GetSymbol(),names[i],'.','UNL','L',1,'.','?',*xyz,1.,'?',1,'UNL','L',names[i],1,atom.GetFormalCharge()])));graph_atoms.append({'id':i,'name':names[i],'element':atom.GetSymbol(),'formalCharge':atom.GetFormalCharge(),'xyz':xyz,'aromatic':atom.GetIsAromatic()})
 cif=folder/'ligand.cif';cif.write_text('\n'.join(lines)+'\n#\n')
 return {'state':'prepared_conformer','canonicalIsomericSmiles':smiles,'inputSmiles':request['smiles'],'formula':rdMolDescriptors.CalcMolFormula(mol),'molecularWeightDa':Descriptors.MolWt(mol),'formalCharge':Chem.GetFormalCharge(mol),'atoms':graph_atoms,'bonds':[{'a':b.GetBeginAtomIdx(),'b':b.GetEndAtomIdx(),'order':str(b.GetBondType()),'aromatic':b.GetIsAromatic()} for b in mol.GetBonds()],'conformers':{'requested':request['conformers'],'embedded':len(ids),'converged':len(candidates),'selectedId':best,'energies':[{'id':int(i),'status':int(state),'energyKcalMol':float(e) if math.isfinite(e) else None} for i,(state,e) in zip(ids,optimized,strict=True)]},'energyKcalMol':energy,'sdfCoordinateMaxErrorAngstrom':sdf_error,'method':{'embedding':'RDKit ETKDGv3','forceField':'MMFF94s','maxIterations':500,'threads':1,'seed':request['seed'],'stereochemistryFrom3D':'verified'},'runtime':{'rdkit':rdBase.rdkitVersion,'python':sys.version,'architecture':platform.machine()},'artifacts':{'ligand.cif':digest(cif.read_bytes()),'ligand.sdf':digest(sdf.read_bytes())},'limitations':['Generated local molecular-mechanics conformer; not a docking pose or prediction of binding/activity.','Input formal charges and stereochemistry are retained; no pH titration, neutralization, salt stripping or tautomer search.','Energy in kcal/mol applies only to this atom/protonation state and force field; it is not a binding free energy.','ETKDGv3 sampling and local MMFF94s convergence do not prove the global minimum or experimental conformation.']}

if __name__=='__main__':
 request_file=pathlib.Path(sys.argv[1]);folder=request_file.parent;start=time.perf_counter();result=prepare(json.loads(request_file.read_text()),folder);result.update(requestSha256=digest(request_file.read_bytes()),runnerSha256=digest(pathlib.Path(__file__).read_bytes()),seconds=time.perf_counter()-start);(folder/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:result[k] for k in ('state','formula','energyKcalMol','seconds','method')},indent=2))
