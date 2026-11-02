"""Mechanistic Biology Lab actions: load models, run numerical experiments,
discover published models and export reproducible COMBINE archives.

Every numerical result comes from SciPy integration of a compiled SBML model;
nothing here estimates biology from a sequence or structure. Each run is stored
as a manifest under <library>/mechanistic/runs with the model hash, parameters,
initial values, solver settings, diagnostics, outputs and software versions.
"""
import csv, hashlib, io, json, pathlib, time, uuid, zipfile
import numpy as np
import mechanistic_sbml as sbml
import mechanistic_sim as sim
import mechanistic_library as lib
import mechanistic_demos as demos
import mechanistic_knowledge as kb

from mechanistic_actions import ACTIONS
MODELS = {}
MAX_SBML = 8 * 1024 * 1024


def _root(service):
    root = pathlib.Path(service.root) / 'mechanistic'
    (root / 'runs').mkdir(parents=True, exist_ok=True)
    return root


def _cache(service):
    return kb.Cache(_root(service) / 'cache')


def _model(p):
    key = p.get('key')
    if key not in MODELS:
        raise sbml.SBMLError('Load the model again; it is no longer in memory.')
    return MODELS[key]


def _register(model, key):
    MODELS[key] = model
    return key


def catalog(service, p):
    return {'demos': [{'id': k, **{f: v for f, v in d.items()}} for k, d in demos.DEMOS.items()], 'components': lib.catalogue(), 'sources': kb.SOURCES,
            'methods': list(sim.METHODS), 'readouts': list(sim.READOUTS), 'environment': sim.environment()}


def load(service, p):
    source = p.get('source')
    meta = {}
    if source == 'demo':
        model = demos.load(p['id']); key = 'demo:' + p['id']; meta = {**demos.DEMOS[p['id']], 'provenance': demos.provenance(p['id'])}
    elif source == 'biomodels':
        text, src = kb.biomodels_fetch(_cache(service), str(p['id']))
        model = sbml.Model(text, src); key = 'biomodels:' + p['id']
    elif source == 'sbml':
        text = str(p.get('text', ''))
        if len(text.encode()) > MAX_SBML:
            raise sbml.SBMLError('SBML files are limited to 8 MB.')
        model = sbml.Model(text, {'kind': 'imported', 'name': p.get('name')}); key = 'sbml:' + model.sha256[:16]
    elif source == 'compose':
        model = sbml.Model(lib.compose(p['network']), {'kind': 'composed'}); key = 'composed:' + model.sha256[:16]
    else:
        raise sbml.SBMLError('Unknown model source.')
    _register(model, key)
    return {'key': key, 'model': model.describe(), 'demo': meta}


def _record(service, model, kind, request, result):
    run = {'id': uuid.uuid4().hex, 'kind': kind, 'created': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'model': {'id': model.id, 'name': model.name, 'sha256': model.sha256, 'source': model.source, 'level': model.level, 'version': model.version},
           'request': request, 'environment': sim.environment(), 'result': result,
           'interpretation': 'Numerical output of the stated model and parameters. Solver convergence says nothing about whether the model describes the biology.'}
    (_root(service) / 'runs' / (run['id'] + '.json')).write_text(json.dumps(run))
    (_root(service) / 'runs' / (run['id'] + '.sbml')).write_text(model.write(request.get('overrides'), request.get('initial')))
    return run['id']


def _clean(p, *keys):
    return {k: p[k] for k in keys if k in p and p[k] is not None}


def run(service, action, p):
    model = _model(p)
    common = dict(overrides=p.get('overrides') or None, initial=p.get('initial') or None)
    if action == 'mech_simulate':
        result = sim.simulate(model, float(p['tEnd']), int(p.get('points', 400)), p.get('method', 'LSODA'), float(p.get('rtol', 1e-8)), float(p.get('atol', 1e-10)), **common)
    elif action == 'mech_scan':
        result = sim.scan(model, float(p['tEnd']), p['sweep'], p['target'], p.get('kind', 'final'), int(p.get('points', 200)), p.get('method', 'LSODA'), base=common['overrides'], initial=common['initial'])
    elif action == 'mech_scan2d':
        result = sim.scan2d(model, float(p['tEnd']), p['a'], p['b'], p['target'], p.get('kind', 'final'), base=common['overrides'], initial=common['initial'])
    elif action == 'mech_uncertainty':
        result = sim.uncertainty(model, float(p['tEnd']), p['ranges'], p['target'], p.get('kind', 'final'), int(p.get('samples', 64)), int(p.get('seed', 1)), base=common['overrides'], initial=common['initial'])
    elif action == 'mech_sensitivity':
        result = sim.local_sensitivity(model, float(p['tEnd']), p['target'], p.get('kind', 'final'), p.get('parameters'), base=common['overrides'], initial=common['initial'])
    elif action == 'mech_steady':
        result = sim.steady_state(model, **common)
    elif action == 'mech_fit':
        result = sim.fit(model, p['data'], p['parameters'], p.get('tEnd'), base=common['overrides'], initial=common['initial'])
    else:
        raise ValueError('Unsupported action.')
    request = {k: v for k, v in p.items() if k != 'key'}
    result['runId'] = _record(service, model, action[5:], request, result)
    return result


def export(service, p):
    """Write a COMBINE archive (.omex) for one recorded run: SBML with the run's
    parameter values, a SED-ML time course where applicable, CSV results and the JSON record."""
    run_id = str(p.get('runId', ''))
    if not run_id.isalnum():
        raise ValueError('Invalid run identifier.')
    folder = _root(service) / 'runs'
    record = json.loads((folder / (run_id + '.json')).read_text())
    model_text = (folder / (run_id + '.sbml')).read_text()
    path = pathlib.Path(p['path'])
    if path.suffix.lower() not in ('.omex', '.zip'):
        raise ValueError('Export as a .omex COMBINE archive.')
    result, req = record['result'], record['request']
    files = {'model.xml': model_text, 'record.json': json.dumps(record, indent=1)}
    if 'time' in result and 'series' in result:
        out = io.StringIO(); w = csv.writer(out)
        names = list(result['series']); w.writerow(['time'] + names)
        for i, t in enumerate(result['time']):
            w.writerow([t] + [result['series'][n][i] for n in names])
        files['results.csv'] = out.getvalue()
        solver = result.get('solver', {})
        kisao = {'LSODA': 'KISAO:0000088', 'BDF': 'KISAO:0000288', 'Radau': 'KISAO:0000304', 'RK45': 'KISAO:0000087', 'DOP853': 'KISAO:0000436'}.get(solver.get('method'), 'KISAO:0000019')
        files['simulation.sedml'] = (
            '<?xml version="1.0" encoding="UTF-8"?>\n<sedML xmlns="http://sed-ml.org/sed-ml/level1/version4" level="1" version="4">'
            '<listOfModels><model id="model" language="urn:sedml:language:sbml" source="model.xml"/></listOfModels>'
            f'<listOfSimulations><uniformTimeCourse id="sim" initialTime="0" outputStartTime="0" outputEndTime="{solver.get("tEnd")}" numberOfSteps="{int(solver.get("points", 2)) - 1}">'
            f'<algorithm kisaoID="{kisao}"><listOfAlgorithmParameters><algorithmParameter kisaoID="KISAO:0000209" value="{solver.get("rtol")}"/>'
            f'<algorithmParameter kisaoID="KISAO:0000211" value="{solver.get("atol")}"/></listOfAlgorithmParameters></algorithm></uniformTimeCourse></listOfSimulations>'
            '<listOfTasks><task id="task" modelReference="model" simulationReference="sim"/></listOfTasks></sedML>')
    elif 'values' in result and 'readout' in result:
        out = io.StringIO(); w = csv.writer(out)
        w.writerow([result.get('sweep', {}).get('name', 'value'), result['kind'] + '(' + result['target'] + ')'])
        for v, y in zip(result['values'], result['readout']):
            w.writerow([v, y])
        files['results.csv'] = out.getvalue()
    formats = {'model.xml': 'http://identifiers.org/combine.specifications/sbml', 'simulation.sedml': 'http://identifiers.org/combine.specifications/sed-ml',
               'results.csv': 'http://purl.org/NET/mediatypes/text/csv', 'record.json': 'http://purl.org/NET/mediatypes/application/json'}
    manifest = ('<?xml version="1.0" encoding="UTF-8"?>\n<omexManifest xmlns="http://identifiers.org/combine.specifications/omex-manifest">'
                '<content location="." format="http://identifiers.org/combine.specifications/omex"/>'
                + ''.join(f'<content location="./{n}" format="{formats[n]}"' + (' master="true"' if n == ('simulation.sedml' if 'simulation.sedml' in files else 'model.xml') else '') + '/>' for n in files)
                + '</omexManifest>')
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('manifest.xml', manifest)
        for n, text in files.items():
            z.writestr(n, text)
    return {'path': str(path), 'files': ['manifest.xml'] + list(files), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def dispatch(service, action, p):
    try:
        if action == 'mech_catalog': return catalog(service, p)
        if action == 'mech_load': return load(service, p)
        if action == 'mech_validate':
            checks = demos.validate(p['id'])
            return {'id': p['id'], 'checks': checks, 'passed': all(c['passed'] for c in checks), 'environment': sim.environment()}
        if action == 'mech_search':
            cache = _cache(service)
            return {'proteins': kb.uniprot_search(cache, str(p['query'])), 'models': kb.biomodels_search(cache, str(p['query']))}
        if action == 'mech_target':
            cache = _cache(service); acc = str(p['accession'])
            return kb.reactome_pathways(cache, acc)
        if action == 'mech_discover':
            cache = _cache(service); target = p['target']
            found = kb.discover(cache, target['accession'], (target.get('genes') or [None])[0])
            pathways = kb.reactome_pathways(cache, target['accession'])['pathways']
            return {**found, 'pathways': pathways, 'graph': kb.graph(target, pathways, found['models'])}
        if action == 'mech_runs':
            folder = _root(service) / 'runs'
            runs = sorted(folder.glob('*.json'), key=lambda f: f.stat().st_mtime, reverse=True)[:30]
            return [{k: json.loads(f.read_text())[k] for k in ('id', 'kind', 'created', 'model')} for f in runs]
        if action == 'mech_export': return export(service, p)
        return run(service, action, p)
    except (sbml.SBMLError, sim.SimulationError, lib.CompositionError, kb.KnowledgeError) as e:
        raise ValueError(str(e))
