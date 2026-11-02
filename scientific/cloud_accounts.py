"""Named Modal identities: metadata in settings, each token pair in Keychain.
Provider operations use a fresh child environment pinned to the request owner.
"""
import json,re,uuid
ACTIONS={'cloud_accounts','cloud_account_save','cloud_account_switch','cloud_account_rename','cloud_account_remove'}

def get(s):return s.setting('modalAccounts',{'activeId':None,'profiles':[]})
def write(s,value):
    with s.db:s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('modalAccounts',json.dumps(value)))
def name(value):
    if not isinstance(value,str) or not 1<=len(value.strip())<=80:raise ValueError('Choose an account name of 1–80 characters.')
    return value.strip()
def slot(id,kind):
    if not re.fullmatch('[a-f0-9]{32}',id or ''):raise ValueError('Invalid saved account identity.')
    return 'modal-'+id+'-token-'+kind

def environment(s,owner=None):
    from provider_credentials import access,environment as legacy
    value=get(s);id=owner if owner is not None else value.get('activeId')
    if not id or id=='legacy':return legacy()
    if not any(p['id']==id for p in value['profiles']):raise ValueError('The campaign’s original account must be restored before provider access.')
    pair={key:access(slot(id,kind)) for key,kind in [('MODAL_TOKEN_ID','id'),('MODAL_TOKEN_SECRET','secret')]}
    if not all(pair.values()):raise ValueError('The selected account credentials are unavailable. No fallback to another account is allowed.')
    boltz=access('boltz-api-key')
    return {**({'BOLTZ_API_KEY':boltz} if boltz else {}),**pair}

def owner(s,p):
    if p.get('id'):
        from biology_modal import table
        table(s);r=s.db.execute('SELECT data FROM biology_modal_jobs WHERE id=? AND project_id=?',(p['id'],p['projectId'])).fetchone()
        if r:return json.loads(r[0]).get('accountId') or 'legacy'
    return get(s).get('activeId')

def register_login(s,auth):
    if auth.get('state')!='connected' or not auth.get('profileId'):return
    value=get(s)
    if any(p['id']==auth['profileId'] for p in value['profiles']):return
    value['profiles'].append({'id':auth['profileId'],'name':auth['profileName'],'workspace':None,'credentialStorage':'macOS Keychain','configuration':None,'identityVerified':False});write(s,value)

def dispatch(s,action,p):
    s.project(p['projectId']);value=get(s)
    if action=='cloud_accounts':return {**value,'billingBalance':None,'billingSource':'Provider dashboard; no balance API is connected.'}
    if action=='cloud_account_save':
        from provider_credentials import access
        label=name(p.get('name'));id=uuid.uuid4().hex
        if value.get('activeId'):raise ValueError('This account is already saved. Use Add Account to connect another identity.')
        if p.get('approvedKeychainCopy') is not True:raise ValueError('Approve saving the connected account as a separate Keychain profile.')
        token=access('modal-token-id');secret=access('modal-token-secret')
        if not token or not secret:raise ValueError('Connect Modal first.')
        access(slot(id,'id'),token);access(slot(id,'secret'),secret)
        value['profiles'].append({'id':id,'name':label,'workspace':None,'configuration':s.setting('biologyModal'),'identityVerified':False,'credentialStorage':'macOS Keychain'});value['activeId']=id
        from biology_modal import table
        table(s)
        with s.db:
            for r in s.rows('SELECT id,data FROM biology_modal_jobs'):
                row=json.loads(r['data'])
                if not row.get('accountId'):row['accountId']=id;s.db.execute('UPDATE biology_modal_jobs SET data=? WHERE id=?',(json.dumps(row),r['id']))
        write(s,value);return dispatch(s,'cloud_accounts',p)
    matches=[v for v in value['profiles'] if v['id']==p.get('accountId')]
    if len(matches)!=1:raise ValueError('Choose a saved Modal account.')
    selected=matches[0]
    if action=='cloud_account_rename':selected['name']=name(p.get('name'))
    elif action=='cloud_account_switch':
        environment(s,selected['id']) # Verify presence, never return secrets.
        current=next((v for v in value['profiles'] if v['id']==value['activeId']),None)
        if current:current['configuration']=s.setting('biologyModal')
        value['activeId']=selected['id']
        with s.db:s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('biologyModal',json.dumps(selected.get('configuration'))))
    elif action=='cloud_account_remove':
        from biology_modal import table
        table(s)
        linked=any(json.loads(r['data']).get('accountId')==selected['id'] for r in s.rows('SELECT data FROM biology_modal_jobs'))
        if linked:raise ValueError('This account owns saved campaigns. Keep its credentials for monitoring and artifact recovery.')
        if value['activeId']==selected['id']:
            # Signing out of the active account: the app falls back to this Mac until another account is chosen.
            value['activeId']=None
            with s.db:s.db.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('executionBackend',json.dumps({'mode':'local'})))
        from provider_credentials import access
        access(slot(selected['id'],'id'),remove=True);access(slot(selected['id'],'secret'),remove=True);value['profiles'].remove(selected)
    else:raise ValueError('Unsupported account operation.')
    write(s,value);return dispatch(s,'cloud_accounts',p)
