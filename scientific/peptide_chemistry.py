"""Chemical evolution branch using an existing isolated RDKit runtime."""
import copy
import hashlib
import json
import os
import pathlib
import subprocess
import time
import evolution as ev
import research

ACTIONS={'biology_peptide_chemistry_start'}


def dispatch(s,action,p):
    if p.get('approved') is not True:raise ValueError('Approve bounded chemical topology/conformer computation.')
    parent=ev.Evolution(s).candidate(p['projectId'],p['candidateId'])
    if parent['chemistry']['representation']!='canonical_linear_protein':raise ValueError('Start each independent chemical hypothesis from its canonical linear parent.')
    request={'sequence':parent['sequence'],'headToTail':p.get('headToTail',False),'disulfides':p.get('disulfides',[]),'dResidues':p.get('dResidues',[]),'seed':ev.integer(p.get('seed',42),'Seed',0,2147483647),'conformers':ev.integer(p.get('conformers',0),'Conformers',0,3)}
    if not request['headToTail'] and not request['disulfides'] and not request['dResidues']:raise ValueError('Specify at least one supported chemical transformation.')
    python=s.engine_python()
    if not pathlib.Path(python).is_file():raise ValueError('The existing isolated RDKit runtime is missing.')
    s.db.execute('BEGIN IMMEDIATE')
    if s.active():s.db.rollback();raise ValueError('Another scientific job owns local compute.')
    runner=pathlib.Path(__file__).with_name('peptide_chemistry_runner.py')
    job=s.job_new({'projectId':p['projectId'],'name':parent['name']+' · peptide chemistry','parentId':parent['id'],'request':request,'runnerSha256':hashlib.sha256(runner.read_bytes()).hexdigest(),'runtime':python,'outputs':[]},'peptide_chemistry','queued')
    folder=s.root/'jobs'/job['id'];folder.mkdir(exist_ok=True);(folder/'request.json').write_text(ev.canonical(request));return s.spawn(job,'--peptide-chemistry-job')


def run(s,id):
    job=s.job(id);folder=s.root/'jobs'/id;data=job['data']
    if job['engine']!='peptide_chemistry' or job['state']!='queued':raise ValueError('Chemical workflow cannot execute in this state.')
    try:
        runner=pathlib.Path(__file__).with_name('peptide_chemistry_runner.py')
        if hashlib.sha256(runner.read_bytes()).hexdigest()!=data['runnerSha256'] or json.loads((folder/'request.json').read_text())!=data['request']:raise ValueError('Chemical execution inputs changed.')
        s.job_update(id,'running',{'started':research.utc()})
        with (folder/'chemistry.log').open('ab') as log:process=subprocess.run([data['runtime'],'-I','-B',str(runner),str(folder)],stdout=log,stderr=log,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'1'},timeout=180)
        if s.job(id)['state']=='cancelled':return
        if process.returncode:raise ValueError('Real RDKit peptide validation failed; exact diagnostics retained in chemistry.log.')
        result=json.loads((folder/'chemistry.json').read_text());parent=ev.Evolution(s).candidate(job['project_id'],data['parentId'])
        with s.db:
            child=ev.Evolution(s).insert(job['project_id'],parent['name']+' · chemical descendant',parent['sequence'],copy.deepcopy(parent['constraints']),copy.deepcopy(parent['reference']),parent['residueMap'],parent,'rdkit_peptide_chemistry')
            child['chemistry']={'representation':'explicit_isomeric_smiles','isomericSmiles':result['canonicalIsomericSmiles'],'atomResidueMap':result['atoms'],'bonds':result['bonds'],'request':data['request'],'artifact':str((folder/'chemistry.json').relative_to(s.root)),'sha256':hashlib.sha256((folder/'chemistry.json').read_bytes()).hexdigest()};child['validation']='chemical_graph_validated_not_binding_pose';child['backboneReference']=parent.get('structure');child['structure']=None
            s.db.execute('UPDATE evolution_candidates SET data=? WHERE id=?',(ev.canonical(child),child['id']));ev.Evolution(s).event(job['project_id'],child['id'],'chemical_validation',{'jobId':id,'runtime':result['version'],'formula':result['formula'],'limitations':result['limitations']})
        s.job_update(id,'completed',{'candidateId':child['id'],'report':str((folder/'chemistry.json').relative_to(s.root)),'finished':research.utc()})
    except Exception as error:
        if s.job(id)['state']!='cancelled':s.job_update(id,'failed',{'error':str(error),'finished':research.utc()})
