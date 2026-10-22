"""Private SQLite broker, explicit capabilities, and conservative resource admission."""
from __future__ import annotations
import contextlib, datetime, fcntl, hashlib, json, os, pathlib, re, sqlite3, subprocess, sys, time, uuid

REPO = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_HOME = pathlib.Path.home() / 'Library/Application Support/FoldStudioWorker'
TERMINAL = {'completed', 'failed', 'cancelled'}
OPERATIONS = {'git-check', 'config-check', 'backend-tests', 'frontend-tests', 'typecheck', 'worker-tests', 'fixture-check', 'peptide-tests', 'coding-fixture-tests','worker-coding-acceptance'}
PROTECTED = {'.git', '.env', 'AGENTS.md', 'node_modules', 'private', '.ssh', '.aws', '.gnupg', 'credentials'}

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def digest(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def run(argv, **kw): return subprocess.run(argv, text=True, capture_output=True, timeout=kw.pop('timeout', 10), **kw)
def proc(pid):
    p=run(['/bin/ps','-p',str(int(pid)),'-o','lstart=,command='])
    return p.stdout.strip() if p.returncode == 0 else ''

def scoped(repo, name):
    p=pathlib.PurePosixPath(name)
    if not isinstance(name,str) or p.is_absolute() or not p.parts or any(x in ('..','.') or x in PROTECTED or x.startswith('.env') for x in p.parts):
        raise ValueError('Use exact repository-relative files; protected paths are refused.')
    path=repo.joinpath(*p.parts)
    # Every existing component must be a real directory/file, never a symlink.
    for component in [path, *path.parents]:
        if component == repo.parent: break
        if component.is_symlink(): raise ValueError('Symlinks are not authorized file capabilities.')
    if not path.resolve().is_relative_to(repo.resolve()): raise ValueError('Path leaves repository.')
    return path

def validate(spec, repo=REPO):
    if not isinstance(spec,dict): raise ValueError('A task must be a JSON object.')
    allowed={'schemaVersion','type','instructions','authorizedPaths','acceptanceCriteria','priority','resourceBudget','timeoutSeconds','retryLimit','operations','patches','repairs','model','maxModelCalls','maxContextBytes'}
    if set(spec)-allowed: raise ValueError('Unknown task fields: '+', '.join(sorted(set(spec)-allowed)))
    if spec.get('schemaVersion')!=1 or spec.get('type') not in ('deterministic','patch','local-ai','reasoning'):
        raise ValueError('Use schemaVersion 1 and a supported task type.')
    if not isinstance(spec.get('instructions'),str) or not 1<=len(spec['instructions'])<=12000: raise ValueError('Instructions must contain 1–12000 characters.')
    if not isinstance(spec.get('acceptanceCriteria'),list) or not spec['acceptanceCriteria'] or any(not isinstance(x,str) or len(x)>2000 for x in spec['acceptanceCriteria']): raise ValueError('Supply explicit acceptance criteria; prose is reported, operations are executable checks.')
    paths=spec.setdefault('authorizedPaths',[])
    if not isinstance(paths,list) or len(paths)>8 or any(not isinstance(x,str) for x in paths) or len(paths)!=len(set(paths)): raise ValueError('Authorize at most eight exact files.')
    for name in paths: scoped(repo,name)
    ops=spec.setdefault('operations',[])
    if not isinstance(ops,list) or len(ops)>8 or any(x not in OPERATIONS for x in ops): raise ValueError('Operations must come from the approved catalogue.')
    if spec['type']!='reasoning' and not ops: raise ValueError('At least one executable acceptance operation is required.')
    defaults={'priority':0,'timeoutSeconds':300,'retryLimit':0,'maxModelCalls':2,'maxContextBytes':24000}
    limits={'priority':(0,9),'timeoutSeconds':(1,3600),'retryLimit':(0,2),'maxModelCalls':(1,3),'maxContextBytes':(1000,48000)}
    for key,default in defaults.items():
        v=spec.setdefault(key,default);lo,hi=limits[key]
        if type(v)!=int or not lo<=v<=hi: raise ValueError('Invalid bounded '+key)
    budget=spec.setdefault('resourceBudget',{})
    if not isinstance(budget,dict) or set(budget)-{'memoryMiB','minAvailableMiB','maxLogMiB'}: raise ValueError('Unknown resource budget.')
    for key,default,lo,hi in [('memoryMiB',1024,64,6144),('minAvailableMiB',4096,1024,20000),('maxLogMiB',8,1,16)]:
        v=budget.setdefault(key,default)
        if type(v)!=int or not lo<=v<=hi: raise ValueError('Invalid '+key)
    if spec['type']=='deterministic' and paths: raise ValueError('Read-only deterministic tasks do not receive write capabilities.')
    if spec['type'] in ('patch','local-ai') and not paths: raise ValueError('Editing requires exact file capabilities.')
    for batch in [spec.setdefault('patches',[]),*spec.setdefault('repairs',[])]:
        if not isinstance(batch,list) or len(batch)>8: raise ValueError('Invalid patch batch.')
        for patch in batch:
            if not isinstance(patch,dict) or set(patch)!={'path','sha256','before','after'} or patch['path'] not in paths: raise ValueError('A patch needs an authorized path, SHA-256, before and after.')
            if not re.fullmatch('[0-9a-f]{64}',str(patch['sha256'])) or not all(isinstance(patch[k],str) and len(patch[k])<=100000 for k in ('before','after')) or not patch['before']: raise ValueError('Patch content or checksum is invalid.')
    if len(spec['repairs'])>spec['retryLimit']: raise ValueError('Repair batches exceed retry limit.')
    if spec['type'] not in ('patch',) and (spec['patches'] or spec['repairs']): raise ValueError('Deterministic patch capabilities require the patch task type.')
    if spec['type']=='local-ai' and not re.fullmatch(r'[a-zA-Z0-9_.:/-]{1,120}',str(spec.get('model',''))): raise ValueError('Name an already installed local Ollama model.')
    return spec

class Broker:
    def __init__(self, home=DEFAULT_HOME, repo=REPO, resource_domain=None):
        self.home=pathlib.Path(home).expanduser().resolve();self.repo=pathlib.Path(repo).resolve();self.resource_domain=pathlib.Path(resource_domain or DEFAULT_HOME).resolve();self.resource_domain.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.home.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(self.home,0o700)
        self.db=sqlite3.connect(self.home/'broker.sqlite3',timeout=20,isolation_level=None);self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA busy_timeout=20000')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,spec TEXT,status TEXT,created TEXT,started TEXT,finished TEXT,heartbeat REAL,attempts INTEGER DEFAULT 0,result TEXT,error TEXT,runner_pid INTEGER,runner_identity TEXT,revision TEXT);CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,id TEXT,time TEXT,status TEXT,detail TEXT);CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);''')
        self.db.execute('PRAGMA synchronous=FULL');os.chmod(self.home/'broker.sqlite3',0o600)
    @contextlib.contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try: yield;self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise
    def event(self,id,status,detail=''):self.db.execute('INSERT INTO events(id,time,status,detail) VALUES(?,?,?,?)',(id,now(),status,detail[:2000]))
    def task(self,id):
        row=self.db.execute('SELECT * FROM tasks WHERE id=?',(id,)).fetchone()
        if not row:raise ValueError('Unknown task ID.')
        d=dict(row);d['spec']=json.loads(d['spec']);d['result']=json.loads(d['result']) if d['result'] else None;return d
    def setting(self,key,default=None):
        r=self.db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone();return json.loads(r[0]) if r else default
    def set(self,key,value):self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(key,json.dumps(value)))
    def submit(self,spec):
        spec=validate(json.loads(json.dumps(spec,allow_nan=False)),self.repo);id=str(uuid.uuid4())
        with self.transaction():
            self.db.execute('INSERT INTO tasks(id,spec,status,created) VALUES(?,?,?,?)',(id,json.dumps(spec),'queued',now()));self.event(id,'queued')
        self.wake();return {'id':id,'status':'queued','report':str(self.home/'tasks'/id/'report.json')}
    def wake(self):
        try:
            fd=os.open(self.home/'wake',os.O_WRONLY|os.O_NONBLOCK);os.write(fd,b'!');os.close(fd)
        except OSError:pass
    def claim(self):
        with self.transaction():
            row=self.db.execute("SELECT id FROM tasks WHERE status='queued' ORDER BY json_extract(spec,'$.priority') DESC,created LIMIT 1").fetchone()
            if not row:return None
            id=row[0];self.db.execute("UPDATE tasks SET status='running',started=?,heartbeat=?,attempts=attempts+1,error=NULL WHERE id=? AND status='queued'",(now(),time.time(),id));self.event(id,'running')
        return self.task(id)
    def finish(self,id,status,result=None,error=None):
        if status not in TERMINAL|{'blocked'}:raise ValueError('Invalid final state.')
        with self.transaction():
            current=self.task(id)
            if current['status']=='cancelled':status='cancelled'
            self.db.execute('UPDATE tasks SET status=?,finished=?,heartbeat=?,result=?,error=? WHERE id=?',(status,now() if status in TERMINAL else None,time.time(),json.dumps(result),error,id));self.event(id,status,error or '')
    def resume(self,id):
        with self.transaction():
            d=self.task(id)
            if d['status']!='blocked':raise ValueError('Only blocked tasks can be explicitly resumed; submit a new task for terminal results.')
            if d['runner_pid'] and proc(d['runner_pid'])==d['runner_identity']:raise ValueError('Previous runner still exists; waiting avoids duplicate execution.')
            self.db.execute("UPDATE tasks SET status='queued',runner_pid=NULL,runner_identity=NULL,error=NULL,finished=NULL WHERE id=?",(id,));self.event(id,'queued','Explicit resume')
        self.wake()
    def cancel(self,id):
        with self.transaction():
            if self.task(id)['status'] in TERMINAL:return
            self.db.execute("UPDATE tasks SET status='cancelled',finished=? WHERE id=?",(now(),id));self.event(id,'cancelled')
        self.wake()
    def recover(self):
        # Restarted side effects are never silently replayed, even with an expired heartbeat.
        for row in self.db.execute("SELECT id FROM tasks WHERE status='running'").fetchall():
            self.finish(row[0],'blocked',error='Worker interrupted; inspect artifacts and explicitly resume. No side effect was replayed.')


def resources(repo=REPO):
    memory={};processes=[];science=[];reason=None
    pressure=run(['/usr/sbin/sysctl','-n','kern.memorystatus_vm_pressure_level'])
    if pressure.returncode:reason='Memory-pressure telemetry unavailable.'
    try:level=int(pressure.stdout.strip())
    except ValueError:level=None
    vm=run(['/usr/bin/vm_stat']);page=re.search(r'page size of (\d+)',vm.stdout);pages=dict((k,int(v)) for k,v in re.findall(r'^([^:]+):\s+(\d+)\.',vm.stdout,re.M))
    available=sum(pages.get(k,0) for k in ['Pages free','Pages inactive','Pages speculative','Pages purgeable'])*int(page[1])//1048576 if page else 0
    ps=run(['/bin/ps','-axo','pid=,ppid=,rss=,%cpu=,command='])
    for line in ps.stdout.splitlines():
        fields=line.strip().split(None,4)
        if len(fields)!=5:continue
        pid,ppid,rss,cpu,command=fields
        if int(pid)==os.getpid() or command.startswith(('/bin/ps','/bin/zsh -lc','/bin/bash -lc')):continue
        # Launchers and idle ChimeraX sessions are not inference. Known workers take priority.
        demanding=any(marker in command for marker in ['bindcraft_native_runner.py','bindcraft_campaign.py','amme_worker.py','boltz_entry.py','prediction_runner.py','openmm_runner.py','rapid_worker.py run'])
        related='FoldStudio-MetalPort' in command or 'ChimeraX' in command
        if demanding or (related and (int(rss)>2*1024**2 or float(cpu)>80)):
            science.append({'pid':int(pid),'rssMiB':round(int(rss)/1024,1),'cpuPercent':float(cpu),'command':command[:240]})
    live=pathlib.Path(repo).parent/'validation/bindcraft-fab-amme-native/library.sqlite3'
    if live.exists():
        try:
            db=sqlite3.connect('file:'+str(live)+'?mode=ro',uri=True,timeout=1)
            with contextlib.closing(db):
                for id,name,state in db.execute("SELECT id,name,state FROM jobs WHERE state IN ('running','starting','cancelling')"):
                    science.append({'jobId':id,'name':name,'state':state,'source':'read-only saved-job state; conservative admission'})
        except sqlite3.Error:reason='Scientific job state temporarily unavailable.'
    return {'memoryPressureLevel':level,'estimatedAvailableMiB':available,'availableMethod':'reclaimable free+inactive+speculative+purgeable pages; estimate, not guaranteed capacity','scientificWorkloads':science,'telemetryError':reason}

def admission(spec, snapshot):
    if spec['type']=='reasoning':return 'Tier 3 reasoning requested; review in Work. No cloud model was invoked.'
    if snapshot['telemetryError']:return snapshot['telemetryError']
    if snapshot['memoryPressureLevel']!=1:return 'Memory pressure is not normal; scientific and interactive work take priority.'
    if snapshot['scientificWorkloads']:return 'Scientific workload detected; deferred without interrupting it.'
    if snapshot['estimatedAvailableMiB']<spec['resourceBudget']['minAvailableMiB']+spec['resourceBudget']['memoryMiB']:return 'Insufficient estimated memory headroom.'
    if spec['type']=='local-ai' and any(p.startswith(('scientific/','local_worker/','src-tauri/','scripts/seal','scripts/install')) for p in spec['authorizedPaths']):return 'Scientific/security-sensitive edits require Tier 3 review, not autonomous local coding.'
    return None
