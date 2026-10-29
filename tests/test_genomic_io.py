import pathlib,sys,tempfile,unittest,subprocess,json,hashlib
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
SAM='@HD\tVN:1.6\tSO:unsorted\n@SQ\tSN:chr\tLN:100\nr1\t0\tchr\t2\t60\t4M\t*\t0\t0\tACGT\tIIII\nr2\t256\tchr\t10\t255\t2M1I1M\t*\t0\t0\tAAAA\t!!!!\nr3\t4\t*\t0\t0\t*\t*\t0\t0\tNN\t!!\nr4\t2048\tchr\t20\t10\t1S3M\t*\t0\t0\tTACG\tIIII\n'
class GenomicIOTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.s=Service(self.root/'library');self.pid=self.s.project_create({'name':'Isolated indexed genomic QA'})['id'];dev=pathlib.Path('/tmp/fold-genomics-runtime/venv/bin/python3.12');bundled=pathlib.Path(__file__).resolve().parents[2]/'current/FOLD STUDIO Metal Dev.app/Contents/Resources/runtime-boltz/bin/python3.12';self.python=str(dev if dev.is_file() else bundled);self.s.setting_set({'key':'enginePython','value':self.python})
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def reference(self,path,circular=[]):return self.s.dispatch('indexed_genome_import',{'projectId':self.pid,'path':str(path),'metadata':{'organism':'Artificial sequence','assembly':'Numerical reference v1','source':'Explicit synthetic fixture'},'circularReplicons':circular})
 def region(self,r,**changes):return self.s.dispatch('indexed_genome_region',{'projectId':self.pid,'id':r['id'],'replicon':'chr','start':1,'end':4,'strand':'+',**changes})
 def test_exact_indexed_windows_circular_reverse_export_and_archive_restore(self):
  from project_archive import inspect_archive
  from project_restore import import_archive
  path=self.root/'r.fa';raw=b'>chr attributed numerical fixture\nACGTRYSW\nKMBDHVN\n>other\nAAAACCCC\n\n';path.write_bytes(raw);r=self.reference(path,['chr']);self.assertEqual(self.reference(path,['chr'])['id'],r['id']);self.assertEqual(self.region(r)['dna'],'ACGT');
  saved=self.s.dispatch('indexed_genome_region_save',{'projectId':self.pid,'id':r['id'],'replicon':'chr','start':1,'end':4,'strand':'+','expectedSequenceSha256':hashlib.sha256(b'ACGT').hexdigest()});self.assertEqual(saved['data']['result']['dna'],'ACGT')
  aligned=self.s.dispatch('sequence_align',{'projectId':self.pid,'target':'ACGT','query':'ACGT','alphabet':'DNA','mode':'global','queryOrientation':'forward','matchScore':2,'mismatchScore':-1,'gapOpenScore':-3,'gapExtendScore':-1,'targetReference':{'referenceId':r['id'],'replicon':'chr','start':1,'end':4,'strand':'+','storageKind':'indexed_fasta'}});self.assertEqual(aligned['data']['targetReference']['storageKind'],'indexed_fasta');self.assertEqual(self.region(r,start=14,end=3)['dna'],'VNACG');self.assertEqual(self.region(r,start=14,end=3,strand='-')['dna'],'CGTNB')
  output=self.root/'original.fasta';self.s.dispatch('indexed_genome_export',{'projectId':self.pid,'id':r['id'],'path':str(output)});self.assertEqual(output.read_bytes(),raw)
  archive=self.root/'indexed.zip';self.s.export_project({'id':self.pid,'path':str(archive)});review=inspect_archive({'path':str(archive)});restored=import_archive(self.s,{'path':str(archive),'expectedSha256':review['archiveSha256']});copy=self.s.dispatch('indexed_genomes',{'projectId':restored['projectId']})[0];value=self.s.dispatch('indexed_genome_region',{'projectId':restored['projectId'],'id':copy['id'],'replicon':'chr','start':1,'end':4,'strand':'+'});self.assertEqual(value['dna'],'ACGT');self.assertEqual(copy['data']['sourceFile']['sha256'],hashlib.sha256(raw).hexdigest())
 def test_reference_larger_than_previous_limit_is_streamed_and_tampering_rejected(self):
  path=self.root/'larger.fna';line=b'ACGT'*16384+b'\n'
  with path.open('wb') as out:
   out.write(b'>chr\n')
   for _ in range(520):out.write(line)
  self.assertGreater(path.stat().st_size,32*1024**2);r=self.reference(path);self.assertEqual(r['data']['replicons'][0]['length'],520*65536);self.assertEqual(self.region(r,start=520*65536-7,end=520*65536)['dna'],'ACGTACGT');asset=self.s.root/'assets'/r['data']['sourceFile']['asset']
  with asset.open('r+b') as stream:stream.seek(5);stream.write(b'T')
  with self.assertRaisesRegex(ValueError,'changed'):self.region(r)
 def test_invalid_fasta_rolls_back_and_index_tampering_is_detected(self):
  before=len(list((self.s.root/'assets').iterdir()));path=self.root/'bad.fa';path.write_text('>chr\nACGT\n>chr\nAAAA\n')
  with self.assertRaises(ValueError):self.reference(path)
  self.assertEqual(len(list((self.s.root/'assets').iterdir())),before);self.assertEqual(self.s.dispatch('indexed_genomes',{'projectId':self.pid}),[]);path.write_text('>chr\nACGTACGT\n');r=self.reference(path);(self.s.root/'assets'/r['data']['sourceFile']['indexAsset']).write_text('corrupt')
  with self.assertRaisesRegex(ValueError,'index checksum'):self.region(r)
 def test_active_local_job_blocks_genomic_import_without_open_transaction(self):
  path=self.root/'blocked.fa';path.write_text('>chr\nACGT\n');job=self.s.job_new({'projectId':self.pid,'name':'Synthetic active-job admission guard'},'setup','running')
  with self.assertRaisesRegex(ValueError,'active local'):self.reference(path)
  self.assertFalse(self.s.db.in_transaction);self.assertEqual(self.s.dispatch('indexed_genomes',{'projectId':self.pid}),[])
  self.s.job_update(job['id'],'cancelled')
 def test_actual_SAM_and_BAM_flags_MAPQ_and_original_archive(self):
  sam=self.root/'input.sam';bam=self.root/'input.bam';sam.write_text(SAM)
  code="import pysam,sys\nwith pysam.AlignmentFile(sys.argv[1],'r') as source,pysam.AlignmentFile(sys.argv[2],'wb',header=source.header) as out:\n for read in source:out.write(read)"
  subprocess.run([self.python,'-I','-c',code,str(sam),str(bam)],check=True)
  values=[]
  for path,fmt in ((sam,'sam'),(bam,'bam')):
   r=self.s.dispatch('genomic_alignment_import',{'projectId':self.pid,'path':str(path),'format':fmt});v=r['data']['result'];values.append(v);self.assertEqual(v['records'],4);self.assertEqual(v['flagCounts']['unmapped'],1);self.assertEqual(v['flagCounts']['secondary'],1);self.assertEqual(v['flagCounts']['supplementary'],1);self.assertEqual(v['mappedMAPQHistogram']['255'],1);self.assertEqual(v['mappedRecordCountsByHeaderReference']['chr'],3);self.assertEqual(v['CIGAROperationBaseTotals']['1'],1);self.assertEqual((self.s.root/'assets'/r['data']['sourceFile']['asset']).read_bytes(),path.read_bytes())
  self.assertEqual(values[0],values[1])
  with self.assertRaises(ValueError):self.s.dispatch('genomic_alignment_import',{'projectId':self.pid,'path':str(bam),'format':'cram'})
  self.s.dispatch('execution_backend_select',{'mode':'modal'})
  with self.assertRaisesRegex(ValueError,'Cloud Mode'):self.s.dispatch('genomic_alignment_import',{'projectId':self.pid,'path':str(sam),'format':'sam'})
