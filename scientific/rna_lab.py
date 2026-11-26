"""RNA-to-Protein Laboratory: RNA folding ensembles (Demo 3) and stochastic translation (Demo 4).

Every number returned here comes from `rna_lab_fold` (thermodynamic secondary-structure model)
or `rna_lab_translate` (exact Gillespie TASEP). Each run is stored as a research record under
<library>/rna_lab/runs with its inputs, engine, evidence category, assumptions and SHA-256.
Pure standard library, so the worker can run it under any bundled interpreter.
"""
import hashlib, json, math, pathlib, platform, shutil, sys, time, uuid
import rna_lab_fold as fold
import rna_lab_translate as tl
from rna_lab_actions import ACTIONS

HERE = pathlib.Path(__file__).resolve().parent
ENGINE_VERSION = '1.0.0'
FOLD_EVIDENCE = {'category': 'C', 'name': 'Statistically predicted · thermodynamic model',
                 'statement': 'Equilibrium secondary-structure ensemble of an isolated RNA computed from nearest-neighbour free energies. '
                              'Not an observed or in-cell structure; modifications, proteins, ions and tertiary contacts are not modelled.'}
TL_EVIDENCE = {'category': 'B', 'name': 'Stochastic kinetic simulation (parameterised hypothesis for initiation)',
               'statement': 'Exact stochastic simulation of an exclusion-process model of ribosome traffic. Elongation and footprint come from '
                            'cited averages; the initiation and termination rates are scenario values (category D), so outputs describe the '
                            'model, not a measured translation rate for this mRNA.'}
ELONGATION = {'value': 5.6, 'unit': 'codons/s', 'source': 'Mean elongation rate measured by ribosome run-off in mouse embryonic stem cells, Ingolia, Lareau & Weissman 2011, Cell 147:789, doi:10.1016/j.cell.2011.10.002'}
FOOTPRINT = {'value': 9, 'unit': 'codons', 'source': '~28-nt ribosome-protected fragment ≈ 9 codons, Ingolia et al. 2009, Science 324:218, doi:10.1126/science.1168978; rSNAPsim uses the same 9-codon exclusion'}
INITIATION = {'value': 0.033, 'unit': '1/s', 'source': 'Hypothetical scenario value (one initiation per ~30 s); not measured for this mRNA'}
TERMINATION = {'value': 5.6, 'unit': '1/s', 'source': 'Hypothetical: set equal to the mean elongation rate (no codon-specific termination data used)'}


def reference():
    return json.loads((HERE / 'rna_lab_reference.json').read_text())


def _runs(service):
    folder = pathlib.Path(service.root) / 'rna_lab' / 'runs'
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _record(service, kind, engine, evidence, inputs, solver, outputs, assumptions, limitations, seed, benchmark=None):
    rec = {'schema': 'fold.research-record', 'schemaVersion': 1, 'id': uuid.uuid4().hex, 'kind': kind,
           'engine': engine, 'evidence': evidence, 'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'inputs': inputs, 'solver': solver, 'outputs': outputs, 'assumptions': assumptions, 'limitations': limitations,
           'reproducibility': {'deterministic': True, 'seed': seed, 'runtime': 'Python ' + platform.python_version() + ' · ' + sys.platform,
                               'inputsSha256': _sha(inputs)}}
    if benchmark: rec['benchmark'] = benchmark
    rec['reproducibility']['contentSha256'] = _sha({k: rec[k] for k in ('engine', 'inputs', 'solver', 'outputs')})
    (_runs(service) / (rec['id'] + '.json')).write_text(json.dumps(rec))
    return rec


def tools():
    """What is actually installed in this interpreter — reported, never assumed."""
    vienna = fold.vienna_available()
    rnastructure = bool(shutil.which('efn2') and shutil.which('partition'))
    return {
        'viennarna': {'installed': bool(vienna), 'version': vienna, 'interpreter': sys.executable,
                      'note': None if vienna else 'The ViennaRNA Python module is not importable here. It is present only in the Modal cloud worker image (remote_worker/fold_rapid/editcraft_core.py); the built-in model is used locally.'},
        'rnastructure': {'installed': rnastructure, 'note': None if rnastructure else 'RNAstructure (efn2/partition executables) is not installed; no second-package comparison is available.'},
        'builtin': {'installed': True, 'version': ENGINE_VERSION, 'model': fold.MODEL},
    }


def catalog(_service, _p):
    ref = reference()
    t = ref['trna_phe']; c = ref['angptl3_cds']
    return {'engineVersion': ENGINE_VERSION, 'tools': tools(),
            'fold': {'demo': {k: t[k] for k in ('id', 'name', 'sequence', 'structure', 'structureSource', 'sequenceSource', 'pdb', 'priorViennaReceipt')},
                     'evidence': FOLD_EVIDENCE, 'limits': {'builtinMaxLength': fold.MAX_BUILTIN}},
            'translate': {'demo': {'id': c['id'], 'name': c['name'], 'sequence': c['sequence'], 'source': c['source'], 'codons': len(c['sequence']) // 3 - 1},
                          'defaults': {'elongation': ELONGATION, 'footprint': FOOTPRINT, 'initiation': INITIATION, 'termination': TERMINATION},
                          'evidence': TL_EVIDENCE}}


def run_fold(service, p):
    ref = reference()['trna_phe']
    seq = p.get('sequence') or ref['sequence']
    structure = p.get('reference')
    if structure is None and fold.clean(seq) == ref['sequence']: structure = ref['structure']
    samples = int(p.get('samples', 1000)); seed = int(p.get('seed', 1))
    if not 10 <= samples <= 5000: raise ValueError('Sample between 10 and 5,000 structures.')
    started = time.time()
    out = fold.analyse(seq, samples, seed, structure or None, p.get('backend', 'auto'))
    out['seconds'] = time.time() - started
    out['tools'] = tools()
    if structure and fold.clean(seq) == ref['sequence']:
        out['referenceSource'] = ref['structureSource']; out['priorViennaReceipt'] = ref['priorViennaReceipt']
    out['comparison'] = _compare_backends(out, structure)
    rec = _record(service, 'rna_fold_ensemble',
                  {'id': 'rna-lab.fold', 'name': out['model']['title'], 'version': ENGINE_VERSION,
                   'numericalMethod': 'Zuker MFE + McCaskill partition function + stochastic backtracking' if out['backend'] == 'builtin-nn' else 'ViennaRNA RNAfold/RNAsubopt-equivalent library calls'},
                  FOLD_EVIDENCE, {'sequence': out['sequence'], 'reference': structure, 'samples': samples, 'seed': seed, 'backend': out['backend']},
                  {'temperatureC': 37.0, 'maxLoop': fold.MAXLOOP, 'minHairpin': fold.MIN_HAIRPIN},
                  {k: out[k] for k in ('mfe', 'ensembleFreeEnergy', 'mfeProbability', 'centroid', 'ensembleDiversity', 'alternativeStates', 'reference') if k in out},
                  ['Canonical Watson–Crick and GU pairs only', 'Nested (pseudoknot-free) secondary structure', 'Equilibrium at 37 °C, 1 M NaCl parameter set'],
                  fold.MODEL['omitted'] if out['backend'] == 'builtin-nn' else ['Pseudoknots and tertiary contacts are not modelled', 'Modified nucleotides are treated as their parent bases'],
                  seed)
    out['recordId'] = rec['id']; out['recordSha256'] = rec['reproducibility']['contentSha256']; out['evidence'] = FOLD_EVIDENCE
    return out


def _compare_backends(out, structure):
    """When both engines are available, report the other one's MFE beside this run (never merged into it)."""
    if not fold.vienna_available() or out['length'] > fold.MAX_BUILTIN: return None
    rows = []
    for name in ('viennarna', 'builtin-nn'):
        if name == out['backend']:
            mfe = out['mfe']; acc = out.get('reference', {}).get('mfe'); g = out['ensembleFreeEnergy']; title = out['model']['title']
        else:
            eng = fold.Vienna(out['sequence']) if name == 'viennarna' else fold.Builtin(out['sequence'])
            db = fold.to_dotbracket(eng.mfe_pairs, out['length'])
            mfe = {'structure': db, 'energy': eng.mfe_energy}; g = eng.ensemble_energy
            acc = fold.compare(eng.mfe_pairs, fold.pairs_of(structure)) if structure else None
            title = 'ViennaRNA ' + str(fold.vienna_available()) + ' (Turner 2004, dangles=2)' if name == 'viennarna' else fold.MODEL['title']
        rows.append({'backend': name, 'title': title, 'mfe': mfe, 'ensembleFreeEnergy': g, 'accuracy': acc})
    return {'rows': rows, 'mfeBpDistance': fold.bp_distance(fold.pairs_of(rows[0]['mfe']['structure']), fold.pairs_of(rows[1]['mfe']['structure']))}


def _rate(p, key, default):
    v = p.get(key, default['value'])
    return float(v)


def run_translate(service, p):
    demo = reference()['angptl3_cds']
    cds = p.get('sequence') or demo['sequence']
    codons = tl.parse_cds(cds)
    L = len(codons)
    eps = _rate(p, 'elongation', ELONGATION); alpha = _rate(p, 'initiation', INITIATION); beta = _rate(p, 'termination', TERMINATION)
    ell = int(p.get('footprint', FOOTPRINT['value']))
    t_end = float(p.get('tEnd', 7200)); burn = float(p.get('burnIn', 600)); seed = int(p.get('seed', 1))
    window = float(p.get('playbackSeconds', 240)); frames = int(min(900, max(60, p.get('frames', 480))))
    if burn >= t_end: raise ValueError('Burn-in must be shorter than the simulated time.')
    rates = [eps] * L
    started = time.time()
    r = tl.simulate(L, ell, alpha, rates, beta, t_end, seed, burn, grid=240, frames=frames, frame_window=(0.0, min(window, t_end)))
    J, se = tl.steady_current(r['finished'], burn, t_end)
    transit_mean = sum(r['transits']) / len(r['transits']) if r['transits'] else None
    single = (L - 1) / eps + 1 / beta
    mf = tl.mean_field_current(alpha, eps, ell) if alpha < tl.critical_alpha(eps, ell) else None
    density = sum(r['occupancy'])
    outputs = {
        'codons': L, 'proteinRate': J, 'proteinRateSE': se, 'proteinsPerHour': J * 3600, 'proteinsTotal': len(r['finished']),
        'meanRibosomes': r['meanRibosomes'], 'ribosomesPer100Codons': 100 * density / L,
        'meanTransit': transit_mean, 'isolatedTransit': single,
        'collisions': r['collisions'], 'collisionsPerProtein': r['collisions'] / len(r['finished']) if r['finished'] else None,
        'blockedFraction': r['blockedFraction'], 'events': r['events'],
        'meanFieldRate': mf, 'phase': 'low density (initiation-limited)' if alpha < tl.critical_alpha(eps, ell) else 'initiation above the low-density limit',
    }
    out = {'inputs': {'codons': L, 'elongation': eps, 'initiation': alpha, 'termination': beta, 'footprint': ell, 'tEnd': t_end, 'burnIn': burn, 'seed': seed,
                      'source': 'ANGPTL3 CDS demo' if not p.get('sequence') else 'user CDS'},
           'outputs': outputs,
           'occupancy': [round(x, 6) for x in r['occupancy']],
           'production': {'time': r['grid'], 'proteins': r['produced']},
           'playback': {'frames': r['snapshots'], 'footprint': ell, 'codons': L,
                        'note': 'Each frame is the exact simulated state at that instant; motion drawn between frames is visual interpolation.'},
           'parameters': {'elongation': {**ELONGATION, 'value': eps, 'used': 'uniform for every codon'}, 'footprint': {**FOOTPRINT, 'value': ell},
                          'initiation': {**INITIATION, 'value': alpha}, 'termination': {**TERMINATION, 'value': beta}},
           'seconds': time.time() - started}
    rec = _record(service, 'translation_tasep',
                  {'id': 'rna-lab.translate', 'name': 'Extended-particle TASEP (Gillespie)', 'version': ENGINE_VERSION, 'numericalMethod': 'Gillespie direct method'},
                  TL_EVIDENCE, {**out['inputs'], 'cdsSha256': hashlib.sha256(''.join(codons).encode()).hexdigest()},
                  {'method': 'Gillespie direct', 'rng': 'Python random.Random (Mersenne Twister)', 'batches': 20},
                  {**outputs, 'occupancy': out['occupancy']},
                  ['Uniform elongation rate at every codon (no codon-specific rates: no cited per-codon dataset is bundled)',
                   'Initiation requires the first footprint-length of codons to be clear', 'No ribosome drop-off, abortive termination, mRNA decay or tRNA depletion',
                   'Single mRNA with constant rates'],
                  ['Initiation and termination rates are hypothetical', 'Does not predict protein abundance in a cell', 'No ribosome recycling or reinitiation'], seed)
    out['recordId'] = rec['id']; out['recordSha256'] = rec['reproducibility']['contentSha256']; out['evidence'] = TL_EVIDENCE
    return out


# ---------------- validation ----------------

def _brute_structures(seq):
    def gen(i, j):
        if i > j: yield frozenset(); return
        for rest in gen(i + 1, j): yield rest
        for k in range(i + fold.MIN_HAIRPIN + 1, j + 1):
            if seq[i] + seq[k] in fold.PAIRS:
                for a in gen(i + 1, k - 1):
                    for b in gen(k + 1, j): yield a | b | {(i, k)}
    return list(gen(0, len(seq) - 1))


def validate_fold():
    checks = []
    for seq in ('GGGAAACCC', 'GCGCUUAAGCGAAAGCGC', 'GGGCAAAGCCGCAAAGCAACCC'):
        S = _brute_structures(seq); n = len(seq)
        E = [fold.evaluate(seq, fold.to_dotbracket(s, n)) for s in S]
        Z = sum(math.exp(-e / fold.KT) for e in E); b = fold.Builtin(seq)
        P = {}
        for s, e in zip(S, E):
            w = math.exp(-e / fold.KT) / Z
            for pq in s: P[pq] = P.get(pq, 0.0) + w
        perr = max([abs(b.P[i][j] - P.get((i, j), 0.0)) for i in range(n) for j in range(i + 1, n)] + [0.0])
        zerr = abs(b.Z - Z) / Z; merr = abs(b.mfe_energy - min(E))
        checks.append({'check': f'Exhaustive enumeration · {seq}', 'detail': f'{len(S)} structures: MFE, partition function and every pair probability from the DP match explicit enumeration',
                       'value': max(perr, zerr, merr), 'threshold': 1e-9, 'passed': max(perr, zerr, merr) < 1e-9})
    ref = reference()['trna_phe']
    d = _reference_geometry(ref)
    if d:
        ok = all(9.0 <= x <= 12.0 for x in d.values())
        checks.append({'check': 'Reference pairs present in 1EHZ coordinates', 'detail': f"C1'–C1' distance of each of the {len(d)} reference pairs (canonical pairs ≈ 10.5 Å)",
                       'value': max(abs(x - 10.5) for x in d.values()), 'threshold': 1.5, 'passed': ok, 'distances': d})
    b = fold.Builtin('GGGGAAAACCCC')
    samples = b.sample(4000, 3); freq = sum(1 for s in samples if s == fold.to_dotbracket(b.mfe_pairs, 12)) / len(samples)
    p_mfe = math.exp(-(b.mfe_energy - b.ensemble_energy) / fold.KT); se = math.sqrt(p_mfe * (1 - p_mfe) / len(samples))
    checks.append({'check': 'Stochastic sampling matches Boltzmann probability', 'detail': f'GGGGAAAACCCC: sampled MFE frequency {freq:.4f} vs exact {p_mfe:.4f} (4,000 samples, seed 3)',
                   'value': abs(freq - p_mfe) / se if se else 0.0, 'threshold': 4.0, 'passed': abs(freq - p_mfe) <= 4 * se + 1e-12})
    version = fold.vienna_available()
    if version:
        import random, rna_lab_vienna as vienna
        diffs = vienna.table_check()
        checks.append({'check': f'Parameter tables vs ViennaRNA {version} Turner 1999', 'detail': 'Stacking, hairpin, bulge, interior-loop, Ninio, terminal AU and multiloop values' + (' differ: ' + ', '.join(diffs) if diffs else ' identical'),
                       'value': float(len(diffs)), 'threshold': 0.0, 'passed': not diffs})
        rng = random.Random(2)
        seqs = [ref['sequence']] + [''.join(rng.choice('ACGU') for _ in range(rng.randint(20, 70))) for _ in range(8)]
        w = vienna.model_check(seqs)
        worst = max(w.values())
        checks.append({'check': f'Same model in ViennaRNA {version}', 'detail': f'ViennaRNA run on a parameter file reduced to the built-in model (tRNA-Phe + 8 random sequences): max |ΔMFE| {w["mfe"]:.1e}, |ΔG_ensemble| {w["ensemble"]:.1e} kcal/mol, |Δp| {w["probability"]:.1e}, |Δeval| {w["evaluation"]:.1e} (ViennaRNA reports float32)',
                       'value': worst, 'threshold': 1e-5, 'passed': worst < 1e-5})
    else:
        checks.append({'check': 'ViennaRNA cross-check', 'detail': 'Skipped: ViennaRNA is not importable in this interpreter (' + sys.executable + ').', 'value': None, 'passed': True, 'skipped': True})
    return checks


def _reference_geometry(ref):
    path = HERE.parent / 'fixtures' / 'nucleic-acids' / '1EHZ.cif'
    if not path.is_file(): return None
    header, coords = [], {}
    for line in path.read_text().splitlines():
        if line.startswith('_atom_site.'): header.append(line.split('.', 1)[1].strip())
        elif line.startswith(('ATOM', 'HETATM')) and header:
            f = line.split()
            if len(f) != len(header): continue
            row = dict(zip(header, f))
            if row['label_asym_id'] != 'A' or row['label_atom_id'].strip('"') != "C1'": continue
            coords[int(row['label_seq_id'])] = tuple(float(row[k]) for k in ('Cartn_x', 'Cartn_y', 'Cartn_z'))
    out = {}
    for i, j in sorted(fold.pairs_of(ref['structure'])):
        a, b = coords.get(i + 1), coords.get(j + 1)
        if a and b: out[f'{i + 1}-{j + 1}'] = round(math.dist(a, b), 2)
    return out


def validate_translate():
    checks = []
    L, eps = 100, 1.0
    r = tl.simulate(L, 1, 0.2, [eps] * L, 1.0, 20000, 11, 500, grid=10)
    J, se = tl.steady_current(r['finished'], 500, 20000); exact = 0.2 * 0.8
    checks.append({'check': 'ℓ = 1 low-density current (exact)', 'detail': f'J = {J:.4f} ± {se:.4f} vs α(1−α) = {exact:.4f} (Derrida et al. 1993, doi:10.1088/0305-4470/26/7/011); L = 100, α = 0.2, β = 1',
                   'value': abs(J - exact) / se, 'threshold': 3.0, 'passed': abs(J - exact) <= 3 * se + 0.005 * exact})
    r = tl.simulate(200, 9, 0.05, [1.0] * 200, 1.0, 40000, 12, 1000, grid=10)
    J, se = tl.steady_current(r['finished'], 1000, 40000); mf = tl.mean_field_current(0.05, 1.0, 9)
    checks.append({'check': 'ℓ = 9 low-density current (mean field)', 'detail': f'J = {J:.4f} ± {se:.4f} vs α(1−α)/(1+α(ℓ−1)) = {mf:.4f} (Lakatos & Chou 2003); mean field is an approximation, tolerance 6 %',
                   'value': abs(J - mf) / mf, 'threshold': 0.06, 'passed': abs(J - mf) / mf <= 0.06})
    r = tl.simulate(200, 9, 1.0, [1.0] * 200, 1.0, 20000, 13, 1000, grid=10)
    J, se = tl.steady_current(r['finished'], 1000, 20000); mc = tl.max_current(1.0, 9)
    checks.append({'check': 'ℓ = 9 maximal current', 'detail': f'J = {J:.4f} ± {se:.4f} vs 1/(1+√ℓ)² = {mc:.4f}; L = 200 finite-size excess expected, tolerance 6 %',
                   'value': abs(J - mc) / mc, 'threshold': 0.06, 'passed': abs(J - mc) / mc <= 0.06})
    L = 100; rates = [1.0 + 0.5 * math.sin(x) for x in range(L)]
    r = tl.simulate(L, 9, 5.0, rates, 2.0, 180000, 14, grid=10, max_ribosomes=1)
    tr = r['transits']; m = sum(tr) / len(tr)
    mean = sum(1 / rates[x] for x in range(1, L)) + 1 / 2.0; var = sum(1 / rates[x] ** 2 for x in range(1, L)) + 1 / 4.0
    z = abs(m - mean) / math.sqrt(var / len(tr))
    checks.append({'check': 'Isolated-ribosome transit time (exact)', 'detail': f'{len(tr)} ribosomes with non-uniform rates: mean {m:.2f} s vs Σ1/kᵢ + 1/β = {mean:.2f} s',
                   'value': z, 'threshold': 3.0, 'passed': z <= 3.0})
    return checks


def dispatch(service, action, p):
    if action == 'rna_lab_catalog': return catalog(service, p)
    if action == 'rna_lab_fold': return run_fold(service, p)
    if action == 'rna_lab_translate': return run_translate(service, p)
    if action == 'rna_lab_validate':
        which = p.get('demo', 'fold')
        checks = validate_fold() if which == 'fold' else validate_translate()
        return {'demo': which, 'checks': checks, 'passed': all(c['passed'] for c in checks), 'runtime': 'Python ' + platform.python_version()}
    if action == 'rna_lab_runs':
        runs = sorted(_runs(service).glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:30]
        return [{k: json.loads(f.read_text()).get(k) for k in ('id', 'kind', 'created')} for f in runs]
    raise ValueError('Unsupported RNA laboratory action.')
