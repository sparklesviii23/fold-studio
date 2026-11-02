import gzip, io, json, pathlib, sys, tempfile, types, unittest, zipfile
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scientific'))
import numpy as np
import virtual_cell as V, virtual_cell_annotations as VA

HPA = ['Gene\tGene name\tReliability\tMain location\tAdditional location\tExtracellular location\tEnhanced\tSupported\tApproved\tUncertain\t'
       'Single-cell variation intensity\tSingle-cell variation spatial\tCell cycle dependency\tGO id',
       'ENSG01\tALB\tEnhanced\tEndoplasmic reticulum;Golgi apparatus\t\t\t\t\t\t\t\t\t\t',
       'ENSG02\tCDK1\tSupported\tNucleoplasm\tCytosol\t\t\t\t\t\t\t\tMitotic chromosome (biological definition)\t',
       'ENSG03\tTOMM20\tUncertain\tMitochondria\t\t\t\t\t\t\t\t\t\t',
       'ENSG04\tACTB\tEnhanced\tActin filaments;Plasma membrane\t\t\t\t\t\t\t\t\t\t']
UNI = ['Entry\tGene Names (primary)\tGene Names (synonym)\tEnsembl\tHGNC\tSubcellular location [CC]\tGene Ontology (cellular component)\tPDB\tLength',
       'P02768\tALB\tGIG42\tENST1 [P02768-1];ENSG01.5;\tHGNC:399;\tSUBCELLULAR LOCATION: Secreted {ECO:0000269|PubMed:1}.\textracellular space [GO:0005615]\t1AO6;1BJ5;\t609',
       'P06493\tCDK1\tCDC2 CDC28A\t\tHGNC:1722;\tSUBCELLULAR LOCATION: Nucleus {ECO:0000250}. Mitochondrion {ECO:0000269|PubMed:2}; Peripheral membrane protein {ECO:0000305}. '
       'SUBCELLULAR LOCATION: [Isoform 2]: Cytoplasm {ECO:0000305}. Note=Moves during mitosis.\tnucleus [GO:0005634]\t4YC3;\t297',
       'Q0001\tGENEA\tSHARED\t\t\t\t\t\t100', 'Q0002\tGENEB\tSHARED\t\t\t\t\t\t100',
       'P60709\tACTB\t\tENSG04;\tHGNC:132;\t\t\t\t375']
GENES = ['ALB', 'CDK1', 'TOMM20', 'ACTB', 'GENEA', 'GENEB'] + [f'X{i}' for i in range(14)]


def write_originals(root):
    org = VA.folder(root) / 'original'; org.mkdir(parents=True)
    with zipfile.ZipFile(org / 'subcellular_location.tsv.zip', 'w') as z:
        z.writestr('subcellular_location.tsv', '\n'.join(HPA) + '\n')
    with gzip.open(org / 'uniprot_human_reviewed.tsv.gz', 'wt') as f:
        f.write('\n'.join(UNI) + '\n')
    (org / 'ReactomePathways.txt').write_text('R-HSA-1\tTop\tHomo sapiens\nR-HSA-2\tChild A\tHomo sapiens\nR-HSA-3\tChild B\tHomo sapiens\nR-MMU-9\tMouse\tMus musculus\n')
    (org / 'ReactomePathwaysRelation.txt').write_text('R-HSA-1\tR-HSA-2\nR-HSA-1\tR-HSA-3\nR-MMU-8\tR-MMU-9\n')
    gmt = ['Top\tR-HSA-1\t' + '\t'.join(GENES[:12]), 'Child A\tR-HSA-2\tALB\tCDK1\tX0\tX1\tX2\tX3', 'Child B\tR-HSA-3\t' + '\t'.join(GENES[6:20])]
    with zipfile.ZipFile(org / 'ReactomePathways.gmt.zip', 'w') as z:
        z.writestr('ReactomePathways.gmt', '\n'.join(gmt) + '\n')
    (org / 'UniProt2Reactome.txt').write_text('P02768\tR-HSA-2\turl\tChild A\tTAS\tHomo sapiens\nP06493-2\tR-HSA-2\turl\tChild A\tIEA\tHomo sapiens\n'
                                               'P02768\tR-MMU-9\turl\tMouse\tIEA\tMus musculus\n')
    (org / 'reactome_release.txt').write_text('98')


def write_depmap(root, rrid='CVCL_0027'):
    dm = pathlib.Path(root) / 'oncology' / 'depmap' / '24Q4'; dm.mkdir(parents=True)
    models = ['ACH-000001', 'ACH-000739']
    (dm / 'models.json').write_text(json.dumps([{'ModelID': 'ACH-000739', 'CellLineName': 'Hep G2', 'RRID': rrid, 'OncotreePrimaryDisease': 'Hepatoblastoma',
                                                  'Sex': 'Male', 'Age': '15', 'SourceType': 'ATCC', 'CatalogNumber': 'HB-8065'}]))
    (dm / 'expression.json').write_text(json.dumps({'models': models, 'genes': GENES}))
    (dm / 'gene_effect.json').write_text(json.dumps({'models': models, 'genes': GENES}))
    expr = np.zeros((2, len(GENES)), np.float32); expr[1] = np.arange(len(GENES)); expr[1, 0] = 14.0
    np.save(dm / 'expression.npy', expr); np.save(dm / 'gene_effect.npy', np.full((2, len(GENES)), -0.2, np.float32))


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = self.tmp.name
        write_originals(self.root); VA.build(self.root); self.ix = VA.index(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_manifest_records_hashes_and_release(self):
        m = json.loads((VA.folder(self.root) / 'manifest.json').read_text())
        self.assertEqual(m['reactomeRelease'], '98')
        self.assertEqual(set(m['files']), set(VA.FILES))
        self.assertTrue(all(len(f['sha256']) == 64 for f in m['files'].values()))
        self.assertEqual(m['counts']['pathways'], 3)                       # mouse rows excluded

    def test_resolution(self):
        r = lambda q: VA.resolve(self.ix, q)
        self.assertEqual(r('alb')['symbol'], 'ALB')
        self.assertEqual(r('P06493-2')['symbol'], 'CDK1')
        self.assertEqual(r('ENSG01.5')['symbol'], 'ALB')
        self.assertEqual((r('CDC2')['symbol'], r('CDC2')['matchedBy'].split()[0]), ('CDK1', 'alias'))
        self.assertEqual(r('SHARED')['status'], 'ambiguous'); self.assertEqual(r('SHARED')['candidates'], ['GENEA', 'GENEB'])
        self.assertEqual(r('NOPE')['status'], 'unknown')

    def test_uniprot_locations_keep_evidence_and_drop_topology(self):
        locs = self.ix.genes['CDK1']['uniprotLocations']
        self.assertEqual([(l['location'], l['evidence'], l['isoform']) for l in locs],
                         [('Nucleus', 'inferred', None), ('Mitochondrion', 'experimental', None), ('Cytoplasm', 'inferred', 'Isoform 2')])

    def test_localization_layers(self):
        l = VA.localization(self.ix, 'ALB')
        self.assertEqual(l['layers'], ['er', 'golgi']); self.assertTrue(l['hpa']['drawn'])
        a = VA.localization(self.ix, 'ACTB')                                # terms without renderer geometry: listed, not drawn
        self.assertEqual(a['layers'], []); self.assertEqual([t['layer'] for t in a['hpa']['terms']], [None, None])
        self.assertEqual(VA.localization(self.ix, 'CDK1')['hpa']['cellCycleDependency'], 'Mitotic chromosome (biological definition)')
        sets = VA.channel_sets(self.ix)
        self.assertNotIn('TOMM20', sets['mito'])                            # Uncertain calls never drive the renderer
        self.assertFalse(VA.localization(self.ix, 'TOMM20')['hpa']['drawn'])
        self.assertIn('CDK1', sets['dna'])

    def test_pathways_hierarchy_and_evidence(self):
        self.assertEqual(self.ix.genes['ALB']['reactome'], [{'id': 'R-HSA-2', 'evidence': 'TAS'}])
        self.assertEqual(self.ix.genes['CDK1']['reactome'], [{'id': 'R-HSA-2', 'evidence': 'IEA'}])     # isoform accession folded to the entry
        self.assertEqual([a['id'] for a in VA.ancestry(self.ix, 'R-HSA-2')], ['R-HSA-1', 'R-HSA-2'])

    def test_enrichment_matches_scipy(self):
        from scipy.stats import hypergeom
        r = VA.enrichment(self.ix, ['ALB', 'CDK1', 'X0', 'X1'], GENES, min_size=3)
        self.assertEqual(r['tested'], 2)                                    # top-level parent R-HSA-1 is not tested
        a = next(x for x in r['rows'] if x['id'] == 'R-HSA-2')
        self.assertAlmostEqual(a['p'], hypergeom.sf(3, 20, 6, 4), places=12)
        self.assertGreaterEqual(a['fdr'], a['p'])
        self.assertEqual(VA.enrichment(self.ix, ['NOPE'], GENES)['rows'], [])


class HepG2ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = self.tmp.name
        write_originals(self.root); VA.build(self.root); write_depmap(self.root); V._LINES.clear()
        self.ref = V.context_reference(self.root, 'CVCL_0027')
        self.cell = V.create(self.root, self.ref, '', 'CVCL_0027')

    def tearDown(self):
        V._LINES.clear(); self.tmp.cleanup()

    def test_identity_and_measured_baseline(self):
        info = V.context_info(self.ref)
        self.assertEqual((info['name'], info['cellosaurus'], info['depmap']), ('Hep G2', 'CVCL_0027', 'ACH-000739'))
        self.assertIn('C3A', info['related'])
        self.assertEqual(self.ref.depmap_expr['ALB'], 14.0)

    def test_identity_mismatch_is_refused(self):
        with tempfile.TemporaryDirectory() as other:
            write_depmap(other, rrid='CVCL_1098')
            with self.assertRaisesRegex(ValueError, 'does not carry RRID'):
                V.DepMapContext(other, 'CVCL_0027')

    def test_only_knockouts_and_no_drugs(self):
        with self.assertRaisesRegex(ValueError, 'only knockouts'):
            V.perturb(self.root, self.ref, self.cell['id'], 'gene_overexpression', 'ALB')
        with self.assertRaisesRegex(ValueError, 'No drug-response measurements'):
            V.perturb(self.root, self.ref, self.cell['id'], 'small_molecule', None, 'Trametinib', 1)
        V.perturb(self.root, self.ref, self.cell['id'], 'gene_knockout', 'CDK1')
        f = V.observe_fitness(self.ref, V.load(self.root, self.cell['id']))
        self.assertEqual(f['rows'][0]['gene'], 'CDK1'); self.assertIn('Hep G2', f['meaning'])

    def test_protein_and_pathway_readouts(self):
        p = V.protein(self.root, self.ref, self.cell, 'P02768')
        self.assertEqual(p['symbol'], 'ALB'); self.assertEqual(p['expression']['baseline'], 14.0)
        self.assertEqual(p['expression']['evidenceBaseline'], V.EVIDENCE['A'])
        self.assertEqual(p['localization']['layers'], ['er', 'golgi'])
        self.assertEqual(p['structures']['pdb'], ['1AO6', '1BJ5'])
        self.assertEqual(p['pathways'][0]['topLevel'], 'Top')
        self.assertEqual(p['mechanisticTarget'], {'accession': 'P02768', 'genes': ['ALB'], 'name': 'ALB'})
        self.assertIn('not available', p['abundance'])
        self.assertEqual(V.protein(self.root, self.ref, self.cell, 'SHARED')['resolution']['status'], 'ambiguous')
        w = V.pathway(self.root, self.ref, self.cell, 'R-HSA-2')
        self.assertEqual(w['measured'], 6); self.assertEqual([a['name'] for a in w['ancestry']], ['Top', 'Child A'])
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            V.pathway(self.root, self.ref, self.cell, 'R-MMU-9')
        self.assertIn('empty', V.pathway_enrichment(self.root, self.ref, self.cell))

    def test_channels_use_hpa_when_installed(self):
        s = V.replay(self.ref, []); ch = {c['id']: c for c in V.channels(self.root, self.ref, s)}
        self.assertEqual(ch['er']['genes'], 1); self.assertEqual(ch['mito']['genes'], 0)
        self.assertTrue(V.summary(self.root, self.ref, self.cell['id'])['state']['channelSource'].startswith('Compartments: Human Protein Atlas'))

    def test_dispatch_lists_profile_and_routes(self):
        svc = types.SimpleNamespace(root=self.root, setting=lambda k: None)
        cat = V.dispatch(svc, 'vcell_catalog', {})
        self.assertIn('CVCL_0027', [c['id'] for c in cat['contexts']]); self.assertTrue(cat['annotations']['ready'])
        self.assertEqual(V.dispatch(svc, 'vcell_protein', {'id': self.cell['id'], 'query': 'cdk1'})['symbol'], 'CDK1')


if __name__ == '__main__':
    unittest.main()
