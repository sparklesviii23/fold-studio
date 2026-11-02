"""Spatial statistics against known answers on synthetic Visium-like hexagonal grids (method tests, not findings)."""
import pathlib, sys, unittest
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import spatial_tumor as S


def grid(n=30):
    rows, cols = [], []
    for r in range(n):
        for c in range(r % 2, 2 * n, 2):            # Visium staggering: columns step by 2, offset on odd rows
            rows.append(r); cols.append(c)
    return np.array(rows), np.array(cols)


class SpatialStatTests(unittest.TestCase):
    def test_hex_grid_interior_spots_have_six_neighbours(self):
        r, c = grid(); nb = S.hex_neighbours(r, c)
        interior = [len(n) for (rr, cc, n) in zip(r, c, nb) if 2 <= rr <= 27 and 3 <= cc <= 56]
        self.assertEqual(set(interior), {6})

    def test_morans_i_gradient_vs_random(self):
        r, c = grid(); nb = S.hex_neighbours(r, c); rng = np.random.default_rng(0)
        self.assertGreater(S.morans_i(c.astype(float), nb), 0.9)            # smooth gradient: strong positive autocorrelation
        rand = [S.morans_i(rng.normal(size=len(r)), nb) for _ in range(50)]
        self.assertLess(abs(np.mean(rand)), 0.02)                           # E[I] = −1/(n−1) ≈ 0
        Z = np.c_[c.astype(float), rng.normal(size=len(r))]
        np.testing.assert_allclose(S.morans_matrix(Z, nb)[0], S.morans_i(c.astype(float), nb), rtol=1e-9)

    def test_neighbourhood_enrichment_detects_segregated_regions(self):
        r, c = grid(); nb = S.hex_neighbours(r, c)
        labels = np.where(c < 30, 'tumor', 'stroma'); rng = np.random.default_rng(1)
        cats, z, _ = S.neighbourhood_enrichment(list(labels), nb, 100, rng)
        self.assertGreater(z[cats.index('tumor'), cats.index('tumor')], 10)
        self.assertLess(z[cats.index('tumor'), cats.index('stroma')], -10)
        mixed = list(rng.permutation(labels)); cats, z, _ = S.neighbourhood_enrichment(mixed, nb, 100, rng)
        self.assertLess(np.abs(z).max(), 4)


class SimulatorTests(unittest.TestCase):
    """The in-silico section must plant what it says: exclusion puts T cells at the rim, infiltration spreads them evenly."""
    def setUp(self):
        try:
            import scipy  # noqa: F401
        except ImportError:
            self.skipTest('scipy not available')
        import spatial_sim
        self.sim = spatial_sim

    def test_phenotypes_and_null_genes(self):
        for ph in ('excluded', 'infiltrated'):
            xy, row, col, F, comp, genes, counts, tum, truth = self.sim.simulate(ph, 3, 4)
            self.assertTrue(0 < tum.sum() < len(tum))
            np.testing.assert_allclose(F.sum(1), 1)
            t = F[:, 1]; ratio = t[tum].mean() / t[(~tum) & (comp != 'Tumor stroma fibrous')].mean()
            (self.assertLess if ph == 'excluded' else self.assertGreater)(ratio, 0.5)
        lib = counts.sum(1); null = counts[:, [genes.index(g) for g in truth['nullGenes']]].sum(1) / lib
        self.assertLess(abs(np.corrcoef(null, tum)[0, 1]), 0.1)        # pattern-free genes carry no tissue signal
        with self.assertRaises(ValueError):
            self.sim.simulate('bogus')

    def test_tumor_label_excludes_tumor_stroma(self):
        self.assertTrue(S.is_tumor('Tumor cells')); self.assertTrue(S.is_tumor('malignant cell'))
        self.assertFalse(S.is_tumor('Tumor stroma fibrous')); self.assertFalse(S.is_tumor('non-tumor'))


if __name__ == '__main__':
    unittest.main()
