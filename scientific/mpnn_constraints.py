"""Explicit source-residue constraints for the original ProteinMPNN decoder."""
import math

AMINO = frozenset('ACDEFGHIKLMNPQRSTVWY')


def prepare(structure, design_chains, options):
    residues = structure['residues']
    by_id = {r['id']: r for r in residues if r['chain'] in design_chains}
    selected = options.get('designResidues')
    if selected is not None:
        if not isinstance(selected, list) or not selected or any(not isinstance(r, str) for r in selected) or len(set(selected)) != len(selected) or set(selected) - set(by_id):
            raise ValueError('Design residues must be distinct observed identities on the selected redesign chains; omit the field to redesign whole chains.')
        selected = set(selected)
    layout = {c['id']: [{'id': r['id'], 'number': r['num'], 'aminoAcid': r['one'],
                         'design': c['id'] in design_chains and (selected is None or r['id'] in selected)}
                        for r in residues if r['chain'] == c['id']] for c in structure['chains']}
    groups = options.get('tiedChains', [])
    if not isinstance(groups, list):
        raise ValueError('Tied chains must be a list of disjoint corresponding-chain groups.')
    seen = set()
    for group in groups:
        if not isinstance(group, list) or len(group) < 2 or any(not isinstance(c, str) for c in group) or len(set(group)) != len(group) or set(group) - set(design_chains) or seen.intersection(group):
            raise ValueError('Tie distinct redesign chains in disjoint groups of at least two.')
        seen.update(group)
        if len({len(layout[c]) for c in group}) != 1:
            raise ValueError('Tied chains require equal observed residue counts; no alignment or numbering equivalence is inferred.')
        for positions in zip(*(layout[c] for c in group)):
            if len({r['design'] for r in positions}) != 1 or not positions[0]['design'] and len({r['aminoAcid'] for r in positions}) != 1:
                raise ValueError('Tied corresponding positions require identical design masks and compatible fixed amino acids.')
    omitted = options.get('omitAminoAcids', '')
    if not isinstance(omitted, str) or set(omitted) - AMINO or len(set(omitted)) != len(omitted) or len(omitted) >= 20:
        raise ValueError('Omitted amino acids must be distinct canonical one-letter codes, leaving at least one choice.')
    bias = options.get('aminoAcidBias', {})
    if not isinstance(bias, dict) or set(bias) - AMINO or any(type(v) not in (int, float) or not math.isfinite(v) or not -20 <= v <= 20 for v in bias.values()):
        raise ValueError('Amino-acid biases must be finite upstream log-odds shifts from −20 to 20 on canonical codes.')
    return {'schemaVersion': 1, 'residues': layout, 'tiedChains': groups,
            'omitAminoAcids': omitted, 'aminoAcidBias': bias,
            'mapping': 'Observed source chain order and residue numbers verified against the upstream parser; ties use within-chain positions, not inferred homology.'}
