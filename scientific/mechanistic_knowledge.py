"""Scientific knowledge adapters and model discovery for the Mechanistic Biology Lab.

Sources (all public, documented REST APIs):
- UniProt REST  https://rest.uniprot.org        protein identity and function
- Reactome      https://reactome.org/ContentService   pathways for a UniProt accession
- BioModels     https://www.ebi.ac.uk/biomodels   published SBML models (content CC0)

Every response is cached on disk with its URL and retrieval time, and every node
and edge in the knowledge graph carries the source it came from. Entities are
linked only through stable identifiers (UniProt accessions in model annotations),
never by name similarity. A pathway relationship is curated knowledge, not a
kinetic model; only executable SBML can produce numbers.
"""
import hashlib, json, pathlib, time, urllib.parse, urllib.request
import mechanistic_sbml as sbml

USER_AGENT = 'FoldStudio-MechanisticLab/1.0 (+local research application)'
TTL = 7 * 24 * 3600
SOURCES = {
    'uniprot': {'name': 'UniProt', 'url': 'https://www.uniprot.org', 'licence': 'CC BY 4.0', 'reference': 'The UniProt Consortium, Nucleic Acids Res. 2025, doi:10.1093/nar/gkae1010'},
    'reactome': {'name': 'Reactome', 'url': 'https://reactome.org', 'licence': 'CC BY 4.0', 'reference': 'Milacic M et al., Nucleic Acids Res. 2024, doi:10.1093/nar/gkad1025'},
    'biomodels': {'name': 'BioModels', 'url': 'https://www.ebi.ac.uk/biomodels', 'licence': 'Models CC0', 'reference': 'Malik-Sheriff RS et al., Nucleic Acids Res. 2020, doi:10.1093/nar/gkz1055'},
    'sabio-rk': {'name': 'SABIO-RK', 'url': 'https://sabiork.h-its.org', 'licence': 'See terms of use', 'reference': 'Wittig U et al., Nucleic Acids Res. 2012, doi:10.1093/nar/gkr1046', 'status': 'planned: the REST endpoint redirected during integration on 29 Oct 2026'},
    'chembl': {'name': 'ChEMBL', 'url': 'https://www.ebi.ac.uk/chembl', 'licence': 'CC BY-SA 3.0', 'status': 'planned'},
    'iuphar': {'name': 'IUPHAR/BPS Guide to Pharmacology', 'url': 'https://www.guidetopharmacology.org', 'licence': 'CC BY-SA 4.0', 'status': 'planned'},
    'rhea': {'name': 'Rhea', 'url': 'https://www.rhea-db.org', 'licence': 'CC BY 4.0', 'status': 'planned'},
    'bindingdb': {'name': 'BindingDB', 'url': 'https://www.bindingdb.org', 'licence': 'CC BY 3.0', 'status': 'planned'},
}


class KnowledgeError(RuntimeError):
    pass


class Cache:
    def __init__(self, root):
        self.root = pathlib.Path(root); self.root.mkdir(parents=True, exist_ok=True)

    def path(self, url, suffix='.json'):
        return self.root / (hashlib.sha256(url.encode()).hexdigest()[:24] + suffix)

    def fetch(self, url, as_json=True, ttl=TTL):
        f = self.path(url, '.json' if as_json else '.txt')
        meta = f.with_suffix(f.suffix + '.meta')
        if f.exists() and meta.exists() and time.time() - json.loads(meta.read_text())['retrieved'] < ttl:
            text = f.read_text(); m = json.loads(meta.read_text())
            return (json.loads(text) if as_json else text), {**m, 'cached': True}
        try:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json' if as_json else '*/*'})
            with urllib.request.urlopen(req, timeout=25) as r:
                text = r.read().decode('utf-8')
        except Exception as e:
            if f.exists():
                m = json.loads(meta.read_text()) if meta.exists() else {}
                return (json.loads(f.read_text()) if as_json else f.read_text()), {**m, 'cached': True, 'stale': True, 'error': str(e)}
            raise KnowledgeError('Could not reach ' + urllib.parse.urlparse(url).netloc + ': ' + str(e))
        f.write_text(text)
        m = {'url': url, 'retrieved': time.time(), 'retrievedISO': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
        meta.write_text(json.dumps(m))
        return (json.loads(text) if as_json else text), {**m, 'cached': False}


def uniprot_search(cache, query, organism='9606', size=8):
    q = '(' + query + ')' + (' AND organism_id:' + organism if organism else '') + ' AND reviewed:true'
    fields = 'accession,id,protein_name,gene_names,organism_name,cc_function,cc_subcellular_location,xref_reactome'
    data, meta = cache.fetch('https://rest.uniprot.org/uniprotkb/search?' + urllib.parse.urlencode({'query': q, 'format': 'json', 'size': size, 'fields': fields}))
    out = []
    for r in data.get('results', []):
        names = r.get('proteinDescription', {}).get('recommendedName', {}).get('fullName', {}).get('value') or r.get('uniProtkbId')
        genes = [g.get('geneName', {}).get('value') for g in r.get('genes', []) if g.get('geneName')]
        function = next((t['value'] for c in r.get('comments', []) if c.get('commentType') == 'FUNCTION' for t in c.get('texts', [])), '')
        locations = [loc['location']['value'] for c in r.get('comments', []) if c.get('commentType') == 'SUBCELLULAR LOCATION' for loc in c.get('subcellularLocations', []) if loc.get('location')]
        out.append({'accession': r['primaryAccession'], 'name': names, 'genes': genes, 'organism': r.get('organism', {}).get('scientificName'), 'function': function[:600], 'locations': locations[:6]})
    return {'results': out, 'source': {**SOURCES['uniprot'], **meta}}


def reactome_pathways(cache, accession, species='9606'):
    try:
        data, meta = cache.fetch(f'https://reactome.org/ContentService/data/mapping/UniProt/{urllib.parse.quote(accession)}/pathways?species={species}')
    except KnowledgeError as e:
        if '404' in str(e):
            return {'pathways': [], 'source': SOURCES['reactome']}
        raise
    return {'pathways': [{'id': p['stId'], 'name': p['displayName'], 'url': 'https://reactome.org/content/detail/' + p['stId']} for p in data], 'source': {**SOURCES['reactome'], **meta}}


def biomodels_search(cache, query, size=10):
    data, meta = cache.fetch('https://www.ebi.ac.uk/biomodels/search?' + urllib.parse.urlencode({'query': query, 'format': 'json', 'numResults': size, 'domain': 'biomodels'}))
    models = [{'id': m['id'], 'name': m.get('name'), 'format': m.get('format'), 'curated': (m.get('curationStatus') or '').upper() == 'CURATED' or m['id'].startswith('BIOMD'),
               'url': m.get('url'), 'submitted': m.get('submissionDate')} for m in data.get('models', [])]
    return {'models': models, 'total': data.get('matches', len(models)), 'source': {**SOURCES['biomodels'], **meta}}


def biomodels_fetch(cache, model_id):
    if not model_id or not all(c.isalnum() or c in '_-' for c in model_id):
        raise KnowledgeError('Invalid BioModels identifier.')
    meta_json, meta = cache.fetch(f'https://www.ebi.ac.uk/biomodels/{model_id}?format=json')
    files = meta_json.get('files', {}).get('main', [])
    sbml_file = next((f['name'] for f in files if f['name'].lower().endswith('.xml')), None)
    if not sbml_file:
        raise KnowledgeError(model_id + ' has no SBML main file.')
    text, file_meta = cache.fetch(f'https://www.ebi.ac.uk/biomodels/model/download/{model_id}?' + urllib.parse.urlencode({'filename': sbml_file}), as_json=False)
    publication = meta_json.get('publication') or {}
    source = {'kind': 'biomodels', 'id': model_id, 'name': meta_json.get('name'), 'file': sbml_file, 'curation': meta_json.get('curationStatus'),
              'publication': {'title': publication.get('title'), 'link': publication.get('link'), 'year': publication.get('year'), 'journal': publication.get('journal'),
                              'authors': [a.get('name') for a in publication.get('authors', [])][:8]},
              'retrieved': file_meta.get('retrievedISO'), 'url': f'https://www.ebi.ac.uk/biomodels/{model_id}', 'licence': 'CC0'}
    return text, source


def discover(cache, accession, gene, limit=6):
    """Rank published models for a target. Relevance is evidence-based: a model
    whose species annotations cite the accession outranks a keyword hit."""
    found, notes = {}, []
    for query in [q for q in (accession, gene) if q]:
        try:
            for m in biomodels_search(cache, query, 15)['models']:
                found.setdefault(m['id'], {**m, 'matchedBy': []})['matchedBy'].append(query)
        except KnowledgeError as e:
            notes.append(str(e))
    ranked = []
    for m in list(found.values())[:limit * 2]:
        entry = {**m, 'executable': False, 'unsupported': [], 'annotatedTarget': False, 'missingParameters': []}
        if (m.get('format') or '').upper().find('SBML') < 0:
            entry['unsupported'] = ['Not an SBML model (' + str(m.get('format')) + ').']
        else:
            try:
                text, source = biomodels_fetch(cache, m['id'])
                model = sbml.Model(text, source)
                entry.update(executable=model.executable, unsupported=model.unsupported, species=len(model.species), reactions=len(model.reactions),
                             publication=source['publication'], annotatedTarget=any(r['accession'].split('-')[0] == accession for s in model.species for r in s['references'] if r['database'] == 'uniprot'),
                             missingParameters=[p['id'] for p in model.parameters if p['value'] is None])
            except (KnowledgeError, sbml.SBMLError) as e:
                entry['unsupported'] = [str(e)]
        score = (3 if entry['annotatedTarget'] else 0) + (2 if entry['executable'] else 0) + (1 if entry['curated'] else 0) + (0.5 if accession in entry['matchedBy'] else 0)
        entry['score'] = score
        entry['why'] = ', '.join(x for x in [('cites ' + accession + ' in its species annotations') if entry['annotatedTarget'] else '',
                                             'curated' if entry['curated'] else 'not curated', 'executable here' if entry['executable'] else 'not executable here'] if x)
        ranked.append(entry)
    ranked.sort(key=lambda e: -e['score'])
    return {'models': ranked[:limit], 'notes': notes, 'source': SOURCES['biomodels']}


def graph(target, pathways, models, model_detail=None):
    """Knowledge graph: protein → pathways (Reactome), protein → models (BioModels), model → species → cross-references."""
    nodes, edges = [], []
    pid = 'uniprot:' + target['accession']
    nodes.append({'id': pid, 'kind': 'protein', 'label': (target.get('genes') or [target['accession']])[0], 'detail': target.get('name'), 'source': 'UniProt'})
    for p in pathways[:14]:
        nodes.append({'id': 'reactome:' + p['id'], 'kind': 'pathway', 'label': p['name'], 'url': p['url'], 'source': 'Reactome'})
        edges.append({'from': pid, 'to': 'reactome:' + p['id'], 'relation': 'participates in', 'evidence': 'curated pathway annotation', 'source': 'Reactome'})
    for m in models:
        nodes.append({'id': 'biomodels:' + m['id'], 'kind': 'model', 'label': m['name'], 'executable': m.get('executable'), 'source': 'BioModels'})
        edges.append({'from': pid, 'to': 'biomodels:' + m['id'], 'relation': 'described by model' if m.get('annotatedTarget') else 'keyword match', 'evidence': 'model annotation' if m.get('annotatedTarget') else 'search hit (unverified)', 'source': 'BioModels'})
        link = (m.get('publication') or {}).get('link')
        if link:
            nodes.append({'id': 'pub:' + link, 'kind': 'publication', 'label': (m['publication'].get('title') or link)[:80], 'url': link, 'source': 'BioModels'})
            edges.append({'from': 'biomodels:' + m['id'], 'to': 'pub:' + link, 'relation': 'published in', 'evidence': 'model metadata', 'source': 'BioModels'})
    return {'nodes': nodes, 'edges': edges}
