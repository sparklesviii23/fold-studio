#!/usr/bin/env python3
"""Optional independent numerical checks. Run in an environment with NumPy/Biopython.
No network, predictions, native session or app database is used.
"""
import argparse, hashlib, json, pathlib, sys
sys.dont_write_bytecode=True
repo=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'scientific'))
from intelligence import RADII,fit,parse_structure,sasa

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--structure',type=pathlib.Path,default=repo/'fixtures/ANGPTL3.cif');parser.add_argument('--points',type=int,default=960);parser.add_argument('--max-relative-area-error',type=float,default=.02);args=parser.parse_args()
 if not 60<=args.points<=2000:parser.error('Use 60–2000 sphere points.')
 try:
  import numpy as np
  import Bio
  from Bio.PDB.Atom import Atom
  from Bio.PDB.Chain import Chain
  from Bio.PDB.Model import Model
  from Bio.PDB.Residue import Residue
  from Bio.PDB.SASA import ShrakeRupley
 except ImportError:raise SystemExit('Use the separately installed scientific environment containing NumPy and Biopython; the production analysis service does not require them.')
 rng=np.random.default_rng(20261017);errors=[]
 for _ in range(30):
  moving=rng.normal(size=(30,3));fixed=rng.normal(size=(30,3));actual=fit(moving.tolist(),fixed.tolist());a=moving-moving.mean(0);b=fixed-fixed.mean(0);u,s,vt=np.linalg.svd(a.T@b);rotation=u@np.diag([1,1,np.linalg.det(u@vt)])@vt;expected=float(np.sqrt(np.sum((a@rotation-b)**2)/len(a)));errors.append(abs(actual['rmsd']-expected))
 raw=args.structure.read_bytes();data=parse_structure(raw.decode(),'pdb' if args.structure.suffix.lower()=='.pdb' else 'mmcif');atoms=[a for a in data['atoms'] if a['element'] not in ('H','D')]
 unknown={a['element'] for a in atoms}-RADII.keys()
 if unknown:raise SystemExit('Unsupported reference radii: '+', '.join(sorted(unknown)))
 # Identical input atoms isolate the two independent surface algorithms. This
 # comparison is not a second parser-validation test.
 model=Model(0);chains={};residues={}
 for a in atoms:
  if a['chain'] not in chains:chains[a['chain']]=Chain(a['chain']);model.add(chains[a['chain']])
  if a['residue'] not in residues:
   residue=Residue((' ',a['num'],a['ins'] or ' '),a['resname'],'');residues[a['residue']]=residue;chains[a['chain']].add(residue)
  residues[a['residue']].add(Atom(a['name'],np.array(a['xyz'],dtype=float),a['bfactor'] or 0,a['occupancy'],' ',a['name'].rjust(4),a['id']+1,element=a['element']))
 ours=sasa(atoms,args.points,1.4);ShrakeRupley(probe_radius=1.4,n_points=args.points,radii_dict=RADII).compute(model,level='M');reference=float(model.sasa);relative=abs(ours-reference)/reference if reference else None
 output={'sourceSha256':hashlib.sha256(raw).hexdigest(),'atoms':len(atoms),'versions':{'numpy':np.__version__,'biopython':Bio.__version__},'hornVsSvd':{'seed':20261017,'fits':30,'maximumRmsdDifferenceAngstrom':max(errors)},'surface':{'oursAngstromSquared':ours,'biopythonAngstromSquared':reference,'relativeDifference':relative,'spherePoints':args.points,'probeAngstrom':1.4,'maximumRelativeDifference':args.max_relative_area_error},'scope':'Numerical cross-check on identical selected atoms; finite-sampling agreement does not establish biological validity.'}
 output['passed']=max(errors)<1e-10 and relative is not None and relative<=args.max_relative_area_error;print(json.dumps(output,indent=2));return 0 if output['passed'] else 1
if __name__=='__main__':sys.exit(main())
