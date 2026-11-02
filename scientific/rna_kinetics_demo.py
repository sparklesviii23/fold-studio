"""Demo 10: exact folding kinetics of a two-state RNA switch, with checks and a saved record."""
import json, math, pathlib, platform, time, uuid
import numpy as np, scipy
import rna_kinetics as K

DEFAULT = 'GGCGGUGCCCGCCCGGCGGG'
REFS = {
    'kinfold': {'citation': 'Flamm C, Fontana W, Hofacker IL, Schuster P. RNA folding at elementary step resolution. RNA 2000;6:325–338.', 'doi': '10.1017/S1355838200992161'},
    'barriers': {'citation': 'Wolfinger MT, Svrcek-Seiler WA, Flamm C, Hofacker IL, Stadler PF. Efficient computation of RNA folding dynamics. J Phys A 2004;37:4731.', 'doi': '10.1088/0305-4470/37/17/005'},
    'vienna': {'citation': 'Lorenz R, Bernhart SH, Höner zu Siederdissen C, et al. ViennaRNA Package 2.0. Algorithms Mol Biol 2011;6:26.', 'doi': '10.1186/1748-7188-6-26'},
}
ASSUMPTIONS = [
    'Turner 2004 nearest-neighbour energies (ViennaRNA defaults), dangles = 0, 1 M NaCl reference conditions.',
    'Elementary moves open or close one base pair; Metropolis rates k₀·min(1, e^(−ΔE/RT)).',
    'k₀ is uncalibrated: times are in units of 1/k₀ (published estimates put elementary steps near microseconds, but this run does not depend on that).',
    'Folding starts from the fully open chain; the whole chain exists at t = 0 (no co-transcriptional growth).',
]
LIMITATIONS = [
    'Test sequence chosen in silico for two competing hairpins; no measured kinetics exist for it.',
    'No pseudoknots, shift moves, Mg²⁺ or tertiary contacts.',
    'Exact eigen-solution is limited to ≈6,000 structures (about 20 nt).',
]


def _clean(seq):
    s = ''.join(seq.split()).upper().replace('T', 'U')
    if not s or set(s) - set('ACGU'):
        raise ValueError('Use an RNA sequence of A, C, G and U.')
    if not 8 <= len(s) <= 24:
        raise ValueError('Exact kinetics needs 8–24 nucleotides.')
    return s


def run(sequence=DEFAULT, temperature=37.0, seed=1, trajectories=400):
    started = time.time()
    seq = _clean(sequence)
    if not 0 <= temperature <= 80:
        raise ValueError('Temperature must lie in 0–80 °C.')
    L = K.enumerate_landscape(seq, temperature)
    E, kT, structs = L['energies'], L['kT'], L['structures']
    n = len(E)
    edges, _ = K.graph(structs)
    Q = K.generator(E, edges, kT)
    pi = K.boltzmann(E, kT)
    sol = K.Solution(Q, pi)
    open_i = structs.index('.' * len(seq))
    mfe_i = int(np.argmin(E))
    p0 = np.zeros(n); p0[open_i] = 1.0
    slowest = max(K.Solution.relaxation_times(sol, 1) or [1.0])
    times = np.logspace(-2, math.log10(slowest * 30), 140)
    raw_c = sol.V.T @ (p0 / sol.s)
    P_raw = ((np.exp(np.outer(times, sol.lam)) * raw_c) @ sol.V.T) * sol.s[None, :]
    P = np.maximum(P_raw, 0.0)

    root = K.basins(E, edges, n)
    mins = np.unique(root)
    eq = {int(m): float(pi[root == m].sum()) for m in mins}
    top = sorted(mins, key=lambda m: -eq[int(m)])[:4]
    macro = [{'minimum': int(m), 'structure': structs[m], 'energy': float(E[m]), 'equilibrium': eq[int(m)], 'states': int((root == m).sum()),
              'population': P[:, root == m].sum(1).tolist()} for m in top]
    other = 1 - sum(np.array(b['population']) for b in macro)
    sad = K.saddles(E, edges, sorted(int(m) for m in top))
    barriers = [{'from': structs[a], 'to': structs[b], 'saddle': s, 'barrierFrom': s - float(E[a]), 'barrierTo': s - float(E[b])} for (a, b), s in sad.items()]
    tau = K.mean_first_passage(Q, mfe_i)

    checks = []
    G_enum = -kT * math.log(np.exp(-(E - E.min()) / kT).sum()) + E.min()
    checks.append({'name': 'Complete enumeration reproduces the partition function', 'passed': abs(G_enum - L['ensembleEnergy']) < 1e-4,
                   'detail': f'{n:,} structures: −RT ln Σe^(−E/RT) = {G_enum:.6f} vs ViennaRNA pf {L["ensembleEnergy"]:.6f} kcal/mol'})
    flux = np.abs(Q.T @ pi).max() / np.abs(Q.diagonal()).max()
    checks.append({'name': 'Boltzmann distribution is stationary (detailed balance)', 'passed': flux < 1e-12 and abs(sol.lam.max()) < 1e-9,
                   'detail': f'max |Qᵀπ| relative {flux:.1e}; largest eigenvalue {sol.lam.max():.1e}'})
    tv = 0.5 * float(np.abs(P[-1] - pi).sum())
    checks.append({'name': 'Long-time limit equals the Boltzmann ensemble', 'passed': tv < 1e-3, 'detail': f'total-variation distance {tv:.1e} at t = {times[-1]:.3g}/k₀'})
    cons = float(np.abs(P_raw.sum(1) - 1).max())
    checks.append({'name': 'Probability conservation', 'passed': cons < 1e-6 and P_raw.min() > -1e-9, 'detail': f'max |Σp(t) − 1| = {cons:.1e} (eigen-solution in double precision over a spectrum spanning {abs(sol.lam.min()):.0e}–{abs(sorted(sol.lam)[-2]):.0e}); most negative raw p {P_raw.min():.1e}'})

    # Independent solver: exact stochastic simulation on the same generator at early and intermediate times.
    ssa_t = times[(times >= 1) & (times <= min(times[-1], 3e4))][::14]
    states, _ = K.gillespie(Q, open_i, ssa_t, trajectories, seed)
    zmax, rows = 0.0, []
    for k, t in enumerate(ssa_t):
        pk = sol.at(p0, np.array([t]))[0]
        for b in macro:
            m = root == b['minimum']
            exact = float(pk[m].sum()); obs = float(np.isin(states[:, k], np.nonzero(m)[0]).mean())
            se = math.sqrt(max(exact * (1 - exact), 1e-12) / trajectories)
            zmax = max(zmax, abs(obs - exact) / se if se > 0 else 0.0)
            rows.append({'t': float(t), 'basin': b['structure'], 'exact': exact, 'ssa': obs})
    checks.append({'name': 'Stochastic simulation agrees with the master equation', 'passed': zmax < 4.5,
                   'detail': f'{trajectories} Gillespie trajectories, {len(ssa_t)} times × {len(macro)} basins; largest |z| {zmax:.2f}', 'rows': rows})

    try:
        import RNA
        fc = RNA.fold_compound(seq, K.model(temperature))
        a, b = (int(m) for m in top[:2]) if len(top) > 1 else (mfe_i, mfe_i)
        heur = fc.path_findpath_saddle(structs[a], structs[b], 10) / 100.0
        exact = sad.get((min(a, b), max(a, b)), float(E[a]))
        checks.append({'name': 'Exact saddle is at or below the ViennaRNA findpath estimate', 'passed': exact <= heur + 1e-6,
                       'detail': f'exact minimax saddle {exact:.2f} vs findpath (width 10, direct paths only) {heur:.2f} kcal/mol'})
    except (ImportError, AttributeError, TypeError) as e:
        checks.append({'name': 'Exact saddle against findpath', 'passed': False, 'detail': 'findpath unavailable: ' + str(e)})

    return {
        'id': 'demo10', 'title': 'Demo 10 · RNA folding kinetics', 'sequence': seq, 'temperature': temperature, 'seed': seed,
        'question': 'Starting from an unfolded chain, which hairpin does this RNA fold into first, and how long until it reaches thermodynamic equilibrium?',
        'evidence': {'kinetics': 'Physics-simulated (Markov model on a thermodynamic landscape; time scale uncalibrated)', 'energies': 'Statistically predicted · nearest-neighbour model'},
        'method': 'Complete secondary-structure enumeration (ViennaRNA RNAsubopt), Metropolis single-pair moves, exact master-equation solution by eigen-decomposition',
        'landscape': {'states': n, 'moves': int(len(edges)), 'minima': int(len(mins)), 'mfe': structs[mfe_i], 'mfeEnergy': float(E[mfe_i]), 'ensembleEnergy': L['ensembleEnergy'],
                      'viennarna': L['version']},
        'times': times.tolist(), 'basins': macro, 'other': np.maximum(other, 0).tolist(), 'barriers': barriers,
        'relaxationTimes': [float(x) for x in K.Solution.relaxation_times(sol, 5)],
        'outputs': {'mfptOpenToMfe': float(tau[open_i]), 'slowestRelaxation': float(slowest),
                    'kineticPartition': {b['structure']: float(np.interp(math.log10(min(1e3, times[-1])), np.log10(times), b['population'])) for b in macro}},
        'checks': checks, 'assumptions': ASSUMPTIONS, 'limitations': LIMITATIONS, 'references': REFS,
        'seconds': time.time() - started,
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__, 'viennarna': L['version']},
    }
