"""Independent geometric checks and real bounded encoding; no model predictions."""
import base64
import hashlib
import importlib.util
import json
import math
import pathlib
import struct
import subprocess
import tempfile
import unittest
import zlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('research_worker',ROOT/'scientific/worker.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)


def atom(i,res,chain,n,xyz):
    return f'ATOM  {i:5d}   CA {res:>3s} {chain}{n:4d}    {xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00 80.00           C\n'


def png(width=320,height=180):
    def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+bytes([60,90,160])*width)*height))+chunk(b'IEND',b'')


def timeline():
    camera={'position':[0,0,20],'target':[0,0,0],'up':[0,1,0]}
    return {'schemaVersion':1,'mode':'presentation','duration':1,'keyframes':[{'time':0,'camera':camera},{'time':1,'camera':camera}]}


class ResearchCinemaTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.temp.name);self.s=w.Service(self.root/'library');self.project=self.s.project_create({'name':'Analytical fixture'})
        text=''.join(atom(i+1,res,'A',i+11,xyz) for i,(res,xyz) in enumerate(zip(['ALA','SER','GLY'],[[0,0,0],[3,0,0],[0,3,0]])))+atom(4,'TRP','D',1,[0,0,8])
        self.path=self.root/'fixture.pdb';self.path.write_text(text);self.record=self.s.import_structure({'projectId':self.project['id'],'path':str(self.path),'metadata':{'chainRoles':{'A':{'role':'target'},'D':{'role':'candidate'}}}})
        self.p={'structureId':self.record['id'],'projectId':self.project['id']}
        self.hash=hashlib.sha256(self.path.read_bytes()).hexdigest()
    def tearDown(self):self.s.db.close();self.temp.cleanup()
    def call(self,action,**values):return self.s.dispatch(action,{**self.p,**values})
    def test_candidate_records_observed_geometry_without_fabricated_assays(self):
        r=self.call('research_candidate');self.assertEqual([c['sequence'] for c in r['chains']],['ASG','W']);self.assertEqual(r['chains'][1]['role'],'candidate');self.assertEqual(r['evidence'],[])
        self.assertEqual(r['checks'][-1]['state'],'not supplied');self.assertAlmostEqual(r['chains'][1]['descriptors']['gravy'],-.9)
    def test_annotation_and_raw_assay_persist_without_affinity_claim(self):
        self.call('research_annotation',text='Compare independent conformations.')
        self.call('research_assay_save',name='Supplied test measurements',concentrationUnit='nM',responseUnit='RU',rows=[{'concentration':0,'response':0},{'concentration':10,'response':3}],conditions='Synthetic software fixture, not biological results')
        r=self.call('research_candidate');self.assertEqual(len(r['evidence']),2);self.assertNotIn('KD',json.dumps(r['evidence']));self.assertEqual(r['checks'][-1]['state'],'supplied')
        with self.assertRaises(ValueError):self.call('research_assay_save',name='Bad',concentrationUnit='nM',responseUnit='RU',rows=[{'concentration':-1,'response':3}])
    def test_scope_and_checksum_guards(self):
        with self.assertRaises(ValueError):self.s.dispatch('research_candidate',{**self.p,'projectId':'another-project'})
        asset=self.s.root/'assets'/self.record['data']['asset'];asset.write_text(asset.read_text()+'REMARK changed\n')
        with self.assertRaises(ValueError):self.call('research_candidate')
    def test_full_target_fit_retains_author_mapping_and_original_source(self):
        text=''.join(atom(i+1,res,'B',i+101,[xyz[0]+10,xyz[1]-4,xyz[2]+2]) for i,(res,xyz) in enumerate(zip(['ALA','SER','GLY'],[[0,0,0],[3,0,0],[0,3,0]])))
        full=self.root/'full.pdb';full.write_text(text);item=self.s.import_structure({'projectId':self.project['id'],'path':str(full)})
        result=self.call('research_full_target',fullStructureId=item['id'],chainMap={'A':'B'},binderChains=['D'])['data']
        self.assertLess(result['transform']['rmsd'],1e-7);self.assertEqual(result['clashPairs'],0);self.assertIn('101',result['residueMap'][0]['full'])
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(),self.hash)
        with self.assertRaises(ValueError):self.call('research_full_target',fullStructureId=item['id'],chainMap={'A':'B'},binderChains=['A'])
    def test_larger_reference_scene_preserves_both_sources_and_records_pose_hypothesis(self):
        text=''.join(atom(i+1,res,'B',i+101,[xyz[0]+10,xyz[1]-4,xyz[2]+2]) for i,(res,xyz) in enumerate(zip(['ALA','SER','GLY'],[[0,0,0],[3,0,0],[0,3,0]])))
        full=self.root/'full.pdb';full.write_text(text);item=self.s.import_structure({'projectId':self.project['id'],'path':str(full)})
        result=self.call('research_full_scene',fullStructureId=item['id'],chainMap={'A':'B'},binderChains=['D'])
        derived=result['record'];st=w.intelligence.parse_structure((self.s.root/'assets'/derived['data']['asset']).read_text(),'mmcif')
        self.assertEqual([c['id'] for c in st['chains']],['B','D']);self.assertEqual(st['atoms'][0]['xyz'],[10,-4,2]);self.assertEqual(st['atoms'][-1]['xyz'],[10,-4,10]);self.assertEqual(self.path.read_bytes(),(self.s.root/'assets'/self.record['data']['asset']).read_bytes())
        self.assertEqual(derived['data']['metadata']['parentStructureId'],self.record['id']);self.assertIn('UNVERIFIED',result['disclosure']);self.assertEqual(full.read_text(),text)
        scene=self.s.dispatch('cinema_save',{'projectId':self.project['id'],'structureId':derived['id'],'name':'Derived fixture','timeline':timeline()})
        self.assertEqual(scene['data']['sourceContext']['referenceSha256'],item['data']['sha256']);self.assertEqual(scene['data']['style']['disclosure'],result['disclosure'])
    def test_poor_fit_requires_explicit_illustration_choice(self):
        full=self.root/'different.pdb';full.write_text(''.join(atom(i+1,res,'B',i+101,xyz) for i,(res,xyz) in enumerate(zip(['ALA','SER','GLY'],[[0,0,0],[30,0,0],[0,30,0]]))))
        item=self.s.import_structure({'projectId':self.project['id'],'path':str(full)})
        with self.assertRaises(ValueError):self.call('research_full_scene',fullStructureId=item['id'],chainMap={'A':'B'},binderChains=['D'])
        result=self.call('research_full_scene',fullStructureId=item['id'],chainMap={'A':'B'},binderChains=['D'],allowPoorFit=True)
        self.assertIn('POOR FIT',result['disclosure'])
    def test_pose_contacts_use_exact_heavy_atom_cutoff_and_cached_source_evidence(self):
        path=self.root/'contacts.pdb';path.write_text(atom(1,'ALA','A',11,[0,0,0])+atom(2,'TRP','D',1,[0,0,4]))
        item=self.s.import_structure({'projectId':self.project['id'],'path':str(path)})
        p={'projectId':self.project['id'],'structureId':item['id'],'targetChains':['A'],'binderChains':['D']}
        first=self.s.dispatch('research_contacts',p);second=self.s.dispatch('research_contacts',p)
        self.assertEqual(first['id'],second['id']);self.assertEqual(first['data']['pairs'],1);self.assertEqual(first['data']['atomPairs'][0]['distanceAngstrom'],4);self.assertEqual(len(first['data']['atoms']),2)
    def test_export_is_reproducible_source_evidence_not_validation_certificate(self):
        result=self.call('research_export');data=json.loads(result['text']);self.assertEqual(data['sourceSha256'],self.hash);self.assertEqual(hashlib.sha256(result['text'].encode()).hexdigest(),result['sha256'])
    def test_variants_keep_author_residues_and_reject_invalid_batch_without_mutation(self):
        with self.assertRaises(ValueError):self.call('research_variants',binderChain='A',substitutions=[{'position':1,'aminoAcid':'W'},{'position':4,'aminoAcid':'F'}])
        self.assertEqual(self.s.dispatch('intelligence_candidates',{'projectId':self.project['id']}),[])
        r=self.call('research_variants',binderChain='A',substitutions=[{'position':2,'aminoAcid':'F'}])
        variant=r['variants'][0]['data'];self.assertEqual(variant['sequence'],'AFG');self.assertIn('12',variant['mutation']['authorResidue']);self.assertEqual(variant['sourceSha256'],self.hash)
    def test_reviewed_screen_is_reproducible_and_does_not_launch(self):
        r=self.call('research_screen_plan',binderChain='A',targetChains=['D'],seeds=[42,43],includeScramble=True)
        self.assertEqual(r['plan']['workload']['jobs'],4);self.assertEqual(self.s.rows('SELECT * FROM jobs'),[]);self.assertEqual(self.s.rows('SELECT * FROM intelligence_tasks'),[])
        self.assertEqual(r['startPayload']['msa'],'single');self.assertTrue(r['startPayload']['start'])
        seqs=[c['data']['sequence'] for c in self.s.dispatch('intelligence_candidates',{'projectId':self.project['id']})];self.assertEqual(len(seqs),2);self.assertTrue(all(sorted(s)==sorted('ASG') for s in seqs))
    def test_bad_screen_plan_does_not_create_sequences(self):
        with self.assertRaises(ValueError):self.call('research_screen_plan',binderChain='A',targetChains=['D'],seeds=[42,42],includeScramble=True)
        self.assertEqual(self.s.dispatch('intelligence_candidates',{'projectId':self.project['id']}),[])
    def test_poor_registration_cannot_be_misread_as_compatibility(self):
        full=self.root/'different.pdb';full.write_text(''.join(atom(i+1,res,'B',i+101,xyz) for i,(res,xyz) in enumerate(zip(['ALA','SER','GLY'],[[0,0,0],[30,0,0],[0,30,0]]))))
        item=self.s.import_structure({'projectId':self.project['id'],'path':str(full)})
        result=self.call('research_full_target',fullStructureId=item['id'],chainMap={'A':'B'},binderChains=['D'])['data']
        self.assertEqual(result['registrationState'],'poor_fit');self.assertIn('unverified',result['referenceScope']);self.assertGreater(result['transform']['rmsd'],2)
    def test_render_observations_reject_empty_frames_and_nonfinite_values(self):
        r=self.call('cinema_validate_views',frames=[{'axis':'x','foregroundFraction':0}]);self.assertEqual(r['state'],'failed')
        r=self.call('cinema_validate_views',frames=[{'axis':'y','foregroundFraction':.2}]);self.assertEqual(r['state'],'passed');self.assertIn('does not prove every atom',r['scope'])
        with self.assertRaises(ValueError):self.call('cinema_validate_views',frames=[{'axis':'z','foregroundFraction':float('nan')}])
    def test_bundle_manifest_covers_transitive_local_service_imports(self):
        import ast
        config=json.loads((ROOT/'src-tauri/tauri.conf.json').read_text());resources=set(config['bundle']['resources'].values());pending=['worker'];seen=set()
        while pending:
            name=pending.pop()
            if name in seen:continue
            seen.add(name);self.assertIn('scientific/'+name+'.py',resources)
            for node in ast.walk(ast.parse((ROOT/'scientific'/(''+name+'.py')).read_text())):
                imports=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module] if isinstance(node,ast.ImportFrom) and node.module else []
                pending.extend(n.split('.')[0] for n in imports if (ROOT/'scientific'/(n.split('.')[0]+'.py')).is_file())
    def begin(self,extension='zip'):
        return self.call('cinema_begin',timeline=timeline(),path=str(self.root/('film.'+extension)),fps=2,width=320,height=180)
    def test_timeline_validation_rejects_physical_mode_and_invalid_camera(self):
        t=timeline();t['mode']='simulation'
        with self.assertRaises(ValueError):self.call('cinema_save',name='Unsupported',timeline=t)
        t=timeline();t['keyframes'][0]['camera']['position']=[0,0,0]
        with self.assertRaises(ValueError):self.call('cinema_save',name='Invalid camera',timeline=t)
    def test_presentation_translation_contract_and_degenerate_camera(self):
        t=timeline();t['style']={'binderChains':['D']};t['keyframes'][0]['offsets']={'D':[40,0,0]}
        self.call('cinema_save',name='Approach',timeline=t)
        t['keyframes'][0]['offsets']={'A':[40,0,0]}
        with self.assertRaises(ValueError):self.call('cinema_save',name='Moves target',timeline=t)
        t=timeline();t['keyframes'][0]['camera']['up']=[0,0,1]
        with self.assertRaises(ValueError):self.call('cinema_save',name='Degenerate camera',timeline=t)
    def test_save_restore_versions_and_ordered_frame_contract(self):
        self.call('cinema_save',name='Fixture presentation',timeline=timeline());self.assertEqual(len(self.call('cinema_list')),1)
        job=self.begin();frame=base64.b64encode(png()).decode()
        with self.assertRaises(ValueError):self.call('cinema_frame',id=job['id'],index=1,png=frame)
        self.call('cinema_frame',id=job['id'],index=0,png=frame)
        with self.assertRaises(ValueError):self.call('cinema_frame',id=job['id'],index=1,png=base64.b64encode(png(322)).decode())
        self.call('cinema_cancel',id=job['id']);self.assertFalse(list((self.s.root/'cinema'/job['id']).glob('*.png')))
    def test_real_frame_archive_and_cleanup(self):
        import zipfile
        job=self.begin();frame=base64.b64encode(png()).decode()
        for index in range(2):self.call('cinema_frame',id=job['id'],index=index,png=frame)
        result=self.call('cinema_finish',id=job['id']);self.assertEqual(result['state'],'completed')
        with zipfile.ZipFile(result['output']) as z:self.assertEqual(len([n for n in z.namelist() if n.endswith('.png')]),2)
        self.assertFalse(list((self.s.root/'cinema'/job['id']).glob('*.png')))
    @unittest.skipUnless(w.cinema.encoder(),'FFmpeg unavailable; real encoder check NOT RUN')
    def test_real_mp4_encoding_and_decode(self):
        job=self.begin('mp4');frame=base64.b64encode(png()).decode()
        for index in range(2):self.call('cinema_frame',id=job['id'],index=index,png=frame)
        result=self.call('cinema_finish',id=job['id']);self.assertGreater(pathlib.Path(result['output']).stat().st_size,100)
        decoded=subprocess.run([w.cinema.encoder(),'-v','error','-i',result['output'],'-f','null','-'],capture_output=True)
        self.assertEqual(decoded.returncode,0,decoded.stderr.decode())
    def test_movie_guard_does_not_overwrite_existing_output(self):
        (self.root/'film.zip').write_text('keep')
        with self.assertRaises(ValueError):self.begin()
        self.assertEqual((self.root/'film.zip').read_text(),'keep')
    def test_cancel_marker_survives_stale_manifest_and_allows_another_export(self):
        job=self.begin();folder=self.s.root/'cinema'/job['id'];stale=(folder/'export.json').read_text()
        self.call('cinema_cancel',id=job['id']);(folder/'export.json').write_text(stale)
        self.assertEqual(self.call('cinema_status',id=job['id'])['state'],'cancelled')
        with self.assertRaises(ValueError):self.call('cinema_frame',id=job['id'],index=0,png=base64.b64encode(png()).decode())
        self.assertNotEqual(self.begin()['id'],job['id'])
