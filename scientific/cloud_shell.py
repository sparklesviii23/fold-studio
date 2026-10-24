"""Explicit existing-container diagnostics through Modal's official CLI.
No local user shell, new container, deployment, or model execution fallback.
"""
import hashlib,json,os,re,subprocess,sys
ACTIONS={'cloud_shell_containers','cloud_shell_execute'}

def cli(args):
    result=subprocess.run([sys.executable,'-m','modal',*args],capture_output=True,text=True,timeout=45)
    from cloud_monitor import modules
    redact=modules()[1]
    if result.returncode:raise ValueError(redact(result.stderr)[-1500:] or 'The official Modal CLI request failed.')
    return result.stdout

def containers(cfg):
    apps=json.loads(cli(['app','list','--json','--limit','100']))
    ids=[a.get('App ID') or a.get('app_id') for a in apps if (a.get('Description') or a.get('description') or a.get('Name'))==cfg['appName']]
    if len(ids)!=1:return {'containers':[],'reason':'No unique deployed app was found for this account and saved campaign.','gpuStarted':False}
    id=ids[0]
    if not re.fullmatch('ap-[A-Za-z0-9]+',id or ''):raise ValueError('Provider returned an invalid application identity.')
    rows=json.loads(cli(['container','list','--app-id',id,'--json']))
    return {'containers':rows,'appId':id,'appName':cfg['appName'],'gpuStarted':False}

def dispatch(s,action,p):
    s.project(p['projectId'])
    import biology_modal,biology_providers
    biology_modal.table(s);row=biology_modal.read(s,p)
    if not os.environ.get('FOLD_PROVIDER_CHILD'):return biology_providers.rpc(s,action,p)
    listing=containers(row['configuration'])
    if action=='cloud_shell_containers':return listing
    if p.get('approvedSystemAccess') is not True or p.get('approvedRemoteCost') is not True:raise ValueError('Review this exact command and approve existing-container system access and possible CPU charges.')
    command=p.get('command','');id=p.get('containerId','')
    if not isinstance(command,str) or not command.strip() or len(command)>4000 or '\0' in command:raise ValueError('Enter a bounded remote diagnostic command.')
    if hashlib.sha256(command.encode()).hexdigest()!=p.get('reviewedCommandSha256'):raise ValueError('Command changed after review.')
    available=[r.get('Container ID') or r.get('container_id') for r in listing['containers']]
    if id not in available or not re.fullmatch('ta-[A-Za-z0-9]+',id):raise ValueError('Select a currently running container in this campaign’s original account/app.')
    # argv boundaries are explicit; only the selected remote bash interprets text.
    output=cli(['container','exec','--no-pty',id,'--','timeout','--signal=TERM','--kill-after=5','30','bash','-lc',command])
    from cloud_monitor import modules
    redact=modules()[1]
    result={'command':redact(command),'containerId':id,'appId':listing['appId'],'accountId':row.get('accountId'),'status':'completed','output':redact(output)[-128000:],'exitCode':0,'newContainerStarted':False,'transport':'Official Modal container exec; command session, not a persistent PTY'}
    folder=s.root/'provider-auth';folder.mkdir(exist_ok=True,mode=0o700)
    with (folder/'remote-shell-audit.jsonl').open('a') as f:f.write(json.dumps({k:v for k,v in result.items() if k!='output'})+'\n')
    return result
