import pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
class AlignmentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.s=Service(self.root/'library');self.pid=self.s.project_create({'name':'Isolated pairwise numerical QA'})['id'];self.s.setting_set({'key':'enginePython','value':str(pathlib.Path(__file__).resolve().parents[2]/'current/FOLD STUDIO Metal Dev.app/Contents/Resources/runtime-boltz/bin/python3.12')})
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def align(self,**change):return self.s.dispatch('sequence_align',{'projectId':self.pid,'target':'ACGTTAC','query':'ACGTAC','alphabet':'DNA','mode':'global','queryOrientation':'forward','matchScore':2,'mismatchScore':-1,'gapOpenScore':-3,'gapExtendScore':-1,**change})
 def test_known_insertion_and_scoring_are_saved_and_reopened(self):
  r=self.align();v=r['data']['result'];self.assertEqual(v['score'],9);self.assertEqual(v['identicalResiduePairs'],6);self.assertEqual(v['gapBases'],1);self.assertEqual(v['targetCoordinateRange0BasedHalfOpen'],[0,7]);self.assertEqual(v['orientedQueryCoordinateRange0BasedHalfOpen'],[0,6]);self.assertEqual(self.align()['id'],r['id']);self.assertEqual(self.s.dispatch('sequence_alignments',{'projectId':self.pid})[0]['data'],r['data'])
 def test_reverse_complement_RNA_local_offsets_and_absent_positive_hit(self):
  r=self.align(target='AACG',query='CGUU',alphabet='RNA',queryOrientation='reverse_complement')['data']['result'];self.assertEqual(r['orientedQuery'],'AACG');self.assertEqual(r['score'],8)
  local=self.align(target='TTTACGTAAA',query='ACGT',mode='local')['data']['result'];self.assertEqual(local['targetCoordinateRange0BasedHalfOpen'],[3,7]);self.assertEqual(local['identicalResiduePairs'],4)
  self.assertEqual(self.align(target='AAAA',query='CCCC',mode='local')['data']['result']['state'],'no_positive_local_alignment')
 def test_reference_handoff_rechecks_exact_source_and_rejects_stale_target(self):
  fa=self.root/'ref.fna';fa.write_text('>chr\nTTTACGTAAA\n');ref=self.s.dispatch('genome_import',{'projectId':self.pid,'fastaPath':str(fa),'metadata':{'organism':'Artificial fixture','assembly':'Numerical QA','source':'Synthetic data'}});context={'referenceId':ref['id'],'replicon':'chr','start':4,'end':7,'strand':'+'};r=self.align(target='ACGT',query='ACGT',targetReference=context);self.assertEqual(r['data']['targetReference']['referenceId'],ref['id'])
  with self.assertRaisesRegex(ValueError,'differs'):self.align(target='ACGA',targetReference=context)
 def test_limits_alphabets_and_cloud_are_explicit(self):
  for change in ({'target':'ACGN'},{'target':'A'*10000,'query':'C'*10000},{'gapOpenScore':0},{'alphabet':'protein','queryOrientation':'reverse_complement'},{'target':'acgt'}):
   with self.subTest(change=change),self.assertRaises(ValueError):self.align(**change)
  self.s.dispatch('execution_backend_select',{'mode':'modal'})
  with self.assertRaisesRegex(ValueError,'Cloud Mode'):self.align()
