import pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
class VariantTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.s=Service(self.root/'library');self.project=self.s.project_create({'name':'Artificial allele tests'})['id'];runtime=pathlib.Path(__file__).resolve().parents[2]/'current/FOLD STUDIO Metal Dev.app/Contents/Resources/runtime-boltz/bin/python3.12';self.runtime=runtime
  self.s.setting_set({'key':'enginePython','value':str(runtime)})
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def reference(self,strand='+'):
  fasta=self.root/'r.fna';fasta.write_text('>chr\n'+('ATGAAATAA' if strand=='+' else 'TTATTTCAT')+'\n');gff=self.root/'r.gff3';gff.write_text('chr\tfixture\tCDS\t1\t9\t.\t'+strand+'\t0\tID=cds1\n');return self.s.dispatch('genome_import',{'projectId':self.project,'fastaPath':str(fasta),'gffPath':str(gff),'metadata':{'organism':'Artificial','assembly':'Synthetic','source':'Numerical QA'}})
 def request(self,row,**change):return {'projectId':self.project,'id':row['id'],'replicon':'chr','position':4,'ref':'A','alt':'G','flank':2,**change}
 def test_forward_reference_and_persistence_without_coding_inference(self):
  row=self.reference();p=self.request(row);result=self.s.dispatch('genome_variant',p);self.assertIsNone(result['codingConsequence']);self.assertEqual(result['referenceContext'],'TGAAA');self.assertEqual(result['alternateContext'],'TGGAA')
  saved=self.s.dispatch('genome_variant_save',{**p,'expectedInputSha256':result['inputSha256']});self.assertEqual(saved['data']['result'],result)
  for change in ({'ref':'T'},{'position':0},{'ref':'N'},{'alt':'A'},{'position':9,'ref':'AA'}):
   with self.assertRaises(ValueError):self.s.dispatch('genome_variant',self.request(row,**change))
 def test_coding_changes_and_initiation_uncertainty(self):
  if not self.runtime.is_file():self.skipTest('Existing Biopython runtime absent')
  row=self.reference();p=self.request(row,cdsFeatureIndex=0,translationTable=11)
  for changes,effect in [({},'amino_acid_change'),({'position':6,'alt':'G'},'synonymous_codon_change'),({'alt':'T'},'stop_gained'),({'position':3,'ref':'G','alt':'A'},'start_region_variant'),({'alt':'AG'},'frameshift')]:
   result=self.s.dispatch('genome_variant',{**p,**changes});self.assertEqual(result['codingConsequence']['effect'],effect)
 def test_negative_strand_allele_is_oriented_before_translation(self):
  if not self.runtime.is_file():self.skipTest('Existing Biopython runtime absent')
  row=self.reference('-');result=self.s.dispatch('genome_variant',self.request(row,position=6,ref='T',alt='C',cdsFeatureIndex=0,translationTable=11));consequence=result['codingConsequence'];self.assertEqual(consequence['referenceCDS'],'ATGAAATAA');self.assertEqual(consequence['alternateCDS'],'ATGGAATAA');self.assertEqual(consequence['alternateTranslation']['protein'],'ME*')
