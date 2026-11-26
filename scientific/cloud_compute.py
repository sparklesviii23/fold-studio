"""Private connection profiles and strict OpenSSH transport for RAPID workers.

Profiles/known hosts never enter the shared settings or scientific project ZIP.
There is no provider billing operation or model installation in this foundation.
"""
import base64, contextlib, datetime, fcntl, hashlib, ipaddress, json, os
import pathlib, re, shlex, stat, subprocess, sys, uuid
import selectors, time
ACTIONS={'gpu_profiles','gpu_profile_save','gpu_profile_archive','gpu_parse_connection','gpu_host_scan','gpu_host_trust','gpu_connection_test','gpu_worker_prepare','gpu_worker_health','gpu_worker_selftest'}
SSH='/usr/bin/ssh'; KEYSCAN='/usr/bin/ssh-keyscan'; KEYGEN='/usr/bin/ssh-keygen'
REMOTE_BASE='.local/share/fold-rapid/worker'
KEY_TYPES={'ssh-ed25519','ecdsa-sha2-nistp256','ecdsa-sha2-nistp384','ecdsa-sha2-nistp521','ssh-rsa'}

def bounded_transport(argv, *, input, timeout):
    """Bound both SSH response streams while draining stdin without deadlocks."""
    process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    pending=memoryview(input.encode());buffers={'stdout':bytearray(),'stderr':bytearray()}
    deadline=time.monotonic()+timeout
    try:
        with selectors.DefaultSelector() as selected:
            for stream,name,event in [(process.stdin,'stdin',selectors.EVENT_WRITE),(process.stdout,'stdout',selectors.EVENT_READ),(process.stderr,'stderr',selectors.EVENT_READ)]:
                os.set_blocking(stream.fileno(),False);selected.register(stream,event,name)
            while selected.get_map():
                remaining=deadline-time.monotonic()
                if remaining<=0:raise subprocess.TimeoutExpired(argv,timeout)
                for item,_ in selected.select(min(1,remaining)):
                    stream,name=item.fileobj,item.data
                    if name=='stdin':
                        try:pending=pending[os.write(stream.fileno(),pending[:8192]):]
                        except BrokenPipeError:pending=memoryview(b'')
                        if not pending:selected.unregister(stream);stream.close()
                    else:
                        block=os.read(stream.fileno(),65536)
                        if not block:selected.unregister(stream);stream.close();continue
                        buffers[name].extend(block)
                        if len(buffers[name])>(2*1024**2 if name=='stdout' else 65536):raise ValueError('Remote response exceeded the safe size limit.')
        returncode=process.wait(timeout=max(.01,deadline-time.monotonic()))
        return subprocess.CompletedProcess(argv,returncode,*(buffers[name].decode('utf-8',errors='replace') for name in ('stdout','stderr')))
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)
        for stream in (process.stdin,process.stdout,process.stderr):
            if not stream.closed:stream.close()

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def text(value,label,maximum=120):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum or any(ord(c)<32 for c in value): raise ValueError('Invalid '+label+'.')
    return value.strip()
def host(value):
    value=text(value,'server address',253).strip('[]')
    try: return str(ipaddress.ip_address(value))
    except ValueError:
        if not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?',p) for p in value.split('.')): raise ValueError('Enter a valid server hostname or IP address.')
        return value.lower()
def port(value):
    if type(value) is not int or not 1<=value<=65535: raise ValueError('Port must be a whole number from 1 to 65535.')
    return value

def parse_connection(value):
    words=shlex.split(text(value,'SSH connection',2000))
    if not words or pathlib.PurePosixPath(words.pop(0)).name!='ssh': raise ValueError('Paste the SSH connection shown by your provider.')
    result={'port':22,'username':'root','keyPath':''}; destination=None
    while words:
        word=words.pop(0)
        if word in ('-p','-i'):
            if not words: raise ValueError('Incomplete SSH connection option.')
            argument=words.pop(0)
            if word=='-p':
                if not argument.isdecimal():raise ValueError('Invalid SSH port.')
                result['port']=port(int(argument))
            else:result['keyPath']=argument
        elif word.startswith('-p') and word[2:].isdecimal():result['port']=port(int(word[2:]))
        elif word=='-L':
            if not words:raise ValueError('Incomplete forwarding option.')
            words.pop(0);result['ignoredForwarding']=True
        elif word.startswith('-') or destination is not None:raise ValueError('Only host, user, port and key-file options are accepted; remote commands are refused.')
        else:destination=word
    if not destination:raise ValueError('SSH server address is missing.')
    if '@' in destination:result['username'],destination=destination.rsplit('@',1)
    result['host']=host(destination)
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]{0,31}',result['username']):raise ValueError('Invalid SSH username.')
    return result

def worker_source():
    # Tauri bundles the same reviewed worker beside these Python modules.
    source=pathlib.Path(__file__).resolve().parent/'rapid_worker.py'
    if not source.is_file():source=pathlib.Path(__file__).resolve().parents[1]/'remote_worker/rapid_worker.py'
    data=source.read_bytes()
    if len(data)>262144:raise ValueError('Worker package exceeds the approved small bootstrap size.')
    return data,hashlib.sha256(data).hexdigest()

def private_key(path):
    if path=='':return ''
    path=pathlib.Path(text(path,'private-key path',4096)).expanduser().absolute()
    info=path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077:raise ValueError('Choose a private key owned by you with access restricted to your account.')
    return str(path)

class CloudCompute:
    def __init__(self,service):
        self.root=service.root/'private-compute'
        if self.root.is_symlink():raise ValueError('Private connection storage must not be a symbolic link.')
        self.root.mkdir(mode=0o700,exist_ok=True);os.chmod(self.root,0o700)
        self.path=self.root/'profiles.json'
    @contextlib.contextmanager
    def store(self):
        lock=self.root/'profiles.lock'
        if lock.is_symlink() or self.path.is_symlink():raise ValueError('Unsafe private connection storage.')
        with lock.open('a+') as stream:
            os.chmod(lock,0o600);fcntl.flock(stream,fcntl.LOCK_EX)
            data=json.loads(self.path.read_text()) if self.path.exists() else {'schemaVersion':1,'profiles':[]}
            if data.get('schemaVersion')!=1:raise ValueError('Unsupported connection profile version.')
            before=json.dumps(data,sort_keys=True)
            yield data
            if json.dumps(data,sort_keys=True)!=before:
                pending=self.path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
                try:
                    with pending.open('x') as output:
                        os.chmod(pending,0o600);json.dump(data,output,allow_nan=False,indent=2);output.flush();os.fsync(output.fileno())
                    os.replace(pending,self.path)
                finally:pending.unlink(missing_ok=True)
    def profile(self,id):
        if not isinstance(id,str) or not re.fullmatch('[a-f0-9]{32}',id):raise ValueError('Invalid connection profile.')
        with self.store() as data:
            entry=next((p.copy() for p in data['profiles'] if p['id']==id and not p.get('archived')),None)
        if entry is None:raise ValueError('Saved connection was not found.')
        return entry
    def update(self,id,values):
        with self.store() as data:
            entry=next(p for p in data['profiles'] if p['id']==id);entry.update(values,updated=now())
    def gpu_profiles(self,p):
        with self.store() as data:profiles=[{k:v for k,v in entry.items() if k not in ('pendingHostKey','trustedHostKey')} for entry in data['profiles'] if not entry.get('archived')]
        code,digest=worker_source()
        return {'profiles':profiles,'worker':{'apiVersion':1,'version':'0.1.0','sha256':digest,'downloadBytes':len(code)},'cloudCampaignExecutionAvailable':False,'scope':'Connection and worker foundation. No rented instance, remote scientific engine or CUDA reference execution has been verified.'}
    def gpu_parse_connection(self,p):return parse_connection(p.get('connection'))
    def gpu_profile_save(self,p):
        user=text(p.get('username','root'),'SSH username',32)
        if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]{0,31}',user):raise ValueError('Invalid SSH username.')
        provider=p.get('provider')
        if provider not in ('vast','custom'):raise ValueError('Choose Vast.ai or a custom NVIDIA server.')
        values={'name':text(p.get('name'),'connection name',80),'provider':provider,'host':host(p.get('host')),'port':port(p.get('port',22)),'username':user,'keyPath':private_key(p.get('keyPath','')),'updated':now()}
        id=p.get('id') or uuid.uuid4().hex
        with self.store() as data:
            old=next((entry for entry in data['profiles'] if entry['id']==id and not entry.get('archived')),None)
            if p.get('id') and old is None:raise ValueError('Connection profile not found.')
            if old:
                if (old['host'],old['port'],old['username'],old['keyPath'])!=(values['host'],values['port'],values['username'],values['keyPath']):
                    for field in ('connection','worker','lastWorkerReading','health','rapid'):old.pop(field,None)
                if (old['host'],old['port'])!=(values['host'],values['port']):
                    for field in ('trustedHostKey','fingerprint','pendingHostKey','worker','connection'):old.pop(field,None)
                    (self.root/(id+'.known_hosts')).unlink(missing_ok=True)
                old.update(values)
            else:data['profiles'].append({'id':id,'created':now(),**values})
        return {'id':id,'state':'saved'}
    def gpu_profile_archive(self,p):
        entry=self.profile(p.get('id'));self.update(entry['id'],{'archived':now()});return {'state':'archived','billingChanged':False}
    def gpu_host_scan(self,p):
        entry=self.profile(p.get('id'))
        result=subprocess.run([KEYSCAN,'-T','5','-p',str(entry['port']),'-t','ed25519,ecdsa,rsa',entry['host']],capture_output=True,text=True,timeout=20)
        keys=[]
        for line in result.stdout[:65536].splitlines():
            parts=line.split()
            if len(parts)!=3 or parts[1] not in KEY_TYPES:continue
            try:raw=base64.b64decode(parts[2],validate=True)
            except ValueError:continue
            if not 32<=len(raw)<=16384:continue
            checked=subprocess.run([KEYGEN,'-lf','-','-E','sha256'],input=line+'\n',capture_output=True,text=True,timeout=3)
            if checked.returncode:continue
            fingerprint='SHA256:'+base64.b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
            keys.append({'type':parts[1],'key':parts[2],'fingerprint':fingerprint})
        if not keys:raise ValueError('No SSH identity was received. Check the address, port and instance status.')
        trusted=entry.get('trustedHostKey')
        if trusted:
            matches=any(k['key']==trusted['key'] and k['type']==trusted['type'] for k in keys)
            if not matches:return {'state':'host_key_mismatch','fingerprint':trusted['fingerprint'],'reason':'The server identity changed. Connection is blocked; verify this change independently.'}
            return {'state':'trusted','fingerprint':trusted['fingerprint']}
        chosen=next((k for k in keys if k['type']=='ssh-ed25519'),keys[0]);challenge=uuid.uuid4().hex
        self.update(entry['id'],{'pendingHostKey':{**chosen,'challenge':challenge}})
        return {'state':'identity_review','fingerprint':chosen['fingerprint'],'keyType':chosen['type'],'challenge':challenge,'reason':'Compare this fingerprint with an independent trusted source before accepting.'}
    def gpu_host_trust(self,p):
        entry=self.profile(p.get('id'));pending=entry.get('pendingHostKey')
        if entry.get('trustedHostKey'):raise ValueError('Replacing an existing trusted identity is not enabled; a mismatch remains blocked.')
        if not pending or p.get('challenge')!=pending['challenge'] or p.get('fingerprint')!=pending['fingerprint'] or p.get('confirmed') is not True:raise ValueError('Review and explicitly confirm the current server fingerprint.')
        target=entry['host'] if entry['port']==22 else '['+entry['host']+']:'+str(entry['port'])
        known=self.root/(entry['id']+'.known_hosts')
        if known.is_symlink():raise ValueError('Unsafe known-hosts file.')
        with known.open('w') as f:os.chmod(known,0o600);f.write(target+' '+pending['type']+' '+pending['key']+'\n')
        self.update(entry['id'],{'trustedHostKey':{k:v for k,v in pending.items() if k!='challenge'},'pendingHostKey':None,'fingerprint':pending['fingerprint']})
        return {'state':'trusted','fingerprint':pending['fingerprint']}
    def ssh(self,entry,command,payload,timeout=35):
        trusted=entry.get('trustedHostKey');known=self.root/(entry['id']+'.known_hosts')
        if not trusted or not known.is_file() or known.is_symlink():raise ValueError('Confirm the server identity before connecting.')
        key=private_key(entry['keyPath'])
        algorithms='rsa-sha2-512,rsa-sha2-256' if trusted['type']=='ssh-rsa' else trusted['type']
        argv=[SSH,'-F','/dev/null','-T','-p',str(entry['port']),'-o','BatchMode=yes','-o','ConnectTimeout=8','-o','ConnectionAttempts=1','-o','StrictHostKeyChecking=yes','-o','GlobalKnownHostsFile=/dev/null','-o','UserKnownHostsFile="'+str(known).replace('\\','\\\\').replace('"','\\"')+'"','-o','HostKeyAlgorithms='+algorithms,'-o','ClearAllForwardings=yes','-o','ForwardAgent=no','-o','PermitLocalCommand=no','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2']
        if sys.platform=='darwin':argv+=['-o','UseKeychain=yes']
        if key:argv+=['-o','IdentitiesOnly=yes','-i',key]
        argv+=['--',entry['username']+'@'+entry['host'],command]
        try:result=bounded_transport(argv,input=json.dumps(payload),timeout=timeout)
        except subprocess.TimeoutExpired:raise ValueError('The server did not respond in time. No scientific campaign was submitted.') from None
        if result.returncode:
            message='SSH connection failed. Check the instance and your selected key or unlocked SSH agent.'
            if 'HOST IDENTIFICATION HAS CHANGED' in result.stderr or 'Host key verification failed' in result.stderr:message='Server identity verification failed. Connection is blocked.'
            raise ValueError(message)
        try:
            if len(result.stdout)>2*1024**2:raise ValueError('Oversized worker response.')
            value=json.loads(result.stdout)
            if not isinstance(value,dict):raise ValueError("The server returned an invalid worker response.")
            return value
        except json.JSONDecodeError:raise ValueError('The server returned an invalid worker response.') from None
    def gpu_connection_test(self,p):
        entry=self.profile(p.get('id'))
        code="import json,platform,shutil,sys;print(json.dumps({'state':'connected','platform':platform.system(),'architecture':platform.machine(),'python':platform.python_version(),'pythonExecutable':sys.executable,'diskFreeBytes':shutil.disk_usage('.').free}))"
        value=self.ssh(entry,'python3 -I -B -c '+shlex.quote(code),{})
        if value.get('state')!='connected':raise ValueError('Remote connection test was not completed.')
        self.update(entry['id'],{'connection':{**value,'checkedUtc':now()}});return value
    def gpu_worker_prepare(self,p):
        if p.get('approved') is not True:raise ValueError('Approve the small worker-code transfer before preparing the environment.')
        entry=self.profile(p.get('id'));code,digest=worker_source()
        installer="""import base64,hashlib,json,os,pathlib,sys
v=json.load(sys.stdin);b=base64.b64decode(v['code'],validate=True)
assert len(b)<=262144 and hashlib.sha256(b).hexdigest()==v['sha256']
p=pathlib.Path.home()/'.local/share/fold-rapid/worker'/v['sha256'];p.mkdir(parents=True,exist_ok=True,mode=0o700)
f=p/'rapid_worker.py'
if f.exists():assert not f.is_symlink() and hashlib.sha256(f.read_bytes()).hexdigest()==v['sha256']
else:
 with f.open('x') as s:os.chmod(f,0o600);s.write(b.decode());s.flush();os.fsync(s.fileno())
print(json.dumps({'state':'installed','sha256':v['sha256'],'bytes':len(b)}))
"""
        value=self.ssh(entry,'python3 -I -B -c '+shlex.quote(installer),{'code':base64.b64encode(code).decode(),'sha256':digest})
        if value.get('state')!='installed' or value.get('sha256')!=digest:raise ValueError('Remote worker installation integrity check failed.')
        self.update(entry['id'],{'worker':{**value,'checkedUtc':now()}})
        return self.worker_call(entry,'health')
    def worker_call(self,entry,operation):
        _,digest=worker_source();request={'apiVersion':1,'requestId':uuid.uuid4().hex,'operation':operation,'payload':{}}
        runner="import hashlib,pathlib,runpy;p=pathlib.Path.home()/"+repr(REMOTE_BASE)+"/"+repr(digest)+"/'rapid_worker.py';assert hashlib.sha256(p.read_bytes()).hexdigest()=="+repr(digest)+";runpy.run_path(str(p),run_name='__main__')"
        response=self.ssh(entry,'python3 -I -B -c '+shlex.quote(runner),request,timeout=210 if operation=='gpu_selftest' else 35)
        if response.get('error'):raise ValueError(response['error'])
        if response.get('apiVersion')!=1 or response.get('requestId')!=request['requestId']:raise ValueError('Remote worker version or request identity mismatch.')
        result=response['result']
        if operation=='health' and result.get('workerSha256')!=digest:raise ValueError('Remote worker source does not match the reviewed version.')
        self.update(entry['id'],{'lastWorkerReading':{'operation':operation,'checkedUtc':now(),'result':result},**({'health':result} if operation=='health' else {})})
        return result
    def gpu_worker_health(self,p):return self.worker_call(self.profile(p.get('id')),'health')
    def gpu_worker_selftest(self,p):return self.worker_call(self.profile(p.get('id')),'gpu_selftest')

def dispatch(service,action,payload):
    if action not in ACTIONS:raise ValueError('Unsupported Cloud Compute action.')
    if not isinstance(payload,dict):raise ValueError('Cloud Compute requires a structured request.')
    return getattr(CloudCompute(service),action)(payload)
