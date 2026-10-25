"""Model contract and provenance tests. Mocks are never scientific execution evidence."""
import copy,hashlib,json,os,pathlib,sys,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'remote_worker'))
from fold_rapid import editcraft_models as m
from fold_rapid.editcraft_core import validate_plan

class ModelContracts(unittest.TestCase):
 def rs3(self):return {'nuclease':'SpCas9','tracrRNA':'Hsu2013','sequences':[{'id':'official_1','sequence':'GACGAAAGCGACAACGCGTTCATCCGGGCA'}]}
 def test_reference_context_and_pam(self):
  self.assertEqual(m.validate_input('rs3_activity',self.rs3())['sequences'][0]['sequence'][24:27],'CGG')
  p=self.rs3();p['sequences'][0]['sequence']='A'*30
  with self.assertRaisesRegex(ValueError,'PAM'):m.validate_input('rs3_activity',p)
 def test_upstream_prime_readme_example_is_not_padded_or_rewritten(self):
  import re
  text=(ROOT/'reports/editcraft/discovery/uzh-dqbm-cmi-PRIDICT2--README.md').read_text()
  sequence=re.search(r'--sequence "([ACGT]+\([ACGT]/[ACGT]\)[ACGT]+)"',text).group(1)
  self.assertEqual(len(sequence.split('(')[0]),99)
  self.assertEqual(m.validate_input('pridict2_design',{'editSequence':sequence,'cellContext':'HEK','folds':5})['editSequence'],sequence)
 def test_no_model_or_tracr_substitution(self):
  for key,value in [('nuclease','Cas12a'),('tracrRNA','unknown')]:
   p=self.rs3();p[key]=value
   with self.assertRaisesRegex(ValueError,'supports'):m.validate_input('rs3_activity',p)
 def test_duplicate_identifiers_and_ambiguity_rejected(self):
  p=self.rs3();p['sequences']*=2
  with self.assertRaisesRegex(ValueError,'unique'):m.validate_input('rs3_activity',p)
  p=self.rs3();p['sequences'][0]['sequence']='N'+p['sequences'][0]['sequence'][1:]
  with self.assertRaisesRegex(ValueError,'unambiguous'):m.validate_input('rs3_activity',p)
 def test_bedict_requires_exact_editor_and_target_bases(self):
  p={'editor':'ABEmax','sequences':[{'id':'fixture','sequence':'C'*20}]}
  with self.assertRaisesRegex(ValueError,'supported'):m.validate_input('bedict_per_base',p)
  p['sequences'][0]['sequence']='A'*20;p['editor']='ABE8e'
  with self.assertRaises(ValueError):m.validate_input('bedict_per_base',p)
 def test_prime_edits_context_and_full_ensemble(self):
  p={'editSequence':'A'*100+'(A/G)'+'C'*100,'cellContext':'HEK','folds':5}
  self.assertEqual(m.validate_input('pridict2_design',p),p)
  for changed in ({'folds':1},{'cellContext':'primary_T_cells'},{'editSequence':'A'*98+'(A/G)'+'C'*100},{'editSequence':'A'*100+'(A/A)'+'C'*100}):
   with self.assertRaises(ValueError):m.validate_input('pridict2_design',{**p,**changed})
 def test_preflight_rejects_model_inputs_before_any_upload(self):
  p={'schemaVersion':1,'seconds':60,'stages':[{'id':'activity','operation':'rs3_activity','parameters':self.rs3()}]}
  self.assertEqual(validate_plan(p),p);p['stages'][0]['parameters']['tracrRNA']='unknown'
  with self.assertRaises(ValueError):validate_plan(p)
 def test_real_upstream_score_is_not_relabelled_as_percentage(self):
  import types
  seq=types.ModuleType('rs3.seq');seq.predict_seq=lambda contexts,**kwargs:[-.90030944]
  with patch.dict(sys.modules,{'rs3':types.ModuleType('rs3'),'rs3.seq':seq}):
   result=m.infer_rs3(self.rs3(),pathlib.Path('/nonexistent-contract-fixture'))
  self.assertEqual(result['rows'][0]['predictedActivity'],-.90030944);self.assertIn('not a probability',result['units'])
 def test_missing_cloud_role_prevents_local_inference(self):
  with patch.dict(os.environ,{'FOLD_ENGINE_ROLE':'native'}):
   with self.assertRaisesRegex(RuntimeError,'Modal'):m.run_external('rs3_activity',self.rs3())
 def test_content_addressed_manifest_and_receipt_tamper_detection(self):
  raw=b'fixture only';asset={'path':'source.py','bytes':len(raw),'gitBlobSha1':m.blob_sha(raw)}
  manifest={'schemaVersion':1,'models':{'rs3':{'repository':'fixture/fixture','revision':'a'*40,'license':'fixture','assets':[asset]}}}
  with tempfile.TemporaryDirectory() as tmp,patch.object(m,'MANIFEST',manifest):
   root=pathlib.Path(tmp);folder=root/'rs3';(folder/'source').mkdir(parents=True);(folder/'source/source.py').write_bytes(raw)
   receipt={'manifestSha256':m.manifest_sha(),'files':{'source.py':hashlib.sha256(raw).hexdigest()}};(folder/'receipt.json').write_text(json.dumps(receipt))
   self.assertFalse(m.verify_model('rs3',root)['scientificBenchmarkComplete'])
   (folder/'source/source.py').write_bytes(b'tampered')
   with self.assertRaisesRegex(ValueError,'checksum'):m.verify_model('rs3',root)
 def test_manifest_preserves_all_original_runs(self):
  assets=m.MANIFEST['models']['bedict']['assets']
  for editor in ['ABEmax','BE4max']:
   self.assertEqual(len([a for a in assets if '/'+editor+'/' in a['path']]),5)
  assets=m.MANIFEST['models']['pridict2']['assets']
  for group in ['pridict1_1/exp_2023-08-25_20-55-53','pridict1_2/exp_2023-08-28_22-22-26']:
   for run in range(5):self.assertTrue(any(group+'/train_val/run_'+str(run)+'/' in a['path'] for a in assets))
  self.assertFalse(any('DeepCas9' in a['path'] for a in assets))
 def test_no_automatic_model_download_on_import(self):
  self.assertTrue(all(v.startswith('/opt/') for v in m.VENV.values()));self.assertLess(sum(s['totalBytes'] for s in m.MANIFEST['models'].values()),80*1024**2)

if __name__=='__main__':unittest.main()
