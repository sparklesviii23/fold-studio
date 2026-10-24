"""Synthetic contracts for real-cloud qualification safeguards, no model runs."""
import pathlib,sys,tempfile,unittest,json,types,copy
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'remote_worker'),str(ROOT/'scientific'),str(ROOT/'tests')]
from fold_rapid import billing
from fold_rapid.unified_contract import campaign,estimate
from fold_rapid.unified import CampaignStore,run,atomic
from fold_rapid.modal_provider import configuration
from fold_rapid.unified_modal import cost
from test_unified_campaign import fixture,SyntheticStages
from test_biology_pipeline import complex_pdb

PRICES={'gpuSecondUSD':.000694,'cpuCoreSecondUSD':.0000131,'memoryGiBSecondUSD':.00000222,'workerCPUs':2,'workerMemoryGiB':64,'startupSecondsPerStage':60,'safetyUSD':.6,'storageAndControlUSD':.2}
class CloudQualificationTests(unittest.TestCase):
 def test_original_ranked_acceptance_and_refold_pass_are_distinct(self):
  import gemmi,csv
  from fold_rapid.adapters import collect
  from test_rapid_worker import fixture as worker_fixture
  m=worker_fixture();m.update(engine='bindcraft2',operation='design')
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);ranked=p/'output/3_Ranked';ranked.mkdir(parents=True);refold=p/'output/2_Refolded';refold.mkdir()
   s=gemmi.read_pdb_string(complex_pdb());doc=s.make_mmcif_document();block=doc.sole_block();block.set_pair('_bindcraft.binder_chains','B');block.set_pair('_bindcraft.target_chains','A');(ranked/'winner.cif').write_text(doc.as_string());(refold/'passing.cif').write_text(doc.as_string())
   (ranked/'!_Ranked.csv').write_text('rank,design,Binder_Sequence\n1,winner,ACDE\n');(refold/'!_Refolded.csv').write_text('design,outcome,Binder_Sequence,failed_filters\npassing,passed,ACDE,\n')
   rows=collect(p,m,{'jobId':'fixture'});self.assertEqual([r['outcome'] for r in rows],['accepted','passed_upstream_filters']);self.assertEqual(rows[0]['metrics']['upstreamStage'],'ranked');self.assertIn('not experimental',rows[0]['metrics']['acceptanceScope'])
   (ranked/'winner.cif').unlink()
   with self.assertRaisesRegex(ValueError,'ranked acceptance'):collect(p,m,{'jobId':'fixture'})
 def test_retained_refolds_do_not_expand_reviewed_generator_budget(self):
  from fold_rapid.contracts import digest
  from fold_rapid.molecules import inspect
  v=fixture();v['generators']=[{'engine':'bindcraft2','design':{'modality':'peptide','lengths':[4],'count':1,'attempts':1}}];v['stageBudgets']['bindcraft2']={'seconds':10,'hourlyEstimateUSD':1}
  with tempfile.TemporaryDirectory() as f:
   store=CampaignStore(f);id=store.submit(v,'bounded-generator',True)['campaignId']
   class Stages(SyntheticStages):
    def __call__(self,stage,m,checkpoint,cancelled):
     if m['engine']!='bindcraft2':return super().__call__(stage,m,checkpoint,cancelled)
     self.calls.append(copy.deepcopy(m));folder=self.root/'campaigns'/id/'stages'/stage['stageId']/'jobs'/('c'*32);folder.mkdir(parents=True);raw=complex_pdb().encode();(folder/'fixture.pdb').write_bytes(raw)
     rows=[{'candidateId':str(i),'generator':'bindcraft2','binderSequence':'ACDE','coordinates':{'artifact':'fixture.pdb','sha256':digest(raw),'mapping':inspect(raw,'pdb'),'chainRoles':{'binder':['B'],'target':['A']}},'outcome':'accepted' if i==3 else 'passed_upstream_filters','metrics':{'rank':1} if i==3 else {},'fixture':True} for i in range(4)]
     atomic(folder/'candidates.json',rows);return {'folder':str(folder),'job':{'state':'completed'}}
   executor=Stages(pathlib.Path(f),store,id);out=run(f,id,executor);self.assertEqual(out['state'],'COMPLETED');self.assertEqual(sum(c['engine']=='proteinmpnn' for c in executor.calls),2);self.assertEqual(len([c for c in store.candidates(id) if c['generator']=='bindcraft2']),4)
   selected={c['parents'][0] for c in store.candidates(id) if c['operation']=='REDESIGN'};winner=next(c for c in store.candidates(id) if c.get('nativeCandidate',{}).get('outcome')=='accepted');self.assertIn(winner['candidateId'],selected)
 def test_total_reservation_counts_more_than_gpu(self):
  v=fixture();v['budget']['resourcePricing']=PRICES;v['budget']['maxEstimatedUSD']=6
  q=billing.quote(campaign(v),estimate(v));self.assertGreater(q['expectedResourceReservationUSD'],estimate(v)['upperReservationUSD']);self.assertIsNone(q['providerReportedUSD'])
 def test_resource_budget_stops_dispatch_before_spend(self):
  v=fixture();v['budget'].update(resourcePricing=PRICES,maxEstimatedUSD=.1)
  with tempfile.TemporaryDirectory() as f:
   store=CampaignStore(f);id=store.submit(v,'fixture',True)['campaignId'];executor=SyntheticStages(pathlib.Path(f),store,id)
   out=run(f,id,executor);self.assertEqual(out['state'],'PARTIALLY_COMPLETE');self.assertFalse(executor.calls)
 def test_live_meter_increases_with_active_time(self):
  v=fixture();v['budget']['resourcePricing']=PRICES
  self.assertGreater(billing.live(v,[{'engine':'bindcraft2','observedRemoteSeconds':20}],30),billing.live(v,[{'engine':'bindcraft2','observedRemoteSeconds':10}],20))
 def test_rejected_generator_is_retained_and_diagnostic_branches_remain_distinct(self):
  from fold_rapid.contracts import digest
  from fold_rapid.molecules import inspect
  v=fixture();v['parents']=[];v['constraints']={};v['generators']=[{'engine':'bindcraft2','design':{'modality':'peptide','lengths':[4],'count':1,'attempts':1}}];v['stageBudgets']['bindcraft2']={'seconds':10,'hourlyEstimateUSD':1};v['workflow']['diagnosticRejectedParents']=True
  with tempfile.TemporaryDirectory() as f:
   store=CampaignStore(f);id=store.submit(v,'fixture',True)['campaignId']
   class Stages(SyntheticStages):
    def __call__(self,stage,m,checkpoint,cancelled):
     if m['engine']!='bindcraft2':return super().__call__(stage,m,checkpoint,cancelled)
     folder=self.root/'campaigns'/id/'stages'/stage['stageId']/'jobs'/('a'*32);folder.mkdir(parents=True);raw=complex_pdb().encode();(folder/'rejected.pdb').write_bytes(raw)
     atomic(folder/'candidates.json',[{'candidateId':'rejected-fixture','generator':'bindcraft2','binderSequence':'ACDE','coordinates':{'artifact':'rejected.pdb','sha256':digest(raw),'mapping':inspect(raw,'pdb'),'chainRoles':{'binder':['B'],'target':['A']}},'outcome':'rejected','rejectionReasons':'fixture_filter','metrics':{},'fixture':True}]);return {'folder':str(folder),'job':{'id':'a'*32,'state':'no_qualified_candidates'}}
   out=run(f,id,Stages(pathlib.Path(f),store,id));nodes=store.candidates(id);parent=next(n for n in nodes if n['generator']=='bindcraft2');self.assertEqual(parent['nativeCandidate']['outcome'],'rejected');desc=[n for n in nodes if n['operation']=='REDESIGN'];self.assertEqual(len(desc),2);self.assertTrue(all(n['parents']==[parent['candidateId']] for n in desc));self.assertFalse(out['qualifiedCandidates'])
 def test_prediction_serialization_uses_new_sequence_and_new_atoms(self):
  import numpy as np,gemmi
  from fold_rapid.serialization import write_prediction
  stub=types.ModuleType('bindcraft.protein');stub.ATOM_NAMES=['CA'];stub.AMINO_ACIDS='ACDEW';stub.THREE_LETTER_CODE={'A':'ALA','C':'CYS','D':'ASP','E':'GLU','W':'TRP'}
  proteins={ch:types.SimpleNamespace(sequence=np.eye(5)[[4,1,2,3] if ch=='B' else [0,1,2,3]],atoms=np.array([[[90+i,5,2]] for i in range(4)]),atom_mask=np.ones((4,1),bool)) for ch in ['A','B']}
  with tempfile.TemporaryDirectory() as f,patch.dict(sys.modules,{'bindcraft.protein':stub}):
   p=pathlib.Path(f);(p/'source.pdb').write_text(complex_pdb());write_prediction(p/'source.pdb',proteins,p/'new.cif',['B'],['A']);s=gemmi.read_structure(str(p/'new.cif'));self.assertEqual(s[0]['B'][0].name,'TRP');self.assertEqual(s[0]['B'][0].seqid.num,1);self.assertEqual(s[0]['B'][0]['CA'][0].pos.x,90)

if __name__=='__main__':unittest.main()
