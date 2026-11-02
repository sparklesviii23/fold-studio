"""Demo I pathology pipeline on synthetic H&E-like images with known nuclei (method checks)."""
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import numpy as np
import pathology as P


def synthetic(seed=0):
    rng = np.random.default_rng(seed); H = W = 300; img = np.zeros((H, W, 3)) + [235, 190, 215]; gt = np.zeros((H, W), int); yy, xx = np.mgrid[:H, :W]
    for k, (cy, cx) in enumerate([(50, 50), (50, 68), (120, 200), (200, 80), (240, 240), (150, 150), (150, 166), (80, 250)], 1):   # two touching pairs
        m = (yy - cy) ** 2 + (xx - cx) ** 2 < 81; gt[m & (gt == 0)] = k; img[m] = [90, 60, 150]
    return np.clip(img + rng.normal(0, 6, img.shape), 0, 255).astype(np.uint8), gt


class PathologyTests(unittest.TestCase):
    def test_perfect_prediction_scores_one(self):
        _, gt = synthetic(); s = P.score(gt, gt)
        self.assertEqual((s['dice'], s['f1'], s['aji']), (1.0, 1.0, 1.0))

    def test_splitting_separates_touching_nuclei(self):
        img, gt = synthetic(); a = P.score(P.segment(img)[0], gt); b = P.score(P.segment(img, split=False)[0], gt)
        self.assertGreater(a['f1'], b['f1']); self.assertGreater(a['dice'], 0.95)

    def test_tiling_matches_whole_image(self):
        img, gt = synthetic(); whole = P.score(P.segment(img, tile=512)[0], gt); tiled = P.score(P.segment(img, tile=128, overlap=32)[0], gt)
        self.assertEqual(whole['nucleiFound'], tiled['nucleiFound']); self.assertAlmostEqual(whole['aji'], tiled['aji'], places=2)

    def test_ignored_region_is_not_scored(self):
        img, gt = synthetic(); lab = P.segment(img)[0]; ign = np.zeros_like(gt, bool); ign[:100, :100] = True
        self.assertLess(P.score(lab, gt, ign)['nucleiTrue'], P.score(lab, gt)['nucleiTrue'])


if __name__ == '__main__':
    unittest.main()
