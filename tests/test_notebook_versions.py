"""Notebook version persistence and project isolation; isolated SQLite fixtures only."""
import json,pathlib,sys,tempfile,unittest
sys.path[:0]=[str(pathlib.Path(__file__).resolve().parents[1]/'scientific')]
from worker import Service
import editcraft

class NotebookVersionTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.s=Service(self.temp.name);self.project=self.s.project_create({'name':'Isolated notebook reference'})['id']
 def tearDown(self):self.s.db.close();self.temp.cleanup()
 def save(self,**payload):return self.s.dispatch('editcraft_notebook',{'projectId':self.project,**payload})
 def test_versions_retain_original_citations_links_and_project_scope(self):
  a=self.save(name='Original notebook note',data={'markdown':'Original observation','citations':[{'text':'Original source'}],'experimentId':'observed-experiment'})
  b=self.save(id=a['id'],parentVersion=1,name='Revised notebook note',data={**a['data'],'markdown':'Corrected interpretation'})
  state=self.s.dispatch('editcraft_state',{'projectId':self.project});versions=state['versions']
  self.assertEqual([v['version'] for v in versions],[2,1]);self.assertEqual(versions[1]['data'],a['data']);self.assertEqual(versions[1]['sha256'],editcraft.digest(a['data']))
  self.assertEqual(b['data']['experimentId'],'observed-experiment');self.assertEqual(b['data']['citations'],a['data']['citations'])
  before=json.dumps(versions,sort_keys=True)
  with self.assertRaisesRegex(ValueError,'newer'):self.save(id=a['id'],parentVersion=1,name='Stale draft',data={'markdown':'Must not save'})
  self.assertEqual(json.dumps(self.s.dispatch('editcraft_state',{'projectId':self.project})['versions'],sort_keys=True),before)
  other=self.s.project_create({'name':'Separate notebook project'})['id']
  self.assertEqual(self.s.dispatch('editcraft_state',{'projectId':other})['versions'],[])
  with self.assertRaisesRegex(ValueError,'absent'):self.s.dispatch('editcraft_notebook',{'projectId':other,'id':a['id'],'parentVersion':2,'name':'Wrong project','data':{'markdown':'Must not save'}})
 def test_library_failure_rolls_back_the_entity_and_project_timestamp(self):
  a=self.save(name='Persisted note',data={'markdown':'Version one'})
  before=self.s.project(self.project)['updated']
  self.s.db.execute("CREATE TRIGGER refuse_notebook_library BEFORE INSERT ON records WHEN NEW.name='Blocked note · v2' BEGIN SELECT RAISE(ABORT,'isolated forced library failure'); END")
  self.s.db.commit()
  with self.assertRaisesRegex(Exception,'forced library failure'):self.save(id=a['id'],parentVersion=1,name='Blocked note',data={'markdown':'Must roll back'})
  self.assertEqual(self.s.project(self.project)['updated'],before)
  self.assertEqual([row['version'] for row in self.s.rows('SELECT version FROM editcraft_entities WHERE id=?',(a['id'],))],[1])
  self.assertEqual(len(self.s.rows('SELECT * FROM records WHERE project_id=?',(self.project,))),1)
  self.assertFalse(self.s.db.in_transaction)

if __name__=='__main__':unittest.main()
