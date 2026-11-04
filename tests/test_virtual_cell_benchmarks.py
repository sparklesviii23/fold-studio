"""Software invariants using synthetic fixtures; scientific evidence is in saved real-data runs."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import virtual_cell_benchmarks as B
import virtual_cell_drugs as D


def fixture(root):
    root = pathlib.Path(root); folder = root / 'virtualcell/data/tahoe100m'; folder.mkdir(parents=True)
    rng = np.random.default_rng(21); genes = [f'G{i}' for i in range(128)]
    conditions = []; effects = []
    for i in range(20):
        for drug in ('a', 'b', 'c'):
            for plate in (1, 2, 11, 13):
                conditions.append({'cellosaurus': f'CVCL_{i:04d}', 'drug': drug, 'concentration': 1., 'plate': str(plate),
                                   'unit': 'uM', 'depmap': f'ACH-{i}', 'cellLine': f'Line {i}'})
                effects.append(rng.normal(size=len(genes)))
    for name, data in [('conditions.json', conditions), ('genes.json', genes), ('progress.json', {'done': list(range(1026))}), ('manifest.json', {'synthetic': True})]:
        (folder / name).write_text(json.dumps(data))
    np.asarray(effects, np.float16).tofile(folder / 'lfc.f16'); np.ones_like(effects, dtype=np.float16).tofile(folder / 'se.f16')
    dm = root / 'oncology/depmap/24Q4'; dm.mkdir(parents=True)
    (dm / 'expression.json').write_text(json.dumps({'genes': genes, 'models': [f'ACH-{i}' for i in range(20)]}))
    np.save(dm / 'expression.npy', rng.normal(size=(20, len(genes))))
    return folder, conditions


class BenchmarkTests(unittest.TestCase):
    def test_seeded_split_is_disjoint_and_prespecifies_c3a(self):
        lines = [f'CVCL_{i:04d}' for i in range(49)] + ['CVCL_1098']
        a = B.split_lines(lines); B.assert_split(a)
        self.assertEqual(a, B.split_lines(list(reversed(lines))))
        self.assertIn('CVCL_1098', a['test'])
        with self.assertRaises(ValueError): B.assert_split({'train': ['a'], 'validation': ['a'], 'test': ['b']})

    def test_common_finite_mask_and_constant_correlation(self):
        observed = np.array([1., 2., np.nan, 4.])
        p = {'zero': np.zeros(4), 'candidate': np.array([1., np.nan, 3., 4.])}
        scores, mask = B.metrics(observed, p, min_genes=2)
        self.assertEqual(mask.tolist(), [True, False, False, True])
        self.assertEqual(scores['zero']['mse'], 8.5)
        self.assertIsNone(scores['zero']['pearson'])
        self.assertEqual(scores['candidate']['mse'], 0)
        with self.assertRaises(ValueError): B.metrics(observed, {'x': np.ones(2)}, min_genes=1)

    def test_units_duplicate_samples_and_conflicting_identities_are_refused(self):
        c = {'cellosaurus': 'CVCL_0001', 'cellLine': 'a', 'depmap': 'd', 'drug': 'x', 'concentration': 1, 'plate': '1', 'unit': 'uM'}
        with self.assertRaisesRegex(ValueError, 'Duplicate'): B.group_rows([c, dict(c)])
        with self.assertRaisesRegex(ValueError, 'uM'): B.group_rows([{**c, 'unit': 'nM'}])
        with self.assertRaisesRegex(ValueError, 'identity'): B.group_rows([c, {**c, 'plate': '2', 'cellLine': 'b'}])

    def test_heldout_outcomes_cannot_change_fitted_predictions(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, conditions = fixture(temp)
            a, arrays = B.evaluate(temp, conditions_per_line=3)
            training = set(a['trainingRows']); targets = set()
            for mode in ('validation', 'test'):
                for row in a['results'][mode]:
                    targets.update(row['targetRows'])
                    self.assertTrue(all(conditions[r]['cellosaurus'] in a['split']['train'] for r in row['donorRows']))
                    self.assertTrue(all(int(conditions[r]['plate']) <= 10 for r in row['donorRows']))
            self.assertFalse(training & targets)
            changed = np.memmap(folder / 'lfc.f16', dtype=np.float16, mode='r+', shape=(len(conditions), 128))
            changed[sorted(targets)] = 100; changed.flush(); del changed
            D._CACHE.clear()
            b, second = B.evaluate(temp, conditions_per_line=3)
            for key in arrays:
                if not key.endswith(('_observed', '_mask')):
                    np.testing.assert_array_equal(arrays[key], second[key])
            self.assertNotEqual(a['summary']['test']['unchanged']['mse']['mean'], b['summary']['test']['unchanged']['mse']['mean'])

    def test_saved_predictions_reproduce_metrics_and_detect_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture(temp); report, arrays = B.evaluate(temp, conditions_per_line=1)
            saved = B.save(temp, report, arrays); restored = B.load(temp, saved['id'])
            self.assertEqual(saved, restored)
            self.assertEqual(B.listing(temp, 'CVCL_9999')[0]['contextRole'], None)
            for row in report['results']['test']:
                prefix = row['artifactPrefix']; preds = {m: arrays[prefix + '_' + m] for m in B.MODELS}
                self.assertEqual(row['metrics'], B.metrics(arrays[prefix + '_observed'], preds)[0])
            path = pathlib.Path(temp).joinpath(*B.FOLDER, saved['id'], 'predictions.npz')
            path.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'artifact integrity'): B.load(temp, saved['id'])
            with self.assertRaises(ValueError): B.load(temp, '../x')

    def test_no_downloads_or_unbounded_requests(self):
        with tempfile.TemporaryDirectory() as temp:
            for kwargs in ({'conditions_per_line': 100}, {'conditions_per_line': True}, {'seed': False}, {'seed': -1}):
                with self.assertRaises(ValueError): B.evaluate(temp, **kwargs)
            with self.assertRaisesRegex(ValueError, 'completed'): B.evaluate(temp)


if __name__ == '__main__': unittest.main()
