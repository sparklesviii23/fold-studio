"""BGMEE contracts, ancestry and counterfactual evidence; no predictor invoked."""
import copy
import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('evolution_worker', ROOT/'scientific/worker.py')
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)
import evolution as ev
import boltz_api_adapter as ba


class EvolutionFixture:

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = pathlib.Path(self.tmp.name)
        self.s = w.Service(self.root/'research'); self.project = self.s.project_create({'name': 'Software fixture'})['id']
    def tearDown(self):
        self.s.db.close(); self.tmp.cleanup()
    def call(self, action, **p):
        return self.s.dispatch(action, {'projectId': self.project, **p})
    def parent(self, **p):
        return self.call('evolution_import', fasta='>reference\nACDEFG', **p)['candidates'][0]
    def derive(self, parent, **p):
        return self.call('evolution_derive', candidateId=parent['id'], mutations=[{'position': 3, 'from': parent['sequence'][2], 'to': 'A'}], **p)
    def observation(self, id, **values):
        obs = {'model': 'fixture_model', 'family': 'fixture_family', 'version': 'test1', 'role': 'assessment', 'contextId': 'same-target-and-conditions', 'seed': 42,
               'metrics': {'score': 4.0}, 'artifactSha256': 'a'*64, 'method': 'synthetic contract fixture, no molecular inference', 'units': {'score': 'test_units'}, **values}
        return self.call('evolution_assess', candidateId=id, observation=obs)
    def evidence_reference(self):
        return {'species': 'Homo sapiens', 'accession': 'TEST', 'isoform': 'TEST-1', 'start': 101, 'end': 106}
    def evidence(self):
        return {'species': 'Homo sapiens', 'accession': 'TEST', 'isoform': 'TEST-1', 'nativePosition': 103, 'wildType': 'D', 'mutant': 'A', 'assay': 'synthetic fixture', 'measurement': -2.0,
                'unit': 'fixture units', 'direction': 'loss', 'source': 'local test', 'publication': 'synthetic, no publication', 'context': 'same synthetic target'}

class EvolutionTests(EvolutionFixture, unittest.TestCase):
    def test_multi_fasta_preserves_separate_candidates_and_group(self):
        values = self.call('evolution_import', fasta='>region one\nACD\n>region two\nEFG', reference={'group': 'uncertain'})['candidates']
        self.assertEqual([c['sequence'] for c in values], ['ACD', 'EFG'])
        self.assertTrue(all(c['reference']['group'] == 'uncertain' and c['parentId'] is None for c in values))
        self.assertEqual(self.s.rows('SELECT * FROM jobs'), [])
    def test_mutation_preserves_original_and_invalidates_coordinates_and_scores(self):
        parent = self.parent(); child = self.derive(parent)
        saved = self.call('evolution_list')['candidates']
        self.assertEqual(saved[0], parent); self.assertEqual(child['sequence'], 'ACAEFG')
        self.assertEqual(child['parentId'], parent['id']); self.assertEqual(child['rootId'], parent['id'])
        self.assertIsNone(child['structure']); self.assertEqual(child['validation'], 'sequence_only_unvalidated')
        self.assertNotIn('metrics', child)
    def test_fixed_and_unlisted_positions_cannot_be_changed(self):
        parent = self.parent(constraints={'mutable': [2]})
        self.assertEqual(parent['constraints']['fixed'], [1, 3, 4, 5, 6])
        with self.assertRaises(ValueError): self.derive(parent)
    def test_excluded_and_incompatible_preferred_constraints(self):
        parent = self.parent(constraints={'excluded': {'3': 'A'}})
        with self.assertRaises(ValueError): self.derive(parent)
        with self.assertRaises(ValueError): self.parent(constraints={'excluded': {'3': 'A'}, 'preferred': {'3': 'A'}})
    def test_duplicate_and_wrong_wildtype_mutations_are_rejected(self):
        p = self.parent()
        for changes in [[{'position': 3, 'from': 'E', 'to': 'A'}], [{'position': 3, 'from': 'D', 'to': 'A'}]*2, [{'position': True, 'from': 'A', 'to': 'D'}]]:
            with self.assertRaises(ValueError): self.call('evolution_derive', candidateId=p['id'], mutations=changes)
        self.assertEqual(len(self.call('evolution_list')['candidates']), 1)
    def test_hard_constraints_cannot_be_relaxed_by_descendant(self):
        p = self.parent(constraints={'fixed': [1]})
        with self.assertRaises(ValueError): self.derive(p, constraints={})
    def test_native_range_requires_species_isoform_and_exact_length(self):
        for ref in [{'start': 1, 'end': 6}, {**self.evidence_reference(), 'end': 108}]:
            with self.assertRaises(ValueError): self.parent(reference=ref)
    def test_multiple_regions_cannot_share_native_numbering(self):
        with self.assertRaises(ValueError): self.call('evolution_import', fasta='>one\nACDEFG\n>two\nACDEFG', reference=self.evidence_reference())
        self.assertEqual(self.call('evolution_list')['candidates'], [])
    def test_evidence_cannot_cross_species_accession_isoform_or_native_position(self):
        parent = self.parent(reference=self.evidence_reference())
        for key, value in [('species', 'Mus musculus'), ('accession', 'OTHER'), ('isoform', 'TEST-2'), ('nativePosition', 3)]:
            with self.assertRaises(ValueError): self.derive(parent, evidence={**self.evidence(), key: value})
        child = self.derive(parent, evidence=self.evidence())
        self.assertEqual(child['mutationEvidence']['verification'], 'user_supplied_not_independently_verified')
    def test_project_scoping(self):
        p = self.parent(); other = self.s.project_create({'name': 'Other'})['id']
        with self.assertRaises(ValueError): self.s.dispatch('evolution_derive', {'projectId': other, 'candidateId': p['id'], 'mutations': []})
    def test_decisions_are_append_only_and_do_not_delete_rejected_candidates(self):
        original = self.parent(); p = self.derive(original)
        for decision in ('reject', 'retain', 'revert'):
            self.call('evolution_decide', candidateId=p['id'], decision=decision, reason='Synthetic review')
        result = self.call('evolution_list')
        self.assertEqual(result['candidates'], [original,p]); self.assertEqual(len(result['events']), 5)
    def test_correlated_model_is_not_an_independent_validator(self):
        p = self.parent(); self.observation(p['id'], role='optimization')
        child = self.derive(p); obs = self.observation(child['id'])
        self.assertEqual(obs['data']['independence']['state'], 'conditioned_or_correlated')
        other = self.observation(child['id'], family='different', model='other')
        self.assertEqual(other['data']['independence']['state'], 'independence_unverified')
    def test_counterfactual_same_context_and_units_required(self):
        p = self.parent(reference=self.evidence_reference()); c = self.derive(p, evidence=self.evidence()); a = self.observation(p['id'])
        for update in [{'contextId': 'another_target'}, {'seed': 43}, {'units': {'score': 'other_units'}}, {'version': 'test2'}]:
            b = self.observation(c['id'], **update)
            with self.assertRaises(ValueError): self.call('evolution_compare', parentId=p['id'], candidateId=c['id'], parentObservationId=a['id'], observationId=b['id'], metric='score', higherIsBetter=True)
    def test_counterfactual_retains_raw_delta_and_disagreement(self):
        p = self.parent(reference=self.evidence_reference()); c = self.derive(p, evidence=self.evidence())
        a = self.observation(p['id']); b = self.observation(c['id'], metrics={'score': 6.0})
        r = self.call('evolution_compare', parentId=p['id'], candidateId=c['id'], parentObservationId=a['id'], observationId=b['id'], metric='score', higherIsBetter=True)
        self.assertEqual(r['delta']['score'], 2); self.assertFalse(r['directionalAgreement']); self.assertNotIn('bindingProbability', r)
    def test_observation_rejects_nonfinite_metrics_and_missing_units(self):
        p = self.parent()
        for update in [{'metrics': {'score': float('nan')}}, {'units': {}}, {'metrics': {'score': True}}, {'artifactSha256': 'invalid'}]:
            with self.assertRaises(ValueError): self.observation(p['id'], **update)
    def test_persistence_survives_service_restart(self):
        parent = self.parent(); self.s.db.close(); self.s = w.Service(self.root/'research')
        self.assertEqual(self.call('evolution_list')['candidates'], [parent])
    def test_structure_residue_map_retains_numbering_gaps_and_insertion_codes(self):
        path = self.root/'input.pdb'
        path.write_text('ATOM      1   CA ALA A  19       0.000   0.000   0.000  1.00 80.00           C\nATOM      2   CA ASP A  25A      3.000   0.000   0.000  1.00 80.00           C\n')
        item = self.s.import_structure({'projectId': self.project, 'path': str(path)})
        parent = self.call('evolution_import', structureId=item['id'], chain='A')['candidates'][0]
        self.assertEqual(parent['sequence'], 'AD'); self.assertEqual([r['number'] for r in parent['residueMap']], [19, 25])
        self.assertEqual(parent['residueMap'][1]['insertion'], 'A')
        child = self.call('evolution_derive', candidateId=parent['id'], mutations=[{'position': 2, 'from': 'D', 'to': 'E'}])
        self.assertIsNone(child['structure']); self.assertEqual(child['backboneReference']['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
    def test_saved_sequence_and_existing_intelligence_candidate_import(self):
        item = self.s.sequence_save({'projectId': self.project, 'name': 'Saved', 'sequence': 'ACD'})
        imported = self.call('evolution_import', recordId=item['id'])['candidates'][0]
        self.assertEqual(imported['sequence'], 'ACD')
        i = self.call('intelligence_candidate_save', name='Registered', sequence='EFG')
        other = self.call('evolution_import', intelligenceCandidateId=i['id'])['candidates'][0]
        self.assertEqual(other['source']['intelligenceCandidateId'], i['id'])
    def test_protocol_retains_original_control_and_never_launches_compute(self):
        parent=self.parent()
        item=self.s.import_structure({'projectId':self.project,'path':str(ROOT/'fixtures/ANGPTL3.cif')})
        result=self.call('evolution_manifest',candidateIds=[parent['id']],structureId=item['id'],minutes=60,seed=42)
        self.assertEqual(result['originalSequenceControls'],[parent['id']]);self.assertEqual(result['budget']['heavyGpuConcurrency'],1)
        self.assertEqual(result['state'],'prepared_not_executable');self.assertEqual(result['budget']['approvedSpend'],0)
        self.assertEqual(self.call('evolution_manifests')[0]['id'],result['id']);self.assertEqual(self.s.rows('SELECT * FROM jobs'),[])
        with self.assertRaises(ValueError):self.call('evolution_manifest',candidateIds=[parent['id']],structureId=item['id'],minutes=31)
    def test_project_export_includes_lineage_evidence_and_external_requests(self):
        import zipfile
        p=self.parent();child=self.derive(p);self.observation(child['id'])
        self.call('biology_boltz_prepare',operation='protein_library_screen',targetFasta='ACDE',candidateIds=[child['id']])
        file=self.root/'explicit-test-export.zip';self.s.export_project({'id':self.project,'path':str(file)})
        with zipfile.ZipFile(file) as archive:data=json.loads(archive.read('project.json'))
        biology=data['biologyGuidedDesign']
        self.assertEqual(len(biology['candidates']),2);self.assertEqual(len(biology['events']),3)
        self.assertEqual(biology['externalAPIRequests'][0]['state'],'prepared')
    def test_project_delete_removes_new_metadata_but_protects_unresolved_paid_jobs(self):
        self.parent();self.s.project_delete({'id':self.project})
        self.assertEqual(self.s.rows('SELECT * FROM evolution_candidates'),[])



class BoltzContractTests(EvolutionFixture, unittest.TestCase):
    # Synthetic SDK doubles test adapter control flow, never molecular accuracy.
    def setUp(self):
        super().setUp()
        # Unit tests intentionally remain in-process; isolated real SDK is tested separately.
        probe=patch.object(ba.importlib.metadata,'version',return_value=ba.SDK_VERSION)
        probe.start();self.addCleanup(probe.stop)
    def request(self):
        return self.call('biology_boltz_prepare', operation='protein_library_screen', targetFasta='>target\nACDEFG', candidateIds=[self.parent()['id']])
    def fake(self):
        from unittest.mock import MagicMock
        api = MagicMock(); api.__enter__.return_value = api
        resource = api.protein.library_screen
        resource.estimate_cost.return_value.model_dump.return_value = {'estimated_cost_usd': '0.05', 'disclaimer': 'estimate only', 'breakdown': {}}
        resource.start.return_value.model_dump.return_value = {'id': 'fixture_remote', 'status': 'pending'}
        resource.retrieve.return_value.model_dump.return_value = {'id': 'fixture_remote', 'status': 'running'}
        resource.stop.return_value.model_dump.return_value = {'id': 'fixture_remote', 'status': 'stopped'}
        resource.list_results.return_value.data = []; resource.list_results.return_value.has_more = False
        return api
    def test_preparation_never_initializes_client_or_charges(self):
        with patch.object(ba, 'client', side_effect=AssertionError('No network during prepare')):
            r = self.request()
        self.assertEqual(r['state'], 'prepared'); self.assertEqual(r['request']['proteins'][0]['entities'][0]['value'], 'ACDEFG')
        self.assertEqual(r['requestSha256'], ev.sha(r['request']))
    def test_quote_upload_and_paid_submission_need_distinct_approvals(self):
        r = self.request(); fake = self.fake()
        with patch.object(ba, 'client', return_value=fake):
            with self.assertRaises(ValueError): self.call('biology_boltz_quote', id=r['id'])
            self.call('biology_boltz_quote', id=r['id'], approveUpload=True)
            with self.assertRaises(ValueError): self.call('biology_boltz_start', id=r['id'], approved=True, maxEstimatedCostUSD='0.04')
            fake.protein.library_screen.start.assert_not_called()
            started = self.call('biology_boltz_start', id=r['id'], approved=True, maxEstimatedCostUSD='0.05')
            self.assertEqual(started['remoteId'], 'fixture_remote')
            with self.assertRaises(ValueError): self.call('biology_boltz_start', id=r['id'], approved=True, maxEstimatedCostUSD='1')
            self.assertEqual(fake.protein.library_screen.start.call_count, 1)
    def test_ambiguous_submission_does_not_resubmit(self):
        r = self.request(); fake = self.fake()
        with patch.object(ba, 'client', return_value=fake):
            self.call('biology_boltz_quote', id=r['id'], approveUpload=True)
            fake.protein.library_screen.start.side_effect = TimeoutError('sensitive message')
            with self.assertRaisesRegex(ValueError, 'uncertain'): self.call('biology_boltz_start', id=r['id'], approved=True, maxEstimatedCostUSD='1')
            with self.assertRaises(ValueError): self.call('biology_boltz_start', id=r['id'], approved=True, maxEstimatedCostUSD='1')
            self.assertEqual(fake.protein.library_screen.start.call_count, 1)
    def test_reconnection_only_reads_and_stop_uses_known_remote_id(self):
        r = self.request(); fake = self.fake()
        with patch.object(ba, 'client', return_value=fake):
            self.call('biology_boltz_quote', id=r['id'], approveUpload=True)
            self.call('biology_boltz_start', id=r['id'], approved=True, maxEstimatedCostUSD='1')
            value = self.call('biology_boltz_read', id=r['id']); self.assertEqual(value['state'], 'running')
            self.call('biology_boltz_stop', id=r['id'])
            self.assertEqual(fake.protein.library_screen.start.call_count, 1)
            fake.protein.library_screen.stop.assert_called_once_with('fixture_remote')
    def test_missing_sdk_and_credentials_do_not_claim_readiness(self):
        with patch('importlib.metadata.version', side_effect=ba.importlib.metadata.PackageNotFoundError), patch.dict(ba.os.environ, {}, clear=True):
            info = ba.capabilities(); self.assertFalse(info['sdkReady']); self.assertFalse(info['authenticated']); self.assertFalse(info['realServiceQualified'])
            with self.assertRaises(ValueError): ba.client()
    def test_expired_quotes_cannot_submit_and_ambiguous_jobs_block_project_deletion(self):
        r=self.request();fake=self.fake()
        with patch.object(ba,'client',return_value=fake):
            value=self.call('biology_boltz_quote',id=r['id'],approveUpload=True)
            value['quote']['received']='2000-01-01T00:00:00+00:00';ba.BoltzAPI(self.s).save(value)
            with self.assertRaises(ValueError):self.call('biology_boltz_start',id=r['id'],approved=True,maxEstimatedCostUSD='1')
            fake.protein.library_screen.start.assert_not_called()
            value['state']='submission_uncertain';ba.BoltzAPI(self.s).save(value)
            with self.assertRaisesRegex(ValueError,'reconcile'):self.s.project_delete({'id':self.project})
    def test_requote_cannot_reset_a_request_claimed_during_network_delay(self):
        r=self.request();fake=self.fake()
        def racing_quote(**kwargs):
            value=ba.BoltzAPI(self.s).read({'projectId':self.project,'id':r['id']});value['state']='submission_uncertain';ba.BoltzAPI(self.s).save(value)
            from unittest.mock import MagicMock
            result=MagicMock();result.model_dump.return_value={'estimated_cost_usd':'0.05'};return result
        fake.protein.library_screen.estimate_cost.side_effect=racing_quote
        with patch.object(ba,'client',return_value=fake):
            with self.assertRaises(ValueError):self.call('biology_boltz_quote',id=r['id'],approveUpload=True)
        self.assertEqual(ba.BoltzAPI(self.s).read({'projectId':self.project,'id':r['id']})['state'],'submission_uncertain')


if __name__ == '__main__': unittest.main()
