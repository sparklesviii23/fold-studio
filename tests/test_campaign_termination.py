"""Preserve cancellation, interrupted attempt budgets and genuine runtime failures."""
import os,pathlib,signal,types,unittest
from unittest.mock import patch
from test_project_metal import ProjectMetalTests as Fixtures
import bindcraft_cpu

class CampaignTermination(unittest.TestCase):
 setUp=Fixtures.setUp
 tearDown=Fixtures.tearDown
 prepared=Fixtures.prepared
 def queued(self):
  job=self.prepared();folder=self.s.root/'jobs'/job['id'];(folder/'execution-settings.json').write_text('{}');(folder/'saved-output.txt').write_text('preserved partial scientific output');self.s.job_update(job['id'],'queued',{'runtime':os.sys.executable,'parameters':'unused_test_parameters'});return job,folder
 def test_termination_signals_are_interrupted_without_promoting_or_erasing_outputs(self):
  for number in (signal.SIGINT,signal.SIGTERM,signal.SIGKILL):
   job,folder=self.queued();before={p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()}
   with patch.object(bindcraft_cpu.subprocess,'run',return_value=types.SimpleNamespace(returncode=-number)):bindcraft_cpu.run(self.s,job['id'])
   saved=self.s.job(job['id']);self.assertEqual(saved['state'],'interrupted');self.assertEqual(saved['data']['termination']['signal'],number.name);self.assertEqual(saved['data']['termination']['cause'],'not_reported');self.assertFalse(saved['data'].get('outputs'));self.assertNotIn('outcome',saved['data']);self.assertEqual(before,{p.name:p.read_bytes() for p in folder.iterdir() if p.is_file()})
 def test_explicit_cancellation_remains_cancelled(self):
  job,_=self.queued()
  def stop(*args,**kwargs):self.s.job_update(job['id'],'cancelled');return types.SimpleNamespace(returncode=-signal.SIGTERM)
  with patch.object(bindcraft_cpu.subprocess,'run',side_effect=stop):bindcraft_cpu.run(self.s,job['id'])
  self.assertEqual(self.s.job(job['id'])['state'],'cancelled')
 def test_application_error_remains_failed(self):
  job,_=self.queued()
  with patch.object(bindcraft_cpu.subprocess,'run',return_value=types.SimpleNamespace(returncode=1)):bindcraft_cpu.run(self.s,job['id'])
  self.assertEqual(self.s.job(job['id'])['state'],'failed');self.assertNotIn('termination',self.s.job(job['id'])['data'])
del Fixtures
