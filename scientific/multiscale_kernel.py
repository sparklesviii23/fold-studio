"""fold Scientific Simulation Kernel: contracts, provenance and one-way coupling.

Each stage of a multiscale experiment is a model with a declared contract
(family, equations, inputs and outputs with units, scale, assumptions,
evidence). The coordinator runs stages in order and moves values along
declared links: every link converts units through multiscale_units (refusing
incompatible dimensions) or through an explicit, described transformation, and
every transfer is recorded. Results keep their own evidence category, and any
output can be traced back to the equations, parameters and sources behind it.

Only one-way coupling is implemented: a validated output becomes an input
downstream. Iterative and strong coupling are not attempted.
"""
import hashlib, json, math, time
from dataclasses import dataclass, field, asdict
import numpy as np
from scipy.stats import qmc, spearmanr
import multiscale_units as units

EVIDENCE = {
    'experimental': 'Experimentally observed',
    'physics': 'Physics-simulated',
    'statistical': 'Statistically predicted',
    'hypothesis': 'Parameterized hypothesis',
    'illustrative': 'Illustrative',
}
PARAM_KINDS = ('literature', 'database', 'derived', 'hypothetical', 'assumption')


class CouplingError(ValueError):
    pass


@dataclass
class Param:
    name: str
    value: float
    unit: str
    kind: str                      # literature | database | derived | hypothetical | assumption
    description: str = ''
    source: dict = field(default_factory=dict)   # citation, doi, quote, context
    range: tuple | None = None     # (lo, hi) explored in uncertainty analysis
    log: bool = True

    def __post_init__(self):
        if self.kind not in PARAM_KINDS:
            raise CouplingError('Unknown parameter kind: ' + self.kind)
        units.dimension(self.unit)
        if not math.isfinite(self.value):
            raise CouplingError(self.name + ' must be finite.')
        if self.kind in ('literature', 'database') and not self.source:
            raise CouplingError(self.name + ' is marked as literature but has no source.')


@dataclass
class Entity:
    id: str
    molecular_class: str
    name: str
    accessions: dict
    sequence_sha256: str | None = None
    provenance: str = ''


@dataclass
class Compartment:
    id: str
    name: str
    volume: float | None
    volume_unit: str | None
    kind: str                      # well-mixed | spatial | count
    source: str = ''


@dataclass
class Contract:
    id: str
    title: str
    family: str
    equations: list
    inputs: dict                   # name -> unit
    outputs: dict                  # name -> unit
    scale: str
    timescale: str
    assumptions: list
    limitations: list
    evidence: str                  # key of EVIDENCE
    engine: str

    def __post_init__(self):
        for u in list(self.inputs.values()) + list(self.outputs.values()):
            units.dimension(u)
        if self.evidence not in EVIDENCE:
            raise CouplingError('Unknown evidence category: ' + self.evidence)


@dataclass
class Link:
    source: str                    # 'stage.output'
    target: str                    # 'stage.input'
    transform: object = None       # optional callable(value, params) -> (value, description)
    assumption: str = ''


@dataclass
class Stage:
    contract: Contract
    run: object                    # callable(inputs, params, seed) -> dict
    params: list


def _value_out(result, name, unit):
    v = result['outputs'].get(name)
    if v is None:
        raise CouplingError(f'Stage did not produce {name}.')
    if not math.isfinite(v):
        raise CouplingError(f'{name} is not finite.')
    return v


def run_chain(stages, links, overrides=None, seed=1, light=False):
    """Execute stages in order. `overrides` maps 'stage.param' to a value (in the param's unit)."""
    by_id = {s.contract.id: s for s in stages}
    results, transfers, events = {}, [], []
    for stage in stages:
        c = stage.contract
        params = {}
        for p in stage.params:
            v = (overrides or {}).get(c.id + '.' + p.name, p.value)
            params[p.name] = float(v)
        inputs = {}
        for link in (l for l in links if l.target.split('.')[0] == c.id):
            sid, out = link.source.split('.', 1); _, inp = link.target.split('.', 1)
            if sid not in results:
                raise CouplingError(f'{c.id} needs {link.source}, which has not run.')
            src_unit = by_id[sid].contract.outputs[out]; dst_unit = c.inputs[inp]
            value = _value_out(results[sid], out, src_unit)
            if link.transform:
                converted, how = link.transform(value, params)
            else:
                converted, how = units.convert(value, src_unit, dst_unit), (f'unit conversion {src_unit} → {dst_unit}' if src_unit != dst_unit else 'same unit')
            inputs[inp] = converted
            transfers.append({'from': link.source, 'to': link.target, 'value': value, 'unit': src_unit, 'converted': converted, 'convertedUnit': dst_unit,
                              'how': how, 'assumption': link.assumption})
        missing = set(c.inputs) - set(inputs)
        if missing:
            raise CouplingError(f'{c.id} is missing inputs: ' + ', '.join(sorted(missing)))
        started = time.time()
        r = stage.run(inputs, params, seed, light) if light else stage.run(inputs, params, seed)
        r['seconds'] = time.time() - started
        for name, unit in c.outputs.items():
            _value_out(r, name, unit)
        r['inputs'] = inputs; r['params'] = params
        for e in r.get('events', []):
            events.append({**e, 'model': c.id})
        results[c.id] = r
    return {'results': results, 'transfers': transfers, 'events': events}


def trace(stages, links, run, target):
    """Causal chain for 'stage.output': the stage's equations, parameters (with provenance)
    and, recursively, the upstream outputs that fed its inputs."""
    by_id = {s.contract.id: s for s in stages}
    seen = set()

    def node(ref, depth):
        sid, out = ref.split('.', 1)
        stage = by_id[sid]; c = stage.contract; r = run['results'][sid]
        item = {'output': ref, 'value': r['outputs'][out], 'unit': c.outputs[out], 'model': c.title, 'family': c.family, 'evidence': EVIDENCE[c.evidence],
                'equations': c.equations, 'assumptions': c.assumptions,
                'parameters': [{'name': p.name, 'value': r['params'][p.name], 'unit': p.unit, 'kind': p.kind, 'description': p.description, 'source': p.source} for p in stage.params],
                'upstream': []}
        if sid in seen or depth > 12:
            return item
        seen.add(sid)
        for t in (t for t in run['transfers'] if t['to'].split('.')[0] == sid):
            up = node(t['from'], depth + 1)
            up['transfer'] = t
            item['upstream'].append(up)
        return item
    return node(target, 0)


def uncertainty(stages, links, outputs, samples=32, seed=7):
    """Latin-hypercube propagation over every hypothetical parameter that declares a range."""
    space = [(s.contract.id + '.' + p.name, p) for s in stages for p in s.params if p.kind in ('hypothetical', 'assumption') and p.range]
    if not space:
        return {'parameters': [], 'samples': []}
    u = qmc.LatinHypercube(d=len(space), seed=seed).random(samples)
    rows, values = [], {o: [] for o in outputs}
    for k, row in enumerate(u):
        over = {}
        for (key, p), x in zip(space, row):
            lo, hi = p.range
            over[key] = math.exp(math.log(lo) + x * (math.log(hi) - math.log(lo))) if p.log else lo + x * (hi - lo)
        run = run_chain(stages, links, over, seed=seed + k, light=True)
        rows.append(over)
        for o in outputs:
            sid, name = o.split('.', 1)
            values[o].append(run['results'][sid]['outputs'][name])
    X = np.array([[r[key] for key, _ in space] for r in rows])
    # Only causal ancestors can influence an output; correlations with downstream parameters are sampling noise.
    parents = {}
    for l in links:
        parents.setdefault(l.target.split('.')[0], set()).add(l.source.split('.')[0])
    def ancestors(sid, seen=None):
        seen = seen if seen is not None else set()
        for p in parents.get(sid, ()):
            if p not in seen:
                seen.add(p); ancestors(p, seen)
        return seen | {sid}
    summary, sensitivity = {}, {}
    for o in outputs:
        y = np.array(values[o])
        summary[o] = {'p5': float(np.percentile(y, 5)), 'p50': float(np.percentile(y, 50)), 'p95': float(np.percentile(y, 95))}
        upstream = ancestors(o.split('.')[0])
        sensitivity[o] = sorted(({'parameter': key, 'spearman': float(spearmanr(X[:, j], y).statistic) if np.ptp(y) > 0 else 0.0} for j, (key, _) in enumerate(space) if key.split('.')[0] in upstream),
                                key=lambda s: -abs(s['spearman']))
    return {'parameters': [{'name': key, 'unit': p.unit, 'range': list(p.range), 'log': p.log} for key, p in space], 'samples': samples, 'seed': seed,
            'values': values, 'summary': summary, 'sensitivity': sensitivity,
            'method': 'Latin hypercube over hypothetical and assumed parameters (log-uniform where marked); Spearman rank correlation'}


def describe(stages, links):
    return {'stages': [{**asdict(s.contract), 'parameters': [asdict(p) for p in s.params]} for s in stages],
            'links': [{'source': l.source, 'target': l.target, 'assumption': l.assumption, 'transform': bool(l.transform)} for l in links]}


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()
