import pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
class LibraryEditTests(unittest.TestCase):
 def test_edit_remove_restore_preserve_scientific_data(self):
  with tempfile.TemporaryDirectory() as root:
   s=Service(root);p=s.project_create({'name':'QA'});i=s.record_save({'projectId':p['id'],'kind':'structure','name':'Wrong name','data':{'sha256':'original','source':'Scientific source','metadata':{'jobId':'original-job'}}})
   r=s.dispatch('record_update',{'id':i['id'],'projectId':p['id'],'name':'Correct name','notes':'My details'})
   self.assertEqual(r['name'],'Correct name');self.assertEqual(r['data']['metadata'],i['data']['metadata']);self.assertEqual(r['data']['sha256'],'original')
   s.dispatch('record_remove',{'id':i['id'],'projectId':p['id']});self.assertEqual(s.library({})['records'],[]);self.assertEqual(s.library({})['removedRecords'][0]['name'],'Correct name')
   s.dispatch('record_restore',{'id':i['id'],'projectId':p['id']});self.assertEqual(s.library({})['records'][0]['data']['notes'],'My details')
   other=s.project_create({'name':'Other'})
   with self.assertRaises(ValueError):s.record_remove({'id':i['id'],'projectId':other['id']})
   with self.assertRaises(ValueError):s.record_update({'id':i['id'],'projectId':p['id'],'name':'   '})
   s.db.close()
