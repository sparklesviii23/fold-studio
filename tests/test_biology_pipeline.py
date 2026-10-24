"""Software fixtures exercise real handoffs; never claim molecular predictions."""
import copy
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scientific'));sys.path.insert(0,str(ROOT/'remote_worker'))
import worker as w
import evolution as ev
import biology_pipeline as bp
import biology_assessment as assess
import biology_evidence as evidence
import biology_agent as agent
import biology_modal as bm
from fold_rapid.biology_contract import validate,validate_outputs,pareto
from fold_rapid.modal_provider import configuration,build_app
from fold_rapid.contracts import manifest


def complex_pdb():
    # Deliberately synthetic, non-collinear atomic coordinates for contract tests.
    rows=[];serial=1
    for ch,offset in [('A',0),('B',4)]:
        for i,(name,p) in enumerate(zip(['ALA','CYS','ASP','GLU'],[(0,0,0),(3,0,0),(4,3,0),(7,3,1)]),1):
            for atom,delta,el in [('N',-.8,'N'),('CA',0,'C'),('C',.8,'C'),('O',1.3,'O')]:
                rows.append(f'ATOM  {serial:5d} {atom:^4s} {name:3s} {ch}{i:4d}    {p[0]+delta:8.3f}{p[1]+offset:8.3f}{p[2]:8.3f}  1.00 50.00          {el:>2s}');serial+=1
        rows.append('TER')
    return '\n'.join(rows)+'\nEND\n'


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.s=w.Service(self.root/'research');self.project=self.s.project_create({'name':'Software fixture'})['id']
        self.file=self.root/'complex.pdb';self.file.write_text(complex_pdb());self.record=self.s.import_structure({'projectId':self.project,'path':str(self.file)})
        self.parent=ev.Evolution(self.s).evolution_import({'projectId':self.project,'structureId':self.record['id'],'chain':'B','constraints':{'mutable':[3,4],'excluded':{'3':'W'}}})['candidates'][0]
    def tearDown(self):self.s.db.close();self.tmp.cleanup()
    def params(self,**p):return {'projectId':self.project,'candidateId':self.parent['id'],'targetChains':['A'],**p}
    def bio(self):return {'parents':[{'id':self.parent['id'],'chain':'B','sequenceSha256':self.parent['sequenceSha256']}],'sequences':{'B':'ACDE'},'constraints':{'B':{'mutable':[3,4],'excluded':{'3':'W'}}}}
    def modal(self):return {'appName':'fixture-science','imageDigest':'example.org/fold@sha256:'+'a'*64,'gpu':'L4','maxSeconds':600,'hourlyEstimateUSD':1.0}
    def request_manifest(self,engine='solublempnn'):
        import base64
        return {'schemaVersion':1,'engine':engine,'operation':'redesign','mode':'reference','budget':{'seconds':300},'seed':42,'target':{'format':'pdb','contentBase64':base64.b64encode(self.file.read_bytes()).decode(),'sha256':self.record['data']['sha256'],'chains':['A']},'design':{'modality':'peptide','lengths':[4],'count':1,'attempts':1,'designChains':['B']},'biology':self.bio(),'parentCandidates':[self.parent['id']]}


class ContractTests(Fixture):
    def test_chain_and_parent_checksum_binding(self):
        bio=self.bio();validate(bio);bio['sequences']['B']='AAAA'
        with self.assertRaisesRegex(ValueError,'identity'):validate(bio)
    def test_fixed_and_excluded_residues_rejected(self):
        for seq in ('CCDE','ACWE'):
            with self.assertRaises(ValueError):validate_outputs({'B':seq},{'B':'ACDE'},self.bio()['constraints'])
        validate_outputs({'B':'ACAA'},{'B':'ACDE'},self.bio()['constraints'])
    def test_unsupported_options_cannot_be_ignored(self):
        value=self.request_manifest();value['biology']['prediction']={'samples':1}
        with self.assertRaisesRegex(ValueError,'silently ignored'):manifest(value)
    def test_target_cannot_acquire_mutable_mask(self):
        from fold_rapid.molecules import selected_target
        value=self.request_manifest();value['biology']['sequences']['A']='ACDE';value['biology']['constraints']['A']={'mutable':[1]}
        with self.assertRaisesRegex(ValueError,'redesign chains'):selected_target(manifest(value))
    def test_prediction_round_trip_preserves_numbering_not_template(self):
        import gemmi
        from fold_rapid.biology_tasks import normalize_prediction
        from fold_rapid.molecules import inspect
        st=gemmi.read_pdb_string(complex_pdb());st[0]['B'][0].find_atom('CA','*').pos.x+=8
        raw=normalize_prediction(st.make_mmcif_document().as_string(),{'A':'ACDE','B':'ACDE'},inspect(self.file.read_bytes(),'pdb'),{})
        result=gemmi.make_structure_from_block(gemmi.cif.read_string(raw).sole_block());self.assertAlmostEqual(result[0]['B'][0].find_atom('CA','*').pos.x,8)
        self.assertEqual([r.seqid.num for r in result[0]['B']],[1,2,3,4])
    def test_wrong_predicted_sequence_rejected(self):
        import gemmi
        from fold_rapid.biology_tasks import normalize_prediction
        from fold_rapid.molecules import inspect
        raw=gemmi.read_pdb_string(complex_pdb()).make_mmcif_document().as_string()
        with self.assertRaisesRegex(ValueError,'sequence'):normalize_prediction(raw,{'A':'ACDE','B':'AAAA'},inspect(self.file.read_bytes(),'pdb'),{})
    def test_ccd_crosslink_indices_and_self_bonds(self):
        bio={'sequences':{'B':'ACDE'},'chemistry':{'bonds':[{'chain1':'B','position1':1,'atomIndex1':0,'chain2':'B','position2':4,'atomIndex2':2}]}}
        validate(bio);bio['chemistry']['bonds'][0].update(position2=1,atomIndex2=0)
        with self.assertRaises(ValueError):validate(bio)
    def test_msa_query_and_columns_must_match(self):
        bio={'sequences':{'B':'ACDE'},'prediction':{'msa':{'B':'>query\nACDE\n>homolog\nACdDE'}}};validate(bio)
        bio['prediction']['msa']['B']='>wrong\nAAAA'
        with self.assertRaises(ValueError):validate(bio)
    def test_pareto_never_invents_missing_or_nonfinite_metrics(self):
        rows=pareto([{'id':'a','metrics':{'x':1,'y':3}},{'id':'b','metrics':{'x':2,'y':2}},{'id':'bad','metrics':{'x':float('nan')}}],{'x':'min','y':'max'},{})
        self.assertEqual(rows[1]['dominatedBy'],['a']);self.assertFalse(rows[2]['eligible'])
    def test_rosetta_unlicensed_never_execution_available(self):
        from fold_rapid.registry import inventory
        folder=self.root/'worker';folder.mkdir();(folder/'config.json').write_text(json.dumps({'runtimes':{'rosetta':{'python':sys.executable,'source':str(self.root)}}}))
        self.assertFalse(next(r for r in inventory(folder)['engines'] if r['id']=='rosetta')['executionAvailable'])


class ControllerTests(Fixture):
    def test_plan_bounded_and_no_compute_on_prepare(self):
        value=bp.plan(self.s,self.params(policy={'rounds':2}));self.assertEqual(value['selectionRules']['rounds'],2)
        self.assertFalse(self.s.rows('SELECT * FROM jobs'))
        for p in [{'seconds':0},{'policy':{'rounds':4}},{'policy':{'limits':{'affinity':[0,1]}}}]:
            with self.assertRaises(ValueError):bp.plan(self.s,self.params(**p))
    def test_descendant_does_not_reuse_parent_predicted_coordinates(self):
        child=bp.ingest_sequences(self.s,self.parent,{'B':'ACAA'},'solublempnn',{'fixture':True})
        self.assertIsNone(child['structure']);self.assertEqual(child['parentId'],self.parent['id']);self.assertEqual(child['backboneReference'],self.parent['structure'])
        with self.assertRaises(ValueError):bp.candidate_source(self.s,self.params(candidateId=child['id']))
    def test_local_admission_blocks_concurrent_scientific_run(self):
        self.s.job_new({'projectId':self.project,'name':'blocked'},'proteinmpnn','running')
        with self.assertRaisesRegex(ValueError,'competing'):bp.start(self.s,self.params(approved=True))
    def test_parent_cancellation_does_not_cancel_unowned_job(self):
        parent=self.s.job_new({'projectId':self.project,'name':'controller','children':[]},'bgmee','running')
        child=self.s.job_new({'projectId':self.project,'name':'unrelated'},'proteinmpnn','queued')
        self.s.job_cancel({'id':parent['id']});self.assertEqual(self.s.job(child['id'])['state'],'queued')
    def test_rigid_transform_does_not_create_pose_drift(self):
        import intelligence as mi
        a=mi.parse_structure(complex_pdb(),'pdb');b=copy.deepcopy(a)
        for atom in b['atoms']:
            x,y,z=atom['xyz'];atom['xyz']=[-y+30,x-20,z+10]
        self.assertLess(assess.drift(a,b,['A'],'B',[1,2])['candidatePoseRmsd'],1e-6)
        for atom in b['atoms']:
            if atom['chain']=='B':atom['xyz'][0]+=6
        self.assertGreater(assess.drift(a,b,['A'],'B',[1,2])['candidatePoseRmsd'],5)
    def row(self,id,area=10,clashes=0):return {'id':id,'samples':[{'family':'ESMFold2/ESMC','metrics':{'severeClashes':clashes,'interfaceArea':area,'liabilityCount':0},'drift':{'candidatePoseRmsd':1}}],'physicsAssessment':{'method':'fixture'},'conditionedFamilies':[],'maxDisagreement':0}
    def test_failed_candidate_cannot_dominate_valid_candidate(self):
        a=self.row('a');b=self.row('b',area=100);b['maxDisagreement']=5
        rows=assess.select([a,b],assess.policy(),pareto)
        self.assertTrue(rows[0]['eligible']);self.assertFalse(rows[1]['eligible']);self.assertEqual(rows[0]['dominatedBy'],[])
    def test_fast_and_full_same_family_not_independent(self):
        row=self.row('a');row['conditionedFamilies']=['ESMFold2/ESMC']
        value=assess.select([row],assess.policy(),pareto)[0];self.assertIn('no_unconditioned_prediction_family',value['reasons'])
    def test_missing_physics_and_reprediction_never_qualified(self):
        row={'id':'a','samples':[],'physicsAssessment':False,'maxDisagreement':None}
        value=assess.select([row],assess.policy(),pareto)[0];self.assertFalse(value['eligible'])
    def test_geometry_only_campaign_completes_without_fake_descendants(self):
        with patch.object(self.s,'spawn',side_effect=lambda job,flag:job):job=bp.start(self.s,self.params(approved=True,engines=[]))
        bp.run(self.s,job['id']);value=self.s.job(job['id']);self.assertEqual(value['state'],'completed');self.assertEqual(value['data']['qualifiedCandidates'],[])
        report=json.loads((self.s.root/value['data']['report']).read_text());self.assertFalse(report['scientificCertification']);self.assertEqual(report['stoppingReason'],'no_new_constraint_valid_sequence')
    def test_checkpoint_registration_never_accepts_wrong_bytes(self):
        path=self.root/'bad.pt';path.write_bytes(b'not a scientific model')
        with self.assertRaisesRegex(ValueError,'checkpoint|Checkpoint'):bp.model_register(self.s,self.params(approved=True,model='solublempnn',path=str(path)))


class ProviderAndAgentTests(Fixture):
    def test_modal_requires_immutable_image_and_cost_profile(self):
        configuration(self.modal())
        with self.assertRaises(ValueError):configuration({**self.modal(),'imageDigest':'example/fold:latest'})
    def test_modal_preparation_is_local_and_strips_coordinates_from_display(self):
        bm.dispatch(self.s,'biology_modal_configure',self.params(configuration=self.modal()))
        with patch.object(bm.biology_providers,'rpc',side_effect=AssertionError('no network')):
            result=bm.dispatch(self.s,'biology_modal_prepare',self.params(structureId=self.record['id'],manifest=self.request_manifest()))
        self.assertEqual(result['state'],'prepared');self.assertNotIn('contentBase64',result['manifest']['target'])
        saved=bm.read(self.s,self.params(id=result['id']));self.assertIn('contentBase64',saved['manifest']['target'])
    def test_modal_unknown_submission_blocks_project_deletion(self):
        bm.table(self.s);bm.save(self.s,{'id':'test','projectId':self.project,'state':'submission_uncertain','created':'now'})
        with self.assertRaisesRegex(ValueError,'Modal'):self.s.project_delete({'id':self.project})
    def test_agent_unknown_tool_cannot_execute(self):
        replies=[{'models':[{'name':'fixture','digest':'a','size':100}]},{'message':{'content':json.dumps({'answer':'bad','tool':'shell','arguments':{'command':'anything'}})}}]
        with patch.object(agent,'request',side_effect=replies):
            with self.assertRaisesRegex(ValueError,'unsupported tool'):agent.dispatch(self.s,'biology_agent_ask',self.params(approvedLocalInference=True,model='fixture',question='test'))
    def test_agent_science_resource_guard(self):
        self.s.job_new({'projectId':self.project,'name':'science'},'proteinmpnn','running')
        with patch.object(agent,'request',side_effect=AssertionError('LLM must not load')):
            with self.assertRaisesRegex(ValueError,'owns local'):agent.dispatch(self.s,'biology_agent_ask',self.params(approvedLocalInference=True,model='fixture',question='test'))
    def test_agent_read_only_answer_retains_model_hash_and_no_compute(self):
        replies=[{'models':[{'name':'fixture','digest':'a','size':100}]},{'message':{'content':json.dumps({'answer':'No experimental evidence is established.','tool':'none','arguments':{}})}}]
        with patch.object(agent,'request',side_effect=replies):value=agent.dispatch(self.s,'biology_agent_ask',self.params(approvedLocalInference=True,model='fixture',question='test'))
        self.assertEqual(value['modelDigest'],'a');self.assertFalse(value['scientificComputeStarted']);self.assertFalse(value['biologyReasoningQualified'])
    def test_evidence_provider_url_cannot_escape_allowlist(self):
        with self.assertRaises(ValueError):evidence.fetch('http://127.0.0.1/anything')
    def test_evidence_search_retains_exact_receipt_and_raw_snapshot(self):
        receipt={'url':'https://europepmc.org/fixture','sha256':'a'*64,'retrieved':'fixture'}
        with patch.object(evidence,'search',return_value=([{'id':'fixture','title':'Synthetic software fixture'}],receipt,{'fixture':True})):
            value=evidence.dispatch(self.s,'biology_evidence_search',self.params(query='fixture',provider='europepmc'))
        self.assertEqual(value['receipt'],receipt);self.assertEqual(hashlib.sha256((self.s.root/value['snapshot']).read_bytes()).hexdigest(),value['snapshotSha256'])
    def test_reference_mapping_rejects_other_species_and_ambiguous_sequence(self):
        fake={'sequence':{'value':'ACDEACDE'},'organism':{'scientificName':'Homo sapiens'}}
        with patch.object(evidence,'fetch',return_value=(fake,{})):
            for species in ('Mus musculus','Homo sapiens'):
                with self.assertRaises(ValueError):evidence.dispatch(self.s,'biology_reference_map',self.params(accession='Q6Q788',species=species))


class BoltzArtifactTests(Fixture):
    def test_coordinate_content_bound_to_provider_entities(self):
        import boltz_artifacts as artifacts
        request={'id':'fixture-request','projectId':self.project,'operation':'design','request':{'target':{'entities':[{'type':'protein','value':'ACDE','chain_ids':['A']}]}}}
        raw=complex_pdb().replace(' B',' Z').encode();result={'id':'fixture-result','entities':[{'type':'protein','value':'ACDE','chain_ids':['A','Z']}],'metrics':{'iptm':.5}}
        receipt={'sha256':hashlib.sha256(raw).hexdigest()}
        value=artifacts.import_result(self.s,request,result,raw,receipt)
        self.assertEqual(value['record']['data']['sha256'],receipt['sha256']);self.assertFalse(value['experimentalValidation'])
        self.assertTrue(artifacts.import_result(self.s,request,result,raw,receipt)['alreadyImported'])
        result['entities'][0]['value']='AAAA'
        with self.assertRaisesRegex(ValueError,'sequences'):artifacts.import_result(self.s,request,result,raw,receipt)
    def test_expired_or_local_artifact_url_is_rejected(self):
        import boltz_artifacts as artifacts
        for url in ('http://localhost/x','https://127.0.0.1/x'):
            with self.assertRaises(ValueError):artifacts.download({'url':url,'url_expires_at':'2099-01-01T00:00:00Z'})
    def test_modal_submit_network_failure_cannot_be_retried(self):
        import os
        bm.dispatch(self.s,'biology_modal_configure',self.params(configuration=self.modal()))
        prepared=bm.dispatch(self.s,'biology_modal_prepare',self.params(structureId=self.record['id'],manifest=self.request_manifest()))
        funcs=bm.contract();calls=[]
        def failed(*args):calls.append(args);raise TimeoutError('synthetic ambiguous transport')
        with patch.dict(os.environ,{'FOLD_PROVIDER_CHILD':'1'}),patch.object(bm,'contract',return_value=(*funcs[:3],failed)):
            for _ in range(2):
                with self.assertRaises(ValueError):bm.dispatch(self.s,'biology_modal_submit',self.params(id=prepared['id'],approvedResearchTransfer=True,approvedWorkload=True,maxEstimatedCostUSD=1))
        self.assertEqual(len(calls),1);self.assertEqual(bm.read(self.s,self.params(id=prepared['id']))['state'],'submission_uncertain')





class PeptideChemistryTests(Fixture):
    def test_genuine_rdkit_job_preserves_parent_and_saves_explicit_graph(self):
        import peptide_chemistry
        runtime=ROOT.parent/'current/FOLD STUDIO Metal Dev.app/Contents/Resources/runtime-boltz/bin/python3.12'
        if not runtime.is_file():self.skipTest('Existing licensed local RDKit runtime is unavailable on this host.')
        with patch.object(self.s,'engine_python',return_value=str(runtime)),patch.object(self.s,'spawn',side_effect=lambda job,flag:job):
            job=peptide_chemistry.dispatch(self.s,'biology_peptide_chemistry_start',self.params(approved=True,headToTail=True))
        peptide_chemistry.run(self.s,job['id']);done=self.s.job(job['id']);self.assertEqual(done['state'],'completed',done['data'].get('error'))
        child=ev.Evolution(self.s).candidate(self.project,done['data']['candidateId']);self.assertIsNone(child['structure']);self.assertEqual(child['chemistry']['representation'],'explicit_isomeric_smiles');self.assertEqual(child['validation'],'chemical_graph_validated_not_binding_pose')
        saved=ev.Evolution(self.s).candidate(self.project,self.parent['id']);self.assertEqual(saved,self.parent)
    def test_chemical_jobs_participate_in_common_resource_admission(self):
        self.s.job_new({'projectId':self.project,'name':'chemistry'},'peptide_chemistry','running')
        self.assertTrue(self.s.active())
        with self.assertRaises(ValueError):bp.start(self.s,self.params(approved=True))
    def test_counterfactual_does_not_mutate_characterized_variants(self):
        child=ev.Evolution(self.s).evolution_derive({'projectId':self.project,'candidateId':self.parent['id'],'mutations':[{'position':3,'from':'D','to':'A'}]})
        with self.assertRaisesRegex(ValueError,'cannot redesign'):bp.plan(self.s,self.params(counterfactualCandidates=[child['id']]))
        value=bp.plan(self.s,self.params(counterfactualCandidates=[child['id']],engines=['esmfold2_fast'],policy={'rounds':3}))
        self.assertEqual(value['selectionRules']['rounds'],1);self.assertEqual(value['counterfactualCandidates'],[child['id']])

if __name__=='__main__':unittest.main()
