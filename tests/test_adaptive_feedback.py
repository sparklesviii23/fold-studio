"""Measured-rule/seeded-feedback contracts; synthetic evidence, no model claims."""
import pathlib,sys,unittest,copy
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'remote_worker'),str(ROOT/'scientific'),str(ROOT/'tests')]
from fold_rapid.feedback import choose,validate
from fold_rapid.unified import model_manifest
from fold_rapid.unified_contract import campaign,estimate
from test_unified_campaign import fixture
RULES={'rules':[{'metric':'liabilityCount','comparison':'above','threshold':0,'operation':'solublempnn'},{'metric':'interfaceArea','comparison':'below','threshold':600,'operation':'bindcraft2'}],'defaultOperations':['proteinmpnn']}
class FeedbackTests(unittest.TestCase):
 def test_observed_quality_changes_next_operation(self):
  self.assertEqual(choose(RULES,{'eligible':True,'metrics':{'liabilityCount':0,'interfaceArea':800}})['operations'],['proteinmpnn'])
  r=choose(RULES,{'eligible':True,'metrics':{'liabilityCount':2,'interfaceArea':500}});self.assertEqual(r['operations'],['solublempnn','bindcraft2']);self.assertEqual(r['matchedRules'][0]['observed'],2)
 def test_feedback_never_weakens_qualification_or_missing_measurements(self):
  self.assertFalse(choose(RULES,{'eligible':False,'metrics':{'liabilityCount':3,'interfaceArea':500}})['operations'])
  self.assertFalse(choose(RULES,{'eligible':True,'metrics':{}})['operations'])
 def test_no_unavailable_or_invented_metric(self):
  r=copy.deepcopy(RULES);r['rules'][0]['metric']='bindingProbability'
  with self.assertRaises(ValueError):validate(r)
 def test_gradient_feedback_uses_explicit_seed_and_fixed_residues(self):
  v=fixture();v['stageBudgets']['bindcraft2']={'seconds':120,'hourlyEstimateUSD':1}
  n={'candidateId':'fixture','binderChains':['B'],'targetChains':['A'],'sequences':{'A':'ACDE','B':'ACDE'},'coordinates':v['target']}
  m=model_manifest({'manifest':v},n,'bindcraft2');self.assertEqual(m['biology']['sequences'],{'B':'ACDE'});self.assertEqual(m['biology']['constraints']['B']['mutable'],[3,4]);self.assertTrue(m['settings']['save_design_trajectory']);self.assertEqual(m['design']['attempts'],1)
 def test_feedback_engines_must_be_budgeted(self):
  v=fixture();v['workflow']['feedback']=RULES
  with self.assertRaises(ValueError):campaign(v)
  v['stageBudgets']['bindcraft2']={'seconds':10,'hourlyEstimateUSD':1};v['policy']['rounds']=2;campaign(v);q=estimate(v);self.assertGreater(next(r['maximumCalls'] for r in q['stages'] if r['engine']=='af2_multimer'),6)
if __name__=='__main__':unittest.main()
