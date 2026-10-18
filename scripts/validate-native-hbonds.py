"""Live native H-bond wrapper/command equivalence on an explicit artificial QA fixture."""
import argparse,hashlib,json,pathlib,signal,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--directory',required=True);p.add_argument('--engine-root',default=str(ROOT));a=p.parse_args();ENGINE=pathlib.Path(a.engine_root).resolve();sys.path.insert(0,str(ENGINE/'scientific'))
from worker import Service
from observatory import Observatory
import intelligence as mi
folder=pathlib.Path(a.directory).resolve()
if folder.exists():raise SystemExit('Choose a new disposable validation directory.')
s=Service(folder);obs=Observatory(s);pid=None
def atom(i,name,res,ch,xyz,element):return f'ATOM  {i:5d} {name:>4s} {res:>3s} {ch}{(2 if res=='HOH' else 1):4d}    {xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}{1.:6.2f}{0.:6.2f}          {element:>2s}\n'
rows=[('N','SER','A',(-3.,.5,0),'N'),('CA','SER','A',(-1.8,.5,0),'C'),('C','SER','A',(-1.8,-.9,0),'C'),('O','SER','A',(-2.6,-1.7,0),'O'),('CB','SER','A',(-.5,.8,0),'C'),('OG','SER','A',(0.,0.,0.),'O'),('HG','SER','A',(.96,0.,0.),'H'),('N','ALA','B',(6.,1.2,0.),'N'),('CA','ALA','B',(4.7,1.2,0.),'C'),('C','ALA','B',(4.03,0.,0.),'C'),('O','ALA','B',(2.8,0.,0.),'O'),('CB','ALA','B',(4.3,2.5,0.),'C'),('O','HOH','A',(1.2,.8,0.),'O')]
path=folder/'ARTIFICIAL_hbond_geometry.pdb';path.write_text('REMARK Artificial algorithm QA geometry, not experimental or predicted biology.\n'+''.join(atom(i,*row) for i,row in enumerate(rows,1))+'END\n')
project=s.project_create({'name':'Native hydrogen-bond algorithm QA'});record=s.import_structure({'projectId':project['id'],'path':str(path),'name':'Artificial SER–ALA donor/acceptor geometry · QA only'});lab=mi.Lab(s);saved,asset=lab.record(record['id']);original=hashlib.sha256(asset.read_bytes()).hexdigest()
try:
 launched=obs.chimerax_start({'headless':True});pid=launched['pid']
 for _ in range(60):
  if obs.chimerax_status({})['connected']:break
  time.sleep(1)
 else:raise RuntimeError('Native interpreter did not connect.')
 st=mi.parse_structure(asset.read_text(),'pdb');assign={'A':{'role':'target'},'B':{'role':'candidate'}}
 assert all(a['resname']!='HOH' for a in st['atoms'])
 result=lab.native_radii(saved,asset,st,assign,{'radiusMethod':'chimerax-default','hbAllowance':.4});bonds=result['nativeHydrogenBonds']
 assert bonds and any(st['atoms'][b['donor']]['name']=='OG' and st['atoms'][b['acceptor']]['name']=='O' and abs(b['distance']-2.8)<1e-5 for b in bonds)
 assert len(obs.chimerax_state({})['models'])==0,'Temporary analysis model was not closed.'
 opened=obs.chimerax_open({'projectId':project['id'],'structureId':record['id']});model=opened['mapping'][0]['modelId']
 command='hbonds #'+model+'&~:HOH restrict both relax false interModel false makePseudobonds false'
 code="import json\npairs=run(session,"+repr(command)+")\ndef key(a):return [a.residue.chain_id,int(a.residue.number),a.residue.insertion_code or '',a.name]\nprint('FOLD_NATIVE_REFERENCE:'+json.dumps([[key(d),key(a)] for d,a in pairs if d.residue.chain_id!=a.residue.chain_id]))"
 native=obs.chimerax_python({'projectId':project['id'],'confirmed':True,'code':code})
 if native['state']!='completed':raise RuntimeError(str(native))
 line=next(line for line in native['stdout'].splitlines() if line.startswith('FOLD_NATIVE_REFERENCE:'));reference=json.loads(line.split(':',1)[1])
 def key(atom):return [atom['chain'],atom['num'],atom['ins'],atom['name']]
 actual=[[key(st['atoms'][b['donor']]),key(st['atoms'][b['acceptor']])] for b in bonds]
 assert sorted(actual)==sorted(reference),'Wrapper and original hbonds command pairs differ.'
 lab.intelligence_assign({'structureId':record['id'],'assignments':assign})
 task=lab.intelligence_start({'structureId':record['id'],'settings':{'radiusMethod':'chimerax-default','hbAllowance':.4,'spherePoints':60}})
 deadline=time.monotonic()+45
 while lab.task(task['id'])['state'] in ('queued','running'):
  if time.monotonic()>deadline:raise RuntimeError('Native analysis job timeout.')
  time.sleep(.2)
 saved_result=lab.intelligence_result({'id':task['id']})
 assert saved_result['summary']['nativeHydrogenBonds']==len(bonds)
 assert saved_result['nativeHydrogenBonds']==bonds
 assert 'ChimeraX strict hydrogen bond' in lab.intelligence_export({'id':task['id'],'format':'csv'})['text']
 assert 'ChimeraX strict cross-partner hydrogen bonds' in lab.intelligence_export({'id':task['id'],'format':'markdown'})['text']
 assert json.loads(lab.intelligence_export({'id':task['id'],'format':'json'})['text'])['nativeHydrogenBonds']==bonds
 assert hashlib.sha256(asset.read_bytes()).hexdigest()==original
 report={'state':'passed','scope':'Artificial SER–ALA geometry; wrapper agrees with original ChimeraX strict hbonds command; independent donor–acceptor distance 2.8 Å. Algorithm integration check, not biological validation.','engineRoot':str(ENGINE),'command':command,'pairs':actual,'sourceSha256':original,'nativeHydrogenBondMethod':result['hydrogenBondMethod'],'unselectedWaterExcluded':True,'temporaryModelCleanup':'passed','sourceAssetUnchanged':True,'sharedAnalysisJob':'completed','analysisId':task['id'],'exports':['JSON','CSV','Markdown']}
 (ROOT/'reports/native-hbonds-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
finally:
 if pid:
  try:__import__('os').kill(pid,signal.SIGTERM)
  except ProcessLookupError:pass
 s.db.close()
