"""Constraint-based methods on the E. coli core textbook model (known answers); skipped without COBRApy runtime."""
import json, pathlib, subprocess, sys, types, unittest
HERE = pathlib.Path(__file__).resolve().parents[1] / 'scientific'
sys.path.insert(0, str(HERE))
import singlecell_data as SD

PY = SD.python(types.SimpleNamespace(setting=lambda k, d=None: d))
CODE = r'''
import json, sys, warnings; warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1]); import cobra, metabolism as M
m = cobra.io.load_model("textbook"); out = {"growth": m.slim_optimize()}
# set_medium closes every uptake then opens named components (by metabolite name); glucose cap applies
with m:
    used = M.set_medium(m, ["D-Glucose", "O2", "H2O", "Phosphate", "H+", "Ammonium"], glucose=1.0)
    out["closed"] = all(r.lower_bound == 0 for r in m.exchanges if r.id not in ("EX_glc__D_e", "EX_o2_e", "EX_h2o_e", "EX_pi_e", "EX_h_e", "EX_nh4_e"))
    out["caps"] = [m.reactions.EX_glc__D_e.lower_bound, m.reactions.EX_pi_e.lower_bound]   # glucose 1; names outside INORGANIC get the organic cap
    m.reactions.EX_glc__D_e.lower_bound = -10.0; m.reactions.EX_pi_e.lower_bound = -1000.0; m.reactions.EX_nh4_e.lower_bound = -1000.0
    out["minimal"] = m.slim_optimize(); out["used"] = used
with m:
    for r in m.exchanges: r.lower_bound = 0.0
    m.objective = "ATPM"; out["noNutrientATP"] = m.slim_optimize(error_value=0.0)
with m:
    m.reactions.EX_o2_e.lower_bound = 0.0; out["anaerobic"] = m.slim_optimize()
print(json.dumps(out))
'''


@unittest.skipUnless(PY, 'science runtime not installed')
class ConstraintModelTests(unittest.TestCase):
    def test_textbook_answers(self):
        r = json.loads(subprocess.run([str(PY), '-W', 'ignore', '-c', CODE, str(HERE)], capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1])
        self.assertAlmostEqual(r['growth'], 0.8739, places=3)          # Orth et al. 2010
        self.assertTrue(r['closed']); self.assertEqual(r['caps'], [-0.1, -0.1])   # names are Human-GEM's: E. coli 'D-Glucose' is not 'glucose', so it gets the organic cap
        self.assertAlmostEqual(r['minimal'], 0.8739, places=3)         # glucose/O2/NH4/Pi minimal medium reproduces the optimum
        self.assertEqual(r['noNutrientATP'], 0.0)                      # no energy-generating cycles
        self.assertAlmostEqual(r['anaerobic'], 0.2117, places=3)       # published anaerobic E. coli core growth


if __name__ == '__main__':
    unittest.main()
