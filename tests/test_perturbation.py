"""Perturbation lab routing: each engine represents only what it contains, and says so."""
import pathlib, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scientific'))
import perturbation as P

DRUGS = {'T': {'name': 'Trametinib', 'target': 'MEK1, MEK2'}, 'E': {'name': 'Erlotinib', 'target': 'EGFR'}}


class PerturbationTests(unittest.TestCase):
    def test_validation(self):
        with self.assertRaises(ValueError):
            P._norm_perturbations([])
        with self.assertRaises(ValueError):
            P._norm_perturbations([{'kind': 'interaction', 'pair': 'made–up'}])
        with self.assertRaises(ValueError):
            P._norm_perturbations([{'kind': 'teleport'}])
        p = P._norm_perturbations([{'kind': 'gene', 'gene': 'mek1', 'strength': 7}])[0]
        self.assertEqual((p['gene'], p['strength']), ('MAP2K1', 1.0))          # alias resolved, strength clamped

    def test_paralog_targets_scale_shared_term_once(self):
        perts = P._norm_perturbations([{'kind': 'compound', 'drug': 'T', 'strength': 0.9}])
        e = P.ode_model('mapk', perts, DRUGS)
        self.assertEqual(e['status'], 'ran')
        both = P.ode_model('mapk', P._norm_perturbations([{'kind': 'gene', 'gene': 'MAP2K1', 'strength': 0.9}]), DRUGS)
        self.assertAlmostEqual(e['metrics'][0][2], both['metrics'][0][2], places=6)   # MEK1+MEK2 at 90 % = one MEK term × 0.1

    def test_unmapped_perturbations_are_reported_not_used(self):
        e = P.ode_model('egfr', P._norm_perturbations([{'kind': 'immune', 'factor': 2}]), DRUGS)
        self.assertEqual(e['status'], 'not applicable'); self.assertEqual(len(e['ignored']), 1)
        k = P.kuznetsov(P._norm_perturbations([{'kind': 'gene', 'gene': 'EGFR'}]))
        self.assertEqual(k['status'], 'not applicable')

    def test_mechanistic_directions(self):
        egfr = P.ode_model('egfr', P._norm_perturbations([{'kind': 'compound', 'drug': 'E', 'strength': 0.9}]), DRUGS)
        self.assertLess(egfr['metrics'][0][2], egfr['metrics'][0][1])          # less receptor phosphorylation
        fb = P.ode_model('mapk', P._norm_perturbations([{'kind': 'interaction', 'pair': 'ERK⊣RAF feedback', 'factor': 0}]), DRUGS)
        self.assertGreater(fb['metrics'][0][2], fb['metrics'][0][1])            # removing negative feedback raises mean ERK-PP
        same = P.kuznetsov(P._norm_perturbations([{'kind': 'immune', 'factor': 1}]))
        self.assertAlmostEqual(same['metrics'][0][1], same['metrics'][0][2])    # factor 1 is no perturbation

    def test_published_models_known_directions(self):
        run = lambda mid, g, s=0.9: P.ode_model(mid, P._norm_perturbations([{'kind': 'gene', 'gene': g, 'strength': s}]), DRUGS)
        apc = run('lee', 'APC'); self.assertGreater(apc['metrics'][0][2], 2 * apc['metrics'][0][1])          # APC loss stabilises β-catenin
        bcl2 = run('albeck', 'BCL2'); self.assertLess(bcl2['metrics'][0][2], bcl2['metrics'][0][1])           # Bcl-2 loss: death sooner
        smad = run('zi', 'SMAD4', 1.0); self.assertLess(smad['metrics'][0][2], 1e-6)                          # no SMAD4, no nuclear SMAD complex
        jak = run('yamada', 'JAK1'); self.assertLess(jak['metrics'][0][2], 0.2 * jak['metrics'][0][1])
        pi3k = run('hatakeyama', 'PIK3CA'); akt = next(m for m in pi3k['metrics'] if 'AKT · peak' in m[0])
        self.assertLess(akt[2], 0.5 * akt[1]); self.assertAlmostEqual(pi3k['metrics'][0][2] / pi3k['metrics'][0][1], 1, delta=0.05)   # ERK branch untouched
        for e in (apc, bcl2, smad, jak, pi3k):
            self.assertTrue(e['reliable'], e['name'])

    def test_every_mapped_term_exists(self):
        import mechanistic_demos as demos, mechanistic_sbml as sbml
        for mid, M in P.MODELS.items():
            m = demos.load(M['demo']) if 'demo' in M else sbml.Model((demos.FIXTURES / (M['biomodels'] + '.xml')).read_text())
            species = {s['id'] for s in m.species}
            for g, (kind, terms, _) in M['genes'].items():
                for x in terms:
                    self.assertIn(x, species if kind == 'amount' else m.param_ids, (mid, g, x))
            for pair, terms in M['interactions'].items():
                for x in terms:
                    self.assertIn(x.split('~')[0], m.param_ids, (mid, pair, x))
            self.assertTrue(set(M['outputs']) <= species | set(m.symbols), mid)          # species or assignment-rule totals

    def test_concentration_mode(self):
        import chembl_potency as C
        pot = {'targets': {'MAP2K1': {'ic50_uM': 0.01}, 'ABCB1': {'ic50_uM': 10.0}}}
        inh = C.inhibition(pot, 0.01); self.assertAlmostEqual(inh['MAP2K1'], 0.5)                  # C = IC50 → half inhibited
        self.assertLess(inh['ABCB1'], 0.01)
        p = P._norm_perturbations([{'kind': 'compound', 'drug': 'T', 'conc': 0.1}])[0]
        self.assertEqual(p['conc'], 0.1); p['engagement'] = {'MAP2K1': 0.9, 'MAP2K2': 0.8}
        self.assertEqual(P.targets(p, DRUGS)[0], ('MAP2K1', 0.9))                                   # engagement replaces the annotation
        with self.assertRaises(ValueError):
            P._norm_perturbations([{'kind': 'compound', 'drug': 'T', 'conc': 5000}])

    def test_event_and_delay_models(self):
        run = lambda mid, pert: P.ode_model(mid, P._norm_perturbations([pert]), DRUGS)
        nut = run('proctor', {'kind': 'interaction', 'pair': 'MDM2–TP53', 'factor': 0.1})        # nutlin-like: p53 accumulates
        self.assertGreater(nut['metrics'][0][2], 1.5 * nut['metrics'][0][1]); self.assertTrue(nut['reliable'])
        ikk = run('hoffmann', {'kind': 'gene', 'gene': 'IKBKB', 'strength': 0.9})                 # less IKK, less nuclear NF-κB
        self.assertLess(ikk['metrics'][0][2], ikk['metrics'][0][1]); self.assertTrue(ikk['reliable'])
        z = run('zatorsky', {'kind': 'gene', 'gene': 'MDM2', 'strength': 0.5})                     # delay model: less MDM2, more p53
        self.assertGreater(z['metrics'][0][2], z['metrics'][0][1]); self.assertTrue(z['reliable'])

    def test_same_site_compounds_compete(self):
        mk = lambda drug, c: {**P._norm_perturbations([{'kind': 'compound', 'drug': drug, 'conc': c}])[0], 'engagement': {'EGFR': c / (c + 0.01)}, 'ic50': {'EGFR': 0.01}}
        two = P.ode_model('egfr', [mk('E', 0.01), mk('T', 0.01)], DRUGS)            # two equipotent compounds at C on one site
        one = P.ode_model('egfr', [mk('E', 0.02)], DRUGS)                            # = one compound at 2C (occupancy 2/3)
        self.assertAlmostEqual(two['metrics'][0][2], one['metrics'][0][2], places=6)
        self.assertGreater(two['interaction']['ratio'], 1.0)                           # same-site pairs fall short of Bliss independence

    def test_pd1_blockade_restores_costimulation(self):
        e = P.ode_model('theinmozhi', P._norm_perturbations([{'kind': 'interaction', 'pair': 'PD1–SHP2', 'factor': 0.1}]), DRUGS)
        self.assertTrue(e['reliable']); self.assertGreater(e['metrics'][0][2], 2 * e['metrics'][0][1])    # CD28–PI3K rises when PD-1 cannot recruit SHP2


if __name__ == '__main__':
    unittest.main()
