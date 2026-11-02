"""Demo 5 (protein biogenesis) and Demo 8 (cross-laboratory chain) for human serum albumin.

Reference system: human ALB, mRNA NCBI RefSeq NM_000477.7 (CDS 42..1871), protein UniProt P02768
(609 aa; signal peptide 1–18, propeptide 19–24, mature 25–609). The CDS translation is checked
against UniProt on load. Albumin is a well-characterised, non-hazardous secreted plasma protein.

Stages (each an existing engine, called through a declared contract):
  rna          ViennaRNA ensemble of the 5' UTR + first 30 codons → start-codon accessibility
  translation  exact Gillespie TASEP (rna_lab_translate) → protein output per mRNA
  cell         SBML/SciPy engine (mechanistic_*) → hepatocyte ER pool and secretion
  body         linear whole-body turnover (SciPy) → synthesis, pool, plasma concentration
  capillary    axisymmetric advection–diffusion (blood_transport) → outlet concentration, wall loss
  binding      SBML/SciPy engine → free fraction of a hypothetical ligand bound by albumin

Literature values carry their source and the exact context in which they were measured.
Everything else is labelled hypothetical or an assumption, with the range explored.
The start-codon accessibility is reported but deliberately NOT coupled to the initiation rate:
no calibrated model maps it to an initiation rate for this transcript.
"""
import json, math, pathlib
import numpy as np
from scipy.integrate import solve_ivp
import multiscale_kernel as K
import multiscale_units as U

ROOT = pathlib.Path(__file__).resolve().parents[1]
REF = json.loads((ROOT / 'fixtures' / 'reference' / 'human_albumin.json').read_text())

LEVITT = {'citation': 'Levitt DG, Levitt MD (2016) Human serum albumin homeostasis. Int J Gen Med 9:229–255', 'doi': '10.2147/IJGM.S102819'}
INGOLIA = {'citation': 'Ingolia NT, Lareau LF, Weissman JS (2011) Ribosome profiling of mouse embryonic stem cells. Cell 147:789–802', 'doi': '10.1016/j.cell.2011.10.002'}
UNIPROT = {'citation': 'UniProtKB/Swiss-Prot P02768 (ALBU_HUMAN)', 'url': 'https://www.uniprot.org/uniprotkb/P02768'}
REFSEQ = {'citation': 'NCBI RefSeq NM_000477.7, Homo sapiens albumin mRNA', 'url': 'https://www.ncbi.nlm.nih.gov/nuccore/NM_000477.7'}

CODE = {}
for _i, _a in enumerate('FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG'):
    CODE['UCAG'[_i >> 4] + 'UCAG'[(_i >> 2) & 3] + 'UCAG'[_i & 3]] = _a


def reference_identity():
    """The mRNA CDS must translate exactly to the UniProt sequence; otherwise nothing runs."""
    m = REF['mrna']; cds = m['sequence'][m['cdsStart'] - 1:m['cdsEnd']].replace('T', 'U')
    protein = ''.join(CODE[cds[i:i + 3]] for i in range(0, len(cds), 3))
    ok = protein.endswith('*') and protein[:-1] == REF['protein']['sequence']
    if not ok:
        raise K.CouplingError('The reference mRNA does not translate to UniProt P02768.')
    return {'mrna': m['accession'], 'protein': REF['protein']['accession'], 'cdsCodons': len(cds) // 3, 'senseCodons': len(cds) // 3 - 1, 'translationMatchesUniProt': ok}


ALBUMIN = K.Entity('ALB-HUMAN', 'protein', 'Serum albumin (human)', {'uniprot': 'P02768', 'refseqMRNA': 'NM_000477.7', 'hgnc': 'HGNC:399'},
                   REF['mrna']['sha256'], 'Public databases (RefSeq, UniProt), retrieved ' + REF['retrieved'])
COMPARTMENTS = [K.Compartment('hepatocyte-er', 'Hepatocyte ER/secretory pathway', None, None, 'count', 'Copy numbers per cell; well mixed'),
                K.Compartment('body', 'Whole-body albumin pool', None, None, 'well-mixed', 'Single pool with a fixed intravascular fraction'),
                K.Compartment('plasma', 'Plasma', 2.85, 'L', 'well-mixed', 'Assumed plasma volume'),
                K.Compartment('sinusoid', 'Hepatic sinusoid (idealised straight capillary)', None, None, 'spatial', 'Axisymmetric rigid tube, Newtonian plasma')]


# ---- stage 1: RNA structure around the start codon -------------------------------------
def run_rna(inputs, p, seed, light=False):
    import rna_lab_fold as fold
    m = REF['mrna']; start = m['cdsStart'] - 1
    window = m['sequence'][:start + 90].replace('T', 'U')
    out = fold.analyse(window, 60 if light else 400, seed)
    aug = [out['unpaired'][start + k] for k in range(3)]
    return {'outputs': {'startCodonUnpaired': sum(aug) / 3},
            'data': {'window': window, 'startIndex': start, 'backend': out['backend'], 'backendVersion': out['backendVersion'], 'mfe': out['mfe'],
                     'ensembleFreeEnergy': out['ensembleFreeEnergy'], 'unpaired': out['unpaired'], 'augUnpaired': aug},
            'checks': [], 'events': []}


# ---- stage 2: translation -----------------------------------------------------------
def run_translation(inputs, p, seed, light=False):
    import rna_lab_translate as tr
    L = reference_identity()['senseCodons']; eps = p['elongationRate']
    t_end, burn = (1500.0, 300.0) if light else (6000.0, 600.0)
    sim = tr.simulate(L, int(p['footprint']), p['initiationRate'], [eps] * L, p['terminationRate'], t_end, seed=seed, burn_in=burn, grid=120)
    J, se = tr.steady_current(sim['finished'], burn, t_end)
    mf = tr.mean_field_current(p['initiationRate'], eps, int(p['footprint']))
    checks = [] if light else [K_check('Protein output vs extended-TASEP low-density mean field', abs(J - mf) <= max(4 * se, 0.05 * mf),
                                       f'J = {J:.4f} ± {se:.4f} /s, mean field {mf:.4f} /s', J, mf)]
    return {'outputs': {'proteinRatePerMRNA': J},
            'data': {'standardError': se, 'meanField': mf, 'grid': sim['grid'], 'produced': sim['produced'], 'meanRibosomes': sim['meanRibosomes'],
                     'collisions': sim['collisions'], 'occupancy': sim['occupancy'][::3], 'transitMean': (sum(sim['transits']) / len(sim['transits'])) if sim['transits'] else None},
            'checks': checks,
            'events': [{'kind': 'translation-termination', 'count': len(sim['finished']), 'window': [0, t_end], 'unit': 's', 'entity': ALBUMIN.id, 'compartment': 'hepatocyte-er'}]}


def K_check(name, passed, detail, value=None, reference=None):
    return {'check': name, 'passed': bool(passed), 'detail': detail, 'value': value, 'reference': reference}


# ---- stage 3: hepatocyte synthesis and secretion (SBML engine) ------------------------
def cell_network(rate_per_mrna_s, copies, half_min):
    k_syn = rate_per_mrna_s * 3600.0 * copies
    k_sec = math.log(2) / (half_min / 60.0)
    hyp = {'kind': 'hypothetical'}
    return {'id': 'albumin_hepatocyte', 'name': 'Albumin synthesis and secretion in one hepatocyte', 'time': 'hour', 'copyNumbers': True,
            'compartments': [{'id': 'er', 'name': 'ER and secretory pathway', 'size': 1.0}],
            'species': [{'id': 'Pool', 'name': 'Albumin in the secretory pathway', 'compartment': 'er', 'initial': 0.0, 'provenance': hyp},
                        {'id': 'Secreted', 'name': 'Cumulative secreted albumin', 'compartment': 'er', 'initial': 0.0, 'provenance': hyp}],
            'parameters': [{'id': 'k_syn', 'value': k_syn, 'unit': 'items_per_time', 'provenance': {'kind': 'derived', 'from': 'translation output × mRNA copies'}},
                           {'id': 'k_sec', 'value': k_sec, 'unit': 'per_time', 'provenance': hyp}],
            'components': [{'type': 'synthesis', 'id': 'translation_output', 'species': {'X': 'Pool'}, 'parameters': {'k': 'k_syn'}},
                           {'type': 'degradation', 'id': 'secretion', 'species': {'X': 'Pool'}, 'parameters': {'k': 'k_sec'}},
                           {'type': 'templated_synthesis', 'id': 'secreted_counter', 'species': {'T': 'Pool', 'X': 'Secreted'}, 'parameters': {'k': 'k_sec'}}]}, k_syn, k_sec


def run_cell(inputs, p, seed, light=False):
    import mechanistic_library as lib, mechanistic_sbml as sbml, mechanistic_sim as sim
    net, k_syn, k_sec = cell_network(inputs['proteinRatePerMRNA'], p['mrnaCopies'], p['secretionHalfTime'])
    model = sbml.Model(lib.compose(net), {'kind': 'composed', 'network': net['id']})
    T = 8.0
    r = sim.simulate(model, T, 41 if light else 161, 'LSODA', 1e-10, 1e-12, check=not light)
    t = np.asarray(r['time']); pool = np.asarray(r['series']['Pool']); sec = np.asarray(r['series']['Secreted'])
    exact = k_syn / k_sec * (1 - np.exp(-k_sec * t))
    err = float(np.max(np.abs(pool - exact)) / (k_syn / k_sec))
    balance = float(np.max(np.abs(pool + sec - k_syn * t)) / max(k_syn * T, 1e-300))
    checks = [] if light else [K_check('ER pool vs analytical solution', err < 1e-7, f'max error {err:.1e} of steady state', err, 1e-7),
                               K_check('Mass balance: synthesised = in pathway + secreted', balance < 1e-9, f'relative residual {balance:.1e}', balance, 1e-9)]
    return {'outputs': {'secretionRatePerCell': k_sec * float(pool[-1]), 'intracellularPool': float(pool[-1])},
            'data': {'time': r['time'], 'pool': r['series']['Pool'], 'secreted': r['series']['Secreted'], 'kSynPerHour': k_syn, 'kSecPerHour': k_sec,
                     'sbmlSha256': model.sha256, 'diagnostics': r['diagnostics']},
            'checks': checks,
            'events': [{'kind': 'protein-secretion', 'rate': k_sec * float(pool[-1]), 'unit': 'molecule/h', 'entity': ALBUMIN.id, 'compartment': 'hepatocyte-er'}]}


# ---- stage 4: whole-body albumin turnover --------------------------------------------
def run_body(inputs, p, seed, light=False):
    rate_cell = inputs['secretionRatePerCell']
    S, how = U.count_rate_to_mass_rate(rate_cell * p['hepatocytes'], 'molecule/h', p['molarMass'], 'g/day')
    k = math.log(2) / p['halfTime']
    P0 = 280.0
    days = np.linspace(0, 120, 25 if light else 121)
    sol = solve_ivp(lambda t, y: [S - k * y[0]], (0, 120), [P0], t_eval=days, rtol=1e-10, atol=1e-10)
    exact = S / k + (P0 - S / k) * np.exp(-k * days)
    err = float(np.max(np.abs(sol.y[0] - exact)) / max(P0, S / k))
    pool_ss = S / k
    plasma, _ = U.mass_to_concentration(p['intravascularFraction'] * pool_ss, 'g', p['plasmaVolume'], 'L', 'g/L')
    measured_pool = 10.5 * 17.3 / math.log(2)
    checks = [] if light else [
        K_check('Linear turnover ODE vs analytical solution', err < 1e-8, f'max relative error {err:.1e}', err, 1e-8),
        K_check('Literature self-consistency: 10.5 g/day × 17.3 d / ln 2 vs reported pool 280 g', abs(measured_pool - 280) / 280 < 0.1,
                f'{measured_pool:.0f} g implied vs 280 g reported ({(measured_pool - 280) / 280:+.1%}); both from Levitt & Levitt 2016', measured_pool, 280)]
    comparisons = [
        {'quantity': 'Whole-body albumin synthesis', 'model': S, 'reference': 10.5, 'unit': 'g/day', 'source': LEVITT, 'kind': 'measured (human, steady state)'},
        {'quantity': 'Steady-state body pool', 'model': pool_ss, 'reference': 280.0, 'unit': 'g', 'source': LEVITT, 'kind': 'reported total body albumin'},
        {'quantity': 'Plasma albumin', 'model': plasma, 'reference': 44.5, 'unit': 'g/L', 'source': LEVITT, 'kind': 'baseline value of a study cited in the review (4.45 g/dL)'}]
    return {'outputs': {'synthesisGPerDay': S, 'plasmaAlbumin': plasma},
            'data': {'days': days.tolist(), 'pool': sol.y[0].tolist(), 'steadyPool': pool_ss, 'conversion': how, 'comparisons': comparisons},
            'checks': checks, 'events': [{'kind': 'compartment-transfer', 'from': 'hepatocyte-er', 'to': 'plasma', 'rate': S, 'unit': 'g/day', 'entity': ALBUMIN.id}]}


# ---- stage 5: transport through a hepatic sinusoid ---------------------------------
def run_capillary(inputs, p, seed, light=False):
    import blood_transport as bt
    c = inputs['plasmaAlbuminMolar']
    L, Uv = p['length'], p['meanVelocity']
    duration = 3 * (L * 1e-6) / (Uv * 1e-3)
    q = {'radiusUm': p['radius'], 'lengthUm': L, 'meanVelocityMmPerS': Uv, 'diffusivityUm2PerS': p['diffusivity'], 'wallPermeabilityUmPerS': p['wallPermeability'],
         'durationS': duration, 'inletMode': 'step', 'inletAmplitude': c, 'plasmaViscosityMPaS': 1.2,
         'radialCells': 8 if light else 16, 'axialCells': 60 if light else 160}
    r = bt.solve(q, frames=4 if light else 12, samples=60 if light else 160)
    last = r['series'][-1] if isinstance(r.get('series'), list) else None
    if last is None:
        raise K.CouplingError('The transport solver returned no time series.')
    wall_frac = last['cumulativeWallMol'] / last['cumulativeInMol'] if last['cumulativeInMol'] else 0.0
    resid = abs(last['budgetResidualMol']) / max(last['cumulativeInMol'], 1e-300)
    checks = [] if light else [K_check('Transport mass budget closes', resid < 1e-9, f'relative residual {resid:.1e}', resid, 1e-9)]
    return {'outputs': {'outletConcentration': last['outletCupMolPerM3'], 'wallLossFraction': wall_frac},
            'data': {'inputs': q, 'series': r['series'][::max(1, len(r['series']) // 60)], 'stability': r.get('stability'), 'flow': r.get('flow'), 'field': {k: r['frames'][k] for k in ('rUm', 'zUm', 'peakMolPerM3', 'levels', 'note')} | {'last': r['frames']['items'][-1:]}, 'budget': r.get('budget')},
            'checks': checks, 'events': [{'kind': 'boundary-flux', 'surface': 'sinusoid wall', 'fraction': wall_frac, 'entity': ALBUMIN.id}]}


# ---- stage 6: albumin binding a hypothetical plasma ligand (SBML engine) --------------
def run_binding(inputs, p, seed, light=False):
    import mechanistic_library as lib, mechanistic_sbml as sbml, mechanistic_sim as sim
    A, Lt, Kd = inputs['albuminMolar'] * 1000.0, p['ligandTotal'] * 1000.0, p['kd'] * 1000.0  # nM
    kon = p['kon']; koff = Kd * kon
    hyp = {'kind': 'hypothetical'}
    net = {'id': 'albumin_ligand', 'name': 'Albumin binding a hypothetical ligand', 'time': 'second',
           'compartments': [{'id': 'plasma', 'name': 'Plasma sample', 'size': 1e-6}],
           'species': [{'id': 'Alb', 'compartment': 'plasma', 'initial': A, 'provenance': {'kind': 'coupled'}},
                       {'id': 'Lig', 'compartment': 'plasma', 'initial': Lt, 'provenance': hyp},
                       {'id': 'Complex', 'compartment': 'plasma', 'initial': 0.0, 'provenance': hyp}],
           'parameters': [{'id': 'kon', 'value': kon, 'unit': 'per_nM_per_time', 'provenance': hyp}, {'id': 'koff', 'value': koff, 'unit': 'per_time', 'provenance': {'kind': 'derived', 'from': 'Kd × kon'}}],
           'components': [{'type': 'binding', 'id': 'binding', 'species': {'A': 'Alb', 'B': 'Lig', 'AB': 'Complex'}, 'parameters': {'kon': 'kon', 'koff': 'koff'}}]}
    model = sbml.Model(lib.compose(net), {'kind': 'composed', 'network': net['id']})
    tau = 1.0 / (koff + kon * (A + Lt))
    r = sim.simulate(model, 20 * tau, 81 if light else 201, 'LSODA', 1e-10, 1e-12, check=False)
    free = r['series']['Lig'][-1]
    b = A + Lt + Kd
    exact_complex = (b - math.sqrt(b * b - 4 * A * Lt)) / 2
    exact_free = Lt - exact_complex
    err = abs(free - exact_free) / Lt
    checks = [] if light else [K_check('Kinetic equilibrium vs exact quadratic solution', err < 1e-6, f'free ligand error {err:.1e} of total', err, 1e-6)]
    return {'outputs': {'freeFraction': free / Lt},
            'data': {'time': r['time'], 'free': r['series']['Lig'], 'complex': r['series']['Complex'], 'albuminNM': A, 'kdNM': Kd, 'exactFreeFraction': exact_free / Lt},
            'checks': checks, 'events': [{'kind': 'binding-equilibrium', 'boundFraction': 1 - free / Lt, 'entity': ALBUMIN.id, 'compartment': 'plasma'}]}


# ---- assembly -------------------------------------------------------------------------
def stages(full=True):
    mm = REF['protein']['matureAverageMassDa']
    S = [
        K.Stage(K.Contract('rna', 'Start-codon region folding', 'RNA secondary-structure thermodynamics', ['Partition function Z = Σ exp(−ΔG(s)/RT) over secondary structures s', 'p_unpaired(i) from McCaskill base-pair probabilities'],
                           {}, {'startCodonUnpaired': 'fraction'}, '5′ UTR + 90 nt (131 nt)', 'equilibrium', ['37 °C, ViennaRNA Turner 2004 parameters', 'Isolated transcript region, no proteins'],
                           ['Not coupled to initiation: no calibrated model maps accessibility to an initiation rate for this transcript'], 'statistical', 'rna_lab_fold (ViennaRNA when bundled)'), run_rna, []),
        K.Stage(K.Contract('translation', 'Ribosome traffic on the ALB mRNA', 'Stochastic exclusion process (TASEP)', ['Gillespie simulation: initiation α, elongation ε per codon, termination β, ribosomes exclude ℓ codons', 'J = protein output rate after burn-in'],
                           {}, {'proteinRatePerMRNA': 'molecule/s'}, '609 codons', 'seconds–minutes', ['Uniform codon elongation rate', 'Constant mRNA, unlimited tRNAs and ribosomes'],
                           ['Elongation rate measured in mouse ES cells, applied to human hepatocyte mRNA', 'Initiation rate for ALB unknown'], 'hypothesis', 'rna_lab_translate'),
                run_translation, [K.Param('initiationRate', 0.05, '1/s', 'hypothetical', 'Translation initiation rate α (transcript-specific value unknown)', {}, (0.01, 0.2)),
                                  K.Param('elongationRate', 5.6, 'codon/s', 'literature', 'Mean elongation rate', {**INGOLIA, 'quote': '5.6 ± 0.5 codons/s (Fig. 3C)', 'context': 'Mouse embryonic stem cells, run-off ribosome profiling'}),
                                  K.Param('terminationRate', 5.6, '1/s', 'assumption', 'Termination rate β, set equal to elongation', {}, (2.0, 20.0)),
                                  K.Param('footprint', 10, '1', 'assumption', 'Ribosome footprint in codons (~30 nt)', {})]),
        K.Stage(K.Contract('cell', 'Hepatocyte synthesis and secretion', 'Compartmental ODE (SBML, SciPy LSODA)', ['dPool/dt = J·N_mRNA − k_sec·Pool', 'dSecreted/dt = k_sec·Pool'],
                           {'proteinRatePerMRNA': 'molecule/s'}, {'secretionRatePerCell': 'molecule/h', 'intracellularPool': 'molecule'}, 'one cell', 'hours',
                           ['Constant mRNA copy number', 'All synthesised albumin is secreted (no ER degradation)', 'Signal peptide and propeptide removal not separately modelled'],
                           ['mRNA copies per hepatocyte and secretion half-time are not measured here'], 'hypothesis', 'mechanistic_library + mechanistic_sim'),
                run_cell, [K.Param('mrnaCopies', 1000, 'molecule', 'hypothetical', 'ALB mRNA copies per hepatocyte', {}, (200, 50000)),
                           K.Param('secretionHalfTime', 30, 'min', 'hypothetical', 'Half-time from synthesis to secretion', {}, (10, 90))]),
    ]
    if not full:
        return S
    S += [
        K.Stage(K.Contract('body', 'Whole-body albumin turnover', 'Linear one-pool turnover', ['dP/dt = S − k·P, k = ln 2 / t½', 'S = secretion per cell × hepatocytes × M / N_A', 'C_plasma = f_iv · P_ss / V_p'],
                           {'secretionRatePerCell': 'molecule/h'}, {'synthesisGPerDay': 'g/day', 'plasmaAlbumin': 'g/L'}, 'whole body', 'days–months',
                           ['Single exchangeable pool with a fixed intravascular fraction', 'Starts from the reported 280 g pool'],
                           ['Not a physiologically based PK model; no renal or GI losses separately; hepatocyte number assumed'], 'hypothesis', 'SciPy solve_ivp'),
                run_body, [K.Param('hepatocytes', 2.0e11, 'cell', 'hypothetical', 'Hepatocytes in an adult liver', {}, (1.0e11, 3.0e11)),
                           K.Param('molarMass', mm, 'g/mol', 'derived', 'Mature albumin (25–609) average mass from sequence', UNIPROT),
                           K.Param('halfTime', 17.3, 'day', 'literature', 'Albumin half-time', {**LEVITT, 'quote': 'turnover time of about 25 days or a half-time of 17.3 days', 'context': 'Healthy adult humans'}),
                           K.Param('intravascularFraction', 0.40, 'fraction', 'literature', 'Fraction of body albumin in plasma', {**LEVITT, 'quote': 'About 40% of albumin is intravascular', 'context': 'Healthy adult humans'}),
                           K.Param('plasmaVolume', 2.85, 'L', 'assumption', 'Plasma volume (70 kg adult)', {}, (2.5, 3.5), False)]),
        K.Stage(K.Contract('capillary', 'Transport through a hepatic sinusoid', 'Axisymmetric advection–diffusion (finite volume)', ['∂c/∂t + u(r)∂c/∂z = D∇²c, Poiseuille u(r)', 'Wall flux −D∂c/∂r = P·c'],
                           {'plasmaAlbuminMolar': 'mol/m3'}, {'outletConcentration': 'mol/m3', 'wallLossFraction': 'fraction'}, 'one sinusoid (µm)', 'seconds',
                           ['Rigid straight tube, Newtonian plasma, no blood cells', 'Step inlet at the coupled plasma concentration'],
                           ['Sinusoid geometry, velocity and albumin wall permeability are assumed; real sinusoids are fenestrated'], 'physics', 'blood_transport'),
                run_capillary, [K.Param('radius', 5.0, 'um', 'assumption', 'Sinusoid radius', {}, (3.5, 7.5), False),
                                K.Param('length', 300.0, 'um', 'assumption', 'Sinusoid length', {}),
                                K.Param('meanVelocity', 0.3, 'mm/s', 'assumption', 'Mean plasma velocity', {}, (0.1, 1.0)),
                                K.Param('diffusivity', 61.0, 'um2/s', 'assumption', 'Albumin diffusivity in plasma', {}),
                                K.Param('wallPermeability', 0.001, 'um/s', 'hypothetical', 'Albumin wall permeability', {}, (1e-4, 1e-2))]),
        K.Stage(K.Contract('binding', 'Albumin binding a hypothetical ligand', 'Mass-action binding (SBML, SciPy LSODA)', ['Alb + L ⇌ Alb·L, d[Alb·L]/dt = kon[Alb][L] − koff[Alb·L]', 'Kd = koff/kon'],
                           {'albuminMolar': 'uM'}, {'freeFraction': 'fraction'}, 'plasma sample', 'seconds',
                           ['One binding site per albumin', 'Ligand identity, Kd and total concentration are hypothetical'],
                           ['Illustrates plasma protein binding; not a claim about any real compound'], 'hypothesis', 'mechanistic_library + mechanistic_sim'),
                run_binding, [K.Param('ligandTotal', 10.0, 'uM', 'hypothetical', 'Total ligand concentration', {}, (1.0, 100.0)),
                              K.Param('kd', 5.0, 'uM', 'hypothetical', 'Dissociation constant', {}, (0.1, 100.0)),
                              K.Param('kon', 1e-4, '1', 'hypothetical', 'Association rate constant (1/(nM·s))', {})]),
    ]
    return S


def links(full=True):
    out = [K.Link('translation.proteinRatePerMRNA', 'cell.proteinRatePerMRNA', None, 'Each mRNA copy translated at the simulated steady-state rate')]
    if full:
        mm = REF['protein']['matureAverageMassDa']
        out += [K.Link('cell.secretionRatePerCell', 'body.secretionRatePerCell', None, 'All hepatocytes behave like the modelled cell (no zonation)'),
                K.Link('body.plasmaAlbumin', 'capillary.plasmaAlbuminMolar', lambda v, p: U.molar_from_mass_concentration(v, 'g/L', mm, 'mol/m3'),
                       'Mass → molar concentration with the sequence-derived molar mass'),
                K.Link('capillary.outletConcentration', 'binding.albuminMolar', None, 'Outlet cup-mixing concentration taken as the binding-assay albumin level')]
    return out


DEMOS = {
    'demo5': {'title': 'Protein biogenesis · human serum albumin', 'question': 'Starting from the ALB mRNA, how fast does one hepatocyte make and secrete albumin, and which assumptions control it?',
              'full': False, 'outputs': ['translation.proteinRatePerMRNA', 'cell.secretionRatePerCell', 'cell.intracellularPool']},
    'demo8': {'title': 'Cross-laboratory chain · albumin from mRNA to plasma', 'question': 'Do translation, secretion, whole-body turnover, sinusoid transport and plasma binding connect consistently, and how far does the chain land from measured albumin values?',
              'full': True, 'outputs': ['cell.secretionRatePerCell', 'body.synthesisGPerDay', 'body.plasmaAlbumin', 'capillary.wallLossFraction', 'binding.freeFraction']},
}


def run(demo, overrides=None, seed=1, samples=0):
    spec = DEMOS[demo]
    identity = reference_identity()
    st, ln = stages(spec['full']), links(spec['full'])
    result = K.run_chain(st, ln, overrides, seed)
    checks = [{**c, 'stage': sid} for sid, r in result['results'].items() for c in r.get('checks', [])]
    traces = {o: K.trace(st, ln, result, o) for o in spec['outputs']}
    unc = K.uncertainty(st, ln, spec['outputs'], samples=samples, seed=seed + 100) if samples else None
    calibration = None
    if spec['full']:
        # What initiation rate would reproduce the measured 10.5 g/day, holding the other values fixed? (calibration, not validation)
        import rna_lab_translate as tr
        p = {s.contract.id + '.' + q.name: (overrides or {}).get(s.contract.id + '.' + q.name, q.value) for s in st for q in s.params}
        need_per_cell_h = 10.5 * 1e-3 / 86400 / (p['body.molarMass'] * 1e-3) * U.AVOGADRO * 3600 / p['body.hepatocytes']
        J_need = need_per_cell_h / 3600 / p['cell.mrnaCopies']
        eps, l = p['translation.elongationRate'], int(p['translation.footprint'])
        # Invert the mean-field current J = α(ε−α)/(ε+α(ℓ−1)) for α on the low-density branch;
        # no solution exists if the required output exceeds the maximal (exclusion-limited) current.
        j_max = tr.max_current(eps, l)
        b_ = J_need * (l - 1) - eps
        disc = b_ * b_ - 4 * J_need * eps
        roots = [(-b_ - math.sqrt(disc)) / 2, (-b_ + math.sqrt(disc)) / 2] if disc >= 0 else []
        alpha = min([r for r in roots if 0 < r <= tr.critical_alpha(eps, l)], default=None)
        J_sim = result['results']['translation']['outputs']['proteinRatePerMRNA']
        total_per_s = need_per_cell_h / 3600
        calibration = {'target': '10.5 g/day whole-body synthesis (Levitt & Levitt 2016)', 'requiredRatePerMRNA': J_need, 'maximalCurrent': j_max,
                       'impliedInitiationRate': alpha, 'feasibleAtCurrentCopies': J_need <= j_max,
                       'requiredCopiesAtSimulatedRate': total_per_s / J_sim if J_sim > 0 else None,
                       'minimumCopiesAtMaximalCurrent': total_per_s / j_max,
                       'note': ('Calibration under the other assumed values (hepatocyte number, elongation rate, footprint), using the simulated and mean-field '
                                'currents. It shows what the chain would require; it is not independent validation.')}
    return {'demo': demo, **spec, 'identity': identity, 'entity': K.asdict(ALBUMIN), 'compartments': [K.asdict(c) for c in COMPARTMENTS],
            'model': K.describe(st, ln), 'results': result['results'], 'transfers': result['transfers'], 'events': result['events'],
            'checks': checks, 'traces': traces, 'uncertainty': unc, 'calibration': calibration,
            'overrides': overrides or {}, 'seed': seed,
            'sources': {'albumin': LEVITT, 'elongation': INGOLIA, 'protein': UNIPROT, 'mrna': REFSEQ}}
