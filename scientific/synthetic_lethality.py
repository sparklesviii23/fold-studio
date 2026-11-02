"""Synthetic-lethality research on measured CRISPR screens, with four labels that are never merged:

  Statistical co-dependency       two genes' knockout effects correlate across cell lines (lineage removed)      Statistical association
  Context-specific dependency     gene B is more essential where gene A is damaged (lineage-adjusted)          Statistical association
  Experimentally demonstrated SL  published pair, shown by a direct genetic or pharmacological experiment      Curated evidence (reference set below)
  Predicted synthetic lethality   a context-specific dependency that is also replicated or paralog-explained   Hypothesis
No double-perturbation (combinatorial knockout) dataset is installed, so genetic interaction scores are not computed here.
"""
import json
import math
import pathlib
import urllib.request

import numpy as np

# A small reference set of experimentally demonstrated synthetic-lethal relationships (loss of A → dependency on B), each from a
# direct experiment in human cancer cells; used to label results and as positive controls for the statistical scan.
REFERENCE = [
    ('SMARCA4', 'SMARCA2', 'paralog redundancy (SWI/SNF ATPase)', 'Hoffman GR et al. PNAS 2014;111:3128; Oike T et al. Cancer Res 2013;73:5508'),
    ('ARID1A', 'ARID1B', 'paralog redundancy (SWI/SNF)', 'Helming KC et al. Nat Med 2014;20:251'),
    ('VPS4B', 'VPS4A', 'paralog redundancy (ESCRT)', 'Neggers JE et al. Cancer Cell 2020;37:648'),
    ('ENO1', 'ENO2', 'paralog redundancy (glycolysis)', 'Muller FL et al. Nature 2012;488:337'),
    ('MTAP', 'PRMT5', 'metabolite (MTA) accumulation inhibits PRMT5', 'Kryukov GV et al. Science 2016;351:1214; Mavrakis KJ et al. Science 2016;351:1208'),
    ('BRCA1', 'PARP1', 'homologous-recombination deficiency (shown with PARP inhibitors; their lethality depends partly on trapping PARP1 on DNA, which a PARP1 knockout does not reproduce)', 'Farmer H et al. Nature 2005;434:917; Bryant HE et al. Nature 2005;434:913; Murai J et al. Cancer Res 2012;72:5588'),
    ('BRCA2', 'PARP1', 'homologous-recombination deficiency (shown with PARP inhibitors; see BRCA1)', 'Farmer H et al. Nature 2005;434:917; Bryant HE et al. Nature 2005;434:913'),
]
EVIDENCE = 'Statistical association (DepMap CRISPR gene effect; lineage fixed effects; BH-FDR)'


def _cache(root):
    d = pathlib.Path(root) / 'oncology' / 'synthetic_lethality'; d.mkdir(parents=True, exist_ok=True)
    return d


def paralogs(root, gene):
    """Ensembl Compara paralogues: symbol → 'within_species_paralog' (recent duplication) or older classes. Cached per gene."""
    f = _cache(root) / f'paralogs_{gene}.json'
    if f.is_file():
        return json.loads(f.read_text())
    get = lambda url, body=None: json.loads(urllib.request.urlopen(urllib.request.Request(url, data=None if body is None else json.dumps(body).encode(),
                                                                                       headers={'Content-Type': 'application/json', 'Accept': 'application/json'}), timeout=60).read())
    h = get(f'https://rest.ensembl.org/homology/symbol/human/{gene}?type=paralogues&format=condensed')
    hom = [x for d in h.get('data', []) for x in d.get('homologies', []) if x.get('species') == 'homo_sapiens']
    ids = [x['id'] for x in hom][:900]
    names = get('https://rest.ensembl.org/lookup/id', {'ids': ids}) if ids else {}
    out = {(names.get(x['id']) or {}).get('display_name'): x['type'] for x in hom if (names.get(x['id']) or {}).get('display_name')}
    f.write_text(json.dumps(out)); return out


def co_dependency(rel, gene, top=25):
    """Pearson correlation of gene effects across independent models after removing lineage means (FWL); BH over genes."""
    import oncology_stats as S
    from scipy.stats import t as T
    M, models, genes, gi, keep, dropped = S._rows(rel, 'gene_effect')
    if gene not in gi:
        raise ValueError(f'{gene} is not in the DepMap screen.')
    X = np.asarray(M[keep], float); X = np.where(np.isfinite(X), X, np.nanmean(X, 0))
    L, k = S._lineage_design(rel, [models[i] for i in keep]); X = X - L @ (np.linalg.pinv(L) @ X)
    Z = (X - X.mean(0)) / (X.std(0) + 1e-12); r = Z.T @ Z[:, gi[gene]] / len(Z); n = len(Z) - k
    tt = r * np.sqrt((n - 2) / np.clip(1 - r ** 2, 1e-12, None)); p = 2 * T.sf(np.abs(tt), n - 2); q = S._bh(p)
    order = [j for j in np.argsort(-r) if genes[j] != gene][:top]
    return {'gene': gene, 'models': len(keep), 'lineages': k, 'hits': [{'gene': genes[j], 'r': float(r[j]), 'q': float(q[j])} for j in order],
            'method': 'Pearson r of lineage-residualised gene effects across one model per patient; BH over all genes', 'label': 'Statistical co-dependency', 'evidence': EVIDENCE}


def expression_loss_scan(rel, gene, top=25, cutoff=1.0, min_lost=5):
    """Dependencies stronger where `gene` is not expressed (log2(TPM+1) < cutoff): lineage fixed effects, BH; same layout as mutation_scan.
    Catches loss by deletion or silencing, which mutation calls miss."""
    import oncology_stats as S
    from scipy.stats import t as T
    E, em, genes, gi, keep, dropped = S._rows(rel, 'gene_effect')
    X, xm, xg, xgi, _ = rel.matrix('expression')
    if gene not in xgi:
        raise ValueError(f'{gene} has no expression values in DepMap.')
    xr = {m: i for i, m in enumerate(xm)}; rows = [i for i in keep if em[i] in xr]; ids = [em[i] for i in rows]
    x = np.array([float(X[xr[m], xgi[gene]] < cutoff) for m in ids])
    if x.sum() < min_lost:
        raise ValueError(f'Only {int(x.sum())} independent models do not express {gene} (need ≥ {min_lost}).')
    Y = np.asarray(E[rows], float); Y = np.where(np.isfinite(Y), Y, np.nanmean(Y, 0))
    L, k = S._lineage_design(rel, ids); P = L @ np.linalg.pinv(L); rx = x - P @ x; ry = Y - P @ Y; sxx = rx @ rx
    beta = rx @ ry / sxx; df = len(x) - k - 1; se = np.sqrt(((ry - np.outer(rx, beta)) ** 2).sum(0) / df / sxx); p = 2 * T.sf(np.abs(beta / se), df); q = S._bh(p)
    h = T.ppf(0.975, df) * se; order = np.argsort(np.where(np.isfinite(beta / se), beta / se, np.inf))[:top]
    return {'mutant': int(x.sum()), 'n': len(x), 'lineages': k, 'hits': [{'gene': genes[j], 'beta': float(beta[j]), 'ci': [float(beta[j] - h[j]), float(beta[j] + h[j])], 'p': float(p[j]), 'q': float(q[j])} for j in order],
            'method': f'gene effect ~ {gene} not expressed (log2(TPM+1) < {cutoff}) + lineage fixed effects (OLS); BH over genes'}


def loss_context(root, rel, gene, kind='damaging', top=25):
    """Dependencies stronger where `gene` is lost — damaging mutation, or not expressed (kind='expression'); each hit labelled with
    paralogy, replication (mutation contexts only) and the reference set."""
    import oncology_stats as S
    import sanger_score as SS
    ms = expression_loss_scan(rel, gene, top) if kind == 'expression' else S.mutation_scan(rel, gene, kind, top=top)
    hits = [h for h in ms['hits'] if h['q'] < 0.05 and h['beta'] < 0]
    try:
        para = paralogs(root, gene)
    except Exception:
        para = None
    rep = SS.replicate(root, rel, gene, [h['gene'] for h in hits], kind) if SS.installed(root) and hits and kind != 'expression' else None
    ref = {(a, b): (why, cite) for a, b, why, cite in REFERENCE}
    rows = []
    for h in hits:
        r = (rep or {}).get('genes', {}).get(h['gene'])
        known = ref.get((gene, h['gene']))
        para_t = (para or {}).get(h['gene'])
        label = 'Experimentally demonstrated synthetic lethality (reference set)' if known else \
                'Predicted synthetic lethality (replicated' + (' and paralog' if para_t else '') + ')' if r and r['replicates'] else \
                'Context-specific dependency (not replicated)' if r else 'Context-specific dependency'
        rows.append({**h, 'paralog': para_t, 'replication': r, 'label': label, 'reference': known})
    return {'gene': gene, 'kind': kind, 'mutant': ms['mutant'], 'n': ms['n'], 'lineages': ms['lineages'], 'hits': rows, 'paralogsKnown': para is not None,
            'replication': None if rep is None else {k: rep[k] for k in ('lines', 'mutant') if k in rep} | ({'note': rep['note']} if rep.get('note') else {}),
            'method': ms['method'], 'evidence': EVIDENCE}


def benchmark(root, rel):
    """Positive controls: does the statistical scan recover each experimentally demonstrated pair from the reference set?"""
    import oncology_stats as S
    out = []
    for a, b, why, cite in REFERENCE:
        row = {'lost': a, 'dependency': b, 'mechanism': why, 'citation': cite}
        for kind in ('damaging', 'expression'):
            try:
                ms = S.mutation_scan(rel, a, kind, top=20000) if kind == 'damaging' else expression_loss_scan(rel, a, top=20000)
                h = next((x for x in ms['hits'] if x['gene'] == b), None)
                rank = 1 + sorted([x['beta'] for x in ms['hits']]).index(h['beta']) if h else None
                row[kind] = {'lost': ms['mutant'], 'beta': h['beta'] if h else None, 'q': h['q'] if h else None, 'rank': rank, 'tested': ms['n'], 'recovered': bool(h and h['q'] < 0.05 and h['beta'] < 0)}
            except ValueError as e:
                row[kind] = {'recovered': None, 'note': str(e)}
        out.append(row)
    count = lambda k: (sum(bool(r[k]['recovered']) for r in out), sum(r[k]['recovered'] is not None for r in out))
    return {'pairs': out, 'damaging': dict(zip(('recovered', 'testable'), count('damaging'))), 'expression': dict(zip(('recovered', 'testable'), count('expression'))),
            'note': 'Two definitions of loss: a damaging mutation (DepMap calls), or no expression (log2(TPM+1) < 1), which also catches deletion and silencing. PARP1 knockout is not PARP inhibition (trapping), so the BRCA pairs are not expected to appear as CRISPR dependencies.'}
