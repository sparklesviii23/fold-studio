"""The acceptance manifest cannot quietly lose clauses or reuse changed evidence."""
import contextlib,hashlib,importlib.util,io,json,pathlib,tempfile,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('closure',ROOT/'scripts/update-editcraft-closure.py');closure=importlib.util.module_from_spec(spec);spec.loader.exec_module(closure)
class RequirementClosureTests(unittest.TestCase):
 def fixture(self,directory,accepted=False):
  root=pathlib.Path(directory);(root/'docs').mkdir();(root/'reports/editcraft').mkdir(parents=True);(root/'evidence.json').write_text('{"scope":"synthetic contract evidence only"}');(root/'source.py').write_text('# synthetic contract source\n')
  clauses=[{'id':f'EC-01-C{i:03d}','acceptanceCriterion':f'Synthetic acceptance clause {i}'} for i in range(1349)]
  if accepted:clauses[0].update(status='fully_accepted',assessmentState='reviewed',sourceFiles=['source.py'],executionEvidence=[{'path':'evidence.json'}])
  audit={'sources':[],'features':[{'id':'EC-01','sourceDocument':'EC','requirements':clauses}]};path=root/'docs/EDITCRAFT_FULL_COMPLETION_AUDIT.json';path.write_text(json.dumps(audit))
  original=[(c['id'],c['acceptanceCriterion']) for c in clauses];sha=hashlib.sha256(json.dumps(original,ensure_ascii=False,separators=(',',':')).encode()).hexdigest();return root,path,sha
 def run_update(self,root,path,sha):
  with patch.multiple(closure,ROOT=root,PATH=path,SOURCES={},ORIGINAL_CLAUSE_SHA256=sha),contextlib.redirect_stdout(io.StringIO()):closure.update()
  return json.loads(path.read_text())
 def test_original_clause_identity_and_text_are_anchored(self):
  with tempfile.TemporaryDirectory() as tmp:
   root,path,sha=self.fixture(tmp);data=self.run_update(root,path,sha);self.assertEqual(data['closure']['totalAcceptanceParagraphs'],1349);self.assertEqual(data['closure']['fullyAcceptedParagraphs'],0)
   data['features'][0]['requirements'][0]['acceptanceCriterion']='Changed scope';path.write_text(json.dumps(data))
   with self.assertRaisesRegex(ValueError,'Original acceptance text'):self.run_update(root,path,sha)
 def test_changed_evidence_and_source_require_explicit_revalidation(self):
  with tempfile.TemporaryDirectory() as tmp:
   root,path,sha=self.fixture(tmp,True);data=self.run_update(root,path,sha);self.assertEqual(data['closure']['fullyAcceptedParagraphs'],1);self.assertFalse(data['complete'])
   (root/'evidence.json').write_text('changed')
   with self.assertRaisesRegex(ValueError,'evidence changed'):self.run_update(root,path,sha)
  with tempfile.TemporaryDirectory() as tmp:
   root,path,sha=self.fixture(tmp,True);self.run_update(root,path,sha);(root/'source.py').write_text('changed')
   with self.assertRaisesRegex(ValueError,'Accepted source changed'):self.run_update(root,path,sha)
 def test_full_acceptance_without_applicable_evidence_is_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   root,path,sha=self.fixture(tmp,True);data=json.loads(path.read_text());data['features'][0]['requirements'][0]['executionEvidence']=[];path.write_text(json.dumps(data))
   with self.assertRaisesRegex(ValueError,'Full acceptance needs'):self.run_update(root,path,sha)
