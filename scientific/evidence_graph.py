"""Demo K · cancer evidence graph: one molecular feature, every relationship with its provenance.

Each edge records: relation, origin (experimental · curated · computed · text-mined · predicted), strength, source database and
version, citation, species, cell or disease context, and retrieval time. Raw responses of every external call are saved with
SHA-256 so the graph can be rebuilt offline. A failed source becomes a visible 'unavailable' node, never a silent gap.
A text-mined association is never promoted to an experimental interaction; clinical (CIViC) items are curated evidence
summaries, not treatment recommendations.
"""
import hashlib
import json
import pathlib
import time
import urllib.parse
import urllib.request

UA = {'User-Agent': 'FoldStudio/evidence-graph', 'Accept': 'application/json'}
CONTEXT = {'KRAS': {'disease': 'lung adenocarcinoma', 'mondo': 'MONDO_0005061', 'civic': ['Lung Non-small Cell Carcinoma', 'Lung Adenocarcinoma'], 'study': 'luad_tcga_pan_can_atlas_2018',
                    'partners': ['STK11', 'KEAP1', 'EGFR', 'TP53'], 'variants': ['KRAS G12C', 'KRAS G12D', 'KRAS G12V', 'KRAS Mutation']}}
# Further contexts, each tied to an installed TCGA cohort; disease IDs checked against Open Targets search (MONDO).
_LUNG = {'disease': 'lung adenocarcinoma', 'mondo': 'MONDO_0005061', 'civic': ['Lung Non-small Cell Carcinoma', 'Lung Adenocarcinoma'], 'study': 'luad_tcga_pan_can_atlas_2018'}
_SKIN = {'disease': 'cutaneous melanoma', 'mondo': 'MONDO_0005012', 'civic': ['Melanoma', 'Skin Melanoma', 'Cutaneous Melanoma'], 'study': 'skcm_tcga_pan_can_atlas_2018'}
CONTEXT.update({
    'EGFR': {**_LUNG, 'partners': ['KRAS', 'TP53', 'STK11', 'ERBB2'], 'variants': ['EGFR L858R', 'EGFR T790M', 'EGFR Exon 19 Deletion', 'EGFR Mutation']},
    'STK11': {**_LUNG, 'partners': ['KRAS', 'KEAP1', 'TP53', 'EGFR'], 'variants': ['STK11 Loss', 'STK11 Mutation']},
    'KEAP1': {**_LUNG, 'partners': ['KRAS', 'STK11', 'NFE2L2', 'TP53'], 'variants': ['KEAP1 Mutation', 'KEAP1 Loss']},
    'BRAF': {**_SKIN, 'partners': ['NRAS', 'NF1', 'PTEN', 'CDKN2A'], 'variants': ['BRAF V600E', 'BRAF V600K', 'BRAF V600', 'BRAF Mutation']},
    'NRAS': {**_SKIN, 'partners': ['BRAF', 'NF1', 'PTEN', 'CDKN2A'], 'variants': ['NRAS Q61R', 'NRAS Q61K', 'NRAS Q61', 'NRAS Mutation']},
})


class Graph:
    def __init__(self):
        self.nodes, self.edges, self.sources, self._seen = {}, [], {}, set()

    def node(self, nid, kind, label, **info):
        self.nodes.setdefault(nid, {'id': nid, 'type': kind, 'label': label, **info})
        return nid

    def edge(self, a, b, relation, origin, source, strength=None, citation=None, context=None, species='Homo sapiens', **info):
        key = (a, b, relation, source, str(strength), str(citation))
        if key in self._seen:          # the same fact retrieved by several queries is one edge
            return
        self._seen.add(key)
        self.edges.append({'source': a, 'target': b, 'relation': relation, 'origin': origin, 'strength': strength, 'database': source,
                           'citation': citation, 'context': context, 'species': species, **info})


def _get(g, name, url, raw_dir, body=None, text=False):
    try:
        req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                     headers={**UA, **({'Accept': 'text/plain'} if text else {}), **({'Content-Type': 'application/json'} if body else {})})
        raw = urllib.request.urlopen(req, timeout=60).read()
        (raw_dir / f'{name}.json').write_bytes(raw)
        g.sources[name] = {'url': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'retrieved': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'ok': True}
        return raw.decode().strip() if text else json.loads(raw)
    except Exception as e:
        g.sources[name] = {'url': url, 'ok': False, 'error': f'{type(e).__name__}: {str(e)[:200]}'}
        g.node('unavailable:' + name, 'unavailable', f'{name} unavailable'); return None


def build(s, gene='KRAS', log=print):
    ctx = CONTEXT[gene]; g = Graph()
    out = pathlib.Path(s.root) / 'oncology' / 'evidence' / gene; raw = out / 'raw'; raw.mkdir(parents=True, exist_ok=True)
    G = g.node('gene:' + gene, 'gene', gene); DIS = g.node('disease:' + ctx['mondo'], 'disease', ctx['disease'])
    # ---- protein (UniProt, CC BY 4.0)
    u = _get(g, 'uniprot', f'https://rest.uniprot.org/uniprotkb/search?query=gene_exact:{gene}+AND+organism_id:9606+AND+reviewed:true&fields=accession,protein_name,length,cc_function&format=json', raw)
    if u and u.get('results'):
        e = u['results'][0]; acc = e['primaryAccession']
        fn = next((c['texts'][0]['value'] for c in e.get('comments', []) if c.get('commentType') == 'FUNCTION'), '')
        P = g.node('protein:' + acc, 'protein', f'{acc} · {e["proteinDescription"]["recommendedName"]["fullName"]["value"]}', length=e.get('sequence', {}).get('length'), function=fn[:400])
        g.edge(G, P, 'encodes', 'curated', 'UniProtKB/Swiss-Prot (reviewed)', citation=f'https://www.uniprot.org/uniprotkb/{acc}')
        # ---- pathways (Reactome)
        rv = _get(g, 'reactome_version', 'https://reactome.org/ContentService/data/database/version', raw, text=True)
        rx = _get(g, 'reactome', f'https://reactome.org/ContentService/data/mapping/UniProt/{acc}/pathways?species=9606', raw)
        for pw in (rx or [])[:14]:
            n = g.node('pathway:' + pw['stId'], 'pathway', pw['displayName'], inDisease=pw.get('isInDisease'))
            g.edge(P, n, 'participates in', 'curated', f'Reactome release {rv}', citation=f'https://reactome.org/content/detail/{pw["stId"]}', inferred=pw.get('isInferred'), disease=pw.get('isInDisease'))
    # ---- interactions (STRING): origin from the evidence channel, never collapsed into one label
    sv = _get(g, 'string_version', 'https://string-db.org/api/json/version', raw)
    st = _get(g, 'string', f'https://string-db.org/api/json/network?identifiers={gene}&species=9606&required_score=700&caller_identity=foldstudio', raw)
    for i in (st or []):
        if gene not in (i['preferredName_A'], i['preferredName_B']):
            continue
        other = i['preferredName_B'] if i['preferredName_A'] == gene else i['preferredName_A']
        origin = 'experimental' if i['escore'] >= 0.4 else 'curated' if i['dscore'] >= 0.4 else 'text-mined' if i['tscore'] >= 0.4 else 'predicted'
        n = g.node('gene:' + other, 'interactor', other)
        g.edge(G, n, 'interacts with', origin, f'STRING {sv[0]["string_version"] if sv else "?"}', strength=i['score'], channels={'experimental': i['escore'], 'database': i['dscore'], 'textmining': i['tscore'], 'coexpression': i['ascore']},
               citation='https://string-db.org/network/9606.' + i['stringId_A'].split('.')[-1])
    # ---- target–disease association (Open Targets Platform)
    ot = _get(g, 'opentargets', 'https://api.platform.opentargets.org/api/v4/graphql', raw, body={'query': '{ meta { dataVersion { year month } } search(queryString:"%s", entityNames:["target"]){ hits { id name } } }' % gene})
    ens = next((h['id'] for h in (ot or {}).get('data', {}).get('search', {}).get('hits', []) if h['name'] == gene), None)
    if ens:
        a = _get(g, 'opentargets_assoc', 'https://api.platform.opentargets.org/api/v4/graphql', raw,
                 body={'query': '{ target(ensemblId:"%s"){ associatedDiseases(page:{index:0,size:500}){ rows { disease { id name } score datatypeScores { id score } } } } }' % ens})
        rows = (a or {}).get('data', {}).get('target', {}).get('associatedDiseases', {}).get('rows', [])
        hit = next((r for r in rows if r['disease']['id'] == ctx['mondo']), None)
        ver = ot['data']['meta']['dataVersion']
        if hit:
            g.edge(G, DIS, 'associated with', 'curated', f'Open Targets Platform {ver["year"]}.{ver["month"]}', strength=hit['score'], datatypes={d['id']: d['score'] for d in hit['datatypeScores']},
                   citation=f'https://platform.opentargets.org/evidence/{ens}/{ctx["mondo"]}', note='Integrated score across evidence types; not a measure of causality or efficacy')
    # ---- curated clinical evidence (CIViC, CC0) — summaries of published evidence, not recommendations
    for v in ctx['variants']:
        for dname in ctx['civic']:
            c = _get(g, f'civic_{v}_{dname}'.replace(' ', '_'), 'https://civicdb.org/api/graphql', raw, body={'query': '{ evidenceItems(first:20, molecularProfileName:"%s", diseaseName:"%s", status: ACCEPTED){ nodes { id name evidenceType evidenceLevel significance evidenceDirection therapies{name} source{citation sourceType citationId} } } }' % (v, dname)})
            for ev in ((c or {}).get('data', {}).get('evidenceItems', {}) or {}).get('nodes', []):
                V = g.node('variant:' + v, 'variant', v); g.edge(G, V, 'has variant', 'curated', 'CIViC')
                tgt = g.node('drug:' + ev['therapies'][0]['name'], 'drug', ev['therapies'][0]['name']) if ev['therapies'] else DIS
                g.edge(V, tgt, f'{ev["evidenceType"].lower()} · {ev["significance"].lower().replace("_", " ")}', 'curated', 'CIViC (CC0)', strength=f'level {ev["evidenceLevel"]}',
                       citation=f'{ev["source"]["citation"]} · {ev["source"]["sourceType"]} {ev["source"]["citationId"]}', context=dname, direction=ev['evidenceDirection'], civic=f'https://civicdb.org/evidence/{ev["id"]}')
    # ---- literature (Europe PMC): counts and most-cited; preprints flagged
    q = f'{gene} AND "{ctx["disease"]}"'
    lit = _get(g, 'europepmc', 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urllib.parse.urlencode({'query': q, 'format': 'json', 'pageSize': 8, 'sort': 'CITED desc', 'resultType': 'lite'}), raw)
    pre = _get(g, 'europepmc_preprints', 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?' + urllib.parse.urlencode({'query': q + ' AND SRC:PPR', 'format': 'json', 'pageSize': 1}), raw)
    for r in (lit or {}).get('resultList', {}).get('result', []):
        n = g.node('pub:' + str(r.get('id')), 'publication', f'{r.get("authorString", "")[:40]} {r.get("pubYear", "")} · {r.get("title", "")[:80]}', year=r.get('pubYear'), cited=r.get('citedByCount'),
                   preprint=r.get('source') == 'PPR', journal=r.get('journalTitle'))
        g.edge(n, DIS, 'reports on', 'text-mined', 'Europe PMC search', citation=f'{r.get("source")}:{r.get("id")}', note='retrieved by keyword search; relevance not curated')
    litstats = {'query': q, 'total': (lit or {}).get('hitCount'), 'preprints': (pre or {}).get('hitCount')}
    # ---- mechanistic models (BioModels)
    bm = _get(g, 'biomodels', 'https://www.ebi.ac.uk/biomodels/search?' + urllib.parse.urlencode({'query': gene, 'numResults': 10, 'format': 'json'}), raw)
    for mdl in (bm or {}).get('models', [])[:6]:
        n = g.node('model:' + mdl['id'], 'model', f'{mdl["id"]} · {mdl["name"][:60]}')
        g.edge(n, G, 'includes', 'curated' if 'BIOMD' in mdl['id'] else 'predicted', 'BioModels', citation=f'https://www.ebi.ac.uk/biomodels/{mdl["id"]}', note='BIOMD = manually curated; MODEL = non-curated submission')
    # ---- computed evidence from the app's own analyses on installed data
    computed = {}
    try:
        import oncology_data as D, oncology_stats as S
        rel = D.Release(s); r = S.mutation_scan(rel, gene, 'hotspot', top=20000)
        h = next(x for x in r['hits'] if x['gene'] == gene); rank = r['hits'].index(h) + 1
        DS = g.node('dataset:depmap', 'dataset', f'DepMap {rel.release} CRISPR (Chronos)')
        g.edge(DS, G, f'{gene}-mutant models depend on {gene}', 'computed', f'fold · DepMap {rel.release}', strength=f'β {h["beta"]:.2f} ({h["ci"][0]:.2f} to {h["ci"][1]:.2f}), q {h["q"]:.1e}, rank {rank}',
               context=f'{r["mutant"]} mutant of {r["n"]} models, lineage-adjusted', citation=rel.manifest.get('citation'))
        computed['depmap'] = {'beta': h['beta'], 'ci': h['ci'], 'q': h['q'], 'rank': rank, 'mutant': r['mutant'], 'n': r['n']}
        prof = S.gene_profile(rel, gene); top = prof['lineages'][0]
        computed['depmapLineage'] = {'lineage': top['lineage'], 'median': top['median'], 'fracDependent': top['fracDependent']}
    except Exception as e:
        g.node('unavailable:depmap', 'unavailable', f'DepMap computation unavailable ({type(e).__name__})')
    try:
        import drug_response as R
        b = R.biomarker_scan(s, gene); DG = g.node('dataset:gdsc', 'dataset', 'GDSC2 drug response')
        for x in [r for r in b['results'] if r['q'] < 0.01][:8]:
            n = g.node('drug:' + x['drug'], 'drug', x['drug'], target=x['target'])
            g.edge(G, n, f'mutation {"sensitises to" if x["deltaLnIC50"] < 0 else "associated with resistance to"}', 'computed', 'fold · GDSC 8.5 × DepMap', strength=f'Δ ln IC50 {x["deltaLnIC50"]:.2f} ({x["ci"][0]:.2f} to {x["ci"][1]:.2f}), q {x["q"]:.1e}',
                   context=f'{x["mutant"]} mutant vs {x["wildtype"]} wild-type lines, lineage-adjusted', via=DG)
        computed['gdsc'] = [{k: x[k] for k in ('drug', 'target', 'deltaLnIC50', 'ci', 'q', 'mutant')} for x in b['results'][:12]]
    except Exception as e:
        g.node('unavailable:gdsc', 'unavailable', f'GDSC computation unavailable ({type(e).__name__})')
    try:
        import cancer_genomics as C
        sm = C.summary(s, ctx['study']); row = next(x for x in sm['genes'] if x['gene'] == gene)
        TC = g.node('dataset:tcga', 'dataset', f'TCGA {ctx["disease"]} (cBioPortal)')
        g.edge(TC, DIS, f'{gene} altered in {row["freq"] * 100:.0f} % of tumors', 'experimental', 'TCGA PanCancer Atlas via cBioPortal', strength=f'{row["altered"]}/{sm["profiledSamples"]} samples', context=ctx['disease'])
        pr = C.pairs(s, ctx['study'], [gene] + ctx['partners'])
        for x in pr['pairs']:
            if gene in (x['a'], x['b']) and x['q'] < 0.05:
                other = x['b'] if x['a'] == gene else x['a']; n = g.node('gene:' + other, 'interactor', other)
                g.edge(G, n, x['tendency'], 'computed', 'fold · TCGA', strength=f'log2 OR {x["log2OR"]:.2f}, q {x["q"]:.1e}', context=f'{ctx["disease"]} tumors')
        sv = C.survival(s, ctx['study'], gene)
        g.edge(G, DIS, 'alteration and overall survival', 'computed', 'fold · TCGA', strength=f'HR {sv["cox"][0]["hr"]:.2f} ({sv["cox"][0]["ci"][0]:.2f}–{sv["cox"][0]["ci"][1]:.2f}), age-adjusted', context=f'{sv["patients"]} patients')
        computed['tcga'] = {'freq': row['freq'], 'altered': row['altered'], 'n': sm['profiledSamples'], 'hr': sv['cox'][0]}
    except Exception as e:
        g.node('unavailable:tcga', 'unavailable', f'TCGA computation unavailable ({type(e).__name__})')
    # ---- the causal-explorer trace: observation → screen → pharmacology → clinic, with the gaps named
    trace = [
        {'step': 'Observed in patients', 'category': 'Experimental observation', 'claim': f'{gene} is altered in {computed["tcga"]["freq"] * 100:.0f} % of TCGA {ctx["disease"]}' if 'tcga' in computed else 'unavailable'},
        {'step': 'Functional screen', 'category': 'Statistical association (from a measured CRISPR screen)', 'claim': f'{gene}-mutant cell lines depend on {gene}: β {computed["depmap"]["beta"]:.2f}, rank {computed["depmap"]["rank"]} of all genes' if 'depmap' in computed else 'unavailable'},
        {'step': 'Pharmacology in cell lines', 'category': 'Statistical association (measured drug response)', 'claim': ('; '.join(f'{d} Δ {v:.2f}' for d, v in {x['drug']: x['deltaLnIC50'] for x in sorted(computed.get('gdsc', []), key=lambda x: -x['deltaLnIC50']) if x['q'] < 0.01 and x['deltaLnIC50'] < 0}.items()) or 'no sensitising drug at q < 0.01') + ' (lineage-adjusted; the strongest screen per compound)' if 'gdsc' in computed else 'unavailable'},
        {'step': 'Curated clinical evidence', 'category': 'Curated evidence summary (CIViC)', 'claim': f'{sum(1 for e in g.edges if e["database"] == "CIViC (CC0)")} accepted CIViC evidence items in {", ".join(ctx["civic"])}'},
        {'step': 'Literature', 'category': 'Text-mined retrieval', 'claim': f'{litstats["total"]} Europe PMC records ({litstats["preprints"]} preprints) for {q}'}]
    gaps = ['Normal-tissue dependency: DepMap screens cancer lines only; selectivity against normal tissue is not established here.',
            'Causality in patients: TCGA associations are observational and unadjusted for stage or treatment.',
            'Mutation type: DepMap and GDSC analyses pool all hotspot alleles; allele-specific effects (e.g. G12C) are not separated.',
            'Independent replication: the dependency is computed in one screen release; Sanger Project Score is not yet connected.']
    res = {'gene': gene, 'context': ctx, 'nodes': list(g.nodes.values()), 'edges': g.edges, 'sources': g.sources, 'literature': litstats, 'computed': computed, 'trace': trace, 'gaps': gaps,
           'origins': {'experimental': 'measured in an experiment', 'curated': 'expert-curated database entry', 'computed': 'calculated here from installed data',
                       'text-mined': 'retrieved or inferred from text', 'predicted': 'computational prediction or non-curated submission'},
           'built': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    (out / 'graph.json').write_text(json.dumps(res, default=float))
    log(f'{len(g.nodes)} nodes, {len(g.edges)} edges; sources ok: {sum(v["ok"] for v in g.sources.values())}/{len(g.sources)}')
    return res
