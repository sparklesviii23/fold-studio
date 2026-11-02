"""Read-only bridge from a Virtual Cell protein to the structures already saved in the research library.

Nothing is written to the library and no engine is called. Every saved `structure` record (any project) is read
through Molecular Intelligence's own checks (intelligence.Lab.record: asset path and SHA-256), parsed with its parser,
and its chains are matched to the protein's UniProt sequence with its `map_sequence` (exact unique fragment, or a
≥ 90 % identical unambiguous global alignment). A structure is listed for a protein only when at least one chain
maps; identity and UniProt coverage are reported per chain. No filename or record name is used to decide identity.

Origin is taken from the record's own provenance fields (RCSB download, engine confidence kind, derived-pose marker,
remote-result marker). Where the record has none, the origin is "imported file, provenance not recorded" — a filename
that looks like an AlphaFold or ColabFold output is shown as a hint, not as provenance. Confidence values come only
from Lab.confidence, which extracts them only for records whose confidence semantics are declared; each engine's
metric keeps its own name and scale and nothing is averaged across engines.

Comparison: Cα atoms of residues mapped to the same UniProt positions, superposed with intelligence.fit (Horn
quaternion). TM-score is evaluated on that RMSD superposition (d0 from the number of compared residues) and is
therefore a lower bound of the TM-align optimum; this is stated with every result.
"""
import json, math, pathlib, re

import intelligence as IM

KINDS = ('experimental', 'predicted', 'designed', 'illustrative', 'unknown')


def _cache(root, sha):
    d = pathlib.Path(root) / 'virtualcell' / 'cache' / 'structures'; d.mkdir(parents=True, exist_ok=True)
    return d / f'{sha}.json'


def _origin(rec):
    d = rec['data']; m = d.get('metadata') or {}; src = str(d.get('source') or ''); ck = d.get('confidenceKind')
    if m.get('pdbId') or src.startswith('https://files.rcsb.org/'):
        return 'experimental', f"RCSB PDB {m.get('pdbId') or src.rsplit('/', 1)[-1]}" + (f" · {m['method']}" if m.get('method') else '')
    if 'illustrative' in src.lower() or m.get('presentationDisclosure'):
        return 'illustrative', src
    if ck and 'BindCraft' in ck or 'RAPID' in src or m.get('rapidCandidate') or m.get('campaignId'):
        return 'designed', src + (f' ({ck})' if ck else '')
    if ck:
        return 'predicted', f'{src} ({ck})'
    hint = None; name = rec['name']
    if re.match(r'AF-[A-Z0-9]+-F\d+-model', name):
        hint = 'filename resembles an AlphaFold DB model'
    elif 'unrelaxed_rank' in name and 'alphafold2' in name:
        hint = 'filename resembles a ColabFold AlphaFold2 output'
    return 'unknown', 'imported file, provenance not recorded' + (f' ({hint}; not verified)' if hint else '')


def _parsed(service, rec, path):
    f = _cache(service.root, rec['data']['sha256'])
    if f.is_file():
        return json.loads(f.read_text())
    try:
        st = IM.parse_structure(path.read_text(errors='replace'), rec['data']['format'])
    except ValueError as e:
        out = {'error': str(e)}
    else:
        chains = {}
        for r in st['residues']:
            c = chains.setdefault(r['chain'], {'seq': [], 'ca': [], 'ids': []})
            ca = next((st['atoms'][i] for i in r['atoms'] if st['atoms'][i]['name'] == 'CA'), None)
            if r['one'] != 'X' and ca:
                c['seq'].append(r['one']); c['ca'].append(list(ca['xyz'])); c['ids'].append(r['id'])
        out = {'chains': {k: {'sequence': ''.join(v['seq']), 'ca': v['ca'], 'ids': v['ids']} for k, v in chains.items() if v['seq']},
               'atoms': len(st['atoms']), 'models': st.get('models')}
    f.write_text(json.dumps(out))
    return out


def _map(uniprot_seq, chain_seq):
    try:
        m = IM.map_sequence(uniprot_seq, chain_seq)
    except ValueError:
        return None
    if m.get('state') != 'verified' or not m.get('positions'):
        return None
    pos = {int(k): int(v) for k, v in m['positions'].items()}            # observed (chain) index → reference (UniProt) position
    same = sum(1 for k, v in pos.items() if chain_seq[k - 1] == uniprot_seq[v - 1])
    return {'positions': pos, 'identity': same / len(pos), 'aligned': len(pos), 'uniprotStart': min(pos.values()), 'uniprotEnd': max(pos.values()),
            'method': m.get('method') or 'Molecular Intelligence map_sequence'}


def sequence(service, accession):
    data = service.cached_fetch('https://rest.uniprot.org/uniprotkb/' + accession.split('-')[0] + '.json')
    return data['sequence']['value']


def for_protein(service, accession):
    """Saved library structures whose chains map to this UniProt entry, with origin, chain coverage and declared confidence."""
    seq = sequence(service, accession); lab = IM.Lab(service); found, skipped = [], []
    for row in service.rows("SELECT r.id, r.name, r.project_id, r.data, p.name AS project FROM records r JOIN projects p ON p.id = r.project_id WHERE r.kind = 'structure' "
                            "AND r.id NOT IN (SELECT id FROM removed_records) ORDER BY r.created"):
        rec = {**row, 'data': json.loads(row['data'])}
        try:
            _, path = lab.record(rec['id'])
        except ValueError as e:
            skipped.append({'id': rec['id'], 'name': rec['name'], 'reason': str(e)}); continue
        parsed = _parsed(service, rec, path)
        if 'error' in parsed:
            skipped.append({'id': rec['id'], 'name': rec['name'], 'reason': parsed['error']}); continue
        chains = []
        for cid, c in parsed['chains'].items():
            m = _map(seq, c['sequence'])
            if m:
                chains.append({'chain': cid, 'length': len(c['sequence']), **{k: v for k, v in m.items() if k != 'positions'}})
        if not chains:
            continue
        kind, origin = _origin(rec); conf = None
        if rec['data'].get('confidenceKind'):
            st = IM.parse_structure(path.read_text(errors='replace'), rec['data']['format']); c = lab.confidence(rec, st)
            vals = {}
            for r, v in zip(st['residues'], c.get('plddt') or []):
                if v is not None:
                    vals.setdefault(r['chain'], []).append(v)
            conf = {'metric': rec['data']['confidenceKind'], 'meanByChain': {k: sum(v) / len(v) for k, v in vals.items() if k in {x['chain'] for x in chains}},
                    'ptm': c.get('ptm'), 'iptm': c.get('iptm'), 'warnings': c.get('warnings'), 'sources': c.get('sources')}
        found.append({'id': rec['id'], 'name': rec['name'], 'project': rec['project'], 'projectId': rec['project_id'], 'format': rec['data']['format'],
                      'sha256': rec['data']['sha256'], 'kind': kind, 'origin': origin, 'chains': chains, 'otherChains': sorted(set(parsed['chains']) - {x['chain'] for x in chains}),
                      'confidence': conf, 'atoms': parsed['atoms']})
    order = {k: i for i, k in enumerate(KINDS)}
    found.sort(key=lambda s: (order[s['kind']], -max(c['aligned'] for c in s['chains'])))
    return {'accession': accession, 'uniprotLength': len(seq), 'structures': found, 'skipped': skipped,
            'method': 'Chains matched to the UniProt sequence by Molecular Intelligence map_sequence; records read with its checksum checks. Read-only.',
            'note': 'A structure is not evidence of a cellular function; predicted and designed models are not measurements.'}


def compare(service, accession, a_id, b_id, chain_a=None, chain_b=None):
    seq = sequence(service, accession); lab = IM.Lab(service); sides = []
    for sid, ch in ((a_id, chain_a), (b_id, chain_b)):
        rec, path = lab.record(sid); rec = {**rec, 'data': rec['data']}; parsed = _parsed(service, rec, path)
        if 'error' in parsed:
            raise ValueError(f"{rec['name']}: {parsed['error']}")
        cands = [(c, _map(seq, parsed['chains'][c]['sequence'])) for c in parsed['chains'] if ch in (None, c)]
        cands = [(c, m) for c, m in cands if m]
        if not cands:
            raise ValueError(f"{rec['name']} has no chain mapped to {accession}.")
        c, m = max(cands, key=lambda x: x[1]['aligned'])
        sides.append({'id': sid, 'name': rec['name'], 'chain': c, 'map': {v: parsed['chains'][c]['ca'][k - 1] for k, v in m['positions'].items()}})
    common = sorted(set(sides[0]['map']) & set(sides[1]['map']))
    if len(common) < 3:
        raise ValueError('Fewer than three UniProt positions are resolved in both structures.')
    mobile = [sides[1]['map'][p] for p in common]; fixed = [sides[0]['map'][p] for p in common]
    al = IM.fit(mobile, fixed)
    d = [IM.dist(IM.apply_fit(p, al), q) for p, q in zip(mobile, fixed)]
    L = len(common); d0 = max(0.5, 1.24 * (L - 15) ** (1 / 3) - 1.8) if L > 21 else 0.5
    tm = sum(1 / (1 + (x / d0) ** 2) for x in d) / L
    per = [{'position': p, 'distance': x} for p, x in zip(common, d)]
    return {'accession': accession, 'reference': {k: sides[0][k] for k in ('id', 'name', 'chain')}, 'moving': {k: sides[1][k] for k in ('id', 'name', 'chain')},
            'compared': L, 'uniprotRange': [common[0], common[-1]], 'rmsd': al['rmsd'], 'tmScore': tm, 'd0': d0,
            'largestDeviations': sorted(per, key=lambda r: -r['distance'])[:10], 'over3A': sum(1 for x in d if x > 3) / L,
            'method': 'Cα of residues at identical UniProt positions; Horn quaternion superposition (Molecular Intelligence fit).',
            'tmNote': 'TM-score evaluated on the RMSD superposition with d0 from the compared length: a lower bound of the TM-align optimum, not TM-align.'}
