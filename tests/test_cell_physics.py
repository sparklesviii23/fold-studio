import json, math, pathlib, sys, tempfile, types, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scientific'))
import numpy as np
import cell_physics as cp, cell_physics_bd as bd, cell_physics_actions

# Smaller than the UI defaults so the suite runs in well under a minute; same physics and tolerances.
SMALL_BINDING = {'ligands': 400, 'receptors': 120, 'replicates': 4, 'tEnd': 8.0}


class GeometryTests(unittest.TestCase):
    def test_sphere_reflection_keeps_particles_inside_and_preserves_path_length(self):
        rng = np.random.default_rng(1)
        dom = bd.Domain.sphere(1.0)
        x = dom.uniform(rng, 5000) * 0.999
        dx = rng.standard_normal(x.shape) * 0.3
        y, refl, proj = dom.step(x, dx)
        self.assertGreater(refl, 100)
        self.assertEqual(proj, 0)
        self.assertTrue(dom.contains(y).all())
        # Single reflections are isometries: a particle reflected once ends exactly |dx| from the hit point,
        # so the end point is never farther from the start than the step length.
        self.assertTrue((np.linalg.norm(y - x, axis=1) <= np.linalg.norm(dx, axis=1) + 1e-12).all())

    def test_shell_reflection_handles_both_walls(self):
        rng = np.random.default_rng(2)
        dom = bd.Domain.shell(1.0, 1.5)
        x = dom.uniform(rng, 5000)
        for _ in range(50):
            x, _, proj = dom.step(x, rng.standard_normal(x.shape) * 0.05)
            self.assertEqual(proj, 0)
        r = np.linalg.norm(x, axis=1)
        self.assertGreaterEqual(r.min(), 1.0 - 1e-9)
        self.assertLessEqual(r.max(), 1.5 + 1e-9)

    def test_free_domain_is_untouched(self):
        dom = bd.Domain.free()
        x = np.zeros((10, 3)); dx = np.ones((10, 3)) * 100
        y, refl, proj = dom.step(x, dx)
        self.assertTrue(np.array_equal(y, dx))
        self.assertEqual((refl, proj), (0, 0))

    def test_reaction_volume_matches_monte_carlo(self):
        rng = np.random.default_rng(3)
        sigma, R = 0.3, 2.0
        p = np.array([0, 0, R]) + sigma * np.cbrt(rng.random(400000))[:, None] * bd.directions(rng, 400000)
        mc = 4 / 3 * math.pi * sigma ** 3 * (np.linalg.norm(p, axis=1) >= R).mean()
        self.assertAlmostEqual(bd.reaction_volume(sigma, R) / mc, 1.0, delta=0.01)
        # Flat-membrane limit is half the ball.
        self.assertAlmostEqual(bd.reaction_volume(0.1, 1e6) / (2 / 3 * math.pi * 0.001), 1.0, places=5)

    def test_unit_conversion(self):
        self.assertAlmostEqual(bd.kon_molar(1.0), 6.02214076e8)


class EquilibriumTheoryTests(unittest.TestCase):
    def test_exact_ensemble_small_case(self):
        # Two ligands, one receptor: P(1)/P(0) = 2K/V.
        mean, sd = bd.exact_equilibrium(2, 1, 3.0, 10.0)
        a = 2 * 0.3
        self.assertAlmostEqual(mean, a / (1 + a))

    def test_mean_field_solves_mass_action_and_matches_large_n(self):
        nL, nR, K, V = 600, 200, 1.0, 913.0
        c = bd.mean_field_equilibrium(nL, nR, K, V)
        self.assertAlmostEqual(c, K / V * (nL - c) * (nR - c), places=8)
        exact, _ = bd.exact_equilibrium(nL, nR, K, V)
        self.assertLess(abs(exact - c) / c, 1e-3)


class InputTests(unittest.TestCase):
    def test_out_of_bounds_inputs_are_rejected_not_clamped(self):
        with self.assertRaisesRegex(bd.BDError, 'between'):
            cp.diffusion({'diffusion': 1000})
        with self.assertRaisesRegex(bd.BDError, 'whole number'):
            cp.diffusion({'particles': 100.5})

    def test_step_size_limits(self):
        with self.assertRaisesRegex(bd.BDError, '0.05 R'):
            cp.diffusion({'dt': 0.05})
        with self.assertRaisesRegex(bd.BDError, 'σ'):
            cp.binding({'dt': 0.005})
        with self.assertRaisesRegex(bd.BDError, '≤ 0.2'):
            bd.bind({'membraneRadius': 5, 'outerRadius': 7, 'diffusion': 20, 'ligands': 10, 'receptors': 10, 'replicates': 1,
                     'reactionRadius': 0.1, 'kon': 100, 'koff': 1, 'dt': 1e-4, 'tEnd': 0.01}, 1)

    def test_overlapping_reaction_volumes_are_refused(self):
        with self.assertRaisesRegex(bd.BDError, 'overlap'):
            cp.binding({'receptors': 2000, 'reactionRadius': 0.2, 'dt': 1e-4})


class DiffusionDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = cp.diffusion({})

    def test_all_validations_pass(self):
        for c in self.result['checks']:
            self.assertIsNot(c['passed'], False, c['name'] + ': ' + c['detail'])
            self.assertTrue(c['applicable'], c['name'])
        self.assertTrue(self.result['passed'])
        names = {c['name'] for c in self.result['checks']}
        self.assertTrue({'Free: fitted D', 'Free: MSD(t_end) = 6Dt', 'Sphere: early MSD = 6Dt', 'Sphere: plateau 3/5 R²', 'Sphere: uniform radial density'} <= names)

    def test_numbers_are_close_to_theory(self):
        checks = {c['name']: c['value'] for c in self.result['checks']}
        self.assertLess(abs(checks['Free: fitted D']['relativeError']), 0.05)
        plateau = checks['Sphere: plateau 3/5 R²']
        self.assertLess(abs(plateau['msd'] / plateau['expected'] - 1), 0.03)

    def test_record_contract(self):
        r = self.result['record']
        self.assertEqual(r['schema'], 'fold.research-record')
        self.assertEqual(r['evidence']['category'], 'B')
        self.assertEqual(r['inputs']['diffusion']['unit'], 'µm²/s')
        self.assertEqual(r['reproducibility']['seed'], 20261030)
        self.assertEqual(len(r['reproducibility']['contentSha256']), 64)
        tracks = np.array(r['outputs']['sampled']['sphere'])
        self.assertEqual(tracks.shape[2], 3)
        self.assertLessEqual(np.linalg.norm(tracks, axis=2).max(), 5.0 + 1e-3)

    def test_seeded_runs_are_reproducible(self):
        a = cp.diffusion({'particles': 200, 'tEnd': 0.2})['record']['reproducibility']['contentSha256']
        b = cp.diffusion({'particles': 200, 'tEnd': 0.2})['record']['reproducibility']['contentSha256']
        c = cp.diffusion({'particles': 200, 'tEnd': 0.2, 'seed': 7})['record']['reproducibility']['contentSha256']
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_short_run_reports_plateau_not_applicable(self):
        r = cp.diffusion({'particles': 200, 'tEnd': 0.1})
        plateau = next(c for c in r['checks'] if c['name'] == 'Sphere: plateau 3/5 R²')
        self.assertFalse(plateau['applicable'])
        self.assertIsNone(plateau['passed'])


class BindingDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = cp.binding(SMALL_BINDING)

    def test_equilibrium_matches_exact_and_mechanistic_ode(self):
        checks = {c['name']: c for c in self.result['checks']}
        for name in ('Bookkeeping', 'ODE converged to mass-action equilibrium', 'Equilibrium vs exact ensemble', 'Equilibrium vs well-mixed ODE'):
            self.assertTrue(checks[name]['applicable'], name)
            self.assertTrue(checks[name]['passed'], name + ': ' + checks[name]['detail'])
        eq = self.result['record']['outputs']['equilibrium']
        self.assertLess(abs(eq['bd'] - eq['ode']), 4 * eq['se'])
        self.assertGreater(eq['occupancy'], 0.1)

    def test_ode_comes_from_mechanistic_engine(self):
        solver = self.result['record']['solver']['ode']
        self.assertIn('Mechanistic Biology Lab', solver['engine'])
        self.assertEqual(len(solver['modelSha256']), 64)
        self.assertTrue(solver['diagnostics']['reliable'])

    def test_parameters_are_marked_hypothetical(self):
        inputs = self.result['record']['inputs']
        self.assertEqual(inputs['kon']['provenance']['kind'], 'hypothetical')
        self.assertEqual(inputs['koff']['provenance']['kind'], 'hypothetical')
        self.assertEqual(inputs['kon']['unit'], 'µm³/s')

    def test_sampled_tracks_and_receptor_states(self):
        s = self.result['record']['outputs']['sampled']
        track, bound = np.array(s['track']), np.array(s['bound'])
        self.assertEqual(track.shape[:2], bound.shape)
        r = np.linalg.norm(track, axis=2)
        self.assertGreaterEqual(r.min(), 5.0 - 1e-3)
        self.assertLessEqual(r.max(), 7.0 + 1e-3)
        # Bound ligands are drawn on a receptor.
        receptors = np.array(s['receptors'])
        on = track[bound.astype(bool)]
        if len(on):
            self.assertLess(np.min(np.linalg.norm(on[:, None] - receptors[None], axis=2), axis=1).max(), 2e-3)
        self.assertEqual(len(s['receptorsBound']), track.shape[1])

    def test_short_run_is_not_applicable(self):
        r = cp.binding({**SMALL_BINDING, 'tEnd': 1.0, 'replicates': 3})
        eq = next(c for c in r['checks'] if c['name'] == 'Equilibrium vs exact ensemble')
        self.assertFalse(eq['applicable'])
        self.assertTrue(r['passed'])  # nothing failed; the comparison is simply not made


class SweepTests(unittest.TestCase):
    def test_koff_sweep_tracks_equilibrium(self):
        r = cp.binding_sweep({**SMALL_BINDING, 'replicates': 3, 'koffValues': [1.0, 4.0], 'tEnd': 4.0})
        rows = r['record']['outputs']['rows']
        self.assertTrue(r['passed'])
        self.assertGreater(rows[0]['occupancy'], rows[1]['occupancy'])
        for row in rows:
            self.assertLess(abs(row['bd'] - row['ode']), 4 * row['se'])
        self.assertEqual(r['record']['inputs']['koff']['value'], [1.0, 4.0])


class WorkerIntegrationTests(unittest.TestCase):
    def test_actions_are_routed_allowlisted_and_bundled(self):
        import worker
        self.assertTrue(cell_physics_actions.ACTIONS <= worker.ACTIONS)
        rust = (ROOT / 'src-tauri' / 'src' / 'main.rs').read_text()
        conf = json.loads((ROOT / 'src-tauri' / 'tauri.conf.json').read_text())
        resources = json.dumps(conf)
        for action in cell_physics_actions.ACTIONS:
            self.assertIn('"' + action + '"', rust)
        for name in ('cell_physics.py', 'cell_physics_bd.py', 'cell_physics_actions.py'):
            self.assertIn('../scientific/' + name, resources)

    def test_dispatch_writes_research_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = types.SimpleNamespace(root=tmp)
            r = cp.dispatch(service, 'cell_physics_diffusion', {'particles': 200, 'tEnd': 0.2})
            stored = json.loads((pathlib.Path(tmp) / 'cell_physics' / 'runs' / (r['record']['id'] + '.json')).read_text())
            self.assertEqual(stored['reproducibility']['contentSha256'], r['record']['reproducibility']['contentSha256'])
            listed = cp.dispatch(service, 'cell_physics_runs', {})
            self.assertEqual(listed[0]['id'], r['record']['id'])
            with self.assertRaisesRegex(ValueError, 'between'):
                cp.dispatch(service, 'cell_physics_diffusion', {'radius': -1})
            self.assertIn('Smoldyn', cp.dispatch(service, 'cell_physics_catalog', {})['engine']['solverChoice']['evaluated'])


if __name__ == '__main__':
    unittest.main()
