"""Oncology statistics and drug-response methods on small synthetic data with known answers (method tests, not findings)."""
import json, pathlib, sys, tempfile, types, unittest
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import oncology_data as D
import oncology_stats as S
import drug_response as R


def library(tmp, n=120, genes=40, seed=0):
    rng = np.random.default_rng(seed)
    d = pathlib.Path(tmp) / 'oncology' / 'depmap' / 'TEST'; d.mkdir(parents=True)
    models = [f'ACH-{i:06d}' for i in range(n)]
    lin = ['Skin' if i < 30 else 'Lung' if i < 75 else 'Bowel' for i in range(n)]
    mut = np.zeros((n, 3)); mut[rng.choice(n, 25, replace=False), 0] = 1          # GENEA mutated in 25 models
    E = rng.normal(0, 0.2, (n, genes)).astype(np.float32)
    E[:, 0] -= 0.8 * mut[:, 0]                                                       # GENE0 dependency only where GENEA is mutated
    E[np.array(lin) == 'Skin', 1] -= 1.0                                             # GENE1 selectively essential in Skin
    rows = [{'ModelID': m, 'OncotreeLineage': l, 'PatientID': (f'Q{i // 2}' if i >= n - 10 else f'P{i}'), 'CellLineName': m, 'SangerModelID': f'SIDM{i:05d}'} for i, (m, l) in enumerate(zip(models, lin))]
    (d / 'models.json').write_text(json.dumps(rows))
    names = [f'GENE{j}' for j in range(genes)]
    np.save(d / 'gene_effect.npy', E); (d / 'gene_effect.json').write_text(json.dumps({'models': models, 'genes': names, 'entrez': [str(j) for j in range(genes)]}))
    np.save(d / 'mut_hotspot.npy', mut.astype(np.float32)); (d / 'mut_hotspot.json').write_text(json.dumps({'models': models, 'genes': ['GENEA', 'GENEB', 'GENEC'], 'entrez': ['1', '2', '3']}))
    X = rng.normal(0, 1, (n, 60)).astype(np.float32)
    np.save(d / 'expression.npy', X); (d / 'expression.json').write_text(json.dumps({'models': models, 'genes': [f'X{j}' for j in range(60)], 'entrez': [str(j) for j in range(60)]}))
    (d / 'manifest.json').write_text(json.dumps({'source': 'depmap', 'release': 'TEST', 'derived': {}}))
    return types.SimpleNamespace(root=pathlib.Path(tmp)), X, rows


class StatsTests(unittest.TestCase):
    def test_same_patient_lines_collapse(self):
        with tempfile.TemporaryDirectory() as tmp:
            s, *_ = library(tmp)
            self.assertEqual(S.gene_profile(D.Release(s), 'GENE1')['collapsedSamePatient'], 5)

    def test_lineage_scan_finds_planted_dependency(self):
        with tempfile.TemporaryDirectory() as tmp:
            s, *_ = library(tmp)
            r = S.lineage_scan(D.Release(s), 'Skin')
            self.assertEqual(r['hits'][0]['gene'], 'GENE1')
            self.assertLess(r['hits'][0]['ci'][1], -0.8)
            self.assertLess(r['hits'][0]['q'], 1e-6)

    def test_mutation_scan_is_lineage_adjusted_and_fdr_controlled(self):
        with tempfile.TemporaryDirectory() as tmp:
            s, *_ = library(tmp)
            r = S.mutation_scan(D.Release(s), 'GENEA')
            self.assertEqual(r['hits'][0]['gene'], 'GENE0')
            self.assertAlmostEqual(r['hits'][0]['beta'], -0.8, delta=0.15)
            null = [h for h in r['hits'] if h['gene'] != 'GENE0']
            self.assertLessEqual(sum(h['q'] < 0.05 for h in null), 2)

    def test_bh_matches_definition(self):
        q = S._bh(np.array([0.01, 0.04, 0.03, 0.2]))
        np.testing.assert_allclose(q, [0.04, 0.0533333, 0.0533333, 0.2], rtol=1e-5)


class DrugTests(unittest.TestCase):
    def test_signal_beats_baseline_and_folds_respect_patients(self):
        with tempfile.TemporaryDirectory() as tmp:
            s, X, rows = library(tmp)
            g = pathlib.Path(tmp) / 'oncology' / 'gdsc' / '8.5'; g.mkdir(parents=True)
            y = 1.5 * X[:, 3] - 1.0 * X[:, 7] + np.random.default_rng(1).normal(0, 0.3, len(rows))
            arr = lambda v, t: np.array(v, dtype=t)
            np.savez_compressed(g / 'responses.npz', dataset=arr(['GDSC2'] * len(rows), object), model=arr([r['SangerModelID'] for r in rows], object), cosmic=arr([''] * len(rows), object),
                                drug=arr(['GDSC2:1'] * len(rows), object), ln_ic50=y, auc=y * 0, rmse=y * 0, z=y * 0, min_conc=y * 0, max_conc=y * 0)
            (g / 'drugs.json').write_text(json.dumps([{'key': 'GDSC2:1', 'dataset': 'GDSC2', 'id': '1', 'name': 'Testinib', 'target': 'X3', 'pathway': 'Test'}]))
            r = R.held_out_cell_lines(s, 'GDSC2:1', top=60)
            self.assertEqual(r['leakage']['patientsSharedAcrossFolds'], 0)
            self.assertGreater(r['results']['ridge']['pearson'], 0.9)
            self.assertLess(r['results']['ridge']['rmse'], r['results']['mean']['rmse'] / 2)

    def test_folds_never_split_a_group(self):
        groups = ['a', 'a', 'b', 'c', 'c', 'c', 'd']
        f = R._folds(groups, 3)
        for g in set(groups):
            self.assertEqual(len({f[i] for i, x in enumerate(groups) if x == g}), 1)


if __name__ == '__main__':
    unittest.main()
