"""Model comparison: paired bootstrap over patients detects a clearly worse model and calls equal models equal."""
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import numpy as np
import model_comparison as MC


class ModelComparisonTests(unittest.TestCase):
    def test_paired_bootstrap(self):
        rng = np.random.default_rng(0); y = rng.normal(size=400); pts = [f'p{i // 2}' for i in range(400)]
        good = y + rng.normal(scale=0.3, size=400); bad = y + rng.normal(scale=1.0, size=400); same = good + rng.normal(scale=1e-6, size=400)
        r = MC.drugs({'predictions': {'observed': y.tolist(), 'patient': pts, 'ridge': good.tolist(), 'noisy': bad.tolist(), 'copy': same.tolist()}, 'drug': {'name': 'test'}}, n_boot=500)
        calls = {c['model']: c['call'] for c in r['comparisons']}
        self.assertEqual(calls['noisy'], 'noisy worse than ridge'); self.assertEqual(calls['copy'], 'no clear difference')
        self.assertEqual(r['patients'], 200)                                         # bootstrap unit is the patient, not the line

    def test_signalling_models_agree_on_direction(self):
        s = MC.signalling()
        self.assertTrue(all(r['agreeDirection'] for r in s['rows']))


if __name__ == '__main__':
    unittest.main()
