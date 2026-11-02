import json, pathlib, subprocess, sys, tempfile, types, unittest
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import gpu_tasks as G
import rna3d_compare as C

TRNA = 'GCGGAUUUAGCUCAGUUGGGAGAGCGCCAGACUGAAGAUCUGGAGGUCCUGUGUUCGAUCCACAGAAUUCGCACCA'


def svc(tmp):
    return types.SimpleNamespace(root=pathlib.Path(tmp), setting=lambda k, d=None: d)


class RecipeTests(unittest.TestCase):
    def test_catalog_hides_scripts_and_lists_every_recipe(self):
        c = G.dispatch(svc(tempfile.mkdtemp()), 'gpu_tasks_catalog', {})
        self.assertEqual(set(c['recipes']), {'rhofold', 'boltz_rna', 'hemocell', 'physicell', 'custom', 'bio_evo2', 'bio_borzoi', 'bio_esmc', 'bio_esmfold2', 'bio_antisense', 'tahoe_atlas'})
        self.assertTrue(all('script' not in r for r in c['recipes'].values()))
        self.assertTrue(all(r['license'] for r in c['recipes'].values()))

    def test_inputs_are_validated(self):
        self.assertEqual(G._clean_inputs('rhofold', {'sequence': 'acgt acgu'})['sequence'], 'ACGUACGU')
        for bad in ({'sequence': 'ACGX'}, {'sequence': 'A' * 401}):
            with self.assertRaises(ValueError):
                G._clean_inputs('rhofold', bad)
        with self.assertRaises(ValueError):
            G._clean_inputs('custom', {'registry': 'bad image; rm -rf /', 'command': 'x'})
        with self.assertRaises(ValueError):
            G._clean_inputs('custom', {'registry': 'ubuntu:22.04', 'command': 'x', 'files': {'../etc': 'x'}})
        with self.assertRaises(ValueError):
            G._gpu('rhofold', {'gpu': 'TPU'})

    def test_nothing_runs_without_cost_approval(self):
        with self.assertRaises(ValueError) as e:
            G.dispatch(svc(tempfile.mkdtemp()), 'gpu_task_submit', {'recipe': 'rhofold', 'inputs': {'sequence': TRNA}})
        self.assertIn('Approve', str(e.exception))


class LifecycleTests(unittest.TestCase):
    """Simulated provider: verifies launch, polling, download, path safety and the record, with no network or cost."""

    def test_launch_poll_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = svc(tmp)
            fake = mock.MagicMock(pid=999999)
            with mock.patch.object(G, '_provider', return_value=('/usr/bin/true', {}, 'a' * 32)), mock.patch.object(G.subprocess, 'Popen', return_value=fake):
                rec = G.dispatch(s, 'gpu_task_submit', {'recipe': 'rhofold', 'inputs': {'sequence': TRNA}, 'approvedRemoteCost': True})
            d = G._folder(s) / rec['id']
            (d / 'launch.json').write_text(json.dumps({'result': {'sandboxId': 'sb-test', 'appName': G.APP_NAME, 'launched': 0}}))
            pdb = ''.join(f"ATOM  {i+1:5d}  C1' G A{i+1:4d}    {i*3.0:8.3f}{0:8.3f}{0:8.3f}  1.00  0.00           C\n" for i in range(5))
            calls = iter([{'running': True, 'returncode': None},
                          {'running': False, 'returncode': 0, 'stdout': 'ok', 'stderr': ''},
                          {'files': {'rhofold/unrelaxed_model.pdb': pdb.encode().hex(), '../escape.txt': b'x'.hex()}}])
            with mock.patch.object(G, '_rpc', side_effect=lambda *a, **k: next(calls)):
                self.assertEqual(G.dispatch(s, 'gpu_task_status', {'taskId': rec['id']})['state'], 'running')
                done = G.dispatch(s, 'gpu_task_status', {'taskId': rec['id']})
            self.assertEqual(done['state'], 'done')
            self.assertEqual([o['path'] for o in done['outputs']], ['rhofold/unrelaxed_model.pdb'])
            self.assertFalse((G._folder(s) / 'escape.txt').exists())
            self.assertEqual(G.dispatch(s, 'gpu_tasks_list', {})[0]['state'], 'done')
            with self.assertRaises(ValueError):
                G.dispatch(s, 'gpu_task_exec', {'taskId': rec['id'], 'command': 'ls', 'approvedRemoteCommand': True})

    def test_failed_launch_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = svc(tmp)
            with mock.patch.object(G, '_provider', return_value=('/usr/bin/true', {}, 'a' * 32)), mock.patch.object(G.subprocess, 'Popen', return_value=mock.MagicMock(pid=999999)):
                rec = G.dispatch(s, 'gpu_task_submit', {'recipe': 'boltz_rna', 'inputs': {'sequence': 'GGGAAACCC'}, 'approvedRemoteCost': True})
            (G._folder(s) / rec['id'] / 'launch.json').write_text(json.dumps({'error': 'Image build failed'}))
            r = G.dispatch(s, 'gpu_task_status', {'taskId': rec['id']})
            self.assertEqual((r['state'], r['error']), ('failed', 'Image build failed'))


    def test_build_output_before_result_is_parsed_and_shown(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = svc(tmp)
            with mock.patch.object(G, '_provider', return_value=('/usr/bin/true', {}, 'a' * 32)), mock.patch.object(G.subprocess, 'Popen', return_value=mock.MagicMock(pid=999999)):
                rec = G.dispatch(s, 'gpu_task_submit', {'recipe': 'rhofold', 'inputs': {'sequence': 'GGGAAACCC'}, 'approvedRemoteCost': True})
            d = G._folder(s) / rec['id']
            (d / 'launch.json').write_text('Building image im-1\n=> Step 1: RUN pip install x\nModal token ak-secret expires\nERROR: No matching distribution\n'
                                           + json.dumps({'error': 'Image build for im-1 failed.'}) + '\n')
            r = G.dispatch(s, 'gpu_task_status', {'taskId': rec['id']})
            self.assertEqual(r['state'], 'failed')
            self.assertIn('Image build', r['error'])
            log = (d / 'build.log').read_text()
            self.assertIn('No matching distribution', log)
            self.assertNotIn('ak-secret', log)

    def test_live_log_while_running(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = svc(tmp)
            with mock.patch.object(G, '_provider', return_value=('/usr/bin/true', {}, 'a' * 32)), mock.patch.object(G.subprocess, 'Popen', return_value=mock.MagicMock(pid=999999)):
                rec = G.dispatch(s, 'gpu_task_submit', {'recipe': 'rhofold', 'inputs': {'sequence': 'GGGAAACCC'}, 'approvedRemoteCost': True})
            (G._folder(s) / rec['id'] / 'launch.json').write_text('Built image\n' + json.dumps({'result': {'sandboxId': 'sb-1', 'appName': G.APP_NAME, 'launched': 0}}))
            with mock.patch.object(G, '_rpc', return_value={'running': True, 'returncode': None, 'liveLog': '[fold] container started\nstep 3/10'}):
                r = G.dispatch(s, 'gpu_task_status', {'taskId': rec['id']})
            self.assertEqual((r['state'], r['phase']), ('running', 'Running on A10G'))
            self.assertIn('step 3/10', r['serverLog'])


    def test_stop_keeps_outputs_written_so_far(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = svc(tmp)
            with mock.patch.object(G, '_provider', return_value=('/usr/bin/true', {}, 'a' * 32)), mock.patch.object(G.subprocess, 'Popen', return_value=mock.MagicMock(pid=999999)):
                rec = G.dispatch(s, 'gpu_task_submit', {'recipe': 'rhofold', 'inputs': {'sequence': 'GGGAAACCC', 'relaxSteps': 0}, 'approvedRemoteCost': True})
            self.assertEqual(rec['inputs']['relaxSteps'], 0)
            (G._folder(s) / rec['id'] / 'launch.json').write_text(json.dumps({'result': {'sandboxId': 'sb-1', 'appName': G.APP_NAME, 'launched': 0}}))
            calls = iter([{'running': True, 'returncode': None, 'liveLog': ''},
                          {'terminated': True},
                          {'running': False, 'returncode': 137, 'stdout': '', 'stderr': 'killed'},
                          {'files': {'rhofold/unrelaxed_model.pdb': b'ATOM'.hex()}}])
            with mock.patch.object(G, '_rpc', side_effect=lambda *a, **k: next(calls)):
                G.dispatch(s, 'gpu_task_status', {'taskId': rec['id']})
                r = G.dispatch(s, 'gpu_task_cancel', {'taskId': rec['id']})
            self.assertEqual(r['state'], 'stopped')
            self.assertEqual([o['path'] for o in r['outputs']], ['rhofold/unrelaxed_model.pdb'])


class Rna3dTests(unittest.TestCase):
    def test_crystal_against_itself(self):
        ref = C.read_cif(C.REFERENCE['cif'], 'A')
        refdata = json.loads((pathlib.Path(C.__file__).with_name('rna_lab_reference.json')).read_text())['trna_phe']
        r = C.analyse({'crystal': ref}, ref, C.pairs_from_dotbracket(refdata['structure']))
        m = r['models'][0]
        self.assertEqual(m['residues'], 76)
        self.assertLess(m['rmsdToReference'], 1e-6)
        self.assertEqual(m['clashes'], 0)
        self.assertEqual(m['basePairGeometry'], 1.0)


class RoutingTests(unittest.TestCase):
    def test_worker_routes_without_provider_sdk(self):
        code = ("import sys,builtins;real=builtins.__import__\n"
                "def guard(name,*a,**k):\n"
                "    if name.split('.')[0] in ('numpy','scipy','modal'): raise ImportError('blocked '+name)\n"
                "    return real(name,*a,**k)\n"
                "builtins.__import__=guard;sys.path.insert(0,sys.argv[1]);import worker;print('gpu_task_submit' in worker.ACTIONS)")
        r = subprocess.run([sys.executable, '-B', '-c', code, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific')], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ['True'], r.stderr[-800:])


if __name__ == '__main__':
    unittest.main()
