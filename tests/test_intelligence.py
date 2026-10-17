"""Analytically verifiable structures; no fabricated research results."""
import importlib.util, json, math, pathlib, tempfile, unittest
from unittest.mock import patch
REPO=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mi_worker',REPO/'scientific/worker.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
mi=w.intelligence

def pdb_atom(i,name,res,chain,num,xyz,element=None,b=75,alt='',occ=1):
 return f"ATOM  {i:5d} {name:>4s}{alt:1s}{res:>3s} {chain}{num:4d}    {xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}{occ:6.2f}{b:6.2f}          {(element or name[0]):>2s}\n"
def structure():
 return mi.parse_structure(pdb_atom(1,'CA','ALA','A',11,[0,0,0])+pdb_atom(2,'CB','ALA','A',11,[0,1,0])+pdb_atom(3,'CA','ALA','B',1,[4,0,0])+pdb_atom(4,'CB','ALA','B',1,[2,1,0]),'pdb')
ASSIGN={'A':{'role':'target','identity':'target'},'B':{'role':'candidate','identity':'peptide'}}
class NumericalTests(unittest.TestCase):
 def test_distance_threshold_and_residue_pair_deduplication(self):
  r=mi.analyze(structure(),ASSIGN,{'contact':4,'spherePoints':60});self.assertEqual(r['summary']['atomicContacts'],3);self.assertEqual(r['summary']['uniqueResiduePairs'],1);self.assertEqual(r['residuePairs'][0]['atomPairs'],3)
  self.assertTrue(any(x['distance']==4 for x in r['contacts']))
  r=mi.analyze(structure(),ASSIGN,{'contact':3.999,'spherePoints':60});self.assertEqual(r['summary']['atomicContacts'],2)
 def test_clash_bondi_overlap_and_unique_pair(self):
  r=mi.analyze(structure(),ASSIGN,{'spherePoints':60});self.assertEqual(r['summary']['clashingResiduePairs'],1);self.assertAlmostEqual(r['clashes'][0]['overlap'],1.4);self.assertEqual(r['clashes'][0]['severity'],'severe')
 def test_sasa_isolated_sphere_and_nonintersecting_additivity(self):
  atom=structure()['atoms'][0];a=mi.sasa([atom],120,1.4);self.assertAlmostEqual(a,4*math.pi*3.1**2,9)
  b={**atom,'id':99,'xyz':[20,0,0]};self.assertAlmostEqual(mi.sasa([atom,b],120,1.4),2*a,9)
 def test_identical_sphere_occlusion_is_nonnegative(self):
  r=mi.analyze(structure(),ASSIGN,{'spherePoints':120});self.assertGreaterEqual(r['surface']['totalLoss'],0);self.assertAlmostEqual(r['surface']['interfaceArea']*2,r['surface']['totalLoss'])
 def test_explicit_hydrogen_geometry(self):
  text=pdb_atom(1,'N','ALA','A',1,[0,0,0])+pdb_atom(2,'H','ALA','A',1,[1,0,0])+pdb_atom(3,'O','ALA','B',1,[2.8,0,0]);st=mi.parse_structure(text,'pdb');r=mi.analyze(st,ASSIGN,{'spherePoints':60});hb=[x for x in r['interactions'] if x['type']=='potential hydrogen bond'];self.assertEqual(len(hb),1);self.assertAlmostEqual(hb[0]['angle'],180)
  st['atoms'][1]['xyz']=[-1,0,0];r=mi.analyze(st,ASSIGN,{'spherePoints':60});self.assertFalse(any(x['type']=='potential hydrogen bond' for x in r['interactions']))
 def test_missing_hydrogens_and_non_donor_nitrogen(self):
  text=pdb_atom(1,'ND2','ASN','A',1,[0,0,0])+pdb_atom(2,'O','ALA','B',1,[2.8,0,0]);r=mi.analyze(mi.parse_structure(text,'pdb'),ASSIGN,{'spherePoints':60});self.assertTrue(any(x['type']=='polar approach' for x in r['interactions']));self.assertFalse(any(x['type']=='potential hydrogen bond' for x in r['interactions']))
  self.assertEqual(mi.chemistry({'resname':'ASN','name':'ND2'}),(True,False));self.assertEqual(mi.chemistry({'resname':'LYS','name':'NZ'}),(True,False))
 def test_crop_mapping_and_ambiguity(self):
  r=mi.map_sequence('MACDEFGHIK','DEFG');self.assertEqual(r['state'],'verified');self.assertEqual(r['positions'][1],4)
  self.assertEqual(mi.map_sequence('ACDACD','ACD')['state'],'ambiguous');self.assertFalse(mi.map_sequence('ACDACD','ACD')['positions'])
 def test_mapping_deletion_unique(self):
  r=mi.map_sequence('ACDEFGHIKLMN','ACDEGHIKLMN');self.assertEqual(r['state'],'verified');self.assertEqual(r['positions'][5],6)
 def test_hotspot_original_number_identity_and_missing(self):
  r=mi.analyze(structure(),{**ASSIGN,'A':{**ASSIGN['A'],'reference':'MAM','referenceStart':20}},{'spherePoints':60},[{'chain':'A','referenceNumber':21,'aminoAcid':'A'},{'chain':'A','referenceNumber':22,'aminoAcid':'W'}]);self.assertEqual(r['hotspots'][0]['atomPairs'],4);self.assertEqual(r['hotspots'][1]['state'],'mapping requires confirmation')
 def test_horn_rotation_translation_and_positional_rmsd(self):
  moving=[[0,0,0],[1,0,0],[0,2,0],[0,0,3]];fixed=[[-p[1]+3,p[0]+4,p[2]-2] for p in moving];fit=mi.fit(moving,fixed);self.assertLess(fit['rmsd'],1e-9)
  for a,b in zip(moving,fixed):self.assertLess(math.dist(mi.apply_fit(a,fit),b),1e-8)
  with self.assertRaises(ValueError):mi.fit([[0,0,0],[1,0,0],[2,0,0]],[[0,0,0],[1,0,0],[2,0,0]])
 def test_gapped_cross_model_correspondence_uses_only_identical_mapped_residues(self):
  import copy
  text='';i=0
  for index,(res,xyz) in enumerate(zip(['ALA','SER','GLY','PRO'],[[0,0,0],[1,0,0],[0,2,0],[0,0,3]]),1):i+=1;text+=pdb_atom(i,'CA',res,'A',index,xyz)
  text+=pdb_atom(5,'CA','TRP','D',1,[2,5,0]);st=mi.parse_structure(text,'pdb');base={'id':'one','structure':st,'assignments':{'A':{'role':'target'},'D':{'role':'candidate'}},'residuePairs':[],'summary':{'atomicClashes':0},'hotspots':[]};moving=copy.deepcopy(base);moving['id']='two';moving['structure']=mi.parse_structure(''.join(line+'\n' for line in text.splitlines() if 'SER A   2' not in line),'pdb');pair=mi.compare_pair(base,moving);self.assertLess(pair['alignment']['rmsd'],1e-8);self.assertEqual(pair['alignment']['atoms'],3);self.assertAlmostEqual(pair['metrics']['caPositionalRmsd'],0)
 def test_cif_pdb_equivalence_and_numbering(self):
  st=structure();headers=['group_PDB','id','type_symbol','label_atom_id','label_comp_id','label_asym_id','label_seq_id','auth_asym_id','auth_seq_id','Cartn_x','Cartn_y','Cartn_z','occupancy','B_iso_or_equiv']
  text='data_test\nloop_\n'+'\n'.join('_atom_site.'+h for h in headers)+'\n'
  text+='\n'.join(' '.join(map(str,['ATOM',a['id']+1,a['element'],a['name'],a['resname'],a['chain'],i+1,a['chain'],a['num'],*a['xyz'],1,75])) for i,a in enumerate(st['atoms']))+'\n#\n'
  parsed=mi.parse_structure(text,'mmcif');self.assertEqual([a['xyz'] for a in parsed['atoms']],[a['xyz'] for a in st['atoms']]);self.assertEqual(parsed['chains'][0]['id'],'A');self.assertEqual(parsed['residues'][0]['num'],11)
 def test_residue_altloc_model_and_zero_occupancy(self):
  text='MODEL        1\n'+pdb_atom(1,'CA','ALA','A',1,[0,0,0],alt='A',occ=.4)+pdb_atom(2,'CA','ALA','A',1,[1,0,0],alt='B',occ=.6)+pdb_atom(3,'CB','ALA','A',1,[9,0,0],occ=0)+'ENDMDL\nMODEL        2\n'+pdb_atom(4,'CA','ALA','A',1,[20,0,0]);st=mi.parse_structure(text,'pdb');self.assertEqual(len(st['atoms']),1);self.assertEqual(st['atoms'][0]['xyz'],[1,0,0]);self.assertEqual(len(st['models']),2)
 def test_unknown_element_surface_unavailable(self):
  st=structure();st['atoms'][0]['element']='UNKNOWN';r=mi.analyze(st,ASSIGN,{'spherePoints':60});self.assertEqual(r['surface']['state'],'unavailable')
 def test_symmetry_label_exchange_and_displaced_peptide(self):
  import copy
  text='';i=0
  for ch,res,offset in [('A','ALA',[0,0,0]),('B','ALA',[10,0,0]),('D','GLY',[0,5,0])]:
   for j,p in enumerate([[0,0,0],[1,0,0],[0,2,0],[0,0,3]]):i+=1;text+=pdb_atom(i,'CA',res,ch,j+1,[p[k]+offset[k] for k in range(3)])
  st=mi.parse_structure(text,'pdb');base={'id':'one','structure':st,'assignments':{'A':{'role':'target'},'B':{'role':'target'},'D':{'role':'candidate'}},'residuePairs':[],'summary':{'atomicClashes':0},'hotspots':[]};other=copy.deepcopy(base);other['id']='two'
  for c in other['structure']['chains']:
   if c['id'] in ('A','B'):c['id']='B' if c['id']=='A' else 'A'
  for r in other['structure']['residues']:
   if r['chain'] in ('A','B'):r['chain']='B' if r['chain']=='A' else 'A'
  for a in other['structure']['atoms']:
   if a['chain'] in ('A','B'):a['chain']='B' if a['chain']=='A' else 'A'
   if a['chain']=='D':a['xyz'][1]+=4
  result=mi.compare_pair(base,other);self.assertEqual(result['chainMapping']['A'],'B');self.assertLess(result['alignment']['rmsd'],1e-8);self.assertAlmostEqual(result['metrics']['caPositionalRmsd'],4);self.assertLess(result['metrics']['caInternalRmsd'],1e-8)

class PersistenceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.s=w.Service(pathlib.Path(self.temp.name)/'library');self.project=self.s.project_create({'name':'Test'});self.lab=mi.Lab(self.s);self.path=pathlib.Path(self.temp.name)/'complex.pdb';self.path.write_text(pdb_atom(1,'CA','ALA','A',1,[0,0,0])+pdb_atom(2,'CA','ALA','B',1,[4,0,0]));self.record=self.s.import_structure({'projectId':self.project['id'],'path':str(self.path)});self.lab.intelligence_assign({'structureId':self.record['id'],'assignments':ASSIGN})
 def tearDown(self):self.s.db.close();self.temp.cleanup()
 def run_analysis(self):
  with patch.object(self.lab,'launch'):t=self.lab.intelligence_start({'structureId':self.record['id'],'settings':{'spherePoints':60}})
  self.lab.run(t['id']);return self.lab.intelligence_result({'id':t['id']})
 def test_analysis_versions_exports_and_restart(self):
  a=self.run_analysis();b=self.run_analysis();self.assertNotEqual(a['id'],b['id']);self.assertEqual(a['contacts'],b['contacts']);self.assertEqual(a['source']['sha256'],self.record['data']['sha256']);self.assertIsNone(a['confidence']['plddt']);self.assertIsNone(a['confidence']['pae'])
  report=self.lab.intelligence_export({'id':a['id'],'format':'markdown'});self.assertIn('Unavailable',report['text']);csv=self.lab.intelligence_export({'id':a['id'],'format':'csv'});self.assertIn('4.0',csv['text'])
  s=w.Service(self.s.root);self.assertEqual(mi.Lab(s).intelligence_result({'id':a['id']})['contacts'],a['contacts']);s.db.close()
 def test_confidence_mapping_direction_and_bfactor_semantics(self):
  st=self.lab.intelligence_inspect({'structureId':self.record['id']});self.assertIsNone(st['confidence']['plddt']);tokens=[r['id'] for r in st['structure']['residues']];p=pathlib.Path(self.temp.name)/'confidence.json';p.write_text(json.dumps({'pae':[[0,2],[8,0]],'plddt':[80,60],'tokenMap':tokens,'iptm':.6}));self.lab.intelligence_confidence_import({'structureId':self.record['id'],'path':str(p)});r=self.run_analysis();self.assertEqual(r['confidence']['directional']['targetToPeptide'],2);self.assertEqual(r['confidence']['directional']['peptideToTarget'],8);self.assertEqual(r['confidence']['meanByChain'],{'A':80,'B':60})
  p.write_text(json.dumps({'pae':[[0,2],[8,0]]}))
  with self.assertRaises(ValueError):self.lab.intelligence_confidence_import({'structureId':self.record['id'],'path':str(p)})
 def test_scramble_permanent_and_composition(self):
  p={'projectId':self.project['id']};c=self.lab.intelligence_candidate_save({**p,'name':'candidate','sequence':'QTDSGKVLSKLQARLDDLWE'});control=self.lab.intelligence_scramble({**p,'candidateId':c['id'],'seed':42});self.assertEqual(sorted(c['data']['sequence']),sorted(control['data']['sequence']));self.assertNotEqual(c['data']['sequence'],control['data']['sequence']);self.assertEqual(self.lab.intelligence_candidates(p)[1]['data']['sequence'],control['data']['sequence'])
 def test_cancel_and_checksum_refusal(self):
  with patch.object(self.lab,'launch'):t=self.lab.intelligence_start({'structureId':self.record['id']})
  self.lab.intelligence_cancel({'id':t['id']});self.lab.run(t['id']);self.assertEqual(self.lab.task(t['id'])['state'],'cancelled')
  asset=self.s.root/'assets'/self.record['data']['asset'];asset.write_text(asset.read_text()+'REMARK changed\n')
  with self.assertRaises(ValueError):self.lab.intelligence_inspect({'structureId':self.record['id']})
 def test_real_background_worker_lifecycle(self):
  import time
  task=self.lab.intelligence_start({'structureId':self.record['id'],'settings':{'spherePoints':60}})
  deadline=time.monotonic()+8
  while self.lab.task(task['id'])['state'] in ('running','queued') and time.monotonic()<deadline:time.sleep(.05)
  self.assertEqual(self.lab.task(task['id'])['state'],'completed');self.assertEqual(self.lab.intelligence_result({'id':task['id']})['summary']['atomicContacts'],1)
 def test_pdf_exports_and_project_archive_preserves_analyses(self):
  import base64,zipfile
  result=self.run_analysis();pdf=base64.b64decode(self.lab.intelligence_export({'id':result['id'],'format':'pdf'})['base64']);self.assertTrue(pdf.startswith(b'%PDF-1.4'));self.assertTrue(pdf.endswith(b'%%EOF\n'));self.assertIn(b'/Type /Page',pdf)
  path=pathlib.Path(self.temp.name)/'project.zip';self.s.export_project({'id':self.project['id'],'path':str(path)})
  with zipfile.ZipFile(path) as z:
   self.assertIn('intelligence/'+result['id']+'.json',z.namelist());data=json.loads(z.read('project.json'));self.assertEqual(len(data['molecularIntelligence']['intelligence_tasks']),1)
 def test_report_exports_pass_the_actual_file_writer(self):
  result=self.run_analysis()
  for kind in ['pdf','csv','markdown','json']:
   exported=self.lab.intelligence_export({'id':result['id'],'format':kind});path=pathlib.Path(self.temp.name)/exported['name'];self.s.export_file({'path':str(path),**{k:v for k,v in exported.items() if k!='name'}});self.assertTrue(path.is_file());self.assertGreater(path.stat().st_size,20)
  for kind in ['project-pdf','project-json','project-markdown']:
   exported=self.lab.intelligence_export({'projectId':self.project['id'],'format':kind});path=pathlib.Path(self.temp.name)/exported['name'];self.s.export_file({'path':str(path),**{k:v for k,v in exported.items() if k!='name'}});self.assertTrue(path.is_file())
 def test_completed_results_cannot_be_overwritten_and_tampering_is_detected(self):
  result=self.run_analysis();path=self.lab.root/(result['id']+'.json');before=path.read_bytes();self.lab.run(result['id']);self.assertEqual(path.read_bytes(),before)
  path.write_bytes(before+b' ')
  with self.assertRaises(ValueError):self.lab.intelligence_result({'id':result['id']})
 def test_worker_launch_failure_is_retryable(self):
  with patch.object(self.lab,'launch',side_effect=OSError('declared test failure')):
   with self.assertRaises(OSError):self.lab.intelligence_start({'structureId':self.record['id']})
  task=self.lab.intelligence_tasks({'projectId':self.project['id']})[0];self.assertEqual(task['state'],'failed')
  with patch.object(self.lab,'launch'):retry=self.lab.intelligence_resume({'id':task['id']})
  self.assertNotEqual(retry['id'],task['id']);self.assertEqual(retry['data']['previousAttempt'],task['id'])
 def test_saved_scalar_confidence_does_not_require_fabricated_arrays(self):
  info=self.lab.intelligence_inspect({'structureId':self.record['id']});file=pathlib.Path(self.temp.name)/'scalar.json';file.write_text(json.dumps({'ptm':.75,'iptm':.6}))
  cf=self.lab.intelligence_confidence_import({'structureId':self.record['id'],'path':str(file),'tokenMap':[r['id'] for r in info['structure']['residues']]});self.assertEqual(cf['ptm'],.75);self.assertIsNone(cf['pae']);self.assertIsNone(cf['plddt'])
 def test_candidate_control_flags_use_actual_measurements(self):
  p={'projectId':self.project['id']};candidate=self.lab.intelligence_candidate_save({**p,'name':'peptide','sequence':'A'});self.lab.intelligence_assign({'structureId':self.record['id'],'assignments':ASSIGN});self.run_analysis()
  control=self.lab.intelligence_candidate_save({**p,'name':'control','sequence':'G','role':'control','controlFor':candidate['id']})
  path=pathlib.Path(self.temp.name)/'control.pdb';path.write_text(pdb_atom(1,'CA','ALA','A',1,[0,0,0])+pdb_atom(2,'CA','GLY','B',1,[4,0,0]));item=self.s.import_structure({**p,'path':str(path)});assignment={'A':ASSIGN['A'],'B':{'identity':'control','role':'control'}};self.lab.intelligence_assign({'structureId':item['id'],'assignments':assignment})
  with patch.object(self.lab,'launch'):task=self.lab.intelligence_start({'structureId':item['id'],'settings':{'spherePoints':60}})
  self.lab.run(task['id']);evidence=self.lab.intelligence_prioritize(p);self.assertEqual([r['runs'] for r in evidence['candidates']],[1,1]);self.assertTrue(any('Jaccard' in f for f in evidence['flags']));self.assertTrue(any('do not establish sequence-specific binding' in f for f in evidence['flags']))
 def test_native_radius_settings_are_explicit(self):
  with self.assertRaises(ValueError):mi.settings({'hbAllowance':.4})
  settings=mi.settings({'radiusMethod':'chimerax-default','hbAllowance':.4});self.assertEqual(settings['hbAllowance'],.4)
 def test_coincident_spheres_union_surface(self):
  a=structure()['atoms'][0];b={**a,'id':99};self.assertAlmostEqual(mi.sasa([a,b],120,1.4),mi.sasa([a],120,1.4),9)
 def test_screen_orchestration_uses_existing_predictor(self):
  p={'projectId':self.project['id']};candidate=self.lab.intelligence_candidate_save({**p,'name':'candidate','sequence':'A'})
  self.path.write_text(pdb_atom(1,'CA','ALA','A',1,[0,0,0])+pdb_atom(2,'CA','PRO','A',2,[1,0,0])+pdb_atom(3,'CA','GLY','A',3,[0,1,0])+pdb_atom(4,'CA','ALA','B',1,[4,0,0]))
  calls=[]
  def predict(payload):
   calls.append(payload);job=self.s.job_new(payload,'boltz2','completed');record=self.s.import_structure({'projectId':self.project['id'],'path':str(self.path),'metadata':{'jobId':job['id'],'provenance':{'origin':payload['origin']}}});self.s.job_update(job['id'],'completed',{'outputs':[record['id']]});return self.s.job(job['id'])
  with patch.object(self.lab,'launch',side_effect=lambda id:self.lab.run(id)),patch.object(self.s,'prediction_start',side_effect=predict):
   task=self.lab.intelligence_screen({**p,'candidateIds':[candidate['id']],'targetFasta':'>target\nAPG','seeds':[42,43],'start':True,'autoAnalyze':True})
  self.assertEqual(task['state'],'completed');self.assertEqual([c['seed'] for c in calls],[42,43]);result=self.lab.intelligence_result({'id':task['id']});self.assertEqual(len(result['analyses']),2);self.assertEqual(len(result['jobs']),2);self.assertEqual(self.lab.task(result['comparisons'][0])['state'],'completed')
 def test_automatic_analysis_refuses_unmatched_sequences(self):
  self.lab.intelligence_auto({'structureId':self.record['id'],'enabled':True})
  job={'project_id':self.project['id'],'data':{'chains':[{'sequence':'GGGG'}]}}
  with self.assertRaises(ValueError):self.lab.auto_prediction(job,[])
 def test_automatic_roles_allow_identical_target_copies_with_different_names(self):
  job={'project_id':self.project['id'],'data':{'chains':[{'name':'copy_A','sequence':'APG'},{'name':'copy_B','sequence':'APG'},{'name':'peptide','sequence':'W'}]}}
  config={'enabled':True,'chains':[{'sequence':'APG','assignment':{'role':'target','identity':'copy_A'}},{'sequence':'APG','assignment':{'role':'target','identity':'copy_B'}},{'sequence':'W','assignment':{'role':'candidate','identity':'peptide'}}]}
  with patch.object(self.s,'setting',return_value=config):self.assertEqual(self.lab.auto_prediction(job,[]),[])
 def test_screen_plan_is_read_only_and_exact_sequences(self):
  p={'projectId':self.project['id']};c=self.lab.intelligence_candidate_save({**p,'name':'candidate','sequence':'ACDE'});plan=self.lab.intelligence_screen({**p,'candidateIds':[c['id']],'targetFasta':'>target\nGGGG','seeds':[42,43],'samples':2});self.assertEqual(plan['plan']['workload']['jobs'],2);self.assertEqual(plan['plan']['workload']['samples'],4);self.assertFalse(self.s.library({})['jobs'])
if __name__=='__main__':unittest.main()
