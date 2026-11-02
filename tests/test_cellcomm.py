"""Cell–cell communication: a planted ligand–receptor pair between two cell types is called; a pair with no co-expression is not."""
import json, pathlib, sys, tempfile, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))


class CellCommTests(unittest.TestCase):
    def test_planted_pair(self):
        try:
            import anndata as ad, numpy as np, pandas as pd, scipy.sparse as sp
        except ImportError:
            self.skipTest('needs the science runtime')
        import cellcomm
        rng = np.random.default_rng(0); genes = ['LIGA', 'RECB', 'LIGC', 'RECD'] + [f'G{i}' for i in range(40)]
        rows, obs = [], []
        for d in range(4):
            for t in ('sender', 'receiver'):
                for _ in range(60):
                    lam = np.full(len(genes), 2.0)
                    if t == 'sender': lam[0] = 20     # LIGA only in senders
                    if t == 'receiver': lam[1] = 20   # RECB only in receivers
                    lam[2] = lam[3] = 2.0             # LIGC/RECD flat everywhere: no cell-type structure
                    rows.append(rng.poisson(lam)); obs.append({'donor_id': f'd{d}', 'cell_type': t, 'disease': 'tumor' if d < 2 else 'normal'})
        A = ad.AnnData(sp.csr_matrix(np.array(rows, np.float32)), obs=pd.DataFrame(obs).astype('category'), var=pd.DataFrame({'feature_name': genes}, index=genes))
        lr = [{'source_genesymbol': 'LIGA', 'target_genesymbol': 'RECB', 'sources': ['CellPhoneDB', 'CellChatDB']},
              {'source_genesymbol': 'LIGC', 'target_genesymbol': 'RECD', 'sources': ['CellPhoneDB', 'CellChatDB']}]
        with tempfile.TemporaryDirectory() as tmp:
            A.write_h5ad(f'{tmp}/a.h5ad'); json.dump(lr, open(f'{tmp}/lr.json', 'w'))
            cellcomm.main(f'{tmp}/a.h5ad', f'{tmp}/lr.json', f'{tmp}/out.json', 'disease', 'tumor', 'normal', perms=99)
            r = json.load(open(f'{tmp}/out.json'))
        called = {(x['sender'], x['ligand'], x['receptor'], x['receiver']) for x in r['interactions']}
        self.assertIn(('sender', 'LIGA', 'RECB', 'receiver'), called)
        self.assertFalse(any(c[1] == 'LIGC' for c in called))


if __name__ == '__main__':
    unittest.main()
