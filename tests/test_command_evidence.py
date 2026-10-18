"""Prevent registered capability counts from masquerading as complete parity."""
import hashlib,json,pathlib,unittest
BASE=pathlib.Path(__file__).resolve().parents[1]
class ScopedCommandEvidence(unittest.TestCase):
 def test_every_evidence_command_matches_a_registered_name(self):
  base=json.loads((BASE/'scientific/pinned-capabilities-1.12.json').read_text());names={r['name'] for r in base['capabilities'] if r['kind']=='command'};evidence=json.loads((BASE/'scientific/validation-evidence-current.json').read_text())
  self.assertFalse(evidence['completeParityVerified']);self.assertEqual(len(evidence['capabilities']),10)
  for row in evidence['capabilities']:self.assertIn(row['name'],names);self.assertEqual(row['status'],'Partial');self.assertTrue(row['validationScope']);self.assertIn('Other arguments',row['limitations'])
 def test_evidence_links_exact_passing_live_report(self):
  raw=(BASE/'reports/chimerax-current-acceptance.json').read_bytes();report=json.loads(raw);evidence=json.loads((BASE/'scientific/validation-evidence-current.json').read_text());self.assertTrue(report['passed']);self.assertTrue(all(c['passed'] for c in report['checks']));self.assertEqual(hashlib.sha256(raw).hexdigest(),evidence['reportSha256']);names={c['name'] for c in report['checks']}
  for row in evidence['capabilities']:self.assertIn(row['evidenceCheck'],names)
 def test_numerical_scope_is_limited_to_measured_distance_and_alignment(self):
  evidence=json.loads((BASE/'scientific/validation-evidence-current.json').read_text());self.assertEqual({r['name'] for r in evidence['capabilities'] if r['scientificOutputValidated']},{'distance','matchmaker'})
