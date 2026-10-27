"""Real child-process analysis of explicitly artificial coordinate frames."""
import hashlib,json,os,unittest
from test_project_metal import ProjectMetalTests as Fixtures

def fixture():
 text='REMARK Artificial C-alpha coordinates for numerical QA only.\n'
 for frame,delta in [(1,0),(2,3)]:
  text+=f'MODEL     {frame:4d}\n'
  for i,(x,y,z) in enumerate([(0.,0.,0.),(2.,0.,0.),(0.,1.,0.),(0.,0.,1.)],1):text+=f'ATOM  {i:5d}   CA ALA A{i:4d}    {x+delta:8.3f}{y:8.3f}{z:8.3f}{1.:6.2f}{0.:6.2f}           C\n'
  text+='ENDMDL\n'
 return text+'END\n'
class TrajectoryAnalysisContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def source(self):
  self.file.write_text(fixture());self.s.setting_set({'key':'openmmPython','value':os.sys.executable});return self.s.import_structure({'projectId':self.project['id'],'path':str(self.file),'coordinateSets':True,'name':'Artificial Cα translation QA'})
 def payload(self,record,**extra):return {'projectId':self.project['id'],'structureId':record['id'],**extra}
 def test_actual_raw_measurement_persists_source_pinned_analysis_without_inventing_time(self):
  record=self.source();result=self.s.dispatch('dynamics_analyze',self.payload(record,align=False));self.assertEqual(result['rmsdAngstrom'],[0,3]);self.assertEqual(result['rmsfAngstrom'],[1.5]*4);self.assertEqual(len(result['radiusOfGyrationAngstrom']),2);self.assertAlmostEqual(result['radiusOfGyrationAngstrom'][0],(1.125)**.5);self.assertAlmostEqual(result['radiusOfGyrationAngstrom'][0],result['radiusOfGyrationAngstrom'][1]);self.assertNotIn('physicalTimePs',result);self.assertTrue(result['sourceUnchanged']);self.assertEqual(hashlib.sha256((self.s.root/'assets'/record['data']['asset']).read_bytes()).hexdigest(),record['data']['sha256']);self.assertTrue(any(row['id']==result['analysisId'] for row in self.s.dispatch('observatory_library',{'projectId':self.project['id']})))
 def test_actual_rigid_fit_removes_known_translation(self):
  record=self.source();result=self.s.dispatch('dynamics_analyze',self.payload(record,align=True));self.assertLess(max(result['rmsdAngstrom']),1e-12);self.assertLess(max(result['rmsfAngstrom']),1e-12);self.assertFalse(list((self.s.root/'cache').glob('motion-*')))
 def test_unknown_fields_cross_project_or_single_model_sources_are_refused(self):
  record=self.source();other=self.s.project_create({'name':'Other'})
  for payload in (self.payload(record,temperature=300),self.payload(record,align='yes'),self.payload(record,projectId=other['id']),self.payload(self.record)):
   with self.subTest(payload=payload),self.assertRaises(ValueError):self.s.dispatch('dynamics_analyze',payload)
 def test_active_compute_guard_rolls_back_without_a_partial_analysis(self):
  record=self.source();self.s.job_new({'projectId':self.project['id']},'openmm','running')
  with self.assertRaisesRegex(ValueError,'Another local compute'):self.s.dispatch('dynamics_analyze',self.payload(record))
  self.assertFalse(self.s.db.in_transaction);self.assertEqual(self.s.dispatch('observatory_library',{'projectId':self.project['id']}),[])
del Fixtures
