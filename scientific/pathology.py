"""Demo I · pathology analysis on an openly licensed H&E dataset with expert nucleus annotations (NumPy/SciPy only).

Pipeline and evidence
  Images and expert masks            Experimental observation (NuInsSeg, Mahbod et al., Sci Data 2024; CC BY 4.0)
  Tiling (256 px, 32 px overlap)     objects kept only in the tile they are centred in, so seams are not double-counted
  Colour deconvolution               Ruifrok & Johnston 2001 H&E matrix → hematoxylin optical density
  Segmentation                       image-wide Otsu threshold on smoothed hematoxylin, opening, hole filling, distance-transform
                                     watershed seeded at local maxima; objects < 30 px removed
  Morphology                         area, perimeter, equivalent diameter, eccentricity, circularity, mean hematoxylin
  Quality checks                     focus (variance of the Laplacian), tissue fraction, stain strength
  Benchmark vs annotations           pixel Dice, object precision / recall / F1 at IoU ≥ 0.5, AJI (Kumar et al. 2017);
                                     regions the annotators marked as ambiguous ("vague areas") are excluded from scoring
Computational measurement (classical image analysis); its accuracy is the benchmark, not an assumption.
"""
import json
import math

import numpy as np
from scipy import ndimage as ndi

HE = np.array([[0.650, 0.704, 0.286], [0.072, 0.990, 0.105], [0.268, 0.570, 0.776]])   # H, E, residual (Ruifrok & Johnston 2001)


def hematoxylin(rgb):
    od = -np.log((rgb.astype(float) + 1) / 256.0)
    M = HE / np.linalg.norm(HE, axis=1, keepdims=True)
    return (od.reshape(-1, 3) @ np.linalg.inv(M)).reshape(rgb.shape)[..., 0]


def otsu(x, bins=256):
    h, e = np.histogram(x, bins=bins); c = (e[:-1] + e[1:]) / 2; w = np.cumsum(h); m = np.cumsum(h * c)
    w0, w1 = w[:-1], w[-1] - w[:-1]; mu0 = m[:-1] / np.maximum(w0, 1); mu1 = (m[-1] - m[:-1]) / np.maximum(w1, 1)
    return float(c[:-1][np.argmax(w0 * w1 * (mu0 - mu1) ** 2)])


def segment_tile(rgb, split=True, min_area=30, peak=5, threshold=None):
    H = ndi.gaussian_filter(hematoxylin(rgb), 1.0)
    mask = H > (otsu(H) if threshold is None else threshold)      # tiles use the image-wide threshold: a background-only tile has no nuclei to find
    mask = ndi.binary_fill_holes(ndi.binary_opening(mask, np.ones((3, 3)), iterations=1))
    if not split:
        lab, _ = ndi.label(mask)
    else:
        dist = ndi.gaussian_filter(ndi.distance_transform_edt(mask), 1.0)
        peaks = (dist == ndi.maximum_filter(dist, size=2 * peak + 1)) & (dist > 2)
        markers, _ = ndi.label(peaks)
        surf = (dist.max() - dist); surf = (surf / max(surf.max(), 1e-9) * 254).astype(np.uint8)
        markers = markers.astype(np.int32); markers[~mask] = -1                   # background seed keeps one nucleus from flooding into another
        lab = ndi.watershed_ift(surf, markers); lab[lab < 0] = 0; lab[~mask] = 0
        # The background seed also claims nuclear rims; give each unlabelled foreground pixel to its nearest nucleus in the same
        # blob, and give a blob without any seed its own label.
        comp, nc = ndi.label(mask)
        if lab.max():
            idx = ndi.distance_transform_edt(lab == 0, return_indices=True)[1]; near = lab[idx[0], idx[1]]
            fill = (lab == 0) & mask & (comp[idx[0], idx[1]] == comp); lab[fill] = near[fill]
        seeded = np.unique(comp[lab > 0])
        for c in range(1, nc + 1):
            if c not in seeded:
                lab[comp == c] = lab.max() + 1
    sizes = np.bincount(lab.ravel()); small = sizes < min_area; small[0] = False
    lab[small[lab]] = 0
    return _relabel(lab), H


def _relabel(lab):
    u = np.unique(lab); u = u[u > 0]; out = np.zeros(lab.shape, np.int32)
    lut = np.zeros(lab.max() + 1, np.int32); lut[u] = np.arange(1, len(u) + 1)
    return lut[lab]


def segment(rgb, tile=256, overlap=32, **kw):
    """Tiled segmentation: each object is kept from the tile whose core contains its centroid."""
    h, w = rgb.shape[:2]
    kw.setdefault('threshold', otsu(ndi.gaussian_filter(hematoxylin(rgb), 1.0)))
    if h <= tile and w <= tile:
        return segment_tile(rgb, **kw)
    out = np.zeros((h, w), np.int32); Hfull = np.zeros((h, w)); n = 0; step = tile - overlap
    for y0 in range(0, max(h - overlap, 1), step):
        for x0 in range(0, max(w - overlap, 1), step):
            y1, x1 = min(y0 + tile, h), min(x0 + tile, w); lab, H = segment_tile(rgb[y0:y1, x0:x1], **kw); Hfull[y0:y1, x0:x1] = H
            cy0, cx0 = (0 if y0 == 0 else overlap // 2), (0 if x0 == 0 else overlap // 2)
            cy1, cx1 = (y1 - y0) - (0 if y1 == h else overlap // 2), (x1 - x0) - (0 if x1 == w else overlap // 2)
            for k, sl in enumerate(ndi.find_objects(lab), 1):
                if sl is None:
                    continue
                cy, cx = ndi.center_of_mass(lab[sl] == k); cy += sl[0].start; cx += sl[1].start
                if cy0 <= cy < cy1 and cx0 <= cx < cx1:
                    n += 1; reg = out[y0:y1, x0:x1]; reg[(lab == k) & (reg == 0)] = n
    return out, Hfull


def morphology(lab, H):
    rows = []
    for k, sl in enumerate(ndi.find_objects(lab), 1):
        if sl is None:
            continue
        m = lab[sl] == k; a = int(m.sum()); per = int((m & ~ndi.binary_erosion(m)).sum())
        yy, xx = np.nonzero(m); cov = np.cov(np.vstack([yy, xx])) if a > 2 else np.eye(2); ev = np.sort(np.linalg.eigvalsh(cov))
        ecc = float(math.sqrt(1 - ev[0] / ev[1])) if ev[1] > 0 else 0.0
        rows.append({'area': a, 'perimeter': per, 'diameter': 2 * math.sqrt(a / math.pi), 'eccentricity': ecc, 'circularity': 4 * math.pi * a / max(per, 1) ** 2,
                     'hematoxylin': float(H[sl][m].mean()), 'y': float(yy.mean() + sl[0].start), 'x': float(xx.mean() + sl[1].start)})
    return rows


def qc(rgb, H):
    g = rgb.astype(float).mean(2); lap = ndi.laplace(g)
    tissue = float((g < 0.85 * 255).mean())
    return {'focus': float(lap.var()), 'tissueFraction': tissue, 'meanHematoxylin': float(H.mean()),
            'flags': [f for f, bad in (('possibly out of focus (Laplacian variance < 50)', lap.var() < 50), ('little tissue (< 30 %)', tissue < 0.3), ('weak hematoxylin', H.mean() < 0.05)) if bad]}


def score(pred, gt, ignore=None):
    """Pixel Dice, object P/R/F1 at IoU ≥ 0.5 and AJI; pixels in `ignore` are removed from both before scoring."""
    if ignore is not None:
        pred = pred.copy(); gt = gt.copy(); pred[ignore] = 0; gt[ignore] = 0
    P, G = pred > 0, gt > 0; dice = 2 * (P & G).sum() / max(P.sum() + G.sum(), 1)
    gt = _relabel(gt); pred = _relabel(pred); ng, npd = gt.max(), pred.max()
    inter = np.bincount(gt.ravel() * (npd + 1) + pred.ravel(), minlength=(ng + 1) * (npd + 1)).reshape(ng + 1, npd + 1)
    ag, ap = inter.sum(1), inter.sum(0); I = inter[1:, 1:]; U = ag[1:, None] + ap[None, 1:] - I; iou = np.where(U > 0, I / np.maximum(U, 1), 0)
    tp = int((iou >= 0.5).sum()); prec = tp / max(npd, 1); rec = tp / max(ng, 1); f1 = 2 * prec * rec / max(prec + rec, 1e-9)
    C = Uu = 0; used = np.zeros(npd, bool)
    for g in range(ng):
        j = int(np.argmax(iou[g])) if npd else -1
        if j >= 0 and I[g, j] > 0:
            C += I[g, j]; Uu += U[g, j]; used[j] = True
        else:
            Uu += ag[g + 1]
    Uu += ap[1:][~used].sum()
    return {'dice': float(dice), 'precision': prec, 'recall': rec, 'f1': f1, 'aji': float(C / max(Uu, 1)), 'nucleiTrue': int(ng), 'nucleiFound': int(npd), 'matched': tp}


def _outline(lab):
    return (lab > 0) & ~ndi.binary_erosion(lab > 0) | (ndi.maximum_filter(lab, 3) != ndi.minimum_filter(lab, 3)) & (lab > 0)


def overlay_jpeg(rgb, pred, gt, size=384):
    """Expert outlines orange, computed outlines green; JPEG bytes."""
    import io
    from PIL import Image
    im = rgb.copy(); im[_outline(gt)] = [255, 150, 60]; im[_outline(pred)] = [80, 255, 140]
    buf = io.BytesIO(); Image.fromarray(im).resize((size, int(size * im.shape[0] / im.shape[1]))).save(buf, 'JPEG', quality=82); return buf.getvalue()


# Method development, recorded as it happened. The rule above was fixed before any NuInsSeg image was scored. Afterwards four
# variants were compared with mouse images as the development set and human images held out: a three-class Otsu threshold was
# best on mouse (AJI 0.151 → 0.199) but worse on the held-out human images (0.336 → 0.304); a size-adaptive splitting radius
# changed little. Choosing by the human scores would be selecting on the test set, so the pre-specified rule is kept.
DEVELOPMENT = {'design': 'variants compared on mouse images (development, 193); human images (472) held out',
               'variants': [{'rule': 'Otsu, peak radius 5 (pre-specified, kept)', 'mouseAJI': 0.151, 'humanAJI': 0.336},
                            {'rule': 'three-class Otsu, peak 5 (best on development)', 'mouseAJI': 0.199, 'humanAJI': 0.304},
                            {'rule': 'Otsu, size-adaptive peak', 'mouseAJI': 0.141, 'humanAJI': 0.335},
                            {'rule': 'three-class Otsu, size-adaptive peak', 'mouseAJI': 0.184, 'humanAJI': 0.301}],
               'decision': 'The development winner did not transfer to human tissue; the pre-specified rule is kept rather than choosing on the held-out set.'}


def run_dataset(zip_path, out_dir, log=print, overlays_per_organ=1):
    """All NuInsSeg images: segment (watershed and threshold-only baseline), score against the expert masks, measure, check."""
    import base64
    import hashlib
    import io
    import pathlib
    import time
    import zipfile
    from PIL import Image
    t0 = time.time(); out = pathlib.Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    z = zipfile.ZipFile(zip_path); names = set(z.namelist())
    imgs = sorted(n for n in names if '/tissue images/' in n and n.endswith('.png'))
    read = lambda n: np.array(Image.open(io.BytesIO(z.read(n))))
    rows, overlays, density, morph = [], {}, {}, {}
    for i, n in enumerate(imgs):
        organ, stem = n.split('/')[0], n.rsplit('/', 1)[1][:-4]
        lm, va = f'{organ}/label masks modify/{stem}.tif', f'{organ}/vague areas/mask binary/{stem}.png'
        if lm not in names:
            continue
        rgb = read(n)[..., :3]; gt = read(lm).astype(np.int64); ign = read(va) > 0 if va in names else None
        if ign is not None and ign.ndim == 3:
            ign = ign[..., 0]
        lab, H = segment(rgb); base, _ = segment(rgb, split=False)
        s, sb = score(lab, gt, ign), score(base, gt, ign); q = qc(rgb, H); m = morphology(lab, H)
        rows.append({'image': stem, 'organ': organ, 'species': organ.split(' ')[0], 'watershed': s, 'threshold': sb, 'qc': q, 'nuclei': len(m),
                     'medianArea': float(np.median([x['area'] for x in m])) if m else None, 'medianCircularity': float(np.median([x['circularity'] for x in m])) if m else None,
                     'ignoredPixels': int(ign.sum()) if ign is not None else 0})
        morph.setdefault(organ, []).extend([[round(x['area']), round(x['circularity'], 3)] for x in m[:150]])
        if sum(1 for k in overlays if k.startswith(organ + '|')) < overlays_per_organ:
            overlays[organ + '|' + stem] = base64.b64encode(overlay_jpeg(rgb, lab, gt)).decode()
            yy, xx = np.array([x['y'] for x in m]), np.array([x['x'] for x in m]); g, _, _ = np.histogram2d(yy, xx, bins=16, range=[[0, rgb.shape[0]], [0, rgb.shape[1]]]) if m else (np.zeros((16, 16)), 0, 0)
            density[organ + '|' + stem] = g.astype(int).tolist()
        if i % 50 == 0:
            log(f'[{time.time() - t0:6.1f}s] {i + 1}/{len(imgs)} {organ}')
    def agg(rs, key):
        v = {k: np.array([r[key][k] for r in rs]) for k in ('dice', 'f1', 'aji', 'precision', 'recall')}
        return {k: {'mean': float(x.mean()), 'sd': float(x.std(ddof=1)) if len(x) > 1 else 0.0} for k, x in v.items()}
    by = {}
    for r in rows:
        by.setdefault(r['organ'], []).append(r)
    rng = np.random.default_rng(0); d = np.array([r['watershed']['aji'] - r['threshold']['aji'] for r in rows])
    boot = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
    flagged = [r for r in rows if r['qc']['flags']]; ok = [r for r in rows if not r['qc']['flags']]
    res = {'images': len(rows), 'organs': len(by), 'overall': {'watershed': agg(rows, 'watershed'), 'threshold': agg(rows, 'threshold')},
           'bySpecies': {sp: {'images': len(rs), **agg(rs, 'watershed')} for sp in ('human', 'mouse') for rs in [[r for r in rows if r['species'] == sp]] if rs},
           'development': DEVELOPMENT,
           'byOrgan': sorted([{'organ': o, 'images': len(rs), 'nuclei': int(sum(x['watershed']['nucleiTrue'] for x in rs)), **{f'{k}': agg(rs, 'watershed')[k]['mean'] for k in ('dice', 'f1', 'aji')},
                               'ajiThreshold': agg(rs, 'threshold')['aji']['mean'], 'medianArea': float(np.median([x['medianArea'] for x in rs if x['medianArea']]))} for o, rs in by.items()], key=lambda x: -x['aji']),
           'splitting': {'meanAjiGain': float(d.mean()), 'ci': [float(np.quantile(boot, .025)), float(np.quantile(boot, .975))], 'imagesImproved': int((d > 0).sum())},
           'qc': {'flagged': len(flagged), 'ajiFlagged': float(np.mean([r['watershed']['aji'] for r in flagged])) if flagged else None, 'ajiUnflagged': float(np.mean([r['watershed']['aji'] for r in ok])) if ok else None,
                  'flags': {f: sum(f in r['qc']['flags'] for r in rows) for f in {f for r in rows for f in r['qc']['flags']}}},
           'perImage': rows, 'overlays': overlays, 'density': density, 'morphology': {o: v[:600] for o, v in morph.items()},
           'dataset': {'name': 'NuInsSeg', 'citation': 'Mahbod A et al. NuInsSeg: a fully annotated dataset for nuclei instance segmentation in H&E-stained histological images. Sci Data 2024;11:295.',
                       'licence': 'CC BY 4.0', 'doi': '10.5281/zenodo.10518968', 'sha256': hashlib.sha256(open(zip_path, 'rb').read()).hexdigest()},
           'method': __doc__.split('Pipeline and evidence')[1].strip(), 'evidence': 'Computational measurement (classical image analysis) benchmarked against expert annotations (experimental observation)',
           'seconds': round(time.time() - t0, 1)}
    (out / 'result.json').write_text(json.dumps(res)); log(f'done: {len(rows)} images in {res["seconds"]} s'); return res


RECORD = 'https://zenodo.org/api/records/10518968'


def install(folder, log=print):
    """Download the full NuInsSeg archive (≈ 1.6 GB, resumable) and verify it against Zenodo's published MD5."""
    import hashlib
    import pathlib
    import urllib.request
    d = pathlib.Path(folder); d.mkdir(parents=True, exist_ok=True); z = d / 'NuInsSeg.zip'
    f = next(x for x in json.loads(urllib.request.urlopen(RECORD, timeout=60).read())['files'] if x['key'] == 'NuInsSeg.zip')
    size, md5 = f['size'], f['checksum'].split(':', 1)[1]
    while not z.is_file() or z.stat().st_size < size:
        have = z.stat().st_size if z.is_file() else 0; log(f'downloading from byte {have:,} of {size:,}')
        req = urllib.request.Request(f'{RECORD}/files/NuInsSeg.zip/content', headers={'Range': f'bytes={have}-'})
        with urllib.request.urlopen(req, timeout=120) as r, open(z, 'ab') as out:
            while chunk := r.read(1 << 22):
                out.write(chunk)
    h = hashlib.md5()
    with open(z, 'rb') as fh:
        while chunk := fh.read(1 << 22):
            h.update(chunk)
    if h.hexdigest() != md5:
        z.rename(z.with_suffix('.corrupt')); raise SystemExit('MD5 mismatch; the archive was set aside as NuInsSeg.corrupt.')
    (d / 'manifest.json').write_text(json.dumps({'dataset': 'NuInsSeg', 'record': RECORD, 'md5': md5, 'bytes': size, 'licence': 'CC BY 4.0'}, indent=1)); log('verified')


if __name__ == '__main__':
    import sys
    install(sys.argv[2]) if sys.argv[1] == 'install' else run_dataset(sys.argv[1], sys.argv[2])
