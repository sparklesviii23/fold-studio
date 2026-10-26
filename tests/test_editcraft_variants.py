"""VEP API identity/assembly contracts; fixtures are not real inference evidence."""
import pathlib,sys,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'remote_worker'))
from fold_rapid import editcraft_variants as v
from fold_rapid.editcraft_core import validate_plan
def params():return {'assembly':'GRCh37','chromosome':'21','position':26960070,'ref':'G','alt':'A'}
class VEPTests(unittest.TestCase):
 def responses(self):return [({'assembly_name':'GRCh37.p13'},{}),({'releases':[75]},{}),({'seq':'G','id':'reference'},{}),([{'assembly_name':'GRCh37','seq_region_name':'21','start':26960070,'end':26960070,'strand':1,'allele_string':'G/A','transcript_consequences':[{'transcript_id':'ENST-fixture.3','strand':-1,'consequence_terms':['missense_variant'],'impact':'MODERATE'}]}],{})]
 def test_distinct_reference_hosts_and_unmodified_transcript_results(self):
  with patch.object(v,'request',side_effect=self.responses()) as request:
   result=v.annotate(params());self.assertTrue(result['referenceAlleleVerified']);self.assertEqual(result['transcriptConsequences'][0]['strand'],-1);self.assertEqual(result['transcriptConsequences'][0]['transcript_id'],'ENST-fixture.3')
   self.assertEqual(request.call_args_list[0].args[0],'https://grch37.rest.ensembl.org');self.assertEqual(request.call_args_list[-1].args[2],{'variants':['21 26960070 fold_variant G A . . .']})
 def test_reference_allele_failure_never_submits_variant(self):
  responses=self.responses();responses[2]=({'seq':'A'}, {})
  with patch.object(v,'request',side_effect=responses) as request,self.assertRaisesRegex(ValueError,'Reference allele'):v.annotate(params())
  self.assertEqual(request.call_count,3)
 def test_wrong_host_assembly_is_not_silently_lifted(self):
  with patch.object(v,'request',return_value=({'assembly_name':'GRCh38.p14'},{})) as request,self.assertRaisesRegex(ValueError,'no longer serves'):v.annotate(params())
  self.assertEqual(request.call_count,1)
 def test_returned_variant_must_match_exact_forward_coordinates(self):
  for change in [{'assembly_name':'GRCh38'},{'strand':-1},{'start':26960071},{'allele_string':'A/G'},{'seq_region_name':'22'}]:
   responses=self.responses();responses[-1][0][0].update(change)
   with patch.object(v,'request',side_effect=responses),self.assertRaisesRegex(ValueError,'identity'):v.annotate(params())
 def test_strict_snv_contract_is_checked_at_review(self):
  for change in [{'position':True},{'assembly':'unknown'},{'ref':'GG'},{'alt':'G'},{'chromosome':'chr21'},{'chromosome':'21/../../'}]:
   plan={'schemaVersion':1,'seconds':60,'stages':[{'id':'v','operation':'variant_vep','parameters':{**params(),**change}}]}
   with self.assertRaises(ValueError):validate_plan(plan)
 def test_unreviewed_hosts_cannot_receive_input(self):
  with self.assertRaisesRegex(ValueError,'official'):v.request('https://other.invalid','/anything',params())
