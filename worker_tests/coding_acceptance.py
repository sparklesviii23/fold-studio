"""Acceptance checks for the deliberately broken coding fixture, not normal CI."""
import importlib.util
import pathlib
import unittest
path=pathlib.Path(__file__).parent/'fixtures/coding_task.py'
spec=importlib.util.spec_from_file_location('owned_coding_fixture',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Addition(unittest.TestCase):
    def test_positive(self):self.assertEqual(module.add(2,3),5)
    def test_negative(self):self.assertEqual(module.add(-2,3),1)
    def test_zero(self):self.assertEqual(module.add(0,0),0)
if __name__=='__main__':unittest.main()
