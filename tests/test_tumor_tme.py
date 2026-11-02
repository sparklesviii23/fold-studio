import json, pathlib, sys, tempfile, types, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import gpu_tasks as G
import tumor_tme as T


def svc(tmp):
    return types.SimpleNamespace(root=pathlib.Path(tmp), setting=lambda k, d=None: d)


def write_run(root, frames, field_hi=38.0):
    """A small run in the exact shape the PhysiCell recipe returns (format test only, not a simulation)."""
    tid = 'c' * 32
    d = pathlib.Path(root) / 'gpu_tasks' / tid
    (d / 'outputs' / 'physicell').mkdir(parents=True)
    (d / 'task.json').write_text(json.dumps({'id': tid, 'recipe': 'physicell', 'state': 'done', 'inputs': {'sample': 'heterogeneity', 'days': 3}}))
    xs = [-30.0, -10.0, 10.0, 30.0]
    fr = []
    for k, n in enumerate(frames):
        cells = [[(i % 4) * 5.0, (i // 4) * 5.0, 0.0, 8.0, 0, 0, 14, 1.0] for i in range(n)]
        fr.append({'t': k * 1440.0, 'total': n, 'sampled': n, 'counts': {'0': {'live': n, 'dead': 0}}, 'cells': cells,
                   'fields': [[field_hi - 1.0 * (abs(x) < 20) for _ in xs for x in xs]]})
    (d / 'outputs' / 'physicell' / 'tme.json').write_text(json.dumps({'engine': 'PhysiCell', 'version': '1.14.2', 'sample': 'heterogeneity',
        'substrates': [{'name': 'oxygen', 'units': 'mmHg', 'dirichlet': 38.0, 'diffusion': 1e5, 'decay': 0.1}], 'types': {'0': 'cancer cell'},
        'grid': {'x': xs, 'y': xs, 'z0': 0.0, 'nz': 1, 'voxels': 16}, 'frames': fr, 'snapshots': len(fr), 'sampling': 'all'}))
    return tid


class TmeTests(unittest.TestCase):
    def test_recipe_inputs(self):
        # Every declared input is filled with its recipe default (immune parameters added with the immune-scaling recipe).
        self.assertEqual(G._clean_inputs('physicell', {}), {'sample': 'cancer_immune', 'days': 21, 'immuneScale': 1.0, 'immuneStartDay': -1.0, 'killScale': 1.0})
        with self.assertRaises(ValueError):
            G._clean_inputs('physicell', {'immuneScale': 6})
        with self.assertRaises(ValueError):
            G._clean_inputs('physicell', {'sample': 'rm -rf'})
        with self.assertRaises(ValueError):
            G._clean_inputs('physicell', {'days': 99})

    def test_logistic_counts_select_a_saturating_law(self):
        import math
        with tempfile.TemporaryDirectory() as tmp:
            counts = [round(200 / (1 + 9 * math.exp(-0.8 * t))) for t in range(12)]
            tid = write_run(tmp, counts)
            r = T.load(svc(tmp), {'taskId': tid})
            fits = {f['model']: f for f in r['growthFits']['fits']}
            self.assertGreater(fits['exponential']['deltaAic'], 10)
            self.assertAlmostEqual(fits['logistic']['params'][1], 200, delta=5)
            self.assertTrue(all(c['passed'] is not False for c in r['checks']))
            self.assertEqual(T.runs(svc(tmp))[0]['ready'], True)

    def test_oxygen_above_boundary_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            tid = write_run(tmp, [5, 6, 7, 8, 9], field_hi=45.0)
            c = {x['check']: x for x in T.load(svc(tmp), {'taskId': tid})['checks']}
            self.assertFalse(c['Oxygen maximum principle']['passed'])


if __name__ == '__main__':
    unittest.main()
