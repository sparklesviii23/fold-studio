"""Worker contracts, real molecular fixtures and detached process lifecycle."""
import base64,copy,fcntl,json,pathlib,subprocess,sys,tempfile,time,unittest,uuid
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'remote_worker'))
from fold_rapid.api import Worker
from fold_rapid.contracts import manifest,digest
from fold_rapid.molecules import inspect,confined
from fold_rapid.store import Store,TERMINAL

def fixture():
    raw=(ROOT/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb').read_bytes()
    return {'schemaVersion':1,'engine':'structure_screen','operation':'screen','target':{'format':'pdb','contentBase64':base64.b64encode(raw).decode(),'sha256':digest(raw),'chains':['A']},'design':{'modality':'peptide','lengths':[20],'count':1,'attempts':1},'seed':42,'budget':{'seconds':30},'mode':'reference'}

class RapidWorkerTest(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.worker=Worker(self.root)
    def tearDown(self):self.tmp.cleanup()
    def call(self,op,payload={}):return self.worker.dispatch({'apiVersion':2,'requestId':'test','operation':op,'payload':payload})['result']
    def test_health_truthful(self):
        value=self.call('health');self.assertFalse(value['scientificCUDAQualified']);self.assertEqual(value['apiVersion'],2)
        self.assertTrue(next(x for x in value['engines'] if x['id']=='structure_screen')['executionAvailable'])
        self.assertTrue(all(not x['cudaExecutionTested'] for x in value['engines']))
    def test_version_refused(self):
        with self.assertRaises(ValueError):self.worker.dispatch({'apiVersion':1,'requestId':'test','operation':'health','payload':{}})
    def test_public_command_refused(self):
        with self.assertRaises(ValueError):self.call('exec',{'command':'echo unsafe'})
    def test_real_target_mapping(self):
        value=self.call('campaign_validate',{'manifest':fixture()});self.assertTrue(value['valid']);self.assertEqual(value['target']['residueCount'],115)
        self.assertEqual(len(value['target']['chains']['A']['residues']),115)
    def test_real_cif_numbering(self):
        raw=(ROOT/'reports/architect-fab-components-v2/COMPONENT_OUTPUT/2_Refolded/Complexes/engineering_full_fab_fixture_candidate1.cif').read_bytes()
        value=inspect(raw,'cif');self.assertEqual(value['residueCount'],559);self.assertEqual(sorted(len(c['sequence']) for c in value['chains'].values()),[115,213,231])
    def test_bad_target_checksum(self):
        value=fixture();value['target']['sha256']='0'*64
        with self.assertRaises(ValueError):manifest(value)
    def test_missing_chain(self):
        value=fixture();value['target']['chains']=['Z']
        with self.assertRaises(ValueError):self.call('campaign_validate',{'manifest':value})
    def test_redesign_roles_are_validated_before_submission(self):
        value=fixture();value.update(engine='proteinmpnn',operation='redesign')
        value['design']['designChains']=['Z']
        with self.assertRaisesRegex(ValueError,'existing binder'):self.worker.store.submit(value,'missing-design-chain')
        value['design']['designChains']=['A']
        with self.assertRaisesRegex(ValueError,'disjoint'):self.worker.store.submit(value,'overlapping-role')
    def test_hotspot_mapping_refused(self):
        value=fixture();value['design']['hotspots']={'A':[99999]}
        with self.assertRaises(ValueError):self.call('campaign_validate',{'manifest':value})
    def test_nan_refused(self):
        value=fixture();value['budget']['seconds']=float('nan')
        with self.assertRaises(ValueError):manifest(value)
    def test_command_injection_settings(self):
        value=fixture();value['settings']={'project_folder':'/tmp/escape'}
        with self.assertRaises(ValueError):manifest(value)
    def test_cross_engine_unverified_refused(self):
        value=fixture();value['parentCandidates']=['fake']
        with self.assertRaises(ValueError):manifest(value)
    def test_price_required(self):
        value=fixture();value['budget']['maxCost']=1
        with self.assertRaises(ValueError):manifest(value)
    def test_budget_cost_reduces_deadline(self):
        value=fixture();value['budget']={'seconds':7200,'maxCost':1,'hourlyPrice':2}
        result=self.call('campaign_validate',{'manifest':value});self.assertEqual(result['effectiveDeadlineSeconds'],1800)
    def test_idempotency_persistent_and_conflict(self):
        first=self.worker.store.submit(fixture(),'stable');second=Store(self.root).submit(fixture(),'stable')
        self.assertEqual(first['jobId'],second['jobId']);self.assertFalse(second['created'])
        changed=fixture();changed['seed']=43
        with self.assertRaises(ValueError):self.worker.store.submit(changed,'stable')
    def test_explicit_submission_approval(self):
        with self.assertRaises(ValueError):self.call('job_submit',{'manifest':fixture(),'idempotencyKey':'x','approvedResearchTransfer':False})
    def test_artifact_traversal_refused(self):
        for path in ('../outside','/etc/passwd','../../'):
            with self.assertRaises(ValueError):confined(self.root,path)
    def test_artifact_symlink_refused(self):
        (self.root/'link').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):confined(self.root,'link')
    def test_recovery_marks_lost_runner_interrupted(self):
        value=self.worker.store.submit(fixture(),'lost');self.call('job_recover')
        self.assertEqual(self.worker.store.get(value['jobId'])['state'],'interrupted')
    def test_detached_real_job_and_result_package(self):
        value=self.call('job_submit',{'manifest':fixture(),'idempotencyKey':'actual','approvedResearchTransfer':True});id=value['jobId']
        # New client proves the request that spawned the job is not its owner.
        other=Worker(self.root);deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            state=other.store.get(id)
            if state['state'] in TERMINAL:break
            time.sleep(.1)
        self.assertEqual(state['state'],'completed',state)
        self.assertEqual(state['result']['accepted'],0)
        screen=json.loads((other.store.folder(id)/'output/structure-screen.json').read_text());self.assertFalse(screen['prediction'])
        data=self.call('artifact_read',{'jobId':id,'path':'results.zip','length':100})
        self.assertEqual(digest(base64.b64decode(data['contentBase64'])),data['chunkSha256'])
        events=self.call('job_events',{'jobId':id})['events'];self.assertTrue(any(e['kind']=='started' for e in events))
        replay=self.call('job_submit',{'manifest':fixture(),'idempotencyKey':'actual','approvedResearchTransfer':True});self.assertFalse(replay['created'])
    def test_scientific_cuda_refusal_not_cpu_prediction(self):
        value=fixture();value.update(engine='bindcraft2',operation='design')
        result=self.call('job_submit',{'manifest':value,'idempotencyKey':'missing-models','approvedResearchTransfer':True});deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            job=self.worker.store.get(result['jobId'])
            if job['state'] in TERMINAL:break
            time.sleep(.1)
        self.assertEqual(job['state'],'failed');self.assertIn('Install the isolated',job['error']);self.assertFalse((self.worker.store.folder(job['id'])/'candidates.json').exists())
        # The failure package includes original inputs/diagnostics, no invented model output.
        deadline=time.monotonic()+3
        while not (self.worker.store.folder(job['id'])/'results.zip').exists() and time.monotonic()<deadline:time.sleep(.05)
        artifacts=self.call('artifact_list',{'jobId':job['id']})['artifacts']
        self.assertTrue(any(a['path']=='failure.json' for a in artifacts));self.assertTrue(any(a['path']=='results.zip' for a in artifacts))
    def test_cancel_owned_waiting_job(self):
        with (self.root/'accelerator.lock').open('a+') as lease:
            fcntl.flock(lease,fcntl.LOCK_EX)
            value=self.call('job_submit',{'manifest':fixture(),'idempotencyKey':'cancel','approvedResearchTransfer':True});id=value['jobId']
            self.call('job_cancel',{'jobId':id})
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                state=self.worker.store.get(id)['state']
                if state in TERMINAL:break
                time.sleep(.05)
            self.assertEqual(state,'cancelled');self.assertFalse((self.worker.store.folder(id)/'execution.log').exists())
    def test_deadline_stops_waiting_job(self):
        with (self.root/'accelerator.lock').open('a+') as lease:
            fcntl.flock(lease,fcntl.LOCK_EX)
            m=fixture();m['budget']['seconds']=1
            value=self.call('job_submit',{'manifest':m,'idempotencyKey':'deadline','approvedResearchTransfer':True});deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                state=self.worker.store.get(value['jobId'])['state']
                if state in TERMINAL:break
                time.sleep(.05)
            self.assertEqual(state,'deadline_exceeded')
    def test_active_process_is_terminated_by_cancel_and_deadline(self):
        # Process-control fixture only. No substitute molecular result/model.
        import os
        for reason in ('cancel','deadline'):
            with self.subTest(reason=reason):
                value=fixture();value['budget']['seconds']=1 if reason=='deadline' else 30
                id=self.worker.store.submit(value,'active-'+reason)['jobId']
                code="from pathlib import Path;import sys;from fold_rapid import runner;runner.prepare=lambda root,folder,manifest,**kwargs:{'command':[sys.executable,'-c','import time;time.sleep(60)'],'environment':{},'models':{}};runner.execute(Path(sys.argv[1]),sys.argv[2])"
                import os
                process=subprocess.Popen([sys.executable,'-c',code,str(self.root),id],env={**os.environ,'PYTHONPATH':str(ROOT/'remote_worker')},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    until=time.monotonic()+10
                    while time.monotonic()<until and self.worker.store.get(id)['state']!='running':time.sleep(.02)
                    self.assertEqual(self.worker.store.get(id)['state'],'running')
                    child=next(e['childPid'] for e in self.worker.store.events(id) if e['kind']=='started')
                    if reason=='cancel':self.worker.store.cancel(id)
                    self.assertEqual(process.wait(timeout=12),0)
                    self.assertEqual(self.worker.store.get(id)['state'],'cancelled' if reason=='cancel' else 'deadline_exceeded')
                    with self.assertRaises(ProcessLookupError):os.kill(child,0)
                    self.assertTrue((self.worker.store.folder(id)/'results.zip').is_file())
                finally:
                    if process.poll() is None:process.kill();process.wait()
    def test_bindcraft_translation_preserves_scientific_overrides(self):
        from fold_rapid.adapters import prepare
        m=fixture();m.update(engine='bindcraft2',operation='design',settings={'weights_iptm_loss':0.1,'filters':{'pLDDT':{'threshold':0.8}}})
        folder=self.root/'translation';folder.mkdir()
        runtime={'python':sys.executable,'source':str(ROOT/'vendor/bindcraft2')}
        with patch('fold_rapid.adapters.verified_runtime',return_value=(runtime,{})):
            result=prepare(self.root,folder,m)
        values=json.loads((folder/'execution-settings.json').read_text())
        self.assertEqual(values['filters'],m['settings']['filters']);self.assertEqual(values['binder_lengths'],[20]);self.assertEqual(values['campaign_seed'],42)
        self.assertEqual(result['command'][2],'design');self.assertEqual(result['environment']['JAX_PLATFORMS'],'cuda');self.assertEqual((folder/'target.pdb').read_bytes(),base64.b64decode(m['target']['contentBase64']))
    def test_boltzgen_official_peptide_contract(self):
        from fold_rapid.adapters import prepare
        m=fixture();m.update(engine='boltzgen',operation='design')
        folder=self.root/'boltz';folder.mkdir();moldir=self.root/'mols';moldir.mkdir()
        models={name:{'path':str(self.root/(name+'.ckpt'))} for name in ('design-diverse','design-adherence','folding','solublempnn','moldir')}
        with patch('fold_rapid.adapters.verified_runtime',return_value=({'python':sys.executable,'source':'/isolated/boltzgen','moldir':str(moldir),'esmfold2Python':sys.executable},models)):
            result=prepare(self.root,folder,m)
        spec=json.loads((folder/'design.yaml').read_text());self.assertEqual(spec['entities'][0]['protein'],{'id':'G','sequence':'20..20'})
        self.assertEqual(spec['entities'][1]['file']['include'],[{'chain':{'id':'A'}}]);self.assertIn('peptide-anything',result['command']);self.assertIn('fold_rapid.boltz_entry',result['command']);self.assertEqual(result['environment']['HF_HUB_OFFLINE'],'1')
    def test_original_rejected_candidate_normalization(self):
        from fold_rapid.adapters import collect
        import shutil
        folder=self.root/'result';folder.mkdir();shutil.copytree(ROOT/'reports/architect-fab-components-v2/COMPONENT_OUTPUT',folder/'output')
        m=fixture();m.update(engine='bindcraft2',operation='design')
        results=collect(folder,m,{'sourceRevision':'actual saved fixture, not a new GPU run'})
        self.assertEqual(len(results),1);r=results[0];self.assertEqual(r['outcome'],'rejected');self.assertEqual(r['rejectionReasons'],'i_pTM');self.assertEqual(r['coordinates']['mapping']['residueCount'],559)
        self.assertTrue(r['coordinates']['chainRoles']['binder']);self.assertFalse(r['independentEvaluationHistory'])
    def test_boltzgen_import_selects_refolded_coordinates(self):
        # Public-coordinate/schema fixture; does not assert a BoltzGen prediction.
        import gemmi,csv
        from fold_rapid.adapters import collect
        value=fixture();value.update(engine='boltzgen',operation='design')
        source=gemmi.read_pdb_string(base64.b64decode(value['target']['contentBase64']).decode())
        binder=source[0]['A'].clone();binder.name='G';source[0].add_chain(binder)
        folder=self.root/'bg';output=folder/'output';refold=output/'refold_cif';refold.mkdir(parents=True)
        raw=source.make_mmcif_document().as_string().encode()
        (refold/'design.cif').write_bytes(raw)
        # A different earlier backbone with the same filename must not win.
        source[0]['G'][0][0].pos.x+=3
        source.make_mmcif_document().write_file(str(output/'design.cif'))
        with (output/'all_designs_metrics.csv').open('w') as f:
            writer=csv.DictWriter(f,fieldnames=['id','file_name','designed_sequence','pass_structure_filter']);writer.writeheader();writer.writerow({'id':'fixture','file_name':'design.cif','designed_sequence':'ACDE','pass_structure_filter':False})
        candidates=collect(folder,value,{'jobId':'fixture-only'})
        self.assertEqual(candidates[0]['coordinates']['artifact'],'output/refold_cif/design.cif')
        self.assertEqual(candidates[0]['coordinates']['sha256'],digest(raw));self.assertEqual(candidates[0]['outcome'],'rejected')
        self.assertEqual(candidates[0]['rejectionReasons'],'pass_structure_filter')

if __name__=='__main__':unittest.main()
