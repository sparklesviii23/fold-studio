#!/usr/bin/env python3
"""Verify a freshly delivered bundle using a NEW disposable copy of a baseline.
Native process startup is deliberately not native GUI acceptance. No inference.
"""
import argparse,hashlib,json,os,pathlib,plistlib,shutil,sqlite3,subprocess,time
p=argparse.ArgumentParser()
p.add_argument('--app',required=True);p.add_argument('--baseline',required=True)
p.add_argument('--root',required=True);p.add_argument('--report',required=True)
p.add_argument('--existing-job',help='Optional already completed job directory; copied, never run')
a=p.parse_args();app=pathlib.Path(a.app).resolve();base=pathlib.Path(a.baseline).resolve();root=pathlib.Path(a.root).resolve()
source=pathlib.Path(__file__).resolve().parents[1];resources=app/'Contents/Resources';exe=app/'Contents/MacOS/fold-studio'
if root.exists():raise SystemExit('Choose a new, disposable --root.')
shutil.copytree(base,root)
if a.existing_job:
    job=pathlib.Path(a.existing_job).resolve();shutil.copytree(job,root/'jobs'/job.name)
checks=[]
def check(name,condition,details=None):
    checks.append({'name':name,'passed':bool(condition),'details':details})
    if not condition:raise AssertionError(name)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(db,table):return [list(r) for r in db.execute('SELECT * FROM '+table+' ORDER BY 1,2')]
env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','FOLD_DATA_DIR':str(root)}
def rpc(action,payload=None):
    result=subprocess.run(['/usr/bin/python3',str(resources/'scientific/worker.py'),'--root',str(root),'--fixtures',str(resources/'fixtures')],input=json.dumps({'action':action,'payload':payload or {}}),text=True,capture_output=True,env=env,timeout=30)
    data=json.loads(result.stdout)
    if result.returncode or 'error' in data:raise RuntimeError(data.get('error',result.stderr))
    return data['result']
def signature():subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True,capture_output=True)
signature();identity=plistlib.loads((app/'Contents/Info.plist').read_bytes())
check('Bundle identity retained',identity['CFBundleIdentifier']=='org.foldstudio.observatory' and identity['CFBundleShortVersionString']=='4.0.0-stellar-arcade.1',{'identifier':identity['CFBundleIdentifier'],'version':identity['CFBundleShortVersionString']})
architecture=subprocess.check_output(['/usr/bin/file',str(exe)],text=True).strip();check('arm64 executable','arm64' in architecture,architecture)
config=json.loads((source/'src-tauri/tauri.conf.json').read_text());resource_hashes={}
for relative,target in config['bundle']['resources'].items():
    original=source/'src-tauri'/relative;bundled=resources/target
    if original.is_file():check('Bundled source: '+target,digest(original)==digest(bundled));resource_hashes[target]=digest(bundled)
for capability in ['default','arcade-lifecycle']:
    caps=json.loads((source/('src-tauri/capabilities/'+capability+'.json')).read_text())
    if capability=='default':check('Drag capability covers main and arcade',{'main','arcade'}.issubset(caps['windows']) and 'core:window:allow-start-dragging' in caps['permissions'])
library=rpc('library');project=library['projects'][0]['id'];job_ids=[j['id'] for j in library['jobs']]
db=sqlite3.connect(root/'library.sqlite3');old_progress=rows(db,'arcade_progress');originals={r['id']:r['data']['sha256'] for r in library['records'] if r['data'].get('asset')};db.close()
components=rpc('amino_acids')['components'];check('20 packaged canonical components',len(components)==20)
migrated=rpc('molecular_draft_load',{'projectId':project});again=rpc('molecular_draft_load',{'projectId':project});check('Idempotent migration',migrated==again)
db=sqlite3.connect(root/'library.sqlite3');check('Original v1 Arcade and Architect progress retained',rows(db,'arcade_progress')==old_progress);db.close()
state=migrated['state']
if not state or not rpc('molecular_graph_validate',{'state':state})['valid']:
    # Explicit synthetic canonical QA graph from a copied template, not an inference result.
    c=next(c for c in components if c['one']=='G');state={'schemaVersion':2,'residues':[{'id':'qa','one':'G','position':[180,220],'rotation':0}],'atoms':[{'id':'qa:'+v['id'],'residueId':'qa','templateAtom':v['id'],'element':v['element'],'charge':v['charge'],'stereo':v['stereo'],'xyz':v['xyz'],'board':[180+i*10,220]} for i,v in enumerate(c['atoms'])],'bonds':[{**b,'a':'qa:'+b['a'],'b':'qa:'+b['b'],'kind':'component'} for b in c['bonds']],'mode':'free','challengeId':'free','completed':[],'name':'Packaged graph QA','notes':'Disposable verification','assisted':False}
check('Actual packaged graph validation',rpc('molecular_graph_validate',{'state':state})['valid'])
draft=rpc('molecular_draft_save',{'state':state,'revision':0});check('Durable local practice round trip',rpc('molecular_draft_load')['state']==state)
record=rpc('peptide_save',{'projectId':project,'sequence':''.join(r['one'] for r in state['residues']),'name':'Packaged graph QA','state':state});check('Exact graph promoted',record['data']['graph']==state)
transfer=rpc('peptide_transfer',{'id':record['id'],'revision':record['data']['revision']});check('Revision and graph provenance transfer',transfer['sequence']==record['data']['sequence'] and bool(transfer.get('graphSha256') or transfer.get('origin',{}).get('graphSha256')))
structure=rpc('peptide_structure',{'id':record['id'],'revision':record['data']['revision']})
check('Separate idealized copy retains exact graph provenance',structure['data']['metadata']['graphSha256']==record['data']['graphSha256'] and structure['data']['metadata']['geometryStatus']=='idealized_unrelaxed')
path=root/'checked-draft.json';path.write_text(json.dumps(state));check('Checked external draft import',rpc('molecular_draft_import',{'path':str(path)})['state']==state)
confidence=[]
if a.existing_job:
    for r in library['records']:
        if r['data'].get('metadata',{}).get('jobId')==pathlib.Path(a.existing_job).name:
            for kind in ['pae','pde']:
                result=rpc('confidence_fetch',{'structureId':r['id'],'kind':kind});confidence.append({'kind':kind,'tokens':len(result['matrix'])});check('Existing 460-token '+kind+' reads',len(result['matrix'])==460)
before=digest(exe);proc=subprocess.Popen([str(exe)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:
    time.sleep(5);check('Own packaged process alive after five seconds',proc.poll() is None)
finally:
    proc.terminate()
    try:proc.communicate(timeout=10)
    except subprocess.TimeoutExpired:proc.kill();proc.communicate()
signature();check('Executable unchanged after startup',digest(exe)==before)
after=rpc('library');check('No jobs created or started',[j['id'] for j in after['jobs']]==job_ids)
check('Original coordinate assets unchanged',all(digest(root/'assets'/r['data']['asset'])==originals[r['id']] for r in library['records'] if r['id'] in originals))
report={'date':time.strftime('%Y-%m-%d'),'app':str(app),'root':str(root),'checks':checks,'passed':all(c['passed'] for c in checks),'executableSha256':digest(exe),'resources':resource_hashes,'existingConfidence':confidence,'nativeGUIAcceptance':'unverified','signature':'strict deep ad-hoc verification passed before and after startup','engineInstallOrInferencePerformed':False}
pathlib.Path(a.report).write_text(json.dumps(report,indent=2));print(json.dumps({'checks':len(checks),'passed':report['passed'],'report':a.report}))
