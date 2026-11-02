"""Reusable biochemical mechanism components that compose into SBML Level 3.

A component declares its governing rate law, the unit each parameter must
carry, its assumptions and, where relevant, a source. `compose` checks that
every parameter has a value in the unit its role requires, that every symbol in
a rate law is declared, and then writes standard SBML, so composed networks run
through the same compiler and export as ordinary model files.

Concentrations are nM in a compartment measured in litres (species symbols are
concentrations); copy-number networks use amount-only species ('item').
"""
import math
from xml.sax.saxutils import escape

TIME_UNITS = {'second': ('second', 1), 'minute': ('second', 60), 'hour': ('second', 3600)}

# Unit ids → SBML unit definitions (kind, exponent, scale, multiplier).
def unit_definitions(time):
    base, mult = TIME_UNITS[time]
    t = lambda e: ('second', e, 0, mult)
    return {
        'nmole': [('mole', 1, -9, 1)],
        'nM': [('mole', 1, -9, 1), ('litre', -1, 0, 1)],
        'per_time': [t(-1)],
        'per_nM_per_time': [('mole', -1, -9, 1), ('litre', 1, 0, 1), t(-1)],
        'nM_per_time': [('mole', 1, -9, 1), ('litre', -1, 0, 1), t(-1)],
        'items_per_time': [('item', 1, 0, 1), t(-1)],
        'litre_per_time': [('litre', 1, 0, 1), t(-1)],
        'dimensionless': [('dimensionless', 1, 0, 1)],
        'time': [t(1)],
    }

UNIT_LABEL = {'nM': 'nM', 'per_time': '1/{t}', 'per_nM_per_time': '1/(nM·{t})', 'nM_per_time': 'nM/{t}', 'items_per_time': 'molecules/{t}', 'litre_per_time': 'L/{t}', 'dimensionless': '—'}

COMPONENTS = {
    'binding': {'name': 'Reversible binding', 'scheme': 'A + B ⇌ AB', 'species': ['A', 'B', 'AB'], 'rate': 'kon·A·B − koff·AB',
                'parameters': {'kon': 'per_nM_per_time', 'koff': 'per_time'},
                'assumptions': ['Well-mixed compartment', 'Mass-action kinetics', 'Kd = koff/kon'], 'source': 'Law of mass action'},
    'mass_action_enzyme': {'name': 'Enzyme catalysis (mass action)', 'scheme': 'E + S ⇌ ES → E + P', 'species': ['E', 'S', 'ES', 'P'],
                           'rate': 'k1·E·S − k_1·ES ; kcat·ES', 'parameters': {'k1': 'per_nM_per_time', 'k_1': 'per_time', 'kcat': 'per_time'},
                           'assumptions': ['Well-mixed', 'Irreversible catalytic step', 'No product inhibition'], 'source': 'Briggs & Haldane 1925, doi:10.1042/bj0190338'},
    'michaelis_menten': {'name': 'Michaelis–Menten rate law', 'scheme': 'S → P (catalysed by E)', 'species': ['E', 'S', 'P'], 'rate': 'kcat·E·S / (Km + S)',
                         'parameters': {'kcat': 'per_time', 'Km': 'nM'}, 'assumptions': ['Quasi-steady state: E ≪ S + Km', 'Enzyme not consumed'],
                         'source': 'Michaelis & Menten 1913; Briggs & Haldane 1925'},
    'competitive_inhibition': {'name': 'Competitive inhibition (rate law)', 'scheme': 'S → P (E, inhibited by I)', 'species': ['E', 'S', 'P', 'I'],
                               'rate': 'kcat·E·S / (Km·(1 + I/Ki) + S)', 'parameters': {'kcat': 'per_time', 'Km': 'nM', 'Ki': 'nM'},
                               'assumptions': ['Quasi-steady state', 'Inhibitor binds free enzyme only', 'Free inhibitor ≈ total inhibitor'], 'source': 'Standard steady-state treatment (e.g. Cornish-Bowden, Fundamentals of Enzyme Kinetics)'},
    'synthesis': {'name': 'Synthesis (zero order)', 'scheme': '∅ → X', 'species': ['X'], 'rate': 'k', 'parameters': {'k': 'nM_per_time'},
                  'assumptions': ['Constant production rate'], 'source': None},
    'templated_synthesis': {'name': 'Templated synthesis', 'scheme': '∅ → X (from template T)', 'species': ['T', 'X'], 'rate': 'k·T', 'parameters': {'k': 'per_time'},
                            'assumptions': ['Production proportional to template, e.g. translation from mRNA'], 'source': None},
    'repressed_synthesis': {'name': 'Repressed synthesis (Hill)', 'scheme': '∅ → X (repressed by R)', 'species': ['R', 'X'], 'rate': 'k·K^n / (K^n + R^n)',
                            'parameters': {'k': 'nM_per_time', 'K': 'nM', 'n': 'dimensionless'}, 'assumptions': ['Rapid repressor binding equilibrium', 'Phenomenological Hill coefficient'], 'source': 'Hill 1910'},
    'degradation': {'name': 'First-order degradation', 'scheme': 'X → ∅', 'species': ['X'], 'rate': 'k·X', 'parameters': {'k': 'per_time'},
                    'assumptions': ['Exponential decay, half-life ln2/k'], 'source': None},
    'modification': {'name': 'Reversible modification (MM)', 'scheme': 'X ⇌ Xp (kinase K, phosphatase P)', 'species': ['X', 'Xp', 'K', 'P'],
                     'rate': 'kcat_K·K·X/(Km_K + X) ; kcat_P·P·Xp/(Km_P + Xp)', 'parameters': {'kcat_K': 'per_time', 'Km_K': 'nM', 'kcat_P': 'per_time', 'Km_P': 'nM'},
                     'assumptions': ['Quasi-steady state for both enzymes'], 'source': 'Goldbeter & Koshland 1981, doi:10.1073/pnas.78.11.6840'},
    'exchange': {'name': 'Compartment exchange', 'scheme': 'X(a) ⇌ X(b)', 'species': ['Xa', 'Xb'], 'rate': 'PS·(Xa − Xb)', 'parameters': {'PS': 'litre_per_time'},
                 'assumptions': ['Passive exchange; PS is permeability × surface area', 'Each side well mixed'], 'source': None, 'flux': True},
}


class CompositionError(ValueError):
    pass


def _ml(expr):
    """Tiny prefix-tuple → MathML: ('*', 'a', ('+', 'b', 1))."""
    if isinstance(expr, (int, float)):
        return f'<cn>{float(expr)!r}</cn>'
    if isinstance(expr, str):
        return f'<ci> {escape(expr)} </ci>'
    op, *args = expr
    tagname = {'+': 'plus', '-': 'minus', '*': 'times', '/': 'divide', '^': 'power'}[op]
    return f'<apply><{tagname}/>' + ''.join(_ml(a) for a in args) + '</apply>'


def _rate_laws(kind, s, p, comp):
    """Rate laws as (reactants, products, modifiers, expression) in substance/time."""
    V = comp
    if kind == 'binding':
        return [([s['A'], s['B']], [s['AB']], [], ('*', V, ('-', ('*', p['kon'], s['A'], s['B']), ('*', p['koff'], s['AB']))))]
    if kind == 'mass_action_enzyme':
        return [([s['E'], s['S']], [s['ES']], [], ('*', V, ('-', ('*', p['k1'], s['E'], s['S']), ('*', p['k_1'], s['ES'])))),
                ([s['ES']], [s['E'], s['P']], [], ('*', V, p['kcat'], s['ES']))]
    if kind == 'michaelis_menten':
        return [([s['S']], [s['P']], [s['E']], ('*', V, ('/', ('*', p['kcat'], s['E'], s['S']), ('+', p['Km'], s['S']))))]
    if kind == 'competitive_inhibition':
        return [([s['S']], [s['P']], [s['E'], s['I']], ('*', V, ('/', ('*', p['kcat'], s['E'], s['S']), ('+', ('*', p['Km'], ('+', 1, ('/', s['I'], p['Ki']))), s['S']))))]
    if kind == 'synthesis':
        return [([], [s['X']], [], ('*', V, p['k']))]
    if kind == 'templated_synthesis':
        return [([], [s['X']], [s['T']], ('*', V, p['k'], s['T']))]
    if kind == 'repressed_synthesis':
        return [([], [s['X']], [s['R']], ('*', V, ('/', ('*', p['k'], ('^', p['K'], p['n'])), ('+', ('^', p['K'], p['n']), ('^', s['R'], p['n'])))))]
    if kind == 'degradation':
        return [([s['X']], [], [], ('*', V, p['k'], s['X']))]
    if kind == 'modification':
        return [([s['X']], [s['Xp']], [s['K']], ('*', V, ('/', ('*', p['kcat_K'], s['K'], s['X']), ('+', p['Km_K'], s['X'])))),
                ([s['Xp']], [s['X']], [s['P']], ('*', V, ('/', ('*', p['kcat_P'], s['P'], s['Xp']), ('+', p['Km_P'], s['Xp']))))]
    if kind == 'exchange':
        return [([s['Xa']], [s['Xb']], [], ('*', p['PS'], ('-', s['Xa'], s['Xb'])))]
    raise CompositionError('Unknown component: ' + kind)


def compose(network):
    """network = {id, name, time, copyNumbers?, compartments:[{id,size}], species:[{id,name,compartment,initial,provenance}],
                  parameters:[{id,value,unit,provenance,source?}], components:[{type, species:{role:id}, parameters:{role:id}, id?}]}"""
    time = network.get('time', 'second')
    if time not in TIME_UNITS:
        raise CompositionError('Time unit must be second, minute or hour.')
    items = bool(network.get('copyNumbers'))
    comps = {c['id']: c for c in network['compartments']}
    species = {s['id']: s for s in network['species']}
    params = {p['id']: p for p in network['parameters']}
    for p in params.values():
        if p.get('value') is None or not math.isfinite(float(p['value'])) or float(p['value']) < 0:
            raise CompositionError('Parameter ' + p['id'] + ' needs a finite, non-negative value.')
    reactions, used = [], set()
    for k, c in enumerate(network['components']):
        spec = COMPONENTS.get(c['type'])
        if not spec:
            raise CompositionError('Unknown component: ' + c['type'])
        missing = [r for r in spec['species'] if r not in c['species']] + [r for r in spec['parameters'] if r not in c['parameters']]
        if missing:
            raise CompositionError(spec['name'] + ' is missing: ' + ', '.join(missing))
        for role, sid in c['species'].items():
            if sid not in species:
                raise CompositionError('Undeclared species: ' + sid)
        for role, pid in c['parameters'].items():
            if pid not in params:
                raise CompositionError('Undeclared parameter: ' + pid)
            want = spec['parameters'][role]
            if items and want == 'nM_per_time':
                want = 'items_per_time'
            if params[pid]['unit'] != want:
                raise CompositionError(f"{spec['name']}: {pid} must be in {UNIT_LABEL[want].format(t=time)}, not {params[pid]['unit']}.")
            used.add(pid)
        sp_comps = {species[sid]['compartment'] for sid in c['species'].values()}
        if c['type'] != 'exchange' and len(sp_comps) > 1:
            raise CompositionError(spec['name'] + ' links species in different compartments; use an exchange component.')
        compartment = 1.0 if items else next(iter(sp_comps))
        for j, (re_, pr, mods, law) in enumerate(_rate_laws(c['type'], c['species'], c['parameters'], compartment)):
            reactions.append({'id': c.get('id', f'R{k + 1}') + ('' if j == 0 else f'_{j + 1}'), 'name': spec['name'], 'reactants': re_, 'products': pr, 'modifiers': mods, 'law': law, 'component': c['type']})
    unused = sorted(set(params) - used)
    if unused:
        raise CompositionError('Parameters not used by any component: ' + ', '.join(unused))
    return _sbml(network, reactions, time, items)


def _sbml(network, reactions, time, items):
    units = unit_definitions(time)
    u = ''.join(f'<unitDefinition id="{uid}"><listOfUnits>' + ''.join(f'<unit kind="{k}" exponent="{e}" scale="{s}" multiplier="{m!r}"/>' for k, e, s, m in defs) + '</listOfUnits></unitDefinition>' for uid, defs in units.items())
    substance = 'item' if items else 'nmole'
    comps = ''.join(f'<compartment id="{c["id"]}" name="{escape(c.get("name", c["id"]))}" spatialDimensions="3" size="{float(c["size"])!r}" units="litre" constant="true"/>' for c in network['compartments'])
    sp = ''.join(f'<species id="{s["id"]}" name="{escape(s.get("name", s["id"]))}" compartment="{s["compartment"]}" '
                 + (f'initialAmount="{float(s["initial"])!r}" hasOnlySubstanceUnits="true"' if items else f'initialConcentration="{float(s["initial"])!r}" hasOnlySubstanceUnits="false"')
                 + f' boundaryCondition="{str(bool(s.get("boundary"))).lower()}" constant="false"/>' for s in network['species'])
    pa = ''.join(f'<parameter id="{p["id"]}" name="{escape(p.get("name", p["id"]))}" value="{float(p["value"])!r}" units="{p["unit"]}" constant="true"/>' for p in network['parameters'])
    rx = ''
    for r in reactions:
        ref = lambda ids: ''.join(f'<speciesReference species="{i}" stoichiometry="1" constant="true"/>' for i in ids)
        rx += (f'<reaction id="{r["id"]}" name="{escape(r["name"])}" reversible="false">'
               + (f'<listOfReactants>{ref(r["reactants"])}</listOfReactants>' if r['reactants'] else '')
               + (f'<listOfProducts>{ref(r["products"])}</listOfProducts>' if r['products'] else '')
               + (f'<listOfModifiers>' + ''.join(f'<modifierSpeciesReference species="{m}"/>' for m in r['modifiers']) + '</listOfModifiers>' if r['modifiers'] else '')
               + f'<kineticLaw><math xmlns="http://www.w3.org/1998/Math/MathML">{_ml(r["law"])}</math></kineticLaw></reaction>')
    model_units = f'substanceUnits="{substance}" timeUnits="time" volumeUnits="litre" extentUnits="{substance}"'
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<sbml xmlns="http://www.sbml.org/sbml/level3/version2/core" level="3" version="2">'
            f'<model id="{network["id"]}" name="{escape(network["name"])}" {model_units}>'
            f'<listOfUnitDefinitions>{u}</listOfUnitDefinitions><listOfCompartments>{comps}</listOfCompartments>'
            f'<listOfSpecies>{sp}</listOfSpecies><listOfParameters>{pa}</listOfParameters><listOfReactions>{rx}</listOfReactions></model></sbml>')


def catalogue():
    return [{'type': k, **{f: v for f, v in c.items()}} for k, c in COMPONENTS.items()]
