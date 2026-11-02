"""Synthetic lethality on installed DepMap: demonstrated pairs must be recovered by the matching definition of loss."""
import pathlib, sys, types, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import synthetic_lethality as SL

ROOT = pathlib.Path(__file__).resolve().parents[2] / 'validation' / 'bindcraft-fab-amme-native'


@unittest.skipUnless((ROOT / 'oncology' / 'depmap').is_dir(), 'DepMap not installed')
class SyntheticLethalityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import oncology_data as D
        cls.rel = D.Release(types.SimpleNamespace(root=str(ROOT)))

    def test_reference_pairs_recovered(self):
        b = {(r['lost'], r['dependency']): r for r in SL.benchmark(str(ROOT), self.rel)['pairs']}
        self.assertTrue(b[('SMARCA4', 'SMARCA2')]['damaging']['recovered'])
        self.assertTrue(b[('ARID1A', 'ARID1B')]['damaging']['recovered'])
        self.assertTrue(b[('MTAP', 'PRMT5')]['expression']['recovered'])          # MTAP is lost by deletion, not mutation

    def test_labels_kept_apart(self):
        r = SL.loss_context(str(ROOT), self.rel, 'SMARCA4')
        top = r['hits'][0]
        self.assertEqual(top['gene'], 'SMARCA2'); self.assertTrue(top['label'].startswith('Experimentally demonstrated'))
        self.assertTrue(all(h['label'].split(' ')[0] in ('Experimentally', 'Predicted', 'Context-specific') for h in r['hits']))


if __name__ == '__main__':
    unittest.main()
