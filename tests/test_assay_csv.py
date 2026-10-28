import pathlib,sys,unittest,hashlib,base64
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from test_research_cinema import ResearchCinemaTests as Fixture
from assay_csv import read
class CSVTests(unittest.TestCase):
 setUp=Fixture.setUp
 tearDown=Fixture.tearDown
 call=Fixture.call
 def payload(self):return {'name':'Supplied numerical fixture','endpoint':'Test endpoint','concentrationUnit':'nM','responseUnit':'RU','csvText':'concentration,response,biologicalReplicate,technicalReplicate,sampleGroup\n1,2,"bio, one",tech1,control\n1,3,bio2,tech1,control\n'}
 def test_original_csv_and_independent_unit_labels_survive_save(self):
  p=self.payload();saved=self.call('research_assay_import',**p);source=saved['data']['sourceCSV'];self.assertEqual(base64.b64decode(source['originalBase64']),p['csvText'].encode());self.assertEqual(source['sha256'],hashlib.sha256(p['csvText'].encode()).hexdigest());self.assertEqual(saved['data']['rows'][0]['biologicalReplicate'],'bio, one');summary=self.call('research_assay_summary',assayId=saved['id']);self.assertEqual(summary['data']['groups'][0]['biologicalUnits'],2)
 def test_invalid_and_mixed_units_do_not_publish_partial_evidence(self):
  before=len(self.call('research_candidate')['evidence'])
  for text in ('concentration,response\n1,2\n',self.payload()['csvText'].replace('1,2,','1,NaN,'),'concentration,response,biologicalReplicate,technicalReplicate,sampleGroup,responseUnit\n1,2,b1,t1,g,percent\n'):
   with self.assertRaises(ValueError):self.call('research_assay_import',**{**self.payload(),'csvText':text})
  self.assertEqual(len(self.call('research_candidate')['evidence']),before)
del Fixture
