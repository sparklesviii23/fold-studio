"""RNA Design contracts, durable search, ownership and Modal import."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
from rna_design_core import atomic, digest, search, validate, violations
import rna_design
from worker import Service


class DesignTests(unittest.TestCase):
    def test_invalid_constraints(self):
        for request in ({'target': '((...))'}, {'target': '(((..)))'}, {'target': '[[[....]]]'},
                        {'target': '(((....)))', 'locks': 'A........A'},
                        {'target': '(((....)))', 'mask': 'C' * 10, 'gcMax': .1},
                        {'target': '(((....)))', 'maxCandidates': True},
                        {'target': '(((....)))', 'maxSeconds': float('nan')}):
            with self.subTest(request=request), self.assertRaises(ValueError):
                validate(request)

    def test_durable_resume_and_cache(self):
        with tempfile.TemporaryDirectory() as path:
            folder = pathlib.Path(path)
            request = {'target': '((((....))))', 'wanted': 3, 'maxCandidates': 16, 'maxSeconds': 5,
                       'locks': 'G..........C', 'mask': 'N' * 12}
            stopped = [False]
            partial = search(request, folder / 'run', folder / 'cache.sqlite',
                             on_batch=lambda _: stopped.__setitem__(0, True), stop=lambda: stopped[0])
            self.assertEqual(partial['metrics']['stopReason'], 'cancelled')
            self.assertEqual(len(partial['candidates']), 1)
            final = search(request, folder / 'run', folder / 'cache.sqlite')
            self.assertGreaterEqual(final['qualifyingCount'], 3)
            self.assertEqual(len({c['sequence'] for c in final['candidates']}), len(final['candidates']))
            self.assertTrue(all(not violations(c['sequence'], validate(request)) for c in final['candidates']))
            self.assertTrue(all('independent' in c for c in final['candidates'] if c['qualifies']))
            again = search(request, folder / 'run', folder / 'cache.sqlite')
            self.assertEqual(again['metrics']['evaluations'], final['metrics']['evaluations'])
            other = search(request, folder / 'other', folder / 'cache.sqlite')
            self.assertEqual(other['metrics']['evaluations'], 0)
            with self.assertRaisesRegex(ValueError, 'Resume inputs'):
                search({**request, 'seed': 2}, folder / 'run')

    def test_time_limit(self):
        with tempfile.TemporaryDirectory() as path:
            out = search({'target': '((((..(((....)))..(((.....)))..))))', 'maxSeconds': 1, 'maxCandidates': 4096, 'wanted': 20}, path)
            self.assertIn(out['metrics']['stopReason'], ('time_limit', 'enough_candidates'))
            self.assertTrue((pathlib.Path(path) / 'result.json').is_file())


class JobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = Service(pathlib.Path(self.tmp.name))
        self.project = self.s.project_create({'name': 'Design test'})['id']
        self.payload = {'projectId': self.project, 'target': '((((....))))', 'maxCandidates': 8, 'maxSeconds': 3}

    def tearDown(self):
        self.s.db.close()
        self.tmp.cleanup()

    def new(self, mode='local'):
        self.s.db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', ('executionBackend', json.dumps({'mode': mode})))
        self.s.db.commit()
        q = rna_design.quote(self.s, self.payload)
        return q

    def test_quote_approval_and_no_fallback(self):
        q = self.new('modal')
        self.assertIn('CPU', q['hardware'])
        self.assertIsNone(q['cost']['billedCost'])
        with self.assertRaisesRegex(ValueError, 'Approve'):
            rna_design.start(self.s, {**self.payload, 'quoteSha256': q['quoteSha256']})
        with self.assertRaisesRegex(ValueError, 'Review'):
            rna_design.start(self.s, {**self.payload, 'quoteSha256': 'old'})
        self.assertEqual(self.s.rows("SELECT id FROM jobs WHERE engine='rna-design'"), [])

    def test_save_ownership_and_integrity(self):
        q = self.new()
        with patch.object(rna_design, 'launch_local'):
            job = rna_design.start(self.s, {**self.payload, 'quoteSha256': q['quoteSha256']})
        folder = self.s.root / 'jobs' / job['id']
        out = search(self.payload, folder)
        self.s.job_update(job['id'], 'completed')
        p = {'projectId': self.project, 'id': job['id'], 'candidateId': out['candidates'][0]['id']}
        a = rna_design.dispatch(self.s, 'rna_design_save', p)
        b = rna_design.dispatch(self.s, 'rna_design_save', p)
        self.assertEqual(a['id'], b['id'])
        self.assertEqual(a['data']['result']['sha256'], out['sha256'])
        other = self.s.project_create({'name': 'Other'})['id']
        with self.assertRaisesRegex(ValueError, 'this project'):
            rna_design.dispatch(self.s, 'rna_design_run', {**p, 'projectId': other})
        out['target'] = 'tampered'
        atomic(folder / 'result.json', out)
        with self.assertRaisesRegex(ValueError, 'integrity'):
            rna_design.result(folder)

    def test_modal_import_and_cancelled_partial(self):
        q = self.new('modal')
        task_id = 'a' * 32
        with patch('gpu_tasks.submit', return_value={'id': task_id}) as submit:
            job = rna_design.start(self.s, {**self.payload, 'quoteSha256': q['quoteSha256'], 'approvedRemoteCost': True})
        self.assertIsNone(submit.call_args.args[1]['gpu'])
        remote = self.s.root / 'gpu_tasks' / task_id / 'outputs'
        search(self.payload, remote)
        with patch('gpu_tasks.status', return_value={'state': 'stopped', 'error': 'Stopped by you'}):
            out = rna_design.poll(self.s, {'projectId': self.project, 'id': job['id']})
        self.assertEqual(out['job']['state'], 'cancelled')
        self.assertGreater(len(out['result']['candidates']), 0)
        self.assertEqual(out['result']['sha256'], rna_design.result(remote)['sha256'])

    def test_modal_resume_requires_quote_and_reuses_state(self):
        q = self.new('modal')
        with patch('gpu_tasks.submit', return_value={'id': 'b' * 32}):
            job = rna_design.start(self.s, {**self.payload, 'quoteSha256': q['quoteSha256'], 'approvedRemoteCost': True})
        folder = self.s.root / 'jobs' / job['id']
        search(self.payload, folder)
        self.s.job_update(job['id'], 'cancelled')
        p = {'projectId': self.project, 'id': job['id'], 'maxSeconds': 4}
        with self.assertRaisesRegex(ValueError, 'Review and approve'):
            rna_design.dispatch(self.s, 'rna_design_resume', p)
        quote = rna_design.quote(self.s, {**self.payload, 'maxSeconds': 4})
        with patch.object(rna_design, 'launch_cloud') as launch:
            rna_design.dispatch(self.s, 'rna_design_resume', {**p, 'quoteSha256': quote['quoteSha256'], 'approvedRemoteCost': True})
        self.assertGreater(len(launch.call_args.args[4]['seen']), 0)
        self.assertEqual(launch.call_args.args[2]['target'], self.payload['target'])


if __name__ == '__main__':
    unittest.main()
