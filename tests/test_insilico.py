"""In-silico runs: each demo's own analysis code must recover what the simulator planted (method tests, not findings)."""
import pathlib, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import insilico as I


def checks(r):
    return {c['name']: c['passed'] for c in r['checks']}


class InSilicoTests(unittest.TestCase):
    def test_atlas_recovers_planted_dependencies_and_removes_confounding(self):
        r = I.atlas(I.validate('atlas', {'seed': 3}))
        self.assertTrue(all(v for v in checks(r).values() if v is not None), r['checks'])

    def test_synergy_directions_and_sham(self):
        for kind, want in (('synergy', 'synergy'), ('antagonism', 'antagonism'), ('none', 'consistent with no interaction')):
            r = I.synergy(I.validate('synergy', {'interaction': kind, 'plates': 4, 'seed': 2}))
            bliss = next(row for row in r['tables'][0]['rows'] if row[0] == 'Bliss')
            self.assertEqual(bliss[4], want, kind)
        r = I.synergy(I.validate('synergy', {'interaction': 'sham', 'plates': 4, 'noise': 2, 'seed': 2}))
        self.assertAlmostEqual(r['truth']['noiseFreeScores']['Loewe'], 0.0, places=3)      # a drug with itself is Loewe-additive by definition

    def test_genomics_planted_associations(self):
        r = I.genomics(I.validate('genomics', {'patients': 800, 'seed': 4}))
        c = checks(r)
        for k in ('KRAS–EGFR mutual exclusivity detected', 'KRAS–STK11 co-occurrence detected', 'MYC amplification raises MYC expression',
                  'STK11 hazard ratio interval covers the planted value', 'Age-confounded ATM: no effect after adjusting for age'):
            self.assertTrue(c[k], k)

    def test_drug_null_compound_has_no_skill_and_split_is_grouped(self):
        r = I.drugs(I.validate('drugs', {'lines': 240, 'seed': 5}))
        c = checks(r)
        self.assertTrue(c['Grouped split keeps sister lines on one side'])
        self.assertTrue(c['No skill on the null compound'])
        self.assertTrue(c['Ridge beats the lineage-mean baseline'])

    def test_validation_rejects_out_of_range(self):
        with self.assertRaises(ValueError):
            I.validate('atlas', {'lineages': 99})
        with self.assertRaises(ValueError):
            I.validate('synergy', {'interaction': 'magic'})
        with self.assertRaises(ValueError):
            I.validate('nope', {})

    def test_signatures_smoking_signal(self):
        root = pathlib.Path(__file__).resolve().parents[2] / 'validation' / 'bindcraft-fab-amme-native'
        if not (root / 'oncology' / 'signatures' / 'COSMIC_v3.4_SBS_GRCh37_exome.txt').is_file():
            self.skipTest('COSMIC reference not installed')
        r = I.signatures(I.validate('signatures', {'samples': 60, 'snvs': 800, 'seed': 6}), str(root))
        self.assertTrue(checks(r)['SBS4 higher in smokers (Demo B smoking check, same test)'])


if __name__ == '__main__':
    unittest.main()
