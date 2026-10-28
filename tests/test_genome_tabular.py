import pathlib,sys,tempfile,unittest,hashlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
from genome_tabular import normalize
from genome_workspace import annotations
from genome_products import assemble
class TabularTests(unittest.TestCase):
 def test_gtf_explicit_transcript_and_cds_junctions(self):
  text='\n'.join('chr\tfixture\t'+kind+'\t'+str(start)+'\t'+str(end)+'\t.\t+\t'+phase+'\tgene_id "g1"; transcript_id "t1"; gene_name "Gene; quoted"; tag "a"; tag "b";' for kind,start,end,phase in [('transcript',1,13,'.'),('exon',1,4,'.'),('exon',9,13,'.'),('CDS',1,4,'0'),('CDS',9,13,'2')])
  converted,receipt=normalize(text,'gtf');fs=annotations(converted,{'chr':'ATGACCCCAATAA'},[])
  self.assertEqual(assemble({'chr':'ATGACCCCAATAA'},fs,[],0,'transcript')['dna'],'ATGAAATAA');self.assertEqual(assemble({'chr':'ATGACCCCAATAA'},fs,[],3,'cds')['dna'],'ATGAAATAA');self.assertEqual(fs[0]['attributes']['tag'],'a | b');self.assertEqual(receipt['rows'],5)
 def test_gtf_does_not_invent_absent_parent_or_append_stop_codon(self):
  text='chr\tfixture\tCDS\t1\t6\t.\t+\t0\tgene_id "g"; transcript_id "t";\nchr\tfixture\tstop_codon\t7\t9\t.\t+\t0\tgene_id "g"; transcript_id "t";'
  converted,_=normalize(text,'gtf');fs=annotations(converted,{'chr':'ATGAAATAA'},[]);self.assertEqual(len(fs),2);self.assertEqual(assemble({'chr':'ATGAAATAA'},fs,[],0,'cds')['dna'],'ATGAAA')
  for attrs in ('gene_id "g";', 'gene_id "g"; transcript_id "a"; transcript_id "b";', 'gene_id=g; transcript_id=t;'):
   with self.assertRaises(ValueError):normalize('chr\tx\tCDS\t1\t6\t.\t+\t0\t'+attrs,'gtf')
 def test_bed_coordinates_and_unsupported_semantics(self):
  converted,_=normalize('chr\t0\t4\tfirst\t50\t-\n','bed');fs=annotations(converted,{'chr':'ATGC'},[]);self.assertEqual((fs[0]['start'],fs[0]['end'],fs[0]['strand'],fs[0]['type']),(1,4,'-','region'))
  for text in ('chr\t0\t0','chr\t0\t4\tx\t1001\t+','chr\t0\t4\tx\t0\t+\t0','chr\t0\t4\nchr\t0\t2\tx'):
   with self.assertRaises(ValueError):normalize(text,'bed')
 def test_original_compressed_gtf_roundtrip_remains_operational(self):
  import gzip
  from project_archive import inspect_archive
  from project_restore import import_archive
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);s=Service(root/'library');pid=s.project_create({'name':'Isolated GTF archive fixture'})['id'];fa=root/'ref.fna';fa.write_text('>chr\nATGAAATAA\n');gtf=root/'ref.gtf.gz';raw=gzip.compress(b'chr\tfixture\tCDS\t1\t9\t.\t+\t0\tgene_id "g"; transcript_id "t";\n');gtf.write_bytes(raw)
   row=s.dispatch('genome_import',{'projectId':pid,'fastaPath':str(fa),'gffPath':str(gtf),'annotationFormat':'gtf','metadata':{'organism':'Artificial','assembly':'Numerical fixture','source':'Synthetic QA'}})
   self.assertEqual(len(row['sources']),3);original=next(item for item in row['sources'] if item['kind']=='gtf');self.assertEqual(original['sha256'],hashlib.sha256(raw).hexdigest())
   archive=root/'project.zip';s.export_project({'id':pid,'path':str(archive)});review=inspect_archive({'path':str(archive)});self.assertEqual(review['verifiedGenomeSourceCount'],3);copy=import_archive(s,{'path':str(archive),'expectedSha256':review['archiveSha256']});ref=s.dispatch('genome_list',{'projectId':copy['projectId']})[0]
   product=s.dispatch('genome_product',{'projectId':copy['projectId'],'id':ref['id'],'featureIndex':0,'kind':'cds'});self.assertEqual(product['dna'],'ATGAAATAA');asset=next(item for item in ref['sources'] if item['kind']=='gtf')['asset'];self.assertEqual((s.root/'genome-assets'/asset).read_bytes(),raw);s.db.close()
