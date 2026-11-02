import base64, json, os, pathlib, shlex, subprocess, sys, tempfile, unittest, zipfile
from types import SimpleNamespace
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scientific'))
import cloud_compute as cc
from worker import Service

class CloudConnections(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.service=SimpleNamespace(root=self.root);self.cloud=cc.CloudCompute(self.service)
        self.id=self.cloud.gpu_profile_save({'name':'Private test GPU','provider':'vast','host':'private.server.example','port':2222,'username':'research','keyPath':''})['id']
    def tearDown(self):self.tmp.cleanup()
    def trust(self):
        key={'type':'ssh-ed25519','key':base64.b64encode(b'K'*48).decode(),'fingerprint':'SHA256:test','challenge':'reviewed'}
        self.cloud.update(self.id,{'pendingHostKey':key})
        self.cloud.gpu_host_trust({'id':self.id,'challenge':'reviewed','fingerprint':'SHA256:test','confirmed':True})
    def test_parse_provider_connection_without_remote_execution(self):
        result=cc.parse_connection('ssh -p 12345 root@ssh4.vast.ai -L 8080:localhost:8080')
        self.assertEqual((result['host'],result['port'],result['username']),('ssh4.vast.ai',12345,'root'))
        self.assertTrue(result['ignoredForwarding'])
    def test_injection_remote_commands_and_unsafe_ssh_options_rejected(self):
        for value in ['ssh root@host id','ssh -o ProxyCommand=whoami root@host','ssh root@host;touch /tmp/x','ssh -p 0 root@host','ssh -p abc root@host','ssh root@$(whoami)','ssh -F file root@host']:
            with self.subTest(value=value),self.assertRaises(ValueError):cc.parse_connection(value)
    def test_profile_ports_and_usernames_validate(self):
        for values in [{'port':True},{'port':65536},{'username':'root;id'},{'host':'-evil'},{'provider':'unknown'}]:
            with self.assertRaises(ValueError):self.cloud.gpu_profile_save({'name':'x','provider':'vast','host':'host','username':'root','port':22,**values})
    def test_private_store_permissions_and_known_host_confirmation(self):
        self.assertEqual(self.cloud.root.stat().st_mode&0o777,0o700)
        self.assertEqual(self.cloud.path.stat().st_mode&0o777,0o600)
        with self.assertRaises(ValueError):self.cloud.gpu_host_trust({'id':self.id,'confirmed':True})
        self.trust();known=self.cloud.root/(self.id+'.known_hosts')
        self.assertEqual(known.stat().st_mode&0o777,0o600)
        self.assertTrue(known.read_text().startswith('[private.server.example]:2222 ssh-ed25519 '))
        with self.assertRaises(ValueError):self.cloud.gpu_host_trust({'id':self.id,'confirmed':True})
    def test_unknown_identity_cannot_connect(self):
        with patch.object(cc,'bounded_transport') as run:
            with self.assertRaises(ValueError):self.cloud.gpu_connection_test({'id':self.id})
            run.assert_not_called()
    def test_strict_transport_never_uses_a_shell_or_public_port(self):
        self.trust()
        with patch.object(cc,'bounded_transport',return_value=SimpleNamespace(returncode=0,stdout=json.dumps({'state':'connected'}),stderr='')) as run:
            self.cloud.gpu_connection_test({'id':self.id})
        argv=run.call_args.args[0]
        for option in ['StrictHostKeyChecking=yes','BatchMode=yes','ClearAllForwardings=yes','GlobalKnownHostsFile=/dev/null']:self.assertIn(option,argv)
        self.assertFalse(run.call_args.kwargs.get('shell',False));self.assertNotIn('-L',argv)
        self.assertEqual(argv[-2],'research@private.server.example')
    def test_host_key_change_refused(self):
        self.trust()
        other='host ssh-ed25519 '+base64.b64encode(b'X'*48).decode()
        with patch.object(cc.subprocess,'run',side_effect=[SimpleNamespace(returncode=0,stdout=other,stderr=''),SimpleNamespace(returncode=0,stdout='256 SHA256:other',stderr='')]):
            value=self.cloud.gpu_host_scan({'id':self.id})
        self.assertEqual(value['state'],'host_key_mismatch')
        self.assertEqual(self.cloud.profile(self.id)['fingerprint'],'SHA256:test')
    def test_authentication_failure_is_not_ready(self):
        self.trust()
        with patch.object(cc,'bounded_transport',return_value=SimpleNamespace(returncode=255,stdout='',stderr='Permission denied (publickey).')):
            with self.assertRaisesRegex(ValueError,'key or unlocked SSH agent'):self.cloud.gpu_connection_test({'id':self.id})
        self.assertNotIn('connection',self.cloud.profile(self.id))
    def test_timeout_is_explicit_and_not_a_submission(self):
        self.trust()
        with patch.object(cc,'bounded_transport',side_effect=subprocess.TimeoutExpired('ssh',8)):
            with self.assertRaisesRegex(ValueError,'No scientific campaign'):self.cloud.gpu_connection_test({'id':self.id})
    def test_worker_response_version_and_request_identity_checked(self):
        self.trust()
        with patch.object(self.cloud,'ssh',return_value={'apiVersion':0,'requestId':'wrong','result':{}}):
            with self.assertRaisesRegex(ValueError,'version or request identity'):self.cloud.gpu_worker_health({'id':self.id})
    def test_bootstrap_requires_approval_and_transfers_no_private_key(self):
        self.trust()
        with self.assertRaises(ValueError):self.cloud.gpu_worker_prepare({'id':self.id})
        code,digest=cc.worker_source()
        calls=[]
        def remote(entry,command,payload,**kwargs):
            calls.append((command,payload))
            if 'code' in payload:
                self.assertEqual(base64.b64decode(payload['code']),code)
                return {'state':'installed','sha256':digest,'bytes':len(code)}
            return {'apiVersion':1,'requestId':payload['requestId'],'result':{'workerSha256':digest,'state':'worker_available','ready':False}}
        with patch.object(self.cloud,'ssh',side_effect=remote):value=self.cloud.gpu_worker_prepare({'id':self.id,'approved':True})
        self.assertFalse(value['ready']);self.assertEqual(len(calls),2)
        self.assertNotIn('keyPath',calls[0][1]);self.assertNotIn('token',calls[0][1])
    def test_editing_credentials_invalidates_old_readiness(self):
        self.trust();self.cloud.update(self.id,{'connection':{'state':'connected'},'worker':{'state':'installed'},'lastWorkerReading':{'result':{'ready':False}}})
        self.cloud.gpu_profile_save({'id':self.id,'name':'renamed','provider':'vast','host':'private.server.example','port':2222,'username':'different','keyPath':''})
        profile=self.cloud.profile(self.id);self.assertNotIn('connection',profile);self.assertNotIn('worker',profile);self.assertIn('fingerprint',profile)
    def test_private_key_file_must_not_be_world_readable(self):
        path=self.root/'testkey';path.write_text('TEST ONLY NOT A REAL KEY');path.chmod(0o644)
        with self.assertRaises(ValueError):cc.private_key(str(path))
        path.chmod(0o600);self.assertEqual(cc.private_key(str(path)),str(path))
    def test_profiles_are_excluded_from_project_export(self):
        service=Service(self.root/'library');project=service.project_create({'name':'Export boundary'})
        try:
            cloud=cc.CloudCompute(service);cloud.gpu_profile_save({'name':'PRIVATE_CONNECTION_MARKER','provider':'vast','host':'private.server.example','port':22,'username':'root'})
            archive=self.root/'project.zip';service.export_project({'id':project['id'],'path':str(archive)})
            with zipfile.ZipFile(archive) as z:
                self.assertFalse(any('private-compute' in name for name in z.namelist()))
                self.assertTrue(all(b'PRIVATE_CONNECTION_MARKER' not in z.read(name) for name in z.namelist()))
        finally:service.db.close()
    def test_archive_removes_only_saved_profile_and_never_billing(self):
        result=self.cloud.gpu_profile_archive({'id':self.id});self.assertFalse(result['billingChanged']);self.assertEqual(self.cloud.gpu_profiles({})['profiles'],[])

class BoundedTransport(unittest.TestCase):
    def test_actual_transport_drains_large_input_and_valid_output(self):
        value=cc.bounded_transport([sys.executable,'-I','-B','-c','import sys,json;v=sys.stdin.read();print(json.dumps({"length":len(v)}))'],input='x'*100000,timeout=5)
        self.assertEqual(json.loads(value.stdout)['length'],100000)
    def test_actual_untrusted_output_is_bounded(self):
        with self.assertRaisesRegex(ValueError,'safe size limit'):
            cc.bounded_transport([sys.executable,'-I','-B','-c','import sys;sys.stdout.write("x"*3000000)'],input='{}',timeout=5)
    def test_actual_stalled_process_times_out(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            cc.bounded_transport([sys.executable,'-I','-B','-c','import time;time.sleep(10)'],input='{}',timeout=.05)

class RealWorkerProtocol(unittest.TestCase):
    def request(self,request):
        result=subprocess.run([sys.executable,'-I','-B',str(ROOT/'remote_worker/rapid_worker.py')],input=json.dumps(request),capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0);return json.loads(result.stdout)
    def test_actual_health_has_no_false_scientific_readiness(self):
        value=self.request({'apiVersion':1,'requestId':'real-health','operation':'health','payload':{}})
        self.assertEqual(value['requestId'],'real-health');self.assertFalse(value['result']['ready'])
        self.assertFalse(value['result']['campaignSubmissionAvailable'])
        self.assertEqual(value['result']['workerSha256'],cc.worker_source()[1])
    def test_actual_mac_selftest_refuses_cpu_fallback(self):
        if sys.platform!='darwin':self.skipTest('Explicit real macOS refusal case.')
        value=self.request({'apiVersion':1,'requestId':'real-refusal','operation':'gpu_selftest','payload':{}})
        self.assertEqual(value['result']['state'],'blocked');self.assertFalse(value['result']['ready']);self.assertEqual(value['result']['frameworks'],[])
    def test_version_unknown_operations_and_arguments_rejected(self):
        for extra in [{'apiVersion':2},{'apiVersion':True},{'operation':'submit_campaign'},{'payload':{'command':'id'}}]:
            value=self.request({'apiVersion':1,'requestId':'refusal','operation':'health','payload':{},**extra});self.assertIn('error',value)

if __name__=='__main__':unittest.main()
