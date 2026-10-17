import importlib.util, json, pathlib, tempfile, unittest, zipfile
from unittest.mock import patch

REPO=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('fold_worker',REPO/'scientific/worker.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)

class ScientificTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.s=w.Service(pathlib.Path(self.temp.name)/'library');self.project=self.s.project_create({'name':'Test research'})
    def tearDown(self): self.s.db.close();self.temp.cleanup()
    def test_fasta_normalization_multiple_chains(self):
        result=w.parse_fasta('>Chain A\nacd efg\n>Chain B\nHIKL\n')
        self.assertEqual([r['sequence'] for r in result],['ACDEFG','HIKL'])
    def test_sequence_rejects_ambiguous_and_injection(self):
        for text in ['', 'ACDX', 'ACD;touch /tmp/owned','>ACDE']:
            with self.assertRaises(ValueError): w.validate_sequence(text)
    def test_validation_proteins_sequence_integrity(self):
        expected={'ANGPTL3':('Q9Y5C1',460),'ANGPTL8':('Q6UXH0',198),'APOA5':('Q6Q788',366),'LPL':('P06858',475)}
        for gene,(accession,length) in expected.items():
            entry=json.loads((REPO/'fixtures'/f'{gene}.json').read_text())['results'][0]
            self.assertEqual(entry['primaryAccession'],accession);self.assertEqual(len(w.validate_sequence(entry['sequence']['value'])),length);self.assertEqual(entry['organism']['taxonId'],9606)
    def test_project_sequence_and_variant_persistence(self):
        original=self.s.sequence_save({'projectId':self.project['id'],'name':'Reference','sequence':'ACDEFG','origin':{'accession':'test'}})
        variant=self.s.mutate({'projectId':self.project['id'],'name':'Variant','sequence':'ACDEFG','mutations':'A1V, F5Y'})
        self.assertEqual(variant['data']['sequence'],'VCDEYG');self.assertEqual(variant['data']['reference'],'ACDEFG')
        self.assertEqual(original['data']['sequence'],'ACDEFG');self.assertEqual(len(original['data']['sha256']),64)
        second=w.Service(self.s.root);self.assertEqual(len(second.library({})['records']),2);second.db.close()
    def test_mutation_reference_and_numbering_validation(self):
        for mutation in ['G1V','A0V','A8V','A1X','A1V, A1G']:
            with self.assertRaises(ValueError):self.s.mutate({'projectId':self.project['id'],'name':'Invalid','sequence':'ACDEFG','mutations':mutation})
    def test_real_structure_import_checksum_and_export(self):
        item=self.s.import_structure({'projectId':self.project['id'],'path':str(REPO/'fixtures/ANGPTL3.cif')})
        self.assertIn('_atom_site.',self.s.asset_read({'asset':item['data']['asset']}));self.assertEqual(item['data']['format'],'mmcif')
        archive=pathlib.Path(self.temp.name)/'research.zip';self.s.export_project({'id':self.project['id'],'path':str(archive)})
        with zipfile.ZipFile(archive) as z:self.assertIn('project.json',z.namelist());self.assertEqual(len(z.namelist()),2)
    def test_pdb_import_preserves_coordinates_and_saves_to_selected_project(self):
        data=b"ATOM      1  N   ALA A   1      11.104  13.207   9.100  1.00 20.00           N\nATOM      2  CA  ALA A   1      12.560  13.300   9.200  1.00 20.00           C\nEND\n"
        path=pathlib.Path(self.temp.name)/'protein.pdb';path.write_bytes(data)
        item=self.s.import_structure({'projectId':self.project['id'],'path':str(path)})
        self.assertEqual(item['project_id'],self.project['id']);self.assertEqual(item['data']['format'],'pdb')
        self.assertEqual((self.s.root/'assets'/item['data']['asset']).read_bytes(),data)
        self.assertEqual(path.read_bytes(),data);self.assertEqual(self.s.asset_read({'asset':item['data']['asset']}),data.decode())
    def test_asset_path_traversal_rejected(self):
        with self.assertRaises(ValueError):self.s.asset_read({'asset':'../../secrets'})
    def test_arbitrary_remote_urls_rejected(self):
        for url in ['http://rest.uniprot.org/test','https://example.com/test','file:///etc/passwd']:
            with self.assertRaises(ValueError):w.fetch(url)
    def test_cloud_input_and_state_are_not_running(self):
        job=self.s.cloud_prepare({'projectId':self.project['id'],'name':'Cloud','fasta':'>A\nACDE\n>B\nFGHI','model':'auto','msa':'single_sequence','templates':'none'})
        self.assertEqual(job['state'],'prepared');self.assertEqual(job['data']['query_sequence'],'ACDE:FGHI')
        opened=self.s.cloud_opened({'id':job['id']});self.assertEqual(opened['state'],'awaiting_import')
        self.assertFalse(self.s.active())
    def test_cloud_archive_traversal_rejected(self):
        job=self.s.cloud_prepare({'projectId':self.project['id'],'fasta':'>A\nACDE'})
        archive=pathlib.Path(self.temp.name)/'malicious.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape.pdb','ATOM  ')
        with self.assertRaises(ValueError):self.s.cloud_import({'id':job['id'],'path':str(archive)})
    def test_cloud_real_coordinates_import_preserves_metadata(self):
        job=self.s.cloud_prepare({'projectId':self.project['id'],'fasta':'>A\nACDE'})
        archive=pathlib.Path(self.temp.name)/'results.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.write(REPO/'fixtures/ANGPTL3.cif','actual_coordinates.cif');z.writestr('scores.json',json.dumps({'test_metadata':True}))
        result=self.s.cloud_import({'id':job['id'],'path':str(archive)})
        self.assertEqual(result['job']['state'],'results_imported');self.assertEqual(len(result['structures']),1)
        self.assertIn('Verify',result['job']['data']['sequenceCorrespondence'])
    def test_supported_actions_whitelisted(self):
        with self.assertRaises(ValueError):self.s.dispatch('__dict__',{})
    def test_offline_cache_and_network_error(self):
        url='https://rest.uniprot.org/uniprotkb/Q9Y5C1.json'
        self.s.db.execute('INSERT INTO cache VALUES(?,?,?)',(url,json.dumps({'primaryAccession':'Q9Y5C1'}),0));self.s.db.commit()
        with patch.object(w,'fetch',side_effect=w.urllib.error.URLError('offline')):
            result=self.s.cached_fetch(url);self.assertTrue(result['_offlineCache'])
            with self.assertRaises(w.urllib.error.URLError):self.s.cached_fetch(url+'missing')
    def test_installation_detection_without_engine(self):
        status=self.s.compute({});self.assertFalse(status['installed']);self.assertFalse(status['mpsAvailable']);self.assertGreater(status['diskFreeGB'],0)
    def test_job_cancel_of_inactive_job_does_not_change_state(self):
        job=self.s.cloud_prepare({'projectId':self.project['id'],'fasta':'ACDE'})
        self.assertEqual(self.s.job_cancel({'id':job['id']})['state'],'prepared')

if __name__=='__main__':unittest.main(verbosity=2)
