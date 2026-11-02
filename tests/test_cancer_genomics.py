"""Survival and association methods against known answers (method tests on simulated data, not findings)."""
import math, pathlib, sys, unittest
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import cancer_genomics as G


class SurvivalMethodTests(unittest.TestCase):
    def test_kaplan_meier_hand_calculation(self):
        c = G._km(np.array([1.0, 2.0, 2.0, 3.0, 4.0]), np.array([1, 1, 0, 1, 0]))
        # S(1)=4/5, S(2)=4/5·3/4=0.6, S(3)=0.6·1/2=0.3 (one censored at 2, one at 4)
        np.testing.assert_allclose([p[1] for p in c], [1.0, 0.8, 0.6, 0.3])

    def test_cox_recovers_simulated_hazard_ratio(self):
        rng = np.random.default_rng(3); n = 4000
        g = rng.integers(0, 2, n).astype(float); age = rng.normal(0, 1, n)
        t = rng.exponential(1 / (0.1 * np.exp(math.log(2.0) * g + 0.3 * age)))
        cens = rng.exponential(15, n); e = (t <= cens).astype(int); t = np.minimum(t, cens)
        b, se = G._cox(t, e, np.c_[g, age])
        self.assertAlmostEqual(math.exp(b[0]), 2.0, delta=0.15)
        self.assertAlmostEqual(b[1], 0.3, delta=0.06)
        self.assertTrue(np.all(se > 0))

    def test_logrank_null_and_effect(self):
        rng = np.random.default_rng(4); n = 600
        g = rng.integers(0, 2, n).astype(bool)
        t0 = rng.exponential(10, n); self.assertGreater(G._logrank(t0, np.ones(n, int), g)[1], 0.01)
        t1 = rng.exponential(np.where(g, 4, 10)); self.assertLess(G._logrank(t1, np.ones(n, int), g)[1], 1e-6)

    def test_bh(self):
        np.testing.assert_allclose(G._bh(np.array([0.01, 0.04, 0.03, 0.2])), [0.04, 0.0533333, 0.0533333, 0.2], rtol=1e-5)


if __name__ == '__main__':
    unittest.main()
