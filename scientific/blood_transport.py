"""Blood & Circulation Laboratory, Demo 6: tracer transport in a modelled plasma vessel.

Axisymmetric (r, z) finite-volume solution, in the laboratory frame, of

    ∂c/∂t + u(r) ∂c/∂z = D [ (1/r) ∂/∂r (r ∂c/∂r) + ∂²c/∂z² ]

for a dilute passive tracer in a straight rigid cylinder of radius R carrying
steady Poiseuille flow of a Newtonian, cell-free fluid (plasma only). The
velocity profile is itself computed: the axisymmetric Stokes equation
(1/r) d/dr (r du/dr) = (1/μ) dp/dz is solved on the same radial rings and its
error against the analytic profile 2U(1 − r²/R²) is reported.

Boundaries: symmetry at r = 0; wall either impermeable or permeable with an
explicit Robin condition −D ∂c/∂r = P c at r = R (outward loss into a perfect
sink); inlet z = 0 carries the advective flux u·c_in(t) (Danckwerts, zero
diffusive flux) for a step or a Gaussian pulse, or is closed for the slug
(validation) experiments; outlet z = L is advective outflow.

Numerics: per-ring flux-limited Lax–Wendroff advection (van Leer) with explicit
central axial diffusion; Crank–Nicolson radial diffusion with the wall Robin
term, solved by a pre-factorised LU; Strang splitting radial ½Δt → axial Δt →
radial ½Δt. Δt comes from the Courant and axial-diffusion limits, and every
stability number is reported. Every flux through every boundary is accumulated
exactly as the scheme applies it, so the budget mass(t) − mass(0) + out − in
closes to round-off.

Evidence: physics-simulated (category B) for the idealised model. Plasma-like
presets are parameterised scenarios (category D): this is a modelled vessel,
not validated human circulation, and nothing here is a clinical or dosing claim.
"""
import hashlib, json, math, platform, time

import numpy as np
import scipy
from scipy import linalg, special, optimize

from blood_transport_actions import ACTIONS

ENGINE = {'id': 'fold.blood.plasma-transport-axisymmetric', 'name': 'Plasma tracer transport (axisymmetric FV, lab frame)', 'version': '1.0.0'}
FMOL = 1e-15
MAX_CELL_STEPS = 4e8

INPUTS = [  # key, unit, description, lower, upper
    ('radiusUm', 'µm', 'Vessel radius R', 0.5, 2000.0),
    ('lengthUm', 'µm', 'Vessel (domain) length L', 5.0, 2e5),
    ('meanVelocityMmPerS', 'mm/s', 'Cross-section mean plasma velocity U (0 = pure diffusion)', 0.0, 500.0),
    ('diffusivityUm2PerS', 'µm²/s', 'Tracer molecular diffusivity D', 0.1, 1e5),
    ('wallPermeabilityUmPerS', 'µm/s', 'Wall permeability P (0 = impermeable wall)', 0.0, 1e5),
    ('durationS', 's', 'Simulated time', 1e-5, 1e4),
    ('inletAmplitude', 'mol/m³', 'Inlet concentration (step level, pulse peak) or slug cross-section mean peak', 1e-12, 1e6),
    ('pulseCentreS', 's', 'Inlet pulse centre time t₀', 0.0, 1e4),
    ('pulseWidthS', 's', 'Inlet pulse standard deviation σ_t', 1e-6, 1e4),
    ('slugCentreUm', 'µm', 'Slug centre z₀ (slug mode)', 0.0, 2e5),
    ('slugWidthUm', 'µm', 'Slug standard deviation σ₀ (slug mode)', 0.05, 1e5),
    ('plasmaViscosityMPaS', 'mPa·s', 'Plasma dynamic viscosity μ (for the pressure gradient and wall shear stress only)', 0.3, 10.0),
    ('radialCells', '1', 'Radial finite volumes', 4, 96),
    ('axialCells', '1', 'Axial finite volumes', 20, 4000),
]
INLETS = ('step', 'pulse', 'slug')
LIMITERS = {
    'van-leer': lambda t: (t + np.abs(t)) / (1 + np.abs(t)),
    'monotonized-central': lambda t: np.maximum(0, np.minimum(np.minimum(2 * t, (1 + t) / 2), 2)),
    'minmod': lambda t: np.maximum(0, np.minimum(1, t)),
    'upwind': lambda t: np.zeros_like(t),
}

ASSUMPTIONS = [
    'Plasma only: hematocrit is 0; no red cells, platelets or leukocytes, so no cell-free layer, plasma skimming, Fåhræus or Fåhræus–Lindqvist effect.',
    'Newtonian, incompressible fluid with constant viscosity; steady, fully developed laminar Poiseuille flow (no entrance length, no pulsatility).',
    'Rigid, straight, circular vessel wall; no compliance, branching, curvature or roughness.',
    'Dilute passive tracer: no binding to plasma proteins, no reaction, no buoyancy; constant isotropic molecular diffusivity.',
    'Permeable wall (if P > 0) is a linear Robin condition into a perfect sink; no tissue compartment, back-flux, convective (Starling) filtration or saturable transport.',
    'Inlet is cross-sectionally uniform with zero diffusive flux (Danckwerts); outlet is advective outflow only.',
]
LIMITS = [
    'This is a modelled vessel. It is not validated human circulation and makes no physiological, pharmacokinetic, clinical or dosing claim.',
    'Not valid for whole blood (hematocrit > 0), red-cell single-file flow in capillaries below ~8 µm diameter, non-Newtonian rheology, pulsatile arterial flow, turbulence or vessel networks.',
    'Wall permeability is a model parameter, not a measured endothelial property; the wall-loss benchmark verifies the numerics only.',
    'Validated domain is the set of benchmark cases below at the stated resolutions; other parameters run but are unverified.',
]
EQUATIONS = [
    '∂c/∂t + u(r) ∂c/∂z = D[(1/r)∂/∂r(r ∂c/∂r) + ∂²c/∂z²]',
    '(1/r) d/dr(r du/dr) = (1/μ) dp/dz, u(R) = 0, du/dr(0) = 0  →  u = 2U(1 − r²/R²), dp/dz = −8μU/R²',
    'r = 0: ∂c/∂r = 0;  r = R: −D ∂c/∂r = P c (P = 0: no flux)',
    'z = 0: flux = u(r)·c_in(t) (step / Gaussian pulse) or closed (slug);  z = L: advective outflow (closed for slug)',
]
METHOD = ('Axisymmetric finite volume in the laboratory frame; per-ring flux-limited Lax–Wendroff advection with explicit central axial diffusion; '
          'Crank–Nicolson radial diffusion including the wall Robin term (pre-factorised LU); Strang splitting radial ½Δt → axial Δt → radial ½Δt. '
          'Velocity from a finite-volume solve of the axisymmetric Stokes equation.')

PRESETS = [
    {'id': 'taylor-aris', 'label': 'Validation · Taylor–Aris (Pe = 20)', 'evidence': 'B',
     'note': 'Verification case: a cross-sectionally uniform slug in a closed tube, chosen so shear dispersion dominates. Not a vessel.',
     'inputs': {'radiusUm': 5, 'lengthUm': 700, 'meanVelocityMmPerS': 4, 'diffusivityUm2PerS': 1000, 'wallPermeabilityUmPerS': 0, 'durationS': 0.1,
                'inletMode': 'slug', 'inletAmplitude': 1, 'pulseCentreS': 0, 'pulseWidthS': 0.01, 'slugCentreUm': 150, 'slugWidthUm': 20,
                'plasmaViscosityMPaS': 1.2, 'radialCells': 24, 'axialCells': 500, 'particles': 4000, 'seed': 7}},
    {'id': 'arteriole-pulse', 'label': 'Plasma arteriole · inlet pulse', 'evidence': 'D',
     'note': 'Parameterised scenario: radius 15 µm and 2 mm/s are literature magnitudes for a small arteriole; D = 60 µm²/s is an albumin-sized tracer. Plasma only (hematocrit 0), Newtonian, rigid wall.',
     'inputs': {'radiusUm': 15, 'lengthUm': 1500, 'meanVelocityMmPerS': 2, 'diffusivityUm2PerS': 60, 'wallPermeabilityUmPerS': 0, 'durationS': 1.2,
                'inletMode': 'pulse', 'inletAmplitude': 1, 'pulseCentreS': 0.1, 'pulseWidthS': 0.03, 'slugCentreUm': 0, 'slugWidthUm': 20,
                'plasmaViscosityMPaS': 1.2, 'radialCells': 24, 'axialCells': 300, 'particles': 4000, 'seed': 7}},
    {'id': 'permeable-step', 'label': 'Plasma venule · step + permeable wall', 'evidence': 'D',
     'note': 'Parameterised scenario: a small solute (D = 800 µm²/s) entering a 10 µm-radius plasma-filled tube whose wall leaks with an assumed P = 2 µm/s. P is a model parameter, not a measured endothelial value.',
     'inputs': {'radiusUm': 10, 'lengthUm': 600, 'meanVelocityMmPerS': 0.5, 'diffusivityUm2PerS': 800, 'wallPermeabilityUmPerS': 2, 'durationS': 2,
                'inletMode': 'step', 'inletAmplitude': 1, 'pulseCentreS': 0, 'pulseWidthS': 0.01, 'slugCentreUm': 0, 'slugWidthUm': 20,
                'plasmaViscosityMPaS': 1.2, 'radialCells': 20, 'axialCells': 200, 'particles': 4000, 'seed': 7}},
]

BENCHMARKS = [
    {'name': 'Mass conservation (closed, impermeable)', 'reference': 'Finite-volume flux balance', 'acceptance': 'max |M(t) − M(0)|/M(0) ≤ 1e-12'},
    {'name': 'Boundary budget (open, permeable)', 'reference': 'M(t) − M(0) − ∫(in − out − wall) dt = 0', 'acceptance': 'relative residual ≤ 1e-12'},
    {'name': 'Taylor–Aris dispersion', 'reference': 'Taylor 1953 Proc. R. Soc. A 219:186; Aris 1956 Proc. R. Soc. A 235:67', 'acceptance': '|K_num − D(1+Pe²/48)| / K_TA ≤ 1%'},
    {'name': 'Cross-check against the in-app Demo D solver', 'reference': 'src/lib/taylorAris.ts (co-moving axisymmetric FV)', 'acceptance': 'K within 1%, cross-section profile L1 difference ≤ 2%'},
    {'name': 'Pure diffusion', 'reference': 'Gaussian σ² = σ₀² + 2Dt', 'acceptance': 'max |c̄ − c̄_exact| / max c̄_exact ≤ 0.5%'},
    {'name': 'Permeable-wall decay', 'reference': 'Bessel eigen-series, λ J₁(λ) = Bi J₀(λ), Bi = PR/D', 'acceptance': 'retained mass within 0.5% (relative) of the series'},
    {'name': 'Velocity field', 'reference': 'u = 2U(1 − r²/R²), dp/dz = −8μU/R²', 'acceptance': 'FV Stokes error ≤ 2e-3 of u_max at 24 rings, order ≥ 1.8; discrete flow rate exact'},
    {'name': 'Grid convergence', 'reference': 'Richardson extrapolation on three grids (r = 2)', 'acceptance': 'observed order ≥ 1.5 and finest-grid error decreasing monotonically'},
]


class TransportError(ValueError):
    pass


def environment():
    return {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__, 'machine': platform.machine()}


def defaults():
    return dict(PRESETS[0]['inputs'])


def check(inputs):
    p = {**defaults(), **(inputs or {})}
    for key, unit, description, lo, hi in INPUTS:
        v = p.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < lo or v > hi:
            raise TransportError(f'{description} must be a number from {lo:g} to {hi:g} {unit}.')
    for key in ('radialCells', 'axialCells'):
        if int(p[key]) != p[key]: raise TransportError('Cell counts must be whole numbers.')
        p[key] = int(p[key])
    if p.get('inletMode') not in INLETS: raise TransportError('Inlet mode must be step, pulse or slug.')
    if p['inletMode'] == 'slug' and not (0 <= p['slugCentreUm'] <= p['lengthUm']):
        raise TransportError('The slug centre must lie inside the vessel.')
    return p


def stokes_fv(R, Nr):
    """Finite-volume solve of (1/r)(r u')' = G/μ on Nr rings with u(R) = 0, normalised to unit mean velocity.

    Used to verify the velocity field: returns the computed centre values and the computed G/μ (both for U = 1)."""
    dr = R / Nr
    faces = np.arange(Nr + 1) * dr
    area = np.pi * (faces[1:] ** 2 - faces[:-1] ** 2)
    A = np.zeros((Nr, Nr))
    for i in range(Nr):
        if i > 0:
            g = 2 * np.pi * faces[i] / dr; A[i, i - 1] += g; A[i, i] -= g
        if i < Nr - 1:
            g = 2 * np.pi * faces[i + 1] / dr; A[i, i + 1] += g; A[i, i] -= g
        else:
            A[i, i] -= 2 * np.pi * R / (dr / 2)        # wall no-slip half a cell beyond the last centre
    u = np.linalg.solve(A, area)                       # G/μ = 1
    scale = np.pi * R * R / float(np.sum(area * u))    # rescale to unit mean velocity (flow rate πR²)
    return u * scale, scale


def stokes_velocity(R, U, mu, Nr):
    """Velocity field for the transport solver.

    The steady axisymmetric Stokes equation has the exact Poiseuille solution u = 2U(1 − r²/R²) with dp/dz = −8μU/R²;
    the transport solver uses its exact ring averages (so the discrete flow rate is exactly πR²U). The same equation is
    also solved by finite volumes on the transport rings and the difference is reported, so the field is a verified
    solution, not an assumed shape."""
    dr = R / Nr
    faces = np.arange(Nr + 1) * dr
    centres = (np.arange(Nr) + 0.5) * dr
    area = np.pi * (faces[1:] ** 2 - faces[:-1] ** 2)
    a, b = faces[:-1], faces[1:]
    ring = 2 * U * (1 - (a * a + b * b) / (2 * R * R))
    point = 2 * U * (1 - centres ** 2 / R ** 2)
    fv, g = stokes_fv(R, Nr)
    exact_g = -8 / R ** 2
    q = float(np.sum(area * ring))
    return {'ringVelocity': ring, 'centres': centres, 'pointVelocity': point, 'fvPointVelocity': fv * U,
            'pressureGradientPaPerM': -8 * mu * U / R ** 2, 'wallShearStressPa': 4 * mu * U / R,
            'fvRelativeError': float(np.max(np.abs(fv - 2 * (1 - centres ** 2 / R ** 2))) / 2),
            'fvPressureGradientRelativeError': float(abs(g - exact_g) / abs(exact_g)),
            'flowRateRelativeError': abs(q - np.pi * R * R * U) / (np.pi * R * R * U) if U > 0 else 0.0}


def _inlet(p, t):
    if p['inletMode'] == 'step': return p['inletAmplitude']
    if p['inletMode'] == 'pulse': return p['inletAmplitude'] * math.exp(-0.5 * ((t - p['pulseCentreS']) / p['pulseWidthS']) ** 2)
    return 0.0


def solve(inputs, settings=None, frames=36, samples=240, particles=None):
    """Run one experiment. Returns a JSON-serialisable result with fields, time series, budget and stability checks."""
    p = check(inputs)
    s = {'limiter': 'van-leer', 'courant': 0.4, 'axialDiffusionNumber': 0.25, 'radialImplicitness': 0.5, **(settings or {})}
    if s['limiter'] not in LIMITERS: raise TransportError('Unknown flux limiter.')
    theta = float(s['radialImplicitness'])
    if not 0.5 <= theta <= 1: raise TransportError('Radial implicitness must be from 0.5 (Crank–Nicolson) to 1 (backward Euler).')
    if not 0 < s['courant'] <= 0.9: raise TransportError('Courant number must be in (0, 0.9].')
    if not 0 < s['axialDiffusionNumber'] <= 0.5: raise TransportError('Axial diffusion number must be in (0, 0.5].')
    R, L = p['radiusUm'] * 1e-6, p['lengthUm'] * 1e-6
    U, D, P, T = p['meanVelocityMmPerS'] * 1e-3, p['diffusivityUm2PerS'] * 1e-12, p['wallPermeabilityUmPerS'] * 1e-6, p['durationS']
    mu = p['plasmaViscosityMPaS'] * 1e-3
    Nr, Nz = p['radialCells'], p['axialCells']
    dr, dz = R / Nr, L / Nz
    flow = stokes_velocity(R, U, mu, Nr)
    w = flow['ringVelocity']
    faces = np.arange(Nr + 1) * dr
    area = np.pi * (faces[1:] ** 2 - faces[:-1] ** 2)
    perim = 2 * np.pi * faces
    xs = np.pi * R * R
    z = (np.arange(Nz) + 0.5) * dz
    wmax = float(np.max(np.abs(w))) if U > 0 else 0.0
    limits = [s['axialDiffusionNumber'] * dz * dz / D]
    if wmax > 0: limits.append(s['courant'] * dz / wmax)
    if p['inletMode'] == 'pulse': limits.append(p['pulseWidthS'] / 20)
    steps = max(1, math.ceil(T / min(limits)))
    dt = T / steps
    if steps * Nr * Nz > MAX_CELL_STEPS:
        raise TransportError(f'This run needs {steps:,} steps on {Nr * Nz:,} cells; reduce the duration or resolution (limit {MAX_CELL_STEPS:.0e} cell-steps).')
    stability = {
        'courant': {'value': wmax * dt / dz, 'limit': 0.9, 'requested': s['courant'], 'meaning': 'u_max Δt / Δz (explicit advection)'},
        'axialDiffusionNumber': {'value': D * dt / dz ** 2, 'limit': 0.5, 'requested': s['axialDiffusionNumber'], 'meaning': 'D Δt / Δz² (explicit axial diffusion)'},
        'radialDiffusionNumber': {'value': D * dt / dr ** 2, 'limit': None, 'meaning': 'D Δt / Δr² (implicit, unconditionally stable; large values cost accuracy, not stability)'},
        'cellPeclet': {'value': wmax * dz / D, 'limit': None, 'meaning': 'u_max Δz / D; > 2 would oscillate with central advection, the TVD limiter keeps the solution monotone'},
        'peclet': {'value': U * R / D, 'meaning': 'U R / D (radial Péclet number, Taylor–Aris)'},
        'axialPeclet': {'value': U * L / D, 'meaning': 'U L / D (vessel-length Péclet number)'},
        'wallBiot': {'value': P * R / D, 'meaning': 'P R / D (wall loss vs radial diffusion)'},
    }
    stability['pass'] = stability['courant']['value'] <= 0.9 + 1e-12 and stability['axialDiffusionNumber']['value'] <= 0.5 + 1e-12
    warnings = []
    if stability['cellPeclet']['value'] > 2:
        warnings.append(f"Cell Péclet number {stability['cellPeclet']['value']:.3g} > 2: the TVD limiter keeps the solution monotone, but limiter (numerical) axial diffusion "
                        'can be comparable to physical axial spreading; repeat with more axial cells to confirm the result is grid-independent.')
    if U > 0 and T < R * R / D:
        warnings.append('Duration is shorter than the radial diffusion time R²/D, so the plume has not reached the Taylor–Aris regime.')
    if 2 * R / dz > 50 and Nr < 16:
        warnings.append('Few radial cells for this vessel; radial gradients near the wall may be under-resolved.')
    stability['warnings'] = warnings

    # Initial condition (mol/m³ per ring × axial cell).
    c = np.zeros((Nr, Nz))
    if p['inletMode'] == 'slug':
        z0, s0 = p['slugCentreUm'] * 1e-6, p['slugWidthUm'] * 1e-6
        c[:] = p['inletAmplitude'] * np.exp(-0.5 * ((z - z0) / s0) ** 2)[None, :]
    closed = p['inletMode'] == 'slug'

    # Radial θ-method half step: (Aᵢ − τ M) cⁿ⁺ = (Aᵢ + (½Δt − τ) M) cⁿ, M the conductance matrix including wall loss.
    cond = D * perim / dr                             # interior face conductances (per unit length)
    P_eff = P * 2 * D / (2 * D + P * dr) if P > 0 else 0.0   # wall concentration eliminated through the half cell
    wall_g = P_eff * perim[Nr]
    M = np.zeros((Nr, Nr))
    for i in range(Nr):
        if i > 0: M[i, i - 1] += cond[i]; M[i, i] -= cond[i]
        if i < Nr - 1: M[i, i + 1] += cond[i + 1]; M[i, i] -= cond[i + 1]
    M[Nr - 1, Nr - 1] -= wall_g
    half = dt / 2
    lhs = linalg.lu_factor(np.diag(area) - theta * half * M)
    rhs_op = np.diag(area) + (1 - theta) * half * M

    def radial(c):
        old = c[Nr - 1].copy()
        new = linalg.lu_solve(lhs, rhs_op @ c)
        wall = float(half * wall_g * np.sum(theta * new[Nr - 1] + (1 - theta) * old) * dz)   # mol lost through the wall
        return new, wall

    phi = LIMITERS[s['limiter']]
    nu = (w * dt / dz)[:, None]
    wcol = w[:, None]

    def axial(c, cin):
        F = np.zeros((Nr, Nz + 1))                    # flux density (mol/m²/s) at axial faces, per ring
        jump = c[:, 1:] - c[:, :-1]
        back = np.empty_like(jump)
        back[:, 1:] = c[:, 1:-1] - c[:, :-2]
        back[:, 0] = c[:, 0] - (cin if not closed else c[:, 0])
        with np.errstate(divide='ignore', invalid='ignore'):
            r = np.where(jump != 0, back / np.where(jump != 0, jump, 1), 0.0)
        F[:, 1:-1] = wcol * c[:, :-1] + 0.5 * wcol * (1 - nu) * phi(r) * jump - D * jump / dz
        if not closed:
            F[:, 0] = w * cin
            F[:, -1] = w * c[:, -1]
        inflow = float(np.sum(area * F[:, 0])) * dt
        outflow = float(np.sum(area * F[:, -1])) * dt
        return c - dt / dz * (F[:, 1:] - F[:, :-1]), inflow, outflow

    def mass(c): return float(np.sum(area[:, None] * c)) * dz

    def mean(c): return (area @ c) / xs

    def cup(c): return (area * w) @ c / (xs * U) if U > 0 else mean(c)

    frame_every = max(1, steps // max(1, frames - 1))
    sample_every = max(1, steps // max(1, samples))
    keep_r = np.linspace(0, Nr - 1, min(Nr, 24)).round().astype(int)
    keep_z = np.linspace(0, Nz - 1, min(Nz, 140)).round().astype(int)
    m0 = mass(c)
    budget = {'in': 0.0, 'out': 0.0, 'wall': 0.0}   # mol, accumulated exactly as the scheme applies each flux
    series, frame_list = [], []

    def moments(cm):
        m = float(np.sum(cm)) * dz * xs
        if m <= 0: return m, None, None
        centre = float(np.sum(cm * z) / np.sum(cm))
        return m, centre, float(np.sum(cm * (z - centre) ** 2) / np.sum(cm))

    def sample(t, c, flux=None):
        cm = mean(c)
        m, centre, var = moments(cm)
        series.append({'t': t, 'massMol': m, 'centroidM': centre, 'varianceM2': var,
                       'inletFluxMolPerS': flux[0] if flux else (xs * U * _inlet(p, t) if not closed else 0.0),
                       'outletFluxMolPerS': flux[1] if flux else (float(np.sum(area * w * c[:, -1])) if not closed else 0.0),
                       'wallFluxMolPerS': flux[2] if flux else float(wall_g * np.sum(c[Nr - 1]) * dz),
                       'cumulativeInMol': budget['in'], 'cumulativeOutMol': budget['out'], 'cumulativeWallMol': budget['wall'],
                       'budgetResidualMol': m - m0 - budget['in'] + budget['out'] + budget['wall'],
                       'outletMeanMolPerM3': float(cm[-1]), 'outletCupMolPerM3': float(cup(c)[-1]), 'midMeanMolPerM3': float(cm[Nz // 2])})

    def frame(t, c):
        frame_list.append({'t': t, 'field': c[np.ix_(keep_r, keep_z)].copy(), 'mean': mean(c)[keep_z].tolist()})

    sample(0.0, c); frame(0.0, c)
    started = time.perf_counter()
    t = 0.0
    for n in range(1, steps + 1):
        tm = (n - 0.5) * dt                          # midpoint inlet value: second order in time for the inlet flux
        c, w1 = radial(c)
        c, fin, fout = axial(c, _inlet(p, tm))
        c, w2 = radial(c)
        budget['in'] += fin; budget['out'] += fout; budget['wall'] += w1 + w2
        t = n * dt
        if n % sample_every == 0 or n == steps:
            sample(t, c, (fin / dt, fout / dt, (w1 + w2) / dt))
        if n % frame_every == 0 or n == steps:
            if frame_list[-1]['t'] != t: frame(t, c)
    elapsed = time.perf_counter() - started
    # Display frames: quantised to 16-bit levels of the run's peak (relative error ≤ 7.6e-6 of the peak); all benchmarks use full precision.
    peak = max(float(np.max(f['field'])) for f in frame_list) or 1.0
    for f in frame_list:
        f['field'] = np.rint(np.clip(f['field'], 0, None) / peak * 65535).astype(int).tolist()
    scale = max(m0, budget['in'], 1e-300)
    residual = float(max(abs(row['budgetResidualMol']) for row in series) / scale)
    result = {
        'engine': ENGINE, 'inputs': p, 'settings': s, 'environment': environment(),
        'derived': {'radiusM': R, 'lengthM': L, 'meanVelocityMPerS': U, 'diffusivityM2PerS': D, 'permeabilityMPerS': P,
                    'drM': dr, 'dzM': dz, 'dtS': dt, 'steps': steps, 'cells': Nr * Nz, 'elapsedS': elapsed,
                    'radialTimeS': R * R / D, 'transitTimeS': L / U if U > 0 else None,
                    'taylorArisM2PerS': D * (1 + (U * R / D) ** 2 / 48), 'peclet': U * R / D},
        'stability': stability,
        'flow': {'rUm': (flow['centres'] * 1e6).tolist(), 'ringVelocityMmPerS': (w * 1e3).tolist(), 'pointVelocityMmPerS': (flow['pointVelocity'] * 1e3).tolist(),
                 'fvPointVelocityMmPerS': (flow['fvPointVelocity'] * 1e3).tolist(),
                 'pressureGradientPaPerM': flow['pressureGradientPaPerM'], 'wallShearStressPa': flow['wallShearStressPa'],
                 'fvRelativeError': flow['fvRelativeError'], 'fvPressureGradientRelativeError': flow['fvPressureGradientRelativeError'],
                 'flowRateRelativeError': flow['flowRateRelativeError']},
        'series': series,
        'frames': {'rUm': ((keep_r + 0.5) * dr * 1e6).tolist(), 'zUm': (z[keep_z] * 1e6).tolist(), 'peakMolPerM3': peak, 'levels': 65535,
                   'note': 'Field values are integer levels of peakMolPerM3 (display only; negative undershoots clipped to 0).', 'items': frame_list},
        'final': {'zUm': (z * 1e6).tolist(), 'meanMolPerM3': mean(c).tolist(), 'minMolPerM3': float(np.min(c))},
        'budget': {'initialMol': m0, 'finalMol': mass(c), 'inMol': budget['in'], 'outMol': budget['out'], 'wallMol': budget['wall'],
                   'maxRelativeResidual': residual, 'tolerance': 1e-12, 'pass': residual <= 1e-12},
    }
    if closed and P == 0:
        drift = max(abs(row['massMol'] - m0) for row in series) / m0
        result['budget']['closedMassDrift'] = drift
    if p['inletMode'] == 'slug' and U > 0:
        result['dispersion'] = dispersion_fit(series, R, D, U, T)
    if particles:
        result['particles'] = particle_run(p, flow, particles, series)
    return result


def dispersion_fit(series, R, D, U, T):
    fit_start = max(0.5 * R * R / D, 0.25 * T)
    rows = [r for r in series if r['t'] >= fit_start and r['varianceM2'] is not None]
    K = D * (1 + (U * R / D) ** 2 / 48)
    applicable = T >= R * R / D and len(rows) >= 3
    slope = float(np.polyfit([r['t'] for r in rows], [r['varianceM2'] for r in rows], 1)[0]) if len(rows) >= 3 else float('nan')
    err = abs(slope / 2 - K) / K
    return {'numericalM2PerS': slope / 2, 'taylorArisM2PerS': K, 'relativeError': err, 'tolerance': 0.01, 'applicable': applicable,
            'pass': bool(applicable and err <= 0.01), 'fitWindowS': [fit_start, T], 'fitPoints': len(rows),
            'centroidVelocityMPerS': (series[-1]['centroidM'] - series[0]['centroidM']) / T}


def particle_run(p, flow, n, series):
    """Lagrangian tracer particles: z advected by the computed ring velocity at each particle's radius, Brownian
    increments in x, y, z; specular reflection at the wall, Robin absorption with probability P√(πΔt/D)
    (Erban & Chapman 2007, Phys. Biol. 4:16). Inlet particles are seeded with probability proportional to the
    inlet flux u(r)·c_in(t); slug particles are seeded uniformly in the cross-section. Seeded and reproducible."""
    n = int(n)
    if not 100 <= n <= 50000: raise TransportError('Particle count must be from 100 to 50 000.')
    seed = int(p.get('seed', 7))
    rng = np.random.default_rng(seed)
    R, L = p['radiusUm'] * 1e-6, p['lengthUm'] * 1e-6
    U, D, P, T = p['meanVelocityMmPerS'] * 1e-3, p['diffusivityUm2PerS'] * 1e-12, p['wallPermeabilityUmPerS'] * 1e-6, p['durationS']
    Nr = p['radialCells']; dr = R / Nr
    ring_u = np.asarray(flow['ringVelocity'])
    vel = lambda r: 2 * U * (1 - np.minimum(r, R) ** 2 / R ** 2)      # the same Poiseuille solution the continuum solver averages
    dt = min(0.02 * R * R / D, 0.25 * dr / max(float(np.max(ring_u)), 1e-30) if U > 0 else math.inf, T / 200)
    if p['inletMode'] == 'pulse': dt = min(dt, p['pulseWidthS'] / 10)
    steps = max(1, math.ceil(T / dt)); dt = T / steps
    if steps * n > 2.5e8: raise TransportError('Too many particle steps; reduce the particle count or the duration.')
    absorb = P * math.sqrt(math.pi * dt / D) if P > 0 else 0.0
    if absorb > 0.2: raise TransportError('Wall absorption probability per hit exceeds 0.2; reduce Δt (duration) or P for the particle view.')
    closed = p['inletMode'] == 'slug'
    sq = math.sqrt(2 * D * dt)
    if closed:
        rad = R * np.sqrt(rng.random(n)); ang = 2 * np.pi * rng.random(n)
        x, y = rad * np.cos(ang), rad * np.sin(ang)
        zz = rng.normal(p['slugCentreUm'] * 1e-6, p['slugWidthUm'] * 1e-6, n)
        alive = np.ones(n, bool); born = np.zeros(n)
    else:
        # Release times from the inlet flux history (∝ c_in(t)); positions ∝ u(r) r dr (flux-weighted).
        tt = (np.arange(steps) + 0.5) * dt
        weights = np.array([_inlet(p, t) for t in tt]) * U * math.pi * R * R * dt
        total = float(weights.sum())
        born_step = rng.choice(steps, size=n, p=weights / total) if total > 0 else np.zeros(n, int)
        born = (born_step + rng.random(n)) * dt
        u_ = rng.random(n)          # inverse CDF of the flux-weighted radius for a parabola: F(ρ) = 2ρ² − ρ⁴
        rad = R * np.sqrt(1 - np.sqrt(1 - u_))
        ang = 2 * np.pi * rng.random(n)
        x, y = rad * np.cos(ang), rad * np.sin(ang)
        zz = np.zeros(n); alive = np.zeros(n, bool)
    weight = (total / n) if not closed else series[0]['massMol'] / n
    lost_wall = np.zeros(n, bool); exited = np.zeros(n, bool)
    sample_times = [r['t'] for r in series]
    out, j = [], 0
    track_ids = np.arange(min(n, 160))
    tracks = []
    frames_every = max(1, steps // 36)
    for k in range(steps + 1):
        t = k * dt
        while j < len(sample_times) and sample_times[j] <= t + 0.5 * dt:
            live = alive & ~lost_wall & ~exited
            m = int(live.sum())
            zl = zz[live]
            out.append({'t': sample_times[j], 'massMol': m * weight, 'centroidM': float(zl.mean()) if m else None,
                        'varianceM2': float(zl.var()) if m > 1 else None, 'wallMol': int(lost_wall.sum()) * weight, 'outMol': int(exited.sum()) * weight})
            j += 1
        if k % frames_every == 0 or k == steps:
            ids = track_ids
            tracks.append({'t': t, 'zUm': np.round(zz[ids] * 1e6, 3).tolist(), 'rUm': np.round(np.hypot(x[ids], y[ids]) * 1e6, 4).tolist(),
                           'state': [int(0 if not alive[i] else 2 if lost_wall[i] else 3 if exited[i] else 1) for i in ids]})
        if k == steps: break
        if not closed:
            newborn = (~alive) & (born < t + dt)
            alive |= newborn
            # Newborns advance only the remaining fraction of the step.
            frac = np.where(newborn, (t + dt - born) / dt, 1.0)
        else:
            frac = 1.0
        move = alive & ~lost_wall & ~exited
        rc = np.hypot(x, y)
        h = np.sqrt(frac) * sq
        zz = np.where(move, zz + vel(rc) * dt * frac + h * rng.standard_normal(n), zz)
        x = np.where(move, x + h * rng.standard_normal(n), x)
        y = np.where(move, y + h * rng.standard_normal(n), y)
        rn = np.hypot(x, y)
        hit = move & (rn > R)
        if hit.any():
            if absorb > 0:
                gone = hit & (rng.random(n) < absorb)
                lost_wall |= gone
            fac = np.where(hit, (2 * R - rn) / np.where(rn > 0, rn, 1), 1.0)
            x, y = x * fac, y * fac
        if closed:
            zz = np.where(move & (zz < 0), -zz, zz)
            zz = np.where(move & (zz > L), 2 * L - zz, zz)
        else:
            zz = np.where(move & (zz < 0), -zz, zz)   # zero diffusive flux at the inlet face, approximated by reflection
            exited |= move & (zz > L)
    cont, part = series, out
    stats = []
    for a, b in zip(cont, part):
        if a['t'] == 0 and closed: continue
        stats.append({'t': a['t'], 'continuumMassMol': a['massMol'], 'particleMassMol': b['massMol'],
                      'continuumCentroidM': a['centroidM'], 'particleCentroidM': b['centroidM'],
                      'continuumVarianceM2': a['varianceM2'], 'particleVarianceM2': b['varianceM2'],
                      'continuumWallMol': a['cumulativeWallMol'], 'particleWallMol': b['wallMol']})
    last = stats[-1] if stats else None
    summary = {}
    if last and last['particleCentroidM'] is not None and last['continuumCentroidM'] is not None and last['continuumVarianceM2']:
        m = max(2, round(last['particleMassMol'] / weight))
        summary = {'atTimeS': last['t'], 'particlesInVessel': m,
                   'centroidDifferenceM': last['particleCentroidM'] - last['continuumCentroidM'],
                   'centroidStandardErrorM': math.sqrt(last['continuumVarianceM2'] / m),
                   'varianceRelativeDifference': (last['particleVarianceM2'] - last['continuumVarianceM2']) / last['continuumVarianceM2'],
                   'varianceRelativeStandardError': math.sqrt(2 / m),
                   'massRelativeDifference': (last['particleMassMol'] - last['continuumMassMol']) / last['continuumMassMol'] if last['continuumMassMol'] else None}
        released = n if closed else int(alive.sum())
        f = m / max(released, 1)
        summary['massRelativeStandardError'] = math.sqrt(max(0.0, 1 - f) / max(f * released, 1))   # binomial: each particle is in or out
        z = [abs(summary['centroidDifferenceM']) / summary['centroidStandardErrorM'], abs(summary['varianceRelativeDifference']) / summary['varianceRelativeStandardError']]
        if summary['massRelativeStandardError'] > 0: z.append(abs(summary['massRelativeDifference'] or 0) / summary['massRelativeStandardError'])
        elif abs(summary['massRelativeDifference'] or 0) > 1e-9: z.append(math.inf)
        summary['maxStandardScore'] = max(z)
        summary['consistent'] = bool(max(z) <= 3)
    return {'count': n, 'seed': seed, 'dtS': dt, 'steps': steps, 'absorptionProbabilityPerHit': absorb, 'molPerParticle': weight,
            'method': 'Euler–Maruyama: z += u(r)Δt + √(2DΔt)ξ_z; x, y += √(2DΔt)ξ; specular wall reflection; Robin absorption probability P√(πΔt/D) per wall hit (Erban & Chapman 2007).',
            'label': 'Lagrangian particle view — a stochastic second estimate of the same model; statistics carry Monte-Carlo error.',
            'stats': stats, 'summary': summary, 'tracks': tracks}


# ───────────────────────── validation suite ─────────────────────────

def _bessel_roots(Bi, count=40):
    f = lambda l: l * special.j1(l) - Bi * special.j0(l)
    roots, a = [], 1e-9
    grid = np.linspace(1e-9, 3.2 * (count + 2), 40 * (count + 2))
    vals = f(grid)
    for i in range(len(grid) - 1):
        if vals[i] == 0 or vals[i] * vals[i + 1] < 0:
            roots.append(optimize.brentq(f, grid[i], grid[i + 1], xtol=1e-14))
            if len(roots) == count: break
    return np.array(roots)


def wall_decay_exact(Bi, tau):
    """Fraction of an initially uniform tracer remaining in an infinitely long tube with a Robin wall (dimensionless time Dt/R²)."""
    lam = _bessel_roots(Bi)
    return float(np.sum(4 * Bi ** 2 / (lam ** 2 * (lam ** 2 + Bi ** 2)) * np.exp(-lam ** 2 * tau)))


def _case(**over):
    base = {'radiusUm': 5, 'lengthUm': 700, 'meanVelocityMmPerS': 4, 'diffusivityUm2PerS': 1000, 'wallPermeabilityUmPerS': 0, 'durationS': 0.1,
            'inletMode': 'slug', 'inletAmplitude': 1, 'pulseCentreS': 0, 'pulseWidthS': 0.01, 'slugCentreUm': 150, 'slugWidthUm': 20,
            'plasmaViscosityMPaS': 1.2, 'radialCells': 24, 'axialCells': 500}
    base.update(over)
    return base


def validate_mass():
    r = solve(_case(), frames=2, samples=60)
    drift = r['budget']['closedMassDrift']
    return {'id': 'mass', 'name': 'Mass conservation · closed tube, impermeable wall', 'metric': 'max |M(t) − M(0)| / M(0)', 'value': drift, 'tolerance': 1e-12, 'passed': drift <= 1e-12,
            'detail': f"{r['derived']['steps']} steps on {r['derived']['cells']} cells; centroid speed {r['dispersion']['centroidVelocityMPerS'] * 1e3:.6f} mm/s vs U = 4 mm/s"}


def validate_budget():
    r = solve(_case(inletMode='pulse', lengthUm=300, meanVelocityMmPerS=1, diffusivityUm2PerS=300, wallPermeabilityUmPerS=5, durationS=0.6, pulseCentreS=0.05, pulseWidthS=0.015,
                    radialCells=16, axialCells=150), frames=2, samples=80)
    b = r['budget']
    return {'id': 'budget', 'name': 'Boundary budget · inlet pulse, permeable wall, open outlet', 'metric': 'max |M(t) − M(0) − in + out + wall| / max(M₀, in)',
            'value': b['maxRelativeResidual'], 'tolerance': 1e-12, 'passed': b['pass'],
            'detail': f"in {b['inMol']:.4e} mol = out {b['outMol']:.4e} + wall {b['wallMol']:.4e} + held {b['finalMol']:.4e}"}


def validate_taylor_aris(radial=24, axial=500):
    r = solve(_case(radialCells=radial, axialCells=axial), frames=2, samples=200)
    d = r['dispersion']
    return {'id': 'taylor-aris', 'name': 'Taylor–Aris dispersion · Pe = 20, closed tube', 'metric': '|K_num − K_TA| / K_TA', 'value': d['relativeError'], 'tolerance': 0.01, 'passed': d['pass'],
            'detail': f"K_num = {d['numericalM2PerS'] * 1e12:.2f} µm²/s, K_TA = D(1 + Pe²/48) = {d['taylorArisM2PerS'] * 1e12:.2f} µm²/s; fit over t ∈ [{d['fitWindowS'][0]:.3g}, {d['fitWindowS'][1]:.3g}] s",
            'numericalK': d['numericalM2PerS']}


def validate_diffusion():
    D, s0, T = 1000e-12, 20e-6, 0.05
    r = solve(_case(meanVelocityMmPerS=0, lengthUm=600, slugCentreUm=300, durationS=T, radialCells=8, axialCells=600), frames=2, samples=10)
    z = np.asarray(r['final']['zUm']) * 1e-6
    var = s0 ** 2 + 2 * D * T
    exact = s0 / math.sqrt(var) * np.exp(-0.5 * (z - 300e-6) ** 2 / var)
    err = float(np.max(np.abs(np.asarray(r['final']['meanMolPerM3']) - exact)) / np.max(exact))
    return {'id': 'diffusion', 'name': 'Pure diffusion limit (U = 0)', 'metric': 'max |c̄ − c̄_exact| / max c̄_exact', 'value': err, 'tolerance': 5e-3, 'passed': err <= 5e-3,
            'detail': f"σ(T) exact {math.sqrt(var) * 1e6:.3f} µm vs numerical {math.sqrt(r['series'][-1]['varianceM2']) * 1e6:.3f} µm"}


def validate_wall(radial=32):
    R, D, P = 5e-6, 100e-12, 20e-6          # Bi = 1
    T = 0.25                                # τ = DT/R² = 1
    r = solve(_case(meanVelocityMmPerS=0, lengthUm=40, slugCentreUm=20, slugWidthUm=1e5, diffusivityUm2PerS=100, wallPermeabilityUmPerS=20,
                    durationS=T, radialCells=radial, axialCells=20), frames=2, samples=20)
    num = r['series'][-1]['massMol'] / r['series'][0]['massMol']
    ex = wall_decay_exact(P * R / D, D * T / R ** 2)
    err = abs(num - ex) / ex
    return {'id': 'wall', 'name': 'Permeable-wall decay · Bi = PR/D = 1, Dt/R² = 1', 'metric': '|M/M₀ − series| / series', 'value': err, 'tolerance': 5e-3, 'passed': err <= 5e-3,
            'detail': f"retained {num:.6f} vs Bessel series {ex:.6f}; wall budget residual {r['budget']['maxRelativeResidual']:.1e}"}


def validate_velocity():
    errs = [stokes_fv(5e-6, n) for n in (12, 24, 48)]
    R = 5e-6
    e = [float(np.max(np.abs(u - 2 * (1 - ((np.arange(len(u)) + 0.5) * R / len(u)) ** 2 / R ** 2))) / 2) for u, _ in errs]
    order = math.log2(e[1] / e[2])
    f = stokes_velocity(R, 4e-3, 1.2e-3, 24)
    passed = e[1] <= 2e-3 and order >= 1.8 and f['flowRateRelativeError'] <= 1e-12
    return {'id': 'velocity', 'name': 'Velocity field · FV Stokes solve vs Poiseuille', 'metric': 'max |u_FV − u| / u_max at 24 rings', 'value': e[1], 'tolerance': 2e-3, 'passed': passed,
            'detail': f"errors {e[0]:.2e} → {e[1]:.2e} → {e[2]:.2e} (12 → 24 → 48 rings, order {order:.2f}); ring-averaged flow rate error {f['flowRateRelativeError']:.1e}; "
                      f"dp/dz = {f['pressureGradientPaPerM']:.4g} Pa/m, wall shear {f['wallShearStressPa']:.3g} Pa (μ = 1.2 mPa·s)"}


def validate_convergence():
    """Pure-diffusion Gaussian error on three axial grids (Δz halves); Δt is tied to Δz², so the error is second order."""
    D, s0, T = 1000e-12, 10e-6, 0.02
    errs = []
    for nz in (75, 150, 300):
        r = solve(_case(meanVelocityMmPerS=0, lengthUm=300, slugCentreUm=150, slugWidthUm=10, durationS=T, radialCells=4, axialCells=nz), frames=2, samples=4)
        z = np.asarray(r['final']['zUm']) * 1e-6
        var = s0 ** 2 + 2 * D * T
        exact = s0 / math.sqrt(var) * np.exp(-0.5 * (z - 150e-6) ** 2 / var)
        # Compare cell averages with the exact cell average (Simpson on the cell) so the measured order is the scheme's.
        dz = z[1] - z[0]
        lo, hi = z - dz / 2, z + dz / 2
        avg = s0 * math.sqrt(math.pi / 2) / dz * (special.erf((hi - 150e-6) / math.sqrt(2 * var)) - special.erf((lo - 150e-6) / math.sqrt(2 * var)))
        errs.append(float(np.sqrt(np.mean((np.asarray(r['final']['meanMolPerM3']) - avg) ** 2))))
    order = math.log2(errs[1] / errs[2])
    # Taylor–Aris residual on three grids for the advective problem (reported, not gated: limiter-dependent order).
    ta = [validate_taylor_aris(radial=nr, axial=nz)['value'] for nr, nz in ((12, 125), (24, 250), (48, 500))]
    passed = order >= 1.5 and errs[0] > errs[1] > errs[2]
    return {'id': 'convergence', 'name': 'Grid convergence · three grids, refinement ratio 2', 'metric': 'observed order p = log₂(e₂/e₃)', 'value': order, 'tolerance': 1.5, 'passed': passed,
            'detail': f"RMS errors {errs[0]:.3e} → {errs[1]:.3e} → {errs[2]:.3e} (pure diffusion); Taylor–Aris |ΔK|/K {ta[0] * 100:.2f}% → {ta[1] * 100:.2f}% → {ta[2] * 100:.2f}% (12×125 → 24×250 → 48×500)",
            'errors': errs, 'taylorArisErrors': ta, 'comparison': 'lower-is-better', 'higherIsBetter': True}


VALIDATIONS = {'mass': validate_mass, 'budget': validate_budget, 'taylor-aris': validate_taylor_aris, 'diffusion': validate_diffusion,
               'wall': validate_wall, 'velocity': validate_velocity, 'convergence': validate_convergence}


def validate(ids=None):
    started = time.perf_counter()
    checks = [VALIDATIONS[k]() for k in (ids or VALIDATIONS)]
    return {'checks': checks, 'passed': all(c['passed'] for c in checks), 'elapsedS': time.perf_counter() - started, 'environment': environment()}


def descriptor():
    return {**ENGINE, 'evidence': 'B', 'numericalMethod': METHOD, 'equations': EQUATIONS, 'assumptions': ASSUMPTIONS, 'limits': LIMITS, 'benchmarks': BENCHMARKS,
            'inputs': [{'key': k, 'unit': u, 'description': d, 'bounds': [lo, hi]} for k, u, d, lo, hi in INPUTS],
            'presets': PRESETS, 'inlets': list(INLETS), 'limiters': list(LIMITERS), 'environment': environment(),
            'validatedDomain': ['Taylor–Aris variance growth within 1% at Pe = 20 (24 × 500 cells)', 'Pure diffusion within 0.5%', 'Permeable-wall decay within 0.5% at Bi = 1',
                                'Mass and boundary budgets to round-off for every inlet mode'],
            'uncertainty': 'Discretisation error quantified by the benchmarks and grid study; no parameter or model uncertainty is propagated.'}


def record(result, evidence):
    body = {'inputs': result['inputs'], 'settings': result['settings'], 'derived': result['derived'], 'budget': result['budget'], 'stability': result['stability'],
            'dispersion': result.get('dispersion'), 'series': result['series']}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, default=float).encode()).hexdigest()
    return {'schema': 'fold-studio.research-record', 'schemaVersion': 1,
            'engine': {**ENGINE, 'numericalMethod': METHOD},
            'evidence': {'category': evidence, 'name': 'Physics simulation' if evidence == 'B' else 'Parameterised hypothesis',
                         'statement': 'Physics-simulated: numerical solution of the stated idealised equations. ' + (
                             'Verification case, not a vessel.' if evidence == 'B' else 'Parameters resemble a plasma-filled vessel; the model is not validated human circulation.')},
            'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'inputs': {k: {'value': result['inputs'][k], 'unit': u, 'description': d} for k, u, d, *_ in INPUTS} | {'inletMode': {'value': result['inputs']['inletMode'], 'unit': '—', 'description': 'Inlet condition'}},
            'solver': {**result['settings'], 'equations': EQUATIONS, **{k: result['derived'][k] for k in ('drM', 'dzM', 'dtS', 'steps')}, 'stability': result['stability']},
            'outputs': {'series': result['series'], 'final': result['final'], 'budget': result['budget'], 'flow': result['flow']},
            'benchmark': result.get('dispersion'), 'assumptions': ASSUMPTIONS, 'limitations': LIMITS,
            'reproducibility': {'deterministic': True, 'seed': result.get('particles', {}).get('seed'), 'runtime': json.dumps(environment()), 'contentSha256': digest}}


def _payload_inputs(p):
    inputs = dict(p.get('inputs') or {})
    return inputs


def dispatch(service, action, p):
    try:
        if action == 'blood_transport_describe': return descriptor()
        if action == 'blood_transport_run':
            particles = p.get('particles')
            result = solve(_payload_inputs(p), p.get('settings'), particles=int(particles) if particles else None)
            evidence = p.get('evidence') if p.get('evidence') in ('B', 'D') else 'B'
            result['record'] = record(result, evidence)
            return result
        if action == 'blood_transport_validate': return validate(p.get('ids'))
    except TransportError as e:
        raise ValueError(str(e))
    raise ValueError('Unsupported blood transport action.')


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == '--reference':
        # Cross-language reference consumed by src/lib/bloodTransport.test.ts (TS Demo D solver vs this solver).
        r = solve(_case(), frames=2, samples=200)
        out = {'inputs': r['inputs'], 'numericalKM2PerS': r['dispersion']['numericalM2PerS'], 'taylorArisM2PerS': r['dispersion']['taylorArisM2PerS'],
               'finalTimeS': r['inputs']['durationS'], 'final': r['final'], 'environment': environment()}
        open(sys.argv[2], 'w').write(json.dumps(out))
    else:
        print(json.dumps(validate(), indent=1, default=float))
