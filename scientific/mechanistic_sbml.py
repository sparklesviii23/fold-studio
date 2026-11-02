"""SBML Level 2/3 core reader and compiler for the Mechanistic Biology Lab.

Reads compartments, species, global and local parameters, function definitions,
initial assignments, assignment and rate rules and reactions, and compiles them
into one generated Python right-hand-side function for SciPy integrators.

Semantics follow the SBML specification for the supported subset:
- species with reactions are integrated as amounts; a species symbol in maths
  means concentration (amount / compartment size) unless hasOnlySubstanceUnits;
- kinetic laws are rates in substance per time;
- boundary or constant species are not changed by reactions.

Anything outside the subset (events, delays, algebraic rules, fast reactions,
variable stoichiometry, conversion factors, non-constant compartments) is
listed in `unsupported`; such a model is not executable and is never run
with the offending part silently dropped.
"""
import hashlib, math, re
import xml.etree.ElementTree as ET
import numpy as np

AVOGADRO = 6.02214076e23
BASE_UNITS = {'ampere', 'avogadro', 'becquerel', 'candela', 'coulomb', 'dimensionless', 'farad', 'gram', 'gray', 'henry', 'hertz', 'item', 'joule', 'katal', 'kelvin', 'kilogram',
              'litre', 'lumen', 'lux', 'metre', 'mole', 'newton', 'ohm', 'pascal', 'radian', 'second', 'siemens', 'sievert', 'steradian', 'tesla', 'volt', 'watt', 'weber'}


class SBMLError(ValueError):
    pass


def tag(e):
    return e.tag.split('}', 1)[-1]


def kids(e, name=None):
    return [c for c in e if name is None or tag(c) == name]


def child(e, name):
    for c in e:
        if tag(c) == name:
            return c
    return None


def listof(model, name):
    e = child(model, name)
    return kids(e) if e is not None else []


def number(text):
    return float(text.strip())


IDENTIFIER = re.compile(r'https?://identifiers\.org/([^/]+)/(.+)$|urn:miriam:([^:]+):(.+)$')


def annotations(e):
    """identifiers.org / MIRIAM cross-references grouped by qualifier."""
    out = []
    ann = child(e, 'annotation')
    if ann is None:
        return out
    for desc in ann.iter():
        if tag(desc) != 'Description':
            continue
        for qual in desc:
            for li in qual.iter():
                if tag(li) != 'li':
                    continue
                uri = next((v for k, v in li.attrib.items() if k.endswith('resource')), '')
                m = IDENTIFIER.match(uri)
                if m:
                    db, acc = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
                    out.append({'qualifier': tag(qual), 'database': db.replace('obo.', '').lower(), 'accession': acc.replace('%3A', ':'), 'uri': uri})
    return out


# ---------------------------------------------------------------------------
# MathML → Python source, plus a human-readable infix rendering.

FUNCS = {'exp': 'math.exp', 'ln': 'math.log', 'abs': 'abs', 'floor': 'math.floor', 'ceiling': 'math.ceil', 'sin': 'math.sin', 'cos': 'math.cos', 'tan': 'math.tan',
         'arcsin': 'math.asin', 'arccos': 'math.acos', 'arctan': 'math.atan', 'sinh': 'math.sinh', 'cosh': 'math.cosh', 'tanh': 'math.tanh', 'factorial': '_factorial'}
RELATIONS = {'eq': '==', 'neq': '!=', 'lt': '<', 'gt': '>', 'leq': '<=', 'geq': '>='}
PRETTY_REL = {'eq': '=', 'neq': '≠', 'lt': '<', 'gt': '>', 'leq': '≤', 'geq': '≥'}


def _factorial(x):
    return math.gamma(x + 1)


class MathCompiler:
    def __init__(self, resolve, functions, delay=None):
        self.resolve = resolve          # id -> python expression
        self.functions = functions      # function id -> python name
        self.delay = delay              # (argument node, compiled delay) -> python expression, or None if delays are unsupported
        self.used = set()               # symbol ids referenced

    def compile(self, node):
        name = tag(node)
        if name == 'math':
            return self.compile(kids(node)[0])
        if name == 'cn':
            kind = node.get('type', 'real')
            parts = [t for t in node.itertext()]
            if kind in ('e-notation', 'rational'):
                sep = [c for c in node if tag(c) == 'sep']
                head = (node.text or '').strip(); tail = (sep[0].tail or '').strip() if sep else '1'
                value = float(head) * 10 ** float(tail) if kind == 'e-notation' else float(head) / float(tail)
            else:
                value = number(''.join(parts))
            return repr(float(value))
        if name == 'ci':
            ident = (node.text or '').strip()
            self.used.add(ident)
            return self.resolve(ident)
        if name == 'csymbol':
            url = node.get('definitionURL', '')
            if url.endswith('/time'):
                return 't'
            if url.endswith('/avogadro'):
                return repr(AVOGADRO)
            raise SBMLError('Unsupported MathML csymbol: ' + url.rsplit('/', 1)[-1])
        if name in ('pi', 'exponentiale', 'true', 'false', 'infinity', 'notanumber'):
            return {'pi': repr(math.pi), 'exponentiale': repr(math.e), 'true': 'True', 'false': 'False', 'infinity': 'math.inf', 'notanumber': 'math.nan'}[name]
        if name == 'piecewise':
            pieces = kids(node, 'piece'); other = child(node, 'otherwise')
            expr = self.compile(kids(other)[0]) if other is not None else 'math.nan'
            for piece in reversed(pieces):
                value, cond = kids(piece)
                expr = '(' + self.compile(value) + ' if ' + self.compile(cond) + ' else ' + expr + ')'
            return expr
        if name == 'apply':
            return self.apply(node)
        if name == 'semantics':
            return self.compile(kids(node)[0])
        raise SBMLError('Unsupported MathML element: ' + name)

    def apply(self, node):
        op, *args = kids(node)
        o = tag(op)
        qualifiers = {tag(a): a for a in args if tag(a) in ('degree', 'logbase')}
        args = [a for a in args if tag(a) not in ('degree', 'logbase', 'bvar')]
        c = [self.compile(a) for a in args]
        if o == 'plus':
            return '(' + ' + '.join(c) + ')' if c else '0.0'
        if o == 'minus':
            return '(-' + c[0] + ')' if len(c) == 1 else '(' + c[0] + ' - ' + c[1] + ')'
        if o == 'times':
            return '(' + ' * '.join(c) + ')' if c else '1.0'
        if o == 'divide':
            return '(' + c[0] + ' / ' + c[1] + ')'
        if o == 'power':
            return '(' + c[0] + ' ** ' + c[1] + ')'
        if o == 'root':
            degree = self.compile(kids(qualifiers['degree'])[0]) if 'degree' in qualifiers else '2.0'
            return '(' + c[0] + ' ** (1.0 / ' + degree + '))'
        if o == 'log':
            base = self.compile(kids(qualifiers['logbase'])[0]) if 'logbase' in qualifiers else '10.0'
            return '(math.log(' + c[0] + ') / math.log(' + base + '))'
        if o in FUNCS:
            return FUNCS[o] + '(' + c[0] + ')'
        if o in RELATIONS:
            return '(' + (' and '.join('(' + c[i] + ' ' + RELATIONS[o] + ' ' + c[i + 1] + ')' for i in range(len(c) - 1))) + ')'
        if o in ('and', 'or'):
            return '(' + (' ' + o + ' ').join(c) + ')'
        if o == 'xor':
            return '(' + ' != '.join('bool(' + x + ')' for x in c) + ')'
        if o == 'not':
            return '(not ' + c[0] + ')'
        if o == 'ci':
            fid = (op.text or '').strip()
            if fid not in self.functions:
                raise SBMLError('Unknown function: ' + fid)
            return self.functions[fid] + '(' + ', '.join(c) + ')'
        if o == 'csymbol' and op.get('definitionURL', '').endswith('/delay'):
            if self.delay is None:
                raise SBMLError('Delay differential equations are not supported here.')
            return self.delay(args[0], c[1])
        raise SBMLError('Unsupported MathML operator: ' + o)


def pretty(node, names=lambda i: i):
    """Readable infix with Unicode operators, for equation inspection."""
    name = tag(node)
    if name in ('math', 'semantics'):
        return pretty(kids(node)[0], names)
    if name == 'cn':
        kind = node.get('type', 'real')
        if kind == 'e-notation':
            sep = [c for c in node if tag(c) == 'sep']
            return (node.text or '').strip() + 'e' + (sep[0].tail or '').strip()
        text = ''.join(node.itertext()).strip()
        try:
            v = float(text); return str(int(v)) if v == int(v) and abs(v) < 1e6 else text
        except ValueError:
            return text
    if name == 'ci':
        return names((node.text or '').strip())
    if name == 'csymbol':
        return node.get('definitionURL', '').rsplit('/', 1)[-1]
    if name in ('pi', 'exponentiale', 'true', 'false', 'infinity', 'notanumber'):
        return {'pi': 'π', 'exponentiale': 'e', 'infinity': '∞', 'notanumber': 'NaN'}.get(name, name)
    if name == 'piecewise':
        parts = []
        for piece in kids(node, 'piece'):
            v, cnd = kids(piece); parts.append(pretty(v, names) + ' if ' + pretty(cnd, names))
        other = child(node, 'otherwise')
        if other is not None:
            parts.append(pretty(kids(other)[0], names) + ' otherwise')
        return '{ ' + '; '.join(parts) + ' }'
    if name != 'apply':
        return name
    op, *args = kids(node)
    o = tag(op)
    args = [a for a in args if tag(a) not in ('degree', 'logbase', 'bvar')]
    p = [pretty(a, names) for a in args]
    wrap = lambda s: s if re.fullmatch(r'[\w.]+', s) else '(' + s + ')'
    if o == 'plus':
        return ' + '.join(p)
    if o == 'minus':
        return '−' + wrap(p[0]) if len(p) == 1 else p[0] + ' − ' + wrap(p[1])
    if o == 'times':
        return ' · '.join(wrap(x) for x in p)
    if o == 'divide':
        return wrap(p[0]) + ' / ' + wrap(p[1])
    if o == 'power':
        return wrap(p[0]) + '^' + wrap(p[1])
    if o in RELATIONS:
        return (' ' + PRETTY_REL[o] + ' ').join(p)
    if o == 'ci':
        return (op.text or '').strip() + '(' + ', '.join(p) + ')'
    return o + '(' + ', '.join(p) + ')'


# ---------------------------------------------------------------------------

class Model:
    """A compiled SBML model. Parameters are addressed by id ('k1') or, for
    reaction-local parameters, 'reactionId.localId'."""

    def __init__(self, text, source=None):
        self.text = text
        self.sha256 = hashlib.sha256(text.encode()).hexdigest()
        self.source = source or {}
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            raise SBMLError('Not valid XML: ' + str(e))
        if tag(root) != 'sbml':
            raise SBMLError('Not an SBML document.')
        self.level, self.version = int(root.get('level', 0)), int(root.get('version', 0))
        if self.level not in (2, 3):
            raise SBMLError('Only SBML Level 2 and Level 3 are supported.')
        model = child(root, 'model')
        if model is None:
            raise SBMLError('The SBML document has no model.')
        self.id = model.get('id') or 'model'
        self.name = model.get('name') or self.id
        self.unsupported = []
        self.cross_references = annotations(model)
        self._read(model)
        self._compile()

    # -- reading -----------------------------------------------------------
    def _read(self, model):
        L3 = self.level == 3
        self.units = {u.get('id'): [{k: x.get(k) for k in ('kind', 'exponent', 'scale', 'multiplier')} for x in u.iter() if tag(x) == 'unit'] for u in listof(model, 'listOfUnitDefinitions')}
        self.model_units = {k: model.get(k) for k in ('substanceUnits', 'timeUnits', 'volumeUnits', 'extentUnits') if model.get(k)}
        self.functions = {}
        for f in listof(model, 'listOfFunctionDefinitions'):
            lam = child(child(f, 'math'), 'lambda') if child(f, 'math') is not None else None
            if lam is None:
                self.unsupported.append('Function ' + f.get('id') + ' has no lambda.'); continue
            bvars = [(child(b, 'ci').text or '').strip() for b in kids(lam, 'bvar')]
            body = [c for c in lam if tag(c) != 'bvar'][0]
            self.functions[f.get('id')] = {'args': bvars, 'body': body}
        self.compartments = []
        for c in listof(model, 'listOfCompartments'):
            size = c.get('size') or c.get('volume')
            self.compartments.append({'id': c.get('id'), 'name': c.get('name') or c.get('id'), 'size': float(size) if size is not None else (None if L3 else 1.0),
                                      'constant': c.get('constant', 'true') == 'true', 'units': c.get('units'), 'dimensions': c.get('spatialDimensions', '3')})
            if c.get('constant', 'true') != 'true':
                self.unsupported.append('Compartment ' + c.get('id') + ' changes size.')
        self.species = []
        for s in listof(model, 'listOfSpecies'):
            amount, conc = s.get('initialAmount'), s.get('initialConcentration')
            self.species.append({'id': s.get('id'), 'name': s.get('name') or s.get('id'), 'compartment': s.get('compartment'),
                                 'initialAmount': float(amount) if amount is not None else None, 'initialConcentration': float(conc) if conc is not None else None,
                                 'hasOnlySubstanceUnits': s.get('hasOnlySubstanceUnits', 'false') == 'true', 'boundary': s.get('boundaryCondition', 'false') == 'true',
                                 'constant': s.get('constant', 'false') == 'true', 'units': s.get('substanceUnits') or s.get('units'), 'references': annotations(s)})
            if s.get('conversionFactor'):
                self.unsupported.append('Species ' + s.get('id') + ' uses a conversion factor.')
        if model.get('conversionFactor'):
            self.unsupported.append('The model uses a conversion factor.')
        self.parameters = []
        for p in listof(model, 'listOfParameters'):
            v = p.get('value')
            self.parameters.append({'id': p.get('id'), 'name': p.get('name') or p.get('id'), 'value': float(v) if v is not None else None, 'units': p.get('units'),
                                    'constant': p.get('constant', 'true') == 'true', 'scope': 'global', 'references': annotations(p)})
        self.initial_assignments = [(a.get('symbol'), child(a, 'math')) for a in listof(model, 'listOfInitialAssignments')]
        self.assignment_rules, self.rate_rules = [], []
        for r in listof(model, 'listOfRules'):
            kind = tag(r)
            var = r.get('variable') or r.get('compartment') or r.get('species') or r.get('name')
            if kind in ('assignmentRule', 'speciesConcentrationRule', 'compartmentVolumeRule', 'parameterRule') and r.get('type', 'scalar') == 'scalar':
                self.assignment_rules.append((var, child(r, 'math')))
            elif kind == 'rateRule' or r.get('type') == 'rate':
                self.rate_rules.append((var, child(r, 'math')))
            else:
                self.unsupported.append('Algebraic rule' + (' for ' + var if var else '') + '.')
        self.reactions = []
        for r in listof(model, 'listOfReactions'):
            if r.get('fast') == 'true':
                self.unsupported.append('Reaction ' + r.get('id') + ' is marked fast.')
            def refs(listname):
                out = []
                for sr in listof(r, listname):
                    if child(sr, 'stoichiometryMath') is not None:
                        self.unsupported.append('Reaction ' + r.get('id') + ' uses variable stoichiometry.')
                    st = sr.get('stoichiometry')
                    out.append({'species': sr.get('species'), 'stoichiometry': float(st) if st is not None else 1.0})
                    if L3 and st is None and sr.get('id'):
                        self.unsupported.append('Reaction ' + r.get('id') + ' has stoichiometry set elsewhere.')
                return out
            law = child(r, 'kineticLaw')
            local = []
            if law is not None:
                for lp in listof(law, 'listOfParameters') + listof(law, 'listOfLocalParameters'):
                    v = lp.get('value')
                    local.append({'id': lp.get('id'), 'name': lp.get('name') or lp.get('id'), 'value': float(v) if v is not None else None, 'units': lp.get('units'), 'scope': r.get('id')})
            math_el = child(law, 'math') if law is not None else None
            if math_el is None:
                self.unsupported.append('Reaction ' + r.get('id') + ' has no kinetic law.')
            self.reactions.append({'id': r.get('id'), 'name': r.get('name') or r.get('id'), 'reversible': r.get('reversible', 'true') == 'true',
                                   'reactants': refs('listOfReactants'), 'products': refs('listOfProducts'),
                                   'modifiers': [m.get('species') for m in listof(r, 'listOfModifiers')], 'math': math_el, 'local': local, 'references': annotations(r)})
        self.events = []
        for ev in listof(model, 'listOfEvents'):
            trig, dl = child(ev, 'trigger'), child(ev, 'delay')
            tm = child(trig, 'math') if trig is not None else None
            if tm is None:
                self.unsupported.append('Event ' + str(ev.get('id')) + ' has no trigger.'); continue
            if child(ev, 'priority') is not None:
                self.unsupported.append('Event ' + str(ev.get('id')) + ' has a priority (simultaneous-event ordering is not supported).')
            self.events.append({'id': ev.get('id') or f'event{len(self.events) + 1}', 'trigger': tm, 'delay': child(dl, 'math') if dl is not None else None,
                                'initialValue': trig.get('initialValue', 'true') == 'true', 'persistent': trig.get('persistent', 'true') == 'true',
                                'fromTrigger': ev.get('useValuesFromTriggerTime', 'true') == 'true',
                                'assign': [(a.get('variable'), child(a, 'math')) for a in listof(ev, 'listOfEventAssignments')]})
        if listof(model, 'listOfConstraints'):
            self.unsupported.append('Constraints are not checked.')
        for p in self.parameters:
            if p['value'] is None and not any(v == p['id'] for v, _ in self.initial_assignments + self.assignment_rules):
                self.unsupported.append('Parameter ' + p['id'] + ' has no value.')
        for c in self.compartments:
            if c['size'] is None and not any(v == c['id'] for v, _ in self.initial_assignments + self.assignment_rules):
                self.unsupported.append('Compartment ' + c['id'] + ' has no size.')

    # -- compiling ---------------------------------------------------------
    def _compile(self):
        self.executable = not self.unsupported
        ruled = {v for v, _ in self.assignment_rules}
        rated = {v for v, _ in self.rate_rules}
        self.compartment_size = {c['id']: c['size'] for c in self.compartments}
        sp = {s['id']: s for s in self.species}
        # State: reaction-driven species (as amounts) and rate-ruled symbols (as their own value).
        self.state = []
        for s in self.species:
            if s['id'] in ruled:
                continue
            if s['id'] in rated:
                self.state.append({'id': s['id'], 'kind': 'rate-rule'})
            elif not s['boundary'] and not s['constant'] and any(s['id'] in [x['species'] for x in r['reactants'] + r['products']] for r in self.reactions):
                self.state.append({'id': s['id'], 'kind': 'amount'})
        for p in self.parameters:
            if p['id'] in rated:
                self.state.append({'id': p['id'], 'kind': 'rate-rule'})
        self.state_index = {s['id']: i for i, s in enumerate(self.state)}
        # Parameter vector: global then local; the solver passes it explicitly so sweeps never mutate the model.
        self.param_ids = [p['id'] for p in self.parameters if p['id'] not in ruled and p['id'] not in rated]
        self.param_ids += [r['id'] + '.' + lp['id'] for r in self.reactions for lp in r['local']]
        self.param_info = {p['id']: p for p in self.parameters}
        for r in self.reactions:
            for lp in r['local']:
                self.param_info[r['id'] + '.' + lp['id']] = lp
        self.param_index = {pid: i for i, pid in enumerate(self.param_ids)}
        self.fixed_ids = [s['id'] for s in self.species if s['id'] not in self.state_index and s['id'] not in ruled]
        self.default_values = np.array([self.param_info[pid]['value'] if self.param_info[pid]['value'] is not None else math.nan for pid in self.param_ids]
                                       + [self._initial_symbol(s) for s in self.species if s['id'] in self.fixed_ids], float)
        self._initial_code = []
        # Stoichiometry over amount-state species.
        self.stoichiometry = np.zeros((len(self.state), len(self.reactions)))
        for j, r in enumerate(self.reactions):
            for ref in r['reactants']:
                i = self.state_index.get(ref['species'])
                if i is not None and self.state[i]['kind'] == 'amount':
                    self.stoichiometry[i, j] -= ref['stoichiometry']
            for ref in r['products']:
                i = self.state_index.get(ref['species'])
                if i is not None and self.state[i]['kind'] == 'amount':
                    self.stoichiometry[i, j] += ref['stoichiometry']
        if not self.executable:
            return
        py = lambda i: 'v_' + re.sub(r'\W', '_', i)
        lines = ['def _rhs(t, y, p):']
        body, observe = [], []
        for c in self.compartments:
            body.append(f"{py(c['id'])} = {c['size']!r}")
        for pid in self.param_ids:
            if '.' not in pid:
                body.append(f"{py(pid)} = p[{self.param_index[pid]}]")
        for s in self.state:
            i = self.state_index[s['id']]
            if s['kind'] == 'amount':
                spc = sp[s['id']]
                body.append(f"{py(s['id'])} = y[{i}]" if spc['hasOnlySubstanceUnits'] else f"{py(s['id'])} = y[{i}] / {py(spc['compartment'])}")
            else:
                body.append(f"{py(s['id'])} = y[{i}]")
        # Constant / boundary species are fixed at their initial symbol value (held in `self.fixed`).
        # Species no reaction changes (boundary, constant or modifier-only) are read from the
        # tail of the parameter vector, so their initial values can be overridden per run.
        for k, sid in enumerate(self.fixed_ids):
            body.append(f"{py(sid)} = p[{len(self.param_ids) + k}]")
        functions = {fid: 'f_' + re.sub(r'\W', '_', fid) for fid in self.functions}
        header = []
        for fid, f in self.functions.items():
            comp = MathCompiler(lambda i, args=f['args']: ('a_' + re.sub(r'\W', '_', i)) if i in args else py(i), functions)
            header.append(f"def {functions[fid]}({', '.join('a_' + re.sub(r'\W', '_', a) for a in f['args'])}):\n    return {comp.compile(f['body'])}")
        self.delays = []                                  # compiled delay-time expressions; history lookups go through _hist
        def delay(arg, tau):
            ident = (arg.text or '').strip() if tag(arg) == 'ci' else None
            if ident not in self.state_index:
                raise SBMLError('delay() is supported only on a state variable (a species or rate-ruled symbol).')
            i = self.state_index[ident]; spc = sp.get(ident)
            self.delays.append(tau)
            conv = f" / {py(spc['compartment'])}" if spc and self.state[i]['kind'] == 'amount' and not spc['hasOnlySubstanceUnits'] else ''
            return f'(_hist({i}, t - ({tau})){conv})'
        compiler = MathCompiler(py, functions, delay)
        for var, m in self._ordered_rules():
            body.append(f"{py(var)} = {compiler.compile(m)}")
        self.reaction_source = []
        for j, r in enumerate(self.reactions):
            scope = {lp['id']: f"p[{self.param_index[r['id'] + '.' + lp['id']]}]" for lp in r['local']}
            rc = MathCompiler(lambda i, scope=scope: scope.get(i, py(i)), functions, delay)
            expr = rc.compile(r['math'])
            r['depends'] = sorted(rc.used)
            body.append(f"_r{j} = {expr}")
        rr = {var: MathCompiler(py, functions, delay).compile(m) for var, m in self.rate_rules}
        out = []
        for s in self.state:
            i = self.state_index[s['id']]
            if s['kind'] == 'amount':
                terms = [f"({float(self.stoichiometry[i, j])!r}) * _r{j}" for j in range(len(self.reactions)) if self.stoichiometry[i, j] != 0]
                out.append(' + '.join(terms) if terms else '0.0')
            else:
                out.append(rr[s['id']])
        rates = '[' + ', '.join(f'_r{j}' for j in range(len(self.reactions))) + ']'
        symbols = [s['id'] for s in self.species] + [v for v, _ in self.assignment_rules if v not in sp]
        src = '\n'.join(header) + '\n' + '\n'.join(lines + ['    ' + b for b in body] + [f"    return [{', '.join(out)}], {rates}, [{', '.join(py(x) for x in symbols)}]"])
        pre = [b for b in body if not b.startswith('_r')]         # symbol values without reaction rates
        ev_src = []
        if self.events or self.delays:
            ec = MathCompiler(py, functions, delay)
            trig = [ec.compile(e['trigger']) for e in self.events]
            ev_src.append('def _events(t, y, p):\n' + '\n'.join('    ' + b for b in pre) + f"\n    return [{', '.join('bool(' + x + ')' for x in trig)}]")
            for k, e in enumerate(self.events):
                vals = [ec.compile(m) for _, m in e['assign']]
                dly = ec.compile(e['delay']) if e['delay'] is not None else '0.0'
                ev_src.append(f'def _assign{k}(t, y, p):\n' + '\n'.join('    ' + b for b in pre) + f"\n    return [{', '.join(vals)}], {dly}")
            ev_src.append('def _taus(t, y, p):\n' + '\n'.join('    ' + b for b in pre) + f"\n    return [{', '.join(self.delays)}]")
            for e in self.events:
                for var, _ in e['assign']:
                    if var in self.state_index:
                        continue
                    if var in self.param_index and '.' not in var or var in self.fixed_ids:
                        continue
                    raise SBMLError(f'Event {e["id"]} assigns {var}, which is not a species, rate-ruled symbol or parameter.')
        src += '\n' + '\n'.join(ev_src)
        namespace = {'math': math, '_factorial': _factorial, '_hist': lambda i, tt: (_ for _ in ()).throw(SBMLError('delay() history is not available outside a simulation.'))}
        try:
            exec(compile(src, '<sbml:' + self.id + '>', 'exec'), namespace)
        except SyntaxError as e:
            raise SBMLError('Could not compile the model: ' + str(e))
        self._fn = namespace['_rhs']
        self._namespace = namespace
        self._events_fn = namespace.get('_events'); self._taus_fn = namespace.get('_taus')
        self._assign_fns = [namespace[f'_assign{k}'] for k in range(len(self.events))] if self.events else []
        self._initial_code = [(var, MathCompiler(lambda i: 'env[' + repr(i) + ']', functions).compile(m)) for var, m in self.initial_assignments]
        self.symbols = symbols
        self.source_code = src

    def _ordered_rules(self):
        """Assignment rules in dependency order (SBML forbids cycles)."""
        pending = list(self.assignment_rules); done, ordered = set(), []
        targets = {v for v, _ in pending}
        while pending:
            progressed = False
            for var, m in list(pending):
                deps = {(c.text or '').strip() for c in m.iter() if tag(c) == 'ci'} & targets
                if deps <= done:
                    ordered.append((var, m)); done.add(var); pending.remove((var, m)); progressed = True
            if not progressed:
                raise SBMLError('Assignment rules form a cycle.')
        return ordered

    def _initial_symbol(self, s):
        size = self.compartment_size.get(s['compartment']) or 1.0
        if s['initialConcentration'] is not None:
            return s['initialConcentration'] * size if s['hasOnlySubstanceUnits'] else s['initialConcentration']
        if s['initialAmount'] is not None:
            return s['initialAmount'] if s['hasOnlySubstanceUnits'] else s['initialAmount'] / size
        return 0.0

    # -- evaluation --------------------------------------------------------
    def parameter_vector_value(self, pid, overrides=None):
        if pid in (overrides or {}):
            return float(overrides[pid])
        if pid not in self.param_index:
            raise SBMLError('Unknown parameter: ' + pid)
        return float(self.default_values[self.param_index[pid]])

    def prepare(self, overrides=None, initial=None):
        """Resolve (y0, p): defaults, user overrides, then SBML initial assignments in dependency order."""
        p = self.default_values.copy()
        for pid, value in (overrides or {}).items():
            if pid not in self.param_index:
                raise SBMLError('Unknown parameter: ' + pid)
            if not np.isfinite(float(value)):
                raise SBMLError('Parameter ' + pid + ' must be a finite number.')
            p[self.param_index[pid]] = float(value)
        sp = {s['id']: s for s in self.species}
        for sid in (initial or {}):
            if sid not in sp:
                raise SBMLError('Unknown species: ' + sid)
            if not np.isfinite(float(initial[sid])) or float(initial[sid]) < 0:
                raise SBMLError('Initial value for ' + sid + ' must be a finite, non-negative number.')
        symbols = {s['id']: float((initial or {}).get(s['id'], self._initial_symbol(s))) for s in self.species}
        if self._initial_code:
            env = {**{c['id']: c['size'] for c in self.compartments}, **{pid: v for pid, v in zip(self.param_ids, p) if '.' not in pid}, **symbols}
            pending = list(self._initial_code)
            for _ in range(len(pending) + 1):
                for var, code in list(pending):
                    try:
                        env[var] = float(eval(code, self._namespace, {'env': env, 't': 0.0}))
                        pending.remove((var, code))
                    except (KeyError, TypeError):
                        continue
            if pending:
                raise SBMLError('Could not evaluate initial assignments for: ' + ', '.join(v for v, _ in pending))
            for var, _ in self._initial_code:
                if var in self.param_index and var not in (overrides or {}):
                    p[self.param_index[var]] = env[var]
                elif var in symbols and var not in (initial or {}):
                    symbols[var] = env[var]
        for k, sid in enumerate(self.fixed_ids):
            p[len(self.param_ids) + k] = symbols[sid]
        if np.isnan(p).any():
            missing = [pid for pid, v in zip(self.param_ids, p) if math.isnan(v)]
            raise SBMLError('Parameters without values: ' + ', '.join(missing))
        y = np.zeros(len(self.state))
        for s in self.state:
            i = self.state_index[s['id']]
            if s['id'] in sp:
                spc = sp[s['id']]
                y[i] = symbols[s['id']] * (self.compartment_size.get(spc['compartment']) or 1.0) if s['kind'] == 'amount' and not spc['hasOnlySubstanceUnits'] else symbols[s['id']]
            else:
                y[i] = p[self.param_index[s['id']]] if s['id'] in self.param_index else self.param_info[s['id']]['value']
        return y, p

    def rhs(self, t, y, p):
        return self._fn(t, y, p)[0]

    def evaluate(self, t, y, p):
        dy, rates, symbols = self._fn(t, y, p)
        return np.asarray(dy, float), np.asarray(rates, float), np.asarray(symbols, float)

    # -- description -------------------------------------------------------
    def describe(self):
        names = {s['id']: s['name'] for s in self.species}
        sp = {s['id']: s for s in self.species}
        def fmt(refs):
            return ' + '.join((('' if r['stoichiometry'] == 1 else f"{r['stoichiometry']:g} ") + r['species']) for r in refs) or '∅'
        reactions = []
        for r in self.reactions:
            reactions.append({'id': r['id'], 'name': r['name'], 'scheme': fmt(r['reactants']) + (' ⇌ ' if r['reversible'] else ' → ') + fmt(r['products']),
                              'rate': pretty(r['math']) if r['math'] is not None else '', 'modifiers': r['modifiers'],
                              'parameters': [r['id'] + '.' + lp['id'] for lp in r['local']] + [d for d in r.get('depends', []) if d in self.param_info and '.' not in d],
                              'species': sorted({x['species'] for x in r['reactants'] + r['products']} | set(r['modifiers'])), 'references': r['references']})
        odes = []
        for s in self.state:
            if s['kind'] != 'amount':
                rule = next(m for v, m in self.rate_rules if v == s['id'])
                odes.append({'species': s['id'], 'equation': 'd' + s['id'] + '/dt = ' + pretty(rule)}); continue
            i = self.state_index[s['id']]; terms = []
            for j, r in enumerate(self.reactions):
                c = self.stoichiometry[i, j]
                if c:
                    terms.append(('− ' if c < 0 else '+ ') + ('' if abs(c) == 1 else f'{abs(c):g}·') + r['id'])
            size = '' if sp[s['id']]['hasOnlySubstanceUnits'] else ' (amount; concentration = amount / ' + sp[s['id']]['compartment'] + ')'
            odes.append({'species': s['id'], 'equation': 'd' + s['id'] + '/dt = ' + ' '.join(terms).lstrip('+ ') + size})
        params = []
        for pid in self.param_ids:
            info = self.param_info[pid]
            used_by = [r['id'] for r in self.reactions if pid in [r['id'] + '.' + lp['id'] for lp in r['local']] or ('.' not in pid and pid in r.get('depends', []))]
            params.append({'id': pid, 'name': info['name'], 'value': info['value'], 'units': info['units'], 'scope': info['scope'], 'usedBy': used_by,
                           'provenance': 'model file' if info['value'] is not None else 'unknown'})
        return {'id': self.id, 'name': self.name, 'level': self.level, 'version': self.version, 'sha256': self.sha256, 'executable': self.executable,
                'unsupported': self.unsupported, 'units': self._unit_summary(), 'compartments': self.compartments,
                'species': [{'id': s['id'], 'name': s['name'], 'compartment': s['compartment'], 'initial': self._initial_symbol(s), 'boundary': s['boundary'],
                             'state': s['id'] in self.state_index, 'references': s['references']} for s in self.species],
                'parameters': params, 'reactions': reactions, 'odes': odes,
                'rules': [{'variable': v, 'equation': v + ' = ' + pretty(m)} for v, m in self.assignment_rules] + [{'variable': v, 'equation': 'd' + v + '/dt = ' + pretty(m)} for v, m in self.rate_rules],
                'references': self.cross_references, 'source': self.source}

    def _unit_summary(self):
        def describe_unit(uid, default):
            defs = self.units.get(uid)
            if defs and len(defs) == 1 and defs[0]['kind'] == 'second' and defs[0].get('exponent') in (None, '1') and defs[0].get('scale') in (None, '0'):
                mult = float(defs[0].get('multiplier') or 1)
                return {1.0: 'second', 60.0: 'minute', 3600.0: 'hour', 86400.0: 'day'}.get(mult, f'{mult:g} × second')
            if uid in BASE_UNITS:
                return uid
            if uid in self.units:
                return ' · '.join((('10^' + u['scale'] + ' ') if u.get('scale') not in (None, '0') else '') + u['kind'] + (('^' + u['exponent']) if u.get('exponent') not in (None, '1') else '') for u in self.units[uid])
            return default
        default_time = 'second' if self.level == 2 else self.model_units.get('timeUnits', 'unspecified')
        return {'substance': describe_unit(self.model_units.get('substanceUnits', 'substance'), 'mole' if self.level == 2 else 'unspecified'),
                'time': describe_unit(self.model_units.get('timeUnits', 'time'), default_time),
                'volume': describe_unit(self.model_units.get('volumeUnits', 'volume'), 'litre' if self.level == 2 else 'unspecified')}

    def write(self, overrides=None, initial=None):
        """SBML text with parameter values and initial concentrations replaced; everything else untouched."""
        for prefix, uri in re.findall(r'xmlns(?::(\w+))?="([^"]+)"', self.text[:4000]):
            ET.register_namespace(prefix or '', uri)
        root = ET.fromstring(self.text)
        model = child(root, 'model')
        for p in listof(model, 'listOfParameters'):
            if p.get('id') in (overrides or {}):
                p.set('value', repr(float(overrides[p.get('id')])))
        for r in listof(model, 'listOfReactions'):
            law = child(r, 'kineticLaw')
            if law is None:
                continue
            for lp in listof(law, 'listOfParameters') + listof(law, 'listOfLocalParameters'):
                key = r.get('id') + '.' + lp.get('id')
                if key in (overrides or {}):
                    lp.set('value', repr(float(overrides[key])))
        for s in listof(model, 'listOfSpecies'):
            if s.get('id') in (initial or {}):
                attr = 'initialAmount' if s.get('initialAmount') is not None else 'initialConcentration'
                s.set(attr, repr(float(initial[s.get('id')])))
        return ET.tostring(root, encoding='unicode')
