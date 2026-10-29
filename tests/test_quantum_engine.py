import os,pathlib,sys,tempfile,unittest,fcntl,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
from quantum_engine import validate
class QuantumTests(unittest.TestCase):
 def request(self,**change):return {'xyz':'2\nNumerical H2 reference\nH 0 0 0\nH 0 0 .74','unit':'Angstrom','basis':'sto-3g','method':'HF','charge':0,'spin':0,'gradients':True,**change}
 def test_input_units_charge_spin_and_bounds_are_explicit(self):
  self.assertEqual(validate(self.request())['electrons'],2)
  for change in ({'xyz':'H 0 0 0'},{'spin':1},{'charge':True},{'basis':'arbitrary-file'},{'unit':'unknown'},{'xyz':'2\ncoincident\nH 0 0 0\nH 0 0 0'},{'xyz':'1\nUnsupported\nU 0 0 0'}):
   with self.subTest(change=change),self.assertRaises(ValueError):validate(self.request(**change))
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=Service(pathlib.Path(self.tmp.name)/'library');self.pid=self.s.project_create({'name':'Isolated quantum reference qualification'})['id'];runtime=pathlib.Path(os.environ.get('FOLD_TEST_QUANTUM_PYTHON','/tmp/fold-pyscf-probe/venv/bin/python3.12'))
  bundled=pathlib.Path(__file__).resolve().parents[2]/'current/FOLD STUDIO Metal Dev.app/Contents/Resources/runtime-boltz/bin/python3.12'
  self.s.setting_set({'key':'enginePython','value':str(runtime if runtime.is_file() else bundled)})
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def calculate(self,**change):
  status=self.s.dispatch('quantum_status',{'projectId':self.pid})
  if not status.get('pinnedRuntime'):self.skipTest('Pinned CPU quantum runtime not prepared')
  return self.s.dispatch('quantum_calculate',{'projectId':self.pid,**self.request(**change)})
 def test_genuine_HF_energy_gradient_density_and_cached_record(self):
  record=self.calculate(densityGrid=True);r=record['data']['result'];self.assertTrue(r['converged']);self.assertAlmostEqual(r['totalEnergyHartree'],-1.1167593073964255,places=9);self.assertAlmostEqual(r['densityOverlapElectronTrace'],2,places=9);self.assertAlmostEqual(r['electronicEnergyHartree']+r['nuclearRepulsionHartree'],r['totalEnergyHartree'],places=9);self.assertAlmostEqual(r['gradientHartreePerBohr'][0][2],-r['gradientHartreePerBohr'][1][2],places=9);self.assertAlmostEqual(sum(r['mullikenAtomicCharges']),0,places=8);self.assertEqual(self.calculate(densityGrid=True)['id'],record['id']);self.assertEqual(len(self.s.dispatch('quantum_list',{'projectId':self.pid})),1)
  field=r['densityField'];self.assertEqual(field['dimensions'],[24,24,24]);self.assertEqual(field['unit'],'electrons/Bohr^3');self.assertLess(abs(field['boxTrapezoidalElectronIntegral']-2),.05);self.assertEqual(len(field['slice']['valuesXThenY']),24);self.assertEqual(field['cubeText'].splitlines()[2].split()[0],'2');self.assertTrue(r['SCFIterationHistory']);self.assertEqual(self.s.job(record['data']['jobId'])['state'],'completed')
  from unittest.mock import patch
  import quantum_engine
  original=quantum_engine.run
  def interrupted(service,request,job_id=None):
   if not job_id:return original(service,request)
   service.job_cancel({'id':job_id});return r
  with patch.object(quantum_engine,'run',interrupted),self.assertRaisesRegex(ValueError,'cancelled'):self.calculate(xyz='2\nUnpublished cancelled result test\nH 0 0 0\nH 0 0 .75')
  self.assertEqual(len(self.s.dispatch('quantum_list',{'projectId':self.pid})),1);self.assertIn('cancelled',[row['state'] for row in self.s.dispatch('quantum_jobs',{'projectId':self.pid})])
 def test_translation_invariance_and_open_shell_density(self):
  a_record=self.calculate(gradients=False);a=a_record['data']['result'];b=self.calculate(xyz='2\nTranslated H2 reference\nH 1 2 3\nH 1 2 3.74',gradients=False)['data']['result'];self.assertAlmostEqual(a['totalEnergyHartree'],b['totalEnergyHartree'],places=9)
  h_record=self.calculate(xyz='1\nNeutral doublet hydrogen\nH 0 0 0',spin=1,gradients=False);h=h_record['data']['result'];self.assertTrue(h['converged']);self.assertAlmostEqual(h['densityOverlapElectronTrace'],1,places=9);self.assertAlmostEqual(h['totalEnergyHartree'],-.4665818495572753,places=8);self.assertEqual(len(h['orbitalChannels']),2);self.assertAlmostEqual(h['spinSquareExpectation'],.75,places=8)
  terms=[{'recordId':a_record['id'],'coefficient':-1},{'recordId':h_record['id'],'coefficient':2}]
  energy=self.s.dispatch('quantum_reaction',{'projectId':self.pid,'terms':terms});self.assertAlmostEqual(energy['data']['electronicReactionEnergyHartree'],2*h['totalEnergyHartree']-a['totalEnergyHartree'],places=12)
  self.assertEqual(self.s.dispatch('quantum_reaction',{'projectId':self.pid,'terms':terms})['id'],energy['id'])
  with self.assertRaisesRegex(ValueError,'balanced'):self.s.dispatch('quantum_reaction',{'projectId':self.pid,'terms':[terms[0],{**terms[1],'coefficient':1}]})
  changed={**h_record['data'],'result':{**h,'totalEnergyHartree':-999}}
  with self.s.db:self.s.db.execute('UPDATE records SET data=? WHERE id=?',(json.dumps(changed),h_record['id']))
  with self.assertRaisesRegex(ValueError,'integrity'):self.s.dispatch('quantum_reaction',{'projectId':self.pid,'terms':terms})

 def test_genuine_PBE_convergence_and_exclusive_compute_lease(self):
  r=self.calculate(method='PBE',gradients=False)['data']['result'];self.assertTrue(r['converged']);self.assertEqual(r['PBEGridLevel'],2);self.assertAlmostEqual(r['totalEnergyHartree'],-1.1520727844018834,places=7)
  with (self.s.root/'cache/quantum-calculation.lock').open('a') as lease:
   fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
   with self.assertRaisesRegex(ValueError,'already running'):self.calculate()
