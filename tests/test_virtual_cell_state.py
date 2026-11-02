import gzip, hashlib, json, pathlib, sys, tempfile, types, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scientific')); sys.path.insert(0, str(ROOT / 'tests'))
import numpy as np
import virtual_cell as V, virtual_cell_state as VS, virtual_cell_registry as VR, virtual_cell_transcripts as VT, virtual_cell_cycle as VC, virtual_cell_annotations as VA
from test_virtual_cell_annotations import write_depmap, write_originals

CTX = {'name': 'Hep G2', 'cellosaurus': 'CVCL_0027'}


def cell(cid='a' * 32, history=()):
    return {'id': cid, 'name': 'c', 'history': list(history), 'sha256': 'x', 'reference': None}


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def test_blocks_need_a_known_category(self):
        with self.assertRaises(ValueError):
            VS.block('guess', {}, 'x')
        with self.assertRaises(ValueError):
            VS.create(self.root, cell(), CTX, blocks={'b': {'category': 'vibes', 'values': {}}})

    def test_snapshots_branch_compare_and_protect_parents(self):
        a = VS.create(self.root, cell(), CTX, 'base', 'baseline', {'e': VS.block('measured', {'G1': 1.0, 'G2': 2.0}, 'S', unit='u')})
        b = VS.create(self.root, cell(history=[{'op': 'gene_knockout', 'gene': 'G1'}]), CTX, 'ko', 'perturbed',
                      {'e': VS.block('measured', {'G1': 1.0, 'G2': 3.5}, 'S', unit='u'), 'f': VS.block('measured', {'G1': -1.2}, 'D')}, parent=a['id'])
        self.assertEqual([s['label'] for s in VS.listing(self.root, 'a' * 32)], ['base', 'ko'])
        c = VS.compare(VS.load(self.root, 'a' * 32, a['id']), VS.load(self.root, 'a' * 32, b['id']))
        self.assertEqual(c['blocks']['e']['rows'], [{'key': 'G2', 'a': 2.0, 'b': 3.5, 'difference': 1.5}])
        self.assertEqual(c['blocks']['f'], {'only': 'b'})
        with self.assertRaisesRegex(ValueError, 'branch from this one'):
            VS.delete(self.root, 'a' * 32, a['id'])
        x = VS.create(self.root, cell(), CTX, 'p', 'perturbed', {'e': VS.block('prediction', {'G2': 9.0}, 'M', unit='u')})
        self.assertIn('incompatible', VS.compare(VS.load(self.root, 'a' * 32, a['id']), VS.load(self.root, 'a' * 32, x['id']))['blocks']['e'])

    def test_export_import_integrity_and_identity(self):
        a = VS.create(self.root, cell(), CTX, 'base', 'baseline')
        b = VS.create(self.root, cell(), CTX, 'child', 'perturbed', parent=a['id'])
        bundle = VS.export(self.root, 'a' * 32, b['id'])
        self.assertEqual(len(bundle['ancestors']), 1)
        self.assertEqual(VS.validate_bundle(json.loads(json.dumps(bundle)), CTX)['id'], b['id'])
        with self.assertRaisesRegex(ValueError, 'cannot be imported into K-562'):
            VS.validate_bundle(bundle, {'name': 'K-562', 'cellosaurus': 'CVCL_0004'})
        bundle['snapshot']['label'] = 'edited'
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            VS.validate_bundle(bundle, CTX)
        f = VS._path(self.root, 'a' * 32, a['id']); d = json.loads(f.read_text()); d['label'] = 'x'; f.write_text(json.dumps(d))
        self.assertFalse(VS.load(self.root, 'a' * 32, a['id'])['intact'])


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = self.tmp.name

    def tearDown(self):
        V._LINES.clear(); self.tmp.cleanup()

    def test_unsupported_carries_no_values_and_capabilities_are_complete(self):
        u = VR.unsupported('vcell.microscopy', 'no data', ['x'])
        self.assertEqual((u['supported'], u['values']), (False, None))
        for c in VR.capabilities():
            self.assertIn(c['provider'], VR.PROVIDERS); self.assertIn(c['validation'], VR.VALIDATION)
        self.assertEqual(set(VR.DATASETS) - set(V.plugins.RESOURCES), set())

    def test_integrity_hashes_small_files_and_skips_large_ones(self):
        p = pathlib.Path(self.root) / 'd.bin'; p.write_bytes(b'abc')
        self.assertEqual(VR.integrity(self.root, 'd.bin')['sha256'], hashlib.sha256(b'abc').hexdigest())
        self.assertFalse(VR.integrity(self.root, 'missing')['present'])
        old = VR.HASH_LIMIT; VR.HASH_LIMIT = 1
        try:
            q = pathlib.Path(self.root) / 'big.bin'; q.write_bytes(b'0123')
            self.assertIsNone(VR.integrity(self.root, 'big.bin')['sha256'])
        finally:
            VR.HASH_LIMIT = old

    def test_coverage_distinguishes_states_per_context(self):
        write_originals(self.root); VA.build(self.root); write_depmap(self.root)
        cov = VR.coverage(self.root, V.context_reference(self.root, 'CVCL_0027'))
        self.assertEqual(cov['transcript isoforms']['state'], 'not_downloaded')
        self.assertEqual(cov['protein localization']['state'], 'available')
        self.assertEqual(cov['protein abundance']['state'], 'unsupported')
        self.assertEqual(cov['drug response']['state'], 'unsupported'); self.assertIn('C3A', cov['drug response']['note'])
        self.assertTrue(set(c['state'] for c in cov.values()) <= set(VR.COVERAGE))


GTF_ROWS = [('chr1', 'transcript', 100, 900, '+', 'ENST1.1', 'ALB-201', 'protein_coding', ['basic', 'CCDS']),
            ('chr1', 'exon', 100, 200, '+', 'ENST1.1'), ('chr1', 'exon', 500, 900, '+', 'ENST1.1'), ('chr1', 'CDS', 150, 200, '+', 'ENST1.1'),
            ('chr1', 'transcript', 100, 600, '+', 'ENST2.1', 'ALB-202', 'retained_intron', []), ('chr1', 'exon', 100, 600, '+', 'ENST2.1')]
RSEM_HEAD = 'transcript_id\tgene_id\tlength\teffective_length\texpected_count\tTPM\tFPKM\tIsoPct\tposterior_mean_count\tposterior_standard_deviation_of_count\tpme_TPM\tpme_FPKM\tIsoPct_from_pme_TPM\tTPM_ci_lower_bound\tTPM_ci_upper_bound'


class TranscriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = self.tmp.name
        org = VT.folder(self.root) / 'original'; org.mkdir(parents=True); self.org = org
        lines = []
        for r in GTF_ROWS:
            attrs = f'gene_id "ENSG9.3"; transcript_id "{r[5]}"; gene_name "ALB";' + (f' transcript_name "{r[6]}"; transcript_type "{r[7]}";' + ''.join(f' tag "{t}";' for t in r[8]) if r[1] == 'transcript' else '')
            lines.append('\t'.join([r[0], 'HAVANA', r[1], str(r[2]), str(r[3]), '.', r[4], '.', attrs]))
        with gzip.open(org / VT.GTF, 'wt') as f:
            f.write('##header\n' + '\n'.join(lines) + '\n')
        self.gtf_md5 = hashlib.md5((org / VT.GTF).read_bytes()).hexdigest()
        for k, (acc, rep) in enumerate(VT.REPLICATES.items()):
            rows = [RSEM_HEAD, f'ENST1.1\tENSG9.3\t1\t1\t1\t{60 + k}\t0\t{60 + k}\t0\t0\t{58 + k}\t0\t0\t{55 + k}\t{61 + k}',
                    f'ENST2.1\tENSG9.3\t1\t1\t1\t{40 - k}\t0\t{40 - k}\t0\t0\t39\t0\t0\t35\t42', '10904\t10904\t93\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0\t0']
            (org / f'{acc}.tsv').write_text('\n'.join(rows) + '\n')
            (org / f'{acc}.json').write_text(json.dumps({'md5sum': hashlib.md5((org / f'{acc}.tsv').read_bytes()).hexdigest(), 'assembly': 'GRCh38', 'genome_annotation': 'V29',
                                                          'dataset': f'/experiments/{VT.EXPERIMENT}/', 'status': 'released', 'output_type': 'transcript quantifications'}))
        (org / f'{VT.EXPERIMENT}.json').write_text(json.dumps({'description': 'd', 'lab': {'title': 'L'}, 'biosample_summary': 'HepG2', 'assay_title': 'polyA plus RNA-seq'}))
        self.old = VT.GTF_MD5; VT.GTF_MD5 = self.gtf_md5

    def tearDown(self):
        VT.GTF_MD5 = self.old; self.tmp.cleanup()

    def test_build_keeps_replicates_and_structure(self):
        m = VT.build(self.root)
        self.assertEqual(m['counts']['excludedNonGencodeRows'], {a: 1 for a in VT.REPLICATES})
        g = VT.gene(self.root, 'alb')
        self.assertEqual([t['transcript_name'] for t in g['transcripts']], ['ALB-201', 'ALB-202'])
        t = g['transcripts'][0]
        self.assertEqual([r['TPM'] for r in t['replicates']], [60.0, 61.0]); self.assertEqual(t['meanTPM'], 60.5)
        self.assertEqual(t['replicates'][1]['pme_TPM'], 59.0)
        self.assertEqual(t['exons'], [[100, 200], [500, 900]]); self.assertEqual(t['cds'], [[150, 200]]); self.assertIn('CCDS', t['tags'])
        self.assertEqual(g['geneTPM']['perReplicate'], {'ENCFF416RHJ': 100.0, 'ENCFF938LTW': 100.0})
        self.assertEqual(VT.gene(self.root, 'NOPE')['transcripts'], [])

    def test_build_refuses_files_that_do_not_match_their_records(self):
        acc = next(iter(VT.REPLICATES)); f = self.org / f'{acc}.tsv'; f.write_text(f.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'does not match its ENCODE record'):
            VT.build(self.root)


class CycleTests(unittest.TestCase):
    def series(self, amp=1.0, decay=0.0, hours=200):
        t = np.arange(0, hours + 1e-9, 0.1); env = amp * np.exp(-decay * t)
        wave = lambda lag: env * (0.5 + 0.5 * np.cos(2 * np.pi * (t - lag) / 25)) ** 4
        return t, {'Md': wave(0), 'Me': wave(5), 'Ma': wave(8), 'Mb': wave(15)}

    def test_phases_are_ordered_and_period_recovered(self):
        t, s = self.series()
        a = VC.analyse(t, s)
        self.assertTrue(a['sustained']); self.assertAlmostEqual(a['period'], 25, delta=0.2)
        seq = [x['phase'] for x in a['segments']]
        self.assertTrue(seq); self.assertEqual(seq[:4], ['G1', 'G1/S', 'S–G2', 'G2/M'][seq.index('G1'):][:4] if seq[0] == 'G1' else seq[:4])
        nxt = {'G1': 'G1/S', 'G1/S': 'S–G2', 'S–G2': 'G2/M', 'G2/M': 'G1'}
        self.assertTrue(all(nxt[p] == q for p, q in zip(seq, seq[1:])))
        self.assertIsNone(a['labels'][0])                               # unlabelled before the first mitotic exit

    def test_quiescent_and_damped_runs_get_no_phases(self):
        t = np.arange(0, 200.01, 0.1); flat = {k: np.full(len(t), 0.2) for k in ('Md', 'Me', 'Ma', 'Mb')}
        q = VC.analyse(t, flat)
        self.assertTrue(q['quiescent']); self.assertEqual(q['segments'], []); self.assertIsNone(q['period'])
        t, s = self.series(decay=0.01)
        d = VC.analyse(t, s)
        self.assertFalse(d['sustained']); self.assertEqual(d['segments'], []); self.assertIn('damped', d['regime'])

    def test_at_reports_phase_and_rule(self):
        t, s = self.series(); r = {'time': t.tolist(), 'series': {k: v.tolist() for k, v in s.items()}, 'analysis': VC.analyse(t, s)}
        x = VC.at(r, 120.03)
        self.assertAlmostEqual(x['time'], 120.0); self.assertIn(x['phase'], VC.PHASES); self.assertIn('half-maximum', x['phaseRule'])

    def test_limits(self):
        with self.assertRaises(ValueError):
            VC.run(tempfile.gettempdir(), gf=9, hours=100)
        with self.assertRaises(ValueError):
            VC.load_run(tempfile.gettempdir(), '../etc')


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = self.tmp.name
        write_originals(self.root); VA.build(self.root); write_depmap(self.root); V._LINES.clear()
        self.s = types.SimpleNamespace(root=self.root, setting=lambda k: None)

    def tearDown(self):
        V._LINES.clear(); self.tmp.cleanup()

    def test_state_actions_round_trip(self):
        d = lambda act, **p: V.dispatch(self.s, act, p)
        c = d('vcell_create', context='CVCL_0027'); cid = c['cell']['id']
        self.assertFalse(d('vcell_transcripts', id=cid, gene='ALB')['supported'])           # index not built here
        self.assertEqual(d('vcell_coverage', id=cid)['coverage']['protein abundance']['state'], 'unsupported')
        a = d('vcell_snapshot_save', id=cid, label='base')
        d('vcell_perturb', id=cid, op='gene_knockout', gene='CDK1')
        b = d('vcell_snapshot_save', id=cid, label='ko', parent=a['id'])
        self.assertEqual(b['blocks']['fitness']['category'], 'measured')
        self.assertTrue(d('vcell_snapshot_get', id=cid, snapshot=a['id'])['cellChanged'])
        self.assertEqual(d('vcell_snapshot_compare', id=cid, a=a['id'], b=b['id'])['blocks']['fitness'], {'only': 'b'})
        bundle = d('vcell_snapshot_export', id=cid, snapshot=b['id'])
        self.assertEqual(d('vcell_snapshot_import', id=cid, bundle=bundle)['kind'], 'imported')
        reg = d('vcell_registry')
        self.assertIn('encode_hepg2_rna', [x['id'] for x in reg['datasets']])


if __name__ == '__main__':
    unittest.main()
