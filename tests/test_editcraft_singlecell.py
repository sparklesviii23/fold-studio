"""Bounded offline contracts; real Scanpy/H5AD science is qualified on Modal."""
import base64,copy,hashlib,json,os,pathlib,sys,tempfile,unittest
from unittest.mock import MagicMock,patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'remote_worker'),str(ROOT/'scientific')]
from fold_rapid import editcraft_singlecell as c
from fold_rapid.editcraft_core import resources,validate_plan
from worker import Service
import editcraft
def params():return {'datasetSha256':c.MANIFEST['datasets']['pbmc3k']['sha256'],'seed':42,'minGenes':200,'maxGenes':2500,'minCells':3,'maxMitoPct':5,'mitoPrefix':'MT-','nTopGenes':2000,'nPCs':30,'nNeighbors':10,'maxDisplayCells':3000,'resolution':.5,'minDist':.5,'displayGenes':['CD3D','MS4A1'],'metadataColumns':[]}
def plan():return {'schemaVersion':1,'seconds':300,'stages':[{'id':'cells','operation':'scanpy_analysis','parameters':params()}]}
class ContractTests(unittest.TestCase):
 def test_artifact_receipt_works_through_a_mounted_volume_symlink(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=pathlib.Path(temporary);volume=root/'volume';volume.mkdir();mount=root/'research';mount.symlink_to(volume,target_is_directory=True);key='a'*32;folder=mount/key;folder.mkdir();path=folder/'analysis.h5ad';raw=c.HDF_HEADER+b'owned-synthetic-artifact';path.write_bytes(raw)
   artifact={'path':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
   self.assertEqual(c.artifact_info(artifact,key,mount)['volumePath'],key+'/analysis.h5ad')
   with self.assertRaisesRegex(ValueError,'size'):c.artifact_info({**artifact,'bytes':len(raw)+1},key,mount)
   with self.assertRaisesRegex(ValueError,'checksum'):c.artifact_info({**artifact,'sha256':'0'*64},key,mount)
   external=root/'unrelated.h5ad';external.write_bytes(raw);path.unlink();path.symlink_to(external)
   with self.assertRaisesRegex(ValueError,'outside'):c.artifact_info(artifact,key,mount)
 def test_explicit_parameters_and_seed(self):
  self.assertEqual(c.validate_input(params()),params())
  for change in [{'seed':True},{'seed':-1},{'maxMitoPct':float('nan')},{'minGenes':0},{'maxGenes':200},{'datasetSha256':'../private'},{'nTopGenes':5000},{'displayGenes':[{}]},{'metadataColumns':[[]]}]:
   with self.subTest(change=change),self.assertRaises(ValueError):c.validate_input({**params(),**change})
 def test_raw_matrix_resource_bounds_are_checked_before_loading(self):
  c.validate_shape([2700,32738],nnz=2286884)
  for shape,kwargs in [([10001,100],{}),([1000,40001],{}),([10000,40000],{'dense':True}),([100,100],{'nnz':20000000}),([4,2000],{})]:
   with self.assertRaises(ValueError):c.validate_shape(shape,**kwargs)
 def test_actual_public_legacy_h5ad_metadata_is_supported_without_rewriting_source(self):
  fixture=json.loads((ROOT/'fixtures/editcraft/singlecell/pbmc3k-container-metadata.json').read_text());self.assertEqual(c.sparse_layout(fixture['xAttributes']),('csr',[2700,32738]));self.assertEqual(fixture['nonzeroElements'],2286884)
  self.assertEqual(c.sparse_layout({'encoding-type':'csr_matrix','shape':[2700,32738]}),('csr',[2700,32738]))
 def test_conflicting_or_guessed_sparse_layout_is_rejected(self):
  for attributes in [{'encoding-type':'csr_matrix','shape':[2700,32738],'h5sparse_format':'csc','h5sparse_shape':[2700,32738]},{'h5sparse_format':'csr','h5sparse_shape':[2700.5,32738]},{'shape':[2700,32738]},{'encoding-type':'csr_matrix','shape':[True,32738]}]:
   with self.assertRaises(ValueError):c.sparse_layout(attributes)
 def test_separate_actual_memory_profile(self):
  self.assertEqual(resources(validate_plan(plan())),{'cpu':2,'memoryGiB':8,'gpu':False})
  self.assertEqual(resources({'stages':[{'operation':'sequence_analyze'}]})['memoryGiB'],4)
 def test_unqualified_mixed_runtime_cannot_be_silently_routed(self):
  value=plan();value['stages'].append({'id':'activity','operation':'rs3_activity','parameters':{'nuclease':'SpCas9','tracrRNA':'Hsu2013','sequences':[{'id':'a','sequence':'GACGAAAGCGACAACGCGTTCATCCGGGCA'}]}})
  with self.assertRaisesRegex(ValueError,'isolated CPU'):validate_plan(value)
 def test_local_scientific_fallback_is_refused(self):
  with patch.dict(os.environ,{},clear=True),self.assertRaisesRegex(RuntimeError,'cloud-only'):c.execute(params())
 def test_data_copy_is_not_scientific_h5ad_qualification(self):
  raw=c.HDF_HEADER+b'synthetic-header-contract-only';sha=hashlib.sha256(raw).hexdigest()
  with tempfile.TemporaryDirectory() as temporary,patch.object(c,'DATA_ROOT',pathlib.Path(temporary)),patch.dict(os.environ,{'FOLD_ENGINE_ROLE':'editcraft_cloud'}):
   receipt=c.prepare_dataset({'kind':'upload','sha256':sha,'name':'synthetic.h5ad','base64':base64.b64encode(raw).decode()});file,actual=c.verify_dataset(sha)
   self.assertEqual(file.read_bytes(),raw);self.assertEqual(receipt,actual);self.assertFalse(receipt['analysisPerformed'])
   file.write_bytes(c.HDF_HEADER+b'changed')
   with self.assertRaisesRegex(ValueError,'changed'):c.verify_dataset(sha)
 def test_invalid_upload_header_checksum_and_path_are_refused(self):
  with tempfile.TemporaryDirectory() as temporary,patch.object(c,'DATA_ROOT',pathlib.Path(temporary)),patch.dict(os.environ,{'FOLD_ENGINE_ROLE':'editcraft_cloud'}):
   for raw,sha in [(b'not HDF5','a'*64),(c.HDF_HEADER+b'wrong-checksum','b'*64)]:
    with self.assertRaises(ValueError):c.prepare_dataset({'kind':'upload','sha256':sha,'name':'fixture.h5ad','base64':base64.b64encode(raw).decode()})
   with self.assertRaisesRegex(ValueError,'identity'):c.verify_dataset('../private')
 def test_display_sampling_preserves_scientific_counts_and_expression_correspondence(self):
  result={'cells':[{'barcode':'cell_'+str(i)} for i in range(200)],'expression':[{'name':'GENE','values':list(range(200))}],'clusters':[{'id':'0','cells':200}]}
  value=c.display_view(copy.deepcopy(result),100,42);self.assertEqual(len(value['cells']),100);self.assertFalse(value['display']['allRetainedCellsDisplayed']);self.assertEqual(value['clusters'],result['clusters'])
  for cell,expression in zip(value['cells'],value['expression'][0]['values']):self.assertEqual(int(cell['barcode'].split('_')[1]),expression)
  self.assertEqual(value,c.display_view(copy.deepcopy(result),100,42))
 def test_runtime_and_reference_are_independently_attributed(self):
  spec=c.MANIFEST['datasets']['pbmc3k'];self.assertEqual((spec['cells'],spec['genes']),(2700,32738));self.assertEqual(spec['license'],'CC-BY-4.0');self.assertIn('No perturbation labels',spec['scope']);self.assertEqual(c.MANIFEST['runtime']['scanpy'],'1.11.5')

class NativeTests(unittest.TestCase):
 def setUp(self):
  self.temporary=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temporary.name);self.service=Service(self.root);self.project=self.service.project_create({'name':'Single-cell offline fixture'})['id']
 def tearDown(self):self.service.db.close();self.temporary.cleanup()
 def call(self,action,**p):return self.service.dispatch(action,{'projectId':self.project,**p})
 def test_import_preserves_original_bytes_without_upload_or_h5ad_loading(self):
  file=self.root/'synthetic.h5ad';raw=c.HDF_HEADER+b'synthetic-container-header-only';file.write_bytes(raw)
  with patch('editcraft.provider',side_effect=AssertionError('Import must not transmit')):record=self.call('editcraft_dataset_import',path=str(file))
  self.assertFalse(record['data']['uploadPerformed']);self.assertFalse(record['data']['analysisPerformed']);self.assertEqual((self.root/'editcraft-datasets'/record['data']['asset']).read_bytes(),raw);self.assertEqual(file.read_bytes(),raw)
 def test_review_is_offline_and_cost_reflects_the_deployed_memory(self):
  with patch('editcraft.provider',side_effect=AssertionError('Review must not transmit')):job=self.call('editcraft_prepare',plan=plan(),allowanceUSD=.5)
  self.assertEqual(job['resources']['memoryGiB'],8);self.assertIn('8 GiB',job['pricingBasis']);self.assertAlmostEqual(job['estimatedUSD'],round(360*(2*.0000131+8*.00000222)+.10,4));self.assertEqual(job['state'],'prepared')
 def test_import_is_not_marked_as_cloud_execution(self):
  state=self.call('editcraft_state');method=next(m for m in state['models'] if m['id']=='scanpy');self.assertTrue(method['adapterImplemented']);self.assertFalse(method['cloudExecutionValidated']);self.assertFalse(method['scientificallyBenchmarked']);self.assertIn('pbmc3k',[d['id'] for d in state['cellDatasets']])
 def artifact_fixture(self,raw):
  identity='f'*32;sha=hashlib.sha256(raw).hexdigest();editcraft.table(self.service);editcraft.save_job(self.service,{'id':identity,'projectId':self.project,'state':'completed','accountId':None})
  modal=MagicMock();modal.Function.from_name.return_value.remote.return_value={'volumePath':identity+'/scanpy-fixture/analysis.h5ad','sha256':sha,'bytes':len(raw)};modal.Volume.from_name.return_value.read_file.return_value=[raw[:8],raw[8:]]
  return identity,sha,modal
 def test_original_artifact_stream_matches_checksum_before_destination_replace(self):
  raw=c.HDF_HEADER+b'synthetic-transfer-contract';identity,sha,modal=self.artifact_fixture(raw);destination=self.root/'processed.h5ad'
  with patch.dict(sys.modules,{'modal':modal}),patch.dict(os.environ,{'FOLD_EDITCRAFT_CHILD':'1'}):result=self.call('editcraft_artifact_export',id=identity,artifactSha256=sha,path=str(destination))
  self.assertEqual(destination.read_bytes(),raw);self.assertEqual(result['sha256'],sha);self.assertFalse(list(self.root.glob('*.partial-*')))
 def test_failed_transfer_preserves_existing_destination(self):
  raw=c.HDF_HEADER+b'synthetic-transfer-contract';identity,sha,modal=self.artifact_fixture(raw);destination=self.root/'processed.h5ad';destination.write_bytes(b'existing-user-file');modal.Volume.from_name.return_value.read_file.return_value=[b'corrupted']
  with patch.dict(sys.modules,{'modal':modal}),patch.dict(os.environ,{'FOLD_EDITCRAFT_CHILD':'1'}),self.assertRaisesRegex(ValueError,'checksum'):self.call('editcraft_artifact_export',id=identity,artifactSha256=sha,path=str(destination))
  self.assertEqual(destination.read_bytes(),b'existing-user-file');self.assertFalse(list(self.root.glob('*.partial-*')))
