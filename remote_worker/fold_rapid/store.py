"""SQLite job/event store. Idempotency survives app and transport disconnects."""
import contextlib
import datetime
import json
import os
import pathlib
import sqlite3
import uuid
from .contracts import canonical,digest,identifier,manifest
from .molecules import selected_target

TERMINAL={'completed','no_qualified_candidates','failed','cancelled','deadline_exceeded','interrupted'}
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()

class Store:
    def __init__(self,root):
        self.root=pathlib.Path(root).absolute()
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        os.chmod(self.root,0o700)
        self.jobs=self.root/'jobs';self.jobs.mkdir(exist_ok=True,mode=0o700)
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, idempotency TEXT UNIQUE NOT NULL, manifest_hash TEXT NOT NULL, manifest TEXT NOT NULL, state TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL, runner_pid INTEGER, error TEXT, result TEXT);
CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, job TEXT NOT NULL, time TEXT NOT NULL, data TEXT NOT NULL);''')
    @contextlib.contextmanager
    def db(self):
        db=sqlite3.connect(self.root/'rapid.sqlite3',timeout=15);db.row_factory=sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
        try:
            with db:yield db
        finally:db.close()
    def folder(self,id):return self.jobs/identifier(id)
    def submit(self,value,key):
        value=manifest(value);mapping=selected_target(value)
        if not isinstance(key,str) or not 1<=len(key)<=100:raise ValueError('An idempotency key is required.')
        text=canonical(value);sha=digest(text.encode());id=uuid.uuid4().hex
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT id,manifest_hash FROM jobs WHERE idempotency=?',(key,)).fetchone()
            if old:
                if old['manifest_hash']!=sha:raise ValueError('Idempotency key is already associated with different scientific inputs.')
                return {'jobId':old['id'],'created':False}
            folder=self.folder(id);folder.mkdir(mode=0o700)
            (folder/'manifest.json').write_text(text)
            (folder/'target-mapping.json').write_text(canonical(mapping))
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)',(id,key,sha,text,'queued',now(),now(),None,None,None))
        self.event(id,{'kind':'queued','manifestSha256':sha})
        return {'jobId':id,'created':True}
    def get(self,id):
        identifier(id)
        with self.db() as db:row=db.execute('SELECT * FROM jobs WHERE id=?',(id,)).fetchone()
        if row is None:raise ValueError('Job not found.')
        value=dict(row);value['manifest']=json.loads(value['manifest']);value['result']=json.loads(value['result']) if value['result'] else None
        return value
    def list(self):
        with self.db() as db:rows=db.execute('SELECT id,state,created,updated,error FROM jobs ORDER BY created DESC LIMIT 100').fetchall()
        return [dict(row) for row in rows]
    def event(self,id,value):
        with self.db() as db:db.execute('INSERT INTO events(job,time,data) VALUES(?,?,?)',(identifier(id),now(),canonical(value)))
    def events(self,id,after=None):
        self.get(id)
        if after is not None and (type(after) is not int or after<0):raise ValueError('Invalid event cursor.')
        with self.db() as db:
            rows=(list(reversed(db.execute('SELECT * FROM events WHERE job=? ORDER BY seq DESC LIMIT 100',(id,)).fetchall())) if after is None else db.execute('SELECT * FROM events WHERE job=? AND seq>? ORDER BY seq LIMIT 100',(id,after)).fetchall())
        return [{'cursor':r['seq'],'time':r['time'],**json.loads(r['data'])} for r in rows]
    def finish(self,id,state,error=None,result=None):
        if state not in TERMINAL:raise ValueError('Invalid terminal state.')
        with self.db() as db:db.execute('UPDATE jobs SET state=?,updated=?,error=?,result=? WHERE id=?',(state,now(),error,canonical(result) if result is not None else None,id))
        self.event(id,{'kind':state,'error':error})
    def cancel(self,id):
        value=self.get(id)
        with self.db() as db:
            db.execute("UPDATE jobs SET state='cancel_requested',updated=? WHERE id=? AND state NOT IN ("+','.join('?'*len(TERMINAL))+')',(now(),id,*TERMINAL))
        return {'jobId':id,'state':self.get(id)['state'],'recovery':'Existing artifacts retained. Exact optimizer/RNG-step resume is not implemented.'}
    def recover(self):
        results=[]
        for row in self.list():
            if row['state'] in TERMINAL:continue
            job=self.get(row['id']);pid=job['runner_pid']
            if pid:
                try:os.kill(pid,0);continue
                except ProcessLookupError:pass
            self.finish(job['id'],'interrupted','Worker process is absent. Existing outputs preserved; exact optimizer-step resume is unavailable.')
            results.append(job['id'])
        return {'interrupted':results,'exactStepResume':False}
