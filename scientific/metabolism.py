"""Demo F · tumor metabolic modelling with COBRApy on Human-GEM (Robinson JL et al., Sci Signal 2020; CC BY 4.0).

    python metabolism.py <model.json> <genes.tsv> <out.json> [depmap_gene_effect.npy depmap_gene_effect.json]

Constraint-based models give feasible steady-state fluxes, not measured reaction rates; a flux is not a concentration.
Evidence: Mechanistic simulation (stoichiometric constraint model; parameters are bounds, not kinetics).
Checks: (1) E. coli core textbook optimum 0.8739 h⁻¹ (Orth 2010); (2) no ATP without nutrients (energy-generating cycles);
(3) ATP per glucose aerobic ≈ 30–33 and anaerobic = 2 (textbook stoichiometry); (4) predicted essential genes vs DepMap CRISPR.
"""
import json
import sys
import time

import numpy as np

# Ham's F-12 components (the medium used for Human-GEM metabolic tasks), matched to exchange metabolites by name.
HAMS = ['glucose', 'O2', 'H2O', 'Pi', 'H+', 'sulfate', 'Na+', 'K+', 'Ca2+', 'Cl-', 'Fe2+', 'Fe3+', 'HCO3-', 'NH3',
        'arginine', 'histidine', 'lysine', 'methionine', 'phenylalanine', 'tryptophan', 'tyrosine', 'alanine', 'glycine', 'serine',
        'threonine', 'aspartate', 'glutamate', 'asparagine', 'glutamine', 'isoleucine', 'leucine', 'proline', 'valine', 'cysteine',
        'thiamin', 'hypoxanthine', 'folate', 'biotin', 'pantothenate', 'choline', 'inositol', 'nicotinamide', 'pyridoxine', 'riboflavin',
        'thymidine', 'aquacob(III)alamin', 'lipoic acid', 'linoleate', 'linolenate', 'putrescine', 'pyruvate']
# Fat-soluble vitamins absent from Ham's F-12 but supplied by serum in culture; Human-GEM's biomass cofactor pool needs them
# (without them biomass is 0 — found by testing each biomass precursor). Added explicitly and reported.
SERUM = ['retinol', 'alpha-tocopherol', 'gamma-tocopherol']
INORGANIC = {'O2', 'H2O', 'Pi', 'H+', 'sulfate', 'Na+', 'K+', 'Ca2+', 'Cl-', 'Fe2+', 'Fe3+', 'HCO3-', 'NH3'}
ATPM = 'MAR03964'          # cytosolic ATP phosphohydrolase (maintenance)
BIOMASS = 'MAR13082'
EX = {'glucose': 'MAR09034', 'O2': 'MAR09048', 'L-lactate': 'MAR09135'}
CENTRAL = {'Glycolysis / Gluconeogenesis': 'glycolysis', 'Tricarboxylic acid cycle and glyoxylate/dicarboxylate metabolism': 'TCA cycle',
           'Pentose phosphate pathway': 'pentose phosphate', 'Oxidative phosphorylation': 'oxidative phosphorylation', 'Pyruvate metabolism': 'pyruvate metabolism',
           'Glutamate metabolism': 'glutaminolysis'}   # Human-GEM subsystems


def exchange_by_name(m):
    out = {}
    for r in m.exchanges:
        for met in r.metabolites:
            out.setdefault(met.name, r)
    return out


def set_medium(m, names, glucose=1.0, oxygen=1000.0, organic=0.1):
    """Close every uptake, then open the named components: inorganic ones unlimited, organic ones capped (relative units,
    glucose = 1), so growth responds to the carbon and oxygen supply rather than to unlimited amino acids. Secretion stays open."""
    ex = exchange_by_name(m); used = []
    for r in m.exchanges:
        r.lower_bound = 0.0
    for n in names:
        if n in ex:
            ex[n].lower_bound = -(1000.0 if n in INORGANIC else organic); used.append(n)
    if 'glucose' in ex:
        ex['glucose'].lower_bound = -glucose
    if 'O2' in ex:
        ex['O2'].lower_bound = -oxygen
    return used


def main(model_path, genes_tsv, out, dep_npy=None, dep_json=None):
    import warnings; warnings.filterwarnings('ignore')
    import cobra
    from cobra.flux_analysis import flux_variability_analysis, pfba, single_gene_deletion
    t0 = time.time(); log = lambda s: print(f'[{time.time() - t0:6.1f}s] {s}', flush=True)
    res = {'software': {'cobra': cobra.__version__, 'solver': None}}
    # ---- (1) solver benchmark on the textbook E. coli core model
    ec = cobra.io.load_model('textbook'); res['benchmark'] = {'model': 'E. coli core (Orth 2010)', 'growth': ec.slim_optimize(), 'published': 0.8739, 'passed': abs(ec.slim_optimize() - 0.8739) < 1e-3}
    m = cobra.io.load_json_model(model_path); res['software']['solver'] = type(m.solver).__module__.split('.')[-2] if '.' in type(m.solver).__module__ else str(m.solver)
    res['model'] = {'name': 'Human-GEM', 'reactions': len(m.reactions), 'metabolites': len(m.metabolites), 'genes': len(m.genes)}
    # ---- (2) energy-generating-cycle check: no uptake at all → no ATP
    with m:
        for r in m.exchanges:
            r.lower_bound = 0.0
        m.objective = ATPM; res['noNutrientATP'] = {'atp': m.slim_optimize(error_value=0.0)}
    res['noNutrientATP']['passed'] = res['noNutrientATP']['atp'] < 1e-6
    # ---- (3) ATP per glucose with only glucose, O2, water, phosphate and protons available
    def atp_yield(o2, block=()):
        with m:
            set_medium(m, ['glucose', 'O2', 'H2O', 'Pi', 'H+'], glucose=1.0, oxygen=o2)
            for rid in block:
                m.reactions.get_by_id(rid).upper_bound = 0.0
            m.objective = ATPM; sol = m.optimize()
            secreted = {r.name.replace('Exchange of ', ''): round(float(sol.fluxes[r.id]), 4) for r in m.exchanges if sol.fluxes[r.id] > 1e-6}
            return sol.objective_value, -sol.fluxes[EX['O2']], sol.fluxes[EX['L-lactate']], secreted
    SUCC = 'MAR09415'
    aer, ana, ana_lac = atp_yield(1000.0), atp_yield(0.0), atp_yield(0.0, block=[SUCC])
    res['atpYield'] = {'aerobic': {'atp': aer[0], 'o2': aer[1], 'secreted': aer[3]}, 'anaerobic': {'atp': ana[0], 'secreted': ana[3]},
                       'anaerobicNoSuccinate': {'atp': ana_lac[0], 'secreted': ana_lac[3]},
                       'expected': 'aerobic ≈ 30–33 ATP/glucose (P/O-ratio dependent); anaerobic glycolysis exactly 2 ATP per glucose (textbook stoichiometry)',
                       'note': 'Without oxygen the unconstrained optimum secretes succinate (fumarate as electron acceptor, complex II in reverse — a route reported in ischaemic tissue, Chouchani ET et al., Nature 2014), giving > 2 ATP. Blocking succinate secretion recovers the textbook glycolytic yield of 2 ATP (here with pyruvate as the end product).'}
    res['atpYield']['passed'] = 29 <= aer[0] <= 34 and abs(ana_lac[0] - 2) < 1e-6
    log(f'ATP/glucose aerobic {aer[0]:.2f}, anaerobic {ana[0]:.2f}')
    # ---- (4) oxygen sweep: ATP yield and lactate secretion as O2 per glucose falls (the stoichiometric side of the Warburg question)
    sweep = []
    for o2 in [0, 0.5, 1, 2, 3, 4, 5, 6, 8, 10]:
        a, o, l, sec = atp_yield(float(o2)); sweep.append({'o2PerGlucose': o2, 'atp': a, 'lactate': l, 'succinate': sec.get('succinate', 0.0)})
    res['oxygenSweep'] = {'points': sweep, 'note': 'As oxygen falls this model secretes succinate, not lactate, and with ample oxygen it secretes neither: stoichiometry alone does not produce aerobic glycolysis (Warburg); that needs extra constraints (e.g. enzyme or proteome capacity) absent here.'}
    # ---- (5) Ham's medium: biomass, pFBA central fluxes, FVA ranges
    used = set_medium(m, HAMS + SERUM, glucose=1.0)
    m.objective = BIOMASS; growth = m.slim_optimize()
    res['medium'] = {'name': "Ham's F-12 + serum fat-soluble vitamins (retinol, α- and γ-tocopherol)", 'bounds': 'glucose ≤ 1, other organic components ≤ 0.1, inorganic ions, water and gases unlimited (relative units)',
                     'matched': used, 'missing': [n for n in HAMS + SERUM if n not in used]}
    res['growth'] = {'biomass': growth, 'units': 'relative growth under the stated bounds — not a predicted doubling time'}
    log(f'biomass {growth:.4f}')
    sub = lambda r: r.subsystem[0] if isinstance(r.subsystem, (list, tuple)) and r.subsystem else (r.subsystem or '')
    pf = pfba(m).fluxes
    central = [r for r in m.reactions if sub(r) in CENTRAL and abs(pf[r.id]) > 1e-6]
    fva = flux_variability_analysis(m, reaction_list=central, fraction_of_optimum=0.95)
    res['central'] = sorted([{'id': r.id, 'name': r.name, 'pathway': CENTRAL[sub(r)], 'equation': r.build_reaction_string(use_metabolite_names=True)[:90], 'compartment': ','.join(sorted(r.compartments)),
                              'pfba': float(pf[r.id]), 'min': float(fva.loc[r.id, 'minimum']), 'max': float(fva.loc[r.id, 'maximum'])} for r in central], key=lambda x: (x['pathway'], -abs(x['pfba'])))
    res['fvaNote'] = 'FVA at ≥ 95 % of optimal biomass: the range shows how undetermined each flux is; pFBA picks the minimal-total-flux solution among optima. Ranges reaching ±1000 come from reversible internal loops (no loopless constraint applied).'
    # ---- (6) growth sensitivity to glucose and oxygen availability
    grid = []
    for g in (0.25, 0.5, 1, 2, 4):
        row = []
        for o in (0, 0.5, 1, 2, 5, 1000):
            with m:
                set_medium(m, HAMS + SERUM, glucose=g, oxygen=o); m.objective = BIOMASS; row.append(m.slim_optimize(error_value=0.0))
        grid.append(row)
    res['sensitivity'] = {'glucose': [0.25, 0.5, 1, 2, 4], 'oxygen': [0, 0.5, 1, 2, 5, 'unlimited'], 'growth': grid}
    # ---- (7) single-gene deletion essentiality vs DepMap
    import csv
    sym = {}
    with open(genes_tsv) as f:
        for row in csv.DictReader(f, delimiter='\t'):
            sym[row['genes']] = (row.get('geneSymbols') or '').split(';')[0]
    log('single-gene deletions…')
    dele = single_gene_deletion(m, processes=4)
    ess = {}
    for ids, g in zip(dele['ids'], dele['growth']):
        gid = next(iter(ids)); ess[gid] = float(np.nan_to_num(g, nan=0.0)) / growth if growth > 0 else np.nan
    predicted = {sym[g]: v < 0.01 for g, v in ess.items() if sym.get(g)}
    res['essentiality'] = {'genes': len(ess), 'predictedEssential': int(sum(predicted.values())), 'definition': 'growth < 1 % of wild type after knockout (gene–reaction rules)'}
    if dep_npy:
        M = np.load(dep_npy, mmap_mode='r'); ids = json.load(open(dep_json)); gi = {g: i for i, g in enumerate(ids['genes'])}
        common = [g for g in predicted if g in gi]
        mean = np.array([float(np.nanmean(M[:, gi[g]])) for g in common]); frac = np.array([float(np.nanmean(M[:, gi[g]] < -0.5)) for g in common])
        pred = np.array([predicted[g] for g in common]); dep_ess = frac >= 0.9
        from scipy.stats import mannwhitneyu, fisher_exact
        tp, fp, fn = int((pred & dep_ess).sum()), int((pred & ~dep_ess).sum()), int((~pred & dep_ess).sum()); tn = int((~pred & ~dep_ess).sum())
        auc = float(mannwhitneyu(-mean[pred], -mean[~pred]).statistic / (pred.sum() * (~pred).sum())) if pred.any() and (~pred).any() else None
        res['essentiality']['depmap'] = {'genesCompared': len(common), 'depmapCommonEssential': int(dep_ess.sum()), 'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
                                         'precision': tp / max(tp + fp, 1), 'recall': tp / max(tp + fn, 1), 'oddsRatio': float(fisher_exact([[tp, fp], [fn, tn]])[0]), 'fisherP': float(fisher_exact([[tp, fp], [fn, tn]], alternative='greater')[1]),
                                         'aucMeanEffect': auc, 'definition': 'DepMap common essential = gene effect < −0.5 in ≥ 90 % of models (all lineages)',
                                         'examples': {'agree': sorted([g for g, p, d in zip(common, pred, dep_ess) if p and d])[:15], 'modelOnly': sorted([g for g, p, d in zip(common, pred, dep_ess) if p and not d])[:15],
                                                      'depmapOnly': sorted([g for g, p, d in zip(common, pred, dep_ess) if d and not p])[:15]}}
    res['evidence'] = 'Mechanistic simulation (Human-GEM stoichiometry with medium bounds); essentiality compared against an experimental CRISPR screen (statistical association)'
    res['seconds'] = round(time.time() - t0, 1)
    json.dump(res, open(out, 'w'), default=float); log('done')


RELEASE = 'v2.1.1'
FILES = {'Human-GEM.xml': 'b5cecde878096546f819491be38ce274777e981d', 'genes.tsv': 'cc67706849e88c4829cd2345777f156e6e5d6243', 'reactions.tsv': '0e5662321de8a98acc58c378430bdba23a3c90f7'}


def install(folder):
    """Download Human-GEM at a fixed release, verify each file's git blob hash, and write a fast JSON copy."""
    import hashlib, pathlib, urllib.request, cobra
    d = pathlib.Path(folder); d.mkdir(parents=True, exist_ok=True)
    for name, git in FILES.items():
        raw = urllib.request.urlopen(f'https://raw.githubusercontent.com/SysBioChalmers/Human-GEM/{RELEASE}/model/{name}', timeout=600).read()
        if hashlib.sha1(b'blob %d\0' % len(raw) + raw).hexdigest() != git:
            raise SystemExit(f'{name}: git hash mismatch; not used.')
        (d / name).write_bytes(raw); print(f'{name}: {len(raw):,} bytes, git hash verified', flush=True)
    cobra.io.save_json_model(cobra.io.read_sbml_model(str(d / 'Human-GEM.xml')), str(d / 'Human-GEM.json'))
    (d / 'manifest.json').write_text(json.dumps({'model': 'Human-GEM', 'release': RELEASE, 'source': 'https://github.com/SysBioChalmers/Human-GEM', 'licence': 'CC BY 4.0',
                                                 'citation': 'Robinson JL et al. An atlas of human metabolism. Sci Signal 2020;13:eaaz1482.', 'gitBlobSha1': FILES}, indent=1))
    print('ready', flush=True)


if __name__ == '__main__':
    install(sys.argv[2]) if sys.argv[1] == 'install' else main(*sys.argv[1:])
