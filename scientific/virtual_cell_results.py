"""Saved laboratory simulation results, read into one Virtual Cell result shape (read-only).

Sources are the labs' own `fold-studio.research-record` v1 files; their engines are not called or modified:
  cell_physics  <library>/cell_physics/runs/*.json   Living Cell Brownian dynamics (diffusion, receptor binding)
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
            if rec.get('schema') != 'fold-studio.research-record':
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
            'context': 'Describes the idealised system in its own inputs, not the selected Virtual Cell context; nothing is mapped onto the 3D cell.'}
