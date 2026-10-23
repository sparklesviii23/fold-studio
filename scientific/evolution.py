"""Immutable, project-scoped BGMEE candidates and evidence. No implicit compute.

Sequence proposals never inherit their parent's predicted coordinates or scores.
Native residue identities are explicit maps, not offsets guessed from chain names.
"""
import copy
import hashlib
import json
import math
import re
import uuid

import intelligence as mi
import research

ACTIONS = {'evolution_list', 'evolution_import', 'evolution_derive', 'evolution_decide',
           'evolution_assess', 'evolution_compare', 'evolution_manifest', 'evolution_manifests'}
AA = frozenset('ACDEFGHIKLMNPQRSTVWY')
TAGS = {'motif', 'interface', 'exposed', 'core', 'linker', 'experimental'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def text(value, label, maximum=200, required=True):
    if not isinstance(value, str) or len(value.strip()) > maximum or required and not value.strip():
        raise ValueError('Supply '+label+' of up to '+str(maximum)+' characters.')
    return value.strip()


def integer(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(label+' must be an integer from '+str(low)+' to '+str(high)+'.')
    return value


def positions(values, length, label):
    if not isinstance(values, list) or any(type(v) is not int or not 1 <= v <= length for v in values) or len(set(values)) != len(values):
        raise ValueError(label+' must contain distinct 1-based sequence positions.')
    return sorted(values)


def mask(value, sequence):
    if not isinstance(value, dict) or set(value)-{'fixed', 'mutable', 'preferred', 'excluded', 'tags'}:
        raise ValueError('Unsupported residue constraint fields.')
    length = len(sequence)
    fixed = positions(value.get('fixed', []), length, 'Fixed residues')
    mutable = positions(value.get('mutable', [i for i in range(1, length+1) if i not in fixed]), length, 'Mutable residues')
    if set(fixed) & set(mutable):
        raise ValueError('Fixed and mutable residues overlap.')
    # Unlisted positions are fixed, never silently made mutable.
    fixed = sorted(set(range(1, length+1))-set(mutable))
    result = {'fixed': fixed, 'mutable': mutable, 'preferred': {}, 'excluded': {}, 'tags': {}}
    for name in ('preferred', 'excluded'):
        table = value.get(name, {})
        if not isinstance(table, dict):
            raise ValueError(name+' must be keyed by 1-based sequence position.')
        for key, codes in table.items():
            if not isinstance(key, str) or not key.isdigit() or str(int(key)) != key or int(key) not in mutable or not isinstance(codes, str) or not codes or set(codes)-AA or len(set(codes)) != len(codes):
                raise ValueError('Use distinct canonical amino acids at mutable positions for '+name+'.')
            if name == 'excluded' and len(codes) == 20:
                raise ValueError('At least one amino acid must remain allowed.')
            result[name][key] = ''.join(sorted(codes))
    for key, codes in result['preferred'].items():
        if set(codes) <= set(result['excluded'].get(key, '')):
            raise ValueError('All preferred amino acids are excluded.')
    tags = value.get('tags', {})
    if not isinstance(tags, dict) or set(tags)-TAGS:
        raise ValueError('Unknown residue annotation tag.')
    result['tags'] = {tag: positions(items, length, tag) for tag, items in tags.items()}
    return result


def reference(value, sequence):
    allowed = {'group', 'protein', 'species', 'accession', 'isoform', 'start', 'end', 'source', 'publication', 'evidence', 'uncertainty'}
    if not isinstance(value, dict) or set(value)-allowed:
        raise ValueError('Unsupported biological reference field.')
    result = {key: text(v, key, 4000 if key in ('evidence', 'uncertainty') else 500, False) for key, v in value.items() if key not in ('start', 'end')}
    if 'start' in value or 'end' in value:
        start = integer(value.get('start'), 'Native start', 1, 1000000)
        end = integer(value.get('end'), 'Native end', start, 1000000)
        if end-start+1 != len(sequence):
            raise ValueError('Native reference range must match this exact sequence length; use explicit mapping for gaps.')
        if not all(result.get(k) for k in ('species', 'accession', 'isoform')):
            raise ValueError('Native numbering requires species, accession and isoform.')
        result.update(start=start, end=end)
    return result


def independence(candidate, observation):
    used = candidate['provenance']['conditioning']
    matches = [r for r in used if r['family'] == observation['family'] or r['model'] == observation['model']]
    if matches:
        return {'state': 'conditioned_or_correlated', 'reason': 'Model or family guided this lineage; not an independent final validator.'}
    return {'state': 'independence_unverified', 'reason': 'No matching conditioning recorded; training/template independence is not established.'}


class Evolution:
    def __init__(self, service):
        self.s = service
        service.db.executescript('''
          CREATE TABLE IF NOT EXISTS evolution_candidates(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,parent_id TEXT,data TEXT NOT NULL,created TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS evolution_events(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,candidate_id TEXT NOT NULL,kind TEXT NOT NULL,data TEXT NOT NULL,created TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS evolution_manifests(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,data TEXT NOT NULL,created TEXT NOT NULL);
        ''')

    def candidate(self, project, id):
        row = self.s.db.execute('SELECT data FROM evolution_candidates WHERE id=? AND project_id=?', (id, project)).fetchone()
        if not row:
            raise ValueError('Choose a saved evolution candidate in this project.')
        return json.loads(row[0])

    def event(self, project, id, kind, data):
        event = {'id': str(uuid.uuid4()), 'candidateId': id, 'kind': kind, 'data': data, 'created': research.utc()}
        self.s.db.execute('INSERT INTO evolution_events VALUES(?,?,?,?,?,?)', (event['id'], project, id, kind, canonical(data), event['created']))
        return event

    def insert(self, project, name, sequence, constraints, origin, mapping, parent=None, operation='import', conditioning=None):
        inherited = copy.deepcopy(parent['provenance']['conditioning']) if parent else []
        inherited += copy.deepcopy(conditioning or [])
        value = {'schemaVersion': 1, 'id': str(uuid.uuid4()), 'projectId': project, 'name': text(name, 'candidate name'),
                 'sequence': sequence, 'sequenceSha256': hashlib.sha256(sequence.encode()).hexdigest(),
                 'parentId': parent['id'] if parent else None, 'rootId': parent['rootId'] if parent else None,
                 'constraints': constraints, 'residueMap': copy.deepcopy(mapping), 'reference': origin,
                 'chemistry': {'representation': 'canonical_linear_protein', 'modifications': [], 'crosslinks': []},
                 'provenance': {'operation': operation, 'conditioning': inherited},
                 'structure': None, 'descriptors': research.liabilities(sequence),
                 'validation': 'sequence_only_unvalidated', 'created': research.utc()}
        value['rootId'] = value['rootId'] or value['id']
        self.s.db.execute('INSERT INTO evolution_candidates VALUES(?,?,?,?,?)', (value['id'], project, value['parentId'], canonical(value), value['created']))
        return value

    def evolution_list(self, p):
        rows = self.s.rows('SELECT data FROM evolution_candidates WHERE project_id=? ORDER BY created,id', (p['projectId'],))
        events = self.s.rows('SELECT * FROM evolution_events WHERE project_id=? ORDER BY created,id', (p['projectId'],))
        for event in events:
            event['data'] = json.loads(event['data'])
        return {'schemaVersion': 1, 'candidates': [json.loads(row['data']) for row in rows], 'events': events}

    def evolution_import(self, p):
        allowed = {'projectId', 'fasta', 'reference', 'constraints', 'structureId', 'chain', 'recordId', 'intelligenceCandidateId'}
        if set(p)-allowed:
            raise ValueError('Unsupported candidate import field.')
        modes = [key for key in ('fasta', 'structureId', 'recordId', 'intelligenceCandidateId') if p.get(key)]
        if len(modes) != 1:
            raise ValueError('Choose exactly one source: FASTA, saved sequence, structure chain or intelligence candidate.')
        source = {}; structure = None; native = None
        if modes[0] == 'fasta':
            if not isinstance(p['fasta'], str) or len(p['fasta']) > 120000:
                raise ValueError('FASTA input exceeds 120,000 characters.')
            records = self.s.fasta_parse({'text': p['fasta']})
        elif modes[0] == 'structureId':
            record, path = mi.Lab(self.s).record(p['structureId'])
            if record['project_id'] != p['projectId']:
                raise ValueError('Structure belongs to another project.')
            parsed = mi.parse_structure(path.read_text(), record['data']['format'])
            chain = next((c for c in parsed['chains'] if c['id'] == p.get('chain')), None)
            if not chain or not chain['sequence'] or set(chain['sequence'])-AA:
                raise ValueError('Select one observed canonical protein chain.')
            native = [r for r in parsed['residues'] if r['chain'] == chain['id'] and r['polymer']]
            if ''.join(r['one'] for r in native) != chain['sequence']:
                raise ValueError('Observed residue map and chain sequence disagree.')
            records = [{'name': record['name']+' · chain '+chain['id'], 'sequence': chain['sequence']}]
            structure = {'recordId': record['id'], 'sha256': record['data']['sha256'], 'chain': chain['id'], 'scope': 'observed saved coordinates; biological assembly unverified'}
        elif modes[0] == 'recordId':
            row = self.s.db.execute("SELECT * FROM records WHERE id=? AND project_id=? AND kind='sequence'", (p['recordId'], p['projectId'])).fetchone()
            if not row:
                raise ValueError('Choose a saved sequence in this project.')
            data = json.loads(row['data']); records = self.s.fasta_parse({'text': data.get('sequence', '')})
            records[0]['name'] = row['name']; source = {'recordId': row['id'], 'metadata': data}
        else:
            lab = mi.Lab(self.s)
            found = next((c for c in lab.intelligence_candidates(p) if c['id'] == p['intelligenceCandidateId']), None)
            if not found:
                raise ValueError('Choose a molecular intelligence candidate in this project.')
            records = [{'name': found['name'], 'sequence': found['data']['sequence']}]
            source = {'intelligenceCandidateId': found['id'], 'metadata': found['data']}
        prepared = []
        for record in records:
            seq = record['sequence']
            if not seq or set(seq)-AA:
                raise ValueError('Use canonical amino acids for this representation.')
            ref = reference(p.get('reference', {}), seq)
            if len(records) > 1 and ('start' in ref or p.get('constraints')):
                raise ValueError('Import numbered regions or constrained sequences individually; masks cannot be shared implicitly.')
            mapping = [{'position': i+1, 'wildType': aa, **({'structureResidueId': native[i]['id'], 'chain': native[i]['chain'], 'number': native[i]['num'], 'insertion': native[i]['ins']} if native else {}),
                        **({'referenceNumber': ref['start']+i, 'species': ref['species'], 'accession': ref['accession'], 'isoform': ref['isoform']} if 'start' in ref else {})} for i, aa in enumerate(seq)]
            prepared.append((record, ref, mask(p.get('constraints', {}), seq), mapping))
        values = []
        with self.s.db:
            for record, ref, constraints, mapping in prepared:
                value = self.insert(p['projectId'], record['name'], record['sequence'], constraints, ref, mapping)
                value['structure'] = structure
                value['source'] = source
                value['validation'] = 'observed_coordinates_unvalidated_binding' if structure else 'sequence_only_unvalidated'
                self.s.db.execute('UPDATE evolution_candidates SET data=? WHERE id=?', (canonical(value), value['id']))
                self.event(p['projectId'], value['id'], 'import', {'source': modes[0], 'structure': structure})
                values.append(value)
        return {'candidates': values, 'computationStarted': False}

    def evolution_derive(self, p):
        if set(p)-{'projectId', 'candidateId', 'name', 'mutations', 'constraints', 'purpose', 'evidence'}:
            raise ValueError('Unsupported mutation proposal field.')
        parent = self.candidate(p['projectId'], p['candidateId'])
        mutations = p.get('mutations')
        if not isinstance(mutations, list) or not 1 <= len(mutations) <= len(parent['sequence']):
            raise ValueError('Supply explicit residue substitutions.')
        seq = list(parent['sequence']); seen = set()
        for mutation in mutations:
            if not isinstance(mutation, dict) or set(mutation) != {'position', 'from', 'to'}:
                raise ValueError('Each mutation requires position, from and to.')
            pos = integer(mutation['position'], 'Mutation position', 1, len(seq))
            if pos in seen or pos not in parent['constraints']['mutable']:
                raise ValueError('Mutation is duplicated or outside the parent mutable mask.')
            if mutation['from'] != seq[pos-1] or not isinstance(mutation['to'], str) or mutation['to'] not in AA or len(mutation['to']) != 1 or mutation['from'] == mutation['to']:
                raise ValueError('Verify the wild-type residue and a distinct canonical substitution.')
            if mutation['to'] in parent['constraints']['excluded'].get(str(pos), ''):
                raise ValueError('Mutation violates an excluded amino acid constraint.')
            seen.add(pos); seq[pos-1] = mutation['to']
        evidence = p.get('evidence', {})
        if evidence:
            evidence = self.mutation_evidence(parent, mutations, evidence)
        sequence = ''.join(seq)
        constraints = mask(p.get('constraints', parent['constraints']), sequence)
        # Descendants may tighten, but cannot silently relax inherited hard constraints.
        if not set(parent['constraints']['fixed']) <= set(constraints['fixed']) or any(not set(v) <= set(constraints['excluded'].get(k, '')) for k, v in parent['constraints']['excluded'].items() if int(k) in constraints['mutable']):
            raise ValueError('A descendant cannot relax the parent hard constraints.')
        with self.s.db:
            value = self.insert(p['projectId'], p.get('name', parent['name']+' · variant'), sequence, constraints, copy.deepcopy(parent['reference']), parent['residueMap'], parent, 'explicit_substitution')
            value['changes'] = copy.deepcopy(mutations)
            value['backboneReference'] = parent.get('structure') or parent.get('backboneReference')
            value['purpose'] = text(p.get('purpose', 'Controlled sequence proposal'), 'purpose', 2000)
            value['mutationEvidence'] = evidence
            self.s.db.execute('UPDATE evolution_candidates SET data=? WHERE id=?', (canonical(value), value['id']))
            self.event(p['projectId'], value['id'], 'derive', {'parentId': parent['id'], 'mutations': mutations, 'rePredictionRequired': True})
        return value

    def mutation_evidence(self, parent, mutations, value):
        required = {'species', 'accession', 'isoform', 'nativePosition', 'wildType', 'mutant', 'assay', 'measurement', 'unit', 'direction', 'source', 'publication', 'context'}
        if not isinstance(value, dict) or set(value) != required or len(mutations) != 1:
            raise ValueError('Evidence requires one mapped mutation and all source, assay and context fields.')
        for key in required-{'nativePosition', 'measurement'}:
            text(value[key], key, 4000)
        if value['direction'] not in ('loss', 'gain', 'neutral') or type(value['measurement']) not in (float, int) or not math.isfinite(value['measurement']):
            raise ValueError('Use loss, gain or neutral and a finite experimental measurement.')
        m = mutations[0]; mapping = parent['residueMap'][m['position']-1]
        if any(value[k] != mapping.get(k) for k in ('species', 'accession', 'isoform')) or type(value['nativePosition']) is not int or value['nativePosition'] != mapping.get('referenceNumber') or value['wildType'] != mapping['wildType'] or value['wildType'] != m['from'] or value['mutant'] != m['to']:
            raise ValueError('Experimental mutation does not match the explicit species, accession, isoform and residue map.')
        return {**value, 'verification': 'user_supplied_not_independently_verified'}

    def evolution_decide(self, p):
        candidate=self.candidate(p['projectId'], p['candidateId'])
        if p.get('decision') not in ('retain', 'reject', 'revert'):
            raise ValueError('Choose retain, reject or revert.')
        if p['decision']=='revert' and not candidate['parentId']:
            raise ValueError('An original reference has no parent to revert to.')
        reason = text(p.get('reason'), 'decision reason', 4000)
        with self.s.db:
            return self.event(p['projectId'], p['candidateId'], 'decision', {'decision': p['decision'], 'reason': reason})

    def evolution_assess(self, p):
        candidate = self.candidate(p['projectId'], p['candidateId'])
        observation = p.get('observation')
        required = {'model', 'family', 'version', 'role', 'contextId', 'seed', 'metrics', 'artifactSha256', 'method', 'units'}
        if not isinstance(observation, dict) or set(observation) != required:
            raise ValueError('Supply model, family, version, role, contextId, seed, metrics, artifact checksum, method and units.')
        for key in ('model', 'family', 'version', 'contextId', 'method'):
            text(observation[key], key, 1000)
        if observation['role'] not in ('generation', 'optimization', 'refold', 'assessment'):
            raise ValueError('Unknown model role.')
        integer(observation['seed'], 'Seed', 0, 2147483647)
        if not re.fullmatch('[a-f0-9]{64}', str(observation['artifactSha256'])):
            raise ValueError('Record a SHA-256 for the original result artifact.')
        metrics = observation['metrics']; units = observation['units']
        if not isinstance(metrics, dict) or not 1 <= len(metrics) <= 100 or not isinstance(units, dict) or set(metrics) != set(units) or any(not isinstance(k, str) or not k or len(k) > 160 or type(v) not in (float, int) or not math.isfinite(v) or not isinstance(units[k], str) or not units[k] or len(units[k]) > 100 for k, v in metrics.items()):
            raise ValueError('Record finite raw scalar metrics with explicit units; no implicit score normalization.')
        with self.s.db:
            # Conditioning updates are immutable events; evaluate against all ancestors' recorded use.
            conditioned = self.conditioned(candidate)
            annotated = {**copy.deepcopy(observation), 'independence': independence(conditioned, observation), 'origin': 'user_supplied_result_not_verified_by_import'}
            return self.event(p['projectId'], candidate['id'], 'assessment', annotated)

    def conditioned(self, candidate):
        value = copy.deepcopy(candidate)
        node = candidate
        while node:
            for row in self.s.rows("SELECT data FROM evolution_events WHERE candidate_id=? AND kind='assessment'", (node['id'],)):
                item = json.loads(row['data'])
                if item['role'] in ('generation', 'optimization'):
                    value['provenance']['conditioning'].append({'model': item['model'], 'family': item['family']})
            node = self.candidate(candidate['projectId'], node['parentId']) if node['parentId'] else None
        return value

    def evolution_compare(self, p):
        parent = self.candidate(p['projectId'], p['parentId']); child = self.candidate(p['projectId'], p['candidateId'])
        if child['parentId'] != parent['id']:
            raise ValueError('Compare a direct parent and descendant.')
        def observations(id):
            return {r['id']: json.loads(r['data']) for r in self.s.rows("SELECT id,data FROM evolution_events WHERE candidate_id=? AND kind='assessment'", (id,))}
        a = observations(parent['id']).get(p.get('parentObservationId')); b = observations(child['id']).get(p.get('observationId'))
        if not a or not b or any(a[k] != b[k] for k in ('model', 'version', 'family', 'contextId', 'seed', 'method', 'units')) or a['metrics'].keys() != b['metrics'].keys():
            raise ValueError('Select matching result records with the same model, version, molecular context, seed, method and metric units.')
        delta = {k: b['metrics'][k]-v for k, v in a['metrics'].items()}
        if not all(math.isfinite(v) for v in delta.values()):
            raise ValueError('Metric difference overflow; verify source units and numeric range.')
        metric = p.get('metric'); higher = p.get('higherIsBetter')
        if metric not in delta or type(higher) is not bool:
            raise ValueError('Choose an observed metric and explicitly define its favourable direction.')
        effect = delta[metric]*(1 if higher else -1)
        direction = 'gain' if effect > 0 else 'loss' if effect < 0 else 'neutral'
        expected = child.get('mutationEvidence', {}).get('direction')
        return {'parentId': parent['id'], 'candidateId': child['id'], 'delta': delta, 'units': a['units'],
                'metric': metric, 'predictedDirection': direction, 'experimentalDirection': expected,
                'directionalAgreement': direction == expected if expected else None,
                'interpretation': 'Exact numerical sign for one matched pair; no calibrated neutral threshold, effect-size association or model certification.',
                'independence': independence(self.conditioned(child), b)}

    def evolution_manifest(self, p):
        ids = p.get('candidateIds')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 26 or len(set(ids)) != len(ids):
            raise ValueError('Choose 1–26 distinct candidate references.')
        candidates = [self.candidate(p['projectId'], id) for id in ids]
        minutes = integer(p.get('minutes', 60), 'Budget minutes', 30, 120)
        if minutes not in (30, 60, 120):
            raise ValueError('Choose a 30, 60 or 120 minute research budget.')
        strategy = p.get('strategy', 'evolution')
        if strategy not in ('sequence_seeded', 'evolution', 'counterfactual'):
            raise ValueError('This preparation supports sequence-seeded, evolution and counterfactual protocols. Other engine protocols need separate qualification.')
        target, _ = mi.Lab(self.s).record(p['structureId'])
        if target['project_id'] != p['projectId']:
            raise ValueError('Target belongs to another project.')
        seed = integer(p.get('seed', 42), 'Seed', 0, 2147483647)
        # A saved protocol is deliberately not submitted to an incompatible legacy run API.
        manifest = {'schemaVersion': 1, 'engine': 'BGMEE', 'strategy': strategy,
                    'target': {'recordId': target['id'], 'sha256': target['data']['sha256'], 'assembly': 'unverified'},
                    'references': [{'candidateId': c['id'], 'sequenceSha256': c['sequenceSha256'], 'constraints': c['constraints']} for c in candidates],
                    'budget': {'wallMinutes': minutes, 'currency': 'USD', 'approvedSpend': 0, 'heavyGpuConcurrency': 1},
                    'seed': seed, 'originalSequenceControls': ids, 'branches': ['proteinmpnn', 'solublempnn'],
                    'stoppingRules': ['budget_exhausted', 'no_supported_next_operation', 'all_candidates_fail_constraints'],
                    'state': 'prepared_not_executable', 'blockers': ['Sequence-seeded optimizer and dual-branch execution need qualification.', 'Independent structural validation must be configured.'],
                    'claim': 'A reproducible proposed protocol; no computation, external upload or paid operation started.'}
        id = str(uuid.uuid4()); manifest['sha256'] = sha(manifest)
        with self.s.db:
            self.s.db.execute('INSERT INTO evolution_manifests VALUES(?,?,?,?)', (id, p['projectId'], canonical(manifest), research.utc()))
        return {'id': id, **manifest}

    def evolution_manifests(self, p):
        return [{'id': row['id'], **json.loads(row['data'])} for row in self.s.rows('SELECT id,data FROM evolution_manifests WHERE project_id=? ORDER BY created DESC', (p['projectId'],))]


def dispatch(service, action, payload):
    service.project(payload['projectId'])
    return getattr(Evolution(service), action)(payload)
