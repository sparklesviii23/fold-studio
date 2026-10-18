"""Reject ambiguous or contradictory constraint maps before any model is loaded."""
import unittest
from test_project_metal import w
from mpnn_constraints import prepare


class ConstraintContracts(unittest.TestCase):
 def setUp(self):
  self.structure={'chains':[{'id':'A'},{'id':'B'}],'residues':[{'id':f'{c}{i}','chain':c,'num':i,'one':aa} for c in ('A','B') for i,aa in enumerate('ACD',1)]}
 def test_default_whole_chain_and_explicit_fixed_context(self):
  result=prepare(self.structure,['A'],{})
  self.assertTrue(all(r['design'] for r in result['residues']['A']));self.assertFalse(any(r['design'] for r in result['residues']['B']))
 def test_subset_is_exact_source_identity(self):
  result=prepare(self.structure,['A','B'],{'designResidues':['A2','B2'],'tiedChains':[['A','B']]})
  self.assertEqual([r['design'] for r in result['residues']['A']],[False,True,False])
  for selected in ([],['A1','A1'],['C2'],['B2']):
   with self.subTest(selected=selected),self.assertRaises(ValueError):prepare(self.structure,['A'],{'designResidues':selected})
 def test_ties_cannot_override_fixed_residues_or_infer_alignment(self):
  for options in ({'tiedChains':[['A','A']]},{'tiedChains':[['A','B'],['B','A']]},{'designResidues':['A2'],'tiedChains':[['A','B']]}):
   with self.assertRaises(ValueError):prepare(self.structure,['A','B'],options)
  self.structure['residues'].pop()
  with self.assertRaisesRegex(ValueError,'equal observed'):prepare(self.structure,['A','B'],{'tiedChains':[['A','B']]})
 def test_omissions_and_log_biases_are_explicit_and_finite(self):
  for options in ({'omitAminoAcids':'X'},{'omitAminoAcids':'CC'},{'omitAminoAcids':'ACDEFGHIKLMNPQRSTVWY'},{'aminoAcidBias':{'A':float('nan')}},{'aminoAcidBias':{'A':True}}):
   with self.assertRaises(ValueError):prepare(self.structure,['A'],options)
  result=prepare(self.structure,['A'],{'omitAminoAcids':'CW','aminoAcidBias':{'Y':.5}})
  self.assertEqual(result['omitAminoAcids'],'CW');self.assertEqual(result['aminoAcidBias'],{'Y':.5})
