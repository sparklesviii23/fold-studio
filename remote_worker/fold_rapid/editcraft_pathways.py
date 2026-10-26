"""Explicit-background gene-set over-representation; production is cloud-only.

No implicit whole-genome background, identifier mapping, downloaded collection,
pathway activation score, or causal/therapeutic conclusion is supplied.
"""
import hashlib
import json
import math
import os
import pathlib
import re

VERSION = '1.0.0'


def identifiers(value, maximum, name):
    if not isinstance(value, list) or not 1 <= len(value) <= maximum:
        raise ValueError(name + ' must be an explicit bounded identifier list.')
    if any(not isinstance(g, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:|+\-]{0,199}', g) for g in value):
        raise ValueError(name + ' contains an unsupported identifier; no aliases or case changes are inferred.')
    if len(set(value)) != len(value):
        raise ValueError(name + ' contains duplicates; resolve scientific identities explicitly.')
    return set(value)


def validate_input(p):
    if not isinstance(p, dict):
        raise ValueError('Supply an explicit pathway-analysis input.')
    universe = identifiers(p.get('background'), 50000, 'Measured/testable background')
    selected = identifiers(p.get('genes'), 5000, 'Selected genes')
    if len(universe) < 2 or not selected <= universe:
        raise ValueError('Every selected gene must belong to the declared measured/testable background.')
    collection = p.get('collection')
    required = ('name', 'version', 'source', 'organism', 'identifierNamespace', 'license')
    if not isinstance(collection, dict) or any(not isinstance(collection.get(k), str) or not 0 < len(collection[k].strip()) <= 1000 for k in required):
        raise ValueError('Record collection name, version, source, organism, exact identifier namespace and licensing attribution.')
    sets = p.get('geneSets')
    if not isinstance(sets, list) or not 1 <= len(sets) <= 1000:
        raise ValueError('Supply 1–1,000 explicit, attributed gene sets.')
    names = set()
    total = 0
    for group in sets:
        if not isinstance(group, dict) or not isinstance(group.get('id'), str) or not 0 < len(group['id']) <= 200 or group['id'] in names:
            raise ValueError('Gene-set identities must be unique and nonempty.')
        names.add(group['id'])
        members = identifiers(group.get('genes'), 10000, 'Gene-set members')
        total += len(members)
    if total > 200000 or len(json.dumps(p, allow_nan=False).encode()) > 3 * 1024**2:
        raise ValueError('Collection exceeds this reviewed bounded analysis profile.')
    if p.get('multipleTesting') not in ('BH', 'BY'):
        raise ValueError('Choose explicit BH or BY multiple-testing adjustment.')
    alpha = p.get('alpha')
    if type(alpha) not in (int, float) or not math.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError('Choose a finite significance threshold strictly between zero and one.')
    return p


def log_upper_tail(population, members, draws, overlap):
    """log P[X >= overlap], using the exact hypergeometric support and recurrence."""
    if any(type(n) is not int for n in (population, members, draws, overlap)) or not 0 <= members <= population or not 0 <= draws <= population or population < 1 or overlap < 0:
        raise ValueError('Invalid hypergeometric dimensions.')
    low, high = max(0, draws - population + members), min(members, draws)
    if overlap <= low:
        return 0.0
    if overlap > high:
        return -math.inf
    def log_choose(n, k):
        return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    current = log_choose(members, overlap) + log_choose(population - members, draws - overlap) - log_choose(population, draws)
    terms = [current]
    for k in range(overlap, high):
        current += math.log(members-k) + math.log(draws-k) - math.log(k+1) - math.log(population-members-draws+k+1)
        terms.append(current)
    largest = max(terms)
    return min(0.0, largest + math.log(math.fsum(math.exp(t-largest) for t in terms)))


def adjusted_logs(log_p, method):
    """Stable BH/BY across the entire supplied family, retaining non-significant sets."""
    count = len(log_p)
    if not count or method not in ('BH', 'BY') or any(math.isnan(p) or p > 0 for p in log_p):
        raise ValueError('Invalid multiple-testing family.')
    factor = math.fsum(1/i for i in range(1, count+1)) if method == 'BY' else 1.0
    order = sorted(range(count), key=lambda i: log_p[i])
    result = [0.0] * count
    running = 0.0
    for rank in range(count, 0, -1):
        i = order[rank-1]
        running = min(running, log_p[i] + math.log(count * factor / rank))
        result[i] = running
    return result


def calculate(p):
    """Pure arithmetic for offline numerical reference tests; not a local research runner."""
    validate_input(p)
    background, selected = set(p['background']), set(p['genes'])
    population, draws = len(background), len(selected)
    rows, logs = [], []
    for group in p['geneSets']:
        original = set(group['genes'])
        eligible = original & background
        overlap = sorted(selected & eligible)
        log_p = log_upper_tail(population, len(eligible), draws, len(overlap))
        logs.append(log_p)
        expected = draws * len(eligible) / population
        rows.append({'id': group['id'], 'originalMembers': len(original), 'testableMembers': len(eligible), 'outsideBackground': sorted(original-background), 'overlapGenes': overlap, 'overlapCount': len(overlap), 'expectedOverlap': expected, 'foldEnrichment': len(overlap)/expected if expected else None, 'logPValue': log_p, 'pValue': math.exp(log_p), 'minusLog10P': -log_p/math.log(10), 'noTestableMembers': not eligible})
    for row, log_q in zip(rows, adjusted_logs(logs, p['multipleTesting'])):
        row.update(logAdjustedPValue=log_q, adjustedPValue=math.exp(log_q), minusLog10AdjustedP=-log_q/math.log(10), passesDeclaredThreshold=log_q<=math.log(p['alpha']), pValueUnderflow=row['pValue']==0, adjustedPValueUnderflow=math.exp(log_q)==0)
    rows.sort(key=lambda r: (r['logAdjustedPValue'], r['logPValue'], r['id']))
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    return {'method': 'One-sided hypergeometric over-representation', 'rows': rows, 'selectedGenes': sorted(selected), 'backgroundCount': population, 'selectedCount': draws, 'testedFamilySize': len(rows), 'multipleTesting': p['multipleTesting'], 'alpha': p['alpha'], 'collection': p['collection'], 'collectionVerification': 'Explicitly supplied attribution; no external collection/source verification or identifier mapping performed.', 'backgroundSha256': hashlib.sha256(canonical(sorted(background))).hexdigest(), 'collectionSha256': hashlib.sha256(canonical(p['geneSets'])).hexdigest(), 'inputSha256': hashlib.sha256(canonical(p)).hexdigest(), 'sourceSha256': hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(), 'version': VERSION, 'scope': 'Gene-set membership enrichment conditional on the supplied measured/testable background and selected list. BH assumes independence or suitable positive dependence; BY is conservative under arbitrary dependence. Correlated pathways are not independent replication. Post-clustering marker selection is exploratory. These values do not measure pathway activation, direction, causal mechanism, therapeutic efficacy or validated cell types. No biological collection, universe or annotation was invented.'}


def execute(p):
    if os.environ.get('FOLD_ENGINE_ROLE') != 'editcraft_cloud':
        raise RuntimeError('Production pathway analysis is cloud-only; local arithmetic is restricted to offline numerical reference checks.')
    return calculate(p)
