import json, math, pathlib, sys, tempfile, types, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import rna_lab, rna_lab_fold as fold, rna_lab_translate as tl


class FoldTests(unittest.TestCase):
    def test_validation_checks_pass(self):
        checks = rna_lab.validate_fold()
        self.assertTrue(all(c['passed'] for c in checks), [c for c in checks if not c['passed']])
        self.assertEqual(len(checks), 7 if fold.vienna_available() else 6)

    def test_evaluate_matches_mfe_and_hand_energy(self):
        b = fold.Builtin('GGGAAACCC')
        self.assertEqual(fold.to_dotbracket(b.mfe_pairs, 9), '(((...)))')
        # 5'GG/3'CC stacks twice (-3.3 each) + hairpin of 3 (+5.7) = -0.9 kcal/mol, no AU ends.
        self.assertAlmostEqual(b.mfe_energy, -0.9, places=9)
        self.assertAlmostEqual(fold.evaluate('GGGAAACCC', '(((...)))'), -0.9, places=9)

    def test_trna_reference_and_accuracy_fields(self):
        ref = rna_lab.reference()['trna_phe']
        self.assertEqual(len(ref['sequence']), 76)
        self.assertEqual(len(fold.pairs_of(ref['structure'])), 21)
        cif = (pathlib.Path(rna_lab.__file__).parent.parent / 'fixtures/nucleic-acids/1EHZ.cif').read_text()
        self.assertIn(ref['sequence'], cif)
        r = fold.analyse(ref['sequence'], 200, 1, ref['structure'], 'builtin')
        self.assertEqual(r['backend'], 'builtin-nn')
        acc = r['reference']['mfe']
        self.assertEqual(acc['truePositive'] + acc['falseNegative'], 21)
        self.assertAlmostEqual(acc['f1'], 2 * acc['sensitivity'] * acc['ppv'] / (acc['sensitivity'] + acc['ppv']), places=12)
        self.assertLessEqual(r['ensembleFreeEnergy'], r['mfe']['energy'])
        self.assertTrue(0 < r['mfeProbability'] <= 1)
        self.assertTrue(all(0 <= p <= 1 + 1e-9 for _, _, p in r['bpp']))
        self.assertTrue(all(-1e-9 <= u <= 1 for u in r['unpaired']))
        self.assertAlmostEqual(sum(s['frequency'] for s in r['alternativeStates']), 1.0, delta=0.2)

    def test_sampling_is_seeded(self):
        b = fold.Builtin('GGGCAAAGCCGCAAAGCAACCC')
        self.assertEqual(b.sample(50, 9), b.sample(50, 9))

    def test_input_validation(self):
        with self.assertRaises(ValueError): fold.clean('ACGX')
        with self.assertRaises(ValueError): fold.Builtin('A' * (fold.MAX_BUILTIN + 1))


@unittest.skipUnless(fold.vienna_available(), 'ViennaRNA is not importable in this interpreter')
class ViennaTests(unittest.TestCase):
    def test_tables_match_turner1999(self):
        import rna_lab_vienna
        self.assertEqual(rna_lab_vienna.table_check(), [])

    def test_same_model_in_vienna(self):
        import rna_lab_vienna
        w = rna_lab_vienna.model_check([rna_lab.reference()['trna_phe']['sequence'], 'GGGCAAAGCCGCAAAGCAACCC'])
        self.assertLess(max(w.values()), 1e-5)

    def test_vienna_backend_recovers_trna_cloverleaf(self):
        ref = rna_lab.reference()['trna_phe']
        r = fold.analyse(ref['sequence'], 100, 1, ref['structure'], 'viennarna')
        self.assertEqual(r['mfe']['structure'], ref['structure'])
        self.assertAlmostEqual(r['mfe']['energy'], ref['priorViennaReceipt']['mfeKcalMol'], places=4)
        self.assertAlmostEqual(r['ensembleFreeEnergy'], ref['priorViennaReceipt']['ensembleFreeEnergyKcalMol'], places=3)


class TranslateTests(unittest.TestCase):
    def test_validation_checks_pass(self):
        checks = rna_lab.validate_translate()
        self.assertTrue(all(c['passed'] for c in checks), [c for c in checks if not c['passed']])

    def test_cds_parsing(self):
        self.assertEqual(tl.parse_cds('ATGAAATAA'), ['AUG', 'AAA'])
        for bad in ('AUGAA', 'AAAUAA', 'AUGAAA', 'AUGUAAAAAUAA'):
            with self.assertRaises(ValueError): tl.parse_cds(bad)
        self.assertEqual(len(tl.parse_cds(rna_lab.reference()['angptl3_cds']['sequence'])), 460)

    def test_exclusion_never_violated_in_snapshots(self):
        r = tl.simulate(120, 9, 2.0, [1.0] * 120, 0.5, 300, 4, frames=300)
        for f in r['snapshots']:
            xs = [x for _, x in f['ribosomes']]
            self.assertEqual(xs, sorted(xs))
            self.assertTrue(all(b - a >= 9 for a, b in zip(xs, xs[1:])))
        self.assertEqual(r['produced'][-1], len(r['finished']))
        self.assertEqual(sorted(r['finished']), r['finished'])

    def test_simulation_is_seeded(self):
        a = tl.simulate(50, 3, 0.3, [1.0] * 50, 1.0, 200, 8); b = tl.simulate(50, 3, 0.3, [1.0] * 50, 1.0, 200, 8)
        self.assertEqual(a['finished'], b['finished'])


class DispatchTests(unittest.TestCase):
    def test_runs_are_recorded(self):
        with tempfile.TemporaryDirectory() as root:
            svc = types.SimpleNamespace(root=root)
            cat = rna_lab.dispatch(svc, 'rna_lab_catalog', {})
            self.assertIn('viennarna', cat['tools'])
            f = rna_lab.dispatch(svc, 'rna_lab_fold', {'samples': 100, 'seed': 2})
            self.assertIn('reference', f); self.assertEqual(f['evidence']['category'], 'C')
            t = rna_lab.dispatch(svc, 'rna_lab_translate', {'tEnd': 900, 'burnIn': 300, 'seed': 3})
            self.assertEqual(t['outputs']['codons'], 460); self.assertTrue(t['playback']['frames'])
            runs = rna_lab.dispatch(svc, 'rna_lab_runs', {})
            self.assertEqual({r['kind'] for r in runs}, {'rna_fold_ensemble', 'translation_tasep'})
            rec = json.loads((pathlib.Path(root) / 'rna_lab' / 'runs' / (f['recordId'] + '.json')).read_text())
            self.assertEqual(rec['reproducibility']['contentSha256'], f['recordSha256'])


if __name__ == '__main__':
    unittest.main()
