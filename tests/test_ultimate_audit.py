"""Inventory integrity: migration must not lose or silently accept old scope."""
import importlib.util,json,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ultimate_audit',ROOT/'scripts/update-ultimate-audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

class UltimateAuditTests(unittest.TestCase):
 def test_every_original_id_criterion_and_assessment_is_lossless(self):
  old=json.loads((ROOT/'docs/EDITCRAFT_FULL_COMPLETION_AUDIT.json').read_text())
  clauses={c['id']:c for f in old['features'] for c in f['requirements']}
  value=audit.inventory();actual={r['id']:r for r in value['requirements']}
  self.assertEqual(len(clauses),1933);self.assertEqual(len(actual),1933+value['newRequirementCount']);self.assertGreater(value['newRequirementCount'],1)
  for id,clause in clauses.items():
   self.assertEqual(actual[id]['acceptanceCriteria'],clause['acceptanceCriterion'])
   self.assertEqual(actual[id]['historicalAssessment'],clause)
  self.assertFalse(value['complete']);self.assertFalse(value['inventoryReconciliationComplete']);self.assertIsNone(value['completionPercentage'])
 def test_every_nonempty_ultimate_source_line_has_exactly_one_source_occurrence(self):
  value=audit.inventory();lines=(ROOT/'docs/specifications/FOLD_STUDIO_ULTIMATE.md').read_text().splitlines();seen=set()
  self.assertEqual([s['number'] for s in value['ultimateSections']],list(range(1,101)))
  for occurrence in value['ultimateSourceOccurrences']:
   start,end=occurrence['sourceLine'],occurrence['sourceEndLine']
   self.assertEqual(occurrence['text'],'\n'.join(lines[start-1:end]))
   for index in range(start,end+1):self.assertNotIn(index,seen);seen.add(index)
  self.assertEqual(seen,{i for i,line in enumerate(lines,1) if line.strip()})
  self.assertGreater(value['sourceReconciliation']['pendingSemanticMapping'],0)
