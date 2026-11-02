"""In-domain CellFlux benchmark on BBBC021 (MCF7), using the IMPA preprocessed crops and the authors' checkpoint.

python cellflux_benchmark.py <plugin dir> <metadata csv> <image root> <out dir> [n_generate] [n_reference]

For each treated compound in the metadata: N test-split DMSO crops are transformed by CellFlux conditioned on the
compound's Morgan fingerprint (IMPA emb_fp.csv), and the generated crops are compared with test-split crops really
treated with that compound. Features per crop (all on [0, 1] intensities, channels in the dataset's stored order):
per-channel mean, standard deviation, Otsu foreground fraction and GLCM contrast (12 features), standardised by the
DMSO reference set. Metrics per compound:
  effect cosine   cos(generated − its DMSO inputs, real treated − DMSO reference): does the model move cells the right way
  magnitude ratio |predicted effect| / |true effect|
  distance        ‖mean(generated) − mean(treated)‖ vs ‖mean(DMSO) − mean(treated)‖ (closer than untreated = useful)
Baseline: the mean true effect of the other compounds (what a model that ignores the compound identity would predict).
Generation uses scientific/cellflux_runner.py (authors' settings). Dose is not part of CellFlux's conditioning; treated
reference crops pool all doses and the result says so.
"""
import json, pathlib, subprocess, sys, time

import numpy as np
import pandas as pd

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import virtual_cell_microscopy as VM


def load(root, key):
    batch, plate, *rest = key.split('_')
    return np.load(pathlib.Path(root) / batch / plate / ('_'.join(rest) + '.npy'))


def features(img):
    """img (C, H, W) in [0, 1] → 12 features."""
    out = []
    for c in img:
        t = VM.otsu(c) if c.max() > c.min() else 1.0
        out += [float(c.mean()), float(c.std()), float((c > t).mean()), VM.glcm_contrast(c.astype(float), 16)]
    return np.array(out)


def main(plugin, meta, images, out, n_gen=12, n_ref=150, seed=0):
    plugin, out = pathlib.Path(plugin), pathlib.Path(out); out.mkdir(parents=True, exist_ok=True)
    py = next(p / 'runtimes' / 'gbcell' / 'bin' / 'python' for p in HERE.parents if (p / 'runtimes' / 'gbcell' / 'bin' / 'python').is_file())
    df = pd.read_csv(meta); test = df[df.SPLIT == 'test']; rng = np.random.default_rng(seed)
    ctrl_keys = test[test.CPD_NAME == 'DMSO'].SAMPLE_KEY.tolist()
    if len(ctrl_keys) < n_gen + 20:
        raise SystemExit('Too few test-split DMSO crops.')
    perm = rng.permutation(ctrl_keys); inputs = list(perm[:n_gen]); ref_ctrl = list(perm[n_gen:n_gen + n_ref])  # disjoint
    X_in = np.stack([load(images, k).transpose(2, 0, 1) for k in inputs])                                      # (N, C, 96, 96) uint8
    F_ref = np.stack([features(load(images, k).transpose(2, 0, 1) / 255.0) for k in ref_ctrl])
    mu0, sd0 = F_ref.mean(0), F_ref.std(0) + 1e-9; z = lambda F: (F - mu0) / sd0
    np.save(out / 'inputs.npy', X_in)
    F_in = z(np.stack([features(x / 255.0) for x in X_in]))
    compounds = [c for c in test.CPD_NAME.unique() if c != 'DMSO']; rows = {}; true_effects = {}
    for cpd in compounds:
        trt = test[test.CPD_NAME == cpd].SAMPLE_KEY.tolist(); trt = list(rng.permutation(trt)[:n_ref])
        F_trt = z(np.stack([features(load(images, k).transpose(2, 0, 1) / 255.0) for k in trt]))
        true_effects[cpd] = F_trt.mean(0)
        gen = out / f'gen_{cpd.replace(" ", "_")}.npy'
        if not gen.is_file():
            req = {'src': str(plugin / 'src'), 'deps': str(plugin / 'deps'), 'checkpoint': str(plugin / 'checkpoints' / 'bbbc021.pth'), 'embeddings': str(plugin / 'data' / 'emb_fp.csv'),
                   'arch': 'bbbc021', 'perturbation': cpd, 'inputs': str(out / 'inputs.npy'), 'output': str(gen), 'seed': seed}
            (out / 'req.json').write_text(json.dumps(req)); t = time.time()
            subprocess.run([str(py), '-I', str(HERE / 'cellflux_runner.py'), str(out / 'req.json')], check=True)
            print(cpd, 'generated in', round(time.time() - t, 1), 's', flush=True)
        F_gen = z(np.stack([features(g) for g in np.load(gen)]))
        rows[cpd] = {'nTreatedReference': len(trt), 'doses': sorted(test[test.CPD_NAME == cpd].DOSE.unique().tolist()), 'moa': test[test.CPD_NAME == cpd].ANNOT.iloc[0],
                     'pred': F_gen.mean(0) - F_in.mean(0), 'genMean': F_gen.mean(0), 'trt': F_trt.mean(0)}
    cos = lambda a, b: float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))
    res = {}
    for cpd, r in rows.items():
        T = true_effects[cpd]; base = np.mean([true_effects[c] for c in compounds if c != cpd], 0)
        res[cpd] = {'moa': r['moa'], 'nGenerated': n_gen, 'nTreatedReference': r['nTreatedReference'], 'doses': r['doses'],
                    'effectCosine': cos(r['pred'], T), 'baselineCosine': cos(base, T), 'magnitudeRatio': float(np.linalg.norm(r['pred']) / (np.linalg.norm(T) + 1e-12)),
                    'distanceGeneratedToTreated': float(np.linalg.norm(r['genMean'] - r['trt'])), 'distanceUntreatedToTreated': float(np.linalg.norm(T)),
                    'distanceBaselineToTreated': float(np.linalg.norm(base - T))}
    summary = {k: float(np.mean([v[k] for v in res.values()])) for k in ('effectCosine', 'baselineCosine', 'magnitudeRatio', 'distanceGeneratedToTreated', 'distanceUntreatedToTreated', 'distanceBaselineToTreated')}
    report = {'dataset': str(meta), 'compounds': res, 'summary': summary, 'nDmsoInputs': n_gen, 'nDmsoReference': len(ref_ctrl), 'seed': seed,
              'features': 'per channel: mean, SD, Otsu foreground fraction, GLCM contrast (16 levels); standardised by DMSO reference',
              'caveats': ['Compounds were seen in training; cells are from the test split of this metadata table, which may not equal the split used to train the released checkpoint.',
                          'Dose is not conditioned on; treated references pool all doses.', 'Feature-level comparison, not FID.']}
    (out / 'benchmark.json').write_text(json.dumps(report, indent=1))
    print(json.dumps({'summary': summary, 'compounds': {k: {m: round(v[m], 3) if isinstance(v[m], float) else v[m] for m in ('effectCosine', 'baselineCosine', 'magnitudeRatio', 'distanceGeneratedToTreated', 'distanceUntreatedToTreated')} for k, v in res.items()}}, indent=1))


if __name__ == '__main__':
    a = sys.argv[1:]
    main(a[0], a[1], a[2], a[3], *(int(x) for x in a[4:6]))
