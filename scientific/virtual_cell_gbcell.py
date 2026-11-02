"""GB.Cell plugin: embeddings and in-silico knockout ranking, run locally (runtimes/gbcell: PyTorch + GenBio's gb_cell).

    python virtual_cell_gbcell.py benchmark <library root> [targets] [candidates] [cells]

GB.Cell (GenBio AI Community License, non-commercial; outputs inherit the terms) reads all 19,264 genes as tokens.
Without CUDA it uses torch's scaled_dot_product_attention. On Apple's Metal backend that kernel materialises the
19k × 19k attention matrix and the process is killed, so the model runs on the CPU, where torch uses a
memory-efficient kernel.

Benchmark (does the in-silico knockout carry information beyond the knocked-out gene itself?): for each target gene X
knocked down in Replogle 2022 K-562, the target is the mean embedding of X-knockdown cells with X's own expression reset
to its control value, so moving toward it requires predicting X's downstream programme. Every candidate gene is zeroed
in control cells; candidates are ranked by how much closer the mean embedding moves to the target. Scored by the rank of
X among the candidates (mean reciprocal rank), against the same procedure in a PCA embedding of the same cells
(co-expression baseline) and against chance.
"""
import json
import pathlib
import sys
import time

import numpy as np

MODEL = 'genbio-ai/GB.Cell-3M'


def embedder(device=None):
    import torch
    from gb_cell.models import CellFoundationModel, CellFoundationConfig
    from gb_cell.utils import preprocess_counts
    device = device or 'cpu'
    cfg = CellFoundationConfig.from_pretrained(MODEL); m = CellFoundationModel.from_pretrained(MODEL, config=cfg).to(device).eval()

    def embed(counts, mask, batch=4):
        am = torch.from_numpy(mask).unsqueeze(0).to(device); out = []
        with torch.no_grad():
            for i in range(0, len(counts), batch):
                x = preprocess_counts(np.asarray(counts[i:i + batch], np.float32), device=device)
                mm = torch.cat([am.repeat(x.shape[0], 1), torch.ones((x.shape[0], 2), device=device)], 1)
                o = m(input_ids=x, attention_mask=mm, output_hidden_states=True).last_hidden_state
                out.append(((o * mm.unsqueeze(-1)).sum(1) / mm.sum(1, keepdim=True)).float().cpu().numpy())
        return np.vstack(out)
    return embed, device


def benchmark(root, n_targets=12, n_candidates=40, n_cells=24, seed=0):
    import anndata as ad
    from gb_cell.utils import align_adata
    import virtual_cell as V
    root = pathlib.Path(root); rng = np.random.default_rng(seed); t0 = time.time()
    log = lambda m: print(f'[{time.time() - t0:7.0f}s] {m}', flush=True)
    ref = V.reference(root)
    A = ad.read_h5ad(root / 'virtualcell' / 'data' / 'replogle2022' / 'ReplogleWeissman2022_K562_essential.h5ad', backed='r')
    labels = A.obs['perturbation'].astype(str).values
    # targets: strong measured knockdowns (≤ 30 % target mRNA left) with the largest downstream change
    strong = sorted((g for g, r in ref.kd_remaining.items() if r <= 0.3 and ref.kd[g][1] >= n_cells), key=lambda g: -np.abs(ref.kd[g][0]).sum())
    targets = strong[:n_targets]
    others = [g for g in rng.permutation(strong[n_targets:]).tolist()][:n_candidates - n_targets]
    candidates = targets + others
    pick = lambda lab: rng.choice(np.where(labels == lab)[0], n_cells, replace=False)
    rows = np.concatenate([pick('control')] + [pick(g) for g in targets])
    sub = A[np.sort(rows)].to_memory(); sub.var_names = sub.var['gene_symbol'].astype(str).values if 'gene_symbol' in sub.var else sub.var_names
    sub.var_names_make_unique()
    al, mask = align_adata(sub); X = al.X.toarray() if hasattr(al.X, 'toarray') else np.asarray(al.X)
    genes = list(al.var_names); gi = {g: i for i, g in enumerate(genes)}
    lab = sub.obs['perturbation'].astype(str).values
    candidates = [g for g in candidates if g in gi and mask[gi[g]]]; targets = [g for g in targets if g in candidates]
    ctrl = X[lab == 'control']
    log(f'{len(targets)} targets, {len(candidates)} candidates, {len(ctrl)} control cells per condition')

    def masked_target(g):
        T = X[lab == g].copy(); lib_t = T.sum(1, keepdims=True); lib_c = ctrl.sum(1).mean()
        T[:, gi[g]] = ctrl[:, gi[g]].mean() * lib_t[:, 0] / lib_c          # X reset to its control level (depth-scaled)
        return T

    def ko(g):
        C = ctrl.copy(); C[:, gi[g]] = 0; return C

    # co-expression baseline: PCA on log-normalised expression of these cells
    norm = lambda M: np.log1p(M / np.maximum(M.sum(1, keepdims=True), 1) * 1e4)
    Z = norm(X); mu = Z.mean(0); U, S, Vt = np.linalg.svd(Z - mu, full_matrices=False); P = Vt[:20].T
    pca = lambda M: (norm(M) - mu) @ P
    embed, device = embedder(); log(f'GB.Cell-3M on {device}')
    res = {'gbcell': [], 'pca': []}
    for name, f in (('pca', pca), ('gbcell', lambda M: embed(M, mask))):
        base = f(ctrl).mean(0); kos = {g: f(ko(g)).mean(0) for g in candidates}
        for g in targets:
            tc = f(masked_target(g)).mean(0); d0 = np.linalg.norm(base - tc)
            shift = {c: d0 - np.linalg.norm(kos[c] - tc) for c in candidates}
            rank = 1 + sorted(shift, key=shift.get, reverse=True).index(g)
            res[name].append({'target': g, 'rank': rank})
        log(f'{name}: MRR {np.mean([1 / r["rank"] for r in res[name]]):.3f}')
    chance = float(np.mean([1 / k for k in range(1, len(candidates) + 1)]))
    out = {'model': MODEL, 'device': device, 'targets': targets, 'candidates': len(candidates), 'cellsPerCondition': n_cells,
           'mrr': {k: float(np.mean([1 / r['rank'] for r in v])) for k, v in res.items()}, 'chanceMrr': chance,
           'top1': {k: sum(r['rank'] == 1 for r in v) for k, v in res.items()}, 'ranks': res, 'seconds': round(time.time() - t0)}
    d = root / 'virtualcell' / 'plugins' / 'gbcell'; d.mkdir(parents=True, exist_ok=True)
    (d / 'benchmark.json').write_text(json.dumps(out, indent=1))
    log(json.dumps({k: out[k] for k in ('mrr', 'chanceMrr', 'top1')}))
    return out


if __name__ == '__main__':
    benchmark(sys.argv[2], *map(int, sys.argv[3:6]))
