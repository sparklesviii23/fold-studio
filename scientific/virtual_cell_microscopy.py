"""Observed Cell Painting images for a cell context, with segmentation and per-cell morphology.

Data (<library>/virtualcell/data/cellpainting_hepg2/original; Cell Painting Gallery, CC0 1.0; cite Wolff et al.,
iScience 2025, doi:10.1016/j.isci.2025.112445): cpg0036-EU-OS-bioactives, partner FMP, batch 2021_09_03_Batch1_HepG2,
plate B1001_R1, DMSO control wells A23 and B24, sites 1/5/9. `subset.json` lists every file with its S3 source and
SHA-256. Channels are the dataset's own load_data names (DNA, ER, AGP, Mito); this partner's load_data has no RNA
channel and none is invented. Raw 16-bit pixels are never modified; display PNGs are separate, percentile-scaled copies.

Segmentation and features (SciPy only; the bundled runtime has no scikit-image or Cellpose):
  nuclei  log(1 + DNA), Gaussian σ=2; a pixel is nuclear when above the Otsu threshold (global foreground) AND above its
          Gaussian σ=8 local mean (local adaptive threshold, which separates nuclei along the darker gaps inside Hep G2
          clusters); opening (2 iterations), holes filled, objects < 80 px removed. Tightly touching nuclei can remain
          merged (visible as the upper tail of nuclear area). Distance-transform watershed was tried and rejected: on
          clustered Hep G2 it produced axis-aligned fragments.
  cells   foreground = Otsu on Gaussian σ=2 of (AGP + ER), each normalised by its 99.5th percentile; each foreground
          pixel joins its nearest nucleus within 60 px (Voronoi within foreground; an approximation of CellProfiler's
          propagation, which also weighs intensity gradients). Objects touching the image border are excluded.
  shape   area (px²), crack perimeter (pixel-edge count; overestimates smooth outlines by ≈ 4/π), eccentricity and axes of
          the moment-equivalent ellipse, form factor 4πA/P², nucleus/cell area ratio.
  signal  mean and integrated raw intensity per channel in nucleus, cytoplasm and cell; DNA texture in the nucleus as
          coefficient of variation and GLCM contrast (16 grey levels, 1-pixel horizontal offset).
Units: pixels. The TIFF resolution tag (≈ 6.45 µm/px) is the camera sensor pitch, not the sample plane; converting
needs the objective magnification and binning, which the files do not carry. No illumination correction is applied
(the dataset's illum functions were not downloaded), so intensities compare within an image better than across plates.
"""
import base64, hashlib, io, json, pathlib

import numpy as np
from scipy import ndimage as ndi

DIR = ('virtualcell', 'data', 'cellpainting_hepg2')
CONTEXT = 'CVCL_0027'
CHANNELS = {'DNA': {'stain': 'DNA (Hoechst in the standard Cell Painting naming)', 'color': '#3d6bff'},
            'ER': {'stain': 'Endoplasmic reticulum (concanavalin A in the standard naming)', 'color': '#38ff80'},
            'AGP': {'stain': 'Actin, Golgi, plasma membrane (phalloidin + WGA in the standard naming)', 'color': '#ff8033'},
            'Mito': {'stain': 'Mitochondria (MitoTracker in the standard naming)', 'color': '#ff3a52'}}
DATASET = {'id': 'cpg0036_fmp_hepg2', 'name': 'EU-OPENSCREEN Bioactives Cell Painting, Hep G2 (FMP), DMSO controls', 'cellosaurus': CONTEXT,
           'source': 's3://cellpainting-gallery/cpg0036-EU-OS-bioactives/FMP/', 'licence': 'CC0 1.0 (Cell Painting Gallery)',
           'citation': 'Wolff C et al. iScience 2025;28:112445. doi:10.1016/j.isci.2025.112445', 'units': 'pixels; raw 16-bit intensity'}
PARAMS = {'sigma': 2.0, 'localSigma': 8.0, 'opening': 2, 'minNucleus': 80, 'maxReach': 60, 'glcmLevels': 16}


def folder(root):
    return pathlib.Path(root).joinpath(*DIR)


def subset(root):
    f = folder(root) / 'original' / 'subset.json'
    return json.loads(f.read_text()) if f.is_file() else []


def images(root):
    """Field-of-view keys (plate_well_site) with their channel files."""
    out = {}
    for m in subset(root):
        k = f"{m['plate']}_{m['well']}_s{m['site']}"
        out.setdefault(k, {'key': k, 'plate': m['plate'], 'well': m['well'], 'site': m['site'], 'batch': m['batch'], 'condition': 'DMSO (0 µM)', 'channels': {}})['channels'][m['channel']] = m
    return [out[k] for k in sorted(out)]


def _load(root, m, verify=True):
    from PIL import Image
    f = folder(root) / 'original' / m['file']; data = f.read_bytes()
    if verify and hashlib.sha256(data).hexdigest() != m['sha256']:
        raise ValueError(f"{m['file']} changed since download (SHA-256 mismatch).")
    return np.array(Image.open(io.BytesIO(data)))


def otsu(x, bins=256):
    h, e = np.histogram(x, bins=bins); c = (e[:-1] + e[1:]) / 2; w = np.cumsum(h); w2 = w[-1] - w
    m1 = np.cumsum(h * c) / np.maximum(w, 1); m2 = (np.sum(h * c) - np.cumsum(h * c)) / np.maximum(w2, 1)
    return float(c[np.argmax(w[:-1] * w2[:-1] * (m1[:-1] - m2[:-1]) ** 2)])


def segment_nuclei(dna, p=PARAMS):
    s = ndi.gaussian_filter(np.log1p(dna.astype(float)), p['sigma'])
    mask = (s > otsu(s)) & (s > ndi.gaussian_filter(s, p['localSigma']))
    mask = ndi.binary_fill_holes(ndi.binary_opening(mask, iterations=p['opening']))
    lab, n = ndi.label(mask)
    sizes = ndi.sum(mask, lab, range(1, n + 1)); keep = 1 + np.flatnonzero(sizes >= p['minNucleus'])
    remap = np.zeros(n + 1, np.int32); remap[keep] = np.arange(1, len(keep) + 1)
    return remap[lab]


def segment_cells(nuclei, agp, er, p=PARAMS):
    norm = lambda a: a.astype(float) / max(np.percentile(a, 99.5), 1)
    s = ndi.gaussian_filter(norm(agp) + norm(er), p['sigma']); fg = (s > otsu(s)) | (nuclei > 0)
    dist, (iy, ix) = ndi.distance_transform_edt(nuclei == 0, return_indices=True)
    cells = nuclei[iy, ix]; cells[~fg | (dist > p['maxReach'])] = 0
    return cells.astype(np.int32)


def _shape(m):
    ys, xs = np.nonzero(m); a = len(ys)
    perim = int(np.sum(m[:, 1:] != m[:, :-1]) + np.sum(m[1:, :] != m[:-1, :]) + m[0, :].sum() + m[-1, :].sum() + m[:, 0].sum() + m[:, -1].sum())
    cov = np.cov(np.vstack([xs, ys])) if a > 2 else np.zeros((2, 2)); ev = np.sort(np.linalg.eigvalsh(cov))
    ecc = float(np.sqrt(max(0.0, 1 - ev[0] / ev[1]))) if ev[1] > 0 else 0.0
    return {'area': a, 'perimeter': perim, 'eccentricity': ecc, 'majorAxis': float(4 * np.sqrt(max(ev[1], 0))), 'minorAxis': float(4 * np.sqrt(max(ev[0], 0))),
            'formFactor': float(4 * np.pi * a / perim ** 2) if perim else None}


def glcm_contrast(values, levels=16):
    """GLCM contrast for horizontal neighbours inside the object (values: 2-D array with NaN outside)."""
    v = values[~np.isnan(values)]
    if v.size < 4 or v.max() == v.min():
        return 0.0
    q = np.floor((values - v.min()) / (v.max() - v.min() + 1e-9) * levels).clip(0, levels - 1)
    a, b = q[:, :-1], q[:, 1:]; ok = ~np.isnan(a) & ~np.isnan(b)
    return float(np.mean((a[ok] - b[ok]) ** 2)) if ok.any() else 0.0


def measure(chans, nuclei, cells):
    h, w = nuclei.shape; border = set(np.unique(np.concatenate([cells[0], cells[-1], cells[:, 0], cells[:, -1]])))
    rows = []
    for i in range(1, int(nuclei.max()) + 1):
        if i in border:
            continue
        nm, cm = nuclei == i, cells == i
        if not nm.any() or cm.sum() < nm.sum():
            continue
        sl = ndi.find_objects(cm.astype(np.int32))[0]; nmc, cmc = nm[sl], cm[sl]; cyto = cmc & ~nmc
        r = {'id': i, 'nucleus': _shape(nmc), 'cell': _shape(cmc)}
        r['ratio'] = r['nucleus']['area'] / r['cell']['area']
        for ch, img in chans.items():
            x = img[sl].astype(float)
            r[ch] = {'nucleusMean': float(x[nmc].mean()), 'cellMean': float(x[cmc].mean()), 'cytoplasmMean': float(x[cyto].mean()) if cyto.any() else None,
                     'cellIntegrated': float(x[cmc].sum())}
        d = chans['DNA'][sl].astype(float); dn = np.where(nmc, d, np.nan)
        r['dnaTexture'] = {'cv': float(np.nanstd(dn) / max(np.nanmean(dn), 1e-9)), 'glcmContrast': glcm_contrast(dn, PARAMS['glcmLevels'])}
        rows.append(r)
    return rows


def _png(a, color=None):
    from PIL import Image
    buf = io.BytesIO(); Image.fromarray(a).save(buf, format='PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


def _summary(rows, key):
    pick = {'nucleusArea': lambda r: r['nucleus']['area'], 'cellArea': lambda r: r['cell']['area'], 'ratio': lambda r: r['ratio'],
            'nucleusEccentricity': lambda r: r['nucleus']['eccentricity'], 'cellEccentricity': lambda r: r['cell']['eccentricity'],
            'cellPerimeter': lambda r: r['cell']['perimeter'], 'nucleusFormFactor': lambda r: r['nucleus']['formFactor'],
            'dnaTextureCv': lambda r: r['dnaTexture']['cv'], 'dnaGlcmContrast': lambda r: r['dnaTexture']['glcmContrast'],
            'mitoCytoplasmMean': lambda r: r['Mito']['cytoplasmMean'], 'erCellMean': lambda r: r['ER']['cellMean'], 'agpCellMean': lambda r: r['AGP']['cellMean']}
    out = {}
    for k, f in pick.items():
        v = np.array([f(r) for r in rows if f(r) is not None], float)
        out[k] = None if not v.size else {'median': float(np.median(v)), 'q1': float(np.percentile(v, 25)), 'q3': float(np.percentile(v, 75)), 'n': int(v.size)}
    return out


def analyse(root, key):
    fov = next((x for x in images(root) if x['key'] == key), None)
    if fov is None:
        raise ValueError('Unknown field of view.')
    cache = folder(root) / 'features' / f'{key}.json'
    shas = {c: m['sha256'] for c, m in fov['channels'].items()}
    if cache.is_file():
        d = json.loads(cache.read_text())
        if d.get('inputs') == shas and d.get('params') == PARAMS:
            return d
    chans = {c: _load(root, m) for c, m in fov['channels'].items()}
    nuclei = segment_nuclei(chans['DNA']); cells = segment_cells(nuclei, chans['AGP'], chans['ER']); rows = measure(chans, nuclei, cells)
    out = {'key': key, 'fov': {k: v for k, v in fov.items() if k != 'channels'}, 'inputs': shas, 'params': PARAMS, 'dataset': DATASET,
           'raw': {c: {'min': int(a.min()), 'max': int(a.max()), 'mean': float(a.mean()), 'dtype': str(a.dtype), 'shape': list(a.shape)} for c, a in chans.items()},
           'counts': {'nucleiDetected': int(nuclei.max()), 'cellsMeasured': len(rows)}, 'summary': _summary(rows, key), 'cells': rows,
           'evidence': 'Measured image features computed from observed microscopy (A · Experimental image, computed morphology)', 'units': DATASET['units'],
           'method': __doc__.split('Segmentation and features')[1].split('Units:')[0].strip()}
    cache.parent.mkdir(parents=True, exist_ok=True); cache.write_text(json.dumps(out))
    np.savez_compressed(cache.with_suffix('.masks.npz'), nuclei=nuclei.astype(np.int32), cells=cells.astype(np.int32))
    return out


def view(root, key):
    """Display layers: per-channel 8-bit PNG (0.5–99.8th percentile, display only) and mask outlines."""
    fov = next((x for x in images(root) if x['key'] == key), None)
    if fov is None:
        raise ValueError('Unknown field of view.')
    a = analyse(root, key); masks = np.load(folder(root) / 'features' / f'{key}.masks.npz')
    layers = {}
    for c, m in fov['channels'].items():
        x = _load(root, m).astype(float); lo, hi = np.percentile(x, [0.5, 99.8])
        layers[c] = {'png': _png((np.clip((x - lo) / max(hi - lo, 1), 0, 1) * 255).astype(np.uint8)), 'displayRange': [float(lo), float(hi)], **CHANNELS[c], 'source': m['source']}
    outline = {}
    for name in ('nuclei', 'cells'):
        lab = masks[name]; edge = (lab != np.roll(lab, 1, 0)) | (lab != np.roll(lab, 1, 1)); edge &= lab > 0
        rgba = np.zeros(lab.shape + (4,), np.uint8); rgba[edge] = (255, 255, 255, 230) if name == 'nuclei' else (255, 214, 102, 200)
        outline[name] = _png(rgba)
    return {'key': key, 'layers': layers, 'outlines': outline, 'size': list(masks['nuclei'].shape), 'analysis': {k: v for k, v in a.items() if k != 'cells'},
            'cells': [{'id': r['id'], 'nucleusArea': r['nucleus']['area'], 'cellArea': r['cell']['area'], 'ratio': r['ratio'], 'eccentricity': r['cell']['eccentricity']} for r in a['cells'][:400]]}
