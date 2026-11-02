"""Shared Virtual Cell state: evidence-typed values, versioned snapshots, comparison, export and import.

A snapshot freezes what one cell looked like at one moment for one purpose, so every laboratory can refer to the same
state by one identifier (`<cellId>/<snapshotId>`). It never stores values it cannot reproduce or attribute:

  * The cell's genetic / drug state is not copied; it is the cell's operation history (virtual_cell.py), which replays
    deterministically against the stated reference, and the snapshot records its SHA-256 to detect drift.
  * Every value block carries one evidence category (CATEGORIES) plus source, version, units and context. Blocks of
    different categories are never merged.
  * Time-indexed values (e.g. a cell-cycle simulation) live in a `simulation` block with model, solver and time point.

Layout: <library>/virtualcell/states/<cellId>/<snapshotId>.json. Snapshots are immutable; branching = new snapshot
whose `parent` is another snapshot. Export bundles a snapshot with the cell record and the dataset manifest.
"""
import hashlib, json, pathlib, re, time, uuid

SCHEMA = 'fold.virtualcell.state/1'
CATEGORIES = {
    'measured': 'Experimentally measured value',
    'annotation': 'Curated database annotation',
    'statistic': 'Computed statistic over measured or modelled values',
    'prediction': 'Model prediction (statistical or machine-learned)',
    'simulation': 'Mechanistic simulation output',
    'illustrative': 'Illustrative visualization parameter (not biological evidence)',
}
KINDS = ('baseline', 'perturbed', 'simulation', 'imported')
_ID = re.compile(r'^[0-9a-f]{32}$')


def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def block(category, values, source, unit=None, version=None, context=None, uncertainty=None, note=None):
    """One evidence-typed group of values. Raises on unknown categories so mixed evidence cannot slip in."""
    if category not in CATEGORIES:
        raise ValueError(f'Unknown evidence category: {category}')
    return {'category': category, 'categoryLabel': CATEGORIES[category], 'source': source, 'version': version, 'unit': unit,
            'context': context, 'uncertainty': uncertainty, 'note': note, 'values': values}


def _dir(root, cell_id):
    if not _ID.match(str(cell_id)):
        raise ValueError('Invalid virtual cell identifier.')
    d = pathlib.Path(root) / 'virtualcell' / 'states' / cell_id; d.mkdir(parents=True, exist_ok=True)
    return d


def _path(root, cell_id, snap_id):
    if not _ID.match(str(snap_id)):
        raise ValueError('Invalid snapshot identifier.')
    f = _dir(root, cell_id) / f'{snap_id}.json'
    if not f.is_file():
        raise ValueError('That snapshot no longer exists.')
    return f


def create(root, cell, context, label='', kind='perturbed', blocks=None, simulation=None, parent=None, datasets=None):
    """Freeze a snapshot of `cell` (virtual_cell record). `context` is virtual_cell.context_info(ref)."""
    if kind not in KINDS:
        raise ValueError('Unknown snapshot kind.')
    for b in (blocks or {}).values():
        if b.get('category') not in CATEGORIES:
            raise ValueError('Every value block needs an evidence category.')
    if parent:
        _path(root, cell['id'], parent)
    snap = {'schema': SCHEMA, 'id': uuid.uuid4().hex, 'cellId': cell['id'], 'label': str(label or '')[:120], 'kind': kind, 'created': now(), 'seq': time.time_ns(),
            'parent': parent, 'context': context, 'cell': {'name': cell['name'], 'history': cell['history'], 'sha256': cell.get('sha256'),
                                                           'reference': cell.get('reference'), 'steps': len(cell['history'])},
            'blocks': blocks or {}, 'simulation': simulation, 'datasets': datasets or []}
    snap['sha256'] = sha({k: v for k, v in snap.items() if k != 'sha256'})
    (_dir(root, cell['id']) / f"{snap['id']}.json").write_text(json.dumps(snap, indent=1))
    return snap


def load(root, cell_id, snap_id):
    snap = json.loads(_path(root, cell_id, snap_id).read_text())
    snap['intact'] = sha({k: v for k, v in snap.items() if k not in ('sha256', 'intact')}) == snap['sha256']
    return snap


def listing(root, cell_id):
    out = []
    for f in sorted(_dir(root, cell_id).glob('*.json')):
        s = json.loads(f.read_text())
        out.append({k: s.get(k) for k in ('id', 'label', 'kind', 'created', 'parent', 'seq')} | {'steps': s['cell']['steps'],
                    'time': (s.get('simulation') or {}).get('time'), 'model': ((s.get('simulation') or {}).get('model') or {}).get('id')})
    return sorted(out, key=lambda s: s['seq'] or 0)


def delete(root, cell_id, snap_id):
    if any(s['parent'] == snap_id for s in listing(root, cell_id)):
        raise ValueError('Other snapshots branch from this one; delete them first.')
    _path(root, cell_id, snap_id).unlink()
    return listing(root, cell_id)


def compare(a, b):
    """What differs between two snapshots, block by block. Values are compared only within the same block and
    category; a block present in one snapshot only is reported, never imputed."""
    out = {'sameContext': a['context'].get('cellosaurus') == b['context'].get('cellosaurus'), 'history': {
        'a': [h['op'] + ':' + str(h.get('gene') or h.get('drug')) for h in a['cell']['history']],
        'b': [h['op'] + ':' + str(h.get('gene') or h.get('drug')) for h in b['cell']['history']]}, 'blocks': {}}
    if not out['sameContext']:
        out['warning'] = 'Different cell contexts: values come from different biological samples and are not directly comparable.'
    for k in sorted(set(a['blocks']) | set(b['blocks'])):
        x, y = a['blocks'].get(k), b['blocks'].get(k)
        if x is None or y is None:
            out['blocks'][k] = {'only': 'a' if y is None else 'b'}; continue
        if x['category'] != y['category'] or x.get('unit') != y.get('unit'):
            out['blocks'][k] = {'incompatible': f"{x['category']} [{x.get('unit')}] vs {y['category']} [{y.get('unit')}]"}; continue
        if isinstance(x['values'], dict) and isinstance(y['values'], dict):
            rows = []
            for g in sorted(set(x['values']) | set(y['values'])):
                u, v = x['values'].get(g), y['values'].get(g)
                if isinstance(u, (int, float)) and isinstance(v, (int, float)) and u != v:
                    rows.append({'key': g, 'a': u, 'b': v, 'difference': v - u})
                elif (u is None) != (v is None):
                    rows.append({'key': g, 'a': u, 'b': v, 'difference': None})
            rows.sort(key=lambda r: -abs(r['difference'] or 0))
            out['blocks'][k] = {'category': x['category'], 'unit': x.get('unit'), 'changed': len(rows), 'rows': rows[:50]}
    sa, sb = a.get('simulation'), b.get('simulation')
    if sa and sb:
        same = (sa['model'] or {}).get('sha256') == (sb['model'] or {}).get('sha256')
        out['simulation'] = {'sameModel': same, 'timeA': sa.get('time'), 'timeB': sb.get('time'),
                             'variables': [{'id': k, 'a': sa['variables'].get(k), 'b': sb['variables'].get(k)} for k in sorted(sa['variables']) if k in sb['variables']] if same else []}
    return out


def export(root, cell_id, snap_id):
    snap = load(root, cell_id, snap_id)
    snap.pop('intact', None)
    chain = []
    p = snap.get('parent')
    while p:
        s = load(root, cell_id, p); s.pop('intact', None); chain.append(s); p = s.get('parent')
    bundle = {'schema': SCHEMA + '+bundle', 'exported': now(), 'snapshot': snap, 'ancestors': chain,
              'reproduce': 'Recreate the cell from snapshot.cell.history in the same context and reference (virtual_cell.replay); '
                           'simulations rerun from snapshot.simulation.model / solver / parameters. Dataset checksums are in snapshot.datasets.'}
    bundle['sha256'] = sha({k: v for k, v in bundle.items() if k != 'sha256'})
    return bundle


def validate_bundle(bundle, context):
    """Checks before import: schema, integrity, and that the bundle belongs to the target cell context."""
    if not isinstance(bundle, dict) or bundle.get('schema') != SCHEMA + '+bundle':
        raise ValueError('Not a Fold Studio virtual cell state bundle.')
    if sha({k: v for k, v in bundle.items() if k != 'sha256'}) != bundle.get('sha256'):
        raise ValueError('The bundle was modified after export (checksum mismatch).')
    snap = bundle['snapshot']
    if snap['context'].get('cellosaurus') != context.get('cellosaurus'):
        raise ValueError(f"The snapshot is from {snap['context'].get('name')} ({snap['context'].get('cellosaurus')}); "
                         f"it cannot be imported into {context.get('name')} ({context.get('cellosaurus')}).")
    for b in snap['blocks'].values():
        if b.get('category') not in CATEGORIES:
            raise ValueError('The bundle contains a value block without a known evidence category.')
    return snap
