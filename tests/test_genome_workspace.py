import pathlib,sys,tempfile,unittest,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
from genome_workspace import fasta,annotations,region,reverse_complement
class GenomeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.s=Service(self.root/'data');self.project=self.s.project_create({'name':'Artificial genome coordinate reference'})['id'];self.fa=self.root/'ref.fna';self.fa.write_text('>chrom\nACGTTGCA\n>plasmid\nTTAC\n');self.gff=self.root/'ref.gff3';self.gff.write_text('##gff-version 3\nchrom\tfixture\tgene\t2\t5\t.\t-\t.\tID=g1;Name=reverse%20gene\nchrom\tfixture\tgene\t7\t10\t.\t+\t.\tID=origin\n')
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def import_(self):return self.s.dispatch('genome_import',{'projectId':self.project,'fastaPath':str(self.fa),'gffPath':str(self.gff),'metadata':{'organism':'Artificial coordinate fixture; not a biological reference','assembly':'synthetic v1','source':'Numerical test only'},'circularReplicons':['chrom']})
 def test_strands_and_circular_origin(self):
  self.assertEqual(region('ACGTTGCA',7,2,'+',True),'CAAC');self.assertEqual(region('ACGTTGCA',7,10,'-',True),reverse_complement('CAAC'))
  with self.assertRaises(ValueError):region('ACGT',4,2,'+',False)
  with self.assertRaises(ValueError):region('ACGT',1,9,'+',True)
 def test_persistent_reference_features_and_exact_sequences(self):
  row=self.import_();p={'projectId':self.project,'id':row['id']}
  self.assertEqual(row['replicons'][0]['length'],8);self.assertEqual(row['featureCount'],2)
  features=self.s.dispatch('genome_features',{**p,'query':'reverse gene'});self.assertEqual(features['total'],1)
  result=self.s.dispatch('genome_region',{**p,'featureIndex':0});self.assertEqual(result['dna'],'AACG');self.assertEqual(result['rnaAlphabet'],'AACG');self.assertEqual(result['feature']['strand'],'-')
  self.assertEqual(self.s.dispatch('genome_region',{**p,'featureIndex':1})['dna'],'CAAC')
  self.s.db.close();self.s=Service(self.root/'data');self.assertEqual(self.s.dispatch('genome_list',{'projectId':self.project})[0]['sources'],row['sources'])
 def test_scope_integrity_and_bad_annotations(self):
  row=self.import_();other=self.s.project_create({'name':'Other'})['id']
  with self.assertRaises(ValueError):self.s.dispatch('genome_region',{'projectId':other,'id':row['id'],'replicon':'chrom','start':1,'end':2})
  asset=self.s.root/'genome-assets'/row['sources'][0]['asset'];asset.write_text('>chrom\nAAAA\n')
  with self.assertRaisesRegex(ValueError,'checksum'):self.s.dispatch('genome_features',{'projectId':self.project,'id':row['id']})
  self.gff.write_text('missing\tx\tgene\t1\t2\t.\t+\t.\tID=x\n')
  before=len(self.s.library({})['records'])
  with self.assertRaises(ValueError):self.import_()
  self.assertEqual(len(self.s.library({})['records']),before)
 def test_exact_search_both_strands_and_origin(self):
  row=self.import_();result=self.s.dispatch('genome_search',{'projectId':self.project,'id':row['id'],'sequence':'CAAC','replicon':'chrom'});self.assertIn({'replicon':'chrom','start':7,'end':10,'strand':'+'},result['hits'])
  with self.assertRaises(ValueError):self.s.dispatch('genome_search',{'projectId':self.project,'id':row['id'],'sequence':'N'})
 def test_fasta_validation(self):
  for text in ('ACGT','>a\nACGT\n>a\nAAAA','>a\nACGU','>a\n'):
   with self.assertRaises(ValueError):fasta(text)
 def test_region_save_and_genome_archive_preserve_sources(self):
  import zipfile,hashlib
  from project_archive import inspect_archive
  row=self.import_();p={'projectId':self.project,'id':row['id'],'replicon':'chrom','start':2,'end':5,'strand':'-'}
  result=self.s.dispatch('genome_region',p)
  with self.assertRaises(ValueError):self.s.dispatch('genome_region_save',{**p,'expectedSequenceSha256':'bad'})
  saved=self.s.dispatch('genome_region_save',{**p,'expectedSequenceSha256':result['sequenceSha256']})
  self.assertEqual(saved['data']['result']['dna'],result['dna'])
  archive=self.root/'genome.zip';self.s.export_project({'id':self.project,'path':str(archive)})
  self.assertEqual(inspect_archive({'path':str(archive)})['verifiedGenomeSourceCount'],2)
  with zipfile.ZipFile(archive) as z:
   data=json.loads(z.read('project.json'))
   for source in data['genomeReferences'][0]['sources']:self.assertEqual(hashlib.sha256(z.read(source['file'])).hexdigest(),source['sha256'])
if __name__=='__main__':unittest.main()
