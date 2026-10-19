"""Coordinate scoring contracts with synthetic files and isolated source stubs."""
import pathlib,tempfile,types,unittest
from unittest.mock import Mock,patch
from test_project_metal import w
from test_unbound_predictions import cif
from campaign_scoring import score
class ScoringContracts(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.ranked=self.root/'3_Ranked';self.ranked.mkdir();self.path=self.ranked/'synthetic.cif';self.path.write_text(cif(True));self.original=Mock(return_value={'Binder_Sequence':'A','Geometry':12.5,'Hotspot_Contact_Fraction':0});self.modules={'bindcraft.score':types.SimpleNamespace(score_design=self.original),'bindcraft.filters':types.SimpleNamespace(REGISTERED_FILTER_METRICS={'Geometry':None,'Hotspot_Contact_Fraction':None,'Unavailable_Confidence':None}),'bindcraft.campaign_output':types.SimpleNamespace(design_model_scores=lambda path:{'model_1_ptm':{'i_pTM':0.9}})}
 def tearDown(self):self.tmp.cleanup()
 def run_score(self,rows=None):
  with patch.dict('sys.modules',self.modules):return score(self.root,[{'design':'synthetic'}] if rows is None else rows)
 def test_explicit_roles_are_passed_to_original_and_missing_site_evidence_is_not_zero(self):
  before=self.path.read_bytes();rows,details=self.run_score();self.original.assert_called_once_with(str(self.path),binder='A',target='B');self.assertEqual(rows[0]['Geometry'],12.5);self.assertNotIn('Hotspot_Contact_Fraction',rows[0]);self.assertNotIn('i_pTM',rows[0]);self.assertEqual(details[0]['recordedModelReadings']['model_1_ptm']['i_pTM'],0.9);self.assertIn('Unavailable_Confidence',details[0]['unavailableMetricNames']);self.assertEqual(self.path.read_bytes(),before)
 def test_missing_explicit_roles_or_unmatched_identity_refuses_scoring(self):
  with self.assertRaisesRegex(ValueError,'unique accepted'):self.run_score([{'design':'other'}])
  self.path.write_text(cif(True).replace('_bindcraft.binder_chains A\n','').replace('_bindcraft.target_chains B\n',''))
  with self.assertRaisesRegex(ValueError,'explicit original'):self.run_score()
  self.original.assert_not_called()
 def test_unbound_files_are_not_silently_presented_as_bound_interface_scores(self):
  self.path.unlink();(self.ranked/'synthetic_monomer.cif').write_text(cif())
  with self.assertRaisesRegex(ValueError,'accepted complex CIF'):self.run_score()
  self.original.assert_not_called()
 def test_more_than_four_complexes_is_refused_before_source_calculation(self):
  for i in range(4):(self.ranked/f'other{i}.cif').write_text(cif(True))
  with self.assertRaisesRegex(ValueError,'one to four'):self.run_score()
  self.original.assert_not_called()
 def test_bundle_carries_the_real_scoring_adapter(self):
  import json
  root=pathlib.Path(w.__file__).parents[1];self.assertIn('../scientific/campaign_scoring.py',json.loads((root/'src-tauri/tauri.conf.json').read_text())['bundle']['resources'])
