"""Degenerate measurement inputs must not produce apparently valid native angles."""
import pathlib,sys,types,unittest
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from scene_bridge import SceneBridge

class MeasurementContracts(unittest.TestCase):
 def bridge(self,points):
  bridge=SceneBridge.__new__(SceneBridge);bridge.identity='synthetic-session'
  bridge.atoms={str(i):types.SimpleNamespace(scene_coord=np.asarray(point),deleted=False,string=lambda **kw:'#fixture') for i,point in enumerate(points)}
  return bridge
 def test_duplicate_deleted_unknown_and_nonlist_atoms_are_refused(self):
  b=self.bridge([(0,0,0),(1,0,0)])
  for keys in (['0','0'],['0','missing'],['0',{}],None,'01'):
   with self.assertRaises(ValueError):b.measure({'keys':keys})
  b.atoms['1'].deleted=True
  with self.assertRaises(ValueError):b.measure({'keys':['0','1']})
 def test_zero_length_angle_and_collinear_torsion_are_undefined(self):
  for points in ([(0,0,0),(0,0,0),(1,0,0)],[(0,0,0),(1,0,0),(2,0,0),(2,1,0)],[(0,1,0),(0,0,0),(1,0,0),(2,0,0)]):
   b=self.bridge(points)
   with self.assertRaisesRegex(ValueError,'undefined'):b.measure({'keys':list(b.atoms)})
 def test_nonfinite_and_invalid_coordinate_shape_are_refused(self):
  for point in ((float('nan'),0,0),(float('inf'),0,0),(1,0)):
   with self.assertRaisesRegex(ValueError,'finite three-dimensional'):self.bridge([(0,0,0),point]).measure({'keys':['0','1']})
 def test_native_function_preserves_order_signed_value_and_scene_coordinates(self):
  points=[(1,0,0),(0,0,0),(0,1,0),(0,1,1)];b=self.bridge(points);calls=[]
  def dihedral(*args):calls.append(args);return -90.
  module=types.SimpleNamespace(distance=lambda *p:0.,angle=lambda *p:180.,dihedral=dihedral)
  with patch.dict(sys.modules,{'chimerax.geometry':module}):result=b.measure({'keys':['0','1','2','3']})
  self.assertEqual(result['value'],-90.);self.assertEqual(result['unit'],'degrees');self.assertEqual(result['sessionId'],b.identity)
  self.assertEqual([p.tolist() for p in calls[0]],[list(p) for p in points]);self.assertEqual([a['key'] for a in result['atoms']],['0','1','2','3'])
 def test_distinct_coincident_distance_and_straight_angle_remain_valid(self):
  module=types.SimpleNamespace(distance=lambda *p:0.,angle=lambda *p:180.,dihedral=lambda *p:0.)
  with patch.dict(sys.modules,{'chimerax.geometry':module}):
   self.assertEqual(self.bridge([(0,0,0),(0,0,0)]).measure({'keys':['0','1']})['value'],0.)
   self.assertEqual(self.bridge([(0,0,0),(1,0,0),(2,0,0)]).measure({'keys':['0','1','2']})['value'],180.)
 def test_native_nonfinite_result_is_never_saved_as_a_number(self):
  module=types.SimpleNamespace(distance=lambda *p:float('nan'),angle=None,dihedral=None)
  with patch.dict(sys.modules,{'chimerax.geometry':module}),self.assertRaisesRegex(ValueError,'non-finite'):self.bridge([(0,0,0),(1,0,0)]).measure({'keys':['0','1']})
