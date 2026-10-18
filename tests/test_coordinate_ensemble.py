"""Synthetic multi-frame import contracts; live native checks are separate."""
import hashlib,json,unittest
from test_project_metal import ProjectMetalTests as Fixtures,w,pdb
import coordinate_ensemble as ensemble

def frames():return ('MODEL        3\n'+pdb().replace('END\n','')+'ENDMDL\nMODEL        7\n'+pdb().replace('   1.450','   2.450').replace('END\n','')+'ENDMDL\nEND\n').encode()
class CoordinateEnsembleContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def test_explicit_frames_are_pinned_without_inventing_time_or_simulation(self):
  data=frames();info=ensemble.inspect(data);self.assertEqual(info['frameIds'],[3,7]);self.assertEqual(info['atomsPerFrame'],4);self.assertEqual(info['sourceSha256'],hashlib.sha256(data).hexdigest());self.assertIn('no dynamics',info['interpretation'])
 def test_malformed_missing_or_ambiguous_frames_are_refused(self):
  raw=frames()
  for data in (pdb().encode(),raw.replace(b'MODEL        7',b'MODEL        3'),raw.replace(b'ENDMDL\nEND\n',b'END\n'),b'ENDMDL\n'+raw,raw.replace(b'ENDMDL\nMODEL',b'MODEL',1)):
   with self.subTest(data=data),self.assertRaises(ValueError):ensemble.inspect(data)
 def test_topology_reordering_or_changing_atom_metadata_is_refused(self):
  raw=frames();a,b=raw.split(b'MODEL        7')
  for changed in (b.replace(b' ALA ',b' GLY ',1),b.replace(b'  1.00',b'  0.50',1),b.replace(b' 75.00',b' 76.00',1),b.replace(b'   N ',b'  XX ',1)):
   with self.subTest(changed=changed),self.assertRaises(ValueError):ensemble.inspect(a+b'MODEL        7'+changed)
 def test_nonfinite_coordinates_alternates_and_uncertainty_records_are_refused(self):
  raw=frames()
  for data in (raw.replace(b'   1.450',b'     nan',1),raw.replace(b' ALA ',b'AALA ',1),raw+b'ANISOU\n'):
   with self.subTest(data=data),self.assertRaises(ValueError):ensemble.inspect(data)
 def test_import_retains_all_original_bytes_and_verified_metadata(self):
  self.file.write_bytes(frames());record=self.s.import_structure({'projectId':self.project['id'],'path':str(self.file),'coordinateSets':True});self.assertEqual((self.s.root/'assets'/record['data']['asset']).read_bytes(),frames());self.assertEqual(record['data']['metadata']['coordinateEnsemble'],ensemble.inspect(frames()));self.assertIsNone(record['data']['confidenceKind'])
 def test_invalid_ensemble_creates_no_library_record_or_asset(self):
  before=set((self.s.root/'assets').iterdir());count=len(self.s.library({})['records'])
  for value in (True,'true'):
   with self.assertRaises(ValueError):self.s.import_structure({'projectId':self.project['id'],'path':str(self.file),'coordinateSets':value})
  self.assertEqual(set((self.s.root/'assets').iterdir()),before);self.assertEqual(len(self.s.library({})['records']),count)
 def test_bundle_contains_ensemble_validator(self):
  root=w.pathlib.Path(w.__file__).parents[1];resources=json.loads((root/'src-tauri/tauri.conf.json').read_text())['bundle']['resources'];self.assertIn('../scientific/coordinate_ensemble.py',resources)
 def test_reversed_frame_numbers_and_duplicate_named_atoms_are_refused(self):
  raw=frames()
  for data in (raw.replace(b'MODEL        3',b'MODEL        9'),raw.replace(b'  CA ',b'   N ')):
   with self.subTest(data=data),self.assertRaises(ValueError):ensemble.inspect(data)
del Fixtures
