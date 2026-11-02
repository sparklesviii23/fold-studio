"""Control-plane tests only. Synthetic records do not validate model accuracy."""
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
from worker import Service
import biological_models as B
import gpu_tasks as G
import biological_model_runner as R


class BiologicalModelsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.s = Service(pathlib.Path(self.tmp.name)); self.pid = self.s.project_create({'name': 'Synthetic software acceptance'})['id']
        self.p = {'projectId': self.pid}

    def tearDown(self):
        self.s.db.close(); self.tmp.cleanup()

    def call(self, a, **p): return self.s.dispatch(a, {**self.p, **p})

    def study(self): return self.call('bio_study_create', name='Software test dossier', organism='Synthetic reference', reference='fixture', question='Does provenance survive a restart?')

    def evidence(self, r, **kwargs):
        return self.call('bio_study_evidence', id=r['id'], expectedSha256=r['data']['sha256'], category='research_note', title='Software observation', source='Synthetic control test', summary='Not a biological result.', **kwargs)

    def test_catalog_exposes_all_integrations_without_claiming_qualification(self):
        c = self.call('bio_models_catalog')
        self.assertEqual(set(c['models']), B.RECIPE_IDS)
        self.assertFalse(c['clinicalUse'])
        self.assertTrue(all(r['qualification'] == 'integration_unvalidated' and 'script' not in r for r in c['models'].values()))

    def test_every_remote_script_is_syntactically_valid(self):
        for rid in B.RECIPE_IDS:
            r = G.RECIPES[rid]
            subprocess.run(['bash', '-n'], input=r['script'], text=True, check=True, capture_output=True)
        compile(pathlib.Path(R.__file__).read_text(), R.__file__, 'exec')

    def test_cost_gate_precedes_provider_calls(self):
        with patch.object(G, '_provider') as provider:
            for rid in B.RECIPE_IDS:
                with self.assertRaisesRegex(ValueError, 'Approve'):
                    self.call('bio_models_submit', recipe=rid, inputSource='Synthetic fixture', inputs={})
            provider.assert_not_called()
        self.assertFalse(list((self.s.root/'gpu_tasks').glob('*/task.json')))

    def test_inputs_use_the_correct_alphabets(self):
        self.assertEqual(G._clean_inputs('bio_evo2', {'sequence':'ac gt', 'alternate':''})['sequence'], 'ACGT')
        for rid, seq in [('bio_evo2','ACGU'),('bio_esmc','ACDX'),('bio_esmfold2','A'*601),('bio_evo2','A'*8001)]:
            with self.assertRaises(ValueError): G._clean_inputs(rid, {'sequence':seq})
        self.assertEqual(G._clean_inputs('bio_borzoi', {})['start'], 1000000)
        for value in (1.5, True, float('nan')):
            with self.assertRaises(ValueError): G._clean_inputs('bio_borzoi', {'start':value})

    def test_all_recipes_use_the_existing_remote_lifecycle(self):
        for rid in B.RECIPE_IDS:
            with patch.object(G, '_provider', return_value=('/usr/bin/true', {}, 'synthetic-account')), patch.object(G.subprocess, 'Popen') as popen:
                popen.return_value.pid = 999999
                inputs = {'sequence':'ACGT'} if rid=='bio_evo2' else {} if rid=='bio_borzoi' else {'sequence':'MAAC'}
                if rid == 'bio_antisense': inputs = {'request': {'mode': 'benchmark', 'source': 'Public benchmark'}}
                r = self.call('bio_models_submit', recipe=rid, inputSource='Synthetic software input', inputs=inputs, approvedRemoteCost=True)
                self.assertEqual(r['projectId'], self.pid); self.assertEqual(r['inputSource'], 'Synthetic software input')
                self.assertEqual(r['provider'], 'modal'); self.assertEqual(r['state'], 'launching')
        self.assertEqual(len(self.call('bio_models_runs')), len(B.RECIPE_IDS))
        other = self.s.project_create({'name':'Other'})['id']
        self.assertEqual(B.dispatch(self.s, 'bio_models_runs', {'projectId':other}), [])
        with self.assertRaises(ValueError): B.dispatch(self.s, 'bio_models_result', {'projectId':other,'taskId':r['id']})

    def test_study_persists_and_evidence_is_append_only_with_conflict_detection(self):
        initial = self.study(); r = self.evidence(initial)
        self.assertEqual(r['data']['content']['evidence'][0]['category'], 'research_note')
        self.assertIn('not independently verified', r['data']['content']['evidence'][0]['verification'])
        with self.assertRaisesRegex(ValueError, 'changed'): self.evidence(initial)
        self.assertEqual(len(self.call('bio_studies')[0]['data']['content']['evidence']), 1)
        root=self.s.root; self.s.db.close(); self.s=Service(root)
        self.assertEqual(self.call('bio_studies')[0]['data']['sha256'], r['data']['sha256'])
        self.assertTrue(any(x['id']==r['id'] for x in self.s.library({})['records']))

    def test_bad_evidence_and_cross_project_changes_leave_study_intact(self):
        r=self.study();other=self.s.project_create({'name':'Other'})['id']
        with self.assertRaises(ValueError): B.dispatch(self.s,'bio_study_evidence',{'projectId':other,'id':r['id']})
        with self.assertRaises(ValueError): self.call('bio_study_evidence',id=r['id'],expectedSha256=r['data']['sha256'],category='treatment_recommendation')
        self.assertEqual(self.call('bio_studies')[0]['data']['sha256'], r['data']['sha256'])

    def test_tampered_study_refuses_new_evidence(self):
        r=self.study();data=r['data'];data['content']['organism']='tampered'
        with self.s.db:self.s.db.execute('UPDATE records SET data=? WHERE id=?',(json.dumps(data),r['id']))
        with self.assertRaisesRegex(ValueError, 'integrity'):self.evidence(r)

    def test_artifact_export_preserves_bytes_and_rejects_tampering(self):
        tid='b'*32;d=G._folder(self.s)/tid;(d/'outputs').mkdir(parents=True)
        raw=b'Synthetic binary export fixture, not a model result';(d/'outputs/protein-embeddings.npy').write_bytes(raw)
        rec={'id':tid,'projectId':self.pid,'recipe':'bio_esmc','state':'done','outputs':[{'path':'protein-embeddings.npy','sha256':hashlib.sha256(raw).hexdigest()}]}
        G._write(self.s,rec)
        with tempfile.TemporaryDirectory() as dest:
            path=pathlib.Path(dest)/'fixture.npy'
            self.call('bio_models_export',taskId=tid,file='protein-embeddings.npy',path=str(path))
            self.assertEqual(path.read_bytes(),raw)
            with self.assertRaises(ValueError):self.call('bio_models_export',taskId=tid,file='../task.json',path=str(path))
            (d/'outputs/protein-embeddings.npy').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'checksum'):self.call('bio_models_export',taskId=tid,file='protein-embeddings.npy',path=str(path))
            self.assertEqual(path.read_bytes(),raw)

    def test_result_identity_and_checksum_are_verified_before_display(self):
        tid='a'*32;d=G._folder(self.s)/tid;(d/'outputs').mkdir(parents=True)
        result={'schema':'fold-studio.biological-model-result.v1','recipe':'bio_esmc','inputsSha256':'fixture'}
        raw=json.dumps(result).encode();(d/'outputs/result.json').write_bytes(raw)
        rec={'id':tid,'projectId':self.pid,'recipe':'bio_esmc','state':'done','created':'test','inputsSha256':'fixture',
             'outputs':[{'path':'result.json','sha256':hashlib.sha256(raw).hexdigest()}]}
        G._write(self.s,rec)
        self.assertEqual(self.call('bio_models_result',taskId=tid)['result'],result)
        (d/'outputs/result.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'checksum'):self.call('bio_models_result',taskId=tid)


if __name__ == '__main__': unittest.main()
