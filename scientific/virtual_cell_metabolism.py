"""Virtual Cell metabolism readout: Human-GEM growth with a cell's knocked-out genes removed (science runtime, COBRApy).

    python virtual_cell_metabolism.py <Human-GEM.json> <genes.tsv> <out.json> [GENE ...]

Same medium and bounds as Demo F (scientific/metabolism.py): Ham's F-12 plus serum fat-soluble vitamins, glucose ≤ 1,
other organic components ≤ 0.1 (relative units). Knockouts use COBRApy's gene-protein-reaction rules: a reaction is
removed only when every isozyme able to carry it is knocked out. Growth is the biomass optimum relative to the
unperturbed model: a feasibility statement about a generic human cell, not K-562-specific and not a doubling time.
"""
import json
import sys
import time

from metabolism import BIOMASS, HAMS, SERUM, set_medium


def run(model_path, genes_tsv, out, genes):
    import warnings; warnings.filterwarnings('ignore')
    import cobra
    t0 = time.time()
    sym = {}
    with open(genes_tsv) as f:
        head = f.readline().rstrip('\n').split('\t'); gi, si = head.index('genes'), head.index('geneSymbols')
        for line in f:
            c = line.rstrip('\n').split('\t')
            for s in c[si].split(';'):
                if s:
                    sym.setdefault(s.upper(), []).append(c[gi])
    m = cobra.io.load_json_model(model_path)
    set_medium(m, HAMS + SERUM, glucose=1.0); m.objective = BIOMASS
    wt = m.slim_optimize(error_value=0.0)
    mapped = {g: [e for e in sym.get(g, []) if e in m.genes] for g in genes}
    with m:
        removed = set()
        for g, ids in mapped.items():
            for e in ids:
                gene = m.genes.get_by_id(e)
                before = {r.id for r in gene.reactions if r.bounds == (0.0, 0.0)}
                gene.knock_out()
                removed |= {r.id for r in gene.reactions if r.bounds == (0.0, 0.0)} - before
        ko = m.slim_optimize(error_value=0.0)
    wt, ko = (0.0 if abs(x) < 1e-9 else x for x in (wt, ko))      # solver round-off, not growth
    res = {'readout': 'metabolism', 'model': 'Human-GEM v2.1.1', 'cobra': cobra.__version__,
           'medium': "Ham's F-12 + serum fat-soluble vitamins; glucose ≤ 1, other organics ≤ 0.1 (relative units)",
           'genes': [{'gene': g, 'ensembl': ids, 'inModel': bool(ids)} for g, ids in mapped.items()],
           'reactionsRemoved': sorted(removed), 'growthUnperturbed': wt, 'growthPerturbed': ko,
           'relativeGrowth': (ko / wt) if wt > 0 else None, 'seconds': round(time.time() - t0, 1)}
    with open(out, 'w') as f:
        json.dump(res, f, indent=1)


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2], sys.argv[3], [g.upper() for g in sys.argv[4:]])
