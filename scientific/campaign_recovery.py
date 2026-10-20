"""Continue the original upstream attempt budget, retaining every prior receipt.

Upstream resumes at the next claimed trajectory, not an optimizer checkpoint.
An interrupted claimed trajectory remains spent, as in CampaignProgress.
"""
import json,pathlib,subprocess
import fold_engine as fe

STATES=('failed','cancelled','interrupted')
def effective_fab_compiler_flags(runtime,source,existing):
 """Ask the pinned package to apply its own startup flags, without importing JAX.

 BindCraft appends its Triton setting during import. Comparing a parent's raw
 launch flags with a worker's effective flags incorrectly refused valid resume.
 """
 from amme_campaign import environment
 code="import json,os,sys;sys.path.insert(0,sys.argv[1]);import bindcraft;print(json.dumps(os.environ.get('XLA_FLAGS','')))"
 result=subprocess.run([runtime,'-I','-B','-c',code,str(source)],env=environment(existing),capture_output=True,text=True,timeout=30)
 if result.returncode:raise ValueError('Cannot verify original Fab compiler initialization: '+result.stderr[-2000:])
 try:value=json.loads(result.stdout.strip())
 except (ValueError,TypeError):raise ValueError('Invalid Fab compiler initialization receipt.')
 if not isinstance(value,str):raise ValueError('Invalid Fab compiler initialization receipt.')
 return value

def prepare(engine,p):
 if set(p)-{'id','projectId'}:raise ValueError('Campaign recovery preserves the profile, seeds, scientific settings and original attempt budget.')
 job=engine.campaign(p);data=job['data'];folder=engine.s.root/'jobs'/job['id']
 if job['state'] not in STATES or not data.get('executionSettingsSha256') or not data.get('profile'):raise ValueError('Choose an interrupted, cancelled or failed native campaign with saved execution settings.')
 # A dead worker parent can leave its scientific child alive. Check the original
 # process group as well as the exact worker/job command before touching output.
 pid=data.get('pid')
 if pid:
  processes=subprocess.check_output(['/bin/ps','-axo','pid=,pgid=,command='],text=True)
  for line in processes.splitlines():
   fields=line.strip().split(None,2)
   if len(fields)==3 and fields[1]==str(pid) and (job['id'] in fields[2] or str(folder) in fields[2]):raise ValueError('The previous scientific worker is still stopping. Wait before continuing this campaign.')
 settings=folder/'execution-settings.json';original=json.loads(settings.read_text())
 if settings.is_symlink() or fe.checksum(fe.canonical(original).encode())!=data['executionSettingsSha256']:raise ValueError('Saved execution settings changed; recovery refused.')
 from campaign_inputs import verify
 verify(folder,data['preparation'])
 source=fe.verify_source();prepared=data['preparation']['upstream']
 if prepared.get('manifestSha256')!=source['manifestSha256'] or prepared.get('revision')!=source['revision']:raise ValueError('Pinned upstream source differs from the original campaign.')
 runtime=json.loads((folder/'runtime-provenance.json').read_text())
 if runtime.get('execution')!=data.get('execution') or runtime.get('precision')!=data.get('precision') or runtime.get('upstreamSource',{}).get('manifestSha256')!=source['manifestSha256']:raise ValueError('Original scientific runtime provenance differs.')
 if data.get('precision')=='float32' and runtime.get('precisionAdapterSha256')!=fe.checksum(pathlib.Path(__file__).with_name('af2_native.py').read_bytes()):raise ValueError('The validated numerical adapter differs from this campaign.')
 if data.get('memoryPolicy'):
  from amme_campaign import POLICY
  import os
  policy=runtime.get('amme',{})
  if data['memoryPolicy']!=POLICY or policy.get('policy')!=POLICY:raise ValueError('The original Fab memory policy differs; recovery refused.')
  for key,name in (('adapterSha256','amme_campaign.py'),('ssdAdapterSha256','ssd_checkpoint.py')):
   if policy.get(key)!=fe.checksum(pathlib.Path(__file__).with_name(name).read_bytes()):raise ValueError('The original Fab memory adapter differs; recovery refused.')
  if policy.get('compilerEnvironment')!=effective_fab_compiler_flags(data['runtime'],fe.UPSTREAM,os.environ):raise ValueError('Fab compiler settings differ from the original execution; recovery refused.')
 state_path=folder/'output/.campaign_state.json'
 if state_path.is_symlink() or not state_path.is_file():raise ValueError('No upstream campaign progress exists. Prepare a repeat to retry initialization.')
 state=json.loads(state_path.read_text());attempts=state.get('trajectories');accepted=state.get('accepted');maximum=original.get('max_trajectories');requested=original.get('number_of_final_designs')
 if any(type(x) is not int or x<0 for x in (attempts,accepted)) or type(maximum) is not int or maximum<1 or type(requested) is not int or requested<1:raise ValueError('Invalid upstream progress or bounded campaign budget.')
 if accepted>=requested or attempts>=maximum:raise ValueError('The original accepted-design or trajectory budget is already satisfied; prepare a distinct repeat instead.')
 manifest={};total=0
 output=folder/'output'
 for path in sorted(output.rglob('*')):
  if path.is_symlink():raise ValueError('Campaign recovery cannot follow output symlinks.')
  if not path.is_file():continue
  raw=path.read_bytes();total+=len(raw)
  if len(raw)>100*1024**2 or total>512*1024**2 or len(manifest)>=20000:raise ValueError('Campaign recovery snapshot exceeds its bounded manifest scope.')
  manifest[str(path.relative_to(output))]={'sha256':fe.checksum(raw),'bytes':len(raw)}
 return {'job':job,'settings':original,'runtime':runtime,'state':state,'outputManifest':manifest,'source':source,'recordedAt':fe.mi.now(),'scope':'Original upstream resume at the next trajectory. Claimed interrupted attempts remain spent; no optimizer-state or exact mid-trajectory restart claim.'}

def verify_manifest(folder,recovery):
 output=folder/'output';actual={str(path.relative_to(output)) for path in output.rglob('*') if path.is_file()}
 if actual!=set(recovery['outputManifest']):raise ValueError('Campaign output changed while preparing recovery.')
 for name,entry in recovery['outputManifest'].items():
  path=output/name
  if path.is_symlink() or fe.checksum(path.read_bytes())!=entry['sha256']:raise ValueError('Campaign output changed while preparing recovery: '+name)

def archive(folder,recovery):
 history=folder/'recovery';history.mkdir(exist_ok=True);index=1
 while (history/f'{index:04d}').exists():index+=1
 target=history/f'{index:04d}';target.mkdir()
 for name in ('execution-settings.json','runtime-provenance.json','execution.log','amme-memory.json','amme-stage.json'):
  path=folder/name
  if path.is_file():(target/name).write_bytes(path.read_bytes())
 (target/'receipt.json').write_text(json.dumps(recovery,indent=2)+'\n')
 return {'folder':str(target.relative_to(folder)),'receiptSha256':fe.checksum((target/'receipt.json').read_bytes()),'originalState':recovery['job']['state'],'claimedTrajectories':recovery['state']['trajectories'],'accepted':recovery['state']['accepted'],'recordedAt':recovery['recordedAt'],'scope':recovery['scope']}
