"""Clonal populations: interval maths, the selection model's limits, and drivers looking more clonal than long passengers."""
import pathlib, sys, types, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import clonal as C

ROOT = pathlib.Path(__file__).resolve().parents[2] / 'validation' / 'bindcraft-fab-amme-native'


class ClonalTests(unittest.TestCase):
    def test_wilson_and_projection(self):
        lo, hi = C._wilson(50, 100); self.assertLess(lo, 0.5); self.assertGreater(hi, 0.5)
        no_drug = C.projection(kill=0.0, r_s=0.03, r_r=0.02)
        self.assertIsNone(no_drug['timeToResistantMajority'])                     # a fitter sensitive clone keeps the majority without drug
        drug = C.projection(kill=0.06)
        self.assertIsNotNone(drug['timeToResistantMajority']); self.assertGreater(drug['timeToResistantMajority'], 30)

    @unittest.skipUnless((ROOT / 'oncology' / 'cbioportal' / 'luad_tcga_pan_can_atlas_2018').is_dir(), 'LUAD cohort not installed')
    def test_drivers_more_clonal_than_ttn(self):
        r = {g['gene']: g for g in C.observed(types.SimpleNamespace(root=str(ROOT)), 'luad_tcga_pan_can_atlas_2018')['genes']}
        self.assertGreater(r['TP53']['clonal'], r['TTN']['clonal']); self.assertGreater(r['KRAS']['clonal'], r['TTN']['clonal'])


if __name__ == '__main__':
    unittest.main()
