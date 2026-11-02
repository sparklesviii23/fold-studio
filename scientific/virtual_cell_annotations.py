"""Proteome-wide annotations for the Virtual Cell: identifiers, subcellular localization and Reactome pathways.

Sources (fetched from the original providers into <library>/virtualcell/data/annotations/original, never committed):
  HPA       Human Protein Atlas subcellular resource: immunofluorescence location calls with reliability
            (Enhanced / Supported / Approved / Uncertain) and cell-cycle dependency. Images come from several cell
            lines, so a call is a general human annotation, not a measurement in the cell context being viewed.
  UniProt   reviewed human entries: accession, HGNC symbol, synonyms, Ensembl, curated subcellular location with ECO
            evidence (ECO:0000269 = experimental; others = inferred), GO cellular component, PDB cross-references.
  Reactome  lowest-level pathway membership (UniProt2Reactome, human rows, with evidence code), gene-symbol pathway
            sets (GMT) and the pathway hierarchy.

Localization is compartment-level only. Renderer layers light up for the HPA terms listed in LAYERS; every other term
is reported per protein but has no geometry in the cell view, and no position inside a compartment is ever implied.
"""
import gzip, hashlib, io, json, math, pathlib, re, sys, time, urllib.request, zipfile

DIR = ('virtualcell', 'data', 'annotations')
FILES = {
    'subcellular_location.tsv.zip': ('https://www.proteinatlas.org/download/tsv/subcellular_location.tsv.zip', 'hpa'),
    'uniprot_human_reviewed.tsv.gz': ('https://rest.uniprot.org/uniprotkb/stream?query=%28organism_id%3A9606%29+AND+%28reviewed%3Atrue%29'
                                      '&fields=accession,gene_primary,gene_synonym,xref_ensembl,xref_hgnc,cc_subcellular_location,go_c,xref_pdb,length&format=tsv&compressed=true', 'uniprot'),
    'ReactomePathways.gmt.zip': ('https://reactome.org/download/current/ReactomePathways.gmt.zip', 'reactome'),
    'ReactomePathways.txt': ('https://reactome.org/download/current/ReactomePathways.txt', 'reactome'),
    'ReactomePathwaysRelation.txt': ('https://reactome.org/download/current/ReactomePathwaysRelation.txt', 'reactome'),
    'UniProt2Reactome.txt': ('https://reactome.org/download/current/UniProt2Reactome.txt', 'reactome'),
}
# HPA location term → renderer layer of the virtual cell view (virtual_cell.CHANNELS ids). Documented mapping; terms
# absent here (cytosol, plasma membrane, cytoskeleton, centrosome, cilia, sperm structures, …) are listed, not drawn.
LAYERS = {
    'dna': ['Nucleoplasm', 'Nuclear bodies', 'Nuclear speckles', 'Nuclear membrane', 'Nucleoli', 'Nucleoli fibrillar center', 'Nucleoli rim', 'Mitotic chromosome', 'Kinetochore'],
    'mito': ['Mitochondria'], 'er': ['Endoplasmic reticulum'], 'golgi': ['Golgi apparatus'],
    'vesicles': ['Vesicles', 'Endosomes', 'Lysosomes', 'Peroxisomes'],
}
TERM_LAYER = {t: k for k, ts in LAYERS.items() for t in ts}
RELIABLE = ('Enhanced', 'Supported', 'Approved')          # 'Uncertain' calls never drive the renderer
TOPOLOGY = re.compile(r'membrane protein|anchor|side$|^Note=', re.I)
ECO = re.compile(r'\{([^}]*)\}')
_IX = {}


def folder(root):
    return pathlib.Path(root).joinpath(*DIR)


def _sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------- install / build

def install(root):
    """Download any missing original file, then build the index. Run as a background job (vcell_annotations_install)."""
    org = folder(root) / 'original'; org.mkdir(parents=True, exist_ok=True)
    for name, (url, _) in FILES.items():
        if (org / name).is_file() and (org / name).stat().st_size > 1000:
            continue
        print('downloading', name, flush=True)
        req = urllib.request.Request(url, headers={'User-Agent': 'FoldStudio/4.3 (research)'})
        with urllib.request.urlopen(req, timeout=300) as r, open(org / (name + '.part'), 'wb') as f:
            while (b := r.read(1 << 20)):
                f.write(b)
        (org / (name + '.part')).rename(org / name)
    try:
        with urllib.request.urlopen('https://reactome.org/ContentService/data/database/version', timeout=30) as r:
            (org / 'reactome_release.txt').write_text(r.read().decode().strip())
    except Exception as e:                                  # the release number is metadata; its absence is recorded
        print('Reactome release unavailable:', e, flush=True)
    return build(root)


def _uniprot_locations(text):
    """Curated UniProt subcellular location text → [{location, isoform, evidence, eco}]; topology statements and notes dropped."""
    out = []
    for block in text.split('SUBCELLULAR LOCATION:')[1:]:
        block = block.split('Note=')[0].strip(); iso = None
        m = re.match(r'\[([^\]]+)\]:\s*', block)
        if m:
            iso, block = m.group(1), block[m.end():]
        for sentence in re.split(r'\.\s+|\.$', block):
            for item in sentence.split(';'):
                eco = [c for g in ECO.findall(item) for c in g.split('|') if c.startswith('ECO:')]
                loc = ECO.sub('', item).strip(' .')
                if loc and not TOPOLOGY.search(loc):
                    out.append({'location': loc, 'isoform': iso, 'eco': sorted(set(eco)),
                                'evidence': 'experimental' if 'ECO:0000269' in eco else 'inferred' if eco else 'unstated'})
    return out


def build(root):
    org = folder(root) / 'original'
    missing = [n for n in FILES if not (org / n).is_file()]
    if missing:
        raise ValueError('Missing annotation files: ' + ', '.join(missing))
    genes, acc_sym = {}, {}

    def rec(sym):
        return genes.setdefault(sym, {'symbol': sym, 'uniprot': [], 'ensembl': [], 'hgnc': None, 'synonyms': [], 'pdb': [], 'length': None,
                                      'hpa': None, 'uniprotLocations': [], 'goComponent': [], 'reactome': []})
    with gzip.open(org / 'uniprot_human_reviewed.tsv.gz', 'rt') as f:
        head = next(f).rstrip('\n').split('\t'); col = {h: i for i, h in enumerate(head)}
        for line in f:
            c = line.rstrip('\n').split('\t'); sym = c[col['Gene Names (primary)']].strip().upper()
            if not sym or ';' in sym:
                continue
            r = rec(sym); acc = c[col['Entry']]; r['uniprot'].append(acc); acc_sym[acc] = sym
            r['synonyms'] = sorted(set(r['synonyms']) | {s.upper() for s in c[col['Gene Names (synonym)']].split() if s})
            r['ensembl'] = sorted(set(r['ensembl']) | set(re.findall(r'ENSG\d+', c[col['Ensembl']])))
            r['hgnc'] = r['hgnc'] or (c[col['HGNC']].strip(';').split(';')[0] or None)
            r['pdb'] = sorted(set(r['pdb']) | {p for p in c[col['PDB']].split(';') if p})
            r['length'] = r['length'] or int(c[col['Length']] or 0) or None
            r['uniprotLocations'] += [{**x, 'accession': acc} for x in _uniprot_locations(c[col['Subcellular location [CC]']])]
            r['goComponent'] = sorted(set(r['goComponent']) | {g.strip() for g in c[col['Gene Ontology (cellular component)']].split(';') if g.strip()})
    with zipfile.ZipFile(org / 'subcellular_location.tsv.zip') as z:
        lines = z.read(z.namelist()[0]).decode().splitlines()
    head = lines[0].split('\t'); col = {h: i for i, h in enumerate(head)}; hpa_n = 0
    for line in lines[1:]:
        c = line.split('\t'); sym = c[col['Gene name']].strip().upper()
        if not sym:
            continue
        split = lambda k: [t for t in c[col[k]].split(';') if t]
        r = rec(sym); hpa_n += 1
        r['ensembl'] = sorted(set(r['ensembl']) | {c[col['Gene']]})
        r['hpa'] = {'ensembl': c[col['Gene']], 'reliability': c[col['Reliability']], 'main': split('Main location'), 'additional': split('Additional location'),
                    'extracellular': split('Extracellular location'), 'cellCycleDependency': c[col['Cell cycle dependency']] or None,
                    'singleCellVariation': split('Single-cell variation intensity') + split('Single-cell variation spatial')}
    names = {}
    for line in (org / 'ReactomePathways.txt').read_text().splitlines():
        c = line.split('\t')
        if len(c) == 3 and c[2] == 'Homo sapiens':
            names[c[0]] = c[1]
    parents = {}
    for line in (org / 'ReactomePathwaysRelation.txt').read_text().splitlines():
        a, _, b = line.partition('\t')
        if b.startswith('R-HSA'):
            parents.setdefault(b, []).append(a)
    pathways = {pid: {'name': n, 'parents': parents.get(pid, []), 'genes': []} for pid, n in names.items()}
    with zipfile.ZipFile(org / 'ReactomePathways.gmt.zip') as z:
        for line in z.read(z.namelist()[0]).decode().splitlines():
            c = line.split('\t')
            if len(c) > 2 and c[1] in pathways:
                pathways[c[1]]['genes'] = sorted({g.upper() for g in c[2:] if g})
    with open(org / 'UniProt2Reactome.txt') as f:
        for line in f:
            if not line.rstrip().endswith('Homo sapiens'):
                continue
            c = line.rstrip('\n').split('\t'); acc = c[0].split('-')[0]
            if acc in acc_sym and c[1] in pathways:
                r = genes[acc_sym[acc]]
                if not any(x['id'] == c[1] for x in r['reactome']):
                    r['reactome'].append({'id': c[1], 'evidence': c[4]})
    files = {n: {'url': FILES[n][0], 'sha256': _sha(org / n), 'bytes': (org / n).stat().st_size,
                 'retrieved': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime((org / n).stat().st_mtime))} for n in FILES}
    rel = org / 'reactome_release.txt'
    manifest = {'built': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'files': files, 'reactomeRelease': rel.read_text().strip() if rel.is_file() else None,
                'counts': {'genes': len(genes), 'uniprotEntries': len(acc_sym), 'hpaGenes': hpa_n, 'pathways': len(pathways),
                           'pathwaysWithGenes': sum(1 for p in pathways.values() if p['genes'])},
                'layers': LAYERS, 'reliableTiers': list(RELIABLE)}
    out = folder(root)
    with gzip.open(out / 'index.json.gz.part', 'wt') as f:
        json.dump({'genes': genes, 'pathways': pathways}, f, separators=(',', ':'))
    (out / 'index.json.gz.part').rename(out / 'index.json.gz')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1))
    print('built', manifest['counts'], flush=True)
    return manifest


# ---------------------------------------------------------------- index

class Index:
    def __init__(self, path, manifest):
        with gzip.open(path, 'rt') as f:
            d = json.load(f)
        self.manifest = manifest; self.genes = d['genes']; self.pathways = d['pathways']
        self.by_acc, self.by_ens, self.alias = {}, {}, {}
        for s, r in self.genes.items():
            for a in r['uniprot']:
                self.by_acc[a] = s
            for e in r['ensembl']:
                self.by_ens.setdefault(e, set()).add(s)
            for a in r['synonyms']:
                if a not in self.genes:
                    self.alias.setdefault(a, set()).add(s)
        self.children = {}
        for pid, p in self.pathways.items():
            for q in p['parents']:
                self.children.setdefault(q, []).append(pid)


def index(root):
    f = folder(root) / 'index.json.gz'
    if not f.is_file():
        return None
    key = (str(f), f.stat().st_mtime)
    if key not in _IX:
        _IX.clear(); _IX[key] = Index(f, json.loads((folder(root) / 'manifest.json').read_text()))
    return _IX[key]


def resolve(ix, query):
    """HGNC symbol, alias, UniProt accession or Ensembl gene ID → one symbol, or an explicit ambiguity / miss."""
    q = str(query or '').strip()
    u = q.upper().split('-')[0] if re.match(r'^[A-Z0-9]{6,10}(-\d+)?$', q.upper()) else q.upper()
    if u in ix.genes:
        return {'status': 'resolved', 'symbol': u, 'matchedBy': 'symbol'}
    if u in ix.by_acc:
        return {'status': 'resolved', 'symbol': ix.by_acc[u], 'matchedBy': 'UniProt accession'}
    e = u.split('.')[0]
    if e in ix.by_ens:
        c = sorted(ix.by_ens[e])
        return {'status': 'resolved', 'symbol': c[0], 'matchedBy': 'Ensembl gene ID'} if len(c) == 1 else {'status': 'ambiguous', 'candidates': c, 'matchedBy': 'Ensembl gene ID'}
    if u in ix.alias:
        c = sorted(ix.alias[u])
        return {'status': 'resolved', 'symbol': c[0], 'matchedBy': 'alias (previous or alternative symbol)'} if len(c) == 1 else \
            {'status': 'ambiguous', 'candidates': c, 'matchedBy': 'alias shared by several genes'}
    return {'status': 'unknown', 'query': q}


def localization(ix, sym):
    r = ix.genes[sym]; h = r['hpa']
    hpa = None
    if h:
        terms = [{'term': t, 'main': t in h['main'], 'layer': TERM_LAYER.get(t)} for t in h['main'] + h['additional']]
        hpa = {**h, 'terms': terms, 'drawn': h['reliability'] in RELIABLE,
               'scope': 'General human annotation from immunofluorescence in several cell lines (HPA); not specific to this cell context.'}
    return {'hpa': hpa, 'uniprot': r['uniprotLocations'], 'goComponent': r['goComponent'],
            'layers': sorted({t['layer'] for t in (hpa['terms'] if hpa and hpa['drawn'] else []) if t['layer']}),
            'note': 'Compartment-level annotations only: positions inside a compartment are not known and are not drawn.'}


def channel_sets(ix):
    """Renderer layer → symbols with a reliable HPA call (main or additional) in one of its terms."""
    out = {k: set() for k in LAYERS}
    for s, r in ix.genes.items():
        h = r['hpa']
        if h and h['reliability'] in RELIABLE:
            for t in h['main'] + h['additional']:
                if t in TERM_LAYER:
                    out[TERM_LAYER[t]].add(s)
    return out


def _logcomb(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def _hyper_sf(k, N, K, n):
    """P(X ≥ k) for X ~ Hypergeometric(population N, K successes, n draws)."""
    top = min(K, n); den = _logcomb(N, n)
    return min(1.0, sum(math.exp(_logcomb(K, i) + _logcomb(N - K, n - i) - den) for i in range(k, top + 1)))


def enrichment(ix, query, universe, min_size=5, max_size=500, limit=25):
    """Over-representation of `query` genes in Reactome lowest-level gene sets, universe-restricted (one-sided
    hypergeometric, Benjamini–Hochberg). The universe is the set of genes the context measures."""
    U = set(universe); Q = set(query) & U; rows = []
    if not Q:
        return {'tested': 0, 'rows': [], 'queryInUniverse': 0, 'universe': len(U)}
    for pid, p in ix.pathways.items():
        G = set(p['genes']) & U
        if not min_size <= len(G) <= max_size or pid in ix.children:
            continue
        k = len(G & Q)
        if k:
            rows.append({'id': pid, 'name': p['name'], 'size': len(G), 'hits': sorted(G & Q), 'p': _hyper_sf(k, len(U), len(G), len(Q))})
    tested = sum(1 for pid, p in ix.pathways.items() if pid not in ix.children and min_size <= len(set(p['genes']) & U) <= max_size)
    rows.sort(key=lambda r: r['p'])
    prev = 1.0
    for i in range(len(rows) - 1, -1, -1):                   # BH over all tested sets (sets with no hit have p = 1)
        prev = min(prev, rows[i]['p'] * tested / (i + 1)); rows[i]['fdr'] = prev
    return {'tested': tested, 'universe': len(U), 'queryInUniverse': len(Q), 'rows': rows[:limit],
            'method': 'one-sided hypergeometric test per lowest-level Reactome pathway, Benjamini–Hochberg FDR across tested pathways'}


def ancestry(ix, pid, depth=12):
    """Path(s) from a pathway up to its top-level Reactome event, first parent at each step."""
    chain, cur = [], pid
    while cur in ix.pathways and len(chain) < depth:
        chain.append({'id': cur, 'name': ix.pathways[cur]['name']})
        ps = ix.pathways[cur]['parents']
        if not ps:
            break
        cur = ps[0]
    return chain[::-1]


if __name__ == '__main__':
    install(sys.argv[1])
