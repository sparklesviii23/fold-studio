"""Engine integration/contract tests; fixtures are synthetic, not binder predictions."""
import importlib.util, json, pathlib, tempfile, unittest, zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('metal_worker',ROOT/'scientific/worker.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)

def pdb():
    return ''.join(f'ATOM  {i:5d} {name:>4s} ALA A   1    {x:8.3f}{0.:8.3f}{0.:8.3f}{1.:6.2f}{75.:6.2f}          {element:>2s}\n' for i,(name,x,element) in enumerate([('N',0.,'N'),('CA',1.45,'C'),('C',2.9,'C'),('O',3.9,'O')],1))+'END\n'

class ProjectMetalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=pathlib.Path(self.tmp.name);self.s=w.Service(self.base/'library');self.project=self.s.project_create({'name':'Metal test'});self.file=self.base/'target.pdb';self.file.write_text(pdb());self.record=self.s.import_structure({'projectId':self.project['id'],'path':str(self.file)});self.engine=w.fold_engine.Engine(self.s)
        self.config={'projectId':self.project['id'],'structureId':self.record['id'],'name':'Experiment','targetChains':['A'],'hotspots':['["A",1,""]'],'binderLengths':[15,20],'candidates':2,'attempts':4,'seed':7,'modality':'peptide'}
    def tearDown(self):self.s.db.close();self.tmp.cleanup()
    def prepared(self):return self.s.dispatch('bindcraft_prepare',self.config)
    def result_folder(self):
        root=self.base/'upstream-output';ranked=root/'3_Ranked';ranked.mkdir(parents=True);(ranked/'candidate.cif').write_text('not a structure');(ranked/'candidate.cif').unlink();(ranked/'candidate.pdb').write_text(pdb());(ranked/'!_Ranked.csv').write_text('rank,design,Binder_Sequence,i_pTM\n1,candidate,ACDEFGHIKL,0.81\n');(root/'campaign_metadata.json').write_text(json.dumps({'version':'test-fixture','revision':'synthetic','settings':{'campaign_seed':7}}));return root
    def test_shared_reference_has_identical_coordinates_and_ids(self):
        shared=self.s.dispatch('fold_structure',self.config);existing=self.engine.lab.intelligence_inspect({'structureId':self.record['id']});self.assertEqual(shared['structure'],existing['structure']);self.assertEqual(shared['reference']['sha256'],self.record['data']['sha256'])
    def test_configuration_uses_real_upstream_preset_and_explicit_numbering(self):
        r=self.s.dispatch('bindcraft_validate',self.config);self.assertTrue(r['valid']);self.assertFalse(r['executionReady']);self.assertEqual(r['config']['targets'][0]['hotspots'],'A1');self.assertEqual(r['config']['campaign_seed'],7);self.assertEqual(r['config']['attention_backend'],'stock');self.assertFalse(r['config']['use_cueq'])
    def test_bad_fields_are_not_ignored(self):
        for key,value in [('gpu','cuda'),('binder_lengths',[10]),('optimization',{})]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.engine.bindcraft_validate({**self.config,key:value})
    def test_bad_integer_bounds_bool_and_nan(self):
        for key,value in [('seed',True),('seed',-1),('attempts',1),('candidates',float('nan')),('binderLengths',[20,15]),('binderLengths',[True]),('binderLengths',[])]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.engine.bindcraft_validate({**self.config,key:value})
    def test_missing_unknown_duplicate_chains_and_sites(self):
        for key,value in [('targetChains',[]),('targetChains',['B']),('targetChains',['A','A']),('hotspots',['["A",2,""]']),('hotspots',['["A",1,""]']*2),('coldspots',['["A",1,""]'])]:
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):self.engine.bindcraft_validate({**self.config,key:value})
    def test_unsupported_modality_does_not_fallback(self):
        with self.assertRaisesRegex(ValueError,'modalities remain blocked'):self.engine.bindcraft_validate({**self.config,'modality':'Fab'})
    def test_cross_project_structure_rejected(self):
        other=self.s.project_create({'name':'Other'})
        with self.assertRaisesRegex(ValueError,'another project'):self.engine.bindcraft_validate({**self.config,'projectId':other['id']})
    def test_incomplete_backbone_rejected(self):
        self.file.write_text(pdb().replace('   N ', '  XX '));r=self.s.import_structure({'projectId':self.project['id'],'path':str(self.file)})
        with self.assertRaisesRegex(ValueError,'backbone'):self.engine.bindcraft_validate({**self.config,'structureId':r['id']})
    def test_coordinate_tampering_rejected(self):
        (self.s.root/'assets'/self.record['data']['asset']).write_text(pdb().replace('1.450','1.451'))
        with self.assertRaisesRegex(ValueError,'checksum'):self.engine.bindcraft_validate(self.config)
    def test_prepare_persists_real_inputs_restarts_and_reuses_jobs(self):
        job=self.prepared();self.assertEqual(job['state'],'prepared');folder=self.s.root/'jobs'/job['id'];self.assertEqual((folder/'input.pdb').read_bytes(),self.file.read_bytes());self.assertEqual(json.loads((folder/'settings.json').read_text())['campaign_seed'],7);self.assertEqual(self.s.job(job['id'])['engine'],'bindcraft2');self.s.db.close();self.s=w.Service(self.base/'library');self.assertEqual(self.s.dispatch('bindcraft_campaigns',{'projectId':self.project['id']})[0]['id'],job['id'])
    def test_start_is_explicitly_blocked_without_spawning(self):
        j=self.prepared()
        with self.assertRaisesRegex(ValueError,'execution is blocked'):self.s.dispatch('bindcraft_start',{'projectId':self.project['id'],'id':j['id']})
        self.assertEqual(self.s.job(j['id'])['state'],'prepared');self.assertNotIn('pid',self.s.job(j['id'])['data'])
    def test_result_import_retains_raw_metrics_no_inferred_plddt_and_is_idempotent(self):
        j=self.prepared();root=self.result_folder();p={'projectId':self.project['id'],'id':j['id'],'directory':str(root)};a=self.s.dispatch('bindcraft_import',p);b=self.s.dispatch('bindcraft_import',p);self.assertEqual(a['records'],b['records']);self.assertEqual(b['state'],'already_imported');record=next(r for r in self.s.library({})['records'] if r['id']==a['records'][0]);self.assertEqual(record['data']['sha256'],self.record['data']['sha256']);self.assertEqual(record['data']['metadata']['rawMetrics']['i_pTM'],'0.81');self.assertIsNone(record['data']['confidenceKind']);self.assertEqual(a['provenanceMatch'],'external_unverified');self.assertEqual(self.engine.lab.intelligence_inspect({'structureId':record['id']})['confidence']['plddt'],None)
    def test_result_import_rejects_bad_structure_without_partial_records(self):
        j=self.prepared();root=self.result_folder();(root/'3_Ranked/candidate_bad.pdb').write_text('ATOM  broken');before=len(self.s.library({})['records'])
        with self.assertRaises(ValueError):self.s.dispatch('bindcraft_import',{'projectId':self.project['id'],'id':j['id'],'directory':str(root)})
        self.assertEqual(len(self.s.library({})['records']),before);self.assertEqual(self.s.job(j['id'])['state'],'prepared')
    def test_result_import_rejects_symlink_escape(self):
        j=self.prepared();root=self.result_folder();f=root/'3_Ranked/candidate.pdb';f.unlink();f.symlink_to(self.file)
        with self.assertRaisesRegex(ValueError,'selected campaign directory'):self.s.dispatch('bindcraft_import',{'projectId':self.project['id'],'id':j['id'],'directory':str(root)})
    def test_result_import_requires_metadata_and_ranked_identity(self):
        j=self.prepared();root=self.result_folder();(root/'3_Ranked/!_Ranked.csv').write_text('design\nother\n')
        with self.assertRaisesRegex(ValueError,'unambiguously'):self.s.dispatch('bindcraft_import',{'projectId':self.project['id'],'id':j['id'],'directory':str(root)})
    def test_export_includes_inputs_import_evidence_and_records(self):
        j=self.prepared();root=self.result_folder();self.s.dispatch('bindcraft_import',{'projectId':self.project['id'],'id':j['id'],'directory':str(root)});out=self.base/'project.zip';self.s.export_project({'id':self.project['id'],'path':str(out)})
        with zipfile.ZipFile(out) as z:
            self.assertIn('jobs/'+j['id']+'/input.pdb',z.namelist());self.assertTrue(any(x.endswith('campaign_metadata.json') for x in z.namelist()));self.assertEqual(json.loads(z.read('project.json'))['jobs'][0]['engine'],'bindcraft2')
    def test_registry_reports_full_modality_inventory_without_execution_claim(self):
        r=self.engine.fold_engine_status({});self.assertEqual(len(r['modalities']),12);self.assertEqual({x['name'] for x in r['modalities'] if x['execution']=='experimental'},{'binder','large_binder','multidomain','peptide','cyclic_peptide','VHH','ARP','scFv','homo_oligomer'});self.assertTrue(all(x['execution']=='blocked' for x in r['modalities'] if x['name'] not in ('binder','large_binder','multidomain','peptide','cyclic_peptide','VHH','ARP','scFv','homo_oligomer')));self.assertIn('VHH',{x['name'] for x in r['modalities']})
    def test_vendored_source_verified_and_license_retained(self):
        source=w.fold_engine.verify_source();self.assertEqual(source['revision'],w.fold_engine.PIN);self.assertIn('Hosting-Restricted',(w.fold_engine.UPSTREAM/'LICENSE').read_text())
    def test_probe_missing_runtime_is_unavailable(self):
        self.assertEqual(w.fold_engine.fold_compute.probe('/missing/python')['state'],'unavailable')
    def test_python_and_rust_ipc_allowlists_cover_all_new_actions(self):
        native=(ROOT/'src-tauri/src/main.rs').read_text()
        for action in w.fold_engine.ACTIONS:self.assertIn(action,w.ACTIONS);self.assertIn('"'+action+'"',native)
if __name__=='__main__':unittest.main()
