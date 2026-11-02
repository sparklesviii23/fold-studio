"""Evidence-graph provenance rules, offline (network calls replaced; no data fetched)."""
import pathlib, sys, tempfile, types, unittest
from unittest import mock
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import evidence_graph as E

STRING = [{'preferredName_A': 'KRAS', 'preferredName_B': 'RAF1', 'stringId_A': '9606.A', 'stringId_B': '9606.B', 'score': .99, 'escore': .9, 'dscore': .9, 'tscore': .9, 'ascore': 0},
          {'preferredName_A': 'KRAS', 'preferredName_B': 'XYZ', 'stringId_A': '9606.A', 'stringId_B': '9606.C', 'score': .75, 'escore': .1, 'dscore': 0, 'tscore': .7, 'ascore': 0}]


class GraphRuleTests(unittest.TestCase):
    def build(self, fake):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(E, '_get', side_effect=fake):
            return E.build(types.SimpleNamespace(root=pathlib.Path(tmp), setting=lambda k, d=None: d), 'KRAS', log=lambda *a: None)

    def test_text_mined_link_is_never_called_experimental(self):
        def fake(g, name, url, raw, body=None, text=False):
            g.sources[name] = {'ok': True}
            return {'string': STRING, 'string_version': [{'string_version': '12.5'}]}.get(name)
        r = self.build(fake)
        org = {e['target']: e['origin'] for e in r['edges'] if e['relation'] == 'interacts with'}
        self.assertEqual(org['gene:RAF1'], 'experimental')
        self.assertEqual(org['gene:XYZ'], 'text-mined')

    def test_failed_source_is_visible_and_duplicates_collapse(self):
        def fake(g, name, url, raw, body=None, text=False):
            if name == 'uniprot':
                g.sources[name] = {'ok': False, 'error': 'URLError'}; g.node('unavailable:uniprot', 'unavailable', 'uniprot unavailable'); return None
            g.sources[name] = {'ok': True}
            return {'string': STRING + STRING, 'string_version': [{'string_version': '12.5'}]}.get(name)
        r = self.build(fake)
        self.assertIn('unavailable:uniprot', [n['id'] for n in r['nodes']])
        self.assertEqual(sum(1 for e in r['edges'] if e['relation'] == 'interacts with'), 2)
        self.assertTrue(all(k in r['origins'] for k in ('experimental', 'curated', 'computed', 'text-mined', 'predicted')))


if __name__ == '__main__':
    unittest.main()
