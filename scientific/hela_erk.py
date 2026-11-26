"""Predictive HeLa EGF–ERK experiment: EGF binding, ERK pathway kinetics and nuclear transport of the ERK reporter,
tested against measured single-cell trajectories with the assay's own readout.

Data (fixtures/hela_erk/tany2022_egf_ktr.json, built by scripts/build-hela-erk-ktr.py from CC BY images): Tany R, Goto Y,
Kondo Y, Aoki K. Biochem J 2022;479(8):883-900, SSBD repository ssbd-repos-000232, Figure 2C. HeLa cells carrying a nuclear
marker and the ERK kinase translocation reporter (ERK-KTR), 10 ng/ml EGF, one frame per minute for 16 frames, several dishes
of the same day with four stage positions each. The readout is cytoplasmic over nuclear reporter fluorescence (C/N) per cell.

Model chain (evidence category B; units: minutes, nM, fractions):
  EGF L(t)  ->  occupied receptor B  ->  pathway drive D  ->  cascade stages X1…Xn  ->  active ERK E  ->  reporter phosphorylation p
            ->  reporter in nucleus and cytoplasm  ->  C/N
  dB/dt  = kon·L·(1 − B) − (koff + kint)·B
  D      = (1 − i_EGFR)·B/(K + B) / (1 + fb·F)
  dX1/dt = kc·(D − X1), …, dE/dt = kc·(Xn·(1 − i_MEK) − E);   dF/dt = kf·(E − F)
  dp/dt  = kdp·(g·G·E·(1 − p) − p)                           g: this cell's gain, log-normal across cells
  each reporter form keeps its own cytoplasm/nucleus concentration ratio (r_u unphosphorylated, ρ·r_u phosphorylated); with the
  cytoplasm/nucleus volume ratio v the pooled ratio is C/N_eq(p), approached at the transport rate:  dC/N/dt = ktr·(C/N_eq − C/N)
Fitted on the calibration dishes: the time EGF reaches the cells t0, the cascade rate kc, the reporter gain G, the spread of
the single-cell gain and the measurement noise. Everything else is assumed and tagged so. v comes from the electron-microscopy
HeLa volume, used as a geometry reference only: it is another specimen.

Three stages on separate dishes: calibration, model selection (cascade depth and transport lag), final test. The public
deposit holds one dose and no inhibitor, so a held-out dose or intervention cannot be scored from it; that is reported as
blocked, and `hela_erk_import` accepts such a series when one exists.
"""
import datetime, hashlib, json, math, pathlib, platform, re, uuid

import numpy as np

import cell_state
from hela_erk_actions import ACTIONS

VERSION = '1.0.0'
FIXTURE = pathlib.Path(__file__).resolve().parents[1] / 'fixtures' / 'hela_erk' / 'tany2022_egf_ktr.json'
CONTEXT = 'hela-tany2022-erk-ktr'          # the live-cell specimens
GEOMETRY = 'hela-jrc_hela-2'               # the electron-microscopy specimen, geometry reference only
EGF_KDA = 6.045
PROTOCOL_T0 = 5.0                          # min: the paper adds ligands "5 min after the start of imaging"
D04, D02 = 'Figure2C_20211008_DORA_KTR_EGF_04-03', 'Figure2C_20211008_DORA_KTR_EGF_02-01'
# A series is one stage position of one dish: the dishes have four compartments and EGF reaches each at its own time.
SPLIT = {'calibration': [D04 + '/s1', D04 + '/s2'], 'selection': [D04 + '/s3', D04 + '/s4'], 'test': [D02 + '/s1', D02 + '/s2', D02 + '/s3', D02 + '/s4']}
# Dishes labelled like the others (10 ng/ml EGF) that show no reporter response in the 16 deposited frames. Scored as labelled.
UNEXPLAINED = ['Figure2C_20211008_DORA_KTR_EGF_06-05', 'Figure2C_20211008_DORA_KTR_EGF_08-07', 'Figure2C_20211008_DORA_KTR_EGF_10-09', 'Figure2C_20211008_DORA_KTR_EGF_12-11']
ROLE_NAME = {'calibration': 'used for fitting', 'selection': 'used to choose the model structure', 'test': 'held out · another dish', 'unexplained': 'held out · no response measured', 'imported': 'imported · held-out condition'}
EM_REFERENCE = {'context': GEOMETRY, 'dataset': 'OpenOrganelle jrc_hela-2, level s4', 'classesSha256': '9fb38c1eeddaaf201c1ff317eebcf503a0d2c84d1990f2bea0d624cb475fb390',
                'nucleusUm3': 768.8, 'cytosolUm3': 1930.9, 'volumeRatio': round(1930.9 / 768.8, 3),
                'note': 'Nucleoplasm (nucleus, chromatin, nucleolus) and cytosol of the acquired slab of one HeLa cell, from machine-learning segmentations. A geometry reference: the live cells were not imaged by electron microscopy, and the slab is not a whole cell.'}
FITTED = [('kc', 'min⁻¹', 'Rate of each cascade stage between receptor and active ERK', 0.6, 0.05, 20.0),
          ('G', '', 'Reporter phosphorylation gain at full ERK activity', 0.6, 0.01, 50.0)]
ASSUMED = {
    'kon': (0.1, 'nM⁻¹ min⁻¹', 'EGF binding to its receptor', 'Order of magnitude for EGF and EGFR (dissociation constant of a few nM); not measured in these cells.'),
    'koff': (0.24, 'min⁻¹', 'EGF release from its receptor', 'Order of magnitude for EGF and EGFR; not measured in these cells.'),
    'kint': (0.1, 'min⁻¹', 'Internalisation of occupied receptor', 'Assumed. Receptor recycling and ligand depletion are not modelled.'),
    'K': (0.01, 'fraction', 'Receptor occupancy at half-maximal pathway drive', 'Assumed so that ERK is half-maximal near 0.2 ng/ml EGF. One measured dose cannot determine it.'),
    'fb': (0.5, '', 'Strength of the negative feedback from ERK', 'Assumed. The 16 measured minutes end before feedback can be told from no feedback.'),
    'kf': (0.03, 'min⁻¹', 'Rate of the negative feedback', 'Assumed, for the same reason.'),
    'kdp': (1.0, 'min⁻¹', 'Reporter dephosphorylation', 'Assumed fast compared with the cascade.'),
    'ktr': (0.5, 'min⁻¹', 'Exchange of the reporter between nucleus and cytoplasm', 'Assumed: a transport time of about two minutes.'),
    'rho': (4.0, '', 'Cytoplasm/nucleus ratio of phosphorylated over unphosphorylated reporter', 'Assumed. With one dose it cannot be separated from the gain G.'),
}
STRUCTURES = [{'key': 'd1', 'depth': 1, 'transport': False, 'name': 'one stage, instant transport'}, {'key': 'd2', 'depth': 2, 'transport': False, 'name': 'two stages, instant transport'},
              {'key': 'd1t', 'depth': 1, 'transport': True, 'name': 'one stage, transport lag'}, {'key': 'd2t', 'depth': 2, 'transport': True, 'name': 'two stages, transport lag'},
              {'key': 'd3t', 'depth': 3, 'transport': True, 'name': 'three stages, transport lag'}]
SELECT_MARGIN = 0.05
MODELS = {'mechanistic': 'Mechanistic chain', 'nominal': 'Mechanistic chain at the protocol time (5 min)', 'template': 'Mean calibration response (empirical)', 'static': 'No response (static baseline)'}
ONSET_NOTE = 'The deposit does not record when EGF reached each compartment. One number per series, the onset time, is therefore inferred from that series itself, with every other parameter frozen. For held-out series this is the only quantity taken from their own data; the "protocol time" predictor takes none.'
LIMITS = {'egfNgPerMl': (0.0, 100.0), 'durationMin': (5.0, 240.0), 'samples': 200, 'inhibition': (0.0, 1.0)}
DT = 0.05
DISPLAY = {'copies': 600, 'frames': 96, 'provenance': {'kind': 'assumed', 'note': 'Reporter copies per cell were not measured. Six hundred particles carry the nuclear and cytoplasmic fractions; only the fractions are modelled.'}}
STATE = cell_state.describe(
    'fold.cell-state.erk-ktr', 1,
    [{'key': 'egf', 'name': 'EGF in the medium', 'unit': 'ng/ml', 'from': 'input', 'where': 'medium', 'evidence': 'input'},
     {'key': 'receptor', 'name': 'Occupied EGF receptor', 'unit': 'fraction of surface receptor', 'from': 'B', 'where': 'plasma membrane', 'evidence': 'simulated'},
     {'key': 'erk', 'name': 'Active ERK', 'unit': 'fraction of its maximum', 'from': 'E', 'where': 'cytoplasm and nucleus', 'evidence': 'simulated'},
     {'key': 'phospho', 'name': 'Phosphorylated reporter', 'unit': 'fraction of reporter', 'from': 'p', 'where': 'whole cell', 'evidence': 'simulated'},
     {'key': 'nuclear', 'name': 'Reporter in the nucleus', 'unit': 'fraction of reporter molecules', 'from': '1 / (1 + C/N·v)', 'where': 'nucleus', 'evidence': 'inferred'},
     {'key': 'cytoplasmic', 'name': 'Reporter in the cytoplasm', 'unit': 'fraction of reporter molecules', 'from': 'C/N·v / (1 + C/N·v)', 'where': 'cytoplasm', 'evidence': 'inferred'},
     {'key': 'cn', 'name': 'ERK-KTR cytoplasm / nucleus', 'unit': 'ratio of mean fluorescence', 'from': 'readout', 'where': 'two regions per cell', 'evidence': 'predicted · measured in the assay'}],
    [{'key': 'kinetic', 'stepMin': DT, 'what': 'Receptor, cascade, feedback, reporter phosphorylation and transport, advanced together (fourth-order Runge–Kutta for the pathway, exact exponential steps for the reporter).'},
     {'key': 'measurement', 'stepMin': 1.0, 'what': 'One frame per minute; the prediction is read at each cell\'s recorded frame times.'},
     {'key': 'display', 'frames': DISPLAY['frames'], 'what': 'Evenly spaced times at which the nuclear and cytoplasmic fractions become particles in the 3-D reference cell.'},
     {'key': 'spatial', 'what': 'None. The assay resolves two regions per cell; each display frame draws fresh positions inside the nucleus and the cytosol of the reference cell.'}],
    ['EGF (ng/ml ÷ 6.045 kDa → nM) → occupied receptor (fraction)', 'occupied receptor → pathway drive → active ERK (fraction of maximum)', 'active ERK × this cell\'s gain → phosphorylated reporter (fraction)',
     'phosphorylated fraction, this cell\'s resting C/N and the volume ratio v → nuclear and cytoplasmic reporter (fractions of molecules): the one reporter split',
     'reporter split → C/N, the quantity the microscope reports', 'reporter split × assumed copies → display particles in the nucleus and the cytosol of the reference cell'],
    {'key': 'cn', 'mapping': 'relative', 'note': 'C/N is a ratio of wide-field fluorescence means: light from cytoplasm above and below the nucleus enters the nuclear region. Each cell\'s own resting C/N anchors the prediction; absolute concentrations are not claimed.'})
RESOLUTION = {'supported': 'Two regions per cell: the nucleus and a perinuclear cytoplasmic ring.', 'pixelUm': 0.74, 'frameIntervalMin': 1.0,
              'notSupported': 'Gradients inside the nucleus or the cytoplasm, membrane-proximal signalling, and anything below a few micrometres. The 3-D view places molecules uniformly inside each of the two compartments.'}
ENGINE = {'id': 'fold.hela-erk.egf-ktr', 'name': 'HeLa EGF–ERK reporter response', 'version': VERSION, 'evidence': 'B',
          'numericalMethod': f'Fixed step of {DT} min: fourth-order Runge–Kutta for receptor, cascade and feedback; exact exponential steps for reporter phosphorylation and transport. Every run is recomputed with SciPy LSODA.',
          'equations': ['dB/dt = kon·L·(1 − B) − (koff + kint)·B', 'D = (1 − i_EGFR)·B/(K + B)/(1 + fb·F)', 'dX1/dt = kc·(D − X1) … dE/dt = kc·(Xn·(1 − i_MEK) − E)', 'dF/dt = kf·(E − F)',
                        'dp/dt = kdp·(g·G·E·(1 − p) − p)', 'd(C/N)/dt = ktr·(C/N_eq(p; r_u, ρ, v) − C/N)'],
          'assumptions': ['EGF concentration in the medium is constant after addition', 'Every cell shares the pathway kinetics; cells differ in resting C/N (measured) and in reporter gain (log-normal, fitted)',
                          'ERK activity is the same in nucleus and cytoplasm', 'Nucleus and cytoplasm are each well mixed', 'The reference volume ratio of another HeLa cell applies to these cells'],
          'limits': ['One measured dose (10 ng/ml) and no measured inhibitor: dose dependence and inhibitor responses rest on assumed constants and are simulations, not tested predictions',
                     'Measured for 16 minutes: the peak and the recovery are never reached, so neither is tested', 'One day, one laboratory, one cell line and one reporter',
                     'ERK activity itself was not measured: it is inferred through the reporter', RESOLUTION['notSupported']]}


class ErkError(ValueError):
    pass


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), default=float).encode()).hexdigest()


_DATA = None


def dataset():
    global _DATA
    if _DATA is None:
        if not FIXTURE.is_file():
            raise ErkError('The HeLa ERK-KTR dataset is missing from this installation.')
        raw = FIXTURE.read_bytes()
        _DATA = json.loads(raw); _DATA['sha256'] = hashlib.sha256(raw).hexdigest()
        units = {}
        for sr in _DATA['series']:
            for pos in sorted({c['position'] for c in sr['cells']}):
                cells = [c for c in sr['cells'] if c['position'] == pos]
                units[f"{sr['id']}/s{pos}"] = {'id': f"{sr['id']}/s{pos}", 'dish': sr['id'], 'position': pos, 'cells': cells, 'name': sr['id'].replace('Figure2C_20211008_DORA_KTR_EGF_', 'Dish ') + f' · position {pos}'}
        _DATA['byId'] = units
    return _DATA


def unexplained_units():
    return [u for u, x in dataset()['byId'].items() if x['dish'] in UNEXPLAINED and len(x['cells']) >= 5]


def cells_of(uid, extra=None):
    """Kept cells of one series: frame times and C/N (cells × frames), and identity."""
    u = {**dataset()['byId'], **(extra or {})}[uid]
    return np.array([c['t'] for c in u['cells']], float), np.array([c['cn'] for c in u['cells']], float), [c['id'] for c in u['cells']]


def baseline(t, cn, t0):
    """Each cell's resting C/N: the mean of its frames before EGF arrives (at least the first frame)."""
    mask = t < t0 - 0.25; mask[:, 0] = True
    return (cn * mask).sum(axis=1) / mask.sum(axis=1)


# ------------------------------------------------------------------ model

def constants(theta=None):
    out = {k: v[0] for k, v in ASSUMED.items()}; out['v'] = EM_REFERENCE['volumeRatio']
    out.update(theta or {})
    return out


def pathway(c, duration, egf_ng_ml, t0, depth=2, mek=0.0, egfr=0.0, dt=DT):
    """Receptor occupancy, cascade and feedback on the kinetic clock. Returns t, B, E, F (arrays of steps + 1)."""
    n = int(round(duration / dt)); L = egf_ng_ml / EGF_KDA
    kon, koff, kint, K, fb, kf, kc = c['kon'], c['koff'], c['kint'], c['K'], c['fb'], c['kf'], c['kc']

    def rhs(y, lig):
        B = y[0]; F = y[-1]; D = (1 - egfr) * B / (K + B) / (1 + fb * F) if B > 0 else 0.0
        d = np.empty_like(y); d[0] = kon * lig * (1 - B) - (koff + kint) * B
        prev = D
        for i in range(1, depth + 1):
            d[i] = kc * ((prev * (1 - mek) if i == depth else prev) - y[i]); prev = y[i]
        d[-1] = kf * (y[depth] - F)
        return d
    y = np.zeros(depth + 2); out = np.empty((n + 1, depth + 2)); out[0] = y
    for j in range(n):
        lig = L * min(1.0, max(0.0, ((j + 1) * dt - t0) / dt))            # the step that contains t0 gets EGF for its remaining part
        k1 = rhs(y, lig); k2 = rhs(y + dt / 2 * k1, lig); k3 = rhs(y + dt / 2 * k2, lig); k4 = rhs(y + dt * k3, lig)
        y = y + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4); out[j + 1] = y
    return np.arange(n + 1) * dt, out[:, 0], out[:, depth], out[:, -1]


def cn_eq(p, r_u, rho, v):
    """Pooled cytoplasm/nucleus concentration ratio when a fraction p of the reporter is phosphorylated."""
    fu = r_u * v / (1 + r_u * v); fp = rho * r_u * v / (1 + rho * r_u * v)
    cyt = (1 - p) * fu + p * fp
    return cyt / ((1 - cyt) * v)


def reporter(c, E, r_u, gain, transport=True, dt=DT):
    """Reporter phosphorylation and C/N for arrays of cells (resting ratio r_u, gain). Returns p and C/N (cells × steps + 1)."""
    r_u = np.atleast_1d(np.asarray(r_u, float)); gain = np.broadcast_to(np.asarray(gain, float), r_u.shape); n = len(E) - 1
    p = np.zeros(len(r_u)); cn = r_u.copy(); P = np.empty((len(r_u), n + 1)); C = np.empty_like(P); P[:, 0] = p; C[:, 0] = cn
    et = math.exp(-c['ktr'] * dt)
    for j in range(n):
        a = gain * c['G'] * (E[j] + E[j + 1]) / 2; rate = c['kdp'] * (a + 1); p_inf = a / (a + 1)
        p_new = p_inf + (p - p_inf) * np.exp(-rate * dt)
        target = cn_eq((p + p_new) / 2, r_u, c['rho'], c['v'])
        cn = target + (cn - target) * et if transport else cn_eq(p_new, r_u, c['rho'], c['v'])
        p = p_new; P[:, j + 1] = p; C[:, j + 1] = cn
    return P, C


GRID_END = 18.0


def erk_from_onset(c, structure, cond=None):
    """Active ERK on the kinetic clock with EGF added at time 0; a later onset is this curve shifted (the equations do not
    depend on absolute time)."""
    cond = cond or {}
    t, B, E, F = pathway(c, GRID_END, cond.get('egf', 10.0), 0.0, structure['depth'], cond.get('mek', 0.0), cond.get('egfr', 0.0))
    return t, E


def predict_unit(c, structure, t_obs, base, t0, gain=1.0, cond=None, curve=None):
    """C/N of cells (cells × frames) at their own frame times, for EGF arriving at t0."""
    t, E0 = curve or erk_from_onset(c, structure, cond)
    E = np.interp(t - t0, t, E0, left=0.0)
    C = reporter(c, E, base, gain, structure['transport'])[1]
    return np.array([np.interp(t_obs[i], t, C[i]) for i in range(len(t_obs))])


def onset(c, structure, t_obs, cn, gain=1.0, cond=None):
    """When EGF reached one series: the onset time that best fits its mean relative C/N with every other parameter frozen.
    `detected` is False when no onset inside the measured window fits better than no response at all."""
    curve = erk_from_onset(c, structure, cond); end = float(t_obs.max())

    def err(t0):
        base = baseline(t_obs, cn, t0); pred = predict_unit(c, structure, t_obs, base, t0, gain, cond, curve)
        return float((((pred / base[:, None]).mean(axis=0) - (cn / base[:, None]).mean(axis=0)) ** 2).sum())
    coarse = np.arange(0.0, end + 0.01, 0.5); e = [err(x) for x in coarse]; k = int(np.argmin(e))
    fine = np.arange(max(0.0, coarse[k] - 0.5), min(end, coarse[k] + 0.5) + 1e-9, 0.1); e2 = [err(x) for x in fine]; t0 = float(fine[int(np.argmin(e2))])
    base = baseline(t_obs, cn, end + 1); flat = float((((cn / base[:, None]).mean(axis=0) - 1) ** 2).sum())
    return {'t0': round(t0, 2), 'detected': bool(t0 < end - 2.0 and min(e2) < 0.5 * flat), 'sse': float(min(e2)), 'sseNoResponse': flat, 'evidence': 'inferred'}


def fit_structure(structure, units):
    """Shared kc and G by least squares on C/N relative to each cell's resting value, alternating with each calibration
    series' onset time."""
    from scipy.optimize import least_squares
    lo = np.log([FITTED[0][4], FITTED[1][4]]); hi = np.log([FITTED[0][5], FITTED[1][5]])
    unpack = lambda x: constants({'kc': float(np.exp(x[0])), 'G': float(np.exp(x[1]))})
    data = {u: cells_of(u)[:2] for u in units}; t0s = {u: 4.0 for u in units}; x = np.log([FITTED[0][3], FITTED[1][3]]); best = None

    def resid(x):
        c = unpack(x); curve = erk_from_onset(c, structure); out = []
        for u, (t, cn) in data.items():
            base = baseline(t, cn, t0s[u]); out.append(((predict_unit(c, structure, t, base, t0s[u], 1.0, None, curve) - cn) / base[:, None]).ravel())
        return np.concatenate(out)
    for _ in range(4):
        best = least_squares(resid, np.clip(x, lo + 1e-6, hi - 1e-6), bounds=(lo, hi), diff_step=1e-3, max_nfev=60); x = best.x
        t0s = {u: onset(unpack(x), structure, *data[u])['t0'] for u in units}
    best = least_squares(resid, x, bounds=(lo, hi), diff_step=1e-3, max_nfev=60)
    n = best.fun.size; cov = 2 * best.cost / max(1, n - 2 - len(units)) * np.linalg.pinv(best.jac.T @ best.jac); c = unpack(best.x)
    return {'x': best.x.tolist(), 'theta': {'kc': c['kc'], 'G': c['G']}, 'onsets': t0s, 'rmseRelative': float(np.sqrt(2 * best.cost / n)), 'cov': cov.tolist(), 'points': int(n),
            'atBound': [bool(abs(v - a) < 1e-4 or abs(v - b) < 1e-4) for v, a, b in zip(best.x, lo, hi)]}


GAIN_GRID = np.exp(np.linspace(-3.0, 3.0, 61))


def cell_gains(c, structure, t_obs, cn, t0):
    """Each cell's own gain (best of a fixed grid) and the residual left after it: the two sources of single-cell spread."""
    t, E0 = erk_from_onset(c, structure); E = np.interp(t - t0, t, E0, left=0.0); base = baseline(t_obs, cn, t0)
    gains = np.empty(len(base)); left = []
    for i in range(len(base)):
        pred = np.array([np.interp(t_obs[i], t, row) for row in reporter(c, E, np.full(len(GAIN_GRID), base[i]), GAIN_GRID, structure['transport'])[1]])
        err = ((pred - cn[i][None, :]) ** 2).sum(axis=1); k = int(np.argmin(err)); gains[i] = GAIN_GRID[k]; left.append((pred[k] - cn[i]) / base[i])
    return gains, np.array(left)


def train():
    """Calibration, then model selection, each on its own series. Deterministic."""
    fits = {}; sel = {}; sel_onsets = {}
    for st in STRUCTURES:
        f = fit_structure(st, SPLIT['calibration']); c = constants(f['theta']); err = []; sel_onsets[st['key']] = {}
        for u in SPLIT['selection']:
            t, cn, _ = cells_of(u); o = onset(c, st, t, cn); base = baseline(t, cn, o['t0']); post = t.mean(axis=0) >= o['t0']; sel_onsets[st['key']][u] = o
            d = (predict_unit(c, st, t, base, o['t0']) / base[:, None]).mean(axis=0) - (cn / base[:, None]).mean(axis=0); err.append((d[post] ** 2).mean())
        fits[st['key']] = f; sel[st['key']] = float(np.sqrt(np.mean(err)))
    best = min(sel.values())
    chosen = min((st for st in STRUCTURES if sel[st['key']] <= (1 + SELECT_MARGIN) * best + 1e-12), key=lambda st: (st['depth'] + st['transport'], sel[st['key']]))
    f = fits[chosen['key']]; c = constants(f['theta']); gains = []; left = []; tau = np.arange(-6.0, 16.01, 0.25); rel = []
    for u in SPLIT['calibration']:
        t, cn, _ = cells_of(u); g, l = cell_gains(c, chosen, t, cn, f['onsets'][u]); gains.append(g); left.append(l[:, t.mean(axis=0) >= f['onsets'][u]].ravel())
        base = baseline(t, cn, f['onsets'][u]); rel += [np.interp(tau, t[i] - f['onsets'][u], cn[i] / base[i], left=np.nan, right=np.nan) for i in range(len(base))]
    gains = np.concatenate(gains); left = np.concatenate(left)
    inner = (gains > GAIN_GRID[0] * 1.01) & (gains < GAIN_GRID[-1] * 0.99)
    count = (~np.isnan(np.array(rel))).sum(axis=0); mean = np.where(count >= 5, np.nansum(np.array(rel), axis=0) / np.maximum(count, 1), np.nan)
    ok = ~np.isnan(mean); mean = np.interp(tau, tau[ok], mean[ok]); mean[tau < 0] = 1.0                 # before EGF: resting; beyond the measured span: the last measured value
    return {'version': VERSION, 'dataset': dataset()['sha256'], 'split': SPLIT, 'structure': chosen, 'theta': f['theta'], 'fit': f, 'onsets': {**{u: {'t0': v, 'detected': True, 'evidence': 'inferred'} for u, v in f['onsets'].items()}, **sel_onsets[chosen['key']]},
            'selection': {'rmseOfMeanRelative': sel, 'margin': SELECT_MARGIN},
            'gain': {'sigmaLn': float(np.log(gains[inner]).std(ddof=1)), 'muLn': float(np.log(gains[inner]).mean()), 'cells': int(inner.sum()), 'atGridEdge': int((~inner).sum()), 'note': 'Spread of the single-cell reporter gain among calibration cells, in natural-log units.'},
            'noise': {'relative': float(np.sqrt((left ** 2).mean())), 'note': 'Residual of C/N relative to each cell\'s resting value after its own gain is fitted, on frames after EGF.'},
            'template': {'tau': tau.tolist(), 'mean': mean.tolist(), 'measuredSpanMin': float(tau[ok].max()), 'note': 'Mean relative C/N of the calibration cells against time since EGF arrived. It knows nothing about dose or inhibitors.'},
            'calibrationCells': int(len(gains)), 'selectionCells': int(sum(len(cells_of(u)[2]) for u in SPLIT['selection']))}


def quantiles(fit, n=41):
    """Gains at evenly spaced quantiles of the fitted log-normal: a deterministic stand-in for sampling cells."""
    from scipy.stats import norm
    q = (np.arange(n) + 0.5) / n
    return np.exp(fit['gain']['muLn'] + fit['gain']['sigmaLn'] * norm.ppf(q))


def interval(fit, bands_rel):
    """90 % predictive interval of relative C/N: the spread across cell gains, widened by the measurement noise."""
    z = 1.645 * fit['noise']['relative']
    return np.percentile(bands_rel, 5, axis=0) - z, np.percentile(bands_rel, 95, axis=0) + z


def predict(fit, model, t_obs, base, t0, cond=None):
    """C/N for cells (cells × frames) from one predictor; the median cell for the mechanistic chain."""
    if model == 'static':
        return np.repeat(base[:, None], t_obs.shape[1], axis=1)
    if model == 'template':
        return base[:, None] * np.interp(t_obs - t0, fit['template']['tau'], fit['template']['mean'])
    return predict_unit(constants(fit['theta']), fit['structure'], t_obs, base, PROTOCOL_T0 if model == 'nominal' else t0, math.exp(fit['gain']['muLn']), cond)


# ------------------------------------------------------------------ scoring

def half_rise(t, y, t0):
    """Time after t0 at which a rising series reaches half of its last value's gain over its first, or None."""
    amp = y[-1] - y[0]
    if not amp > 0.02:
        return None
    for i in range(1, len(t)):
        if y[i - 1] < y[0] + amp / 2 <= y[i]:
            return float(t[i - 1] + (y[0] + amp / 2 - y[i - 1]) / (y[i] - y[i - 1]) * (t[i] - t[i - 1]) - t0)
    return None


def score(fit, uid, extra=None, condition=None):
    """One series against every predictor: single-cell and population-mean trajectory errors, response features and
    interval coverage. The onset time is inferred from the series (see ONSET_NOTE); the baseline of each cell is its
    frames before that time, or before the protocol time when no onset is detected."""
    cond = {'egf': 10.0, 'mek': 0.0, 'egfr': 0.0, **(condition or {})}; c = constants(fit['theta']); st = fit['structure']; g0 = math.exp(fit['gain']['muLn'])
    t, cn, who = cells_of(uid, extra); tm = t.mean(axis=0)
    o = fit['onsets'].get(uid) or onset(c, st, t, cn, g0, cond)
    t0 = o['t0'] if o['detected'] else PROTOCOL_T0                      # no onset found: score against the protocol, which is what the labels promise
    base = baseline(t, cn, t0); rel = cn / base[:, None]; post = tm >= t0; meas_mean = rel.mean(axis=0)
    out = {'id': uid, 'name': ({**dataset()['byId'], **(extra or {})}[uid]).get('name', uid), 'cells': len(base), 'condition': cond, 'onset': {**o, 'used': t0, 'protocol': PROTOCOL_T0}, 't': tm.tolist(),
           'measured': {'meanRelative': meas_mean.tolist(), 'sdRelative': rel.std(axis=0, ddof=1).tolist(), 'meanCn': cn.mean(axis=0).tolist(), 'restingCn': float(base.mean()), 'evidence': 'measured'}, 'models': {}}
    m_amp = float(meas_mean[-1] - 1); m_half = half_rise(tm[post], meas_mean[post], t0) if post.sum() > 2 else None
    for m in MODELS:
        pred = predict(fit, m, t, base, t0, cond); prel = pred / base[:, None]
        cell_rmse = np.sqrt((((pred - cn) / base[:, None])[:, post] ** 2).mean(axis=1)); pm = prel.mean(axis=0)
        f = {'amplitude': {'label': 'Rise of C/N at the last frame, relative to rest', 'unit': 'fraction of resting C/N', 'measured': m_amp, 'predicted': float(pm[-1] - 1), 'supported': True},
             'halfRiseMin': {'label': 'Time from EGF to half of the last-frame rise', 'unit': 'min', 'measured': m_half, 'predicted': half_rise(tm[post], pm[post], t0) if post.sum() > 2 else None, 'supported': m_half is not None},
             'timeToPeakMin': {'label': 'Time to peak', 'unit': 'min', 'measured': None, 'predicted': None, 'supported': False, 'note': 'No peak is observed inside the measured frames.'},
             'halfRecoveryMin': {'label': 'Time to half recovery', 'unit': 'min', 'measured': None, 'predicted': None, 'supported': False, 'note': 'The measurement ends before any recovery.'}}
        for v in f.values():
            if v['supported'] and v['predicted'] is not None:
                v['error'] = v['predicted'] - v['measured']; v['relativeError'] = v['error'] / v['measured'] if abs(v['measured']) > 0.02 else None
            elif v['supported']:
                v['supported'] = False; v['note'] = 'This predictor does not rise, so the feature does not exist for it.'
        out['models'][m] = {'meanRelative': pm.tolist(), 'rmseOfMeanRelative': float(np.sqrt(((pm - meas_mean)[post] ** 2).mean())), 'cellRmseRelative': {'median': float(np.median(cell_rmse)), 'mean': float(cell_rmse.mean()), 'p90': float(np.percentile(cell_rmse, 90))},
                            'pooledRmseRelative': float(np.sqrt((cell_rmse ** 2).mean())), 'features': f}
    # uncertainty: where a single cell's trajectory should fall
    g = quantiles(fit); tg, E0 = erk_from_onset(c, st, cond); E = np.interp(tg - t0, tg, E0, left=0.0)
    inside = 0; total = 0; lows = []; highs = []
    for i in range(len(base)):
        bands = np.array([np.interp(t[i], tg, row) for row in reporter(c, E, np.full(len(g), base[i]), g, st['transport'])[1]]) / base[i]
        lo, hi = interval(fit, bands); lows.append(lo); highs.append(hi)
        inside += int(((rel[i] >= lo) & (rel[i] <= hi))[post].sum()); total += int(post.sum())
    out['models']['mechanistic']['interval'] = {'level': 0.9, 'low': np.mean(lows, axis=0).tolist(), 'high': np.mean(highs, axis=0).tolist(), 'inside': inside, 'total': total, 'coverage': inside / total if total else None,
                                                'note': 'Spread of the single-cell gain fitted on the calibration series, widened by the measurement noise. Counted per cell and frame after EGF.'}
    keep = np.linspace(0, len(base) - 1, min(len(base), 30)).round().astype(int)
    out['sample'] = [{'id': who[i], 't': t[i].tolist(), 'cn': cn[i].tolist(), 'relative': rel[i].tolist(), 'restingCn': float(base[i])} for i in keep]
    return out


def imports(root):
    """Series added by the user (another dose, an inhibitor): {id: series}."""
    d = pathlib.Path(root) / 'hela_erk' / 'imports' if root else None; out = {}
    for f in sorted(d.glob('*.json')) if d and d.is_dir() else []:
        s = json.loads(f.read_text()); out[s['id']] = s
    return out


def resting_default(fit):
    """Median resting C/N of the calibration cells."""
    return float(np.median(np.concatenate([baseline(*cells_of(u)[:2], fit['onsets'][u]['t0']) for u in SPLIT['calibration']])))


def benchmark(fit, extra=None):
    """Every series against every predictor, by role; what could be held out and what could not; and every miss."""
    extra = extra or {}
    rows = {role: [score(fit, u) for u in ids] for role, ids in SPLIT.items()}
    rows['unexplained'] = [score(fit, u) for u in unexplained_units()]
    rows['imported'] = [{**score(fit, sid, extra, s_.get('condition')), 'label': s_.get('label'), 'evidenceOfData': s_.get('evidence', 'measured')} for sid, s_ in extra.items()]
    pool = lambda rs, m, key: float(np.sqrt(np.average([r['models'][m][key] ** 2 for r in rs], weights=[r['cells'] for r in rs]))) if rs else None
    summary = {role: {m: {'pooledCellRmseRelative': pool(rs, m, 'pooledRmseRelative'), 'rmseOfMeanRelative': pool(rs, m, 'rmseOfMeanRelative')} for m in MODELS} for role, rs in rows.items()}
    cover = {role: {'inside': sum(r['models']['mechanistic']['interval']['inside'] for r in rs), 'total': sum(r['models']['mechanistic']['interval']['total'] for r in rs)} for role, rs in rows.items() if rs}
    for cv in cover.values():
        cv['coverage'] = cv['inside'] / cv['total'] if cv['total'] else None
    test = summary['test']
    gate_ok = test['mechanistic']['pooledCellRmseRelative'] < test['static']['pooledCellRmseRelative']
    known_dose = any(r['condition']['egf'] != 10.0 for r in rows['imported']); known_drug = any(r['condition']['mek'] or r['condition']['egfr'] for r in rows['imported'])
    blocked = ('The public deposit (SSBD project 232, Figure 2C) labels every dish 10 ng/ml EGF and holds no inhibitor. The signalling study of Gross and Rotwein (2017) reports dose and inhibitor experiments in HeLa cells with a related reporter, '
               'but its single-cell data are not deposited: Europe PMC lists no supplementary files for PMC5401947. Import such a series to score it.')
    n_un = sum(r['cells'] for r in rows['unexplained'])
    holdouts = {'series': {'status': 'scored', 'what': f"{len(SPLIT['test'])} positions of another dish, {sum(r['cells'] for r in rows['test'])} cells, never used for fitting or model selection",
                           'independence': 'Another dish of the same day, laboratory and labelled dose. Not an independent laboratory or day.'},
                'dose': {'status': 'scored' if known_dose else 'blocked', 'reason': None if known_dose else blocked},
                'intervention': {'status': 'scored' if known_drug else 'blocked', 'reason': None if known_drug else blocked},
                'unexplained': {'status': 'scored as labelled', 'dishes': UNEXPLAINED, 'cells': n_un,
                                'statement': f'Four dishes ({n_un} cells) carry the same label, 10 ng/ml EGF, and show no rise of C/N in their 16 deposited frames: the mean drifts down by a few percent. The deposit does not say why. '
                                             'They may be lower doses of the paper\'s dose-response figure or may have been stimulated after the deposited frames; neither can be established from the files, so they are not used as a dose hold-out. '
                                             'Taken at their label, the model predicts a rise that was not measured: a failure, shown below.'}}
    failures = []
    for role in ('test', 'unexplained', 'imported'):
        for r in rows[role]:
            m = r['models']['mechanistic']; why = [k for k, v in m['features'].items() if v.get('relativeError') is not None and abs(v['relativeError']) > 0.25]
            if not r['onset']['detected']:
                why.append('no response measured where one is predicted')
            if m['interval']['coverage'] is not None and m['interval']['coverage'] < 0.8:
                why.append('uncertainty coverage')
            if m['pooledRmseRelative'] >= r['models']['template']['pooledRmseRelative']:
                why.append('no better than the empirical mean response')
            if m['pooledRmseRelative'] >= r['models']['static']['pooledRmseRelative']:
                why.append('no better than assuming no response')
            if why:
                failures.append({'id': r['id'], 'name': r['name'], 'role': role, 'why': why, 'coverage': m['interval']['coverage'], 'cellRmse': m['pooledRmseRelative'], 'templateRmse': r['models']['template']['pooledRmseRelative'],
                                 'staticRmse': r['models']['static']['pooledRmseRelative'], 'measuredAmplitude': m['features']['amplitude']['measured'], 'predictedAmplitude': m['features']['amplitude']['predicted']})
    return {'schedules': rows, 'summary': summary, 'intervalCoverage': {'level': 0.9, **cover}, 'holdouts': holdouts, 'failures': failures, 'onsetNote': ONSET_NOTE,
            'status': 'retrospective',
            'statement': 'Retrospective and not blind. The images were public before this model was written, and the split was fixed only after a first pass showed that four of the six dishes do not respond: '
                         'calibration and model selection then went to dish 04-03 (the dataset named in the task) and the final test to dish 02-01. No parameter and no structure was chosen on dish 02-01.',
            'gate': {'passed': bool(gate_ok), 'statement': 'On the held-out dish the mechanistic chain is closer to single cells than assuming no response.' if gate_ok else 'On the held-out dish the mechanistic chain is no closer to single cells than assuming no response.'},
            'unsupportedFeatures': ['timeToPeakMin', 'halfRecoveryMin'], 'metric': 'Root-mean-square error of C/N relative to each cell\'s resting C/N, on the frames after EGF (0 is perfect; 0.10 is ten percent of the resting ratio).'}


def _fit_file(root):
    return pathlib.Path(root) / 'hela_erk' / f"fit-{VERSION}-{dataset()['sha256'][:16]}.json"


def fitted(service):
    """The calibrated model and its benchmark, computed once per library and dataset version; imports are rescored on every call."""
    root = getattr(service, 'root', None); f = _fit_file(root) if root else None; fit = None
    if f is not None and f.is_file():
        try:
            body = json.loads(f.read_text())
            if body['fit'].get('version') == VERSION and body['fit'].get('dataset') == dataset()['sha256']:
                fit = body['fit']; bench = body['benchmark']
        except (ValueError, KeyError):
            fit = None
    extra = imports(root)
    if fit is None:
        fit = train(); bench = benchmark(fit)
        if f is not None:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps({'fit': fit, 'benchmark': bench, 'created': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}, default=float))
    if extra:
        bench = benchmark(fit, extra)
    return fit, bench


def parameter_table(fit):
    se = np.sqrt(np.maximum(np.diag(np.array(fit['fit']['cov'])), 0)); rows = []
    for i, (key, unit, desc, _, lo, hi) in enumerate(FITTED):
        v = fit['theta'][key]
        rows.append({'key': key, 'value': v, 'unit': unit, 'description': desc, 'ci95': [v * math.exp(-1.96 * se[i]), v * math.exp(1.96 * se[i])], 'bounds': [lo, hi], 'atBound': fit['fit']['atBound'][i], 'determined': bool(not fit['fit']['atBound'][i] and se[i] < 0.5),
                     'provenance': {'kind': 'fitted', 'note': f"Fitted to {fit['calibrationCells']} cells of {len(SPLIT['calibration'])} calibration series."}})
    for u in SPLIT['calibration'] + SPLIT['selection']:
        rows.append({'key': 'onset · ' + dataset()['byId'][u]['name'], 'value': fit['onsets'][u]['t0'], 'unit': 'min', 'description': 'Time EGF reached this series', 'determined': True, 'provenance': {'kind': 'inferred', 'note': ONSET_NOTE}})
    rows.append({'key': 'σ gain', 'value': fit['gain']['sigmaLn'], 'unit': 'ln units', 'description': 'Spread of the reporter gain across cells', 'determined': True, 'provenance': {'kind': 'fitted', 'note': fit['gain']['note']}})
    rows.append({'key': 'noise', 'value': fit['noise']['relative'], 'unit': 'fraction of resting C/N', 'description': 'Measurement noise of one cell in one frame', 'determined': True, 'provenance': {'kind': 'fitted', 'note': fit['noise']['note']}})
    rows.append({'key': 'v', 'value': EM_REFERENCE['volumeRatio'], 'unit': '', 'description': 'Cytoplasm / nucleus volume ratio', 'determined': False, 'provenance': {'kind': 'inferred', 'note': EM_REFERENCE['note']}})
    for key, (v, unit, desc, note) in ASSUMED.items():
        rows.append({'key': key, 'value': v, 'unit': unit, 'description': desc, 'determined': False, 'provenance': {'kind': 'assumed', 'note': note}})
    return rows


# ------------------------------------------------------------------ the experiment

def _num(p, key, default, lo, hi, what):
    try:
        v = float(p.get(key, default))
    except (TypeError, ValueError):
        raise ErkError(f'{what} must be a number.')
    if not math.isfinite(v) or not lo <= v <= hi:
        raise ErkError(f'{what} must be between {lo:g} and {hi:g}.')
    return v


def _configure(p, fit):
    sid = p.get('series') if p.get('series') in dataset()['byId'] else None
    rest = resting_default(fit); t0 = PROTOCOL_T0
    if sid:                                                             # a measured series runs at its own inferred onset and mean resting C/N
        t_, cn_, _ = cells_of(sid); o = fit['onsets'].get(sid) or onset(constants(fit['theta']), fit['structure'], t_, cn_, math.exp(fit['gain']['muLn']))
        t0 = o['t0'] if o['detected'] else PROTOCOL_T0; rest = float(baseline(t_, cn_, t0).mean())
    cfg = {'context': CONTEXT, 'geometry': GEOMETRY, 'series': sid,
           'egfNgPerMl': 10.0 if sid else _num(p, 'egfNgPerMl', 10.0, *LIMITS['egfNgPerMl'], 'EGF'),
           'egfAtMin': t0 if sid else _num(p, 'egfAtMin', PROTOCOL_T0, 0.0, 60.0, 'The time of EGF addition'),
           'durationMin': _num(p, 'durationMin', 16.0 if sid else 60.0, *LIMITS['durationMin'], 'The duration'),
           'mekInhibition': 0.0 if sid else _num(p, 'mekInhibition', 0.0, *LIMITS['inhibition'], 'MEK inhibition'), 'egfrInhibition': 0.0 if sid else _num(p, 'egfrInhibition', 0.0, *LIMITS['inhibition'], 'EGFR inhibition'),
           'restingCn': rest if sid else _num(p, 'restingCn', rest, 0.05, 5.0, 'The resting C/N'), 'label': str(p.get('label') or '')[:120]}
    try:
        cfg['samples'] = int(p.get('samples', 41)); cfg['seed'] = int(p.get('seed', 7))
    except (TypeError, ValueError):
        raise ErkError('Samples and seed must be whole numbers.')
    if not 0 <= cfg['samples'] <= LIMITS['samples'] or not 0 <= cfg['seed'] < 2 ** 31:
        raise ErkError(f"Choose 0 to {LIMITS['samples']} cells for the uncertainty band and a non-negative seed.")
    parent = str(p.get('parent') or ''); cfg['parent'] = parent if re.fullmatch(r'[0-9a-f]{32}', parent) else None
    return cfg


def _trajectory(fit, cfg, dt=DT):
    c = constants(fit['theta']); st = fit['structure']
    t, B, E, F = pathway(c, cfg['durationMin'], cfg['egfNgPerMl'], cfg['egfAtMin'], st['depth'], cfg['mekInhibition'], cfg['egfrInhibition'], dt)
    P, C = reporter(c, E, [cfg['restingCn']], math.exp(fit['gain']['muLn']), st['transport'], dt)
    cyt = C[0] * c['v'] / (1 + C[0] * c['v'])
    return {'t': t, 'egf': np.where(t >= cfg['egfAtMin'], cfg['egfNgPerMl'], 0.0), 'receptor': B, 'erk': E, 'feedback': F, 'phospho': P[0], 'cn': C[0], 'cytoplasmic': cyt, 'nuclear': 1 - cyt}, c, st


def lsoda_check(fit, cfg, traj):
    """The whole chain recomputed by SciPy LSODA as one system, against the fixed-step integrator."""
    try:
        from scipy.integrate import solve_ivp
        c = constants(fit['theta']); st = fit['structure']; d = st['depth']; L = cfg['egfNgPerMl'] / EGF_KDA; g = math.exp(fit['gain']['muLn']); r_u = cfg['restingCn']

        def rhs(t, y):
            B, F, p, cn = y[0], y[d + 1], y[d + 2], y[d + 3]; D = (1 - cfg['egfrInhibition']) * B / (c['K'] + B) / (1 + c['fb'] * F) if B > 0 else 0.0
            out = [c['kon'] * L * (1 - B) - (c['koff'] + c['kint']) * B]; prev = D
            for i in range(1, d + 1):
                out.append(c['kc'] * ((prev * (1 - cfg['mekInhibition']) if i == d else prev) - y[i])); prev = y[i]
            a = g * c['G'] * y[d]
            return out + [c['kf'] * (y[d] - F), c['kdp'] * (a * (1 - p) - p), c['ktr'] * (cn_eq(p, r_u, c['rho'], c['v']) - cn) if st['transport'] else 0.0]
        t0 = cfg['egfAtMin']; end = cfg['durationMin']; grid = traj['t'][traj['t'] >= t0 + DT][::20]
        if t0 >= end or len(grid) < 3:
            return cell_state.check('Independent solver', True, 'n/a', None, 'EGF is added after the end of this run; nothing happens.') | {'applicable': False}
        y0 = [0.0] * (d + 2) + [0.0, r_u]
        r = solve_ivp(rhs, (t0, end), y0, method='LSODA', t_eval=grid, rtol=1e-9, atol=1e-12)
        ref = np.interp(grid, traj['t'], traj['cn'])
        got = r.y[d + 3] if st['transport'] else cn_eq(r.y[d + 2], r_u, c['rho'], c['v'])
        diff = float(np.max(np.abs(got - ref) / ref))
        return cell_state.check('Independent solver', r.success and diff < 5e-3, 'relative difference of C/N < 0.5 %', {'maxRelativeDifference': diff, 'solver': 'SciPy LSODA', 'points': int(len(grid))},
                                'The same equations integrated by SciPy LSODA from the moment EGF is added.')
    except Exception as e:                                             # a failed cross-check is reported, never hidden
        return cell_state.check('Independent solver', False, 'relative difference < 0.5 %', {'error': str(e)[:300]}, 'SciPy LSODA could not reproduce this run.')


def _thin(n_points, n=600):
    k = max(1, -(-(n_points - 1) // n))
    return np.unique(np.append(np.arange(0, n_points, k), n_points - 1))


def _events(traj, cfg):
    t = traj['t']; out = []
    if cfg['egfNgPerMl'] > 0 and cfg['egfAtMin'] < t[-1]:
        out.append({'time': round(cfg['egfAtMin'], 2), 'kind': 'stimulus', 'scale': 'stimulus', 'label': f"EGF added · {cfg['egfNgPerMl']:g} ng/ml", 'value': cfg['egfNgPerMl'], 'where': 'pm'})

    def add(series, kind, scale, label, where, floor):
        y = traj[series]; k = int(np.argmax(y)); amp = y[k] - y[0]
        if amp > floor:
            i = int(np.argmax(y >= y[0] + amp / 2)); out.append({'time': round(float(t[i]), 2), 'kind': kind, 'scale': scale, 'label': label, 'value': float(y[i]), 'where': where})
            if k < len(t) - 1:
                out.append({'time': round(float(t[k]), 2), 'kind': kind + '-peak', 'scale': scale, 'label': label.split(' half')[0].split(' at half')[0] + ' peak', 'value': float(y[k]), 'where': where})
    add('receptor', 'receptor', 'molecular', 'Receptor half-occupied', 'pm', 0.01)
    add('erk', 'erk', 'pathway', 'ERK at half its peak', 'cytosol', 0.02)
    add('cn', 'reporter', 'cell', 'Reporter at half its nuclear exit', 'nucleus', 0.01 * traj['cn'][0])
    return sorted(out, key=lambda e: e['time'])


def simulate(service, p):
    """Run one EGF experiment and save it as a research record. Deterministic."""
    fit, bench = fitted(service); cfg = _configure(p or {}, fit)
    traj, c, st = _trajectory(fit, cfg); t = traj['t']; idx = _thin(len(t))
    series = {k: traj[k][idx].tolist() for k in ('egf', 'receptor', 'erk', 'phospho', 'cn', 'nuclear', 'cytoplasmic')}
    if cfg['samples']:
        g = quantiles(fit, cfg['samples']); bands = reporter(c, traj['erk'], np.full(len(g), cfg['restingCn']), g, st['transport'])[1] / cfg['restingCn']
        lo, hi = interval(fit, bands); series['cnLow'] = (lo * cfg['restingCn'])[idx].tolist(); series['cnHigh'] = (hi * cfg['restingCn'])[idx].tolist()
    k = int(np.argmax(traj['cn'])); peak_reached = bool(k < len(t) - 1 and traj['cn'][k] > 1.001 * traj['cn'][-1])
    feats = {'amplitude': float(traj['cn'][k] / traj['cn'][0] - 1), 'timeToPeakMin': float(t[k] - cfg['egfAtMin']) if peak_reached else None, 'halfRiseMin': half_rise(t, traj['cn'][:k + 1] if k else traj['cn'], cfg['egfAtMin']) if k else None,
             'erkPeak': float(traj['erk'].max()), 'receptorPeak': float(traj['receptor'].max()), 'recoveryAtEnd': float((traj['cn'][k] - traj['cn'][-1]) / (traj['cn'][k] - traj['cn'][0])) if peak_reached else None}
    measured = score(fit, cfg['series']) if cfg['series'] else None
    half = _trajectory(fit, cfg, DT / 2)[0]['cn'][::2]; step = float(np.max(np.abs(half - traj['cn']) / traj['cn']))
    split_sum = float(np.max(np.abs(traj['nuclear'] + traj['cytoplasmic'] - 1)))
    back = traj['cytoplasmic'] / (traj['nuclear'] * c['v'])
    checks = [lsoda_check(fit, cfg, traj),
              cell_state.check('Bounds', min(traj[k_].min() for k_ in ('receptor', 'erk', 'phospho')) >= -1e-9 and max(traj[k_].max() for k_ in ('receptor', 'erk', 'phospho')) <= 1 + 1e-9 and traj['cn'].min() > 0, '0 ≤ occupancy, ERK activity, phosphorylated fraction ≤ 1; C/N > 0',
                               {'erkMax': float(traj['erk'].max()), 'receptorMax': float(traj['receptor'].max())}, 'Fractions stay fractions.'),
              cell_state.check('Step size', step < 2e-3, 'relative change of C/N < 0.2 % when the step is halved', {'maxRelativeChange': step, 'stepMin': DT}, f'The same run with a {DT / 2}-minute step.'),
              cell_state.check('Reporter conserved', split_sum < 1e-12, 'nuclear + cytoplasmic reporter = 1', {'maxDeviation': split_sum}, 'The reporter only moves between the two compartments; none is made or lost in the model.'),
              cell_state.same_series('One reporter split', back, traj['cn'], 'The plotted C/N and the molecules drawn in 3-D come from the same nuclear and cytoplasmic fractions, through the volume ratio v.', {'v': c['v']})]
    passed = all(ch['passed'] for ch in checks if ch['applicable'])
    warnings = []
    if cfg['egfNgPerMl'] != 10.0:
        warnings.append('Only 10 ng/ml EGF was measured. The response at another dose follows from assumed receptor constants: a simulation, not a tested prediction.')
    if cfg['mekInhibition'] or cfg['egfrInhibition']:
        warnings.append('No inhibitor was measured in this dataset. This inhibitor response is a simulation, not a tested prediction.')
    if cfg['durationMin'] > 16.5:
        warnings.append('Measurements end 16 minutes after the first frame. Later times, including the peak and any recovery, depend on the assumed feedback and were never tested.')
    evidence = {'egf': 'input', 'receptor': 'simulated', 'erk': 'simulated', 'phospho': 'simulated', 'nuclear': 'inferred', 'cytoplasmic': 'inferred', 'cn': 'predicted', 'measured': 'measured'}
    inputs = {'egfNgPerMl': {'value': cfg['egfNgPerMl'], 'unit': 'ng/ml', 'description': 'EGF in the medium'}, 'egfAtMin': {'value': cfg['egfAtMin'], 'unit': 'min', 'description': 'Time EGF reaches the cells' + (' (inferred from this series)' if cfg['series'] else '')},
              'durationMin': {'value': cfg['durationMin'], 'unit': 'min', 'description': 'Simulated duration'}, 'mekInhibition': {'value': cfg['mekInhibition'], 'unit': 'fraction', 'description': 'Fraction of MEK activity removed'},
              'egfrInhibition': {'value': cfg['egfrInhibition'], 'unit': 'fraction', 'description': 'Fraction of receptor signalling removed'}, 'restingCn': {'value': cfg['restingCn'], 'unit': 'ratio', 'description': 'Resting C/N of the simulated cell'},
              'samples': {'value': cfg['samples'], 'unit': 'cells', 'description': 'Quantiles of the single-cell gain for the uncertainty band'}, 'seed': {'value': cfg['seed'], 'unit': '', 'description': 'Seed of the 3-D particle positions'}}
    solver = {'stepMin': DT, 'outputPoints': int(len(idx)), 'model': 'mechanistic', 'modelVersion': VERSION, 'datasetSha256': dataset()['sha256'], 'fitSha256': _sha({'theta': fit['theta'], 'structure': fit['structure'], 'gain': fit['gain'], 'noise': fit['noise']}),
              'structure': st, 'parameters': {**fit['theta'], **{k_: v[0] for k_, v in ASSUMED.items()}, 'v': c['v']}, 'context': CONTEXT, 'geometryReference': EM_REFERENCE, 'stateVersion': STATE['version']}
    outputs = {'time': float(t[-1]), 'timeUnit': 'min', 'features': feats, 'events': _events(traj, cfg), 'cnAtEnd': float(traj['cn'][-1]), 'cnPeak': float(traj['cn'].max()), 'evidence': evidence}
    run_id = uuid.uuid4().hex; created = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    record = {'schema': 'fold.research-record', 'schemaVersion': 1, 'id': run_id, 'kind': 'hela_erk.experiment',
              'experiment': {'label': cfg['label'], 'parent': cfg['parent'], 'config': cfg, 'context': CONTEXT, 'rerun': 'Send `config` to hela_erk_simulate. The run is deterministic for a given dataset and model version.'},
              'engine': {k_: ENGINE[k_] for k_ in ('id', 'name', 'version', 'numericalMethod')},
              'evidence': {'category': 'B', 'name': 'Mechanistic model fitted to measurements', 'statement': 'A model of the ERK reporter in HeLa cells, fitted to single cells of two dishes and tested on other dishes of the same experiment. This run is a prediction; it is not a measurement.'},
              'created': created, 'inputs': inputs, 'solver': solver, 'outputs': outputs, 'benchmark': {'checks': checks, 'passed': passed}, 'warnings': warnings,
              'validation': {'status': bench['status'], 'test': bench['summary']['test'], 'holdouts': bench['holdouts'], 'coverage': bench['intervalCoverage'].get('test')},
              'data': {'source': dataset()['source'], 'sha256': dataset()['sha256'], 'specimen': dataset()['specimen']}, 'specimens': {'liveCell': dataset()['specimen'], 'geometryReference': EM_REFERENCE},
              'assumptions': ENGINE['assumptions'], 'limitations': ENGINE['limits'], 'state': STATE, 'resolution': RESOLUTION}
    record['reproducibility'] = {'deterministic': True, 'seed': cfg['seed'], 'runtime': 'Python ' + platform.python_version() + ' · NumPy ' + np.__version__,
                                 'contentSha256': _sha({k_: record[k_] for k_ in ('inputs', 'solver', 'outputs')}), 'seriesSha256': _sha(series), 'note': 'Deterministic. Rerunning the saved configuration reproduces the series hash on the same NumPy and platform.'}
    root = getattr(service, 'root', None)
    if root and not (p or {}).get('dryRun'):
        d = pathlib.Path(root) / 'hela_erk' / 'runs'; d.mkdir(parents=True, exist_ok=True)
        (d / (run_id + '.json')).write_text(json.dumps(record, default=float))
    return {'id': run_id, 'time': t[idx].tolist(), 'series': series, 'evidence': evidence, 'measured': measured, 'model': 'mechanistic', 'modelName': MODELS['mechanistic'], 'record': record, 'hasState': True,
            'sha256': record['reproducibility']['contentSha256'], 'seriesSha256': record['reproducibility']['seriesSha256'], 'passed': passed, 'checks': checks, 'warnings': warnings}


def _load(service, rid):
    rid = str(rid or ''); f = pathlib.Path(service.root) / 'hela_erk' / 'runs' / (rid + '.json')
    if not re.fullmatch(r'[0-9a-f]{32}', rid) or not f.is_file():
        raise ErkError('That saved experiment no longer exists.')
    return json.loads(f.read_text())


def runs(service):
    d = pathlib.Path(service.root) / 'hela_erk' / 'runs'; out = []
    for f in sorted(d.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:60] if d.is_dir() else []:
        r = json.loads(f.read_text()); cfg = r['experiment']['config']
        out.append({'id': r['id'], 'created': r['created'], 'label': cfg.get('label') or '', 'parent': cfg.get('parent'), 'passed': r['benchmark'].get('passed'), 'model': r['solver']['model'], 'time': r['outputs']['time'],
                    'peak': r['outputs'].get('cnPeak'), 'sha256': r['reproducibility']['contentSha256'], 'series': cfg.get('series'), 'egfNgPerMl': cfg.get('egfNgPerMl'), 'mekInhibition': cfg.get('mekInhibition')})
    return out


def run_get(service, p):
    """A saved experiment, recomputed from its configuration, with a statement of whether it reproduces."""
    rec = _load(service, p.get('id')); again = simulate(service, {**rec['experiment']['config'], 'dryRun': True})
    same = again['seriesSha256'] == rec['reproducibility'].get('seriesSha256')
    return {**again, 'id': rec['id'], 'record': rec, 'sha256': rec['reproducibility']['contentSha256'],
            'reproduced': {'identical': bool(same), 'saved': rec['reproducibility'].get('seriesSha256'), 'now': again['seriesSha256'],
                           'statement': 'Recomputed from the saved configuration: every plotted value is identical to the saved run.' if same else
                                        'Recomputed from the saved configuration, but the values differ from the saved run. The dataset, model version or numerical library has changed since it was saved.',
                           'savedVersions': {'model': rec['solver'].get('modelVersion'), 'dataset': rec['solver'].get('datasetSha256')}, 'currentVersions': {'model': VERSION, 'dataset': dataset()['sha256']}}}


def compare(service, p):
    """Two saved experiments recomputed on their own time axes: what was changed, and what that did."""
    a, b = (run_get(service, {'id': p.get(k)}) for k in ('baseline', 'variant'))
    ca, cb = a['record']['experiment']['config'], b['record']['experiment']['config']
    keys = ('egfNgPerMl', 'egfAtMin', 'durationMin', 'mekInhibition', 'egfrInhibition', 'restingCn', 'series', 'samples', 'seed')
    changed = [{'what': k, 'baseline': ca.get(k), 'variant': cb.get(k), 'affectsDynamics': k not in ('samples', 'seed', 'series')} for k in keys if ca.get(k) != cb.get(k)]
    fa, fb = a['record']['outputs']['features'], b['record']['outputs']['features']
    label = {'amplitude': ('Peak rise of C/N', 'fraction'), 'timeToPeakMin': ('Time to peak', 'min'), 'halfRiseMin': ('Time to half rise', 'min'), 'erkPeak': ('Peak ERK activity', 'fraction')}
    outcomes = [{'key': k, 'label': label[k][0], 'unit': label[k][1], 'baseline': fa.get(k), 'variant': fb.get(k), 'change': (fb[k] - fa[k]) if fa.get(k) is not None and fb.get(k) is not None else None} for k in label]
    side = lambda r, cfg: {'id': r['id'], 'label': cfg['label'], 'time': r['time'], 'series': r['series'], 'events': r['record']['outputs']['events'], 'reproduced': r['reproduced']['identical']}
    return {'baseline': side(a, ca), 'variant': side(b, cb), 'changed': changed, 'outcomes': outcomes, 'identicalDynamics': not any(ch['affectsDynamics'] for ch in changed),
            'scales': {'cn': [min(min(a['series']['cn']), min(b['series']['cn'])), max(max(a['series'].get('cnHigh', a['series']['cn'])), max(b['series'].get('cnHigh', b['series']['cn'])))], 'fractions': [0.0, 1.0]},
            'note': 'Both sides are recomputed from their saved configurations with the current model, and share one scale per quantity.'}


def particles(service, p):
    """The reporter split of a run as particles in the electron-microscopy reference cell (nucleus and cytosol).
    Needs the EM dataset in the library; without it the reason is returned and the plots stand alone."""
    import cell_em
    fit, bench = fitted(service)
    cfg = _load(service, p['id'])['experiment']['config'] if p.get('id') else _configure(p, fit)
    try:
        cls, voxel, meta, sha = cell_em.geometry(service.root, GEOMETRY)
    except Exception as e:
        return {'available': False, 'reason': 'The 3-D reference cell is not installed in this library: open Cell Explorer › Workspace with the HeLa cell and download it. ' + str(e)[:160], 'context': GEOMETRY}
    traj, c, st = _trajectory(fit, cfg); k = cell_em.KEYS; at = cell_state.display_clock(len(traj['t']), DISPLAY['frames'])
    species = [{'key': 'nuclear', 'name': 'ERK reporter in the nucleus', 'compartment': 'nucleus', 'where': 'Nucleus', 'radiusNm': 3.0, 'evidence': 'inferred · assumed copies', 'classes': [k['nucleus'], k['chromatin'], k['nucleolus']], 'counts': traj['nuclear'] * DISPLAY['copies'], 'group': 'reporter'},
               {'key': 'cytoplasmic', 'name': 'ERK reporter in the cytoplasm', 'compartment': 'cytosol', 'where': 'Cytosol', 'radiusNm': 3.0, 'evidence': 'inferred · assumed copies', 'classes': [k['cytosol']], 'counts': traj['cytoplasmic'] * DISPLAY['copies'], 'group': 'reporter'}]
    try:
        d = cell_state.particles(np.asarray(cls), voxel, species, at, cfg['seed'], DISPLAY['copies'], p.get('weight'))
    except ValueError as e:
        raise ErkError(str(e))
    total = np.array(d['species'][0]['molecules']) + np.array(d['species'][1]['molecules'])
    conserved = cell_state.check('Molecule totals', float(np.max(np.abs(total - DISPLAY['copies']))) < 1e-9, 'nuclear + cytoplasmic molecules = total copies, in every frame', {'copies': DISPLAY['copies'], 'maxDeviation': float(np.max(np.abs(total - DISPLAY['copies'])))},
                                 'The reporter only moves between the two compartments.')
    n_ = np.array(d['species'][0]['molecules']); c_ = np.array(d['species'][1]['molecules'])
    readout = cell_state.same_series('One reporter split', c_ / (n_ * c['v']), traj['cn'][at], 'C/N recomputed from the molecule numbers drawn in 3-D equals the plotted C/N.', {'v': c['v']})
    checks = [conserved, readout] + d['checks']
    return {**d, 'available': True, 'context': GEOMETRY, 'liveContext': CONTEXT, 'geometrySha256': sha, 'sizeUm': meta['sizeUm'], 'time': traj['t'][at].tolist(), 'timeUnit': 'min', 'id': p.get('id'), 'model': 'mechanistic', 'checks': checks,
            'passed': all(ch['passed'] for ch in checks), 'readout': traj['cn'][at].tolist(), 'readoutUnit': 'C/N', 'copies': DISPLAY,
            'evidence': {'positions': 'Illustrative placement in a measured geometry: uniform draws inside the nucleus and the cytosol of the electron-microscopy HeLa cell, which is not one of the live cells.', 'numbers': 'Inferred fractions of an assumed number of reporter copies.'}}


def import_series(service, p):
    """Add a held-out condition (another dose, an inhibitor) as single-cell C/N trajectories, to be scored by the benchmark.
    Each cell needs frame times in minutes from the first frame and C/N. The onset time is inferred from the series, like every other."""
    sid = str(p.get('id') or ''); cells = p.get('cells') or []
    if not re.fullmatch(r'[A-Za-z0-9_.-]{3,64}', sid) or sid in dataset()['byId']:
        raise ErkError('Give the series a new name of 3 to 64 letters, digits, dots, dashes or underscores.')
    if not 5 <= len(cells) <= 5000:
        raise ErkError('A series needs between 5 and 5000 cells.')
    out = []
    for i, c in enumerate(cells):
        try:
            t = [float(x) for x in c['t']]; cn = [float(x) for x in c['cn']]
        except (KeyError, TypeError, ValueError):
            raise ErkError(f'Cell {i + 1} needs lists `t` and `cn` of numbers.')
        if len(t) != len(cn) or len(t) < 8 or len(t) != len(cells[0]['t']) or any(b <= a for a, b in zip(t, t[1:])) or min(cn) <= 0 or not all(map(math.isfinite, t + cn)):
            raise ErkError(f'Cell {i + 1}: times must increase, C/N must be positive, and every cell needs the same number of frames (at least 8).')
        out.append({'id': f'{sid}-c{i + 1:04d}', 't': t, 'cn': cn})
    cond = {'egf': _num(p, 'egfNgPerMl', 10.0, *LIMITS['egfNgPerMl'], 'EGF'), 'mek': _num(p, 'mekInhibition', 0.0, 0.0, 1.0, 'MEK inhibition'), 'egfr': _num(p, 'egfrInhibition', 0.0, 0.0, 1.0, 'EGFR inhibition')}
    evidence = p.get('evidence') if p.get('evidence') in ('measured', 'synthetic') else 'measured'
    body = {'id': sid, 'name': str(p.get('label') or sid)[:120], 'label': str(p.get('label') or sid)[:120], 'condition': cond, 'evidence': evidence, 'source': str(p.get('source') or '')[:300], 'cells': out, 'imported': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'sha256': _sha({'c': cond, 'cells': out})}
    d = pathlib.Path(service.root) / 'hela_erk' / 'imports'; d.mkdir(parents=True, exist_ok=True); (d / (sid + '.json')).write_text(json.dumps(body))
    fit, bench = fitted(service)
    return {'id': sid, 'cells': len(out), 'condition': cond, 'evidence': evidence, 'score': next(r for r in bench['schedules']['imported'] if r['id'] == sid), 'holdouts': bench['holdouts']}


def series(service, p):
    fit, _ = fitted(service); sid = p.get('id'); extra = imports(getattr(service, 'root', None))
    if sid not in dataset()['byId'] and sid not in extra:
        raise ErkError('Unknown series.')
    role = next((r for r, ids in SPLIT.items() if sid in ids), 'unexplained' if sid in dataset()['byId'] else 'imported')
    return {**score(fit, sid, extra, (extra.get(sid) or {}).get('condition')), 'supported': True, 'role': role}


def catalog(service):
    d = dataset(); fit, bench = fitted(service); role = {sid: r for r, ids in SPLIT.items() for sid in ids}; extra = imports(getattr(service, 'root', None))
    onsets = {r['id']: r['onset'] for rs in bench['schedules'].values() for r in rs}
    listed = [{'id': u, 'name': x['name'], 'dish': x['dish'], 'position': x['position'], 'role': role.get(u, 'unexplained'), 'cells': len(x['cells']), 'egfNgPerMl': 10.0, 'onset': onsets.get(u), 'evidence': 'measured'} for u, x in d['byId'].items() if len(x['cells']) >= 5]
    listed += [{'id': sid, 'name': s_.get('label') or sid, 'role': 'imported', 'cells': len(s_['cells']), 'egfNgPerMl': s_['condition']['egf'], 'condition': s_['condition'], 'onset': onsets.get(sid), 'evidence': s_.get('evidence', 'measured')} for sid, s_ in extra.items()]
    return {'engine': ENGINE, 'context': CONTEXT, 'geometry': EM_REFERENCE, 'dataset': {'sha256': d['sha256'], 'source': d['source'], 'specimen': d['specimen'], 'readout': d['readout'], 'rules': d['rules'],
                                                                                   'archives': [{'id': x['id'], 'usable': x.get('usable', False), 'reason': x.get('reason'), 'cells': len(x['cells']), 'dropped': x.get('dropped'), 'sha256': x['archiveSha256']} for x in d['series']]},
            'series': listed, 'split': SPLIT, 'roles': ROLE_NAME, 'models': MODELS, 'structure': fit['structure'], 'structures': STRUCTURES, 'selection': fit['selection'], 'summary': bench['summary'], 'holdouts': bench['holdouts'],
            'status': bench['status'], 'statement': bench['statement'], 'onsetNote': ONSET_NOTE, 'gate': bench['gate'], 'failures': bench['failures'], 'coverage': bench['intervalCoverage'], 'parameters': parameter_table(fit), 'limits': LIMITS, 'state': STATE,
            'resolution': RESOLUTION, 'display': DISPLAY, 'defaults': {'egfAtMin': PROTOCOL_T0, 'restingCn': resting_default(fit), 'egfNgPerMl': 10.0, 'durationMin': 60.0},
            'training': {'cells': fit['calibrationCells'], 'rmseRelative': fit['fit']['rmseRelative'], 'gain': fit['gain'], 'noise': fit['noise']}}


def dispatch(service, action, p):
    p = p or {}
    try:
        if action == 'hela_erk_catalog': return catalog(service)
        if action == 'hela_erk_benchmark': return fitted(service)[1]
        if action == 'hela_erk_series': return series(service, p)
        if action == 'hela_erk_simulate': return simulate(service, p)
        if action == 'hela_erk_runs': return runs(service)
        if action == 'hela_erk_run_get': return run_get(service, p)
        if action == 'hela_erk_compare': return compare(service, p)
        if action == 'hela_erk_particles': return particles(service, p)
        if action == 'hela_erk_import': return import_series(service, p)
    except ErkError as e:
        raise ValueError(str(e))
    raise ValueError('Unsupported HeLa ERK action.')
