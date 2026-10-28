import pathlib,sys,unittest,csv,io,hashlib,json
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from test_genome_workspace import GenomeTests as Fixture
from genome_evidence import parse_evidence,FIELDS
class EvidenceTests(unittest.TestCase):
 setUp=Fixture.setUp
 tearDown=Fixture.tearDown
 import_=Fixture.import_
 def evidence(self,reference,**changes):
  row=dict(zip(FIELDS,['g1','experimental_essentiality','conditional',reference['metadata']['organism'],'Explicit fixture strain',reference['metadata']['assembly'],'Defined fixture condition','Synthetic arithmetic fixture, not biological evidence','Fixture citation','A supplied statement, with a comma and "quotes".']));row.update(changes);out=io.StringIO();writer=csv.DictWriter(out,fieldnames=FIELDS);writer.writeheader();writer.writerow(row);return out.getvalue().encode()
 def test_preserved_csv_and_project_scoped_gene_lookup(self):
  reference=self.import_();raw=self.evidence(reference);path=self.root/'evidence.csv';path.write_bytes(raw)
  saved=self.s.dispatch('genome_evidence_import',{'projectId':self.project,'id':reference['id'],'path':str(path)})
  self.assertEqual(saved['data']['sourceFileSha256'],hashlib.sha256(raw).hexdigest())
  result=self.s.dispatch('genome_evidence',{'projectId':self.project,'id':reference['id'],'geneId':'g1'});self.assertEqual(len(result['rows']),1);self.assertEqual(result['rows'][0]['classification'],'conditional');self.assertIn('not independently verified',result['rows'][0]['scope'])
  other=self.s.project_create({'name':'Other'})['id']
  with self.assertRaises(ValueError):self.s.dispatch('genome_evidence',{'projectId':other,'id':reference['id'],'geneId':'g1'})
 def test_invalid_context_and_inferred_essentiality_are_rejected_without_save(self):
  reference=self.import_();before=len(self.s.library({})['records']);path=self.root/'evidence.csv'
  for changes in ({'organism':'Different organism'},{'assembly':'Unknown assembly'},{'geneId':'alias_not_supplied'},{'evidenceType':'hypothesis','classification':'essential'},{'condition':''}):
   path.write_bytes(self.evidence(reference,**changes))
   with self.subTest(changes=changes),self.assertRaises(ValueError):self.s.dispatch('genome_evidence_import',{'projectId':self.project,'id':reference['id'],'path':str(path)})
  self.assertEqual(len(self.s.library({})['records']),before)
 def test_missing_evidence_is_empty_not_an_essentiality_prediction(self):
  reference=self.import_();result=self.s.dispatch('genome_evidence',{'projectId':self.project,'id':reference['id'],'geneId':'g1'});self.assertEqual(result['rows'],[]);self.assertIn('No source means no essentiality claim',result['scope'])
del Fixture
