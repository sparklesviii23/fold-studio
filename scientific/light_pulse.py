"""Virtual light-pulse experiment: a light-responsive reporter in E. coli, fitted to and tested against published time courses.

Data (fixtures/light_pulse/olson2017_ccasr.json, CC BY 4.0): Olson EJ, Tzouanas CN, Tabor JJ. A photoconversion model
for full spectral programming and multiplexing of optogenetic systems. Mol Syst Biol 2017;13:926
(doi:10.15252/msb.20167456), Dataset EV2. E. coli BW29655 carrying the green-activated, red-deactivated CcaS/CcaR
two-component system driving superfolder GFP; flow cytometry population means in MEFL. One 24-well plate is one schedule:
every well runs the same light program shifted in time, so the 24 wells are 24 time points of one time course. The bundle
holds 8 step-on and 8 step-off schedules at 0.16-20 µmol m⁻² s⁻¹ of green light and four 480-min dynamic programs
(green only; a 380 nm LED; green with a red perturbation; green re-optimised against that perturbation), three runs each.

Model chain (evidence category B, fitted to a subset of the measured schedules):
  light I(t) -> regulator activity a  ->  transcription drive T(a)  ->  mRNA m  ->  immature reporter u  ->  fluorescent reporter g
  da/dt = k1·I·(1 − a) − (k2·I + kdr + kg)·a          photoconversion, dark reversion, dilution (the published photoconversion step)
  T(a)  = b + A·rⁿ/(Kⁿ + rⁿ),  r = a/(1 − a)          promoter output at steady state, MEFL
  dm/dt = km·(T − m);  du/dt = (kmat + kg)·(m − u);  dg/dt = kg·(u − g)
m, u and g are expressed in the units of the reporter they would produce at steady state (MEFL), so each stage has unit
gain and the readout is g. km is not identifiable from fluorescence and is an assumption; the others are fitted.

Three predictors are compared on whole schedules held out from fitting, with a static dose-response as the simple baseline:
  mechanistic  the chain above
  learned      ridge regression on a bank of low-pass filtered, saturating light features (no mechanism)
  combined     the mechanistic prediction plus a ridge-regressed residual on the same features
Version 2 adds the other wavelengths. Every LED has its own pair of photoconversion rates,
  da/dt = (k1·I_green + Σ k1_led·I_led)·(1 − a) − (k2·I_green + Σ k2_led·I_led + kdr + kg)·a
calibrated on the forward and reverse action spectra of the same paper (fixtures/light_pulse/olson2017_ccasr_spectral.json):
steady-state points with one LED alone and with that LED on top of green light. The green chain is fitted first and is not
refitted, so every green-only result of version 1 is unchanged. Three stages are kept apart:
  calibration      action-spectrum points of one LED fit that LED's k1 and k2
  model selection  whether an LED activates, deactivates, both or neither is chosen by leaving one experimental run out at a
                   time, inside the action spectra
  final test       complete dynamic schedules with red light on top of green (and one driven by a 380 nm LED), never fitted
The mixed-colour schedules were scored as a failure case of the green-only model before the red input existed, so they are
not untouched: their result is labelled retrospective. The green-only chain stays available as a regression case.

One versioned state (STATE) carries regulator activity, transcription, reporter production, maturation and abundance in
stated units. Reporter molecules are the single source of both the predicted fluorescence and the particles drawn in 3-D.

The nominal trajectory of every saved experiment is recomputed with the Mechanistic Lab solver (SBML rate rules and events,
SciPy LSODA) and compared with the fast exponential integrator used for fitting.
"""
import datetime, hashlib, json, math, pathlib, platform, re, uuid

import numpy as np

from light_pulse_actions import ACTIONS

VERSION = '2.0.0'
FIXTURE = pathlib.Path(__file__).resolve().parents[1] / 'fixtures' / 'light_pulse' / 'olson2017_ccasr.json'
SPECTRAL = FIXTURE.with_name('olson2017_ccasr_spectral.json')
CONTEXT = 'ecoli-bw29655-ccasr'
GREEN = '520-2-KB'                          # the LED of every green program; its k1 and k2 belong to the fitted chain
LN2 = math.log(2.0)
# Held out as whole schedules; never seen by any fit. `scope` says whether the model has every input the schedule uses.
SPLIT = {
    'train': ['step-on-0.15625', 'step-on-0.3125', 'step-on-0.625', 'step-on-2.5', 'step-on-5', 'step-on-10',
              'step-off-0.15625', 'step-off-0.3125', 'step-off-1.25', 'step-off-2.5', 'step-off-5', 'step-off-20'],
    'heldOut': ['step-on-1.25', 'step-on-20', 'step-off-0.625', 'step-off-10', 'dynamic-green'],
    'mixedColour': ['dynamic-green-red-perturbation', 'dynamic-green-red-compensated'],     # final test: complete schedules, red on top of green
    'otherColour': ['dynamic-uv'],                                                          # final test: a 380 nm LED alone drives the program
}
FINAL_TEST = SPLIT['mixedColour'] + SPLIT['otherColour']
# How an LED may act on the sensor; chosen per LED by leave-one-run-out inside its action spectrum. Simpler first.
STRUCTURES = ('none', 'off', 'on', 'both')
STRUCTURE_NAME = {'none': 'no effect', 'off': 'switches the sensor off', 'on': 'switches the sensor on', 'both': 'switches the sensor on and off'}
CHANNEL_BOUNDS = (1e-7, 50.0)
SPECTRAL_STEP = 8.0                        # min: step of the 480-minute constant-light runs used for calibration
# key, unit, description, initial guess, lower, upper
PARAMS = [
    ('k1', 'm² s µmol⁻¹ min⁻¹', 'Activation of the sensor by green light, per unit intensity', 0.1, 1e-4, 50.0),
    ('k2', 'm² s µmol⁻¹ min⁻¹', 'Deactivation of the sensor by green light, per unit intensity', 0.01, 1e-6, 50.0),
    ('kdr', 'min⁻¹', 'Dark reversion of the active sensor', 0.003, 1e-6, 1.0),
    ('kg', 'min⁻¹', 'Dilution by growth', LN2 / 37.4, 0.006, 0.06),
    ('b', 'MEFL', 'Reporter level in the dark', 2000.0, 100.0, 2e4),
    ('A', 'MEFL', 'Light-inducible range of the reporter', 1.1e5, 1e4, 1e6),
    ('n', '', 'Hill coefficient of the promoter response', 2.0, 0.5, 6.0),
    ('K', '', 'Active-to-inactive sensor ratio at half-maximal promoter output', 1.0, 1e-3, 1e3),
    ('kmat', 'min⁻¹', 'Maturation of the reporter into its fluorescent form', 0.08, 0.005, 2.0),
]
KEYS = [p[0] for p in PARAMS]
ASSUMED = {'km': {'value': LN2 / 3.0, 'unit': 'min⁻¹', 'description': 'mRNA turnover (decay plus dilution)',
                  'provenance': {'kind': 'assumed', 'note': 'A 3-minute mRNA half-life, typical for E. coli transcripts; not measured for this reporter. Fluorescence cannot separate it from maturation, which is fitted.'}}}
MEASURED = {'doublingMin': 37.4, 'kg': LN2 / 37.4, 'source': 'Growth rate of the CcaSR strain reported in the paper (37.4 min per doubling); not used in the fit, compared with the fitted dilution rate.'}
FILTER_K = (0.1, 0.5, 2.0, 8.0)            # µmol m⁻² s⁻¹: saturation constants of the learned features
FILTER_TAU = (10.0, 30.0, 90.0, 270.0)     # min: low-pass time constants of the learned features
RIDGE = (1e-3, 1e-2, 1e-1, 1.0, 10.0)
ENSEMBLE = 200
GATE = {'rmseLog10': 0.15, 'beatsBaselineBy': 2.0}
SELECT_MARGIN = 0.05
FEATURE_MISS = 0.25                        # a response feature more than 25 % off is reported as a miss even when the trajectory error passes
LIMITS = {'durationMin': (10.0, 1440.0), 'intensity': (0.0, 20.0), 'steps': 200, 'otherSteps': 600, 'samples': 200}
ENGINE = {
    'id': 'fold.light-pulse.ccasr', 'name': 'Light-pulse reporter response', 'version': VERSION, 'evidence': 'B',
    'numericalMethod': 'Piecewise-constant light; the regulator equation is advanced exactly over each step and the three linear stages with the step-averaged forcing of the stage above (second order). Nominal runs are recomputed by the Mechanistic Lab solver (SBML rate rules and events, SciPy LSODA).',
    'equations': ['da/dt = (k1·I + Σ k1_led·I_led)·(1 − a) − (k2·I + Σ k2_led·I_led + kdr + kg)·a', 'T = b + A·rⁿ/(Kⁿ + rⁿ), r = a/(1 − a)', 'dm/dt = km·(T − m)', 'du/dt = (kmat + kg)·(m − u)', 'dg/dt = kg·(u − g)'],
    'assumptions': ['A well-mixed population average: one cell stands for the mean of the culture', 'Exponential growth at a constant rate for the whole experiment',
                    'Light reaches every cell at the programmed intensity (the paper harvests at low density for this reason)', 'The culture starts dark-adapted; preconditioning light is simulated for its recorded duration',
                    'mRNA turnover is an assumed constant'],
    'limits': ['Fitted to one strain, one reporter, one medium and 37 °C; other conditions are extrapolation', 'Other LEDs enter through two rates each, calibrated on steady-state action spectra only: their dynamics are a prediction',
               'The learned predictor and the static baseline see green light only',
               'Population mean only: the model does not predict cell-to-cell variation; the measured spread is shown beside it', 'Intensities above 20 µmol m⁻² s⁻¹ were not measured',
               'No spatial structure: molecules equilibrate across a bacterium in tens of milliseconds, far faster than any modelled step'],
}


class PulseError(ValueError):
    pass


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), default=float).encode()).hexdigest()


_DATA = None


def dataset():
    global _DATA
    if _DATA is None:
        if not FIXTURE.is_file():
            raise PulseError('The light-pulse dataset is missing from this installation.')
        raw = FIXTURE.read_bytes()
        _DATA = json.loads(raw); _DATA['sha256'] = hashlib.sha256(raw).hexdigest()
        _DATA['byId'] = {s['id']: s for s in _DATA['schedules']}
    return _DATA


_SPEC = None


def spectral():
    """Forward and reverse action spectra and the published model parameters (see scripts/build-light-pulse-spectral.py)."""
    global _SPEC
    if _SPEC is None:
        if not SPECTRAL.is_file():
            raise PulseError('The action-spectrum dataset is missing from this installation.')
        raw = SPECTRAL.read_bytes()
        _SPEC = json.loads(raw); _SPEC['sha256'] = hashlib.sha256(raw).hexdigest()
        _SPEC['byLed'] = {l['id']: l for l in _SPEC['leds']}
    return _SPEC


def data_sha():
    """One identifier for everything the fit reads: the time courses and the action spectra."""
    return hashlib.sha256((dataset()['sha256'] + spectral()['sha256']).encode()).hexdigest()


# ------------------------------------------------------------------ light programs

def program_values(program, times):
    """Intensity at each time (min) of a program {'pre': I before t = 0, 'steps': [[t, I], …]}."""
    steps = program['steps']; ts = np.array([s[0] for s in steps], float); vs = np.array([s[1] for s in steps], float)
    idx = np.searchsorted(ts, np.asarray(times, float) + 1e-9, side='right') - 1
    return np.where(idx >= 0, vs[np.clip(idx, 0, len(vs) - 1)], float(program.get('pre') or 0.0))


def well_light(schedule, t, total=480):
    """Per-minute green intensity seen by the well harvested at experiment time t: the recorded program shifted so the
    well is harvested at the end of the `total`-minute culture."""
    return program_values(schedule['program'], np.arange(total) + 0.5 - (total - t))


def well_inputs(schedule, t, total=480):
    """Per-minute intensity of every LED seen by the well harvested at experiment time t: {led: array of `total`}.
    The second LED of a mixed-colour schedule is recorded per minute; before the program starts it is dark."""
    times = np.arange(total) + 0.5 - (total - t)
    out = {schedule.get('led') or GREEN: program_values(schedule['program'], times)}
    if schedule.get('second'):
        pm = np.asarray(schedule['second']['perMinute'], float); idx = np.floor(times).astype(int)
        out[schedule['second']['led']] = np.where(idx >= 0, pm[np.clip(idx, 0, len(pm) - 1)], 0.0)
    return out


def stack_inputs(rows):
    """[{led: array}] -> {led: matrix (points × steps)}, zeros where a point does not use an LED."""
    leds = sorted({k for r in rows for k in r}); n = len(next(iter(rows[0].values())))
    return {led: np.array([r.get(led, np.zeros(n)) for r in rows]) for led in leds}


def green_of(inputs):
    any_ = next(iter(inputs.values()))
    return inputs.get(GREEN, np.zeros_like(any_))


def other_rates(channels, inputs):
    """Extra switching-on and switching-off rates (min⁻¹) from every LED that is not the green one, or None.
    `channels[led]` holds k1 and k2 as numbers, or as one value per point."""
    extra = [led for led in inputs if led != GREEN and np.any(inputs[led])]
    if not extra:
        return None
    on = 0.0; off = 0.0
    for led in extra:
        if led not in channels:
            raise PulseError(f'The LED {led} has no calibrated response.')
        k1, k2 = (np.asarray(channels[led][k], float) for k in ('k1', 'k2'))
        on = on + (k1[:, None] if k1.ndim else k1) * inputs[led]; off = off + (k2[:, None] if k2.ndim else k2) * inputs[led]
    return on, off


def points_of(ids, include_excluded=False):
    """All measured points of the named schedules: light matrix (points × 480), observed MEFL, and their identity."""
    d = dataset(); light, obs, who = [], [], []
    for sid in ids:
        s = d['byId'][sid]
        for ri, rep in enumerate(s['replicates']):
            for p in rep['points']:
                if p.get('excluded') and not include_excluded:
                    continue
                light.append(well_light(s, p['t'])); obs.append(p['fl']); who.append((sid, ri, p['t']))
    return np.array(light), np.array(obs), who


# ------------------------------------------------------------------ mechanistic model

def hill(theta, a):
    r = a / np.maximum(1.0 - a, 1e-12)
    rn = np.power(np.maximum(r, 0.0), theta['n'])
    return theta['b'] + theta['A'] * rn / (theta['K'] ** theta['n'] + rn)


def integrate(theta, light, dt=1.0, state=None, record=False, other=None):
    """Advance the chain through `light` (points × steps, one green intensity per step of `dt` minutes). `other` is a pair
    of matrices of the same shape: the switching-on and switching-off rates contributed by every other LED.

    The regulator equation is linear for constant light and is advanced exactly. Each downstream stage is a first-order
    lag driven by the stage above; it is advanced with that stage's exact average over the step. Returns the final reporter
    level per point, or with `record` the full trajectories {a, T, m, u, g} (points × steps + 1) and the final state."""
    light = np.atleast_2d(np.asarray(light, float)); P, N = light.shape
    km = theta.get('km', ASSUMED['km']['value']); ku = theta['kmat'] + theta['kg']; kg = theta['kg']      # scalars, or one value per point
    em, eu, eg = np.exp(-km * dt), np.exp(-ku * dt), np.exp(-kg * dt)
    fm, fu, fg = (1 - em) / (km * dt), (1 - eu) / (ku * dt), (1 - eg) / (kg * dt)      # mean of the transient over a step
    if state is None:
        a = np.zeros(P); m = hill(theta, a) * np.ones(P); u = m.copy(); g = m.copy()
    else:
        a, m, u, g = (np.array(x, float) for x in state)
    out = {k: np.empty((P, N + 1)) for k in 'aTmug'} if record else None
    if record:
        out['a'][:, 0], out['T'][:, 0], out['m'][:, 0], out['u'][:, 0], out['g'][:, 0] = a, hill(theta, a), m, u, g
    for j in range(N):
        I = light[:, j]
        k_on = theta['k1'] * I; rate = k_on + theta['k2'] * I + theta['kdr'] + theta['kg']
        if other is not None:
            k_on = k_on + other[0][:, j]; rate = rate + other[0][:, j] + other[1][:, j]
        a_inf = k_on / rate; e = np.exp(-rate * dt)
        a_mean = a_inf + (a - a_inf) * (1 - e) / (rate * dt)
        a = a_inf + (a - a_inf) * e
        T = hill(theta, a_mean)
        m_mean = T + (m - T) * fm; m = T + (m - T) * em
        u_mean = m_mean + (u - m_mean) * fu; u = m_mean + (u - m_mean) * eu
        g = u_mean + (g - u_mean) * eg
        if record:
            out['a'][:, j + 1], out['T'][:, j + 1], out['m'][:, j + 1], out['u'][:, j + 1], out['g'][:, j + 1] = a, hill(theta, a), m, u, g
    if record:
        return out, (a, m, u, g)
    return g


def _theta(x):
    return {k: float(v) for k, v in zip(KEYS, np.exp(x))}


def fit_mechanistic(light, obs, starts=6, seed=11):
    """Least squares on log10 fluorescence in log-parameter space, from several seeded starting points."""
    from scipy.optimize import least_squares
    lo = np.log([p[4] for p in PARAMS]); hi = np.log([p[5] for p in PARAMS]); x0 = np.log([p[3] for p in PARAMS])
    target = np.log10(obs)
    resid = lambda x: np.log10(np.maximum(integrate(_theta(x), light), 1e-9)) - target
    rng = np.random.default_rng(seed); best = None; costs = []
    for s in range(starts):
        start = x0 if s == 0 else np.clip(x0 + rng.normal(0, 0.8, len(x0)), lo + 1e-6, hi - 1e-6)
        try:
            r = least_squares(resid, start, bounds=(lo, hi), x_scale=1.0, max_nfev=400)
        except Exception:
            continue
        costs.append(float(2 * r.cost))
        if best is None or r.cost < best.cost:
            best = r
    if best is None:
        raise PulseError('The model could not be fitted to the training schedules.')
    n, k = len(target), len(KEYS)
    s2 = 2 * best.cost / max(1, n - k)
    jtj = best.jac.T @ best.jac
    cov = s2 * np.linalg.pinv(jtj)
    se = np.sqrt(np.maximum(np.diag(cov), 0.0))                         # standard error of ln(parameter)
    at_bound = [bool(abs(v - a) < 1e-4 or abs(v - b) < 1e-4) for v, a, b in zip(best.x, lo, hi)]
    return {'x': best.x.tolist(), 'theta': _theta(best.x), 'cov': cov.tolist(), 'seLog': se.tolist(), 'atBound': at_bound, 'rmseLog10': float(np.sqrt(2 * best.cost / n)),
            'points': n, 'starts': starts, 'startCosts': sorted(costs), 'seed': seed, 'ensemble': ensemble(best.x, cov, 2 * best.cost, light, target, lo, hi, seed)}


def stack(xs):
    """Parameter sets (rows of log-parameters) as one dict of arrays, for a single vectorised pass."""
    xs = np.atleast_2d(xs)
    return {k: np.exp(xs[:, i]) for i, k in enumerate(KEYS)}


def ensemble(x, cov, sse, light, target, lo, hi, seed, draws=2000, keep=ENSEMBLE):
    """Parameter sets the training data cannot tell apart from the best fit.

    Candidates are drawn from the fit's covariance in log-parameter space and kept only when their training error stays
    inside the joint 95 % confidence region (F-test on the sum of squares). The covariance alone is a linearisation and
    badly overstates the spread along poorly determined directions; testing each candidate against the data removes those."""
    from scipy.stats import f as fdist
    n, k = len(target), len(x)
    limit = sse * (1 + k / (n - k) * fdist.ppf(0.95, k, n - k))
    rng = np.random.default_rng([seed, 4242])
    c = (cov + cov.T) / 2; w, v = np.linalg.eigh(c); root = v * np.sqrt(np.clip(w, 0, None))
    cand = np.clip(x[None, :] + rng.standard_normal((draws, k)) @ root.T, lo, hi)
    kept, tested = [], 0
    for start in range(0, draws, 100):
        block = cand[start:start + 100]; d = len(block)
        th = {key: np.repeat(val, len(target)) for key, val in stack(block).items()}
        pred = integrate(th, np.tile(light, (d, 1)))
        err = ((np.log10(np.maximum(pred, 1e-9)).reshape(d, -1) - target[None, :]) ** 2).sum(axis=1)
        kept += [block[i].tolist() for i in np.flatnonzero(err <= limit)]; tested += d
        if len(kept) >= keep:
            break
    return {'x': kept[:keep], 'tested': tested, 'accepted': len(kept), 'sseLimit': float(limit), 'sse': float(sse),
            'method': 'Draws from the fit covariance, kept when the training sum of squares stays within the joint 95 % region (F-test).'}


# ------------------------------------------------------------------ other wavelengths: calibration, model selection, published model

def spectral_rows(led):
    """Calibration points of one LED from both action spectra: (green intensity, LED intensity, measured MEFL, run, kind)."""
    sp = spectral()
    return [(r['green'], r['intensity'], r['fl'], r['run'], kind) for kind in ('forward', 'reverse') for r in sp[kind] if r['led'] == led]


def steady_state(theta, green, led, k1, k2):
    """Reporter at the photostationary state of constant light: the promoter output at a = k_on / (k_on + k_off + kdr + kg).
    After 480 minutes the chain is within about 1 % of it (checked against the integrator in `calibration_check`)."""
    green = np.asarray(green, float); led = np.asarray(led, float)
    k_on = theta['k1'] * green + k1 * led
    return hill(theta, k_on / (k_on + theta['k2'] * green + k2 * led + theta['kdr'] + theta['kg']))


def _fit_structure(theta, rows, structure, x0=None, seed=5):
    """Least squares on log10 fluorescence for one LED and one structure, in log-rate space."""
    from scipy.optimize import least_squares
    g = np.array([r[0] for r in rows]); I = np.array([r[1] for r in rows]); target = np.log10([r[2] for r in rows])
    free = {'none': (), 'off': ('k2',), 'on': ('k1',), 'both': ('k1', 'k2')}[structure]

    def unpack(x):
        v = dict(zip(free, np.exp(x)))
        return v.get('k1', 0.0), v.get('k2', 0.0)
    resid = lambda x: np.log10(np.maximum(steady_state(theta, g, I, *unpack(x)), 1e-9)) - target
    if not free:
        r0 = resid(np.empty(0))
        return {'k1': 0.0, 'k2': 0.0, 'sse': float(r0 @ r0), 'x': [], 'cov': [], 'free': []}
    lo, hi = np.log(CHANNEL_BOUNDS); rng = np.random.default_rng([seed, len(rows)]); best = None
    starts = [np.asarray(x0, float)] if x0 is not None else [np.full(len(free), math.log(0.005))] + [rng.uniform(math.log(1e-4), math.log(0.5), len(free)) for _ in range(3)]
    for start in starts:
        r = least_squares(resid, np.clip(start, lo + 1e-6, hi - 1e-6), bounds=(lo, hi), max_nfev=200)
        if best is None or r.cost < best.cost:
            best = r
    k1, k2 = unpack(best.x); n = len(target)
    cov = 2 * best.cost / max(1, n - len(free)) * np.linalg.pinv(best.jac.T @ best.jac)
    return {'k1': float(k1), 'k2': float(k2), 'sse': float(2 * best.cost), 'x': best.x.tolist(), 'cov': cov.tolist(), 'free': list(free)}


def calibrate_led(theta, led, seed=11):
    """One LED's switching rates. Calibration: its forward and reverse action-spectrum points. Model selection: which of
    STRUCTURES it follows, by leaving one experimental run out at a time; a richer structure must beat a simpler one by
    SELECT_MARGIN. The dynamic schedules are not read here."""
    from scipy.stats import f as fdist
    rows = spectral_rows(led); runs = sorted({r[3] for r in rows}); n = len(rows)
    fits = {st: _fit_structure(theta, rows, st) for st in STRUCTURES}; cv = {}
    for st in STRUCTURES:
        err = 0.0
        for run in runs:
            hold = [r for r in rows if r[3] == run]
            fs = fits[st] if st == 'none' else _fit_structure(theta, [r for r in rows if r[3] != run], st, x0=fits[st]['x'])
            pred = steady_state(theta, [r[0] for r in hold], [r[1] for r in hold], fs['k1'], fs['k2'])
            err += float(((np.log10(pred) - np.log10([r[2] for r in hold])) ** 2).sum())
        cv[st] = math.sqrt(err / n)
    best = min(cv.values())
    chosen = min((st for st in STRUCTURES if cv[st] <= (1 + SELECT_MARGIN) * best), key=lambda st: (len(fits[st]['free']), cv[st]))
    fit = fits[chosen]; k = len(fit['free']); ens = []
    if k:                                                               # rate pairs the calibration points cannot tell from the best one
        limit = fit['sse'] * (1 + k / (n - k) * fdist.ppf(0.95, k, n - k))
        c = np.array(fit['cov']); c = (c + c.T) / 2; w, v = np.linalg.eigh(c); root = v * np.sqrt(np.clip(w, 0, None))
        cand = np.clip(np.array(fit['x'])[None, :] + np.random.default_rng([seed, 77, n]).standard_normal((1500, k)) @ root.T, *np.log(CHANNEL_BOUNDS))
        g = np.array([r[0] for r in rows]); I = np.array([r[1] for r in rows]); target = np.log10([r[2] for r in rows])
        for x in cand:
            v_ = dict(zip(fit['free'], np.exp(x))); k1, k2 = v_.get('k1', 0.0), v_.get('k2', 0.0)
            if float(((np.log10(steady_state(theta, g, I, k1, k2)) - target) ** 2).sum()) <= limit:
                ens.append([float(k1), float(k2)])
                if len(ens) >= ENSEMBLE:
                    break
    info = spectral()['byLed'].get(led, {})
    return {'led': led, 'centroidNm': info.get('centroidNm'), 'structure': chosen, 'k1': fit['k1'], 'k2': fit['k2'], 'rmseLog10': math.sqrt(fit['sse'] / n), 'points': n, 'runs': runs,
            'cvRmseLog10': cv, 'ensemble': ens, 'published': {'k1': info.get('publishedK1'), 'k2': info.get('publishedK2')}}


def calibration_check(theta, channels):
    """The photostationary shortcut used for calibration against the integrator, on every calibration point."""
    worst = 0.0
    for led, ch in channels.items():
        rows = spectral_rows(led); g = np.array([r[0] for r in rows]); I = np.array([r[1] for r in rows]); ones = np.ones((len(rows), 480))
        full = integrate(theta, g[:, None] * ones, other=((ch['k1'] * I)[:, None] * ones, (ch['k2'] * I)[:, None] * ones))
        worst = max(worst, float(np.max(np.abs(steady_state(theta, g, I, ch['k1'], ch['k2']) / full - 1))))
    return {'maxRelativeDifference': worst, 'passed': bool(worst < 0.02), 'threshold': 'within 2 % of 480 simulated minutes'}


def published_predict(inputs, dt=1.0):
    """The published model with the parameters distributed with the dataset, for the same per-minute inputs:
    photoconversion, promoter output, a pure delay τ, then one lag at the growth rate."""
    sp = spectral(); pm = {k: v['value'] for k, v in sp['publishedModel']['parameters'].items()}
    P, N = next(iter(inputs.values())).shape
    k1 = sum(sp['byLed'][led]['publishedK1'] * inputs[led] for led in inputs); k2 = sum(sp['byLed'][led]['publishedK2'] * inputs[led] for led in inputs)
    y = np.zeros(P); out = np.empty((P, N))
    for j in range(N):
        rate = k1[:, j] + k2[:, j] + pm['kdr'] + pm['kg']; y_inf = k1[:, j] / rate; e = np.exp(-rate * dt)
        y_mean = y_inf + (y - y_inf) * (1 - e) / (rate * dt); y = y_inf + (y - y_inf) * e
        r = y_mean / np.maximum(1 - y_mean, 1e-12); out[:, j] = pm['b'] + pm['a'] * r ** pm['n'] / (pm['k'] ** pm['n'] + r ** pm['n'])
    centres = (np.arange(N) + 0.5) * dt
    delayed = np.stack([np.interp(centres - pm['tau'], centres, row, left=pm['b']) for row in out])
    g = np.full(P, pm['b']); eg = math.exp(-pm['kg'] * dt)
    for j in range(N):
        g = delayed[:, j] + (g - delayed[:, j]) * eg
    return g


# ------------------------------------------------------------------ learned features, ridge, baseline

def features(light, dt=1.0, state=None, record=False):
    """Low-pass filtered saturating transforms of the light history, one per (K, τ) pair, plus a constant."""
    light = np.atleast_2d(np.asarray(light, float)); P, N = light.shape
    Ks = np.array(FILTER_K); alpha = 1 - np.exp(-dt / np.array(FILTER_TAU))
    f = np.zeros((P, len(Ks), len(alpha))) if state is None else np.array(state, float)
    hist = np.empty((P, N + 1, f[0].size + 1)) if record else None
    if record:
        hist[:, 0, 0] = 1.0; hist[:, 0, 1:] = f.reshape(P, -1)
    for j in range(N):
        s = light[:, j, None] / (light[:, j, None] + Ks[None, :])
        f = f + (s[:, :, None] - f) * alpha[None, None, :]
        if record:
            hist[:, j + 1, 0] = 1.0; hist[:, j + 1, 1:] = f.reshape(P, -1)
    if record:
        return hist, f
    return np.concatenate([np.ones((P, 1)), f.reshape(P, -1)], axis=1)


def ridge(X, y, lam):
    reg = lam * np.eye(X.shape[1]); reg[0, 0] = 0.0                     # the constant is not penalised
    return np.linalg.solve(X.T @ X + reg, X.T @ y)


def choose_ridge(X, y, groups):
    """Penalty chosen by leaving one training schedule out at a time."""
    names = sorted(set(groups)); groups = np.array(groups); scores = []
    for lam in RIDGE:
        err = 0.0
        for g in names:
            hold = groups == g
            err += float(((X[hold] @ ridge(X[~hold], y[~hold], lam) - y[hold]) ** 2).sum())
        scores.append(math.sqrt(err / len(y)))
    best = int(np.argmin(scores))
    return RIDGE[best], dict(zip(map(str, RIDGE), scores))


def fit_baseline(light, obs):
    """Static dose-response: the reporter is a Hill function of the light at the moment of harvest. No dynamics."""
    from scipy.optimize import least_squares
    now = light[:, -1]; target = np.log10(obs)
    r = least_squares(lambda x: np.log10(baseline_predict(x, now)) - target, np.log([2000.0, 1e5, 1.5, 1.0]), bounds=(np.log([10.0, 100.0, 0.2, 1e-3]), np.log([1e5, 1e7, 8.0, 1e3])), max_nfev=400)
    return {'x': r.x.tolist(), 'rmseLog10': float(np.sqrt(2 * r.cost / len(target)))}


def baseline_predict(x, intensity):
    x = np.asarray(x); I = np.asarray(intensity, float); n = np.exp(x[2])
    return np.exp(x[0]) + np.exp(x[1]) * I ** n / (np.exp(x[3]) ** n + I ** n)


MODELS = {'mechanistic': 'Mechanistic chain', 'green': 'Green-only chain (version 1)', 'learned': 'Learned (filtered-light regression)', 'combined': 'Mechanistic + learned residual',
          'baseline': 'Static dose-response (baseline)', 'published': 'Published model (Olson et al. 2017)'}
SCORED = ('mechanistic', 'green', 'learned', 'combined', 'baseline', 'published')


def train():
    """Fit every predictor on the training schedules. Deterministic."""
    light, obs, who = points_of(SPLIT['train'])
    groups = [w[0] for w in who]; y = np.log10(obs)
    mech = fit_mechanistic(light, obs)
    X = features(light)
    lam_l, cv_l = choose_ridge(X, y, groups)
    mech_log = np.log10(integrate(mech['theta'], light))
    lam_c, cv_c = choose_ridge(X, y - mech_log, groups)
    theta = mech['theta']; leds = [l['id'] for l in spectral()['leds'] if l['id'] != GREEN]
    channels = {led: calibrate_led(theta, led) for led in leds}
    # the green chain against action-spectrum points it was never fitted to: the green LED alone, and green-only wells of the reverse plates
    gr = [(r[0] + r[1], r[2]) for r in spectral_rows(GREEN)] + [(r[0], r[2]) for r in spectral_rows('None') if r[4] == 'reverse']     # (total green, MEFL)
    green_err = np.log10(steady_state(theta, [r[0] for r in gr], np.zeros(len(gr)), 0.0, 0.0)) - np.log10([r[1] for r in gr])
    return {'version': VERSION, 'dataset': data_sha(), 'split': SPLIT, 'mechanistic': mech, 'channels': channels, 'calibrationCheck': calibration_check(theta, channels),
            'greenSpectrum': {'points': len(gr), 'rmseLog10': float(np.sqrt((green_err ** 2).mean())), 'note': 'Green LED alone and green-only wells of the action-spectrum plates, predicted by the fitted chain without refitting.'},
            'learned': {'weights': ridge(X, y, lam_l).tolist(), 'lambda': lam_l, 'cvRmseLog10': cv_l, 'rmseLog10': float(np.sqrt(((X @ ridge(X, y, lam_l) - y) ** 2).mean()))},
            'combined': {'weights': ridge(X, y - mech_log, lam_c).tolist(), 'lambda': lam_c, 'cvRmseLog10': cv_c},
            'baseline': fit_baseline(light, obs), 'trainingPoints': len(obs)}


def predict(fit, model, inputs):
    """Reporter level (MEFL) at the end of each light history {led: points × minutes}, for one predictor. Only the
    mechanistic chain and the published model take LEDs other than green."""
    light = green_of(inputs)
    if model == 'mechanistic':
        return integrate(fit['mechanistic']['theta'], light, other=other_rates(fit['channels'], inputs))
    if model == 'green':
        return integrate(fit['mechanistic']['theta'], light)
    if model == 'published':
        return published_predict(inputs)
    if model == 'baseline':
        return baseline_predict(fit['baseline']['x'], np.atleast_2d(light)[:, -1])
    X = features(light)
    if model == 'learned':
        return 10 ** (X @ np.array(fit['learned']['weights']))
    if model == 'combined':
        return integrate(fit['mechanistic']['theta'], light) * 10 ** (X @ np.array(fit['combined']['weights']))
    raise PulseError('Unknown model.')


# ------------------------------------------------------------------ response features and scoring

def _cross(t, y, level, rising):
    """First time the series crosses `level` (linear interpolation), or None."""
    for i in range(1, len(t)):
        a, b = y[i - 1], y[i]
        if (a < level <= b) if rising else (a > level >= b):
            return float(t[i - 1] + (level - a) / (b - a) * (t[i] - t[i - 1])) if b != a else float(t[i])
    return None


def response_features(kind, t, y):
    """Amplitude, timing and recovery of one time course, using only what its sampling supports."""
    t = np.asarray(t, float); y = np.asarray(y, float)
    if len(t) < 4:
        return {}
    if kind == 'step_on':
        start, end = float(y[0]), float(y[-3:].mean()); amp = end - start
        return {'amplitude': amp, 'halfRiseMin': _cross(t, y, start + amp / 2, True) if amp > 0 else None}
    if kind == 'step_off':
        start, end = float(y[0]), float(y[-3:].mean()); amp = start - end
        return {'amplitude': amp, 'halfRecoveryMin': _cross(t, y, start - amp / 2, False) if amp > 0 else None}
    k = int(np.argmax(y)); peak = float(y[k]); base = float(y[0]); amp = peak - base
    out = {'amplitude': amp, 'timeToPeakMin': float(t[k])}
    after = _cross(t[k:], y[k:], base + amp / 2, False) if amp > 0 and k < len(t) - 1 else None
    out['halfRecoveryMin'] = after - float(t[k]) if after is not None else None
    return out


FEATURE_LABEL = {'amplitude': ('Response amplitude', 'MEFL'), 'halfRiseMin': ('Time to half-maximal response', 'min'), 'halfRecoveryMin': ('Time to half recovery', 'min'), 'timeToPeakMin': ('Time to peak', 'min')}


def channel_draws(fit, leds, d):
    """`d` rate pairs per LED from its calibration ensemble (cycled), as {led: {k1: array, k2: array}}."""
    out = {}
    for led in leds:
        ch = fit['channels'][led]; e = np.array(ch['ensemble']) if ch['ensemble'] else np.array([[ch['k1'], ch['k2']]])
        pick = e[np.arange(d) % len(e)]; out[led] = {'k1': pick[:, 0], 'k2': pick[:, 1]}
    return out


def score(fit, sid, models=SCORED):
    """Measured points and each model's prediction for one schedule, with errors per replicate run and their mean."""
    s = dataset()['byId'][sid]; out = {'id': sid, 'name': s['name'], 'kind': s['kind'], 'replicates': [], 'models': {}}
    cache = {}
    for rep in s['replicates']:
        pts = [p for p in rep['points'] if not p.get('excluded')]
        t = [p['t'] for p in pts]; fl = [p['fl'] for p in pts]
        out['replicates'].append({'run': rep['run'], 't': t, 'fl': fl, 'rcv': [p['rcv'] for p in pts], 'excluded': [{'t': p['t'], 'fl': p['fl'], 'reason': p['excluded']} for p in rep['points'] if p.get('excluded')],
                                  'features': response_features(s['kind'], t, fl)})
    times = sorted({p['t'] for rep in s['replicates'] for p in rep['points']})
    inputs = stack_inputs([well_inputs(s, t) for t in times]); light = green_of(inputs)
    extra = sorted(led for led in inputs if led != GREEN and np.any(inputs[led]))
    out['inputs'] = [{'led': led, 'centroidNm': (spectral()['byLed'].get(led) or {}).get('centroidNm'), 'peak': float(inputs[led].max())} for led in sorted(inputs) if np.any(inputs[led])]
    for m in models:
        pred = dict(zip(times, predict(fit, m, inputs).tolist())); cache[m] = pred
        runs = []
        for rep in out['replicates']:
            p = np.array([pred[t] for t in rep['t']]); o = np.array(rep['fl'])
            e = np.log10(p) - np.log10(o)
            runs.append({'rmseLog10': float(np.sqrt((e ** 2).mean())), 'biasLog10': float(e.mean()), 'points': len(o), 'features': response_features(s['kind'], rep['t'], p)})
        feats = {}
        for key in FEATURE_LABEL:
            pairs = [(r['features'].get(key), rep['features'].get(key)) for r, rep in zip(runs, out['replicates']) if key in rep['features']]
            if not pairs:
                continue
            ok = [(a, b) for a, b in pairs if a is not None and b is not None]
            feats[key] = {'label': FEATURE_LABEL[key][0], 'unit': FEATURE_LABEL[key][1], 'measured': float(np.mean([b for _, b in ok])) if ok else None, 'predicted': float(np.mean([a for a, _ in ok])) if ok else None,
                          'supported': bool(ok), 'note': None if ok else 'The sampled time course does not reach this feature.'}
            if ok:
                feats[key]['error'] = feats[key]['predicted'] - feats[key]['measured']
                feats[key]['relativeError'] = feats[key]['error'] / feats[key]['measured'] if feats[key]['measured'] else None
        rmse = float(np.sqrt(np.mean([r['rmseLog10'] ** 2 for r in runs])))
        out['models'][m] = {'t': times, 'fl': [pred[t] for t in times], 'runs': runs, 'rmseLog10': rmse, 'foldError': 10 ** rmse, 'features': feats}
    ens = np.array(fit['mechanistic'].get('ensemble', {}).get('x') or [])
    if len(ens) and 'mechanistic' in out['models']:                     # 90 % predictive interval: parameter spread widened by the training residual
        d = len(ens); th = {k: np.repeat(v, len(times)) for k, v in stack(ens).items()}
        other = None
        if extra:                                                       # each parameter set carries its own draw of the other LEDs' rates
            draws = channel_draws(fit, extra, d)
            other = other_rates({led: {k: np.repeat(v, len(times)) for k, v in draws[led].items()} for led in extra}, {led: np.tile(inputs[led], (d, 1)) for led in extra})
        logs = np.log10(integrate(th, np.tile(light, (d, 1)), other=other)).reshape(d, -1)
        z = 1.645 * fit['mechanistic']['rmseLog10']
        low, high = 10 ** (np.percentile(logs, 5, axis=0) - z), 10 ** (np.percentile(logs, 95, axis=0) + z)
        at = dict(zip(times, zip(low.tolist(), high.tolist())))
        inside = sum(at[t][0] <= v <= at[t][1] for rep in out['replicates'] for t, v in zip(rep['t'], rep['fl'])); total = sum(len(rep['t']) for rep in out['replicates'])
        out['models']['mechanistic']['interval'] = {'low': low.tolist(), 'high': high.tolist(), 'level': 0.9, 'inside': int(inside), 'total': int(total), 'coverage': inside / total,
                                                    'note': 'Parameter spread of the accepted ensemble, widened by the scatter of the training residuals. It does not include day-to-day variation between runs, which the training plates (one run each) cannot reveal.'}
    if len(out['replicates']) > 1:                                      # run-to-run spread: the floor no model of the mean can beat
        common = sorted(set.intersection(*[set(r['t']) for r in out['replicates']]))
        logs = np.array([[math.log10(r['fl'][r['t'].index(t)]) for t in common] for r in out['replicates']])
        out['replicateSdLog10'] = float(np.sqrt(logs.var(axis=0, ddof=1).mean()))
    out['program'] = s['program']; out['led'] = s.get('led') or GREEN
    out['second'] = {'led': s['second']['led'], 'peak': max(s['second']['perMinute']), 'perMinute': s['second']['perMinute']} if s.get('second') else None
    return out


def benchmark(fit):
    """Every model on every schedule, grouped by its role in the split; the predictor the green held-out schedules select;
    and the three stages of the other wavelengths: calibration, model selection, final test."""
    rows = {role: [score(fit, sid) for sid in ids] for role, ids in SPLIT.items()}
    models = SCORED
    pooled = lambda role: {m: float(np.sqrt(np.mean([r['models'][m]['rmseLog10'] ** 2 for r in rows[role]]))) for m in models}
    summary = {role: pooled(role) for role in rows}
    cover = {role: {'inside': sum(r['models']['mechanistic']['interval']['inside'] for r in rows[role]), 'total': sum(r['models']['mechanistic']['interval']['total'] for r in rows[role])} for role in rows}
    for c in cover.values():
        c['coverage'] = c['inside'] / c['total']
    held = summary['heldOut']
    best = min(('mechanistic', 'learned', 'combined'), key=lambda m: held[m])
    # The mechanistic chain is kept unless another predictor is clearly better: a gain smaller than SELECT_MARGIN is within
    # what a different choice of held-out schedules would change, and the simpler model keeps its internal states.
    selected = best if held[best] < (1 - SELECT_MARGIN) * held['mechanistic'] else 'mechanistic'
    worst = max(r['models'][selected]['rmseLog10'] for r in rows['heldOut'])
    gate = {'thresholds': GATE, 'worstHeldOutRmseLog10': worst, 'baselineRatio': held['baseline'] / held[selected],
            'passed': bool(worst <= GATE['rmseLog10'] and held['baseline'] / held[selected] >= GATE['beatsBaselineBy'])}
    gate['statement'] = (f"Every held-out green-light schedule is predicted within {10 ** worst:.2f}-fold (root-mean-square), {gate['baselineRatio']:.1f} times closer than the static baseline. Closed-loop control is enabled." if gate['passed']
                         else 'The open-loop model does not meet the stated accuracy on every held-out schedule, so closed-loop control stays disabled.')
    note = (f"{MODELS[selected]} powers the experiment: it has the lowest pooled error on the held-out green-light schedules." if selected == best else
            f"{MODELS[best]} scores {100 * (1 - held[best] / held['mechanistic']):.1f} % better than the mechanistic chain on the held-out schedules, less than the {100 * SELECT_MARGIN:.0f} % needed to prefer it, so the mechanistic chain powers the experiment.")
    ch = fit['channels']; used = sorted({i['led'] for sid in FINAL_TEST for i in next(r for role in rows for r in rows[role] if r['id'] == sid)['inputs']} - {GREEN})
    final_rows = rows['mixedColour'] + rows['otherColour']
    fpool = lambda rs: {m: float(np.sqrt(np.mean([r['models'][m]['rmseLog10'] ** 2 for r in rs]))) for m in models}
    mixed = fpool(rows['mixedColour'])
    failures = [{'id': r['id'], 'name': r['name'], 'foldError': r['models']['mechanistic']['foldError'], 'replicateFold': 10 ** r.get('replicateSdLog10', 0.0),
                 'coverage': r['models']['mechanistic']['interval']['coverage'],
                 'features': {k: {'relativeError': v.get('relativeError'), 'error': v.get('error'), 'unit': v['unit'], 'supported': v['supported']} for k, v in r['models']['mechanistic']['features'].items()}}
                for r in final_rows if r['models']['mechanistic']['rmseLog10'] > GATE['rmseLog10'] or any(v.get('relativeError') is not None and abs(v['relativeError']) > FEATURE_MISS for v in r['models']['mechanistic']['features'].values())]
    for x in failures:                                                  # a miss is shown with its reason, never dropped
        x['why'] = [k for k, v in x['features'].items() if v['relativeError'] is not None and abs(v['relativeError']) > FEATURE_MISS] + (['trajectory'] if math.log10(x['foldError']) > GATE['rmseLog10'] else [])
    stages = {
        'calibration': {'data': 'Forward and reverse action spectra: steady-state points after 480 min of constant light, 24 per LED, five experimental runs.', 'leds': len(ch), 'points': sum(c['points'] for c in ch.values()),
                        'rmseLog10': float(np.sqrt(np.mean([c['rmseLog10'] ** 2 for c in ch.values()]))), 'greenChain': 'fitted first on the green training schedules and not refitted', 'shortcutCheck': fit['calibrationCheck'],
                        'greenSpectrum': fit['greenSpectrum']},
        'modelSelection': {'method': f"Each LED: no effect, off only, on only, or both, by leaving one experimental run out at a time inside its action spectrum; a richer structure must be more than {100 * SELECT_MARGIN:.0f} % better.",
                           'structures': {st: sum(c['structure'] == st for c in ch.values()) for st in STRUCTURES}, 'usedInFinalTest': {led: {'structure': ch[led]['structure'], 'cvRmseLog10': ch[led]['cvRmseLog10']} for led in used}},
        'finalTest': {'schedules': FINAL_TEST, 'status': 'retrospective', 'untouched': False,
                      'statement': 'Complete dynamic schedules, never used to fit a parameter or to choose a structure. They are not untouched: version 1 reported the red-light schedules as its failure case before the red input was built, so this result is retrospective, not prospective.',
                      'pooled': fpool(final_rows), 'mixedColour': mixed, 'otherColour': fpool(rows['otherColour']),
                      'coverage': {'inside': sum(cover[r]['inside'] for r in ('mixedColour', 'otherColour')), 'total': sum(cover[r]['total'] for r in ('mixedColour', 'otherColour'))},
                      'failures': failures},
    }
    stages['finalTest']['coverage']['coverage'] = stages['finalTest']['coverage']['inside'] / stages['finalTest']['coverage']['total']
    regression = {'case': 'Red light on top of the green program', 'schedules': SPLIT['mixedColour'], 'greenOnlyRmseLog10': mixed['green'], 'withRedRmseLog10': mixed['mechanistic'],
                  'greenOnlyFoldError': 10 ** mixed['green'], 'withRedFoldError': 10 ** mixed['mechanistic'], 'publishedFoldError': 10 ** mixed['published'],
                  'failureReproduced': bool(mixed['green'] > math.log10(2.0)), 'improved': bool(mixed['mechanistic'] < mixed['green']),
                  'statement': f"Without the red input the chain is {10 ** mixed['green']:.2f}-fold off on these schedules (the known failure, kept as a regression case). With the calibrated red input it is {10 ** mixed['mechanistic']:.2f}-fold off; the published model is {10 ** mixed['published']:.2f}-fold off."}
    return {'schedules': rows, 'summary': summary, 'intervalCoverage': {'level': 0.9, **cover}, 'selected': selected, 'best': best, 'selectionNote': note + ' The held-out schedules were never used to fit parameters; they are used once, here, to choose between predictors.',
            'gate': gate, 'stages': stages, 'regression': regression, 'unsupported': [],
            'publishedNote': 'The published model was fitted by its authors to the action spectra and to every step-on and step-off plate, so only the dynamic programs test it out of sample.',
            'greenOnlyNote': 'The learned predictor and the static baseline take green light only. On schedules with another LED their errors show what that omission costs.'}


def _fit_file(root):
    return pathlib.Path(root) / 'light_pulse' / f"fit-{VERSION}-{data_sha()[:16]}.json"


def fitted(service):
    """The trained predictors and their benchmark, computed once per library and dataset version."""
    root = getattr(service, 'root', None)
    f = _fit_file(root) if root else None
    if f is not None and f.is_file():
        try:
            body = json.loads(f.read_text())
            if body.get('fit', {}).get('version') == VERSION and body['fit'].get('dataset') == data_sha():
                return body['fit'], body['benchmark']
        except (ValueError, KeyError):
            pass
    fit = train(); bench = benchmark(fit)
    if f is not None:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({'fit': fit, 'benchmark': bench, 'created': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}, default=float))
    return fit, bench


def parameter_table(fit):
    """Fitted values with the spread of the accepted ensemble: how far each parameter can move without the training data noticing."""
    m = fit['mechanistic']; rows = []; ens = np.array(m['ensemble']['x'])
    for i, ((key, unit, desc, _, lo, hi), bound) in enumerate(zip(PARAMS, m['atBound'])):
        v = m['theta'][key]
        sd = float(ens[:, i].std()) if len(ens) > 5 else float(m['seLog'][i])
        ci = [float(x) for x in np.exp(np.percentile(ens[:, i], [2.5, 97.5]))] if len(ens) > 5 else [v * math.exp(-1.96 * sd), v * math.exp(1.96 * sd)]
        rows.append({'key': key, 'value': v, 'unit': unit, 'description': desc, 'relativeSe': sd, 'ci95': ci, 'bounds': [lo, hi], 'atBound': bound,
                     'determined': bool(sd < 0.5 and not bound), 'provenance': {'kind': 'fitted', 'note': f"Fitted to {m['points']} measured points of {len(SPLIT['train'])} training schedules."}})
    rows.append({'key': 'km', **{k: ASSUMED['km'][k] for k in ('value', 'unit', 'description', 'provenance')}, 'determined': False})
    return rows


# ------------------------------------------------------------------ the experiment

def _program(p, name='program', limit=None):
    if not isinstance(p, dict):
        raise PulseError(f'The {name} is missing.')
    lo, hi = LIMITS['intensity']
    try:
        pre = float(p.get('pre') or 0.0); steps = [[float(t), float(v)] for t, v in (p.get('steps') or [])]
    except (TypeError, ValueError):
        raise PulseError(f'The {name} must be a list of [time, intensity] steps.')
    limit = limit or LIMITS['steps']
    if not steps or len(steps) > limit:
        raise PulseError(f"A light program needs between 1 and {limit} steps.")
    if any(not math.isfinite(v) or not lo <= v <= hi for _, v in steps) or not lo <= pre <= hi:
        raise PulseError(f'Light intensity must be between {lo:g} and {hi:g} µmol m⁻² s⁻¹, the range that was measured.')
    if steps[0][0] != 0 or any(b[0] <= a[0] for a, b in zip(steps, steps[1:])) or any(round(t * 10) != t * 10 for t, _ in steps):
        raise PulseError('Steps must start at 0 min, increase in time and fall on 0.1-minute marks.')
    return {'pre': pre, 'steps': steps}


def _other(p):
    """Programs of LEDs other than green: {led: program}. Only calibrated LEDs are accepted."""
    if not p:
        return {}
    if not isinstance(p, dict) or len(p) > 4:
        raise PulseError('Other light must be given per LED, for at most four LEDs.')
    known = spectral()['byLed']; out = {}
    for led, prog in p.items():
        if led == GREEN or led not in known:
            raise PulseError(f'{led} is not an LED with a calibrated response.')
        q = _program(prog, f'{led} program', LIMITS['otherSteps'])
        if any(v for _, v in q['steps']) or q['pre']:
            out[led] = q
    return out


def compress(per_minute):
    """Per-minute intensities -> step program, keeping only the changes."""
    steps = []
    for i, v in enumerate(per_minute):
        if not steps or steps[-1][1] != v:
            steps.append([float(i), float(v)])
    return {'pre': 0.0, 'steps': steps}


def schedule_programs(sid):
    """A measured schedule as the experiment runs it: the green program and the program of every other LED."""
    s = dataset()['byId'][sid]; main = s.get('led') or GREEN; dark = {'pre': 0.0, 'steps': [[0.0, 0.0]]}
    other = {} if main == GREEN else {main: s['program']}
    if s.get('second'):
        other[s['second']['led']] = compress(s['second']['perMinute'])
    return (s['program'] if main == GREEN else dark), other


def pulses_to_program(pulses, off=0.0):
    """[{start, duration, intensity}] -> step program; overlapping pulses are rejected."""
    edges = [(0.0, off)]
    for q in sorted(pulses, key=lambda q: q['start']):
        a, b = float(q['start']), float(q['start']) + float(q['duration'])
        if a < edges[-1][0] or b <= a:
            raise PulseError('Pulses must not overlap and must have a positive duration.')
        if a == edges[-1][0]:
            edges[-1] = (a, float(q['intensity']))
        else:
            edges.append((a, float(q['intensity'])))
        edges.append((b, off))
    return {'pre': off, 'steps': [[round(t, 1), v] for t, v in edges]}


def _configure(p):
    lo, hi = LIMITS['durationMin']
    try:
        duration = float(p.get('durationMin', 480)); samples = int(p.get('samples', 60)); seed = int(p.get('seed', 7)); pre_min = float(p.get('preMin', 480))
    except (TypeError, ValueError):
        raise PulseError('Duration, samples and seed must be numbers.')
    if not lo <= duration <= hi:
        raise PulseError(f'The experiment must last between {lo:g} and {hi:g} minutes.')
    if not 0 <= samples <= LIMITS['samples'] or not 0 <= seed < 2 ** 31 or not 0 <= pre_min <= 1440:
        raise PulseError(f"Choose 0 to {LIMITS['samples']} uncertainty samples, a non-negative seed and at most 1440 minutes of preconditioning.")
    model = p.get('model') or 'auto'
    if model not in ('auto', 'mechanistic', 'green', 'learned', 'combined', 'baseline'):
        raise PulseError('Unknown model.')
    if (p.get('context') or CONTEXT) != CONTEXT:
        raise PulseError('The light-pulse experiment is calibrated for the E. coli CcaSR context only. No measurement of this reporter exists for the selected cell.')
    parent = str(p.get('parent') or ''); sid = p.get('schedule') if p.get('schedule') in dataset()['byId'] else None
    program, other = schedule_programs(sid) if sid else (p.get('program'), p.get('other'))     # a measured schedule runs exactly as recorded
    return {'context': CONTEXT, 'program': _program(program), 'other': _other(other), 'reference': _program(p['reference'], 'reference program') if p.get('reference') else None,
            'durationMin': duration, 'preMin': pre_min, 'model': model, 'samples': samples, 'seed': seed, 'label': str(p.get('label') or '')[:120],
            'parent': parent if re.fullmatch(r'[0-9a-f]{32}', parent) else None, 'schedule': sid}


def _trajectory(fit, model, program, duration, pre_min, thetas=None, dt=0.1, other=None):
    """Full time courses of every modelled quantity for one program. `thetas` (list of parameter dicts) adds an ensemble.
    `other` {led: program} is taken by the mechanistic chain only."""
    n = int(round(duration / dt)); t = np.arange(n + 1) * dt
    light = program_values(program, t[:-1] + dt / 2)[None, :]
    pre = np.full((1, int(round(pre_min / dt))), program['pre'])
    out = {'t': t, 'light': np.append(light[0], light[0][-1])}
    theta = fit['mechanistic']['theta']
    other = other if model in ('mechanistic', 'combined') else None
    run_in = {led: program_values(q, t[:-1] + dt / 2)[None, :] for led, q in (other or {}).items()}
    pre_in = {led: np.full(pre.shape, q['pre']) for led, q in (other or {}).items()}
    for led, v in run_in.items():
        out['light:' + led] = np.append(v[0], v[0][-1])
    extra = lambda inp, ch: other_rates(ch, inp) if inp else None
    if model in ('mechanistic', 'combined', 'green'):
        state = integrate(theta, pre, dt, record=True, other=extra(pre_in, fit['channels']))[1] if pre.size else None
        series, _ = integrate(theta, light, dt, state=state, record=True, other=extra(run_in, fit['channels']))
        for k in 'aTmug':
            out[k] = series[k][0]
    if model in ('learned', 'combined'):
        fs = features(pre, dt, record=True)[1] if pre.size else None
        hist, _ = features(light, dt, state=fs, record=True)
        corr = 10 ** (hist[0] @ np.array(fit[model]['weights']))
        out['g'] = out['g'] * corr if model == 'combined' else corr
    if model == 'baseline':
        out['g'] = baseline_predict(fit['baseline']['x'], out['light'])
    if thetas is not None and len(thetas) and model in ('mechanistic', 'combined', 'green'):
        th = stack(thetas); d = len(thetas)
        draws = channel_draws(fit, sorted(run_in), d) if run_in else None
        tile = lambda inp: {led: np.tile(v, (d, 1)) for led, v in inp.items()}
        st = integrate(th, np.tile(pre, (d, 1)), dt, record=True, other=extra(tile(pre_in), draws))[1] if pre.size else None
        ens = integrate(th, np.tile(light, (d, 1)), dt, state=st, record=True, other=extra(tile(run_in), draws))[0]['g']
        if model == 'combined':
            ens = ens * corr[None, :]
        out['band'] = np.percentile(ens, [5, 50, 95], axis=0)
    return out


def sample_thetas(fit, n, seed):
    """`n` parameter sets from the stored ensemble (see `ensemble`), as log-parameter rows; the seed picks which."""
    xs = np.array(fit['mechanistic']['ensemble']['x'])
    if n <= 0 or not len(xs):
        return np.empty((0, len(KEYS)))
    pick = np.random.default_rng([seed, 4242]).permutation(len(xs))[:n]
    return xs[pick]


def merged_steps(program, other, channels, duration):
    """Every change of any LED before `duration`: [t, green intensity, extra on-rate, extra off-rate], and the same before t = 0."""
    rate = lambda t, k: sum(channels[led][k] * float(program_values(q, [t])[0]) for led, q in other.items())
    times = sorted({s[0] for s in program['steps']} | {s[0] for q in other.values() for s in q['steps']})
    rows = [[t, float(program_values(program, [t])[0]), rate(t, 'k1'), rate(t, 'k2')] for t in times if t < duration]
    pre = [program['pre'], sum(channels[led]['k1'] * q['pre'] for led, q in other.items()), sum(channels[led]['k2'] * q['pre'] for led, q in other.items())]
    return rows, pre


def sbml_text(theta, program, duration, other=None, channels=None):
    """The mechanistic chain as SBML Level 3: rate rules for the four states, one event per change of light. Other LEDs
    enter as the two rates they add to the sensor (`on`, `off`)."""
    km = ASSUMED['km']['value']
    num = lambda v: f'<cn type="real">{float(v)!r}</cn>'
    ci = lambda s: f'<ci>{s}</ci>'
    ap = lambda op, *xs: f'<apply><{op}/>{"".join(xs)}</apply>'
    math_ = lambda body: f'<math xmlns="http://www.w3.org/1998/Math/MathML">{body}</math>'
    r = ap('divide', ci('a'), ap('minus', num(1.0), ci('a')))
    rn = ap('power', r, ci('n'))
    T = ap('plus', ci('b'), ap('divide', ap('times', ci('A'), rn), ap('plus', ap('power', ci('K'), ci('n')), rn)))
    rules = {'a': ap('minus', ap('times', ap('plus', ap('times', ci('k1'), ci('I')), ci('on')), ap('minus', num(1.0), ci('a'))), ap('times', ap('plus', ap('times', ci('k2'), ci('I')), ci('off'), ci('kdr'), ci('kg')), ci('a'))),
             'm': ap('times', ci('km'), ap('minus', T, ci('m'))), 'u': ap('times', ap('plus', ci('kmat'), ci('kg')), ap('minus', ci('m'), ci('u'))), 'g': ap('times', ci('kg'), ap('minus', ci('u'), ci('g')))}
    steps, pre = merged_steps(program, other or {}, channels or {}, duration)
    k_on = theta['k1'] * pre[0] + pre[1]; a0 = k_on / (k_on + theta['k2'] * pre[0] + pre[2] + theta['kdr'] + theta['kg'])
    g0 = float(hill(theta, np.array(a0)))
    consts = ''.join(f'<parameter id="{k}" value="{float(v)!r}" constant="true"/>' for k, v in {**theta, 'km': km}.items())
    light = ''.join(f'<parameter id="{k}" value="{float(v)!r}" constant="false"/>' for k, v in zip(('I', 'on', 'off'), steps[0][1:]))
    states = ''.join(f'<species id="{k}" compartment="cell" initialAmount="{v!r}" hasOnlySubstanceUnits="true" boundaryCondition="false" constant="false"/>' for k, v in (('a', float(a0)), ('m', g0), ('u', g0), ('g', g0)))
    events = ''.join(f'<event id="light{i}" useValuesFromTriggerTime="true"><trigger initialValue="false" persistent="true">{math_(ap("geq", "<csymbol encoding=\"text\" definitionURL=\"http://www.sbml.org/sbml/symbols/time\">t</csymbol>", num(t)))}</trigger>'
                     f'<listOfEventAssignments>{"".join(f"<eventAssignment variable=\"{k}\">{math_(num(x))}</eventAssignment>" for k, x in zip(("I", "on", "off"), v))}</listOfEventAssignments></event>' for i, (t, *v) in enumerate(steps[1:], 1))
    return ('<?xml version="1.0" encoding="UTF-8"?><sbml xmlns="http://www.sbml.org/sbml/level3/version1/core" level="3" version="1">'
            f'<model id="light_pulse_ccasr" name="Light-pulse reporter response (CcaSR, E. coli)"><listOfCompartments><compartment id="cell" size="1" constant="true" spatialDimensions="3"/></listOfCompartments>'
            f'<listOfSpecies>{states}</listOfSpecies><listOfParameters>{consts}{light}</listOfParameters>'
            f'<listOfRules>{"".join(f"<rateRule variable=\"{k}\">{math_(v)}</rateRule>" for k, v in rules.items())}</listOfRules>'
            + (f'<listOfEvents>{events}</listOfEvents>' if events else '') + '</model></sbml>')


def solver_check(theta, program, duration, t, g, other=None, channels=None):
    """Recompute the nominal reporter trajectory with the Mechanistic Lab solver and compare. The start is the steady state
    at the preconditioning light, so this check applies when the experiment was preconditioned to steady state."""
    try:
        import mechanistic_sbml as sbml, mechanistic_sim as sim
        model = sbml.Model(sbml_text(theta, program, duration, other, channels), {'kind': 'generated', 'by': ENGINE['id'] + ' ' + VERSION})
        points = min(2000, int(round(duration)) + 1)
        r = sim.simulate(model, duration, points=points, method='LSODA', rtol=1e-8, atol=1e-10, check=True)
        ref = np.interp(np.array(r['time']), t, g); got = np.array(r['series']['g'])
        diff = float(np.max(np.abs(got - ref) / np.maximum(np.abs(ref), 1.0)))
        return {'name': 'Independent solver', 'passed': bool(diff < 5e-3 and r['diagnostics'].get('reliable', False)), 'applicable': True, 'threshold': 'relative difference < 0.5 %; tolerance-insensitive',
                'value': {'maxRelativeDifference': diff, 'toleranceSensitivity': r['diagnostics'].get('toleranceSensitivity'), 'status': r['diagnostics']['status'], 'sbmlSha256': model.sha256, 'solver': r['solver']['library'] + ' ' + r['solver']['method']},
                'detail': 'The reporter trajectory recomputed by the Mechanistic Lab solver from an SBML description of the same model (rate rules, one event per light change), against the exponential integrator.'}
    except Exception as e:                                             # a failed cross-check is reported, never hidden
        return {'name': 'Independent solver', 'passed': False, 'applicable': True, 'threshold': 'relative difference < 0.5 %', 'value': {'error': str(e)[:300]}, 'detail': 'The Mechanistic Lab solver could not reproduce this run.'}


def _events(t, light, traj, program):
    """What happened, in order: changes of light, and the response milestones the trajectory actually reaches."""
    out = []
    prev = program['pre']
    for ts, v in program['steps']:
        if ts > t[-1]:
            break
        if v != prev:
            out.append({'time': ts, 'kind': 'light', 'scale': 'stimulus', 'label': ('Light on' if prev == 0 else 'Light off' if v == 0 else 'Light raised' if v > prev else 'Light lowered') + (f' · {v:g} µmol m⁻² s⁻¹' if v else ''), 'value': v})
        prev = v
    g = traj['g']; k = int(np.argmax(g)); base = float(g[0]); peak = float(g[k])

    def add(time, kind, scale, label, value):
        if time is not None:
            out.append({'time': round(float(time), 2), 'kind': kind, 'scale': scale, 'label': label, 'value': float(value)})
    if 'a' in traj:
        a = traj['a']; ka = int(np.argmax(a))
        if a[ka] - a[0] > 0.02:
            add(_cross(t, a, a[0] + (a[ka] - a[0]) / 2, True), 'regulator', 'molecular', 'Regulator half-activated', a[0] + (a[ka] - a[0]) / 2)
        T = traj['T']; kt = int(np.argmax(T))
        if T[kt] > 1.2 * T[0]:
            add(_cross(t, T, T[0] + (T[kt] - T[0]) / 2, True), 'transcription', 'gene', 'Transcription half-induced', T[0] + (T[kt] - T[0]) / 2)
    if peak > 1.2 * base:
        add(_cross(t, g, base + (peak - base) / 2, True), 'reporter', 'cell', 'Reporter at half its peak', base + (peak - base) / 2)
        if k < len(t) - 1:
            add(t[k], 'peak', 'cell', 'Reporter peak', peak)
            add(_cross(t[k:], g[k:], base + (peak - base) / 2, False), 'recovery', 'cell', 'Reporter half recovered', base + (peak - base) / 2)
    return sorted(out, key=lambda e: e['time'])


def _thin(a, n=600):
    a = np.asarray(a); k = max(1, -(-(len(a) - 1) // n))
    idx = np.unique(np.append(np.arange(0, len(a), k), len(a) - 1))
    return idx


# ------------------------------------------------------------------ one state: counts, fluorescence and display particles

PHI = {'value': 1.0, 'unit': 'MEFL per mature reporter molecule', 'mapping': 'relative',
       'provenance': {'kind': 'assumed', 'note': 'MEFL is fluorescence in units of fluorescein molecules, calibrated with beads. The brightness of one sfGFP in this cytometer channel relative to fluorescein was not measured, so one MEFL is taken as one molecule. Molecule numbers are therefore relative: they scale by one unknown constant, and every ratio and time course is unaffected.'}}
SENSOR = {'copies': 100, 'provenance': {'kind': 'assumed', 'note': 'CcaS copies per cell were not measured. One hundred display sites carry the active fraction; only the fraction is modelled.'}}
DISPLAY = {'reporterCapacity': 420, 'frames': 96, 'voxelJitter': True}
STATE = {
    'schema': 'fold-studio.cell-state.reporter', 'version': 1,
    'variables': [
        {'key': 'regulator', 'name': 'Regulator activity', 'unit': 'fraction of sensor in the active form', 'from': 'a', 'where': 'envelope'},
        {'key': 'transcription', 'name': 'Transcription drive', 'unit': 'MEFL at steady state', 'from': 'T(a)', 'where': 'nucleoid'},
        {'key': 'transcript', 'name': 'Reporter transcript', 'unit': 'MEFL at steady state (relative)', 'from': 'm', 'where': 'nucleoid'},
        {'key': 'production', 'name': 'Reporter production', 'unit': 'molecules min⁻¹ per cell (relative)', 'from': '(kmat + kg)·kg·m / (kmat·φ)', 'where': 'cytoplasm'},
        {'key': 'immature', 'name': 'Immature reporter', 'unit': 'molecules per cell (relative)', 'from': 'kg·u / (kmat·φ)', 'where': 'cytoplasm'},
        {'key': 'mature', 'name': 'Mature reporter', 'unit': 'molecules per cell (relative)', 'from': 'g / φ', 'where': 'cytoplasm'},
        {'key': 'fluorescence', 'name': 'Predicted fluorescence', 'unit': 'MEFL', 'from': 'φ · mature', 'where': 'whole cell'}],
    'clocks': [
        {'key': 'kinetic', 'stepMin': 0.1, 'what': 'Light, regulator, transcription, production, maturation and dilution, advanced together by the exponential integrator.'},
        {'key': 'output', 'what': 'The kinetic series thinned to at most 600 points for plots and records.'},
        {'key': 'display', 'frames': DISPLAY['frames'], 'what': 'Evenly spaced times at which molecule numbers become particles in 3-D.'},
        {'key': 'spatial', 'what': 'None. A protein crosses the cell in about 87 ms, thousands of times faster than the display interval, so each display frame draws fresh, independent positions. Particle paths between frames have no meaning.'}],
    'handoffs': [
        'light program (µmol m⁻² s⁻¹ per LED) → switching rates (min⁻¹) → regulator activity (fraction)',
        'regulator activity → transcription drive → transcript → immature and mature reporter (MEFL at steady state)',
        'MEFL ÷ φ → molecules per cell: the one reporter count',
        'reporter count × φ → predicted fluorescence (MEFL)',
        'reporter count ÷ weight, rounded → display particles in the cytoplasm; each particle stands for `weight` molecules'],
}


def state_of(theta, traj, dt=0.1):
    """The versioned state from one mechanistic trajectory: molecule numbers, their production, and the balance they must obey.
    Exact relations of the chain: with U = kg·u/(kmat·φ) and G = g/φ,  dU/dt = P − (kmat + kg)·U,  dG/dt = kmat·U − kg·G,
    so the total N = U + G obeys dN/dt = P − kg·N with P = (kmat + kg)·kg·m/(kmat·φ)."""
    phi = PHI['value']; kg, kmat = theta['kg'], theta['kmat']
    U = kg * traj['u'] / (kmat * phi); G = traj['g'] / phi; P = (kmat + kg) * kg * traj['m'] / (kmat * phi); N = U + G
    import cell_state
    balance = cell_state.balance('Molecule totals', N, P, kg * N, dt, 'Immature plus mature reporter over the whole run against the integral of production and of dilution by growth.')
    readout = cell_state.same_series('One reporter count', phi * G, traj['g'], 'The plotted fluorescence and the molecules drawn in 3-D are the same series, apart from the constant φ.', {'phi': phi})
    return {'regulator': traj['a'], 'transcription': traj['T'], 'transcript': traj['m'], 'production': P, 'immature': U, 'mature': G, 'fluorescence': phi * G}, [balance, readout]


def display_particles(root, series_t, immature, mature, regulator, seed, weight=None):
    """Molecule numbers at the display clock as particles in the illustrative rod, through the shared hand-off
    (cell_state.particles). One weight serves both reporter species; the sensor is drawn one particle per copy."""
    import cell_em, cell_state
    cls, voxel, meta, sha = cell_em.geometry(root, CONTEXT); k = cell_em.KEYS
    at = cell_state.display_clock(len(series_t), DISPLAY['frames']); inside = [k['cytosol'], k['chromatin']]
    species = [{'key': 'regulator', 'name': 'Active sensor (CcaS)', 'compartment': 'pm', 'where': 'Cell envelope', 'radiusNm': 3.5, 'evidence': 'assumed copies', 'classes': [k['pm']], 'counts': regulator * SENSOR['copies']},
               {'key': 'immature', 'name': 'Immature reporter', 'compartment': 'cytosol', 'where': 'Cytoplasm and nucleoid region', 'radiusNm': 2.4, 'evidence': 'predicted', 'classes': inside, 'counts': immature, 'group': 'reporter'},
               {'key': 'mature', 'name': 'Mature reporter (sfGFP)', 'compartment': 'cytosol', 'where': 'Cytoplasm and nucleoid region', 'radiusNm': 2.4, 'evidence': 'predicted', 'classes': inside, 'counts': mature, 'group': 'reporter'}]
    try:
        d = cell_state.particles(cls, voxel, species, at, seed, DISPLAY['reporterCapacity'], weight)
    except ValueError as e:
        raise PulseError(str(e))
    return {'context': CONTEXT, 'geometrySha256': sha, 'sizeUm': meta['sizeUm'], 'time': [float(series_t[i]) for i in at], 'timeUnit': 'min', **d,
            'evidence': {'positions': 'Illustrative: independent uniform draws inside an illustrative rod; nothing was measured with spatial resolution.', 'numbers': 'Predicted response; molecule numbers are relative (φ assumed).'}}


def spatial_note():
    """What in this experiment has a location, in this cell context."""
    return {'context': CONTEXT, 'geometry': 'illustrative', 'measured': False,
            'statement': 'Nothing in this experiment was measured with spatial resolution: the readout is whole-cell fluorescence by flow cytometry. Locations below come from what is known about each component, drawn on an illustrative rod-shaped cell, not from an image of this strain.',
            'components': [{'quantity': 'Light', 'where': 'whole culture', 'interpretable': False, 'note': 'Uniform across a low-density culture; no gradient is modelled.'},
                           {'quantity': 'Regulator activity (CcaS)', 'where': 'inner membrane', 'interpretable': True, 'note': 'CcaS is a membrane-anchored sensor kinase; the active fraction is modelled as one number for the whole membrane.'},
                           {'quantity': 'Transcription', 'where': 'nucleoid / plasmid', 'interpretable': True, 'note': 'The promoter is on a plasmid; plasmid position is not modelled.'},
                           {'quantity': 'Reporter (sfGFP)', 'where': 'cytoplasm', 'interpretable': True, 'note': 'Soluble and uniform at the time scales modelled.'}],
            'mixing': {'cellLengthUm': 2.0, 'DUm2PerS': 7.7, 'equilibrationMs': round(2.0 ** 2 / (6 * 7.7) * 1000, 1),
                       'source': 'GFP diffusion in E. coli cytoplasm, 7.7 µm²/s (Elowitz et al. 1999, J Bacteriol 181:197-203). L²/6D for a 2 µm cell.'}}


def simulate(service, p):
    """Run one light-pulse experiment and save it as a research record. Deterministic: the same inputs give the same record."""
    cfg = _configure(p)
    fit, bench = fitted(service)
    model = bench['selected'] if cfg['model'] == 'auto' else cfg['model']
    thetas = sample_thetas(fit, cfg['samples'], cfg['seed'])
    other = cfg['other'] if model in ('mechanistic', 'combined') else {}
    traj = _trajectory(fit, model, cfg['program'], cfg['durationMin'], cfg['preMin'], thetas, other=other)
    t = traj['t']; idx = _thin(t)
    series = {'light': traj['light'][idx].tolist(), 'reporter': traj['g'][idx].tolist()}
    for led in other:
        series['light:' + led] = traj['light:' + led][idx].tolist()
    state_checks = []; has_state = model in ('mechanistic', 'green')
    if has_state:                                                       # molecule numbers: the one count behind fluorescence and 3-D
        st, state_checks = state_of(fit['mechanistic']['theta'], traj)
        for key in ('production', 'immature', 'mature'):
            series[key] = st[key][idx].tolist()
    names = {'a': 'regulator', 'T': 'transcription', 'm': 'mrna', 'u': 'immature'}
    for k, name in names.items():
        if k in traj:
            series[name] = traj[k][idx].tolist()
    if 'band' in traj:
        series['reporterLow'], series['reporterMedian'], series['reporterHigh'] = (traj['band'][i][idx].tolist() for i in range(3))
        z = 10 ** (1.645 * fit['mechanistic']['rmseLog10'])
        series['predictiveLow'], series['predictiveHigh'] = (traj['band'][0][idx] / z).tolist(), (traj['band'][2][idx] * z).tolist()
    ref = None
    if cfg['reference']:
        rt = _trajectory(fit, model, cfg['reference'], cfg['durationMin'], cfg['preMin'])
        ref = {'light': rt['light'][idx].tolist(), 'reporter': rt['g'][idx].tolist(), 'features': response_features('dynamic', t, rt['g'])}
    feats = response_features('dynamic', t, traj['g'])
    spread = None
    if 'band' in traj:
        k = int(np.argmax(traj['g'])); spread = {'atPeak': {'low': float(traj['band'][0][k]), 'high': float(traj['band'][2][k])}, 'relativeWidthAtPeak': float((traj['band'][2][k] - traj['band'][0][k]) / traj['g'][k])}
    measured = score(fit, cfg['schedule'], tuple(dict.fromkeys((model, 'mechanistic', 'green', 'published', 'baseline')))) if cfg['schedule'] else None
    checks = []
    if model in ('mechanistic', 'combined', 'green'):
        steady = cfg['preMin'] >= 240 or (cfg['program']['pre'] == 0 and not any(q['pre'] for q in other.values()))
        base = 'green' if model == 'green' else 'mechanistic'
        c = solver_check(fit['mechanistic']['theta'], cfg['program'], cfg['durationMin'], t, _trajectory(fit, base, cfg['program'], cfg['durationMin'], 1440.0 if steady else cfg['preMin'], other=other)['g'], other, fit['channels']) if steady else \
            {'name': 'Independent solver', 'passed': None, 'applicable': False, 'threshold': 'n/a', 'value': None, 'detail': 'Not run: the preconditioning is too short for the steady-state start the SBML model assumes.'}
        checks.append(c)
        a = traj['a']
        checks.append({'name': 'Bounds', 'passed': bool(a.min() >= -1e-12 and a.max() <= 1 + 1e-12 and traj['g'].min() > 0), 'applicable': True, 'threshold': '0 ≤ regulator activity ≤ 1; reporter > 0',
                       'value': {'regulatorMin': float(a.min()), 'regulatorMax': float(a.max()), 'reporterMin': float(traj['g'].min())}, 'detail': 'The active fraction stays a fraction and the reporter stays positive.'})
        half = _trajectory(fit, model, cfg['program'], cfg['durationMin'], cfg['preMin'], dt=0.05, other=other)['g'][::2]
        d = float(np.max(np.abs(half - traj['g']) / traj['g']))
        checks.append({'name': 'Step size', 'passed': bool(d < 2e-3), 'applicable': True, 'threshold': 'relative change < 0.2 % when the step is halved', 'value': {'maxRelativeChange': d, 'stepMin': 0.1},
                       'detail': 'The same run with a 0.05-minute step.'})
        checks += state_checks
    used = sorted({v for _, v in cfg['program']['steps']} | {cfg['program']['pre']})
    warnings = []
    if max(used) > 20:
        warnings.append('Intensities above 20 µmol m⁻² s⁻¹ were never measured.')
    undetermined = [r['key'] for r in parameter_table(fit) if r['provenance']['kind'] == 'fitted' and not r['determined']]
    if undetermined and model != 'learned':
        warnings.append('Poorly determined by the training data: ' + ', '.join(undetermined) + '. The uncertainty band reflects this.')
    if spread and spread['relativeWidthAtPeak'] > 0.5:
        warnings.append('The 5–95 % band at the peak is wider than half the prediction: treat the amplitude as uncertain.')
    if model == 'learned':
        warnings.append('The learned model has no internal states: regulator activity and transcription are not available for this run.')
    if cfg['other'] and not other:
        warnings.append('This program contains ' + ', '.join(cfg['other']) + ' light, which the chosen predictor does not take. Its prediction ignores that light.')
    if other:
        warnings.append('Light other than green enters through rates calibrated on steady-state action spectra; its dynamics are a prediction tested retrospectively on three schedules.')
    if not has_state:
        warnings.append('Molecule numbers and the 3-D view need the mechanistic chain; this predictor gives fluorescence only.')
    passed = all(c['passed'] for c in checks if c['applicable'])
    inputs = {'program': {'value': cfg['program'], 'unit': 'min, µmol m⁻² s⁻¹', 'description': 'Green light program (526 nm LED)'},
              'other': {'value': cfg['other'], 'unit': 'min, µmol m⁻² s⁻¹', 'description': 'Programs of other LEDs' + ('' if other or not cfg['other'] else ' (ignored by this predictor)')}, 'durationMin': {'value': cfg['durationMin'], 'unit': 'min', 'description': 'Simulated duration'},
              'preMin': {'value': cfg['preMin'], 'unit': 'min', 'description': 'Preconditioning at the program\'s starting light before t = 0'}, 'model': {'value': model, 'unit': '', 'description': 'Predictor' + (' (selected by the held-out benchmark)' if cfg['model'] == 'auto' else ' (chosen by you)')},
              'samples': {'value': cfg['samples'], 'unit': 'draws', 'description': 'Parameter sets drawn from the fit covariance for the uncertainty band'}, 'seed': {'value': cfg['seed'], 'unit': '', 'description': 'Random seed of those draws'}}
    solver = {'stepMin': 0.1, 'outputPoints': int(len(idx)), 'model': model, 'modelVersion': VERSION, 'datasetSha256': data_sha(), 'timeCoursesSha256': dataset()['sha256'], 'spectraSha256': spectral()['sha256'],
              'fitSha256': _sha({'x': fit['mechanistic']['x'], 'l': fit['learned']['weights'], 'c': fit['combined']['weights'], 'ch': {led: [c['k1'], c['k2']] for led, c in fit['channels'].items()}}),
              'channels': {led: {k: fit['channels'][led][k] for k in ('k1', 'k2', 'structure', 'centroidNm')} for led in other}, 'stateVersion': STATE['version'] if has_state else None,
              'parameters': {k: fit['mechanistic']['theta'][k] for k in KEYS}, 'assumed': {'km': ASSUMED['km']['value']}, 'context': CONTEXT}
    outputs = {'time': float(t[-1]), 'timeUnit': 'min', 'features': feats, 'reference': ref and ref['features'], 'uncertainty': spread, 'events': _events(t, traj['light'], traj, cfg['program']),
               'reporterAtEnd': float(traj['g'][-1]), 'reporterPeak': float(traj['g'].max())}
    drivers = [{'output': 'Reporter amplitude', 'drivenBy': ['Light program', 'A (inducible range)', 'K, n (promoter sensitivity)', 'k1, k2, kdr (sensor switching)']},
               {'output': 'Time to peak and recovery', 'drivenBy': ['Light program timing', 'kg (dilution by growth)', 'kmat (maturation)', 'km (assumed mRNA turnover)']}] if model != 'learned' else \
              [{'output': 'Reporter', 'drivenBy': ['Filtered light history (16 features)', 'Ridge weights fitted to the training schedules']}]
    run_id = uuid.uuid4().hex
    created = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    record = {'schema': 'fold-studio.research-record', 'schemaVersion': 1, 'id': run_id, 'kind': 'light_pulse.experiment',
              'experiment': {'label': cfg['label'], 'parent': cfg['parent'], 'config': cfg, 'context': CONTEXT, 'rerun': 'Send `config` to light_pulse_simulate. The run is deterministic for a given dataset and model version.'},
              'engine': {k: ENGINE[k] for k in ('id', 'name', 'version', 'numericalMethod')},
              'evidence': {'category': 'B', 'name': 'Mechanistic model fitted to measurements', 'statement': 'A model of one E. coli strain\'s light-responsive reporter, fitted to a subset of published time courses and tested on schedules held out from the fit. This run is a prediction for a light program; it is not a measurement.'},
              'created': created, 'inputs': inputs, 'solver': solver, 'outputs': outputs, 'benchmark': {'checks': checks, 'passed': passed}, 'drivers': drivers, 'warnings': warnings,
              'validation': {'selected': bench['selected'], 'heldOut': bench['summary']['heldOut'], 'gate': bench['gate']},
              'data': {'source': {k: dataset()['source'][k] for k in ('authors', 'journal', 'doi', 'licence', 'dataset')}, 'sha256': dataset()['sha256']},
              'assumptions': ENGINE['assumptions'], 'limitations': ENGINE['limits'],
              'state': {**STATE, 'phi': PHI, 'sensor': SENSOR, 'display': DISPLAY} if has_state else None}
    record['reproducibility'] = {'deterministic': True, 'seed': cfg['seed'], 'runtime': 'Python ' + platform.python_version() + ' · NumPy ' + np.__version__,
                                 'contentSha256': _sha({k: record[k] for k in ('inputs', 'solver', 'outputs')}), 'seriesSha256': _sha(series),
                                 'note': 'Deterministic. Rerunning the saved configuration reproduces the series hash on the same NumPy and platform.'}
    root = getattr(service, 'root', None)
    if root and not p.get('dryRun'):
        d = pathlib.Path(root) / 'light_pulse' / 'runs'; d.mkdir(parents=True, exist_ok=True)
        (d / (run_id + '.json')).write_text(json.dumps(record, default=float))
    return {'id': run_id, 'time': t[idx].tolist(), 'series': series, 'reference': ref, 'measured': measured, 'model': model, 'modelName': MODELS[model], 'record': record, 'spatial': spatial_note(), 'hasState': has_state,
            'sha256': record['reproducibility']['contentSha256'], 'seriesSha256': record['reproducibility']['seriesSha256'], 'passed': passed, 'checks': checks, 'warnings': warnings}


def sweep(service, p):
    """One program parameter varied over a range: pulse intensity, duration, or the dark gap of a repeated pulse."""
    fit, bench = fitted(service)
    model = bench['selected'] if (p.get('model') or 'auto') == 'auto' else p['model']
    what = p.get('vary'); values = p.get('values') or []
    if what not in ('intensity', 'duration', 'period') or not 2 <= len(values) <= 24:
        raise PulseError('Vary intensity, duration or period over 2 to 24 values.')
    base = {'intensity': float(p.get('intensity', 5.0)), 'duration': float(p.get('duration', 60.0)), 'period': float(p.get('period', 120.0)), 'pulses': int(p.get('pulses', 1)), 'start': float(p.get('start', 30.0))}
    total = float(p.get('durationMin', 480)); rows = []
    for v in values:
        q = {**base, what: float(v)}
        if q['duration'] <= 0 or (q['pulses'] > 1 and q['period'] <= q['duration']):
            raise PulseError('Each pulse must be shorter than the period.')
        pulses = [{'start': round(q['start'] + i * q['period'], 1), 'duration': round(q['duration'], 1), 'intensity': q['intensity']} for i in range(q['pulses'])]
        prog = _program(pulses_to_program([x for x in pulses if x['start'] < total]))
        tr = _trajectory(fit, model, prog, total, 0.0)
        f = response_features('dynamic', tr['t'], tr['g'])
        rows.append({'value': float(v), 'program': prog, 'peak': float(tr['g'].max()), **f, 'dose': float(sum(x['duration'] * x['intensity'] for x in pulses))})
    return {'vary': what, 'unit': {'intensity': 'µmol m⁻² s⁻¹', 'duration': 'min', 'period': 'min'}[what], 'base': base, 'durationMin': total, 'model': model, 'rows': rows,
            'note': 'Each row is one deterministic run of the selected model; nothing is saved.'}


def runs(service):
    d = pathlib.Path(service.root) / 'light_pulse' / 'runs'; out = []
    for f in sorted(d.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:60] if d.is_dir() else []:
        r = json.loads(f.read_text()); ex = r.get('experiment') or {}
        out.append({'id': r['id'], 'created': r['created'], 'label': ex.get('label') or '', 'parent': ex.get('parent'), 'passed': r['benchmark'].get('passed'), 'model': r['solver']['model'],
                    'time': r['outputs']['time'], 'peak': r['outputs'].get('reporterPeak'), 'sha256': r['reproducibility']['contentSha256'], 'schedule': (ex.get('config') or {}).get('schedule')})
    return out


def run_get(service, p):
    """A saved experiment, recomputed from its configuration, with a statement of whether it reproduces."""
    rid = str(p.get('id', '')); f = pathlib.Path(service.root) / 'light_pulse' / 'runs' / (rid + '.json')
    if not re.fullmatch(r'[0-9a-f]{32}', rid) or not f.is_file():
        raise PulseError('That saved experiment no longer exists.')
    rec = json.loads(f.read_text())
    again = simulate(service, {**rec['experiment']['config'], 'model': rec['solver']['model'], 'dryRun': True})
    same = again['seriesSha256'] == rec['reproducibility'].get('seriesSha256')
    return {**again, 'id': rid, 'record': rec, 'sha256': rec['reproducibility']['contentSha256'],
            'reproduced': {'identical': bool(same), 'saved': rec['reproducibility'].get('seriesSha256'), 'now': again['seriesSha256'],
                           'statement': 'Recomputed from the saved configuration: every plotted value is identical to the saved run.' if same else
                                        'Recomputed from the saved configuration, but the values differ from the saved run. The dataset, model version or numerical library has changed since it was saved.',
                           'savedVersions': {'model': rec['solver'].get('modelVersion'), 'dataset': rec['solver'].get('datasetSha256')}, 'currentVersions': {'model': VERSION, 'dataset': data_sha()}}}


def particles(service, p):
    """Molecule numbers of a run as display particles for the 3-D view. Recomputed from the saved configuration (or from a
    configuration sent directly); deterministic for a given seed. Nothing is saved."""
    fit, bench = fitted(service)
    if p.get('id'):
        rid = str(p['id']); f = pathlib.Path(service.root) / 'light_pulse' / 'runs' / (rid + '.json')
        if not re.fullmatch(r'[0-9a-f]{32}', rid) or not f.is_file():
            raise PulseError('That saved experiment no longer exists.')
        rec = json.loads(f.read_text()); cfg = _configure(rec['experiment']['config']); model = rec['solver']['model']
    else:
        cfg = _configure(p); model = bench['selected'] if cfg['model'] == 'auto' else cfg['model']
    if model not in ('mechanistic', 'green'):
        raise PulseError('Molecule numbers come from the mechanistic chain. Choose it under Parameters to see this run in 3-D.')
    traj = _trajectory(fit, model, cfg['program'], cfg['durationMin'], cfg['preMin'], other=cfg['other'])
    st, checks = state_of(fit['mechanistic']['theta'], traj)
    d = display_particles(getattr(service, 'root', None), traj['t'], st['immature'], st['mature'], st['regulator'], cfg['seed'], p.get('weight'))
    at = np.searchsorted(traj['t'], d['time'])
    return {**d, 'id': p.get('id'), 'model': model, 'checks': checks + d['checks'], 'passed': all(c['passed'] for c in checks + d['checks']),
            'fluorescence': st['fluorescence'][at].tolist(), 'fluorescenceUnit': 'MEFL', 'phi': PHI, 'sensor': SENSOR, 'state': {k: STATE[k] for k in ('schema', 'version', 'clocks', 'handoffs')}}


def compare(service, p):
    """Two saved experiments recomputed on the same time axis: what was changed, and what that did."""
    a, b = (run_get(service, {'id': p.get(k)}) for k in ('baseline', 'variant'))
    ca, cb = a['record']['experiment']['config'], b['record']['experiment']['config']
    changed = [{'what': k, 'baseline': ca[k], 'variant': cb[k], 'affectsDynamics': k not in ('label', 'samples', 'seed', 'parent', 'schedule')} for k in ('program', 'other', 'durationMin', 'preMin', 'model', 'samples', 'seed') if ca.get(k) != cb.get(k)]
    fa, fb = a['record']['outputs']['features'], b['record']['outputs']['features']
    outcomes = [{'key': k, 'label': FEATURE_LABEL[k][0], 'unit': FEATURE_LABEL[k][1], 'baseline': fa.get(k), 'variant': fb.get(k),
                 'change': (fb[k] - fa[k]) if fa.get(k) is not None and fb.get(k) is not None else None} for k in ('amplitude', 'timeToPeakMin', 'halfRecoveryMin')]
    return {'baseline': {'id': a['id'], 'label': ca['label'], 'time': a['time'], 'series': a['series'], 'events': a['record']['outputs']['events'], 'reproduced': a['reproduced']['identical']},
            'variant': {'id': b['id'], 'label': cb['label'], 'time': b['time'], 'series': b['series'], 'events': b['record']['outputs']['events'], 'reproduced': b['reproduced']['identical']},
            'changed': changed, 'outcomes': outcomes, 'identicalDynamics': not any(c['affectsDynamics'] for c in changed),
            'note': 'Both sides are recomputed from their saved configurations with the current model, so they share one model version and one time axis.'}


def control(service, p):
    """Closed-loop control in simulation: a model-predictive controller steers a virtual culture whose parameters differ
    from the controller's model. Available only when the open-loop benchmark passes its gate."""
    fit, bench = fitted(service)
    if not bench['gate']['passed']:
        raise PulseError('Closed-loop control is disabled: ' + bench['gate']['statement'])
    try:
        target = float(p.get('target', 30000.0)); duration = float(p.get('durationMin', 480)); interval = float(p.get('intervalMin', 10)); seed = int(p.get('seed', 7)); noise = float(p.get('noiseCv', 0.05))
    except (TypeError, ValueError):
        raise PulseError('Target, duration, interval, seed and noise must be numbers.')
    theta = fit['mechanistic']['theta']
    lo, hi = theta['b'] * 1.05, (theta['b'] + theta['A']) * 0.95
    if not lo <= target <= hi or not 120 <= duration <= 1440 or not 5 <= interval <= 60 or not 0 <= noise <= 0.5:
        raise PulseError(f'Choose a target between {lo:.0f} and {hi:.0f} MEFL (inside the reporter\'s range), 120–1440 min, a 5–60 min interval and noise up to 50 %.')
    rng = np.random.default_rng([seed, 99]); plant = _theta(sample_thetas(fit, 1, seed)[0])
    dt = 0.5; n = int(interval / dt); steps = int(duration / interval)
    levels = np.concatenate([[0.0], np.geomspace(0.02, 20.0, 40)])
    horizon = max(1, int(round(60 / interval)))

    def advance(th, state, I, k):
        tr, st = integrate(th, np.full((1, k), I), dt, state=state, record=True)
        return tr['g'][0], st
    dark = lambda th: (np.zeros(1), *(np.full(1, float(hill(th, np.zeros(1))[0])) for _ in range(3)))
    # open loop: the constant light the model says holds the target at steady state
    ss = [float(integrate(theta, np.full((1, 2000), I), 1.0)[0]) for I in levels]
    open_I = float(levels[int(np.argmin(np.abs(np.array(ss) - target)))])
    res = {}
    for mode in ('open', 'closed'):
        true_state = dark(plant); est = dark(theta); g_series, light, t_axis, meas = [float(true_state[3][0])], [], [0.0], []
        gain = 1.0
        for k in range(steps):
            if mode == 'open':
                I = open_I
            else:
                y = float(true_state[3][0]) * (1 + noise * rng.standard_normal()); meas.append({'t': k * interval, 'fl': y})
                gain = 0.7 * gain + 0.3 * (y / max(float(est[3][0]), 1.0))        # multiplicative output correction from the last measurements
                best = None
                for I_try in levels:
                    pred = integrate(theta, np.full((1, n * horizon), I_try), dt, state=est)[0] * gain
                    err = abs(pred - target)
                    if best is None or err < best[0]:
                        best = (err, float(I_try))
                I = best[1]
            g, true_state = advance(plant, true_state, I, n)
            _, est = advance(theta, est, I, n)
            g_series += g[1:].tolist(); light += [I] * n; t_axis += [(k * n + i + 1) * dt for i in range(n)]
        g_arr = np.array(g_series); settle = np.array(t_axis) >= duration / 2
        res[mode] = {'time': t_axis[::2], 'reporter': g_arr[::2].tolist(), 'light': (light + [light[-1]])[::2], 'measurements': meas,
                     'rmseSecondHalf': float(np.sqrt(((g_arr[settle] - target) ** 2).mean())), 'relativeErrorSecondHalf': float(np.abs(g_arr[settle] / target - 1).mean())}
    return {'target': target, 'durationMin': duration, 'intervalMin': interval, 'noiseCv': noise, 'seed': seed, 'open': res['open'], 'closed': res['closed'], 'openLoopLight': open_I,
            'plant': {k: plant[k] for k in KEYS}, 'model': {k: theta[k] for k in KEYS},
            'evidence': {'category': 'B', 'statement': 'Simulation only. The "culture" is the same model with parameters drawn from the fit covariance, measured every interval with the stated noise. No real culture was controlled; this shows what feedback would correct if the true parameters differed from the fitted ones by their fitted uncertainty.'},
            'improved': bool(res['closed']['rmseSecondHalf'] < res['open']['rmseSecondHalf'])}


def schedule(service, p):
    fit, _ = fitted(service)
    sid = p.get('id')
    if sid not in dataset()['byId']:
        raise PulseError('Unknown schedule.')
    role = next(r for r, ids in SPLIT.items() if sid in ids)
    return {**score(fit, sid), 'supported': True, 'role': role}


def catalog(service):
    d = dataset(); fit, bench = fitted(service)
    role = {sid: r for r, ids in SPLIT.items() for sid in ids}
    return {'engine': ENGINE, 'context': CONTEXT, 'dataset': {'sha256': d['sha256'], 'source': d['source'], 'system': d['system'], 'units': d['units']},
            'schedules': [{'id': s['id'], 'name': s['name'], 'kind': s['kind'], 'role': role[s['id']], 'runs': len(s['replicates']), 'points': sum(len(r['points']) for r in s['replicates']),
                           'intensity': s.get('intensity'), 'program': schedule_programs(s['id'])[0], 'other': schedule_programs(s['id'])[1], 'led': s.get('led') or GREEN, 'second': s['second']['led'] if s.get('second') else None} for s in d['schedules']],
            'split': SPLIT, 'models': MODELS, 'runnable': ['mechanistic', 'green', 'learned', 'combined', 'baseline'], 'selected': bench['selected'], 'gate': bench['gate'], 'summary': bench['summary'], 'parameters': parameter_table(fit),
            'spectral': {'sha256': spectral()['sha256'], 'design': spectral()['design'], 'green': {'led': GREEN, 'centroidNm': spectral()['byLed'][GREEN]['centroidNm']}},
            'channels': [{k: c[k] for k in ('led', 'centroidNm', 'structure', 'k1', 'k2', 'rmseLog10', 'points', 'cvRmseLog10', 'published')} | {'structureName': STRUCTURE_NAME[c['structure']],
                          'ci95': {key: [float(x) for x in np.percentile(np.array(c['ensemble'])[:, i], [2.5, 97.5])] for i, key in enumerate(('k1', 'k2'))} if c['ensemble'] else None} for c in fit['channels'].values()],
            'stages': bench['stages'], 'regression': bench['regression'], 'state': {**STATE, 'phi': PHI, 'sensor': SENSOR, 'display': DISPLAY},
            'measuredGrowth': {**MEASURED, 'fittedKg': fit['mechanistic']['theta']['kg'], 'fittedDoublingMin': LN2 / fit['mechanistic']['theta']['kg']},
            'limits': LIMITS, 'spatial': spatial_note(), 'training': {'points': fit['trainingPoints'], 'rmseLog10': fit['mechanistic']['rmseLog10'], 'starts': fit['mechanistic']['starts'], 'startCosts': fit['mechanistic']['startCosts']},
            'learned': {'lambda': fit['learned']['lambda'], 'cv': fit['learned']['cvRmseLog10'], 'features': f'{len(FILTER_K)} saturations × {len(FILTER_TAU)} time constants'}, 'combined': {'lambda': fit['combined']['lambda'], 'cv': fit['combined']['cvRmseLog10']}}


def dispatch(service, action, p):
    p = p or {}
    if action == 'light_pulse_catalog': return catalog(service)
    if action == 'light_pulse_benchmark': return fitted(service)[1]
    if action == 'light_pulse_schedule': return schedule(service, p)
    if action == 'light_pulse_simulate': return simulate(service, p)
    if action == 'light_pulse_sweep': return sweep(service, p)
    if action == 'light_pulse_runs': return runs(service)
    if action == 'light_pulse_run_get': return run_get(service, p)
    if action == 'light_pulse_compare': return compare(service, p)
    if action == 'light_pulse_control': return control(service, p)
    if action == 'light_pulse_particles': return particles(service, p)
    raise ValueError('Unsupported light-pulse action.')
