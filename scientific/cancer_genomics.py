"""Demo B · cancer genomics cohorts from cBioPortal (public TCGA PanCancer Atlas studies).

Stored in <library>/oncology/cbioportal/<studyId>/: every API response is saved as returned (raw/*.json) with its URL,
request body, retrieval time and SHA-256, so the cohort is reproducible offline. Sample and patient identifiers are kept
as published. Gene coverage: the cancer genes of DepMap's hotspot panel plus pathway genes (a defined list, recorded).

Evidence: mutations, copy number, expression and clinical fields are Experimental observations (as processed by TCGA /
cBioPortal); frequencies, co-occurrence tests and survival models are Statistical associations.
"""
import hashlib
import json
import math
import pathlib
import time
import urllib.request

import numpy as np

API = 'https://www.cbioportal.org/api'
EVIDENCE_OBS = 'Experimental observation (TCGA sequencing / GISTIC / RNA-seq via cBioPortal)'
EVIDENCE_STAT = 'Statistical association (cohort-level; not causal)'

# Core members of the 10 canonical oncogenic pathways (Sanchez-Vega F et al., Cell 2018;173:321–337). A subset of each curated
# pathway, recorded as such: frequencies are therefore lower bounds of the published pathway alteration rates.
PATHWAYS = {
    'RTK-RAS': ['EGFR', 'ERBB2', 'ERBB3', 'MET', 'ALK', 'ROS1', 'RET', 'KRAS', 'NRAS', 'HRAS', 'BRAF', 'RAF1', 'MAP2K1', 'NF1', 'PTPN11', 'SOS1', 'RIT1', 'CBL', 'FGFR1', 'FGFR2', 'FGFR3', 'PDGFRA', 'KIT'],
    'PI3K': ['PIK3CA', 'PIK3CB', 'PIK3R1', 'PTEN', 'AKT1', 'AKT2', 'AKT3', 'MTOR', 'TSC1', 'TSC2', 'RICTOR'],
    'TP53': ['TP53', 'MDM2', 'MDM4', 'ATM', 'CHEK2'],
    'Cell cycle': ['CDKN2A', 'CDKN2B', 'CDKN1A', 'CDKN1B', 'CDK4', 'CDK6', 'CCND1', 'CCNE1', 'RB1', 'E2F3'],
    'WNT': ['APC', 'CTNNB1', 'RNF43', 'ZNRF3', 'AXIN1', 'AXIN2', 'TCF7L2'],
    'NOTCH': ['NOTCH1', 'NOTCH2', 'NOTCH3', 'NOTCH4', 'FBXW7', 'SPEN'],
    'Hippo': ['NF2', 'LATS1', 'LATS2', 'SAV1', 'YAP1', 'TEAD1'],
    'MYC': ['MYC', 'MYCN', 'MYCL', 'MAX', 'MGA'],
    'NRF2': ['KEAP1', 'NFE2L2', 'CUL3'],
    'TGF-β': ['TGFBR1', 'TGFBR2', 'ACVR2A', 'ACVR1B', 'SMAD2', 'SMAD3', 'SMAD4'],
}
ONCOGENES = {'EGFR', 'ERBB2', 'ERBB3', 'MET', 'ALK', 'ROS1', 'RET', 'KRAS', 'NRAS', 'HRAS', 'BRAF', 'RAF1', 'MAP2K1', 'SOS1', 'RIT1', 'FGFR1', 'FGFR2', 'FGFR3', 'PDGFRA', 'KIT',
             'PIK3CA', 'PIK3CB', 'AKT1', 'AKT2', 'AKT3', 'MTOR', 'RICTOR', 'MDM2', 'MDM4', 'CDK4', 'CDK6', 'CCND1', 'CCNE1', 'E2F3', 'CTNNB1', 'TCF7L2', 'YAP1', 'TEAD1', 'MYC', 'MYCN', 'MYCL', 'NFE2L2'}
NON_SILENT = {'Missense_Mutation', 'Nonsense_Mutation', 'Frame_Shift_Del', 'Frame_Shift_Ins', 'Splice_Site', 'In_Frame_Del', 'In_Frame_Ins', 'Nonstop_Mutation', 'Translation_Start_Site', 'Splice_Region'}


def _dir(s, study=''):
    d = pathlib.Path(s.root) / 'oncology' / 'cbioportal' / study
    d.mkdir(parents=True, exist_ok=True)
    return d


def _call(path, body=None, save=None, log=print):
    url = API + path
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': 'FoldStudio/cancer-genomics'})
    with urllib.request.urlopen(req, timeout=300) as r:
        raw = r.read()
    if save:
        save.write_bytes(raw)
        log(f'{save.name}: {len(raw) / 1e6:.2f} MB')
    return json.loads(raw), {'url': url, 'body': body, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'retrieved': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}


def studies():
    data, _ = _call('/studies?keyword=pan_can_atlas&projection=SUMMARY')
    return sorted([{'id': d['studyId'], 'name': d['name'], 'samples': d.get('allSampleCount'), 'citation': d.get('citation')} for d in data], key=lambda d: d['name'])


def genes_for(s):
    """Cancer genes from DepMap's hotspot panel (if installed) plus pathway genes, resolved to Entrez IDs by cBioPortal."""
    names = {g for v in PATHWAYS.values() for g in v}
    try:
        import oncology_data as D
        names |= set(D.Release(s).matrix('mut_hotspot')[2])
    except Exception:
        pass
    data, _ = _call('/genes/fetch?geneIdType=HUGO_GENE_SYMBOL&projection=SUMMARY', sorted(names))
    return {g['hugoGeneSymbol']: g['entrezGeneId'] for g in data}


def install(s, study, log=print):
    d = _dir(s, study); raw = d / 'raw'; raw.mkdir(exist_ok=True)
    prov = {}
    meta, prov['study'] = _call(f'/studies/{study}', save=raw / 'study.json', log=log)
    genes = genes_for(s); (d / 'genes.json').write_text(json.dumps(genes))
    ids = sorted(genes.values())
    _, prov['patients'] = _call(f'/studies/{study}/clinical-data?clinicalDataType=PATIENT&projection=SUMMARY', save=raw / 'clinical_patient.json', log=log)
    _, prov['samples'] = _call(f'/studies/{study}/clinical-data?clinicalDataType=SAMPLE&projection=SUMMARY', save=raw / 'clinical_sample.json', log=log)
    lists, prov['sampleLists'] = _call(f'/studies/{study}/sample-lists?projection=DETAILED', save=raw / 'sample_lists.json', log=log)
    _, prov['mutations'] = _call(f'/molecular-profiles/{study}_mutations/mutations/fetch?projection=DETAILED', {'sampleListId': f'{study}_sequenced', 'entrezGeneIds': ids}, raw / 'mutations.json', log)
    _, prov['cna'] = _call(f'/molecular-profiles/{study}_gistic/discrete-copy-number/fetch?discreteCopyNumberEventType=ALL&projection=SUMMARY', {'sampleListId': f'{study}_cna', 'entrezGeneIds': ids}, raw / 'cna.json', log)
    try:
        _, prov['mrna'] = _call(f'/molecular-profiles/{study}_rna_seq_v2_mrna_median_all_sample_Zscores/molecular-data/fetch?projection=SUMMARY', {'sampleListId': f'{study}_rna_seq_v2_mrna', 'entrezGeneIds': ids}, raw / 'mrna.json', log)
    except Exception as e:
        log(f'mRNA z-scores unavailable: {e}')
    manifest = {'source': 'cBioPortal', 'study': study, 'name': meta['name'], 'citation': meta.get('citation'), 'pmid': meta.get('pmid'), 'importDate': meta.get('importDate'),
                'portal': _call('/info')[0].get('portalVersion'), 'genes': len(genes), 'geneSource': 'DepMap hotspot panel + Sanchez-Vega 2018 pathway core genes',
                'sampleLists': {l['sampleListId']: len(l.get('sampleIds') or []) for l in lists}, 'provenance': prov,
                'licence': 'TCGA open-access data; cBioPortal terms of use. Controlled-access TCGA data are not used.', 'installed': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (d / 'manifest.json').write_text(json.dumps(manifest, indent=1))
    log(f'{study} ready: {manifest["sampleLists"]}')
    return manifest


def installed(s):
    root = _dir(s)
    return [json.loads((p / 'manifest.json').read_text()) for p in sorted(root.iterdir()) if (p / 'manifest.json').is_file()]


_CACHE = {}


def Cohort(s, study):
    """Parsed cohorts are cached per process, keyed by the manifest's modification time."""
    m = _dir(s, study) / 'manifest.json'
    key = (str(m), m.stat().st_mtime if m.is_file() else 0)
    if key not in _CACHE:
        _CACHE.clear(); _CACHE[key] = _Cohort(s, study)
    return _CACHE[key]


class _Cohort:
    def __init__(self, s, study):
        d = _dir(s, study); r = d / 'raw'
        if not (d / 'manifest.json').is_file():
            raise ValueError('Install this study first.')
        self.manifest = json.loads((d / 'manifest.json').read_text())
        lists = {l['sampleListId']: set(l.get('sampleIds') or []) for l in json.loads((r / 'sample_lists.json').read_text())}
        self.seq, self.cnaset = lists.get(f'{study}_sequenced', set()), lists.get(f'{study}_cna', set())
        self.profiled = sorted(self.seq & self.cnaset)          # alteration frequencies use samples profiled for both
        self.sample_patient, self.sclin, self.pclin = {}, {}, {}
        for row in json.loads((r / 'clinical_sample.json').read_text()):
            self.sample_patient[row['sampleId']] = row['patientId']; self.sclin.setdefault(row['sampleId'], {})[row['clinicalAttributeId']] = row['value']
        for row in json.loads((r / 'clinical_patient.json').read_text()):
            self.pclin.setdefault(row['patientId'], {})[row['clinicalAttributeId']] = row['value']
        self.genes = json.loads((d / 'genes.json').read_text()); byid = {v: k for k, v in self.genes.items()}
        self.muts = [m for m in json.loads((r / 'mutations.json').read_text()) if m['entrezGeneId'] in byid]
        for m in self.muts:
            m['gene'] = byid[m['entrezGeneId']]
        self.builds = {}
        for m in self.muts:
            b = m.get('ncbiBuild') or 'not stated'; self.builds[b] = self.builds.get(b, 0) + 1
        self.cna = {}
        for c in json.loads((r / 'cna.json').read_text()):
            if c['entrezGeneId'] in byid:
                self.cna[(c['sampleId'], byid[c['entrezGeneId']])] = c['alteration']
        self.mrna = {}
        if (r / 'mrna.json').is_file():
            for x in json.loads((r / 'mrna.json').read_text()):
                if x['entrezGeneId'] in byid:
                    self.mrna[(x['sampleId'], byid[x['entrezGeneId']])] = x['value']
        # Recurrent positions within this cohort: a weak, cohort-internal driver proxy (not a curated oncogenicity call).
        pos = {}
        for m in self.muts:
            if m['mutationType'] in NON_SILENT and m.get('proteinPosStart'):
                pos.setdefault((m['gene'], m['proteinPosStart']), set()).add(m['sampleId'])
        self.recurrent = {k for k, v in pos.items() if len(v) >= 3}

        # Per-gene indexes: each query touches only that gene's records.
        self.P = set(self.profiled); self.mut_by, self.cna_by = {}, {}
        for m in self.muts:
            if m['sampleId'] in self.P and m['mutationType'] in NON_SILENT:
                self.mut_by.setdefault(m['gene'], []).append(m)
        for (sm, g), a in self.cna.items():
            if sm in self.P and a in (2, -2):
                self.cna_by.setdefault(g, []).append((sm, a))

    def altered(self, gene, mode='any'):
        """Set of profiled samples with the gene altered. Oncogenes count amplification (+2); tumour suppressors deep deletion (−2)."""
        out = {m['sampleId'] for m in self.mut_by.get(gene, []) if mode != 'recurrent' or (gene, m.get('proteinPosStart')) in self.recurrent}
        if mode == 'any':
            want = 2 if gene in ONCOGENES else -2
            out |= {sm for sm, a in self.cna_by.get(gene, []) if a == want}
        return out


def _bh(p):
    p = np.asarray(p, float); n = len(p); o = np.argsort(p); q = np.empty(n)
    q[o] = np.minimum.accumulate((p[o] * n / np.arange(1, n + 1))[::-1])[::-1].clip(max=1)
    return q


def summary(s, study, top=25, c=None):
    c = c or Cohort(s, study); P = c.profiled; n = len(P)
    rows = []
    for g in c.genes:
        a = c.altered(g)
        if not a:
            continue
        mut = c.altered(g, 'mutation')
        rec = c.altered(g, 'recurrent')
        rows.append({'gene': g, 'altered': len(a), 'freq': len(a) / n, 'mutated': len(mut), 'cna': len(a - mut), 'recurrent': len(rec), 'role': 'oncogene (amp counted)' if g in ONCOGENES else 'TSG/other (deep del counted)'})
    rows.sort(key=lambda r: -r['altered'])
    genes = [r['gene'] for r in rows[:top]]
    # Oncoprint: per sample and gene, the alteration classes present.
    kinds = {}
    for m in c.muts:
        if m['gene'] in genes and m['sampleId'] in set(P) and m['mutationType'] in NON_SILENT:
            kinds.setdefault((m['sampleId'], m['gene']), set()).add('trunc' if m['mutationType'] in ('Nonsense_Mutation', 'Frame_Shift_Del', 'Frame_Shift_Ins', 'Splice_Site', 'Nonstop_Mutation') else 'inframe' if 'In_Frame' in m['mutationType'] else 'missense')
    for (sm, g), a in c.cna.items():
        if g in genes and sm in set(P) and a in (2, -2):
            kinds.setdefault((sm, g), set()).add('amp' if a == 2 else 'del')
    order = sorted(P, key=lambda sm: [0 if (sm, g) in kinds else 1 for g in genes])
    grid = [[sorted(kinds.get((sm, g), [])) for sm in order] for g in genes]
    tmb = [float(c.sclin[sm]['TMB_NONSYNONYMOUS']) for sm in P if c.sclin.get(sm, {}).get('TMB_NONSYNONYMOUS') not in (None, 'NA')]
    pw = []
    for name, members in PATHWAYS.items():
        alt = set().union(*(c.altered(g) for g in members if g in c.genes)) if any(g in c.genes for g in members) else set()
        pw.append({'pathway': name, 'altered': len(alt), 'freq': len(alt) / n, 'genesCovered': sum(g in c.genes for g in members), 'genesListed': len(members)})
    builds = {'counts': c.builds, 'note': 'Mutations carry more than one reference build label. Analyses here are gene-level (no coordinates are compared across builds), so counts are unaffected; positional analyses must lift over first.' if len(c.builds) > 1 else 'Single reference build.'}
    return {'study': c.manifest, 'profiledSamples': n, 'patients': len({c.sample_patient.get(sm) for sm in P}), 'builds': builds, 'genes': rows, 'oncoprint': {'genes': genes, 'samples': len(order), 'grid': grid},
            'tmb': {'n': len(tmb), 'median': float(np.median(tmb)) if tmb else None, 'q1': float(np.quantile(tmb, .25)) if tmb else None, 'q3': float(np.quantile(tmb, .75)) if tmb else None, 'values': sorted(tmb)},
            'pathways': pw, 'definitions': {'altered': 'non-silent mutation, or GISTIC amplification (+2) for oncogenes / deep deletion (−2) for other genes, among samples profiled for both mutation and copy number',
                                            'recurrent': 'mutation at a protein position mutated in ≥ 3 samples of this cohort (weak driver proxy; not curated oncogenicity)',
                                            'pathways': 'core-gene subsets of Sanchez-Vega et al. 2018; frequencies are lower bounds',
                                            'passengers': 'Very long genes (e.g. TTN, MUC16, USH2A) accumulate passenger mutations in proportion to length and mutation burden (Lawrence MS et al., Nature 2013); high frequency alone is not driver evidence. Sort by recurrent positions for a driver-enriched view.'},
            'evidence': {'alterations': EVIDENCE_OBS, 'frequencies': EVIDENCE_STAT}}


def pairs(s, study, genes, c=None):
    """Co-occurrence / mutual exclusivity among genes: two-sided Fisher exact test, log2 odds ratio (Haldane +0.5), BH-FDR."""
    from scipy.stats import fisher_exact
    c = c or Cohort(s, study); P = set(c.profiled); n = len(P); sets = {g: c.altered(g) for g in genes}
    out = []
    for i, a in enumerate(genes):
        for b in genes[i + 1:]:
            A, B = sets[a], sets[b]
            t = [[len(A & B), len(A - B)], [len(B - A), n - len(A | B)]]
            p = fisher_exact(t)[1]
            lor = math.log2(((t[0][0] + .5) * (t[1][1] + .5)) / ((t[0][1] + .5) * (t[1][0] + .5)))
            out.append({'a': a, 'b': b, 'both': t[0][0], 'aOnly': t[0][1], 'bOnly': t[1][0], 'neither': t[1][1], 'log2OR': lor, 'p': p})
    q = _bh([r['p'] for r in out]) if out else []
    for r, v in zip(out, q):
        r['q'] = float(v); r['tendency'] = 'co-occurrence' if r['log2OR'] > 0 else 'mutual exclusivity'
    return {'pairs': sorted(out, key=lambda r: r['p']), 'n': n, 'method': 'two-sided Fisher exact per pair; BH-FDR over all pairs', 'evidence': EVIDENCE_STAT,
            'caveat': 'Exclusivity can reflect subtype structure or limited power, not only functional redundancy.'}


def expression_by_cna(s, study, gene, c=None):
    c = c or Cohort(s, study); groups = {}
    for sm in c.profiled:
        z = c.mrna.get((sm, gene)); a = c.cna.get((sm, gene), 0)
        if z is not None:
            groups.setdefault(int(a), []).append(float(z))
    from scipy.stats import spearmanr
    xs = [k for k, v in groups.items() for _ in v]; ys = [z for v in groups.values() for z in v]
    rho, p = spearmanr(xs, ys) if len(set(xs)) > 1 else (float('nan'), float('nan'))
    return {'gene': gene, 'groups': {str(k): {'n': len(v), 'median': float(np.median(v)), 'q1': float(np.quantile(v, .25)), 'q3': float(np.quantile(v, .75)), 'values': v} for k, v in sorted(groups.items())},
            'spearman': float(rho), 'p': float(p), 'units': 'mRNA z-score (RSEM, relative to all samples)', 'method': 'Spearman correlation between GISTIC level (−2…+2) and mRNA z-score', 'evidence': EVIDENCE_STAT}


def _km(t, e):
    order = np.argsort(t); t, e = t[order], e[order]; S, curve, at = 1.0, [[0.0, 1.0]], len(t)
    for u in np.unique(t):
        d = e[t == u].sum(); n_at = (t >= u).sum()
        if d:
            S *= 1 - d / n_at; curve.append([float(u), S])
    return curve


def _logrank(t, e, g):
    from scipy.stats import chi2
    O = E = V = 0.0
    for u in np.unique(t[e == 1]):
        at = t >= u; n = at.sum(); n1 = (at & g).sum(); d = ((t == u) & (e == 1)).sum(); d1 = ((t == u) & (e == 1) & g).sum()
        O += d1; E += d * n1 / n; V += d * (n1 / n) * (1 - n1 / n) * (n - d) / max(n - 1, 1)
    stat = (O - E) ** 2 / V if V > 0 else float('nan')
    return float(stat), float(chi2.sf(stat, 1)) if V > 0 else float('nan')


def _cox(t, e, X, iters=50):
    """Cox proportional hazards by Newton–Raphson on the Breslow partial likelihood; returns β and its standard errors."""
    n, k = X.shape; b = np.zeros(k); order = np.argsort(-t); t, e, X = t[order], e[order], X[order]
    for _ in range(iters):
        eta = X @ b; w = np.exp(eta - eta.max())
        cw = np.cumsum(w); cwx = np.cumsum(w[:, None] * X, 0); cwxx = np.cumsum(w[:, None, None] * X[:, :, None] * X[:, None, :], 0)
        # Ties: group by time (Breslow), using the risk set at the last index of each tied block.
        last = np.r_[np.where(np.diff(t) != 0)[0], n - 1]; idx = np.searchsorted(last, np.arange(n)); r = last[idx]
        mu = cwx[r] / cw[r][:, None]
        g = ((X - mu) * e[:, None]).sum(0)
        H = -(((cwxx[r] / cw[r][:, None, None]) - mu[:, :, None] * mu[:, None, :]) * e[:, None, None]).sum(0)
        step = np.linalg.solve(H, -g); b += step
        if np.abs(step).max() < 1e-9:
            break
    se = np.sqrt(np.diag(np.linalg.inv(-H)))
    return b, se


def survival(s, study, gene, endpoint='OS', c=None):
    """Kaplan–Meier by gene alteration (patient-level), log-rank test, and Cox HR adjusted for age at diagnosis."""
    from scipy.stats import norm
    c = c or Cohort(s, study); alt = c.altered(gene)
    pts = {}
    for sm in c.profiled:
        pid = c.sample_patient.get(sm)
        if pid:
            pts[pid] = pts.get(pid, False) or sm in alt            # patient altered if any profiled sample is
    rows = []
    for pid, a in pts.items():
        cl = c.pclin.get(pid, {}); m, st = cl.get(f'{endpoint}_MONTHS'), cl.get(f'{endpoint}_STATUS')
        if m in (None, 'NA', '') or not st:
            continue
        age = cl.get('AGE')
        rows.append((float(m), 1 if st.startswith('1') else 0, a, float(age) if age not in (None, 'NA', '') else float('nan')))
    if len(rows) < 30:
        raise ValueError(f'Only {len(rows)} patients have {endpoint} data.')
    t = np.array([r[0] for r in rows]); e = np.array([r[1] for r in rows]); g = np.array([r[2] for r in rows]); age = np.array([r[3] for r in rows])
    if g.sum() < 5 or (~g).sum() < 5:
        raise ValueError(f'{gene}: too few patients in one group ({int(g.sum())} altered).')
    chi, p = _logrank(t, e, g)
    ok = np.isfinite(age)
    b, se = _cox(t[ok], e[ok], np.c_[g[ok].astype(float), (age[ok] - age[ok].mean()) / 10])
    z = b / se
    cox = [{'term': f'{gene} altered', 'hr': float(math.exp(b[0])), 'ci': [float(math.exp(b[0] - 1.96 * se[0])), float(math.exp(b[0] + 1.96 * se[0]))], 'p': float(2 * norm.sf(abs(z[0])))},
           {'term': 'age (per 10 years)', 'hr': float(math.exp(b[1])), 'ci': [float(math.exp(b[1] - 1.96 * se[1])), float(math.exp(b[1] + 1.96 * se[1]))], 'p': float(2 * norm.sf(abs(z[1])))}]
    return {'gene': gene, 'endpoint': endpoint, 'patients': len(rows), 'events': int(e.sum()), 'altered': int(g.sum()), 'coxPatients': int(ok.sum()),
            'km': {'altered': _km(t[g], e[g]), 'unaltered': _km(t[~g], e[~g])}, 'logrank': {'chi2': chi, 'p': p}, 'cox': cox,
            'method': 'Kaplan–Meier; log-rank test; Cox proportional hazards (Breslow ties) with alteration status and age',
            'evidence': EVIDENCE_STAT, 'caveat': 'Retrospective association in one cohort, unadjusted for stage and treatment; not causal and not individual prognosis. TCGA clinical follow-up is heterogeneous (Liu J et al., Cell 2018 recommends PFI for several cancer types).'}


if __name__ == '__main__':
    import sys, types
    install(types.SimpleNamespace(root=sys.argv[1]), sys.argv[2])
