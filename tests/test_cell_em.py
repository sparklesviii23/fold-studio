import gzip, io, json, math, pathlib, struct, sys, tempfile, types, unittest, zlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scientific'))
import numpy as np
import cell_em as E, cell_em_actions, virtual_cell_results as VRS


def grid():
    """A synthetic class grid: cytosol box with an outside rim, a nucleus block and a mitochondrion slab."""
    g = np.zeros((24, 20, 30), np.uint8)               # z, y, x
    g[2:22, 2:18, 2:28] = E.KEYS['cytosol']
    g[8:16, 6:14, 10:20] = E.KEYS['nucleus']
    g[4:7, 4:16, 4:26] = E.KEYS['mito']
    return g


class FormatTests(unittest.TestCase):
    def test_n5_block_decodes_with_x_fastest(self):
        data = np.arange(2 * 3 * 4, dtype='>u2')        # stored x fastest: index = x + 2*(y + 3*z)
        raw = struct.pack('>HHIII', 0, 3, 2, 3, 4) + gzip.compress(data.tobytes())
        b = E.decode_block(raw, 'uint16')
        self.assertEqual(b.shape, (4, 3, 2))
        self.assertEqual(int(b[3, 2, 1]), 1 + 2 * (2 + 3 * 3))
        with self.assertRaises(E.EMError):
            E.decode_block(struct.pack('>HHIII', 1, 3, 2, 3, 4) + gzip.compress(data.tobytes()), 'uint16')

    def test_classes_paint_order_and_outside(self):
        shape = (2, 2, 2); z = lambda: np.zeros(shape, bool)
        seg = {a.split('/')[-1]: z() for a in E.ARRAYS[1:]}
        seg['foreground'][:] = True; seg['foreground'][0, 0, 0] = False
        seg['ecs_seg'][0, 0, 1] = True
        seg['er_seg'][1, 1, 1] = True; seg['mito_seg'][1, 1, 1] = True      # mito is painted after ER
        c = E.classes_from(seg)
        self.assertEqual(c[0, 0, 0], 0); self.assertEqual(c[0, 0, 1], 0)
        self.assertEqual(c[1, 0, 0], E.KEYS['cytosol']); self.assertEqual(c[1, 1, 1], E.KEYS['mito'])

    def test_install_requires_confirmation(self):
        with self.assertRaises(E.EMError):
            E.install(types.SimpleNamespace(root='/nonexistent'), {})


class PhysicsTests(unittest.TestCase):
    def test_stokes_einstein_matches_gfp_in_water(self):
        self.assertAlmostEqual(E.water_viscosity(298.15) * 1e3, 0.89, delta=0.01)
        self.assertAlmostEqual(E.diffusion_coefficient(2.8, 298.15, 1.0), 87, delta=3)     # GFP, room temperature
        self.assertAlmostEqual(E.diffusion_coefficient(2.8, 310.15, 3.2) * 3.2, E.diffusion_coefficient(2.8, 310.15, 1.0))

    def test_free_control_reproduces_6dt(self):
        c = E.free_control(40.0, (E.STEP_FRACTION * min(E.VOXEL)) ** 2 / 80.0, 3)
        self.assertLess(abs(c['z']), 4); self.assertEqual(c['edgeHits'], 0)

    def test_walk_never_leaves_accessible_classes_and_counts_encounters(self):
        g = grid(); rng = np.random.default_rng(5); n = 300
        allowed = np.zeros(E.EDGE + 1, bool); allowed[E.KEYS['cytosol']] = True
        x, home = E._release(g, {'compartment': 'cytosol'}, n, rng)
        self.assertEqual(home, E.KEYS['cytosol'])
        D = 30.0; dt = (E.STEP_FRACTION * min(E.VOXEL)) ** 2 / (2 * D)
        y, bound, frames, enc, binds, rel = E.walk(g, x, np.zeros(n, bool), allowed, D, dt, 4000, 500, rng)
        self.assertTrue((E.class_at(g, y) == E.KEYS['cytosol']).all())
        self.assertEqual(len(frames), 8); self.assertEqual(binds, 0); self.assertFalse(bound.any())
        self.assertGreater(enc[E.KEYS['nucleus']], 0); self.assertGreater(enc[E.KEYS['mito']], 0); self.assertGreater(enc[0], 0)
        self.assertEqual(enc[E.KEYS['cytosol']], 0)

    def test_rejection_walk_keeps_uniform_density(self):
        g = np.zeros((12, 12, 12), np.uint8); g[2:10, 2:10, 2:10] = 1
        rng = np.random.default_rng(11); n = 6000
        allowed = np.zeros(E.EDGE + 1, bool); allowed[1] = True
        x, _ = E._release(g, {'compartment': 'cytosol'}, n, rng)
        D = 30.0; dt = (E.STEP_FRACTION * min(E.VOXEL)) ** 2 / (2 * D)
        y, *_ = E.walk(g, x, np.zeros(n, bool), allowed, D, dt, 1500, 1500, rng)
        u = (y[:, 0] / E.VOXEL[0] - 2) / 8                                  # uniform on 0–1 when the density stays flat
        counts = np.histogram(u, bins=8, range=(0, 1))[0]
        chi2 = ((counts - n / 8) ** 2 / (n / 8)).sum()
        self.assertLess(chi2, 26.0)                                         # χ²(7) upper 0.05 % point ≈ 26

    def test_binding_and_release(self):
        g = grid(); rng = np.random.default_rng(2); n = 200
        allowed = np.zeros(E.EDGE + 1, bool); allowed[E.KEYS['cytosol']] = True
        x, _ = E._release(g, {'compartment': 'cytosol'}, n, rng)
        D = 30.0; dt = (E.STEP_FRACTION * min(E.VOXEL)) ** 2 / (2 * D)
        y, bound, _, _, binds, rel = E.walk(g, x, np.zeros(n, bool), allowed, D, dt, 3000, 3000, rng, E.KEYS['mito'], 1.0, 0.0)
        self.assertGreater(binds, 0); self.assertEqual(rel, 0); self.assertEqual(int(bound.sum()), binds)
        z, bound2, _, _, _, rel2 = E.walk(g, y, bound, allowed, D, dt, 400, 400, rng, E.KEYS['mito'], 0.0, 1e9)
        self.assertEqual(rel2, binds); self.assertFalse(bound2.any())

    def test_simulate_streams_and_is_repeatable(self):
        g = grid()
        with tempfile.TemporaryDirectory() as root:
            s = types.SimpleNamespace(root=root)
            p = {'particles': 40, 'release': {'compartment': 'cytosol'}, 'target': 'mito', 'pBind': 0.3, 'koff': 50, 'frameSeconds': 0.0005}
            a = E.simulate(s, p, g); b = E.simulate(s, p, g)
            self.assertEqual(a['frames'], b['frames']); self.assertEqual(len(a['frames']), E.FRAMES); self.assertEqual(len(a['frames'][0]), 120)
            self.assertTrue(a['passed']); self.assertEqual([c['name'] for c in a['checks']][0], 'Free-diffusion control')
            c = E.simulate(s, json.loads(json.dumps({'state': a['state']})), g)
            self.assertEqual(c['id'], a['id']); self.assertAlmostEqual(c['time'][0], a['time'][-1] + a['time'][0], places=6)
            self.assertEqual(c['checks'][0]['name'], 'Free-diffusion control')
            total = lambda r: sum(r['species'][0]['encounters'].values())
            self.assertGreaterEqual(total(c), total(a)); self.assertGreater(c['events']['binds'], 0)
            rec = VRS.get(root, 'cell_em', a['id'])                          # the Virtual Cell adapter reads the saved record
            self.assertTrue(rec['integrity']['match']); self.assertEqual(rec['evidence']['category'], 'B')
            self.assertEqual(len(E.runs(s)), 2)

    def test_point_release_nuclear_group_and_rejected_inputs(self):
        g = grid(); s = types.SimpleNamespace(root=None)
        point = [15 * E.VOXEL[0], 10 * E.VOXEL[1], 12 * E.VOXEL[2]]
        r = E.simulate(s, {'particles': 5, 'release': {'point': point}, 'frameSeconds': 0.0002}, g)
        self.assertEqual(r['species'][0]['home'], 'nucleus'); self.assertEqual(r['species'][0]['accessible'], ['nucleus', 'chromatin', 'nucleolus'])
        r = E.simulate(s, {'particles': 5, 'release': {'point': point}, 'nuclearExchange': True, 'frameSeconds': 0.0002}, g)
        self.assertEqual(r['species'][0]['accessible'], ['cytosol', 'nucleus', 'chromatin', 'nucleolus', 'ne'])
        for bad in ({'radiusNm': 0}, {'particles': 1000}, {'release': {'compartment': 'nowhere'}}, {'release': {'point': [-1, 0, 0]}},
                    {'release': {'compartment': 'cytosol'}, 'target': 'cytosol'}, {'species': [{}] * 5},
                    {'species': [{}, {}], 'pairs': [{'a': 0, 'b': 0}]}, {'species': [{}, {}], 'pairs': [{'a': 0, 'b': 1}, {'a': 1, 'b': 0}]}):
            with self.assertRaises(E.EMError):
                E.simulate(s, bad, g)

    def test_two_species_form_and_break_complexes(self):
        g = np.zeros((14, 14, 14), np.uint8); g[2:12, 2:12, 2:12] = 1
        s = types.SimpleNamespace(root=None)
        p = {'species': [{'name': 'Target', 'radiusNm': 5, 'particles': 60}, {'name': 'Binder', 'radiusNm': 2, 'particles': 60}],
             'pairs': [{'a': 0, 'b': 1, 'reachNm': 200, 'rate': 1e5, 'koff': 0}], 'frameSeconds': 0.0005}
        r = E.simulate(s, p, g)
        self.assertTrue(r['passed']); self.assertEqual(r['owner'], [0] * 60 + [1] * 60)
        self.assertGreater(r['events']['pairBinds'], 10); self.assertEqual(r['events']['pairReleases'], 0)
        self.assertEqual(r['species'][0]['complexFraction'][-1], r['species'][1]['complexFraction'][-1])
        last = np.array(r['frames'][-1]).reshape(-1, 3); partner = np.array(r['state']['partner'])
        joined = np.flatnonzero(partner >= 0)
        self.assertEqual(len(joined), 2 * r['events']['pairBinds']); self.assertEqual(sorted(i for pair in r['paired'][-1] for i in pair), joined.tolist())
        self.assertTrue(np.allclose(last[joined], last[partner[joined]]))                 # both copies of a complex share one position
        self.assertTrue((partner[partner[joined]] == joined).all())
        st = r['state']; st['config']['pairs'][0].update({'rate': 0, 'koff': 1e4})        # then let every complex dissociate
        r2 = E.simulate(s, json.loads(json.dumps({'state': st})), g)
        self.assertEqual(r2['events']['pairReleases'], r['events']['pairBinds']); self.assertEqual(r2['species'][0]['complexFraction'][-1], 0.0)

    def test_complex_diffuses_as_the_summed_volume_sphere(self):
        g = np.ones((40, 40, 40), np.uint8); n = 1500; rng = np.random.default_rng(4)
        x0 = np.tile(np.array([20 * v for v in E.VOXEL]), (2 * n, 1))
        species = np.repeat([0, 1], n); partner = np.concatenate([np.arange(n, 2 * n), np.arange(n)])
        D = np.array([20.0, 60.0]); dt = (E.STEP_FRACTION * min(E.VOXEL)) ** 2 / (2 * D.max()); steps = 40
        allowed = np.ones((2, E.EDGE + 1), bool); allowed[:, E.EDGE] = False
        x, *_ = E.walk(g, x0, np.zeros(2 * n, bool), allowed, D, dt, steps, steps, rng, [-1, -1], [0, 0], [0, 0], species, partner, [])
        expected = 6 * (D[0] ** -3 + D[1] ** -3) ** (-1 / 3) * dt * steps
        sq = ((x[:n] - x0[:n]) ** 2).sum(axis=1)
        self.assertLess(abs(sq.mean() - expected) / (sq.std(ddof=1) / math.sqrt(n)), 4)
        self.assertTrue(np.array_equal(x[:n], x[n:]))


class ExperimentTests(unittest.TestCase):
    PAIR = {'species': [{'name': 'Target', 'radiusNm': 5, 'particles': 50, 'structure': 't.pdb', 'structureSha256': 'a' * 64}, {'name': 'Binder', 'radiusNm': 2, 'particles': 50}],
            'pairs': [{'a': 0, 'b': 1, 'reachNm': 200, 'rate': 1e5, 'koff': 200}], 'frameSeconds': 0.0005, 'label': 'baseline'}

    def box(self):
        g = np.zeros((14, 14, 14), np.uint8); g[2:12, 2:12, 2:12] = 1
        return g

    def test_events_match_counts_frames_and_the_saved_record(self):
        g = self.box()
        with tempfile.TemporaryDirectory() as root:
            s = types.SimpleNamespace(root=root)
            r = E.simulate(s, dict(self.PAIR), g)
            binds = [e for e in r['pairEvents'] if e['kind'] == 'bind']; unbinds = [e for e in r['pairEvents'] if e['kind'] == 'unbind']
            self.assertEqual(len(binds), r['events']['pairBinds']); self.assertEqual(len(unbinds), r['events']['pairReleases']); self.assertGreater(len(binds), 5)
            e = binds[0]; frame = np.array(r['frames'][e['frame']]).reshape(-1, 3)
            self.assertIn([e['a'], e['b']], r['paired'][e['frame']] + [[u['a'], u['b']] for u in unbinds])       # visible in the frame it is reported for, unless already apart
            self.assertEqual(e['species'], ['Target', 'Binder']); self.assertEqual(e['compartment'], 'cytosol')
            self.assertLessEqual(e['time'], r['time'][e['frame']] + 1e-9)
            self.assertTrue(np.allclose(frame[e['a']], frame[e['b']]) or [e['a'], e['b']] not in r['paired'][e['frame']])
            rec = E.run_get(s, {'id': r['id']})
            self.assertEqual(len(rec['outputs']['pairEvents']), min(len(r['pairEvents']), E.MAX_EVENTS)); self.assertEqual(rec['outputs']['events'], r['events'])
            self.assertEqual(rec['outputs']['pairEventsTruncated'], len(r['pairEvents']) > E.MAX_EVENTS)
            self.assertEqual(rec['experiment']['config']['species'][0]['structureSha256'], 'a' * 64); self.assertEqual(rec['experiment']['label'], 'baseline')
            again = E.simulate(types.SimpleNamespace(root=None), dict(rec['experiment']['config']), g)             # replay from the saved configuration
            self.assertEqual(again['frames'], r['frames']); self.assertEqual(again['pairEvents'], r['pairEvents'])
            self.assertEqual(E.runs(s)[0]['species'], ['Target', 'Binder']); self.assertTrue(E.runs(s)[0]['replayable'])
            self.assertTrue(VRS.get(root, 'cell_em', r['id'])['integrity']['match'])
            with self.assertRaises(E.EMError):
                E.run_get(s, {'id': '../x'})

    def test_preview_places_without_advancing_or_saving(self):
        with tempfile.TemporaryDirectory() as root:
            s = types.SimpleNamespace(root=root)
            p = E.simulate(s, {**self.PAIR, 'preview': True}, self.box())
            self.assertTrue(p['preview']); self.assertEqual(len(p['frames']), 1); self.assertEqual(len(p['frames'][0]), 300); self.assertEqual(E.runs(s), [])
            r = E.simulate(s, dict(self.PAIR), self.box())
            self.assertTrue(np.allclose(np.array(r['state']['x0']), np.array(p['frames'][0]), atol=1e-4))            # the preview shows the real start positions

    def test_compare_reports_changes_and_identical_dynamics(self):
        g = self.box()
        with tempfile.TemporaryDirectory() as root:
            s = types.SimpleNamespace(root=root)
            base = E.simulate(s, dict(self.PAIR), g)
            renamed = {**self.PAIR, 'label': 'variant', 'parent': base['id'], 'species': [{**self.PAIR['species'][0], 'name': 'Target v2', 'structure': 'v2.pdb', 'structureSha256': 'b' * 64}, self.PAIR['species'][1]]}
            same = E.simulate(s, renamed, g)
            c = E.compare(s, {'baseline': base['id'], 'variant': same['id'], 'chunks': 2}, g)
            json.dumps(c)                                                                                          # the answer must serialise
            self.assertTrue(c['identicalDynamics']); self.assertTrue(c['matchedTime']); self.assertEqual(c['baseline']['events'], c['variant']['events'])
            self.assertEqual({x['what'] for x in c['changed']}, {'molecule 1 · name', 'molecule 1 · structure', 'molecule 1 · structureSha256'})
            self.assertEqual(c['baseline']['series']['species'][0]['complex'], c['variant']['series']['species'][0]['complex'])
            self.assertEqual(E.run_get(s, {'id': same['id']})['experiment']['parent'], base['id'])
            weaker = E.simulate(s, {**renamed, 'pairs': [{'a': 0, 'b': 1, 'reachNm': 200, 'rate': 0, 'koff': 200}]}, g)
            c = E.compare(s, {'baseline': base['id'], 'variant': weaker['id'], 'chunks': 2}, g)
            self.assertFalse(c['identicalDynamics']); self.assertEqual(c['variant']['events']['pairBinds'], 0); self.assertGreater(c['baseline']['events']['pairBinds'], 0)
            faster = E.simulate(s, {**renamed, 'species': [renamed['species'][0], {**self.PAIR['species'][1], 'radiusNm': 0.6}]}, g)       # a smaller partner shortens the time step
            c2 = E.compare(s, {'baseline': base['id'], 'variant': faster['id'], 'chunks': 1}, g)
            json.dumps(c2); self.assertTrue(c2['matchedTime']); self.assertGreater(max(c2['variant']['chunks'], c2['baseline']['chunks']), 1)       # one side needed more chunks to reach the common time
            self.assertIn('pair interactions', {x['what'] for x in c['changed']})
            self.assertEqual(len(E.runs(s)), 4)                                                                       # comparing saves nothing


class StructureAndPaintingTests(unittest.TestCase):
    PDB = ''.join(f"ATOM  {i + 1:5d}  CA  ALA A{i + 1:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C\n" for i, (x, y, z) in enumerate((a * 3.8, 0.0, 0.0) for a in range(12))) + \
        "ATOM     13  H   ALA A  12      50.000  50.000  50.000  1.00  0.00           H\nHETATM   14  O   HOH A 100       9.000   9.000   9.000  1.00  0.00           O\nENDMDL\nATOM     15  CA  ALA A   1      99.000  99.000  99.000  1.00  0.00           C\n"

    def test_pdb_and_mmcif_atoms(self):
        xyz, el, ch, het = E.parse_atoms(self.PDB, 'pdb')
        self.assertEqual(len(xyz), 12); self.assertEqual(set(el), {'C'}); self.assertEqual(set(ch), {'A'})       # hydrogen, water and model 2 dropped
        cif = 'data_x\nloop_\n_atom_site.group_PDB\n_atom_site.type_symbol\n_atom_site.label_comp_id\n_atom_site.auth_asym_id\n_atom_site.Cartn_x\n_atom_site.Cartn_y\n_atom_site.Cartn_z\n_atom_site.pdbx_PDB_model_num\n' + \
            ''.join(f'ATOM C ALA B {i * 3.8:.3f} 0.000 0.000 1\n' for i in range(12)) + 'HETATM ZN ZN B 1.0 1.0 1.0 1\nATOM C ALA B 5.0 5.0 5.0 2\n#\n'
        xyz2, el2, ch2, het2 = E.parse_atoms(cif, 'mmcif')
        self.assertEqual(len(xyz2), 13); self.assertEqual(el2[-1], 'ZN'); self.assertTrue(het2[-1]); self.assertTrue(np.allclose(xyz2[:12], xyz))

    def test_structure_action_reads_only_library_assets(self):
        with tempfile.TemporaryDirectory() as root:
            (pathlib.Path(root) / 'assets').mkdir(); (pathlib.Path(root) / 'assets' / 'rod.pdb').write_text(self.PDB)
            s = types.SimpleNamespace(root=root)
            r = E.structure(s, {'asset': 'rod.pdb'})
            rg = math.sqrt(sum((i * 3.8 - 5.5 * 3.8) ** 2 for i in range(12)) / 12) / 10
            self.assertEqual(r['kind'], 'protein'); self.assertEqual(r['residueCount'], 12); self.assertEqual(r['residues'][0], ['A', 'ALA', '1'])
            self.assertEqual(r['atomNames'], ['CA']); self.assertEqual(r['residueOf'], list(range(12)))
            self.assertEqual(r['atoms'], 12); self.assertAlmostEqual(r['rgNm'], rg, places=4); self.assertAlmostEqual(r['radiusNm'], math.sqrt(5 / 3) * rg, places=4)
            self.assertAlmostEqual(sum(r['xyz'][0::3]), 0, places=1)
            for bad in ('../rod.pdb', 'rod.txt', 'missing.pdb', ''):
                with self.assertRaises(E.EMError):
                    E.structure(s, {'asset': bad})

    def test_painting_channels_follow_their_classes(self):
        with tempfile.TemporaryDirectory() as root:
            d = E.folder(root) / 'derived'; d.mkdir(parents=True)
            g = grid(); g[10:12, 8:12, 13:17] = E.KEYS['nucleolus']
            np.save(d / 'classes_u8.npy', g)
            s = types.SimpleNamespace(root=root)
            r = E.paint(s, {'psfNm': 200, 'molecules': [3 * E.VOXEL[0], 0.5, 3 * E.VOXEL[2]]})
            self.assertEqual(list(r['images']), ['DNA', 'RNA', 'ER', 'AGP', 'Mito', 'Probe']); self.assertEqual(r['evidence']['category'], 'D'); self.assertEqual(r['size'], [30, 24])
            from PIL import Image
            import base64
            img = lambda k: np.asarray(Image.open(io.BytesIO(base64.b64decode(r['images'][k]))).convert('RGB')).sum(axis=2).astype(int)
            self.assertGreater(img('Mito')[5, 15], 5 * img('Mito')[19, 15])              # the mitochondrion slab is at z 4–6
            self.assertGreater(img('RNA')[11, 15], 1.5 * img('RNA')[19, 5]); self.assertGreater(img('DNA')[9, 12], img('DNA')[19, 3])
            self.assertEqual(np.unravel_index(img('Probe').argmax(), (24, 30)), (3, 3))
            self.assertTrue((pathlib.Path(root) / 'cell_em' / 'paintings' / (r['id'] + '.png')).is_file())
            with self.assertRaises(E.EMError):
                E.paint(s, {'psfNm': 5})


class RegistrationTests(unittest.TestCase):
    def test_actions_are_registered(self):
        self.assertEqual(cell_em_actions.ACTIONS, {'cell_em_catalog', 'cell_em_install', 'cell_em_volume', 'cell_em_simulate', 'cell_em_structure', 'cell_em_paint', 'cell_em_runs', 'cell_em_run_get', 'cell_em_compare',
                                                   'cell_em_replicates', 'cell_em_sweep', 'cell_em_crowding', 'cell_em_region', 'cell_em_registration'})
        self.assertIs(E.ACTIONS, cell_em_actions.ACTIONS)



def two_boxes():
    """Two cytosol-like boxes (classes cytosol and nucleus) separated by a two-voxel wall of nuclear envelope."""
    g = np.zeros((14, 14, 34), np.uint8)                # z, y, x
    g[2:12, 2:12, 2:16] = E.KEYS['cytosol']; g[2:12, 2:12, 16:18] = E.KEYS['ne']; g[2:12, 2:12, 18:32] = E.KEYS['nucleus']
    return g


class KineticsTests(unittest.TestCase):
    """Numerical benchmarks of the processes added in engine 3: each is compared with its closed-form result."""

    def setup(self, g, n, home, classes, D=20.0):
        rng = np.random.default_rng(11); allowed = np.zeros((1, E.EDGE + 1), bool); allowed[0, [E.KEYS[c] for c in classes]] = True
        x, _ = E._release(g, {'compartment': home}, n, rng)
        dt = (E.STEP_FRACTION * min(E.VOXEL)) ** 2 / (2 * D)
        return rng, allowed, x, dt, D

    def test_permeable_boundary_equilibrates_at_the_two_compartment_rate(self):
        g = two_boxes(); n = 600; rng, allowed, x, dt, D = self.setup(g, n, 'cytosol', ('cytosol', 'nucleus'))
        kappa = 2.0                                             # µm/s; κL/D ≈ 0.09, so each box stays well mixed
        hop = np.zeros((1, E.EDGE + 1)); hop[0, E.KEYS['ne']] = kappa * math.sqrt(math.pi * dt / D)
        self.assertLess(hop.max(), E.MAX_HOP)
        kin = {'alive': np.ones(n, bool), 'hop': hop, 'far': {(0, E.KEYS['ne']): ({E.KEYS['cytosol']}, {E.KEYS['nucleus']})}}
        steps, every = 24000, 2000
        _, _, frames, _, counts, _ = E.walk(g, x, np.zeros(n, bool), allowed, [D], dt, steps, every, rng, [-1], [0.0], [0.0], np.zeros(n, np.int64), None, (), E.VOXEL, kin)
        area = 10 * E.VOXEL[1] * 10 * E.VOXEL[2]; volume = 14 * E.VOXEL[0] * area       # the two boxes are equal
        rate = kappa * area * 2 / volume
        t = np.arange(1, len(frames) + 1) * every * dt
        got = np.array([(E.class_at(g, f[0]) == E.KEYS['nucleus']).mean() for f in frames]); want = 0.5 * (1 - np.exp(-rate * t))
        self.assertLess(np.abs(got - want).max(), 0.05, (got.round(3), want.round(3)))
        fitted = -np.log(1 - 2 * np.clip(got[:6], 0, 0.49)) / t[:6]
        self.assertAlmostEqual(float(fitted.mean()) / rate, 1.0, delta=0.15)
        self.assertTrue(np.isin(E.class_at(g, frames[-1][0]), [E.KEYS['cytosol'], E.KEYS['nucleus']]).all())      # nobody rests inside the wall
        self.assertGreater(int(counts['crossings'].sum()), 100); self.assertEqual(counts['thick'], 0)

    def test_synthesis_and_decay_reach_the_expected_steady_state(self):
        g = grid(); cap = 300; rng, allowed, x, dt, D = self.setup(g, cap, 'cytosol', ('cytosol',))
        k_syn, k_dec = 40000.0, 400.0                           # copies/s and 1/s: steady state 100 copies, lifetime 2.5 ms
        alive = np.zeros(cap, bool); alive[:20] = True
        kin = {'alive': alive, 'decay': [-math.expm1(-k_dec * dt)], 'births': [(0, k_syn * dt, np.flatnonzero(g.ravel() == E.KEYS['cytosol']))]}
        steps = int(0.05 / dt); every = max(1, steps // 200)
        _, _, frames, _, counts, _ = E.walk(g, x, np.zeros(cap, bool), allowed, [D], dt, steps, every, rng, [-1], [0.0], [0.0], np.zeros(cap, np.int64), None, (), E.VOXEL, kin)
        late = np.array([f[3].sum() for f in frames[len(frames) // 2:]])
        self.assertAlmostEqual(late.mean(), k_syn / k_dec, delta=8)       # mean of a Poisson(100) process sampled over ≈ 10 lifetimes
        self.assertLess(abs(late.var() / late.mean() - 1), 0.6)           # Poisson: variance ≈ mean
        self.assertEqual(counts['saturated'], 0)
        self.assertEqual(int(counts['alive'].sum()), 20 + counts['born'] - counts['died'])
        self.assertTrue((E.class_at(g, frames[-1][0][frames[-1][3]]) == E.KEYS['cytosol']).all())

    def test_conversion_follows_first_order_decay_and_conserves_copies(self):
        g = grid(); n = 400; rng = np.random.default_rng(3)
        allowed = np.zeros((2, E.EDGE + 1), bool); allowed[:, E.KEYS['cytosol']] = True
        x, _ = E._release(g, {'compartment': 'cytosol'}, n, rng); owner = np.repeat([0, 1], [200, 200])
        alive = owner == 0; D = 20.0; dt = (E.STEP_FRACTION * min(E.VOXEL)) ** 2 / (2 * D); k = 300.0
        kin = {'alive': alive, 'convert': [(0, 1, -math.expm1(-k * dt))]}
        steps = int(0.006 / dt); every = steps // 12
        _, _, frames, _, counts, _ = E.walk(g, x, np.zeros(n, bool), allowed, [D, D], dt, steps, every, rng, [-1, -1], [0.0, 0.0], [0.0, 0.0], owner, None, (), E.VOXEL, kin)
        t = np.arange(1, len(frames) + 1) * every * dt
        a = np.array([f[3][owner == 0].sum() for f in frames]); b = np.array([f[3][owner == 1].sum() for f in frames])
        self.assertTrue((a + b == 200).all())
        self.assertLess(np.abs(a / 200 - np.exp(-k * t)).max(), 0.08)
        self.assertEqual(counts['converted'], 200 - int(counts['alive'][owner == 0].sum()))

    def test_simulate_with_kinetics_keeps_counts_and_continues(self):
        g = two_boxes(); quiet = types.SimpleNamespace(root=None)
        req = {'seed': 4, 'species': [{'name': 'A', 'radiusNm': 2.8, 'particles': 60, 'capacity': 120, 'release': {'compartment': 'cytosol'}, 'synthesis': {'rate': 300.0, 'compartment': 'cytosol'}, 'decay': 2.0,
                                       'exchange': [{'through': 'ne', 'to': 'nucleus', 'permeabilityUmS': 3.0}]},
                                      {'name': 'B', 'radiusNm': 2.8, 'particles': 0 + 1, 'capacity': 80, 'release': {'compartment': 'cytosol'}}], 'reactions': [{'from': 0, 'to': 1, 'rate': 4.0}]}
        r = E.simulate(quiet, req, g); r2 = E.simulate(quiet, {'state': r['state']}, g)
        for out in (r, r2):
            self.assertTrue(out['passed'], out['checks'])
            self.assertIn('Counts agree with events', [c['name'] for c in out['checks']])
            self.assertEqual(len(out['absent']), E.FRAMES)
        a = r2['species'][0]
        self.assertEqual(len(a['present']), E.FRAMES); self.assertTrue(a['crossings'].get('ne', 0) > 0)
        self.assertEqual(sum(v[-1] for v in a['occupancySeries'].values()), a['present'][-1])           # plotted occupancy adds up to the copies present
        self.assertEqual(r2['events']['born'] + r2['events']['converted'] >= r['events']['born'] + r['events']['converted'], True)
        self.assertIn('nucleus', a['occupancySeries'])
        with self.assertRaises(E.EMError):                       # a permeability the time step cannot represent is refused, not clamped
            E.simulate(quiet, {**req, 'species': [{**req['species'][0], 'exchange': [{'through': 'ne', 'to': 'nucleus', 'permeabilityUmS': 9e4}]}, req['species'][1]]}, g)
        with self.assertRaises(E.EMError):
            E.simulate(quiet, {**req, 'species': [{**req['species'][0], 'capacity': 10}, req['species'][1]]}, g)

    def test_runs_without_kinetics_are_unchanged_by_the_pool(self):
        g = grid(); quiet = types.SimpleNamespace(root=None)
        r = E.simulate(quiet, {'seed': 9, 'radiusNm': 2.8, 'particles': 50}, g)
        self.assertIsNone(r['absent']); self.assertFalse(r['solver']['kinetics']); self.assertEqual(r['species'][0]['present'], [50] * E.FRAMES)
        self.assertEqual([c['name'] for c in r['checks']], ['Free-diffusion control', 'Confinement', 'Step length'])


class ContextTests(unittest.TestCase):
    def test_illustrative_rod_has_plausible_volumes_and_runs(self):
        cls, voxel, m, sha = E.geometry(None, E.ECOLI)
        self.assertTrue(m['illustrative']); self.assertEqual(len(sha), 64)
        vol = {c['key']: c['volumeUm3'] for c in m['classes']}
        cell = vol['cytosol'] + vol['pm'] + vol['chromatin']
        r, h = E.ROD['radius'], E.ROD['halfLength']
        self.assertAlmostEqual(cell, math.pi * r * r * 2 * h + 4 / 3 * math.pi * r ** 3, delta=0.03)       # spherocylinder
        self.assertEqual(set(np.unique(cls)), {0, E.KEYS['cytosol'], E.KEYS['pm'], E.KEYS['chromatin']})
        out = E.simulate(types.SimpleNamespace(root=None), {'context': E.ECOLI, 'seed': 2, 'radiusNm': 2.8, 'particles': 80})
        self.assertTrue(out['passed'], out['checks']); self.assertEqual(out['context'], E.ECOLI)
        self.assertAlmostEqual(out['species'][0]['D'], E.GFP_ECOLI_D, delta=0.05)     # the context's calibrated default
        self.assertEqual(out['solver']['geometry'], 'illustrative'); self.assertIn('illustrative', out['state']['config']['context'] and E.CONTEXTS[E.ECOLI]['geometry'])
        self.assertIsNone(out['solver']['dataset'])
        with self.assertRaises(E.EMError):
            E.volume(types.SimpleNamespace(root=None), {'kind': 'em', 'context': E.ECOLI})

    def test_contexts_keep_their_own_default_slowdown(self):
        self.assertEqual(E.context_defaults(E.HELA)['slowdown']['value'], 3.2)
        self.assertEqual(E.context_defaults(E.HELA)['slowdown']['provenance']['kind'], 'assumed')
        self.assertEqual(E.context_defaults(E.ECOLI)['slowdown']['provenance']['kind'], 'literature')
        self.assertEqual(E._configure({'radiusNm': 2.8})['context'], E.HELA)
        with self.assertRaises(E.EMError):
            E._configure({'context': 'mouse'})

    def test_replicates_and_sweep_shapes(self):
        g = grid(); quiet = types.SimpleNamespace(root=None)
        cfg = {'seed': 5, 'species': [{'name': 'A', 'radiusNm': 3, 'particles': 40}, {'name': 'B', 'radiusNm': 3, 'particles': 40}], 'pairs': [{'a': 0, 'b': 1, 'reachNm': 150, 'rate': 3000, 'koff': 5}]}
        rep = E.replicates(quiet, {'config': cfg, 'seeds': 3, 'chunks': 1}, g)
        self.assertEqual(len(rep['seeds']), 3); self.assertEqual(len(set(rep['seeds'])), 3)
        c = rep['species'][0]['complex']; self.assertEqual(len(c['mean']), len(rep['time'])); self.assertTrue(all(a <= b for a, b in zip(c['min'], c['max'])))
        sw = E.sweep(quiet, {'config': cfg, 'parameter': 'pair.rate', 'values': [0, 6000], 'chunks': 1}, g)
        self.assertEqual(sw['rows'][0]['events']['pairBinds'], 0); self.assertGreater(sw['rows'][1]['events']['pairBinds'], 0)
        with self.assertRaises(E.EMError):
            E.sweep(quiet, {'config': cfg, 'parameter': 'colour', 'values': [1, 2]}, g)

    def test_crowding_benchmark_matches_obstruction_theory(self):
        r = E.crowding(None, {'volumeFraction': 0.1, 'crowderRadiusNm': 5.0, 'tracerRadiusNm': 1.0, 'seed': 3})
        self.assertTrue(r['check']['passed'], r); self.assertLess(r['relativeD'], 1.0); self.assertGreater(r['slowdown'], 1.0)
        self.assertAlmostEqual(r['excludedFraction'], 0.1 * 1.2 ** 3, delta=1e-6)

if __name__ == '__main__':
    unittest.main()
