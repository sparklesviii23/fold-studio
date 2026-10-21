"""Actual distributed Linux AMD64 artifact: SSH/RPC, persistence, molecules/export.

Uses disposable keys, private data and a localhost-only Docker port. No GPU,
model download, paid service, scientific inference or original research mutation.
"""
import base64,json,pathlib,shlex,socket,subprocess,sys,tempfile,time
from types import SimpleNamespace
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'remote_worker')]
from cloud_compute import CloudCompute
from rapid_remote import RapidRemote
from fold_rapid.contracts import digest
parser=__import__('argparse').ArgumentParser();parser.add_argument('--image',default='fold-rapid:0.2.0-core');parser.add_argument('--report',type=pathlib.Path,default=ROOT/'reports/rapid-container-validation.json');parser.add_argument('--managed-python',action='store_true');args=parser.parse_args()
def docker(*a,**kw):return subprocess.run(['/opt/homebrew/bin/docker' if sys.platform=='darwin' else 'docker',*a],check=True,capture_output=True,text=True,**kw)
with tempfile.TemporaryDirectory(prefix='fold-rapid-container-') as temp:
 root=pathlib.Path(temp);container=None
 try:
  subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(root/'key')],check=True,capture_output=True)
  with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
  container=docker('run','--detach','--platform','linux/amd64','--publish',f'127.0.0.1:{port}:22','--env','PUBLIC_KEY='+(root/'key.pub').read_text().strip(),args.image).stdout.strip()
  cloud=CloudCompute(SimpleNamespace(root=root));id=cloud.gpu_profile_save({'name':'Disposable AMD64 image','provider':'custom','host':'127.0.0.1','port':port,'username':'root','keyPath':str(root/'key')})['id']
  for _ in range(40):
   try:scan=cloud.gpu_host_scan({'id':id});break
   except ValueError:time.sleep(.25)
  else:raise ValueError('Container SSH did not start.')
  expected=docker('exec',container,'ssh-keygen','-lf','/etc/ssh/ssh_host_ed25519_key.pub','-E','sha256').stdout.split()[1];assert expected==scan['fingerprint']
  cloud.gpu_host_trust({'id':id,'fingerprint':expected,'challenge':scan['challenge'],'confirmed':True})
  connection=cloud.gpu_connection_test({'id':id});assert connection['platform']=='Linux' and connection['architecture']=='x86_64'
  remote=RapidRemote(cloud,None);entry=cloud.profile(id)
  health=remote.call(entry,'health',{});assert health['workerVersion']=='0.2.0' and not health['scientificCUDAQualified'] and not health['gpu']['detected']
  raw=(ROOT/'vendor/bindcraft2/settings/target/structures/hPDL1.pdb').read_bytes()
  manifest={'schemaVersion':1,'engine':'structure_screen','operation':'screen','target':{'format':'pdb','contentBase64':base64.b64encode(raw).decode(),'sha256':digest(raw),'chains':['A']},'design':{'modality':'peptide','lengths':[20],'count':1,'attempts':1},'seed':42,'budget':{'seconds':60},'mode':'reference'}
  validated=remote.call(entry,'campaign_validate',{'manifest':manifest});assert validated['target']['residueCount']==115
  payload={'manifest':manifest,'idempotencyKey':'container-reference','approvedResearchTransfer':True}
  job=remote.call(entry,'job_submit',payload);idjob=job['jobId']
  # Each call above is a closed SSH session; this next client reconnects.
  for _ in range(50):
   status=RapidRemote(cloud,None).call(entry,'job_status',{'jobId':idjob})
   if status['state'] in ('completed','failed'):break
   time.sleep(.15)
  assert status['state']=='completed',status
  replay=remote.call(entry,'job_submit',payload);assert replay['jobId']==idjob and replay['created'] is False
  artifacts=remote.call(entry,'artifact_list',{'jobId':idjob})['artifacts'];package=next(a for a in artifacts if a['path']=='results.zip')
  data=remote.call(entry,'artifact_read',{'jobId':idjob,'path':'results.zip','length':196608});raw=base64.b64decode(data['contentBase64']);assert digest(raw)==data['chunkSha256']==package['sha256']
  installation=remote.gpu_rapid_install({'id':id,'approved':True,'preferManagedPython':args.managed_python});assert installation['state']=='installing'
  for _ in range(90):
   installed=remote.gpu_rapid_status({'id':id})
   if installed['state'] in ('installed','failed'):break
   time.sleep(1)
  assert installed['state']=='installed',installed
  interpreter=cloud.ssh(entry,shlex.quote(installed['python'])+' -I -B -c '+shlex.quote('import json,sys;print(json.dumps({"basePrefix":sys.base_prefix,"python":sys.version.split()[0]}))'),{})
  if args.managed_python:assert '/python/cpython-3.12.14-' in interpreter['basePrefix'],interpreter
  # Route B updates activate into their own prefix, preserving Route A data.
  assert remote.call(entry,'job_status',{'jobId':idjob})['state']=='completed'
  for operation,payload in [('job_cancel',{'jobId':idjob}),('worker_shutdown',{})]:remote.call(entry,operation,payload)
  image=json.loads(docker('image','inspect',args.image).stdout)[0]
  result={'state':'passed','scope':'Actual AMD64 CUDA-base container, no GPU. Original 115-residue hPDL1 structure analysis; not a model prediction.','imageId':image['Id'],'repoDigests':image.get('RepoDigests',[]),'architecture':image['Architecture'],'workerVersion':health['workerVersion'],'realAuthenticatedSSH':True,'independentHostFingerprint':True,'clientDisconnectedJobSurvived':True,'idempotency':True,'realMolecularResidues':115,'resultArchiveSha256':package['sha256'],'existingInstanceBootstrap':installed,'bootstrapInterpreter':interpreter,'managedPythonBootstrap':args.managed_python,'bootstrapPreservedExistingJobs':True,'cudaScientificExecution':'NOT RUN: NVIDIA hardware unavailable','modelsDownloaded':False,'researchIncludedInImage':False}
 except Exception as e:result={'state':'failed','reason':str(e)}
 finally:
  if container:docker('rm','--force',container)
 args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 if result['state']!='passed':raise SystemExit(1)
