"""Real upstream assets/diagnostic coordinates; no model inference or acceptance."""
import copy,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'remote_worker'),str(ROOT/'tests')]
from test_rapid_worker import fixture
from fold_rapid.contracts import manifest,digest
from fold_rapid.fab import prepare,validate_output,FILES
from fold_rapid.molecules import inspect
from fold_rapid.adapters import prepare as adapter_prepare


class FabCloudTransport(unittest.TestCase):
 def value(self):
  value=fixture();value.update(engine='bindcraft2',operation='design')
  value['design']={'modality':'Fab','count':1,'attempts':1}
  return value
 def test_cloud_contract_cannot_truncate_or_substitute_the_original_scaffold(self):
  value=self.value();self.assertEqual(manifest(value)['design'],value['design'])
  for key,val in [('lengths',[20]),('designChains',['H']),('settings',{'design_models':1})]:
   bad=copy.deepcopy(value)
   if key=='settings':bad[key]=val
   else:bad['design'][key]=val
   with self.subTest(key=key),self.assertRaises(ValueError):manifest(bad)
  value['engine']='boltzgen'
  with self.assertRaisesRegex(ValueError,'BindCraft2'):manifest(value)
 def test_actual_cloud_adapter_retains_original_settings_target_seed_and_complete_asset(self):
  with tempfile.TemporaryDirectory() as directory:
   job=pathlib.Path(directory);source=ROOT/'vendor/bindcraft2';value=self.value()
   models={'model_1_multimer_v3':{'path':'/approved/model.npz'}}
   with patch('fold_rapid.adapters.verified_runtime',return_value=({'python':'/approved/python','source':str(source)},models)):
    result=adapter_prepare(job,job,manifest(value))
   settings=json.loads((job/'execution-settings.json').read_text())
   self.assertEqual(settings['modality'],['Fab']);self.assertNotIn('binder_lengths',settings)
   self.assertNotIn('design_models',settings);self.assertEqual(settings['campaign_seed'],42)
   self.assertEqual((job/'fab-scaffold.cif').read_bytes(),(source/'scaffolds/Fab.cif').read_bytes())
   self.assertEqual((job/'target.pdb').read_bytes(),__import__('base64').b64decode(value['target']['contentBase64']))
   self.assertEqual(result['command'][1:3],[str(source/'bindcraft.py'),'design'])
   self.assertEqual(result['environment']['JAX_PLATFORMS'],'cuda')
   self.assertFalse(json.loads((job/'fab-input.json').read_text())['scientificQualificationPassed'])
 def test_corrupt_or_missing_scaffold_refused_before_model_execution(self):
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory);source=root/'source';job=root/'job';job.mkdir()
   for name in FILES:
    target=source/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/'vendor/bindcraft2'/name).read_bytes())
   (source/'scaffolds/Fab.cif').write_bytes(b'fragment')
   with self.assertRaisesRegex(ValueError,'asset differs'):prepare(job,source)
   self.assertFalse((job/'fab-scaffold.cif').exists())
 def test_both_real_diagnostic_chains_required_without_relabelling_as_acceptance(self):
  raw=(ROOT/'reports/architect-fab-components-v2/COMPONENT_OUTPUT/2_Refolded/Complexes/engineering_full_fab_fixture_candidate1.cif').read_bytes()
  mapping=inspect(raw,'cif');chains=[ch for ch,row in mapping['chains'].items() if len(row['sequence']) in (231,213)]
  record={'coordinates':{'mapping':mapping,'chainRoles':{'binder':chains}},'binderSequence':'/'.join(mapping['chains'][ch]['sequence'] for ch in chains),'outcome':'rejected'}
  validate_output(record);self.assertEqual(sorted(record['fullFabTransport']['chainLengths'].values()),[213,231]);self.assertFalse(record['fullFabTransport']['scientificQualificationPassed']);self.assertEqual(record['outcome'],'rejected')
  record['coordinates']['chainRoles']['binder']=chains[:1]
  with self.assertRaisesRegex(ValueError,'both explicit'):validate_output(record)
 def test_domain_stamp_allows_cloud_downstream_but_not_single_chain_fab_refinement(self):
  value=fixture();value['scientificDomain']='full_fab';self.assertEqual(manifest(value)['scientificDomain'],'full_fab')
  value.update(engine='bindcraft2',operation='design')
  with self.assertRaisesRegex(ValueError,'two-chain'):manifest(value)
 def test_two_chain_downstream_keeps_both_full_sequences_and_fab_execution_domain(self):
  import base64
  from fold_rapid.unified import model_manifest
  from test_unified_campaign import fixture as campaign_fixture
  raw=(ROOT/'reports/architect-fab-components-v2/COMPONENT_OUTPUT/2_Refolded/Complexes/engineering_full_fab_fixture_candidate1.cif').read_bytes()
  mapping=inspect(raw,'cif');binders=[ch for ch,row in mapping['chains'].items() if len(row['sequence']) in (231,213)];targets=[ch for ch in mapping['chains'] if ch not in binders]
  coordinates={'format':'cif','contentBase64':base64.b64encode(raw).decode(),'sha256':digest(raw),'chains':targets}
  node={'candidateId':'f'*64,'scientificDomain':'full_fab','coordinates':coordinates,'binderChains':binders,'sequences':{ch:row['sequence'] for ch,row in mapping['chains'].items()},'af2ModelExposure':{'gradientDesignModels':['model_1_multimer_v3','model_3_multimer_v3','model_5_multimer_v3'],'validationModels':['model_2_multimer_v3','model_4_multimer_v3']}}
  row={'manifest':campaign_fixture()}
  for engine in ('proteinmpnn','solublempnn','af2_multimer'):
   row['manifest']['stageBudgets'][engine]={'seconds':60,'hourlyEstimateUSD':1}
   result=model_manifest(row,node,engine)
   self.assertEqual(result['scientificDomain'],'full_fab');self.assertEqual(result['design']['designChains'],binders)
   self.assertEqual(result['biology']['sequences'],node['sequences']);self.assertEqual(result['target'],coordinates)
   if engine=='af2_multimer':self.assertEqual(result['biology']['af2']['models'],node['af2ModelExposure']['validationModels'])
