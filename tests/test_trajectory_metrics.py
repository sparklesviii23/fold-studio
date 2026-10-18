"""Analytic geometry checks on the actual numerical motion implementation."""
import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).parents[1]/'scientific'))
from trajectory_metrics import coordinate_metrics

class TrajectoryMetrics(unittest.TestCase):
 def test_raw_translation_has_analytic_rmsd_and_population_rmsf(self):
  result=coordinate_metrics([[[0,0,0],[1,0,0],[0,1,0]],[[3,0,0],[4,0,0],[3,1,0]]],False)
  self.assertEqual(result['rmsdAngstrom'],[0,3]);self.assertEqual(result['rmsfAngstrom'],[1.5]*3)
 def test_rigid_rotation_and_translation_have_zero_fitted_motion(self):
  result=coordinate_metrics([[[0,0,0],[2,0,0],[0,1,0]],[[7,-3,2],[7,-1,2],[6,-3,2]]])
  self.assertLess(max(result['rmsdAngstrom']),1e-12);self.assertLess(max(result['rmsfAngstrom']),1e-12);self.assertTrue(all(abs(v-1)<1e-12 for v in result['rotationDeterminants']))
 def test_reflection_is_not_hidden_by_an_improper_rotation(self):
  first=[[0,0,0],[1,0,0],[0,1,0],[0,0,1]];second=[[-x,y,z] for x,y,z in first];result=coordinate_metrics([first,second]);self.assertGreater(result['rmsdAngstrom'][1],.4);self.assertAlmostEqual(result['rotationDeterminants'][1],1)
 def test_invalid_or_degenerate_inputs_are_refused(self):
  for frames in ([[[0,0,0]]],[[[0,0,0]],[[float('nan'),0,0]]],[[[0,0,0],[1,0,0],[2,0,0]],[[0,0,0],[1,0,0],[2,0,0]]]):
   with self.subTest(frames=frames),self.assertRaises(ValueError):coordinate_metrics(frames)
 def test_small_raw_motion_does_not_require_a_rigid_fit(self):
  result=coordinate_metrics([[[0,0,0]],[[0,2,0]]],False);self.assertEqual(result['rmsdAngstrom'],[0,2]);self.assertEqual(result['rmsfAngstrom'],[1])
