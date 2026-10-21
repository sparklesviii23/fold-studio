"""Check actual upstream Protein-array serialization; no model is evaluated."""
import argparse
import json
import pathlib
import sys

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'vendor/bindcraft2'),str(ROOT/'remote_worker')]


def main():
    import tempfile
    import numpy as np
    import gemmi
    from bindcraft.protein import Protein,ATOM_NAMES
    from fold_rapid.serialization import write_prediction
    from fold_rapid.molecules import inspect
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=pathlib.Path,default=ROOT/'reports/rapid-coordinate-transport.json')
    args=parser.parse_args()
    source=ROOT/'reports/architect-fab-components-v2/COMPONENT_OUTPUT/2_Refolded/Complexes/engineering_full_fab_fixture_candidate1.cif'
    proteins=Protein.from_structure(str(source));before=inspect(source.read_bytes(),'cif')
    with tempfile.TemporaryDirectory(prefix='rapid-coordinates-') as directory:
        out=pathlib.Path(directory)/'output.cif'
        # Use the genuine file's explicit native chain-role stamps.
        block=gemmi.cif.read_file(str(source)).sole_block()
        roles={role:gemmi.cif.as_string(block.find_value('_bindcraft.'+role+'_chains')).split(',') for role in ('binder','target')}
        write_prediction(source,proteins,out,roles['binder'],roles['target'])
        after=inspect(out.read_bytes(),'cif')
        assert set(before['chains'])==set(after['chains'])
        for chain,old in before['chains'].items():
            new=after['chains'][chain]
            assert old['sequence']==new['sequence']
            assert [(r['authorNumber'],r['insertionCode']) for r in old['residues']]==[(r['authorNumber'],r['insertionCode']) for r in new['residues']]
        structure=gemmi.read_structure(str(out));largest=0
        for name,protein in proteins.items():
            residues=list(structure[0][name]);expected=np.asarray(protein.atoms);mask=np.asarray(protein.atom_mask)
            for index,residue in enumerate(residues):
                for atom_index,atom_name in enumerate(ATOM_NAMES):
                    if not mask[index,atom_index]:continue
                    atom=residue.find_atom(atom_name,'*')
                    largest=max(largest,float(np.max(np.abs(np.array([atom.pos.x,atom.pos.y,atom.pos.z])-expected[index,atom_index]))))
        assert largest<1e-5
    report={'state':'passed','scope':'Existing genuine 559-residue coordinate transport through actual upstream Protein arrays. No new model computation.','residues':after['residueCount'],'chains':list(after['chains']),'authorNumbersAndSequencesPreserved':True,'maxOutputCoordinateRoundtripError':largest,'note':'Comparison is against the actual supplied upstream Protein arrays, including their float16 representation, not a claim of restoring precision absent from those arrays.'}
    args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))


if __name__=='__main__':main()
