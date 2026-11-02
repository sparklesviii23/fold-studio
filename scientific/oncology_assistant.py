"""Oncology research assistant that answers only from computations on the app's data and named public databases.

Every answer is assembled from tool outputs; each claim carries its evidence class and source. Free-text questions are routed by
keywords to one of the supported questions, and the interpretation is shown so the user can correct it. No language model writes
numbers: none is required, and none is called by this module.
"""
import json
import re
import urllib.parse
import urllib.request

import numpy as np

QUESTIONS = {
    'support': ('Which datasets support this dependency?', ['gene', 'lineage']),
    'reproduce': ('Does this result reproduce in another cancer model?', ['gene', 'mutation']),
    'lineage': ('How does the result change after controlling for cell lineage?', ['gene', 'mutation']),
    'normal': ('What normal-tissue evidence is missing?', ['gene']),
    'origin': ('Is this interaction experimental or predicted?', ['gene', 'partner']),
    'first': ('Which paper first reported this relationship?', ['gene', 'partner']),
    'equation': ('What model equation explains this simulated behaviour?', ['gene']),
    'generalize': ('How well does this model generalize to independent cohorts?', ['drug', 'lineage']),
}
ROUTES = [('first', r'\b(first|earliest|paper|reported|publication)\b'), ('origin', r'\b(experimental|predicted|interaction)\b'), ('reproduce', r'\b(reproduc|replicat|another)\b'),
          ('lineage', r'\blineage\b|\bcontroll?ing\b|\bconfound'), ('normal', r'\bnormal\b|\btissue\b|\btoxic'), ('equation', r'\bequation|\bgradient|\bsimulat|\bmodel explain'),
          ('generalize', r'\bgenerali[sz]e|\bindependent cohort|\btransfer'), ('support', r'\bsupport|\bdatasets?\b|\bevidence for\b')]


def claim(text, evidence, source):
    return {'text': text, 'evidence': evidence, 'source': source}


def _get(url, timeout=40):
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={'Accept': 'application/json'}), timeout=timeout).read())


def route(text, rel, drugs, lineages):
    """Keyword routing: question id plus arguments found in the text (gene symbols known to DepMap, GDSC compounds, lineages)."""
    q = next((k for k, pat in ROUTES if re.search(pat, text, re.I)), 'support')
    genes_known = set(rel.matrix('gene_effect')[2]) if rel else set()
    tokens = [t for t in re.findall(r'\b[A-Z][A-Z0-9-]{1,9}\b', text) if t in genes_known]
    drug = next((d['key'] for d in drugs if re.search(r'\b' + re.escape(d['name']) + r'\b', text, re.I)), None)
    lineage = next((l for l in lineages if re.search(r'\b' + re.escape(l) + r'\b', text, re.I)), None)
    args = {'gene': tokens[0] if tokens else None, 'partner': tokens[1] if len(tokens) > 1 else None, 'mutation': tokens[1] if len(tokens) > 1 else None, 'drug': drug, 'lineage': lineage}
    return q, {k: v for k, v in args.items() if k in QUESTIONS[q][1]}


def answer(s, rel, q, args):
    if q not in QUESTIONS:
        raise ValueError('Unsupported question.')
    need = [k for k in QUESTIONS[q][1] if k in ('gene', 'drug') and not args.get(k)]
    if need:
        raise ValueError(f'Name the {" and ".join(need)} (for example BRAF, or a GDSC compound).')
    out = globals()['_' + q](s, rel, args)
    return {'question': QUESTIONS[q][0], 'id': q, 'arguments': args, **out}


def _support(s, rel, a):
    import oncology_stats as S
    import sanger_score as SS
    g, lin = a['gene'], a.get('lineage'); C, gaps = [], []
    p = S.gene_profile(rel, g); row = next((l for l in p['lineages'] if l['lineage'] == lin), None) if lin else None
    C.append(claim(f'DepMap {rel.release}: median gene effect {np.median([x["effect"] for x in p["points"]]):.2f} across {p["n"]} models; {p["fracDependent"]:.0%} below −0.5.', 'Experimental observation (CRISPR screen, Chronos-corrected)', f'DepMap {rel.release}'))
    if row:
        C.append(claim(f'In {lin}: median {row["median"]:.2f}, {row["fracDependent"]:.0%} of {row["n"]} models dependent.', 'Experimental observation', f'DepMap {rel.release}'))
    if SS.installed(s.root):
        import model_comparison as MC
        d = MC.dependency(s.root, rel, g).get('gene')
        if d and d['spearman'] is not None:
            C.append(claim(f'Sanger Project Score agrees across {len(d["points"])} shared lines: Spearman ρ {d["spearman"]:.2f}.', 'Statistical association between two independent screens', 'Sanger Project Score (Behan 2019)'))
    else:
        gaps.append('Sanger Project Score is not installed (Data tab), so independent replication was not checked.')
    try:
        import drug_response as R
        dr = [d for d in R.drugs(s) if g in [x.strip().upper() for x in (d.get('target') or '').split(',')]]
        if dr:
            C.append(claim(f'{len(dr)} GDSC compound screen(s) annotate {g} as a target: {", ".join(sorted({d["name"] for d in dr})[:6])}.', 'Curated annotation of measured screens', 'GDSC 8.5'))
        else:
            gaps.append(f'No GDSC compound is annotated with {g} as its target.')
    except ValueError:
        gaps.append('GDSC is not installed.')
    return {'answer': ' '.join(c['text'] for c in C), 'claims': C, 'gaps': gaps}


def _reproduce(s, rel, a):
    import sanger_score as SS
    g, m = a['gene'], a.get('mutation')
    if not SS.installed(s.root):
        return {'answer': 'Not checkable: Sanger Project Score is not installed (Data tab).', 'claims': [], 'gaps': ['Install Sanger Project Score.']}
    if m:
        r = SS.replicate(s.root, rel, m, [g], 'hotspot' if m in __import__('cancer_genomics').ONCOGENES else 'damaging')
        x = r['genes'].get(g)
        if not x:
            return {'answer': r.get('note') or f'{g} was not screened in Project Score.', 'claims': [], 'gaps': []}
        c = claim(f'In Sanger Project Score ({r["mutant"]} {m}-mutant of {r["lines"]} independent lines), {g} Δ log fold change {x["delta"]:.2f}, p {x["p"]:.1e}: {"replicates" if x["replicates"] else "does not replicate"}.',
                  'Statistical association on an independent CRISPR screen', 'Sanger Project Score (Behan 2019); lineage fixed effects')
        return {'answer': c['text'], 'claims': [c], 'gaps': []}
    import model_comparison as MC
    d = MC.dependency(s.root, rel, g).get('gene')
    c = claim(f'{g} gene effects correlate between DepMap and Sanger at Spearman ρ {d["spearman"]:.2f} over {len(d["points"])} shared lines.', 'Statistical association between two independent screens', 'DepMap; Sanger Project Score')
    return {'answer': c['text'] + ' Name a mutation (e.g. "KRAS in BRAF") to test a context-specific dependency.', 'claims': [c], 'gaps': []}


def _lineage(s, rel, a):
    import oncology_stats as S
    g, m = a['gene'], a.get('mutation')
    if not m:
        raise ValueError('Name the mutation that defines the comparison, e.g. "MAP2K1 in BRAF-mutant lines".')
    kind = 'hotspot' if m in __import__('cancer_genomics').ONCOGENES else 'damaging'
    ms = S.mutation_scan(rel, m, kind, top=20000); h = next((x for x in ms['hits'] if x['gene'] == g), None)
    E, em, genes, gi, keep, _ = S._rows(rel, 'gene_effect'); Mu, mm, mg, mgi, _ = rel.matrix('mut_' + kind); mrow = {x: i for i, x in enumerate(mm)}
    rows = [i for i in keep if em[i] in mrow]; x = np.array([float(Mu[mrow[em[i]], mgi[m]] > 0) for i in rows]); y = np.asarray(E[rows, gi[g]], float)
    naive = float(np.nanmean(y[x > 0]) - np.nanmean(y[x == 0]))
    c = claim(f'{g} in {m}-{kind} vs other lines: Δ {naive:.2f} without adjustment, {h["beta"]:.2f} (95 % CI {h["ci"][0]:.2f} to {h["ci"][1]:.2f}, q {h["q"]:.1e}) with {ms["lineages"]} lineage fixed effects.',
              'Statistical association', f'DepMap {rel.release}; OLS with lineage fixed effects')
    return {'answer': c['text'] + (' Lineage accounts for a large part of the unadjusted difference.' if abs(naive) > 1.5 * abs(h['beta']) else ' Adjusting for lineage changes the estimate little.'), 'claims': [c], 'gaps': []}


def _normal(s, rel, a):
    import oncology_stats as S
    g = a['gene']; C, gaps = [], []
    p = S.gene_profile(rel, g)
    C.append(claim(f'{p["fracDependent"]:.0%} of {p["n"]} cancer models depend on {g} (effect < −0.5); pan-essential genes suggest a narrow therapeutic window.', 'Experimental observation (cancer cell lines only)', f'DepMap {rel.release}'))
    try:
        ref = _get(f'https://gtexportal.org/api/v2/reference/gene?geneId={urllib.parse.quote(g)}&gencodeVersion=v26&genomeBuild=GRCh38%2Fhg38')['data'][0]['gencodeId']
        ex = [x for x in _get(f'https://gtexportal.org/api/v2/expression/medianGeneExpression?gencodeId={ref}&datasetId=gtex_v8')['data'] if not x['tissueSiteDetailId'].startswith('Cells_')]   # cultured cells are not tissues
        top = sorted(ex, key=lambda x: -x['median'])[:5]
        C.append(claim(f'GTEx v8 normal tissues: highest median expression in {", ".join(f"{x["tissueSiteDetailId"].replace("_", " ")} ({x["median"]:.1f} TPM)" for x in top)}; expressed above 1 TPM in {sum(x["median"] > 1 for x in ex)} of {len(ex)} tissues.',
                       'Experimental observation (normal-tissue RNA-seq)', 'GTEx v8 (gtexportal.org API)'))
    except Exception as e:
        gaps.append(f'GTEx not reachable ({type(e).__name__}).')
    gaps += ['No CRISPR screen of normal cells is installed, so normal-cell dependency is unmeasured here.', 'Expression in a normal tissue does not show that inhibiting the gene harms it.',
             'No in vivo toxicology or human safety data are connected.']
    return {'answer': ' '.join(c['text'] for c in C), 'claims': C, 'gaps': gaps}


def _origin(s, rel, a):
    import pathlib
    g, b = a['gene'], a.get('partner')
    if not b:
        raise ValueError('Name both genes, e.g. "Is the KRAS–RAF1 interaction experimental or predicted?"')
    f = pathlib.Path(s.root) / 'oncology' / 'evidence' / g / 'graph.json'; C = []
    if f.is_file():
        for e in json.loads(f.read_text())['edges']:
            if {e['source'].split(':', 1)[1], e['target'].split(':', 1)[1]} == {g, b}:
                C.append(claim(f'{e["relation"]}: {e["origin"]} ({e["database"]}{", strength " + str(e["strength"]) if e.get("strength") is not None else ""}).', f'Origin label: {e["origin"]}', e['database']))
    if not C:
        st = _get(f'https://string-db.org/api/json/network?identifiers={g}%0d{b}&species=9606&caller_identity=foldstudio')
        for i in st:
            if {i['preferredName_A'], i['preferredName_B']} == {g, b}:
                C.append(claim(f'STRING combined score {i["score"]:.2f}; experimental channel {i["escore"]:.2f}, curated databases {i["dscore"]:.2f}, text mining {i["tscore"]:.2f}, co-expression {i["ascore"]:.2f}.',
                               'experimental' if i['escore'] >= 0.4 else 'curated' if i['dscore'] >= 0.4 else 'text-mined' if i['tscore'] >= 0.4 else 'predicted', 'STRING (live)'))
    return {'answer': ' '.join(c['text'] for c in C) or f'No recorded interaction between {g} and {b} in the evidence graph or STRING.', 'claims': C,
            'gaps': ['STRING channels summarise evidence types; an experimental score is not proof of a direct, functional interaction in cancer cells.']}


def _first(s, rel, a):
    g, b = a['gene'], a.get('partner')
    q = f'"{g}" AND "{b}"' if b else f'"{g}" AND cancer'
    d = _get('https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urllib.parse.urlencode({'query': q, 'format': 'json', 'pageSize': 3, 'sort': 'FIRST_PDATE_D asc', 'resultType': 'lite'}))
    rs = d['resultList']['result']
    C = [claim(f'{r.get("firstPublicationDate", r.get("pubYear"))}: {r.get("title")} ({r.get("journalTitle", r.get("source"))}{", PMID " + r["pmid"] if r.get("pmid") else ""}).', 'Literature record', 'Europe PMC, earliest by first publication date') for r in rs]
    return {'answer': f'{d["hitCount"]} Europe PMC records match {q}; the earliest indexed is listed first.', 'claims': C,
            'gaps': ['The earliest indexed record that mentions both names is not necessarily the first report of the relationship; read it to check.']}


def _equation(s, rel, a):
    import mechanistic_demos as demos
    import mechanistic_sbml as sbml
    import perturbation as P
    g = a['gene']; C = []
    for mid, M in P.MODELS.items():
        if g not in M['genes']:
            continue
        kind, terms, what = M['genes'][g]
        m = demos.load(M['demo']) if 'demo' in M else sbml.Model((demos.FIXTURES / (M['biomodels'] + '.xml')).read_text())
        d = m.describe(); rx = [r for r, rr in zip(m.reactions, d['reactions']) if any(t in [x['species'] for x in r['reactants'] + r['products']] or t.split('.')[-1] in rr['rate'] for t in terms)][:4]
        for r, rr in [(r, next(x for x in d['reactions'] if x['id'] == r['id'])) for r in rx]:
            C.append(claim(f'{M["name"].split(" (")[0]} — {rr.get("name", rr["id"])}: rate = {rr["rate"]}', 'Mechanistic model (published equation)', M['name']))
    C.append(claim('Spatial gradients in the PhysiCell tumor model follow BioFVM: ∂ρ/∂t = D∇²ρ − λρ + S(ρ* − ρ) − Uρ, with diffusion D, decay λ, secretion S toward a target ρ* and uptake U set per substrate and cell type.',
                   'Mechanistic model (reaction–diffusion)', 'Ghaffarizadeh A et al., Bioinformatics 2016 (BioFVM)'))
    return {'answer': f'{len(C) - 1} rate law(s) involving {g} in the published models here, plus the transport equation behind simulated gradients.', 'claims': C,
            'gaps': [] if len(C) > 1 else [f'{g} is not mapped into any mechanistic model here.']}


def _generalize(s, rel, a):
    import drug_response as R
    lin = a.get('lineage')
    if not lin:
        raise ValueError('Name a lineage to hold out, e.g. "Does the erlotinib model generalize to Lung?"')
    r = R.held_out_lineage(s, a['drug'], lin); rr = r['results']['ridge']; mm = r['results']['mean']
    c = claim(f'{r["drug"]["name"]}: ridge trained on {r["train"]} lines from other lineages, tested on {r["test"]} {lin} lines: Pearson {rr.get("pearson", float("nan")):.2f}, RMSE {rr["rmse"]:.2f} vs {mm["rmse"]:.2f} for the training mean; 90 % interval coverage {rr.get("coverage90", float("nan")):.0%}.',
              'AI prediction scored against experimental observation', 'GDSC 8.5; DepMap expression; held-out lineage')
    return {'answer': c['text'], 'claims': [c], 'gaps': ['Cell lines are not patient cohorts; generalisation to patients is not tested here.']}
