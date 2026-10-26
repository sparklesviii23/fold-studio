"""Deployment-admission protocol fixtures, never scientific qualification."""
import copy,json,pathlib,sys,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'remote_worker'),str(ROOT/'scientific'),str(ROOT/'tests')]
from test_biology_pipeline import Fixture
from fold_rapid.contracts import canonical,digest
import cloud_deployment as deployment

class DeploymentReceiptTests(Fixture):
 def health(self):
  source=ROOT/'remote_worker'
  checksum=digest(canonical({str(p.relative_to(source)):digest(p.read_bytes()) for p in sorted((source/'fold_rapid').glob('*.py'))}).encode())
  return {'controllerLocation':'remote','provider':'modal','deploymentReachable':True,'sourceCodeSha256':checksum,'fixture':True}
 def test_both_deployment_routes_can_bind_the_exact_reviewed_source_and_account(self):
  with patch('cloud_accounts.get',return_value={'activeId':'fixture-account'}):
   receipt=deployment.record_verified(self.s,{'appName':'fixture'},self.health(),'fixture-app','fixture-account')
  self.assertEqual(receipt['recordSource'],'health_checked_modal_deployment');self.assertFalse(receipt['gpuStarted'])
  self.assertTrue(deployment.require_current_engine(self.s,{'appName':'fixture'},'fixture-account'))
  with self.assertRaisesRegex(ValueError,'differs'):deployment.require_current_engine(self.s,{'appName':'fixture'},'different-account')
 def test_incorrect_remote_source_or_account_never_creates_a_launch_receipt(self):
  for field,value in [('sourceCodeSha256','0'*64),('provider','other')]:
   health=self.health();health[field]=value
   with patch('cloud_accounts.get',return_value={'activeId':'fixture-account'}):
    with self.assertRaises(ValueError):deployment.record_verified(self.s,{'appName':'fixture'},health,'fixture-app','fixture-account')
   self.assertFalse((self.s.root/'cloud-engine-deployment/status.json').exists())
  with patch('cloud_accounts.get',return_value={'activeId':'other'}):
   with self.assertRaisesRegex(ValueError,'account changed'):deployment.record_verified(self.s,{'appName':'fixture'},self.health(),'fixture-app','fixture-account')
 def test_in_progress_deployment_is_not_overwritten_by_receipt_reconciliation(self):
  path=self.s.root/'cloud-engine-deployment/status.json';path.parent.mkdir();prior={'state':'checking','pid':123};path.write_text(json.dumps(prior))
  with patch('cloud_accounts.get',return_value={'activeId':'fixture-account'}):
   with self.assertRaisesRegex(ValueError,'still being reconciled'):deployment.record_verified(self.s,{'appName':'fixture'},self.health(),'fixture-app','fixture-account')
  self.assertEqual(json.loads(path.read_text()),prior)
  self.assertFalse((path.parent/'source').exists())

del Fixture
