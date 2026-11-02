"""Single-cell pipeline: QC helpers and an end-to-end synthetic run in the isolated Scanpy runtime (skipped if absent)."""
import json, pathlib, subprocess, sys, tempfile, types, unittest
import numpy as np
HERE = pathlib.Path(__file__).resolve().parents[1] / 'scientific'
sys.path.insert(0, str(HERE))
import singlecell_tumor as SC
import singlecell_data as SD

SYNTH = r'''
import sys, numpy as np, pandas as pd, anndata as ad, scipy.sparse as sp
rng = np.random.default_rng(1); rows, obs = [], []
genes = [f'G{i}' for i in range(400)] + ['GLI1', 'PTCH1', 'HHIP', 'MT-CO1']
base = rng.gamma(2, 1, len(genes))
for d in range(12):
    case = d < 6; donor_shift = rng.lognormal(0, 0.3, len(genes))     # real donor-to-donor variation
    for c in range(60):
        mu = base * donor_shift * (1 + 3 * case * np.isin(genes, ['GLI1', 'PTCH1', 'HHIP']))
        rows.append(rng.poisson(mu)); obs.append({'donor_id': f'D{d}', 'disease': 'tumor' if case else 'normal', 'cell_type': 'k', '02_group': 'face'})
X = sp.csr_matrix(np.array(rows, dtype=np.float32)); var = pd.DataFrame({'feature_name': genes}, index=genes)
a = ad.AnnData(X=X, obs=pd.DataFrame(obs, index=[f'c{i}' for i in range(len(obs))]), var=var); a.raw = a.copy(); a.write_h5ad(sys.argv[1])
'''


class HelperTests(unittest.TestCase):
    def test_mad_flags(self):
        x = np.r_[np.random.default_rng(0).normal(10, 1, 200), 30.0]
        f = SC.mad_flags(x); self.assertTrue(f[-1]); self.assertLess(f[:-1].mean(), 0.02)
        self.assertFalse(SC.mad_flags(np.r_[x[:-1], -30.0], upper_only=True)[-1])

    def test_runtime_lookup_respects_setting(self):
        s = types.SimpleNamespace(setting=lambda k, d=None: sys.executable if k == 'singlecellPython' else d)
        self.assertEqual(str(SD.python(s)), sys.executable)


@unittest.skipUnless(SD.python(types.SimpleNamespace(setting=lambda k, d=None: d)), 'single-cell runtime not installed')
class EndToEndTests(unittest.TestCase):
    def test_planted_genes_found_at_donor_level_and_naive_inflation_shown(self):
        py = str(SD.python(types.SimpleNamespace(setting=lambda k, d=None: d)))
        with tempfile.TemporaryDirectory() as tmp:
            h5, out, gmt = f'{tmp}/x.h5ad', f'{tmp}/r.json', f'{tmp}/h.gmt'
            pathlib.Path(gmt).write_text('HALLMARK_HEDGEHOG_SIGNALING\tx\t' + '\t'.join(['GLI1', 'PTCH1', 'HHIP'] + [f'G{i}' for i in range(10)]) + '\n')
            subprocess.run([py, '-W', 'ignore', '-c', SYNTH, h5], check=True)
            r = subprocess.run([py, '-W', 'ignore', str(HERE / 'singlecell_tumor.py'), h5, out, gmt, 'k', 'disease', 'tumor', 'normal', 'face'], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr[-2000:])
            res = json.loads(pathlib.Path(out).read_text())
            self.assertTrue(all(c['passed'] for c in res['controls']), res['controls'])
            self.assertGreater(res['significantNaiveCellLevel'], res['significantDonorLevel'])   # cell-level testing inflates
            self.assertEqual((len(res['contrast']['caseDonors']), len(res['contrast']['controlDonors'])), (6, 6))


if __name__ == '__main__':
    unittest.main()
