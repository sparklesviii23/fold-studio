"""Synergy reference models and signature refitting against known answers (synthetic method tests)."""
import pathlib, sys, unittest
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import synergy as Y
import mutational_signatures as M


class SynergyTests(unittest.TestCase):
    def test_sham_combination_is_loewe_additive(self):
        p = np.array([1e-6, 1.3, 0.9])                       # EC50 1 µM, slope 1.3, Emax 0.9
        bliss = []
        for a, b in ((2e-7, 3e-7), (1e-6, 5e-7), (3e-6, 1e-6)):
            truth = Y._hill(a + b, *p)                       # a drug combined with itself: dose additivity holds exactly
            self.assertAlmostEqual(Y._loewe_expected(a, b, p, p), truth, places=5)
            ea, eb = Y._hill(a, *p), Y._hill(b, *p); bliss.append(truth - (ea + eb - ea * eb))
        # Known pitfall: Bliss is not neutral for a sham pair; its sign changes with dose when the Hill slope ≠ 1.
        self.assertTrue(max(bliss) > 0.005 and min(bliss) < -0.005)
        flat = np.array([1e-6, 1.0, 1.0])                    # slope 1: Bliss is conservative for a sham pair
        self.assertLessEqual(Y._hill(2e-6, *flat) - (2 * Y._hill(1e-6, *flat) - Y._hill(1e-6, *flat) ** 2), 1e-12)

    def test_loewe_undefined_beyond_single_agent_reach(self):
        strong, weak = np.array([1e-6, 1.0, 0.9]), np.array([1e-6, 1.0, 0.3])
        self.assertTrue(np.isnan(Y._loewe_expected(1e-5, 1e-6, strong, weak)))   # drug A alone already exceeds what B can reach
        self.assertFalse(np.isnan(Y._loewe_expected(1e-8, 1e-8, strong, weak)))

    def test_nci_expected_growth_rule(self):
        self.assertAlmostEqual(Y.nci_expected(80, 50), 40)
        self.assertAlmostEqual(Y.nci_expected(120, 50), 50)    # single-agent growth truncated at 100 %
        self.assertAlmostEqual(Y.nci_expected(-10, 50), -10)   # net kill: the lower growth


class SignatureTests(unittest.TestCase):
    def test_refit_recovers_planted_exposures(self):
        rng = np.random.default_rng(0)
        sigs = rng.dirichlet(np.full(96, 0.3), 8).T
        names = [f'SBS{i}' for i in (1, 2, 4, 5, 13, 18, 40, 92)]
        x = rng.multinomial(600, 0.7 * sigs[:, 2] + 0.3 * sigs[:, 0])
        ex, cos = M.fit_one(x, sigs, names, boot=50)
        got = {e['signature']: e for e in ex}
        self.assertGreater(cos, 0.95)
        self.assertAlmostEqual(got['SBS4']['fraction'], 0.7, delta=0.08)
        self.assertLessEqual(got['SBS4']['ci'][0], 0.7); self.assertGreaterEqual(got['SBS4']['ci'][1], 0.62)
        self.assertTrue(set(got) <= {'SBS4', 'SBS1', 'SBS5', 'SBS40'})

    def test_types_are_the_96_pyrimidine_contexts(self):
        self.assertEqual(len(set(M.TYPES)), 96)
        self.assertTrue(all(t[2] in 'CT' for t in M.TYPES))


if __name__ == '__main__':
    unittest.main()
