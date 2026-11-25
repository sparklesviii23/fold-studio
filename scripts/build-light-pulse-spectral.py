#!/usr/bin/env python3
"""Build fixtures/light_pulse/olson2017_ccasr_spectral.json from Dataset EV2 of Olson, Tzouanas & Tabor 2017.

Usage:  python3 scripts/build-light-pulse-spectral.py <folder holding the extracted dataset_ev2_ccasr_data_and_analysis>

The folder comes from MSB-13-926-s010.zip inside the supplementary archive of PMC5408778
(https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5408778/supplementaryFiles). Standard library only.

What is kept: the forward (`aas`) and reverse (`ras`) action spectra, one steady-state point per LED and intensity after
480 minutes of constant light, and the parameters of the published model. Nothing is averaged, rescaled or dropped.
"""
import hashlib, json, pathlib, re, sys, zipfile
import xml.etree.ElementTree as ET

M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def sheet(path):
    """First worksheet of an .xlsx as a list of dicts keyed by the header row."""
    z = zipfile.ZipFile(path); shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        shared = [''.join(t.text or '' for t in si.iter(M + 't')) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(M + 'si')]
    rels = {r.get('Id'): r.get('Target') for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    first = ET.fromstring(z.read('xl/workbook.xml')).find(M + 'sheets')[0]
    target = rels[first.get(R + 'id')]; target = target.lstrip('/') if target.startswith('/') else 'xl/' + target
    rows = []
    for row in ET.fromstring(z.read(target)).iter(M + 'row'):
        cells = {}
        for c in row.findall(M + 'c'):
            v = c.find(M + 'v'); t = c.get('t')
            if v is None:
                continue
            n = 0
            for ch in re.match(r'[A-Z]+', c.get('r')).group():
                n = n * 26 + ord(ch) - 64
            if t == 's':
                cells[n - 1] = shared[int(v.text)]
            elif t in ('str', 'b', 'e'):
                cells[n - 1] = v.text
            else:
                cells[n - 1] = float(v.text)
        rows.append([cells.get(i) for i in range(max(cells) + 1)] if cells else [])
    head = rows[0]
    return [dict(zip(head, r + [None] * (len(head) - len(r)))) for r in rows[1:] if r]


def main(folder):
    folder = pathlib.Path(folder); members = {}

    def load(rel):
        f = folder / rel; members[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
        return f

    def spectrum(kind):
        out = []
        for r in sheet(load(f'ccasr_data/{kind}/rgv2_wholepop_{kind}_concise.xlsx')):
            out.append({'led': r['Top LED ID'] or 'None', 'centroidNm': round(r['Top Centroid (nm)'], 1) if r['Top Centroid (nm)'] is not None else None, 'intensity': round(r['Spectral intensity'], 6),
                        'green': round(r['Activating intensity'], 6), 'greenCentroidNm': round(r['Bot Centroid (nm)'], 1), 't': r['Data time point'], 'fl': round(r['FL1 Mean'], 3), 'rcv': round(r['FL1 RCV'], 4),
                        'run': r['Run ID'], 'well': int(r['Well']), 'sample': r['Sample ID']})
        return sorted(out, key=lambda r: (r['led'], r['intensity'], r['run']))
    forward, reverse = spectrum('aas'), spectrum('ras')
    published = sheet(load('ccasr_model_parameters/rgv2_m01/k1_k2_results.xlsx'))
    params = json.loads(load('ccasr_model_parameters/rgv2_m01/all_data_with_k2_holds_ratio_onetau_k_fixed.params').read_text())
    scalar = {p[0]: {'value': p[1], 'fitted': bool(p[2])} for p in params if not p[0].startswith(('k1_', 'k2_'))}
    leds = [{'id': r['LED name'], 'centroidNm': r['Centroid'], 'publishedK1': r['k1 (1/min/umol/m2/s)'], 'publishedK2': r['k2 (1/min/umol/m2/s)']} for r in published]
    body = {
        'schema': 'fold-studio.light-pulse-spectral', 'schemaVersion': 1,
        'source': {'title': 'A photoconversion model for full spectral programming and multiplexing of optogenetic systems', 'authors': 'Olson EJ, Tzouanas CN, Tabor JJ', 'journal': 'Molecular Systems Biology 2017;13(4):926',
                   'doi': '10.15252/msb.20167456', 'pmcid': 'PMC5408778', 'licence': 'CC BY 4.0', 'dataset': 'Dataset EV2 · CcaSR measurements and analysis (MSB-13-926-s010.zip)',
                   'retrievedFrom': 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5408778/supplementaryFiles', 'memberSha256': members,
                   'changes': 'Columns renamed; values rounded to the precision shown; rows sorted. No point was averaged, rescaled or removed. The spectral-validation plates (folder sv) are not included: their concise table does not name the LEDs of each well.'},
        'units': {'light': 'µmol m⁻² s⁻¹', 'fluorescence': 'MEFL', 'time': 'min'},
        'design': {'forward': 'Forward action spectrum (aas): one LED alone at 12 intensities for 480 min; the reporter after 480 min.',
                   'reverse': 'Reverse action spectrum (ras): the same LED and intensities on top of 1.25 µmol m⁻² s⁻¹ of green light (520-2-KB).',
                   'control': "Rows with led 'None' carry no spectral LED: dark wells in the forward plates, green-only wells in the reverse plates."},
        'leds': leds, 'forward': forward, 'reverse': reverse,
        'publishedModel': {'name': 'Olson et al. 2017, CcaSR model rgv2_m01', 'parameters': scalar, 'greenLed': '520-2-KB',
                           'equations': ['dy/dt = k1(I)·(1 − y) − (k2(I) + kdr + kg)·y,  k1(I) = Σ k1_led·I_led,  k2(I) = Σ k2_led·I_led', 'P(t) = b + a·rⁿ/(kⁿ + rⁿ),  r = y/(1 − y)', 'dg/dt = kg·(P(t − τ) − g)'],
                           'note': 'Parameters as distributed with the dataset (all_data_with_k2_holds_ratio_onetau_k_fixed). The published fit used the action spectra and every step-on and step-off plate; the dynamic programs were its validation.'},
    }
    out = pathlib.Path(__file__).resolve().parents[1] / 'fixtures' / 'light_pulse' / 'olson2017_ccasr_spectral.json'
    out.write_text(json.dumps(body, ensure_ascii=False, separators=(',', ':')))
    print(out, out.stat().st_size, 'bytes', len(forward), 'forward', len(reverse), 'reverse', len(leds), 'LEDs', hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == '__main__':
    main(sys.argv[1])
