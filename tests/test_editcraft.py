"""EditCraft contracts and metadata fixtures; no paid compute or local model install."""
import copy,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch,MagicMock
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'remote_worker')]
from worker import Service
import editcraft
from fold_rapid.editcraft_core import coordinate_map,experimental_compare,validate_plan,run_plan,FUNCTIONS
class CoordinateTests(unittest.TestCase):
 def transcript(self,strand=1):return {'id':'ENST-fixture','version':3,'assembly_name':'fixture-assembly','strand':strand,'Exon':[{'id':'e1','start':10,'end':12},{'id':'e2','start':20,'end':24}]}
 def map(self,position,strand=1,**extra):return coordinate_map({'transcript':self.transcript(strand),'position':position,'assembly':'fixture-assembly',**extra})
 def test_exon_edges_and_intron(self):
  self.assertEqual([self.map(i)['transcriptPosition'] for i in [10,12,20,24]],[1,3,4,8])
  self.assertIsNone(self.map(15)['transcriptPosition']);self.assertIsNone(self.map(10)['proteinResidue'])
 def test_reverse_strand_is_in_transcription_order(self):self.assertEqual([self.map(i,-1)['transcriptPosition'] for i in [24,20,12,10]],[1,5,6,8])
 def test_assembly_and_overlapping_exons_refused(self):
  with self.assertRaisesRegex(ValueError,'assembly'):self.map(12,assembly='other')
  t=self.transcript();t['Exon'][1]['start']=12
  with self.assertRaisesRegex(ValueError,'non-overlapping'):coordinate_map({'transcript':t,'position':12,'assembly':'fixture-assembly'})
 def test_comparisons_require_identical_measurement_context(self):
  context={k:'fixture' for k in ('organism','cellType','assay','editor','endpoint','units')}
  p={'context':context,'predictionContext':copy.deepcopy(context),'rows':[{'observed':1,'predicted':2},{'observed':3,'predicted':4},{'observed':5,'predicted':6}]}
  out=experimental_compare(p);self.assertEqual(out['mae'],1);self.assertEqual(out['pearsonR'],1)
  p['predictionContext']['units']='different'
  with self.assertRaisesRegex(ValueError,'must match'):experimental_compare(p)
class PlanTests(unittest.TestCase):
 def plan(self):return {'schemaVersion':1,'seconds':60,'stages':[{'id':'g','operation':'gene_context','parameters':{'symbol':'ANGPTL3'}}]}
 def test_dag_type_safety(self):
  p=self.plan();p['stages'] += [{'id':'s','operation':'sequence_analyze','inputFrom':'g','parameters':{}},{'id':'r','operation':'rna_fold','inputFrom':'s','parameters':{}}]
  self.assertEqual(validate_plan(p),p)
  p['stages'][-1]['inputFrom']='g'
  with self.assertRaisesRegex(ValueError,'conversion'):validate_plan(p)
 def test_unknown_engine_and_cycle_rejected(self):
  p=self.plan();p['stages'][0]['operation']='fake_editor_model'
  with self.assertRaisesRegex(ValueError,'not executable'):validate_plan(p)
  p=self.plan();p['stages'][0]['inputFrom']='g'
  with self.assertRaisesRegex(ValueError,'cycles'):validate_plan(p)
 def test_typed_conversion_requires_actual_retrieved_cds(self):
  p=self.plan();p['stages'].append({'id':'s','operation':'sequence_analyze','inputFrom':'g','parameters':{}})
  with patch.dict(FUNCTIONS,{'gene_context':lambda p:{'sequences':{}}}):
   with self.assertRaisesRegex(ValueError,'no retrieved CDS'):run_plan(p)
class NativeTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);self.s=Service(self.root);self.project=self.s.project_create({'name':'EditCraft synthetic fixture'})['id']
 def tearDown(self):self.s.db.close();self.tmp.cleanup()
 def call(self,action,**params):return self.s.dispatch(action,{'projectId':self.project,**params})
 def test_registry_versions_and_library_share_identity(self):
  a=self.call('editcraft_save',kind='sequence',name='Synthetic CDS',data={'sequence':'ATGGCC','kind':'DNA'})
  b=self.call('editcraft_save',kind='sequence',name='Synthetic alternate',id=a['id'],parentVersion=1,data={'sequence':'ATGGCT','kind':'DNA'})
  self.assertEqual(b['version'],2)
  with self.assertRaisesRegex(ValueError,'newer'):self.call('editcraft_save',kind='sequence',name='Stale',id=a['id'],parentVersion=1,data={})
  state=self.call('editcraft_state');self.assertEqual(len(state['versions']),2)
  library=self.s.rows('SELECT data FROM records WHERE project_id=?',(self.project,));self.assertEqual(len(library),2);self.assertEqual(json.loads(library[0]['data'])['entityId'],a['id'])
 def test_cross_project_entity_edit_is_refused(self):
  a=self.call('editcraft_save',kind='notebook',name='Private fixture note',data={'markdown':'fixture'})
  other=self.s.project_create({'name':'Other fixture'})['id']
  with self.assertRaisesRegex(ValueError,'absent'):self.s.dispatch('editcraft_save',{'projectId':other,'id':a['id'],'parentVersion':1,'kind':'notebook','name':'No access','data':{}})
 def test_prepare_is_local_no_transfer_no_provider_calls(self):
  p={'schemaVersion':1,'seconds':60,'stages':[{'id':'a','operation':'sequence_analyze','parameters':{'sequence':'ATGGCC','kind':'DNA'}}]}
  with patch('editcraft.provider',side_effect=AssertionError('No network during preparation')):
   r=self.call('editcraft_prepare',plan=p,allowanceUSD=.5)
  self.assertEqual(r['state'],'prepared');self.assertFalse(r['gpuStarted']);self.assertNotIn('remote',r)
 def test_import_is_bounded_file_preservation_only(self):
  p=self.root/'fixture.fasta';p.write_text('>synthetic\nATGGCC\n')
  r=self.call('editcraft_import_text',path=str(p));self.assertEqual(r['data']['text'],p.read_text());self.assertFalse(r['data']['analysisPerformed'])
 def test_all_domain_actions_are_allowed_by_the_native_host(self):
  host=(ROOT/'src-tauri/src/main.rs').read_text()
  for action in editcraft.ACTIONS:self.assertIn('"'+action+'"',host)

 def test_no_catalogue_name_is_substituted_for_an_engine(self):
  state=self.call('editcraft_state');names=[m['name'] for m in state['models']]
  self.assertIn('AlphaGenome',names);self.assertIn('PRIDICT2',names)
  for m in state['models']:
   self.assertFalse(m['scientificallyBenchmarked']);self.assertEqual(m['cloudExecutionValidated'],m['id'] in ('viennarna','ensembl'))
  self.assertNotIn('DeepPrime',[op['id'] for op in state['operations']])
