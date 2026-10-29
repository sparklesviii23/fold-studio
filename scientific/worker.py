#!/usr/bin/env python3
"""FOLD STUDIO scientific service. stdlib-only IPC; isolated Boltz process.
Native host invokes one JSON request on stdin. No network listener in production.
"""
import argparse, base64, datetime, hashlib, json, math, os, pathlib, platform, re, shutil, signal, sqlite3, subprocess, sys, time, urllib.error, urllib.parse, urllib.request, uuid, zipfile
sys.dont_write_bytecode = True

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from observatory import Observatory, ACTIONS as OBSERVATORY_ACTIONS
from peptides import Peptides, ACTIONS as PEPTIDE_ACTIONS
import molecular_graph
import periodic_dynamics
import genomic_io
import chemical_screen
import sequence_alignment
import sequence_reads
import quantum_engine
import intelligence
import fold_engine
import mpnn
import ligand
import dynamics
import cloud_compute
import rapid_remote
import research
import cinema
import evolution
import boltz_api_adapter
import biology_pipeline
import biology_evidence
import biology_agent
import cloud_deployment
import cloud_shell
import cloud_accounts
import cloud_monitor
import cloud_audit
import molecular_observatory
import editcraft
import execution_policy
import modal_account
import biology_modal
import peptide_chemistry
import project_archive
import project_restore
import genome_workspace

AA = 'ACDEFGHIKLMNPQRSTVWY'
MAX_FILE = 100 * 1024 * 1024
COLAB_URL = 'https://colab.research.google.com/github/sokrypton/ColabFold/blob/main/AlphaFold2.ipynb'
ENGINE_VERSION = (pathlib.Path(__file__).parent / 'engine-version.txt').read_text().strip()

def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())
def digest(text): return hashlib.sha256(text.encode()).hexdigest()
def validate_sequence(text):
    sequence = re.sub(r'\s+', '', text).upper()
    if not sequence: raise ValueError('Enter a protein sequence.')
    bad = sorted(set(sequence) - set(AA))
    if bad: raise ValueError('Unsupported amino acids: ' + ', '.join(bad) + '. Use the 20 canonical amino acids; resolve ambiguous residues before prediction.')
    if len(sequence) > 4000: raise ValueError('Sequences above 4,000 residues exceed the workstation input limit.')
    return sequence

def parse_fasta(text):
    records, name, parts = [], None, []
    for line in text.splitlines():
        line = line.strip()
        if not line: continue
        if line.startswith('>'):
            if name is not None: records.append({'name': name, 'sequence': validate_sequence(''.join(parts))})
            name, parts = line[1:].strip() or 'Untitled sequence', []
        else:
            if name is None: name = 'Custom sequence'
            parts.append(line)
    if name is not None: records.append({'name': name, 'sequence': validate_sequence(''.join(parts))})
    if not records: raise ValueError('No FASTA sequences found.')
    if len(records) > 26: raise ValueError('At most 26 protein chains are supported.')
    return records

def fetch(url, raw=False):
    allowed = {'rest.uniprot.org', 'alphafold.ebi.ac.uk', 'files.rcsb.org', 'data.rcsb.org', 'search.rcsb.org', 'www.ebi.ac.uk'}
    if urllib.parse.urlparse(url).scheme != 'https' or urllib.parse.urlparse(url).hostname not in allowed:
        raise ValueError('Unsupported scientific provider URL.')
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'FOLD-STUDIO/0.1 scientific workstation', 'Accept': '*/*' if raw else 'application/json'})
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read(MAX_FILE + 1)
                if len(body) > MAX_FILE: raise ValueError('Remote file exceeds the 100 MB limit.')
                return body if raw else json.loads(body)
        except urllib.error.HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2: raise
        except urllib.error.URLError:
            if attempt == 2: raise
        time.sleep(0.5 * (attempt + 1))

class Service:
    def __init__(self, root, fixtures=None):
        self.root = pathlib.Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for folder in ['assets', 'jobs', 'engine', 'cache']: (self.root/folder).mkdir(exist_ok=True)
        self.db = sqlite3.connect(str(self.root/'library.sqlite3'), timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,notes TEXT NOT NULL DEFAULT '',created TEXT,updated TEXT);
        CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),kind TEXT NOT NULL,name TEXT NOT NULL,data TEXT NOT NULL,created TEXT);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),name TEXT,engine TEXT,state TEXT,data TEXT,created TEXT,updated TEXT);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS cache(url TEXT PRIMARY KEY,data TEXT,created REAL);''')
        if fixtures and not self.db.execute('SELECT 1 FROM projects LIMIT 1').fetchone():
            project = self.project_create({'name':'Observatory Library'})
            f = pathlib.Path(fixtures)
            if (f/'ANGPTL3.json').exists():
                protein = json.loads((f/'ANGPTL3.json').read_text())['results'][0]
                protein['_retrieved'] = '2026-10-09'
                protein['_source'] = 'Bundled UniProt reference, retrieved 9 October 2026'
                self.record_save({'projectId':project['id'],'kind':'protein','name':'ANGPTL3 · Q9Y5C1','data':protein})
                af = json.loads((f/'ANGPTL3-alphafold.json').read_text())[0]
                self.import_structure({'projectId':project['id'],'path':str(f/'ANGPTL3.cif'),'name':'ANGPTL3 · AlphaFold DB reference','source':af['cifUrl'],'accession':'Q9Y5C1','confidenceKind':'AlphaFold pLDDT','metadata':af})
            self.db.commit()
    def rows(self, sql, args=()): return [dict(row) for row in self.db.execute(sql,args)]
    def setting(self, key, default=None):
        row = self.db.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else default
    def setting_set(self, p):
        allowed = {'appearance','effects','onboarded','enginePython','sidebarWidth','interface','lastStructureId','bindcraftPython','bindcraftMetalPython','af2Parameters','openmmPython'}
        if p['key'] not in allowed: raise ValueError('Unknown preference.')
        if p['key']=='interface':
            v=p.get('value')
            if not isinstance(v,dict) or v.get('scale') not in [100,110,125,150] or v.get('density') not in ['comfortable','compact'] or any(not isinstance(v.get(k),bool) for k in ['transparency','motion']): raise ValueError('Unsupported interface preferences.')
        self.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(p['key'],json.dumps(p['value'])))
        self.db.commit(); return p['value']
    def library(self, p):
        self.db.execute('CREATE TABLE IF NOT EXISTS removed_records(id TEXT PRIMARY KEY)')
        removed={r['id'] for r in self.rows('SELECT id FROM removed_records')}
        records = self.rows('SELECT * FROM records ORDER BY created DESC')
        jobs = self.rows('SELECT * FROM jobs ORDER BY created DESC')
        for record in records + jobs: record['data'] = json.loads(record['data'])
        return {'projects':self.rows('SELECT * FROM projects ORDER BY updated DESC'), 'records':[r for r in records if r['id'] not in removed],'removedRecords':[r for r in records if r['id'] in removed],'jobs':jobs, 'settings':{row['key']:json.loads(row['value']) for row in self.rows('SELECT * FROM settings')}}
    def project(self, id):
        row = self.db.execute('SELECT * FROM projects WHERE id=?',(id,)).fetchone()
        if not row: raise ValueError('Choose an existing research project.')
        return dict(row)
    def project_create(self, p):
        name = str(p.get('name','')).strip()[:160]
        if not name: raise ValueError('Project name cannot be empty.')
        id, date = uid(), now()
        self.db.execute('INSERT INTO projects VALUES(?,?,?,?,?)',(id,name,'',date,date)); self.db.commit()
        return self.project(id)
    def project_update(self,p):
        self.project(p['id'])
        name = str(p['name']).strip()[:160]
        if not name: raise ValueError('Project name cannot be empty.')
        self.db.execute('UPDATE projects SET name=?,notes=?,updated=? WHERE id=?',(name,str(p.get('notes',''))[:100000],now(),p['id'])); self.db.commit()
        return self.project(p['id'])
    def project_delete(self,p):
        self.project(p['id'])
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE name='biology_api_requests'").fetchone():
            import json as request_json
            api_states=[request_json.loads(row['data']).get('state') for row in self.rows('SELECT data FROM biology_api_requests WHERE project_id=?',(p['id'],))]
            if any(state in ('submission_uncertain','submitted','pending','running') for state in api_states):raise ValueError('Stop or reconcile external Boltz jobs before deleting this project.')
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE name='biology_modal_jobs'").fetchone():
            states=[json.loads(row['data']).get('state') for row in self.rows('SELECT data FROM biology_modal_jobs WHERE project_id=?',(p['id'],))]
            if any(state not in ('prepared','completed','failed','cancelled','interrupted','rejected','finished','partial','COMPLETED','PARTIALLY_COMPLETE','FAILED','CANCELLED') for state in states):raise ValueError('Stop or reconcile remote Modal jobs before deleting this project.')
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE name='editcraft_jobs'").fetchone():
            states=[json.loads(row['data']).get('state') for row in self.rows('SELECT data FROM editcraft_jobs WHERE project_id=?',(p['id'],))]
            if any(state not in ('prepared','completed','failed','cancelled','deadline_exceeded') for state in states):raise ValueError('Stop or reconcile EditCraft cloud experiments before deleting this project.')
        active = self.db.execute("SELECT 1 FROM jobs WHERE project_id=? AND state IN ('running','queued','installing')",(p['id'],)).fetchone()
        if active: raise ValueError('Cancel active jobs before deleting the project.')
        lab=intelligence.Lab(self)
        if self.db.execute("SELECT 1 FROM intelligence_tasks WHERE project_id=? AND state IN ('running','queued')",(p['id'],)).fetchone():raise ValueError('Cancel active intelligence tasks before deleting the project.')
        for table in ['intelligence_tasks','intelligence_assignments','intelligence_candidates','intelligence_hotspots','intelligence_confidence']:self.db.execute('DELETE FROM '+table+' WHERE project_id=?',(p['id'],))
        for table in ['evolution_events','evolution_candidates','evolution_manifests','biology_api_requests','biology_modal_jobs','biology_evidence','editcraft_entities','editcraft_jobs']:
            if self.db.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():self.db.execute('DELETE FROM '+table+' WHERE project_id=?',(p['id'],))
        # File assets remain until an explicit future garbage collection; deletion is metadata-only.
        Observatory(self)
        Peptides(self)
        self.db.execute('DELETE FROM peptide_versions WHERE record_id IN (SELECT id FROM records WHERE project_id=?)',(p['id'],))
        self.db.execute('DELETE FROM arcade_progress WHERE project_id=?',(p['id'],))
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE name='molecular_drafts'").fetchone():
            self.db.execute('DELETE FROM molecular_drafts WHERE context=?',(p['id'],))
            self.db.execute('DELETE FROM molecular_migrations WHERE context=?',(p['id'],))
        for table in ['observatory_entries','observatory_commands','records','jobs','projects']: self.db.execute('DELETE FROM '+table+' WHERE '+('id' if table=='projects' else 'project_id')+'=?',(p['id'],))
        self.db.commit(); return True
    def record_save(self,p):
        self.project(p['projectId'])
        if p['kind'] not in ['protein','sequence','variant','structure','analysis','figure','complex']: raise ValueError('Unsupported library item.')
        id = uid()
        self.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(id,p['projectId'],p['kind'],str(p['name'])[:200],json.dumps(p['data']),now()))
        self.db.execute('UPDATE projects SET updated=? WHERE id=?',(now(),p['projectId'])); self.db.commit()
        return {'id':id,'project_id':p['projectId'],'kind':p['kind'],'name':p['name'],'data':p['data']}
    def record_update(self,p):
        row=self.db.execute('SELECT * FROM records WHERE id=? AND project_id=?',(p['id'],p['projectId'])).fetchone()
        if not row:raise ValueError('Library item not found in this project.')
        name=str(p.get('name','')).strip()
        if not name or len(name)>200:raise ValueError('Enter a name between 1 and 200 characters.')
        notes=str(p.get('notes',''))
        if len(notes)>10000:raise ValueError('Notes must be below 10,000 characters.')
        data=json.loads(row['data']);data['notes']=notes
        self.db.execute('UPDATE records SET name=?,data=? WHERE id=?',(name,json.dumps(data),p['id']));self.db.commit()
        return {**dict(row),'name':name,'data':data}
    def record_remove(self,p):
        if not self.db.execute('SELECT id FROM records WHERE id=? AND project_id=?',(p['id'],p['projectId'])).fetchone():raise ValueError('Library item not found in this project.')
        self.db.execute('CREATE TABLE IF NOT EXISTS removed_records(id TEXT PRIMARY KEY)')
        self.db.execute('INSERT OR IGNORE INTO removed_records VALUES(?)',(p['id'],));self.db.commit();return True
    def record_restore(self,p):
        if not self.db.execute('SELECT id FROM records WHERE id=? AND project_id=?',(p['id'],p['projectId'])).fetchone():raise ValueError('Library item not found in this project.')
        self.db.execute('CREATE TABLE IF NOT EXISTS removed_records(id TEXT PRIMARY KEY)')
        self.db.execute('DELETE FROM removed_records WHERE id=?',(p['id'],));self.db.commit();return True
    def cached_fetch(self,url):
        row = self.db.execute('SELECT * FROM cache WHERE url=?',(url,)).fetchone()
        if row and time.time()-row['created'] < 86400: return json.loads(row['data'])
        try:
            result = fetch(url)
            self.db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(url,json.dumps(result),time.time())); self.db.commit()
            return result
        except (urllib.error.URLError, TimeoutError):
            if row:
                result = json.loads(row['data'])
                if isinstance(result,dict): result['_offlineCache'] = True
                return result
            raise
    def uniprot_search(self,p):
        query = str(p.get('query','')).strip()
        if not query: return {'results':[]}
        tax = str(p.get('taxonomy','')).strip()
        if tax and not tax.isdigit(): raise ValueError('Taxonomy must be a numeric ID.')
        q = '('+query+')'+(' AND organism_id:'+tax if tax else '')+(' AND reviewed:true' if p.get('reviewed') else '')
        params = {'query':q,'format':'json','size':25,'fields':'accession,id,protein_name,gene_names,organism_name,length,reviewed'}
        if p.get('cursor'): params['cursor'] = str(p['cursor'])
        url = 'https://rest.uniprot.org/uniprotkb/search?'+urllib.parse.urlencode(params)
        # Fetch headers for documented cursor pagination.
        row = self.db.execute('SELECT * FROM cache WHERE url=?',(url,)).fetchone()
        if row and time.time()-row['created'] < 3600: return json.loads(row['data'])
        try:
            request = urllib.request.Request(url,headers={'User-Agent':'FOLD-STUDIO/0.1'})
            with urllib.request.urlopen(request,timeout=30) as response:
                result = json.load(response)
                link = response.headers.get('Link','')
                nexturl = re.search(r'<([^>]+)>; rel="next"',link)
                result['nextCursor'] = urllib.parse.parse_qs(urllib.parse.urlparse(nexturl[1]).query).get('cursor',[None])[0] if nexturl else None
                result['total'] = int(response.headers.get('x-total-results',len(result.get('results',[]))))
            self.db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(url,json.dumps(result),time.time())); self.db.commit(); return result
        except urllib.error.URLError:
            if row:
                result=json.loads(row['data']); result['_offlineCache']=True; return result
            raise
    def uniprot_get(self,p):
        acc = str(p['accession']).upper()
        if not re.fullmatch(r'[A-Z0-9]{6,10}(?:-\d+)?',acc): raise ValueError('Invalid UniProt accession.')
        result = self.cached_fetch('https://rest.uniprot.org/uniprotkb/'+acc+'.json')
        result['_source'] = 'https://rest.uniprot.org/uniprotkb/'+acc+'.json'
        result['_retrieved'] = now()
        return result
    def structures(self,p):
        protein = p['protein']; accession = protein['primaryAccession']; results=[]; errors=[]
        try:
            for entry in self.cached_fetch('https://alphafold.ebi.ac.uk/api/prediction/'+accession):
                results.append({'id':entry['entryId'],'source':'AlphaFold DB','type':'Predicted','url':entry['cifUrl'],'confidenceKind':'AlphaFold pLDDT','coverage':str(entry.get('uniprotStart',entry.get('sequenceStart','?')))+'–'+str(entry.get('uniprotEnd',entry.get('sequenceEnd','?'))),'metadata':entry,'accession':accession})
        except Exception as error: errors.append('AlphaFold DB: '+str(error))
        for ref in protein.get('uniProtKBCrossReferences',[]):
            if ref['database']!='PDB': continue
            props={x['key']:x['value'] for x in ref.get('properties',[])}
            results.append({'id':ref['id'],'source':'RCSB PDB','type':'Experimental','url':'https://files.rcsb.org/download/'+ref['id']+'.cif','coverage':props.get('Chains','Unavailable'),'method':props.get('Method'),'resolution':props.get('Resolution'),'metadata':props,'accession':accession})
        return {'results':results,'errors':errors}
    def structure_download(self,p):
        entry = p['entry']; content = fetch(entry['url'],raw=True)
        path = self.root/'assets'/(uid()+'.cif'); path.write_bytes(content)
        return self.import_structure({**p,'path':str(path),'name':entry['id']+' · '+entry['source'],'source':entry['url'],'accession':entry.get('accession'),'confidenceKind':entry.get('confidenceKind'),'metadata':entry['metadata']})
    def import_structure(self,p):
        path=pathlib.Path(p['path'])
        if path.suffix.lower() not in ['.pdb','.cif','.mmcif']: raise ValueError('Choose a PDB or mmCIF file.')
        if not path.is_file() or path.stat().st_size>MAX_FILE: raise ValueError('Structure must be a file below 100 MB.')
        data=path.read_bytes()
        if not (b'_atom_site.' in data or b'ATOM  ' in data or b'HETATM' in data): raise ValueError('No atom coordinates found in this structure file.')
        metadata=dict(p.get('metadata',{}))
        if 'coordinateSets' in p and type(p['coordinateSets']) is not bool: raise ValueError('Coordinate ensemble import requires an explicit boolean option.')
        if p.get('coordinateSets'):
            if path.suffix.lower()!='.pdb': raise ValueError('Coordinate ensemble import currently requires a multi-MODEL PDB.')
            from coordinate_ensemble import inspect
            metadata['coordinateEnsemble']=inspect(data)
        target=self.root/'assets'/(uid()+path.suffix.lower()); target.write_bytes(data)
        info={'asset':target.name,'format':'pdb' if path.suffix.lower()=='.pdb' else 'mmcif','sha256':hashlib.sha256(data).hexdigest(),'source':p.get('source','Imported local coordinate ensemble' if p.get('coordinateSets') else 'Imported local file'),'accession':p.get('accession'),'confidenceKind':p.get('confidenceKind'),'metadata':metadata,'imported':now()}
        return self.record_save({'projectId':p['projectId'],'kind':'structure','name':p.get('name',path.name),'data':info})
    def asset_read(self,p):
        name=str(p['asset'])
        if pathlib.Path(name).name!=name: raise ValueError('Invalid asset identifier.')
        path=self.root/'assets'/name
        if path.stat().st_size>MAX_FILE: raise ValueError('File exceeds read limit.')
        return path.read_text()
    def sequence_save(self,p):
        seq=validate_sequence(p['sequence']); origin=p.get('origin',{})
        return self.record_save({'projectId':p['projectId'],'kind':'sequence','name':p['name'],'data':{'sequence':seq,'sha256':digest(seq),'origin':origin,'created':now()}})
    def mutate(self,p):
        sequence=validate_sequence(p['sequence']); mutations=[]; modified=list(sequence); seen=set()
        for text in str(p['mutations']).split(','):
            match=re.fullmatch(r'([A-Z])(\d+)([A-Z])',text.strip().upper())
            if not match: raise ValueError('Use substitutions like A25V, L78P.')
            ref,pos,alt=match[1],int(match[2]),match[3]
            if ref not in AA or alt not in AA or pos<1 or pos>len(sequence): raise ValueError('Mutation outside sequence or invalid residue.')
            if pos in seen: raise ValueError('Only one substitution per residue is allowed.')
            if sequence[pos-1]!=ref: raise ValueError('Reference mismatch at '+str(pos)+': expected '+sequence[pos-1]+'.')
            seen.add(pos); modified[pos-1]=alt; mutations.append(match[0])
        return self.record_save({'projectId':p['projectId'],'kind':'variant','name':p['name'],'data':{'sequence':''.join(modified),'reference':sequence,'mutations':mutations,'origin':p.get('origin',{}),'sha256':digest(''.join(modified)),'classification':'User-generated hypothetical variant'}})
    def fasta_parse(self,p): return parse_fasta(p['text'])
    def fasta_import(self,p):
        path=pathlib.Path(p['path'])
        if path.suffix.lower() not in ['.fa','.fasta','.txt'] or path.stat().st_size>1024**2: raise ValueError('Choose a FASTA file below 1 MB.')
        return parse_fasta(path.read_text())
    def engine_python(self):
        bundled=pathlib.Path(__file__).resolve().parents[1]/'runtime-boltz/bin/python3.12'
        return self.setting('enginePython') or str(bundled if bundled.is_file() else self.root/'engine/venv/bin/python')
    def prediction_resources(self,p):
        if set(p)-{'verify'} or type(p.get('verify',False)) is not bool:raise ValueError('Model inspection accepts only an explicit verification switch.')
        from boltz_resources import status
        return status(self.root/'engine/models',p.get('verify',False))
    def compute(self,p):
        return self.compute_for(self.engine_python())
    def compute_for(self,python):
        memory=None; chip=platform.machine()
        try:
            memory=int(subprocess.check_output(['/usr/sbin/sysctl','-n','hw.memsize'],text=True,stderr=subprocess.DEVNULL).strip())
            chip=subprocess.check_output(['/usr/sbin/sysctl','-n','machdep.cpu.brand_string'],text=True).strip()
        except Exception: pass
        result={'chip':chip,'architecture':platform.machine(),'macOS':platform.mac_ver()[0],'memoryGB':round(memory/1024**3,1) if memory else None,'diskFreeGB':round(shutil.disk_usage(self.root).free/1024**3,1),'python':str(python),'runtimeKind':'bundled' if os.path.abspath(python)==str(pathlib.Path(__file__).resolve().parents[1]/'runtime-boltz/bin/python3.12') else 'configured' if self.setting('enginePython') else 'managed','installed':False,'mpsAvailable':False,'mpsBuilt':False,'version':None,'weightsDownloaded':(self.root/'engine/models/boltz2_conf.ckpt').exists()}
        py=pathlib.Path(python)
        if not py.is_file(): return result
        try:
            proc=subprocess.run([str(py),'-B','-c','import json,torch,importlib.metadata; print(json.dumps(dict(installed=True,version=importlib.metadata.version("boltz-community"),mpsAvailable=torch.backends.mps.is_available(),mpsBuilt=torch.backends.mps.is_built(),torchVersion=torch.__version__)))'],capture_output=True,text=True,timeout=45)
            if proc.returncode==0: result.update(json.loads(proc.stdout.strip().splitlines()[-1]))
            else: result['error']=proc.stderr[-3000:]
        except Exception as error: result['error']=str(error)
        # Hardware detection is not an inference acceptance test.
        result['validatedMPS']=self.setting('validatedMPS',False)
        return result
    def active(self):
        owner=getattr(self,'_compute_owner',None)
        if owner:
            job=self.job(owner)
            if job['engine']!='bgmee' or job['state']!='running':owner=None
        return self.db.execute("SELECT id FROM jobs WHERE engine IN ('boltz2','setup','proteinmpnn','bindcraft2','rdkit','peptide_chemistry','openmm','bgmee','pyscf','genomic_io','periodic_lj') AND state IN ('running','queued','installing') AND id!=? LIMIT 1",(owner or '',)).fetchone()
    def job_new(self,p,engine,state):
        if getattr(self,'_compute_owner',None) and engine!='bgmee':p={**p,'controllerId':self._compute_owner}
        self.project(p['projectId']); id,date=uid(),now()
        self.db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',(id,p['projectId'],p.get('name','Prediction'),engine,state,json.dumps(p),date,date)); self.db.commit()
        return self.job(id)
    def job(self,id):
        row=self.db.execute('SELECT * FROM jobs WHERE id=?',(id,)).fetchone()
        if not row: raise ValueError('Unknown job.')
        result=dict(row); result['data']=json.loads(result['data']); return result
    def job_update(self,id,state,extra=None):
        if not self.db.in_transaction: self.db.execute('BEGIN IMMEDIATE')
        job=self.job(id); job['data'].update(extra or {})
        self.db.execute('UPDATE jobs SET state=?,data=?,updated=? WHERE id=?',(state,json.dumps(job['data']),now(),id)); self.db.commit()
    def job_metadata(self,id,extra):
        # A short worker can finish before Popen returns. Attaching its PID must
        # neither restore an earlier state nor overwrite its completed results.
        self.db.execute('BEGIN IMMEDIATE')
        try:
            job=self.job(id); job['data'].update(extra)
            self.db.execute('UPDATE jobs SET data=?,updated=? WHERE id=?',(json.dumps(job['data']),now(),id)); self.db.commit()
        except Exception:
            self.db.rollback(); raise
    def spawn(self,job,mode):
        folder=self.root/'jobs'/job['id']; folder.mkdir(exist_ok=True)
        with open(folder/'execution.log','ab',buffering=0) as log:
            process=subprocess.Popen([sys.executable,'-B',str(pathlib.Path(__file__).resolve()),'--root',str(self.root),mode,job['id']],stdout=log,stderr=log,start_new_session=True,env=dict(os.environ,PYTHONUNBUFFERED='1',PYTHONDONTWRITEBYTECODE='1'))
        self.job_metadata(job['id'],{'pid':process.pid,'workerPath':str(pathlib.Path(__file__).resolve()),'logAsset':str(folder/'execution.log')})
        return self.job(job['id'])
    def install_engine(self,p):
        if self.active(): raise ValueError('One local process at a time. Wait for the current job or cancel it.')
        if platform.system()!='Darwin' or platform.machine()!='arm64': raise ValueError('This setup targets Apple Silicon macOS.')
        if shutil.disk_usage(self.root).free < 12*1024**3: raise ValueError('At least 12 GB free disk space is required for dependencies and weights.')
        self.db.execute('BEGIN IMMEDIATE')
        if self.active():
            self.db.rollback(); raise ValueError('Another local job is active.')
        return self.spawn(self.job_new(p,'setup','installing'),'--install')
    def prediction_start(self,p):
        import scientific_capabilities
        scientific_capabilities.enforce(self,'prediction_start',p)
        if self.active(): raise ValueError('One local process at a time. Wait for the current job or cancel it.')
        chains=parse_fasta(p['fasta']); total=sum(len(c['sequence']) for c in chains)
        if total>1500: raise ValueError('This 24 GB workstation limits local predictions to 1,500 total residues. Smaller inputs may still exhaust memory.')
        for key,lo,hi,default in [('recycles',1,10,3),('samples',1,5,1),('steps',10,500,200),('seed',0,2147483647,42)]:
            value=int(p.get(key,default))
            if value<lo or value>hi: raise ValueError('Invalid '+key+'.')
            p[key]=value
        if p.get('msa') not in ['server','single']: raise ValueError('Select a supported MSA mode.')
        status=self.compute({})
        if not status['installed'] or not status['mpsAvailable']: raise ValueError('Install the engine and verify MPS availability first.')
        p.update({'chains':chains,'inputSha256':digest(json.dumps(chains,sort_keys=True)),'hardware':status,'model':'boltz2','engineVersion':status['version'],'msaSource':'https://api.colabfold.com' if p['msa']=='server' else 'Single sequence; no MSA','started':now()})
        self.db.execute('BEGIN IMMEDIATE')
        if self.active():
            self.db.rollback(); raise ValueError('A local job was started while diagnostics were being checked. Wait for it to finish.')
        return self.spawn(self.job_new(p,'boltz2','queued'),'--run-job')
    def job_read(self,p):
        job=self.job(p['id']); path=self.root/'jobs'/p['id']/'execution.log'
        log_data=b''
        if path.exists():
            with open(path,'rb') as f:
                # Full Fab emits many per-gradient memory events. Keep a wider,
                # bounded context for trajectory/stage parsing, while the visible
                # log stays small. Otherwise its header disappears mid-trajectory.
                limit=1024**2 if job['engine']=='bindcraft2' else 30000
                f.seek(max(0,path.stat().st_size-limit)); log_data=f.read(limit)
        job['log']=log_data[-30000:].decode('utf8','replace')
        if job['engine']=='bindcraft2':
            from bindcraft_cpu import progress_from_log,failure_from_log
            job['data']['executionProgress']=progress_from_log(log_data.decode('utf8','replace'))
            if job['state']=='failed':job['data']['failureDiagnostic']=failure_from_log(log_data.decode('utf8','replace'))
            if job['data'].get('memoryPolicy'):
                execution={}
                for key,name in (('telemetry','amme-memory.json'),('stage','amme-stage.json')):
                    report=path.parent/name
                    try:
                        if report.is_file() and not report.is_symlink() and report.stat().st_size<=1024**2:
                            value=json.loads(report.read_text())
                            if isinstance(value,dict):execution[key]=value
                    except (OSError,ValueError):pass
                job['data']['memoryExecution']=execution
        return job
    def job_cancel(self,p):
        job=self.job(p['id'])
        if job['state'] not in ['queued','running','installing']: return job
        if job['engine']=='bgmee':
            for id in job['data'].get('children',[]):
                child=self.job(id)
                if child['project_id']==job['project_id'] and child['data'].get('controllerId')==job['id']:self.job_cancel({'id':id})
        pid=job['data'].get('pid')
        if pid:
            # The stored PID must still have this exact worker and job in its command.
            try:
                args=subprocess.check_output(['/bin/ps','-p',str(pid),'-o','command='],text=True)
                if job['data'].get('workerPath',str(pathlib.Path(__file__).resolve())) in args and p['id'] in args: os.killpg(pid,signal.SIGTERM)
                else: raise ValueError('The original worker is no longer running; refresh the job state.')
            except (subprocess.CalledProcessError,ProcessLookupError): pass
        # The worker may have committed its results while cancellation was
        # locating the process. Preserve that completed transaction and outputs.
        self.db.execute('BEGIN IMMEDIATE')
        try:
            current=self.job(p['id'])
            if current['state'] in ['queued','running','installing']:
                current['data']['finished']=now()
                self.db.execute('UPDATE jobs SET state=?,data=?,updated=? WHERE id=?',('cancelled',json.dumps(current['data']),now(),p['id']))
            self.db.commit()
        except Exception:
            self.db.rollback(); raise
        return self.job(p['id'])
    def cloud_prepare(self,p):
        chains=parse_fasta(p['fasta'])
        if p.get('model','auto') not in ['auto','alphafold2_ptm','alphafold2_multimer_v3']: raise ValueError('Unsupported ColabFold model.')
        if p.get('msa','mmseqs2_uniref_env') not in ['mmseqs2_uniref_env','single_sequence']: raise ValueError('Unsupported ColabFold MSA mode.')
        if p.get('templates','none') not in ['none','pdb100']: raise ValueError('Unsupported template mode.')
        p.update({'chains':chains,'query_sequence':':'.join(c['sequence'] for c in chains),'notebook':COLAB_URL,'inputSha256':digest(json.dumps(chains,sort_keys=True)),'prepared':now()})
        job=self.job_new(p,'colabfold','prepared'); folder=self.root/'jobs'/job['id']; folder.mkdir(exist_ok=True)
        (folder/'input.fasta').write_text(p['fasta']); (folder/'parameters.json').write_text(json.dumps(p,indent=2))
        return job
    def cloud_opened(self,p):
        job=self.job(p['id'])
        if job['engine']!='colabfold': raise ValueError('This is not a cloud experiment.')
        self.job_update(p['id'],'awaiting_import',{'notebookOpened':now()}); return self.job(p['id'])
    def cloud_import(self,p):
        job=self.job(p['id'])
        if job['engine']!='colabfold': raise ValueError('Choose a ColabFold experiment.')
        path=pathlib.Path(p['path']); imported=[]; metadata=[]; jobfolder=self.root/'jobs'/job['id']
        if path.suffix.lower()=='.zip':
            if path.stat().st_size>512*1024**2: raise ValueError('Archive exceeds 512 MB.')
            with zipfile.ZipFile(path) as archive:
                entries=[i for i in archive.infolist() if not i.is_dir()]
                if len(entries)>500 or sum(i.file_size for i in entries)>512*1024**2: raise ValueError('Archive exceeds safe extraction limits.')
                folder=jobfolder/'imported'; folder.mkdir(exist_ok=True)
                for index,info in enumerate(entries):
                    filename=pathlib.PurePosixPath(info.filename)
                    if filename.is_absolute() or '..' in filename.parts: raise ValueError('Unsafe archive path.')
                    if info.file_size>MAX_FILE: raise ValueError('Archive member exceeds 100 MB.')
                    if filename.suffix.lower() not in ['.pdb','.cif','.mmcif','.json','.a3m','.csv','.txt']: continue
                    target=folder/(str(index)+'_'+filename.name); target.write_bytes(archive.read(info))
                    if target.suffix.lower() in ['.pdb','.cif','.mmcif']:
                        imported.append(self.import_structure({'projectId':job['project_id'],'path':str(target),'name':filename.name,'source':'ColabFold imported output','confidenceKind':'ColabFold pLDDT' if re.search(r'rank_\d+_alphafold2',filename.name) else None,'metadata':{'jobId':job['id'],'originalFilename':info.filename}}))
                    elif target.suffix.lower()=='.json':
                        try: metadata.append({'file':filename.name,'data':json.loads(target.read_text())})
                        except (ValueError,UnicodeDecodeError): pass
        else:
            imported.append(self.import_structure({'projectId':job['project_id'],'path':str(path),'source':'ColabFold imported output','confidenceKind':'ColabFold pLDDT' if re.search(r'rank_\d+_alphafold2',path.name) else None,'metadata':{'jobId':job['id']}}))
        if not imported: raise ValueError('No coordinate models in these results.')
        # Association does not certify that the imported sequences match prepared inputs.
        self.job_update(job['id'],'results_imported',{'outputs':[s['id'] for s in imported],'confidenceFiles':metadata,'imported':now(),'sequenceCorrespondence':'Verify by sequence alignment in the viewer; import alone does not prove correspondence.'})
        return {'job':self.job(job['id']),'structures':imported}
    def export_project(self,p):
        self.project(p['id']); library=self.library({}); data={'format':'fold-studio-project-v1','exported':now(),'project':self.project(p['id']),'records':[r for r in library['records'] if r['project_id']==p['id']],'jobs':[j for j in library['jobs'] if j['project_id']==p['id']]}
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE name='scientific_record_domains'").fetchone():
            data['scientificExecutionDomains']=[dict(row) for row in self.rows('SELECT d.* FROM scientific_record_domains d JOIN records r ON r.id=d.record_id WHERE r.project_id=? ORDER BY d.record_id,d.domain,d.source',(p['id'],))]
        research=Observatory(self)
        data['researchViews']=research.observatory_library({'projectId':p['id']})
        data['commandHistory']=research.console_history({'projectId':p['id']})
        Peptides(self)
        data['peptideVersions']=[{**v,'data':json.loads(v['data'])} for v in self.rows('SELECT v.* FROM peptide_versions v JOIN records r ON r.id=v.record_id WHERE r.project_id=?',(p['id'],))]
        if self.db.execute("SELECT 1 FROM sqlite_master WHERE name='molecular_drafts'").fetchone():
            data['molecularDrafts']=[{**v,'state':json.loads(v['state'])} for v in self.rows('SELECT * FROM molecular_drafts WHERE context=?',(p['id'],))]
            data['molecularMigrations']=[{**v,'original':json.loads(v['original'])} for v in self.rows('SELECT * FROM molecular_migrations WHERE context=?',(p['id'],))]
        data['constructionProgress']=[{**v,'state':json.loads(v['state'])} for v in self.rows('SELECT * FROM arcade_progress WHERE project_id=?',(p['id'],))]
        lab=intelligence.Lab(self)
        data['molecularIntelligence']={}
        for table in ['intelligence_tasks','intelligence_assignments','intelligence_candidates','intelligence_hotspots','intelligence_confidence']:
            data['molecularIntelligence'][table]=[{**r,'data':json.loads(r['data'])} for r in self.rows('SELECT * FROM '+table+' WHERE project_id=?',(p['id'],))]
        biology=evolution.Evolution(self)
        data['biologyGuidedDesign']=biology.evolution_list({'projectId':p['id']})
        data['biologyGuidedDesign']['manifests']=biology.evolution_manifests({'projectId':p['id']})
        for table in ('biology_modal_jobs','biology_evidence'):
            if self.db.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():data['biologyGuidedDesign'][table]=[json.loads(row['data']) for row in self.rows('SELECT data FROM '+table+' WHERE project_id=?',(p['id'],))]
        data['biologyGuidedDesign']['externalAPIRequests']=boltz_api_adapter.BoltzAPI(self).biology_boltz_jobs({'projectId':p['id']})
        path=pathlib.Path(p['path'])
        if path.suffix.lower()!='.zip': raise ValueError('Project exports use .zip.')
        assets={}
        def add_asset(name,expected):
            if not isinstance(name,str) or pathlib.Path(name).name!=name or not re.fullmatch('[a-f0-9]{64}',str(expected)):raise ValueError('Invalid saved research asset or integrity receipt.')
            source=self.root/'assets'/name
            if source.is_symlink() or not source.is_file() or source.stat().st_size>MAX_FILE:raise ValueError('Saved research asset is missing or exceeds the archive limit: '+name)
            if name in assets and assets[name][1]!=expected:raise ValueError('Conflicting saved asset integrity receipts.')
            assets[name]=(source,expected)
        for record in data['records']:
            if record['data'].get('domain') in ('sequencing_reads','genomic_alignment','indexed_genome'):
                source=record['data']['sourceFile']
                if source.get('bytes',0)>MAX_FILE:raise ValueError('This managed genomic source exceeds the 100 MiB portable archive member limit. Export its original FASTA separately; no incomplete project archive will be produced.')
                add_asset(source['asset'],source['sha256'])
                if source.get('indexAsset'):add_asset(source['indexAsset'],source['indexSha256'])
            if record['kind']=='structure':
                add_asset(record['data']['asset'],record['data']['sha256'])
                ligand=record['data'].get('metadata',{}).get('ligand',{})
                if ligand.get('sdfAsset'):add_asset(ligand['sdfAsset'],ligand['sdfSha256'])
        for entry in data['researchViews']:
            if entry['kind']=='scene' and entry['data'].get('engine')=='chimerax':add_asset(entry['data']['asset'],entry['data']['sha256'])
        temporary=path.with_name('.'+path.name+'.'+uid()+'.tmp')
        try:
            with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as z:
                data['assetManifest']=[]
                for name,(source,expected) in assets.items():
                    digest=hashlib.sha256();size=0
                    with source.open('rb') as original,z.open('assets/'+name,'w') as saved:
                        while block:=original.read(1024**2):
                            size+=len(block)
                            if size>MAX_FILE:raise ValueError('Saved research asset grew beyond the archive limit.')
                            digest.update(block);saved.write(block)
                    if digest.hexdigest()!=expected:raise ValueError('A saved research asset checksum changed: '+name)
                    data['assetManifest'].append({'file':'assets/'+name,'sha256':expected,'bytes':size})
                for task in data['molecularIntelligence']['intelligence_tasks']:
                    if task['result'] and pathlib.Path(task['result']).name==task['result']:
                        result=lab.root/task['result']
                        if result.is_file():z.write(result,'intelligence/'+result.name)
                for confidence in data['molecularIntelligence']['intelligence_confidence']:
                    for source in confidence['data'].get('sources',[]):
                        if re.fullmatch('[a-f0-9]{64}',str(source.get('sha256',''))):
                            file=lab.root/('confidence-'+source['sha256']+'.json')
                            if file.is_file():z.write(file,'intelligence/'+file.name)
                for job in data['jobs']:
                    folder=self.root/'jobs'/job['id']
                    if folder.exists():
                        for file in folder.rglob('*'):
                            if file.is_file() and file.stat().st_size<=MAX_FILE:z.write(file,'jobs/'+job['id']+'/'+str(file.relative_to(folder)))
                data['genomeReferences']=genome_workspace.export_references(self,p['id'],z)
                data['importedArchives']=project_restore.export_snapshots(self,p['id'],z)
                z.writestr('project.json',json.dumps(data,indent=2))
            temporary.replace(path)
        finally:temporary.unlink(missing_ok=True)
        return str(path)
    def project_archive_inspect(self,p):
        return project_archive.inspect_archive(p)
    def project_archive_import(self,p):
        return project_restore.import_archive(self,p)
    def project_archive_snapshots(self,p):
        return project_restore.list_snapshots(self,p)
    def project_archive_snapshot_read(self,p):
        return project_restore.read_snapshot(self,p)
    def project_archive_original_export(self,p):
        return project_restore.export_original(self,p)
    def export_file(self,p):
        path=pathlib.Path(p['path'])
        if path.suffix.lower() not in ['.json','.fasta','.fa','.png','.svg','.pdb','.cif','.mmcif','.txt','.py','.cxc','.pdf','.csv','.tsv','.md','.sdf']: raise ValueError('Unsupported export format.')
        if p.get('asset'):
            asset=str(p['asset'])
            if pathlib.Path(asset).name!=asset: raise ValueError('Invalid asset identifier.')
            shutil.copyfile(self.root/'assets'/asset,path)
        elif p.get('base64'):
            data=base64.b64decode(p['base64'],validate=True)
            if len(data)>MAX_FILE: raise ValueError('Export exceeds 100 MB.')
            path.write_bytes(data)
        else: path.write_text(p.get('text',''))
        return str(path)
    def reconcile(self,p):
        for job in self.rows("SELECT * FROM jobs WHERE state IN ('queued','running','installing')"):
            data=json.loads(job['data']); pid=data.get('pid')
            if pid:
                try: os.kill(pid,0)
                except ProcessLookupError: self.job_update(job['id'],'interrupted',{'error':'Worker stopped before completion; review logs and start a new job.'})
        return True
    def dispatch(self,action,p):
        if action not in ACTIONS: raise ValueError('Unsupported scientific action.')
        if action in cloud_shell.ACTIONS:return cloud_shell.dispatch(self,action,p)
        if action in cloud_accounts.ACTIONS:return cloud_accounts.dispatch(self,action,p)
        if action in genome_workspace.ACTIONS:return genome_workspace.dispatch(self,action,p)
        if action in molecular_observatory.ACTIONS:return molecular_observatory.dispatch(self,action,p)
        if action in editcraft.ACTIONS:return editcraft.dispatch(self,action,p)
        if action in cloud_monitor.ACTIONS:return cloud_monitor.dispatch(self,action,p)
        if action in cloud_audit.ACTIONS:return cloud_audit.dispatch(self,action,p)
        if action in cloud_deployment.ACTIONS:return cloud_deployment.dispatch(self,action,p)
        if action in execution_policy.ACTIONS:return execution_policy.dispatch(self,action,p)
        execution_policy.enforce(self,action,p)
        if action in periodic_dynamics.ACTIONS:return periodic_dynamics.dispatch(self,action,p)
        if action in genomic_io.ACTIONS:return genomic_io.dispatch(self,action,p)
        if action in chemical_screen.ACTIONS:return chemical_screen.dispatch(self,action,p)
        if action in sequence_alignment.ACTIONS:return sequence_alignment.dispatch(self,action,p)
        if action in sequence_reads.ACTIONS:return sequence_reads.dispatch(self,action,p)
        if action in quantum_engine.ACTIONS:return quantum_engine.dispatch(self,action,p)
        if action in biology_evidence.ACTIONS:return biology_evidence.dispatch(self,action,p)
        if action in biology_agent.ACTIONS:return biology_agent.dispatch(self,action,p)
        if action in peptide_chemistry.ACTIONS:return peptide_chemistry.dispatch(self,action,p)
        if action in modal_account.ACTIONS:return modal_account.dispatch(self,action,p)
        if action in biology_modal.ACTIONS:return biology_modal.dispatch(self,action,p)
        if action in biology_pipeline.ACTIONS: return biology_pipeline.dispatch(self,action,p)
        if action in boltz_api_adapter.ACTIONS: return boltz_api_adapter.dispatch(self,action,p)
        if action in evolution.ACTIONS: return evolution.dispatch(self,action,p)
        if action in research.ACTIONS: return research.dispatch(self,action,p)
        if action in cinema.ACTIONS: return cinema.dispatch(self,action,p)
        if action in rapid_remote.ACTIONS: return rapid_remote.dispatch(self,action,p)
        if action in cloud_compute.ACTIONS: return cloud_compute.dispatch(self,action,p)
        if action in ligand.ACTIONS: return ligand.dispatch(self,action,p)
        if action in dynamics.ACTIONS: return dynamics.dispatch(self,action,p)
        if action in mpnn.ACTIONS: return mpnn.dispatch(self,action,p)
        if action in fold_engine.ACTIONS: return fold_engine.Engine(self).dispatch(action,p)
        if action in intelligence.ACTIONS: return intelligence.Lab(self).dispatch(action,p)
        if action in OBSERVATORY_ACTIONS: return Observatory(self).dispatch(action,p)
        if action in molecular_graph.ACTIONS: return molecular_graph.dispatch(self,action,p)
        if action in PEPTIDE_ACTIONS: return Peptides(self).dispatch(action,p)
        return getattr(self,action)(p)

ACTIONS={'record_update','record_remove','record_restore','library','setting_set','project_create','project_update','project_delete','record_save','sequence_save','mutate','fasta_parse','fasta_import','uniprot_search','uniprot_get','structures','structure_download','import_structure','asset_read','compute','install_engine','prediction_start','prediction_resources','job_read','job_cancel','cloud_prepare','cloud_opened','cloud_import','export_project','project_archive_inspect','project_archive_import','project_archive_snapshots','project_archive_snapshot_read','project_archive_original_export','export_file','reconcile'}

ACTIONS |= periodic_dynamics.ACTIONS | genomic_io.ACTIONS | chemical_screen.ACTIONS | sequence_alignment.ACTIONS | sequence_reads.ACTIONS | quantum_engine.ACTIONS | genome_workspace.ACTIONS | molecular_observatory.ACTIONS | editcraft.ACTIONS | cloud_shell.ACTIONS | cloud_accounts.ACTIONS | cloud_monitor.ACTIONS | cloud_audit.ACTIONS | cloud_deployment.ACTIONS | execution_policy.ACTIONS | modal_account.ACTIONS | peptide_chemistry.ACTIONS | biology_modal.ACTIONS | biology_agent.ACTIONS | biology_evidence.ACTIONS | biology_pipeline.ACTIONS | boltz_api_adapter.ACTIONS | evolution.ACTIONS | research.ACTIONS | cinema.ACTIONS | rapid_remote.ACTIONS | cloud_compute.ACTIONS | dynamics.ACTIONS | ligand.ACTIONS | mpnn.ACTIONS | fold_engine.ACTIONS | OBSERVATORY_ACTIONS | PEPTIDE_ACTIONS | molecular_graph.ACTIONS | intelligence.ACTIONS

def execute_job(service,id):
    job=service.job(id); p=job['data']; folder=service.root/'jobs'/id
    import scientific_capabilities
    scientific_capabilities.enforce(service,'prediction_start',p)
    service.job_update(id,'running',{'started':now()})
    def cancelled(signum,frame):
        service.job_update(id,'cancelled',{'finished':now()}); raise SystemExit(143)
    signal.signal(signal.SIGTERM,cancelled)
    try:
        lines=['version: 1','sequences:']
        for i,chain in enumerate(p['chains']):
            lines += ['  - protein:','      id: '+chr(65+i),'      sequence: '+chain['sequence']]
            if p['msa']=='single': lines += ['      msa: empty']
        inputfile=folder/'input.yaml'; inputfile.write_text('\n'.join(lines)+'\n')
        from boltz_resources import fingerprints,receipt,ensure_checkpoint
        checkpoint_pin=ensure_checkpoint(service.root/'engine/models')
        before_resources=fingerprints(service.root/'engine/models',p['chains'])
        command=[service.engine_python(),'-B','-c','from boltz.main import cli; cli()','predict',str(inputfile),'--accelerator','mps','--model','boltz2','--cache',str(service.root/'engine/models'),'--out_dir',str(folder/'output'),'--output_format','mmcif','--recycling_steps',str(p['recycles']),'--sampling_steps',str(p['steps']),'--diffusion_samples',str(p['samples']),'--max_parallel_samples','1','--num_workers','0','--seed',str(p['seed'])]
        if p['msa']=='server': command += ['--use_msa_server']
        environment=dict(os.environ,PYTORCH_ENABLE_MPS_FALLBACK='1',PYTHONUNBUFFERED='1',OMP_NUM_THREADS='4',WANDB_MODE='disabled',NUMBA_CACHE_DIR=str(service.root/'engine/cache/numba'))
        provenance={**p,'command':command,'environment':{k:environment[k] for k in ['PYTORCH_ENABLE_MPS_FALLBACK','OMP_NUM_THREADS','WANDB_MODE','NUMBA_CACHE_DIR']},'inputYamlSha256':digest(inputfile.read_text())}
        (folder/'provenance.json').write_text(json.dumps(provenance,indent=2)); print('Starting Boltz-2 MPS inference. No synthetic progress.\n'+json.dumps(command),flush=True)
        proc=subprocess.run(command,env=environment)
        if proc.returncode: raise RuntimeError('Boltz exited with code '+str(proc.returncode)+'. Review the execution log. Reduce sequence size for out-of-memory errors.')
        provenance['modelResources']=receipt(before_resources,fingerprints(service.root/'engine/models',p['chains']),checkpoint_pin)
        (folder/'provenance.json').write_text(json.dumps(provenance,indent=2))
        outputdir=folder/'output'/('boltz_results_'+inputfile.stem)/'predictions'
        outputs=[]; metrics=[]
        for file in sorted(outputdir.rglob('*')):
            if file.suffix.lower() in ['.cif','.pdb']:
                outputs.append(service.import_structure({'projectId':job['project_id'],'path':str(file),'name':job['name']+' · '+file.name,'source':'Local Boltz-2 MPS prediction','confidenceKind':'Boltz-2 pLDDT','metadata':{'jobId':id,'originalFilename':file.name,'provenance':provenance}}))
            elif file.suffix=='.json': metrics.append({'file':file.name,'data':json.loads(file.read_text())})
        if not outputs: raise RuntimeError('Engine exited successfully but no coordinate output was found.')
        service.job_update(id,'completed',{'outputs':[s['id'] for s in outputs],'confidenceFiles':metrics,'finished':now(),'provenance':provenance})
        service.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('validatedMPS',json.dumps({'jobId':id,'date':now(),'version':p['engineVersion']}))); service.db.commit()
        try:
            analysis_ids=intelligence.Lab(service).auto_prediction(service.job(id),outputs)
            if analysis_ids:service.job_update(id,'completed',{'intelligenceAnalyses':analysis_ids})
        except Exception as analysis_error:
            service.job_update(id,'completed',{'intelligenceAnalysisError':str(analysis_error)})
        print('Inference completed; '+str(len(outputs))+' genuine coordinate model(s) imported.',flush=True)
    except Exception as error:
        service.job_update(id,'failed',{'error':str(error),'finished':now()}); print('ERROR:',error,flush=True)
        raise

def install(service,id):
    signal.signal(signal.SIGTERM,lambda a,b:sys.exit(143))
    try:
        engine=service.root/'engine'; uv=engine/'uv'
        if not uv.exists():
            import tarfile, io
            url='https://github.com/astral-sh/uv/releases/download/0.8.22/uv-aarch64-apple-darwin.tar.gz'
            print('Downloading uv 0.8.22 from the official Astral release.',flush=True)
            with urllib.request.urlopen(url,timeout=120) as response: archive=response.read(30*1024**2)
            with tarfile.open(fileobj=io.BytesIO(archive),mode='r:gz') as tar:
                member=next(m for m in tar.getmembers() if pathlib.PurePosixPath(m.name).name=='uv' and m.isfile())
                uv.write_bytes(tar.extractfile(member).read()); uv.chmod(0o755)
        environment=dict(os.environ,UV_PYTHON_INSTALL_DIR=str(engine/'python'),UV_CACHE_DIR=str(engine/'uv-cache'))
        # Stage each setup separately; switch only after diagnostics succeed.
        venv=engine/'environments'/id
        requirements=pathlib.Path(__file__).parent/'requirements-tested-macos-arm64.txt'
        dependencies=['-r',str(requirements)] if requirements.exists() else ['boltz-community=='+ENGINE_VERSION]
        commands=[[str(uv),'python','install','3.12'],[str(uv),'venv','--python','3.12',str(venv)],[str(uv),'pip','install','--python',str(venv/'bin/python'),*dependencies],[str(venv/'bin/boltz-fix-macos-libomp')]]
        for command in commands:
            print('Setup:',json.dumps(command),flush=True); subprocess.run(command,check=True,env=environment)
        status=service.compute_for(str(venv/'bin/python'))
        if not status['installed'] or not status['mpsAvailable']: raise RuntimeError('Dependencies installed, but MPS is unavailable. '+str(status.get('error','')))
        with open(engine/'installed-requirements.txt','w') as requirements:
            subprocess.run([str(uv),'pip','freeze','--python',str(venv/'bin/python')],stdout=requirements,check=True,env=environment)
        service.setting_set({'key':'enginePython','value':str(venv/'bin/python')})
        service.job_update(id,'completed',{'finished':now(),'compute':status})
        print('Engine installed. Run a small test prediction to verify inference. Weights download on first prediction.',flush=True)
    except Exception as error:
        service.job_update(id,'failed',{'error':str(error),'finished':now()}); print('SETUP ERROR:',error,flush=True); raise

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--root',required=True); parser.add_argument('--fixtures'); parser.add_argument('--run-job'); parser.add_argument('--install'); parser.add_argument('--serve',type=int); parser.add_argument('--intelligence-job'); parser.add_argument('--mpnn-job'); parser.add_argument('--bindcraft-cpu-job'); parser.add_argument('--ligand-job'); parser.add_argument('--dynamics-job'); parser.add_argument('--biology-job'); parser.add_argument('--peptide-chemistry-job')
    args=parser.parse_args(); service=Service(args.root,args.fixtures)
    if args.peptide_chemistry_job:peptide_chemistry.run(service,args.peptide_chemistry_job);return
    if args.biology_job:biology_pipeline.run(service,args.biology_job);return
    if args.bindcraft_cpu_job:
        import bindcraft_cpu
        bindcraft_cpu.run(service,args.bindcraft_cpu_job); return
    if args.ligand_job: ligand.run(service,args.ligand_job); return
    if args.dynamics_job: dynamics.run(service,args.dynamics_job); return
    if args.mpnn_job: mpnn.run(service,args.mpnn_job); return
    if args.intelligence_job: intelligence.Lab(service).run(args.intelligence_job); return
    if args.run_job: execute_job(service,args.run_job); return
    if args.install: install(service,args.install); return
    if args.serve:
        # Development preview only, bound to localhost with Origin and bearer checks.
        from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
        root,fixtures=args.root,args.fixtures
        token=os.environ.get('FOLD_DEV_TOKEN')
        if not token: raise ValueError('Set FOLD_DEV_TOKEN for the development preview.')
        class Handler(BaseHTTPRequestHandler):
            def send_cors_headers(self):
                self.send_header('Access-Control-Allow-Origin','http://127.0.0.1:1424'); self.send_header('Access-Control-Allow-Headers','Content-Type,Authorization'); self.send_header('Access-Control-Allow-Methods','POST,OPTIONS'); self.end_headers()
            def do_OPTIONS(self): self.send_response(204); self.send_cors_headers()
            def do_POST(self):
                if self.headers.get('Origin')!='http://127.0.0.1:1424' or self.headers.get('Authorization')!='Bearer '+token:
                    self.send_response(403); self.send_cors_headers(); return
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if size>2*1024**2: raise ValueError('Request too large.')
                    request=json.loads(self.rfile.read(size)); svc=Service(root,fixtures)
                    if request['action']=='preview_confidence_export':
                        export_dir=os.environ.get('FOLD_DEV_EXPORT_DIR')
                        if not export_dir:raise ValueError('Preview exports are not configured.')
                        payload=request.get('payload',{});kind=payload.get('kind','pae')
                        if kind not in ['pae','pde']:raise ValueError('Choose PAE or predicted distance error.')
                        pathlib.Path(export_dir).mkdir(parents=True,exist_ok=True)
                        result=svc.dispatch('confidence_export',{**payload,'path':str(pathlib.Path(export_dir)/('fold-confidence-'+kind+'.json'))})
                    elif request['action']=='preview_export':
                        export_dir=os.environ.get('FOLD_DEV_EXPORT_DIR')
                        if not export_dir: raise ValueError('Preview exports are not configured.')
                        payload=request.get('payload',{}); name=payload.pop('name')
                        if pathlib.Path(name).name!=name: raise ValueError('Invalid preview filename.')
                        pathlib.Path(export_dir).mkdir(parents=True,exist_ok=True)
                        result=svc.export_file({**payload,'path':str(pathlib.Path(export_dir)/name)})
                    else: result=svc.dispatch(request['action'],request.get('payload',{}))
                    self.send_response(200); self.send_cors_headers(); self.wfile.write(json.dumps({'result':result}).encode())
                except Exception as error:
                    self.send_response(400); self.send_cors_headers(); self.wfile.write(json.dumps({'error':str(error)}).encode())
        ThreadingHTTPServer(('127.0.0.1',args.serve),Handler).serve_forever(); return
    try:
        request=json.load(sys.stdin); print(json.dumps({'result':service.dispatch(request['action'],request.get('payload',{}))}))
    except Exception as error: print(json.dumps({'error':str(error)})); sys.exit(1)
if __name__=='__main__': main()
