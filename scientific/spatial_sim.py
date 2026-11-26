"""In-silico tumor section with known ground truth, written in the same layout as a deposited Visium H5AD so the
spatial pipeline runs on it unchanged and can be scored against what was planted. Runs in the single-cell runtime.

    python spatial_sim.py <out_dir> <phenotype: infiltrated|excluded|desert> <nests> <seed>

Generative model (all stated, nothing fitted to real data; evidence category: Hypothetical / illustrative):
  geometry   Visium layout, 100 µm centre to centre on a hexagonal array, 55 µm spots, 60 rows x 60 spots
  tumor      union of Gaussian nests; a spot is tumor where the summed field exceeds 0.5
  fractions  fixed per compartment; T cells set by the phenotype (inside tumor vs distance to the tumor edge)
  ambient    other cell types carry 0.05 % of a marker's level (0.02 vs 30–60)
  counts     cells per spot ~ 1 + Poisson(8); depth ~ lognormal(0, 0.3); counts ~ negative binomial (dispersion 0.2)
  genes      cell-type markers (inherit the tissue pattern), 5 smooth gradient genes, 300 pattern-free genes;
             every cell-type profile has the same total so library size carries no spatial signal
"""
import hashlib
import json
import pathlib
import sys
import time

import numpy as np

TYPES = ['Cancer Epithelial', 'T-cells', 'CAFs', 'Myeloid', 'B-cells', 'Endothelial']
MARKERS = {'Cancer Epithelial': ['EPCAM', 'KRT8', 'KRT18', 'MKI67'], 'T-cells': ['CD3E', 'CD8A', 'PTPRC'], 'CAFs': ['COL1A1', 'DCN', 'FAP'],
           'Myeloid': ['CD68', 'LYZ', 'CD163'], 'B-cells': ['MS4A1', 'CD79A'], 'Endothelial': ['PECAM1', 'VWF']}
PHENOTYPES = ('infiltrated', 'excluded', 'desert')


def simulate(phenotype='excluded', nests=3, seed=0, rows=60):
    if phenotype not in PHENOTYPES:
        raise ValueError('phenotype must be one of ' + ', '.join(PHENOTYPES))
    rng = np.random.default_rng(seed)
    row = np.repeat(np.arange(rows), rows); col = np.concatenate([np.arange(r % 2, 2 * rows, 2) for r in range(rows)])
    xy = np.c_[col * 50.0, row * 100 * np.sqrt(3) / 2] + 200             # µm
    span = xy.max(0) - xy.min(0)
    centres = xy.min(0) + span * (0.2 + 0.6 * rng.random((nests, 2))); radii = rng.uniform(450, 900, nests)
    field = sum(np.exp(-((xy - c) ** 2).sum(1) / (2 * r ** 2)) for c, r in zip(centres, radii))
    tum = field > 0.5
    from scipy.spatial import cKDTree
    dist = cKDTree(xy[tum]).query(xy)[0] if tum.any() else np.full(len(xy), 1e9); dist[tum] = 0
    F = np.zeros((len(xy), len(TYPES)))
    t_in = {'infiltrated': 0.15, 'excluded': 0.01, 'desert': 0.01}[phenotype]
    t_out = {'infiltrated': np.full(len(xy), 0.15), 'excluded': 0.03 + 0.25 * np.exp(-dist / 250), 'desert': np.full(len(xy), 0.01)}[phenotype]
    F[tum] = [0.70, t_in, 0.10, 0.08, 0.0, 0.05]
    F[~tum] = np.c_[np.zeros((~tum).sum()), t_out[~tum], np.full((~tum).sum(), 0.50), np.full((~tum).sum(), 0.12), np.full((~tum).sum(), 0.05), np.full((~tum).sum(), 0.10)]
    F = F / F.sum(1, keepdims=True)
    comp = np.where(tum, 'Tumor cells', np.where(F[:, 1] > 0.12, 'Tumor stroma with inflammation', 'Tumor stroma fibrous'))
    # Expression profiles with equal totals per cell type.
    markers = [g for t in TYPES for g in MARKERS[t]]; grad = [f'SIMGRAD{i}' for i in range(1, 6)]; null = [f'SIMNULL{i:03d}' for i in range(1, 301)]
    genes = markers + grad + null; G = len(genes); P = np.ones((len(TYPES), G))
    for i, t in enumerate(TYPES):
        P[i, :len(markers)] = 0.02; P[i, [genes.index(g) for g in MARKERS[t]]] = 120.0 / len(MARKERS[t])   # equal marker mass per type keeps the null-gene share composition-free
    P = P / P.sum(1, keepdims=True) * 400
    mu_type = F @ P
    g = (xy[:, 0] - xy[:, 0].min()) / span[0]                          # smooth left-to-right gradient, independent of tissue
    for k, name in enumerate(grad):
        mu_type[:, genes.index(name)] = 1.0 + 4.0 * (g if k % 2 == 0 else 1 - g)
    cells = 1 + rng.poisson(8, len(xy)); depth = rng.lognormal(0, 0.3, len(xy))
    mu = mu_type * (cells * depth)[:, None]
    lam = rng.gamma(1 / 0.2, mu * 0.2)                                   # gamma-Poisson = negative binomial, dispersion 0.2
    counts = rng.poisson(lam).astype(np.float32)
    truth = {'phenotype': phenotype, 'nests': int(nests), 'seed': int(seed), 'tumorSpots': int(tum.sum()), 'spots': int(len(xy)),
             'spatialGenes': MARKERS['Cancer Epithelial'] + MARKERS['CAFs'] + grad, 'nullGenes': null,
             'tCellInside': t_in, 'tCellOutside': {'infiltrated': '0.15 flat', 'excluded': '0.03 + 0.25·exp(−d/250 µm)', 'desert': '0.01 flat'}[phenotype],
             'model': 'Gaussian tumor nests; fixed compartment fractions; negative-binomial counts (dispersion 0.2); equal-total cell-type profiles'}
    return xy, row, col, F, comp, genes, counts, tum, truth


def render(xy, comp, um_per_px=5.0):
    """A flat colour rendering of the true compartments (synthetic; not an H&E image)."""
    from scipy.spatial import cKDTree
    W, H = int(xy[:, 0].max() / um_per_px) + 40, int(xy[:, 1].max() / um_per_px) + 40
    yy, xx = np.mgrid[0:H, 0:W]; pts = np.c_[xx.ravel(), yy.ravel()] * um_per_px
    d, i = cKDTree(xy).query(pts)
    pal = {'Tumor cells': (0.55, 0.36, 0.62), 'Tumor stroma with inflammation': (0.86, 0.62, 0.74), 'Tumor stroma fibrous': (0.94, 0.78, 0.84)}
    img = np.array([pal[c] for c in comp])[i]; img[d > 70] = 1.0
    return img.reshape(H, W, 3).astype(np.float32)


def write(out_dir, phenotype, nests, seed):
    import anndata as ad, pandas as pd, scipy.sparse as sp
    out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    xy, row, col, F, comp, genes, counts, tum, truth = simulate(phenotype, int(nests), int(seed))
    obs = pd.DataFrame({'in_tissue': 1, 'array_row': row, 'array_col': col, 'ground truth compartment': pd.Categorical(comp)}, index=[f'spot{i}' for i in range(len(xy))])
    for j, t in enumerate(TYPES):
        obs['true fraction: ' + t] = F[:, j]
    a = ad.AnnData(sp.csr_matrix(counts), obs=obs, var=pd.DataFrame({'feature_name': genes}, index=genes))
    a.obsm['spatial'] = xy                                              # full-resolution pixel = 1 µm
    a.uns['spatial'] = {'synthetic': {'images': {'hires': render(xy, comp)}, 'scalefactors': {'spot_diameter_fullres': 55.0, 'tissue_hires_scalef': 0.2}}}
    a.uns['synthetic_truth'] = json.dumps(truth)
    a.write_h5ad(out / 'dataset.h5ad')
    m = {'source': 'In-silico (fold spatial simulator)', 'datasetId': out.name, 'title': f'Synthetic section · {phenotype} · {nests} nests · seed {seed}', 'synthetic': True,
         'params': {'phenotype': phenotype, 'nests': int(nests), 'seed': int(seed)}, 'model': truth['model'], 'sha256': hashlib.sha256((out / 'dataset.h5ad').read_bytes()).hexdigest(),
         'licence': 'Generated locally', 'installed': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (out / 'manifest.json').write_text(json.dumps(m, indent=1)); print('generated', m['title'], flush=True)


if __name__ == '__main__':
    write(*sys.argv[1:5])
