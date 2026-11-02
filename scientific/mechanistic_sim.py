"""Numerical experiments on compiled SBML models (see mechanistic_sbml).

Every function runs SciPy integrators and returns numbers together with the
settings that produced them. Diagnostics describe the calculation (solver
status, conservation drift, tolerance sensitivity, negativity), which says
nothing about whether the underlying biology is right.
"""
import math, platform
import numpy as np
import scipy
from scipy.integrate import solve_ivp
from scipy.linalg import null_space
from scipy.optimize import least_squares, root
from scipy.stats import qmc, spearmanr

METHODS = ('LSODA', 'BDF', 'Radau', 'RK45', 'DOP853')
READOUTS = ('final', 'max', 'min', 'auc', 'time_of_max')
MAX_POINTS, MAX_RUNS = 2000, 400


class SimulationError(ValueError):
    pass


def _settings(model, t_end, points, method, rtol, atol):
    if not model.executable:
        raise SimulationError('This model cannot be executed: ' + '; '.join(model.unsupported))
    if not (isinstance(t_end, (int, float)) and math.isfinite(t_end) and t_end > 0):
        raise SimulationError('End time must be a positive number.')
    if method not in METHODS:
        raise SimulationError('Unknown integrator: ' + str(method))
    points = int(points)
    if not 2 <= points <= MAX_POINTS:
        raise SimulationError(f'Choose between 2 and {MAX_POINTS} output points.')
    if not (0 < rtol < 1e-2 and 0 < atol < 1):
        raise SimulationError('Tolerances must satisfy 0 < rtol < 1e-2 and 0 < atol < 1.')
    return float(t_end), points, method, float(rtol), float(atol)


def _scale(y):
    """Magnitude used to make absolute tolerances relative to the model's own units
    (SBML amounts can be ~1e-9 or ~1e6, so no fixed floor is safe)."""
    m = float(np.max(np.abs(y))) if np.size(y) else 0.0
    return m if m > 0 else 1.0


class _History:
    """State history for delay(): dense-output segments, with the initial state before t = 0 (SBML convention)."""
    def __init__(self, y0):
        self.y0, self.seg = np.asarray(y0, float), []

    def __call__(self, i, tt):
        if tt <= 0 or not self.seg:
            return float(self.y0[i])
        for a, b, f in reversed(self.seg):
            if a <= tt <= b + 1e-12:
                return float(f(min(tt, b))[i])
        return float(self.seg[-1][2](self.seg[-1][1])[i])


class _Piecewise:
    """Result of an event/delay integration, shaped like solve_ivp's (t, y, message, nfev, njev) plus the parameter vector in force at each output time."""
    def __init__(self, t, y, p_at, message, nfev, njev, fired):
        self.t, self.y, self.p_at, self.message, self.nfev, self.njev, self.success, self.fired = t, y, p_at, message, nfev, njev, True, fired


def _apply(model, k, vals, y, p):
    sp = {s['id']: s for s in model.species}
    for (var, _), v in zip(model.events[k]['assign'], vals):
        if var in model.state_index:
            i = model.state_index[var]; s = sp.get(var)
            y[i] = v * (model.compartment_size.get(s['compartment']) or 1.0) if s and model.state[i]['kind'] == 'amount' and not s['hasOnlySubstanceUnits'] else v
        elif var in model.param_index:
            p[model.param_index[var]] = v
        else:
            p[len(model.param_ids) + model.fixed_ids.index(var)] = v


def _integrate_hybrid(model, y0, p, t_end, points, method, rtol, atol, max_events=10000):
    """Piecewise integration for events (SBML trigger semantics: fire on false → true, exact time by bisection on the dense
    output; delayed events queued; values from trigger time by default) and delays (method of steps: chunks no longer than the
    shortest delay, delayed values read from the stored history)."""
    grid = np.linspace(0.0, t_end, points); scale = _scale(y0); hist = _History(y0); model._namespace['_hist'] = hist
    y, p = np.array(y0, float), np.array(p, float); t0 = 0.0
    taus = [float(x) for x in model._taus_fn(0.0, y, p)] if model._taus_fn else []
    if any(x <= 0 for x in taus):
        raise SimulationError('A delay must be positive.')
    chunk = min(taus) if taus else math.inf
    state = model._events_fn(0.0, y, p) if model.events else []
    state = [s if e['initialValue'] else False for s, e in zip(state, model.events)]
    queue, out_t, out_y, out_p, nfev, njev, fired, msg = [], [], [], [], 0, 0, 0, 'completed'
    while t0 < t_end - 1e-12 * max(1.0, t_end):
        t1 = min(t_end, t0 + chunk, min((q[0] for q in queue), default=math.inf))
        with np.errstate(divide='raise', invalid='raise', over='raise', under='ignore'):
            try:
                sol = solve_ivp(lambda tt, yy: model.rhs(tt, yy, p), (t0, t1), y, method=method, rtol=rtol, atol=atol * scale, dense_output=True, max_step=max((t_end) / 2000, 1e-9))
            except (FloatingPointError, ZeroDivisionError, OverflowError, ValueError) as e:
                raise SimulationError('The integration failed numerically: ' + str(e))
        if not sol.success:
            raise SimulationError('The integrator stopped: ' + sol.message)
        nfev += int(sol.nfev); njev += int(getattr(sol, 'njev', 0) or 0)
        t_stop, hit = t1, None
        if model.events:                                 # first false → true transition inside this segment
            prev = list(state)
            for k in range(1, len(sol.t)):
                now = model._events_fn(sol.t[k], sol.y[:, k], p)
                up = [i for i, (a, b) in enumerate(zip(prev, now)) if b and not a]
                if up:
                    lo, hi = sol.t[k - 1], sol.t[k]
                    for _ in range(60):
                        mid = (lo + hi) / 2; m = model._events_fn(mid, sol.sol(mid), p)
                        if any(m[i] and not prev[i] for i in up):
                            hi = mid
                        else:
                            lo = mid
                    t_stop, hit = hi, [i for i in up if model._events_fn(hi, sol.sol(hi), p)[i]] or up
                    break
                prev = now
        f = sol.sol; a = t0; b = t_stop
        hist.seg.append((a, b, f))
        sel = (grid >= a - 1e-12) & (grid <= b + 1e-12) & ~np.isin(grid, out_t)
        for g in grid[sel]:
            out_t.append(float(g)); out_y.append(f(g)); out_p.append(p.copy())
        y = np.array(f(b)); t0 = b
        if hit is not None:
            state = list(model._events_fn(b, y, p))
            for k in hit:
                vals, d = model._assign_fns[k](b, y, p)
                if d > 0:
                    queue.append((b + float(d), k, list(vals) if model.events[k]['fromTrigger'] else None))
                else:
                    _apply(model, k, vals, y, p); fired += 1
            state = list(model._events_fn(b, y, p))
        due = [q for q in queue if q[0] <= t0 + 1e-12]
        for q in sorted(due):
            queue.remove(q); k = q[1]
            if not model.events[k]['persistent'] and not model._events_fn(t0, y, p)[k]:
                continue                                 # non-persistent trigger went false before the delayed execution
            vals = q[2] if q[2] is not None else model._assign_fns[k](t0, y, p)[0]
            _apply(model, k, vals, y, p); fired += 1
        if due:
            state = list(model._events_fn(t0, y, p))
        if fired > max_events:
            msg = f'stopped after {max_events} events'; break
    order = np.argsort(out_t)
    return _Piecewise(np.array(out_t)[order], np.array(out_y).T[:, order], [out_p[i] for i in order], f'{msg}; {fired} event(s) fired' if model.events else msg, nfev, njev, fired)


def _integrate(model, y0, p, t_end, points, method, rtol, atol):
    if getattr(model, 'events', None) or getattr(model, 'delays', None):
        return _integrate_hybrid(model, y0, p, t_end, points, method, rtol, atol)
    t = np.linspace(0.0, t_end, points)
    scale = _scale(y0)
    with np.errstate(divide='raise', invalid='raise', over='raise', under='ignore'):
        try:
            sol = solve_ivp(lambda tt, yy: model.rhs(tt, yy, p), (0.0, t_end), y0, method=method, t_eval=t, rtol=rtol, atol=atol * scale)
        except (FloatingPointError, ZeroDivisionError, OverflowError, ValueError) as e:
            raise SimulationError('The integration failed numerically: ' + str(e))
    if not sol.success:
        raise SimulationError('The integrator stopped: ' + sol.message)
    return sol


def observables(model, sol, p):
    """Species symbols (concentrations unless amount-only) and assignment-rule values over time."""
    p_at = getattr(sol, 'p_at', None)                    # events can change parameters during the run
    rows = np.array([model.evaluate(tt, sol.y[:, k], p if p_at is None else p_at[k])[2] for k, tt in enumerate(sol.t)]).T
    return {sid: rows[i] for i, sid in enumerate(model.symbols)}


def conservation(model, y):
    """Conserved moieties from the left null space of the stoichiometry matrix and their relative drift."""
    amount = [i for i, s in enumerate(model.state) if s['kind'] == 'amount']
    if not amount or not model.reactions:
        return {'laws': 0, 'maxRelativeDrift': 0.0}
    N = model.stoichiometry[amount]
    C = null_space(N.T)
    if C.size == 0:
        return {'laws': 0, 'maxRelativeDrift': 0.0}
    totals = C.T @ y[amount]
    # Drift is judged against the size of the species in each law, not its total: a law whose total is 0 (a difference of
    # pools) would otherwise turn 1e-12 of round-off into a large "relative" drift.
    scale = np.abs(C).T @ np.abs(y[amount][:, :1])
    ref = np.maximum(np.maximum(np.abs(totals[:, :1]), scale), 1e-12 * max(1.0, float(np.max(np.abs(y)))))
    drift = float(np.max(np.abs(totals - totals[:, :1]) / ref))
    return {'laws': int(C.shape[1]), 'maxRelativeDrift': drift}


def simulate(model, t_end, points=400, method='LSODA', rtol=1e-8, atol=1e-10, overrides=None, initial=None, check=True):
    t_end, points, method, rtol, atol = _settings(model, t_end, points, method, rtol, atol)
    y0, p = model.prepare(overrides, initial)
    sol = _integrate(model, y0, p, t_end, points, method, rtol, atol)
    obs = observables(model, sol, p)
    diagnostics = {'status': sol.message, 'rhsEvaluations': int(sol.nfev), 'jacobianEvaluations': int(getattr(sol, 'njev', 0) or 0),
                   'conservation': conservation(model, sol.y),
                   'minimumState': float(sol.y.min()) if sol.y.size else 0.0}
    scale = _scale(sol.y)
    diagnostics['negativeValues'] = bool(diagnostics['minimumState'] < -1e-6 * scale)
    if check:
        # Re-solve 100× tighter: a large change means the reported curves depend on the tolerance.
        tight = _integrate(model, y0, p, t_end, points, method, rtol / 100, atol / 100)
        diff = float(np.max(np.abs(tight.y - sol.y)) / scale) if sol.y.size else 0.0
        diagnostics['toleranceSensitivity'] = diff
        diagnostics['reliable'] = diff < 1e-4 and diagnostics['conservation']['maxRelativeDrift'] < 1e-6 and not diagnostics['negativeValues']
    return {'time': sol.t.tolist(), 'series': {k: v.tolist() for k, v in obs.items()},
            'solver': {'library': 'SciPy ' + scipy.__version__, 'method': method, 'rtol': rtol, 'atol': atol, 'atolScaledBy': 'max |y0| (absolute tolerance = atol × largest initial state value)', 'tEnd': t_end, 'points': points},
            'parameters': dict(zip(model.param_ids, map(float, p))), 'initial': {s['id']: float(v) for s, v in zip(model.state, y0)},
            'overrides': dict(overrides or {}), 'initialOverrides': dict(initial or {}), 'diagnostics': diagnostics}


def readout(series, time, kind):
    x, t = np.asarray(series, float), np.asarray(time, float)
    if kind == 'final': return float(x[-1])
    if kind == 'max': return float(x.max())
    if kind == 'min': return float(x.min())
    if kind == 'auc': return float(np.trapezoid(x, t))
    if kind == 'time_of_max': return float(t[int(x.argmax())])
    raise SimulationError('Unknown readout: ' + str(kind))


def _run(model, t_end, points, method, rtol, atol, overrides, initial, target, kind):
    r = simulate(model, t_end, points, method, rtol, atol, overrides, initial, check=False)
    if target not in r['series']:
        raise SimulationError('Unknown output: ' + str(target))
    return r, readout(r['series'][target], r['time'], kind)


def _split(model, name, value):
    """A sweep variable is a parameter id or 'init:<species>'."""
    if name.startswith('init:'):
        return {}, {name[5:]: value}
    if name not in model.param_index:
        raise SimulationError('Unknown parameter: ' + name)
    return {name: value}, {}


def _values(spec):
    lo, hi, n = float(spec['min']), float(spec['max']), int(spec.get('steps', 9))
    if not (math.isfinite(lo) and math.isfinite(hi) and hi > lo and 2 <= n <= 60):
        raise SimulationError('A sweep needs finite min < max and 2–60 steps.')
    if spec.get('log'):
        if lo <= 0:
            raise SimulationError('Logarithmic sweeps need positive bounds.')
        return np.geomspace(lo, hi, n)
    return np.linspace(lo, hi, n)


def scan(model, t_end, sweep, target, kind='final', points=200, method='LSODA', rtol=1e-8, atol=1e-10, base=None, initial=None):
    """One-dimensional scan: one simulation per value."""
    values = _values(sweep)
    curves, outs = [], []
    for v in values:
        o, i = _split(model, sweep['name'], v)
        r, y = _run(model, t_end, points, method, rtol, atol, {**(base or {}), **o}, {**(initial or {}), **i}, target, kind)
        curves.append(r['series'][target]); outs.append(y)
    return {'values': values.tolist(), 'readout': outs, 'time': r['time'], 'curves': curves, 'target': target, 'kind': kind, 'sweep': sweep}


def scan2d(model, t_end, a, b, target, kind='final', points=150, method='LSODA', rtol=1e-7, atol=1e-9, base=None, initial=None):
    va, vb = _values(a), _values(b)
    if len(va) * len(vb) > MAX_RUNS:
        raise SimulationError(f'A two-dimensional scan is limited to {MAX_RUNS} simulations.')
    grid = []
    for x in va:
        row = []
        for y in vb:
            o1, i1 = _split(model, a['name'], x); o2, i2 = _split(model, b['name'], y)
            row.append(_run(model, t_end, points, method, rtol, atol, {**(base or {}), **o1, **o2}, {**(initial or {}), **i1, **i2}, target, kind)[1])
        grid.append(row)
    return {'a': {**a, 'values': va.tolist()}, 'b': {**b, 'values': vb.tolist()}, 'grid': grid, 'target': target, 'kind': kind}


def uncertainty(model, t_end, ranges, target, kind='final', samples=64, seed=1, points=150, method='LSODA', rtol=1e-7, atol=1e-9, base=None, initial=None):
    """Latin-hypercube propagation of parameter ranges, with percentile bands and
    Spearman rank correlations as a global sensitivity measure."""
    if not ranges:
        raise SimulationError('Choose at least one uncertain parameter.')
    samples = int(samples)
    if not 8 <= samples <= MAX_RUNS:
        raise SimulationError(f'Use between 8 and {MAX_RUNS} samples.')
    sampler = qmc.LatinHypercube(d=len(ranges), seed=int(seed))
    u = sampler.random(samples)
    X = np.empty_like(u)
    for j, r in enumerate(ranges):
        lo, hi = float(r['min']), float(r['max'])
        if not hi > lo:
            raise SimulationError('Each range needs min < max.')
        if r.get('log'):
            if lo <= 0:
                raise SimulationError('Log-uniform ranges need positive bounds.')
            X[:, j] = np.exp(np.log(lo) + u[:, j] * (np.log(hi) - np.log(lo)))
        else:
            X[:, j] = lo + u[:, j] * (hi - lo)
    outs, curves, failures = [], [], 0
    for row in X:
        o, i = {}, {}
        for r, v in zip(ranges, row):
            a, b = _split(model, r['name'], v); o.update(a); i.update(b)
        try:
            res, y = _run(model, t_end, points, method, rtol, atol, {**(base or {}), **o}, {**(initial or {}), **i}, target, kind)
            outs.append(y); curves.append(res['series'][target]); time = res['time']
        except SimulationError:
            outs.append(math.nan); failures += 1
    outs = np.asarray(outs)
    ok = ~np.isnan(outs)
    C = np.asarray(curves)
    sensitivity = []
    for j, r in enumerate(ranges):
        rho = spearmanr(X[ok, j], outs[ok]).statistic if ok.sum() > 3 and np.ptp(outs[ok]) > 0 else math.nan
        sensitivity.append({'name': r['name'], 'spearman': None if math.isnan(rho) else float(rho)})
    sensitivity.sort(key=lambda s: -abs(s['spearman'] or 0))
    return {'samples': X.tolist(), 'readout': [None if math.isnan(v) else float(v) for v in outs], 'failures': failures,
            'time': time if curves else [], 'bands': {q: np.percentile(C, q, axis=0).tolist() for q in (5, 25, 50, 75, 95)} if curves else {},
            'summary': {q: float(np.nanpercentile(outs, q)) for q in (5, 50, 95)} if ok.any() else {},
            'sensitivity': sensitivity, 'seed': int(seed), 'method': 'Latin hypercube (SciPy qmc), Spearman rank correlation', 'target': target, 'kind': kind}


def local_sensitivity(model, t_end, target, kind='final', parameters=None, step=0.01, points=200, method='LSODA', rtol=1e-9, atol=1e-11, base=None, initial=None):
    """Normalised sensitivity S = ∂ ln y / ∂ ln p by central differences (±step)."""
    names = parameters or [pid for pid in model.param_ids if model.parameter_vector_value(pid, base) != 0][:80]
    _, y0 = _run(model, t_end, points, method, rtol, atol, base, initial, target, kind)
    result = []
    for name in names:
        v = model.parameter_vector_value(name, base)
        if v == 0:
            result.append({'name': name, 'sensitivity': None, 'note': 'parameter is zero'}); continue
        up = _run(model, t_end, points, method, rtol, atol, {**(base or {}), name: v * (1 + step)}, initial, target, kind)[1]
        dn = _run(model, t_end, points, method, rtol, atol, {**(base or {}), name: v * (1 - step)}, initial, target, kind)[1]
        s = (up - dn) / (2 * step * y0) if y0 != 0 else None
        result.append({'name': name, 'sensitivity': s})
    result.sort(key=lambda r: -abs(r['sensitivity'] or 0))
    return {'baseline': y0, 'step': step, 'target': target, 'kind': kind, 'coefficients': result}


def steady_state(model, overrides=None, initial=None, t_relax=1e4):
    """Relax by integration, then polish with a root solve restricted to the same conservation class."""
    y0, p = model.prepare(overrides, initial)
    sol = _integrate(model, y0, p, t_relax, 2, 'LSODA', 1e-9, 1e-12)
    y = sol.y[:, -1]
    amount = [i for i, s in enumerate(model.state) if s['kind'] == 'amount']
    C = null_space(model.stoichiometry[amount].T) if amount and model.reactions else np.zeros((len(amount), 0))
    totals = C.T @ y[amount] if C.size else np.zeros(0)
    def residual(x):
        f = np.asarray(model.rhs(0.0, x, p), float)
        if C.size:
            f = np.concatenate([f, C.T @ x[amount] - totals])
        return f
    polished = least_squares(residual, y, xtol=1e-14, ftol=1e-14, gtol=1e-14)
    ys = polished.x
    resid = float(np.max(np.abs(np.asarray(model.rhs(0.0, ys, p), float)))) if len(ys) else 0.0
    J = _jacobian(model, ys, p)
    eig = np.linalg.eigvals(J) if J.size else np.zeros(0)
    # Eigenvalues tied to conservation laws are ~0 and carry no stability information.
    moving = eig[np.abs(eig) > 1e-9 * max(1.0, float(np.max(np.abs(eig))) if eig.size else 1.0)]
    stable = bool(moving.size == 0 or np.max(moving.real) < 0)
    obs = {sid: float(v) for sid, v in zip(model.symbols, model.evaluate(0.0, ys, p)[2])}
    return {'values': obs, 'maxDerivative': resid, 'stable': stable, 'leadingEigenvalue': float(np.max(moving.real)) if moving.size else None,
            'note': 'A steady state found by relaxation from the initial conditions; other steady states may exist.'}


def _jacobian(model, y, p, eps=1e-7):
    n = len(y); J = np.zeros((n, n)); f0 = np.asarray(model.rhs(0.0, y, p), float)
    for i in range(n):
        h = eps * max(1.0, abs(y[i])); z = y.copy(); z[i] += h
        J[:, i] = (np.asarray(model.rhs(0.0, z, p), float) - f0) / h
    return J


def fit(model, data, parameters, t_end=None, method='LSODA', rtol=1e-8, atol=1e-10, base=None, initial=None):
    """Least-squares estimation (log-parameter space) against measured points [{time, output, value, sd?}].
    Returns estimates, residuals and approximate standard errors from the Jacobian."""
    if not data or not parameters:
        raise SimulationError('Fitting needs data points and at least one parameter.')
    for d in data:
        if d['output'] not in model.symbols or not math.isfinite(float(d['value'])) or float(d['time']) < 0:
            raise SimulationError('Each data point needs a known output, a non-negative time and a finite value.')
    times = sorted({float(d['time']) for d in data})
    t_end = float(t_end or max(times) or 1.0)
    grid = np.unique(np.concatenate([[0.0], times]))
    for p in parameters:
        if model.parameter_vector_value(p['name'], base) <= 0 and not p.get('min'):
            raise SimulationError('Fitted parameters must be positive (estimated on a log scale).')
    x0 = np.log([float(p.get('start') or model.parameter_vector_value(p['name'], base)) for p in parameters])
    lo = np.log([float(p.get('min', 1e-12)) for p in parameters]); hi = np.log([float(p.get('max', 1e12)) for p in parameters])
    def predict(x):
        o = {**(base or {}), **{p['name']: float(np.exp(v)) for p, v in zip(parameters, x)}}
        y0, pv = model.prepare(o, initial)
        sol = solve_ivp(lambda tt, yy: model.rhs(tt, yy, pv), (0, t_end), y0, method=method, t_eval=grid, rtol=rtol, atol=atol * _scale(y0))
        if not sol.success:
            return None
        obs = {k: np.asarray(v) for k, v in zip(model.symbols, np.array([model.evaluate(tt, sol.y[:, k], pv)[2] for k, tt in enumerate(sol.t)]).T)}
        return {d_i: float(np.interp(float(d['time']), sol.t, obs[d['output']])) for d_i, d in enumerate(data)}
    def residuals(x):
        pr = predict(x)
        if pr is None:
            return np.full(len(data), 1e6)
        return np.array([(pr[i] - float(d['value'])) / float(d.get('sd') or 1.0) for i, d in enumerate(data)])
    res = least_squares(residuals, np.clip(x0, lo, hi), bounds=(lo, hi), x_scale='jac')
    dof = max(1, len(data) - len(parameters)); s2 = float(res.fun @ res.fun) / dof
    try:
        cov = np.linalg.inv(res.jac.T @ res.jac) * s2
        se_log = np.sqrt(np.clip(np.diag(cov), 0, None))
    except np.linalg.LinAlgError:
        se_log = np.full(len(parameters), np.nan)
    est = np.exp(res.x)
    return {'estimates': [{'name': p['name'], 'value': float(v), 'approxRelativeSE': None if math.isnan(s) else float(s)} for p, v, s in zip(parameters, est, se_log)],
            'residuals': res.fun.tolist(), 'cost': float(res.cost), 'converged': bool(res.success), 'message': res.message,
            'note': 'Standard errors are a local linear approximation in log-parameter space; check identifiability before trusting them.'}


def environment():
    return {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__}
