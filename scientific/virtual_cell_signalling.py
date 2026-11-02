"""Virtual Cell signalling readout: SPARCED with the cell's mRNA changes applied (science runtime: NumPy, SciPy).

    python virtual_cell_signalling.py <SPARCED.xml> <request.json> <out.json>

SPARCED (Erdem et al., Nat Commun 2022; built on Bouhaddou et al., PLoS Comput Biol 2018) is a mechanistic model of
proliferation and death signalling: 914 species, 2,434 reactions, parameterised for MCF10A breast epithelial cells.
Its mRNAs (m_<GENE>) are fixed inputs, so the virtual cell couples to it by scaling them: knockout → 0, and every other
SPARCED mRNA in the expression panel → the fold change the virtual cell's state predicts. The model is integrated
deterministically (SciPy LSODA via the Mechanistic Lab compiler); SPARCED's stochastic gene-expression module is not run.

request.json: {"fold": {"TP53": 0.0, "CCND1": 1.8, ...}, "hours": 24}
"""
import json
import sys
import time

import mechanistic_sbml as M
import mechanistic_sim as S

OUTPUTS = {'ppERK': 'doubly phosphorylated ERK (MAPK pathway activity)', 'ppAKT': 'doubly phosphorylated AKT (PI3K pathway activity)',
           'Cd': 'cyclin D (G1 progression)', 'E2F': 'free E2F (S-phase entry)', 'p53ac': 'active p53', 'cPARP': 'cleaved PARP (apoptosis marker)'}


def run(xml, request, out):
    t0 = time.time()
    req = json.load(open(request)); hours = float(req.get('hours', 24))
    m = M.Model(open(xml).read())
    fixed = set(m.fixed_ids)
    applied = {g: f for g, f in req['fold'].items() if f'm_{g}' in fixed}
    base = S.simulate(m, hours * 3600, points=int(hours) + 1, method='LSODA', rtol=1e-6, atol=1e-9, check=False)
    # fixed (boundary) species take their value from the initial symbols, so scaling the initial value scales the mRNA level
    sp = {s['id']: s for s in m.species}
    scaled = {f'm_{g}': m._initial_symbol(sp[f'm_{g}']) * float(f) for g, f in applied.items()}
    pert = S.simulate(m, hours * 3600, points=int(hours) + 1, method='LSODA', rtol=1e-6, atol=1e-9, initial=scaled, check=True)
    hours_axis = [t / 3600 for t in pert['time']]
    rows = []
    for k, label in OUTPUTS.items():
        b, p = base['series'].get(k), pert['series'].get(k)
        if b is None or p is None:
            continue
        rows.append({'species': k, 'meaning': label, 'unit': 'nM', 'baseline': b, 'perturbed': p, 'endRatio': (p[-1] / b[-1]) if b[-1] else None})
    res = {'readout': 'signalling', 'model': 'SPARCED (Demo/SPARCED.xml)', 'hours': hours_axis, 'outputs': rows,
           'applied': [{'gene': g, 'fold': f} for g, f in sorted(applied.items())], 'notInModel': sorted(set(req['fold']) - set(applied)),
           'diagnostics': pert['diagnostics'], 'seconds': round(time.time() - t0, 1)}
    with open(out, 'w') as f:
        json.dump(res, f, allow_nan=False, default=lambda x: None)


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2], sys.argv[3])
