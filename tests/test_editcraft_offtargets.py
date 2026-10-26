"""Offline contract and independent coordinate checks, not upstream execution evidence."""
import copy,hashlib,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'remote_worker'),str(ROOT/'scientific')]
from fold_rapid import editcraft_offtargets as o,editcraft_toolchain as t
from fold_rapid.editcraft_core import validate_plan
from worker import Service

GUIDE='ACGTTGCAACGTTGCAACGT'
def parameters(fasta=None,topology='linear',mismatches=1):
 return {'nuclease':'SpCas9','pam':'NGG','mismatches':mismatches,'guides':[{'id':'guide_1','sequence':GUIDE}],'reference':{'kind':'inline','assembly':'synthetic-v1','topology':topology,'fasta':fasta or '>chr1\n'+GUIDE+'AGG\n'}}

def independent_matches(p):
 """Deliberately simple exhaustive oracle used only on tiny synthetic references."""
 rows=[];width=20+len(p['pam']);codes={'N':'ACGT','G':'G','A':'A','T':'T','C':'C'}
 for name,source in o.fasta_records(p['reference']['fasta']).items():
  for start in range(len(source)):
   window=''.join(source[(start+i)%len(source)] for i in range(width)) if p['reference']['topology']=='circular' else source[start:start+width]
   if len(window)!=width:continue
   for strand,seq in [('+',window),('-',window.translate(str.maketrans('ACGT','TGCA'))[::-1])]:
    if any(base not in codes[c] for base,c in zip(seq[20:],p['pam'])):continue
    for g in p['guides']:
     mm=sum(a!=b for a,b in zip(seq[:20],g['sequence']))
     if mm<=p['mismatches']:rows.append((g['id'],name,start,strand,mm,seq))
 return sorted(rows)

class ContractTests(unittest.TestCase):
 def test_input_is_explicit_and_bounded(self):
  self.assertEqual(o.validate_input(parameters()),parameters())
  for key,value in [('nuclease','Cas12a'),('pam','NNN'),('mismatches',True),('mismatches',7),('reference',None)]:
   p=parameters();p[key]=value
   with self.subTest(key=key,value=value),self.assertRaises(ValueError):o.validate_input(p)
  for sequence in ['A'*19,'U'*20,'N'*20]:
   p=parameters();p['guides'][0]['sequence']=sequence
   with self.assertRaises(ValueError):o.validate_input(p)
 def test_duplicate_ids_and_sequences_rejected(self):
  for row in [{'id':'guide_1','sequence':'T'*20},{'id':'different','sequence':GUIDE}]:
   p=parameters();p['guides'].append(row)
   with self.assertRaises(ValueError):o.validate_input(p)
 def test_fasta_headers_are_not_paths_and_contigs_do_not_merge(self):
  self.assertEqual(o.fasta_records('>a description\nACGT\n>b\nTTAA\n'),{'a':'ACGT','b':'TTAA'})
  for text in ['ACGT','>a\nA\n>a\nT','>../escape\nAT','>a\nAU','>a\n']:
   with self.assertRaises(ValueError):o.fasta_records(text)
 def test_input_uses_spacer_pam_wildcards_and_cpu_contract(self):
  text=o.input_text('/reference/search.fa',parameters())
  self.assertEqual(text,'/reference/search.fa\n'+'N'*20+'NGG\n'+GUIDE+'NNN 1 guide_1\n')
 def test_plan_refuses_invalid_search_before_upload(self):
  plan={'schemaVersion':1,'seconds':60,'stages':[{'id':'s','operation':'cas_offinder','parameters':parameters()}]}
  self.assertEqual(validate_plan(plan),plan);plan['stages'][0]['parameters']['guides'][0]['sequence']='RNA'
  with self.assertRaises(ValueError):validate_plan(plan)
 def test_cloud_only_execution_never_falls_back_to_local_scanner(self):
  with patch.dict('os.environ',{},clear=True),self.assertRaisesRegex(RuntimeError,'cloud-only'):o.execute(parameters())

class CoordinateTests(unittest.TestCase):
 def test_both_strands_mismatch_positions_and_original_tsv(self):
  forward=GUIDE+'AGG';variant='T'+GUIDE[1:]+'TGG';reverse=o.reverse_complement(variant)
  p=parameters('>plus\n'+forward+'\n>minus\n'+reverse+'\n');records=o.fasta_records(p['reference']['fasta'])
  lines=[GUIDE+'NNN\tplus\t0\t'+forward+'\t+\t0\tguide_1',GUIDE+'NNN\tminus\t0\tt'+variant[1:]+'\t-\t1\tguide_1']
  rows=o.parse_output('\n'.join(lines),p,records)
  got=sorted((r['guideId'],r['contig'],r['upstreamStart0'],r['strand'],r['mismatches'],r['sequence5to3']) for r in rows)
  self.assertEqual(got,independent_matches(p));self.assertEqual(rows[1]['mismatchPositions'],[1]);self.assertEqual(rows[1]['start'],1);self.assertEqual(rows[1]['end'],23)
 def test_circular_origin_crossing_is_mapped_to_original_contig(self):
  site=GUIDE+'AGG';source=site[11:]+site[:11];p=parameters('>circle\n'+source+'\n',topology='circular',mismatches=0)
  rows=o.parse_output(GUIDE+'NNN\tcircle\t12\t'+site+'\t+\t0\tguide_1',p,{'circle':source})
  self.assertEqual(rows[0]['intervals'],[{'start':13,'end':23},{'start':1,'end':12}]);self.assertTrue(rows[0]['wrapsOrigin'])
  self.assertIn(('guide_1','circle',12,'+',0,site),independent_matches(p))
 def test_bad_coordinates_pam_mismatch_counts_and_duplicates_are_rejected(self):
  p=parameters();source={'chr1':GUIDE+'AGG'};line=GUIDE+'NNN\tchr1\t0\t'+GUIDE+'AGG\t+\t0\tguide_1'
  for invalid in [line.replace('\t0\t'+GUIDE,'\t1\t'+GUIDE),line.replace('\t+\t0','\t+\t1'),line.replace(GUIDE+'AGG',GUIDE+'AAA'),line+'\n'+line]:
   with self.assertRaises(ValueError):o.parse_output(invalid,p,source)
 def test_zero_is_not_invented_from_invalid_output(self):
  self.assertEqual(o.parse_output('',parameters(),{'chr1':GUIDE+'AGG'}),[])
  with self.assertRaises(ValueError):o.parse_output('error: device unavailable',parameters(),{'chr1':GUIDE+'AGG'})
 def test_ambiguous_reference_site_is_not_a_definite_match(self):
  p=parameters();seq='N'+GUIDE[1:]+'AGG';line=GUIDE+'NNN\tchr1\t0\t'+seq+'\t+\t1\tguide_1'
  with self.assertRaisesRegex(ValueError,'ambiguous'):o.parse_output(line,p,{'chr1':seq})
 def test_output_limit_cannot_silently_be_a_partial_enumeration(self):
  p=parameters('>chr1\n'+(GUIDE+'AGG')*2+'\n');site=GUIDE+'AGG'
  text='\n'.join(GUIDE+'NNN\tchr1\t'+str(start)+'\t'+site+'\t+\t0\tguide_1' for start in [0,23])
  with patch.object(o,'MAX_HITS',1),self.assertRaisesRegex(ValueError,'Partial output'):o.parse_output(text,p,o.fasta_records(p['reference']['fasta']))

class ReferenceTests(unittest.TestCase):
 def test_published_contig_manifest_and_fasta_hash_required(self):
  p=parameters();p['reference']={'kind':'catalog','id':'ecoli-k12-ASM584v2','fastaSha256':'a'*64};o.validate_input(p)
  p['reference']['id']='human'
  with self.assertRaises(ValueError):o.validate_input(p)
 def test_reference_window_requires_exact_strand_coordinates(self):
  p={'reference':{'id':'ecoli-k12-ASM584v2','fastaSha256':'a'*64},'contig':'NC_000913.3','start':1,'end':50,'strand':-1};o.validate_window(p)
  for change in [{'start':0},{'end':10001},{'strand':True},{'contig':'chr1'}]:
   with self.assertRaises(ValueError):o.validate_window({**p,**change})
 def test_modified_reference_bytes_are_detected(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=pathlib.Path(temporary);folder=root/'ecoli-k12-ASM584v2';folder.mkdir();file=folder/'reference.fa';file.write_text('>NC_000913.3\nACGT\n')
   spec=t.MANIFEST['references']['ecoli-k12-ASM584v2'];receipt={'id':'ecoli-k12-ASM584v2','manifestSha256':t.manifest_sha(),'assembly':spec['assembly'],'coverage':spec['coverage'],'topology':spec['topology'],'contigs':{k:{'length':v} for k,v in spec['contigs'].items()},'fastaSha256':t.file_sha(file)};(folder/'receipt.json').write_text(json.dumps(receipt))
   with patch.object(t,'REFERENCE_ROOT',root),patch.dict('os.environ',{'FOLD_ENGINE_ROLE':'editcraft_cloud'}):
    self.assertEqual(t.verify_reference('ecoli-k12-ASM584v2',receipt['fastaSha256'])[0],file)
    file.write_text('changed')
    with self.assertRaisesRegex(ValueError,'checksum'):t.verify_reference('ecoli-k12-ASM584v2')
 def test_tool_manifest_does_not_invalidate_prepared_trained_models(self):
  from fold_rapid.editcraft_models import manifest_sha
  before=manifest_sha();self.assertNotEqual(before,t.manifest_sha());self.assertEqual(before,manifest_sha())

class NativeTests(unittest.TestCase):
 def test_review_is_offline_and_does_not_claim_runtime_qualification(self):
  with tempfile.TemporaryDirectory() as temporary:
   service=Service(pathlib.Path(temporary));project=service.project_create({'name':'Off-target synthetic fixture'})['id']
   try:
    plan={'schemaVersion':1,'seconds':60,'stages':[{'id':'s','operation':'cas_offinder','parameters':parameters()}]}
    with patch('editcraft.provider',side_effect=AssertionError('Review must not upload')):
     row=service.dispatch('editcraft_prepare',{'projectId':project,'plan':plan,'allowanceUSD':.5})
    self.assertEqual(row['state'],'prepared');self.assertFalse(row['gpuStarted'])
    model=next(m for m in service.dispatch('editcraft_state',{'projectId':project})['models'] if m['id']=='cas-offinder')
    self.assertTrue(model['adapterImplemented']);self.assertFalse(model['cloudExecutionValidated']);self.assertFalse(model['scientificallyBenchmarked'])
   finally:service.db.close()
