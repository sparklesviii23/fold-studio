import pathlib,sys,tempfile,json,unittest,hashlib
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
import genome_public as public
def row(**changes):return {'accessionversion':'NC_123456.1','slen':9,'organism':'Artificial numerical fixture','taxid':1,'moltype':'dna','topology':'linear','geneticcode':'11',**changes}
class PublicReferenceTests(unittest.TestCase):
 def test_identity_version_and_size_preflight(self):
  described=public.describe(row(),{'url':'https://eutils.ncbi.nlm.nih.gov','sha256':'a'*64});self.assertTrue(described['downloadSupported']);self.assertFalse(public.describe(row(slen=public.MAX_BASES+1),{})['downloadSupported']);self.assertFalse(public.describe(row(moltype='rna'),{})['downloadSupported'])
  with patch.object(public,'ncbi_json',return_value=({'result':{'uids':['1'],'1':row(accessionversion='NC_123456.2')}},{})),self.assertRaisesRegex(ValueError,'different sequence version'):public.summary('NC_123456.1')
  for accession in ('NC_123456','https://example.com','../../x','NC_1.1/abc'):
   with self.assertRaises(ValueError):public.summary(accession)
 def test_review_change_and_unsupported_records_prevent_download(self):
  with patch.object(public,'summary',return_value=public.describe(row(),{})),patch.object(public,'retrieve') as transfer,self.assertRaisesRegex(ValueError,'metadata changed'):public.fetch(None,{'approvedReferenceDownload':True,'expectedSummarySha256':'changed'})
  transfer.assert_not_called()
 def test_reference_bytes_publish_only_after_actual_biopython_identity_check(self):
  runtime=pathlib.Path(__file__).resolve().parents[2]/'current/fold Metal Dev.app/Contents/Resources/runtime-boltz/bin/python3.12'
  if not runtime.is_file():self.skipTest('Existing Biopython runtime unavailable')
  raw=b'LOCUS       NC_123456                  9 bp    DNA     linear   SYN 01-JAN-2000\nDEFINITION  Artificial numerical fixture.\nACCESSION   NC_123456\nVERSION     NC_123456.1\nSOURCE      Artificial numerical fixture\n  ORGANISM  Artificial numerical fixture\n            Unclassified.\nFEATURES             Location/Qualifiers\n     source          1..9\n                     /organism="Artificial numerical fixture"\nORIGIN\n        1 atgaaataa\n//\n'
  with tempfile.TemporaryDirectory() as tmp:
   s=Service(pathlib.Path(tmp)/'library');s.setting_set({'key':'enginePython','value':str(runtime)});pid=s.project_create({'name':'Isolated public transfer contract'})['id'];review=public.describe(row(),{});p={'projectId':pid,'approvedReferenceDownload':True,'accession':'NC_123456.1','expectedSummarySha256':review['summarySha256']}
   receipt={'url':'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?id=NC_123456.1','sha256':hashlib.sha256(raw).hexdigest()}
   with patch.object(public,'summary',return_value=review),patch.object(public,'retrieve',return_value=(raw,receipt)),patch.object(public.time,'sleep'):
    imported=s.dispatch('genome_public_fetch',p);self.assertEqual(imported['replicons'][0]['length'],9);self.assertEqual(imported['sources'][-1]['sha256'],receipt['sha256']);self.assertEqual(s.dispatch('genome_public_fetch',p)['publicFetchState'],'already_imported')
    bad=public.describe(row(slen=10),{})
    with patch.object(public,'summary',return_value=bad),self.assertRaisesRegex(ValueError,'differs from the reviewed'):s.dispatch('genome_public_fetch',{**p,'expectedSummarySha256':bad['summarySha256']})
   self.assertEqual(len(s.dispatch('genome_list',{'projectId':pid})),1);s.db.close()
