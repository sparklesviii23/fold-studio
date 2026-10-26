"""Pinned full Fab cloud transport; this is not scientific qualification."""
from .contracts import canonical, digest
from .molecules import inspect

FILES = {
    'settings/modality/Fab.json': 'c3f07b56b251f1994c372071aef1a1c39d0a430ab0c229cce0e27215f7a79d4b',
    'scaffolds/Fab.cif': '69bb1be47d0ce2dad5f9bea4be30a65b80903369687dd6c660a4b29947f58cf9',
}


def prepare(job, source):
    for name, expected in FILES.items():
        path = source/name
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != expected:
            raise ValueError('Pinned complete Fab asset differs: '+name)
    raw = (source/'scaffolds/Fab.cif').read_bytes()
    mapping = inspect(raw, 'cif')
    if {ch:len(row['sequence']) for ch,row in mapping['chains'].items()} != {'H':221,'L':213}:
        raise ValueError('Full upstream heavy/light scaffold identity differs.')
    # Copy exact original coordinates, including constant domains. The original
    # upstream resolver applies its unmodified CDR edit, loss and model presets.
    (job/'fab-scaffold.cif').write_bytes(raw)
    receipt = {'domain':'full_fab', 'localExecutionAllowed':False,
               'assets':FILES, 'scaffoldChains':mapping['chains'],
               'scientificQualificationPassed':False,
               'scope':'Complete scaffold transport only. Generated loop lengths follow the original upstream preset; no free length or reduced target/model pool.'}
    (job/'fab-input.json').write_text(canonical(receipt))
    return {'binder_scaffold':str(job/'fab-scaffold.cif')}


def validate_output(record):
    coordinates = record.get('coordinates')
    # Failure/rejection without coordinates remains a real recorded outcome.
    if not coordinates:
        if record['outcome'] == 'passed_upstream_filters':
            raise ValueError('Full Fab acceptance requires complete coordinate evidence.')
        return
    roles = coordinates.get('chainRoles', {})
    chains = roles.get('binder', [])
    mapping = coordinates['mapping']['chains']
    if len(chains)!=2 or len(set(chains))!=2 or any(ch not in mapping for ch in chains):
        raise ValueError('Full Fab output needs both explicit upstream binder chain identities.')
    expected = '/'.join(mapping[ch]['sequence'] for ch in chains)
    if record.get('binderSequence') != expected:
        raise ValueError('Full Fab heavy/light sequences differ from the original coordinate output.')
    record['fullFabTransport'] = {
        'binderChains':chains, 'chainLengths':{ch:len(mapping[ch]['sequence']) for ch in chains},
        'scientificQualificationPassed':False,
        'scope':'Both original reported chains and coordinate sequences preserved. Complete-domain, framework, disulfide, held-out and ensemble qualification remains required.'}
