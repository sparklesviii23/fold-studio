"""Blood & Circulation Laboratory, Demo 6: plasma tracer transport solver (scientific/blood_transport.py)."""
import json, math, pathlib, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scientific'))
import numpy as np
import blood_transport as bt, blood_transport_actions


class ValidationTests(unittest.TestCase):
    def test_mass_conserved_to_round_off_with_no_flux_walls(self):
        r = bt.validate_mass()
        self.assertTrue(r['passed'], r); self.assertLess(r['value'], 1e-12)

    def test_open_permeable_budget_closes(self):
        r = bt.validate_budget()
        self.assertTrue(r['passed'], r); self.assertLess(r['value'], 1e-12)

    def test_taylor_aris_dispersion(self):
        r = bt.validate_taylor_aris()
        self.assertTrue(r['passed'], r); self.assertLess(r['value'], 0.01)

    def test_pure_diffusion_matches_gaussian(self):
        r = bt.validate_diffusion()
        self.assertTrue(r['passed'], r); self.assertLess(r['value'], 5e-3)

    def test_permeable_wall_matches_bessel_series(self):
        r = bt.validate_wall()
        self.assertTrue(r['passed'], r)

    def test_wall_series_limits(self):
        # Bi → 0 keeps everything; the series is 1 at τ = 0 for any Bi.
        self.assertAlmostEqual(bt.wall_decay_exact(1e-6, 1.0), 1.0, places=5)
        self.assertAlmostEqual(bt.wall_decay_exact(2.0, 0.0), 1.0, delta=2e-3)

    def test_velocity_field_is_a_verified_stokes_solution(self):
        r = bt.validate_velocity()
        self.assertTrue(r['passed'], r)

    def test_grid_convergence_second_order(self):
        r = bt.validate_convergence()
        self.assertTrue(r['passed'], r)
        self.assertGreater(r['value'], 1.8)
        e = r['taylorArisErrors']; self.assertLess(e[2], e[0])


class SolverTests(unittest.TestCase):
    def test_python_reference_fixture_is_current(self):
        ref = json.loads((ROOT / 'fixtures/blood/python-taylor-aris-reference.json').read_text())
        r = bt.solve(bt._case(), frames=2, samples=200)
        self.assertAlmostEqual(r['dispersion']['numericalM2PerS'], ref['numericalKM2PerS'], delta=1e-6 * ref['numericalKM2PerS'])

    def test_stability_numbers_reported_and_enforced(self):
        r = bt.solve(bt.PRESETS[1]['inputs'], frames=2, samples=10)
        st = r['stability']
        self.assertTrue(st['pass']); self.assertLessEqual(st['courant']['value'], 0.4 + 1e-12); self.assertLessEqual(st['axialDiffusionNumber']['value'], 0.25 + 1e-12)
        for k in ('cellPeclet', 'peclet', 'axialPeclet', 'wallBiot', 'radialDiffusionNumber'): self.assertIn(k, st)
        with self.assertRaises(bt.TransportError): bt.solve(bt.PRESETS[1]['inputs'], {'courant': 1.5})

    def test_step_inlet_reaches_inlet_level_without_wall_loss(self):
        p = {**bt.PRESETS[2]['inputs'], 'wallPermeabilityUmPerS': 0, 'durationS': 4}
        r = bt.solve(p, frames=2, samples=20)
        self.assertAlmostEqual(r['series'][-1]['outletCupMolPerM3'], 1.0, delta=1e-3)
        self.assertGreaterEqual(r['final']['minMolPerM3'], -1e-12)

    def test_permeable_wall_lowers_outlet_and_budget_closes(self):
        r = bt.solve(bt.PRESETS[2]['inputs'], frames=2, samples=20)
        self.assertLess(r['series'][-1]['outletCupMolPerM3'], 0.95)
        self.assertGreater(r['budget']['wallMol'], 0); self.assertTrue(r['budget']['pass'])

    def test_rejects_out_of_bounds_inputs(self):
        for bad in ({'radiusUm': -1}, {'radialCells': 3.5}, {'inletMode': 'bolus'}, {'diffusivityUm2PerS': float('nan')}, {'slugCentreUm': 1e5}):
            with self.assertRaises(bt.TransportError, msg=bad): bt.solve({**bt.defaults(), **bad})

    def test_particles_agree_with_continuum_within_monte_carlo_error(self):
        for preset in bt.PRESETS:
            r = bt.solve(preset['inputs'], frames=2, samples=40, particles=3000)
            s = r['particles']['summary']
            self.assertTrue(s['consistent'], (preset['id'], s))

    def test_particles_reproducible_with_seed(self):
        a = bt.solve(bt.PRESETS[0]['inputs'], frames=2, samples=10, particles=500)['particles']['summary']
        b = bt.solve(bt.PRESETS[0]['inputs'], frames=2, samples=10, particles=500)['particles']['summary']
        self.assertEqual(a, b)

    def test_run_action_is_json_and_carries_record(self):
        r = bt.dispatch(None, 'blood_transport_run', {'inputs': bt.PRESETS[1]['inputs'], 'evidence': 'D'})
        text = json.dumps(r, allow_nan=False)
        self.assertLess(len(text), 2_000_000)
        rec = r['record']
        self.assertEqual(rec['evidence']['category'], 'D'); self.assertIn('not validated human circulation', rec['evidence']['statement'])
        self.assertEqual(len(rec['reproducibility']['contentSha256']), 64)
        self.assertTrue(any('hematocrit' in a.lower() for a in rec['assumptions']))
        with self.assertRaises(ValueError): bt.dispatch(None, 'blood_transport_run', {'inputs': {'radiusUm': 0}})


class WiringTests(unittest.TestCase):
    def test_actions_are_routed_allowlisted_and_bundled(self):
        main = (ROOT / 'src-tauri/src/main.rs').read_text()
        conf = json.loads((ROOT / 'src-tauri/tauri.conf.json').read_text())['bundle']['resources']
        worker = (ROOT / 'scientific/worker.py').read_text()
        self.assertIn('blood_transport_actions.ACTIONS', worker)
        for a in blood_transport_actions.ACTIONS: self.assertIn('"' + a + '"', main)
        for f in ('blood_transport.py', 'blood_transport_actions.py'): self.assertIn('../scientific/' + f, conf)

    def test_actions_module_has_no_numeric_imports(self):
        self.assertNotIn('import numpy', (ROOT / 'scientific/blood_transport_actions.py').read_text())


if __name__ == '__main__':
    unittest.main()
