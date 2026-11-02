"""RNA folding kinetics on the complete secondary-structure landscape (Demo 10).

Method (the microscopic model behind Kinfold and treekin; Flamm et al. 2000,
doi:10.1017/S1355838200992161; Wolfinger et al. 2004, doi:10.1088/0305-4470/37/17/005):
every secondary structure of the sequence is a state, ViennaRNA 2.x evaluates its free
energy, and elementary moves open or close one base pair with Metropolis rates

    k(x → y) = k₀ · min(1, exp(−(E_y − E_x)/RT)).

The state space is enumerated completely (RNAsubopt with unique multiloop
decomposition, dangles = 0, so the Boltzmann sum reproduces ViennaRNA's partition
function exactly), and the master equation dp/dt = Qᵀp is solved exactly through the
eigen-decomposition of the symmetrised generator (detailed balance holds by
construction). States are lumped into gradient basins (steepest descent, as in
Barriers) for display; the time evolution itself is computed on all states.

What this is not: k₀ is not calibrated, so time is in units of 1/k₀; only single base-pair
moves are allowed (no shift moves); co-transcriptional folding, ions and pseudoknots are
not modelled.
"""
import heapq, math
import numpy as np
from scipy import linalg, sparse
from scipy.sparse.linalg import spsolve

KCAL_R = 1.98717e-3   # kcal/(mol·K)
MAX_STATES = 6000


def _rna():
    import RNA
    return RNA


def model(temperature=37.0):
    RNA = _rna()
    md = RNA.md()
    md.temperature, md.dangles, md.uniq_ML = float(temperature), 0, 1
    return md


def pairs(db):
    st, out = [], []
    for i, c in enumerate(db):
        if c == '(':
            st.append(i)
        elif c == ')':
            out.append((st.pop(), i))
    return frozenset(out)


def enumerate_landscape(seq, temperature=37.0):
    RNA = _rna()
    md = model(temperature)
    fc = RNA.fold_compound(seq, md)
    mfe_db, mfe = fc.mfe()
    subs = fc.subopt(100000)   # 1000 kcal/mol window: every structure
    if len(subs) > MAX_STATES:
        raise ValueError(f'{len(subs)} structures exceed the exact-solver limit of {MAX_STATES}; use a shorter sequence.')
    structs = [s.structure for s in subs]
    E = np.array([fc.eval_structure(s) for s in structs])
    fc.exp_params_rescale(mfe)
    _, G = fc.pf()
    return {'sequence': seq, 'structures': structs, 'energies': E, 'mfe': (mfe_db, mfe), 'ensembleEnergy': G, 'kT': KCAL_R * (temperature + 273.15),
            'version': RNA.__version__, 'temperature': temperature}


def graph(structs):
    """Neighbour pairs (i, j) differing by exactly one base pair (j has the extra pair)."""
    ps = [pairs(s) for s in structs]
    index = {p: i for i, p in enumerate(ps)}
    edges = []
    for j, p in enumerate(ps):
        for bp in p:
            i = index.get(p - {bp})
            if i is None:
                raise ValueError('Landscape is not closed under base-pair removal.')
            edges.append((i, j))
    return np.array(edges, dtype=np.int64), ps


def generator(E, edges, kT, k0=1.0):
    i, j = edges[:, 0], edges[:, 1]
    dE = E[j] - E[i]
    kij = k0 * np.minimum(1.0, np.exp(-dE / kT))
    kji = k0 * np.minimum(1.0, np.exp(dE / kT))
    n = len(E)
    Q = sparse.coo_matrix((np.concatenate([kij, kji]), (np.concatenate([i, j]), np.concatenate([j, i]))), shape=(n, n)).tocsr()
    Q = Q - sparse.diags(np.asarray(Q.sum(1)).ravel())
    return Q.tocsr()


def boltzmann(E, kT):
    w = np.exp(-(E - E.min()) / kT)
    return w / w.sum()


class Solution:
    """Exact p(t) = Σ c_k e^{λ_k t} v_k from the symmetrised generator S = Π^{1/2} Q Π^{-1/2}."""

    def __init__(self, Q, pi):
        s = np.sqrt(pi)
        S = (sparse.diags(s) @ Q @ sparse.diags(1 / s)).toarray()
        S = 0.5 * (S + S.T)
        self.lam, self.V = linalg.eigh(S)
        self.s = s

    def at(self, p0, times):
        c = self.V.T @ (p0 / self.s)
        out = (np.exp(np.outer(times, self.lam)) * c) @ self.V.T   # (T, n)
        return np.maximum(out * self.s[None, :], 0.0)

    def relaxation_times(self, k=6):
        lam = np.sort(self.lam)[::-1][1:k + 1]
        return [-1 / l for l in lam if l < 0]


def basins(E, edges, n):
    """Steepest-descent basin of every state (ties broken by index, as a total order)."""
    nb = [[] for _ in range(n)]
    for i, j in edges:
        nb[i].append(j); nb[j].append(i)
    key = lambda x: (E[x], x)
    down = np.array([min(nb[x] + [x], key=key) for x in range(n)])
    root = np.arange(n)
    for x in np.argsort(E):
        root[x] = x if down[x] == x else root[down[x]]
    return root


def saddles(E, edges, minima):
    """Exact lowest saddle between every pair of minima (minimax path, union–find over edges by height)."""
    parent = list(range(len(E)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    height = np.maximum(E[edges[:, 0]], E[edges[:, 1]])
    want = {(a, b) for a in minima for b in minima if a < b}
    out = {}
    for e in np.argsort(height, kind='stable'):
        a, b = find(edges[e, 0]), find(edges[e, 1])
        if a == b:
            continue
        parent[a] = b
        for pair in list(want):
            if find(pair[0]) == find(pair[1]):
                out[pair] = float(height[e]); want.discard(pair)
        if not want:
            break
    return out


def mean_first_passage(Q, target):
    """Mean first-passage time to `target` from every state: solve Q τ = −1 with τ_target = 0."""
    n = Q.shape[0]
    keep = np.array([x for x in range(n) if x != target])
    A = Q[keep][:, keep].tocsc()
    tau = np.zeros(n)
    tau[keep] = spsolve(A, -np.ones(len(keep)))
    return tau


def gillespie(Q, start, times, trajectories, seed, target=None):
    """Independent stochastic check: exact SSA on the same generator. Returns states at `times`
    and first-passage times to `target`."""
    rng = np.random.default_rng(seed)
    Q = Q.tocsr()
    rows = [(Q.indices[Q.indptr[i]:Q.indptr[i + 1]], Q.data[Q.indptr[i]:Q.indptr[i + 1]]) for i in range(Q.shape[0])]
    out = []
    for i in range(Q.shape[0]):
        idx, val = rows[i]
        m = idx != i
        rows[i] = (idx[m], np.cumsum(val[m]))
    states = np.zeros((trajectories, len(times)), dtype=np.int64)
    fpt = np.full(trajectories, np.nan)
    tmax = times[-1]
    for r in range(trajectories):
        x, t, k = start, 0.0, 0
        while True:
            if target is not None and x == target and math.isnan(fpt[r]):
                fpt[r] = t
            idx, cum = rows[x]
            t_next = t + rng.exponential(1 / cum[-1])
            while k < len(times) and times[k] < t_next:
                states[r, k] = x; k += 1
            if k == len(times) and (target is None or not math.isnan(fpt[r])):
                break
            t = t_next
            x = int(idx[np.searchsorted(cum, rng.random() * cum[-1], side='right')])
    return states, fpt
