import pathlib,sys,unittest,tempfile,base64,gzip,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
from genome_vcf import parse
HEADER='##fileformat=VCFv4.3\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n'
class VCFTests(unittest.TestCase):
 def test_multialleles_indels_and_original_filter_fields_remain_separate(self):
  result=parse(HEADER+'chr\t2\tx\tC\tA,G\t20\tLowQual\tDP=5\nchr\t3\t.\tGT\tG\t.\t.\t.\n',{'chr':'ACGTACGT'})
  self.assertEqual(result['rows'][0]['alts'],['A','G']);self.assertEqual(result['rows'][0]['filterRaw'],'LowQual');self.assertEqual(result['rows'][1]['end'],4)
 def test_mismatch_symbolic_unknown_and_malformed_inputs_are_rejected(self):
  for line in ('chr\t2\t.\tT\tA\t.\tPASS\t.', 'chr\t2\t.\tC\t<DEL>\t.\tPASS\t.','alias\t2\t.\tC\tA\t.\tPASS\t.','chr\t8\t.\tTT\tT\t.\tPASS\t.','chr\t2\t.\tC\tA\tNaN\tPASS\t.'):
   with self.subTest(line=line),self.assertRaises(ValueError):parse(HEADER+line+'\n',{'chr':'ACGTACGT'})
  with self.assertRaises(ValueError):parse('chr\t2\t.\tC\tA\t.\tPASS\t.',{'chr':'ACGT'})
 def test_samples_are_retained_without_inferred_genotypes_or_phase(self):
  text=HEADER.rstrip()+'\tFORMAT\tsample\nchr\t2\t.\tC\tA\t.\tPASS\t.\tGT\t0|1\n';result=parse(text,{'chr':'ACGT'});self.assertEqual(result['sampleColumnsRetainedOnlyInOriginal'],1);self.assertNotIn('genotype',result['rows'][0])
 def test_persistence_window_and_archive_restore_preserve_original(self):
  from project_archive import inspect_archive
  from project_restore import import_archive
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);s=Service(root/'library');pid=s.project_create({'name':'Isolated supplied VCF QA'})['id'];fa=root/'ref.fna';fa.write_text('>chr\nACGTACGT\n');ref=s.dispatch('genome_import',{'projectId':pid,'fastaPath':str(fa),'metadata':{'organism':'Artificial fixture','assembly':'Numerical QA','source':'Synthetic data'}});key={'projectId':pid,'id':ref['id']};vcf=root/'variants.vcf.gz';raw=gzip.compress((HEADER+'chr\t2\tx\tC\tA,G\t20\tLowQual\tDP=5\n').encode());vcf.write_bytes(raw)
   saved=s.dispatch('genome_vcf_import',{**key,'path':str(vcf)});self.assertEqual(saved['rowCount'],1);self.assertEqual(s.dispatch('genome_vcf_import',{**key,'path':str(vcf)})['state'],'already_imported')
   interval=s.dispatch('genome_region',{**key,'replicon':'chr','start':1,'end':4});self.assertEqual(interval['variantWindow']['features'][0]['feature']['variant']['alts'],['A','G'])
   before=len(s.library({})['records']);vcf.write_bytes(gzip.compress((HEADER+'chr\t2\tx\tA\tG\t.\tPASS\t.\n').encode()))
   with self.assertRaises(ValueError):s.dispatch('genome_vcf_import',{**key,'path':str(vcf)})
   self.assertEqual(len(s.library({})['records']),before)
   archive=root/'reference.zip';s.export_project({'id':pid,'path':str(archive)});review=inspect_archive({'path':str(archive)});copy=import_archive(s,{'path':str(archive),'expectedSha256':review['archiveSha256']});new=s.dispatch('genome_list',{'projectId':copy['projectId']})[0];actual=s.dispatch('genome_region',{'projectId':copy['projectId'],'id':new['id'],'replicon':'chr','start':1,'end':4});self.assertEqual(actual['variantWindow']['total'],1)
   record=next(r for r in s.library({})['records'] if r['project_id']==copy['projectId'] and r['data'].get('domain')=='genome_variant_set');self.assertEqual(base64.b64decode(record['data']['originalFileBase64']),raw)
   changed=record['data'];changed['rows'][0]['alts']=['T']
   with s.db:s.db.execute('UPDATE records SET data=? WHERE id=?',(json.dumps(changed),record['id']))
   with self.assertRaisesRegex(ValueError,'parsed rows changed'):s.dispatch('genome_region',{'projectId':copy['projectId'],'id':new['id'],'replicon':'chr','start':1,'end':4})
   s.db.close()
