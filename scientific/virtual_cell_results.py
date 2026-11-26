"""Saved laboratory simulation results, read into one Virtual Cell result shape (read-only).

Sources are the labs' own `fold.research-record` v1 files; their engines are not called or modified:
  cell_physics  <library>/cell_physics/runs/*.json   Living Cell Brownian dynamics (diffusion, receptor binding)
  cell_em       <library>/cell_em/runs/*.json        Brownian dynamics in the EM-derived HeLa cell (latest cumulative summary)
  rna_lab       <library>/rna_lab/runs/*.json        RNA folding ensembles, TASEP translation

Each record's integrity is re-checked with the writing lab's own recipe (SOURCES[...]['hashed']). The normalised result
keeps the record's engine identity and version, evidence category and statement, inputs with their units and
provenance, solver settings, benchmark checks, assumptions and limitations. Outputs are split by shape only:
  series    numeric lists as long as the record's `time` axis (unit = the record's timeUnit for the axis; values keep
            the units the lab stated, else "as recorded")
  profiles  other numeric lists (e.g. ribosome occupancy per codon), indexed by position
  scalars   numeric values
Nothing is rescaled, resampled or interpreted as a property of the selected cell context: these runs describe the
idealised systems in their own inputs (e.g. point particles in a 5 µm sphere), and say so.
"""
import hashlib, json, pathlib, re

SCHEMA = 'fold.virtualcell.simulation-result/1'
SOURCES = {
    'cell_physics': {'dir': ('cell_physics', 'runs'), 'lab': 'Living Cell Physics', 'hashed': ('inputs', 'solver', 'outputs'), 'default': float,
                     'scale': 'single idealised cell (µm, s); point particles'},
    'cell_em': {'dir': ('cell_em', 'runs'), 'lab': 'Real Cell (EM) Brownian dynamics', 'hashed': ('inputs', 'solver', 'outputs'), 'default': float,
                'scale': 'one fixed HeLa cell imaged by FIB-SEM (µm, s); point particles in its segmented geometry'},
    'light_pulse': {'dir': ('light_pulse', 'runs'), 'lab': 'Virtual light-pulse experiment', 'hashed': ('inputs', 'solver', 'outputs'), 'default': float,
                    'scale': 'population mean of an E. coli culture (min, MEFL); a compartment model with no geometry'},
    'hela_erk': {'dir': ('hela_erk', 'runs'), 'lab': 'HeLa EGF–ERK experiment', 'hashed': ('inputs', 'solver', 'outputs'), 'default': float,
                 'scale': 'one HeLa cell of a live-cell experiment (min, C/N ratio); two compartments, nucleus and cytoplasm'},
    'rna_lab': {'dir': ('rna_lab', 'runs'), 'lab': 'RNA-to-Protein Lab', 'hashed': ('engine', 'inputs', 'solver', 'outputs'), 'default': None,
                'scale': 'single RNA molecule (nucleotides / codons, s)'},
}
_ID = re.compile(r'^[0-9a-f]{32}$')


def _sha(obj, default):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), default=default).encode()).hexdigest()


def _files(root, source):
    d = pathlib.Path(root).joinpath(*SOURCES[source]['dir'])
    return sorted(d.glob('*.json')) if d.is_dir() else []


def _integrity(rec, source):
    s = SOURCES[source]; stored = (rec.get('reproducibility') or {}).get('contentSha256')
    if not stored or any(k not in rec for k in s['hashed']):
        return {'stored': stored, 'recomputed': None, 'match': False, 'recipe': list(s['hashed'])}
    calc = _sha({k: rec[k] for k in s['hashed']}, s['default'])
    return {'stored': stored, 'recomputed': calc, 'match': calc == stored, 'recipe': list(s['hashed'])}


def listing(root):
    out = []
    for source in SOURCES:
        for f in _files(root, source):
            try:
                rec = json.loads(f.read_text())
            except (OSError, ValueError):
                out.append({'source': source, 'id': f.stem, 'error': 'unreadable record'}); continue
            if rec.get('schema') != 'fold.research-record':
                continue
            out.append({'source': source, 'lab': SOURCES[source]['lab'], 'id': rec.get('id', f.stem), 'kind': rec.get('kind'), 'created': rec.get('created'),
                        'engine': (rec.get('engine') or {}).get('name'), 'version': (rec.get('engine') or {}).get('version'),
                        'evidence': (rec.get('evidence') or {}).get('name'), 'benchmarkPassed': (rec.get('benchmark') or {}).get('passed'),
                        'integrity': _integrity(rec, source)['match']})
    return sorted(out, key=lambda r: r.get('created') or '', reverse=True)


def _split(outputs, n_time, unit_time):
    series, profiles, scalars = [], [], []

    def walk(prefix, v):
        if isinstance(v, bool) or v is None:
            return
        if isinstance(v, (int, float)):
            scalars.append({'id': prefix, 'value': v}); return
        if isinstance(v, list) and v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
            (series if n_time and len(v) == n_time and prefix != 'time' else profiles).append({'id': prefix, 'values': v}); return
        if isinstance(v, dict):
            for k, x in v.items():
                walk(f'{prefix}.{k}' if prefix else k, x)
    for k, v in outputs.items():
        if k not in ('time', 'sampled'):                      # 'sampled' holds example trajectories for display, kept in the raw record
            walk(k, v)
    return series, profiles, scalars


def get(root, source, rid):
    if source not in SOURCES or not _ID.match(str(rid)):
        raise ValueError('Unknown simulation result.')
    f = pathlib.Path(root).joinpath(*SOURCES[source]['dir'], f'{rid}.json')
    if not f.is_file():
        raise ValueError('That saved simulation result no longer exists.')
    rec = json.loads(f.read_text()); out = rec.get('outputs') or {}
    t = out.get('time') if isinstance(out.get('time'), list) else None
    series, profiles, scalars = _split(out, len(t) if t else 0, out.get('timeUnit'))
    return {'schema': SCHEMA, 'source': source, 'lab': SOURCES[source]['lab'], 'id': rec.get('id', rid), 'kind': rec.get('kind'), 'created': rec.get('created'),
            'model': rec.get('engine'), 'evidence': rec.get('evidence'), 'inputs': rec.get('inputs'), 'solver': rec.get('solver'),
            'time': {'values': t, 'unit': out.get('timeUnit')} if t else None, 'lengthUnit': out.get('lengthUnit'),
            'series': series, 'profiles': profiles, 'scalars': scalars,
            'convergence': rec.get('benchmark'), 'assumptions': rec.get('assumptions'), 'limitations': rec.get('limitations'),
            'reproducibility': rec.get('reproducibility'), 'integrity': _integrity(rec, source), 'scale': SOURCES[source]['scale'],
            'validation': ('benchmark checks passed' if (rec.get('benchmark') or {}).get('passed') else 'benchmark checks failed' if rec.get('benchmark') else 'no benchmark recorded'),
            'spatial': ({'specimen': 'HeLa (CVCL_0030), one fixed cell, OpenOrganelle jrc_hela-2 FIB-SEM' if (((rec.get('experiment') or {}).get('config') or {}).get('context') or 'hela-jrc_hela-2') == 'hela-jrc_hela-2' else 'E. coli, illustrative rod geometry (not an image)', 'counts': out.get('events'), 'events': out.get('pairEvents') or [],
                         'eventsTruncated': bool(out.get('pairEventsTruncated')), 'experiment': {k: (rec.get('experiment') or {}).get(k) for k in ('label', 'parent', 'chunks')},
                         'structures': [{k: s.get(k) for k in ('name', 'structure', 'structureSha256', 'structureName')} for s in ((rec.get('experiment') or {}).get('config') or {}).get('species', [])]}
                        if source == 'cell_em' else None),
            'timeline': ({'events': out.get('events') or [], 'unit': out.get('timeUnit'), 'experiment': {k: (rec.get('experiment') or {}).get(k) for k in ('label', 'parent', 'context')},
                          'validation': rec.get('validation'), 'warnings': rec.get('warnings') or [], 'drivers': rec.get('drivers') or []} if source in ('light_pulse', 'hela_erk') else None),
            'open': ({'workspace': 'spatial', 'run': rec.get('id', rid), 'context': ((rec.get('experiment') or {}).get('config') or {}).get('context')} if source == 'cell_em' else
                     {'workspace': source, 'run': rec.get('id', rid), 'context': (rec.get('experiment') or {}).get('context')} if source in ('light_pulse', 'hela_erk') else None),
            'context': ('A prediction for HeLa cells carrying the ERK-KTR reporter, from a model fitted to single cells of a public live-cell experiment. The electron-microscopy HeLa cell is a geometry reference only: it is another specimen, and it is not the selected Virtual Cell context.'
                        if source == 'hela_erk' else 'A prediction for an E. coli strain carrying a light-responsive reporter, from a model fitted to published time courses of that strain. It is not the selected Virtual Cell context and says nothing about a human cell.'
                        if source == 'light_pulse' else 'Computed in the measured geometry of one fixed HeLa cell (the EM specimen). That specimen is not the selected Virtual Cell biological context, and no expression, fitness, metabolism or signalling readout is computed by this run.'
                        if source == 'cell_em' and (((rec.get('experiment') or {}).get('config') or {}).get('context') or 'hela-jrc_hela-2') == 'hela-jrc_hela-2' else
                        'Computed in an illustrative rod-shaped geometry for E. coli; the geometry is drawn, not imaged, and no molecular readout is computed by this run.' if source == 'cell_em' else 'Describes the idealised system in its own inputs, not the selected Virtual Cell context; nothing is mapped onto the 3D cell.')}
