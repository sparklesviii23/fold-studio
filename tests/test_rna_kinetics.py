import json, pathlib, subprocess, sys, tempfile, types, unittest
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
try:
    import RNA  # noqa: F401
    HAVE_RNA = True
except ImportError:
    HAVE_RNA = False
import rna_kinetics as K


@unittest.skipUnless(HAVE_RNA, 'ViennaRNA is not importable in this interpreter')
class LandscapeTests(unittest.TestCase):
    SEQ = 'GGGAAACCCAGGGAAACCCU'

    @classmethod
    def setUpClass(cls):
        cls.L = K.enumerate_landscape(cls.SEQ)
        cls.edges, _ = K.graph(cls.L['structures'])
        cls.Q = K.generator(cls.L['energies'], cls.edges, cls.L['kT'])

    def test_enumeration_matches_partition_function(self):
        E, kT = self.L['energies'], self.L['kT']
        G = -kT * np.log(np.exp(-(E - E.min()) / kT).sum()) + E.min()
        self.assertAlmostEqual(G, self.L['ensembleEnergy'], places=4)

    def test_generator_rows_sum_to_zero_and_boltzmann_is_stationary(self):
        pi = K.boltzmann(self.L['energies'], self.L['kT'])
        self.assertLess(np.abs(np.asarray(self.Q.sum(1))).max(), 1e-12)
        self.assertLess(np.abs(self.Q.T @ pi).max(), 1e-12)

    def test_master_equation_relaxes_to_equilibrium(self):
        pi = K.boltzmann(self.L['energies'], self.L['kT'])
        sol = K.Solution(self.Q, pi)
        p0 = np.zeros(len(pi)); p0[self.L['structures'].index('.' * len(self.SEQ))] = 1
        late = sol.at(p0, np.array([max(sol.relaxation_times(1)) * 40]))[0]
        self.assertLess(0.5 * np.abs(late - pi).sum(), 1e-4)

    def test_saddle_is_minimax(self):
        E = self.L['energies']
        root = K.basins(E, self.edges, len(E))
        mins = sorted(np.unique(root))[:3]
        for (a, b), s in K.saddles(E, self.edges, mins).items():
            self.assertGreaterEqual(s, max(E[a], E[b]))


@unittest.skipUnless(HAVE_RNA, 'ViennaRNA is not importable in this interpreter')
class DemoTests(unittest.TestCase):
    def test_demo_checks_and_record(self):
        import rna_kinetics_actions_impl as A
        with tempfile.TemporaryDirectory() as tmp:
            svc = types.SimpleNamespace(root=pathlib.Path(tmp))
            r = A.dispatch(svc, 'rna_kinetics_run', {'sequence': 'GGGAAACCCAGGGAAACCCU', 'seed': 2})
            json.dumps(r)
            self.assertTrue(all(c['passed'] for c in r['checks']), [c for c in r['checks'] if not c['passed']])
            self.assertEqual(A.dispatch(svc, 'rna_kinetics_runs', {})[0]['id'], r['recordId'])
            self.assertEqual(A.dispatch(svc, 'rna_kinetics_record', {'id': r['recordId']})['sha256'], r['sha256'])
            for bad in ('ACGUX', 'A' * 40):
                with self.assertRaises(ValueError):
                    A.dispatch(svc, 'rna_kinetics_run', {'sequence': bad})


class RoutingTests(unittest.TestCase):
    def test_worker_routes_without_scientific_stack(self):
        code = ("import sys,builtins;real=builtins.__import__\n"
                "def guard(name,*a,**k):\n"
                "    if name.split('.')[0] in ('numpy','scipy','RNA'): raise ImportError('blocked '+name)\n"
                "    return real(name,*a,**k)\n"
                "builtins.__import__=guard;sys.path.insert(0,sys.argv[1]);import worker;print('rna_kinetics_run' in worker.ACTIONS)")
        r = subprocess.run([sys.executable, '-B', '-c', code, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific')], capture_output=True, text=True)
        self.assertEqual(r.stdout.strip().splitlines()[-1:], ['True'], r.stderr[-800:])


if __name__ == '__main__':
    unittest.main()
