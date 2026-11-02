"""Inferred cell–cell communication from single-cell expression (LIANA/CellPhoneDB-style), with donors as replicates.

    python cellcomm.py <dataset.h5ad> <omnipath_lr.json> <out.json> <condition column> <case> <control>

Resource: OmniPath ligand–receptor interactions (ligrecextra), pairs listed by ≥ 2 dedicated ligand–receptor resources, at least one
expert-curated (CellPhoneDB, CellChatDB or ICELLNET); multi-subunit complexes skipped.
Per donor: log-normalised expression (1e4, log1p); for a sender type × receiver type, score = mean(ligand in sender) × mean(receptor
in receiver), both expressed in ≥ 10 % of their cells (≥ 20 cells per type); p from 200 permutations of cell-type labels within the
donor. Across donors: an interaction is called where it is significant (p < 0.05) in ≥ half of the donors that have both cell types.
Case vs control: number of donors calling it in each group (donor-level counts, no cell pooling).
Evidence: Statistical association (co-expression). Ligand and receptor expression does not show that signalling happens.
"""
import json
import sys
import time

import numpy as np

# Dedicated ligand–receptor resources inside OmniPath; a pair must be in ≥ 2 of them (general interaction databases do not count,
# which keeps out intracellular and non-secreted proteins such as ribosomal or ubiquitin genes).
EXPERT = {'CellPhoneDB', 'CellChatDB', 'ICELLNET'}                  # expert-curated; every pair must be in at least one of these
LR_DBS = {'CellPhoneDB', 'CellChatDB', 'ICELLNET', 'connectomeDB2020', 'ConnectomeDB2025', 'Ramilowski2015', 'Guide2Pharma', 'CellTalkDB', 'Cellinker', 'LRdb', 'CellCall', 'iTALK', 'Kirouac2010', 'Fantom5', 'scConnect', 'talklr', 'EMBRACE', 'Baccin2019', 'HPMR'}


def main(path, lr_path, out, cond='disease', case='', control='', perms=200, min_cells=20, min_frac=0.1):
    import anndata as ad, scipy.sparse as sp
    t0 = time.time(); log = lambda m: print(f'[{time.time() - t0:6.1f}s] {m}', flush=True)
    A = ad.read_h5ad(path); X = A.raw.X if A.raw is not None else A.X
    var = A.raw.var if A.raw is not None else A.var
    names = np.array(var['feature_name'].astype(str) if 'feature_name' in var else var.index.astype(str))
    lrdb = lambda srcs: sorted({s.split('_')[0] for s in srcs} & LR_DBS)
    pairs = [(x['source_genesymbol'], x['target_genesymbol'], len(lrdb(x['sources']))) for x in json.load(open(lr_path))
             if len(lrdb(x['sources'])) >= 2 and set(lrdb(x['sources'])) & EXPERT and not x['source_genesymbol'].startswith('COMPLEX') and not x['target_genesymbol'].startswith('COMPLEX')]
    gi = {g: i for i, g in enumerate(names)}; pairs = sorted({p for p in pairs if p[0] in gi and p[1] in gi})
    genes = sorted({g for l, r, _ in pairs for g in (l, r)}); col = [gi[g] for g in genes]; gj = {g: i for i, g in enumerate(genes)}
    X = sp.csr_matrix(X)[:, :]; lib = np.asarray(X.sum(1)).ravel(); X = sp.csr_matrix(X[:, col])
    E = X.multiply(1e4 / np.maximum(lib, 1)[:, None]).tocsr(); E.data = np.log1p(E.data)
    log(f'{A.n_obs} cells; {len(pairs)} ligand–receptor pairs with both genes measured')
    obs = A.obs; rng = np.random.default_rng(0); calls = {}; donors = {}
    for d, idx in obs.groupby('donor_id', observed=True).indices.items():
        ct = obs['cell_type'].astype(str).values[idx]; types = [t for t in np.unique(ct) if (ct == t).sum() >= min_cells]
        if len(types) < 2:
            continue
        group = str(obs[cond].astype(str).values[idx][0]) if cond in obs else ''
        donors[str(d)] = group
        sub = E[idx]; dense = sub.toarray(); expressed = dense > 0
        def means(labels):
            return np.vstack([dense[labels == t].mean(0) for t in types])          # types × genes
        M = means(ct); F = np.vstack([expressed[ct == t].mean(0) for t in types])
        li = np.array([gj[l] for l, r, _ in pairs]); ri = np.array([gj[r] for l, r, _ in pairs])
        S = M[:, li][:, None, :] * M[:, ri][None, :, :]                             # sender × receiver × pair
        ok = (F[:, li][:, None, :] >= min_frac) & (F[:, ri][None, :, :] >= min_frac)
        ge = np.zeros(S.shape)
        for _ in range(perms):
            Mp = means(rng.permutation(ct)); ge += (Mp[:, li][:, None, :] * Mp[:, ri][None, :, :]) >= S
        P = (ge + 1) / (perms + 1)
        for a, b, k in zip(*np.where(ok & (P < 0.05))):
            calls.setdefault((types[a], types[b], k), {}).setdefault(str(d), float(S[a, b, k]))
        for a in range(len(types)):
            for b in range(len(types)):
                calls.setdefault(('__present__', types[a], types[b]), {})[str(d)] = 1
        log(f'donor {d} ({group}): {len(types)} cell types, {int((ok & (P < 0.05)).sum())} calls')
    rows = []
    for (s, r, k), v in calls.items():
        if s == '__present__':
            continue
        present = calls.get(('__present__', s, r), {}); n = len(present)
        if n == 0 or len(v) < max(2, n / 2):
            continue
        l, rc, nsrc = pairs[k]
        ca = [d for d in v if donors.get(d) == case]; co = [d for d in v if donors.get(d) == control]
        pc = [d for d in present if donors.get(d) == case]; pk = [d for d in present if donors.get(d) == control]
        rows.append({'sender': s, 'receiver': r, 'ligand': l, 'receptor': rc, 'resources': nsrc, 'donors': len(v), 'donorsWithTypes': n,
                     'medianScore': float(np.median(list(v.values()))), 'case': f'{len(ca)}/{len(pc)}', 'control': f'{len(co)}/{len(pk)}',
                     'caseShare': len(ca) / len(pc) if pc else None, 'controlShare': len(co) / len(pk) if pk else None})
    rows.sort(key=lambda r: (-r['donors'] / r['donorsWithTypes'], -r['medianScore']))
    shift = [r for r in rows if r['caseShare'] is not None and r['controlShare'] is not None and int(r['case'].split('/')[1]) >= 2 and int(r['control'].split('/')[1]) >= 2]
    gained = sorted([r for r in shift if r['caseShare'] - r['controlShare'] >= 0.5], key=lambda r: -(r['caseShare'] - r['controlShare']))
    lost = sorted([r for r in shift if r['controlShare'] - r['caseShare'] >= 0.5], key=lambda r: -(r['controlShare'] - r['caseShare']))
    res = {'cells': int(A.n_obs), 'pairs': len(pairs), 'donors': donors, 'interactions': rows[:300], 'called': len(rows), 'gainedInCase': gained[:60], 'lostInCase': lost[:60],
           'contrast': {'condition': cond, 'case': case, 'control': control},
           'method': f'OmniPath ligand–receptor pairs (≥ 2 dedicated resources, ≥ 1 of CellPhoneDB, CellChatDB, ICELLNET; no complexes); per donor: mean(ligand, sender) × mean(receptor, receiver), both in ≥ {min_frac:.0%} of cells, ≥ {min_cells} cells per type; {perms} within-donor label permutations; called if p < 0.05 in ≥ half the donors with both types',
           'evidence': 'Statistical association (ligand–receptor co-expression); not a measurement of signalling', 'seconds': round(time.time() - t0, 1),
           'caveat': 'Expression of a ligand and its receptor does not show binding or signalling, and says nothing about distance between the cells; spatial proximity or protein data are needed for that.'}
    json.dump(res, open(out, 'w')); log('done')


if __name__ == '__main__':
    main(*sys.argv[1:7])
