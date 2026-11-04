"""Virtual Cell: a persistent, stateful cell object with observe / perturb / branch / design (docs/VIRTUAL_CELL.md).

A cell is stored as its context and the ordered history of operations applied to it. Its state is never edited in place:
it is rebuilt by replaying the history against the reference pack (virtual_cell_reference.py), so every state is
reproducible from its record. Branching copies a history prefix into a new cell; nothing is ever overwritten.

State levels in this release (the AIDO Cell schema has four; unmodelled levels are reported as such, never filled in):
  gene      expression of a 2,085-gene panel (log1p counts per 10,000), DepMap K-562 knockout fitness, metabolic genes
  cell      context, history, knocked-out and over-expressed gene sets
  isoform, nucleotide   not modelled yet

Transitions
  gene_overexpression (CRISPRa)
     measured single in Norman 2019                 → its measured mean effect                       A · Experimental
     a measured pair matching the over-expressed set → that pair's measured effect                     A · Experimental
     other combinations                             → sum of single effects (additive model)           C · AI prediction
     panel gene never perturbed                     → linear model (Ahlmann-Eltze et al. 2025)         C · AI prediction
     outside the panel                              → refused (outside the validated domain)
  gene_knockout
     expression effect                              → not modelled (needs Replogle 2022, Phase 2); stated on every readout
     fitness                                        → DepMap 24Q4 Chronos score of the gene in K-562   A · Experimental
     metabolism                                     → Human-GEM flux balance with the gene's reactions removed  B
Held-out scores of each transition on Norman 2019 (Demo J) travel with every readout that used it.
"""
import hashlib
import json
import pathlib
import re
import time
import uuid

import numpy as np

import perturb_model
import virtual_cell_drugs as drugs
import virtual_cell_plugins as plugins

REF = ('virtualcell', 'reference', 'k562')
CONTEXTS = {'K562': {'name': 'K-562', 'cellosaurus': 'CVCL_0004', 'depmap': 'ACH-000551', 'disease': 'Chronic myeloid leukaemia, BCR-ABL1+', 'sex': 'Female'}}
OPS = ('gene_overexpression', 'gene_knockout', 'gene_knockdown', 'small_molecule')
UNSUPPORTED = {'gene_mutation': 'Point mutations need sequence-to-function models (Phase 3).'}
EVIDENCE = {'A': 'A · Experimental', 'B': 'B · Physics simulation (mechanistic, constraint-based)', 'C': 'C · AI prediction', 'D': 'D · Parameterised hypothesis'}
GENE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9.\-]{0,30}$')
_CACHE = {}


def _finite(x):
    """JSON-safe copy: NaN and ±inf become None (the interface parses strict JSON)."""
    if isinstance(x, dict):
        return {k: _finite(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_finite(v) for v in x]
    return None if isinstance(x, float) and not np.isfinite(x) else x


def _split(p):
    return [g for g in p.replace('+', '_').split('_') if g and g != 'control']


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


class Reference:
    """The K-562 reference pack, plus the linear model fitted on every measured single over-expression."""

    kind = 'k562'

    def __init__(self, folder, root=None):
        folder = pathlib.Path(folder); self.root = root
        z = np.load(folder / 'pack.npz', allow_pickle=False)
        self.manifest = _finite(json.loads((folder / 'manifest.json').read_text()))     # Demo J stores NaN for undefined correlations
        self.genes = [str(g) for g in z['genes']]; self.gi = {g: i for i, g in enumerate(self.genes)}
        self.control = z['control'].astype(np.float64); self.control_sd = z['controlSd'].astype(np.float64)
        perts = [str(p) for p in z['perturbations']]; eff = z['effects'].astype(np.float64); cells = [int(c) for c in z['cells']]
        self.singles, self.pairs = {}, {}
        for j, p in enumerate(perts):
            g = _split(p)
            if len(g) == 1:
                self.singles[g[0]] = (eff[:, j], cells[j])
            elif len(g) == 2:
                self.pairs[frozenset(g)] = (eff[:, j], cells[j], p)
        self.depmap = dict(zip((str(g) for g in z['depmapGenes']), z['depmapEffect'].astype(float)))
        self.depmap_expr = dict(zip((str(g) for g in z['depmapExprGenes']), z['depmapExpression'].astype(float)))
        names = sorted(self.singles)
        Y = np.column_stack([self.singles[g][0] for g in names])
        self._linear = perturb_model.linear_fit(Y, [[g] for g in names], self.gi)
        self.benchmark = self.manifest['benchmark']
        self.kd, self.kd_remaining, self._kd_linear = {}, {}, None
        if 'kdEffects' in z.files:
            kde = z['kdEffects'].astype(np.float64); self.kd_measured = z['kdMeasured'].astype(bool)
            for j, g in enumerate(str(x) for x in z['kdPerturbations']):
                self.kd[g] = (np.nan_to_num(kde[:, j]), int(z['kdCells'][j]))
                if np.isfinite(z['kdRemaining'][j]):
                    self.kd_remaining[g] = round(float(z['kdRemaining'][j]), 4)
            idx = np.where(self.kd_measured)[0]; sub = {self.genes[i]: k for k, i in enumerate(idx)}
            names = [g for g in self.kd if g in sub]
            if len(names) > 10:
                lin = perturb_model.linear_fit(np.column_stack([self.kd[g][0][idx] for g in names]), [[g] for g in names], sub)

                def kd_linear(gene, lin=lin, idx=idx, sub=sub):
                    out = np.zeros(len(self.genes)); out[idx] = lin([[gene]])[:, 0]
                    return out
                self._kd_linear = kd_linear
                self._kd_sub = sub

    def kd_effect(self, gene):
        """(effect, contribution) of a CRISPRi knockdown: measured in Replogle 2022, else the linear model for panel genes."""
        if gene in self.kd:
            return self.kd[gene][0], {'genes': [gene], 'source': f'measured knockdown, Replogle 2022 ({self.kd[gene][1]} cells)', 'category': 'A', 'kind': 'knockdown'}
        return self._kd_linear(gene), {'genes': [gene], 'source': 'linear model (knockdown never measured)', 'category': 'C', 'kind': 'knockdown'}

    def kd_possible(self, gene):
        return gene in self.kd or (self._kd_linear is not None and gene in self._kd_sub)

    def linear(self, gene):
        return self._linear([[gene]])[:, 0]

    def lin(self, x):
        """Expression on the linear scale (counts per 10,000)."""
        return np.expm1(x)

    def drug_effect(self, drug, conc):
        """K-562 is not in Tahoe-100M: transfer the mean response of the Tahoe lines, applied as fold changes."""
        A = drugs.atlas(self.root)
        if A is None:
            raise ValueError('Drug perturbations need the Tahoe-100M atlas (still downloading or not installed).')
        lfc, how, cat, kind = A.transfer(drug, conc)
        return _apply_fold(self, A, lfc), {'genes': [], 'drug': A.drug(drug)['name'], 'concentration': float(conc), 'source': how, 'category': cat, 'kind': kind}


def reference(root):
    folder = pathlib.Path(root).joinpath(*REF)
    if not (folder / 'pack.npz').is_file():
        return None
    key = (str(folder), (folder / 'pack.npz').stat().st_mtime)
    if key not in _CACHE:
        _CACHE.clear(); _CACHE[key] = Reference(folder, root)
    return _CACHE[key]


def _apply_fold(ref, A, lfc):
    """Change in ref's expression units when each gene's linear expression is multiplied by 2**log2FC (genes Tahoe did
    not test, or ref genes absent from the atlas, are unchanged)."""
    if getattr(ref, '_atlas_key', None) != id(A):
        ref._atlas_idx = np.array([A.gi.get(g, -1) for g in ref.genes]); ref._atlas_key = id(A)
    idx = ref._atlas_idx; f = np.zeros(len(ref.genes))
    ok = idx >= 0; f[ok] = np.nan_to_num(lfc[idx[ok]].astype(float))
    base = ref.control; new = ref.lin(base) * np.exp2(f)
    return (np.log1p(new) if ref.kind == 'k562' else np.log2(new + 1)) - base


class LineContext:
    """A Tahoe-100M cell line as a virtual cell context. Baseline: DepMap 24Q4 bulk expression of that line
    (log2 TPM+1). Drugs at measured doses are measurements; there is no genetic-perturbation transcriptome for these
    lines, so only knockouts (DepMap fitness, metabolism, signalling) are offered."""
    kind = 'tahoe'

    def __init__(self, root, A, cellosaurus):
        self.root = root; self.cellosaurus = cellosaurus; self.info = A.lines[cellosaurus]
        dm = pathlib.Path(root) / 'oncology' / 'depmap' / '24Q4'
        ex_meta = json.loads((dm / 'expression.json').read_text()); ge_meta = json.loads((dm / 'gene_effect.json').read_text())
        ex = np.load(dm / 'expression.npy', mmap_mode='r'); ge = np.load(dm / 'gene_effect.npy', mmap_mode='r')
        mid = self.info['depmap']
        if mid not in ex_meta['models']:
            raise ValueError(f'DepMap 24Q4 has no expression profile for {self.info["name"]}.')
        row = np.array(ex[ex_meta['models'].index(mid)], float); eg = {g: i for i, g in enumerate(ex_meta['genes'])}
        self.genes = [g for g in A.genes if g in eg]; self.gi = {g: i for i, g in enumerate(self.genes)}
        self.control = np.array([row[eg[g]] for g in self.genes]); self.control_sd = np.zeros(len(self.genes))
        self.depmap_expr = dict(zip(ex_meta['genes'], row))
        self.depmap = dict(zip(ge_meta['genes'], np.array(ge[ge_meta['models'].index(mid)], float))) if mid in ge_meta['models'] else {}
        self.singles, self.pairs, self.kd, self.kd_remaining, self._kd_linear = {}, {}, {}, {}, None
        self.manifest = {'expressionUnit': 'log2(TPM+1), DepMap 24Q4 bulk RNA-seq', 'created': 'DepMap 24Q4 + Tahoe-100M', 'benchmark': None,
                         'inputs': {'norman2019': {'sha256': None}},
                         'baselineNote': f'Baseline = DepMap bulk RNA-seq of {self.info["name"]}; drug responses are DESeq2 fold changes against DMSO in Tahoe-100M.'}

    def lin(self, x):
        return np.exp2(x) - 1

    def drug_effect(self, drug, conc):
        A = drugs.atlas(self.root)
        lfc, how, cat, kind = A.response(self.cellosaurus, drug, conc)
        return _apply_fold(self, A, lfc), {'genes': [], 'drug': A.drug(drug)['name'], 'concentration': float(conc), 'source': how, 'category': cat, 'kind': kind}

    def kd_possible(self, gene):
        return False


PROFILES = {'CVCL_0027': {'depmap': 'ACH-000739', 'related': 'HepG2/C3A (CVCL_1098) is a separate Tahoe-100M context: a clonal derivative of HepG2, not the parental line.'}}


class DepMapContext(LineContext):
    """A reference cell line from DepMap 24Q4 alone (no Tahoe-100M measurements): measured bulk RNA-seq baseline over
    all protein-coding genes, CRISPR knockout fitness, and the shared knockout readouts (metabolism, signalling).
    Identity is checked against the DepMap model table (cell line name and Cellosaurus RRID)."""
    kind = 'depmap'

    def __init__(self, root, cellosaurus):
        self.root = root; self.cellosaurus = cellosaurus; prof = PROFILES[cellosaurus]
        dm = pathlib.Path(root) / 'oncology' / 'depmap' / '24Q4'
        if not (dm / 'expression.npy').is_file():
            raise ValueError('DepMap 24Q4 is not installed (Oncology Universe › Data).')
        model = next((m for m in json.loads((dm / 'models.json').read_text()) if m['ModelID'] == prof['depmap']), None)
        if model is None or model.get('RRID') != cellosaurus:
            raise ValueError(f"DepMap model {prof['depmap']} does not carry RRID {cellosaurus}; refusing to use it as this cell line.")
        ex_meta = json.loads((dm / 'expression.json').read_text()); ge_meta = json.loads((dm / 'gene_effect.json').read_text())
        if prof['depmap'] not in ex_meta['models']:
            raise ValueError(f"DepMap 24Q4 has no expression profile for {model['CellLineName']}.")
        row = np.array(np.load(dm / 'expression.npy', mmap_mode='r')[ex_meta['models'].index(prof['depmap'])], float)
        self.info = {'name': model['CellLineName'], 'cellosaurus': cellosaurus, 'depmap': prof['depmap'], 'disease': model.get('OncotreePrimaryDisease'),
                     'sex': model.get('Sex'), 'age': model.get('Age'), 'source': f"{model.get('SourceType')} {model.get('CatalogNumber')}".strip(), 'related': prof['related']}
        self.genes = list(ex_meta['genes']); self.gi = {g: i for i, g in enumerate(self.genes)}
        self.control = row; self.control_sd = np.zeros(len(self.genes)); self.depmap_expr = dict(zip(self.genes, row))
        self.depmap = dict(zip(ge_meta['genes'], np.array(np.load(dm / 'gene_effect.npy', mmap_mode='r')[ge_meta['models'].index(prof['depmap'])], float))) if prof['depmap'] in ge_meta['models'] else {}
        self.singles, self.pairs, self.kd, self.kd_remaining, self._kd_linear = {}, {}, {}, {}, None
        self.manifest = {'expressionUnit': 'log2(TPM+1), DepMap 24Q4 bulk RNA-seq (protein-coding genes)', 'created': 'DepMap 24Q4', 'benchmark': None,
                         'inputs': {'norman2019': {'sha256': None}, 'depmap24q4': {'release': '24Q4', 'model': prof['depmap']}},
                         'baselineNote': f"Baseline = DepMap 24Q4 bulk RNA-seq of {model['CellLineName']} ({cellosaurus}); a single measured profile, no replicate spread."}

    def drug_effect(self, drug, conc):
        raise ValueError(f"No drug-response measurements exist for {self.info['name']}. {self.info['related']}")


_LINES = {}


def context_reference(root, context):
    if context == 'K562':
        ref = reference(root)
        if ref is None:
            raise ValueError('Build the K-562 reference first.')
        return ref
    if context in PROFILES:
        key = (str(root), context)
        if key not in _LINES:
            _LINES.clear(); _LINES[key] = DepMapContext(root, context)
        return _LINES[key]
    A = drugs.atlas(root)
    if A is None or context not in A.lines:
        raise ValueError('Unknown cell context.')
    key = (str(root), context, id(A))
    if key not in _LINES:
        _LINES.clear(); _LINES[key] = LineContext(root, A, context)
    return _LINES[key]


def context_info(ref):
    if ref.kind == 'k562':
        return CONTEXTS['K562']
    i = ref.info
    if ref.kind == 'depmap':
        return {k: i[k] for k in ('name', 'cellosaurus', 'depmap', 'disease', 'sex', 'age', 'source', 'related')}
    return {'name': i['name'], 'cellosaurus': i['cellosaurus'], 'depmap': i['depmap'], 'disease': 'Tahoe-100M cancer cell line', 'sex': None}


# ---------------------------------------------------------------- state

def replay(ref, history):
    """Rebuild the state a history produces. Pure: same reference + history → same state."""
    oe = [h['gene'] for h in history if h['op'] == 'gene_overexpression']
    ko = [h['gene'] for h in history if h['op'] == 'gene_knockout']
    kd = [h['gene'] for h in history if h['op'] == 'gene_knockdown']
    dr = [h for h in history if h['op'] == 'small_molecule']
    delta, contrib, composition, category = _oe_effect(ref, oe)
    for g in kd:
        e, c = ref.kd_effect(g); delta = delta + e; contrib.append(c)
    if kd:
        if oe or len(kd) > 1:
            composition, category = 'additive (sum of single effects' + (', across two screens' if oe else '') + ')', 'C'
        else:
            composition, category = 'single knockdown', contrib[-1]['category']
    for h in dr:
        e, c = ref.drug_effect(h['drug'], h['concentration']); delta = delta + e; contrib.append(c)
    if dr:
        if oe or kd or len(dr) > 1:
            composition, category = 'additive (sum of single effects, drugs included)', 'C'
        else:
            composition, category = f"single drug, {contrib[-1]['source']}", contrib[-1]['category']
    expr = ref.control + delta
    clipped = int((expr < 0).sum()); expr = np.maximum(expr, 0.0)
    return {'overexpressed': oe, 'knockedOut': ko, 'knockedDown': kd, 'drugs': [{'drug': h['drug'], 'concentration': h['concentration']} for h in dr],
            'delta': expr - ref.control, 'expression': expr, 'contributions': contrib,
            'composition': composition, 'category': category, 'clipped': clipped}


def _oe_effect(ref, oe):
    """Expression change of a set of over-expressed genes: the measured pair when that exact pair was measured,
    otherwise the sum of single effects (measured, or the linear model for genes never perturbed)."""
    delta, contrib = np.zeros(len(ref.genes)), []
    pair = ref.pairs.get(frozenset(oe)) if len(oe) == 2 else None
    if pair is not None:
        delta += pair[0]; contrib.append({'genes': list(oe), 'source': f'measured pair {pair[2]} ({pair[1]} cells)', 'category': 'A'})
    else:
        for g in oe:
            if g in ref.singles:
                delta += ref.singles[g][0]; contrib.append({'genes': [g], 'source': f'measured single ({ref.singles[g][1]} cells)', 'category': 'A'})
            else:
                delta += ref.linear(g); contrib.append({'genes': [g], 'source': 'linear model (gene never perturbed in the data)', 'category': 'C'})
    composed = len(oe) > 1 and pair is None
    composition = 'additive (sum of single effects)' if composed else 'measured pair' if pair is not None else 'single' if oe else 'baseline'
    category = 'C' if composed or any(c['category'] == 'C' for c in contrib) else 'A'
    return delta, contrib, composition, category


def _benchmark(ref, state):
    if state['drugs']:
        A = drugs.atlas(ref.root); bm = A.benchmark if A else None
        kinds = {c.get('kind') for c in state['contributions'] if c.get('drug')}
        if len(state['contributions']) > 1:
            return {'task': 'combination including drugs, additive', 'note': 'Tahoe-100M measured single drugs only; drug combinations and drug + gene combinations are additive assumptions, not benchmarked.'}
        if bm and (kinds & {'transfer', 'interpolation'}):
            k = (kinds & {'transfer', 'interpolation'}).pop()
            return {'task': ('leave-one-cell-line-out transfer' if k == 'transfer' else 'dose interpolation (middle dose from outer doses)') + ', Tahoe-100M',
                    'pearson': bm[k], 'replicatePlates': bm['replicatePlates'], 'metric': bm['metric'],
                    **({'baseline': {'task': 'generic drug response (mean of random conditions)', 'pearson': bm['genericResponse']}} if k == 'transfer' and bm.get('genericResponse') else {}),
                    'note': None if bm.get('complete') else f"Benchmark from {bm['lines']} of 50 cell lines; the atlas is still downloading."}
        return None
    if ref.kind != 'k562':
        return None
    b = ref.benchmark['results']
    kdm = ref.manifest.get('knockdown')
    if state['knockedDown'] and kdm:
        kb = kdm['benchmark']
        if any(c['category'] == 'C' and c.get('kind') == 'knockdown' for c in state['contributions']):
            return {'task': kb['task'] + ', linear model', **kb['linear model'], 'baseline': {'task': 'mean training effect', **kb['mean effect']}, 'noiseCeiling': kdm['noiseCeiling']}
        if state['category'] == 'C':
            return {'task': 'combination of measured perturbations, additive', 'note': 'Combinations involving knockdowns were never measured; additivity across perturbations and across the two screens is assumed, not benchmarked.'}
        return None
    if state['composition'].startswith('additive'):
        return {'task': 'unseen pairs, additive model', **b['pairs']['additive'], 'noiseCeiling': ref.benchmark['noiseCeiling'],
                'note': 'Measured pairs are mostly sub-additive (median scaling 0.83); combinations of three or more were never measured.' if len(state['overexpressed']) <= 2
                else 'Three or more simultaneous activations were never measured; additivity is extrapolated beyond its benchmark.'}
    if any(c['category'] == 'C' for c in state['contributions']):
        return {'task': 'unseen singles, linear model', **b['singles']['linear model'], 'baseline': {'task': 'mean training effect', **b['singles']['mean effect']},
                'note': 'On held-out genes the linear model is no better than predicting the average effect of all activations.'}
    return None


# ---------------------------------------------------------------- storage

def _cells(root):
    d = pathlib.Path(root) / 'virtualcell' / 'cells'; d.mkdir(parents=True, exist_ok=True)
    return d


def _path(root, cid):
    if not re.fullmatch(r'[0-9a-f]{32}', str(cid)):
        raise ValueError('Invalid virtual cell identifier.')
    f = _cells(root) / f'{cid}.json'
    if not f.is_file():
        raise ValueError('That virtual cell no longer exists.')
    return f


def load(root, cid):
    return json.loads(_path(root, cid).read_text())


def _save(root, cell):
    cell['sha256'] = _sha({k: cell[k] for k in ('context', 'history', 'reference')})
    (_cells(root) / f"{cell['id']}.json").write_text(json.dumps(cell, indent=1))
    return cell


def _now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def create(root, ref, name='', context='K562'):
    info = context_info(ref)
    cell = {'id': uuid.uuid4().hex, 'name': str(name or f"{info['name']} cell")[:80], 'context': context, 'created': _now(), 'parent': None,
            'history': [], 'reference': {'sha256': ref.manifest['inputs']['norman2019']['sha256'], 'created': ref.manifest['created']}}
    return _save(root, cell)


def branch(root, cid, step=None, name=''):
    src = load(root, cid); n = len(src['history']) if step is None else int(step)
    if not 0 <= n <= len(src['history']):
        raise ValueError(f'Choose a step between 0 and {len(src["history"])}.')
    cell = dict(src, id=uuid.uuid4().hex, created=_now(), parent={'id': src['id'], 'name': src['name'], 'step': n}, history=src['history'][:n],
                name=str(name or f"{src['name']} @ step {n}")[:80])
    return _save(root, cell)


def delete(root, cid):
    _path(root, cid).unlink(); return {'deleted': cid}


def listing(root):
    rows = []
    for f in sorted(_cells(root).glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True):
        c = json.loads(f.read_text())
        rows.append({'id': c['id'], 'name': c['name'], 'context': c['context'], 'created': c['created'], 'steps': len(c['history']), 'parent': c['parent']})
    return rows


def perturb(root, ref, cid, op, gene, drug=None, concentration=None):
    cell = load(root, cid)
    if op in UNSUPPORTED:
        raise ValueError(UNSUPPORTED[op])
    if op not in OPS:
        raise ValueError('Unknown perturbation.')
    if op == 'small_molecule':
        try:
            conc = float(concentration)
        except (TypeError, ValueError):
            raise ValueError('Enter a concentration in µM.')
        if not 0 < conc <= 1000:
            raise ValueError('Concentration must be between 0 and 1,000 µM.')
        name = str(drug or '').strip()
        if any(h['op'] == 'small_molecule' and h['drug'].lower() == name.lower() for h in cell['history']):
            raise ValueError(f'{name} is already applied to this cell; branch to try another dose.')
        _, c = ref.drug_effect(name, conc)                 # validates drug, line and dose range
        cell['history'].append({'op': op, 'gene': None, 'drug': c['drug'], 'concentration': conc, 'at': _now()})
        return _save(root, cell)
    if ref.kind != 'k562' and op != 'gene_knockout':
        raise ValueError(f"No genetic-perturbation transcriptome exists for {ref.info['name']}; only knockouts (fitness, metabolism, signalling)"
                         + (' are available here.' if ref.kind == 'depmap' else ' and drugs are available here.'))
    gene = str(gene or '').strip().upper()
    if not GENE.match(gene):
        raise ValueError('Enter a gene symbol, e.g. KLF1.')
    done = {(h['op'], h['gene']) for h in cell['history']}
    if (op, gene) in done:
        raise ValueError(f'{gene} already has that perturbation in this cell.')
    if op == 'gene_overexpression':
        if any(h['op'] == 'gene_knockout' and h['gene'] == gene for h in cell['history']):
            raise ValueError(f'{gene} is knocked out in this cell; branch before the knockout to over-express it.')
        if gene not in ref.singles and gene not in ref.gi:
            raise ValueError(f'{gene} is outside the validated domain: it was neither activated in Norman 2019 nor part of the 2,085-gene panel.')
    elif op == 'gene_knockdown':
        if not ref.kd:
            raise ValueError('Knockdowns need the Replogle 2022 screen in the reference; rebuild the reference after downloading it.')
        if any(h['gene'] == gene and h['op'] != 'gene_knockdown' for h in cell['history']):
            raise ValueError(f'{gene} already carries another perturbation in this cell; branch first.')
        if not ref.kd_possible(gene):
            raise ValueError(f'{gene} is outside the validated domain: it was not knocked down in Replogle 2022 and is not a measured panel gene.')
    else:
        if gene not in ref.depmap and gene not in ref.gi:
            raise ValueError(f'{gene} is not a gene this cell context knows (DepMap 24Q4 or the expression panel).')
    cell['history'].append({'op': op, 'gene': gene, 'at': _now()})
    return _save(root, cell)


# ---------------------------------------------------------------- channels (compartment programmes for the cell view)

CHANNELS = [('dna', 'DNA · nucleus', 0, ['Nucleus']), ('mito', 'Mito', 2, ['Mitochondria', 'Inner mitochondria']), ('er', 'ER', 3, ['Endoplasmic reticulum']),
            ('golgi', 'Golgi', 4, ['Golgi apparatus']), ('rna', 'RNA · ribosomes', 5, None), ('vesicles', 'Lysosome · peroxisome', 6, ['Lysosome', 'Peroxisome'])]
_COMP = {}


def compartments(root):
    """Gene symbol → compartments, from Human-GEM's gene table (SwissProt / DeepLoc2 annotations of metabolic genes)."""
    f = pathlib.Path(root) / 'oncology' / 'metabolism' / 'Human-GEM-v2.1.1' / 'genes.tsv'
    if str(f) not in _COMP:
        out = {}
        if f.is_file():
            lines = f.read_text().splitlines(); head = lines[0].split('\t'); si, ci = head.index('geneSymbols'), head.index('compartments')
            for line in lines[1:]:
                c = line.split('\t')
                for g in c[si].split(';'):
                    if g:
                        out.setdefault(g.upper(), set()).update(x for x in c[ci].split(';') if x)
        _COMP[str(f)] = out
    return _COMP[str(f)]


CHANNEL_SOURCE = {'humangem': 'Compartments: Human-GEM gene annotations (SwissProt / DeepLoc2, metabolic genes only); ribosomes: RPL/RPS gene symbols. Cell geometry is illustrative.',
                  'hpa': 'Compartments: Human Protein Atlas subcellular calls (Enhanced, Supported or Approved; main or additional location; all proteins, '
                         'general human annotation, not measured in this cell line); ribosomes: RPL/RPS gene symbols. Cell geometry is illustrative.'}


def channel_genes(root):
    """(source id, layer id → gene set or None for ribosomes): HPA when the annotation index is installed, else Human-GEM."""
    import virtual_cell_annotations as VA
    ix = VA.index(root)
    if ix is not None:
        sets = VA.channel_sets(ix)
        return 'hpa', {cid: (None if labels is None else sets.get(cid, set())) for cid, _, _, labels in CHANNELS}
    comp = compartments(root)
    return 'humangem', {cid: (None if labels is None else {g for g, c in comp.items() if c & set(labels)}) for cid, _, _, labels in CHANNELS}


def channels(root, ref, s):
    """Per compartment: mean change of its panel genes (control-SD units for K-562, log2 units for Tahoe lines) and a
    display gain for the cell view. Geometry stays illustrative; only brightness follows the data."""
    src, sets = channel_genes(root); sd = ref.control_sd if ref.kind == 'k562' else np.ones(len(ref.genes))
    ribo = re.compile(r'^RP[LS]\d+[A-Z]?\d*$')
    out = []
    for cid, name, layer, labels in CHANNELS:
        if src == 'hpa' and cid == 'vesicles':
            name = 'Vesicles · endosome · lysosome · peroxisome'
        idx = [i for i, g in enumerate(ref.genes) if (ribo.match(g) if labels is None else g in sets[cid]) and sd[i] > 0]
        if not idx:
            out.append({'id': cid, 'name': name, 'layer': layer, 'genes': 0, 'score': None, 'gain': 1.0, 'top': []}); continue
        z = s['delta'][idx] / np.maximum(sd[idx], 0.05)
        score = float(np.mean(z)); order = np.argsort(-np.abs(z))[:5]
        out.append({'id': cid, 'name': name, 'layer': layer, 'genes': len(idx), 'score': score, 'gain': float(np.clip(2 ** (3 * score), 0.2, 3.0)),          # display only: ±0.33 SD mean shift = ×2 brightness
                    'top': [{'gene': ref.genes[idx[k]], 'z': float(z[k])} for k in order if abs(z[k]) > 1e-6]})
    return out


# ---------------------------------------------------------------- observe

def summary(root, ref, cid):
    cell = load(root, cid); s = replay(ref, cell['history'])
    top = np.argsort(-np.abs(s['delta']))[:12]
    return {'cell': cell, 'context': context_info(ref), 'state': {
        'overexpressed': s['overexpressed'], 'knockedOut': s['knockedOut'], 'knockedDown': s['knockedDown'], 'drugs': s['drugs'], 'composition': s['composition'], 'evidence': EVIDENCE[s['category']],
        'changed': [{'gene': ref.genes[i], 'delta': float(s['delta'][i])} for i in top if abs(s['delta'][i]) > 1e-9],
        'channels': channels(root, ref, s),
        'channelSource': CHANNEL_SOURCE[channel_genes(root)[0]],
        'levels': {'gene': f'modelled ({len(ref.genes):,}-gene expression panel; DepMap fitness; Human-GEM metabolic genes)', 'cell': 'context and history',
                   'isoform': 'not modelled yet', 'nucleotide': 'not modelled yet'}}}


def observe_expression(ref, cell, genes=None, top=25):
    s = replay(ref, cell['history'])
    out = {'readout': 'expression', 'unit': ref.manifest['expressionUnit'], 'panel': len(ref.genes), 'evidence': EVIDENCE[s['category']],
           'composition': s['composition'], 'contributions': s['contributions'], 'benchmark': _benchmark(ref, s), 'clippedAtZero': s['clipped'],
           'baselineNote': ref.manifest['baselineNote'], 'terms': plugins.terms(_used(ref, s))}
    if s['knockedOut']:
        out['notModelled'] = f"Knockout of {', '.join(s['knockedOut'])} is not reflected in expression: no knockout transcriptome is available. A CRISPRi knockdown is the closest measured perturbation."
    if s['knockedDown']:
        out['knockdownEfficiency'] = [{'gene': g, 'remaining': ref.kd_remaining.get(g)} for g in s['knockedDown']]
        if ref.manifest.get('knockdown'):
            out['knockdownNote'] = ref.manifest['knockdown']['baselineNote']
    rows = lambda idx: [{'gene': ref.genes[i], 'baseline': float(ref.control[i]), 'value': float(s['expression'][i]), 'delta': float(s['delta'][i]),
                         'z': float(s['delta'][i] / ref.control_sd[i]) if ref.control_sd[i] > 0 else None} for i in idx]
    order = np.argsort(-np.abs(s['delta']))
    out['top'] = rows([i for i in order[:top] if abs(s['delta'][i]) > 1e-9])
    if genes:
        want = [str(g).strip().upper() for g in genes][:50]
        out['requested'] = rows([ref.gi[g] for g in want if g in ref.gi]); out['notInPanel'] = [g for g in want if g not in ref.gi]
    return out


def _used(ref, s):
    ids = ['norman2019'] if ref.kind == 'k562' else ['depmap24q4']
    return ids + (['replogle2022'] if s['knockedDown'] else []) + (['tahoe100m'] if s['drugs'] else [])


def _num(x):
    return None if x is None or not np.isfinite(x) else float(x)


def observe_fitness(ref, cell):
    s = replay(ref, cell['history'])
    rows = []
    for g in s['knockedOut'] + s['knockedDown']:
        c, x = _num(ref.depmap.get(g)), _num(ref.depmap_expr.get(g))
        rows.append({'gene': g, 'chronos': c, 'expressionTpmLog1p': x,
                     'call': None if c is None else 'strong dependency' if c <= -1 else 'dependency' if c <= -0.5 else 'little or no effect'})
    out = {'readout': 'fitness', 'evidence': EVIDENCE['A'], 'rows': rows, 'terms': plugins.terms(['depmap24q4']),
           'meaning': f"DepMap Chronos gene effect of a CRISPR knockout on {context_info(ref)['name']} proliferation: 0 = no effect, −1 = median of common essential genes."}
    if s['knockedDown']:
        out['knockdownNote'] = 'Knockdowns are shown with the DepMap knockout score: partial loss is usually milder than knockout.'
    if len(s['knockedOut']) + len(s['knockedDown']) > 1:
        out['notModelled'] = 'Each value is a single-gene knockout measured on its own; the combined effect of several knockouts is not modelled.'
    if s['overexpressed']:
        out['overexpressionNote'] = 'Over-expression has no fitness readout: DepMap measures knockouts only.'
    if not rows:
        out['empty'] = 'No genes are knocked out or down in this cell.'
    return out


def metabolism_key(cell):
    return _sha(sorted(h['gene'] for h in cell['history'] if h['op'] == 'gene_knockout'))[:24]


# ---------------------------------------------------------------- design

def design(ref, cell, target, limit=10, top_pairs=40, include_drugs=True):
    """Rank interventions that move this cell toward a target: every measured over-expression (Norman 2019) and
    knockdown (Replogle 2022) alone, all pairs of over-expressions, and pairs among the best `top_pairs` singles.

    target: {'delta': vector} (another cell's state) or {'up': [...], 'down': [...]} (a direction on named genes).
    Each candidate's effect is the true transition from the current state (the whole history is replayed with the
    candidate appended), so completing a measured pair uses that measurement. Scores: fraction of the squared distance
    removed (cell target) or mean shift along the direction in control-SD units (gene target); cosine is also given.
    """
    here = replay(ref, cell['history'])
    if 'delta' in target:
        need = np.asarray(target['delta'], float) - here['delta']; mask = np.ones(len(need), bool)
    else:
        need = np.zeros(len(ref.genes)); mask = np.zeros(len(need), bool)
        for sign, key in ((1, 'up'), (-1, 'down')):
            for g in target.get(key) or []:
                g = str(g).strip().upper()
                if g in ref.gi:
                    need[ref.gi[g]] = sign; mask[ref.gi[g]] = True
        if not mask.any():
            raise ValueError(f'None of the target genes are in the {len(ref.genes):,}-gene panel.')
    if np.linalg.norm(need[mask]) < 1e-9:
        raise ValueError('This cell already matches the target.')
    used = {h['gene'] for h in cell['history']} | {('drug', h['drug'].lower()) for h in cell['history'] if h['op'] == 'small_molecule'}
    singles = [{'op': 'gene_overexpression', 'gene': g, 'label': f'over-express {g}'} for g in ref.singles if g not in used] + \
              [{'op': 'gene_knockdown', 'gene': g, 'label': f'knock down {g}'} for g in ref.kd if g not in used]
    A = drugs.atlas(ref.root) if include_drugs else None
    if A is not None:
        for key, d in A.drugs.items():
            if ('drug', key) in used:
                continue
            for c in sorted(d['concentrations']):
                if ref.kind == 'k562' or (ref.cellosaurus, key, c) in A.groups:
                    singles.append({'op': 'small_molecule', 'gene': None, 'drug': d['name'], 'concentration': c, 'label': f"{d['name']} {c:g} µM"})
    n2 = float((need[mask] ** 2).sum()); sd = np.maximum(ref.control_sd, 0.05) if ref.kind == 'k562' else np.ones(len(ref.genes))

    def score(ops):
        drugs_in = [o['drug'].lower() for o in ops if o['op'] == 'small_molecule']
        if len(drugs_in) != len(set(drugs_in)):
            return None
        s = replay(ref, cell['history'] + [{k: v for k, v in o.items() if k != 'label'} for o in ops])
        v = (s['delta'] - here['delta'])[mask]; nv = np.linalg.norm(v)
        row = {'ops': ops, 'genes': [o['gene'] or o['drug'] for o in ops],
               'kind': ('single' if len(ops) == 1 else 'pair') + (', measured' if s['category'] == 'A' else ', additive' if 'additive' in s['composition'] else ', predicted'),
               'evidence': EVIDENCE[s['category']], 'cosine': float(v @ need[mask] / (nv * np.sqrt(n2))) if nv > 0 else 0.0}
        if 'delta' in target:
            row['score'] = row['distanceRemoved'] = 1 - float(((need[mask] - v) ** 2).sum()) / n2
        else:
            row['score'] = row['shiftSd'] = float((v / sd[mask]) @ need[mask] / mask.sum())
        return row

    rows = [score([c]) for c in singles]
    best = [r['ops'][0] for r in sorted(rows, key=lambda r: r['score'], reverse=True)[:top_pairs]]
    oe = [c for c in singles if c['op'] == 'gene_overexpression']
    pairs = [(a, b) for i, a in enumerate(oe) for b in oe[i + 1:]]
    seen = {(a['label'], b['label']) for a, b in pairs}
    pairs += [(a, b) for i, a in enumerate(best) for b in best[i + 1:] if (a['label'], b['label']) not in seen and (b['label'], a['label']) not in seen]
    rows += [r for r in (score(list(pr)) for pr in pairs) if r is not None]
    rows.sort(key=lambda r: r['score'], reverse=True)
    n_kd = sum(c['op'] == 'gene_knockdown' for c in singles); n_dr = sum(c['op'] == 'small_molecule' for c in singles)
    space = ', '.join(x for x in [f'{len(oe)} measured over-expressions (Norman 2019)' if oe else '', f'{n_kd:,} measured knockdowns (Replogle 2022)' if n_kd else '',
                                  f'{n_dr:,} drug–dose conditions (Tahoe-100M, {"transferred to K-562" if ref.kind == "k562" else "measured on this line"})' if n_dr else '']
                      if x) + f'; all over-expression pairs and pairs among the best {top_pairs} singles'
    return {'readout': 'design', 'candidates': rows[:int(limit)], 'bestMeasured': [r for r in rows if r['evidence'] == EVIDENCE['A']][:5], 'searched': len(rows),
            'score': 'fraction of distance removed' if 'delta' in target else 'mean shift along the target direction (control-cell SD units)', 'space': space,
            'caution': 'Ranks expression changes only. An expression change is not a therapeutic effect, and additive pairs inherit the additive model\'s error.',
            'terms': plugins.terms((['norman2019'] if ref.kind == 'k562' else ['depmap24q4']) + (['replogle2022'] if n_kd else []) + (['tahoe100m'] if n_dr else []))}


def embedding_knockout_ranking(embed, cells, genes, candidates, target_centroid):
    """GenBio's in-silico knockout target ranking, model-agnostic (used by the GB.Cell and Geneformer plugins).

    embed(cells × genes matrix) → cells × d embedding. For each candidate gene its expression is set to zero in every
    cell; candidates are ranked by how much closer the mean embedding moves to target_centroid (positive = closer).
    """
    gi = {g: i for i, g in enumerate(genes)}
    base = np.linalg.norm(embed(cells).mean(0) - target_centroid)
    rows = []
    for g in candidates:
        if g not in gi:
            continue
        x = np.array(cells, float, copy=True); x[:, gi[g]] = 0
        rows.append({'gene': g, 'shift': float(base - np.linalg.norm(embed(x).mean(0) - target_centroid))})
    return sorted(rows, key=lambda r: r['shift'], reverse=True)


# ---------------------------------------------------------------- actions

def _jobs(root):
    d = pathlib.Path(root) / 'virtualcell' / 'jobs'; d.mkdir(parents=True, exist_ok=True)
    return d


def _job(root, name):
    import os
    log, pid = _jobs(root) / f'{name}.log', _jobs(root) / f'{name}.pid'
    if not log.is_file():
        return None
    running = False
    try:
        os.kill(int(pid.read_text()), 0); running = True; os.waitpid(int(pid.read_text()), os.WNOHANG)
    except (OSError, ValueError, ChildProcessError):
        pass
    return {'running': running, 'log': log.read_text(errors='replace')[-2000:]}


def _spawn(service, name, script, *args):
    import subprocess, sys
    import singlecell_data as SD
    py = SD.python(service)
    if py is None:
        raise ValueError('The science runtime (runtimes/singlecell) is not available.')
    with open(_jobs(service.root) / f'{name}.log', 'w') as f:
        proc = subprocess.Popen([str(py), '-B', '-u', '-W', 'ignore', str(pathlib.Path(__file__).with_name(script)), *map(str, args)], stdout=f,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=True, close_fds=True, cwd=str(pathlib.Path(__file__).parent))
    (_jobs(service.root) / f'{name}.pid').write_text(str(proc.pid))


def _need(service):
    ref = reference(service.root)
    if ref is None:
        raise ValueError('Build the K-562 reference first.')
    return ref


def _cross_check(ref, ko, met):
    """Two independent engines on one question: does losing this gene stop K-562 growing? Disagreement is reported, not resolved."""
    if len(ko) != 1 or met.get('relativeGrowth') is None or not met['genes'][0]['inModel']:
        return None
    c = _num(ref.depmap.get(ko[0]))
    if c is None:
        return None
    model_essential, measured_essential = met['relativeGrowth'] < 0.05, c <= -0.5
    return {'gene': ko[0], 'metabolicModel': 'essential' if model_essential else 'not essential', 'depmap': f'Chronos {c:.2f}',
            'agree': model_essential == measured_essential,
            'note': None if model_essential == measured_essential else
            ('The metabolic model predicts loss of growth but K-562 grows measurably without it: the generic network or medium may lack a bypass the real cell uses (e.g. salvage from serum).'
             if model_essential else 'K-562 depends on this gene but the metabolic model does not: the dependency is likely outside metabolism or beyond what flux balance captures.')}


def _metabolism(service, ref, cell):
    ko = sorted(h['gene'] for h in cell['history'] if h['op'] == 'gene_knockout')
    if not ko:
        return {'readout': 'metabolism', 'empty': 'No genes are knocked out in this cell.', 'evidence': EVIDENCE['B'], 'terms': plugins.terms(['humangem'])}
    key = metabolism_key(cell); out = pathlib.Path(service.root) / 'virtualcell' / 'cache' / 'metabolism' / f'{key}.json'
    base = {'evidence': EVIDENCE['B'], 'terms': plugins.terms(['humangem']), 'knockedOut': ko,
            'meaning': 'Flux-balance feasibility of biomass in a generic human metabolic network under the stated medium; not K-562-specific, not a growth rate.'}
    if out.is_file():
        return {**json.loads(out.read_text()), **base, 'crossCheck': _cross_check(ref, ko, json.loads(out.read_text()))}
    job = _job(service.root, f'met_{key}')
    if job and job['running']:
        return {**base, 'readout': 'metabolism', 'running': True, 'log': job['log']}
    if job and not job['running']:
        return {**base, 'readout': 'metabolism', 'failed': True, 'log': job['log']}
    gem = pathlib.Path(service.root) / 'oncology' / 'metabolism' / 'Human-GEM-v2.1.1'
    if not (gem / 'Human-GEM.json').is_file():
        return {**base, 'readout': 'metabolism', 'unavailable': 'Install Human-GEM in Oncology Universe › Metabolism.'}
    out.parent.mkdir(parents=True, exist_ok=True)
    _spawn(service, f'met_{key}', 'virtual_cell_metabolism.py', gem / 'Human-GEM.json', gem / 'genes.tsv', out, *ko)
    return {**base, 'readout': 'metabolism', 'running': True}


def sparced_genes(root):
    f = pathlib.Path(root) / plugins.RESOURCES['sparced']['localPath']
    return sorted(set(re.findall(r'id="m_([A-Za-z0-9]+)"', f.read_text()))) if f.is_file() else None


def signalling_folds(ref, cell, genes):
    """mRNA fold changes the cell's state implies for SPARCED's genes: 0 for knockouts, otherwise the ratio of predicted
    to baseline expression on the linear scale (expm1 of log1p values), for panel genes expressed at baseline."""
    s = replay(ref, cell['history']); out = {}
    for g in genes:
        if g in s['knockedOut']:
            out[g] = 0.0
        elif g in s['knockedDown'] and g in ref.kd_remaining:
            out[g] = round(float(np.clip(ref.kd_remaining[g], 0.0, 1.0)), 4)
        elif g in ref.gi:
            i = ref.gi[g]; b = ref.lin(ref.control[i])
            if b > 0.05:
                f = float(np.clip(ref.lin(s['expression'][i]) / b, 0.0, 20.0))
                if abs(np.log(max(f, 1e-6))) > 0.05:
                    out[g] = round(f, 4)
    return out


def _signalling(service, ref, cell):
    base = {'readout': 'signalling', 'evidence': EVIDENCE['D'], 'terms': plugins.terms(['sparced']),
            'meaning': 'SPARCED mechanistic signalling (MCF10A parameters) driven by this cell\'s mRNA changes; a hypothesis for K-562, not a measurement.'}
    genes = sparced_genes(service.root)
    if genes is None:
        return {**base, 'unavailable': 'SPARCED is not installed (virtualcell/models/sparced/SPARCED.xml).'}
    fold = signalling_folds(ref, cell, genes)
    if not fold:
        return {**base, 'empty': 'None of SPARCED\'s 141 modelled mRNAs change in this cell.'}
    key = _sha(fold)[:24]; d = pathlib.Path(service.root) / 'virtualcell' / 'cache' / 'signalling'; out = d / f'{key}.json'
    if out.is_file():
        return {**json.loads(out.read_text()), **base}
    job = _job(service.root, f'sig_{key}')
    if job and job['running']:
        return {**base, 'running': True, 'log': job['log']}
    if job:
        return {**base, 'failed': True, 'log': job['log']}
    d.mkdir(parents=True, exist_ok=True); req = d / f'{key}.request.json'; req.write_text(json.dumps({'fold': fold, 'hours': 24}))
    _spawn(service, f'sig_{key}', 'virtual_cell_signalling.py', pathlib.Path(service.root) / plugins.RESOURCES['sparced']['localPath'], req, out)
    return {**base, 'running': True}


# ---------------------------------------------------------------- proteome annotations (virtual_cell_annotations.py)

def _annotations(root):
    import virtual_cell_annotations as VA
    ix = VA.index(root)
    if ix is None:
        raise ValueError('Install the protein annotations first (HPA, UniProt, Reactome; Virtual Cell home › Data and models).')
    return VA, ix


def _expression_row(ref, s, g):
    """Measured baseline and modelled change of one gene in this context, each with its own provenance."""
    i = ref.gi.get(g)
    row = {'inPanel': i is not None, 'unit': ref.manifest['expressionUnit'],
           'baseline': _num(ref.control[i]) if i is not None else None,
           'baselineSource': ref.manifest['baselineNote'] if i is not None else None,
           'change': _num(s['delta'][i]) if i is not None else None, 'changeEvidence': EVIDENCE[s['category']] if i is not None and s['contributions'] else None}
    if ref.kind == 'k562':
        x = _num(ref.depmap_expr.get(g))
        row['depmapBulk'] = None if x is None else {'value': x, 'unit': 'log2(TPM+1), DepMap 24Q4 bulk RNA-seq of parental K-562', 'evidence': EVIDENCE['A']}
    return row


def protein(root, ref, cell, query):
    """One protein in this cell: resolved identifiers, measured expression and fitness here, general localization
    annotations, Reactome pathways and PDB cross-references, every block with its own source."""
    VA, ix = _annotations(root)
    r = VA.resolve(ix, query)
    if r['status'] != 'resolved':
        return {'resolution': r}
    g = r['symbol']; rec = ix.genes[g]; s = replay(ref, cell['history'])
    paths = [{**p, 'name': ix.pathways[p['id']]['name'], 'topLevel': (VA.ancestry(ix, p['id']) or [{}])[0].get('name'),
              'url': 'https://reactome.org/content/detail/' + p['id']} for p in rec['reactome'] if p['id'] in ix.pathways]
    paths.sort(key=lambda p: (p['topLevel'] or '', p['name']))
    c = _num(ref.depmap.get(g))
    return {'resolution': r, 'symbol': g, 'context': context_info(ref)['name'],
            'identifiers': {'uniprot': rec['uniprot'], 'ensembl': rec['ensembl'], 'hgnc': rec['hgnc'], 'synonyms': rec['synonyms'][:12], 'length': rec['length']},
            'expression': {**_expression_row(ref, s, g), 'evidenceBaseline': EVIDENCE['A']},
            'fitness': None if c is None else {'chronos': c, 'evidence': EVIDENCE['A'], 'source': f"DepMap 24Q4 CRISPR knockout in {context_info(ref)['name']}"},
            'localization': {**VA.localization(ix, g), 'humanGem': sorted(compartments(root).get(g, set()))},
            'pathways': paths, 'pathwayEvidence': 'Reactome lowest-level pathways for the UniProt accession (TAS = traceable author statement, IEA = inferred electronically).',
            'structures': {'pdb': rec['pdb'][:40], 'count': len(rec['pdb']), 'source': 'PDB entries cross-referenced by UniProt (experimental structures; coverage of the chain may be partial).'},
            'mechanisticTarget': {'accession': rec['uniprot'][0], 'genes': [g], 'name': g} if rec['uniprot'] else None,
            'abundance': _abundance(root, ref, g),
            'manifest': {'reactomeRelease': ix.manifest.get('reactomeRelease'), 'built': ix.manifest['built']}}


def _abundance(root, ref, g):
    import virtual_cell_proteomics as VP
    rows = VP.protein(root, g, ref.cellosaurus) if getattr(ref, 'cellosaurus', None) else None
    if not rows:
        return 'Protein abundance is not available for this context (no installed proteomics dataset); RNA is not used as a substitute.'
    return {'datasets': rows, 'evidence': EVIDENCE['A'], 'note': 'Separate experiment from the RNA data shown here: different samples, lab and year.'}


def pathway(root, ref, cell, pid):
    """Members of one Reactome pathway with this cell's measured baseline and modelled change for each."""
    VA, ix = _annotations(root)
    if pid not in ix.pathways:
        raise ValueError('Unknown human Reactome pathway.')
    p = ix.pathways[pid]; s = replay(ref, cell['history'])
    import virtual_cell_proteomics as VP
    sets = VP.available(root, ref.cellosaurus) if getattr(ref, 'cellosaurus', None) else []
    prot = {m['id']: VP.values(root, m['id']) for m in sets}
    members = [{'gene': g, **_expression_row(ref, s, g), 'layers': VA.localization(ix, g)['layers'] if g in ix.genes else [],
                'protein': {d: v.get(g) for d, v in prot.items()}, 'structures': len(ix.genes[g]['pdb']) if g in ix.genes else 0,
                'uniprot': (ix.genes[g]['uniprot'] or [None])[0] if g in ix.genes else None} for g in p['genes']]
    return {'id': pid, 'name': p['name'], 'url': 'https://reactome.org/content/detail/' + pid, 'ancestry': VA.ancestry(ix, pid),
            'children': [{'id': c, 'name': ix.pathways[c]['name']} for c in ix.children.get(pid, [])],
            'members': members, 'measured': sum(m['inPanel'] for m in members), 'context': context_info(ref)['name'],
            'proteinDatasets': [{'id': m['id'], 'method': m['method'], 'unit': m['unit']} for m in sets],
            'proteinMeasured': {d: sum(1 for m in members if m['protein'].get(d) is not None) for d in prot},
            'note': 'Membership is curated by Reactome. Values are this context\'s expression; pathway activity is not inferred from them.',
            'reactomeRelease': ix.manifest.get('reactomeRelease')}


def pathway_enrichment(root, ref, cell, top=100):
    """Reactome over-representation among this cell's largest modelled changes, against the genes the context measures."""
    VA, ix = _annotations(root); s = replay(ref, cell['history'])
    if not s['contributions']:
        return {'empty': 'This cell is the unperturbed baseline; there are no changes to test.'}
    sd = np.maximum(ref.control_sd, 0.05) if ref.kind == 'k562' else np.ones(len(ref.genes))
    z = np.abs(s['delta']) / sd; order = [i for i in np.argsort(-z)[:top] if z[i] > 1e-9]
    r = VA.enrichment(ix, [ref.genes[i] for i in order], ref.genes)
    return {**r, 'query': f'{len(order)} genes with the largest modelled change', 'evidence': EVIDENCE[s['category']],
            'note': 'The tested changes are this cell\'s model output; enrichment describes them and is not an independent measurement.'}


# ---------------------------------------------------------------- shared state, registry, transcripts, cell cycle

_CATEGORY = {'A': 'measured', 'B': 'simulation', 'C': 'prediction', 'D': 'prediction'}


def _snapshot_blocks(root, ref, cell):
    """Evidence-typed blocks for a snapshot: the cell's modelled changes (category of the transition used)."""
    import virtual_cell_state as VS
    s = replay(ref, cell['history']); blocks = {}
    if s['contributions']:
        order = [i for i in np.argsort(-np.abs(s['delta']))[:200] if abs(s['delta'][i]) > 1e-9]
        blocks['expressionChange'] = VS.block(_CATEGORY[s['category']], {ref.genes[i]: float(s['delta'][i]) for i in order},
                                              s['composition'], unit=ref.manifest['expressionUnit'] + ' (change vs baseline)', context=context_info(ref)['name'],
                                              note='200 largest changes; the full state is reproducible from the history.')
    if s['knockedOut']:
        blocks['fitness'] = VS.block('measured', {g: _num(ref.depmap.get(g)) for g in s['knockedOut']}, 'DepMap 24Q4 Chronos', unit='Chronos gene effect',
                                     version='24Q4', context=context_info(ref)['name'])
    return blocks, _used(ref, s)


def _dataset_ids(ref):
    return ['depmap24q4'] + (['encode_hepg2_rna'] if getattr(ref, 'cellosaurus', None) == 'CVCL_0027' else [])


def state_dispatch(service, action, p, ref, cell):
    import virtual_cell_state as VS, virtual_cell_registry as VR, virtual_cell_cycle as VC, virtual_cell_transcripts as VT
    root = service.root
    if action in ('vcell_regulatory_runs', 'vcell_regulatory_track'):
        import virtual_cell_regulatory as VG
        rrid = getattr(ref, 'cellosaurus', None) or 'CVCL_0004'
        return VG.listing(root, rrid) if action == 'vcell_regulatory_runs' else VG.get(root, p.get('run'), rrid)
    if action in ('vcell_benchmarks', 'vcell_benchmark_get', 'vcell_benchmark_run'):
        import virtual_cell_benchmarks as VB
        rrid = getattr(ref, 'cellosaurus', None) or 'CVCL_0004'
        if action == 'vcell_benchmarks':
            return {'context': context_info(ref), 'runs': VB.listing(root, rrid), 'protocol': VB.PROTOCOL,
                    'note': 'Benchmark scores describe their recorded test contexts, not necessarily the selected cell.'}
        if action == 'vcell_benchmark_get':
            return VB.load(root, p.get('run'))
        return VB.run(root, p.get('seed', 17), p.get('conditionsPerLine', 8))
    if action == 'vcell_report':
        import virtual_cell_benchmarks as VB
        import virtual_cell_regulatory as VG
        import virtual_cell_state as VSS
        cov = VR.coverage(root, ref); used = sorted({'depmap24q4', 'hpa_subcellular', 'uniprot_human', 'reactome'} | ({'encode_hepg2_rna', 'paxdb_hepg2', 'cellpainting_hepg2'} if ref.kind == 'depmap' else set()))
        rep = {'schema': 'fold.virtualcell.report/1', 'created': VSS.now(), 'context': context_info(ref), 'cell': {k: cell[k] for k in ('id', 'name', 'created', 'history', 'sha256', 'parent', 'reference')},
               'state': {'composition': replay(ref, cell['history'])['composition'], 'evidence': EVIDENCE[replay(ref, cell['history'])['category']]},
               'coverage': cov, 'missing': {k: v for k, v in cov.items() if v['state'] in ('unsupported', 'not_downloaded', 'unmeasured')},
               'datasets': VR.manifest(root, used), 'capabilities': [{k: c[k] for k in ('id', 'validation', 'validationLabel', 'evidence', 'context')} for c in VR.capabilities()],
               'snapshots': VSS.listing(root, cell['id']), 'benchmarks': VB.listing(root, getattr(ref, 'cellosaurus', None) or 'CVCL_0004'),
               'regulatoryRuns': VG.listing(root, getattr(ref, 'cellosaurus', None) or 'CVCL_0004'),
               'software': {'engine': 'Fold Studio Virtual Cell', 'python': __import__('platform').python_version(), 'numpy': np.__version__},
               'note': 'Datasets come from different experiments, samples and years; values are not simultaneous measurements of one cell. Simulations are generic unless stated.'}
        rep['sha256'] = _sha(rep)
        return rep
    if action == 'vcell_coverage':
        return {'context': context_info(ref), 'coverage': VR.coverage(root, ref), 'states': list(VR.COVERAGE)}
    if action == 'vcell_transcripts':
        if getattr(ref, 'cellosaurus', None) != 'CVCL_0027':
            return VR.unsupported('vcell.transcripts', f"No transcript-level dataset is integrated for {context_info(ref)['name']}.", ['a line-matched RNA-seq quantification'])
        if not VT.available(root):
            return VR.unsupported('vcell.transcripts', 'The ENCODE Hep G2 transcript index is not built in this library.', ['encode_hepg2_rna'])
        return {'supported': True, **VT.gene(root, p.get('gene'), p.get('ensembl'))}
    if action == 'vcell_cycle_run':
        r = VC.run(root, p.get('gf', 1.0), p.get('hours', 120))
        return {**{k: v for k, v in r.items() if k != 'series'}, 'series': {k: r['series'][k] for k in r['shown']}}
    if action == 'vcell_snapshot_save':
        blocks, used = _snapshot_blocks(root, ref, cell); sim = None; kind = 'perturbed' if cell['history'] else 'baseline'
        if p.get('regulatoryRun'):
            import virtual_cell_regulatory as VG
            track = VG.get(root, p['regulatoryRun'], getattr(ref, 'cellosaurus', None) or 'CVCL_0004', include_values=True)
            if not track['supported']: raise ValueError(track['reason'])
            transform = {k: track['track'].get(k) for k in ('sum_stat', 'scale', 'clip', 'clip_soft')}
            unit = f"{track['unit']}; {track['track']['identifier']}; {json.dumps(transform, sort_keys=True)}; hg38; 32 bp bins"
            blocks['regulatoryTrack'] = VS.block('prediction', track.pop('values'), track['model'] + ' · job ' + track['run'],
                                                unit=unit, version=track['checkpointSha256'], context=context_info(ref)['name'],
                                                uncertainty=track['uncertainty'], note=track['note'])
            blocks['regulatoryTrack']['provenance'] = track
            kind = 'imported'
        if p.get('simulation'):
            r = VC.load_run(root, str(p['simulation'].get('key', ''))); x = VC.at(r, p['simulation'].get('time', 0))
            sim = {'model': r['model'], 'solver': r['solver'], 'parameters': {'GF': r['gf']}, 'hours': r['hours'], 'runKey': r['key'], 'diagnostics': r['diagnostics'],
                   'time': x['time'], 'timeUnit': 'h', 'phase': x['phase'], 'regime': x['regime'], 'phaseRule': x['phaseRule'], 'variables': x['variables'], 'visualization': x['visual'],
                   'category': 'simulation', 'calibration': r['model']['calibration']}
            kind = 'simulation'; used = used + ['gerard2009']
        return VS.create(root, cell, context_info(ref), p.get('label', ''), kind, blocks, sim, p.get('parent'), VR.manifest(root, sorted(set(used))))
    if action == 'vcell_snapshot_list':
        return VS.listing(root, cell['id'])
    if action == 'vcell_snapshot_get':
        snap = VS.load(root, cell['id'], p.get('snapshot'))
        snap['cellChanged'] = snap['cell']['sha256'] != cell.get('sha256')
        return snap
    if action == 'vcell_snapshot_compare':
        return VS.compare(VS.load(root, cell['id'], p.get('a')), VS.load(root, cell['id'], p.get('b')))
    if action == 'vcell_snapshot_export':
        return VS.export(root, cell['id'], p.get('snapshot'))
    if action == 'vcell_snapshot_import':
        snap = VS.validate_bundle(p.get('bundle'), context_info(ref))
        return VS.create(root, cell, context_info(ref), 'Imported: ' + (snap.get('label') or snap['id'][:8]), 'imported', snap['blocks'], snap.get('simulation'), None, snap.get('datasets'))
    if action == 'vcell_snapshot_delete':
        return VS.delete(root, cell['id'], p.get('snapshot'))
    if action == 'vcell_rna_protein':
        import virtual_cell_proteomics as VP
        sets = VP.available(root, getattr(ref, 'cellosaurus', None) or '')
        if not sets:
            return VR.unsupported('vcell.proteomics', f"No proteomics dataset is integrated for {context_info(ref)['name']}.", ['a line-matched proteomics dataset'])
        if VT.available(root) and ref.cellosaurus == 'CVCL_0027' and p.get('rna', 'encode') == 'encode':
            import sqlite3
            db = sqlite3.connect(f"file:{VT.folder(root) / 'transcripts.sqlite'}?mode=ro", uri=True); rna = {}
            for g, d in db.execute('SELECT gene_name, data FROM tx'):
                t = json.loads(d); reps = list(t['rsem'].values())
                if reps:
                    rna[g] = rna.get(g, 0.0) + sum(x['TPM'] for x in reps) / len(reps)
            db.close(); rna_label = 'ENCODE ENCSR000CPE gene TPM (sum of transcripts, mean of 2 replicates)'
        else:
            rna = {g: float(v) for g, v in ref.depmap_expr.items() if np.isfinite(v)}; rna_label = ref.manifest['expressionUnit']
        out = []
        for m in sets:
            c = VP.rna_protein(root, m['id'], rna)
            pts = c.pop('points', [])
            out.append({**c, 'dataset': m['id'], 'method': m['method'], 'unit': m['unit'], 'sample': pts[::max(1, len(pts) // 600)]})
        return {'rna': rna_label, 'comparisons': out, 'context': context_info(ref)['name']}
    if action in ('vcell_cellflux_status', 'vcell_cellflux_perturbations', 'vcell_cellflux_run', 'vcell_cellflux_job'):
        import virtual_cell_cellflux as VCF
        if action == 'vcell_cellflux_status':
            return VCF.status(root, service)
        if action == 'vcell_cellflux_perturbations':
            return VCF.perturbations(root, p.get('query', ''))
        if action == 'vcell_cellflux_job':
            return VCF.job(root, str(p.get('run', '')))
        if getattr(ref, 'cellosaurus', None) != 'CVCL_0027':
            return VR.unsupported('vcell.microscopy.generative', f"No observed images to start from in {context_info(ref)['name']}.", ['observed Cell Painting for this context'])
        return VCF.start(root, service, str(p.get('key', '')), str(p.get('perturbation', '')), p.get('n', 4), p.get('seed', 0))
    if action in ('vcell_microscopy_list', 'vcell_microscopy_view'):
        import virtual_cell_microscopy as VM
        if getattr(ref, 'cellosaurus', None) != VM.CONTEXT or not VM.subset(root):
            return VR.unsupported('vcell.microscopy', f"No observed Cell Painting images are integrated for {context_info(ref)['name']}.", ['a line-matched Cell Painting subset'])
        if action == 'vcell_microscopy_list':
            return {'supported': True, 'dataset': VM.DATASET, 'channels': VM.CHANNELS, 'images': [{k: v for k, v in x.items() if k != 'channels'} | {'channels': sorted(x['channels'])} for x in VM.images(root)]}
        return {'supported': True, **VM.view(root, str(p.get('key', '')))}
    if action in ('vcell_structures', 'vcell_structure_compare'):
        import virtual_cell_structures as VST
        acc = str(p.get('accession', '')).upper()
        if not re.fullmatch(r'[A-Z0-9]{6,10}(?:-\d+)?', acc):
            raise ValueError('Invalid UniProt accession.')
        if action == 'vcell_structures':
            return VST.for_protein(service, acc)
        return VST.compare(service, acc, str(p.get('a', '')), str(p.get('b', '')), p.get('chainA'), p.get('chainB'))
    raise ValueError('Unsupported virtual cell action.')


STATE_ACTIONS = {'vcell_coverage', 'vcell_transcripts', 'vcell_cycle_run', 'vcell_snapshot_save', 'vcell_snapshot_list', 'vcell_snapshot_get',
                 'vcell_snapshot_compare', 'vcell_snapshot_export', 'vcell_snapshot_import', 'vcell_snapshot_delete', 'vcell_structures', 'vcell_structure_compare', 'vcell_rna_protein',
                 'vcell_microscopy_list', 'vcell_microscopy_view', 'vcell_report',
                 'vcell_cellflux_status', 'vcell_cellflux_perturbations', 'vcell_cellflux_run', 'vcell_cellflux_job',
                 'vcell_benchmarks', 'vcell_benchmark_get', 'vcell_benchmark_run', 'vcell_regulatory_runs', 'vcell_regulatory_track'}


def dispatch(service, action, p):
    root = service.root
    if action == 'vcell_registry':
        import virtual_cell_registry as VR
        return {'datasets': VR.datasets(root, verify=bool(p.get('verify'))), 'capabilities': VR.capabilities(), 'validation': VR.VALIDATION, 'providers': list(VR.PROVIDERS)}
    if action in ('vcell_results_list', 'vcell_result_get'):
        import virtual_cell_results as VRS
        return VRS.listing(root) if action == 'vcell_results_list' else VRS.get(root, str(p.get('source', '')), str(p.get('result', '')))
    if action == 'vcell_transcripts_build':
        job = _job(root, 'transcripts')
        if job and job['running']:
            raise ValueError('The transcript index is already being built.')
        _spawn(service, 'transcripts', 'virtual_cell_transcripts.py', root)
        return dispatch(service, 'vcell_catalog', p)
    if action == 'vcell_annotations_install':
        job = _job(root, 'annotations')
        if job and job['running']:
            raise ValueError('The annotations are already being installed.')
        _spawn(service, 'annotations', 'virtual_cell_annotations.py', root)
        return dispatch(service, 'vcell_catalog', p)
    if action == 'vcell_catalog':
        ref = reference(root); job = _job(root, 'reference'); A = drugs.atlas(root)
        lines = sorted(A.lines.values(), key=lambda x: x['name']) if A else []
        import virtual_cell_annotations as VA
        ix = VA.index(root); dm = pathlib.Path(root) / 'oncology' / 'depmap' / '24Q4' / 'expression.json'
        measured = set(json.loads(dm.read_text())['models']) if dm.is_file() else set()
        profiles = [{'id': c, 'name': 'Hep G2' if c == 'CVCL_0027' else c, 'cellosaurus': c, 'depmap': v['depmap'], 'kind': 'depmap'} for c, v in PROFILES.items() if v['depmap'] in measured]
        return {'contexts': [{'id': 'K562', **CONTEXTS['K562'], 'kind': 'k562'}] + profiles + [{'id': l['cellosaurus'], 'name': l['name'], 'cellosaurus': l['cellosaurus'], 'depmap': l['depmap'], 'kind': 'tahoe', 'conditions': l['conditions']} for l in lines],
                'operations': {'perturb': list(OPS), 'unsupported': UNSUPPORTED, 'observe': ['expression', 'fitness', 'metabolism', 'signalling'], 'design': ['toward a cell', 'toward a gene direction']},
                'reference': {'ready': ref is not None, 'manifest': ref.manifest if ref else None, 'job': job,
                              'singles': sorted(ref.singles) if ref else [], 'inputsReady': (pathlib.Path(root) / plugins.RESOURCES['norman2019']['localPath']).is_file()},
                'drugs': {'ready': A is not None, 'filesDone': A.files_done if A else 0, 'complete': A.complete if A else False, 'benchmark': A.benchmark if A else None,
                          'list': sorted(({'name': d['name'], 'concentrations': sorted(d['concentrations']), 'lines': len(d['lines'])} for d in A.drugs.values()), key=lambda x: x['name'].lower()) if A else [],
                          'job': _job(root, 'tahoe')},
                'annotations': {'ready': ix is not None, 'manifest': ix.manifest if ix else None, 'job': _job(root, 'annotations')},
                'transcripts': {'ready': (pathlib.Path(root) / 'virtualcell' / 'data' / 'encode_hepg2' / 'transcripts.sqlite').is_file(),
                                'inputsReady': (pathlib.Path(root) / 'virtualcell' / 'data' / 'encode_hepg2' / 'original' / 'ENCFF416RHJ.tsv').is_file(), 'job': _job(root, 'transcripts')},
                'resources': plugins.status(root), 'evidence': EVIDENCE}
    if action == 'vcell_reference_build':
        job = _job(root, 'reference')
        if job and job['running']:
            raise ValueError('The reference is already being built.')
        _spawn(service, 'reference', 'virtual_cell_reference.py', root)
        return dispatch(service, 'vcell_catalog', p)
    if action == 'vcell_list':
        return listing(root)
    if action == 'vcell_delete':
        return delete(root, p.get('id'))
    if action == 'vcell_create':
        context = str(p.get('context', 'K562')); ref = context_reference(root, context)
        return summary(root, ref, create(root, ref, p.get('name', ''), context)['id'])
    cell = load(root, p.get('id')); ref = context_reference(root, cell['context'])
    if action == 'vcell_get':
        return summary(root, ref, cell['id'])
    if action == 'vcell_perturb':
        return summary(root, ref, perturb(root, ref, cell['id'], str(p.get('op', '')), p.get('gene'), p.get('drug'), p.get('concentration'))['id'])
    if action == 'vcell_branch':
        return summary(root, ref, branch(root, cell['id'], p.get('step'), p.get('name', ''))['id'])
    if action == 'vcell_observe':
        kind = str(p.get('readout', 'expression'))
        if kind == 'expression':
            return observe_expression(ref, cell, p.get('genes'))
        if kind == 'fitness':
            return observe_fitness(ref, cell)
        if kind == 'metabolism':
            return _metabolism(service, ref, cell)
        if kind == 'signalling':
            return _signalling(service, ref, cell)
        raise ValueError('Unknown readout.')
    if action in STATE_ACTIONS:
        return state_dispatch(service, action, p, ref, cell)
    if action == 'vcell_protein':
        return protein(root, ref, cell, p.get('query'))
    if action == 'vcell_pathway':
        return pathway(root, ref, cell, str(p.get('pathway', '')))
    if action == 'vcell_enrichment':
        return pathway_enrichment(root, ref, cell)
    if action == 'vcell_design':
        t = p.get('target') or {}
        if t.get('cellId'):
            other = load(root, t['cellId'])
            if other['context'] != cell['context']:
                raise ValueError('The target cell must be in the same cell context.')
            target = {'delta': replay(ref, other['history'])['delta'].tolist()}
        else:
            target = {'up': list(t.get('up') or [])[:200], 'down': list(t.get('down') or [])[:200]}
        r = design(ref, cell, target, min(int(p.get('limit', 10)), 50), include_drugs=bool(p.get('drugs', True)))
        if t.get('cellId'):
            r['target'] = {'cellId': t['cellId']}
        return r
    raise ValueError('Unsupported virtual cell action.')
