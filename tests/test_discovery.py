"""Demo L on installed data: a known driver must recover its known dependency and drug (positive control)."""
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import discovery as X

ROOT = pathlib.Path(__file__).resolve().parents[2] / 'validation' / 'bindcraft-fab-amme-native'


@unittest.skipUnless((ROOT / 'oncology' / 'depmap').is_dir() and (ROOT / 'oncology' / 'gdsc').is_dir(), 'DepMap and GDSC not installed')
class DiscoveryTests(unittest.TestCase):
    def test_braf_positive_control(self):
        r = X.run(str(ROOT), {'gene': 'BRAF', 'lineage': 'Skin'}, log=lambda m: None)
        self.assertEqual(r['kind'], 'hotspot')
        self.assertIn('BRAF', r['candidates'])                                     # oncogene addiction
        drugs = {row[0]: row for row in r['steps'][2]['rows']}
        self.assertIn('Dabrafenib', drugs); self.assertLess(drugs['Dabrafenib'][2], 0)   # mutant lines more sensitive
        synth = {row[0]: row for row in r['steps'][5]['rows']}
        self.assertNotEqual(synth['BRAF'][2], '—')                                 # a compound targeting the candidate was found
        self.assertEqual([s['n'] for s in r['steps']], [1, 2, 3, 4, 5, 6])


if __name__ == '__main__':
    unittest.main()
