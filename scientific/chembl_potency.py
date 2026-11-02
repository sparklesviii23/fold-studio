"""Compound potency per human target from ChEMBL (CC BY-SA 3.0), and the fraction of each target inhibited at a concentration.

Only biochemical/binding assays (assay_type B) against SINGLE PROTEIN human targets with a pChEMBL value are used; the
potency per gene is the median pChEMBL over those measurements (IC50, Ki, Kd and EC50 mixed, as pChEMBL defines them).
Inhibition at free concentration C is C / (C + IC50) — a single-site, Hill slope 1 approximation. It ignores cellular
permeability, ATP competition in cells, protein binding and exposure; the result is a stated calculation, not a measurement.
"""
import hashlib
import json
import re
import pathlib
import time
import urllib.parse
import urllib.request

API = 'https://www.ebi.ac.uk/chembl/api/data'


def _get(path, **q):
    url = f'{API}/{path}.json?' + urllib.parse.urlencode(q)
    raw = urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json'}), timeout=60).read()
    return json.loads(raw), raw, url


def potency(root, name):
    """Cached per compound name: ChEMBL molecule chosen, and median pChEMBL per human gene."""
    d = pathlib.Path(root) / 'oncology' / 'chembl'; d.mkdir(parents=True, exist_ok=True)
    f = d / (hashlib.sha256(name.lower().encode()).hexdigest()[:16] + '.json')
    if f.is_file():
        return json.loads(f.read_text())
    mols, _, _ = _get('molecule/search', q=name, limit=10)
    pick = next((m for m in mols['molecules'] if (m.get('pref_name') or '').upper() == name.upper()), None) \
        or next((m for m in mols['molecules'] if any((s.get('molecule_synonym') or '').upper() == name.upper() for s in m.get('molecule_synonyms') or [])), None)
    out = {'compound': name, 'retrieved': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'licence': 'ChEMBL, CC BY-SA 3.0', 'targets': {}}
    if not pick:
        out['error'] = f'No ChEMBL molecule matches the name {name!r} exactly.'
        f.write_text(json.dumps(out)); return out
    mid = pick['molecule_chembl_id']; out['molecule'] = {'id': mid, 'name': pick.get('pref_name'), 'maxPhase': pick.get('max_phase')}
    acts, offset, digest = [], 0, hashlib.sha256()
    while True:
        a, raw, url = _get('activity', molecule_chembl_id=mid, assay_type='B', pchembl_value__isnull='false', target_organism='Homo sapiens', limit=1000, offset=offset,
                           only='target_chembl_id,pchembl_value,standard_type')
        acts += a['activities']; digest.update(raw); offset += 1000
        if not a['page_meta'].get('next'):
            break
    by_target = {}
    for x in acts:
        by_target.setdefault(x['target_chembl_id'], []).append((float(x['pchembl_value']), x['standard_type']))
    tf = d / 'targets.json'; tcache = json.loads(tf.read_text()) if tf.is_file() else {}       # ChEMBL target id → gene symbol, shared across compounds
    for tid, vals in by_target.items():
        if not isinstance(tcache.get(tid), dict):          # {'genes': [...], 'acc': [...]}; older caches held the gene list only
            t, _, _ = _get(f'target/{tid}')
            single = t.get('target_type') == 'SINGLE PROTEIN'
            tcache[tid] = {'genes': [s['component_synonym'].upper() for c in t['target_components'] for s in c['target_component_synonyms'] if s['syn_type'] == 'GENE_SYMBOL'][:1] if single else [],
                           'acc': [c['accession'] for c in t['target_components'] if c.get('accession')][:1] if single else []}
        genes = tcache[tid]['genes']
        for g in genes:
            v = sorted(p for p, _ in vals); med = v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2
            out['targets'][g] = {'pchembl': round(med, 2), 'ic50_uM': round(10 ** (6 - med), 6), 'n': len(v), 'types': sorted({s for _, s in vals}), 'target': tid,
                                 'uniprot': (tcache[tid]['acc'] or [None])[0]}
    tf.write_text(json.dumps(tcache))
    out['activities'] = len(acts); out['sha256'] = digest.hexdigest()
    f.write_text(json.dumps(out)); return out


def inhibition(pot, conc_uM):
    """Fraction of each target inhibited at a free concentration (µM): C / (C + IC50)."""
    return {g: conc_uM / (conc_uM + t['ic50_uM']) for g, t in pot.get('targets', {}).items()}


def bindingdb(root, pot, genes):
    """Independent cross-check from BindingDB (CC BY 3.0): the same compound (ChEMBL → BindingDB through EBI UniChem, no structure
    matching) against each target's UniProt entry; median of numeric Ki / IC50 / Kd values in nM."""
    d = pathlib.Path(root) / 'oncology' / 'bindingdb'; d.mkdir(parents=True, exist_ok=True)
    mid = (pot.get('molecule') or {}).get('id')
    if not mid:
        return {}
    f = d / f'unichem_{mid}.json'
    if not f.is_file():
        req = urllib.request.Request('https://www.ebi.ac.uk/unichem/api/v1/compounds', data=json.dumps({'compound': mid, 'sourceID': 1, 'type': 'sourceID'}).encode(), headers={'Content-Type': 'application/json'})
        u = json.loads(urllib.request.urlopen(req, timeout=60).read())
        f.write_text(json.dumps([s['compoundId'] for c in u.get('compounds', []) for s in c.get('sources', []) if s['id'] == 31]))
    bdb = set(json.loads(f.read_text()))
    out = {}
    for g in genes:
        acc = (pot['targets'].get(g) or {}).get('uniprot')
        if not acc or not bdb:
            continue
        fa = d / f'target_{acc}.json'
        if not fa.is_file():
            raw = urllib.request.urlopen(f'https://bindingdb.org/rest/getLigandsByUniprots?uniprot={acc}&cutoff=100000&response=application/json', timeout=120).read()
            fa.write_bytes(raw)
        rows = json.loads(fa.read_text()).get('getLindsByUniprotsResponse', {}).get('affinities', [])
        vals = sorted(float(r['affinity']) for r in rows if r.get('monomerid') in bdb and re.fullmatch(r'[0-9.]+', str(r.get('affinity', ''))))
        if vals:
            out[g] = {'median_nM': vals[len(vals) // 2], 'n': len(vals), 'bindingdbId': sorted(bdb)[0]}
    return out
