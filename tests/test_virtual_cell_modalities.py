import hashlib, io, json, pathlib, sys, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scientific')); sys.path.insert(0, str(ROOT / 'tests'))
import numpy as np
import virtual_cell_microscopy as VM, virtual_cell_proteomics as VP, virtual_cell_results as VRS, virtual_cell_structures as VST, virtual_cell_cycle as VC, virtual_cell_annotations as VA
from test_virtual_cell_annotations import write_originals


def disks(shape=(200, 200), centres=((50, 50), (50, 140), (140, 90)), r=14, gap_value=60, value=2000):
    y, x = np.mgrid[:shape[0], :shape[1]]; img = np.full(shape, gap_value, np.uint16)
    for cy, cx in centres:
        img[(y - cy) ** 2 + (x - cx) ** 2 <= r * r] = value
    return img


class MicroscopyTests(unittest.TestCase):
    def test_otsu_separates_two_populations(self):
        x = np.concatenate([np.full(1000, 10.0), np.full(1000, 100.0)])
        self.assertTrue(10 < VM.otsu(x) < 100)

    def test_nuclei_count_and_area_on_known_disks(self):
        n = VM.segment_nuclei(disks())
        self.assertEqual(n.max(), 3)
        areas = sorted(int((n == i).sum()) for i in range(1, 4)); true = np.pi * 14 ** 2
        for a in areas:
            self.assertLess(abs(a - true) / true, 0.15)               # σ=2 smoothing blurs edges slightly

    def test_shape_descriptors(self):
        m = np.zeros((60, 60), bool); m[10:20, 10:50] = True           # 10 × 40 rectangle
        s = VM._shape(m)
        self.assertEqual(s['area'], 400); self.assertEqual(s['perimeter'], 100)
        self.assertGreater(s['eccentricity'], 0.9)
        c = np.zeros((80, 80), bool); y, x = np.mgrid[:80, :80]; c[(y - 40) ** 2 + (x - 40) ** 2 <= 400] = True
        self.assertLess(VM._shape(c)['eccentricity'], 0.1)

    def test_cells_grow_from_nuclei_and_measure(self):
        dna = disks(); nuc = VM.segment_nuclei(dna)
        cyto = disks(r=30, gap_value=50, value=900); cells = VM.segment_cells(nuc, cyto, cyto)
        rows = VM.measure({'DNA': dna, 'ER': cyto, 'AGP': cyto, 'Mito': cyto}, nuc, cells)
        self.assertEqual(len(rows), 3)
        for r in rows:
            self.assertLess(r['ratio'], 1); self.assertGreater(r['cell']['area'], r['nucleus']['area'])
            self.assertGreater(r['DNA']['nucleusMean'], r['DNA']['cytoplasmMean'])

    def test_pixels_are_verified_against_the_manifest(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as root:
            org = VM.folder(root) / 'original' / 'images'; org.mkdir(parents=True)
            buf = io.BytesIO(); Image.fromarray(disks()).save(buf, format='TIFF'); (org / 'a.tiff').write_bytes(buf.getvalue())
            m = {'file': 'images/a.tiff', 'sha256': hashlib.sha256(buf.getvalue()).hexdigest()}
            a = VM._load(root, m)
            self.assertEqual(a.dtype, np.uint16); self.assertEqual(int(a.max()), 2000)           # raw values preserved
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                VM._load(root, {**m, 'sha256': '0' * 64})


class ProteomicsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = self.tmp.name
        write_originals(self.root); VA.build(self.root)
        org = VP.folder(self.root) / 'original'; org.mkdir(parents=True)
        (org / '9606-iBAQ_HepG2_Geiger_2012_uniprot.txt').write_text('#id: 1\n#name: test\n#coverage: 34\n#link: x\n#\n#gene_name\tstring_external_id\tabundance\n'
                                                                   'CDK1\t9606.ENSP0001\t50\nACTB\t9606.ENSP0002\t500\nSHARED\t9606.ENSP0003\t5\n')

    def tearDown(self):
        self.tmp.cleanup()

    def test_build_lookup_missing_and_ambiguity(self):
        meta = VP.build(self.root)[0]
        self.assertEqual(meta['counts'], {'rows': 3, 'resolved': 2, 'unresolved': 1, 'duplicateSymbols': 0})   # SHARED alias is ambiguous: kept unresolved
        self.assertIn('ppm', meta['unit']); self.assertIn('not zero', meta['missing'])
        x = VP.protein(self.root, 'CDK1')[0]
        self.assertEqual((x['value'], x['rank'], x['of']), (50.0, 2, 2))
        self.assertFalse(VP.protein(self.root, 'ALB')[0]['reported'])
        self.assertEqual(VP.protein(self.root, 'CDK1', 'CVCL_0004'), [])                          # other contexts see nothing
        self.assertIn('Too few', VP.rna_protein(self.root, 'geiger2012_ibaq', {'CDK1': 1.0, 'ACTB': 2.0})['note'])

    def test_generic_import_requires_units_and_context(self):
        f = pathlib.Path(self.root) / 't.csv'; f.write_text('gene,value\nCDK1,3\nACTB,\n')
        with self.assertRaisesRegex(ValueError, 'unit'):
            VP.import_table(self.root, f, {'id': 'abc', 'name': 'n', 'cellosaurus': 'CVCL_0027', 'method': 'm', 'value_column': 'value', 'citation': 'c', 'licence': 'l'})
        m = VP.import_table(self.root, f, {'id': 'abc', 'name': 'n', 'cellosaurus': 'CVCL_0027', 'method': 'm', 'unit': 'fmol', 'gene_column': 'gene', 'value_column': 'value', 'citation': 'c', 'licence': 'l'})
        self.assertEqual(m['counts']['rows'], 2)
        acc = [x for x in VP.protein(self.root, 'ACTB') if x['dataset'] == 'abc'][0]
        self.assertTrue(acc['reported']); self.assertIsNone(acc['value'])                         # empty cell stays missing


class ResultTests(unittest.TestCase):
    def test_integrity_recipe_and_split(self):
        with tempfile.TemporaryDirectory() as root:
            d = pathlib.Path(root) / 'cell_physics' / 'runs'; d.mkdir(parents=True)
            rec = {'schema': 'fold-studio.research-record', 'id': 'a' * 32, 'kind': 'diffusion', 'engine': {'name': 'BD', 'version': '1'}, 'evidence': {'category': 'B', 'name': 'Physics simulation'},
                   'inputs': {'D': {'value': 1, 'unit': 'µm²/s'}}, 'solver': {'dt': 0.1},
                   'outputs': {'time': [0, 1, 2], 'timeUnit': 's', 'free': {'msd': [0, 6, 12]}, 'occupancy': [1, 2], 'rate': 0.5}, 'benchmark': {'passed': True, 'checks': []}}
            rec['reproducibility'] = {'contentSha256': VRS._sha({k: rec[k] for k in ('inputs', 'solver', 'outputs')}, float)}
            (d / ('a' * 32 + '.json')).write_text(json.dumps(rec))
            g = VRS.get(root, 'cell_physics', 'a' * 32)
            self.assertTrue(g['integrity']['match']); self.assertEqual(g['time'], {'values': [0, 1, 2], 'unit': 's'})
            self.assertEqual([s['id'] for s in g['series']], ['free.msd']); self.assertEqual([p['id'] for p in g['profiles']], ['occupancy'])
            self.assertEqual(g['scalars'], [{'id': 'rate', 'value': 0.5}])
            rec['outputs']['rate'] = 0.6; (d / ('a' * 32 + '.json')).write_text(json.dumps(rec))
            self.assertFalse(VRS.listing(root)[0]['integrity'])
            with self.assertRaises(ValueError):
                VRS.get(root, 'cell_physics', '../x')


class StructureTests(unittest.TestCase):
    def rec(self, name, **data):
        return {'name': name, 'data': {'metadata': {}, **data}}

    def test_origin_comes_from_provenance_not_names(self):
        self.assertEqual(VST._origin(self.rec('x', source='https://files.rcsb.org/download/1AO6.cif', metadata={'pdbId': '1AO6'}))[0], 'experimental')
        self.assertEqual(VST._origin(self.rec('x', source='Local Boltz-2 MPS prediction', confidenceKind='Boltz-2 pLDDT'))[0], 'predicted')
        self.assertEqual(VST._origin(self.rec('x', source='Derived illustrative pose transfer'))[0], 'illustrative')
        k, o = VST._origin(self.rec('AF-P02768-F1-model_v4.pdb', source='Imported local file'))
        self.assertEqual(k, 'unknown'); self.assertIn('not verified', o)

    def test_chain_mapping_requires_identity(self):
        ref = 'MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWUAAA'.replace('U', 'S')
        frag = ref[20:90]
        m = VST._map(ref, frag)
        self.assertEqual((m['uniprotStart'], m['uniprotEnd'], m['identity']), (21, 90, 1.0))
        self.assertIsNone(VST._map(ref, 'W' * 70))


class CycleVisualTests(unittest.TestCase):
    def test_cached_runs_carry_the_display_rule_and_snapshots_compute_it(self):
        with tempfile.TemporaryDirectory() as root:
            t = np.arange(0, 100.01, 0.1); s = {k: (0.5 + 0.5 * np.cos(2 * np.pi * (t - lag) / 25)) ** 4 for k, lag in (('Md', 0), ('Me', 5), ('Ma', 8), ('Mb', 15))}
            r = {'time': t.tolist(), 'series': {k: v.tolist() for k, v in s.items()}, 'analysis': VC.analyse(t, s)}
            x = VC.at(r, 15.0)
            self.assertAlmostEqual(x['visual']['normalised'], 1.0, places=6); self.assertAlmostEqual(x['visual']['gain'], VC.VISUAL['base'] + VC.VISUAL['scale'])
            self.assertEqual(x['visual']['category'], 'illustrative')


if __name__ == '__main__':
    unittest.main()
