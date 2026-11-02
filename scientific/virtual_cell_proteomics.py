"""Measured protein abundance for a cell context: importer, index and RNA–protein comparison.

Datasets integrated (<library>/virtualcell/data/paxdb_hepg2/original; PaxDb, CC BY 4.0, von Mering lab):
  9606-iBAQ_HepG2_Geiger_2012_uniprot.txt   iBAQ (MaxQuant, mapped by the authors), 6,739 proteins
  9606-HepG2_Geiger_2012.txt                spectral counting (PaxDb pipeline), 3,546 proteins
Both derive from Geiger T et al., Mol Cell Proteomics 2012;11:M111.014050 (eleven common cell lines, HepG2 among
them). PaxDb reports one abundance per protein in ppm (parts per million of the proteome molecules in the sample);
replicate values are not published there, so none are shown. A protein absent from a dataset is "not reported"
(below detection or not identified), never zero.

Identifiers: rows carry a STRING Ensembl protein ID and a gene name. The ENSP is mapped through the GENCODE V29 index
(ENSP → transcript → gene, UniProt isoform) when present; otherwise the gene name is resolved through the annotation
index (symbol or unambiguous alias). Ambiguous or unresolved rows are kept and counted, not guessed.

`import_table` accepts any TSV/CSV abundance table with explicit columns, unit, method and Cellosaurus RRID, so further
proteomics datasets can be added without code changes.
"""
import csv, hashlib, json, pathlib, re, sqlite3, time

DIR = ('virtualcell', 'data', 'paxdb_hepg2')
PAXDB = {
    '9606-iBAQ_HepG2_Geiger_2012_uniprot.txt': {'id': 'geiger2012_ibaq', 'method': 'iBAQ (MaxQuant), values mapped by the authors; PaxDb ppm normalisation'},
    '9606-HepG2_Geiger_2012.txt': {'id': 'geiger2012_sc', 'method': 'Spectral counting; PaxDb ppm normalisation'},
}
CONTEXT = 'CVCL_0027'
CITATION = 'Geiger T, Wehner A, Schaab C, Cox J, Mann M. Mol Cell Proteomics 2012;11:M111.014050. Via PaxDb (Huang Q et al., Proteomics 2023).'


def folder(root):
    return pathlib.Path(root).joinpath(*DIR)


def _db(root, write=False):
    f = folder(root) / 'proteomics.sqlite'
    if write:
        db = sqlite3.connect(f)
        db.executescript('CREATE TABLE IF NOT EXISTS datasets(id TEXT PRIMARY KEY, data TEXT);'
                         'CREATE TABLE IF NOT EXISTS abundance(dataset TEXT, symbol TEXT, uniprot TEXT, source_id TEXT, value REAL, extra TEXT, mapping TEXT);'
                         'CREATE INDEX IF NOT EXISTS ab_symbol ON abundance(symbol); CREATE INDEX IF NOT EXISTS ab_ds ON abundance(dataset);')
        return db
    return sqlite3.connect(f'file:{f}?mode=ro', uri=True) if f.is_file() else None


def _ensp_map(root):
    """ENSP (unversioned) → (gene symbol, UniProt isoform) from the GENCODE V29 transcript index, if built."""
    import virtual_cell_transcripts as VT
    f = VT.folder(root) / 'transcripts.sqlite'; out = {}
    if f.is_file():
        db = sqlite3.connect(f'file:{f}?mode=ro', uri=True)
        for (d,) in db.execute('SELECT data FROM tx'):
            t = json.loads(d)
            if t.get('protein_id'):
                out[t['protein_id'].split('.')[0]] = (t['gene_name'], t.get('uniprot'))
        db.close()
    return out


def _resolver(root):
    import virtual_cell_annotations as VA
    ix = VA.index(root); ensp = _ensp_map(root)

    def resolve(gene, ensp_id):
        e = re.sub(r'^9606\.', '', ensp_id or '').split('.')[0]
        if e in ensp:
            sym, iso = ensp[e]
            acc = ((ix.genes.get(sym) or {}).get('uniprot') or [None])[0] if ix else None
            return sym, iso or acc, 'ENSP via GENCODE V29'
        if ix and gene:
            r = VA.resolve(ix, gene)
            if r['status'] == 'resolved':
                return r['symbol'], (ix.genes[r['symbol']]['uniprot'] or [None])[0], 'gene name (' + r['matchedBy'] + ')'
            return None, None, f"gene name {r['status']}"
        return None, None, 'unresolved'
    return resolve


def _store(root, meta, rows, resolve):
    db = _db(root, write=True)
    db.execute('DELETE FROM abundance WHERE dataset=?', (meta['id'],))
    counts = {'rows': 0, 'resolved': 0, 'unresolved': 0}; seen = set(); dup = 0
    for gene, sid, value, extra in rows:
        sym, acc, how = resolve(gene, sid); counts['rows'] += 1
        counts['resolved' if sym else 'unresolved'] += 1
        if sym and sym in seen:
            dup += 1
        seen.add(sym)
        db.execute('INSERT INTO abundance VALUES(?,?,?,?,?,?,?)', (meta['id'], sym, acc, sid or gene, value, json.dumps(extra), how))
    counts['duplicateSymbols'] = dup; meta['counts'] = counts
    db.execute('INSERT OR REPLACE INTO datasets VALUES(?,?)', (meta['id'], json.dumps(meta))); db.commit(); db.close()
    return meta


def _paxdb(path):
    head, cols, rows = {}, None, []
    for line in path.read_text().splitlines():
        if line.startswith('#') and ':' in line and cols is None and not line.startswith('#gene_name'):
            k, _, v = line[1:].partition(':'); head[k.strip()] = v.strip(); continue
        if line.startswith('#gene_name'):
            cols = line[1:].split('\t'); continue
        if cols and line.strip():
            c = line.split('\t'); d = dict(zip(cols, c))
            rows.append((d.get('gene_name'), d.get('string_external_id'), float(d['abundance']), {k: d[k] for k in cols if k not in ('gene_name', 'string_external_id', 'abundance')}))
    return head, rows


def build(root):
    org = folder(root) / 'original'; resolve = _resolver(root); out = []
    for name, spec in PAXDB.items():
        f = org / name
        if not f.is_file():
            continue
        head, rows = _paxdb(f)
        meta = {'id': spec['id'], 'name': head.get('name'), 'cellosaurus': CONTEXT, 'cellLine': 'Hep G2 (as reported by the authors)', 'method': spec['method'],
                'unit': 'ppm (parts per million of proteome molecules, PaxDb)', 'replicates': 'not published by PaxDb (one integrated value per protein)',
                'missing': 'not reported = below detection or not identified (not zero)', 'coverage': head.get('coverage'), 'paxdbId': head.get('id'),
                'paxdbScore': head.get('score'), 'publication': head.get('link'), 'year': head.get('publication_year'), 'citation': CITATION,
                'source': f'https://pax-db.org/downloads/latest/datasets/9606/{name}', 'licence': 'CC BY 4.0 (PaxDb)',
                'sha256': hashlib.sha256(f.read_bytes()).hexdigest(), 'imported': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        out.append(_store(root, meta, rows, resolve))
    print('built', [(m['id'], m['counts']) for m in out], flush=True)
    return out


def import_table(root, path, spec):
    """Generic importer. spec: {id, name, cellosaurus, method, unit, gene_column | accession_column, value_column,
    [replicate_column], [delimiter], citation, licence}. Rows with an empty value are recorded as missing (None)."""
    for k in ('id', 'name', 'cellosaurus', 'method', 'unit', 'value_column', 'citation', 'licence'):
        if not spec.get(k):
            raise ValueError(f'Proteomics import needs "{k}".')
    if not re.fullmatch(r'[a-z0-9_]{3,40}', spec['id']) or not re.fullmatch(r'CVCL_[0-9A-Z]{4}', spec['cellosaurus']):
        raise ValueError('Invalid dataset id or Cellosaurus RRID.')
    p = pathlib.Path(path); delim = spec.get('delimiter') or ('\t' if p.suffix.lower() in ('.tsv', '.txt') else ',')
    rows = []
    with open(p, newline='') as fh:
        for d in csv.DictReader(fh, delimiter=delim):
            raw = (d.get(spec['value_column']) or '').strip()
            try:
                v = float(raw) if raw else None
            except ValueError:
                raise ValueError(f"Non-numeric value '{raw}' in {spec['value_column']}.")
            rows.append((d.get(spec.get('gene_column', '')), d.get(spec.get('accession_column', '')), v,
                         {'replicate': d.get(spec['replicate_column'])} if spec.get('replicate_column') else {}))
    meta = {k: spec[k] for k in ('id', 'name', 'cellosaurus', 'method', 'unit', 'citation', 'licence')}
    meta.update(replicates='per row' if spec.get('replicate_column') else 'not stated', missing='empty cells stored as missing (None)',
                sha256=hashlib.sha256(p.read_bytes()).hexdigest(), source=str(p.name), imported=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    return _store(root, meta, rows, _resolver(root))


def available(root, cellosaurus=CONTEXT):
    db = _db(root)
    if db is None:
        return []
    try:
        return [json.loads(d) for (d,) in db.execute('SELECT data FROM datasets') if json.loads(d)['cellosaurus'] == cellosaurus]
    finally:
        db.close()


def protein(root, symbol, cellosaurus=CONTEXT):
    """Measured abundance of one protein in every dataset for this context, with its rank within the dataset."""
    db = _db(root)
    if db is None:
        return None
    try:
        out = []
        for meta in available(root, cellosaurus):
            rows = db.execute('SELECT value, uniprot, source_id, extra, mapping FROM abundance WHERE dataset=? AND symbol=? ORDER BY value DESC', (meta['id'], symbol)).fetchall()
            n = meta['counts']['resolved']
            if not rows:
                out.append({'dataset': meta['id'], 'name': meta['name'], 'method': meta['method'], 'unit': meta['unit'], 'reported': False, 'note': meta['missing']}); continue
            v = rows[0][0]; above = db.execute('SELECT COUNT(*) FROM abundance WHERE dataset=? AND symbol IS NOT NULL AND value > ?', (meta['id'], v)).fetchone()[0]
            out.append({'dataset': meta['id'], 'name': meta['name'], 'method': meta['method'], 'unit': meta['unit'], 'reported': True, 'value': v, 'rank': above + 1, 'of': n,
                        'percentile': 100 * (1 - above / max(n, 1)), 'uniprot': rows[0][1], 'sourceId': rows[0][2], 'extra': json.loads(rows[0][3]), 'mapping': rows[0][4],
                        'otherRows': len(rows) - 1, 'citation': meta['citation'], 'licence': meta['licence'], 'replicates': meta['replicates']})
        return out
    finally:
        db.close()


_VALUES = {}


def values(root, dataset):
    """symbol → highest reported value in one dataset (cached by index mtime)."""
    f = folder(root) / 'proteomics.sqlite'
    if not f.is_file():
        return {}
    key = (str(f), f.stat().st_mtime, dataset)
    if key not in _VALUES:
        db = _db(root); out = {}
        for s, v in db.execute('SELECT symbol, value FROM abundance WHERE dataset=? AND symbol IS NOT NULL AND value IS NOT NULL', (dataset,)):
            out[s] = max(v, out.get(s, v))
        db.close(); _VALUES.clear(); _VALUES[key] = out
    return _VALUES[key]


def rna_protein(root, dataset, rna):
    """Spearman correlation between measured protein abundance and an RNA measurement, over proteins with both.
    rna: {symbol: value} in one unit. Restricted to detected proteins, so it is not a proteome-wide estimate."""
    from scipy.stats import spearmanr
    db = _db(root)
    if db is None:
        return None
    try:
        prot = {}
        for s, v in db.execute('SELECT symbol, value FROM abundance WHERE dataset=? AND symbol IS NOT NULL AND value IS NOT NULL', (dataset,)):
            prot[s] = max(v, prot.get(s, v))
    finally:
        db.close()
    both = sorted(s for s in prot if s in rna and rna[s] is not None)
    if len(both) < 30:
        return {'n': len(both), 'note': 'Too few proteins with both measurements for a correlation.'}
    rho, p = spearmanr([prot[s] for s in both], [rna[s] for s in both])
    return {'n': len(both), 'spearman': float(rho), 'p': float(p), 'proteinsInDataset': len(prot), 'rnaGenes': len(rna),
            'points': [[rna[s], prot[s], s] for s in both],
            'note': 'Spearman rank correlation over proteins detected in this dataset (detection truncates low abundances). Different samples, labs and years: '
                    'agreement in rank only; RNA does not determine protein abundance (translation and turnover differ by protein).'}


if __name__ == '__main__':
    import sys
    build(sys.argv[1])
