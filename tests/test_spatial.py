import json, pathlib, subprocess, sys, tempfile, types, unittest
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import spatial, spatial_demos as demo, spatial_rdme as R


class SolverTests(unittest.TestCase):
    def test_generator_conserves_molecules(self):
        mesh = R.sphere_cell(3.0, 0.5, 1.5)
        G = demo._model(mesh, 1.0, 0.3, 0.2, 0.4).generator()
        self.assertLess(np.abs(np.asarray(G.sum(0))).max(), 1e-12)   # every column of a generator sums to zero

    def test_envelope_slows_but_does_not_block_exchange(self):
        mesh = R.sphere_cell(3.0, 0.5, 1.5)
        free, barrier = R.hop_rates(mesh, 1.0, None), R.hop_rates(mesh, 1.0, 0.1)
        crosses = np.array([c for _, _, c in mesh.edges])
        self.assertTrue(crosses.any())
        self.assertTrue(np.all(barrier[crosses] < free[crosses]) and np.all(barrier[crosses] > 0))
        self.assertTrue(np.allclose(barrier[~crosses], free[~crosses]))

    def test_membrane_area_matches_the_sphere(self):
        mesh = R.sphere_cell(5.0, 0.5)
        self.assertAlmostEqual(mesh.membrane.sum() * mesh.membrane_area_per_voxel, 4 * np.pi * 25, places=9)

    def test_simulation_is_seeded_and_conserves_counts(self):
        mesh = R.sphere_cell(2.0, 0.5)
        model = demo._model(mesh, 1.0, 0.5, 0.5, None)
        n0 = np.zeros((2, mesh.n), dtype=int); n0[0, :50] = 2
        a, b = R.simulate(model, n0, 2.0, seed=4), R.simulate(model, n0, 2.0, seed=4)
        self.assertTrue(np.array_equal(a['final'], b['final']))
        self.assertEqual(a['final'].sum(), 100)


class BenchmarkTests(unittest.TestCase):
    def test_lattice_diffusion(self):
        self.assertTrue(demo.check_diffusion(seed=2)['passed'])

    def test_bimolecular_master_equation(self):
        c = demo.check_cme(seed=2)
        self.assertTrue(c['passed'], c['detail'])
        self.assertAlmostEqual(sum(c['exact']), 1.0)

    def test_analytical_gradient_converges(self):
        c = demo.check_continuum(1.0, 0.25, 0.3, spacings=(1.0, 0.5))
        self.assertGreater(c['rows'][0]['relativeL2'], c['rows'][1]['relativeL2'])
        self.assertLess(c['rows'][1]['relativeL2'], 0.06)


class ScenarioTests(unittest.TestCase):
    def test_run_save_reopen_and_plain_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = types.SimpleNamespace(root=pathlib.Path(tmp))
            r = spatial.dispatch(svc, 'spatial_run', {'seed': 3, 'label': 'baseline'})
            json.dumps(r)   # no NumPy types may reach the UI
            self.assertTrue(all(c['passed'] for c in r['checks']), [c for c in r['checks'] if not c['passed']])
            o = r['outputs']
            self.assertLess(o['nucleusFraction']['value'], o['membraneFraction']['value'])
            self.assertAlmostEqual(o['rdmeNucleusFraction']['value'], o['nucleusFraction']['value'], delta=0.03)
            rows = spatial.dispatch(svc, 'spatial_runs', {})
            self.assertEqual(rows[0]['id'], r['recordId'])
            self.assertEqual(spatial.dispatch(svc, 'spatial_record', {'id': r['recordId']})['sha256'], r['sha256'])
            with self.assertRaises(ValueError):
                spatial.dispatch(svc, 'spatial_run', {'overrides': {'cellRadius': 50}})
            with self.assertRaises(ValueError):
                spatial.dispatch(svc, 'spatial_run', {'overrides': {'phosphatase': -1}})

    def test_faster_phosphatase_starves_the_nucleus(self):
        sweep = spatial.dispatch(types.SimpleNamespace(root='.'), 'spatial_catalog', {})
        self.assertIn('references', sweep)
        mesh = R.sphere_cell(5.0, 0.5, 2.5)
        frac = []
        for kp in (0.05, 0.25, 1.0):
            x = demo._model(mesh, 1.0, kp, 0.3, 0.5).steady_state(1000)
            nuc = mesh.compartment == 2
            frac.append(x[1][nuc].sum() / x[:, nuc].sum())
        self.assertTrue(frac[0] > frac[1] > frac[2])

    def test_worker_routes_without_scientific_stack(self):
        code = ("import sys,builtins;real=builtins.__import__\n"
                "def guard(name,*a,**k):\n"
                "    if name.split('.')[0] in ('numpy','scipy'): raise ImportError('blocked '+name)\n"
                "    return real(name,*a,**k)\n"
                "builtins.__import__=guard;sys.path.insert(0,sys.argv[1]);import worker;print('spatial_run' in worker.ACTIONS)")
        r = subprocess.run([sys.executable, '-B', '-c', code, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific')], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ['True'], r.stderr[-800:])


if __name__ == '__main__':
    unittest.main()
