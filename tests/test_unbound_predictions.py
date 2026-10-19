"""Explicit unbound-role protocol fixtures; these are not generated fold switches."""
import json,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures,w
from bindcraft_provenance import chain_roles,prediction_context
class UnboundPredictionContracts(unittest.TestCase):
 def setUp(self):
  self.prep={'modality':'fold_switch','config':{'targets':[{'name':'target','target_path':'input.pdb'}]},'source':{'sha256':'synthetic'},'residueMap':[]};self.row={'design':'synthetic','Binder_Sequence':'ACDE'};self.raw=b'data_fixture\n_bindcraft.binder_chains A\n';self.st={'chains':[{'id':'A','sequence':'ACDE'}]}
 def context(self,**extra):return prediction_context(extra.get('prep',self.prep),extra.get('name','synthetic_monomer.cif'),extra.get('row',self.row),extra.get('raw',self.raw),extra.get('structure',self.st),extra.get('format','mmcif'))
 def test_explicit_unbound_role_does_not_acquire_a_target(self):
  result=self.context();self.assertEqual(result['kind'],'binder_alone');self.assertNotIn('nativeTargetState',result['metadata']);self.assertEqual(result['metadata']['nativePredictionState']['kind'],'unbound_binder_prediction');self.assertEqual(result['roles']['A']['role'],'candidate');self.assertIn('parent-complex',result['metadata']['rawMetricsContext'])
  with self.assertRaises(ValueError):chain_roles(self.raw,self.st)
 def test_wrong_sequence_missing_roles_or_extra_target_are_refused(self):
  for extra in ({'row':{**self.row,'Binder_Sequence':'ACDF'}},{'row':{'design':'synthetic'}},{'raw':b'data_empty\n'},{'raw':self.raw+b'_bindcraft.target_chains A\n'},{'structure':{'chains':self.st['chains']+[{'id':'B','sequence':'ACDE'}]}},{'format':'pdb'}):
   with self.subTest(extra=extra),self.assertRaises(ValueError):self.context(**extra)
 def test_a_plain_binder_cannot_silently_gain_an_unbound_ranked_output(self):
  with self.assertRaisesRegex(ValueError,'Unexpected binder-alone'):self.context(prep={**self.prep,'modality':'binder'})
 def test_multi_chain_unbound_copy_sequences_are_checked_as_an_assembly(self):
  result=self.context(raw=b'data_fixture\n_bindcraft.binder_chains A,B\n',structure={'chains':[{'id':'B','sequence':'FGH'},{'id':'A','sequence':'ACDE'}]},row={**self.row,'Binder_Sequence':'ACDE/FGH'});self.assertEqual(len(result['roles']),2);self.assertTrue(all(v['role']=='candidate' for v in result['roles'].values()))
 def test_target_complex_context_remains_bound_to_the_exact_saved_target(self):
  result=self.context(name='synthetic.cif',raw=b'data_fixture\n_bindcraft.binder_chains B\n_bindcraft.target_chains A\n',structure={'chains':[{'id':'A','sequence':'GG'},{'id':'B','sequence':'ACDE'}]});self.assertEqual(result['kind'],'target_complex');self.assertEqual(result['metadata']['nativeTargetState']['source'],self.prep['source']);self.assertEqual(result['roles']['A']['role'],'target')

def cif(bound=False):
 """One-residue protocol fixture, deliberately not a predicted protein."""
 text='data_synthetic\n_bindcraft.binder_chains A\n'+('_bindcraft.target_chains B\n' if bound else '')
 text+='loop_\n'+''.join('_atom_site.'+name+'\n' for name in ('group_PDB','type_symbol','label_atom_id','label_comp_id','label_asym_id','label_seq_id','Cartn_x','Cartn_y','Cartn_z','B_iso_or_equiv'))
 for chain in ('A','B') if bound else ('A',):
  for name,x,element in [('N',0,'N'),('CA',1.45,'C'),('C',2.9,'C'),('O',3.9,'O')]:text+=f'ATOM {element} {name} ALA {chain} 1 {x} {10 if chain=="B" else 0} 0 {99 if bound else 42}\n'
 return text

class UnboundImportContracts(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 def output(self,bound=True):
  job=self.s.dispatch('bindcraft_prepare',self.config);prep=job['data']['preparation'];prep['modality']='fold_switch';self.s.job_update(job['id'],'prepared',{'preparation':prep})
  root=self.s.root/'jobs'/job['id']/'output';ranked=root/'3_Ranked';ranked.mkdir(parents=True)
  (root/'campaign_metadata.json').write_text(json.dumps({'settings':{}}));(ranked/'!_Ranked.csv').write_text('design,Binder_Sequence,i_pTM\nsynthetic,A,0.99\n');(ranked/'synthetic_monomer.cif').write_text(cif())
  if bound:(ranked/'synthetic.cif').write_text(cif(True))
  return {'projectId':self.project['id'],'id':job['id'],'directory':str(root)}
 def test_unbound_coordinates_do_not_satisfy_a_missing_bound_target(self):
  payload=self.output(False);before=len(self.s.library({})['records'])
  with patch('bindcraft_provenance.native_receipt',return_value={'state':'native_receipts_verified','execution':'cpu','scope':'synthetic protocol fixture'}):
   with self.assertRaisesRegex(ValueError,'missing a prepared target'):self.s.dispatch('bindcraft_import',payload)
  self.assertEqual(len(self.s.library({})['records']),before)
 def test_import_keeps_own_unbound_confidence_and_no_target_assignment(self):
  payload=self.output()
  with patch('bindcraft_provenance.native_receipt',return_value={'state':'native_receipts_verified','execution':'cpu','scope':'synthetic protocol fixture'}):result=self.s.dispatch('bindcraft_import',payload)
  records=[self.engine.lab.intelligence_inspect({'structureId':id}) for id in result['records']];unbound=next(r for r in records if r['record']['data']['metadata']['nativePredictionState']['kind']=='unbound_binder_prediction')
  self.assertEqual(unbound['confidence']['plddt'],[42.0]);self.assertIsNone(unbound['confidence']['iptm']);self.assertIsNone(unbound['confidence']['ptm']);self.assertIsNone(unbound['confidence']['pae']);self.assertNotIn('nativeTargetState',unbound['record']['data']['metadata']);self.assertEqual(unbound['assignments']['A']['role'],'candidate')
 def test_conformational_acceptance_requires_both_saved_prediction_states(self):
  import pathlib
  payload=self.output();(pathlib.Path(payload['directory'])/'3_Ranked/synthetic_monomer.cif').unlink();before=len(self.s.library({})['records'])
  with patch('bindcraft_provenance.native_receipt',return_value={'state':'native_receipts_verified','execution':'cpu','scope':'synthetic protocol fixture'}):
   with self.assertRaisesRegex(ValueError,'required unbound binder'):self.s.dispatch('bindcraft_import',payload)
  self.assertEqual(len(self.s.library({})['records']),before)
del Fixtures
