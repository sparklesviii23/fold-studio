import pathlib,sys,tempfile,unittest,math
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
from periodic_dynamics import validate
class PeriodicTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=Service(pathlib.Path(self.tmp.name)/'library');self.pid=self.s.project_create({'name':'Isolated periodic numerical reference'})['id'];self.s.setting_set({'key':'openmmPython','value':str(pathlib.Path(__file__).resolve().parents[2]/'current/FOLD STUDIO Metal Dev.app/Contents/Resources/runtime-openmm/bin/python3.12')})
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def request(self,**change):return {'projectId':self.pid,'positionsNm':[[.1,.1,.1],[2.7,.1,.1]],'boxLengthsNm':[3,3,3],'sigmaNm':.34,'epsilonKJMol':1.,'massDalton':40.,'cutoffNm':1.,'temperatureK':100.,'frictionPerPs':1.,'stepPs':.001,'steps':0,'reportInterval':10,'seed':42,**change}
 def run_model(self,**change):return self.s.dispatch('periodic_lj_run',self.request(**change))
 def test_periodic_energy_and_force_match_independent_pair_formula(self):
  r=self.run_model();v=r['data']['result'];ratio=.34/.4;energy=4*(ratio**12-ratio**6);force=24*(2*ratio**12-ratio**6)/.4
  self.assertAlmostEqual(v['frames'][0]['potentialKJMol'],energy,places=5);self.assertAlmostEqual(v['initialForcesKJMolPerNm'][0][0],force,places=4);self.assertAlmostEqual(sum(a[0] for a in v['initialForcesKJMolPerNm']),0,places=7);self.assertEqual(v['frames'][0]['positionsNm'],self.request()['positionsNm']);self.assertEqual(self.run_model()['id'],r['id']);self.assertEqual(self.s.job(r['data']['jobId'])['state'],'completed')
 def test_translation_and_wrapping_invariance_and_actual_bounded_trajectory(self):
  a=self.run_model()['data']['result'];b=self.run_model(positionsNm=[[.3,.3,.3],[2.9,.3,.3]])['data']['result'];self.assertAlmostEqual(a['frames'][0]['potentialKJMol'],b['frames'][0]['potentialKJMol'],places=5)
  value=self.run_model(steps=100)['data']['result'];self.assertEqual(value['state'],'bounded_trajectory_completed');self.assertEqual(len(value['frames']),11);self.assertAlmostEqual(value['frames'][-1]['timePs'],.1,places=10);self.assertTrue(all(math.isfinite(frame['potentialKJMol']) for frame in value['frames']));self.assertEqual(self.s.dispatch('periodic_lj_results',{'projectId':self.pid})[0]['data']['request']['positionsNm'],self.request()['positionsNm'])
 def test_overlap_cutoff_units_and_cloud_mode_are_explicit(self):
  for change in ({'positionsNm':[[0,0,0],[.01,0,0]]},{'cutoffNm':1.5},{'sigmaNm':float('nan')},{'steps':15},{'boxLengthsNm':[0,3,3]},{'stepPs':1}):
   with self.subTest(change=change),self.assertRaises(ValueError):validate(self.request(**change))
  self.s.dispatch('execution_backend_select',{'mode':'modal'})
  with self.assertRaisesRegex(ValueError,'Cloud Mode'):self.run_model()
