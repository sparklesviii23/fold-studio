import json, pathlib, subprocess, sys, tempfile, types, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scientific'))
import numpy as np
import virtual_cell as V, virtual_cell_plugins as P, virtual_cell_actions, virtual_cell_drugs as D

GENES = [f'G{i}' for i in range(30)]
SINGLES = GENES[:12]
BENCH = {'results': {'pairs': {'additive': {'pearson': {'mean': 0.88}}}, 'singles': {'no change': {'pearson': {'mean': float('nan')}}, 'linear model': {'pearson': {'mean': 0.49}}, 'mean effect': {'pearson': {'mean': 0.52}}}},
         'noiseCeiling': {'pearson': {'mean': 0.83}}}


KD_GENES = [f'G{i}' for i in range(12, 26)]            # 14 measured knockdowns, all panel genes
KD_META = {'benchmark': {'task': 'unseen knockdowns', 'linear model': {'pearson': {'mean': 0.4}}, 'mean effect': {'pearson': {'mean': 0.45}}},
           'noiseCeiling': {'pearson': {'mean': 0.7}}, 'baselineNote': 'cross-dataset'}


def knockdown_arrays(rng):
    eff = rng.normal(0, 0.2, (len(GENES), len(KD_GENES))).astype(np.float32)
    for j, g in enumerate(KD_GENES):
        eff[GENES.index(g), j] = -1.5                        # the target itself drops
    eff[29, :] = np.nan                                      # one panel gene not measured by the screen
    remaining = np.full(len(KD_GENES), 0.2, np.float32); remaining[-1] = np.nan
    return {'kdEffects': eff, 'kdPerturbations': np.array(KD_GENES), 'kdCells': np.full(len(KD_GENES), 80), 'kdRemaining': remaining,
            'kdMeasured': np.array([i != 29 for i in range(len(GENES))])}


def make_reference(root, seed=0):
    """A small synthetic pack with the real pack's layout: 30 genes, 12 measured singles, one measured pair."""
    rng = np.random.default_rng(seed)
    eff = {g: rng.normal(0, 0.3, len(GENES)) for g in SINGLES}
    pair = eff['G0'] + eff['G1'] * 0.5                       # a measured, sub-additive pair
    perts = SINGLES + ['G0_G1']
    E = np.column_stack([eff[g] for g in SINGLES] + [pair]).astype(np.float32)
    d = pathlib.Path(root, *V.REF); d.mkdir(parents=True)
    np.savez_compressed(d / 'pack.npz', genes=np.array(GENES), ensembl=np.array(GENES), control=np.full(len(GENES), 2.0, np.float32), controlSd=np.full(len(GENES), 0.5, np.float32),
                        effects=E, perturbations=np.array(perts), cells=np.full(len(perts), 100), depmapGenes=np.array(['G2', 'G3', 'DHODH']),
                        depmapEffect=np.array([-1.2, np.nan, -0.48], np.float32), depmapExprGenes=np.array(['G2']), depmapExpression=np.array([3.0], np.float32),
                        **knockdown_arrays(rng))
    (d / 'manifest.json').write_text(json.dumps({'created': 'test', 'expressionUnit': 'log1p(counts per 10,000)', 'baselineNote': 'synthetic',
                                                 'inputs': {'norman2019': {'sha256': 'x'}}, 'benchmark': BENCH, 'knockdown': KD_META}))
    return eff, pair


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = self.tmp.name
        self.eff, self.pair = make_reference(self.root); V._CACHE.clear()
        self.ref = V.reference(self.root)
        self.cid = V.create(self.root, self.ref, 'test')['id']

    def tearDown(self):
        self.tmp.cleanup()

    def oe(self, g, cid=None):
        return V.perturb(self.root, self.ref, cid or self.cid, 'gene_overexpression', g)

    def test_single_uses_its_measured_effect(self):
        self.oe('G2')
        s = V.replay(self.ref, V.load(self.root, self.cid)['history'])
        np.testing.assert_allclose(s['delta'], np.maximum(2.0 + self.eff['G2'], 0) - 2.0, atol=1e-6)
        self.assertEqual(s['category'], 'A')

    def test_measured_pair_replaces_the_additive_sum(self):
        self.oe('G0'); self.oe('G1')
        s = V.replay(self.ref, V.load(self.root, self.cid)['history'])
        self.assertEqual(s['composition'], 'measured pair')
        np.testing.assert_allclose(s['delta'], np.maximum(2.0 + self.pair, 0) - 2.0, atol=1e-6)

    def test_unmeasured_combination_is_additive_and_labelled_prediction(self):
        self.oe('G2'); self.oe('G3')
        s = V.replay(self.ref, V.load(self.root, self.cid)['history'])
        self.assertTrue(s['composition'].startswith('additive'))
        self.assertEqual(s['category'], 'C')
        self.assertEqual(V._benchmark(self.ref, s)['task'], 'unseen pairs, additive model')

    def test_panel_gene_never_perturbed_uses_linear_model(self):
        self.oe('G20')
        s = V.replay(self.ref, V.load(self.root, self.cid)['history'])
        self.assertEqual(s['contributions'][0]['category'], 'C')
        self.assertIn('linear model', V._benchmark(self.ref, s)['task'])

    def test_refusals(self):
        with self.assertRaisesRegex(ValueError, 'outside the validated domain'):
            self.oe('NOTAGENE')
        with self.assertRaisesRegex(ValueError, 'Tahoe-100M atlas'):
            V.perturb(self.root, self.ref, self.cid, 'small_molecule', None, 'X', 1.0)
        with self.assertRaisesRegex(ValueError, 'concentration'):
            V.perturb(self.root, self.ref, self.cid, 'small_molecule', None, 'X', None)
        self.oe('G2')
        with self.assertRaisesRegex(ValueError, 'already'):
            self.oe('G2')

    def test_replay_is_deterministic_and_record_hash_stable(self):
        self.oe('G2'); c = V.load(self.root, self.cid)
        a, b = V.replay(self.ref, c['history']), V.replay(self.ref, json.loads(json.dumps(c))['history'])
        np.testing.assert_array_equal(a['expression'], b['expression'])
        self.assertEqual(c['sha256'], V._sha({k: c[k] for k in ('context', 'history', 'reference')}))

    def test_branch_copies_a_prefix_and_never_touches_the_source(self):
        self.oe('G2'); self.oe('G3')
        b = V.branch(self.root, self.cid, 1)
        self.assertEqual([h['gene'] for h in b['history']], ['G2'])
        self.assertEqual(b['parent'], {'id': self.cid, 'name': 'test', 'step': 1})
        self.assertEqual(len(V.load(self.root, self.cid)['history']), 2)
        with self.assertRaises(ValueError):
            V.branch(self.root, self.cid, 5)

    def test_knockout_reports_depmap_and_states_what_is_not_modelled(self):
        V.perturb(self.root, self.ref, self.cid, 'gene_knockout', 'G2')
        V.perturb(self.root, self.ref, self.cid, 'gene_knockout', 'G3')
        c = V.load(self.root, self.cid)
        f = V.observe_fitness(self.ref, c)
        self.assertEqual(f['rows'][0]['call'], 'strong dependency')
        self.assertIsNone(f['rows'][1]['chronos'])                      # NaN in DepMap → None, never NaN in JSON
        self.assertIn('not modelled', f['notModelled'])
        self.assertIn('not reflected', V.observe_expression(self.ref, c)['notModelled'])
        json.dumps(f, allow_nan=False)

    def test_design_recovers_the_perturbation_that_made_the_target(self):
        target = V.create(self.root, self.ref, 'target')['id']
        self.oe('G0', target); self.oe('G1', target)
        here = V.create(self.root, self.ref, 'here')['id']; self.oe('G0', here)
        r = V.design(self.ref, V.load(self.root, here), {'delta': V.replay(self.ref, V.load(self.root, target)['history'])['delta']})
        self.assertEqual(r['candidates'][0]['genes'], ['G1'])            # completes the measured, sub-additive pair
        self.assertEqual(r['candidates'][0]['evidence'], V.EVIDENCE['A'])
        self.assertAlmostEqual(r['candidates'][0]['distanceRemoved'], 1.0, places=6)

    def test_design_toward_gene_direction(self):
        best = max(SINGLES, key=lambda g: self.eff[g][25])
        r = V.design(self.ref, V.load(self.root, self.cid), {'up': ['G25'], 'down': []}, limit=200)
        top_single = next(c for c in r['candidates'] if len(c['ops']) == 1 and c['ops'][0]['op'] == 'gene_overexpression')
        self.assertEqual(top_single['genes'], [best])
        with self.assertRaises(ValueError):
            V.design(self.ref, V.load(self.root, self.cid), {'up': ['NOPE']})

    def test_measured_knockdown_lowers_its_target_and_is_experimental(self):
        V.perturb(self.root, self.ref, self.cid, 'gene_knockdown', 'G12')
        s = V.replay(self.ref, V.load(self.root, self.cid)['history'])
        self.assertEqual(s['category'], 'A'); self.assertEqual(s['composition'], 'single knockdown')
        self.assertLess(s['delta'][12], -1.0)
        self.assertEqual(s['delta'][29], 0.0)                   # unmeasured gene: no invented change
        e = V.observe_expression(self.ref, V.load(self.root, self.cid))
        self.assertEqual(e['knockdownEfficiency'], [{'gene': 'G12', 'remaining': 0.2}])

    def test_knockdown_plus_overexpression_is_additive_prediction(self):
        self.oe('G2'); V.perturb(self.root, self.ref, self.cid, 'gene_knockdown', 'G12')
        s = V.replay(self.ref, V.load(self.root, self.cid)['history'])
        self.assertEqual(s['category'], 'C'); self.assertIn('two screens', s['composition'])
        self.assertIn('not benchmarked', V._benchmark(self.ref, s)['note'])

    def test_unmeasured_panel_knockdown_uses_linear_model_with_its_benchmark(self):
        V.perturb(self.root, self.ref, self.cid, 'gene_knockdown', 'G5')
        s = V.replay(self.ref, V.load(self.root, self.cid)['history'])
        self.assertEqual(s['category'], 'C')
        self.assertIn('unseen knockdowns', V._benchmark(self.ref, s)['task'])
        with self.assertRaisesRegex(ValueError, 'outside the validated domain'):
            V.perturb(self.root, self.ref, self.cid, 'gene_knockdown', 'DHODH')

    def test_signalling_folds_couple_state_to_sparced_mrnas(self):
        V.perturb(self.root, self.ref, self.cid, 'gene_knockout', 'G2')
        V.perturb(self.root, self.ref, self.cid, 'gene_knockdown', 'G12')
        V.perturb(self.root, self.ref, self.cid, 'gene_knockdown', 'G25')
        f = V.signalling_folds(self.ref, V.load(self.root, self.cid), ['G2', 'G12', 'G25', 'G28', 'NOTINPANEL'])
        self.assertEqual(f['G2'], 0.0)                          # knockout
        self.assertEqual(f['G12'], 0.2)                         # measured on-target remaining fraction
        self.assertLess(f['G25'], 1.0)                          # efficiency unknown: from the expression change
        self.assertNotIn('NOTINPANEL', f)

    def test_design_searches_knockdowns_too(self):
        target = V.create(self.root, self.ref, 'target')['id']
        V.perturb(self.root, self.ref, target, 'gene_knockdown', 'G14')
        r = V.design(self.ref, V.load(self.root, self.cid), {'delta': V.replay(self.ref, V.load(self.root, target)['history'])['delta']})
        self.assertEqual(r['candidates'][0]['ops'], [{'op': 'gene_knockdown', 'gene': 'G14', 'label': 'knock down G14'}])
        self.assertAlmostEqual(r['candidates'][0]['distanceRemoved'], 1.0, places=6)

    def test_metabolism_cross_check_flags_disagreement(self):
        met = {'relativeGrowth': 0.0, 'genes': [{'gene': 'DHODH', 'inModel': True}]}
        x = V._cross_check(self.ref, ['DHODH'], met)
        self.assertFalse(x['agree'])
        self.assertIsNone(V._cross_check(self.ref, ['DHODH', 'G2'], met))

    def test_dispatch_round_trip(self):
        s = types.SimpleNamespace(root=self.root, setting=lambda k: None)
        self.assertEqual(set(virtual_cell_actions.ACTIONS), {'vcell_catalog', 'vcell_reference_build', 'vcell_list', 'vcell_create', 'vcell_get', 'vcell_perturb',
                                                             'vcell_branch', 'vcell_delete', 'vcell_observe', 'vcell_design', 'vcell_protein', 'vcell_pathway',
                                                             'vcell_enrichment', 'vcell_annotations_install'} | V.STATE_ACTIONS | {'vcell_registry', 'vcell_transcripts_build', 'vcell_results_list', 'vcell_result_get', 'vcell_contexts'})
        c = V.dispatch(s, 'vcell_create', {'name': 'd'})
        V.dispatch(s, 'vcell_perturb', {'id': c['cell']['id'], 'op': 'gene_overexpression', 'gene': 'g2'})
        e = V.dispatch(s, 'vcell_observe', {'id': c['cell']['id'], 'readout': 'expression', 'genes': ['G5', 'nope']})
        self.assertEqual(e['notInPanel'], ['NOPE'])
        cat = V.dispatch(s, 'vcell_catalog', {})
        self.assertTrue(cat['reference']['ready'])
        json.dumps(cat, allow_nan=False)                                 # the manifest's NaN benchmark entries are made JSON-safe
        json.dumps(e, allow_nan=False)
        with self.assertRaises(ValueError):
            V.dispatch(s, 'vcell_get', {'id': '../etc'})


def make_atlas(root):
    """A tiny Tahoe-like atlas: two lines (L1, L2), drug 'Drugx' at 0.05/0.5/5 µM on L1 and 0.5 µM on L2, plus DepMap rows."""
    folder = pathlib.Path(root, *D.FOLDER); folder.mkdir(parents=True)
    genes = GENES; (folder / 'genes.json').write_text(json.dumps(genes))
    conds, rows = [], []
    def add(line, depmap, drug, c, lfc):
        conds.append({'cellosaurus': line, 'drug': drug, 'concentration': c, 'plate': '1', 'unit': 'uM', 'depmap': depmap, 'cellLine': line + 'name', 'cellsTreated': 100, 'cellsControl': 400}); rows.append(lfc)
    up = np.zeros(len(genes)); up[3] = 1.0                    # 'Drugx' doubles G3, stronger at higher dose
    add('L1', 'ACH-1', 'Drugx', 0.05, up * 0.2); add('L1', 'ACH-1', 'Drugx', 0.5, up * 0.6); add('L1', 'ACH-1', 'Drugx', 5.0, up * 1.0)
    add('L2', 'ACH-2', 'Drugx', 0.5, up * 0.4)
    down = np.zeros(len(genes)); down[7] = -2.0
    add('L1', 'ACH-1', 'Drugy', 0.5, down)
    lfc = np.memmap(folder / 'lfc.f16', np.float16, 'w+', shape=(90000, len(genes))); se = np.memmap(folder / 'se.f16', np.float16, 'w+', shape=(90000, len(genes)))
    lfc[:] = np.nan; se[:] = 0.1
    for i, r in enumerate(rows):
        lfc[i] = r
    lfc.flush(); se.flush()
    (folder / 'conditions.json').write_text(json.dumps(conds)); (folder / 'progress.json').write_text(json.dumps({'done': list(range(1026))}))
    dm = pathlib.Path(root, 'oncology', 'depmap', '24Q4'); dm.mkdir(parents=True)
    (dm / 'expression.json').write_text(json.dumps({'models': ['ACH-1', 'ACH-2'], 'genes': genes}))
    np.save(dm / 'expression.npy', np.full((2, len(genes)), 3.0, np.float32))
    (dm / 'gene_effect.json').write_text(json.dumps({'models': ['ACH-1'], 'genes': genes}))
    np.save(dm / 'gene_effect.npy', np.full((1, len(genes)), -0.2, np.float32))


class DrugTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = self.tmp.name
        make_reference(self.root); make_atlas(self.root); V._CACHE.clear(); V._LINES.clear(); D._CACHE.clear()
        self.k562 = V.context_reference(self.root, 'K562'); self.l1 = V.context_reference(self.root, 'L1')

    def tearDown(self):
        self.tmp.cleanup()

    def test_k562_drug_is_transferred_mean_and_labelled_prediction(self):
        cid = V.create(self.root, self.k562, '', 'K562')['id']
        V.perturb(self.root, self.k562, cid, 'small_molecule', None, 'drugx', 0.5)
        s = V.replay(self.k562, V.load(self.root, cid)['history'])
        self.assertEqual(s['category'], 'C'); self.assertIn('transferred', s['composition'])
        expected = np.log1p(np.expm1(2.0) * 2 ** 0.5) - 2.0          # mean of 0.6 and 0.4 log2FC on G3
        self.assertAlmostEqual(s['delta'][3], expected, places=2)
        with self.assertRaisesRegex(ValueError, 'measured at'):
            V.perturb(self.root, self.k562, cid, 'small_molecule', None, 'Drugy', 0.2)

    def test_line_context_measured_interpolated_and_refused(self):
        cid = V.create(self.root, self.l1, '', 'L1')['id']
        b = V.branch(self.root, cid, 0)['id']
        V.perturb(self.root, self.l1, cid, 'small_molecule', None, 'Drugx', 0.5)
        s = V.replay(self.l1, V.load(self.root, cid)['history'])
        self.assertEqual(s['category'], 'A')
        self.assertAlmostEqual(s['delta'][3], np.log2((2 ** 3 - 1) * 2 ** 0.6 + 1) - 3, places=2)
        V.perturb(self.root, self.l1, b, 'small_molecule', None, 'Drugx', 1.5)
        si = V.replay(self.l1, V.load(self.root, b)['history'])
        self.assertEqual(si['category'], 'C'); self.assertIn('interpolated', si['composition'])
        with self.assertRaisesRegex(ValueError, 'outside the measured range'):
            V.perturb(self.root, self.l1, V.branch(self.root, cid, 0)['id'], 'small_molecule', None, 'Drugx', 50)
        with self.assertRaisesRegex(ValueError, 'No genetic-perturbation transcriptome'):
            V.perturb(self.root, self.l1, cid, 'gene_overexpression', 'G2')
        with self.assertRaisesRegex(ValueError, 'already applied'):
            V.perturb(self.root, self.l1, cid, 'small_molecule', None, 'DRUGX', 5.0)
        V.perturb(self.root, self.l1, cid, 'gene_knockout', 'G2')
        self.assertAlmostEqual(V.observe_fitness(self.l1, V.load(self.root, cid))['rows'][0]['chronos'], -0.2, places=5)

    def test_design_in_line_context_finds_the_drug(self):
        target = V.create(self.root, self.l1, '', 'L1')['id']
        V.perturb(self.root, self.l1, target, 'small_molecule', None, 'Drugy', 0.5)
        here = V.load(self.root, V.create(self.root, self.l1, '', 'L1')['id'])
        r = V.design(self.l1, here, {'delta': V.replay(self.l1, V.load(self.root, target)['history'])['delta']})
        self.assertEqual(r['candidates'][0]['ops'][0]['drug'], 'Drugy')
        self.assertAlmostEqual(r['candidates'][0]['distanceRemoved'], 1.0, places=4)

    def test_dispatch_lists_contexts_and_drugs(self):
        s = types.SimpleNamespace(root=self.root, setting=lambda k: None)
        cat = V.dispatch(s, 'vcell_catalog', {})
        self.assertEqual([c['id'] for c in cat['contexts']], ['K562', 'L1', 'L2'])
        self.assertEqual(cat['drugs']['list'][0]['concentrations'], [0.05, 0.5, 5.0])
        c = V.dispatch(s, 'vcell_create', {'context': 'L2'})
        r = V.dispatch(s, 'vcell_perturb', {'id': c['cell']['id'], 'op': 'small_molecule', 'drug': 'Drugx', 'concentration': 0.5})
        self.assertEqual(r['state']['drugs'], [{'drug': 'Drugx', 'concentration': 0.5}])
        json.dumps(V.dispatch(s, 'vcell_observe', {'id': c['cell']['id'], 'readout': 'expression'}), allow_nan=False)


class EmbeddingRankingTests(unittest.TestCase):
    def test_knockout_that_moves_toward_target_ranks_first(self):
        W = np.eye(4)[:, :2]                                             # embedding reads genes A and B
        cells = np.array([[1.0, 1.0, 1.0, 1.0]] * 5)
        r = V.embedding_knockout_ranking(lambda x: x @ W, cells, ['A', 'B', 'C', 'D'], ['A', 'B', 'C', 'Z'], np.array([0.0, 1.0]))
        self.assertEqual(r[0]['gene'], 'A'); self.assertAlmostEqual(r[0]['shift'], 1.0)
        self.assertEqual({x['gene'] for x in r}, {'A', 'B', 'C'})


class ResourceTests(unittest.TestCase):
    def test_every_resource_states_its_licence_and_source(self):
        for k, r in P.RESOURCES.items():
            for f in P.REQUIRED:
                self.assertIn(f, r, f'{k} lacks {f}')
            if r['nonCommercial']:
                self.assertTrue(r['plugin'] or k in ('replogle2022',), f'{k} is non-commercial and must be an optional plugin')

    def test_notice_includes_installed_resources_with_attribution(self):
        with tempfile.TemporaryDirectory() as root:
            pathlib.Path(root, P.RESOURCES['gbcell']['localPath']).mkdir(parents=True)
            text = P.notice(root)
            self.assertIn('Powered by GenBio AI', text); self.assertNotIn('Tahoe', text)

    def test_release_check_blocks_weights_data_and_library_content(self):
        script = ROOT / 'scripts' / 'check-release-licenses.py'
        bad = subprocess.run([sys.executable, str(script), 'm/model.safetensors', 'd/x.h5ad', 'lib/virtualcell/cache/metabolism/a.json', 'src/App.tsx'],
                             capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(bad.stdout.count('BLOCKED'), 3)
        ok = subprocess.run([sys.executable, str(script), 'src/App.tsx'], capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(ok.returncode, 0)


if __name__ == '__main__':
    unittest.main()
