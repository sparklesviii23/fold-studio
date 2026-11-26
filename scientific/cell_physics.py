"""Living Cell physics actions: Brownian-dynamics demos with built-in validation.

Demo 1 · diffusion: identical particles with a known D, free and inside a
reflecting sphere. Validated against MSD(t) = 6Dt, the Gaussian displacement
law, the bounded-sphere plateau ⟨|r|²⟩ = 3/5 R² and the uniform radial
distribution, each with a stated statistical tolerance.

Demo 2 · receptor binding: ligands in the pericellular shell R_cell ≤ r ≤
R_outer binding fixed receptors on the membrane (Doi model). The long-time
occupancy is compared with the exact ideal-particle equilibrium and with the
well-mixed mass-action ODE composed and integrated by the Mechanistic Biology
Lab engine (SBML → SciPy). kon and koff are hypothetical generic values.

Every run is stored as a `fold.research-record` JSON (schema of
src/lib/engineContract.ts) under <library>/cell_physics/runs with a SHA-256.
"""
import datetime, hashlib, json, math, pathlib, platform, uuid
import numpy as np
import scipy
from scipy import stats
import cell_physics_bd as bd
from cell_physics_actions import ACTIONS

VERSION = '1.0.0'
Z_LIMIT = 4.0          # |z| acceptance for statistical checks (two-sided p ≈ 6·10⁻⁵ per check)
KS_ALPHA = 1e-3        # minimum Kolmogorov–Smirnov p-value
MAX_WORK = 3e8         # particle-steps admitted per request

ENGINE = {
    'id': 'fold.cell-physics.brownian', 'name': 'Living Cell Brownian dynamics', 'version': VERSION, 'evidence': 'B',
    'spatialScale': {'min': {'value': 0.005, 'unit': 'µm'}, 'max': {'value': 50, 'unit': 'µm'}},
    'timeScale': {'min': {'value': 1e-6, 'unit': 's'}, 'max': {'value': 100, 'unit': 's'}},
    'numericalMethod': 'Overdamped Brownian dynamics (Euler–Maruyama) of point particles; specular reflection at spherical walls; Doi volume-reactivity binding with detailed-balance-exact discrete probabilities; NumPy PCG64 seeded RNG.',
    'equations': ['dx = √(2D) dW (per axis, Itô); x(t+Δt) = x(t) + √(2DΔt)·ξ, ξ ~ N(0, I₃)',
                  'Reflecting wall: the part of a step beyond the hit point is mirrored about the surface normal',
                  'L + R ⇌ C: P(bind | |x − x_R| < σ, receptor empty) = λΔt, λ = kon / V_rx; P(unbind) = koffΔt; released ligand uniform in the reaction volume',
                  'V_rx = 4/3 πσ³ − πσ³(8R_cell − 3σ)/(12 R_cell) (part of the σ-ball outside the cell)',
                  'Equilibrium: P(n) ∝ C(N_R, n)·N_L!/(N_L − n)!·(K/V)ⁿ, K = kon/koff'],
    'assumptions': ['Point particles, no excluded volume or hydrodynamic interactions', 'Constant, isotropic D', 'Rigid spherical walls; receptors fixed and immobile',
                    'One ligand per receptor; receptor reaction volumes do not overlap', 'Ideal dilute solution (activity = concentration)'],
    'validatedDomain': ['Free diffusion: any D and Δt (the scheme is exact); tested D = 10 µm²/s, 2000 particles, 0–3 s',
                        'Sphere: rms step √(2DΔt) ≤ 0.05 R; tested R = 5 µm, D = 10 µm²/s, Δt = 1 ms',
                        'Binding equilibrium: tested R_cell 5 µm, shell to 7 µm, D 20 µm²/s, σ 0.1 µm, kon 1 µm³/s, koff 0.25–4 s⁻¹, Δt 0.2 ms, 600 ligands, 200 receptors'],
    'limits': ['No physiological accuracy is claimed: kon, koff, D, receptor number and geometry are hypothetical generic values',
               'Binding kinetics (not the equilibrium) depend on σ and Δt and are not validated; they are compared with the well-mixed ODE for information only',
               'No crowding, cytoskeleton, membrane curvature effects, receptor diffusion, internalisation or signalling'],
    'benchmarks': [{'name': 'Free MSD', 'reference': 'Einstein 1905: ⟨|Δr|²⟩ = 6Dt in 3-D', 'acceptance': f'|z| < {Z_LIMIT:g} for D fitted on 10 independent groups and for MSD(t_end)'},
                   {'name': 'Gaussian displacements', 'reference': 'Free propagator N(0, 2Dt) per axis', 'acceptance': f'KS p > {KS_ALPHA:g}'},
                   {'name': 'Bounded plateau', 'reference': 'Uniform density in a sphere: ⟨r²⟩ = 3/5 R²', 'acceptance': f'|z| < {Z_LIMIT:g} at t_end ≥ 10 τ₀, τ₀ = R²/(20.19 D)'},
                   {'name': 'Radial uniformity', 'reference': '(r/R)³ ~ U(0, 1) at equilibrium', 'acceptance': f'KS p > {KS_ALPHA:g}'},
                   {'name': 'Binding equilibrium (exact)', 'reference': 'Canonical ensemble of ideal ligands and single-site receptors', 'acceptance': f'|z| < {Z_LIMIT:g} using the between-replicate standard error'},
                   {'name': 'Binding equilibrium (well-mixed ODE)', 'reference': 'Mass-action ODE composed and integrated by the Mechanistic Biology Lab (SBML → SciPy LSODA)', 'acceptance': f'|z| < {Z_LIMIT:g}; the mean-field vs exact finite-size gap is reported'}],
    'uncertainty': 'Statistical (sampling) error is quantified as standard errors over particles (diffusion) or, for binding, the larger of the between-replicate standard error and the fluctuation-theory value √(Var(n)·2τ/(T·replicates)) with τ the well-mixed relaxation time. Discretisation error is controlled by the step-size limits above; model error (point particles, idealised geometry, hypothetical parameters) is not quantified.',
    'solverChoice': {
        'chosen': 'In-house NumPy Brownian-dynamics engine (scientific/cell_physics_bd.py)',
        'evaluated': 'Smoldyn (Andrews & Bray 2004; LGPL-3.0-or-later). PyPI on 30 Oct 2026: 2.76 ships only a Linux x86-64 wheel and a py3-none-any wheel; the last macOS wheels are universal2 for CPython 3.10/3.11 (≤ 2.73). '
                     'No wheel exists for the bundled CPython 3.12 on Apple silicon, and no local runtime has Smoldyn installed.',
        'reason': 'Installing or building Smoldyn would change the bundled runtime every build copies, which needs an explicit decision by the user. The required physics (free/bounded diffusion, spherical reflection, Doi reversible binding) is small enough to implement and test directly with NumPy 2.5 / SciPy 1.18, which the runtime already ships.',
        'futureCrossCheck': 'If Smoldyn is added to a runtime, run the same demos through it and compare MSD and equilibrium occupancy within the same statistical tolerances.'},
}

DIFFUSION_INPUTS = [
    {'key': 'diffusion', 'unit': 'µm²/s', 'description': 'Diffusion coefficient D', 'bounds': [0.01, 100], 'default': 10.0},
    {'key': 'radius', 'unit': 'µm', 'description': 'Cell radius R (reflecting sphere)', 'bounds': [0.5, 50], 'default': 5.0},
    {'key': 'particles', 'unit': 'count', 'description': 'Particles per scenario', 'bounds': [100, 20000], 'default': 2000, 'integer': True},
    {'key': 'dt', 'unit': 's', 'description': 'Time step Δt', 'bounds': [1e-6, 0.1], 'default': 1e-3},
    {'key': 'tEnd', 'unit': 's', 'description': 'Simulated time', 'bounds': [1e-3, 100], 'default': 3.0},
    {'key': 'seed', 'unit': '—', 'description': 'Random seed (PCG64)', 'bounds': [0, 2 ** 32 - 1], 'default': 20261030, 'integer': True},
]

BINDING_INPUTS = [
    {'key': 'membraneRadius', 'unit': 'µm', 'description': 'Cell (membrane) radius; receptors sit on this sphere', 'bounds': [1, 20], 'default': 5.0},
    {'key': 'outerRadius', 'unit': 'µm', 'description': 'Outer reflecting wall of the pericellular compartment', 'bounds': [1.5, 30], 'default': 7.0},
    {'key': 'diffusion', 'unit': 'µm²/s', 'description': 'Ligand diffusion coefficient D', 'bounds': [0.1, 100], 'default': 20.0},
    {'key': 'ligands', 'unit': 'count', 'description': 'Ligand molecules per replicate', 'bounds': [10, 5000], 'default': 600, 'integer': True},
    {'key': 'receptors', 'unit': 'count', 'description': 'Membrane receptors (single binding site)', 'bounds': [1, 2000], 'default': 200, 'integer': True},
    {'key': 'reactionRadius', 'unit': 'µm', 'description': 'Doi reaction radius σ', 'bounds': [0.005, 0.5], 'default': 0.1},
    {'key': 'kon', 'unit': 'µm³/s', 'description': 'Association rate constant (hypothetical; 1 µm³/s ≈ 6.0×10⁸ M⁻¹s⁻¹)', 'bounds': [1e-4, 100], 'default': 1.0},
    {'key': 'koff', 'unit': '1/s', 'description': 'Dissociation rate constant (hypothetical)', 'bounds': [1e-3, 100], 'default': 1.0},
    {'key': 'dt', 'unit': 's', 'description': 'Time step Δt', 'bounds': [1e-6, 0.01], 'default': 2e-4},
    {'key': 'tEnd', 'unit': 's', 'description': 'Simulated time per replicate', 'bounds': [0.1, 60], 'default': 8.0},
    {'key': 'replicates', 'unit': 'count', 'description': 'Independent replicates (for the standard error)', 'bounds': [3, 32], 'default': 6, 'integer': True},
    {'key': 'seed', 'unit': '—', 'description': 'Random seed (PCG64)', 'bounds': [0, 2 ** 32 - 1], 'default': 20261031, 'integer': True},
]

SWEEP_DEFAULT = [0.5, 1.0, 2.0, 4.0, 8.0]
HYPOTHETICAL = {'kind': 'hypothetical', 'note': 'Generic value chosen to exercise the physics in a few seconds of simulated time; not a measurement of any receptor or ligand.'}


def environment():
    return {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__, 'platform': platform.platform(), 'engine': VERSION}


def _inputs(spec, p):
    out = {}
    for s in spec:
        value = p.get(s['key'], s['default'])
        out[s['key']] = bd.bounded(s['description'], value, *s['bounds'], s['unit'], s.get('integer', False))
    return out


def _described(spec, values):
    return {s['key']: {'value': values[s['key']], 'unit': s['unit'], 'description': s['description'], **({'provenance': HYPOTHETICAL} if s['key'] in ('kon', 'koff', 'diffusion', 'receptors', 'ligands') else {})} for s in spec}


def _check(name, passed, value, threshold, detail, applicable=True):
    return {'name': name, 'passed': bool(passed) if applicable else None, 'applicable': applicable, 'value': value, 'threshold': threshold, 'detail': detail}


def _r(a, digits=4):
    return np.round(np.asarray(a, float), digits).tolist()


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), default=float).encode()).hexdigest()


def _record(service, kind, evidence, statement, inputs, solver, outputs, benchmark, seed):
    body = {'schema': 'fold.research-record', 'schemaVersion': 1,
            'engine': {k: ENGINE[k] for k in ('id', 'name', 'version', 'numericalMethod')}, 'kind': kind,
            'evidence': {'category': evidence, 'name': 'Physics simulation', 'statement': statement},
            'created': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'inputs': inputs, 'solver': solver, 'outputs': outputs, 'benchmark': benchmark,
            'assumptions': ENGINE['assumptions'], 'limitations': ENGINE['limits']}
    digest = _sha({k: body[k] for k in ('inputs', 'solver', 'outputs')})
    body['reproducibility'] = {'deterministic': False, 'seed': seed, 'runtime': 'Python ' + platform.python_version() + ' · NumPy ' + np.__version__ + ' · SciPy ' + scipy.__version__,
                               'contentSha256': digest, 'note': 'Stochastic; bit-for-bit repeatable with the same seed, NumPy version and platform.'}
    body['id'] = uuid.uuid4().hex
    if service is not None:
        folder = pathlib.Path(service.root) / 'cell_physics' / 'runs'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (body['id'] + '.json')).write_text(json.dumps(body, default=float))
    return body


# ------------------------------------------------------------- Demo 1

def diffusion(p, service=None):
    v = _inputs(DIFFUSION_INPUTS, p)
    D, R, n, dt, T, seed = v['diffusion'], v['radius'], v['particles'], v['dt'], v['tEnd'], v['seed']
    steps = int(round(T / dt))
    if steps < 10:
        raise bd.BDError('Choose at least 10 time steps (t_end / Δt ≥ 10).')
    if 2 * n * steps > MAX_WORK:
        raise bd.BDError(f'{2 * n * steps:.3g} particle-steps exceed the admission limit of {MAX_WORK:.0e}; use fewer particles or a larger Δt.')
    step_rms = math.sqrt(2 * D * dt)
    if step_rms > 0.05 * R:
        raise bd.BDError(f'The rms step √(2DΔt) = {step_rms:.3g} µm exceeds 0.05 R = {0.05 * R:.3g} µm (validated domain for the reflecting wall). Reduce Δt.')
    every = max(1, steps // 120)
    free = bd.diffuse(D, dt, steps, n, bd.Domain.free(), seed, record_every=every)
    box = bd.diffuse(D, dt, steps, n, bd.Domain.sphere(R), seed + 1, record_every=every)
    t = free['time']
    checks = []
    # Free: D from an origin-constrained least-squares slope in 10 independent particle groups.
    tt = t[1:]
    slopes = (free['groups'] * tt[:, None]).sum(0) / (tt * tt).sum() / 6
    D_fit, D_se = float(slopes.mean()), float(slopes.std(ddof=1) / math.sqrt(len(slopes)))
    z = (D_fit - D) / D_se
    checks.append(_check('Free: fitted D', abs(z) < Z_LIMIT, {'D': D_fit, 'se': D_se, 'z': z, 'relativeError': D_fit / D - 1}, f'|z| < {Z_LIMIT:g}',
                         f'D = {D_fit:.4g} ± {D_se:.2g} µm²/s vs {D:g} (z = {z:.2f})'))
    se_end = free['msdSd'][-1] / math.sqrt(n)
    z = (free['msd'][-1] - 6 * D * t[-1]) / se_end
    checks.append(_check('Free: MSD(t_end) = 6Dt', abs(z) < Z_LIMIT, {'msd': float(free['msd'][-1]), 'expected': 6 * D * t[-1], 'se': float(se_end), 'z': float(z)}, f'|z| < {Z_LIMIT:g}',
                         f'{free["msd"][-1]:.4g} ± {se_end:.2g} µm² vs {6 * D * t[-1]:.4g} µm² (z = {z:.2f})'))
    dx = (free['final'] - free['start'])[:, 0] / math.sqrt(2 * D * t[-1])
    ks = stats.kstest(dx, 'norm')
    checks.append(_check('Free: Gaussian displacements', ks.pvalue > KS_ALPHA, {'ksStatistic': float(ks.statistic), 'p': float(ks.pvalue)}, f'p > {KS_ALPHA:g}',
                         f'KS D = {ks.statistic:.3g}, p = {ks.pvalue:.3g} (x-displacement / √(2Dt) vs N(0, 1))'))
    # Bounded sphere.
    rmax = float(np.linalg.norm(box['final'], axis=1).max())
    checks.append(_check('Sphere: containment', box['projected'] == 0 and rmax <= R * (1 + 1e-9), {'maxRadius': rmax, 'projected': box['projected'], 'reflections': box['reflections']}, 'r ≤ R, 0 fallback projections',
                         f'max r = {rmax:.6g} µm (R = {R:g}); {box["reflections"]} specular reflections, {box["projected"]} fallback projections'))
    # Before the wall is felt: from the centre, √(6Dt) ≤ 0.4 R leaves < 10⁻³ of particles able to reach r = R.
    early = (6 * D * t <= (0.4 * R) ** 2) & (t > 0)
    if early.any():
        ze = (box['msd'][early] - 6 * D * t[early]) / (box['msdSd'][early] / math.sqrt(n))
        checks.append(_check('Sphere: early MSD = 6Dt', float(np.abs(ze).max()) < Z_LIMIT, {'points': int(early.sum()), 'maxAbsZ': float(np.abs(ze).max())}, f'max |z| < {Z_LIMIT:g}',
                             f'{int(early.sum())} times with √(6Dt) ≤ 0.4 R; max |z| = {np.abs(ze).max():.2f}'))
    tau0 = R * R / (20.19 * D)
    plateau_ok = T >= 10 * tau0
    se_p = box['msdSd'][-1] / math.sqrt(n)
    zp = (box['msd'][-1] - 0.6 * R * R) / se_p
    checks.append(_check('Sphere: plateau 3/5 R²', abs(zp) < Z_LIMIT, {'msd': float(box['msd'][-1]), 'expected': 0.6 * R * R, 'se': float(se_p), 'z': float(zp), 'tau0': tau0}, f'|z| < {Z_LIMIT:g}',
                         f'{box["msd"][-1]:.4g} ± {se_p:.2g} µm² vs {0.6 * R * R:.4g} µm² (z = {zp:.2f})' if plateau_ok else f'Not applicable: t_end = {T:g} s < 10 τ₀ = {10 * tau0:.3g} s', plateau_ok))
    u = (np.linalg.norm(box['final'], axis=1) / R) ** 3
    ks = stats.kstest(u, 'uniform')
    checks.append(_check('Sphere: uniform radial density', ks.pvalue > KS_ALPHA, {'ksStatistic': float(ks.statistic), 'p': float(ks.pvalue)}, f'p > {KS_ALPHA:g}',
                         f'KS D = {ks.statistic:.3g}, p = {ks.pvalue:.3g} ((r/R)³ vs U(0, 1))' if plateau_ok else 'Not applicable before the plateau', plateau_ok))
    outputs = {'time': _r(t, 6), 'timeUnit': 's', 'lengthUnit': 'µm',
               'free': {'msd': _r(free['msd']), 'se': _r(free['msdSd'] / math.sqrt(n)), 'reference': _r(6 * D * t)},
               'sphere': {'msd': _r(box['msd']), 'se': _r(box['msdSd'] / math.sqrt(n)), 'plateau': 0.6 * R * R},
               'sampled': {'note': f'{free["track"].shape[0]} of {n} computed particles per scenario, every {every} steps; positions in µm.',
                           'free': _r(free['track'], 3), 'sphere': _r(box['track'], 3)}}
    solver = {'scheme': 'Euler–Maruyama, specular reflection', 'dt': dt, 'steps': steps, 'recordEvery': every, 'stepRms': step_rms, 'rng': 'NumPy PCG64',
              'seeds': {'free': seed, 'sphere': seed + 1}, 'start': 'all particles at the centre', 'environment': environment()}
    passed = all(c['passed'] is not False for c in checks)
    record = _record(service, 'diffusion', 'B', 'Numerical Brownian dynamics of ideal point particles with a stated D; validated against analytical diffusion results. Not a model of any specific molecule or cell.',
                     _described(DIFFUSION_INPUTS, v), solver, outputs, {'checks': checks, 'passed': passed}, seed)
    return {'record': record, 'checks': checks, 'passed': passed, 'inputs': v}


# ------------------------------------------------------------- Demo 2

def _ode_network(v, volume_um3, koff=None):
    """Well-mixed L + R ⇌ C as a Mechanistic Biology Lab network (nM, seconds)."""
    V_L = volume_um3 / bd.UM3_PER_LITRE
    nM = lambda count: count / (bd.AVOGADRO * V_L) * 1e9
    kon_nM = bd.kon_molar(v['kon']) * 1e-9
    return {'id': 'membrane_receptor_binding', 'name': 'Membrane receptor binding (well-mixed)', 'time': 'second',
            'compartments': [{'id': 'shell', 'name': 'Pericellular shell', 'size': V_L}],
            'species': [{'id': 'L', 'name': 'Free ligand', 'compartment': 'shell', 'initial': nM(v['ligands'])},
                        {'id': 'R', 'name': 'Free receptor', 'compartment': 'shell', 'initial': nM(v['receptors'])},
                        {'id': 'C', 'name': 'Complex', 'compartment': 'shell', 'initial': 0.0}],
            'parameters': [{'id': 'kon', 'value': kon_nM, 'unit': 'per_nM_per_time', 'provenance': HYPOTHETICAL},
                           {'id': 'koff', 'value': koff if koff is not None else v['koff'], 'unit': 'per_time', 'provenance': HYPOTHETICAL}],
            'components': [{'type': 'binding', 'id': 'binding', 'species': {'A': 'L', 'B': 'R', 'AB': 'C'}, 'parameters': {'kon': 'kon', 'koff': 'koff'}}]}, V_L


def _ode(v, volume_um3, t_end, points, koff=None):
    import mechanistic_sbml as sbml
    import mechanistic_library as lib
    import mechanistic_sim as sim
    network, V_L = _ode_network(v, volume_um3, koff)
    model = sbml.Model(lib.compose(network), {'kind': 'composed', 'name': network['name']})
    res = sim.simulate(model, t_end, points=points)
    count = np.array(res['series']['C']) * 1e-9 * bd.AVOGADRO * V_L
    return {'time': np.array(res['time']), 'complex': count, 'diagnostics': res['diagnostics'], 'solver': res['solver'], 'modelSha256': model.sha256,
            'konPerNanomolarSecond': network['parameters'][0]['value'], 'volumeLitre': V_L}


def relaxation(v, volume):
    """Linearised well-mixed relaxation rate and the start of the averaging window.

    k = koff + (kon/V)(L_eq + R_eq); the window starts after 6/k (e⁻⁶ ≈ 0.25 % of the
    initial deviation left) plus one shell diffusion time (R_outer − R_cell)²/D."""
    C = bd.mean_field_equilibrium(v['ligands'], v['receptors'], v['kon'] / v['koff'], volume)
    k = v['koff'] + v['kon'] / volume * (v['ligands'] - C + v['receptors'] - C)
    return k, 6 / k + (v['outerRadius'] - v['membraneRadius']) ** 2 / v['diffusion']


def shell_volume(v):
    return bd.Domain.shell(v['membraneRadius'], v['outerRadius']).volume()


def _validate_binding(v, out, ode):
    nL, nR = v['ligands'], v['receptors']
    K, V = v['kon'] / v['koff'], out['volume']
    k_relax, window = relaxation(v, V)
    t, bound = out['time'], out['bound']
    late = t >= min(window, t[-1])
    per_rep = bound[:, late].mean(1)
    exact, exact_sd = bd.exact_equilibrium(nL, nR, K, V)
    # Standard error of the time-averaged occupancy: the larger of the between-replicate estimate
    # (few degrees of freedom, so itself noisy) and the fluctuation-theory value
    # √(Var(n)·2τ/(T·replicates)) with τ = 1/k, the well-mixed correlation time.
    mean, se_rep = float(per_rep.mean()), float(per_rep.std(ddof=1) / math.sqrt(len(per_rep)))
    span = max(float(t[late][-1] - t[late][0]), 1e-12)
    se_theory = math.sqrt(exact_sd ** 2 * 2 / k_relax / span / len(per_rep))
    se = max(se_rep, se_theory, 1e-12)
    mf = bd.mean_field_equilibrium(nL, nR, K, V)
    ode_eq = float(ode['complex'][-1])
    # Applicability: the averaging window must start after relaxation and cover at least 2/k.
    applicable = v['tEnd'] - window >= 2 / k_relax
    checks = [
        _check('Bookkeeping', out['consistent'] and out['events']['binding'] - out['events']['unbinding'] == int(bound[:, -1].sum()) and out['events']['projected'] == 0,
               {'binding': out['events']['binding'], 'unbinding': out['events']['unbinding'], 'boundAtEnd': int(bound[:, -1].sum())}, 'exact',
               f"{out['events']['binding']} binding − {out['events']['unbinding']} unbinding events = {int(bound[:, -1].sum())} complexes at the end; receptor and ligand records agree"),
        _check('ODE converged to mass-action equilibrium', abs(ode_eq - mf) / mf < 1e-3 and ode['diagnostics'].get('reliable', True),
               {'ode': ode_eq, 'analytic': mf, 'relative': abs(ode_eq - mf) / mf}, '< 1e-3', f'Mechanistic engine C(t_end) = {ode_eq:.5g}; analytic root {mf:.5g}', applicable),
    ]
    z_exact, z_ode = (mean - exact) / se, (mean - ode_eq) / se
    checks.append(_check('Equilibrium vs exact ensemble', abs(z_exact) < Z_LIMIT, {'bd': mean, 'se': se, 'exact': exact, 'z': z_exact}, f'|z| < {Z_LIMIT:g}',
                         f'BD {mean:.4g} ± {se:.2g} vs exact {exact:.4g} complexes (z = {z_exact:.2f}), averaged over {window:.3g}–{v["tEnd"]:g} s' if applicable else f'Not applicable: relaxation (6/k + shell diffusion time = {window:.3g} s) leaves less than 2/k = {2 / k_relax:.3g} s to average before t_end; run longer', applicable))
    checks.append(_check('Equilibrium vs well-mixed ODE', abs(z_ode) < Z_LIMIT, {'bd': mean, 'se': se, 'ode': ode_eq, 'z': z_ode, 'finiteSizeGap': exact - ode_eq}, f'|z| < {Z_LIMIT:g}',
                         f'BD {mean:.4g} ± {se:.2g} vs ODE {ode_eq:.4g} (z = {z_ode:.2f}); exact − mean-field = {exact - ode_eq:.3g} complexes' if applicable else 'Not applicable (see above)', applicable))
    return checks, {'bd': mean, 'se': se, 'exact': exact, 'exactSd': exact_sd, 'meanField': mf, 'ode': ode_eq, 'occupancy': mean / nR, 'occupancySe': se / nR,
                    'odeOccupancy': ode_eq / nR, 'seReplicates': se_rep, 'seTheory': se_theory, 'window': [window, v['tEnd']], 'relaxationRate': k_relax, 'perReplicate': per_rep.tolist()}


def _binding_inputs(p):
    v = _inputs(BINDING_INPUTS, p)
    if v['outerRadius'] <= v['membraneRadius'] + 2 * v['reactionRadius']:
        raise bd.BDError('The outer wall must lie beyond the membrane by more than 2σ.')
    step_rms = math.sqrt(2 * v['diffusion'] * v['dt'])
    if step_rms > v['reactionRadius']:
        raise bd.BDError(f'The rms step √(2DΔt) = {step_rms:.3g} µm exceeds σ = {v["reactionRadius"]:g} µm; reduce Δt so the reaction volume is resolved.')
    if step_rms > 0.05 * (v['outerRadius'] - v['membraneRadius']):
        raise bd.BDError('The rms step exceeds 5 % of the shell thickness; reduce Δt.')
    return v, step_rms


def binding(p, service=None):
    v, step_rms = _binding_inputs(p)
    steps = int(round(v['tEnd'] / v['dt']))
    if v['ligands'] * v['replicates'] * steps > MAX_WORK:
        raise bd.BDError(f"{v['ligands'] * v['replicates'] * steps:.3g} particle-steps exceed the admission limit of {MAX_WORK:.0e}.")
    out = bd.bind(v, v['seed'], record_every=max(1, steps // 200))
    ode = _ode(v, out['volume'], v['tEnd'], len(out['time']))
    checks, eq = _validate_binding(v, out, ode)
    mean = out['bound'].mean(0)
    se = out['bound'].std(0, ddof=1) / math.sqrt(v['replicates'])
    kinetic = float(np.max(np.abs(mean - np.interp(out['time'], ode['time'], ode['complex']))) / max(eq['ode'], 1e-12))
    kD = 2 * math.pi * v['diffusion'] * v['reactionRadius']
    outputs = {'time': _r(out['time'], 6), 'timeUnit': 's', 'lengthUnit': 'µm',
               'occupancy': {'mean': _r(mean / v['receptors'], 5), 'se': _r(se / v['receptors'], 5), 'replicates': _r(out['bound'] / v['receptors'], 4)},
               'ode': {'time': _r(ode['time'], 6), 'occupancy': _r(ode['complex'] / v['receptors'], 6)},
               'equilibrium': eq,
               'kinetics': {'maxDeviationFromOde': kinetic, 'collinsKimballFactor': kD / (kD + v['kon']),
                            'note': 'Informative only: BD association is diffusion-influenced (Collins–Kimball factor kD/(kD + kon) with kD ≈ 2πDσ for a membrane-bound target), so the transient differs from the well-mixed ODE; the equilibrium does not.'},
               'derived': {'reactionVolume': out['reactionVolume'], 'lambda': out['lambda'], 'pOn': out['pOn'], 'pOff': out['pOff'], 'volume': out['volume'], 'receptorSpacing': out['spacing'],
                           'konMolar': bd.kon_molar(v['kon']), 'kdMolar': v['koff'] / bd.kon_molar(v['kon']), 'K': v['kon'] / v['koff']},
               'events': out['events'],
               'sampled': {'note': f"{out['track'].shape[0]} of {v['ligands']} ligands from replicate 1; positions in µm; bound ligands sit on their receptor.",
                           'track': _r(out['track'], 3), 'bound': out['trackBound'].astype(int).tolist(), 'receptors': _r(out['receptors'], 3), 'receptorsBound': out['framesBound']}}
    solver = {'scheme': 'Euler–Maruyama + specular reflection + Doi binding (detailed-balance form)', 'dt': v['dt'], 'steps': steps, 'stepRms': step_rms, 'rng': 'NumPy PCG64',
              'averagingWindow': eq['window'], 'ode': {**ode['solver'], 'engine': 'Mechanistic Biology Lab (mechanistic_sbml + mechanistic_sim)', 'modelSha256': ode['modelSha256'],
                                                             'diagnostics': ode['diagnostics'], 'konPerNanomolarSecond': ode['konPerNanomolarSecond'], 'volumeLitre': ode['volumeLitre']},
              'environment': environment()}
    passed = all(c['passed'] is not False for c in checks)
    record = _record(service, 'binding', 'B', 'Brownian dynamics of an idealised ligand–receptor system with hypothetical kon/koff; equilibrium validated against exact and well-mixed results. No physiological claim.',
                     _described(BINDING_INPUTS, v), solver, outputs, {'checks': checks, 'passed': passed}, v['seed'])
    return {'record': record, 'checks': checks, 'passed': passed, 'inputs': v}


def binding_sweep(p, service=None):
    base = {**p}
    values = p.get('koffValues') or SWEEP_DEFAULT
    if not isinstance(values, list) or not 2 <= len(values) <= 8:
        raise bd.BDError('Give 2–8 koff values.')
    base.setdefault('replicates', 3)
    base.setdefault('tEnd', 4.0)
    rows, plan = [], []
    v0, _ = _binding_inputs({**base, 'koff': values[0]})
    for i, koff in enumerate(values):
        v, _ = _binding_inputs({**base, 'koff': koff, 'seed': v0['seed'] + 1000 * i})
        # Slow koff relaxes slowly: extend t_end so every point has an averaging window (cap 60 s).
        v['tEnd'] = min(60.0, max(v['tEnd'], 2 * relaxation(v, shell_volume(v))[1]))
        plan.append(v)
    work = sum(v['ligands'] * v['replicates'] * round(v['tEnd'] / v['dt']) for v in plan)
    if work > 2 * MAX_WORK:
        raise bd.BDError(f'The sweep needs {work:.3g} particle-steps, above the limit of {2 * MAX_WORK:.0e}; use fewer values, replicates or ligands.')
    for v in plan:
        steps = int(round(v['tEnd'] / v['dt']))
        out = bd.bind(v, v['seed'], record_every=max(1, steps // 100), sampled=0)
        ode = _ode(v, out['volume'], v['tEnd'], len(out['time']))
        checks, eq = _validate_binding(v, out, ode)
        rows.append({'koff': v['koff'], 'tEnd': v['tEnd'], 'kdMolar': v['koff'] / bd.kon_molar(v['kon']), **{k: eq[k] for k in ('bd', 'se', 'exact', 'ode', 'occupancy', 'occupancySe', 'odeOccupancy')},
                     'checks': checks, 'passed': all(c['passed'] is not False for c in checks), 'seed': v['seed']})
    # The ODE equilibrium on a fine koff grid for the overlay curve.
    grid = np.geomspace(min(values), max(values), 40)
    curve = [bd.mean_field_equilibrium(v0['ligands'], v0['receptors'], v0['kon'] / k, out['volume']) / v0['receptors'] for k in grid]
    outputs = {'rows': rows, 'curve': {'koff': _r(grid, 6), 'occupancy': _r(curve, 6)}}
    passed = all(r['passed'] for r in rows)
    inputs = _described(BINDING_INPUTS, {**v0, 'koff': None})
    inputs['koff'] = {'value': [float(x) for x in values], 'unit': '1/s', 'description': 'Swept dissociation rate constants (hypothetical)', 'provenance': HYPOTHETICAL}
    solver = {'scheme': 'As cell_physics_binding, one run per koff', 'seeds': [r['seed'] for r in rows], 'environment': environment()}
    record = _record(service, 'binding_sweep', 'B', 'koff sweep of the idealised binding model; each point validated against exact and well-mixed equilibria.', inputs, solver, outputs, {'passed': passed}, v0['seed'])
    return {'record': record, 'passed': passed}


def catalog():
    return {'engine': ENGINE, 'demos': {
        'diffusion': {'name': 'Demo 1 · Bounded diffusion in a virtual cell', 'inputs': DIFFUSION_INPUTS},
        'binding': {'name': 'Demo 2 · Reversible membrane receptor binding', 'inputs': BINDING_INPUTS, 'sweepDefault': SWEEP_DEFAULT}},
        'environment': environment()}


def runs(service):
    folder = pathlib.Path(service.root) / 'cell_physics' / 'runs'
    if not folder.exists():
        return []
    files = sorted(folder.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:30]
    out = []
    for f in files:
        r = json.loads(f.read_text())
        out.append({'id': r['id'], 'kind': r['kind'], 'created': r['created'], 'passed': r['benchmark'].get('passed'), 'sha256': r['reproducibility']['contentSha256']})
    return out


def dispatch(service, action, p):
    try:
        if action == 'cell_physics_catalog': return catalog()
        if action == 'cell_physics_diffusion': return diffusion(p or {}, service)
        if action == 'cell_physics_binding': return binding(p or {}, service)
        if action == 'cell_physics_sweep': return binding_sweep(p or {}, service)
        if action == 'cell_physics_runs': return runs(service)
    except bd.BDError as e:
        raise ValueError(str(e))
    raise ValueError('Unsupported cell physics action.')
