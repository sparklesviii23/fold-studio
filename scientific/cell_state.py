"""One state and readout interface for experiments that turn modelled molecule numbers into what an assay reads and
into particles in a 3-D cell (light_pulse, hela_erk).

A state is a set of named series on a kinetic clock, each with a unit and the expression it comes from. A readout maps
molecule numbers to what the instrument reports and says whether that mapping is calibrated or relative. The display
hand-off turns numbers into weighted particles on a slower display clock: particle i of a species is present while
i < round(count / weight), and every frame draws fresh positions inside the species' compartments, because the cells
modelled here mix far faster than the display interval. Particle paths between frames have no meaning.
"""
import math

import numpy as np

SCHEMA_VERSION = 1


def describe(schema, version, variables, clocks, handoffs, readout):
    """The description saved with every run: what the state holds, on which clocks, and how it is handed on."""
    return {'schema': schema, 'version': version, 'interface': 'fold-studio.cell-state/' + str(SCHEMA_VERSION), 'variables': variables, 'clocks': clocks, 'handoffs': handoffs, 'readout': readout}


def check(name, passed, threshold, value, detail):
    return {'name': name, 'passed': bool(passed), 'applicable': True, 'threshold': threshold, 'value': value, 'detail': detail}


def balance(name, total, produced, removed, dt, detail, tolerance=5e-3):
    """Conservation of a molecule total over a run: change = ∫produced − ∫removed (trapezoid on the kinetic clock)."""
    made = float(np.sum((produced[1:] + produced[:-1]) / 2) * dt); lost = float(np.sum((removed[1:] + removed[:-1]) / 2) * dt)
    gap = float(total[-1] - total[0] - (made - lost)); scale = float(max(np.max(total), made, 1.0))
    return check(name, abs(gap) / scale < tolerance, f'change in molecules = produced − removed, within {100 * tolerance:g} % of the largest total',
                 {'start': float(total[0]), 'end': float(total[-1]), 'produced': made, 'diluted': lost, 'gap': gap, 'relativeGap': abs(gap) / scale}, detail)


def same_series(name, a, b, detail, value=None):
    """Two outputs that must be one series (for example fluorescence and φ × molecules)."""
    diff = float(np.max(np.abs(np.asarray(a) - np.asarray(b)) / np.maximum(np.abs(np.asarray(b)), 1e-300)))
    return check(name, diff < 1e-12, 'identical apart from the stated constant', {'maxRelativeDifference': diff, **(value or {})}, detail)


def display_clock(n_points, frames):
    return np.unique(np.round(np.linspace(0, n_points - 1, frames)).astype(int))


def particles(cls, voxel, species, at, seed, capacity, weight=None, groups=None):
    """Weighted display particles.

    cls       class grid [z, y, x];  voxel  (x, y, z) edge in µm
    species   [{key, name, classes: [class ids], counts: array on the kinetic clock, group: 'a' | None, ...}]
              species sharing a `group` share one weight chosen so the group's largest total fits `capacity`;
              a species without a group has weight 1
    at        indices of the kinetic clock that make the display clock
    Returns frames (µm, flat x y z per particle), absent slots per frame, per-species numbers, and the checks."""
    v = np.array(voxel, float); rng = np.random.default_rng([int(seed), 31337]); F = len(at)
    voxels = {sp['key']: np.argwhere(np.isin(cls, sp['classes'])) for sp in species}
    for sp in species:
        if not len(voxels[sp['key']]):
            raise ValueError(f"The compartment of {sp['name']} is not present in this cell.")
    weights = {}
    for g in sorted({sp.get('group') for sp in species if sp.get('group')}):
        peak = float(sum(np.asarray(sp['counts'], float) for sp in species if sp.get('group') == g).max())
        w = max(1, int(math.ceil(peak / capacity)))
        if weight is not None:                                          # a common scale for two runs shown side by side; never finer than this run's own
            if not w <= int(weight) <= 10 ** 9:
                raise ValueError(f'The display weight must be at least {w} molecules per particle for this run.')
            w = int(weight)
        weights[g] = (w, peak)
    out = []; owner = []; slots = {}
    for i, sp in enumerate(species):
        w = weights[sp['group']][0] if sp.get('group') else 1
        counts = np.asarray(sp['counts'], float)[at]; shown = np.floor(counts / w + 0.5).astype(int); cap = int(shown.max())
        slots[sp['key']] = (len(owner), cap, shown); owner += [i] * cap
        out.append({**{k: x for k, x in sp.items() if k not in ('counts', 'classes', 'group')}, 'capacity': cap, 'weight': w, 'molecules': counts.tolist(), 'particles': shown.tolist()})
    n = len(owner); frames = []; absent = []; outside = 0
    for f in range(F):
        pos = np.zeros((n, 3)); gone = []
        for sp in species:
            start, cap, shown = slots[sp['key']]; vox = voxels[sp['key']]
            pick = vox[rng.integers(0, len(vox), cap)]                                     # rows are [z, y, x]
            pos[start:start + cap] = (pick[:, ::-1] + rng.random((cap, 3))) * v
            present = int(shown[f]); gone += list(range(start + present, start + cap))
            outside += int(np.sum(~np.isin(cls[pick[:present, 0], pick[:present, 1], pick[:present, 2]], sp['classes'])))
        frames.append(np.round(pos.ravel(), 4).tolist()); absent.append(gone)
    worst = {sp['key']: float(np.max(np.abs(np.array(sp['particles']) * sp['weight'] - np.array(sp['molecules'])))) for sp in out}
    main = max(weights.values(), key=lambda x: x[1]) if weights else (1, 0.0)
    checks = [check('Weighted particles', all(worst[sp['key']] <= sp['weight'] / 2 + 1e-9 for sp in out), 'particles × weight within half a weight of the molecule number, in every frame',
                    {'weight': {sp['key']: sp['weight'] for sp in out}, 'largestDifference': worst, 'peakMolecules': main[1], 'relativeAtPeak': (main[0] / 2) / main[1] if main[1] else None},
                    f'Each particle of a weighted species stands for {main[0]} molecule{"s" if main[0] > 1 else ""}; the number shown beside the view is the molecule number, not the number of particles.'),
              check('Compartments', outside == 0, 'every particle inside its compartment', {'outside': outside}, 'Each species is drawn only in the compartments it is assigned to.')]
    return {'owner': owner, 'frames': frames, 'absent': absent, 'species': out, 'weight': main[0], 'seed': int(seed), 'checks': checks, 'passed': all(c['passed'] for c in checks)}
