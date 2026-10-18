"""Versioned research views and genuine authenticated ChimeraX REST transport."""
import datetime, hashlib, json, math, os, pathlib, plistlib, re, secrets, socket, subprocess, time, urllib.error, urllib.parse, urllib.request, uuid
from confidence import local_confidence

ACTIONS={'observatory_library','observatory_save','observatory_delete','console_history','console_record','console_clear','console_sync','chimerax_measure','chimerax_scene','chimerax_camera','chimerax_selection','chimerax_python','chimerax_inventory','chimerax_status','chimerax_start','chimerax_catalog','chimerax_execute','chimerax_open','chimerax_state','chimerax_atoms','chimerax_session_save','chimerax_session_restore','chimerax_import','chimerax_focus','chimerax_select','confidence_fetch','confidence_export','comparison_run'}
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def uid():return str(uuid.uuid4())
def native_quote(value):
    value=str(value)
    if '\n' in value or '\r' in value or '\x00' in value:raise ValueError('Invalid command argument.')
    return '"'+value.replace('\\','\\\\').replace('"','\\"')+'"'
def command_risk(command):
    # This controls review, never the installed command repertoire. Unknown
    # commands and aliases remain executable after deliberate user confirmation.
    safe={'select','color','colour','show','hide','cartoon','surface','style','transparency','lighting','view','zoom','turn','move','distance','angle','info','usage','help','version','hbonds','contacts','clashes','measure','matchmaker','rmsd','label','2dlabels'}
    pieces=re.split(r'[;\n]',command)
    unsafe=[p.strip().split()[0] for p in pieces if p.strip() and p.strip().split()[0].lower() not in safe]
    return {'requiresReview':bool(unsafe),'reason':'These commands may change models, files, software, or execute scripts: '+', '.join(unsafe) if unsafe else ''}

class Observatory:
    def __init__(self,service):
        self.s=service;self.root=service.root/'observatory';self.root.mkdir(exist_ok=True);self.root.chmod(0o700)
        self.s.db.executescript('''CREATE TABLE IF NOT EXISTS observatory_entries(id TEXT PRIMARY KEY,project_id TEXT,kind TEXT,name TEXT,data TEXT,created TEXT,updated TEXT);
        CREATE TABLE IF NOT EXISTS observatory_commands(id TEXT PRIMARY KEY,project_id TEXT,engine TEXT,command TEXT,state TEXT,data TEXT,created TEXT);''')
        self.descriptor=self.root/'chimerax-headless-session.json'
    def dispatch(self,action,p):return getattr(self,action)(p)
    def observatory_library(self,p):
        rows=self.s.rows('SELECT * FROM observatory_entries WHERE project_id=? OR project_id IS NULL ORDER BY updated DESC',(p.get('projectId'),))
        for r in rows:r['data']=json.loads(r['data'])
        return rows
    def observatory_save(self,p):
        if p['kind'] not in {'scene','macro','layout','notebook','timeline','analysis','editing_document'}:raise ValueError('Unsupported research entry.')
        if p.get('projectId'):self.s.project(p['projectId'])
        name=str(p.get('name','')).strip()[:200]
        if not name:raise ValueError('Name the research entry.')
        data=json.dumps(p.get('data',{}))
        if len(data)>2*1024**2:raise ValueError('Research metadata exceeds 2 MB.')
        id=p.get('id') or uid();row=self.s.db.execute('SELECT * FROM observatory_entries WHERE id=?',(id,)).fetchone();created=row['created'] if row else now()
        self.s.db.execute('INSERT OR REPLACE INTO observatory_entries VALUES(?,?,?,?,?,?,?)',(id,p.get('projectId'),p['kind'],name,data,created,now()));self.s.db.commit()
        return {'id':id,'project_id':p.get('projectId'),'kind':p['kind'],'name':name,'data':json.loads(data),'created':created}
    def observatory_delete(self,p):
        self.s.db.execute('DELETE FROM observatory_entries WHERE id=?',(p['id'],));self.s.db.commit();return True
    def console_history(self,p):
        rows=self.s.rows('SELECT * FROM observatory_commands WHERE project_id=? ORDER BY created DESC LIMIT 300',(p.get('projectId'),))
        for r in rows:r['data']=json.loads(r['data'])
        return rows
    def console_record(self,p):
        self.s.project(p['projectId']);id=uid()
        self.s.db.execute('INSERT INTO observatory_commands VALUES(?,?,?,?,?,?,?)',(id,p['projectId'],p.get('engine','viewer'),p['command'],p.get('state','completed'),json.dumps(p.get('data',{})),now()));self.s.db.commit();return id
    def console_clear(self,p):
        if not p.get('confirmed'):raise ValueError('Confirm clearing the project command history.')
        self.s.db.execute('DELETE FROM observatory_commands WHERE project_id=?',(p['projectId'],));self.s.db.commit();return True
    def console_sync(self,p):
        row=self.s.db.execute('SELECT data FROM observatory_commands WHERE id=? AND project_id=?',(p['id'],p['projectId'])).fetchone()
        if not row:raise ValueError('The native command record is missing.')
        data=json.loads(row['data']);data['syncStatus']=str(p['status'])[:300];data['viewerSyncVerified']=now()
        self.s.db.execute('UPDATE observatory_commands SET data=? WHERE id=?',(json.dumps(data),p['id']));self.s.db.commit();return True
    def installations(self):
        candidates=list(pathlib.Path('/Applications').glob('*ChimeraX*.app'))+list((pathlib.Path.home()/'Applications').glob('*ChimeraX*.app'))
        result=[]
        for app in candidates:
            executable=app/'Contents/MacOS/ChimeraX'
            if not executable.is_file():continue
            try:metadata=plistlib.loads((app/'Contents/Info.plist').read_bytes())
            except Exception:metadata={}
            result.append({'app':str(app),'executable':str(executable),'version':metadata.get('CFBundleShortVersionString','Unknown')})
        return sorted(result,key=lambda x:x['version'],reverse=True)
    def write_connection(self,data):
        temporary=self.root/('session-'+uid()+'.tmp')
        descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'w') as file:file.write(json.dumps(data))
        os.replace(temporary,self.descriptor)
    def connection(self):
        if not self.descriptor.exists():raise ValueError('Start the authenticated ChimeraX session first.')
        data=json.loads(self.descriptor.read_text())
        if not 1024<=int(data['port'])<=65535:raise ValueError('Invalid local connection port.')
        return data
    def request(self,path,command=None,timeout=20,payload=None):
        c=self.connection();url='http://127.0.0.1:'+str(c['port'])+path
        body=None
        headers={'Authorization':'Bearer '+c['token'],'Accept':'application/json'}
        if command is not None:
            boundary='fold'+secrets.token_hex(16)
            # Each physical line is a separate command value for the official
            # REST executor. Preserve semicolons and native syntax within lines.
            commands=[line for line in command.splitlines() if line.strip() and not line.lstrip().startswith('#')]
            body=(''.join('--'+boundary+'\r\nContent-Disposition: form-data; name="command"\r\n\r\n'+line+'\r\n' for line in commands)+'--'+boundary+'--\r\n').encode('utf-8')
            headers['Content-Type']='multipart/form-data; boundary='+boundary
        if payload is not None:
            body=json.dumps(payload,allow_nan=False).encode();headers['Content-Type']='application/json'
        request=urllib.request.Request(url,data=body,headers=headers)
        try:
            with urllib.request.urlopen(request,timeout=timeout) as response:
                limit=96*1024**2 if path.startswith('/fold/scene') else 10*1024**2
                raw=response.read(limit+1)
                if len(raw)>limit:raise ValueError('Native response exceeds the bounded transfer limit.')
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            try:detail=json.loads(error.read(65536)).get('error',str(error))
            except Exception:detail=str(error)
            finally:error.close()
            raise ValueError('Scientific engine: '+str(detail)) from error
    def chimerax_status(self,p):
        installed=self.installations();running=False
        if installed:
            try:
                process_list=subprocess.run(['/bin/ps','-axo','comm='],capture_output=True,text=True,timeout=2).stdout.splitlines()
                running=any('ChimeraX' in name and '.app/Contents/' in name for name in process_list)
            except Exception:pass
        result={'installations':installed,'state':('running_not_connected' if running else 'installed_not_running') if installed else 'not_installed','connected':False}
        try:
            current=self.request('/fold/session',timeout=2);c=self.connection()
            if current['sessionId']!=c['sessionId']:raise ValueError('The port belongs to another ChimeraX session.')
            result.update(current,connected=True,state='connected',port=c['port'],pid=c.get('pid'))
        except Exception as error:
            if self.descriptor.exists():
                result['error']=str(error)
                try:
                    c=self.connection();command=subprocess.run(['/bin/ps','-p',str(int(c['pid'])),'-o','command='],capture_output=True,text=True,timeout=2).stdout
                    if str(self.descriptor) in command and 'chimerax_session.py' in command:
                        result.update(state='starting_or_busy',pid=c['pid'],sessionId=c['sessionId'],note='The managed session is still running. It may be starting or executing a native operation; no second session will be launched.')
                except Exception:pass
        return result
    def chimerax_start(self,p):
        existing=self.chimerax_status({})
        if existing['connected']:
            if existing.get('gui'):raise ValueError('A GUI session cannot be used as the background engine.')
            return existing
        if existing['state']=='starting_or_busy':return existing
        installed=self.installations()
        if not installed:raise ValueError('Install your separately licensed copy of UCSF ChimeraX first.')
        compatible=[i for i in installed if i['version'].startswith('1.12')]
        if not compatible:raise ValueError('This adapter is pinned to ChimeraX 1.12. Keep that licensed installation in Applications.')
        chosen=next((i for i in compatible if i['executable']==p.get('executable')),compatible[0])
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        config={'sessionId':uid(),'token':secrets.token_urlsafe(48),'port':port,'executable':chosen['executable'],'created':now(),'headless':True,'ownerPid':os.environ.get('FOLD_HOST_PID')}
        self.write_connection(config)
        helper=pathlib.Path(__file__).parent/'chimerax_session.py'
        command=[chosen['executable'],'--nogui','--notools','--script',native_quote(helper)+' '+native_quote(self.descriptor)]
        with open(self.root/'chimerax.log','ab',buffering=0) as log:
            process=subprocess.Popen(command,stdout=log,stderr=log,start_new_session=True,stdin=subprocess.DEVNULL)
        config['pid']=process.pid;self.write_connection(config)
        return {'state':'starting','pid':process.pid,'sessionId':config['sessionId'],'installation':chosen}
    def chimerax_catalog(self,p):
        status=self.chimerax_status({})
        if not status['connected']:raise ValueError('ChimeraX is not connected.')
        result=self.request('/fold/catalog',timeout=120);return {**result,'version':status['version'],'sessionId':status['sessionId']}
    def chimerax_state(self,p):
        result=self.request('/fold/state')
        result['mapping']=[m for m in self.s.setting('chimeraxMapping',[]) if m['sessionId']==result['sessionId']]
        return result
    def chimerax_atoms(self,p):
        model=str(p['modelId'])
        if not re.fullmatch(r'\d+(?:\.\d+)*',model):raise ValueError('Use an actual native model ID.')
        return self.request('/fold/atoms?model='+model)
    def chimerax_session_save(self,p):
        self.s.project(p['projectId'])
        name='native-session-'+uid()+'.cxs';path=self.s.root/'assets'/name
        result=self.chimerax_execute({**p,'command':'save '+native_quote(path),'confirmed':True})
        if result['state']!='completed' or not path.is_file():raise ValueError('The native ChimeraX session was not saved: '+str(result.get('output',result)))
        data={'engine':'chimerax','asset':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'runtimeVersion':result['version']}
        return self.observatory_save({'projectId':p['projectId'],'kind':'scene','name':p.get('name','ChimeraX native session'),'data':data})
    def chimerax_session_restore(self,p):
        if not p.get('confirmed'):raise ValueError('Confirm replacing the native session with this trusted saved session.')
        entry=next((e for e in self.observatory_library(p) if e['id']==p['id'] and e['project_id']==p['projectId'] and e['kind']=='scene' and e['data'].get('engine')=='chimerax'),None)
        if not entry:raise ValueError('The saved native project session is missing.')
        asset=entry['data']['asset'];path=self.s.root/'assets'/asset
        if pathlib.Path(asset).name!=asset or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['data']['sha256']:raise ValueError('The saved session checksum changed.')
        return self.chimerax_execute({**p,'command':'open '+native_quote(path),'confirmed':True})
    def confidence_fetch(self,p):
        record=self.item(p['structureId']);url=record['data'].get('metadata',{}).get('paeDocUrl')
        if record['data'].get('metadata',{}).get('jobId') and record['data'].get('confidenceKind')=='Boltz-2 pLDDT':
            return local_confidence(self.s,record,p.get('kind','pae'))
        if p.get('kind','pae')!='pae':raise ValueError('This provider has no supported predicted distance-error source.')
        if not url:raise ValueError('This source has no PAE JSON URL. No confidence matrix was synthesized.')
        raw=self.s.cached_fetch(url);data=raw[0] if isinstance(raw,list) else raw
        matrix=data.get('predicted_aligned_error')
        if not isinstance(matrix,list) or not matrix or len(matrix)>4000 or any(not isinstance(row,list) or len(row)!=len(matrix) for row in matrix):raise ValueError('The provider returned an unsupported PAE matrix.')
        if any(not isinstance(v,(int,float)) or not 0<=v<=1000 for row in matrix for v in row):raise ValueError('Invalid provider PAE values.')
        return {'kind':'pae','matrix':matrix,'source':url,'structureId':record['id'],'sourceSha256':record['data']['sha256'],'accession':record['data'].get('accession'),'maximum':data.get('max_predicted_aligned_error'),'method':'Provider predicted aligned error, Å; row/column positions refer to this model sequence.'}
    def confidence_export(self,p):
        if pathlib.Path(p['path']).suffix.lower()!='.json':raise ValueError('Export confidence data as JSON.')
        data=self.confidence_fetch(p)
        text=json.dumps(data,allow_nan=False)
        if len(text.encode())>100*1024**2:raise ValueError('Confidence export exceeds 100 MB.')
        return self.s.export_file({'path':p['path'],'text':text})
    def comparison_run(self,p):
        self.s.project(p['projectId'])
        moving=self.item(p['structureId']);reference=self.item(p['referenceId'])
        if moving['id']==reference['id']:raise ValueError('Choose two distinct saved coordinate assets.')
        if any(record['project_id']!=p['projectId'] for record in (moving,reference)):raise ValueError('Both structures must belong to the selected project.')
        cutoff=p.get('cutoff',2)
        if cutoff is not None and (isinstance(cutoff,bool) or not isinstance(cutoff,(int,float)) or not math.isfinite(cutoff) or not 0.1<=cutoff<=20):raise ValueError('Choose a pruning cutoff from 0.1 to 20 Å, or no pruning.')
        chains=[str(p.get(key,'')).strip() for key in ('movingChain','referenceChain')]
        if any(chain and not re.fullmatch(r'[A-Za-z0-9_]+',chain) for chain in chains):raise ValueError('Use simple native chain IDs here; complex IDs require the native console.')
        status=self.chimerax_status({})
        if not status['connected']:raise ValueError('Start the authenticated ChimeraX session first.')
        if status.get('bridgeVersion',1)<2:raise ValueError('This connected session uses the earlier bridge. Close that managed session and start it again to enable measured comparison.')
        mappings=[]
        for record in (moving,reference):
            asset=(self.s.root/'assets'/record['data']['asset']).resolve()
            if not asset.is_relative_to(self.s.root/'assets') or not asset.is_file() or hashlib.sha256(asset.read_bytes()).hexdigest()!=record['data']['sha256']:raise ValueError('A saved coordinate checksum changed; comparison was refused.')
            opened=self.chimerax_open({'projectId':p['projectId'],'structureId':record['id']})
            if opened.get('state')!='completed' or len(opened.get('mapping',[]))!=1:raise ValueError('The source has multiple native models or failed to open. Choose explicit models in the native console.')
            mappings.append(opened['mapping'][0])
        parameters={'moving':mappings[0]['modelId'],'reference':mappings[1]['modelId'],'movingChain':chains[0],'referenceChain':chains[1],'cutoff':'none' if cutoff is None else str(cutoff)}
        start=time.monotonic()
        result=self.request('/fold/compare?'+urllib.parse.urlencode(parameters),timeout=120)
        result.update({'sourceStructures':[{'id':record['id'],'name':record['name'],'sha256':record['data']['sha256']} for record in (moving,reference)],'projectId':p['projectId'],'created':now(),'latencyMs':round((time.monotonic()-start)*1000,1),'method':'Installed ChimeraX Matchmaker: native sequence/structure alignment and rigid superposition of Cα atoms','syncStatus':'Native superposition executed; awaiting the FOLD scene adapter. Saved source assets remain unchanged.'})
        history=self.console_record({'projectId':p['projectId'],'engine':'chimerax','command':result['command'],'state':'completed','data':result})
        entry=self.observatory_save({'projectId':p['projectId'],'kind':'analysis','name':moving['name']+' vs '+reference['name'],'data':result})
        return {**result,'historyId':history,'analysisId':entry['id']}
    def chimerax_execute(self,p):
        command=str(p['command'])
        if not command.strip() or len(command)>65536 or '\x00' in command:raise ValueError('Enter a native command below 64 KB.')
        risk=command_risk(command)
        if risk['requiresReview'] and not p.get('confirmed'):return {'state':'review_required','risk':risk}
        status=self.chimerax_status({})
        if not status['connected']:raise ValueError('The authenticated ChimeraX session is not connected.')
        start=time.monotonic();record={'command':command,'version':status['version'],'sessionId':status['sessionId'],'structureId':p.get('structureId'),'sourceSha256':p.get('sourceSha256'),'method':'Official ChimeraX REST /run → native command interpreter','syncStatus':'Scientific operation executed · visual update pending'}
        try:
            output=self.request('/run',command=command,timeout=120);record.update(output=output,latencyMs=round((time.monotonic()-start)*1000,1))
            state='failed' if output.get('error') else 'completed'
            try:record['snapshot']=self.chimerax_state({})
            except Exception as error:record['synchronizationError']=str(error)
        except Exception as error:
            state='connection_failed';record['error']=str(error)
        history_id=self.console_record({'projectId':p['projectId'],'engine':'chimerax','command':command,'state':state,'data':record})
        return {'state':state,'historyId':history_id,**record}
    def item(self,id):
        record=next((r for r in self.s.library({})['records'] if r['id']==id and r['kind']=='structure'),None)
        if not record:raise ValueError('The saved source structure is missing. No substitute was loaded.')
        return record
    def chimerax_open(self,p):
        record=self.item(p['structureId']);path=self.s.root/'assets'/record['data']['asset']
        before=self.chimerax_state({});known={m['id'] for m in before['models']}
        linked=[mapping for mapping in before['mapping'] if mapping['structureId']==record['id'] and mapping['sourceSha256']==record['data']['sha256'] and any(m['id']==mapping['modelId'] and (not before.get('bridgeVersion',0)>=4 or m.get('sourceSha256')==mapping['sourceSha256']) and (before.get('bridgeVersion',0)>=4 or m['positionsSha256']==mapping['positionsSha256']) for m in before['models'])]
        if linked:return {'state':'completed','mapping':linked,'snapshot':before,'syncStatus':'Existing authoritative model retained' if before.get('bridgeVersion',0)>=4 else 'Source already linked; native coordinates are unchanged'}
        if p.get('replace'):
            active=self.s.setting('foldActiveModel',None)
            previous=next((m for m in before['models'] if active and active.get('sessionId')==before['sessionId'] and m['id']==active.get('modelId') and m.get('sourceSha256')==active.get('sourceSha256')),None)
            if previous:
                if previous['positionsSha256']!=active.get('positionsSha256'):
                    self.chimerax_session_save({**p,'name':'Automatic checkpoint before changing source'})
                closed=self.chimerax_execute({**p,'command':'close #'+previous['id'],'confirmed':True})
                if closed['state']!='completed':raise ValueError('The previous library model could not be closed safely.')
                known.discard(previous['id'])
        ensemble=record['data'].get('metadata',{}).get('coordinateEnsemble')
        if ensemble:
            from coordinate_ensemble import inspect
            if inspect(path.read_bytes())!=ensemble:raise ValueError('Coordinate ensemble source or frame metadata changed.')
        options=' coordsets true slider false missingCoordsets ignore' if ensemble else ''
        result=self.chimerax_execute({**p,'command':'open '+native_quote(path)+options,'sourceSha256':record['data']['sha256'],'confirmed':True})
        if result['state']!='completed':return result
        models=[m for m in result['snapshot']['models'] if m['id'] not in known]
        mapped=[{'structureId':record['id'],'sourceSha256':record['data']['sha256'],'sessionId':before['sessionId'],'modelId':m['id'],'positionsSha256':m['positionsSha256']} for m in models if m['sourceSha256']==record['data']['sha256']]
        if ensemble:
            if len(models)!=1 or models[0]['coordsets']!=len(ensemble['frameIds']) or models[0]['atoms']!=ensemble['atomsPerFrame']:raise ValueError('Native ensemble frame or atom counts differ from the validated source.')
        self.s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('chimeraxMapping',json.dumps([m for m in self.s.setting('chimeraxMapping',[]) if m['sessionId']==before['sessionId']]+mapped)));self.s.db.commit()
        if mapped:
            self.s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('foldActiveModel',json.dumps(mapped[0])));self.s.db.commit()
        return {**result,'mapping':mapped,'syncStatus':'Authoritative engine model opened; FOLD scene refresh required'}
    def chimerax_select(self,p):
        record=self.item(p['structureId']);state=self.chimerax_state({})
        mapping=next((m for m in reversed(state['mapping']) if m['structureId']==record['id'] and m['sourceSha256']==record['data']['sha256']),None)
        model=next((m for m in state['models'] if mapping and m['id']==mapping['modelId']),None)
        if not model or model['positionsSha256']!=mapping['positionsSha256']:raise ValueError('Selection cannot synchronize: the linked model is missing or its native coordinates changed.')
        if not p.get('atoms'):raise ValueError('Select one or more local atoms first.')
        native_atoms=self.request('/fold/atoms?'+urllib.parse.urlencode({'model':mapping['modelId']}))['atoms']
        selectors=[]
        for atom in p['atoms']:
            if not re.fullmatch(r'[A-Za-z0-9_]+',str(atom['authChain'])) or not re.fullmatch(r'[A-Za-z0-9_\'*]+',str(atom['atomName'])) or not re.fullmatch(r'[A-Za-z0-9]?',str(atom.get('insertion',''))) or atom.get('altLoc'):raise ValueError('This atom identity needs manual native selection syntax; use the console.')
            residue=int(atom['auth']);insertion='^'+atom['insertion'] if atom.get('insertion') else ''
            matches=[a for a in native_atoms if a['chain']==atom['authChain'] and a['residue']==residue and a['insertion']==atom.get('insertion','') and a['atom']==atom['atomName'] and a['element']==atom.get('element') and a['altLoc']==atom.get('altLoc','')]
            if len(matches)!=1 or not isinstance(atom.get('xyz'),list) or len(atom['xyz'])!=3 or not all(math.isfinite(float(v)) for v in atom['xyz']) or not all(math.isfinite(float(v)) for v in matches[0]['xyz']) or math.sqrt(sum((float(a)-float(b))**2 for a,b in zip(matches[0]['xyz'],atom['xyz'])))>0.001:raise ValueError('The local and native atom identities or coordinates do not agree. Use manual native selection or import the native model.')
            selectors.append('#'+mapping['modelId']+'/'+atom['authChain']+':'+str(residue)+insertion+'@'+atom['atomName'])
        return self.chimerax_execute({**p,'command':'select '+' | '.join(selectors),'sourceSha256':record['data']['sha256'],'confirmed':True})
    def chimerax_import(self,p):
        model=str(p['modelId'])
        if not re.fullmatch(r'\d+(?:\.\d+)*',model):raise ValueError('Choose a real native model ID.')
        comparison=None
        if p.get('comparisonId'):
            row=self.s.db.execute("SELECT data FROM observatory_entries WHERE id=? AND project_id=? AND kind='analysis'",(p['comparisonId'],p['projectId'])).fetchone()
            if not row:raise ValueError('The saved comparison is missing from this project.')
            comparison=json.loads(row['data']);state=self.chimerax_state({})
            expected=next((m for m in comparison.get('after',{}).get('models',[]) if m['id']==model),None)
            current=next((m for m in state['models'] if m['id']==model),None)
            if comparison.get('movingModelId')!=model or comparison.get('sessionId')!=state['sessionId'] or not expected or not current or expected['positionsSha256']!=current['positionsSha256']:raise ValueError('The fitted native model changed after this comparison. Run it again before importing the aligned copy.')
        folder=self.root/'transfers';folder.mkdir(exist_ok=True);path=folder/(uid()+'.cif')
        result=self.chimerax_execute({**p,'command':'save '+native_quote(path)+' models #'+model+' format mmcif','confirmed':True})
        if result['state']!='completed':raise ValueError('Native model export failed: '+json.dumps(result.get('output',result)))
        return self.s.import_structure({'projectId':p['projectId'],'path':str(path),'name':p.get('name','ChimeraX model #'+model),'source':'ChimeraX native coordinate export; separate research asset','metadata':{'nativeModelId':model,'nativeSessionId':result['sessionId'],'chimeraxVersion':result['version'],'sourceStructureId':p.get('structureId'),'comparisonId':p.get('comparisonId'),'comparison':comparison,'command':result,'classification':'User-exported native model; inspect geometry and provenance'}})
    def chimerax_focus(self,p):
        return {'refreshScene':True,'mode':'background_scientific_engine'}
    def chimerax_scene(self,p):
        path='/fold/scene'
        if p.get('known'):path+='?'+urllib.parse.urlencode({'known':p['known']})
        return self.request(path,timeout=120)
    def chimerax_measure(self,p):return self.request('/fold/measure',payload=p)
    def chimerax_camera(self,p):return self.request('/fold/camera',payload=p)
    def chimerax_selection(self,p):return self.request('/fold/select',payload=p)
    def chimerax_python(self,p):
        if not p.get('confirmed'):raise ValueError('Review and confirm trusted scientific Python execution.')
        self.s.project(p['projectId']);result=self.request('/fold/python',payload={'code':p['code']},timeout=120)
        result['historyId']=self.console_record({'projectId':p['projectId'],'engine':'python','command':p['code'],'state':result['state'],'data':result})
        return result
    def chimerax_inventory(self,p):return self.request('/fold/inventory',timeout=120)
