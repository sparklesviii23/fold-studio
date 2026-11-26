"""Brownian-dynamics particle engine for the Living Cell physics slice.

Point particles diffuse with a known coefficient D (Euler–Maruyama, which is
exact for free diffusion: each step adds N(0, 2DΔt) per axis). Walls are
spheres; a particle that would cross one is reflected specularly at the hit
point (the remaining displacement is mirrored about the surface normal),
repeated until the whole step lies inside the domain. Reversible binding to
fixed membrane receptors uses the Doi (volume-reactivity) model in a form
whose discrete-time chain satisfies detailed balance exactly:

  free ligand inside an unoccupied receptor's reaction volume binds with
  probability λΔt per step; a complex dissociates with probability koffΔt and
  the ligand is placed uniformly in that reaction volume.

With uniform free density this gives the exact equilibrium constant
K = λ·V_rx / koff = kon / koff for every Δt (λΔt, koffΔt ≤ 0.2 are enforced).

Units throughout: µm, s, µm²/s, µm³/s. RNG: NumPy PCG64 with an explicit seed.
Nothing here depends on the fold worker; it can be tested on its own.
"""
import math
import numpy as np

AVOGADRO = 6.02214076e23
UM3_PER_LITRE = 1e15


class BDError(ValueError):
    pass


def bounded(name, value, lo, hi, unit, integer=False):
    """Reject (never clamp) inputs outside the engine's declared bounds."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise BDError(f'{name} must be a number.')
    if not math.isfinite(v) or not lo <= v <= hi:
        raise BDError(f'{name} must be between {lo:g} and {hi:g} {unit}; got {value}.')
    if integer:
        if v != int(v):
            raise BDError(f'{name} must be a whole number.')
        return int(v)
    return v


class Domain:
    """Region bounded by concentric spheres centred on the origin.

    walls: list of (radius, side) with side +1 = particles stay inside (r ≤ R),
    side −1 = particles stay outside (r ≥ R). No walls = free space."""

    def __init__(self, walls=()):
        self.walls = [(float(r), int(s)) for r, s in walls]

    @staticmethod
    def free():
        return Domain()

    @staticmethod
    def sphere(radius):
        return Domain([(radius, +1)])

    @staticmethod
    def shell(inner, outer):
        if not inner < outer:
            raise BDError('The inner radius must be smaller than the outer radius.')
        return Domain([(outer, +1), (inner, -1)])

    @property
    def kind(self):
        return {0: 'free', 1: 'sphere', 2: 'shell'}[len(self.walls)]

    def volume(self):
        if not self.walls:
            return math.inf
        out = max(r for r, s in self.walls if s > 0)
        inner = [r for r, s in self.walls if s < 0]
        return 4 / 3 * math.pi * (out ** 3 - (inner[0] ** 3 if inner else 0.0))

    def contains(self, x, tol=1e-9):
        r = np.linalg.norm(x, axis=-1)
        ok = np.ones(r.shape, bool)
        for R, s in self.walls:
            ok &= (r <= R * (1 + tol)) if s > 0 else (r >= R * (1 - tol))
        return ok

    def uniform(self, rng, n):
        """Uniform positions by inverse-CDF in r³ and isotropic directions."""
        out = max(r for r, s in self.walls if s > 0)
        inner = ([r for r, s in self.walls if s < 0] or [0.0])[0]
        u = rng.random(n)
        r = np.cbrt(inner ** 3 + u * (out ** 3 - inner ** 3))
        return r[:, None] * directions(rng, n)

    def step(self, x, dx):
        """Move x by dx with specular reflection; returns (new x, reflections, projected)."""
        x0, d = x.copy(), dx.copy()
        reflections = 0
        # Only steps that end beyond an outer wall, or pass within |dx| of an excluded ball, can hit anything.
        r1 = np.linalg.norm(x0 + d, axis=1)
        reach = np.linalg.norm(d, axis=1)
        maybe = np.zeros(len(x), bool)
        for R, s in self.walls:
            maybe |= (r1 > R) if s > 0 else (r1 - reach < R)
        active = np.flatnonzero(maybe)
        for _ in range(16):
            if not len(active) or not self.walls:
                break
            a, b = x0[active], d[active]
            A = np.einsum('ij,ij->i', b, b)
            B = 2 * np.einsum('ij,ij->i', a, b)
            C0 = np.einsum('ij,ij->i', a, a)
            best = np.full(len(active), np.inf)
            which = np.full(len(active), -1)
            for k, (R, s) in enumerate(self.walls):
                C = C0 - R * R
                disc = B * B - 4 * A * C
                root = np.sqrt(np.maximum(disc, 0.0))
                with np.errstate(divide='ignore', invalid='ignore'):
                    if s > 0:
                        # Leaves the ball when the end point is outside; exit at the larger root.
                        end = np.einsum('ij,ij->i', a + b, a + b)
                        t = (-B + root) / (2 * A)
                        hit = (end > R * R) & (A > 0)
                    else:
                        # Enters the excluded ball when the smaller root lies in the step.
                        t = (-B - root) / (2 * A)
                        hit = (disc > 0) & (A > 0) & (t > 1e-12) & (t <= 1)
                t = np.clip(np.where(hit, t, np.inf), 0.0, np.inf)
                better = hit & (t < best)
                best[better] = t[better]
                which[better] = k
            hit = which >= 0
            if not hit.any():
                break
            idx, t, k = active[hit], best[hit], which[hit]
            h = x0[idx] + t[:, None] * d[idx]
            radii = np.array([self.walls[j][0] for j in k])
            n = h / radii[:, None]
            rem = (1 - t)[:, None] * d[idx]
            rem -= 2 * np.einsum('ij,ij->i', rem, n)[:, None] * n
            # Place the hit point exactly on the wall so round-off cannot leak particles through.
            x0[idx] = n * radii[:, None]
            d[idx] = rem
            reflections += int(hit.sum())
            active = idx
        y = x0 + d
        bad = ~self.contains(y)
        projected = int(bad.sum())
        if projected:
            y[bad] = self.project(y[bad])
        return y, reflections, projected

    def project(self, y):
        r = np.linalg.norm(y, axis=1)
        target = r.copy()
        for R, s in self.walls:
            target = np.minimum(target, R) if s > 0 else np.maximum(target, R)
        with np.errstate(invalid='ignore', divide='ignore'):
            scale = np.where(r > 0, target / r, 1.0)
        return y * scale[:, None]


def directions(rng, n):
    v = rng.standard_normal((n, 3))
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def fibonacci_sphere(n, radius):
    """Near-uniform deterministic points on a sphere (golden-angle spiral)."""
    k = np.arange(n) + 0.5
    z = 1 - 2 * k / n
    phi = math.pi * (3 - math.sqrt(5)) * k
    rho = np.sqrt(1 - z * z)
    return radius * np.stack([rho * np.cos(phi), rho * np.sin(phi), z], axis=1)


def reaction_volume(sigma, membrane):
    """Volume of the ball of radius σ centred on the membrane (radius R) that lies outside the cell.

    The sphere–sphere lens with centres a distance R apart has volume
    πσ³(8R − 3σ)/(12R); the reaction volume is the rest of the σ-ball."""
    lens = math.pi * sigma ** 3 * (8 * membrane - 3 * sigma) / (12 * membrane)
    return 4 / 3 * math.pi * sigma ** 3 - lens


def kon_molar(kon_um3):
    """µm³ s⁻¹ per molecule pair → M⁻¹ s⁻¹."""
    return kon_um3 * AVOGADRO / UM3_PER_LITRE


# ---------------------------------------------------------------- diffusion

def diffuse(D, dt, steps, n, domain, seed, start='centre', record_every=10, sampled=32):
    """Run n independent particles; return squared displacements at recorded times and sampled tracks."""
    rng = np.random.Generator(np.random.PCG64(seed))
    if start == 'centre':
        x = np.zeros((n, 3))
    elif start == 'uniform':
        x = domain.uniform(rng, n)
    else:
        raise BDError('Start must be centre or uniform.')
    x_start = x.copy()
    sd = math.sqrt(2 * D * dt)
    times, msd, msd_sd, disp_groups = [0.0], [0.0], [0.0], []
    keep = min(sampled, n)
    track = [x[:keep].copy()]
    group = np.arange(n) % 10
    reflections = projected = 0
    for k in range(1, steps + 1):
        x, refl, proj = domain.step(x, sd * rng.standard_normal((n, 3)))
        reflections += refl
        projected += proj
        if k % record_every == 0 or k == steps:
            r2 = np.einsum('ij,ij->i', x - x_start, x - x_start)
            times.append(k * dt)
            msd.append(float(r2.mean()))
            msd_sd.append(float(r2.std(ddof=1)))
            disp_groups.append(np.bincount(group, weights=r2, minlength=10) / np.bincount(group, minlength=10))
            track.append(x[:keep].copy())
    return {'time': np.array(times), 'msd': np.array(msd), 'msdSd': np.array(msd_sd), 'groups': np.array(disp_groups),
            'final': x, 'start': x_start, 'track': np.stack(track, axis=1), 'reflections': reflections, 'projected': projected}


# ------------------------------------------------------------------ binding

def bind(params, seed, record_every=50, sampled=40):
    """Ligands in a spherical shell (cell membrane at R_cell, reflecting outer wall at R_outer)
    binding fixed membrane receptors; `params` keys documented in cell_physics.BINDING_INPUTS."""
    Ri, Ro, D = params['membraneRadius'], params['outerRadius'], params['diffusion']
    nL, nR, reps = params['ligands'], params['receptors'], params['replicates']
    sigma, kon, koff, dt, t_end = params['reactionRadius'], params['kon'], params['koff'], params['dt'], params['tEnd']
    domain = Domain.shell(Ri, Ro)
    v_rx = reaction_volume(sigma, Ri)
    lam = kon / v_rx
    p_on, p_off = lam * dt, koff * dt
    if p_on > 0.2 or p_off > 0.2:
        raise BDError(f'Time step too large: λΔt = {p_on:.3g} and koffΔt = {p_off:.3g} must both be ≤ 0.2.')
    receptors = fibonacci_sphere(nR, Ri)
    spacing = float(np.min([np.min(np.linalg.norm(np.delete(receptors, i, 0) - receptors[i], axis=1)) for i in range(min(nR, 400))])) if nR > 1 else math.inf
    if spacing <= 2 * sigma:
        raise BDError(f'Receptors are {spacing:.3g} µm apart; reaction volumes overlap unless spacing > 2σ = {2 * sigma:.3g} µm. Use fewer receptors or a smaller σ.')
    rng = np.random.Generator(np.random.PCG64(seed))
    x = domain.uniform(rng, nL * reps)                 # positions, replicate-major
    rep = np.repeat(np.arange(reps), nL)
    partner = np.full(nL * reps, -1)                   # receptor index if bound
    occupied = np.full((reps, nR), -1)                 # ligand index bound to each receptor
    sd = math.sqrt(2 * D * dt)
    steps = int(round(t_end / dt))
    near = Ri + sigma
    times, bound = [0.0], [np.zeros(reps)]
    keep = min(sampled, nL)
    tracks, tracks_bound, frames_bound = [x[:keep].copy()], [np.zeros(keep, bool)], [[]]
    events = {'binding': 0, 'unbinding': 0, 'conflicts': 0, 'reflections': 0, 'projected': 0, 'placementDraws': 0}
    for k in range(1, steps + 1):
        free = partner < 0
        fi = np.flatnonzero(free)
        y, refl, proj = domain.step(x[fi], sd * rng.standard_normal((len(fi), 3)))
        x[fi] = y
        events['reflections'] += refl
        events['projected'] += proj
        # Unbinding is decided from the pre-step state, so a ligand cannot unbind and rebind in one step.
        bi = np.flatnonzero(~free)
        release = bi[rng.random(len(bi)) < p_off]
        # Binding attempts: only free ligands within σ of the membrane can be in a reaction volume.
        cand = fi[np.einsum('ij,ij->i', x[fi], x[fi]) < near * near]
        if len(cand):
            d2 = ((x[cand, None, :] - receptors[None, :, :]) ** 2).sum(-1)
            within = d2 < sigma * sigma
            has = within.any(1)
            cand, which = cand[has], within[has].argmax(1)
            empty = occupied[rep[cand], which] < 0
            cand, which = cand[empty], which[empty]
            go = rng.random(len(cand)) < p_on
            cand, which = cand[go], which[go]
            if len(cand):
                key = rep[cand] * nR + which
                order = rng.permutation(len(cand))
                _, first = np.unique(key[order], return_index=True)
                win = order[first]
                events['conflicts'] += len(cand) - len(win)
                cand, which = cand[win], which[win]
                partner[cand] = which
                occupied[rep[cand], which] = cand
                x[cand] = receptors[which]
                events['binding'] += len(cand)
        if len(release):
            r_idx = partner[release]
            occupied[rep[release], r_idx] = -1
            partner[release] = -1
            x[release] = place(rng, receptors[r_idx], sigma, Ri, Ro, events)
            events['unbinding'] += len(release)
        if k % record_every == 0 or k == steps:
            times.append(k * dt)
            bound.append(np.bincount(rep[partner >= 0], minlength=reps).astype(float))
            tracks.append(x[:keep].copy())
            tracks_bound.append(partner[:keep] >= 0)
            frames_bound.append(np.flatnonzero(occupied[0] >= 0).tolist())
    # Conservation: every bound ligand has exactly one receptor and vice versa.
    consistent = all(int((occupied[r] >= 0).sum()) == int(((partner >= 0) & (rep == r)).sum()) for r in range(reps))
    return {'time': np.array(times), 'bound': np.stack(bound, axis=1), 'receptors': receptors, 'track': np.stack(tracks, axis=1),
            'trackBound': np.stack(tracks_bound, axis=1), 'framesBound': frames_bound, 'events': events, 'consistent': consistent,
            'reactionVolume': v_rx, 'lambda': lam, 'pOn': p_on, 'pOff': p_off, 'spacing': spacing, 'volume': domain.volume(), 'steps': steps}


def place(rng, centres, sigma, Ri, Ro, events):
    """Uniform points in each σ-ball around a receptor, restricted to the domain (rejection sampling)."""
    out = np.empty_like(centres)
    todo = np.arange(len(centres))
    while len(todo):
        u = rng.random(len(todo))
        p = centres[todo] + (sigma * np.cbrt(u))[:, None] * directions(rng, len(todo))
        r = np.linalg.norm(p, axis=1)
        ok = (r >= Ri) & (r <= Ro)
        events['placementDraws'] += len(todo)
        out[todo[ok]] = p[ok]
        todo = todo[~ok]
    return out


def exact_equilibrium(nL, nR, K, V):
    """Mean and SD of bound complexes for ideal particles at equilibrium (canonical ensemble).

    P(n) ∝ C(nR, n) · nL!/(nL − n)! · (K/V)^n, the exact distribution for nL
    non-interacting ligands and nR single-site receptors with association constant K."""
    n = np.arange(min(nL, nR) + 1)
    lg = [math.lgamma(nR + 1) - math.lgamma(k + 1) - math.lgamma(nR - k + 1) + math.lgamma(nL + 1) - math.lgamma(nL - k + 1) + k * math.log(K / V) for k in n]
    w = np.exp(np.array(lg) - max(lg))
    w /= w.sum()
    mean = float((n * w).sum())
    return mean, float(math.sqrt(max(((n - mean) ** 2 * w).sum(), 0.0)))


def mean_field_equilibrium(nL, nR, K, V):
    """Root of C = (K/V)(nL − C)(nR − C) in [0, min(nL, nR)] (the well-mixed mass-action equilibrium)."""
    a = K / V
    b = -(a * (nL + nR) + 1)
    c = a * nL * nR
    return float((-b - math.sqrt(b * b - 4 * a * c)) / (2 * a))
