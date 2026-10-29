import pathlib,sys,tempfile,unittest,subprocess,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
SAM='@HD\tVN:1.6\tSO:unsorted\n@SQ\tSN:chr\tLN:100\n'
SAM+='complex\t0\tchr\t2\t60\t3M1I1=1X2D2M3N1M1S\t*\t0\t0\tACGTACGTAC\tIIII!IIIII\n'
SAM+='reverse\t16\tchr\t2\t60\t2M\t*\t0\t0\tCC\tII\n'
for flag in (256,512,1024,2048):SAM+=f'flag{flag}\t{flag}\tchr\t2\t60\t2M\t*\t0\t0\tTT\tII\n'
SAM+='unavailable\t0\tchr\t2\t255\t2M\t*\t0\t0\tAA\tII\nnoquality\t0\tchr\t2\t60\t2M\t*\t0\t0\tCC\t*\nambiguous\t0\tchr\t1\t60\t1M\t*\t0\t0\tN\tI\nunmapped\t4\t*\t0\t0\t*\t*\t0\t0\tT\tI\n'
class CoverageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.s=Service(self.root/'library');self.pid=self.s.project_create({'name':'Numerical alignment observation QA'})['id'];self.python=str(pathlib.Path(__file__).resolve().parents[2]/'current/FOLD STUDIO Metal Dev.app/Contents/Resources/runtime-boltz/bin/python3.12');self.s.setting_set({'key':'enginePython','value':self.python});self.path=self.root/'reference.sam';self.path.write_text(SAM);self.record=self.s.dispatch('genomic_alignment_import',{'projectId':self.pid,'path':str(self.path),'format':'sam'})
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def request(self,**change):return {'projectId':self.pid,'alignmentId':self.record['id'],'contig':'chr','start':1,'end':16,'minimumMAPQ':20,'minimumBaseQuality':20,'includeUnavailableMAPQ':False,**change}
 def compute(self,**change):return self.s.dispatch('genomic_coverage',self.request(**change))
 def test_known_CIGAR_quality_flags_reverse_alignment_and_unavailable_MAPQ(self):
  r=self.compute();v=r['data']['result'];expected=[0,2,2,1,0,1,0,0,1,1,0,0,0,1,0,0];self.assertEqual(v['ACGTObservationDepth'],expected);self.assertEqual(sum(v['baseObservationCounts']['A']),2);self.assertEqual(sum(v['baseObservationCounts']['C']),4);self.assertEqual(sum(v['baseObservationCounts']['G']),2);self.assertEqual(sum(v['baseObservationCounts']['T']),1);self.assertEqual(v['counters']['ambiguousBaseObservations'],1);self.assertEqual(v['counters']['missingSequenceOrQualityRecords'],1);self.assertEqual(self.compute()['id'],r['id']);self.assertEqual(self.compute(includeUnavailableMAPQ=True)['data']['result']['ACGTObservationDepth'][1],3);self.assertEqual(sum(self.compute(minimumBaseQuality=0)['data']['result']['ACGTObservationDepth']),10)
 def test_archive_restores_coverage_source_link_and_original_bytes(self):
  from project_archive import inspect_archive
  from project_restore import import_archive
  value=self.compute();archive=self.root/'coverage.zip';self.s.export_project({'id':self.pid,'path':str(archive)});review=inspect_archive({'path':str(archive)});copy=import_archive(self.s,{'path':str(archive),'expectedSha256':review['archiveSha256']});alignment=self.s.dispatch('genomic_alignments',{'projectId':copy['projectId']})[0];coverage=self.s.dispatch('genomic_coverages',{'projectId':copy['projectId'],'alignmentId':alignment['id']})[0];self.assertEqual(coverage['data']['result'],value['data']['result']);self.assertEqual(coverage['data']['sourceRecordId'],alignment['id']);self.assertEqual((self.s.root/'assets'/coverage['data']['sourceFile']['asset']).read_text(),SAM)
 def test_crosscheck_independent_pysam_count_coverage_API(self):
  code="""import pysam,sys,json
pysam.view('-b','-o',sys.argv[2],sys.argv[1],catch_stdout=False);pysam.sort('-o',sys.argv[3],sys.argv[2]);pysam.index(sys.argv[3])
with pysam.AlignmentFile(sys.argv[3],'rb') as stream:
 values=stream.count_coverage('chr',0,16,quality_threshold=20,read_callback=lambda r:not r.flag&0xF04 and r.mapping_quality!=255 and r.mapping_quality>=20 and r.query_qualities is not None)
print(json.dumps({b:list(v) for b,v in zip('ACGT',values)}))
"""
  result=subprocess.run([self.python,'-I','-c',code,str(self.path),str(self.root/'in.bam'),str(self.root/'sorted.bam')],check=True,capture_output=True,text=True);reference=json.loads(result.stdout);self.assertEqual(self.compute()['data']['result']['baseObservationCounts'],reference)
 def test_integrity_bounds_and_cloud_mode(self):
  for change in ({'contig':'unknown'},{'start':0},{'end':101},{'minimumMAPQ':255},{'minimumBaseQuality':-1},{'includeUnavailableMAPQ':'yes'}):
   with self.subTest(change=change),self.assertRaises(ValueError):self.compute(**change)
  self.s.dispatch('execution_backend_select',{'mode':'modal'})
  with self.assertRaisesRegex(ValueError,'Cloud Mode'):self.compute()
  self.s.dispatch('execution_backend_select',{'mode':'local'});(self.s.root/'assets'/self.record['data']['sourceFile']['asset']).write_text('corrupted')
  with self.assertRaisesRegex(ValueError,'changed'):self.compute()
