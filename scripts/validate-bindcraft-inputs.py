"""Check prepared Fold configs and target data against real upstream loaders on CPU."""
import json, os, pathlib, sys, tempfile
os.environ['JAX_PLATFORMS']='cpu';ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'vendor/bindcraft2')]
from worker import Service
from fold_engine import Engine
from bindcraft.settings import read_settings,build_design_settings
from bindcraft.protein_preparation import prepare_targets
from bindcraft.protein import ResidueFlags,has_residue_flag
import numpy as np
report={'scope':'Upstream settings parsing and target backbone/hotspot correspondence only. No design/weights invoked.','cases':[]}
with tempfile.TemporaryDirectory() as temp:
 s=Service(temp);project=s.project_create({'name':'Upstream reference'});e=Engine(s)
 for source in [ROOT/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb',ROOT/'fixtures/ANGPTL3.cif']:
  record=s.import_structure({'projectId':project['id'],'path':str(source)});shared=e.fold_structure({'structureId':record['id']});st=shared['structure'];chain=st['chains'][0]['id'];residues=[r for r in st['residues'] if r['chain']==chain and r['polymer']]
  for modality in ('binder','peptide'):
   config={'projectId':project['id'],'structureId':record['id'],'targetChains':[chain],'hotspots':[residues[0]['id']],'coldspots':[residues[-1]['id']],'modality':modality,'seed':2718,'candidates':2,'attempts':5}
   job=e.bindcraft_prepare(config);folder=pathlib.Path(temp)/'jobs'/job['id'];settings=read_settings(folder/'settings.json');design=build_design_settings(settings);targets=prepare_targets(design)
   target=targets['target'];assert len(target)==len(residues),(len(target),len(residues));assert int(has_residue_flag(target.flags,ResidueFlags.HOTSPOT).sum())==1;assert int(has_residue_flag(target.flags,ResidueFlags.COLDSPOT).sum())==1
   # Backbone identity checked through the actual upstream public atom parser.
   from bindcraft.protein import read_structure_atoms
   upstream=read_structure_atoms(str(folder/('input.pdb' if source.suffix=='.pdb' else 'input.cif')))
   own={(a['chain'],a['num'],a['name']):a['xyz'] for a in st['atoms'] if a['chain']==chain and a['name'] in ('N','CA','C','O')}
   other={(a['chain_id'],a['res_id'],a['name']):a['coord'] for a in upstream if a['chain_id']==chain and a['name'] in ('N','CA','C','O')}
   assert own.keys()==other.keys();error=max(float(np.max(np.abs(np.asarray(own[key])-other[key]))) for key in own);assert error<1e-4
   report['cases'].append({'fixture':source.name,'modality':modality,'residues':len(target),'backboneAtoms':len(own),'maxCoordinateDifferenceAngstrom':error,'hotspots':settings['targets'][0]['hotspots'],'coldspots':settings['targets'][0]['coldspots'],'state':'passed'})
 s.db.close()
report['state']='passed';(ROOT/'reports/upstream-input-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
