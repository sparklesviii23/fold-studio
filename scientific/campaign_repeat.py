"""Prepare another auditable run from immutable inputs, without starting compute."""
import copy,json
import fold_engine as fe
from campaign_inputs import snapshots,verify

def prepare(engine,p):
 if set(p)-{'id','projectId','name','seed'}:raise ValueError('Unsupported repeat-run field.')
 job=engine.campaign(p);engine.s.project(p['projectId'])
 from scientific_capabilities import require_local_allowed
 require_local_allowed(job)
 if job['state'] in ('preparing','queued','running'):raise ValueError('Wait for the current run to finish before preparing a repeat.')
 preparation=job['data'].get('preparation')
 if not preparation:raise ValueError('This campaign has no saved preparation to repeat.')
 source=fe.verify_source()
 if preparation['upstream'].get('revision')!=source['revision'] or preparation['upstream'].get('manifestSha256')!=source['manifestSha256']:raise ValueError('Prepared upstream revision differs from the installed source; automatic repeat refused.')
 s=engine.s;old=s.root/'jobs'/job['id'];settings=old/'settings.json'
 if settings.is_symlink() or not settings.is_file() or fe.checksum(fe.canonical(json.loads(settings.read_text())).encode())!=preparation['settingsSha256']:raise ValueError('Original prepared settings changed; repeat refused.')
 verify(old,preparation)
 name=p.get('name',job['name'][:130]+' · repeat')
 if not isinstance(name,str) or not name.strip() or len(name)>160:raise ValueError('Enter a repeat-run name of 1–160 characters.')
 original_seed=preparation['config']['campaign_seed'];seed=fe.integer(p.get('seed',original_seed),'Seed',0,2147483647)
 new=copy.deepcopy(preparation);new['name']=name.strip();new['config']['campaign_seed']=seed;new['settingsSha256']=fe.checksum(fe.canonical(new['config']).encode())
 parent={'campaignId':job['id'],'originalSettingsSha256':preparation['settingsSha256'],'originalSeed':original_seed,'seed':seed,'changedScientificFields':[] if original_seed==seed else ['campaign_seed']}
 new['repeatedFrom']=parent
 files={target['file']:(old/target['file']).read_bytes() for target in snapshots(preparation)}
 if preparation.get('scaffold'):files[preparation['scaffold']['file']]=(old/preparation['scaffold']['file']).read_bytes()
 # Verify again after reading so concurrent source changes never enter a repeat.
 for target in snapshots(preparation):
  if fe.checksum(files[target['file']])!=target['source']['sha256']:raise ValueError('Target changed while reading repeat inputs.')
 if preparation.get('scaffold') and fe.checksum(files[preparation['scaffold']['file']])!=preparation['scaffold']['sha256']:raise ValueError('Scaffold changed while reading repeat inputs.')
 child=s.job_new({'projectId':p['projectId'],'name':new['name'],'preparation':new,'repeatOf':parent,'outputs':[]},'bindcraft2','preparing');folder=s.root/'jobs'/child['id'];folder.mkdir(exist_ok=True)
 try:
  for filename,raw in files.items():(folder/filename).write_bytes(raw)
  (folder/'settings.json').write_text(json.dumps(new['config'],indent=2));(folder/'provenance.json').write_text(json.dumps(new,indent=2));verify(folder,new)
  s.job_update(child['id'],'prepared',{'settingsFile':'settings.json','provenanceFile':'provenance.json'})
 except Exception as error:
  s.job_update(child['id'],'failed',{'error':str(error)});raise
 return s.job(child['id'])
