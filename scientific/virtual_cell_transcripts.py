"""Hep G2 transcript isoforms: ENCODE RSEM quantifications joined to GENCODE V29 transcript structure.

Inputs (<library>/virtualcell/data/encode_hepg2/original; ENCODE data are released without use restrictions; cite the
ENCODE Project Consortium and the producing lab):
  ENCFF416RHJ.tsv, ENCFF938LTW.tsv  RSEM transcript quantifications of ENCSR000CPE (HepG2 whole-cell polyA+ RNA-seq,
                                    Gingeras lab, CSHL), biological replicates 1 and 2, GRCh38, GENCODE V29, md5 checked
                                    against the ENCODE file record on install.
  gencode.v29.primary_assembly.annotation.gtf.gz   the annotation those quantifications were computed against
                                    (primary assembly incl. scaffolds; MD5 from GENCODE).
  uniprot_human_reviewed.tsv.gz     (annotations folder) ENST → UniProt isoform cross-references.

Values are kept per replicate exactly as RSEM reported them: maximum-likelihood TPM, IsoPct, expected count, effective
length, and the posterior-mean TPM (pme_TPM) with RSEM's 95 % credible interval. The interval belongs to pme_TPM, not to
the maximum-likelihood TPM, and is labelled that way (it need not contain TPM). The replicate mean and the gene total (sum of transcript TPM) are derived summaries and
are labelled as such. Non-GENCODE rows in the RSEM files (ENCODE spike-ins / tRNA, numeric identifiers) are excluded
and counted. Nothing here is a model estimate.
"""
import gzip, hashlib, json, pathlib, re, sqlite3, sys, time

DIR = ('virtualcell', 'data', 'encode_hepg2')
REPLICATES = {'ENCFF416RHJ': {'replicate': 1, 'technical': '1_1'}, 'ENCFF938LTW': {'replicate': 2, 'technical': '2_1'}}
EXPERIMENT = 'ENCSR000CPE'
GTF = 'gencode.v29.primary_assembly.annotation.gtf.gz'      # ENCODE quantifies against the primary assembly (incl. scaffolds)
GTF_MD5 = '1e3a8b97e363f2dac1b3dc656a723c04'
ATTR = re.compile(r'(\S+) "([^"]*)"')
RSEM = ('TPM', 'IsoPct', 'expected_count', 'effective_length', 'pme_TPM', 'TPM_ci_lower_bound', 'TPM_ci_upper_bound')


def folder(root):
    return pathlib.Path(root).joinpath(*DIR)


def _md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def build(root):
    org = folder(root) / 'original'
    files = {}
    for acc, rep in REPLICATES.items():
        meta = json.loads((org / f'{acc}.json').read_text())
        md5 = _md5(org / f'{acc}.tsv')
        if md5 != meta['md5sum'] or meta['assembly'] != 'GRCh38' or meta.get('genome_annotation') != 'V29' or meta['dataset'] != f'/experiments/{EXPERIMENT}/':
            raise ValueError(f'{acc} does not match its ENCODE record (md5, assembly, annotation or experiment).')
        files[acc] = {'md5': md5, 'status': meta['status'], 'assembly': meta['assembly'], 'annotation': meta['genome_annotation'], 'biologicalReplicate': rep['replicate'],
                      'technicalReplicate': rep['technical'], 'outputType': meta['output_type'], 'url': f'https://www.encodeproject.org/files/{acc}/'}
    if _md5(org / GTF) != GTF_MD5:
        raise ValueError(GTF + ' does not match the GENCODE MD5.')
    exp = json.loads((org / f'{EXPERIMENT}.json').read_text())
    tx = {}
    with gzip.open(org / GTF, 'rt') as f:
        for line in f:
            if line.startswith('#'):
                continue
            c = line.rstrip('\n').split('\t')
            if c[2] not in ('transcript', 'exon', 'CDS', 'UTR', 'start_codon', 'stop_codon'):
                continue
            a = dict(ATTR.findall(c[8])); tags = re.findall(r'tag "([^"]+)"', c[8]); tid = a['transcript_id']
            if c[2] == 'transcript':
                tx[tid] = {'gene_id': a['gene_id'], 'gene_name': a['gene_name'].upper(), 'transcript_name': a.get('transcript_name'), 'type': a.get('transcript_type'),
                           'chrom': c[0], 'strand': c[6], 'start': int(c[3]), 'end': int(c[4]), 'tags': tags, 'level': int(a.get('level', 0)),
                           'support': a.get('transcript_support_level'), 'exons': [], 'cds': [], 'protein_id': None}
            elif c[2] == 'exon':
                tx[tid]['exons'].append([int(c[3]), int(c[4])])
            elif c[2] == 'CDS':
                tx[tid]['cds'].append([int(c[3]), int(c[4])]); tx[tid]['protein_id'] = a.get('protein_id')
    uni = {}
    up = pathlib.Path(root) / 'virtualcell' / 'data' / 'annotations' / 'original' / 'uniprot_human_reviewed.tsv.gz'
    if up.is_file():
        with gzip.open(up, 'rt') as f:
            head = next(f).rstrip('\n').split('\t'); ei, ai = head.index('Ensembl'), head.index('Entry')
            for line in f:
                c = line.rstrip('\n').split('\t')
                for m in re.finditer(r'(ENST\d+)(?:\.\d+)?(?:\s*\[([A-Z0-9-]+)\])?', c[ei]):       # "ENST….v [P02768-1];"
                    uni.setdefault(m.group(1), m.group(2) or c[ai])
    vals, excluded = {}, {}
    for acc in REPLICATES:
        with open(org / f'{acc}.tsv') as f:
            head = next(f).rstrip('\n').split('\t'); col = {h: i for i, h in enumerate(head)}; n = 0
            for line in f:
                c = line.rstrip('\n').split('\t')
                if not c[0].startswith('ENST'):
                    n += 1; continue
                if c[0] not in tx:
                    raise ValueError(f'{acc}: {c[0]} is not in GENCODE V29.')
                vals.setdefault(c[0], {})[acc] = {k: float(c[col[k]]) for k in RSEM}
            excluded[acc] = n
    out = folder(root) / 'transcripts.sqlite'; tmp = out.with_suffix('.part')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.execute('CREATE TABLE tx(transcript_id TEXT PRIMARY KEY, gene_name TEXT, gene_id TEXT, data TEXT)')
    db.execute('CREATE INDEX gene ON tx(gene_name)'); db.execute('CREATE INDEX gid ON tx(gene_id)')
    db.executemany('INSERT INTO tx VALUES(?,?,?,?)', ((t, d['gene_name'], d['gene_id'].split('.')[0], json.dumps({**d, 'uniprot': uni.get(t.split('.')[0]), 'rsem': vals.get(t, {})}))
                                                      for t, d in tx.items()))
    manifest = {'built': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'experiment': EXPERIMENT, 'experimentUrl': f'https://www.encodeproject.org/experiments/{EXPERIMENT}/',
                'description': exp.get('description'), 'lab': (exp.get('lab') or {}).get('title') if isinstance(exp.get('lab'), dict) else exp.get('lab'),
                'biosample': exp.get('biosample_summary'), 'assay': exp.get('assay_title'), 'released': exp.get('date_released'),
                'audit': {k: len(v) for k, v in (exp.get('audit') or {}).items()}, 'files': files, 'gtf': {'name': GTF, 'md5': GTF_MD5, 'release': 'GENCODE 29 (Ensembl 94), GRCh38'},
                'counts': {'transcripts': len(tx), 'quantified': len(vals), 'excludedNonGencodeRows': excluded, 'withUniProt': sum(1 for t in tx if t.split('.')[0] in uni)},
                'units': {'TPM': 'transcripts per million (RSEM)', 'IsoPct': 'percent of the gene\'s abundance (RSEM)', 'pme_TPM': 'posterior mean TPM (RSEM)', 'TPM_ci': 'RSEM 95 % credible interval of pme_TPM (not of TPM)'},
                'licence': 'ENCODE data: no restrictions on use (ENCODE data release policy); cite the ENCODE Project Consortium'}
    db.execute('CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT)'); db.execute('INSERT INTO meta VALUES(?,?)', ('manifest', json.dumps(manifest)))
    db.commit(); db.close(); tmp.rename(out)
    (folder(root) / 'manifest.json').write_text(json.dumps(manifest, indent=1))
    print('built', manifest['counts'], flush=True)
    return manifest


def available(root):
    return (folder(root) / 'transcripts.sqlite').is_file()


def gene(root, symbol=None, ensembl=None):
    """All GENCODE V29 transcripts of one gene with per-replicate RSEM values, a labelled replicate mean, and structure."""
    f = folder(root) / 'transcripts.sqlite'
    if not f.is_file():
        return None
    db = sqlite3.connect(f'file:{f}?mode=ro', uri=True)
    try:
        rows = db.execute('SELECT data FROM tx WHERE gene_name=?', (str(symbol or '').upper(),)).fetchall() if symbol else []
        if not rows and ensembl:
            rows = db.execute('SELECT data FROM tx WHERE gene_id=?', (ensembl.split('.')[0],)).fetchall()
        manifest = json.loads(db.execute("SELECT v FROM meta WHERE k='manifest'").fetchone()[0])
    finally:
        db.close()
    if not rows:
        return {'gene': symbol, 'transcripts': [], 'manifest': manifest, 'note': 'No GENCODE V29 transcripts for this gene symbol (it may be named differently in V29).'}
    txs = []
    for (d,) in rows:
        t = json.loads(d); reps = t.pop('rsem')
        tpm = [reps[a]['TPM'] for a in REPLICATES if a in reps]
        t['replicates'] = [{'file': a, **REPLICATES[a], **reps[a]} for a in REPLICATES if a in reps]
        t['meanTPM'] = sum(tpm) / len(tpm) if tpm else None
        t['exons'].sort(); t['cds'].sort()
        txs.append(t)
    txs.sort(key=lambda t: -(t['meanTPM'] or 0))
    per_rep = {a: sum(r['TPM'] for t in txs for r in t['replicates'] if r['file'] == a) for a in REPLICATES}
    gid = txs[0]['gene_id']
    return {'gene': txs[0]['gene_name'], 'geneId': gid, 'chrom': txs[0]['chrom'], 'strand': txs[0]['strand'],
            'start': min(t['start'] for t in txs), 'end': max(t['end'] for t in txs), 'transcripts': txs,
            'geneTPM': {'perReplicate': per_rep, 'derivation': 'sum of the gene\'s transcript TPM in each replicate (derived summary)'},
            'meanDerivation': 'mean of the two biological replicates (derived summary; n = 2, no error model)', 'manifest': manifest}


if __name__ == '__main__':
    build(sys.argv[1])
