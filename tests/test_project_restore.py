import pathlib,sys,tempfile,unittest,hashlib,json
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
from project_archive import inspect_archive
import project_restore
class RestoreTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.source=Service(self.root/'source');self.target=Service(self.root/'target');self.project=self.source.project_create({'name':'Isolated archive source'})['id'];self.file=self.root/'input.pdb';self.file.write_text('ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\nEND\n');self.record=self.source.import_structure({'projectId':self.project,'path':str(self.file)});self.sequence=self.source.sequence_save({'projectId':self.project,'name':'Sequence reference','sequence':'ACDE','origin':{'recordId':self.record['id']}});self.archive=self.root/'source.zip';self.source.export_project({'id':self.project,'path':str(self.archive)});self.sha=inspect_archive({'path':str(self.archive)})['archiveSha256']
 def tearDown(self):self.source.db.close();self.target.db.close();self.tmp.cleanup()
 def payload(self):return {'path':str(self.archive),'expectedSha256':self.sha}
 def test_library_copy_relations_duplicate_and_original_archive_roundtrip(self):
  result=self.target.dispatch('project_archive_import',self.payload());self.assertNotEqual(result['projectId'],self.project)
  records=self.target.library({})['records'];structure=next(r for r in records if r['kind']=='structure');sequence=next(r for r in records if r['kind']=='sequence')
  self.assertEqual(sequence['data']['origin']['recordId'],structure['id']);self.assertEqual(sequence['data']['sequence'],'ACDE');self.assertNotEqual(structure['data']['asset'],self.record['data']['asset']);self.assertEqual(hashlib.sha256((self.target.root/'assets'/structure['data']['asset']).read_bytes()).hexdigest(),self.record['data']['sha256']);self.assertEqual(self.target.library({})['jobs'],[])
  duplicate=self.target.dispatch('project_archive_import',self.payload());self.assertEqual(duplicate['state'],'already_imported');self.assertEqual(len(self.target.library({})['records']),2)
  output=self.root/'exact.zip';self.target.dispatch('project_archive_original_export',{'projectId':result['projectId'],'id':result['snapshotId'],'path':str(output)});self.assertEqual(output.read_bytes(),self.archive.read_bytes())
  portable=self.root/'portable.zip';self.target.export_project({'id':result['projectId'],'path':str(portable)});self.assertEqual(inspect_archive({'path':str(portable)})['verifiedSnapshotCount'],1)
 def test_changed_source_and_publication_failure_leave_no_partial_records(self):
  with self.assertRaises(ValueError):self.target.dispatch('project_archive_import',{**self.payload(),'expectedSha256':'a'*64})
  real=project_restore.os.link;calls=[]
  def fail_second(a,b):
   calls.append(b)
   if len(calls)==2:raise OSError('Injected file publication failure')
   return real(a,b)
  with patch('project_restore.os.link',side_effect=fail_second),self.assertRaises(OSError):self.target.dispatch('project_archive_import',self.payload())
  self.assertEqual(self.target.library({})['projects'],[]);self.assertEqual(self.target.library({})['records'],[]);self.assertEqual(list((self.target.root/'assets').iterdir()),[]);self.assertEqual(project_restore.rows(self.target),[])
