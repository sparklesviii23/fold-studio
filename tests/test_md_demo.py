import os, pathlib, subprocess, sys, tempfile, time, types, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))

APP = pathlib.Path(__file__).resolve().parents[2] / 'current' / 'fold Metal Dev.app' / 'Contents' / 'Resources' / 'runtime-openmm' / 'bin' / 'python3'
OPENMM = os.environ.get('FOLD_OPENMM_PYTHON') or (str(APP) if APP.is_file() else '')


class RoutingTests(unittest.TestCase):
    def test_worker_routes_without_scientific_stack(self):
        code = ("import sys,builtins;real=builtins.__import__\n"
                "def guard(name,*a,**k):\n"
                "    if name.split('.')[0] in ('numpy','scipy','openmm'): raise ImportError('blocked '+name)\n"
                "    return real(name,*a,**k)\n"
                "builtins.__import__=guard;sys.path.insert(0,sys.argv[1]);import worker;print('md_reference_start' in worker.ACTIONS)")
        r = subprocess.run([sys.executable, '-B', '-c', code, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific')], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ['True'], r.stderr[-800:])

    def test_reference_coordinates_match_checksum(self):
        import hashlib, md_demo
        self.assertEqual(hashlib.sha256(md_demo.PDB.read_bytes()).hexdigest(), md_demo.PDB_SHA256)


@unittest.skipUnless(OPENMM, 'The OpenMM runtime is not available')
class SimulationTests(unittest.TestCase):
    def test_short_run_checks_and_record(self):
        import md_demo
        os.environ['FOLD_OPENMM_PYTHON'] = OPENMM
        with tempfile.TemporaryDirectory() as tmp:
            svc = types.SimpleNamespace(root=pathlib.Path(tmp), setting=lambda k, d=None: d)
            with self.assertRaises(ValueError):
                md_demo.dispatch(svc, 'md_reference_start', {'production_ps': 1000})
            job = md_demo.dispatch(svc, 'md_reference_start', {'production_ps': 5, 'seed': 3})
            deadline = time.time() + 300
            while time.time() < deadline:
                s = md_demo.dispatch(svc, 'md_reference_status', {'id': job['id']})
                if s['state'] != 'running':
                    break
                time.sleep(2)
            self.assertEqual(s['state'], 'done', s)
            rec = md_demo.dispatch(svc, 'md_reference_record', {'id': job['id']})
            self.assertTrue(all(c['passed'] for c in rec['checks']), [c for c in rec['checks'] if not c['passed']])
            self.assertEqual(len(rec['frames']), 20)
            self.assertEqual(len(rec['frames'][0]), rec['system']['atoms'])
            self.assertEqual(len(rec['rmsfMd']), 20)
            self.assertLess(max(rec['rmsd']), 3.0)          # stays folded over picoseconds
            self.assertEqual(md_demo.dispatch(svc, 'md_reference_runs', {})[0]['id'], job['id'])


if __name__ == '__main__':
    unittest.main()
