"""Scientific orchestration fixtures; fake executor outputs are explicitly synthetic."""
import base64,copy,json,pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'remote_worker'));sys.path.insert(0,str(ROOT/'scientific'));sys.path.insert(0,str(ROOT/'tests'))
from test_biology_pipeline import complex_pdb
from fold_rapid.unified_contract import campaign,estimate,blockers
from fold_rapid.unified import CampaignStore,run,atomic,model_manifest
from fold_rapid.contracts import digest,manifest
from fold_rapid.molecules import inspect
from fold_rapid.modal_provider import configuration


def fixture():
    raw=complex_pdb().encode()
    return {'schemaVersion':1,'kind':'unified','strategy':'evolution','target':{'format':'pdb','contentBase64':base64.b64encode(raw).decode(),'sha256':digest(raw),'chains':['A']},'parents':[{'id':'original','binderChains':['B'],'sequences':{'A':'ACDE','B':'ACDE'}}],'generators':[],'workflow':{'redesign':['proteinmpnn','solublempnn'],'predictors':['esmfold2_fast','af2_multimer'],'rosetta':False,'count':1},'stageBudgets':{e:{'seconds':10,'hourlyEstimateUSD':1} for e in ['proteinmpnn','solublempnn','esmfold2_fast','af2_multimer']},'budget':{'seconds':600,'maxEstimatedUSD':2},'seed':42,'constraints':{'B':{'mutable':[3,4]}},'policy':{'maxDescendants':30}}


class SyntheticStages:
    def __init__(self,root,store=None,id=None,cancel_at=None,corrupt=False):self.root=root;self.calls=[];self.store=store;self.id=id;self.cancel_at=cancel_at;self.corrupt=corrupt
    def __call__(self,stage,value,checkpoint,cancelled):
        self.calls.append(copy.deepcopy(value));engine=value['engine'];folder=self.root/'campaigns'/self.id/'stages'/stage['stageId']/'jobs'/('b'*32);folder.mkdir(parents=True)
        checkpoint({'jobId':'b'*32});records=[]
        if self.cancel_at==len(self.calls):self.store.cancel(self.id)
        sequences=value['biology']['sequences'];sequence=sequences['B']
        if engine in ('proteinmpnn','solublempnn'):
            records=[{'candidateId':digest((engine+sequence).encode()),'generator':engine,'binderSequence':sequence[:2]+'AA','coordinates':None,'metrics':{},'outcome':'sequence_redesigned','fixture':True}]
        else:
            raw=base64.b64decode(value['target']['contentBase64']);raw=raw.replace(b'ASP B   3',b'ALA B   3').replace(b'GLU B   4',b'ALA B   4') if sequence=='ACAA' else raw
            target=folder/'prediction.pdb';target.write_bytes(raw);mapping=inspect(raw,'pdb')
            records=[{'candidateId':digest((engine+sequence).encode()),'generator':engine,'binderSequence':sequence,'coordinates':{'artifact':'prediction.pdb','sha256':'f'*64 if self.corrupt else digest(raw),'mapping':mapping,'chainRoles':{'binder':['B'],'target':['A']}},'metrics':{},'outcome':'evaluated','fixture':True}]
        atomic(folder/'candidates.json',records)
        return {'folder':str(folder),'job':{'id':'b'*32,'state':'completed','result':{'fixture':True}}}


class UnifiedTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.store=CampaignStore(self.root)
    def tearDown(self):self.tmp.cleanup()
    def submit(self,v=None,approved=True):return self.store.submit(v or fixture(),'stable',approved)['campaignId']
    def executor(self,id,**kw):return SyntheticStages(self.root,self.store,id,**kw)
    def test_contract_and_cost(self):
        v=campaign(fixture());self.assertEqual(v,fixture());self.assertGreater(estimate(v)['upperReservationUSD'],0);self.assertFalse(estimate(v)['externalAPIIncluded'])
    def test_compilation_benchmark_has_no_final_candidate_selection(self):
        v=fixture();v['workflow']={'redesign':[],'predictors':[],'rosetta':False,'count':1,'purpose':'compilation_benchmark'}
        v['generators']=[{'engine':'bindcraft2','design':{'modality':'peptide','lengths':[4],'count':1,'attempts':1}}]
        v['stageBudgets']={'bindcraft2':{'seconds':10,'hourlyEstimateUSD':1}}
        self.assertEqual(blockers(campaign(v)),[])
        id=self.submit(v)
        def execute(stage,value,checkpoint,cancelled):
            folder=self.root/'empty-fixture-output';folder.mkdir();atomic(folder/'candidates.json',[])
            return {'folder':str(folder),'job':{'id':'b'*32,'state':'no_qualified_candidates','result':{'fixture':True,'wallSeconds':1}}}
        row=run(self.root,id,execute)
        self.assertEqual(row['state'],'COMPLETED');self.assertTrue(row['benchmarkOnly'])
        self.assertEqual(row['qualifiedCandidates'],[]);self.assertEqual(row['selection'],[])
        v['workflow']['predictors']=['af2_multimer']
        with self.assertRaisesRegex(ValueError,'benchmark'):campaign(v)

    def test_unobserved_initial_sequence_refused(self):
        v=fixture();v['parents'][0]['sequences']['B']='AAAA'
        with self.assertRaisesRegex(ValueError,'observed'):campaign(v)
    def test_roles_overlap_refused(self):
        v=fixture();v['parents'][0]['binderChains']=['A']
        with self.assertRaises(ValueError):campaign(v)
    def test_mask_target_missing_refused(self):
        v=fixture();v['constraints']={'Z':{'mutable':[1]}}
        with self.assertRaises(ValueError):campaign(v)
    def test_target_mutability_cannot_be_silently_dropped(self):
        v=fixture();v['constraints']={'A':{'mutable':[1]}}
        with self.assertRaisesRegex(ValueError,'Fixed target'):campaign(v)
    def test_site_guided_cannot_ignore_missing_hotspots(self):
        v=fixture();v['strategy']='site_guided'
        with self.assertRaisesRegex(ValueError,'hotspots'):campaign(v)
    def test_infinite_cost_refused(self):
        v=fixture();v['budget']['maxEstimatedUSD']=float('inf')
        with self.assertRaises(ValueError):campaign(v)
    def test_no_model_budgets_refused(self):
        v=fixture();v['stageBudgets'].pop('proteinmpnn')
        with self.assertRaises(ValueError):campaign(v)
    def test_model_count_bounded(self):
        v=fixture();v['workflow']['count']=100
        with self.assertRaises(ValueError):campaign(v)
    def test_idempotent_reconnect(self):
        id=self.submit();again=self.store.submit(fixture(),'stable',True);self.assertEqual(again['campaignId'],id);self.assertFalse(again['created'])
    def test_conflicting_reconnect_refused(self):
        self.submit();v=fixture();v['seed']=1
        with self.assertRaisesRegex(ValueError,'conflicts'):self.store.submit(v,'stable',True)
    def test_explicit_approval_required(self):
        id=self.submit(approved=False);executor=self.executor(id);self.assertEqual(run(self.root,id,executor)['state'],'WAITING_FOR_APPROVAL');self.assertFalse(executor.calls)
    def test_unsupported_chemistry_blocks_all_model_dispatch(self):
        v=fixture();v['strategy']='chemically_stabilized';id=self.submit(v);executor=self.executor(id);self.assertEqual(run(self.root,id,executor)['state'],'PARTIALLY_COMPLETE');self.assertFalse(executor.calls)
    def test_automatic_branches_and_fresh_refolds(self):
        id=self.submit();executor=self.executor(id);out=run(self.root,id,executor)
        self.assertEqual(out['state'],'COMPLETED',out['events'][-1]);self.assertEqual(len(executor.calls),8)
        nodes=self.store.candidates(id);redesigns=[c for c in nodes if c['operation']=='REDESIGN'];self.assertEqual(len(redesigns),2)
        self.assertEqual(redesigns[0]['sequences'],redesigns[1]['sequences']);self.assertNotEqual(redesigns[0]['candidateId'],redesigns[1]['candidateId'])
        self.assertEqual(redesigns[0]['parents'],redesigns[1]['parents']);self.assertTrue(all(not c['coordinates'] and c['backboneReference'] for c in redesigns))
        self.assertTrue(all(c['nativeCandidate']['fixture'] for c in nodes if 'nativeCandidate' in c));self.assertFalse(out['qualifiedCandidates'])
        self.assertEqual(len([c for c in nodes if c['operation']=='REFOLD']),6)
        for decision in out['selection'][0]['rows']:self.assertIn('missing_held_out_physics_assessment',decision['reasons'])
    def test_initial_bytes_immutable(self):
        id=self.submit();run(self.root,id,self.executor(id));original=self.store.candidates(id)[0];self.assertEqual(original['coordinates'],fixture()['target']);self.assertEqual(original['sequences']['B'],'ACDE')
    def test_actual_geometry_report_contains_no_affinity(self):
        id=self.submit();out=run(self.root,id,self.executor(id));files=list((self.store.folder(id)/'assessments').glob('*.json'));self.assertEqual(len(files),6)
        data=json.loads(files[0].read_text());self.assertTrue(data['noAffinityClaim']);self.assertIn('interfaceArea',data['metrics']);self.assertIn('analysis',data)
    def test_no_stale_confidence_in_redesign(self):
        id=self.submit();run(self.root,id,self.executor(id));nodes=self.store.candidates(id)
        self.assertTrue(all(c['nativeCandidate']['metrics']=={} for c in nodes if c['operation']=='REDESIGN'))
    def test_cancel_stops_subsequent_work_and_preserves_original(self):
        id=self.submit();executor=self.executor(id,cancel_at=1);out=run(self.root,id,executor);self.assertEqual(out['state'],'CANCELLED');self.assertEqual(len(executor.calls),1);self.assertTrue(self.store.candidates(id))
    def test_ambiguous_dispatch_never_retries(self):
        id=self.submit()
        def fail(*args):raise ConnectionError('lost response')
        self.assertEqual(run(self.root,id,fail)['state'],'PARTIALLY_COMPLETE');executor=self.executor(id);run(self.root,id,executor);self.assertFalse(executor.calls)
    def test_lost_coordinator_does_not_replay_claim(self):
        id=self.submit();row=self.store.get(id);row['stages']=[{'state':'RUNNING'}];self.store.write(row);executor=self.executor(id);out=run(self.root,id,executor);self.assertEqual(out['state'],'PARTIALLY_COMPLETE');self.assertFalse(executor.calls)
    def test_budget_prevents_next_stage(self):
        v=fixture();v['budget']['maxEstimatedUSD']=.004;id=self.submit(v);executor=self.executor(id);out=run(self.root,id,executor);self.assertEqual(out['state'],'PARTIALLY_COMPLETE');self.assertEqual(len(executor.calls),1)
    def test_checksum_failure_not_candidate(self):
        id=self.submit();out=run(self.root,id,self.executor(id,corrupt=True));self.assertEqual(out['state'],'FAILED');self.assertFalse([c for c in self.store.candidates(id) if c['operation']=='REFOLD'])
    def test_status_excludes_snapshot(self):self.assertNotIn('contentBase64',self.store.status(self.submit())['manifest']['target'])
    def test_current_modal_gpu_identifiers(self):
        for gpu in ('A10','L40S','A100-40GB','A100-80GB','H100'):configuration({'appName':'fold-fixture','imageDigest':'example.org/fold@sha256:'+'a'*64,'gpu':gpu,'maxSeconds':600,'hourlyEstimateUSD':1})
        with self.assertRaises(ValueError):configuration({'appName':'fold-fixture','imageDigest':'example.org/fold@sha256:'+'a'*64,'gpu':'A10G','maxSeconds':600,'hourlyEstimateUSD':1})

if __name__=='__main__':unittest.main()

class NativeUnifiedTests(unittest.TestCase):
    def setUp(self):
        import worker
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.s=worker.Service(self.root/'research');self.project=self.s.project_create({'name':'Unified fixture'})['id']
        self.path=self.root/'structure.pdb';self.path.write_text(complex_pdb());self.record=self.s.import_structure({'projectId':self.project,'path':str(self.path)})
        self.cfg={'appName':'fold-fixture','imageDigest':'example.org/fold@sha256:'+'a'*64,'gpu':'A10','maxSeconds':600,'hourlyEstimateUSD':1}
        self.s.dispatch('biology_modal_configure',{'projectId':self.project,'configuration':self.cfg})
    def tearDown(self):self.s.db.close();self.tmp.cleanup()
    def prepared(self,**extra):
        return self.s.dispatch('biology_unified_prepare',{'projectId':self.project,'structureId':self.record['id'],'targetChains':['A'],'binderChains':['B'],'generators':[],'workflow':fixture()['workflow'],'strategy':'evolution','seed':42,'seconds':600,'stageSeconds':10,'maxEstimatedUSD':1,**extra})
    def test_native_prepare_is_local_and_immutable(self):
        out=self.prepared();self.assertEqual(out['kind'],'unified');self.assertEqual(out['state'],'prepared');self.assertNotIn('contentBase64',out['manifest']['target']);self.assertFalse(out['estimate']['scientificGPUValidated'])
        import biology_modal
        stored=biology_modal.read(self.s,{'projectId':self.project,'id':out['id']});self.assertIn('contentBase64',stored['manifest']['target'])
    def test_native_unknown_strategy_has_honest_blocker(self):self.assertTrue(self.prepared(strategy='motif_scaffolding')['blockers'])
    def test_missing_native_parser_routes_review_to_isolated_runtime_only(self):
        import builtins,biology_modal
        from unittest.mock import patch
        original=builtins.__import__
        def imports(name,*args,**kwargs):
            if name=='gemmi':raise ImportError('fixture parser absent from supervisor')
            return original(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=imports),patch.object(biology_modal.biology_providers,'rpc',return_value={'state':'prepared','fixture':True}) as isolated:
            self.assertEqual(self.prepared()['state'],'prepared');self.assertEqual(isolated.call_args.args[1],'biology_unified_prepare')
    def test_native_review_includes_resource_prices_and_distinct_stage_limits(self):
        prices={'gpuSecondUSD':1/3600,'cpuCoreSecondUSD':.0000131,'memoryGiBSecondUSD':.00000222,'workerCPUs':2,'workerMemoryGiB':64,'startupSecondsPerStage':60,'safetyUSD':.6,'storageAndControlUSD':.2}
        out=self.prepared(maxEstimatedUSD=2,resourcePricing=prices,stageLimitsSeconds={'proteinmpnn':12})
        self.assertEqual(out['manifest']['stageBudgets']['proteinmpnn']['seconds'],12)
        self.assertEqual(out['manifest']['stageBudgets']['af2_multimer']['seconds'],10)
        self.assertGreater(out['estimate']['totalResources']['expectedResourceReservationUSD'],out['estimate']['upperReservationUSD'])
        self.assertIsNone(out['estimate']['totalResources']['providerReportedUSD'])
    def test_review_uses_saved_hardware_when_form_has_unsaved_profile(self):
        prices={'gpuSecondUSD':99/3600,'cpuCoreSecondUSD':.0000131,'memoryGiBSecondUSD':.00000222,'workerCPUs':16,'workerMemoryGiB':256,'startupSecondsPerStage':60,'safetyUSD':.6,'storageAndControlUSD':.2}
        out=self.prepared(maxEstimatedUSD=2,resourcePricing=prices)
        saved=out['manifest']['budget']['resourcePricing']
        self.assertEqual(saved['gpuSecondUSD'],1/3600)
        self.assertEqual(saved['workerCPUs'],2)
        self.assertEqual(saved['workerMemoryGiB'],64)
        self.assertEqual(out['estimate']['gpu'],'A10')
        self.assertEqual(prices['workerCPUs'],16)

    def test_review_over_allowance_is_local_but_dispatch_quote_still_enforces_it(self):
        import biology_modal
        from fold_rapid.unified_modal import cost
        prices={'gpuSecondUSD':1/3600,'cpuCoreSecondUSD':.0000131,'memoryGiBSecondUSD':.00000222,'workerCPUs':2,'workerMemoryGiB':64,'startupSecondsPerStage':60,'safetyUSD':.6,'storageAndControlUSD':.2}
        out=self.prepared(maxEstimatedUSD=.01,resourcePricing=prices)
        self.assertEqual(out['state'],'prepared')
        self.assertFalse(out['estimate']['totalResources']['withinAllowance'])
        self.assertNotIn('callId',out)
        stored=biology_modal.read(self.s,{'projectId':self.project,'id':out['id']})
        with self.assertRaisesRegex(ValueError,'exceed the approved allowance'):
            cost(stored['manifest'],stored['configuration'])

    def test_account_replacement_refused_while_another_request_is_uncertain(self):
        import biology_modal
        out=self.prepared();stored=biology_modal.read(self.s,{'projectId':self.project,'id':out['id']});stored['state']='submission_uncertain';biology_modal.save(self.s,stored)
        with self.assertRaisesRegex(ValueError,'outstanding Modal'):
            self.s.dispatch('biology_modal_auth_start',{'projectId':self.project,'approvedBrowserLogin':True})
    def test_native_cross_project_source_refused(self):
        other=self.s.project_create({'name':'Other'})['id']
        with self.assertRaisesRegex(ValueError,'another project'):
            self.s.dispatch('biology_unified_prepare',{'projectId':other,'structureId':self.record['id']})
    def test_browser_login_requires_consent_before_spawn(self):
        with self.assertRaisesRegex(ValueError,'Approve'):self.s.dispatch('biology_modal_auth_start',{'projectId':self.project})
    def test_modal_invocations_require_cost_approval_before_sdk(self):
        from unittest.mock import patch
        import biology_modal
        with patch.dict('os.environ',{'FOLD_PROVIDER_CHILD':'1'}):
            for action in ('biology_modal_check','biology_modal_qualify'):
                with self.assertRaisesRegex(ValueError,'Approve'):self.s.dispatch(action,{'projectId':self.project})
    def test_new_native_actions_registered_everywhere(self):
        import worker,modal_account,biology_modal
        rust=(ROOT/'src-tauri/src/main.rs').read_text()
        for action in modal_account.ACTIONS|biology_modal.ACTIONS:self.assertIn(action,worker.ACTIONS);self.assertIn('"'+action+'"',rust)
    def test_completed_cloud_states_allow_delete_but_active_refuse(self):
        import biology_modal
        out=self.prepared();stored=biology_modal.read(self.s,{'projectId':self.project,'id':out['id']});stored['state']='RUNNING';biology_modal.save(self.s,stored)
        with self.assertRaisesRegex(ValueError,'Modal jobs'):self.s.project_delete({'id':self.project})
        stored['state']='COMPLETED';biology_modal.save(self.s,stored);self.s.project_delete({'id':self.project})
