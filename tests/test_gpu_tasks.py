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
        self.assertEqual(set(c['recipes']), {'rhofold', 'boltz_rna', 'hemocell', 'physicell', 'custom', 'bio_evo2', 'bio_borzoi', 'bio_esmc', 'bio_esmfold2', 'bio_antisense', 'tahoe_atlas', 'rna_design_cpu'})
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

    def test_large_design_resume_uses_a_file_and_reaches_the_cloud_worker(self):
        import os
        import rna_design_cloud
        import rna_design_core
        body = {'request': {'target': '((....))'}, 'runId': 'same-run',
                'files': {'rna_design_core.py': '# preserved source\n', 'rna_design_cloud.py': '# worker\n', 'rna_lab_fold.py': '# checker\n'},
                'resumeState': {'evaluations': 522, 'seen': [str(i) * 30 for i in range(4096)]}}
        inputs = {'design': json.dumps(body)}
        self.assertGreater(len(json.dumps(inputs).encode()), 131072)
        provider = mock.MagicMock()
        provider.Sandbox.create.return_value.object_id = 'sb-file-input'
        volume = provider.Volume.from_name.return_value
        uploaded = {}
        volume.batch_upload.return_value.__enter__.return_value.put_file.side_effect = lambda stream, path: uploaded.update({path: stream.read()})
        task = {'id': 'a' * 32, 'recipe': 'rna_design_cpu', 'inputs': inputs, 'gpu': None, 'timeout': 180, 'recipeSha256': 'sealed'}
        with mock.patch.dict(sys.modules, {'modal': provider}), mock.patch.object(G, '_image'):
            launched = G._remote('gpu_task_launch', {'task': task})
        self.assertEqual(launched['sandboxId'], 'sb-file-input')
        launch = provider.Sandbox.create.call_args.kwargs
        self.assertNotIn('FOLD_INPUT', launch['env'])
        self.assertLess(sum(len(v) for v in launch['env'].values()), 1024)
        self.assertEqual((launch['timeout'], launch['cpu'], launch['memory']), (180, (1.0, 1.0), (2048, 2048)))
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'input.json'
            path.write_bytes(uploaded[launch['env']['FOLD_INPUT_FILE'].removeprefix('/cache')])
            self.assertEqual(json.loads(path.read_text()), inputs)
            env = {**os.environ, 'FOLD_INPUT_FILE': str(path), 'OUT': tmp}
            env.pop('FOLD_INPUT', None)
            code = G.RECIPES['rna_design_cpu']['script'].split("python - <<'PY'\n", 1)[1].split('\nPY\n', 1)[0]
            subprocess.run([sys.executable, '-c', code], cwd=tmp, env=env, check=True, capture_output=True)
            for name, content in body['files'].items():
                self.assertEqual((pathlib.Path(tmp) / name).read_text(), content)
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(rna_design_cloud.signal, 'signal'), mock.patch.object(rna_design_cloud.subprocess, 'run'), mock.patch.object(rna_design_core, 'search') as search:
                rna_design_cloud.main()
            self.assertEqual(json.loads((pathlib.Path(tmp) / 'state.json').read_text()), body['resumeState'])
            self.assertEqual(search.call_args.args[0], body['request'])

    def test_cancel_during_launch_stops_the_late_sandbox_and_fetches_partial_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = svc(tmp)
            with mock.patch.object(G, '_provider', return_value=('/usr/bin/true', {}, 'a' * 32)), mock.patch.object(G.subprocess, 'Popen', return_value=mock.MagicMock(pid=999999)):
                rec = G.dispatch(s, 'gpu_task_submit', {'recipe': 'rhofold', 'inputs': {'sequence': TRNA}, 'approvedRemoteCost': True})
            with mock.patch.object(G, '_alive', return_value=True):
                waiting = G.dispatch(s, 'gpu_task_cancel', {'taskId': rec['id']})
            self.assertEqual(waiting['state'], 'launching')
            self.assertTrue(waiting['stopRequested'])
            d = G._folder(s) / rec['id']
            (d / 'launch.json').write_text(json.dumps({'result': {'sandboxId': 'sb-late', 'appName': G.APP_NAME, 'launched': 0}}))
            calls = []
            def remote(service, action, payload, **kwargs):
                calls.append(action)
                if action == 'gpu_task_poll':
                    return {'running': False, 'returncode': 137, 'stdout': 'partial saved', 'stderr': ''}
                if action == 'gpu_task_fetch':
                    return {'files': {'partial.json': b'{}'.hex()}}
                return {}
            with mock.patch.object(G, '_rpc', side_effect=remote):
                stopped = G.dispatch(s, 'gpu_task_status', {'taskId': rec['id']})
            self.assertEqual(calls, ['gpu_task_cancel_remote', 'gpu_task_poll', 'gpu_task_fetch'])
            self.assertEqual(stopped['state'], 'stopped')
            self.assertEqual(stopped['outputs'][0]['path'], 'partial.json')

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
