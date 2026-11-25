"""Virtual light-pulse experiment: dataset integrity, numerical checks of the integrator, the held-out benchmark and saved runs."""
import json, math, pathlib, sys, tempfile, types, unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import numpy as np
import light_pulse as lp

FIT = None


def fit():
    global FIT
    if FIT is None:
        FIT = lp.train()
    return FIT


class Dataset(unittest.TestCase):
    def test_schedules_and_split_cover_the_dataset_once(self):
        d = lp.dataset(); ids = [s['id'] for s in d['schedules']]
        self.assertEqual(len(ids), 20)
        roles = [i for r in lp.SPLIT.values() for i in r]
        self.assertEqual(sorted(roles), sorted(ids))                    # every schedule has exactly one role
        self.assertFalse(set(lp.SPLIT['train']) & set(lp.SPLIT['heldOut']))
        self.assertEqual(d['source']['doi'], '10.15252/msb.20167456'); self.assertEqual(len(d['source']['archiveSha256']), 64)

    def test_points_and_programs(self):
        d = lp.dataset()
        for s in d['schedules']:
            self.assertEqual(s['inconsistentWells'], 0)
            for r in s['replicates']:
                self.assertEqual(len(r['points']), 24)
                self.assertTrue(all(p['fl'] > 0 and float(p['t']).is_integer() for p in r['points']))
        on = d['byId']['step-on-5']; off = d['byId']['step-off-5']
        self.assertEqual(lp.well_light(on, 100)[[0, 379, 380, 479]].tolist(), [0, 0, 5, 5])     # dark, then 100 min of light before harvest
        self.assertEqual(lp.well_light(off, 100)[[0, 379, 380, 479]].tolist(), [5, 5, 0, 0])


class Numerics(unittest.TestCase):
    THETA = {'k1': 0.02, 'k2': 0.001, 'kdr': 0.002, 'kg': 0.017, 'b': 2000.0, 'A': 1e5, 'n': 2.0, 'K': 0.9, 'kmat': 0.05}

    def test_integrator_matches_scipy(self):
        from scipy.integrate import solve_ivp
        th = self.THETA; km = lp.ASSUMED['km']['value']
        prog = {'pre': 0.0, 'steps': [[0, 0.0], [30, 5.0], [120, 0.0], [200, 1.0], [260, 0.0]]}
        t = np.arange(0, 400.1, 0.1); light = lp.program_values(prog, t[:-1] + 0.05)[None, :]
        got = lp.integrate(th, light, 0.1, record=True)[0]

        def rhs(tt, y):
            I = float(lp.program_values(prog, [tt])[0]); a, m, u, g = y
            T = float(lp.hill(th, np.array(a)))
            return [th['k1'] * I * (1 - a) - (th['k2'] * I + th['kdr'] + th['kg']) * a, km * (T - m), (th['kmat'] + th['kg']) * (m - u), th['kg'] * (u - g)]
        y = [0.0, th['b'], th['b'], th['b']]; ref = [th['b']]; edges = [0, 30, 120, 200, 260, 400]
        for a, b in zip(edges, edges[1:]):                              # integrate between discontinuities
            sol = solve_ivp(rhs, (a + 1e-9, b), y, method='LSODA', rtol=1e-10, atol=1e-10, t_eval=np.arange(a + 10, b + 1e-9, 10)); y = sol.y[:, -1]; ref += sol.y[3].tolist()
        mine = got['g'][0][::100]
        self.assertLess(np.max(np.abs(mine - np.array(ref)) / np.array(ref)), 1e-4)

    def test_steady_state_and_bounds(self):
        th = self.THETA
        for I in (0.0, 0.3, 5.0, 20.0):
            tr = lp.integrate(th, np.full((1, 3000), I), 1.0, record=True)[0]
            a_ss = th['k1'] * I / ((th['k1'] + th['k2']) * I + th['kdr'] + th['kg'])
            self.assertAlmostEqual(tr['a'][0, -1], a_ss, places=9)
            self.assertAlmostEqual(tr['g'][0, -1] / float(lp.hill(th, np.array(a_ss))), 1.0, places=6)      # every stage has unit gain
            self.assertTrue(0 <= tr['a'].min() and tr['a'].max() <= 1 and tr['g'].min() > 0)

    def test_dark_stays_at_baseline_and_recovery_is_dilution_limited(self):
        th = self.THETA
        self.assertTrue(np.allclose(lp.integrate(th, np.zeros((1, 480)), 1.0, record=True)[0]['g'], th['b']))
        light = np.concatenate([np.full(2000, 20.0), np.zeros(600)])[None, :]
        g = lp.integrate(th, light, 1.0, record=True)[0]['g'][0][2000:]
        late = np.log((g[400:500] - th['b']) / (g[401:501] - th['b']))  # late decay rate → the slowest rate constant
        self.assertAlmostEqual(float(late.mean()), min(th['kg'], th['kdr'] + th['kg']), delta=5e-4)

    def test_vectorised_parameters_match_scalar(self):
        xs = np.log([[p[3] for p in lp.PARAMS], [p[3] * 1.3 for p in lp.PARAMS]])
        light = np.tile(np.concatenate([np.zeros(100), np.full(200, 2.0)]), (2, 1))
        both = lp.integrate(lp.stack(xs), light)
        for i in range(2):
            self.assertAlmostEqual(both[i], lp.integrate(lp._theta(xs[i]), light[i:i + 1])[0], places=6)

    def test_sbml_agrees_with_the_integrator(self):
        th = self.THETA; prog = lp.pulses_to_program([{'start': 20, 'duration': 40, 'intensity': 3.0}, {'start': 100, 'duration': 10, 'intensity': 20.0}])
        t = np.arange(0, 240.1, 0.1); g = lp.integrate(th, lp.program_values(prog, t[:-1] + 0.05)[None, :], 0.1, record=True)[0]['g'][0]
        c = lp.solver_check(th, prog, 240.0, t, g)
        self.assertTrue(c['passed'], c); self.assertLess(c['value']['maxRelativeDifference'], 1e-3)

    def test_programs_are_validated(self):
        ok = lp._program({'pre': 0, 'steps': [[0, 0], [10, 5]]})
        self.assertEqual(ok['steps'], [[0.0, 0.0], [10.0, 5.0]])
        for bad in ({'steps': []}, {'steps': [[5, 1]]}, {'steps': [[0, 1], [0, 2]]}, {'steps': [[0, 25]]}, {'steps': [[0, -1]]}, {'steps': [[0, 1], [10.05, 2]]}):
            with self.assertRaises(lp.PulseError):
                lp._program(bad)
        with self.assertRaises(lp.PulseError):
            lp.pulses_to_program([{'start': 10, 'duration': 30, 'intensity': 1}, {'start': 20, 'duration': 30, 'intensity': 1}])


class Benchmark(unittest.TestCase):
    def test_fit_is_reproducible_and_converged(self):
        m = fit()['mechanistic']
        self.assertLess(m['rmseLog10'], 0.07)
        self.assertLess(max(m['startCosts']) - min(m['startCosts']), 1e-3 * min(m['startCosts']) + 1e-6)     # every start reaches the same optimum
        again = lp.fit_mechanistic(*lp.points_of(lp.SPLIT['train'])[:2], starts=1)
        self.assertTrue(np.allclose(again['x'], m['x'], atol=1e-3))
        self.assertGreaterEqual(len(m['ensemble']['x']), 50)

    def test_fitted_growth_rate_is_close_to_the_measured_one(self):
        kg = fit()['mechanistic']['theta']['kg']
        self.assertLess(abs(kg / lp.MEASURED['kg'] - 1), 0.15)          # measured doubling time was not used in the fit

    def test_held_out_accuracy_and_baseline(self):
        b = lp.benchmark(fit()); held = b['summary']['heldOut']
        self.assertLess(held['mechanistic'], 0.10); self.assertGreater(held['baseline'] / held['mechanistic'], 4)
        self.assertGreater(held['learned'], held['mechanistic'])
        self.assertEqual(b['selected'], 'mechanistic'); self.assertTrue(b['gate']['passed'])
        dyn = next(r for r in b['schedules']['heldOut'] if r['id'] == 'dynamic-green')
        self.assertLess(dyn['models']['mechanistic']['rmseLog10'], 1.5 * dyn['replicateSdLog10'])     # as close as two runs are to each other
        f = dyn['models']['mechanistic']['features']
        self.assertLess(abs(f['amplitude']['relativeError']), 0.15); self.assertLess(abs(f['timeToPeakMin']['error']), 30)

    def test_green_only_chain_still_fails_with_red_light(self):
        """The known failure of version 1, kept as a regression case."""
        b = lp.benchmark(fit())
        bad = next(r for r in b['schedules']['mixedColour'] if r['id'] == 'dynamic-green-red-perturbation')
        self.assertGreater(bad['models']['green']['rmseLog10'], 0.3)
        self.assertGreater(bad['models']['green']['features']['amplitude']['relativeError'], 0.5)
        self.assertIsNotNone(bad['second'])
        self.assertTrue(b['regression']['failureReproduced'])

    def test_red_input_repairs_the_failure_on_held_out_mixed_schedules(self):
        b = lp.benchmark(fit()); reg = b['regression']
        self.assertTrue(reg['improved'])
        self.assertLess(reg['withRedRmseLog10'], 0.5 * reg['greenOnlyRmseLog10'])
        for r in b['schedules']['mixedColour']:
            self.assertLess(r['models']['mechanistic']['rmseLog10'], lp.GATE['rmseLog10'], r['id'])
            self.assertLess(abs(r['models']['mechanistic']['features']['amplitude']['relativeError']), 0.25, r['id'])
        self.assertEqual(b['stages']['finalTest']['status'], 'retrospective')
        self.assertFalse(b['stages']['finalTest']['untouched'])

    def test_green_results_are_unchanged_by_the_other_wavelengths(self):
        b = lp.benchmark(fit())
        for role in ('train', 'heldOut'):
            self.assertAlmostEqual(b['summary'][role]['mechanistic'], b['summary'][role]['green'], places=12)
        self.assertAlmostEqual(10 ** b['summary']['heldOut']['mechanistic'], 1.17, places=2)

    def test_calibration_selection_and_test_use_separate_data(self):
        """Channels are fitted on action spectra only; the final-test schedules come from other experimental runs."""
        ch = fit()['channels']; cal_runs = {r for c in ch.values() for r in c['runs']}
        test_runs = {rep['run'] for sid in lp.FINAL_TEST for rep in lp.dataset()['byId'][sid]['replicates']}
        self.assertFalse(cal_runs & test_runs)
        self.assertEqual(ch['660-LS']['structure'], 'off'); self.assertEqual(ch['660-LS']['k1'], 0.0)
        self.assertEqual(ch['380-SB']['structure'], 'on')
        self.assertLess(ch['660-LS']['cvRmseLog10']['off'], 0.5 * ch['660-LS']['cvRmseLog10']['none'])
        self.assertTrue(fit()['calibrationCheck']['passed'])

    def test_uv_schedule_is_predicted_and_its_amplitude_miss_is_reported(self):
        b = lp.benchmark(fit()); uv = b['schedules']['otherColour'][0]
        self.assertLess(uv['models']['mechanistic']['rmseLog10'], 0.5 * uv['models']['green']['rmseLog10'])
        miss = next(f for f in b['stages']['finalTest']['failures'] if f['id'] == 'dynamic-uv')
        self.assertIn('amplitude', miss['why'])
        self.assertEqual(b['unsupported'], [])

    def test_published_model_is_reproduced_from_its_distributed_parameters(self):
        b = lp.benchmark(fit())
        self.assertLess(b['summary']['heldOut']['published'], 0.15)
        self.assertLess(b['summary']['mixedColour']['published'], 0.15)

    def test_held_out_schedules_never_reach_the_fit(self):
        _, _, who = lp.points_of(lp.SPLIT['train'])
        self.assertFalse({w[0] for w in who} & (set(lp.SPLIT['heldOut']) | set(lp.FINAL_TEST)))


class Experiments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.svc = types.SimpleNamespace(root=cls.tmp.name)
        d = pathlib.Path(cls.tmp.name) / 'light_pulse'; d.mkdir()
        f = fit(); lp._fit_file(cls.tmp.name).write_text(json.dumps({'fit': f, 'benchmark': lp.benchmark(f)}, default=float))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_run_saves_reopens_and_reproduces(self):
        prog = lp.pulses_to_program([{'start': 30, 'duration': 90, 'intensity': 5.0}])
        r = lp.simulate(self.svc, {'program': prog, 'durationMin': 360, 'label': 'pulse', 'samples': 20})
        self.assertTrue(r['passed'], r['checks']); self.assertEqual(r['model'], 'mechanistic')
        kinds = [e['kind'] for e in r['record']['outputs']['events']]
        self.assertEqual(kinds, ['light', 'regulator', 'transcription', 'reporter', 'light', 'peak', 'recovery'])
        times = [e['time'] for e in r['record']['outputs']['events']]; self.assertEqual(times, sorted(times))
        peak = max(r['series']['reporter']); self.assertAlmostEqual(peak, r['record']['outputs']['reporterPeak'], delta=peak * 1e-3)   # plotted series and recorded outputs agree
        self.assertTrue(all(lo <= m <= hi for lo, m, hi in zip(r['series']['reporterLow'], r['series']['reporterMedian'], r['series']['reporterHigh'])))
        again = lp.run_get(self.svc, {'id': r['id']})
        self.assertTrue(again['reproduced']['identical']); self.assertEqual(again['series'], r['series'])
        self.assertIn(r['id'], [x['id'] for x in lp.runs(self.svc)])

    def test_compare_reports_changed_inputs_and_outcomes(self):
        a = lp.simulate(self.svc, {'program': lp.pulses_to_program([{'start': 30, 'duration': 60, 'intensity': 5.0}]), 'samples': 0})
        b = lp.simulate(self.svc, {'program': lp.pulses_to_program([{'start': 30, 'duration': 120, 'intensity': 5.0}]), 'samples': 0, 'parent': a['id']})
        c = lp.compare(self.svc, {'baseline': a['id'], 'variant': b['id']})
        self.assertEqual([x['what'] for x in c['changed']], ['program']); self.assertFalse(c['identicalDynamics'])
        amp = next(o for o in c['outcomes'] if o['key'] == 'amplitude'); self.assertGreater(amp['change'], 0)
        same = lp.compare(self.svc, {'baseline': a['id'], 'variant': a['id']}); self.assertTrue(same['identicalDynamics'])

    def test_other_contexts_and_bad_inputs_are_refused(self):
        prog = lp.pulses_to_program([{'start': 30, 'duration': 60, 'intensity': 5.0}])
        with self.assertRaises(lp.PulseError):
            lp.simulate(self.svc, {'program': prog, 'context': 'hela-jrc_hela-2'})
        with self.assertRaises(lp.PulseError):
            lp.simulate(self.svc, {'program': prog, 'durationMin': 5})

    def test_sweep_is_monotonic_in_pulse_duration(self):
        s = lp.sweep(self.svc, {'vary': 'duration', 'values': [5, 30, 120]})
        peaks = [r['peak'] for r in s['rows']]; self.assertEqual(peaks, sorted(peaks))

    def test_closed_loop_needs_the_gate_and_beats_open_loop(self):
        c = lp.control(self.svc, {'target': 30000})
        self.assertLess(c['closed']['relativeErrorSecondHalf'], c['open']['relativeErrorSecondHalf'])
        self.assertLess(c['closed']['relativeErrorSecondHalf'], 0.05)



class State(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.svc = types.SimpleNamespace(root=cls.tmp.name)
        cls.res = lp.simulate(cls.svc, {'schedule': 'dynamic-green-red-perturbation', 'preMin': 480, 'samples': 10})

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_mixed_schedule_runs_as_recorded_and_passes_every_check(self):
        r = self.res
        self.assertIn('light:660-LS', r['series']); self.assertTrue(r['passed'])
        self.assertEqual({c['name'] for c in r['checks']}, {'Independent solver', 'Bounds', 'Step size', 'Molecule totals', 'One reporter count'})
        self.assertEqual(r['record']['state']['version'], lp.STATE['version'])
        self.assertEqual(r['record']['state']['phi']['mapping'], 'relative')

    def test_fluorescence_and_molecules_are_one_series(self):
        r = self.res; phi = lp.PHI['value']
        np.testing.assert_allclose(np.array(r['series']['mature']) * phi, r['series']['reporter'], rtol=1e-12)

    def test_particles_carry_the_molecule_numbers(self):
        q = lp.particles(self.svc, {'id': self.res['id']})
        self.assertTrue(q['passed'])
        for sp in q['species']:
            diff = np.abs(np.array(sp['particles']) * sp['weight'] - np.array(sp['molecules']))
            self.assertLessEqual(diff.max(), sp['weight'] / 2 + 1e-9)
        mature = next(s for s in q['species'] if s['key'] == 'mature')
        np.testing.assert_allclose(np.array(mature['molecules']) * q['phi']['value'], q['fluorescence'], rtol=1e-12)
        n = len(q['owner'])
        self.assertTrue(all(len(f) == 3 * n for f in q['frames'])); self.assertEqual(len(q['frames']), len(q['time']))
        present = [n - len(a) for a in q['absent']]
        self.assertEqual(present, [sum(sp['particles'][i] for sp in q['species']) for i in range(len(q['time']))])
        again = lp.particles(self.svc, {'id': self.res['id']})
        self.assertEqual(again['frames'][5], q['frames'][5])

    def test_green_only_model_ignores_red_and_says_so(self):
        g = lp.simulate(self.svc, {'schedule': 'dynamic-green-red-perturbation', 'preMin': 480, 'samples': 0, 'model': 'green', 'dryRun': True})
        self.assertNotIn('light:660-LS', g['series'])
        self.assertTrue(any('does not take' in w for w in g['warnings']))
        self.assertGreater(max(g['series']['reporter']), 1.5 * max(self.res['series']['reporter']))

    def test_predictor_without_states_has_no_particles(self):
        with self.assertRaises(lp.PulseError):
            lp.particles(self.svc, {'program': {'pre': 0, 'steps': [[0, 5]]}, 'model': 'learned'})

    def test_uncalibrated_led_is_refused(self):
        with self.assertRaises(lp.PulseError):
            lp.simulate(self.svc, {'program': {'pre': 0, 'steps': [[0, 5]]}, 'other': {'laser-999': {'pre': 0, 'steps': [[0, 5]]}}, 'dryRun': True})


class Registry(unittest.TestCase):
    def test_contexts_declare_identity_geometry_measurements_models_and_validation(self):
        import virtual_cell_registry as VR
        with tempfile.TemporaryDirectory() as tmp:
            r = VR.cell_contexts(tmp)
        by = {c['id']: c for c in r['contexts']}
        self.assertEqual(set(by), {'hela-jrc_hela-2', 'CVCL_0027', lp.CONTEXT, 'K562'})
        for c in r['contexts']:
            for key in ('species', 'cellType', 'state', 'geometry', 'measurements', 'models', 'experiments', 'validation', 'qualified'):
                self.assertIn(key, c)
            self.assertEqual(set(c['experiments']), set(r['experiments']))
            for e in c['experiments'].values():
                self.assertEqual(bool(e['missing']), not e['supported'])        # an unavailable experiment always says what is missing
        self.assertEqual(by['hela-jrc_hela-2']['role'], 'EM specimen'); self.assertEqual(by['CVCL_0027']['role'], 'Molecular baseline')
        self.assertEqual(by['hela-jrc_hela-2']['geometry']['kind'], 'measured_em'); self.assertEqual(by[lp.CONTEXT]['geometry']['kind'], 'illustrative'); self.assertEqual(by['CVCL_0027']['geometry']['kind'], 'none')
        self.assertEqual(by[lp.CONTEXT]['qualified'], ['light_pulse', 'spatial_diffusion'])       # usable without measured 3D geometry
        self.assertFalse(by['hela-jrc_hela-2']['experiments']['light_pulse']['supported'])
        self.assertIn('different cell lines', r['identity'])

    def test_saved_runs_read_through_the_shared_result_adapter(self):
        import virtual_cell_results as VRS
        with tempfile.TemporaryDirectory() as tmp:
            svc = types.SimpleNamespace(root=tmp); (pathlib.Path(tmp) / 'light_pulse').mkdir()
            f = fit(); lp._fit_file(tmp).write_text(json.dumps({'fit': f, 'benchmark': lp.benchmark(f)}, default=float))
            r = lp.simulate(svc, {'program': lp.pulses_to_program([{'start': 30, 'duration': 60, 'intensity': 5.0}]), 'samples': 0, 'label': 'adapter'})
            rows = VRS.listing(tmp); self.assertEqual([(x['source'], x['id'], x['integrity']) for x in rows], [('light_pulse', r['id'], True)])
            got = VRS.get(tmp, 'light_pulse', r['id'])
            self.assertTrue(got['integrity']['match']); self.assertEqual(got['open'], {'workspace': 'light_pulse', 'run': r['id'], 'context': lp.CONTEXT})
            self.assertEqual([e['kind'] for e in got['timeline']['events']][0], 'light'); self.assertIn('E. coli', got['context'])
            self.assertIn('features.amplitude', [x['id'] for x in got['scalars']])

if __name__ == '__main__':
    unittest.main()
