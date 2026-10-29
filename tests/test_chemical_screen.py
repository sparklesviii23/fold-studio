import base64,hashlib,json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
class ChemicalTableTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=Service(pathlib.Path(self.tmp.name)/'library');self.pid=self.s.project_create({'name':'Isolated chemical table QA'})['id'];self.s.setting_set({'key':'enginePython','value':str(pathlib.Path(__file__).resolve().parents[2]/'current/FOLD STUDIO Metal Dev.app/Contents/Resources/runtime-boltz/bin/python3.12')})
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def run_table(self,**change):return self.s.dispatch('chemical_screen',{'projectId':self.pid,'csvText':'id,smiles\nethanol,CCO\npropane,CCC\nethanol_equivalent,C(C)O\n','querySmiles':'CCO','smarts':'[#8]',**change})
 def test_exact_graph_similarity_descriptors_atom_matches_and_original(self):
  record=self.run_table();rows=record['data']['result']['rows'];self.assertEqual([r['id'] for r in rows[:2]],['ethanol','ethanol_equivalent']);self.assertEqual(rows[0]['MorganTanimoto'],1);self.assertEqual(rows[0]['formula'],'C2H6O');self.assertAlmostEqual(rows[0]['molecularWeightDa'],46.069,places=3);self.assertEqual(rows[0]['HBD'],1);self.assertEqual(rows[0]['HBA'],1);self.assertEqual(rows[0]['SMARTSMatchesAtomIndices0Based'],[[2]]);self.assertEqual(rows[2]['SMARTSMatchesAtomIndices0Based'],[]);self.assertEqual(record['data']['source']['sha256'],hashlib.sha256(base64.b64decode(record['data']['source']['csvTextBase64'])).hexdigest());self.assertEqual(self.run_table()['id'],record['id']);self.assertEqual(self.s.dispatch('chemical_screens',{'projectId':self.pid})[0]['data'],record['data'])
 def test_invalid_molecules_and_multifragment_inputs_publish_nothing(self):
  for change in ({'csvText':'id,smiles\nx,not_a_molecule\n'},{'csvText':'id,smiles\nsalt,[Na+].[Cl-]\n'},{'csvText':'id,smiles\nx,CCO\nx,CC\n'},{'smarts':'['}):
   with self.subTest(change=change),self.assertRaises(ValueError):self.run_table(**change)
  self.assertEqual(self.s.dispatch('chemical_screens',{'projectId':self.pid}),[])
 def test_query_absence_preserves_order_and_cloud_mode_blocks_compute(self):
  r=self.run_table(querySmiles='',smarts='')['data']['result'];self.assertEqual([row['id'] for row in r['rows']],['ethanol','propane','ethanol_equivalent']);self.assertIsNone(r['rows'][0]['MorganTanimoto']);self.assertIsNone(r['rows'][0]['SMARTSMatchesAtomIndices0Based']);self.s.dispatch('execution_backend_select',{'mode':'modal'})
  with self.assertRaisesRegex(ValueError,'Cloud Mode'):self.run_table()
