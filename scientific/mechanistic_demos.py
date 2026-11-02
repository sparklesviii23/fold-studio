"""Validation demonstrations for the Mechanistic Biology Lab.

A  Enzyme kinetics with competitive inhibition: solver checked against the
   closed-form integrated Michaelis–Menten solution (Lambert W), and the full
   mass-action mechanism checked against it where quasi-steady state holds.
B  Published signalling models from BioModels, executed unmodified: receptor
   signalling (Kholodenko 1999, EGFR) and a feedback cascade (Kholodenko 2000,
   MAPK oscillations). Checks: conserved moieties, agreement of independent
   integrators, and the published qualitative behaviour.
C  mRNA and protein turnover with literature half-lives: solver checked against
   the analytical solution of the linear two-stage model.

Rate constants marked 'hypothetical' are chosen to exercise the mathematics and
represent no particular enzyme or gene.
"""
import math, pathlib
import numpy as np
from scipy.special import lambertw
import mechanistic_library as lib
import mechanistic_sbml as sbml
import mechanistic_sim as sim

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / 'fixtures' / 'biomodels'
HYPOTHETICAL = {'kind': 'hypothetical', 'note': 'Chosen to exercise the mathematics; not a measured value.'}


def enzyme_network(mechanism='rate_law', inhibitor=2000.0):
    common = {'time': 'second', 'compartments': [{'id': 'cuvette', 'name': 'Reaction volume', 'size': 1e-6}]}
    species = [{'id': 'E', 'name': 'Enzyme', 'compartment': 'cuvette', 'initial': 1.0, 'provenance': HYPOTHETICAL},
               {'id': 'S', 'name': 'Substrate', 'compartment': 'cuvette', 'initial': 50000.0, 'provenance': HYPOTHETICAL},
               {'id': 'P', 'name': 'Product', 'compartment': 'cuvette', 'initial': 0.0, 'provenance': HYPOTHETICAL},
               {'id': 'I', 'name': 'Competitive inhibitor', 'compartment': 'cuvette', 'initial': float(inhibitor), 'provenance': HYPOTHETICAL}]
    if mechanism == 'rate_law':
        return {**common, 'id': 'enzyme_competitive_rate_law', 'name': 'Enzyme with competitive inhibitor (rate law)', 'species': species,
                'parameters': [{'id': 'kcat', 'value': 10.0, 'unit': 'per_time', 'provenance': HYPOTHETICAL},
                               {'id': 'Km', 'value': 10100.0, 'unit': 'nM', 'provenance': HYPOTHETICAL},
                               {'id': 'Ki', 'value': 1000.0, 'unit': 'nM', 'provenance': HYPOTHETICAL}],
                'components': [{'type': 'competitive_inhibition', 'id': 'catalysis', 'species': {'E': 'E', 'S': 'S', 'P': 'P', 'I': 'I'}, 'parameters': {'kcat': 'kcat', 'Km': 'Km', 'Ki': 'Ki'}}]}
    species = species + [{'id': 'ES', 'name': 'Enzyme–substrate complex', 'compartment': 'cuvette', 'initial': 0.0, 'provenance': HYPOTHETICAL},
                         {'id': 'EI', 'name': 'Enzyme–inhibitor complex', 'compartment': 'cuvette', 'initial': 0.0, 'provenance': HYPOTHETICAL}]
    return {**common, 'id': 'enzyme_competitive_mass_action', 'name': 'Enzyme with competitive inhibitor (mass action)', 'species': species,
            'parameters': [{'id': 'k1', 'value': 1e-3, 'unit': 'per_nM_per_time', 'provenance': HYPOTHETICAL},
                           {'id': 'k_1', 'value': 0.1, 'unit': 'per_time', 'provenance': HYPOTHETICAL},
                           {'id': 'kcat', 'value': 10.0, 'unit': 'per_time', 'provenance': HYPOTHETICAL},
                           {'id': 'kon_I', 'value': 1e-3, 'unit': 'per_nM_per_time', 'provenance': HYPOTHETICAL},
                           {'id': 'koff_I', 'value': 1.0, 'unit': 'per_time', 'provenance': HYPOTHETICAL}],
            'components': [{'type': 'mass_action_enzyme', 'id': 'catalysis', 'species': {'E': 'E', 'S': 'S', 'ES': 'ES', 'P': 'P'}, 'parameters': {'k1': 'k1', 'k_1': 'k_1', 'kcat': 'kcat'}},
                           {'type': 'binding', 'id': 'inhibition', 'species': {'A': 'E', 'B': 'I', 'AB': 'EI'}, 'parameters': {'kon': 'kon_I', 'koff': 'koff_I'}}]}


def integrated_mm(t, S0, Vmax, Km_app):
    """Closed-form substrate depletion: S = Km·W((S0/Km)·exp((S0 − Vmax·t)/Km)) (Schnell & Mendoza 1997, doi:10.1006/jtbi.1997.0425)."""
    arg = (S0 / Km_app) * np.exp((S0 - Vmax * np.asarray(t)) / Km_app)
    return Km_app * np.real(lambertw(arg))


def turnover_network():
    hl_m, hl_p = 9.0, 46.0  # hours, medians in mouse NIH3T3 fibroblasts (Schwanhäusser et al. 2011)
    source = {'kind': 'literature', 'reference': 'Schwanhäusser B et al. (2011) Global quantification of mammalian gene expression control. Nature 473:337–342', 'doi': '10.1038/nature10098',
              'context': 'Median half-life across genes, mouse NIH3T3 cells, standard culture', 'note': 'A population median, not the half-life of any particular gene.'}
    return {'id': 'mrna_protein_turnover', 'name': 'mRNA and protein synthesis and turnover', 'time': 'hour', 'copyNumbers': True,
            'compartments': [{'id': 'cell', 'name': 'Cell', 'size': 1.0}],
            'species': [{'id': 'mRNA', 'name': 'mRNA (copies per cell)', 'compartment': 'cell', 'initial': 0.0, 'provenance': HYPOTHETICAL},
                        {'id': 'Protein', 'name': 'Protein (copies per cell)', 'compartment': 'cell', 'initial': 0.0, 'provenance': HYPOTHETICAL}],
            'parameters': [{'id': 'k_tx', 'name': 'Transcription rate', 'value': 2.0, 'unit': 'items_per_time', 'provenance': HYPOTHETICAL},
                           {'id': 'k_tl', 'name': 'Translation rate per mRNA', 'value': 50.0, 'unit': 'per_time', 'provenance': HYPOTHETICAL},
                           {'id': 'd_m', 'name': 'mRNA decay rate', 'value': math.log(2) / hl_m, 'unit': 'per_time', 'provenance': {**source, 'derivation': 'ln 2 / 9 h'}},
                           {'id': 'd_p', 'name': 'Protein decay rate', 'value': math.log(2) / hl_p, 'unit': 'per_time', 'provenance': {**source, 'derivation': 'ln 2 / 46 h'}}],
            'components': [{'type': 'synthesis', 'id': 'transcription', 'species': {'X': 'mRNA'}, 'parameters': {'k': 'k_tx'}},
                           {'type': 'degradation', 'id': 'mRNA_decay', 'species': {'X': 'mRNA'}, 'parameters': {'k': 'd_m'}},
                           {'type': 'templated_synthesis', 'id': 'translation', 'species': {'T': 'mRNA', 'X': 'Protein'}, 'parameters': {'k': 'k_tl'}},
                           {'type': 'degradation', 'id': 'protein_decay', 'species': {'X': 'Protein'}, 'parameters': {'k': 'd_p'}}]}


def turnover_analytical(t, k_tx, k_tl, d_m, d_p):
    t = np.asarray(t, float)
    m = k_tx / d_m * (1 - np.exp(-d_m * t))
    p = k_tl * k_tx / d_m * ((1 - np.exp(-d_p * t)) / d_p - (np.exp(-d_m * t) - np.exp(-d_p * t)) / (d_p - d_m))
    return m, p


DEMOS = {
    'enzyme': {'title': 'Enzyme kinetics · competitive inhibition', 'mechanism': 'Enzyme catalysis', 'evidence': 'B · physics of an idealised model; parameters hypothetical',
               'question': 'How does a competitive inhibitor slow substrate turnover, and does the solver match the exact integrated rate law?',
               'tEnd': 7200, 'outputs': ['S', 'P'], 'sweep': {'name': 'init:I', 'min': 0, 'max': 10000, 'steps': 9}},
    'receptor': {'title': 'Receptor signalling · EGFR (Kholodenko 1999)', 'mechanism': 'Receptor signalling', 'evidence': 'Published model (BioModels, curated); parameters from the paper',
                 'question': 'How do EGF dose and adaptor availability shape short-term EGFR signalling?', 'biomodels': 'BIOMD0000000048',
                 'tEnd': 120, 'outputs': ['RP', 'PLCgP', 'RShP', 'RGS'], 'sweep': {'name': 'init:EGF', 'min': 1, 'max': 1000, 'steps': 9, 'log': True}},
    'cascade': {'title': 'MAPK cascade with negative feedback (Kholodenko 2000)', 'mechanism': 'Signalling feedback', 'evidence': 'Published model (BioModels, curated); parameters from the paper',
                'question': 'Does ultrasensitivity plus negative feedback produce sustained oscillations, and how does feedback strength change them?', 'biomodels': 'BIOMD0000000010',
                'tEnd': 9000, 'outputs': ['MAPK_PP', 'MKK_PP', 'MKKK_P'], 'sweep': {'name': 'J0.Ki', 'min': 2, 'max': 40, 'steps': 9, 'log': True}},
    'turnover': {'title': 'mRNA and protein turnover', 'mechanism': 'Gene expression', 'evidence': 'B · analytical model; half-lives literature medians, synthesis rates hypothetical',
                 'question': 'How quickly do mRNA and protein approach steady state, and which rates control the protein level?',
                 'tEnd': 400, 'outputs': ['mRNA', 'Protein'], 'sweep': {'name': 'd_p', 'min': 0.005, 'max': 0.2, 'steps': 9, 'log': True}},
}


def load(demo):
    if demo == 'enzyme':
        return sbml.Model(lib.compose(enzyme_network('rate_law')), {'kind': 'composed', 'network': 'enzyme_competitive_rate_law'})
    if demo == 'turnover':
        return sbml.Model(lib.compose(turnover_network()), {'kind': 'composed', 'network': 'mrna_protein_turnover'})
    if demo in ('receptor', 'cascade'):
        mid = DEMOS[demo]['biomodels']
        return sbml.Model((FIXTURES / (mid + '.xml')).read_text(), {'kind': 'biomodels', 'id': mid, 'bundled': True})
    raise sbml.SBMLError('Unknown demonstration: ' + str(demo))


def provenance(demo):
    """Per-parameter provenance for composed demonstrations (published models carry their own)."""
    net = enzyme_network('rate_law') if demo == 'enzyme' else turnover_network() if demo == 'turnover' else None
    if not net:
        return {}
    out = {p['id']: p['provenance'] for p in net['parameters']}
    out.update({'init:' + sp['id']: sp['provenance'] for sp in net['species']})
    return out


def _check(name, passed, detail, value=None, threshold=None):
    return {'check': name, 'passed': bool(passed), 'detail': detail, 'value': value, 'threshold': threshold}


def validate(demo):
    """Independent checks for a demonstration. Returns a list of pass/fail results with numbers."""
    checks = []
    if demo == 'enzyme':
        m = load('enzyme')
        for inhibitor in (0.0, 2000.0):
            r = sim.simulate(m, 7200, 241, 'LSODA', 1e-10, 1e-12, initial={'I': inhibitor}, check=False)
            km_app = 10100.0 * (1 + inhibitor / 1000.0)
            exact = integrated_mm(r['time'], 50000.0, 10.0 * 1.0, km_app)
            err = float(np.max(np.abs(np.asarray(r['series']['S']) - exact)) / 50000.0)
            checks.append(_check(f'Rate-law model vs exact Lambert-W solution, [I] = {inhibitor:g} nM', err < 1e-6, 'Maximum error relative to S₀', err, 1e-6))
        full = sbml.Model(lib.compose(enzyme_network('mass_action')))
        r = sim.simulate(full, 7200, 241, 'LSODA', 1e-10, 1e-14, check=False)
        exact = integrated_mm(r['time'], 50000.0, 10.0, 10100.0 * (1 + 2000.0 / 1000.0))
        err = float(np.max(np.abs(np.asarray(r['series']['S']) - exact)) / 50000.0)
        checks.append(_check('Full mass-action mechanism vs quasi-steady-state solution (E₀/(S₀+Km) = 1.7·10⁻⁵)', err < 0.01, 'Expected small: QSSA holds when enzyme ≪ substrate + Km', err, 0.01))
        cons = sim.conservation(full, np.array([np.asarray(r['series'][s['id']]) * 1e-6 for s in full.state]))
        checks.append(_check('Total enzyme and substrate conserved', cons['maxRelativeDrift'] < 1e-6, f"{cons['laws']} conservation laws", cons['maxRelativeDrift'], 1e-6))
    elif demo == 'turnover':
        m = load('turnover')
        r = sim.simulate(m, 400, 401, 'LSODA', 1e-10, 1e-12, check=False)
        p = r['parameters']
        am, ap = turnover_analytical(r['time'], p['k_tx'], p['k_tl'], p['d_m'], p['d_p'])
        em = float(np.max(np.abs(np.asarray(r['series']['mRNA']) - am)) / (p['k_tx'] / p['d_m']))
        ep = float(np.max(np.abs(np.asarray(r['series']['Protein']) - ap)) / (p['k_tl'] * p['k_tx'] / (p['d_m'] * p['d_p'])))
        checks.append(_check('mRNA vs analytical solution', em < 1e-6, 'Maximum error relative to steady state', em, 1e-6))
        checks.append(_check('Protein vs analytical solution', ep < 1e-6, 'Maximum error relative to steady state', ep, 1e-6))
        ss = sim.steady_state(m)
        expected = p['k_tl'] * p['k_tx'] / (p['d_m'] * p['d_p'])
        rel = abs(ss['values']['Protein'] - expected) / expected
        checks.append(_check('Steady-state solver vs k_tl·k_tx/(d_m·d_p)', rel < 1e-6 and ss['stable'], 'Root-polished steady state and linear stability', rel, 1e-6))
        half = float(np.interp(0.5 * expected, ap, r['time']))
        checks.append(_check('Protein reaches half its steady state', True, f'{half:.0f} h, set mainly by the slower protein turnover (46 h half-life)', half, None))
    elif demo in ('receptor', 'cascade'):
        m = load(demo)
        t_end = DEMOS[demo]['tEnd']
        runs = {meth: sim.simulate(m, t_end, 400, meth, 1e-9, 1e-11, check=False) for meth in ('LSODA', 'BDF', 'Radau')}
        ref = runs['LSODA']
        scale = max(max(abs(v) for v in s) for s in ref['series'].values()) or 1.0
        diff = max(float(np.max(np.abs(np.asarray(runs[k]['series'][o]) - np.asarray(ref['series'][o])))) for k in ('BDF', 'Radau') for o in ref['series']) / scale
        checks.append(_check('Three independent integrators agree (LSODA, BDF, Radau)', diff < 1e-4, 'Maximum difference relative to the largest concentration', diff, 1e-4))
        r = sim.simulate(m, t_end, 400, 'LSODA', 1e-9, 1e-11, check=True)
        checks.append(_check('Conserved moieties hold', r['diagnostics']['conservation']['maxRelativeDrift'] < 1e-6, f"{r['diagnostics']['conservation']['laws']} conservation laws from the stoichiometry", r['diagnostics']['conservation']['maxRelativeDrift'], 1e-6))
        checks.append(_check('Executed without modifying the published equations', m.executable and not m.unsupported, 'SBML read and compiled as distributed by BioModels; SHA-256 ' + m.sha256[:12], None, None))
        if demo == 'cascade':
            long = sim.simulate(m, 20000, 2000, 'LSODA', 1e-9, 1e-11, check=False)
            x, t = np.asarray(long['series']['MAPK_PP']), np.asarray(long['time'])
            half = x[len(x) // 2:]; th = t[len(t) // 2:]
            peaks = [i for i in range(1, len(half) - 1) if half[i] > half[i - 1] and half[i] >= half[i + 1] and half[i] > half.mean()]
            amp = [half[i] for i in peaks]
            sustained = len(peaks) >= 3 and (max(amp) - min(amp)) / max(amp) < 0.02 and (half.max() - half.min()) > 0.2 * half.max()
            period = float(np.mean(np.diff(th[peaks]))) if len(peaks) > 1 else None
            checks.append(_check('Published behaviour: sustained oscillations of MAPK-PP', sustained, 'Peaks in the second half of a 20 000 s run keep a constant amplitude' + (f'; period ≈ {period / 60:.1f} min' if period else ''), period, None))
        else:
            rp = np.asarray(ref['series']['RP']); plc = np.asarray(ref['series']['PLCgP'])
            transient = plc.argmax() < len(plc) - 1 and plc[-1] < plc.max()
            checks.append(_check('Published behaviour: transient PLCγ phosphorylation', transient, f'PLCγ-P peaks at {ref["time"][int(plc.argmax())]:.0f} s then declines; receptor phosphorylation reaches {rp.max():.2f} nM', None, None))
    else:
        raise sbml.SBMLError('Unknown demonstration: ' + str(demo))
    return checks
