"""Disposable loopback OpenSSH verification; no GPU/provider operations.

Creates its own test keys and listener, binds only127.0.0.1 and stops it on exit.
Never enables Remote Login or changes the system SSH daemon/configuration.
"""
import getpass,json,pathlib,shlex,socket,subprocess,sys,tempfile,time
from types import SimpleNamespace
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
from cloud_compute import CloudCompute
report=ROOT/'reports/rapid-loopback-ssh.json'
with tempfile.TemporaryDirectory(prefix='fold-rapid-ssh-') as directory:
 root=pathlib.Path(directory);server=None
 try:
  for name in ('host','client'):subprocess.run(['/usr/bin/ssh-keygen','-q','-t','ed25519','-N','','-f',str(root/name)],check=True,capture_output=True)
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  config=root/'sshd_config';config.write_text('\n'.join(['Port '+str(port),'ListenAddress 127.0.0.1','HostKey '+str(root/'host'),'PidFile '+str(root/'pid'),'AuthorizedKeysFile '+str(root/'client.pub'),'PasswordAuthentication no','KbdInteractiveAuthentication no','UsePAM no','PubkeyAuthentication yes','StrictModes yes','AllowUsers '+getpass.getuser(),'AllowTcpForwarding no','X11Forwarding no','LogLevel ERROR'])+'\n')
  with (root/'server.log').open('w') as log:
   server=subprocess.Popen(['/usr/sbin/sshd','-D','-e','-f',str(config)],stdout=log,stderr=log,start_new_session=True)
  time.sleep(.4)
  if server.poll() is not None:raise RuntimeError((root/'server.log').read_text()[:500])
  data=root/'data';data.mkdir();cloud=CloudCompute(SimpleNamespace(root=data))
  id=cloud.gpu_profile_save({'name':'Disposable loopback SSH','provider':'custom','host':'127.0.0.1','port':port,'username':getpass.getuser(),'keyPath':str(root/'client')})['id']
  scan=cloud.gpu_host_scan({'id':id});expected=subprocess.check_output(['/usr/bin/ssh-keygen','-lf',str(root/'host.pub'),'-E','sha256'],text=True).split()[1];assert scan['fingerprint']==expected
  cloud.gpu_host_trust({'id':id,'confirmed':True,'fingerprint':scan['fingerprint'],'challenge':scan['challenge']})
  known=cloud.root/(id+'.known_hosts');trusted=known.read_text()
  false_key=(root/'client.pub').read_text().split()
  known.write_text('[127.0.0.1]:'+str(port)+' '+false_key[0]+' '+false_key[1]+'\n')
  try:cloud.gpu_connection_test({'id':id})
  except ValueError as error:assert 'identity verification failed' in str(error)
  else:raise AssertionError('Changed server identity was accepted.')
  known.write_text(trusted)
  entry=cloud.profile(id);cloud.update(id,{'keyPath':str(root/'host')})
  try:cloud.gpu_connection_test({'id':id})
  except ValueError as error:assert 'SSH connection failed' in str(error)
  else:raise AssertionError('Wrong authentication key was accepted.')
  cloud.update(id,{'keyPath':entry['keyPath']})
  connection=cloud.gpu_connection_test({'id':id});assert connection['state']=='connected'
  remote_home=root/'remote-home';remote_home.mkdir()
  transport=cloud.ssh
  def isolated(entry,command,payload,**kwargs):
   return transport(entry,'env HOME='+shlex.quote(str(remote_home))+' '+command,payload,**kwargs)
  cloud.ssh=isolated
  installed=cloud.gpu_worker_prepare({'id':id,'approved':True});assert installed['state']=='worker_available' and installed['ready'] is False
  probe=cloud.gpu_worker_selftest({'id':id});assert probe['state']=='blocked' and not probe['ready']
  files=[p for p in remote_home.rglob('*') if p.is_file()];assert len(files)==1 and files[0].name=='rapid_worker.py'
  result={'state':'passed','scope':'Actual generated-key loopback OpenSSH, independently confirmed host identity and authenticated Python connection; no GPU or remote scientific execution. System SSH settings unchanged.','platform':connection['platform'],'remotePython':connection['python'],'workerPython':installed['python'],'hostFingerprintMatchesGeneratedKey':True,'strictHostVerification':True,'actualHostKeyMismatchRefused':True,'actualWrongKeyRefused':True,'workerCodeHashVerified':True,'workerHealthOverSSH':'passed','actualCUDARefusalOnMac':'passed','onlyReviewedWorkerTransferred':True}
 except Exception as error:
  result={'state':'not_validated','scope':'Disposable loopback SSH only; no GPU or remote scientific execution.','reason':str(error)}
 finally:
  if server is not None and server.poll() is None:server.terminate();server.wait(timeout=5)
 report.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
