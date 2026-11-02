"""Sanger Project Score (Behan FM et al., Nature 2019;568:511): an independent genome-wide CRISPR screen of 324 cancer cell lines,
used to ask whether a DepMap dependency replicates in another laboratory's screen, library and analysis.

    python sanger_score.py <library root>

Installed: CRISPRcleanR copy-number-corrected depletion log fold changes and BAGEL-derived binary dependency calls (17,995 genes),
with each cell line matched to its DepMap model by normalised name. Lines that do not match are counted and left out.
Licence: Wellcome Sanger Institute, Cell Model Passports terms (free for research use; cite Behan et al. 2019).
"""
import hashlib
import io
import json
import math
import pathlib
import re
import sys
import time
import urllib.request
import zipfile

import numpy as np

URL = 'https://cog.sanger.ac.uk/cmp/download/essentiality_matrices.zip'
EVIDENCE = 'Statistical association on an independent measured CRISPR screen (Sanger Project Score, CRISPRcleanR-corrected log fold change)'


def _dir(root):
    d = pathlib.Path(root) / 'oncology' / 'sanger'; d.mkdir(parents=True, exist_ok=True)
    return d


def _norm(n):
    return re.sub(r'[^A-Z0-9]', '', str(n).upper())


def install(root, log=print):
    import oncology_data as D
    import types
    d = _dir(root); z = d / 'essentiality_matrices.zip'
    if not z.is_file():
        log(f'downloading {URL} (≈ 240 MB)')
        tmp = d / 'download.part'; urllib.request.urlretrieve(URL, tmp); tmp.rename(z)
    sha = hashlib.sha256(z.read_bytes()).hexdigest()
    rel = D.Release(types.SimpleNamespace(root=root)); by_name = {}
    for mid, m in rel.models.items():
        for k in ('StrippedCellLineName', 'CellLineName'):
            if m.get(k):
                by_name.setdefault(_norm(m[k]), mid)
    with zipfile.ZipFile(z) as zf:
        for name, key in (('01_corrected_logFCs.tsv', 'lfc'), ('04_binaryDepScores.tsv', 'binary')):
            rows = io.TextIOWrapper(zf.open('EssentialityMatrices/' + name)).read().splitlines()
            head = rows[0].split('\t')[1:]; genes = [r.split('\t', 1)[0] for r in rows[1:]]
            M = np.array([[float(x) if x not in ('', 'NA') else np.nan for x in r.split('\t')[1:]] for r in rows[1:]], np.float32).T   # lines × genes
            np.save(d / f'{key}.npy', M)
            log(f'{name}: {M.shape[0]} lines × {M.shape[1]} genes')
    lines = head; models = [by_name.get(_norm(n)) for n in lines]
    (d / 'index.json').write_text(json.dumps({'lines': lines, 'models': models, 'genes': genes}))
    m = {'source': 'Sanger Project Score', 'citation': 'Behan FM et al. Prioritization of cancer therapeutic targets using CRISPR–Cas9 screens. Nature 2019;568:511–516.',
         'url': URL, 'sha256': sha, 'lines': len(lines), 'matchedToDepMap': sum(x is not None for x in models), 'depmapRelease': rel.release,
         'licence': 'Wellcome Sanger Institute Cell Model Passports terms; cite Behan et al. 2019', 'installed': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (d / 'manifest.json').write_text(json.dumps(m, indent=1)); log(f'ready: {m["matchedToDepMap"]} of {m["lines"]} lines matched to DepMap {rel.release}')
    return m


def installed(root):
    f = _dir(root) / 'manifest.json'
    return json.loads(f.read_text()) if f.is_file() else None


def replicate(root, rel, mut_gene, genes, kind='hotspot'):
    """For each gene: Δ corrected logFC (mutant − wild type) in Sanger lines, lineage fixed effects as in the DepMap scan, two-sided p.
    Mutation status and lineage come from DepMap for the matched model; sister lines are collapsed by PatientID."""
    from scipy.stats import t as T
    import oncology_stats as S
    d = _dir(root); idx = json.loads((d / 'index.json').read_text()); M = np.load(d / 'lfc.npy', mmap_mode='r'); gi = {g: i for i, g in enumerate(idx['genes'])}
    Mu, mm, mg, mgi, _ = rel.matrix('mut_' + kind); mrow = {m: i for i, m in enumerate(mm)}
    if mut_gene not in mgi:
        raise ValueError(f'{mut_gene} has no {kind} calls in DepMap.')
    rows, seen = [], set()
    for i, m in enumerate(idx['models']):
        pid = (rel.models.get(m) or {}).get('PatientID') or m
        if m and m in mrow and pid not in seen:
            seen.add(pid); rows.append((i, m))
    x = np.array([float(Mu[mrow[m], mgi[mut_gene]] > 0) for _, m in rows]); ids = [m for _, m in rows]
    out = {'lines': len(rows), 'mutant': int(x.sum()), 'genes': {}}
    if x.sum() < 3 or (1 - x).sum() < 3:
        out['note'] = f'Only {int(x.sum())} independent {mut_gene}-{kind} lines in Project Score; replication not testable.'; return out
    L, k = S._lineage_design(rel, ids); P = L @ np.linalg.pinv(L); rx = x - P @ x; sxx = rx @ rx; df = len(x) - k - 1
    for g in genes:
        if g not in gi or sxx < 1e-9 or df < 2:
            continue
        y = np.asarray(M[[i for i, _ in rows], gi[g]], float); ok = np.isfinite(y)
        if ok.sum() < len(y):
            y = np.where(ok, y, np.nanmean(y))
        ry = y - P @ y; b = (rx @ ry) / sxx; se = math.sqrt(((ry - rx * b) ** 2).sum() / df / sxx)
        out['genes'][g] = {'delta': float(b), 'p': float(2 * T.sf(abs(b / se), df)), 'replicates': bool(b < 0 and 2 * T.sf(abs(b / se), df) < 0.05)}
    return out


if __name__ == '__main__':
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    install(sys.argv[1])
