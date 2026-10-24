"""Read-only campaign presentation, bounded genuine logs and deterministic console.
No model execution, deployment, account mutation or shell fallback is permitted.
"""
import base64,csv,datetime,hashlib,json,pathlib,re,shlex
import biology_modal

ACTIONS={'cloud_gpu_registry','cloud_campaign_snapshot','cloud_campaign_events','cloud_console','cloud_candidate_open'}
TERMINAL={'COMPLETED','PARTIALLY_COMPLETE','FAILED','CANCELLED'}

def modules():
    import biology_pipeline
    biology_pipeline.common()
    from fold_rapid.events import normalize,redact
    return normalize,redact

def confined(root,path):
    p=(root/path).resolve()
    if root.resolve() not in p.parents or not p.is_file() or p.is_symlink():raise ValueError('Campaign artifact is unavailable or outside its package.')
    return p

def load(path,default=None):
    if not path.is_file():return default
    if path.stat().st_size>32*1024**2:raise ValueError('Campaign metadata exceeds the display limit.')
    return json.loads(path.read_text())

def package(s,row):
    cid=row.get('campaignId','')
    if not re.fullmatch('[a-f0-9]{32}',cid):return None
    p=s.root/'cloud-qualification'/cid
    if p.is_dir():return p
    live=s.root/'cloud-monitor'/cid
    return live if live.is_dir() else None

def public(value):
    if isinstance(value,dict):return {k:public(v) for k,v in value.items() if k not in ('contentBase64','token_id','token_secret','command')}
    if isinstance(value,list):return [public(v) for v in value]
    return value

def snapshot(s,row):
    folder=package(s,row);remote=load(folder/'campaign.json',row.get('remote',{})) if folder else row.get('remote',{})
    nodes=[];ranked={}
    if folder:
        for p in list(folder.glob('stages/*/jobs/*/output/3_Ranked/!_Ranked.csv'))[:100]:
            for record in csv.DictReader(p.read_text().splitlines()):
                seq=record.get('Binder_Sequence',record.get('sequence',''));ranked[seq]=record
        for p in list((folder/'candidates').glob('*.json'))[:10000]:
            node=load(p);native=node.get('nativeCandidate',{});seq='/'.join(node['sequences'][ch] for ch in node['binderChains']);metrics=native.get('metrics',{});rank=ranked.get(seq)
            nodes.append({**public(node),'sequence':seq,'metrics':{**metrics,**(rank or {})},'upstreamStatus':'ranked' if rank else 'passed_upstream_filters' if native.get('outcome')=='passed' else native.get('outcome',node.get('structureStatus','observed')),'upstreamRank':int(float(rank.get('rank',1))) if rank else None,'structureAvailable':bool(node.get('coordinates')),'evaluationStatus':'No complete additional independent evaluation recorded','sourceVersion':metrics.get('bindcraft_version'),'reconciledFromOriginalRankedTable':bool(rank)})
    nodes.sort(key=lambda n:(n.get('upstreamRank') is None,n.get('upstreamRank') or 999,n.get('generator','')))
    stages=[]
    for stage in remote.get('stages',[]):
        stage=dict(stage);proof={}
        if folder and stage.get('jobId') and re.fullmatch('[a-f0-9]{32}',stage.get('stageId','')) and re.fullmatch('[a-f0-9]{32}',stage['jobId']):
            proof=load(folder/'stages'/stage['stageId']/'jobs'/stage['jobId']/'provenance.json',{})
        stage['provenance']=proof
        error=stage.get('error') or ''
        stage['diagnosis']=('Stage deadline reached; completed partial outputs retained. Compilation versus inference time is unresolved.' if stage.get('jobState')=='deadline_exceeded' else 'CUDA initialization failed before model execution.' if 'CUDA startup' in error else 'Model failed; inspect original output. No automatic retry.' if stage.get('state')=='FAILED' else None)
        stage['recovery']={'action':'Review a new evaluation using preserved parent outputs','exactOptimizerResume':False,'additionalApprovalRequired':True,'automaticRetry':False} if stage.get('state')=='FAILED' else None
        stages.append(public(stage))
    return {'schemaVersion':1,'campaignId':row.get('campaignId'),'requestId':row['id'],'state':remote.get('state',row['state']),'target':row.get('manifest',{}).get('target',{}).get('label'),'configuration':row.get('configuration',{}),'created':remote.get('created',row.get('created')),'updated':remote.get('updated',row.get('checked')),'stages':stages,'candidates':nodes,'qualifiedCandidates':remote.get('qualifiedCandidates',[]),'budget':row.get('manifest',{}).get('budget',{}),'events':remote.get('events',[]),'source':'verified_saved_campaign_package' if folder else 'last_saved_provider_snapshot','experimentalBindingEstablished':False,'limitations':['AF2 family agreement is correlated, not experimental proof.','This construct may be a fragment; native assembly accessibility is not established.'],'readiness':'No new paid qualification was performed by this view.'}

def tables(s):
    s.db.executescript('CREATE TABLE IF NOT EXISTS cloud_monitor_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,request TEXT NOT NULL,event_id TEXT NOT NULL,data TEXT NOT NULL,UNIQUE(request,event_id)); CREATE TABLE IF NOT EXISTS cloud_monitor_sources(request TEXT NOT NULL,source TEXT NOT NULL,cursor TEXT NOT NULL,PRIMARY KEY(request,source));')

    if s.setting('cloudMonitorTimestampSchema',0)<1:
        with s.db:
            s.db.execute("UPDATE cloud_monitor_events SET data=json_set(data,'$.timestamp','') WHERE json_extract(data,'$.source')='archived_stdout_stderr'")
            s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('cloudMonitorTimestampSchema','1'))

def insert(s,row,event):
    with s.db:s.db.execute('INSERT OR IGNORE INTO cloud_monitor_events(request,event_id,data) VALUES(?,?,?)',(row['id'],event['eventId'],json.dumps(event)))

def source_cursor(s,row,key,default):
    r=s.db.execute('SELECT cursor FROM cloud_monitor_sources WHERE request=? AND source=?',(row['id'],key)).fetchone()
    return json.loads(r[0]) if r else default

def save_cursor(s,row,key,value):
    with s.db:s.db.execute('INSERT OR REPLACE INTO cloud_monitor_sources VALUES(?,?,?)',(row['id'],key,json.dumps(value)))

def archived_events(s,row):
    normalize,_=modules();folder=package(s,row)
    if not folder:return
    for stage in load(folder/'campaign.json',{}).get('stages',[]):
        sid=stage['stageId'];jid=stage.get('jobId')
        if not jid:continue
        relative=f'stages/{sid}/jobs/{jid}/execution.log'
        try:p=confined(folder,relative)
        except ValueError:continue
        offset=source_cursor(s,row,relative,0)
        with p.open('rb') as f:
            f.seek(offset)
            for _ in range(600):
                start=f.tell();line=f.readline(262144)
                if not line:break
                event=normalize({'message':line.decode(errors='replace').rstrip('\r\n'),'kind':'model_output','rawReference':relative},campaign=row['campaignId'],stage=sid,engine=stage['engine'],call=stage.get('callId',''),cursor=start,timestamp='',source='archived_stdout_stderr')
                insert(s,row,event)
            save_cursor(s,row,relative,f.tell())
    for event in row.get('remote',{}).get('events',[]):
        insert(s,row,normalize(event,campaign=row['campaignId'],cursor=event.get('cursor',0),timestamp=event.get('time'),source='campaign_journal'))

def provider_events(s,row):
    """Official SDK reads existing calls only. Never .remote(), .spawn() or shell."""
    if not __import__('os').environ.get('FOLD_PROVIDER_CHILD'):
        import biology_providers
        return biology_providers.rpc(s,'cloud_campaign_events',{'projectId':row['projectId'],'id':row['id'],'providerRead':True,'after':0,'ingestOnly':True})
    import modal
    normalize,_=modules();count=0
    for stage in row.get('remote',{}).get('stages',[]):
        call_id=stage.get('callId')
        if not call_id or not re.fullmatch('fc-[A-Za-z0-9]+',call_id):continue
        key='modal:'+call_id;begin=source_cursor(s,row,key,stage.get('started',row['created']))
        since=datetime.datetime.fromisoformat(begin);until=min(datetime.datetime.now(datetime.timezone.utc),since+datetime.timedelta(seconds=60))
        seen={}
        for entry in modal.FunctionCall.from_id(call_id).logs.fetch(since=since,until=until):
            stamp=entry.timestamp.isoformat();message=entry.message;source=str(entry.source);k=(stamp,source,message);seen[k]=seen.get(k,0)+1
            event=normalize({'message':message,'kind':'model_output'},campaign=row['campaignId'],stage=stage['stageId'],engine=stage['engine'],call=call_id,cursor=seen[k],timestamp=stamp,source=source);insert(s,row,event);count+=1
            if count>20000:raise ValueError('Log window exceeds the bounded read; narrow the requested interval. Original provider logs remain intact.')
        save_cursor(s,row,key,until.isoformat())
    return {'ingested':count,'gpuStarted':False}

def candidate(s,row,id):
    folder=package(s,row)
    if not folder or not re.fullmatch('[a-f0-9]{64}',id):raise ValueError('Choose an available saved candidate.')
    return load(confined(folder,'candidates/'+id+'.json'))

def open_candidate(s,row,id):
    node=candidate(s,row,id);coordinate=node.get('coordinates')
    if not coordinate:raise ValueError('This sequence has no fresh predicted structure. A parent backbone is not its prediction.')
    if coordinate.get('format') not in ('pdb','cif'):raise ValueError('Unsupported candidate coordinate format.')
    raw=base64.b64decode(coordinate['contentBase64'],validate=True);sha=hashlib.sha256(raw).hexdigest()
    if sha!=coordinate['sha256']:raise ValueError('Candidate coordinate checksum mismatch.')
    s.db.execute('CREATE TABLE IF NOT EXISTS removed_records(id TEXT PRIMARY KEY)')
    for record in s.rows("SELECT * FROM records WHERE project_id=? AND kind='structure' AND id NOT IN (SELECT id FROM removed_records)",(row['projectId'],)):
        data=json.loads(record['data'])
        if data.get('sha256')==sha:return {**dict(record),'data':data}
    folder=s.root/'cloud-previews';folder.mkdir(exist_ok=True);path=folder/(sha+'.'+coordinate['format']);path.write_bytes(raw)
    return s.import_structure({'projectId':row['projectId'],'path':str(path),'name':node['generator']+' · cloud candidate '+id[:8],'source':'Verified RAPID cloud candidate','metadata':{'campaignId':row['campaignId'],'candidateId':id,'upstreamOutcome':node.get('nativeCandidate',{}).get('outcome'),'independentQualification':False}})

def console(s,row,text):
    _,redact=modules()
    if not isinstance(text,str) or len(text)>1000:raise ValueError('Use a short RAPID command.')
    args=shlex.split(text)
    if not args:raise ValueError('Enter a RAPID command.')
    snap=snapshot(s,row);cmd=' '.join(args[:2]);rest=args[2:]
    help_text='help · status · version · health · campaign list/status/stages/candidates/results · candidate list/inspect/metrics/lineage/compare/structure · gpu status/memory/info · worker resources · cloud account/gpu/cost/deployment · performance report · stage timings. Read-only commands never allocate compute. Stop uses the explicit campaign control.'
    if args==['help']:output=help_text
    elif args==['version']:output={'consoleSchemaVersion':1,'provider':'Modal','api':'typed RAPID read-only console'}
    elif args==['status'] or cmd in ('campaign status','worker status','health'):output={k:snap[k] for k in ('campaignId','state','updated','source','qualifiedCandidates')}
    elif cmd=='campaign list':output=[{'id':j['id'],'campaignId':j.get('campaignId'),'state':j['state']} for j in [json.loads(r['data']) for r in s.rows('SELECT data FROM biology_modal_jobs WHERE project_id=?',(row['projectId'],))]]
    elif cmd in ('candidate list','campaign candidates'):output=snap['candidates']
    elif cmd in ('candidate inspect','candidate metrics','candidate lineage','candidate structure','candidate compare'):
        if not rest:raise ValueError('Supply a candidate ID from candidate list.')
        selected=[n for n in snap['candidates'] if n['candidateId'].startswith(rest[0])]
        if len(selected)!=1:raise ValueError('Candidate identifier is missing or ambiguous.')
        n=selected[0];output=n.get('metrics',{}) if args[1]=='metrics' else {k:n.get(k) for k in ('candidateId','sequence','parents','mutationHistory','structureAvailable','upstreamStatus','evaluationStatus')} if args[1] in ('lineage','structure') else n
        if args[1]=='compare':
            if len(rest)!=2:raise ValueError('Use candidate compare <first-id> <second-id>.')
            second=[n for n in snap['candidates'] if n['candidateId'].startswith(rest[1])]
            if len(second)!=1:raise ValueError('Second candidate is missing or ambiguous.')
            output={'first':n['sequence'],'second':second[0]['sequence'],'sameLength':len(n['sequence'])==len(second[0]['sequence']),'structuralComparison':'Not computed by this display command.'}
    elif cmd in ('campaign stages','stage timings','performance report','performance status','cuda status','runtime inspect','gpu status','gpu memory','gpu info','gpu utilization','gpu processes','memory status'):output={'stages':snap['stages'],'telemetry':'Saved observations; unavailable values are not zero. No container was started.'}
    elif cmd=='worker resources' or cmd=='cloud gpu':output=snap['configuration']
    elif cmd=='cloud cost':output={'budget':snap['budget'],'providerReportedUSD':None,'stages':[{k:st.get(k) for k in ('stageId','resourceReservationUSD','liveEstimatedWithSafetyUSD')} for st in snap['stages']]}
    elif cmd in ('cloud account','cloud workspace','cloud deployment'):output={'configuration':snap['configuration'],'workspaceIdentity':'Unavailable in this saved snapshot; test the active account to verify it.'}
    elif cmd=='campaign results':output=snap
    elif cmd=='campaign logs':output={'message':'Open Raw Cloud Terminal or download its retained output. Original archive logs are preserved.'}
    elif cmd=='campaign stop':raise ValueError('Use Stop campaign and review the affected campaign before issuing cancellation.')
    elif args[0]=='models' or cmd in ('worker models','models list','models status'):output={'message':'Open Engine Readiness for evidence by component. A model adapter is not inference qualification.'}
    elif cmd=='cuda validate':raise ValueError('CUDA validation requires a separately approved GPU test. Use CUDA status for saved evidence.')
    else:raise ValueError('Unsupported RAPID command. Type help. Shell commands are never executed on this Mac.')
    return {'command':redact(text),'campaignId':row.get('campaignId'),'status':'completed','output':public(output),'gpuStarted':False,'source':snap['source']}

def dispatch(s,action,p):
    s.project(p['projectId'])
    if action=='cloud_gpu_registry':
        modules()
        from fold_rapid.gpu_profiles import catalog
        return catalog()
    biology_modal.table(s);row=biology_modal.read(s,p)
    if action=='cloud_campaign_snapshot':
        if p.get('providerRead'):
            import os
            if not os.environ.get('FOLD_PROVIDER_CHILD'):
                import biology_providers
                return biology_providers.rpc(s,action,p)
            if row.get('campaignId') and re.fullmatch('[a-f0-9]{32}',row['campaignId']):
                import modal
                modules()
                from fold_rapid.contracts import canonical,digest
                state=modal.Dict.from_name(row['configuration'].get('stateName',row['configuration']['appName']+'-state'))
                remote=state.get('unified:'+row['campaignId'])
                if remote:
                    target=s.root/'cloud-monitor'/row['campaignId'];(target/'candidates').mkdir(parents=True,exist_ok=True)
                    for id in remote.get('candidateIds',[])[:10000]:
                        if not re.fullmatch('[a-f0-9]{64}',id):raise ValueError('Invalid provider candidate identity.')
                        path=target/'candidates'/(id+'.json')
                        if path.exists():continue
                        node=state.get('unified-candidate:'+row['campaignId']+':'+id)
                        if not node:continue
                        if digest(canonical({k:v for k,v in node.items() if k!='candidateId'}).encode())!=id:raise ValueError('Immutable preview checksum mismatch.')
                        coord=node.get('coordinates')
                        if coord and hashlib.sha256(base64.b64decode(coord['contentBase64'],validate=True)).hexdigest()!=coord['sha256']:raise ValueError('Coordinate transfer checksum mismatch.')
                        path.write_text(canonical(node))
                    (target/'campaign.json').write_text(canonical(remote));row['remote']=remote
        return snapshot(s,row)
    if action=='cloud_candidate_open':return open_candidate(s,row,p.get('candidateId',''))
    if action=='cloud_console':return console(s,row,p.get('command',''))
    if action=='cloud_campaign_events':
        after=p.get('after',0)
        if type(after)is not int or after<0:raise ValueError('Invalid event cursor.')
        tables(s);archived_events(s,row);warning=None
        if p.get('providerRead'):
            try:provider_events(s,row)
            except Exception as e:warning=modules()[1](str(e))[:500]
        if p.get('ingestOnly'):return {'ingested':True,'warning':warning}
        events=s.rows('SELECT seq,data FROM cloud_monitor_events WHERE request=? AND seq>? ORDER BY seq LIMIT 300',(row['id'],after))
        return {'events':[{**json.loads(r['data']),'cursor':r['seq']} for r in events],'nextCursor':events[-1]['seq'] if events else after,'hasMore':len(events)==300,'warning':warning,'source':'actual archived subprocess output / official FunctionCall logs','gpuStarted':False}
    raise ValueError('Unsupported cloud monitor operation.')
