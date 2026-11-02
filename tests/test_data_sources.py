"""New data sources: GDC conversion rules, Sanger Project Score replication, tree baselines (method checks on installed data)."""
import pathlib, sys, types, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import gdc

ROOT = pathlib.Path(__file__).resolve().parents[2] / 'validation' / 'bindcraft-fab-amme-native'


class GDCTests(unittest.TestCase):
    def test_study_ids_and_consequences(self):
        self.assertEqual(gdc.study_id('TCGA-LUAD'), 'gdc_tcga_luad')
        self.assertEqual(gdc.study_id('CPTAC-3'), 'gdc_cptac_3')
        self.assertEqual(gdc.SO['stop_gained'], 'Nonsense_Mutation'); self.assertEqual(gdc.SO['synonymous_variant'], 'Silent')   # silent is excluded downstream


@unittest.skipUnless((ROOT / 'oncology' / 'sanger' / 'manifest.json').is_file(), 'Sanger Project Score not installed')
class SangerTests(unittest.TestCase):
    def test_braf_dependencies_replicate_and_control_does_not(self):
        import oncology_data as D, sanger_score as SS
        rel = D.Release(types.SimpleNamespace(root=str(ROOT)))
        r = SS.replicate(str(ROOT), rel, 'BRAF', ['BRAF', 'MAP2K1', 'GAPDH'])
        self.assertTrue(r['genes']['BRAF']['replicates']); self.assertTrue(r['genes']['MAP2K1']['replicates'])
        self.assertFalse(r['genes']['GAPDH']['replicates'])                # common essential: no mutant-specific difference


class TreeBaselineTests(unittest.TestCase):
    def test_trees_fit_when_sklearn_present(self):
        try:
            import sklearn  # noqa: F401
        except ImportError:
            self.skipTest('scikit-learn only in the science runtime')
        import numpy as np, drug_response as R
        rng = np.random.default_rng(0); X = rng.normal(size=(300, 20)); y = X[:, 0] * 2 + rng.normal(scale=0.5, size=300)
        for kind in ('forest', 'boosting'):
            p = R._tree(kind, X[:200], y[:200]).predict(X[200:])
            self.assertGreater(np.corrcoef(p, y[200:])[0, 1], 0.7, kind)


if __name__ == '__main__':
    unittest.main()
