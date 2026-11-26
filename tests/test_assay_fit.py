import pathlib,sys,unittest,math,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from test_research_cinema import ResearchCinemaTests as Fixture
class AssayFitTests(unittest.TestCase):
 setUp=Fixture.setUp
 tearDown=Fixture.tearDown
 call=Fixture.call
 def assay(self,direction='increasing',technical=2):
  rows=[]
  for dose in (0,.1,.5,2,5,20,100,500):
   fraction=0 if dose==0 else 1/(1+(5/dose)**1.2)
   response=2+8*(fraction if direction=='increasing' else 1-fraction)
   for bio,offset in [('a',-.2),('b',0),('c',.2)]:
    for tech in range(technical):rows.append({'concentration':dose,'response':response+offset,'biologicalReplicate':bio,'technicalReplicate':str(tech),'sampleGroup':'supplied'})
  return {'name':'Synthetic 4PL numerical reference only','endpoint':'Authored numerical response','concentrationUnit':'nM','responseUnit':'Artificial RU','replicateDesign':'explicit_biological_technical','rows':rows}
 def configure(self):
  runtime=pathlib.Path(__file__).resolve().parents[2]/'current/fold Metal Dev.app/Contents/Resources/runtime-boltz/bin/python3.12'
  if not runtime.is_file():self.skipTest('Existing SciPy runtime unavailable')
  self.s.setting_set({'key':'enginePython','value':str(runtime)})
 def test_actual_scipy_recovers_known_curve_both_directions_without_affinity_claim(self):
  self.configure()
  for direction in ('increasing','decreasing'):
   assay=self.call('research_assay_save',**self.assay(direction));original=json.dumps(assay['data'],sort_keys=True);request={'assayId':assay['id'],'sampleGroup':'supplied','direction':direction};fit=self.call('research_assay_fit',**request);data=fit['data'];self.assertEqual(data['midpointState'],'estimated_within_observed_range');self.assertAlmostEqual(data['apparentHalfResponseConcentration'],5,places=5);self.assertAlmostEqual(data['diagnosticParameters']['hillMagnitude'],1.2,places=5);self.assertEqual(data['biologicalUnits'],3);self.assertLess(data['residualRMSE'],1e-6);self.assertIn('not a dissociation constant',data['scope']);self.assertEqual(self.call('research_assay_fit',**request)['id'],fit['id']);self.assertEqual(json.dumps(next(e for e in self.call('research_candidate')['evidence'] if e['id']==assay['id'])['data'],sort_keys=True),original)
 def test_repeated_technical_readings_do_not_create_extra_biological_units(self):
  self.configure();values=[]
  for repeats in (1,4):
   assay=self.call('research_assay_save',**self.assay(technical=repeats));fit=self.call('research_assay_fit',assayId=assay['id'],sampleGroup='supplied',direction='increasing')['data'];values.append(fit['apparentHalfResponseConcentration']);self.assertEqual(fit['biologicalUnits'],3)
  self.assertAlmostEqual(*values,places=8)
 def test_unbalanced_flat_or_wrong_direction_is_not_promoted_to_a_midpoint(self):
  self.configure();payload=self.assay();payload['rows'][0]['biologicalReplicate']='unmatched';assay=self.call('research_assay_save',**payload)
  with self.assertRaisesRegex(ValueError,'same at least three'):self.call('research_assay_fit',assayId=assay['id'],sampleGroup='supplied',direction='increasing')
  payload=self.assay()
  for row in payload['rows']:row['response']=1
  assay=self.call('research_assay_save',**payload)
  with self.assertRaisesRegex(ValueError,'varying dose response'):self.call('research_assay_fit',assayId=assay['id'],sampleGroup='supplied',direction='increasing')
  assay=self.call('research_assay_save',**self.assay());fit=self.call('research_assay_fit',assayId=assay['id'],sampleGroup='supplied',direction='decreasing')['data'];self.assertEqual(fit['midpointState'],'not_reliably_estimable');self.assertIsNone(fit['apparentHalfResponseConcentration'])
del Fixture
