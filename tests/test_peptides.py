import copy,hashlib,json,pathlib,sqlite3,sys,tempfile,unittest,zipfile,math
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
from peptides import TEMPLATES,BY_ONE,construct,topology,distance,angle,state_validate
class PeptideTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=Service(self.tmp.name);self.p=self.s.project_create({'name':'Disposable research'})['id']
    def tearDown(self): self.s.db.close();self.tmp.cleanup()
    def save(self,**extra): return self.s.dispatch('peptide_save',{'projectId':self.p,'name':'Five residues','sequence':'AGSTL','workspace':'arcade',**extra})
    def test_twenty_authoritative_templates(self):
        self.assertEqual(set(BY_ONE),set('ACDEFGHIKLMNPQRSTVWY'))
        for c in TEMPLATES['components']:
            raw=pathlib.Path(__file__).resolve().parents[1]/'scientific/components'/(c['code']+'.cif')
            self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(),c['sha256'])
            self.assertIn('https://files.rcsb.org/',c['source']);self.assertGreater(c['mass'],70)
            atoms={a['id']:a for a in c['atoms']};self.assertTrue({'N','CA','C','O','OXT'}<=atoms.keys())
            for a in atoms.values(): self.assertTrue(all(math.isfinite(v) for v in a['xyz']))
            for b in c['bonds']: self.assertIn(b['a'],atoms);self.assertIn(b['b'],atoms)
            self.assertEqual(topology(c['one'])['status'],'validated_connectivity')
    def test_free_formula_counts_match_atoms(self):
        import re,collections
        for c in BY_ONE.values():
            actual=collections.Counter(a['element'] for a in c['atoms'])
            expected={e:int(n or 1) for e,n in re.findall(r'([A-Z][a-z]?)(\d*)',c['formula'])}
            self.assertEqual(dict(actual),expected,c['code'])
    def test_all_four_hundred_dipeptides(self):
        for a in BY_ONE:
            for b in BY_ONE:
                model=construct(a+b);check=topology(a+b);self.assertTrue(check['valid'],a+b);self.assertEqual(len(model['atoms']),len(BY_ONE[a]['atoms'])+len(BY_ONE[b]['atoms'])-3)
                link=[l for l in model['bonds'] if l['kind']=='peptide'];self.assertEqual(link,[{'a':'1:C','b':'2:N','order':1,'aromatic':False,'kind':'peptide'}])
    def test_terminal_chemistry_including_proline(self):
        atoms={a['id'] for a in construct('GPG')['atoms']}
        self.assertNotIn('1:OXT',atoms);self.assertNotIn('1:HXT',atoms);self.assertNotIn('2:H',atoms);self.assertNotIn('3:H2',atoms)
        self.assertIn('1:H2',atoms);self.assertIn('3:OXT',atoms);self.assertIn('3:HXT',atoms)
    def test_geometry_preserves_handedness_and_bonds(self):
        model=construct('ACDEFGHIKLMNPQRSTVWY');aa={a['id']:a for a in model['atoms']}
        for b in model['bonds']:
            d=distance(aa[b['a']]['xyz'],aa[b['b']]['xyz'])
            if b['kind']=='peptide': self.assertAlmostEqual(d,1.329,places=10)
            elif aa[b['a']]['atomName']!='O' and aa[b['b']]['atomName']!='O':
                c=BY_ONE[model['sequence'][aa[b['a']]['residue']-1]];source={a['id']:a for a in c['atoms']}
                self.assertAlmostEqual(d,distance(source[aa[b['a']]['atomName']]['xyz'],source[aa[b['b']]['atomName']]['xyz']),places=9)
        from peptides import dot,cross,sub
        for i,o in enumerate(model['sequence']):
            if o=='G':continue
            original={a['id']:a['xyz'] for a in BY_ONE[o]['atoms']}
            moved={a['atomName']:a['xyz'] for a in model['atoms'] if a['residue']==i+1}
            def chirality(m):return dot(cross(sub(m['N'],m['CA']),sub(m['C'],m['CA'])),sub(m['CB'],m['CA']))
            self.assertAlmostEqual(chirality(original),chirality(moved),places=9)
    def test_nonfinite_and_unsupported_sequence_rejected(self):
        for seq in ['', 'AXB','ACD*','A'*129,None]:
            with self.assertRaises(ValueError):construct(seq)
        with self.assertRaises(ValueError):state_validate({'schemaVersion':1,'blocks':[],'links':[],'x':float('nan')})
    def test_saved_library_survives_restart(self):
        r=self.save();other=Service(self.tmp.name)
        self.assertEqual(other.dispatch('peptide_library',{'projectId':self.p})[0]['id'],r['id']);other.db.close()
    def test_version_history_is_immutable(self):
        r=self.save();new=self.save(id=r['id'],revision=1,sequence='GPG',name='Changed')
        versions=self.s.dispatch('peptide_versions',{'id':r['id']});self.assertEqual([v['revision'] for v in versions],[2,1]);self.assertEqual(versions[1]['data']['data']['sequence'],'AGSTL');self.assertEqual(new['data']['sequence'],'GPG')
    def test_stale_version_cannot_overwrite(self):
        r=self.save();self.save(id=r['id'],revision=1,sequence='GPG')
        with self.assertRaises(ValueError):self.save(id=r['id'],revision=1,sequence='AAAA')
        self.assertEqual(len(self.s.dispatch('peptide_versions',{'id':r['id']})),2)
    def test_other_projects_cannot_update(self):
        r=self.save();other=self.s.project_create({'name':'Other'})['id']
        with self.assertRaises(ValueError):self.save(projectId=other,id=r['id'],revision=1)
    def test_unconnected_scientific_save_rejected(self):
        st={'schemaVersion':1,'blocks':[{'id':'a','one':'A'},{'id':'g','one':'G'}],'links':[]}
        with self.assertRaises(ValueError):self.save(sequence='AG',state=st)
        st['links']=[{'from':'a','to':'g'}];self.assertTrue(self.save(sequence='AG',state=st)['data']['validation']['valid'])
    def test_reverse_and_nonadjacent_links_rejected(self):
        st={'schemaVersion':1,'blocks':[{'id':'a','one':'A'},{'id':'g','one':'G'},{'id':'s','one':'S'}],'links':[{'from':'s','to':'a'}]}
        with self.assertRaises(ValueError):state_validate(st)
    def test_existing_sequence_visible_without_duplication(self):
        r=self.s.sequence_save({'projectId':self.p,'name':'Existing','sequence':'GPG'});lib=self.s.dispatch('peptide_library',{'projectId':self.p});self.assertEqual(lib[0]['id'],r['id']);self.assertEqual(len(self.s.library({})['records']),1)
    def test_prediction_input_sequences_are_read_views(self):
        r=self.s.import_structure({'projectId':self.p,'path':str(pathlib.Path(__file__).resolve().parents[1]/'fixtures/ANGPTL3.cif'),'metadata':{'provenance':{'chains':[{'sequence':'AGSTL'}]}}})
        lib=self.s.dispatch('peptide_library',{'projectId':self.p});self.assertEqual(lib[0]['id'],r['id']);self.assertEqual(lib[0]['data']['sequenceStatus'],'prediction_input_metadata');self.assertNotIn('sequence',self.s.library({})['records'][0]['data'])
    def test_progress_separate_from_scientific_assets(self):
        st={'schemaVersion':1,'blocks':[{'id':'a','one':'A'},{'id':'g','one':'G'}],'links':[]}
        self.s.dispatch('arcade_save',{'projectId':self.p,'workspace':'arcade','revision':0,'state':st})
        other=Service(self.tmp.name);self.assertEqual(other.dispatch('arcade_load',{'projectId':self.p})['state'],st);other.db.close();self.assertEqual(self.s.library({})['records'],[])
        with self.assertRaises(ValueError):self.s.dispatch('arcade_save',{'projectId':self.p,'revision':0,'state':st})
    def test_architect_progress_independent(self):
        st={'schemaVersion':1,'blocks':[],'links':[]}
        self.s.dispatch('arcade_save',{'projectId':self.p,'workspace':'architect','revision':0,'state':st});self.assertIsNone(self.s.dispatch('arcade_load',{'projectId':self.p})['state'])
    def test_transfer_preserves_source_and_is_sequence_only(self):
        r=self.save();t=self.s.dispatch('peptide_transfer',{'id':r['id']});self.assertEqual(t['sequence'],'AGSTL');self.assertEqual(t['origin']['revision'],1);self.assertFalse(t['origin']['geometryTransfer']);self.assertEqual(t['origin']['workspace'],'arcade')
    def test_structural_export_is_new_unrelaxed_asset(self):
        original=self.s.import_structure({'projectId':self.p,'path':str(pathlib.Path(__file__).resolve().parents[1]/'fixtures/ANGPTL3.cif')});asset=self.s.root/'assets'/original['data']['asset'];before=hashlib.sha256(asset.read_bytes()).hexdigest()
        r=self.save();structure=self.s.dispatch('peptide_structure',{'id':r['id']});self.assertEqual(before,hashlib.sha256(asset.read_bytes()).hexdigest());self.assertIsNone(structure['data']['confidenceKind']);self.assertEqual(structure['data']['metadata']['geometryStatus'],'idealized_unrelaxed')
        self.assertIn('CONECT',self.s.asset_read({'asset':structure['data']['asset']}));self.assertEqual(self.s.library({})['records'][1]['id'],r['id'])
    def test_archive_preserves_peptides_versions_and_progress(self):
        r=self.save();self.s.dispatch('arcade_save',{'projectId':self.p,'revision':0,'state':{'schemaVersion':1,'blocks':[],'links':[]}})
        path=self.s.root/'export.zip';self.s.export_project({'id':self.p,'path':str(path)})
        with zipfile.ZipFile(path) as z:data=json.loads(z.read('project.json'))
        self.assertEqual(data['peptideVersions'][0]['record_id'],r['id']);self.assertEqual(data['constructionProgress'][0]['revision'],1)
    def test_delete_requires_confirmation(self):
        r=self.save()
        with self.assertRaises(ValueError):self.s.dispatch('peptide_delete',{'id':r['id'],'revision':1})
        self.s.dispatch('peptide_delete',{'id':r['id'],'revision':1,'confirmed':True});self.assertEqual(self.s.dispatch('peptide_library',{'projectId':self.p}),[]);self.assertEqual(len(self.s.dispatch('peptide_versions',{'id':r['id']})),1)
    def test_project_delete_removes_progress_and_version_rows(self):
        self.save();self.s.dispatch('arcade_save',{'projectId':self.p,'revision':0,'state':{'schemaVersion':1,'blocks':[],'links':[]}});self.s.project_delete({'id':self.p});self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM arcade_progress').fetchone()[0],0);self.assertEqual(self.s.db.execute('SELECT COUNT(*) FROM peptide_versions').fetchone()[0],0)
    def test_generic_record_save_cannot_forge_validated_peptide(self):
        with self.assertRaises(ValueError):self.s.record_save({'projectId':self.p,'kind':'peptide','name':'Fake','data':{'sequence':'AX','validation':{'valid':True}}})
