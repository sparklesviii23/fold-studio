"""HeLa EGF–ERK experiment: dataset, numerics, split discipline, held-out scoring, failures, runs, particles, import."""
import json, math, pathlib, sys, tempfile, types, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import numpy as np
import hela_erk as he
import cell_state

_FIT = None


def fit():
    global _FIT
    if _FIT is None:
        _FIT = he.train()
    return _FIT


_BENCH = None


def bench():
    global _BENCH
    if _BENCH is None:
        _BENCH = he.benchmark(fit())
    return _BENCH


class Dataset(unittest.TestCase):
    def test_fixture_declares_source_readout_and_resolution(self):
        d = he.dataset()
        self.assertEqual(d['source']['licence'], 'CC BY'); self.assertEqual(d['readout']['key'], 'cn')
        self.assertIn('0.74', d['readout']['resolution']); self.assertEqual(d['specimen']['cellLine'], 'HeLa')
        self.assertIn('not the cell of the electron-microscopy volume', d['specimen']['note'])

    def test_every_cell_has_sixteen_positive_frames(self):
        n = 0
        for u in he.dataset()['byId'].values():
            for c in u['cells']:
                self.assertEqual(len(c['t']), 16); self.assertEqual(len(c['cn']), 16); self.assertGreater(min(c['cn']), 0); n += 1
        self.assertGreater(n, 500)

    def test_archive_without_the_reporter_is_listed_not_used(self):
        bad = [s for s in he.dataset()['series'] if not s['usable']]
        self.assertEqual(len(bad), 1); self.assertIn('No ERK-KTR channel', bad[0]['reason'])

    def test_split_roles_do_not_overlap_and_test_is_another_dish(self):
        roles = [set(v) for v in he.SPLIT.values()]
        self.assertFalse(roles[0] & roles[1] or roles[0] & roles[2] or roles[1] & roles[2])
        dish = lambda ids: {he.dataset()['byId'][u]['dish'] for u in ids}
        self.assertFalse(dish(he.SPLIT['test']) & (dish(he.SPLIT['calibration']) | dish(he.SPLIT['selection'])))
        self.assertFalse(set(he.unexplained_units()) & set().union(*roles))


class Numerics(unittest.TestCase):
    def test_no_egf_means_no_response(self):
        c = he.constants({'kc': 0.5, 'G': 0.3}); t, B, E, F = he.pathway(c, 30, 0.0, 5.0, 2)
        self.assertEqual(float(np.abs(E).max()), 0.0)

    def test_receptor_reaches_its_closed_form_steady_state(self):
        c = he.constants({'kc': 0.5, 'G': 0.3}); L = 10 / he.EGF_KDA
        t, B, E, F = he.pathway(c, 120, 10.0, 0.0, 1)
        self.assertAlmostEqual(B[-1], c['kon'] * L / (c['kon'] * L + c['koff'] + c['kint']), places=6)

    def test_reporter_ratio_starts_at_rest_and_rises_with_erk(self):
        c = he.constants({'kc': 0.5, 'G': 0.3}); t, B, E, F = he.pathway(c, 30, 10.0, 5.0, 1)
        P, C = he.reporter(c, E, [0.5], 1.0)
        self.assertAlmostEqual(C[0, 0], 0.5); self.assertTrue(np.all(C[0, :int(5 / he.DT)] == 0.5)); self.assertGreater(C[0, -1], 0.55)
        self.assertAlmostEqual(he.cn_eq(0.0, 0.5, c['rho'], c['v']), 0.5); self.assertAlmostEqual(he.cn_eq(1.0, 0.5, c['rho'], c['v']), 0.5 * c['rho'])

    def test_inhibition_removes_the_response_in_simulation(self):
        c = he.constants({'kc': 0.5, 'G': 0.3})
        self.assertLess(he.pathway(c, 30, 10.0, 5.0, 2, mek=1.0)[2].max(), 1e-12)
        self.assertLess(he.pathway(c, 30, 10.0, 5.0, 2, egfr=1.0)[2].max(), 1e-12)
        self.assertLess(he.pathway(c, 30, 0.05, 5.0, 2)[2].max(), he.pathway(c, 30, 10.0, 5.0, 2)[2].max())

    def test_onset_is_recovered_from_synthetic_cells(self):
        c = he.constants(fit()['theta']); st = fit()['structure']; t_obs = np.tile(np.arange(16.0), (40, 1)); base = np.full(40, 0.5)
        cn = he.predict_unit(c, st, t_obs, base, 6.2)
        o = he.onset(c, st, t_obs, cn)
        self.assertTrue(o['detected']); self.assertAlmostEqual(o['t0'], 6.2, delta=0.11)
        flat = he.onset(c, st, t_obs, np.full((40, 16), 0.5))
        self.assertFalse(flat['detected'])


class Benchmark(unittest.TestCase):
    def test_held_out_dish_beats_no_response_and_misses_are_listed(self):
        b = bench(); t = b['summary']['test']
        self.assertLess(t['mechanistic']['pooledCellRmseRelative'], 0.75 * t['static']['pooledCellRmseRelative'])
        self.assertLess(t['mechanistic']['rmseOfMeanRelative'], 0.5 * t['static']['rmseOfMeanRelative'])
        self.assertLess(t['mechanistic']['pooledCellRmseRelative'], t['nominal']['pooledCellRmseRelative'])
        self.assertTrue(b['gate']['passed']); self.assertEqual(b['status'], 'retrospective'); self.assertIn('not blind', b['statement'])

    def test_mechanistic_chain_is_not_claimed_better_than_the_empirical_mean(self):
        """With one dose the mechanism adds nothing over the mean response; that tie must be reported, not hidden."""
        t = bench()['summary']['test']
        ratio = t['mechanistic']['pooledCellRmseRelative'] / t['template']['pooledCellRmseRelative']
        self.assertGreater(ratio, 0.9)
        if ratio >= 1:
            self.assertTrue(any('no better than the empirical mean response' in f['why'] for f in bench()['failures'] if f['role'] == 'test'))

    def test_interval_coverage_is_reported_per_role(self):
        c = bench()['intervalCoverage']
        self.assertGreater(c['test']['coverage'], 0.75); self.assertLess(c['test']['coverage'], 1.0); self.assertGreater(c['test']['total'], 500)

    def test_non_responding_dishes_are_failures_not_a_dose_holdout(self):
        b = bench(); un = b['schedules']['unexplained']
        self.assertGreater(sum(r['cells'] for r in un), 350)
        self.assertTrue(all(not r['onset']['detected'] for r in un))
        ids = {f['id'] for f in b['failures'] if 'no response measured where one is predicted' in f['why']}
        self.assertEqual(ids, {r['id'] for r in un})
        self.assertGreater(b['summary']['unexplained']['mechanistic']['pooledCellRmseRelative'], b['summary']['unexplained']['static']['pooledCellRmseRelative'])
        self.assertEqual(b['holdouts']['dose']['status'], 'blocked'); self.assertEqual(b['holdouts']['intervention']['status'], 'blocked'); self.assertIn('PMC5401947', b['holdouts']['dose']['reason'])

    def test_peak_and_recovery_are_marked_unsupported(self):
        f = bench()['schedules']['test'][0]['models']['mechanistic']['features']
        self.assertFalse(f['timeToPeakMin']['supported']); self.assertFalse(f['halfRecoveryMin']['supported']); self.assertTrue(f['amplitude']['supported'])

    def test_structure_is_chosen_on_the_selection_series_only(self):
        f = fit(); sel = f['selection']['rmseOfMeanRelative']
        self.assertEqual(set(sel), {s['key'] for s in he.STRUCTURES})
        self.assertLessEqual(sel[f['structure']['key']], (1 + he.SELECT_MARGIN) * min(sel.values()) + 1e-12)
        self.assertEqual(set(f['fit']['onsets']), set(he.SPLIT['calibration']))


class Experiments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.svc = types.SimpleNamespace(root=cls.tmp.name)
        he.fitted = (lambda orig: lambda service: orig(service))(he.fitted)
        d = he._fit_file(cls.tmp.name); d.parent.mkdir(parents=True, exist_ok=True); d.write_text(json.dumps({'fit': fit(), 'benchmark': bench()}, default=float))
        cls.res = he.simulate(cls.svc, {'series': he.SPLIT['test'][0]})

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_measured_series_run_passes_every_check_and_labels_evidence(self):
        r = self.res
        self.assertTrue(r['passed'], [c for c in r['checks'] if not c['passed']])
        self.assertEqual({c['name'] for c in r['checks']}, {'Independent solver', 'Bounds', 'Step size', 'Reporter conserved', 'One reporter split'})
        self.assertEqual(r['evidence']['erk'], 'simulated'); self.assertEqual(r['evidence']['nuclear'], 'inferred'); self.assertEqual(r['measured']['measured']['evidence'], 'measured')
        self.assertEqual(r['record']['specimens']['geometryReference']['context'], he.GEOMETRY); self.assertIn('0.74', str(r['record']['resolution']['pixelUm']))
        self.assertEqual(r['record']['state']['interface'], 'fold-studio.cell-state/' + str(cell_state.SCHEMA_VERSION))

    def test_nuclear_and_cytoplasmic_fractions_give_the_readout(self):
        s = self.res['series']; v = he.EM_REFERENCE['volumeRatio']
        np.testing.assert_allclose(np.array(s['nuclear']) + np.array(s['cytoplasmic']), 1.0, atol=1e-12)
        np.testing.assert_allclose(np.array(s['cytoplasmic']) / (np.array(s['nuclear']) * v), s['cn'], rtol=1e-10)
        self.assertLess(s['nuclear'][-1], s['nuclear'][0])

    def test_saved_run_reopens_identically_and_compares_on_common_scales(self):
        again = he.run_get(self.svc, {'id': self.res['id']})
        self.assertTrue(again['reproduced']['identical'])
        v = he.simulate(self.svc, {'egfNgPerMl': 10, 'mekInhibition': 0.8, 'durationMin': 60, 'label': 'MEK inhibited'}); b = he.simulate(self.svc, {'egfNgPerMl': 10, 'durationMin': 60})
        self.assertTrue(any('simulation, not a tested prediction' in w for w in v['warnings'])); self.assertTrue(any('16 minutes' in w for w in b['warnings']))
        c = he.compare(self.svc, {'baseline': b['id'], 'variant': v['id']})
        self.assertEqual([x['what'] for x in c['changed'] if x['affectsDynamics']], ['mekInhibition'])
        self.assertLess(c['outcomes'][0]['variant'], c['outcomes'][0]['baseline'])
        self.assertLessEqual(c['scales']['cn'][0], min(c['baseline']['series']['cn'])); self.assertGreaterEqual(c['scales']['cn'][1], max(c['baseline']['series']['cn']))
        self.assertIn(self.res['id'], [r['id'] for r in he.runs(self.svc)])

    def test_out_of_range_inputs_are_refused(self):
        for bad in ({'egfNgPerMl': 1e4}, {'mekInhibition': 1.5}, {'durationMin': 1}, {'samples': 10 ** 6}):
            with self.assertRaises(he.ErkError):
                he.simulate(self.svc, {**bad, 'dryRun': True})

    def test_particles_need_the_reference_cell_and_say_so(self):
        q = he.particles(self.svc, {'id': self.res['id']})
        self.assertFalse(q['available']); self.assertIn('not installed', q['reason'])

    def test_particles_in_a_reference_geometry_carry_the_split(self):
        import cell_em
        cls = np.zeros((12, 12, 24), np.uint8); cls[2:10, 2:10, 2:22] = cell_em.KEYS['cytosol']; cls[4:8, 4:8, 6:14] = cell_em.KEYS['nucleus']
        orig = cell_em.geometry; cell_em.geometry = lambda root, context: (cls, (0.5, 0.5, 0.5), {'sizeUm': [12, 6, 6]}, 'test')
        try:
            q = he.particles(self.svc, {'id': self.res['id']})
        finally:
            cell_em.geometry = orig
        self.assertTrue(q['available']); self.assertTrue(q['passed'], [c for c in q['checks'] if not c['passed']])
        n, c = (np.array(sp['molecules']) for sp in q['species'])
        np.testing.assert_allclose(n + c, he.DISPLAY['copies']); np.testing.assert_allclose(c / (n * he.EM_REFERENCE['volumeRatio']), q['readout'], rtol=1e-10)
        self.assertIn('not one of the live cells', q['evidence']['positions'])

    def test_imported_condition_unblocks_and_scores_a_holdout(self):
        """Synthetic cells, labelled synthetic: exercises the path a real dose or inhibitor series would take."""
        c = he.constants(fit()['theta']); st = fit()['structure']; rng = np.random.default_rng(3); t_obs = np.tile(np.arange(16.0), (30, 1)); base = rng.uniform(0.4, 0.6, 30)
        cn = he.predict_unit(c, st, t_obs, base, 5.0, 1.0, {'egf': 10.0, 'mek': 0.7, 'egfr': 0.0}) * (1 + 0.02 * rng.standard_normal((30, 16)))
        r = he.import_series(self.svc, {'id': 'synthetic-mek-0.7', 'label': 'Synthetic MEK inhibition', 'mekInhibition': 0.7, 'evidence': 'synthetic', 'cells': [{'t': t_obs[i].tolist(), 'cn': cn[i].tolist()} for i in range(30)]})
        self.assertEqual(r['evidence'], 'synthetic'); self.assertEqual(r['holdouts']['intervention']['status'], 'scored'); self.assertEqual(r['holdouts']['dose']['status'], 'blocked')
        self.assertLess(r['score']['models']['mechanistic']['pooledRmseRelative'], r['score']['models']['template']['pooledRmseRelative'])
        with self.assertRaises(he.ErkError):
            he.import_series(self.svc, {'id': 'x', 'cells': []})
        (pathlib.Path(self.tmp.name) / 'hela_erk' / 'imports' / 'synthetic-mek-0.7.json').unlink()

    def test_runs_read_through_the_shared_result_adapter(self):
        import virtual_cell_results as vr
        got = vr.get(self.tmp.name, 'hela_erk', self.res['id'])
        self.assertTrue(got['integrity']['match']); self.assertEqual(got['open']['workspace'], 'hela_erk'); self.assertIn('geometry reference only', got['context'])


if __name__ == '__main__':
    unittest.main()
