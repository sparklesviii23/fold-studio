"""Independent exact combinatorial/null examples; no biological dataset or model."""
import copy
import itertools
import math
import os
import pathlib
import sys
import unittest
from fractions import Fraction
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'remote_worker'))
from fold_rapid import editcraft_pathways as p
from fold_rapid.editcraft_core import validate_plan,resources

def fixture():
 return {'genes':['g1','g2','g3'],'background':['g'+str(i) for i in range(1,11)],'geneSets':[{'id':'selected','genes':['g1','g2','g3']},{'id':'no_overlap','genes':['g8','g9']},{'id':'outside','genes':['other']}],'collection':{'name':'Synthetic combinatorial fixture','version':'1','source':'Hand-enumerated finite null population, not biological evidence','organism':'Synthetic identifiers','identifierNamespace':'synthetic','license':'Original test fixture'},'multipleTesting':'BH','alpha':.05}

class PathwayTests(unittest.TestCase):
 def test_hypergeometric_tails_agree_with_independent_finite_population_enumeration(self):
  for population in range(2,10):
   for members in range(population+1):
    for draws in range(population+1):
     observed=[sum(i<members for i in sample) for sample in itertools.combinations(range(population),draws)]
     for overlap in range(min(members,draws)+2):
      expected=Fraction(sum(k>=overlap for k in observed),len(observed));actual=p.log_upper_tail(population,members,draws,overlap)
      self.assertAlmostEqual(math.exp(actual),float(expected),places=12)
 def test_adjustment_preserves_order_and_test_family_with_non_significant_sets(self):
  values=[.01,.04,.03,.8];logs=list(map(math.log,values));bh=list(map(math.exp,p.adjusted_logs(logs,'BH')))
  for a,b in zip(bh,[.04,.0533333333333333,.0533333333333333,.8]):self.assertAlmostEqual(a,b,places=14)
  by=list(map(math.exp,p.adjusted_logs(logs,'BY')))
  for a,b in zip(by,[min(1,q*sum(1/i for i in range(1,5))) for q in bh]):self.assertAlmostEqual(a,b,places=14)
 def test_extreme_significance_is_not_silently_rounded_to_exact_zero(self):
  value=p.log_upper_tail(50000,5000,5000,5000);self.assertTrue(math.isfinite(value));self.assertLess(value,-1000);self.assertTrue(math.isfinite(p.adjusted_logs([value,0],'BY')[0]))
 def test_supplied_background_and_exact_gene_membership_determine_the_result(self):
  result=p.calculate(fixture());row=next(r for r in result['rows'] if r['id']=='selected');self.assertAlmostEqual(row['pValue'],1/120);self.assertAlmostEqual(row['adjustedPValue'],3/120);self.assertEqual(row['overlapGenes'],['g1','g2','g3']);self.assertEqual(result['testedFamilySize'],3)
  absent=next(r for r in result['rows'] if r['id']=='outside');self.assertEqual(absent['pValue'],1);self.assertEqual(absent['outsideBackground'],['other']);self.assertTrue(absent['noTestableMembers']);self.assertIsNone(absent['foldEnrichment'])
 def test_implicit_background_duplicates_namespace_guessing_and_invalid_thresholds_are_rejected(self):
  for change in [{'background':[]},{'genes':['G1']},{'genes':['g1','g1']},{'alpha':True},{'alpha':float('nan')},{'multipleTesting':'uncorrected'},{'collection':{}}]:
   with self.subTest(change=change),self.assertRaises(ValueError):p.validate_input({**fixture(),**change})
  value=fixture();value['geneSets'][1]['id']='selected'
  with self.assertRaises(ValueError):p.validate_input(value)
 def test_review_validates_without_cloud_execution_or_automatic_scientific_fallback(self):
  value={'schemaVersion':1,'seconds':60,'stages':[{'id':'sets','operation':'pathway_enrichment','parameters':fixture()}]}
  self.assertEqual(resources(validate_plan(value)),{'cpu':2,'memoryGiB':4,'gpu':False})
  with patch.dict(os.environ,{},clear=True),self.assertRaisesRegex(RuntimeError,'cloud-only'):p.execute(fixture())
