"""Stochastic translation for the RNA-to-Protein Laboratory (Demo 4).

Exact Gillespie simulation (Gillespie 1977, doi:10.1021/j100540a008) of the totally asymmetric
simple exclusion process with extended particles (ribosomes covering ``footprint`` codons;
MacDonald, Gibbs & Pipkin 1968, doi:10.1002/bip.1968.360060102), with initiation, codon-by-codon
elongation and termination as in rSNAPsim (Aguilera et al. 2019, doi:10.1371/journal.pcbi.1007425).

Lattice convention: a ribosome is identified by its A-site codon x (0-based) and covers codons
x-footprint+1 … x. Initiation places a ribosome with its A site on codon 0 at rate ``alpha`` when
the upstream-most ribosome has x >= footprint. A ribosome at x < L-1 advances at rate k[x+1]
(the rate of decoding the next codon) when the downstream ribosome's A site y satisfies
y - x > footprint. A ribosome at the last sense codon (x = L-1) terminates at rate ``beta``,
releasing one protein. Rates are per second.
"""
import math, random

MAX_EVENTS = 3_000_000
GENETIC_STOPS = {'UAA', 'UAG', 'UGA'}


def parse_cds(seq):
    """Validate a coding sequence and return its sense codons (start..last sense codon)."""
    s = ''.join(str(seq).upper().split()).replace('T', 'U')
    bad = sorted(set(s) - set('ACGU'))
    if bad: raise ValueError('Only A, C, G and U (or T) are accepted in a coding sequence; found ' + ', '.join(bad) + '.')
    if len(s) % 3: raise ValueError(f'A coding sequence must be a whole number of codons; {len(s)} nt is not divisible by 3.')
    codons = [s[i:i + 3] for i in range(0, len(s), 3)]
    if not codons or codons[0] != 'AUG': raise ValueError('The coding sequence must start with AUG.')
    if codons[-1] not in GENETIC_STOPS: raise ValueError('The coding sequence must end with a stop codon (UAA, UAG or UGA).')
    internal = [i + 1 for i, c in enumerate(codons[:-1]) if c in GENETIC_STOPS]
    if internal: raise ValueError(f'In-frame stop codon at codon {internal[0]}; the sequence is not a single open reading frame.')
    return codons[:-1]


def _check(L, footprint, alpha, rates, beta, t_end):
    if L < 2 or L > 20000: raise ValueError('The lattice must have 2–20,000 codons.')
    if footprint < 1 or footprint > 40: raise ValueError('Ribosome footprint must be 1–40 codons.')
    for name, v in (('Initiation rate', alpha), ('Termination rate', beta), ('Simulated time', t_end)):
        if not (v > 0 and math.isfinite(v)): raise ValueError(name + ' must be a positive number.')
    if len(rates) != L or any(not (r > 0 and math.isfinite(r)) for r in rates): raise ValueError('Every elongation rate must be positive.')


def simulate(L, footprint, alpha, rates, beta, t_end, seed=1, burn_in=0.0, grid=200, frames=0, frame_window=None, max_events=MAX_EVENTS, max_ribosomes=None):
    """Run one exact trajectory. ``rates[x]`` is the rate of decoding codon x (index 0 unused).

    Returns time-averaged A-site occupancy after ``burn_in``, cumulative proteins on a time grid,
    termination and transit times, collision statistics, and (optionally) exact state snapshots for playback. ``max_ribosomes=1`` gives the
    exact isolated-ribosome process used to validate transit times.
    """
    rates = [float(r) for r in rates]
    _check(L, footprint, alpha, rates, beta, t_end)
    rng = random.Random(seed)
    pos, ids = [], []                      # ribosomes ordered 5'→3' (ascending A site)
    next_id = 0
    t = 0.0; events = 0
    occupancy = [0.0] * L; blocked_time = 0.0; ribosome_time = 0.0
    finished = []; collisions = 0; initiations = 0; started = {}; transits = []
    grid_t = [t_end * k / grid for k in range(grid + 1)]; produced = [0] * (grid + 1); gi = 0
    fw = frame_window or (0.0, t_end)
    frame_t = [fw[0] + (fw[1] - fw[0]) * k / max(1, frames - 1) for k in range(frames)] if frames else []
    snaps = []; fi = 0
    bt = max(0.0, burn_in)
    while True:
        n = len(pos)
        # Propensities: initiation, one hop or termination per ribosome.
        a0 = alpha if (n == 0 or pos[0] >= footprint) and (max_ribosomes is None or n < max_ribosomes) else 0.0
        props = [0.0] * n; nblocked = 0
        for k in range(n):
            x = pos[k]
            if x == L - 1: props[k] = beta
            elif k == n - 1 or pos[k + 1] - x > footprint: props[k] = rates[x + 1]
            else: nblocked += 1
        total = a0 + sum(props)
        dt = -math.log(1.0 - rng.random()) / total if total > 0 else math.inf
        t_next = min(t + dt, t_end)
        # Exact piecewise-constant state between events: record grid points and snapshots.
        while gi <= grid and grid_t[gi] <= t_next:
            produced[gi] = len(finished); gi += 1
        while fi < len(frame_t) and frame_t[fi] <= t_next:
            snaps.append({'t': frame_t[fi], 'ribosomes': [[ids[k], pos[k]] for k in range(n)]}); fi += 1
        lo = max(t, bt); hi = t_next
        if hi > lo:
            w = hi - lo
            for x in pos: occupancy[x] += w
            ribosome_time += w * n; blocked_time += w * nblocked
        if t + dt >= t_end: break
        t += dt; events += 1
        if events > max_events: raise ValueError(f'More than {max_events:,} events; shorten the simulated time.')
        r = rng.random() * total
        if r < a0:
            pos.insert(0, 0); ids.insert(0, next_id); started[next_id] = t; next_id += 1; initiations += 1
            if len(pos) > 1 and pos[1] - pos[0] == footprint: collisions += 1
            continue
        r -= a0
        for k in range(n):
            if r < props[k]: break
            r -= props[k]
        else:
            k = max(i for i in range(n) if props[i] > 0)
        if pos[k] == L - 1:
            finished.append(t); transits.append(t - started.pop(ids[k])); pos.pop(k); ids.pop(k)
        else:
            pos[k] += 1
            if k + 1 < n and pos[k + 1] - pos[k] == footprint: collisions += 1
    while gi <= grid: produced[gi] = len(finished); gi += 1
    span = max(t_end - bt, 1e-300)
    return {'occupancy': [o / span for o in occupancy], 'grid': grid_t, 'produced': produced, 'finished': finished,
            'events': events, 'initiations': initiations, 'collisions': collisions, 'transits': transits,
            'blockedFraction': blocked_time / ribosome_time if ribosome_time else 0.0,
            'meanRibosomes': ribosome_time / span, 'snapshots': snaps}


def steady_current(finished, burn_in, t_end, batches=20):
    """Protein output rate after burn-in with a batch-means standard error."""
    span = t_end - burn_in
    if span <= 0: raise ValueError('Burn-in must be shorter than the simulated time.')
    width = span / batches; counts = [0] * batches
    for t in finished:
        if t >= burn_in:
            counts[min(batches - 1, int((t - burn_in) / width))] += 1
    rates = [c / width for c in counts]
    mean = sum(rates) / batches
    var = sum((r - mean) ** 2 for r in rates) / (batches - 1)
    return mean, math.sqrt(var / batches)


def mean_field_current(alpha, eps, footprint):
    """Low-density mean-field current of the extended TASEP with uniform hopping rate eps
    (Lakatos & Chou 2003, doi:10.1088/0305-4470/36/8/302; Shaw, Zia & Lee 2003, doi:10.1103/PhysRevE.68.021910)."""
    return alpha * (eps - alpha) / (eps + alpha * (footprint - 1))


def max_current(eps, footprint):
    """Maximal-current phase: J = eps / (1 + sqrt(footprint))^2 (same references)."""
    return eps / (1 + math.sqrt(footprint)) ** 2


def critical_alpha(eps, footprint):
    return eps / (1 + math.sqrt(footprint))
