import json, math, pathlib, sys, tempfile, types, unittest, zipfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import numpy as np
import mechanistic, mechanistic_demos as demos, mechanistic_library as lib, mechanistic_sbml as sbml, mechanistic_sim as sim

FIX = pathlib.Path(__file__).resolve().parents[1] / 'fixtures' / 'biomodels'


def l3(reactions, species='<species id="A" compartment="c" initialConcentration="10" hasOnlySubstanceUnits="false" boundaryCondition="false" constant="false"/>',
       params='<parameter id="k" value="0.5" constant="true"/>', extra=''):
    return ('<sbml xmlns="http://www.sbml.org/sbml/level3/version2/core" level="3" version="2"><model id="t">'
            f'{extra}<listOfCompartments><compartment id="c" size="2" constant="true"/></listOfCompartments><listOfSpecies>{species}</listOfSpecies>'
            f'<listOfParameters>{params}</listOfParameters><listOfReactions>{reactions}</listOfReactions></model></sbml>')


DECAY = ('<reaction id="R" reversible="false"><listOfReactants><speciesReference species="A" stoichiometry="1" constant="true"/></listOfReactants>'
         '<kineticLaw><math xmlns="http://www.w3.org/1998/Math/MathML"><apply><times/><ci>c</ci><ci>k</ci><ci>A</ci></apply></math></kineticLaw></reaction>')


class SBMLTests(unittest.TestCase):
    def test_first_order_decay_matches_exponential(self):
        m = sbml.Model(l3(DECAY))
        r = sim.simulate(m, 10, 101, 'LSODA', 1e-10, 1e-12)
        exact = 10 * np.exp(-0.5 * np.asarray(r['time']))
        self.assertLess(np.max(np.abs(np.asarray(r['series']['A']) - exact)), 1e-7)
        self.assertTrue(r['diagnostics']['reliable'])

    def test_mathml_operators_functions_and_enotation(self):
        law = ('<kineticLaw><math xmlns="http://www.w3.org/1998/Math/MathML"><apply><times/><ci>c</ci><apply><ci>f</ci><ci>A</ci></apply>'
               '<piecewise><piece><cn type="e-notation">1<sep/>-1</cn><apply><gt/><csymbol definitionURL="http://www.sbml.org/sbml/symbols/time">t</csymbol><cn>100</cn></apply></piece>'
               '<otherwise><apply><root/><degree><cn>2</cn></degree><cn>4</cn></apply></otherwise></piecewise></apply></math></kineticLaw>')
        fd = ('<listOfFunctionDefinitions><functionDefinition id="f"><math xmlns="http://www.w3.org/1998/Math/MathML"><lambda><bvar><ci>x</ci></bvar>'
              '<apply><divide/><ci>x</ci><apply><plus/><cn>1</cn><ci>x</ci></apply></apply></lambda></math></functionDefinition></listOfFunctionDefinitions>')
        m = sbml.Model(l3(DECAY.split('<kineticLaw>')[0] + law + '</reaction>', extra=fd))
        y, p = m.prepare()
        # rate = 2 * (10/11) * 2 (before t = 100); amount derivative = -rate
        self.assertAlmostEqual(m.rhs(0.0, y, p)[0], -2 * (10 / 11) * 2)
        self.assertAlmostEqual(m.rhs(200.0, y, p)[0], -2 * (10 / 11) * 0.1)

    def test_unsupported_features_block_execution(self):
        # Events are supported; event priorities (simultaneous-event ordering) still are not.
        event = ('<listOfEvents><event useValuesFromTriggerTime="true"><trigger initialValue="true" persistent="true"><math xmlns="http://www.w3.org/1998/Math/MathML"><true/></math></trigger>'
                 '<priority><math xmlns="http://www.w3.org/1998/Math/MathML"><cn>1</cn></math></priority></event></listOfEvents>')
        text = l3(DECAY).replace('</listOfReactions>', '</listOfReactions>' + event)
        m = sbml.Model(text)
        self.assertFalse(m.executable)
        with self.assertRaises(sim.SimulationError):
            sim.simulate(m, 1)

    def test_event_reset_matches_exact_solution(self):
        ev = ('<listOfEvents><event id="reset" useValuesFromTriggerTime="true"><trigger initialValue="true" persistent="true"><math xmlns="http://www.w3.org/1998/Math/MathML">'
              '<apply><geq/><csymbol encoding="text" definitionURL="http://www.sbml.org/sbml/symbols/time">t</csymbol><cn>1</cn></apply></math></trigger>'
              '<listOfEventAssignments><eventAssignment variable="A"><math xmlns="http://www.w3.org/1998/Math/MathML"><cn>5</cn></math></eventAssignment></listOfEventAssignments></event></listOfEvents>')
        m = sbml.Model(l3(DECAY).replace('</listOfReactions>', '</listOfReactions>' + ev))
        self.assertTrue(m.executable)
        r = sim.simulate(m, 2, 201); t = np.array(r['time']); a = np.array(r['series']['A'])
        k, a0 = 0.5, 10.0                                   # concentration (amount 20 in a size-2 compartment)
        exact = np.where(t < 1, a0 * np.exp(-k * t), 5 * np.exp(-k * (t - 1)))
        self.assertLess(np.max(np.abs(a - exact)[np.abs(t - 1) > 1e-9]), 1e-6)

    def test_delay_matches_method_of_steps_solution(self):
        # dx/dt = -x(t - 1), x = 1 for t <= 0: x = 1 - t on [0, 1], 1 - t + (t - 1)^2 / 2 on [1, 2]
        text = ('<?xml version="1.0"?><sbml xmlns="http://www.sbml.org/sbml/level3/version1/core" level="3" version="1"><model id="d"><listOfCompartments><compartment id="c" size="1" constant="true"/></listOfCompartments>'
                '<listOfSpecies><species id="x" compartment="c" initialConcentration="1" hasOnlySubstanceUnits="false" boundaryCondition="false" constant="false"/></listOfSpecies>'
                '<listOfParameters><parameter id="tau" value="1" constant="true"/></listOfParameters><listOfRules><rateRule variable="x"><math xmlns="http://www.w3.org/1998/Math/MathML">'
                '<apply><minus/><apply><csymbol encoding="text" definitionURL="http://www.sbml.org/sbml/symbols/delay">delay</csymbol><ci>x</ci><ci>tau</ci></apply></apply></math></rateRule></listOfRules></model></sbml>')
        r = sim.simulate(sbml.Model(text), 2, 201); t = np.array(r['time']); x = np.array(r['series']['x'])
        self.assertLess(np.max(np.abs(x - np.where(t <= 1, 1 - t, 1 - t + (t - 1) ** 2 / 2))), 1e-8)

    def test_overrides_and_invalid_input(self):
        m = sbml.Model(l3(DECAY))
        r = sim.simulate(m, 2, 3, overrides={'k': 0.0}, initial={'A': 4.0}, check=False)
        self.assertAlmostEqual(r['series']['A'][-1], 4.0)
        with self.assertRaises(sbml.SBMLError):
            m.prepare({'nope': 1})
        with self.assertRaises(sbml.SBMLError):
            m.prepare(initial={'A': -1})
        with self.assertRaises(sbml.SBMLError):
            sbml.Model('<not-sbml/>')

    def test_written_sbml_round_trips_overrides(self):
        m = sbml.Model((FIX / 'BIOMD0000000010.xml').read_text())
        again = sbml.Model(m.write({'J0.Ki': 25.0}, {'MAPK': 200.0}))
        self.assertEqual(again.parameter_vector_value('J0.Ki'), 25.0)
        self.assertEqual(again.prepare()[0][again.state_index['MAPK']], 200.0)


class DemoTests(unittest.TestCase):
    def test_every_demonstration_passes_its_validation(self):
        for demo in demos.DEMOS:
            checks = demos.validate(demo)
            self.assertTrue(checks and all(c['passed'] for c in checks), (demo, [c for c in checks if not c['passed']]))

    def test_published_models_execute_unmodified(self):
        for mid in ('BIOMD0000000010', 'BIOMD0000000048'):
            m = sbml.Model((FIX / (mid + '.xml')).read_text())
            self.assertTrue(m.executable, m.unsupported)

    def test_composed_models_report_concentration_units(self):
        self.assertEqual(demos.load('enzyme').describe()['units'], {'substance': '10^-9 mole', 'time': 'second', 'volume': 'litre'})
        self.assertEqual(demos.load('turnover').describe()['units']['time'], 'hour')

    def test_unit_checking_rejects_wrong_units(self):
        net = demos.turnover_network()
        net['parameters'][0]['unit'] = 'nM_per_time'
        with self.assertRaises(lib.CompositionError):
            lib.compose(net)


class ExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = demos.load('turnover')

    def test_local_sensitivity_matches_analytic_coefficients(self):
        # Steady-state protein = k_tl·k_tx/(d_m·d_p): log-sensitivities +1, +1, −1, −1.
        r = sim.local_sensitivity(self.m, 4000, 'Protein', 'final')
        s = {c['name']: c['sensitivity'] for c in r['coefficients']}
        for name, want in (('k_tx', 1), ('k_tl', 1), ('d_m', -1), ('d_p', -1)):
            self.assertAlmostEqual(s[name], want, places=3)

    def test_uncertainty_is_reproducible_with_a_seed(self):
        ranges = [{'name': 'd_p', 'min': 0.01, 'max': 0.05, 'log': True}, {'name': 'k_tl', 'min': 20, 'max': 80}]
        a = sim.uncertainty(self.m, 200, ranges, 'Protein', samples=16, seed=7)
        b = sim.uncertainty(self.m, 200, ranges, 'Protein', samples=16, seed=7)
        self.assertEqual(a['readout'], b['readout'])
        self.assertEqual(a['sensitivity'][0]['name'], 'd_p')

    def test_scan_and_steady_state(self):
        r = sim.scan(self.m, 2000, {'name': 'k_tx', 'min': 1, 'max': 4, 'steps': 4}, 'mRNA', 'final')
        ratio = np.asarray(r['readout']) / np.asarray(r['values'])
        self.assertLess(np.ptp(ratio) / ratio.mean(), 1e-6)
        ss = sim.steady_state(self.m)
        self.assertTrue(ss['stable'])

    def test_fit_recovers_a_parameter_from_model_generated_points(self):
        truth = sim.simulate(self.m, 200, 11, overrides={'d_p': 0.03}, check=False)
        data = [{'time': t, 'output': 'Protein', 'value': v} for t, v in zip(truth['time'][1:], truth['series']['Protein'][1:])]
        r = sim.fit(self.m, data, [{'name': 'd_p', 'min': 1e-4, 'max': 1.0}])
        self.assertAlmostEqual(r['estimates'][0]['value'], 0.03, places=5)


class ActionTests(unittest.TestCase):
    def test_load_simulate_record_and_export_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = types.SimpleNamespace(root=pathlib.Path(tmp))
            loaded = mechanistic.dispatch(service, 'mech_load', {'source': 'demo', 'id': 'enzyme'})
            self.assertTrue(loaded['model']['executable'])
            r = mechanistic.dispatch(service, 'mech_simulate', {'key': loaded['key'], 'tEnd': 600, 'points': 31, 'initial': {'I': 500}})
            out = pathlib.Path(tmp) / 'run.omex'
            info = mechanistic.dispatch(service, 'mech_export', {'runId': r['runId'], 'path': str(out)})
            with zipfile.ZipFile(out) as z:
                self.assertEqual(set(z.namelist()), {'manifest.xml', 'model.xml', 'simulation.sedml', 'results.csv', 'record.json'})
                record = json.loads(z.read('record.json'))
                self.assertEqual(record['request']['initial'], {'I': 500})
                again = sbml.Model(z.read('model.xml').decode())
                self.assertEqual(again.prepare()[1][-1], 500.0)
            self.assertEqual(len(info['sha256']), 64)
            with self.assertRaises(ValueError):
                mechanistic.dispatch(service, 'mech_simulate', {'key': loaded['key'], 'tEnd': -1})


if __name__ == '__main__':
    unittest.main()


class IsolationTests(unittest.TestCase):
    def test_worker_imports_without_the_scientific_stack(self):
        # Isolated interpreters run worker.py without NumPy/SciPy; routing must not import the engine.
        import subprocess
        code = ("import sys,builtins;real=builtins.__import__\n"
                "def guard(name,*a,**k):\n"
                "    if name.split('.')[0] in ('numpy','scipy'): raise ImportError('blocked '+name)\n"
                "    return real(name,*a,**k)\n"
                "builtins.__import__=guard;sys.path.insert(0,sys.argv[1]);import worker;print('mech_simulate' in worker.ACTIONS)")
        r = subprocess.run([sys.executable, '-B', '-c', code, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific')], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ['True'], r.stderr[-800:])
