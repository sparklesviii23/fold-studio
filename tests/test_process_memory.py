"""Prevent compressed memory from bypassing a scientific benchmark's governor."""
import os,pathlib,subprocess,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from process_memory import process_memory,exceeds_footprint_budget

class ProcessMemory(unittest.TestCase):
 def test_compressed_footprint_triggers_even_when_resident_memory_is_low(self):
  self.assertTrue(exceeds_footprint_budget({'residentBytes':6*1024**3,'physicalFootprintBytes':48*1024**3},14*1024**3))
  self.assertFalse(exceeds_footprint_budget({'residentBytes':2*1024**3,'physicalFootprintBytes':3*1024**3},14*1024**3))
 @unittest.skipUnless(sys.platform=='darwin','macOS libproc acceptance')
 def test_real_child_allocation_and_process_identity_are_measured(self):
  code='import sys; data=bytearray(64*1024**2); data[::4096]=b"x"*len(data[::4096]); print("ready",flush=True);sys.stdin.read(1)'
  with subprocess.Popen([sys.executable,'-I','-B','-c',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True) as child:
   try:
    self.assertEqual(child.stdout.readline().strip(),'ready');first=process_memory(child.pid);second=process_memory(child.pid)
    self.assertGreater(first['physicalFootprintBytes'],48*1024**2);self.assertGreater(first['residentBytes'],48*1024**2);self.assertEqual(first['processStartAbstime'],second['processStartAbstime']);self.assertTrue(exceeds_footprint_budget(first,32*1024**2))
   finally:child.communicate(input='x',timeout=10)
