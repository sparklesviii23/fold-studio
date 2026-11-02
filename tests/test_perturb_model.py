"""Demo J method checks: the linear model recovers planted low-rank effects for an unseen perturbation; scoring excludes targets."""
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import numpy as np
import perturb_model as PM


class PerturbModelTests(unittest.TestCase):
    def test_linear_model_on_planted_structure(self):
        rng = np.random.default_rng(0); n, K = 300, 4; G0 = rng.normal(size=(n, K)); W0 = rng.normal(size=(K, K))
        genes = [f'g{i}' for i in range(n)]; gi = {g: i for i, g in enumerate(genes)}; perts = [[g] for g in genes[:120]]
        Y = G0 @ W0 @ np.vstack([G0[gi[p[0]]] for p in perts]).T                     # effects follow the model's own assumption
        fit = PM.linear_fit(Y[:, :100], perts[:100], gi, K=4, lam=1e-6)
        pred = fit(perts[100:]); r = [PM._pearson(pred[:, j], Y[:, 100 + j]) for j in range(20)]
        self.assertGreater(np.mean(r), 0.95)

    def test_targets_excluded_from_scoring(self):
        obs = np.zeros(50); obs[3] = 10.0; obs[10:20] = np.linspace(-1, 1, 10)
        s = PM._score(obs.copy(), obs, exclude=[3]); self.assertAlmostEqual(s['pearson'], 1.0)
        s2 = PM._score(np.zeros(50), obs, exclude=[3]); self.assertLess(s2['mse'], 1.0)   # the target's +10 would dominate if scored


if __name__ == '__main__':
    unittest.main()
