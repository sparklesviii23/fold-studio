"""Owned offline Ollama plus a metered loopback gateway; no cloud fallback or pull."""
import contextlib, http.server, json, os, pathlib, signal, socket, subprocess, sys, threading, time, urllib.request
from .core import REPO, run
from .executor import Blocked, environment, sandbox

class LocalProvider:
    def __init__(self,broker,spec,folder):self.b=broker;self.spec=spec;self.folder=folder;self.child=None;self.server=None;self.calls=0;self.metrics=[];self.lock=threading.Lock()
    def consume_call(self):
        with self.lock:
            if self.calls>=self.spec['maxModelCalls']:raise ValueError('Model-call budget exhausted')
            self.calls+=1
    def request(self,path,data=None,timeout=3):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args):raise Blocked('Local provider redirects are forbidden.')
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        req=urllib.request.Request('http://127.0.0.1:'+str(self.upstream)+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
        with opener.open(req,timeout=timeout) as r:return json.loads(r.read(2*1024**2))
    def __enter__(self):
        cfg=self.b.setting('localAI',{});binary=pathlib.Path(cfg.get('ollama','/nonexistent'));aider=pathlib.Path(cfg.get('aider','/nonexistent'));store=pathlib.Path(cfg.get('modelStore',self.b.home/'models'))
        if not binary.is_file() or not aider.is_file() or not store.is_dir():raise Blocked('Approved Aider/Ollama/model installation is missing. No automatic installation or cloud fallback.')
        model=self.spec['model']
        if model.endswith(('-cloud',':cloud')):raise Blocked('Cloud model names are forbidden.')
        manifest=store/'manifests/registry.ollama.ai/library'/model.replace(':','/')
        if not manifest.is_file() or not model.startswith('qwen2.5-coder:'):raise Blocked('Only the explicitly qualified installed Qwen coding model is enabled.')
        # Read the official installed manifest; reject remote pointers and bound weight bytes.
        data=json.loads(manifest.read_text());size=sum(l.get('size',0) for l in data.get('layers',[]))
        if size>self.spec['resourceBudget']['memoryMiB']*1048576:raise Blocked('Installed weights exceed memory budget.')
        sock=socket.socket();sock.bind(('127.0.0.1',0));self.upstream=sock.getsockname()[1];sock.close()
        env=environment(self.folder);(self.folder/'tmp').mkdir(exist_ok=True)
        env.update(OLLAMA_HOST='127.0.0.1:'+str(self.upstream),OLLAMA_MODELS=str(store),OLLAMA_NO_CLOUD='1',OLLAMA_NOPRUNE='1',OLLAMA_MAX_LOADED_MODELS='1',OLLAMA_NUM_PARALLEL='1',OLLAMA_MAX_QUEUE='1',OLLAMA_CONTEXT_LENGTH='8192',OLLAMA_KEEP_ALIVE='0')
        profile=sandbox(REPO,self.folder)+'(allow file-read* (subpath '+json.dumps(str(store))+'))(allow network-inbound (local ip "localhost:*"))(allow network-outbound (remote ip "localhost:*"))(allow iokit-open)'
        policy=self.folder/'ollama.sb';policy.write_text(profile)
        plan=self.folder/'provider-plan.json';plan.write_text(json.dumps({'argv':['/usr/bin/sandbox-exec','-f',str(policy),str(binary),'serve'],'cwd':str(self.folder),'env':env,'log':str(self.folder/'ollama.log'),'receipt':str(self.folder/'provider-receipt.json'),'maxLogBytes':2*1048576}))
        self.child=subprocess.Popen([sys.executable,'-B',str(REPO/'local_worker/runner.py'),str(plan)],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            ready_deadline=time.monotonic()+min(60,self.spec['timeoutSeconds'])
            for _ in range(60):
                if time.monotonic()>ready_deadline:raise Blocked('Offline model-server readiness timeout.')
                if self.child.poll() is not None:raise Blocked('Offline local model server failed; inspect ollama.log.')
                try:
                    tags=self.request('/api/tags',timeout=1).get('models',[])
                    found=[m for m in tags if m.get('name')==model]
                    if found and not found[0].get('remote_model') and not found[0].get('remote_host'):break
                except OSError:pass
                time.sleep(.2)
            else:raise Blocked('Owned offline model server did not become ready.')
            owner=self
            class Gateway(http.server.BaseHTTPRequestHandler):
                def log_message(self,*args):pass
                def do_GET(self):
                    if self.path=='/api/tags':self.reply(200,{'models':found})
                    elif self.path=='/api/version':self.reply(200,owner.request(self.path))
                    else:self.reply(403,{'error':'Read endpoint not approved'})
                def do_POST(self):
                    try:
                        size=int(self.headers.get('Content-Length','0'))
                        if not 0<size<=owner.spec['maxContextBytes']:raise ValueError('Context-byte budget exceeded')
                        body=json.loads(self.rfile.read(size))
                        if body.get('model',body.get('name'))!=model:raise ValueError('Only the selected local model is authorized')
                        if self.path=='/api/show':value=owner.request(self.path,body)
                        elif self.path=='/api/chat':
                            owner.consume_call()
                            body.update(stream=False,keep_alive=0,options={'num_ctx':8192,'num_predict':1200,'temperature':0.1,'num_thread':4})
                            value=owner.request(self.path,body,timeout=min(owner.spec['timeoutSeconds'],300))
                            owner.metrics.append({k:value.get(k) for k in ['total_duration','load_duration','prompt_eval_count','prompt_eval_duration','eval_count','eval_duration','done_reason']})
                        else:raise ValueError('Endpoint not approved; no downloads or remote endpoints')
                        self.reply(200,value)
                    except Exception as e:self.reply(403,{'error':str(e)[:500]})
                def reply(self,status,value):
                    raw=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers()
                    try:self.wfile.write(raw)
                    except (BrokenPipeError,ConnectionResetError):pass
            self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Gateway);self.server.daemon_threads=True;self.port=self.server.server_address[1]
            thread=threading.Thread(target=self.server.serve_forever,daemon=True);thread.start();return self
        except BaseException:self.__exit__(None,None,None);raise
    def __exit__(self,*args):
        if self.child and self.child.poll() is None:
            os.killpg(self.child.pid,signal.SIGTERM)
            try:self.child.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(self.child.pid,signal.SIGKILL);self.child.wait()
        if self.server:self.server.shutdown();self.server.server_close()
        (self.folder/'local-inference.json').write_text(json.dumps({'model':self.spec['model'],'calls':self.calls,'metrics':self.metrics,'network':'OS sandbox: loopback only; OLLAMA_NO_CLOUD=1; no credential environment','serverStopped':self.child is None or self.child.poll() is not None},indent=2))
