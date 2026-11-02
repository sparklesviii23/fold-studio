"""RNA secondary-structure thermodynamics for the RNA-to-Protein Laboratory (Demo 3).

Two backends share one result shape:

* ``viennarna`` — the ViennaRNA Python module (Lorenz et al. 2011, doi:10.1186/1748-7188-6-26),
  used automatically whenever ``import RNA`` succeeds in the running interpreter.
* ``builtin-nn`` — a dependency-free implementation of the Zuker MFE and McCaskill
  partition-function recursions (Zuker & Stiegler 1981, doi:10.1093/nar/9.1.133;
  McCaskill 1990, doi:10.1002/bip.360290621) with stochastic backtracking
  (Ding & Lawrence 2003, doi:10.1093/nar/gkg938). Its energy model is a stated subset of the
  Turner 1999 nearest-neighbour parameters (Mathews et al. 1999, doi:10.1006/jmbi.1999.2700):
  Watson–Crick/GU stacking, hairpin/bulge/interior initiation, Ninio asymmetry, terminal AU/GU
  penalty and a linear multiloop. Terminal mismatches, dangling ends, special hairpins,
  1x1/1x2/2x2 loop tables and coaxial stacking are omitted, and only 37 °C is supported.

Every output is a statistical-thermodynamic prediction for an isolated RNA in standard
buffer conditions — never an observed in-cell structure.
"""
import math, random

KT = 1.98717e-3 * 310.15           # kcal/mol at 37 °C (gas constant as in ViennaRNA)
MAXLOOP = 30
MIN_HAIRPIN = 3
MAX_BUILTIN = 160                  # O(N^3) pure Python: keep interactive
PAIRS = {'CG': 0, 'GC': 1, 'GU': 2, 'UG': 3, 'AU': 4, 'UA': 5}

# Turner 1999 parameters in dcal/mol (as distributed in ViennaRNA's rna_turner1999.par; every table below was
# cross-checked against ViennaRNA 2.7.2's loaded Turner-1999 set — see tests/test_rna_lab.py).
# STACK[t1][t2]: t1 = type of the outer pair (i,j), t2 = type of the inner pair read reversed (l,k).
STACK = [[-240, -330, -210, -140, -210, -210],
         [-330, -340, -250, -150, -220, -240],
         [-210, -250, 130, -50, -140, -130],
         [-140, -150, -50, 30, -60, -100],
         [-210, -220, -140, -60, -110, -90],
         [-210, -240, -130, -100, -90, -130]]
INF = 10 ** 7
HAIRPIN = [INF, INF, INF, 570, 560, 560, 540, 590, 560, 640, 650, 660, 670, 678, 686, 694, 701, 707, 713, 719, 725, 730, 735, 740, 744, 749, 753, 757, 761, 765, 769]
BULGE = [INF, 380, 280, 320, 360, 400, 440, 459, 470, 480, 490, 500, 510, 519, 527, 534, 541, 548, 554, 560, 565, 571, 576, 580, 585, 589, 594, 598, 602, 605, 609]
INTERIOR = [INF, INF, 410, 510, 170, 180, 200, 220, 230, 240, 250, 260, 270, 278, 286, 294, 301, 307, 313, 319, 325, 330, 335, 340, 345, 349, 353, 357, 361, 365, 369]
LXC = 107.856                      # loop-length extrapolation, dcal/mol
NINIO, NINIO_MAX = 50, 300
TERM_AU = 50
ML_A, ML_B, ML_C = 340, 0, 40      # closing, per unpaired base, per branch

MODEL = {
    'name': 'builtin-nn', 'title': 'Built-in nearest-neighbour model (Turner 1999 subset)',
    'parameters': 'Turner 1999 (Mathews et al. 1999, doi:10.1006/jmbi.1999.2700) stacking and loop-initiation tables, 37 °C',
    'included': ['Watson–Crick and GU stacking', 'hairpin, bulge and interior loop initiation with log extrapolation beyond 30 nt',
                 'Ninio asymmetry (0.5 kcal/mol per nt, max 3.0)', 'terminal AU/GU penalty (0.5 kcal/mol per helix end)',
                 'linear multiloop a = 3.4, b = 0, c = 0.4 kcal/mol'],
    'omitted': ['terminal mismatches and dangling ends', 'special hairpin loops (tetraloops, triloops, all-C)', '1x1, 1x2 and 2x2 interior-loop tables',
                'coaxial stacking', 'temperature and salt dependence', 'modified nucleotides', 'pseudoknots and tertiary interactions'],
    'citations': ['doi:10.1093/nar/9.1.133', 'doi:10.1002/bip.360290621', 'doi:10.1093/nar/gkg938', 'doi:10.1006/jmbi.1999.2700'],
}


def _loop_table(table, n):
    return table[n] if n <= 30 else table[30] + int(round(LXC * math.log(n / 30.0)))


def _au(t):
    return TERM_AU if t > 1 else 0


def clean(seq):
    s = ''.join(str(seq).upper().split()).replace('T', 'U')
    bad = sorted(set(s) - set('ACGU'))
    if not s: raise ValueError('Enter an RNA sequence.')
    if bad: raise ValueError('Only A, C, G and U (or T) are accepted; found ' + ', '.join(bad) + '.')
    return s


class Model:
    """Loop energies (dcal/mol) for one sequence under the built-in parameter subset."""

    def __init__(self, seq):
        self.s = seq; self.n = len(seq)
        n = self.n
        self.t = [[PAIRS.get(seq[i] + seq[j], -1) if j - i > MIN_HAIRPIN else -1 for j in range(n)] for i in range(n)]

    def hairpin(self, i, j):
        return _loop_table(HAIRPIN, j - i - 1) + _au(self.t[i][j])

    def interior(self, i, j, k, l):
        t1 = self.t[i][j]; t2 = PAIRS[self.s[l] + self.s[k]]
        u1, u2 = k - i - 1, j - l - 1
        if u1 == 0 and u2 == 0: return STACK[t1][t2]
        if u1 == 0 or u2 == 0:
            u = u1 + u2
            return _loop_table(BULGE, u) + (STACK[t1][t2] if u == 1 else _au(t1) + _au(t2))
        return _loop_table(INTERIOR, u1 + u2) + min(NINIO_MAX, NINIO * abs(u1 - u2)) + _au(t1) + _au(t2)

    def ml_closing(self, i, j):
        return ML_A + ML_C + _au(self.t[i][j])

    def ml_stem(self, i, j):
        return ML_C + _au(self.t[i][j])

    def ext_stem(self, i, j):
        return _au(self.t[i][j])


def pair_table(structure):
    stack, pt = [], [-1] * len(structure)
    for i, c in enumerate(structure):
        if c == '(': stack.append(i)
        elif c == ')':
            if not stack: raise ValueError('Unbalanced dot-bracket structure.')
            j = stack.pop(); pt[i] = j; pt[j] = i
        elif c != '.': raise ValueError('Only "(", ")" and "." are accepted in dot-bracket notation.')
    if stack: raise ValueError('Unbalanced dot-bracket structure.')
    return pt


def pairs_of(structure):
    pt = pair_table(structure)
    return {(i, j) for i, j in enumerate(pt) if j > i}


def to_dotbracket(pairs, n):
    out = ['.'] * n
    for i, j in pairs: out[i] = '('; out[j] = ')'
    return ''.join(out)


def evaluate(seq, structure):
    """Free energy (kcal/mol) of one structure by explicit loop decomposition — independent of the DP."""
    m = Model(seq); pt = pair_table(structure)
    if len(structure) != m.n: raise ValueError('Structure and sequence lengths differ.')
    for i, j in enumerate(pt):
        if j > i and (j - i <= MIN_HAIRPIN or m.s[i] + m.s[j] not in PAIRS):
            raise ValueError(f'Pair {i + 1}-{j + 1} ({m.s[i]}-{m.s[j]}) is not an allowed canonical pair with a ≥3-nt hairpin.')

    def inside(i, j):
        branches, k = [], i + 1
        while k < j:
            if pt[k] > k: branches.append((k, pt[k])); k = pt[k] + 1
            else: k += 1
        return branches

    e, k = 0, 0
    while k < m.n:
        if pt[k] > k: e += m.ext_stem(k, pt[k]); k = pt[k] + 1
        else: k += 1
    for i, j in enumerate(pt):
        if j <= i: continue
        br = inside(i, j)
        if not br: e += m.hairpin(i, j)
        elif len(br) == 1:
            k, l = br[0]
            e += m.interior(i, j, k, l)
        else:
            e += m.ml_closing(i, j) + sum(m.ml_stem(k, l) for k, l in br) + ML_B * ((j - i - 1) - sum(l - k + 1 for k, l in br))
    return e / 100.0


class Builtin:
    """Zuker MFE + McCaskill partition function, outside probabilities and stochastic sampling."""

    def __init__(self, seq):
        self.m = m = Model(seq); self.n = n = m.n
        if n > MAX_BUILTIN: raise ValueError(f'The built-in engine is limited to {MAX_BUILTIN} nt (pure Python, O(N³)). Install ViennaRNA for longer RNAs.')
        self._mfe(); self._pf()

    # ---- minimum free energy ----
    def _mfe(self):
        m, n = self.m, self.n
        V = [[INF] * n for _ in range(n)]; WM = [[INF] * n for _ in range(n)]; WM1 = [[INF] * n for _ in range(n)]
        for d in range(MIN_HAIRPIN + 1, n):
            for i in range(0, n - d):
                j = i + d
                if m.t[i][j] >= 0:
                    best = m.hairpin(i, j)
                    for k in range(i + 1, min(i + MAXLOOP + 2, j - MIN_HAIRPIN - 1)):
                        u1 = k - i - 1
                        for l in range(j - 1, max(k + MIN_HAIRPIN, j - 2 - MAXLOOP + u1), -1):
                            if m.t[k][l] >= 0 and V[k][l] < INF:
                                e = m.interior(i, j, k, l) + V[k][l]
                                if e < best: best = e
                    mc = m.ml_closing(i, j)
                    for u in range(i + 2, j - 1):
                        if WM[i + 1][u - 1] < INF and WM1[u][j - 1] < INF:
                            e = mc + WM[i + 1][u - 1] + WM1[u][j - 1]
                            if e < best: best = e
                    V[i][j] = best
            for i in range(0, n - d):
                j = i + d
                b1 = INF
                for l in range(i + MIN_HAIRPIN + 1, j + 1):
                    if V[i][l] < INF:
                        e = V[i][l] + m.ml_stem(i, l) + ML_B * (j - l)
                        if e < b1: b1 = e
                WM1[i][j] = b1
                b = INF
                for u in range(i, j - MIN_HAIRPIN):
                    if WM1[u][j] >= INF: continue
                    e = ML_B * (u - i) + WM1[u][j]
                    if e < b: b = e
                    if u > i and WM[i][u - 1] < INF:
                        e = WM[i][u - 1] + WM1[u][j]
                        if e < b: b = e
                WM[i][j] = b
        F = [0] * (n + 1)                 # F[j] = MFE of prefix [0, j)
        for j in range(1, n + 1):
            best = F[j - 1]
            for k in range(0, j - MIN_HAIRPIN - 1):
                if V[k][j - 1] < INF:
                    e = F[k] + V[k][j - 1] + m.ext_stem(k, j - 1)
                    if e < best: best = e
            F[j] = best
        self.V, self.WM, self.WM1, self.F = V, WM, WM1, F
        self.mfe_energy = F[n] / 100.0
        self.mfe_pairs = self._mfe_backtrack()

    def _mfe_backtrack(self):
        m, n, V, WM, WM1, F = self.m, self.n, self.V, self.WM, self.WM1, self.F
        pairs, todo = set(), [('F', 0, n)]
        while todo:
            kind, i, j = todo.pop()
            if kind == 'F':
                if j == 0: continue
                if F[j] == F[j - 1]: todo.append(('F', 0, j - 1)); continue
                for k in range(0, j - MIN_HAIRPIN - 1):
                    if V[k][j - 1] < INF and F[k] + V[k][j - 1] + m.ext_stem(k, j - 1) == F[j]:
                        todo += [('F', 0, k), ('V', k, j - 1)]; break
            elif kind == 'V':
                pairs.add((i, j)); target = V[i][j]
                if m.hairpin(i, j) == target: continue
                found = False
                for k in range(i + 1, min(i + MAXLOOP + 2, j - MIN_HAIRPIN - 1)):
                    u1 = k - i - 1
                    for l in range(j - 1, max(k + MIN_HAIRPIN, j - 2 - MAXLOOP + u1), -1):
                        if m.t[k][l] >= 0 and V[k][l] < INF and m.interior(i, j, k, l) + V[k][l] == target:
                            todo.append(('V', k, l)); found = True; break
                    if found: break
                if found: continue
                mc = m.ml_closing(i, j)
                for u in range(i + 2, j - 1):
                    if WM[i + 1][u - 1] < INF and WM1[u][j - 1] < INF and mc + WM[i + 1][u - 1] + WM1[u][j - 1] == target:
                        todo += [('WM', i + 1, u - 1), ('WM1', u, j - 1)]; break
            elif kind == 'WM1':
                for l in range(i + MIN_HAIRPIN + 1, j + 1):
                    if V[i][l] < INF and V[i][l] + m.ml_stem(i, l) + ML_B * (j - l) == WM1[i][j]:
                        todo.append(('V', i, l)); break
            elif kind == 'WM':
                for u in range(i, j - MIN_HAIRPIN):
                    if WM1[u][j] >= INF: continue
                    if ML_B * (u - i) + WM1[u][j] == WM[i][j]: todo.append(('WM1', u, j)); break
                    if u > i and WM[i][u - 1] < INF and WM[i][u - 1] + WM1[u][j] == WM[i][j]:
                        todo += [('WM', i, u - 1), ('WM1', u, j)]; break
        return pairs

    # ---- partition function ----
    def _pf(self):
        m, n = self.m, self.n
        B = lambda e: math.exp(-e / (100.0 * KT))
        eb = B(ML_B)
        self.ebp = ebp = [eb ** k for k in range(n + 2)]
        Qb = [[0.0] * n for _ in range(n)]; Qm = [[0.0] * n for _ in range(n)]; Qm1 = [[0.0] * n for _ in range(n)]
        for d in range(MIN_HAIRPIN + 1, n):
            for i in range(0, n - d):
                j = i + d
                if m.t[i][j] >= 0:
                    q = B(m.hairpin(i, j))
                    for k in range(i + 1, min(i + MAXLOOP + 2, j - MIN_HAIRPIN - 1)):
                        u1 = k - i - 1
                        for l in range(j - 1, max(k + MIN_HAIRPIN, j - 2 - MAXLOOP + u1), -1):
                            if Qb[k][l] > 0: q += B(m.interior(i, j, k, l)) * Qb[k][l]
                    mc = B(m.ml_closing(i, j)); s = 0.0
                    for u in range(i + 2, j - 1): s += Qm[i + 1][u - 1] * Qm1[u][j - 1]
                    Qb[i][j] = q + mc * s
            for i in range(0, n - d):
                j = i + d
                s = 0.0
                for l in range(i + MIN_HAIRPIN + 1, j + 1):
                    if Qb[i][l] > 0: s += Qb[i][l] * B(m.ml_stem(i, l)) * ebp[j - l]
                Qm1[i][j] = s
                s = 0.0
                for u in range(i, j - MIN_HAIRPIN):
                    if Qm1[u][j] > 0: s += (ebp[u - i] + (Qm[i][u - 1] if u > i else 0.0)) * Qm1[u][j]
                Qm[i][j] = s
        Q5 = [1.0] * (n + 1)              # Q5[j]: prefix [0, j)
        for j in range(1, n + 1):
            s = Q5[j - 1]
            for k in range(0, j - MIN_HAIRPIN - 1):
                if Qb[k][j - 1] > 0: s += Q5[k] * Qb[k][j - 1] * B(m.ext_stem(k, j - 1))
            Q5[j] = s
        Q3 = [1.0] * (n + 1)              # Q3[i]: suffix [i, n)
        for i in range(n - 1, -1, -1):
            s = Q3[i + 1]
            for l in range(i + MIN_HAIRPIN + 1, n):
                if Qb[i][l] > 0: s += Qb[i][l] * B(m.ext_stem(i, l)) * Q3[l + 1]
            Q3[i] = s
        self.Qb, self.Qm, self.Qm1, self.Q5, self.Q3, self.B = Qb, Qm, Qm1, Q5, Q3, B
        self.Z = Q5[n]
        self.ensemble_energy = -KT * math.log(self.Z)
        self.P = self._outside()

    def _outside(self):
        m, n, Qb, Qm, Q5, Q3, B, ebp, Z = self.m, self.n, self.Qb, self.Qm, self.Q5, self.Q3, self.B, self.ebp, self.Z
        P = [[0.0] * n for _ in range(n)]
        A = [[0.0] * n for _ in range(n)]   # A[i][q] = Σ_{p<i} W(p,q)·b^(i-p-1)
        C = [[0.0] * n for _ in range(n)]   # C[i][q] = Σ_{p<i} W(p,q)·Qm[p+1][i-1]
        for d in range(n - 1, MIN_HAIRPIN, -1):
            for i in range(0, n - d):
                j = i + d
                if Qb[i][j] == 0: continue
                p_ij = Q5[i] * Qb[i][j] * B(m.ext_stem(i, j)) * Q3[j + 1] / Z
                for p in range(i - 1, max(-1, i - MAXLOOP - 2), -1):
                    u1 = i - p - 1
                    for q in range(j + 1, min(n, j + MAXLOOP + 2 - u1)):
                        if P[p][q] > 0: p_ij += P[p][q] / Qb[p][q] * B(m.interior(p, q, i, j)) * Qb[i][j]
                s = 0.0
                for q in range(j + 1, n):
                    if A[i][q] == 0 and C[i][q] == 0: continue
                    right = Qm[j + 1][q - 1] if q - 1 > j else 0.0
                    s += A[i][q] * right + C[i][q] * (ebp[q - j - 1] + right)
                p_ij += Qb[i][j] * B(m.ml_stem(i, j)) * s
                P[i][j] = p_ij
                if p_ij > 0:
                    w = p_ij / Qb[i][j] * B(m.ml_closing(i, j))
                    for k in range(i + 1, j):
                        A[k][j] += w * ebp[k - i - 1]
                        if k > i + 1: C[k][j] += w * Qm[i + 1][k - 1]
        return P

    def sample(self, count, seed):
        m, n, Qb, Qm, Qm1, Q5, B, ebp = self.m, self.n, self.Qb, self.Qm, self.Qm1, self.Q5, self.B, self.ebp
        rng = random.Random(seed); out = []

        def pick(options, total):
            r = rng.random() * total; acc = 0.0
            for w, val in options:
                acc += w
                if r <= acc: return val
            return options[-1][1]

        for _ in range(count):
            pairs, todo = set(), [('F', 0, n)]
            while todo:
                kind, i, j = todo.pop()
                if kind == 'F':
                    if j == 0: continue
                    opts = [(Q5[j - 1], ('F', 0, j - 1, None))]
                    for k in range(0, j - MIN_HAIRPIN - 1):
                        if Qb[k][j - 1] > 0: opts.append((Q5[k] * Qb[k][j - 1] * B(m.ext_stem(k, j - 1)), ('FV', k, j - 1, None)))
                    c = pick(opts, Q5[j])
                    if c[0] == 'F': todo.append(('F', 0, j - 1))
                    else: todo += [('F', 0, c[1]), ('V', c[1], c[2])]
                elif kind == 'V':
                    pairs.add((i, j))
                    opts = [(B(m.hairpin(i, j)), None)]
                    for k in range(i + 1, min(i + MAXLOOP + 2, j - MIN_HAIRPIN - 1)):
                        u1 = k - i - 1
                        for l in range(j - 1, max(k + MIN_HAIRPIN, j - 2 - MAXLOOP + u1), -1):
                            if Qb[k][l] > 0: opts.append((B(m.interior(i, j, k, l)) * Qb[k][l], ('V', k, l)))
                    mc = B(m.ml_closing(i, j))
                    for u in range(i + 2, j - 1):
                        w = mc * Qm[i + 1][u - 1] * Qm1[u][j - 1]
                        if w > 0: opts.append((w, ('ML', u, j)))
                    c = pick(opts, Qb[i][j])
                    if c is None: continue
                    if c[0] == 'V': todo.append(c)
                    else: todo += [('M', i + 1, c[1] - 1), ('M1', c[1], j - 1)]
                elif kind == 'M1':
                    opts = [(Qb[i][l] * B(m.ml_stem(i, l)) * ebp[j - l], l) for l in range(i + MIN_HAIRPIN + 1, j + 1) if Qb[i][l] > 0]
                    todo.append(('V', i, pick(opts, Qm1[i][j])))
                elif kind == 'M':
                    opts = []
                    for u in range(i, j - MIN_HAIRPIN):
                        if Qm1[u][j] > 0:
                            opts.append((ebp[u - i] * Qm1[u][j], (u, False)))
                            if u > i and Qm[i][u - 1] > 0: opts.append((Qm[i][u - 1] * Qm1[u][j], (u, True)))
                    u, more = pick(opts, Qm[i][j])
                    todo.append(('M1', u, j))
                    if more: todo.append(('M', i, u - 1))
            out.append(to_dotbracket(pairs, n))
        return out

    def bpp(self):
        return [(i, j, self.P[i][j]) for i in range(self.n) for j in range(i + 1, self.n) if self.P[i][j] > 1e-5]


def vienna_available():
    try:
        import RNA  # noqa: F401
        return RNA.__version__
    except Exception:
        return None


class Vienna:
    """Same interface backed by ViennaRNA (Turner 2004 parameters, dangles=2 by default)."""

    def __init__(self, seq):
        import RNA
        self.RNA = RNA; self.n = len(seq); self.seq = seq
        md = RNA.md(); md.uniq_ML = 1
        self.fc = fc = RNA.fold_compound(seq, md)
        structure, mfe = fc.mfe()
        self.mfe_pairs = pairs_of(structure); self.mfe_energy = mfe
        fc.exp_params_rescale(mfe)
        _, g = fc.pf(); self.ensemble_energy = g
        raw = fc.bpp()
        self._bpp = [(i - 1, j - 1, raw[i][j]) for i in range(1, self.n + 1) for j in range(i + 1, self.n + 1) if raw[i][j] > 1e-5]

    def bpp(self):
        return self._bpp

    def sample(self, count, seed):
        self.RNA.init_rand(seed)
        return list(self.fc.pbacktrack(count))

    def evaluate(self, structure):
        return self.fc.eval_structure(structure)


def compare(predicted, reference):
    tp = len(predicted & reference); fp = len(predicted - reference); fn = len(reference - predicted)
    sens = tp / (tp + fn) if tp + fn else 0.0; ppv = tp / (tp + fp) if tp + fp else 0.0
    f1 = 2 * sens * ppv / (sens + ppv) if sens + ppv else 0.0
    return {'truePositive': tp, 'falsePositive': fp, 'falseNegative': fn, 'sensitivity': sens, 'ppv': ppv, 'f1': f1}


def bp_distance(a, b):
    return len(a ^ b)


def analyse(seq, samples=1000, seed=1, reference=None, backend='auto'):
    """Full ensemble analysis; ``reference`` is an optional dot-bracket for accuracy statistics."""
    seq = clean(seq)
    version = vienna_available()
    use = 'viennarna' if (backend == 'viennarna' or (backend == 'auto' and version)) else 'builtin-nn'
    if use == 'viennarna' and not version: raise ValueError('ViennaRNA is not installed in this interpreter.')
    eng = Vienna(seq) if use == 'viennarna' else Builtin(seq)
    ev = eng.evaluate if use == 'viennarna' else (lambda s: evaluate(seq, s))
    n = len(seq)
    bpp = eng.bpp()
    Pm = {(i, j): p for i, j, p in bpp}
    paired = [0.0] * n
    for i, j, p in bpp: paired[i] += p; paired[j] += p
    unpaired = [max(0.0, 1.0 - x) for x in paired]
    centroid = {(i, j) for (i, j), p in Pm.items() if p > 0.5}
    mfe_db = to_dotbracket(eng.mfe_pairs, n)
    sampled = eng.sample(int(samples), int(seed))
    counts = {}
    for s in sampled: counts[s] = counts.get(s, 0) + 1
    sample_sets = {s: pairs_of(s) for s in counts}
    # Ensemble diversity: mean base-pair distance between independent samples (exact formula from P).
    diversity = sum(2 * p * (1 - p) for p in Pm.values()) if Pm else 0.0
    # Alternative states: greedy clustering of distinct samples by base-pair distance.
    radius = max(4, n // 12)
    order = sorted(counts, key=lambda s: -counts[s]); clusters = []
    for s in order:
        for c in clusters:
            if bp_distance(sample_sets[s], sample_sets[c['representative']]) <= radius:
                c['members'] += counts[s]; break
        else:
            clusters.append({'representative': s, 'members': counts[s]})
    states = []
    for c in clusters[:6]:
        rep = c['representative']
        states.append({'structure': rep, 'energy': ev(rep), 'frequency': c['members'] / len(sampled),
                       'bpDistanceToMfe': bp_distance(sample_sets[rep], eng.mfe_pairs),
                       'boltzmannProbability': math.exp(-(ev(rep) - eng.ensemble_energy) / KT)})
    result = {
        'sequence': seq, 'length': n, 'backend': use, 'backendVersion': version if use == 'viennarna' else '1',
        'model': MODEL if use == 'builtin-nn' else {'name': 'viennarna', 'title': 'ViennaRNA ' + str(version) + ' (Turner 2004, dangles=2)', 'citations': ['doi:10.1186/1748-7188-6-26']},
        'temperatureC': 37.0,
        'mfe': {'structure': mfe_db, 'energy': eng.mfe_energy},
        'ensembleFreeEnergy': eng.ensemble_energy,
        'mfeProbability': math.exp(-(eng.mfe_energy - eng.ensemble_energy) / KT),
        'centroid': {'structure': to_dotbracket(centroid, n), 'energy': ev(to_dotbracket(centroid, n))},
        'bpp': [[i, j, round(p, 6)] for i, j, p in bpp if p >= 1e-3],
        'unpaired': [round(x, 6) for x in unpaired],
        'ensembleDiversity': diversity,
        'samples': {'count': len(sampled), 'seed': int(seed), 'distinct': len(counts), 'clusterRadius': radius,
                    'meanBpDistanceToMfe': sum(bp_distance(sample_sets[s], eng.mfe_pairs) * c for s, c in counts.items()) / len(sampled),
                    'top': [{'structure': s, 'count': counts[s], 'energy': ev(s)} for s in order[:12]]},
        'alternativeStates': states,
    }
    if reference:
        ref = pairs_of(reference)
        if len(reference) != n: raise ValueError('Reference structure length differs from the sequence.')
        result['reference'] = {
            'structure': reference,
            'energy': ev(reference),
            'boltzmannProbability': math.exp(-(ev(reference) - eng.ensemble_energy) / KT),
            'mfe': compare(eng.mfe_pairs, ref),
            'centroid': compare(centroid, ref),
            'expectedSensitivity': sum(Pm.get(pq, 0.0) for pq in ref) / len(ref) if ref else 0.0,
            'meanPairProbability': {f'{i + 1}-{j + 1}': round(Pm.get((i, j), 0.0), 4) for i, j in sorted(ref)},
            'sampledSensitivity': sum(len(sample_sets[s] & ref) * c for s, c in counts.items()) / (len(sampled) * len(ref)) if ref else 0.0,
        }
    return result
