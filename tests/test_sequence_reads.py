import gzip,hashlib,io,json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from sequence_reads import summarize,dispatch
from worker import Service
class ReadTests(unittest.TestCase):
 def test_known_scores_cycles_composition_and_expected_error_are_distinct(self):
  value=summarize(io.BytesIO(b'@a\nACGN\n+\n!5?I\n@b\nTG\n+b\nII\n'))
  self.assertEqual(value['reads'],2);self.assertEqual(value['bases'],6);self.assertEqual(value['ambiguousBases'],1);self.assertEqual(value['GCPercentOfACGT'],60);self.assertEqual(value['arithmeticMeanPhred'],170/6);self.assertAlmostEqual(value['sumReportedBaseErrorProbabilities'],1+.01+.001+3*.0001);self.assertEqual(value['Q30BaseFraction'],4/6);self.assertEqual(value['perCycle'][0]['bases'],2);self.assertEqual(value['perCycle'][3]['bases'],1)
 def test_empty_truncated_wrapped_encoding_and_identifier_mismatch_fail(self):
  for raw in (b'',b'@r\nAC\n+\nI',b'r\nA\n+\nI\n',b'@r\nAC\nGT\n+\nIIII\n',b'@r\nA\n+other\nI\n',b'@r\nA\n+\n\x7f\n',b'@r\nX\n+\nI\n'):
   with self.subTest(raw=raw),self.assertRaises(ValueError):summarize(io.BytesIO(raw))
 def test_gzip_original_roundtrip_duplicate_integrity_and_cloud_admission(self):
  from project_archive import inspect_archive
  from project_restore import import_archive
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);s=Service(root/'library');pid=s.project_create({'name':'Isolated read quality QA'})['id'];path=root/'supplied.fastq.gz';original=gzip.compress(b'@a\nACGN\n+\n!5?I\n');path.write_bytes(original);p={'projectId':pid,'path':str(path),'qualityEncoding':'Phred+33'}
   record=s.dispatch('reads_import',p);self.assertEqual(record['data']['sourceFile']['sha256'],hashlib.sha256(original).hexdigest());self.assertEqual(s.dispatch('reads_import',p)['id'],record['id']);self.assertEqual(len(s.dispatch('reads_list',{'projectId':pid})),1)
   archive=root/'reads.zip';s.export_project({'id':pid,'path':str(archive)});review=inspect_archive({'path':str(archive)});restored=import_archive(s,{'path':str(archive),'expectedSha256':review['archiveSha256']});copy=s.dispatch('reads_list',{'projectId':restored['projectId']})[0];self.assertEqual((s.root/'assets'/copy['data']['sourceFile']['asset']).read_bytes(),original);self.assertEqual(copy['data']['summary'],record['data']['summary'])
   s.dispatch('execution_backend_select',{'mode':'modal'})
   with self.assertRaisesRegex(ValueError,'Cloud Mode'):s.dispatch('reads_import',p)
   s.dispatch('execution_backend_select',{'mode':'local'});(s.root/'assets'/record['data']['sourceFile']['asset']).write_bytes(b'corrupted')
   with self.assertRaisesRegex(ValueError,'changed'):s.dispatch('reads_import',p)
   s.db.close()
 def test_failed_import_publishes_nothing_and_encoding_is_explicit(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);s=Service(root/'library');pid=s.project_create({'name':'Rejected reads QA'})['id'];path=root/'invalid.fastq';path.write_bytes(b'@r\nAA\n+\nI\n');p={'projectId':pid,'path':str(path),'qualityEncoding':'Phred+33'};before=list((s.root/'assets').iterdir())
   with self.assertRaises(ValueError):s.dispatch('reads_import',p)
   self.assertEqual(list((s.root/'assets').iterdir()),before);self.assertEqual(s.dispatch('reads_list',{'projectId':pid}),[])
   with self.assertRaisesRegex(ValueError,'Explicitly'):s.dispatch('reads_import',{**p,'qualityEncoding':'auto'})
   s.db.close()
