"""Drug responses for the virtual cell from the Tahoe-100M pseudobulk atlas (virtual_cell_tahoe.py builds the matrices).

Each condition is a DESeq2 log2 fold change of drug-treated versus DMSO cells for one cell line × drug × concentration
× plate. Replicate plates are averaged. Three kinds of answer, each labelled:

  measured     the cell line was treated with this drug at this concentration                    A · Experimental
  interpolated a concentration between two measured ones: per-gene linear in log10(concentration)  C · AI prediction
  transferred  a cell line Tahoe never treated (K-562): the mean response of every Tahoe line at
               that drug and concentration                                                         C · AI prediction
Doses outside the measured range are refused. Benchmarks (benchmark()) score interpolation by predicting each line's
middle dose from its outer doses, and transfer by leave-one-line-out, on the genes each signature changes most.
"""
import json
import pathlib

import numpy as np

FOLDER = ('virtualcell', 'data', 'tahoe100m')
_CACHE = {}


class Atlas:
    def __init__(self, folder):
        folder = pathlib.Path(folder)
        self.genes = json.loads((folder / 'genes.json').read_text()); self.gi = {g: i for i, g in enumerate(self.genes)}
        self.conditions = json.loads((folder / 'conditions.json').read_text())
        prog = json.loads((folder / 'progress.json').read_text())
        self.complete = len(prog['done']) == 1026; self.files_done = len(prog['done'])
        # local runs allocate 90,000 rows; the Modal build writes exactly one row per condition
        shape = ((folder / 'lfc.f16').stat().st_size // (2 * len(self.genes)), len(self.genes))
        self.lfc = np.memmap(folder / 'lfc.f16', np.float16, 'r', shape=shape)
        self.se = np.memmap(folder / 'se.f16', np.float16, 'r', shape=shape)
        self.groups, self.lines, self.drugs = {}, {}, {}
        for i, c in enumerate(self.conditions):
            key = (c['cellosaurus'], c['drug'].lower(), float(c['concentration']))
            self.groups.setdefault(key, []).append(i)
            self.lines.setdefault(c['cellosaurus'], {'cellosaurus': c['cellosaurus'], 'name': c['cellLine'], 'depmap': c['depmap'], 'conditions': 0})['conditions'] += 1
            self.drugs.setdefault(c['drug'].lower(), {'name': c['drug'], 'concentrations': set(), 'lines': set()})
            self.drugs[c['drug'].lower()]['concentrations'].add(float(c['concentration'])); self.drugs[c['drug'].lower()]['lines'].add(c['cellosaurus'])
        self._memo = {}
        bm = folder / 'benchmark.json'
        self.benchmark = json.loads(bm.read_text()) if bm.is_file() else None

    def drug(self, name):
        d = self.drugs.get(str(name).strip().lower())
        if d is None:
            raise ValueError(f'{name} is not one of the {len(self.drugs)} Tahoe-100M drugs.')
        return d

    def active(self, rows, z=4.0):
        """Number of genes the condition changes clearly (|log2FC / SE| > z on the first plate): a measure of drug activity."""
        a, b = np.asarray(self.lfc[rows[0]], np.float32), np.asarray(self.se[rows[0]], np.float32)
        with np.errstate(all='ignore'):
            return int(np.nansum(np.abs(a / b) > z))

    def z(self, row):
        with np.errstate(all='ignore'):
            return np.asarray(self.lfc[row], np.float32) / np.asarray(self.se[row], np.float32)

    def top_genes(self, rows, top):
        """The `top` genes most significantly changed (|log2FC/SE|, averaged over plates): robust to the huge, noisy
        fold changes of barely expressed genes."""
        with np.errstate(all='ignore'):
            z = np.nanmean(np.abs(np.vstack([self.z(r) for r in rows])), axis=0)
        return np.argsort(-np.nan_to_num(z))[:top]

    def _mean(self, rows):
        with np.errstate(all='ignore'):
            return np.nanmean(np.asarray(self.lfc[sorted(rows)], np.float32), axis=0)

    def measured(self, line, drug, conc):
        rows = self.groups.get((line, drug.lower(), float(conc)))
        return None if not rows else (self._mean(rows), len(rows))

    def response(self, line, drug, conc):
        key = ('r', line, str(drug).strip().lower(), float(conc))
        if key not in self._memo:
            self._memo[key] = self._response(line, drug, conc)
        return self._memo[key]

    def transfer(self, drug, conc, exclude=None):
        key = ('t', str(drug).strip().lower(), float(conc), exclude)
        if key not in self._memo:
            self._memo[key] = self._transfer(drug, conc, exclude)
        return self._memo[key]

    def _response(self, line, drug, conc):
        """(log2FC vector over self.genes, how, category, note) for a Tahoe line."""
        d = self.drug(drug); conc = float(conc)
        doses = sorted(c for c in d['concentrations'] if (line, d['name'].lower(), c) in self.groups)
        if not doses:
            raise ValueError(f'{d["name"]} was not tested on this cell line in Tahoe-100M.')
        m = self.measured(line, d['name'], conc)
        if m is not None:
            return m[0], f'measured ({m[1]} plate{"s" if m[1] > 1 else ""})', 'A', None
        if not doses[0] < conc < doses[-1]:
            raise ValueError(f'{conc:g} µM is outside the measured range for {d["name"]} on this line ({doses[0]:g}–{doses[-1]:g} µM).')
        lo = max(c for c in doses if c < conc); hi = min(c for c in doses if c > conc)
        w = (np.log10(conc) - np.log10(lo)) / (np.log10(hi) - np.log10(lo))
        a, b = self.measured(line, d['name'], lo)[0], self.measured(line, d['name'], hi)[0]
        return (1 - w) * a + w * b, f'interpolated between {lo:g} and {hi:g} µM (log-linear)', 'C', 'interpolation'

    def _transfer(self, drug, conc, exclude=None):
        d = self.drug(drug); conc = float(conc)
        rows = [r for (line, dn, c), rs in self.groups.items() if dn == d['name'].lower() and c == conc and line != exclude for r in rs]
        if not rows:
            measured = sorted(d['concentrations'])
            raise ValueError(f'{d["name"]} was measured at {", ".join(f"{c:g}" for c in measured)} µM; transfer uses measured concentrations only.')
        n = len({self.conditions[r]['cellosaurus'] for r in rows})
        return self._mean(rows), f'mean response of {n} Tahoe cell lines (transferred)', 'C', 'transfer'


def atlas(root):
    folder = pathlib.Path(root).joinpath(*FOLDER)
    if not (folder / 'conditions.json').is_file():
        return None
    key = (str(folder), (folder / 'progress.json').stat().st_mtime)
    if key not in _CACHE:
        _CACHE.clear(); _CACHE[key] = Atlas(folder)
    return _CACHE[key]


def _r(a, b):
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 10:
        return None
    a, b = a[ok] - a[ok].mean(), b[ok] - b[ok].mean(); d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else None


def benchmark(root, samples=600, top=200, min_active=30, seed=0):
    """Held-out accuracy of interpolation and transfer on active conditions (≥ min_active genes with |log2FC/SE| > 4),
    scored on the `top` genes each observed signature changes most. Replicate plates give the noise ceiling (top genes
    chosen on one plate, scored against the other)."""
    A = atlas(root); rng = np.random.default_rng(seed)
    keys = list(A.groups); rng.shuffle(keys)
    interp, transfer, noise, inactive, generic = [], [], [], 0, []
    # generic-response baseline: the mean of 3,000 random conditions (any drug, any line); transfer must beat it to
    # show drug-specific information rather than a shared stress response
    with np.errstate(all='ignore'):
        gen = np.nanmean(np.asarray(A.lfc[np.sort(rng.choice(len(A.conditions), 3000, replace=False))], np.float32), axis=0)
    for line, dn, c in keys:
        if len(transfer) >= samples:
            break
        rows = A.groups[(line, dn, c)]
        if A.active(rows) < min_active:
            inactive += 1; continue
        obs = A.measured(line, dn, c)[0]; top_idx = A.top_genes(rows, top)
        if any(l != line for (l, d2, c2) in A.groups if d2 == dn and c2 == c):
            transfer.append(_r(A.transfer(dn, c, exclude=line)[0][top_idx], obs[top_idx])); generic.append(_r(gen[top_idx], obs[top_idx]))
        if len(rows) >= 2:
            a, b = np.asarray(A.lfc[rows[0]], np.float32), np.asarray(A.lfc[rows[1]], np.float32)
            t1 = A.top_genes(rows[:1], top); noise.append(_r(a[t1], b[t1]))
        doses = sorted(cc for (l, d2, cc) in A.groups if l == line and d2 == dn)
        if len(doses) >= 3 and doses[0] < c < doses[-1]:
            lo, hi = max(x for x in doses if x < c), min(x for x in doses if x > c)
            w = (np.log10(c) - np.log10(lo)) / (np.log10(hi) - np.log10(lo))
            p = (1 - w) * A.measured(line, dn, lo)[0] + w * A.measured(line, dn, hi)[0]
            interp.append(_r(p[top_idx], obs[top_idx]))
    s = lambda v: {'mean': float(np.mean([x for x in v if x is not None])) if any(x is not None for x in v) else None, 'n': sum(x is not None for x in v)}
    out = {'metric': f'Pearson r of log2 fold changes on the {top} genes each observed signature changes most significantly (|log2FC/SE|); active conditions only (≥ {min_active} genes with |log2FC/SE| > 4)',
           'interpolation': s(interp), 'transfer': s(transfer), 'genericResponse': s(generic), 'replicatePlates': s(noise), 'inactiveSkipped': inactive,
           'lines': len(A.lines), 'filesDone': A.files_done, 'complete': A.complete}
    (pathlib.Path(root).joinpath(*FOLDER) / 'benchmark.json').write_text(json.dumps(out, indent=1))
    return out
