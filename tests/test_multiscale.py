import pathlib, subprocess, sys, tempfile, types, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import multiscale, multiscale_demos as demos, multiscale_kernel as K, multiscale_units as U


class UnitTests(unittest.TestCase):
    def test_conversions_and_refusals(self):
        self.assertAlmostEqual(U.convert(4.5, 'g/dL', 'g/L'), 45.0)
        self.assertAlmostEqual(U.convert(1, 'mol/m3', 'uM'), 1000.0)
        self.assertAlmostEqual(U.molar_from_mass_concentration(40, 'g/L', 66472.2, 'uM')[0], 601.757, places=2)
        self.assertAlmostEqual(U.count_rate_to_mass_rate(U.AVOGADRO / 86400, 'molecule/s', 100.0)[0], 100.0)
        for a, b in (('nM', 'molecule'), ('g', 'L'), ('1/s', 'day')):
            with self.assertRaises(U.UnitError):
                U.convert(1, a, b)

    def test_literature_parameters_require_a_source(self):
        with self.assertRaises(K.CouplingError):
            K.Param('x', 1.0, '1/s', 'literature', 'no source given')
        with self.assertRaises(U.UnitError):
            K.Param('x', 1.0, 'furlong', 'hypothetical')


class ChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d5 = demos.run('demo5', seed=3)
        cls.d8 = demos.run('demo8', seed=3)

    def test_reference_mrna_translates_to_uniprot(self):
        ident = demos.reference_identity()
        self.assertTrue(ident['translationMatchesUniProt'])
        self.assertEqual(ident['senseCodons'], 609)

    def test_every_numerical_check_passes(self):
        for r in (self.d5, self.d8):
            self.assertTrue(r['checks'] and all(c['passed'] for c in r['checks']), [c for c in r['checks'] if not c['passed']])

    def test_transfers_preserve_units(self):
        t = {x['to']: x for x in self.d8['transfers']}
        mm = demos.REF['protein']['matureAverageMassDa']
        cap = t['capillary.plasmaAlbuminMolar']
        self.assertAlmostEqual(cap['converted'], cap['value'] / mm * 1000, places=12)  # g/L ÷ g/mol = mol/L; ×1000 → mol/m³
        self.assertAlmostEqual(t['binding.albuminMolar']['converted'], t['binding.albuminMolar']['value'] * 1000)

    def test_trace_reaches_literature_sources(self):
        tr = self.d8['traces']['body.plasmaAlbumin']
        names = {p['name']: p for p in tr['parameters']}
        self.assertEqual(names['halfTime']['source']['doi'], '10.2147/IJGM.S102819')
        up = tr['upstream'][0]
        self.assertEqual(up['output'], 'cell.secretionRatePerCell')
        self.assertEqual(up['upstream'][0]['output'], 'translation.proteinRatePerMRNA')

    def test_calibration_reveals_infeasible_default_and_calibrated_scenario_matches(self):
        c = self.d8['calibration']
        self.assertFalse(c['feasibleAtCurrentCopies'])
        self.assertGreater(c['minimumCopiesAtMaximalCurrent'], 1000)
        r = demos.run('demo8', {'cell.mrnaCopies': c['requiredCopiesAtSimulatedRate']}, seed=3)
        # The cell stage runs 8 h = 16 secretion half-times, i.e. within 2·10⁻⁵ of steady state.
        self.assertLess(abs(r['results']['body']['outputs']['synthesisGPerDay'] - 10.5) / 10.5, 1e-4)

    def test_uncertainty_is_seeded_and_causal(self):
        a = demos.run('demo5', seed=5, samples=10)['uncertainty']
        b = demos.run('demo5', seed=5, samples=10)['uncertainty']
        self.assertEqual(a['values'], b['values'])
        sens = demos.run('demo8', seed=5, samples=10)['uncertainty']['sensitivity']['body.plasmaAlbumin']
        self.assertFalse(any(s['parameter'].startswith(('binding.', 'capillary.')) for s in sens))


class ActionTests(unittest.TestCase):
    def test_run_save_and_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = types.SimpleNamespace(root=pathlib.Path(tmp))
            r = multiscale.dispatch(svc, 'multiscale_run', {'demo': 'demo5', 'seed': 2, 'label': 'baseline'})
            rows = multiscale.dispatch(svc, 'multiscale_runs', {})
            self.assertEqual(rows[0]['id'], r['id'])
            self.assertTrue(rows[0]['passed'])
            again = multiscale.dispatch(svc, 'multiscale_record', {'id': r['id']})
            self.assertEqual(again['sha256'], r['sha256'])
            with self.assertRaises(ValueError):
                multiscale.dispatch(svc, 'multiscale_run', {'demo': 'nope'})

    def test_worker_routes_without_scientific_stack(self):
        code = ("import sys,builtins;real=builtins.__import__\n"
                "def guard(name,*a,**k):\n"
                "    if name.split('.')[0] in ('numpy','scipy'): raise ImportError('blocked '+name)\n"
                "    return real(name,*a,**k)\n"
                "builtins.__import__=guard;sys.path.insert(0,sys.argv[1]);import worker;print('multiscale_run' in worker.ACTIONS)")
        r = subprocess.run([sys.executable, '-B', '-c', code, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific')], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ['True'], r.stderr[-800:])


if __name__ == '__main__':
    unittest.main()
