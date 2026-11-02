"""Demo 11: a spatial phospho-protein gradient in a cell, solved with the RDME.

Biology (Brown & Kholodenko 1999, doi:10.1016/S0014-5793(99)01058-3; Kholodenko 2006,
doi:10.1038/nrm1838): a kinase at the plasma membrane phosphorylates a cytosolic
protein, which diffuses inwards while a phosphatase dephosphorylates it. The
phosphorylated form therefore decays with distance from the membrane over the length
L = √(D/kₚ), so less signal reaches the nucleus than is made at the membrane.

Geometry: a spherical cell with a concentric nucleus behind an envelope of finite
permeability, voxelised with edge h. Reactions: U → P on membrane voxels (first order
in U with a surface rate constant), P → U everywhere. All parameter values are
hypothetical and say so; the papers above supply the model structure only.

Validation (numerical, not biological):
  1. lattice diffusion: mean squared displacement against 6Dt;
  2. bimolecular kinetics: A + B ⇌ C in one voxel against the exact stationary
     distribution of the chemical master equation;
  3. continuum: finite-volume steady state against the analytical solution
     p(r) = A·sinh(r/L)/r, with error falling as the mesh is refined;
  4. stochastic mean: RDME time averages against the finite-volume solution on the
     same mesh (exact for first-order networks), with batch-means error bars;
  5. conservation of molecules.
"""
import math, time
import numpy as np
from scipy import stats
from scipy.sparse.linalg import cg
import multiscale_kernel as K
import spatial_rdme as R

REFS = {
    'nsm': {'citation': 'Elf J, Ehrenberg M. Spontaneous separation of bi-stable biochemical systems into spatial domains of opposite phases. Syst Biol 2004;1:230–236.', 'doi': '10.1049/sb:20045021'},
    'gradient': {'citation': 'Brown GC, Kholodenko BN. Spatial gradients of cellular phospho-proteins. FEBS Lett 1999;457:452–454.', 'doi': '10.1016/S0014-5793(99)01058-3'},
    'review': {'citation': 'Kholodenko BN. Cell-signalling dynamics in time and space. Nat Rev Mol Cell Biol 2006;7:165–176.', 'doi': '10.1038/nrm1838'},
    'voxel': {'citation': 'Isaacson SA. The reaction-diffusion master equation as an asymptotic approximation of diffusion to a small target. SIAM J Appl Math 2009;70:77–111.', 'doi': '10.1137/070705039'},
}

PARAMS = [
    K.Param('cellRadius', 5.0, 'um', 'assumption', 'Radius of a small spherical mammalian cell', range=None),
    K.Param('nucleusRadius', 2.5, 'um', 'assumption', 'Concentric nucleus', range=None),
    K.Param('diffusion', 1.0, 'um2/s', 'hypothetical', 'Cytoplasmic diffusion coefficient of the substrate (both forms)', range=(0.5, 10.0)),
    K.Param('phosphatase', 0.25, '1/s', 'hypothetical', 'First-order dephosphorylation rate constant (cytoplasm and nucleus)', range=(0.05, 2.0)),
    K.Param('kinase', 0.3, 'um/s', 'hypothetical', 'Membrane kinase surface rate constant (flux = k·[U] at the membrane)', range=(0.05, 2.0)),
    K.Param('envelope', 0.5, 'um/s', 'hypothetical', 'Nuclear-envelope permeability', range=(0.05, 5.0)),
    K.Param('molecules', 1000, 'molecule', 'hypothetical', 'Substrate copies per cell (sets the noise, not the mean fractions, because the network is first order)', range=None),
]
LIMITS = {'diffusion': (0.05, 50.0), 'phosphatase': (0.01, 10.0), 'kinase': (0.0, 20.0), 'envelope': (0.0, 100.0), 'molecules': (50, 5000)}

DEMO = {
    'id': 'demo11', 'title': 'Demo 11 · Spatial signalling gradient',
    'question': 'How much of a membrane-made phospho-signal reaches the nucleus when a cytoplasmic phosphatase acts during diffusion?',
    'method': 'Reaction–diffusion master equation, exact next-subvolume method; deterministic finite-volume reference on the same mesh',
    'evidence': {'checks': K.EVIDENCE['physics'], 'biology': K.EVIDENCE['hypothesis']},
    'assumptions': [
        'Both forms of the substrate diffuse with the same coefficient and cross the envelope equally.',
        'Kinase is uniform over the membrane and first order in U (far below saturation).',
        'Phosphatase is uniform and first order in P, with the same rate in nucleus and cytoplasm.',
        'Spherical cell and concentric nucleus; no cytoskeletal crowding, organelles or transport.',
        'Voxels are cubes; membrane voxels share the exact sphere area equally (staircase correction).',
    ],
    'limitations': [
        'Parameters are hypothetical; no fit to measured phospho-gradients was made.',
        'Bimolecular reactions are exact only for voxels larger than the reaction radius (Isaacson 2009).',
        'The deterministic reference covers first-order networks only.',
    ],
    'references': REFS,
}


def _model(mesh, D, kp, kk, perm):
    species = [{'name': 'U', 'D': D, 'P': perm}, {'name': 'P', 'D': D, 'P': perm}]
    membrane = mesh.membrane * kk * mesh.membrane_area_per_voxel / mesh.volume
    return R.Model(mesh, species, [
        {'name': 'phosphorylation (membrane kinase)', 'reactants': [0], 'products': [1], 'c': membrane},
        {'name': 'dephosphorylation (phosphatase)', 'reactants': [1], 'products': [0], 'c': np.full(mesh.n, kp)},
    ])


def analytical(r, radius, D, kp, kk, ctot):
    """Steady phospho-concentration in a sphere without a nucleus barrier."""
    L = math.sqrt(D / kp)
    f = lambda x: math.sinh(x / L) / x
    df = math.cosh(radius / L) / (L * radius) - math.sinh(radius / L) / radius ** 2
    A = kk * ctot / (D * df + kk * f(radius))
    r = np.maximum(np.asarray(r, dtype=float), 1e-9)
    return A * np.sinh(r / L) / r


# ---------------------------------------------------------------- benchmarks

def check_diffusion(seed=1, N=2000, D=1.0, h=0.5, t=1.0):
    mesh = R.box(25, h)
    model = R.Model(mesh, [{'name': 'X', 'D': D}], [])
    n0 = np.zeros((1, mesh.n), dtype=int)
    centre = mesh.index[12, 12, 12]; n0[0, centre] = N
    run = R.simulate(model, n0, t, seed=seed)
    x = mesh.centres(); r2 = (x ** 2).sum(1)
    w = run['final'][0]
    msd = float((w * r2).sum() / N)
    sd = float(math.sqrt(max((w * (r2 - msd) ** 2).sum() / (N - 1), 1e-30)))
    se = sd / math.sqrt(N)
    z = (msd - 6 * D * t) / se
    return {'name': 'Lattice diffusion: mean squared displacement', 'measured': msd, 'expected': 6 * D * t, 'unit': 'um2', 'stat': z, 'statName': 'z',
            'passed': abs(z) < 4 and run['final'].sum() == N, 'detail': f'{N} molecules from one voxel, D = {D} µm²/s, t = {t} s, h = {h} µm; expected 6Dt exactly on the lattice; SE {se:.3f} µm²'}


def check_cme(seed=1, n=10, c1=0.05, c2=1.0, samples=8000, every=0.5):
    mesh = R.box(1, 1.0)
    model = R.Model(mesh, [{'name': s, 'D': 1.0} for s in 'ABC'], [
        {'name': 'bind', 'reactants': [0, 1], 'products': [2], 'c': c1},
        {'name': 'unbind', 'reactants': [2], 'products': [0, 1], 'c': c2}])
    times = [every * (k + 1) for k in range(samples)]
    run = R.simulate(model, np.array([[n], [n], [0]]), times[-1], seed=seed, record=times)
    c = np.array([tot[2] for _, tot in run['record']])
    # Exact stationary distribution by detailed balance of the one-dimensional chain.
    w = [1.0]
    for k in range(n):
        w.append(w[-1] * c1 * (n - k) ** 2 / (c2 * (k + 1)))
    pi = np.array(w) / sum(w)
    exact_mean = float((np.arange(n + 1) * pi).sum())
    hist = np.bincount(c, minlength=n + 1)[:n + 1] / len(c)
    tv = 0.5 * float(np.abs(hist - pi).sum())
    bm = c.reshape(40, -1).mean(1)
    se = float(bm.std(ddof=1) / math.sqrt(len(bm)))
    z = (c.mean() - exact_mean) / se
    return {'name': 'Bimolecular A + B ⇌ C against the exact master equation', 'measured': float(c.mean()), 'expected': exact_mean, 'unit': 'molecule', 'stat': float(z), 'statName': 'z',
            'passed': abs(z) < 4 and tv < 0.05, 'detail': f'{n} A + {n} B in one voxel, c₁ = {c1} /s, c₂ = {c2} /s; {samples} samples every {every} s; total-variation distance {tv:.3f}',
            'histogram': hist.tolist(), 'exact': pi.tolist()}


def check_continuum(D, kp, kk, radius=5.0, total=1000.0, spacings=(1.0, 0.5, 0.25)):
    rows = []
    for h in spacings:
        mesh = R.sphere_cell(radius, h)
        # With equal diffusion of both forms, U + P obeys pure diffusion and is uniform at steady
        # state (exactly, on the mesh too), so P alone solves (D∇² − kₚ − k_mem) p = −k_mem·u_tot:
        # symmetric and definite, solved by conjugate gradients.
        cmem = mesh.membrane * kk * mesh.membrane_area_per_voxel / mesh.volume
        G = R.Model(mesh, [{'name': 'P', 'D': D}], [{'name': 'loss', 'reactants': [0], 'products': [], 'c': kp + cmem}]).generator()
        sol, info = cg(-G, cmem * total / mesh.n, rtol=1e-12, maxiter=20000)
        if info:
            raise RuntimeError('Conjugate gradients did not converge.')
        x = np.vstack([total / mesh.n - sol, sol])
        conc = x[1] / mesh.volume
        ctot = total / (mesh.n * mesh.volume)
        r = np.sqrt((mesh.centres() ** 2).sum(1))
        exact = analytical(r, radius, D, kp, kk, ctot)
        err = float(np.sqrt(((conc - exact) ** 2).sum() / (exact ** 2).sum()))
        shells = np.linspace(0, radius, 11)
        k = np.clip(np.digitize(r, shells) - 1, 0, 9)
        prof = [float(conc[k == i].mean() / ctot) if (k == i).any() else None for i in range(10)]
        rows.append({'h': h, 'voxels': mesh.n, 'relativeL2': err, 'profile': prof, 'massResidual': float(abs(x.sum() - total) / total)})
    errs = [r['relativeL2'] for r in rows]
    order = math.log(errs[-2] / errs[-1]) / math.log(spacings[-2] / spacings[-1])
    mids = (np.linspace(0, radius, 11)[:-1] + radius / 20)
    return {'name': 'Finite volume against the analytical gradient', 'measured': errs[-1], 'expected': 0.0, 'unit': '1', 'stat': order, 'statName': 'observed order',
            'passed': all(a > b for a, b in zip(errs, errs[1:])) and errs[-1] < 0.05 and all(r['massResidual'] < 1e-9 for r in rows),
            'detail': 'Relative L2 error ' + ', '.join(f'{e:.3%} (h = {h} µm)' for e, h in zip(errs, spacings)) + f'; observed order {order:.2f}',
            'rows': rows, 'curve': {'r': mids.tolist(), 'fraction': analytical(mids, radius, D, kp, kk, 1.0).tolist()}}


# ---------------------------------------------------------------- scenario

def _shells(mesh, edges):
    r = np.sqrt((mesh.centres() ** 2).sum(1))
    return np.clip(np.digitize(r, edges) - 1, 0, len(edges) - 2)


def run(overrides=None, seed=1, h=0.5, burn=30.0, batches=16, window=5.0):
    started = time.time()
    p = {q.name: float(q.value) for q in PARAMS}
    for k, v in (overrides or {}).items():
        if k not in LIMITS:
            raise ValueError('Parameter cannot be changed: ' + k)
        lo, hi = LIMITS[k]
        if not lo <= float(v) <= hi:
            raise ValueError(f'{k} must lie in {lo}–{hi}.')
        p[k] = float(v)
    N = int(round(p['molecules']))
    D, kp, kk, perm = p['diffusion'], p['phosphatase'], p['kinase'], p['envelope']
    mesh = R.sphere_cell(p['cellRadius'], h, p['nucleusRadius'])
    model = _model(mesh, D, kp, kk, perm)
    fv = model.steady_state(N)

    rng = np.random.default_rng(seed)
    n0 = np.zeros((2, mesh.n), dtype=int)
    np.add.at(n0[0], rng.integers(0, mesh.n, N), 1)
    t_end = burn + batches * window
    times = list(np.linspace(0, t_end, 121)[1:])
    sim = R.simulate(model, n0, t_end, seed=seed, t_avg=burn, batches=batches, record=times)

    edges = np.linspace(0, p['cellRadius'], 11)
    shell = _shells(mesh, edges)
    def shell_frac(x):
        return np.array([x[1][shell == i].sum() / max(x[:, shell == i].sum(), 1e-30) for i in range(10)])
    def shell_p(x):
        return np.array([x[1][shell == i].sum() for i in range(10)])
    fv_p = shell_p(fv)
    B = np.array([shell_p(b) for b in sim['batches']])
    mean, se = B.mean(0), B.std(0, ddof=1) / math.sqrt(len(B))
    t = (mean - fv_p) / np.where(se > 0, se, np.inf)
    pvals = 2 * stats.t.sf(np.abs(t), df=len(B) - 1)
    nucleus, membrane = mesh.compartment == 2, mesh.membrane
    frac = lambda x, m: float(x[1][m].sum() / x[:, m].sum())
    rdme_mean = np.mean(sim['batches'], axis=0)

    checks = [check_diffusion(seed), check_cme(seed), check_continuum(D, kp, kk, p['cellRadius'])]
    checks.append({'name': 'Stochastic mean against finite volume (same mesh)', 'measured': float(np.abs(t).max()), 'expected': 0.0, 'unit': '1', 'stat': float(pvals.min() * len(pvals)), 'statName': 'Bonferroni p',
                   'passed': bool(pvals.min() * len(pvals) > 1e-3),
                   'detail': f'{len(B)} batches of {window} s after {burn} s burn-in; phosphorylated molecules in 10 radial shells; largest |t| {np.abs(t).max():.2f} (df {len(B) - 1})'})
    finals = sim['final'].sum()
    checks.append({'name': 'Molecule conservation', 'measured': float(finals), 'expected': float(N), 'unit': 'molecule', 'stat': float(abs(fv.sum() - N)), 'statName': 'FV residual',
                   'passed': int(finals) == N and abs(fv.sum() - N) < 1e-6 * N, 'detail': 'Integer copy numbers in the RDME; sum of the finite-volume steady state'})

    mid = mesh.shape[2] // 2
    sl = np.full(mesh.shape[:2], None, dtype=object)
    sl_rdme = np.full(mesh.shape[:2], None, dtype=object)
    for v, (i, j, k) in enumerate(mesh.ijk):
        if k == mid:
            tot = fv[:, v].sum()
            sl[i, j] = float(fv[1, v] / tot) if tot > 0 else 0.0
            sl_rdme[i, j] = int(sim['final'][1, v])
    lab = mesh.labels[:, :, mid].tolist()

    sweep = []
    for kpx in np.geomspace(0.02, 4.0, 12):
        x = _model(mesh, D, float(kpx), kk, perm).steady_state(N)
        sweep.append({'phosphatase': float(kpx), 'L': math.sqrt(D / kpx), 'membrane': frac(x, membrane), 'nucleus': frac(x, nucleus)})

    L = math.sqrt(D / kp)
    outputs = {
        'decayLength': {'value': L, 'unit': 'um', 'label': 'Gradient length √(D/kₚ)'},
        'membraneFraction': {'value': frac(fv, membrane), 'unit': '1', 'label': 'Phosphorylated fraction at the membrane'},
        'nucleusFraction': {'value': frac(fv, nucleus), 'unit': '1', 'label': 'Phosphorylated fraction in the nucleus'},
        'nucleusToMembrane': {'value': frac(fv, nucleus) / frac(fv, membrane), 'unit': '1', 'label': 'Nucleus ÷ membrane'},
        'cellFraction': {'value': float(fv[1].sum() / N), 'unit': '1', 'label': 'Phosphorylated fraction, whole cell'},
        'rdmeNucleusFraction': {'value': frac(rdme_mean, nucleus), 'unit': '1', 'label': 'Nuclear fraction, RDME time average'},
    }
    return {
        **{k: DEMO[k] for k in ('id', 'title', 'question', 'method', 'evidence', 'assumptions', 'limitations', 'references')},
        'parameters': [{**q.__dict__, 'value': p[q.name], 'range': list(q.range) if q.range else None, 'editable': q.name in LIMITS} for q in PARAMS],
        'overrides': {k: float(v) for k, v in (overrides or {}).items()}, 'seed': seed,
        'mesh': {'h': h, 'voxels': mesh.n, 'membraneVoxels': int(membrane.sum()), 'nucleusVoxels': int(nucleus.sum()), 'shape': list(mesh.shape),
                 'membraneAreaPerVoxel': mesh.membrane_area_per_voxel, 'volume': mesh.n * mesh.volume, 'sphereVolume': 4 / 3 * math.pi * p['cellRadius'] ** 3},
        'reactions': [{'name': r['name'], 'reactants': [model.species[i]['name'] for i in r['reactants']], 'products': [model.species[i]['name'] for i in r['products']]} for r in model.reactions],
        'equations': ['∂u/∂t = D∇²u + kₚ p,  ∂p/∂t = D∇²p − kₚ p', 'membrane: D ∂p/∂n = k_k u (and −k_k u for U)', 'envelope: hop rate 1/(h²/D + h/P_env)', 'RDME: voxel hops D/h², next-subvolume method'],
        'outputs': outputs,
        'profile': {'edges': edges.tolist(), 'fv': shell_frac(fv).tolist(), 'rdme': shell_frac(rdme_mean).tolist(), 'rdmeCounts': mean.tolist(), 'rdmeSE': se.tolist(), 'fvCounts': fv_p.tolist(),
                    'nucleusRadius': p['nucleusRadius']},
        'slice': {'fv': sl.tolist(), 'rdme': sl_rdme.tolist(), 'labels': lab, 'h': h},
        'timeline': {'t': [t for t, _ in sim['record']], 'P': [tot[1] for _, tot in sim['record']], 'burn': burn},
        'sweep': sweep, 'checks': checks,
        'events': sim['events'], 'seconds': time.time() - started,
    }
