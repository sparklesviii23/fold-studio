import pathlib,sys,unittest,tempfile,os
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from genome_products import assemble,translate
from genome_workspace import annotations,reverse_complement
from worker import Service
def part(start,end,phase,strand='+',kind='CDS',identifier='c1',parents=None):return {'index':0,'replicon':'chr','start':start,'end':end,'strand':strand,'phase':phase,'type':kind,'attributes':{'ID':identifier},'parents':parents or []}
class ProductTests(unittest.TestCase):
 def test_junction_phase_bases_are_retained(self):
  result=assemble({'chr':'ATGACCCCAATAA'},[part(1,4,'0'),part(9,13,'2')],[],0,'cds')
  self.assertEqual(result['dna'],'ATGAAATAA');self.assertEqual(result['trailingIncompleteCodonBases'],0)
 def test_reverse_strand_segments_are_assembled_in_biological_order(self):
  result=assemble({'chr':reverse_complement('ATGACCCCAATAA')},[part(10,13,'0','-'),part(1,5,'2','-')],[],0,'cds')
  self.assertEqual(result['dna'],'ATGAAATAA')
 def test_partial_initial_phase_is_applied_only_once(self):
  result=assemble({'chr':'AATGCCCTAA'},[part(1,4,'1'),part(8,10,'0')],[],0,'cds');self.assertEqual(result['dna'],'ATGTAA');self.assertEqual(result['initialPhaseBasesSkipped'],1)
 def test_bad_phase_overlap_and_ambiguous_circular_order_are_rejected(self):
  for parts,circular in [([part(1,4,'0'),part(9,13,'1')],[]),([part(1,4,'0'),part(4,9,'2')],[]),([part(1,4,'0'),part(9,13,'2')],['chr'])]:
   with self.subTest(parts=parts),self.assertRaises(ValueError):assemble({'chr':'ATGACCCCAATAA'},parts,circular,0,'cds')
 def test_transcript_requires_explicit_exon_relationships(self):
  features=[part(1,13,'.',kind='mRNA',identifier='t1'),part(1,4,'.',kind='exon',identifier='e1',parents=['t1']),part(9,13,'.',kind='exon',identifier='e2',parents=['t1'])]
  self.assertEqual(assemble({'chr':'ATGACCCCAATAA'},features,[],0,'transcript')['rna'],'AUGAAAUAA')
  with self.assertRaises(ValueError):assemble({'chr':'ATGACCCCAATAA'},features[:1],[],0,'transcript')
 def test_parent_lists_preserve_escaped_commas(self):
  result=annotations('chr\tsrc\texon\t1\t3\t.\t+\t.\tID=e1;Parent=rna%2Ca,other',{'chr':'ATG'},[])
  self.assertEqual(result[0]['parents'],['rna,a','other'])
 def test_actual_biopython_translation_and_exceptions(self):
  runtime=pathlib.Path(__file__).resolve().parents[2]/'current/FOLD STUDIO Metal Dev.app/Contents/Resources/runtime-boltz/bin/python3.12'
  if not runtime.is_file():self.skipTest('Existing packaged Biopython runtime unavailable')
  with tempfile.TemporaryDirectory() as tmp:
   s=Service(tmp);s.setting_set({'key':'enginePython','value':str(runtime)})
   product=assemble({'chr':'GTGAAATAA'},[part(1,9,'0')],[],0,'cds')
   self.assertEqual(translate(s,product,11,True)['protein'],'MK');self.assertEqual(translate(s,product,11,False)['protein'],'VK*')
   product['exceptionalAnnotation']=True
   with self.assertRaises(ValueError):translate(s,product,11,True)
   s.db.close()
