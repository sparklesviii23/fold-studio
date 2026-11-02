"""Research assistant: routing of the directive's example questions, and answers carrying evidence classes and sources."""
import pathlib, sys, types, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import oncology_assistant as A

ROOT = pathlib.Path(__file__).resolve().parents[2] / 'validation' / 'bindcraft-fab-amme-native'


@unittest.skipUnless((ROOT / 'oncology' / 'depmap').is_dir(), 'DepMap not installed')
class AssistantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import oncology_data as D
        cls.s = types.SimpleNamespace(root=str(ROOT)); cls.rel = D.Release(cls.s)

    def test_routing(self):
        cases = {'Which paper first reported BRAF and MAP2K1?': ('first', 'BRAF'), 'How does MAPK1 in BRAF change after controlling for lineage?': ('lineage', 'MAPK1'),
                 'Is the KRAS RAF1 interaction experimental or predicted?': ('origin', 'KRAS'), 'What normal-tissue evidence is missing for PRMT5?': ('normal', 'PRMT5')}
        for text, (q, g) in cases.items():
            got, args = A.route(text, self.rel, [], ['Skin', 'Lung'])
            self.assertEqual((got, args.get('gene')), (q, g), text)

    def test_lineage_answer_is_grounded(self):
        r = A.answer(self.s, self.rel, 'lineage', {'gene': 'MAPK1', 'mutation': 'BRAF'})
        self.assertTrue(r['claims'] and all(c['evidence'] and c['source'] for c in r['claims']))
        self.assertIn('lineage fixed effects', r['answer'])

    def test_missing_argument_is_an_error_not_a_guess(self):
        with self.assertRaises(ValueError):
            A.answer(self.s, self.rel, 'support', {})


if __name__ == '__main__':
    unittest.main()
