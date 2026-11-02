"""Demo 9 analysis: compare predicted RNA 3D structures with each other and with an experimental structure.

Runs locally on files returned by remote GPU tasks. Measures (all on C1' atoms unless stated):
  * RMSD to the experimental reference after optimal superposition (Kabsch);
  * pairwise RMSD between predicted models: model disagreement, not a trajectory;
  * steric clashes: heavy atoms of non-adjacent residues closer than 2.2 Å;
  * base-pair geometry: share of the reference secondary-structure pairs whose C1'–C1' distance lies in
    9.0–12.0 Å, the range of canonical Watson–Crick and wobble pairs (~10.5 Å).
"""
import json, math, pathlib
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
REFERENCE = {'pdb': '1EHZ', 'chain': 'A', 'cif': HERE.parent / 'fixtures' / 'nucleic-acids' / '1EHZ.cif'}


def _split(line):
    out, cur, q = [], '', None
    for ch in line:
        if q:
            if ch == q:
                q = None
            else:
                cur += ch
        elif ch in '"\'' and not cur:
            q = ch
        elif ch.isspace():
            if cur:
                out.append(cur); cur = ''
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def read_cif(path, chain):
    cols, rows, inloop = [], [], False
    for line in pathlib.Path(path).read_text().splitlines():
        if line.startswith('_atom_site.'):
            cols.append(line.split('.', 1)[1].strip()); inloop = True; continue
        if inloop and cols:
            if line.startswith(('ATOM', 'HETATM')):
                rows.append(_split(line))
            elif line.startswith(('#', 'loop_', '_')) and rows:
                break
    c = {n: i for i, n in enumerate(cols)}
    atoms = []
    for r in rows:
        if r[c['auth_asym_id']] != chain or r[c.get('pdbx_PDB_model_num', 0)] not in ('1',) and 'pdbx_PDB_model_num' in c:
            continue
        atoms.append({'name': r[c['label_atom_id']], 'element': r[c['type_symbol']], 'res': int(r[c['label_seq_id']]) if r[c['label_seq_id']] not in ('.', '?') else None,
                      'xyz': (float(r[c['Cartn_x']]), float(r[c['Cartn_y']]), float(r[c['Cartn_z']]))})
    return [a for a in atoms if a['res'] is not None]


def read_pdb(text):
    atoms, residues = [], {}
    for line in text.splitlines():
        if line.startswith(('ATOM', 'HETATM')):
            key = (line[21], line[22:27])
            residues.setdefault(key, len(residues) + 1)
            name = line[12:16].strip().replace('*', "'")
            el = (line[76:78].strip() or name[0])
            atoms.append({'name': name, 'element': el, 'res': residues[key], 'xyz': (float(line[30:38]), float(line[38:46]), float(line[46:54]))})
        elif line.startswith('ENDMDL'):
            break
    return atoms


def c1(atoms):
    return {a['res']: np.array(a['xyz']) for a in atoms if a['name'] == "C1'"}


def kabsch_rmsd(P, Q):
    P0, Q0 = P - P.mean(0), Q - Q.mean(0)
    U, _, Vt = np.linalg.svd(P0.T @ Q0)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = U @ np.diag([1, 1, d]) @ Vt
    return float(np.sqrt((((P0 @ R) - Q0) ** 2).sum(1).mean()))


def clashes(atoms, cutoff=2.2):
    heavy = [a for a in atoms if a['element'].upper() != 'H']
    X = np.array([a['xyz'] for a in heavy]); res = np.array([a['res'] for a in heavy])
    n = 0
    for i in range(len(X)):
        d = np.sqrt(((X[i + 1:] - X[i]) ** 2).sum(1))
        far = np.abs(res[i + 1:] - res[i]) > 1
        n += int(((d < cutoff) & far).sum())
    return n


def pairs_from_dotbracket(db):
    st, out = [], []
    for i, ch in enumerate(db):
        if ch == '(':
            st.append(i + 1)
        elif ch == ')':
            out.append((st.pop(), i + 1))
    return out


def superpose(trace, target):
    """Rigid fit (Kabsch) of a {res: xyz} trace onto target over shared residues; applied to every residue of the trace."""
    common = sorted(set(trace) & set(target))
    if len(common) < 3:
        return trace
    P, Q = np.array([trace[k] for k in common]), np.array([target[k] for k in common])
    p, q = P.mean(0), Q.mean(0)
    U, _, Vt = np.linalg.svd((P - p).T @ (Q - q))
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = U @ np.diag([1, 1, d]) @ Vt
    return {k: (v - p) @ R + q for k, v in trace.items()}


def analyse(models, reference_atoms=None, pairs=()):
    """models: {name: atoms}. Returns per-model metrics and the pairwise disagreement matrix."""
    names = list(models)
    traces = {n: c1(a) for n, a in models.items()}
    ref = c1(reference_atoms) if reference_atoms else None
    rows = []
    for n in names:
        t = traces[n]
        row = {'model': n, 'residues': len(t), 'clashes': clashes(models[n])}
        if ref:
            common = sorted(set(t) & set(ref))
            row['rmsdToReference'] = kabsch_rmsd(np.array([t[k] for k in common]), np.array([ref[k] for k in common])) if len(common) >= 3 else None
            row['matchedResidues'] = len(common)
        if pairs:
            ok = [9.0 <= float(np.linalg.norm(t[i] - t[j])) <= 12.0 for i, j in pairs if i in t and j in t]
            row['basePairGeometry'] = sum(ok) / len(ok) if ok else None
        rows.append(row)
    M = [[0.0] * len(names) for _ in names]
    for a in range(len(names)):
        for b in range(a + 1, len(names)):
            ta, tb = traces[names[a]], traces[names[b]]
            common = sorted(set(ta) & set(tb))
            M[a][b] = M[b][a] = kabsch_rmsd(np.array([ta[k] for k in common]), np.array([tb[k] for k in common])) if len(common) >= 3 else None
    out = {'models': rows, 'names': names, 'pairwise': M,
           'traces': {}}
    # Drawn traces are superposed onto the reference (or the first model), the same fit the RMSD uses.
    anchor = ref or (traces[names[0]] if names else {})
    for n in names:
        s = superpose(traces[n], anchor)
        out['traces'][n] = [s[k].round(2).tolist() for k in sorted(s)]
    if ref:
        out['reference'] = {'pdb': REFERENCE['pdb'], 'chain': REFERENCE['chain'], 'trace': [ref[k].round(2).tolist() for k in sorted(ref)]}
    if pairs and reference_atoms:
        r = c1(reference_atoms)
        ok = [9.0 <= float(np.linalg.norm(r[i] - r[j])) <= 12.0 for i, j in pairs if i in r and j in r]
        out['referenceBasePairGeometry'] = sum(ok) / len(ok) if ok else None
    return out


def compare_task(outputs, p):
    outputs = pathlib.Path(outputs)
    files = sorted(f for f in outputs.rglob('*.pdb'))
    if not files:
        raise ValueError('This task returned no PDB files to compare.')
    models = {str(f.relative_to(outputs)): read_pdb(f.read_text()) for f in files[:40]}
    ref_atoms, pairs = None, ()
    if p.get('reference', 'trna_phe') == 'trna_phe':
        ref_atoms = read_cif(REFERENCE['cif'], REFERENCE['chain'])
        refdata = json.loads((HERE / 'rna_lab_reference.json').read_text())['trna_phe']
        pairs = pairs_from_dotbracket(refdata['structure'])
    res = analyse(models, ref_atoms, pairs)
    res['note'] = ('Predicted models are independent predictions: their spread shows model disagreement, not motion along a folding pathway. '
                   'tRNA-Phe in 1EHZ carries modified nucleotides; predictions use the unmodified parent sequence.')
    return res
