"""Explicit derived protein segments preserve source geometry and provenance."""
import hashlib,json,pathlib,tempfile,unittest,zipfile
from test_project_metal import w

def pdb(numbers=(10,11,12),chain='A'):
 text=''
 for i,n in enumerate(numbers):
  for j,(name,element,x) in enumerate([('N','N',0),('CA','C',1.45),('C','C',2.9),('O','O',3.9)]):
   text+=f'ATOM  {i*4+j+1:5d} {name:>4s} ALA {chain}{n:4d}    {x+i*4:8.3f}{1.:8.3f}{2.:8.3f}{1.:6.2f}{75.:6.2f}          {element:>2s}\n'
 return text+'END\n'

class TargetFragmentContracts(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=pathlib.Path(self.tmp.name);self.s=w.Service(self.base/'library');self.project=self.s.project_create({'name':'Fragment QA'});self.file=self.base/'source.pdb';self.file.write_text(pdb());self.source=self.s.import_structure({'projectId':self.project['id'],'path':str(self.file),'confidenceKind':'AlphaFold pLDDT','metadata':{'ptm':.8,'pae':'parent-full-matrix.json'}})
  self.payload={'projectId':self.project['id'],'structureId':self.source['id'],'residues':['["A",10,""]','["A",11,""]'],'name':'Explicit observed A10–11'}
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def test_exact_source_atoms_author_numbering_and_confidence_field_preserved(self):
  lab=w.fold_engine.mi.Lab(self.s);record,path=lab.record(self.source['id']);before=path.read_bytes();self.s.dispatch('intelligence_assign',{'structureId':record['id'],'assignments':{'A':{'role':'target','identity':'Explicit source'}}})
  new=self.s.dispatch('fold_fragment',self.payload);derived=self.s.dispatch('fold_structure',{'projectId':self.project['id'],'structureId':new['id']})['structure'];original=w.fold_engine.mi.parse_structure(before.decode(),'pdb')
  atoms=[a for a in original['atoms'] if a['num'] in (10,11)]
  for key in ('xyz','num','chain','ins','name','bfactor','occupancy','element'):self.assertEqual([a[key] for a in derived['atoms']],[a[key] for a in atoms])
  self.assertEqual(before,path.read_bytes());self.assertEqual(new['data']['confidenceKind'],'AlphaFold pLDDT');self.assertEqual(lab.assigned(new['id']),lab.assigned(record['id']))
  self.assertEqual(new['data']['metadata']['derivedFrom'],{'id':record['id'],'sha256':record['data']['sha256']});self.assertNotIn('pae',new['data']['metadata']);self.assertNotIn('ptm',new['data']['metadata'])
  checked=self.s.dispatch('bindcraft_validate',{'projectId':self.project['id'],'structureId':new['id'],'targetChains':['A'],'binderLengths':[12]});self.assertEqual([r['number'] for r in checked['residueMap']],[10,11])
 def test_disjoint_regions_and_unknown_duplicate_or_empty_selections_refused(self):
  for ids in ([],['["A",10,""]']*2,['["A",99,""]'],['["A",10,""]','["A",12,""]'],None):
   with self.subTest(ids=ids),self.assertRaises(ValueError):self.s.dispatch('fold_fragment',{**self.payload,'residues':ids})
 def test_cross_project_and_changed_source_cannot_be_extracted(self):
  other=self.s.project_create({'name':'Other'})
  with self.assertRaisesRegex(ValueError,'another project'):self.s.dispatch('fold_fragment',{**self.payload,'projectId':other['id']})
  path=self.s.root/'assets'/self.source['data']['asset'];path.write_text(pdb().replace('1.450','1.451'))
  with self.assertRaisesRegex(ValueError,'checksum'):self.s.dispatch('fold_fragment',self.payload)
 def test_numbering_gaps_alternates_and_incomplete_backbones_are_refused(self):
  for raw,ids in [(pdb((10,12)),['["A",10,""]','["A",12,""]']),(pdb().replace('  CA ALA','  CAAALA'),['["A",10,""]']),(pdb().replace('   O ALA','  XX ALA'),['["A",10,""]'])]:
   self.file.write_text(raw);record=self.s.import_structure({'projectId':self.project['id'],'path':str(self.file)})
   with self.assertRaises(ValueError):self.s.dispatch('fold_fragment',{**self.payload,'structureId':record['id'],'residues':ids})
 def test_mmcif_coordinates_keep_precision_beyond_pdb_three_decimals(self):
  fields=['group_PDB','id','type_symbol','label_atom_id','label_comp_id','label_asym_id','label_seq_id','auth_asym_id','auth_seq_id','Cartn_x','Cartn_y','Cartn_z','occupancy','B_iso_or_equiv']
  raw='data_precision\nloop_\n'+'\n'.join('_atom_site.'+k for k in fields)+'\n'
  for i,(atom,el) in enumerate([('N','N'),('CA','C'),('C','C'),('O','O')],1):raw+=f'ATOM {i} {el} {atom} ALA A 1 A 10 {i}.123456789 2.234567891 3.345678912 0.987654321 87.654321\n'
  file=self.base/'precision.cif';file.write_text(raw);source=self.s.import_structure({'projectId':self.project['id'],'path':str(file)});new=self.s.dispatch('fold_fragment',{**self.payload,'structureId':source['id'],'residues':['["A",10,""]']});a=self.s.dispatch('fold_structure',{'projectId':self.project['id'],'structureId':new['id']})['structure']['atoms'][0]
  self.assertEqual(a['xyz'],[1.123456789,2.234567891,3.345678912]);self.assertEqual(a['occupancy'],.987654321);self.assertEqual(a['bfactor'],87.654321)
 def test_export_contains_original_and_derived_assets_and_explicit_selection(self):
  new=self.s.dispatch('fold_fragment',self.payload);file=self.base/'fragments.zip';self.s.export_project({'id':self.project['id'],'path':str(file)})
  with zipfile.ZipFile(file) as archive:
   for record in (self.source,new):self.assertEqual(hashlib.sha256(archive.read('assets/'+record['data']['asset'])).hexdigest(),record['data']['sha256'])
  self.assertEqual(new['data']['metadata']['fragment']['residueIds'],self.payload['residues'])
 def test_ipc_and_resource_registration_is_complete(self):
  base=pathlib.Path(w.__file__).parents[1];self.assertIn('"fold_fragment"',(base/'src-tauri/src/main.rs').read_text());self.assertIn('../scientific/target_fragment.py',json.loads((base/'src-tauri/tauri.conf.json').read_text())['bundle']['resources'])
