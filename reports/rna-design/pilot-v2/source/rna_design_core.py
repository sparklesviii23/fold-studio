"""Bounded inverse folding. All scores are computational predictions."""
import hashlib
import json
import math
import random
import sqlite3
import time
from pathlib import Path

VERSION = 'rna-design/1.0.0'
PAIR_TYPES = ('AU', 'UA', 'GC', 'CG', 'GU', 'UG')
IUPAC = dict(zip('ACGURYSWKMBDHVN', ('A', 'C', 'G', 'U', 'AG', 'CU', 'GC', 'AU', 'GU', 'AC', 'CGU', 'AGU', 'ACU', 'ACG', 'ACGU')))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def pairs(structure):
    stack, out = [], set()
    for i, c in enumerate(structure):
        if c == '(':
            stack.append(i)
        elif c == ')':
            if not stack:
                raise ValueError('Target has an unmatched closing bracket.')
            j = stack.pop()
            if i - j < 4:
                raise ValueError('Each hairpin needs at least 3 unpaired bases.')
            out.add((j, i))
        elif c != '.':
            raise ValueError('Use nested dot-bracket only. Pseudoknots and multiple strands are not supported.')
    if stack:
        raise ValueError('Target has an unmatched opening bracket.')
    return out


def validate(raw):
    target = ''.join(str(raw.get('target', '')).split())
    if not 8 <= len(target) <= 128:
        raise ValueError('Target length must be 8–128 nt.')
    target_pairs = pairs(target)
    mask = ''.join(str(raw.get('mask') or 'N' * len(target)).split()).upper()
    if len(mask) != len(target) or set(mask) - IUPAC.keys():
        raise ValueError('Sequence constraints need one RNA IUPAC symbol per target base.')
    locks = ''.join(str(raw.get('locks') or '.' * len(target)).split()).upper()
    if len(locks) != len(target) or set(locks) - set('.ACGU'):
        raise ValueError('Locked bases need one A, C, G, U or dot per target base.')
    allowed = [IUPAC[c] if lock == '.' else ''.join(b for b in IUPAC[c] if b == lock) for c, lock in zip(mask, locks)]
    if any(not a for a in allowed):
        raise ValueError('A locked base conflicts with the sequence constraints.')
    for i, j in target_pairs:
        if not any(a + b in PAIR_TYPES for a in allowed[i] for b in allowed[j]):
            raise ValueError(f'Constraints conflict with target pair {i + 1}–{j + 1}.')
    def number(key, default, low, high, integer=False):
        value = raw.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high or (integer and int(value) != value):
            raise ValueError(f'{key} must be between {low} and {high}.')
        return int(value) if integer else value
    out = {'target': target, 'mask': mask, 'locks': locks,
           'maxCandidates': number('maxCandidates', 128, 8, 4096, True),
           'maxSeconds': number('maxSeconds', 30, 1, 600),
           'wanted': number('wanted', 3, 1, 20, True), 'seed': number('seed', 1, 0, 2147483647, True),
           'gcMin': number('gcMin', 0, 0, 1), 'gcMax': number('gcMax', 1, 0, 1),
           'maxHomopolymer': number('maxHomopolymer', 128, 1, 128, True),
           'method': raw.get('method', 'solver')}
    if out['gcMin'] > out['gcMax']:
        raise ValueError('gcMin must not exceed gcMax.')
    if out['method'] not in ('solver', 'qwen', 'hybrid'):
        raise ValueError('Choose solver, qwen or hybrid.')
    min_gc = sum(all(b in 'GC' for b in a) for a in allowed) / len(target)
    max_gc = sum(any(b in 'GC' for b in a) for a in allowed) / len(target)
    if min_gc > out['gcMax'] or max_gc < out['gcMin']:
        raise ValueError('GC limits conflict with the sequence constraints.')
    for i, j in target_pairs:
        options = [p for p in PAIR_TYPES if p[0] in allowed[i] and p[1] in allowed[j]]
        min_gc += (min(sum(b in 'GC' for b in p) for p in options) - sum(all(b in 'GC' for b in allowed[k]) for k in (i,j))) / len(target)
        max_gc += (max(sum(b in 'GC' for b in p) for p in options) - sum(any(b in 'GC' for b in allowed[k]) for k in (i,j))) / len(target)
    if min_gc > out['gcMax'] + 1e-10 or max_gc < out['gcMin'] - 1e-10:
        raise ValueError('GC limits conflict with target pair constraints.')
    fixed = ''.join(a if len(a) == 1 else '.' for a in allowed)
    if any(b * (out['maxHomopolymer'] + 1) in fixed for b in 'ACGU'):
        raise ValueError('Locked bases conflict with the homopolymer limit.')
    return out


def domains(request):
    return [IUPAC[c] if lock == '.' else lock for c, lock in zip(request['mask'], request['locks'])]


def violations(sequence, request):
    if len(sequence) != len(request['target']) or set(sequence) - set('ACGU'):
        return ['Invalid RNA sequence.']
    errors = []
    if any(b not in a for b, a in zip(sequence, domains(request))):
        errors.append('Sequence violates a locked base or sequence mask.')
    if any(sequence[i] + sequence[j] not in PAIR_TYPES for i, j in pairs(request['target'])):
        errors.append('Sequence has an incompatible target pair.')
    gc = sum(b in 'GC' for b in sequence) / len(sequence)
    if not request['gcMin'] <= gc <= request['gcMax']:
        errors.append('GC fraction is outside the requested limits.')
    for base in 'ACGU':
        if base * (request['maxHomopolymer'] + 1) in sequence:
            errors.append('Sequence exceeds the homopolymer limit.')
            break
    return errors


def repair(sequence, request, rng):
    allowed = domains(request)
    seq = [b if b in a else rng.choice(a) for b, a in zip(sequence, allowed)]
    for i, j in sorted(pairs(request['target'])):
        options = [p for p in PAIR_TYPES if p[0] in allowed[i] and p[1] in allowed[j]]
        if seq[i] + seq[j] not in options:
            seq[i], seq[j] = rng.choice(options)
    return ''.join(seq)


class Cache:
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=20)
        self.db.execute('CREATE TABLE IF NOT EXISTS evaluations (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        self.hits = 0

    def get(self, key, calculate):
        row = self.db.execute('SELECT value FROM evaluations WHERE key=?', (key,)).fetchone()
        if row:
            self.hits += 1
            return json.loads(row[0]), False
        value = calculate()
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO evaluations VALUES (?,?)', (key, json.dumps(value)))
        return value, True


class Scorer:
    def __init__(self, cache):
        import RNA
        self.RNA, self.cache = RNA, cache
        RNA.params_load_RNA_Turner2004()
        self.version = {'engine': 'ViennaRNA', 'version': RNA.__version__, 'temperatureC': 37, 'dangles': 2, 'parameters': 'Turner2004', 'noLP': False}
        self.evaluations = 0
        self.secondary_evaluations = 0

    def score(self, sequence, target):
        def calculate():
            md = self.RNA.md()
            md.temperature, md.dangles = 37, 2
            fc = self.RNA.fold_compound(sequence, md)
            structure, energy = fc.mfe()
            fc.exp_params_rescale(energy)
            _, ensemble = fc.pf()
            target_energy = fc.eval_structure(target)
            probability = min(1., math.exp(min(0., (ensemble - target_energy) / (0.00198720425864083 * 310.15))))
            defect = fc.ensemble_defect(target)
            return {'structure': structure, 'mfeKcalMol': energy, 'targetKcalMol': target_energy,
                    'targetGapKcalMol': target_energy - energy, 'targetProbability': probability, 'ensembleDefect': defect}
        value, fresh = self.cache.get(digest({'sequence': sequence, 'target': target, **self.version}), calculate)
        self.evaluations += int(fresh)
        return value

    def second(self, sequence):
        from rna_lab_fold import Builtin, to_dotbracket
        def calculate():
            model = Builtin(sequence)
            return {'structure': to_dotbracket(model.mfe_pairs, len(sequence)), 'mfeKcalMol': model.mfe_energy,
                    'engine': 'RNA Lab reduced Turner nearest-neighbour', 'version': 'rna-lab.fold/1.0.0', 'temperatureC': 37}
        source_sha = hashlib.sha256(Path(__file__).with_name('rna_lab_fold.py').read_bytes()).hexdigest()
        value, fresh = self.cache.get(digest({'sequence': sequence, 'engine': 'rna-lab.fold/1.0.0', 'sourceSha256': source_sha, 'temperatureC': 37}), calculate)
        value['sourceSha256'] = source_sha
        self.secondary_evaluations += int(fresh)
        return value


def candidate(sequence, target, score, source, request):
    tp, pp = pairs(target), pairs(score['structure'])
    missed, extra = sorted(tp - pp), sorted(pp - tp)
    errors = violations(sequence, request)
    if missed:
        errors.append(f'{len(missed)} target pairs are missing.')
    if extra:
        errors.append(f'{len(extra)} extra pairs are predicted.')
    f1 = 2 * len(tp & pp) / (len(tp) + len(pp)) if tp or pp else 1.
    return {'id': digest(sequence)[:16], 'sequence': sequence, **score, 'pairF1': f1,
            'missedPairs': [[i + 1, j + 1] for i, j in missed], 'extraPairs': [[i + 1, j + 1] for i, j in extra],
            'source': source, 'qualifies': not errors, 'failureReasons': errors, 'constraintViolations': violations(sequence, request)}


def rank(c):
    return (not c['qualifies'], len(c['constraintViolations']), -c['pairF1'], c['ensembleDefect'], -c['targetProbability'], c['sequence'])


def search(request, folder, cache_path=None, proposals=None, on_batch=None, stop=None):
    """Save each evaluated candidate before the next solver call."""
    request = validate(request)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    immutable = {k: v for k, v in request.items() if k not in ('maxCandidates', 'maxSeconds', 'wanted')}
    seal = digest({'request': immutable, 'version': VERSION})
    state_path = folder / 'state.json'
    state = json.loads(state_path.read_text()) if state_path.is_file() else {
        'inputSeal': seal, 'candidates': [], 'seen': [], 'attempts': 0, 'solverCalls': 0,
        'elapsedSeconds': 0., 'firstSuccessSeconds': None, 'evaluations': 0, 'secondaryEvaluations': 0, 'batches': 0, 'constraintRejections': 0}
    if state['inputSeal'] != seal:
        raise ValueError('Resume inputs or solver version changed. Start a new run.')
    source_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if state.get('sourceSha256') and state['sourceSha256'] != source_sha:
        raise ValueError('Solver source changed. Start a new run and keep the prior result.')
    state['sourceSha256'] = source_sha
    cache = Cache(cache_path or folder / 'evaluations.sqlite')
    scorer = Scorer(cache)
    if state.get('scorer') and state['scorer'] != scorer.version:
        raise ValueError('Scoring engine changed. Start a new run.')
    start = time.monotonic()
    previous_elapsed = state['elapsedSeconds']
    rows, seen = state['candidates'], set(state['seen'])
    RNA = scorer.RNA
    target = request['target']
    base_evals, base_second = state['evaluations'], state['secondaryEvaluations']
    def snapshot(reason):
        rows.sort(key=rank)
        state.update(candidates=rows, seen=sorted(seen), elapsedSeconds=previous_elapsed + time.monotonic() - start,
                     evaluations=base_evals + scorer.evaluations, secondaryEvaluations=base_second + scorer.secondary_evaluations,
                     scorer=scorer.version, stopReason=reason)
        atomic(state_path, state)
        out = {'schema': 'fold.rna-design-result/1', 'version': VERSION, 'request': request,
               'candidates': rows, 'metrics': {k: state[k] for k in ('attempts', 'solverCalls', 'evaluations', 'secondaryEvaluations', 'batches', 'elapsedSeconds', 'firstSuccessSeconds', 'stopReason')},
               'qualifyingCount': sum(c['qualifies'] for c in rows), 'scorer': scorer.version, 'constraintRejections': state.get('constraintRejections', 0),
               'evidence': 'Computational prediction. Solver labels are not experimental measurements.',
               'inputSeal': seal, 'sourceSha256': source_sha, 'proposalModel': getattr(proposals, 'provenance', None), 'cacheHitsThisSession': cache.hits,
               'solverAccounting': 'solverCalls counts RNA.inverse_fold calls. Its internal energy evaluations are not exposed. Explicit final scoring and independent checks are counted separately.'}
        out['sha256'] = digest(out)
        atomic(folder / 'result.json', out)
        if on_batch:
            on_batch(out)
        return out
    try:
        while len(seen) < request['maxCandidates'] and state['attempts'] < request['maxCandidates'] * 12:
            if stop and stop():
                return snapshot('cancelled')
            if previous_elapsed + time.monotonic() - start >= request['maxSeconds']:
                return snapshot('time_limit')
            if sum(c['qualifies'] for c in rows) >= request['wanted']:
                return snapshot('enough_candidates')
            index = state['attempts']
            rng = random.Random(request['seed'] + index * 104729)
            state['attempts'] += 1
            sequence = repair(''.join(rng.choice('ACGU') for _ in target), request, rng)
            source = 'solver'
            if request['method'] in ('qwen', 'hybrid'):
                if not proposals:
                    raise ValueError('The inverse Qwen checkpoint is not available. Select Solver.')
                sequence = repair(proposals(index, rng), request, rng)
                source = 'qwen proposal with constraint repair'
            elif rows and index % 3 != 0:
                parent = rng.choice(sorted(rows, key=rank)[:5])
                seq = list(parent['sequence'])
                focus = sorted({i - 1 for p in parent['missedPairs'] + parent['extraPairs'] for i in p})
                for i in rng.sample(focus or list(range(len(target))), min(len(focus) or len(target), 1 + index % 4)):
                    seq[i] = rng.choice('ACGU')
                sequence = repair(''.join(seq), request, rng)
                source = 'solver pair-error repair'
            if request['method'] != 'qwen':
                RNA.init_rand((request['seed'] + index) % 2147483647 or 1)
                # Lowercase bases remain fixed in ViennaRNA inverse folding.
                initial = ''.join(b.lower() if len(a) == 1 else b for b, a in zip(sequence, domains(request)))
                state['solverCalls'] += 1
                sequence, _ = RNA.inverse_fold(initial, target)
                sequence = repair(sequence.upper(), request, rng)
                if request['method'] == 'hybrid':
                    source = 'qwen proposal plus ViennaRNA inverse folding'
            if sequence in seen:
                snapshot('searching')
                continue
            seen.add(sequence)
            if violations(sequence, request):
                state['constraintRejections'] = state.get('constraintRejections', 0) + 1
                snapshot('searching')
                continue
            value = scorer.score(sequence, target)
            row = candidate(sequence, target, value, source, request)
            rows.append(row)
            if row['qualifies'] and state['firstSuccessSeconds'] is None:
                state['firstSuccessSeconds'] = previous_elapsed + time.monotonic() - start
            state['batches'] += 1
            snapshot('searching')
            if row['qualifies'] or len(seen) % 8 == 0:
                for best in sorted(rows, key=rank)[:max(3, request['wanted'])]:
                    if 'independent' not in best:
                        if previous_elapsed + time.monotonic() - start >= request['maxSeconds'] or (stop and stop()):
                            break
                        independent = scorer.second(best['sequence'])
                        independent['agreesWithTarget'] = independent['structure'] == target
                        independent['disagreementPairs'] = [[i + 1, j + 1] for i, j in sorted(pairs(independent['structure']) ^ pairs(best['structure']))]
                        best['independent'] = independent
                snapshot('searching')
        return snapshot('candidate_limit' if len(seen) >= request['maxCandidates'] else 'attempt_limit')
    finally:
        cache.db.close()
