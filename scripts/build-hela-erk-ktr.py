#!/usr/bin/env python3
"""Build fixtures/hela_erk/tany2022_egf_ktr.json: single-cell ERK-KTR trajectories from SSBD project 232.

Source images (CC BY): Tany R, Goto Y, Kondo Y, Aoki K. Quantitative live-cell imaging of GPCR downstream signaling
dynamics. Biochem J 2022;479(8):883-900. SSBD repository ssbd-repos-000232, datasets Figure2C_20211008_*:
HeLa cells with a nuclear marker (RFP channel), ERK-KTR (iRFP channel) and DORA-RhoA (CFP and FRET channels),
stimulated with 10 ng/ml EGF; 512 × 512 pixels of 0.74 µm, one frame per minute, 16 frames, 4 stage positions per dish.

Usage:  python3.12 scripts/build-hela-erk-ktr.py <folder holding the downloaded Figure2C_*.zip files>
Needs NumPy, SciPy and Pillow (the app runtime has them).

The readout is the one the assay defines: cytoplasmic over nuclear ERK-KTR fluorescence (C/N), per cell, per frame.
  nucleus    connected region of the nuclear marker above a per-image threshold, 60–900 µm², not touching the border,
             followed through time by overlap with its own previous mask; measured on the mask eroded by one pixel
  cytoplasm  ring from 2 to 6 pixels outside the nucleus, inside the cell (DORA-RhoA above background), outside every
             other nucleus
  background mode of the image outside every cell, per channel and frame
A cell is kept when it is present in all frames, its ring holds at least 40 pixels and its KTR signal is at least
five background standard deviations in both regions. Nothing else is filtered and nothing is smoothed.
"""
import hashlib, io, json, pathlib, re, sys, zipfile

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

PIXEL_UM = 0.74
CHANNEL = {'nucleus': 'w2RFP-Chroma', 'ktr': 'w1iRFP', 'cell': 'w4CFP'}
RULES = {'nucleusAreaUm2': [60, 900], 'erodePx': 1, 'ringPx': [2, 6], 'minRingPixels': 40, 'minSignalSd': 5.0, 'nucleusThreshold': '0.5 × Otsu threshold of the smoothed marker image (σ = 1 pixel)',
         'cellThreshold': 'background + 4 background standard deviations of the smoothed DORA-RhoA image'}


def otsu(a):
    hist, edges = np.histogram(a, 256); mid = (edges[:-1] + edges[1:]) / 2
    w = np.cumsum(hist); m = np.cumsum(hist * mid); total = m[-1]
    with np.errstate(divide='ignore', invalid='ignore'):
        var = (total * w - m * w[-1]) ** 2 / (w * (w[-1] - w))
    return mid[np.nanargmax(var[:-1])]


def background(a):
    """Mode and spread of the dim pixels of an image."""
    lo = a[a < np.percentile(a, 60)]; med = np.median(lo); sd = 1.4826 * np.median(np.abs(lo - med))
    return float(med), float(max(sd, 1e-6))


def quantify(z, prefix):
    names = [n for n in z.namelist() if n.upper().endswith('.TIF')]
    key = lambda n: re.search(r'_(w\d[^_]*)_s(\d+)_t(\d+)\.TIF$', n, re.I)
    index = {(key(n).group(1), int(key(n).group(2)), int(key(n).group(3))): n for n in names if key(n)}
    positions = sorted({k[1] for k in index}); frames = sorted({k[2] for k in index})
    load = lambda w, s, t: np.array(Image.open(io.BytesIO(z.read(index[(w, s, t)])))).astype(np.float64)
    stamp = lambda s, t: re.search(r'acquisition-time-local" type="time" value="(\d+) (\d+):(\d+):([\d.]+)"', str(Image.open(io.BytesIO(z.read(index[(CHANNEL['ktr'], s, t)]))).tag_v2.get(270)))
    cells = []; ring_struct = ndi.generate_binary_structure(2, 2); dropped = {'border': 0, 'area': 0, 'lost': 0, 'ring': 0, 'dim': 0}
    for s in positions:
        clock = []
        for t in frames:
            m = stamp(s, t); clock.append(int(m.group(2)) * 60 + int(m.group(3)) + float(m.group(4)) / 60)
        minutes = [round(c - clock[0], 3) for c in clock]
        tracks = None
        for fi, t in enumerate(frames):
            nuc = ndi.gaussian_filter(load(CHANNEL['nucleus'], s, t), 1.0); ktr = load(CHANNEL['ktr'], s, t); cell = ndi.gaussian_filter(load(CHANNEL['cell'], s, t), 1.0)
            mask = ndi.binary_fill_holes(ndi.binary_opening(nuc > 0.5 * otsu(nuc), iterations=1)); lab, n = ndi.label(mask)
            bg_k, sd_k = background(ktr); bg_c, sd_c = background(cell); in_cell = cell > bg_c + 4 * sd_c
            if tracks is None:                                          # first frame: every acceptable nucleus starts a track
                tracks = []
                for i, sl in enumerate(ndi.find_objects(lab), 1):
                    region = lab == i; area = region.sum() * PIXEL_UM ** 2
                    if sl[0].start == 0 or sl[1].start == 0 or sl[0].stop == lab.shape[0] or sl[1].stop == lab.shape[1]:
                        dropped['border'] += 1; continue
                    if not RULES['nucleusAreaUm2'][0] <= area <= RULES['nucleusAreaUm2'][1]:
                        dropped['area'] += 1; continue
                    tracks.append({'mask': region, 'rows': [], 'ok': True, 'why': None})
            all_nuclei = ndi.binary_dilation(mask, ring_struct, iterations=1)
            for tr in tracks:
                if not tr['ok']:
                    continue
                hit = np.bincount(lab[tr['mask']].ravel(), minlength=n + 1); hit[0] = 0
                if not hit.any():
                    tr['ok'] = False; tr['why'] = 'lost'; continue
                region = lab == int(hit.argmax()); tr['mask'] = region
                inner = ndi.binary_erosion(region, iterations=RULES['erodePx'])
                ring = ndi.binary_dilation(region, ring_struct, iterations=RULES['ringPx'][1]) & ~ndi.binary_dilation(region, ring_struct, iterations=RULES['ringPx'][0]) & ~all_nuclei & in_cell
                if ring.sum() < RULES['minRingPixels'] or inner.sum() < 20:
                    tr['ok'] = False; tr['why'] = 'ring'; continue
                nk, ck = ktr[inner].mean() - bg_k, ktr[ring].mean() - bg_k
                if min(nk, ck) < RULES['minSignalSd'] * sd_k:
                    tr['ok'] = False; tr['why'] = 'dim'; continue
                cy, cx = ndi.center_of_mass(region)
                tr['rows'].append({'cn': ck / nk, 'nuc': nk, 'cyt': ck, 'area': float(region.sum() * PIXEL_UM ** 2), 'x': cx * PIXEL_UM, 'y': cy * PIXEL_UM, 'ring': int(ring.sum())})
        for tr in tracks:
            if not tr['ok']:
                dropped[tr['why']] += 1; continue
            r = tr['rows']
            cells.append({'id': f'{prefix}-s{s}-c{len(cells) + 1:03d}', 'position': s, 't': minutes, 'cn': [round(q['cn'], 4) for q in r], 'nuc': [round(q['nuc'], 2) for q in r], 'cyt': [round(q['cyt'], 2) for q in r],
                          'nucleusAreaUm2': round(float(np.mean([q['area'] for q in r])), 1), 'xUm': round(r[0]['x'], 1), 'yUm': round(r[0]['y'], 1), 'driftUm': round(float(np.hypot(r[-1]['x'] - r[0]['x'], r[-1]['y'] - r[0]['y'])), 2)})
    return cells, dropped, len(positions), len(frames)


def main(folder):
    folder = pathlib.Path(folder); series = []
    for f in sorted(folder.glob('Figure2C_20211008_*.zip')):
        name = f.stem; z = zipfile.ZipFile(f)
        if not any(CHANNEL['ktr'] in n for n in z.namelist()):
            series.append({'id': name, 'archive': f.name, 'archiveSha256': hashlib.sha256(f.read_bytes()).hexdigest(), 'usable': False, 'reason': 'No ERK-KTR channel in this archive: ' + ', '.join(sorted({re.search(r'_(w\d[^_]*)_', n).group(1) for n in z.namelist() if re.search(r'_(w\d[^_]*)_', n)}))[:200], 'cells': []})
            continue
        cells, dropped, positions, frames = quantify(z, name.replace('Figure2C_20211008_', ''))
        series.append({'id': name, 'archive': f.name, 'archiveSha256': hashlib.sha256(f.read_bytes()).hexdigest(), 'usable': True, 'egfNgPerMl': 10.0, 'positions': positions, 'frames': frames, 'dropped': dropped, 'cells': cells})
        print(name, len(cells), 'cells', dropped, flush=True)
    body = {'schema': 'fold-studio.hela-erk-ktr', 'schemaVersion': 1,
            'source': {'title': 'Quantitative live-cell imaging of GPCR downstream signaling dynamics', 'authors': 'Tany R, Goto Y, Kondo Y, Aoki K', 'journal': 'Biochemical Journal 2022;479(8):883-900', 'doi': '10.1042/BCJ20220021',
                       'repository': 'SSBD ssbd-repos-000232 (232-Tany-SignalingDyn)', 'url': 'https://ssbd.riken.jp/database/project/232', 'licence': 'CC BY',
                       'changes': 'Images were segmented and measured by scripts/build-hela-erk-ktr.py; the images themselves are not bundled. Values are background-subtracted means; no smoothing, no normalisation.'},
            'specimen': {'cellLine': 'HeLa', 'reporters': 'nuclear marker (RFP channel), ERK-KTR (iRFP channel), DORA-RhoA (CFP and FRET channels)', 'stimulus': 'EGF, 10 ng/ml', 'pixelUm': PIXEL_UM, 'frameIntervalMin': 1.0,
                         'note': 'These are the cells of the live-cell experiment. They are not the cell of the electron-microscopy volume.'},
            'readout': {'key': 'cn', 'name': 'ERK-KTR cytoplasm / nucleus', 'unit': 'ratio of background-subtracted mean fluorescence', 'meaning': 'Rises when ERK phosphorylates the reporter and it leaves the nucleus.',
                        'resolution': 'Two regions per cell (nucleus, a perinuclear cytoplasmic ring) from wide-field images at 0.74 µm per pixel. Nothing finer is supported.'},
            'rules': RULES, 'channels': CHANNEL, 'series': series}
    out = pathlib.Path(__file__).resolve().parents[1] / 'fixtures' / 'hela_erk' / 'tany2022_egf_ktr.json'
    out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(body, ensure_ascii=False, separators=(',', ':')))
    print(out, out.stat().st_size, 'bytes', sum(len(s['cells']) for s in series), 'cells', hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == '__main__':
    main(sys.argv[1])
