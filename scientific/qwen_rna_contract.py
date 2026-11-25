"""Portable RNA contract, valid nested decoding and numerical scoring (no ML runtime)."""
import hashlib
import json
import math
import re

VERSION = '0.1.0'
MAX_LENGTH = 128


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def clean(sequence):
    if not isinstance(sequence, str):
        raise ValueError('Enter an RNA sequence.')
    sequence = re.sub(r'\s+', '', sequence).upper()
    if not 8 <= len(sequence) <= MAX_LENGTH or set(sequence) - set('ACGU'):
        raise ValueError('Use 8–128 RNA bases (A, C, G, U). Positions are preserved; DNA T and ambiguous bases are not silently converted.')
    return sequence


def pairs(structure):
    stack, result = [], []
    for i, c in enumerate(structure):
        if c == '(':
            stack.append(i)
        elif c == ')' and stack:
            result.append((stack.pop(), i))
        elif c != '.':
            raise ValueError('Use balanced, nested dot-bracket notation: (), .')
    if stack:
        raise ValueError('Unbalanced reference structure.')
    return sorted(result)


def decode(probabilities, threshold=.15):
    """Maximum-weight noncrossing matching; one partner/base, hairpin >=3 nt."""
    n = len(probabilities)
    dp = [[0.] * n for _ in range(n)]
    choice = {}
    for span in range(1, n):
        for i in range(n-span):
            j = i+span
            dp[i][j] = dp[i+1][j]
            for k in range(i+4, j+1):
                weight = probabilities[i][k] - threshold
                if weight <= 0:
                    continue
                score = weight + dp[i+1][k-1] + (dp[k+1][j] if k < j else 0)
                if score > dp[i][j]:
                    dp[i][j], choice[i, j] = score, k
    structure = ['.'] * n
    def trace(i, j):
        if i >= j:
            return
        k = choice.get((i, j))
        if k is None:
            trace(i+1, j)
        else:
            structure[i], structure[k] = '(', ')'
            trace(i+1, k-1)
            trace(k+1, j)
    trace(0, n-1)
    return ''.join(structure)


def accuracy(predicted, reference):
    a, b = set(pairs(predicted)), set(pairs(reference))
    tp = len(a & b)
    return {'f1': 2*tp/(len(a)+len(b)) if a or b else 1.,
            'precision': tp/len(a) if a else float(not b),
            'recall': tp/len(b) if b else float(not a),
            'truePositive': tp, 'predictedPairs': len(a), 'referencePairs': len(b),
            'missed': [[i+1, j+1] for i, j in sorted(b-a)],
            'extra': [[i+1, j+1] for i, j in sorted(a-b)]}


def result(sequence, matrix, threshold, provenance, reference=None):
    sequence = clean(sequence)
    n = len(sequence)
    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise ValueError('Pair matrix does not preserve sequence positions.')
    for i, row in enumerate(matrix):
        if any(not math.isfinite(p) or p < 0 or p > 1 for p in row) or sum(row) > 1.00001:
            raise ValueError('Invalid pair probabilities.')
        for j, p in enumerate(row):
            if abs(p-matrix[j][i]) > 1e-5 or (p > 1e-7 and (abs(i-j) <= 3 or sequence[i]+sequence[j] not in {'AU','UA','CG','GC','GU','UG'})):
                raise ValueError('Invalid or asymmetric RNA pair probability.')
    fold = decode(matrix, threshold)
    bases = []
    for i, row in enumerate(matrix):
        unpaired = max(0., 1-sum(row))
        entropy = -sum(p*math.log2(p) for p in [*row, unpaired] if p > 0)
        partner = next((j if i == a else a for a, j in pairs(fold) if i in (a, j)), None)
        bases.append({'position': i+1, 'base': sequence[i], 'partner': partner+1 if partner is not None else None,
                      'unpairedProbability': unpaired, 'entropyBits': entropy,
                      'confidence': row[partner] if partner is not None else unpaired})
    out = {'schema': 'fold.qwen-rna-result/1', 'sequence': sequence, 'length': n,
           'positionIndexing': '1-based, original sequence order', 'structure': fold,
           'basePairProbabilities': [[i+1, j+1, matrix[i][j]] for i in range(n) for j in range(i+1,n) if matrix[i][j] > 0],
           'bases': bases, 'regions': [{'start': i+1, 'end': min(i+10,n),
                                       'meanEntropyBits': sum(x['entropyBits'] for x in bases[i:i+10])/len(bases[i:i+10])}
                                      for i in range(0,n,10)],
           'uncertainty': {'kind': 'constrained categorical partner marginals', 'calibrated': False,
                           'note': 'Predictive entropy is not experimental error or a confidence interval. No thermodynamic ensemble is implied.'},
           'decoder': {'id': 'maximum-weight-noncrossing', 'version': VERSION, 'threshold': threshold, 'minimumHairpin': 3},
           'provenance': provenance, 'comparison': None}
    if reference:
        if len(reference) != n:
            raise ValueError('Reference must have one dot-bracket character per nucleotide.')
        pairs(reference)
        out['comparison'] = {'reference': reference, **accuracy(fold, reference)}
    out['sha256'] = digest(out)
    return out
