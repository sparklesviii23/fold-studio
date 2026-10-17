import copy,json,pathlib,sys,tempfile,unittest,collections
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from worker import Service
from peptides import BY_ONE
from molecular_graph import validate,from_v1,envelope

def legacy(seq,connected=True):
    return {'schemaVersion':1,'blocks':[{'id':'res'+str(i),'one':one,'rotation':90} for i,one in enumerate(seq)],'links':[{'from':'res'+str(i),'to':'res'+str(i+1)} for i in range(len(seq)-1)] if connected else [],'completed':[0,2],'name':'Prior peptide','notes':'Keep my notes','savedId':'prior-id','savedRevision':4,'sourceRecordId':'original-sequence'}
class MolecularGraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.service=Service(self.tmp.name);self.project=self.service.project_create({'name':'Disposable'})['id'];self.service.dispatch('arcade_load',{'projectId':self.project})
    def tearDown(self):self.service.db.close();self.tmp.cleanup()
    def test_each_template_graph_validates_directly(self):
        for one in BY_ONE:self.assertTrue(validate(from_v1(legacy(one)))['valid'],one)
    def test_migration_uses_separated_board_layout_and_legacy_identifiers(self):
        for one in BY_ONE:
            state=from_v1(legacy(one));points=[a['board'] for a in state['atoms']]
            self.assertGreater(min(__import__('math').dist(a,b) for i,a in enumerate(points) for b in points[i+1:]),12,one)
            self.assertEqual(state['legacyChallengeIds'],['v1-first-connection','v1-sulfur-rings'])
            self.assertEqual(state['completed'],[])
    def test_all_four_hundred_condensations_independent_formula(self):
        for a in BY_ONE:
            for b in BY_ONE:
                state=from_v1(legacy(a+b));result=validate(state);self.assertTrue(result['valid'],a+b)
                expected=collections.Counter(atom['element'] for one in a+b for atom in BY_ONE[one]['atoms']);expected.subtract({'H':2,'O':1})
                self.assertEqual(collections.Counter(atom['element'] for atom in state['atoms']),expected)
                peptide=[bond for bond in state['bonds'] if bond['kind']=='peptide'];self.assertEqual(len(peptide),1);self.assertEqual(peptide[0]['order'],1)
                for rid in ['res0','res1']:
                    carbonyl=next(bond for bond in state['bonds'] if {bond['a'],bond['b']}=={rid+':C',rid+':O'});self.assertEqual(carbonyl['order'],2)
    def test_atomic_draft_has_distinct_incomplete_status(self):
        state=from_v1(legacy('G'));removed=state['atoms'].pop();state['bonds']=[b for b in state['bonds'] if removed['id'] not in [b['a'],b['b']]];result=validate(state);self.assertFalse(result['valid']);self.assertEqual(result['status'],'incomplete');self.assertEqual(result['missingAtoms'],1)
    def test_same_sequence_tampered_graph_cannot_save(self):
        original=from_v1(legacy('AG'))
        for kind in ['element','charge','stereo','bond','xyz','aromatic']:
            state=copy.deepcopy(original)
            if kind=='element':state['atoms'][0]['element']='S'
            elif kind=='charge':state['atoms'][0]['charge']=1
            elif kind=='stereo':next(a for a in state['atoms'] if a['templateAtom']=='CA' and a['residueId']=='res0')['stereo']='R'
            elif kind=='bond':next(b for b in state['bonds'] if b['order']==2)['order']=1
            elif kind=='xyz':state['atoms'][0]['xyz'][0]*=-1
            else:state['bonds'][0]['aromatic']=not state['bonds'][0]['aromatic']
            self.assertEqual(validate(state)['status'],'invalid',kind)
            with self.assertRaises(ValueError,msg=kind):self.service.dispatch('peptide_save',{'projectId':self.project,'name':'Tampered','sequence':'AG','state':state})
    def test_duplicate_self_invalid_endpoint_bonds_rejected(self):
        for change in ['duplicate','self','endpoint']:
            state=from_v1(legacy('G'))
            if change=='duplicate':state['bonds'].append(copy.deepcopy(state['bonds'][0]))
            elif change=='self':state['bonds'][0]['b']=state['bonds'][0]['a']
            else:state['bonds'][0]['a']='absent'
            with self.assertRaises(ValueError):envelope(state)
    def test_nonfinite_bounds_and_external_serialization_limits(self):
        for point in [[float('nan'),0],[float('inf'),0],[100001,0]]:
            state=from_v1(legacy('G'));state['atoms'][0]['board']=point
            with self.assertRaises(ValueError):envelope(state)
        state=from_v1(legacy('G'));state['notes']='x'*100001
        with self.assertRaises(ValueError):envelope(state)
    def test_template_stereo_edge_cases_and_aromatic_ring_orders(self):
        for one in 'GPCMHWIT':
            state=from_v1(legacy(one));self.assertTrue(validate(state)['valid'])
            for atom in state['atoms']:
                pinned=next(a for a in BY_ONE[one]['atoms'] if a['id']==atom['templateAtom']);self.assertEqual(atom['stereo'],pinned['stereo'])
        self.assertEqual(next(a for a in from_v1(legacy('C'))['atoms'] if a['templateAtom']=='CA')['stereo'],'R')
        self.assertIn({'res0:N','res0:CD'},[{b['a'],b['b']} for b in from_v1(legacy('P'))['bonds']])
    def test_symmetric_hydrogens_and_arbitrary_atom_ids(self):
        state=from_v1(legacy('G'));ids={a['id']:'player-'+str(i) for i,a in enumerate(state['atoms'])}
        for a in state['atoms']:a['id']=ids[a['id']]
        for b in state['bonds']:b['a']=ids[b['a']];b['b']=ids[b['b']]
        self.assertTrue(validate(state)['valid'])
        # Equivalent HA2/HA3 both connect to CA; swapping endpoint identities remains the same graph.
        left,right=[a['id'] for a in state['atoms'] if a['templateAtom'] in ['HA2','HA3']]
        for b in state['bonds']:
            b['a']=right if b['a']==left else left if b['a']==right else b['a'];b['b']=right if b['b']==left else left if b['b']==right else b['b']
        self.assertTrue(validate(state)['valid'])
    def test_disconnected_migration_preserves_free_termini(self):
        state=from_v1(legacy('GP',False));self.assertEqual(validate(state)['status'],'incomplete');self.assertEqual(len(state['atoms']),sum(len(BY_ONE[o]['atoms']) for o in 'GP'));self.assertEqual(state['completed'],[]);self.assertEqual(state['legacyCompleted'],[0,2]);self.assertEqual(state['notes'],'Keep my notes');self.assertEqual(state['savedRevision'],4);self.assertTrue(all(r['rotation']==0 for r in state['residues']))
    def test_migration_is_idempotent_and_original_retained(self):
        old=legacy('AG');self.service.dispatch('arcade_save',{'projectId':self.project,'revision':0,'state':old});first=self.service.dispatch('molecular_draft_load',{'projectId':self.project});second=self.service.dispatch('molecular_draft_load',{'projectId':self.project});self.assertEqual(first,second);self.assertEqual(self.service.db.execute('SELECT COUNT(*) FROM molecular_migrations').fetchone()[0],1);self.assertEqual(json.loads(self.service.db.execute('SELECT original FROM molecular_migrations').fetchone()[0]),old);self.assertEqual(self.service.dispatch('arcade_load',{'projectId':self.project})['state'],old)
    def test_malformed_legacy_retained_without_overwrite(self):
        broken={'schemaVersion':1,'blocks':[{'id':'x','one':'X'}],'links':[]};self.service.db.execute('INSERT INTO arcade_progress VALUES(?,?,?,?,?)',(self.project,'arcade',1,json.dumps(broken),'now'));self.service.db.commit();result=self.service.dispatch('molecular_draft_load',{'projectId':self.project});self.assertTrue(result['originalRetained']);self.assertIn('migrationError',result);self.assertEqual(self.service.db.execute('SELECT COUNT(*) FROM molecular_drafts').fetchone()[0],0)
    def test_local_practice_needs_no_project(self):
        state=from_v1(legacy('G'));saved=self.service.dispatch('molecular_draft_save',{'revision':0,'state':state});self.assertEqual(saved['revision'],1);self.assertEqual(self.service.dispatch('molecular_draft_load',{})['state'],state)
    def test_draft_roundtrip_and_conflict_are_atomic(self):
        state=from_v1(legacy('AG',False));state['atoms'].pop();state['bonds']=[b for b in state['bonds'] if b['a'] in {a['id'] for a in state['atoms']} and b['b'] in {a['id'] for a in state['atoms']}];self.service.dispatch('molecular_draft_save',{'projectId':self.project,'revision':0,'state':state})
        with self.assertRaises(ValueError):self.service.dispatch('molecular_draft_save',{'projectId':self.project,'revision':0,'state':from_v1(legacy('G'))})
        self.assertEqual(self.service.dispatch('molecular_draft_load',{'projectId':self.project})['state'],state)
    def test_exact_graph_saved_versioned_and_revalidated_on_transfer(self):
        state=from_v1(legacy('AG'));r=self.service.dispatch('peptide_save',{'projectId':self.project,'name':'Direct graph','sequence':'AG','state':state});self.assertEqual(r['data']['graph'],state);self.assertEqual(r['data']['validation']['method'].split()[0],'Direct')
        with self.assertRaises(ValueError):self.service.dispatch('peptide_transfer',{'id':r['id'],'revision':0})
        self.assertEqual(self.service.dispatch('peptide_transfer',{'id':r['id'],'revision':1})['sequence'],'AG');r['data']['graph']['bonds'][0]['order']=3;self.service.db.execute('UPDATE records SET data=? WHERE id=?',(json.dumps(r['data']),r['id']));self.service.db.commit()
        with self.assertRaises(ValueError):self.service.dispatch('peptide_transfer',{'id':r['id']})
    def test_unassigned_free_atoms_are_never_scientific_peptides(self):
        state=from_v1(legacy('G'));state['atoms'].append({'id':'free-carbon','element':'C','charge':0,'stereo':'N','xyz':[0,0,0],'board':[40,60],'residueId':None,'templateAtom':None});self.assertFalse(validate(state)['valid']);self.assertEqual(validate(state)['unassignedAtoms'],1)
    def test_idealized_copy_retains_actual_graph_provenance(self):
        state=from_v1(legacy('AG'));r=self.service.dispatch('peptide_save',{'projectId':self.project,'name':'Graph source','sequence':'AG','state':state})
        result=self.service.dispatch('peptide_structure',{'id':r['id'],'revision':1});metadata=result['data']['metadata']
        self.assertEqual(metadata['graphSha256'],r['data']['graphSha256']);self.assertEqual(metadata['sourceGraphValidation']['method'].split()[0],'Direct')
        self.assertEqual(metadata['geometryStatus'],'idealized_unrelaxed');self.assertNotEqual(result['id'],r['id'])

    def test_interface_preferences_are_bounded_and_persistent(self):
        value={'scale':150,'density':'comfortable','transparency':False,'motion':False}
        self.service.setting_set({'key':'interface','value':value});self.assertEqual(self.service.library({})['settings']['interface'],value)
        with self.assertRaises(ValueError):self.service.setting_set({'key':'interface','value':{**value,'scale':900}})
    def test_external_draft_import_is_bounded_and_structurally_checked(self):
        path=pathlib.Path(self.tmp.name)/'draft.json';state=from_v1(legacy('G'));state['atoms'].pop();state['bonds']=[b for b in state['bonds'] if b['a'] in {a['id'] for a in state['atoms']} and b['b'] in {a['id'] for a in state['atoms']}];path.write_text(json.dumps(state));result=self.service.dispatch('molecular_draft_import',{'path':str(path)});self.assertEqual(result['state'],state);self.assertFalse(result['validation']['valid'])
        state['bonds'][0]['a']='missing';path.write_text(json.dumps(state))
        with self.assertRaises(ValueError):self.service.dispatch('molecular_draft_import',{'path':str(path)})
    def test_project_export_and_delete_preserve_independent_practice(self):
        import zipfile
        state=from_v1(legacy('AG'));self.service.dispatch('molecular_draft_save',{'projectId':self.project,'revision':0,'state':state});self.service.dispatch('molecular_draft_save',{'revision':0,'state':state});path=pathlib.Path(self.tmp.name)/'project.zip';self.service.export_project({'id':self.project,'path':str(path)})
        with zipfile.ZipFile(path) as archive:data=json.loads(archive.read('project.json'))
        self.assertEqual(data['molecularDrafts'][0]['state'],state);self.service.project_delete({'id':self.project});self.assertEqual(self.service.db.execute('SELECT context FROM molecular_drafts').fetchone()[0],'local-practice')
