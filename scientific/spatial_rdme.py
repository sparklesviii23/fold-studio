"""Spatial stochastic reaction–diffusion on a voxel mesh.

Method: the reaction–diffusion master equation (RDME). Space is divided into cubic
voxels of edge h; inside a voxel molecules are well mixed, and diffusion is a
first-order jump to a face neighbour with rate D/h². The RDME is simulated exactly
with the next-subvolume method (NSM; Elf & Ehrenberg 2004, doi:10.1049/sb:20045021),
the algorithm used by MesoRD and URDME: every voxel holds the time of its next event
in a priority queue, and only the voxels touched by an event are rescheduled.

The same voxel generator also gives the deterministic finite-volume system
dc/dt = M c. For first-order networks the RDME mean obeys exactly this equation, so
the finite-volume solution is an exact reference for the stochastic mean on the same
mesh, and its convergence under refinement is checked against analytical solutions.

Limits (stated, not hidden): voxels must be larger than the reaction radius for
bimolecular reactions to stay meaningful (Isaacson 2009, doi:10.1137/070705039);
the cell boundary is a staircase of voxels whose membrane area is renormalised to the
true sphere area; the deterministic solver handles first-order networks only.
"""
import heapq, math, random
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve

DIRS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


class Mesh:
    """Voxels of a labelled Cartesian grid. labels: 0 outside, 1 cytoplasm, 2 nucleus."""

    def __init__(self, labels, h, membrane_area=None, envelope=True):
        self.h, self.shape = float(h), labels.shape
        self.labels = labels
        inside = np.argwhere(labels > 0)
        self.ijk = inside
        self.index = -np.ones(labels.shape, dtype=np.int64)
        self.index[tuple(inside.T)] = np.arange(len(inside))
        self.compartment = labels[tuple(inside.T)].astype(np.int64)
        self.n = len(inside)
        self.volume = self.h ** 3
        edges, boundary = [], np.zeros(self.n, dtype=bool)
        for v, (i, j, k) in enumerate(inside):
            for di, dj, dk in DIRS:
                a, b, c = i + di, j + dj, k + dk
                w = self.index[a, b, c] if 0 <= a < self.shape[0] and 0 <= b < self.shape[1] and 0 <= c < self.shape[2] else -1
                if w < 0:
                    boundary[v] = True
                else:
                    edges.append((v, int(w), envelope and self.compartment[v] != self.compartment[w]))
        self.edges = edges
        self.membrane = boundary & (self.compartment == 1) if envelope else boundary
        # Staircase voxels overstate the area of a curved surface; spread the true area evenly.
        nm = int(self.membrane.sum())
        self.membrane_area_per_voxel = (membrane_area / nm) if (membrane_area and nm) else self.h ** 2

    def centres(self):
        return (self.ijk - (np.array(self.shape) - 1) / 2) * self.h


def sphere_cell(radius, h, nucleus=0.0):
    m = int(math.ceil(radius / h)) + 1
    ax = np.arange(-m, m + 1) * h
    x, y, z = np.meshgrid(ax, ax, ax, indexing='ij')
    r = np.sqrt(x * x + y * y + z * z)
    labels = np.where(r <= radius, 1, 0)
    if nucleus > 0:
        labels = np.where(r <= nucleus, 2, labels)
    return Mesh(labels, h, membrane_area=4 * math.pi * radius ** 2)


def box(n, h):
    return Mesh(np.ones((n, n, n), dtype=np.int64), h, envelope=False)


def hop_rates(mesh, D, permeability=None):
    """Per-edge jump rate (1/s) for one species. Free diffusion D/h²; across the nuclear
    envelope the diffusive and membrane resistances add in series: 1/(h²/D + h/P)."""
    h = mesh.h
    out = np.empty(len(mesh.edges))
    for e, (_, _, crosses) in enumerate(mesh.edges):
        if crosses and permeability is not None:
            out[e] = 0.0 if permeability <= 0 else 1.0 / (h * h / D + h / permeability)
        else:
            out[e] = D / (h * h)
    return out


class Model:
    """species: list of {'name', 'D', 'P'}; reactions: list of {'name', 'reactants': [i], 'products': [j],
    'c': per-voxel propensity constant (1/s for first order, 1/s per molecule for second order)}."""

    def __init__(self, mesh, species, reactions):
        self.mesh, self.species, self.reactions = mesh, species, reactions
        self.rates = [hop_rates(mesh, s['D'], s.get('P')) for s in species]
        for r in reactions:
            if len(r['reactants']) > 2:
                raise ValueError('Only first- and second-order reactions are supported.')
            r['c'] = np.broadcast_to(np.asarray(r['c'], dtype=float), (mesh.n,)).copy()

    def generator(self):
        """Sparse matrix M of the mean equation dn/dt = M n (first-order networks only)."""
        S, V = len(self.species), self.mesh.n
        rows, cols, vals = [], [], []
        for s in range(S):
            for e, (v, w, _) in enumerate(self.mesh.edges):
                k = self.rates[s][e]
                rows += [s * V + w, s * V + v]; cols += [s * V + v, s * V + v]; vals += [k, -k]
        for r in self.reactions:
            if len(r['reactants']) != 1:
                raise ValueError('The deterministic reference handles first-order networks only.')
            a = r['reactants'][0]
            for v in np.nonzero(r['c'])[0]:
                k = r['c'][v]
                rows.append(a * V + v); cols.append(a * V + v); vals.append(-k)
                for b in r['products']:
                    rows.append(b * V + v); cols.append(a * V + v); vals.append(k)
        return sparse.csr_matrix((vals, (rows, cols)), shape=(S * V, S * V))

    def steady_state(self, total):
        """Steady state of dn/dt = M n with the total molecule number fixed (one conserved pool)."""
        # The null space of M is one-dimensional (irreducible network): pin one unknown with a
        # sparse unit row instead of a dense sum row (which would destroy the LU sparsity), then scale.
        M = self.generator().tolil()
        M[0, :] = 0.0
        M[0, 0] = 1.0
        rhs = np.zeros(M.shape[0]); rhs[0] = 1.0
        x = spsolve(M.tocsc(), rhs)
        x *= total / x.sum()
        return x.reshape(len(self.species), self.mesh.n)


def simulate(model, n0, t_end, seed=1, t_avg=0.0, batches=1, record=None):
    """Exact NSM simulation from integer state n0 [species, voxel] until t_end.

    Returns the final state, time-averaged copy numbers over [t_avg, t_end] split into
    `batches` equal windows (for batch-means error bars), the totals at the `record`
    times and the number of events."""
    rng = random.Random(seed)
    mesh = model.mesh
    S, V = len(model.species), mesh.n
    n = [list(map(int, row)) for row in np.asarray(n0)]
    # Neighbour lists with per-species rates.
    nb = [[[] for _ in range(V)] for _ in range(S)]
    out = [[0.0] * V for _ in range(S)]
    for s in range(S):
        for e, (v, w, _) in enumerate(mesh.edges):
            k = float(model.rates[s][e])
            if k > 0:
                nb[s][v].append((w, k)); out[s][v] += k
    rx = [[] for _ in range(V)]
    for r in model.reactions:
        for v in np.nonzero(r['c'])[0]:
            rx[v].append((tuple(r['reactants']), tuple(r['products']), float(r['c'][v])))

    def propensity(v):
        a = 0.0
        for s in range(S):
            a += n[s][v] * out[s][v]
        for reac, _, c in rx[v]:
            if len(reac) == 1:
                a += c * n[reac[0]][v]
            elif reac[0] == reac[1]:
                m = n[reac[0]][v]; a += c * m * (m - 1) / 2
            else:
                a += c * n[reac[0]][v] * n[reac[1]][v]
        return a

    width = (t_end - t_avg) / batches
    edges_t = [t_avg + width * (b + 1) for b in range(batches)]
    acc = [[0.0] * V for _ in range(S)]
    last = [[t_avg] * V for _ in range(S)]
    batch_means = []
    totals = [sum(row) for row in n]
    rec_times = list(record or [])
    rec = []

    def change(s, v, d, t):
        te = t if t > t_avg else t_avg
        acc[s][v] += n[s][v] * (te - last[s][v]); last[s][v] = te
        n[s][v] += d; totals[s] += d

    def flush(tb):
        for s in range(S):
            rs, ls, ns = acc[s], last[s], n[s]
            for v in range(V):
                rs[v] += ns[v] * (tb - ls[v]); ls[v] = tb
        batch_means.append(np.array(acc) / width)
        for s in range(S):
            acc[s] = [0.0] * V

    a = [propensity(v) for v in range(V)]
    stamp = [0] * V
    heap = []
    for v in range(V):
        if a[v] > 0:
            heap.append((rng.expovariate(a[v]), v, 0))
    heapq.heapify(heap)
    events = 0

    def reschedule(v, t):
        a[v] = propensity(v); stamp[v] += 1
        if a[v] > 0:
            heapq.heappush(heap, (t + rng.expovariate(a[v]), v, stamp[v]))

    while heap:
        t, v, st = heap[0]
        if st != stamp[v]:
            heapq.heappop(heap); continue
        while rec_times and rec_times[0] <= min(t, t_end):
            rec.append((rec_times.pop(0), list(totals)))
        while edges_t and edges_t[0] <= min(t, t_end):
            flush(edges_t.pop(0))
        if t > t_end:
            break
        heapq.heappop(heap)
        events += 1
        x = rng.random() * a[v]
        done = False
        for s in range(S):
            ds = n[s][v] * out[s][v]
            if x < ds:
                y = x / out[s][v] % 1.0 * out[s][v]   # reuse the uniform: position within one molecule's hop rate
                for w, k in nb[s][v]:
                    if y < k:
                        break
                    y -= k
                change(s, v, -1, t); change(s, w, 1, t)
                reschedule(w, t)
                done = True
                break
            x -= ds
        if not done:
            for reac, prod, c in rx[v]:
                if len(reac) == 1:
                    p = c * n[reac[0]][v]
                elif reac[0] == reac[1]:
                    m = n[reac[0]][v]; p = c * m * (m - 1) / 2
                else:
                    p = c * n[reac[0]][v] * n[reac[1]][v]
                if x < p:
                    for s in reac:
                        change(s, v, -1, t)
                    for s in prod:
                        change(s, v, 1, t)
                    break
                x -= p
        reschedule(v, t)
    while rec_times:
        rec.append((rec_times.pop(0), list(totals)))
    while edges_t:
        flush(edges_t.pop(0))
    return {'final': np.array(n), 'batches': batch_means, 'record': rec, 'events': events}
