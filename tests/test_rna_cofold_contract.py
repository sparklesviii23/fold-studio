"""Contracts only. No ViennaRNA inference or biological qualification is claimed."""
import sys,pathlib,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'remote_worker'))
from fold_rapid.editcraft_core import validate_cofold,cofold_pairs,validate_plan,cofold_energy_state
class CofoldContracts(unittest.TestCase):
 def test_actual_captured_infinity_sentinel_is_not_a_physical_complex_energy(self):
  result=cofold_energy_state(100000.0,0,0,[])
  self.assertIsNone(result['complexMfeKcalMol']);self.assertIsNone(result['deltaMfeRelativeToSeparateFoldsKcalMol']);self.assertEqual(result['intermolecularMfeState'],'no_interstrand_mfe_returned');self.assertEqual(result['engineRawMfeReturnValue'],100000)
  paired=cofold_energy_state(-19,0,0,[{'sequenceAPosition':1,'sequenceBPosition':8}]);self.assertEqual(paired['complexMfeKcalMol'],-19)
 def test_strand_break_mapping(self):
  normalized,pairs,inter=cofold_pairs('((.&.))',3,3);self.assertEqual(normalized,'((..))');self.assertEqual(inter,[{'sequenceAPosition':2,'sequenceBPosition':2},{'sequenceAPosition':1,'sequenceBPosition':3}])
  for value in ('(()','[..]',')))((('):
   with self.assertRaises(ValueError):cofold_pairs(value,3,3)
 def test_explicit_bounded_inputs_and_plan_admission(self):
  p={'sequenceA':'acgu','sequenceB':'GCGC','temperatureC':37}
  self.assertEqual(validate_cofold(p),('ACGU','GCGC',37))
  for change in ({'sequenceA':''},{'sequenceB':'A'*251},{'sequenceB':'ACNT'},{'temperatureC':True},{'temperatureC':61}):
   with self.assertRaises(ValueError):validate_cofold({**p,**change})
  plan={'schemaVersion':1,'seconds':300,'stages':[{'id':'pair','operation':'rna_cofold','parameters':p}]};self.assertEqual(validate_plan(plan),plan)
 def test_single_strand_size_and_temperature_fail_before_paid_execution(self):
  def plan(op,params):return {'schemaVersion':1,'seconds':300,'stages':[{'id':'rna','operation':op,'parameters':params}]}
  for op,size in [('rna_fold',2000),('rna_ensemble',1000)]:
   valid=plan(op,{'sequence':'>one\nACGU\n','temperatureC':37});self.assertEqual(validate_plan(valid),valid)
   for params in ({'sequence':'A'*(size+1)},{'sequence':'ACGU','temperatureC':True},{'sequence':'>a\nACGU\n>b\nACGU'}):
    with self.assertRaises(ValueError):validate_plan(plan(op,params))
 def test_typed_upstream_sequence_handoffs_remain_valid(self):
  plan={'schemaVersion':1,'seconds':300,'stages':[{'id':'gene','operation':'gene_context','parameters':{'symbol':'Reference'}},{'id':'cds','operation':'sequence_analyze','inputFrom':'gene','parameters':{}},{'id':'rna','operation':'rna_ensemble','inputFrom':'cds','parameters':{'temperatureC':37}}]}
  self.assertEqual(validate_plan(plan),plan)
