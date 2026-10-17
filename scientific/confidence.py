"""Bounded, pickle-free reading of the installed Boltz writer's numeric NPZ outputs.

No inference dependency is imported by the desktop service. Only C-order NPY
float32/float64 arrays in NPZ containers are supported; other formats are refused.
"""
import ast
import hashlib
import json
import math
import pathlib
import re
import struct
import zipfile

MAX_VALUES = 4_000_000
MAX_BYTES = 32 * 1024**2


def read_array(path, key, dimensions, upper):
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Confidence archive exceeds 32 MB.')
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) != 1 or entries[0].filename != key + '.npy':
            raise ValueError('Unsupported confidence NPZ members.')
        entry = entries[0]
        if entry.file_size > MAX_BYTES or entry.flag_bits & 1:
            raise ValueError('Confidence array exceeds the read limit or is encrypted.')
        raw = archive.read(entry)
    if raw[:6] != b'\x93NUMPY' or raw[6:8] not in (b'\x01\x00', b'\x02\x00'):
        raise ValueError('Unsupported NPY format version.')
    offset = 10 if raw[6] == 1 else 12
    if len(raw) < offset:
        raise ValueError('Truncated confidence array.')
    length = struct.unpack('<H' if offset == 10 else '<I', raw[8:offset])[0]
    if length > 65536 or offset + length > len(raw):
        raise ValueError('Invalid confidence array header.')
    try:
        header = ast.literal_eval(raw[offset:offset + length].decode('latin1').strip())
    except (ValueError, SyntaxError, RecursionError):
        raise ValueError('Invalid confidence array header.') from None
    if not isinstance(header, dict) or header.get('fortran_order') is not False:
        raise ValueError('Only C-order numeric confidence arrays are supported.')
    dtype = header.get('descr')
    if dtype not in ('<f4', '>f4', '<f8', '>f8'):
        raise ValueError('Only float32/float64 confidence arrays are supported; object arrays are refused.')
    shape = header.get('shape')
    if not isinstance(shape, tuple) or len(shape) != dimensions or any(type(n) is not int or not 1 <= n <= 2000 for n in shape):
        raise ValueError('Confidence dimensions are unsupported (maximum 2,000 tokens).')
    if dimensions == 2 and shape[0] != shape[1]:
        raise ValueError('Confidence matrix must be square.')
    count = math.prod(shape)
    size = int(dtype[-1])
    if count > MAX_VALUES or len(raw) - offset - length != count * size:
        raise ValueError('Confidence array size does not match its declared dimensions.')
    values = [v[0] for v in struct.iter_unpack(dtype[0] + ('f' if size == 4 else 'd'), raw[offset + length:])]
    if any(not math.isfinite(v) or not 0 <= v <= upper for v in values):
        raise ValueError('Nonfinite or out-of-range prediction confidence values.')
    return values if dimensions == 1 else [values[i:i + shape[1]] for i in range(0, count, shape[1])]


def source(path):
    return {'file': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}


def contained(path, folder):
    path = path.resolve()
    if not path.is_relative_to(folder.resolve()) or not path.is_file():
        raise ValueError('Prediction confidence file is outside its saved job.')
    return path


def local_confidence(service, record, kind='pae'):
    if kind not in ('pae', 'pde'):
        raise ValueError('Choose PAE or predicted distance error.')
    job_id = record['data'].get('metadata', {}).get('jobId', '')
    if not re.fullmatch(r'[0-9a-fA-F-]{36}', job_id):
        raise ValueError('No saved Boltz job is attached to this coordinate asset.')
    job = service.job(job_id)
    if job['engine'] != 'boltz2' or job['state'] != 'completed' or job['project_id'] != record['project_id'] or record['id'] not in job['data'].get('outputs', []):
        raise ValueError('This structure is not a completed output of the saved Boltz job.')
    folder = service.root / 'jobs' / job_id / 'output'
    if not folder.resolve().is_relative_to(service.root / 'jobs'):
        raise ValueError('Prediction job folder is outside the research library.')
    asset = contained(service.root / 'assets' / record['data']['asset'], service.root / 'assets')
    if asset.stat().st_size > 100 * 1024**2 or hashlib.sha256(asset.read_bytes()).hexdigest() != record['data']['sha256']:
        raise ValueError('The saved coordinate checksum changed; confidence was refused.')
    # Older jobs have no original filename metadata. Locate the exact output by
    # coordinate SHA, never by title, model rank guess, or another job's metrics.
    files = list(folder.rglob('*.cif')) + list(folder.rglob('*.pdb'))
    matches = []
    for path in files:
        path = contained(path, folder)
        if path.stat().st_size <= 100 * 1024**2 and hashlib.sha256(path.read_bytes()).hexdigest() == record['data']['sha256']:
            matches.append(path)
    original = record['data'].get('metadata', {}).get('originalFilename')
    if original:
        matches = [path for path in matches if path.name == original]
    if len(matches) != 1:
        raise ValueError('The exact prediction output is missing or ambiguous; confidence was not substituted.')
    coordinate = matches[0]
    base = coordinate.stem
    available = {key: (coordinate.parent / (key + '_' + base + '.npz')).is_file() for key in ('pae', 'pde', 'plddt')}
    path = coordinate.parent / (kind + '_' + base + '.npz')
    if not available[kind]:
        raise ValueError('This prediction has no saved ' + kind.upper() + ' array. No matrix was synthesized.')
    path = contained(path, folder)
    matrix = read_array(path, kind, 2, 1000)
    sources = [source(path)]
    plddt = None
    if available['plddt']:
        plddt_path = contained(coordinate.parent / ('plddt_' + base + '.npz'), folder)
        plddt = read_array(plddt_path, 'plddt', 1, 1)
        if len(plddt) != len(matrix):
            raise ValueError('The saved pLDDT and error array token counts disagree.')
        sources.append(source(plddt_path))
    summary_path = coordinate.parent / ('confidence_' + base + '.json')
    metrics = None
    if summary_path.is_file():
        summary_path = contained(summary_path, folder)
        if summary_path.stat().st_size > 1024**2:
            raise ValueError('Prediction summary exceeds 1 MB.')
        metrics = json.loads(summary_path.read_text())
        def validate(value):
            if value is None:
                return
            if isinstance(value, dict):
                for child in value.values(): validate(child)
            elif not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise ValueError('Prediction summary contains unsupported values.')
        if not isinstance(metrics, dict):
            raise ValueError('Unsupported prediction confidence summary.')
        validate(metrics)
        sources.append(source(summary_path))
    chains = job['data'].get('provenance', {}).get('chains', job['data'].get('chains', []))
    # Protein-only, single-chain predictions can map token positions to their
    # exact saved input. Multichain token order needs a separate verified map.
    sequence = chains[0].get('sequence', '') if len(chains) == 1 else ''
    mapped = bool(sequence and re.fullmatch('[ACDEFGHIKLMNPQRSTVWY]+', sequence) and len(sequence) == len(matrix))
    return {'kind': kind, 'matrix': matrix, 'plddt': plddt, 'metrics': metrics, 'available': available,
            'source': 'Saved local Boltz-2 output', 'jobId': job_id, 'structureId': record['id'],
            'sourceSha256': record['data']['sha256'], 'coordinate': source(coordinate), 'files': sources,
            'engineVersion': job['data'].get('provenance', {}).get('engineVersion', job['data'].get('engineVersion')),
            'tokenCount': len(matrix), 'inputSequence': sequence if mapped else None, 'selectionMapping': 'single_protein_input' if mapped else None,
            'maximum': max(max(row) for row in matrix),
            'method': 'Actual Boltz ' + kind.upper() + ' token-pair array, Å; pickle-free NPY float32/64 parser. Lower error indicates higher model confidence.',
            'definitions': {'plddt': 'Local predicted lDDT; saved fraction 0–1, displayed as 0–100.',
                            'ptm': 'Predicted TM-score: global model confidence, 0–1.',
                            'iptm': 'Interface predicted TM-score, 0–1; single-chain zero is not evidence of poor binding.',
                            'confidence_score': 'Engine ranking score; this installed Boltz version combines complex pLDDT with ipTM (or pTM when ipTM is zero).',
                            'pae': 'Predicted aligned error between tokens, Å; asymmetric values are retained.',
                            'pde': 'Predicted error in pairwise token distances, Å.',
                            'complex_plddt': 'Engine aggregate local confidence for the complex, saved on a 0–1 scale.',
                            'complex_pae': 'Engine aggregate aligned-error estimate, Å; distinct from the unweighted mean of the displayed matrix.',
                            'complex_pde': 'Engine aggregate distance-error estimate, Å; distinct from the unweighted mean of the displayed matrix.'},
            'limitations': ['Confidence estimates are not experimental validation or probabilities of biological correctness.',
                            'Multichain matrices are displayed in native token order; residue click mapping is disabled without a verified map.']}
