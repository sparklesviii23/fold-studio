"""RAPID v2 deployment and scientific jobs over the existing strict SSH transport."""
import base64,hashlib,json,pathlib,re,shlex,uuid
from cloud_compute import now

ACTIONS={'gpu_rapid_install','gpu_rapid_status','gpu_rapid_call','gpu_rapid_submit','gpu_rapid_import','gpu_rapid_target','gpu_rapid_export'}
OPERATIONS={'health','engine_inventory','model_status','engine_install','model_install','installation_status','campaign_validate','job_submit','job_list','job_status','job_events','job_cancel','job_recover','candidate_list','artifact_list','artifact_read','worker_shutdown','unified_validate','unified_submit','unified_status','unified_list','unified_cancel','unified_stage'}

def artifact():
    base=pathlib.Path(__file__).resolve().parent
    options=[base/'rapid-release.tar.gz',base.parent/'remote_worker/dist/fold-rapid-0.2.0.tar.gz']
    path=next((p for p in options if p.is_file()),None)
    if path is None:raise ValueError('Build the source-only RAPID release before packaging this app.')
    data=path.read_bytes()
    if len(data)>8*1024**2:raise ValueError('RAPID source bundle exceeds the reviewed bootstrap limit.')
    return data,hashlib.sha256(data).hexdigest()

INSTALL="""import base64,hashlib,json,os,pathlib,platform,subprocess,sys,tarfile,io
v=json.load(sys.stdin)
if platform.system()!='Linux' or platform.machine() not in ('x86_64','amd64'):raise ValueError('RAPID scientific installation requires Linux AMD64. Use the versioned worker image.')
b=base64.b64decode(v['code'],validate=True)
assert len(b)<=8*1024**2 and hashlib.sha256(b).hexdigest()==v['sha256']
root=pathlib.Path.home()/'.local/share/fold-studio-rapid';folder=root/'releases'/v['sha256'];folder.mkdir(parents=True,exist_ok=True,mode=0o700)
with tarfile.open(fileobj=io.BytesIO(b),mode='r:gz') as tar:
 members=tar.getmembers()
 assert sum(m.size for m in members)<100*1024**2
 assert all(not m.issym() and not m.islnk() and not m.isdev() and m.name.startswith('release/') and folder.resolve() in (folder/m.name).resolve().parents for m in members if m.name!='release')
 if sys.version_info>=(3,12):tar.extractall(folder,filter='data')
 else:tar.extractall(folder) # all paths and member types checked above; no links/devices
release=folder/'release';index=json.loads((release/'release.json').read_text())
assert all(hashlib.sha256((release/name).read_bytes()).hexdigest()==sha for name,sha in index['files'].items())
script=folder/'activate.py';script.write_text(v['activation'])
with (folder/'installation.log').open('ab') as log:
 child=subprocess.Popen([sys.executable,str(script),str(folder)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,env={**os.environ,'RAPID_MANAGED_PYTHON':'1' if v.get('managedPython') else ''})
print(json.dumps({'state':'installing','releaseSha256':v['sha256'],'releaseFolder':str(folder),'pid':child.pid,'version':'0.2.0','modelDownloads':False}))
"""

ACTIVATE="""import hashlib,io,json,os,pathlib,subprocess,sys,urllib.request,zipfile
folder=pathlib.Path(sys.argv[1]);release=folder/'release';env=folder/'venv';state=folder/'state.json'
try:
 managed=os.environ.pop('RAPID_MANAGED_PYTHON','')=='1'
 if sys.version_info<(3,12) or managed:
  url='https://files.pythonhosted.org/packages/0d/8d/e45565a046bd2592b75cb96fded9a7ab0cd6d470152fec713c82ee83ddbb/uv-0.12.17-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl'
  with urllib.request.urlopen(url,timeout=60) as response:wheel=response.read(32*1024**2)
  assert hashlib.sha256(wheel).hexdigest()=='9e25bb39e1674799c408345a6397ebc2c7c719d498be0ce9d935466d36ceacf5'
  with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
   files=[item for item in archive.infolist() if item.filename.endswith('/uv') and item.file_size<100*1024**2]
   assert len(files)==1
   executable=folder/'uv';executable.write_bytes(archive.read(files[0]));executable.chmod(0o700)
  subprocess.run([str(executable),'python','install','3.12.14','--install-dir',str(folder/'python'),'--no-bin','--no-progress'],check=True)
  interpreters=list((folder/'python').glob('cpython-3.12.14-*/bin/python3.12'));assert len(interpreters)==1
  os.execv(str(interpreters[0]),[str(interpreters[0]),str(pathlib.Path(__file__)),str(folder)])
 if not (env/'bin/python').is_file():subprocess.run([sys.executable,'-m','venv',str(env)],check=True)
 python=str(env/'bin/python')
 subprocess.run([python,'-m','pip','install','--require-hashes','-r',str(release/'worker/environments/core.lock')],check=True)
 subprocess.run([python,'-m','pip','install','--no-deps','--no-build-isolation',str(release/'worker')],check=True)
 active=folder.parents[1]/'active.json'
 previous=json.loads(active.read_text()) if active.is_file() else {}
 root=pathlib.Path(previous.get('root') or os.environ.get('RAPID_ROOT') or folder.parents[1]/'data');root.mkdir(parents=True,exist_ok=True)
 value={'state':'installed','version':'0.2.0','python':python,'release':str(release),'root':str(root),'cudaQualified':False,'modelDownloads':False}
 state.write_text(json.dumps(value))
 pending=active.with_suffix('.pending.json');pending.write_text(json.dumps(value));os.replace(pending,active)
except Exception as error:state.write_text(json.dumps({'state':'failed','error':str(error)}));raise
"""

class RapidRemote:
    def __init__(self,cloud,service):self.cloud=cloud;self.service=service
    def gpu_rapid_install(self,p):
        if p.get('approved') is not True:raise ValueError('Approve the RAPID source transfer and small core dependency installation first. Scientific model downloads are separate.')
        entry=self.cloud.profile(p.get('id'));data,digest=artifact()
        result=self.cloud.ssh(entry,'python3 -I -B -c '+shlex.quote(INSTALL),{'code':base64.b64encode(data).decode(),'sha256':digest,'activation':ACTIVATE,'managedPython':p.get('preferManagedPython') is True},timeout=90)
        self.cloud.update(entry['id'],{'rapid':result});return result
    def gpu_rapid_status(self,p):
        entry=self.cloud.profile(p.get('id'))
        code="import json,pathlib;root=pathlib.Path.home()/'.local/share/fold-studio-rapid';p=root/'active.json';print(p.read_text() if p.is_file() else json.dumps({'state':'prebuilt_image' if pathlib.Path('/opt/fold-rapid/bin/python').is_file() else 'not_installed','version':'0.2.0' if pathlib.Path('/opt/fold-rapid/bin/python').is_file() else None}))"
        value=self.cloud.ssh(entry,'python3 -I -B -c '+shlex.quote(code),{})
        current=entry.get('rapid',{})
        if current.get('state')=='installing':
            sha=current.get('releaseSha256','')
            if len(sha)!=64 or any(c not in 'abcdef0123456789' for c in sha):raise ValueError('Invalid installed release identity.')
            code="import json,pathlib;p=pathlib.Path.home()/'.local/share/fold-studio-rapid/releases'/"+repr(sha)+"/'state.json';print(p.read_text() if p.is_file() else json.dumps({'state':'installing'}))"
            value=self.cloud.ssh(entry,'python3 -I -B -c '+shlex.quote(code),{})
        self.cloud.update(entry['id'],{'rapid':{**current,**value,'checkedUtc':now()}})
        return value
    def call(self,entry,operation,payload):
        if operation not in OPERATIONS:raise ValueError('Unsupported scientific worker operation.')
        request={'apiVersion':2,'requestId':uuid.uuid4().hex,'operation':operation,'payload':payload}
        runner="import json,os,pathlib,subprocess,sys;p=pathlib.Path.home()/'.local/share/fold-studio-rapid/active.json';v=json.loads(p.read_text()) if p.is_file() else {'python':'/opt/fold-rapid/bin/python','release':'/opt/fold-rapid-release','root':os.environ.get('RAPID_ROOT','/data/rapid')};r=subprocess.run([v['python'],'-m','fold_rapid.cli','--root',v['root'],'rpc'],input=sys.stdin.read(),text=True,capture_output=True,env={**os.environ,'RAPID_RELEASE_DIR':v['release']});print(r.stdout if r.returncode==0 else json.dumps({'error':'Installed RAPID process failed; inspect its installation log.'}))"
        value=self.cloud.ssh(entry,'python3 -I -B -c '+shlex.quote(runner),request,timeout=45)
        if value.get('error'):raise ValueError(value['error'])
        if value.get('apiVersion')!=2 or value.get('requestId')!=request['requestId']:raise ValueError('RAPID response version or request identity mismatch.')
        return value['result']
    def gpu_rapid_call(self,p):
        operation=p.get('operation');payload=p.get('payload',{})
        if operation in ('job_submit','unified_submit'):raise ValueError('Submit a selected library snapshot through the dedicated scientific transfer action.')
        return self.call(self.cloud.profile(p.get('id')),operation,payload)
    def gpu_rapid_target(self,p):
        record=next((r for r in self.service.library({})['records'] if r['id']==p['targetId'] and r['kind']=='structure'),None)
        if record is None:raise ValueError('Target is not in the local structure library.')
        data=record['data'];name=data['asset']
        if pathlib.Path(name).name!=name:raise ValueError('Invalid coordinate snapshot.')
        path=self.service.root/'assets'/name;raw=path.read_bytes()
        if len(raw)>2_000_000 or hashlib.sha256(raw).hexdigest()!=data['sha256']:raise ValueError('Target snapshot checksum or size is invalid.')
        import intelligence
        mapping=intelligence.parse_structure(raw.decode(),'pdb' if data['format']=='pdb' else 'mmcif')
        return {'sha256':data['sha256'],'chains':[{'id':c['id'],'sequence':c['sequence'],'residues':c['proteinResidues']} for c in mapping['chains'] if c['proteinResidues']],'models':mapping['models'],'researchTransferred':False}
    def gpu_rapid_submit(self,p):
        if p.get('approvedResearchTransfer') is not True:raise ValueError('Approve transferring the selected molecular target to this server.')
        record=next((r for r in self.service.library({})['records'] if r['id']==p['targetId'] and r['kind']=='structure'),None)
        if record is None:raise ValueError('Selected target structure is no longer in the library.')
        data=record['data'] if isinstance(record['data'],dict) else json.loads(record['data'])
        path=self.service.root/'assets'/data['asset']
        if path.name!=data['asset'] or path.is_symlink():raise ValueError('Invalid library coordinate snapshot.')
        raw=path.read_bytes()
        if len(raw)>2_000_000 or hashlib.sha256(raw).hexdigest()!=data['sha256']:raise ValueError('Selected library snapshot is too large or its checksum changed.')
        manifest={**p['manifest'],'target':{'format':'pdb' if data['format']=='pdb' else 'cif','contentBase64':base64.b64encode(raw).decode(),'sha256':data['sha256'],'chains':p['chains'],'label':record['name']}}
        return self.call(self.cloud.profile(p.get('id')),'unified_submit' if manifest.get('kind')=='unified' else 'job_submit',{'manifest':manifest,'idempotencyKey':p['idempotencyKey'],'approvedResearchTransfer':True,**({'approvedWorkload':p.get('approvedWorkload') is True} if manifest.get('kind')=='unified' else {})})
    def gpu_rapid_import(self,p):
        entry=self.cloud.profile(p.get('id'));jobid=p['jobId']
        if not isinstance(jobid,str) or len(jobid)!=32 or any(c not in 'abcdef0123456789' for c in jobid):raise ValueError('Invalid remote job identity.')
        self.service.project(p['projectId'])
        result=self.call(entry,'candidate_list',{'jobId':jobid})
        while result.get('nextOffset') is not None:
            page=self.call(entry,'candidate_list',{'jobId':jobid,'offset':result['nextOffset']})
            if page.get('nextOffset') is not None and page['nextOffset']<=result['nextOffset']:raise ValueError('Remote candidate cursor did not advance.')
            result['candidates'].extend(page['candidates']);result['nextOffset']=page.get('nextOffset')
        artifacts=self.call(entry,'artifact_list',{'jobId':jobid})['artifacts'];index={a['path']:a for a in artifacts}
        root=self.service.root/'remote-results'/entry['id']/jobid;root.mkdir(parents=True,exist_ok=True);imported=[]
        for candidate in result['candidates']:
            cid=candidate.get('candidateId')
            if not isinstance(cid,str) or len(cid)!=64 or any(c not in '0123456789abcdef' for c in cid):raise ValueError('Invalid remote immutable candidate identity.')
            coordinates=candidate.get('coordinates')
            if not coordinates:
                name=candidate.get('metrics',{}).get('fastaArtifact')
                if candidate.get('generator') not in ('proteinmpnn','solublempnn') or not name:continue
                raw=self.receive_artifact(entry,jobid,name,index,limit=1024**2)
                from worker import parse_fasta,digest
                sequences=parse_fasta(raw.decode('utf-8'))
                if '/'.join(s['sequence'] for s in sequences)!=candidate.get('binderSequence'):raise ValueError('Remote FASTA differs from the immutable candidate sequence.')
                seen=set()
                for sequence in sequences:
                    match=re.search(r'(?:^|\|)chain=([A-Za-z0-9_]{1,8})(?:\||$)',sequence['name'])
                    if not match or match[1] in seen:raise ValueError('Remote FASTA chain correspondence is missing or ambiguous.')
                    chain=match[1];seen.add(chain)
                    metadata={'remoteCandidateId':cid,'remoteChainId':chain,'remoteJobId':jobid,'rapidCandidate':candidate,'experimentalValidation':False}
                    existing=[r for r in self.service.library({})['records'] if r['project_id']==p['projectId'] and r['data'].get('metadata',{}).get('remoteCandidateId')==cid and r['data'].get('metadata',{}).get('remoteChainId')==chain]
                    record=existing[0] if existing else self.service.record_save({'projectId':p['projectId'],'kind':'sequence','name':candidate['generator']+' · '+str(candidate.get('upstreamId') or cid[:10])+' · chain '+chain,'data':{'sequence':sequence['sequence'],'sha256':digest(sequence['sequence']),'metadata':metadata,'origin':{'engine':'RAPID '+candidate['generator'],'fixedBackbone':True,'structurePredicted':False},'created':now()}})
                    imported.append(record)
                continue
            name=coordinates['artifact'];item=index.get(name)
            if item is None or item['sha256']!=coordinates['sha256'] or item['bytes']>100*1024**2:raise ValueError('Remote candidate artifact manifest mismatch.')
            raw=self.receive_artifact(entry,jobid,name,index)
            path=root/(candidate['candidateId']+'.cif');path.write_bytes(raw)
            existing=[r for r in self.service.library({})['records'] if r['project_id']==p['projectId'] and r['data'].get('metadata',{}).get('remoteCandidateId')==candidate['candidateId']]
            record=existing[0] if existing else self.service.import_structure({'projectId':p['projectId'],'path':str(path),'name':candidate['generator']+' · '+str(candidate.get('upstreamId') or candidate['candidateId'][:10]),'source':'RAPID remote computational result · '+candidate['outcome'],'metadata':{'remoteCandidateId':candidate['candidateId'],'remoteJobId':jobid,'rapidCandidate':candidate,'experimentalValidation':False}})
            imported.append(record)
        (root/'candidates.json').write_text(json.dumps(result,indent=2))
        return {'records':imported,'jobId':jobid,'acceptanceUnchanged':True}
    def receive_artifact(self,entry,jobid,name,index,limit=100*1024**2):
        item=index.get(name)
        if item is None or type(item.get('bytes')) is not int or not 0<item['bytes']<=limit:raise ValueError('Remote artifact size or manifest is invalid.')
        blocks=[];offset=0
        while offset<item['bytes']:
            chunk=self.call(entry,'artifact_read',{'jobId':jobid,'path':name,'offset':offset,'length':min(786432,item['bytes']-offset)})
            raw=base64.b64decode(chunk['contentBase64'],validate=True)
            if not raw or len(raw)>item['bytes']-offset or chunk['offset']!=offset or hashlib.sha256(raw).hexdigest()!=chunk['chunkSha256']:raise ValueError('Remote artifact transfer integrity failure.')
            blocks.append(raw);offset+=len(raw)
        raw=b''.join(blocks)
        if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('Remote artifact checksum mismatch.')
        return raw
    def gpu_rapid_export(self,p):
        import os
        entry=self.cloud.profile(p.get('id'));job=p['jobId'];path=pathlib.Path(p['path'])
        if path.suffix.lower()!='.zip' or path.is_symlink():raise ValueError('Choose a .zip destination for the full scientific package.')
        items=self.call(entry,'artifact_list',{'jobId':job})['artifacts'];item=next((a for a in items if a['path']=='results.zip'),None)
        if not item or type(item['bytes']) is not int or not 0<item['bytes']<=1024**3:raise ValueError('A finished result package below 1 GiB is required.')
        pending=path.with_name(path.name+'.'+uuid.uuid4().hex+'.partial');h=hashlib.sha256();offset=0
        try:
            with pending.open('xb') as output:
                while offset<item['bytes']:
                    value=self.call(entry,'artifact_read',{'jobId':job,'path':'results.zip','offset':offset,'length':786432});raw=base64.b64decode(value['contentBase64'],validate=True)
                    if not raw or value['offset']!=offset or hashlib.sha256(raw).hexdigest()!=value['chunkSha256']:raise ValueError('Scientific package transfer checksum failed.')
                    output.write(raw);h.update(raw);offset+=len(raw)
                if offset!=item['bytes'] or h.hexdigest()!=item['sha256']:raise ValueError('Final scientific package checksum differs.')
                output.flush();os.fsync(output.fileno())
            os.replace(pending,path)
        finally:pending.unlink(missing_ok=True)
        return {'path':str(path),'bytes':offset,'sha256':h.hexdigest(),'researchInputsAndOriginalOutputsPreserved':True}

def dispatch(service,action,payload):
    from cloud_compute import CloudCompute
    if action not in ACTIONS:raise ValueError('Unsupported scientific remote action.')
    return getattr(RapidRemote(CloudCompute(service),service),action)(payload)
