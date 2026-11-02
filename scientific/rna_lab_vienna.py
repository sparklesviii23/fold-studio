"""ViennaRNA cross-checks for the RNA-to-Protein Laboratory (used only when `import RNA` works).

Builds a ViennaRNA parameter file that encodes exactly the built-in `rna_lab_fold` energy model.

Starting from ViennaRNA's own Turner 1999 set, every term the built-in model omits is reduced to what the
built-in model uses instead: mismatch tables become the terminal AU/GU penalty of the closing pair, the
1x1/2x1/2x2 tables become the generic interior-loop formula, and dangles/special hairpins are switched off
in the model details. ViennaRNA then serves as an independent implementation of the same model.
"""
import re
import rna_lab_fold as fold

VTYPES = {'CG': 1, 'GC': 2, 'GU': 3, 'UG': 4, 'AU': 5, 'UA': 6, 'NS': 7, 'NP': 7}


def _au(t):
    return fold.TERM_AU if t in (3, 4, 5, 6) else 0


def reduced_parameter_file(turner1999_text):
    out, section, row = [], None, 0
    block_types = None
    mismatch = {'mismatch_hairpin', 'mismatch_internal', 'mismatch_internal_1n', 'mismatch_internal_23', 'mismatch_multi', 'mismatch_exterior'}
    for line in turner1999_text.splitlines():
        if line.startswith('# '):
            section, row, block_types = line[2:].strip(), 0, None
            out.append(line); continue
        stripped = line.strip()
        if section in ('int11', 'int21', 'int22') and stripped.startswith('/*'):
            names = re.findall(r'\b(CG|GC|GU|UG|AU|UA|NS|NP)\b', stripped)
            block_types = (VTYPES[names[0]], VTYPES[names[-1]]) if len(names) >= 2 else None
            out.append(line); continue
        if not stripped or stripped.startswith('/*') or section is None:
            out.append(line); continue
        tokens = stripped.split()
        if section in mismatch:
            t = row // 5 + 1; row += 1
            out.append(' '.join(f'{_au(t):6d}' for _ in tokens)); continue
        if section in ('int11', 'int21', 'int22') and block_types:
            t1, t2 = block_types
            if 7 in block_types:
                out.append(line); continue
            size = {'int11': 2, 'int21': 3, 'int22': 4}[section]
            ninio = min(fold.NINIO_MAX, fold.NINIO) if section == 'int21' else 0
            v = fold.INTERIOR[size] + ninio + _au(t1) + _au(t2)
            out.append(' '.join(f'{v:6d}' for _ in tokens)); continue
        if section in ('dangle5', 'dangle3'):
            out.append(' '.join(f'{0:6d}' for _ in tokens)); continue
        out.append(line)
    return '\n'.join(out) + '\n'


def _turner1999_text(RNA, folder):
    import pathlib
    RNA.params_load_RNA_Turner1999()
    path = pathlib.Path(folder) / 'turner1999.par'
    RNA.params_save(str(path))
    return path.read_text()


def table_check():
    """Built-in tables against ViennaRNA's loaded Turner 1999 set (dcal/mol)."""
    import RNA
    RNA.params_load_RNA_Turner1999()
    P = RNA.param(RNA.md())
    diffs = []
    stack = [[P.stack[a][b] for b in range(1, 7)] for a in range(1, 7)]
    if stack != fold.STACK: diffs.append('stack')
    for name, mine in (('hairpin', fold.HAIRPIN), ('bulge', fold.BULGE), ('internal_loop', fold.INTERIOR)):
        theirs = list(getattr(P, name))[:31]
        if any(mine[i] != theirs[i] for i in range(1, 31) if mine[i] < fold.INF): diffs.append(name)
    if (P.TerminalAU, P.MLclosing, P.MLintern[1], P.MLbase, P.ninio[2]) != (fold.TERM_AU, fold.ML_A, fold.ML_C, fold.ML_B, fold.NINIO): diffs.append('scalars')
    if abs(P.lxc - fold.LXC) > 1e-6: diffs.append('lxc')
    RNA.params_load_RNA_Turner2004()
    return diffs


def model_check(sequences):
    """Run ViennaRNA on the reduced parameter file and return the largest differences to the built-in engine."""
    import tempfile, pathlib, RNA
    with tempfile.TemporaryDirectory() as tmp:
        red = pathlib.Path(tmp) / 'reduced.par'
        red.write_text(reduced_parameter_file(_turner1999_text(RNA, tmp)))
        RNA.params_load(str(red))
        try:
            worst = {'mfe': 0.0, 'ensemble': 0.0, 'probability': 0.0, 'evaluation': 0.0}
            for seq in sequences:
                md = RNA.md(); md.dangles = 0; md.special_hp = 0; md.uniq_ML = 1
                fc = RNA.fold_compound(seq, md); s, e = fc.mfe(); fc.exp_params_rescale(e); _, g = fc.pf(); P = fc.bpp()
                b = fold.Builtin(seq); n = len(seq)
                worst['mfe'] = max(worst['mfe'], abs(e - b.mfe_energy))
                worst['ensemble'] = max(worst['ensemble'], abs(g - b.ensemble_energy))
                worst['probability'] = max(worst['probability'], max(abs(P[i + 1][j + 1] - b.P[i][j]) for i in range(n) for j in range(i + 1, n)))
                for st in b.sample(10, 1) + [s]:
                    worst['evaluation'] = max(worst['evaluation'], abs(fc.eval_structure(st) - fold.evaluate(seq, st)))
            return worst
        finally:
            RNA.params_load_RNA_Turner2004()
