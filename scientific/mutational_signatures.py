"""Mutational signatures (single-base substitutions, SBS96) for a cBioPortal cohort, fitted to COSMIC v3.4.

Pipeline
  1. Genome-wide (exome) mutations from cBioPortal; SNVs only; GRCh37 calls only (others are counted and excluded).
  2. Trinucleotide context from Ensembl GRCh37 REST; the mutation's reference base must equal the genome's middle base
     (catches build or coordinate errors; mismatches are counted and excluded).
  3. SBS96 catalogue in pyrimidine-reference convention.
  4. Refitting to COSMIC v3.4 exome-normalised SBS (SigProfilerAssignment reference, BSD-2-Clause, git-hash verified):
     non-negative least squares, backward elimination while cosine similarity drops < 0.01, signatures flagged by COSMIC
     as possible sequencing artefacts excluded; 100 multinomial bootstraps per sample for exposure intervals.
Evidence: Statistical estimate (signature attribution). A weak fit does not identify a patient's mutational process.
"""
import concurrent.futures as cf
import hashlib
import json
import pathlib
import time
import urllib.request

import numpy as np

REF = {'name': 'COSMIC_v3.4_SBS_GRCh37_exome.txt', 'git': '2efb8ead7947dc9c137f5bd94624ea4f3be42d18',
       'url': 'https://raw.githubusercontent.com/SigProfilerSuite/SigProfilerAssignment/main/SigProfilerAssignment/data/Reference_Signatures/GRCh37/COSMIC_v3.4_SBS_GRCh37_exome.txt'}
# COSMIC v3.4 "possible sequencing artefact" SBS signatures (cancer.sanger.ac.uk/signatures/sbs).
ARTEFACTS = {'SBS27', 'SBS43', *(f'SBS{i}' for i in range(45, 61)), 'SBS95'}
AETIOLOGY = {'SBS1': 'clock-like (5-methylcytosine deamination)', 'SBS2': 'APOBEC', 'SBS13': 'APOBEC', 'SBS4': 'tobacco smoking', 'SBS5': 'clock-like', 'SBS6': 'defective mismatch repair',
             'SBS7a': 'UV light', 'SBS7b': 'UV light', 'SBS10a': 'POLE exonuclease', 'SBS15': 'defective mismatch repair', 'SBS18': 'reactive oxygen species', 'SBS40a': 'unknown',
             'SBS3': 'defective homologous recombination', 'SBS92': 'tobacco smoking (bladder)', 'SBS29': 'tobacco chewing', 'SBS24': 'aflatoxin', 'SBS22a': 'aristolochic acid'}
COMP = str.maketrans('ACGT', 'TGCA')
TYPES = [f'{l}[{r}>{a}]{rr}' for r, alts in (('C', 'AGT'), ('T', 'ACG')) for a in alts for l in 'ACGT' for rr in 'ACGT']
EVIDENCE = 'Statistical estimate (NNLS signature attribution to COSMIC v3.4); aetiologies are COSMIC annotations, not observations in this patient'


def _dir(s, *p):
    d = pathlib.Path(s.root) / 'oncology' / 'signatures' / pathlib.Path(*p)
    d.mkdir(parents=True, exist_ok=True)
    return d


def reference(s):
    f = _dir(s) / REF['name']
    if not f.is_file():
        raw = urllib.request.urlopen(REF['url'], timeout=60).read()
        if hashlib.sha1(b'blob %d\0' % len(raw) + raw).hexdigest() != REF['git']:
            raise ValueError('COSMIC reference failed its git-hash check; not used.')
        f.write_bytes(raw)
    lines = f.read_text().splitlines(); head = lines[0].split('\t')[1:]
    rows = {l.split('\t')[0]: [float(x) for x in l.split('\t')[1:]] for l in lines[1:]}
    M = np.array([rows[t] for t in TYPES])
    return head, M


def _contexts(keys, cache, log):
    todo = [k for k in keys if k not in cache]
    def batch(ks):
        body = json.dumps({'regions': [f'{c}:{p - 1}..{p + 1}:1' for c, p in ks]}).encode()
        for attempt in range(5):
            try:
                req = urllib.request.Request('https://grch37.rest.ensembl.org/sequence/region/human', data=body, headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
                out = json.loads(urllib.request.urlopen(req, timeout=60).read())
                return {k: o['seq'].upper() for k, o in zip(ks, out)}
            except Exception:
                time.sleep(2 * (attempt + 1))
        return {}
    chunks = [todo[i:i + 50] for i in range(0, len(todo), 50)]
    with cf.ThreadPoolExecutor(6) as ex:
        for n, res in enumerate(ex.map(batch, chunks)):
            cache.update(res)
            if n % 100 == 0:
                log(f'context {min((n + 1) * 50, len(todo)):,}/{len(todo):,}')
    return cache


def build(s, study, log=print):
    """Fetch cohort SNVs, annotate trinucleotide context, write the SBS96 catalogue (one row per sample)."""
    d = _dir(s, study); saved = d / 'mutations_all.json'
    if saved.is_file():
        raw = saved.read_bytes(); log('using the saved cBioPortal mutation download')   # same bytes; SHA-256 recorded below
    else:
        url = f'https://www.cbioportal.org/api/molecular-profiles/{study}_mutations/mutations/fetch?projection=SUMMARY'
        req = urllib.request.Request(url, data=json.dumps({'sampleListId': f'{study}_sequenced'}).encode(), headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
        raw = urllib.request.urlopen(req, timeout=600).read(); saved.write_bytes(raw)
    muts = json.loads(raw)
    log(f'{len(muts):,} mutations from cBioPortal')
    snv, skipped = [], {'not SNV': 0, 'not GRCh37': 0}
    for m in muts:
        r, a = (m.get('referenceAllele') or ''), (m.get('variantAllele') or '')
        if len(r) != 1 or len(a) != 1 or r not in 'ACGT' or a not in 'ACGT':
            skipped['not SNV'] += 1; continue
        if (m.get('ncbiBuild') or 'GRCh37') not in ('GRCh37', 'NA'):
            skipped['not GRCh37'] += 1; continue
        ch = {'23': 'X', '24': 'Y'}.get(str(m['chr']).replace('chr', ''), str(m['chr']).replace('chr', ''))   # cBioPortal numbers X/Y as 23/24
        snv.append((m['sampleId'], ch, int(m['startPosition']), r, a))
    cf_ = d / 'contexts.json'   # cached flanking bases, keyed by [chromosome, position]
    cache = {tuple(json.loads(k)): v for k, v in json.loads(cf_.read_text()).items()} if cf_.is_file() else {}
    keys = sorted({(c, p) for _, c, p, _, _ in snv})
    cache = _contexts(keys, cache, log)
    cf_.write_text(json.dumps({json.dumps(list(k)): v for k, v in cache.items()}))
    cat, mismatch, missing = {}, 0, 0
    for sm, c, p, r, a in snv:
        tri = cache.get((c, p))
        if not tri or len(tri) != 3:
            missing += 1; continue          # Ensembl did not answer (retried 5×); a rebuild retries only these
        if tri[1] != r:
            mismatch += 1; continue
        if r in 'AG':
            tri, a = tri.translate(COMP)[::-1], a.translate(COMP)
        t = f'{tri[0]}[{tri[1]}>{a}]{tri[2]}'
        cat.setdefault(sm, np.zeros(96, int))[TYPES.index(t)] += 1
    out = {'study': study, 'samples': {k: v.tolist() for k, v in cat.items()}, 'snvs': len(snv), 'used': int(sum(v.sum() for v in cat.values())), 'referenceMismatch': mismatch, 'contextUnavailable': missing,
           'skipped': skipped, 'genome': 'GRCh37 (Ensembl REST)', 'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'sha256': hashlib.sha256(raw).hexdigest()}
    (d / 'sbs96.json').write_text(json.dumps(out))
    log(f'SBS96 ready: {len(cat)} samples, {out["used"]:,} SNVs; reference-base mismatches {mismatch}; contexts unavailable {missing}')
    return out


def _cos(a, b):
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12))


def fit_one(x, sigs, names, boot=100, seed=0):
    from scipy.optimize import nnls
    keep = [i for i, n in enumerate(names) if n not in ARTEFACTS]
    w, _ = nnls(sigs[:, keep], x.astype(float)); active = [keep[i] for i in np.where(w > 0)[0]]
    def refit(cols, y):
        if not cols:
            return np.zeros(0), 0.0
        w, _ = nnls(sigs[:, cols], y.astype(float)); return w, _cos(sigs[:, cols] @ w, y)
    w, cos = refit(active, x)
    while len(active) > 1:                                    # backward elimination
        trial = [(refit([c for c in active if c != r], x)[1], r) for r in active]
        best_cos, worst = max(trial)
        if cos - best_cos < 0.01:
            active.remove(worst); w, cos = refit(active, x)
        else:
            break
    rng = np.random.default_rng(seed); n = int(x.sum()); B = np.zeros((boot, len(active)))
    for b in range(boot):
        y = rng.multinomial(n, x / n); B[b], _ = refit(active, y)
    frac = lambda v: v / max(v.sum(), 1e-12)
    F = np.array([frac(r) for r in B])
    return [{'signature': names[c], 'mutations': float(w[i]), 'fraction': float(frac(w)[i]), 'ci': [float(np.quantile(F[:, i], .025)), float(np.quantile(F[:, i], .975))],
             'aetiology': AETIOLOGY.get(names[c], 'see COSMIC')} for i, c in enumerate(active)], cos


def analyse(s, study, min_snv=50):
    d = _dir(s, study)
    if not (d / 'sbs96.json').is_file():
        raise ValueError('Build the SBS96 catalogue for this study first.')
    cat = json.loads((d / 'sbs96.json').read_text())
    cache = d / f'fit_{min_snv}.json'
    if cache.is_file():
        old = json.loads(cache.read_text())
        if old.get('catalogue', {}).get('created') == cat['created']:
            return old
    names, sigs = reference(s)
    per, low = {}, 0
    for sm, v in cat['samples'].items():
        x = np.array(v)
        if x.sum() < min_snv:
            low += 1; continue
        ex, cos = fit_one(x, sigs, names); per[sm] = {'snvs': int(x.sum()), 'cosine': cos, 'exposures': ex}
    cohort = np.sum([np.array(v) for v in cat['samples'].values()], 0)
    agg = {}
    for r in per.values():
        for e in r['exposures']:
            agg.setdefault(e['signature'], []).append(e['fraction'])
    present = sorted(({'signature': k, 'samples': len(v), 'medianFraction': float(np.median(v)), 'aetiology': AETIOLOGY.get(k, 'see COSMIC')} for k, v in agg.items()), key=lambda r: -r['samples'])
    out = {'study': study, 'catalogue': {k: cat.get(k) for k in ('snvs', 'used', 'referenceMismatch', 'contextUnavailable', 'skipped', 'genome', 'created')}, 'cohortSpectrum': cohort.tolist(), 'types': TYPES,
            'fitted': len(per), 'tooFew': low, 'minSnv': min_snv, 'signatures': present, 'samples': per, 'reference': REF['name'],
            'method': 'NNLS + backward elimination (Δcosine < 0.01), COSMIC artefact signatures excluded, 100 multinomial bootstraps', 'evidence': EVIDENCE,
            'caveat': f'Samples with fewer than {min_snv} SNVs are not fitted. Exome catalogues are small; exposures below ~10 % are uncertain (see intervals), and similar signatures can split (e.g. SBS4 tobacco smoking vs SBS29 tobacco chewing; SBS7a calls in lung are likely misattribution).'}
    cache.write_text(json.dumps(out))
    return out


def smoking_check(s, study, signature='SBS4'):
    """Reference check: tobacco signature exposure in never-smokers vs smokers (TCGA TOBACCO_SMOKING_HISTORY_INDICATOR)."""
    from scipy.stats import mannwhitneyu
    import cancer_genomics as G
    a = analyse(s, study); c = G.Cohort(s, study)
    hist = {p: v.get('TOBACCO_SMOKING_HISTORY_INDICATOR') for p, v in c.pclin.items() if v.get('TOBACCO_SMOKING_HISTORY_INDICATOR')}
    source = study
    if not hist:
        # PanCancer Atlas releases omit smoking history; the legacy TCGA study of the same patients records it (joined on TCGA patient ID).
        source = study.split('_')[0] + '_tcga'; f = _dir(s, study) / f'smoking_{source}.json'
        if not f.is_file():
            url = f'https://www.cbioportal.org/api/studies/{source}/clinical-data?clinicalDataType=PATIENT&attributeId=TOBACCO_SMOKING_HISTORY_INDICATOR&projection=SUMMARY'
            raw = urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json'}), timeout=120).read()
            f.write_text(json.dumps({'url': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'retrieved': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'rows': json.loads(raw)}))
        hist = {r['patientId']: r['value'] for r in json.loads(f.read_text())['rows']}
    never, smoker = [], []
    for sm, r in a['samples'].items():
        v = hist.get(c.sample_patient.get(sm, ''))
        f = next((e['fraction'] for e in r['exposures'] if e['signature'] == signature), 0.0)
        if v == '1':
            never.append(f)
        elif v in ('2', '3', '4', '5'):
            smoker.append(f)
    if len(never) < 5 or len(smoker) < 5:
        raise ValueError('Smoking history is not available for enough patients in this study.')
    p = mannwhitneyu(smoker, never, alternative='greater').pvalue
    return {'signature': signature, 'never': {'n': len(never), 'median': float(np.median(never)), 'fracWithSignature': float(np.mean(np.array(never) > 0))},
            'smokers': {'n': len(smoker), 'median': float(np.median(smoker)), 'fracWithSignature': float(np.mean(np.array(smoker) > 0))}, 'p': float(p),
            'passed': bool(p < 0.01 and np.median(smoker) > np.median(never)), 'method': 'one-sided Mann–Whitney U, smokers > lifelong never-smokers',
            'reference': 'Alexandrov LB et al., Science 2016;354:618 (tobacco smoking and SBS4)', 'smokingSource': f'cBioPortal {source} TOBACCO_SMOKING_HISTORY_INDICATOR (1 = lifelong non-smoker; 2–5 = current or reformed)'}


if __name__ == '__main__':
    import sys, types
    build(types.SimpleNamespace(root=sys.argv[1]), sys.argv[2])
