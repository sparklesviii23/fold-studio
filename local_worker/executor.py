"""Bounded commands in Seatbelt; isolated, review-only exact patches or local Aider."""
from __future__ import annotations
import json, os, pathlib, re, signal, subprocess, sys, time, urllib.request
from .core import DEFAULT_HOME, REPO, digest, run, scoped

PYTHON = REPO.parent/'runtimes/openmm-cpu/bin/python'
NODE = pathlib.Path('/Users/vii/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node')

class Blocked(Exception):pass
class Cancelled(Exception):pass

def environment(folder):
    home=folder/'home';home.mkdir(exist_ok=True)
    return {'HOME':str(home),'TMPDIR':str(folder/'tmp'),'PATH':'/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin','LANG':'en_US.UTF-8','PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_TERMINAL_PROMPT':'0','GIT_OPTIONAL_LOCKS':'0','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','VECLIB_MAXIMUM_THREADS':'2','OLLAMA_API_BASE':'http://127.0.0.1:11434','OLLAMA_KEEP_ALIVE':'0','NO_PROXY':'127.0.0.1,localhost','DO_NOT_TRACK':'1','AIDER_ANALYTICS':'false','AIDER_CHECK_UPDATE':'false','LITELLM_LOCAL_MODEL_COST_MAP':'True','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TIKTOKEN_CACHE_DIR':str(DEFAULT_HOME/'runtime/cache/tiktoken')}

def sandbox(repo, folder, writes=(), local_ai=False, common_repo=REPO):
    if sys.platform!='darwin' or not pathlib.Path('/usr/bin/sandbox-exec').exists():raise Blocked('macOS Seatbelt unavailable; command execution fails closed.')
    def q(path):return json.dumps(str(pathlib.Path(path).resolve()))
    reads=[repo,folder,DEFAULT_HOME/'runtime',folder.parents[1]/'runtime',common_repo/'.git',REPO/'.git',REPO/'local_worker',PYTHON.parent.parent,PYTHON.resolve().parents[2],NODE.resolve().parents[1],'/usr','/bin','/sbin','/System','/Library/Apple','/Library/Developer','/private/var/db/dyld','/dev','/opt/homebrew/opt','/opt/homebrew/Cellar','/Library/Preferences']
    policy='(version 1)(deny default)(allow process*)(allow sysctl-read)(allow mach-lookup)(allow file-read-metadata)(allow ipc-posix-shm*)(allow file-read* '+''.join('(subpath '+q(p)+')' for p in reads)+')'
    policy+='(allow file-read* (require-all '+''.join('(require-not (subpath '+json.dumps(x)+'))' for x in ['/Users','/Volumes','/private/var/folders','/private/tmp'])+'))'
    policy+='(allow file-write* (subpath '+q(folder)+')(literal "/dev/null"))'
    for name in writes:policy+='(allow file-write* (literal '+q(scoped(repo,name))+'))'
    for root in [repo,REPO]:
        for secret in ['.env','private']:policy+='(deny file-read* (subpath '+q(root/secret)+'))'
    policy+='(deny file-read* (regex "/[.]env([./]|$)"))'
    if local_ai:policy+='(allow network-outbound (remote ip "localhost:'+str(local_ai)+'"))'
    return policy

def command(name, repo):
    if name=='git-check':return ['/Library/Developer/CommandLineTools/usr/bin/git','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','diff','--check']
    if name=='config-check':return [str(PYTHON),'-B','-c','import json,pathlib; files=[pathlib.Path("package.json"),pathlib.Path("src-tauri/tauri.conf.json")]; [json.loads(p.read_text()) for p in files]; print("Validated",len(files),"configuration files")']
    if name=='backend-tests':return [str(PYTHON),'-B','-m','unittest','discover','-s','tests']
    if name=='peptide-tests':return [str(PYTHON),'-B','-m','unittest','discover','-s','tests','-p','test_peptides.py']
    if name=='worker-tests':return [str(PYTHON),'-B','-m','unittest','discover','-s','worker_tests']
    if name=='frontend-tests':return [str(NODE),str(REPO/'node_modules/vitest/vitest.mjs'),'run']
    if name=='typecheck':return [str(NODE),str(REPO/'node_modules/typescript/bin/tsc'),'--noEmit','--incremental','false','-p','tsconfig.json']
    if name=='worker-coding-acceptance':return [str(PYTHON),'-B','worker_tests/coding_acceptance.py']
    if name=='coding-fixture-tests':return [str(PYTHON),'-B','-m','unittest','test_worker_fixture']
    if name=='fixture-check':return [str(PYTHON),'-B','-c','import pathlib; assert pathlib.Path("worker_fixture.txt").read_text()=="correct\\n", "recoverable fixture mismatch"; print("fixture check passed")']
    raise ValueError('Unknown approved operation.')

def worktree(broker, task, folder):
    repo=broker.repo
    p=run(['/usr/bin/git','-c','core.fsmonitor=false','status','--porcelain','--untracked-files=normal'],cwd=repo)
    if p.returncode or p.stdout.strip():raise Blocked('Editing needs a clean committed source snapshot; active changes were preserved.')
    root=broker.home/'worktrees';root.mkdir(exist_ok=True)
    if len(list(root.iterdir()))>=3:raise Blocked('Three retained review worktrees already exist. Review or explicitly roll back one first.')
    revision=run(['/usr/bin/git','rev-parse','HEAD'],cwd=repo).stdout.strip();path=root/task['id']
    if path.exists():raise Blocked('An earlier review worktree exists; inspect its patch instead of replaying edits.')
    p=run(['/usr/bin/git','-c','core.hooksPath=/dev/null','worktree','add','--detach',str(path),revision],cwd=repo,timeout=30)
    if p.returncode:raise Blocked('Could not create isolated worktree: '+p.stderr[-1000:])
    broker.db.execute('UPDATE tasks SET revision=? WHERE id=?',(revision,task['id']))
    return path,revision

def patch(repo, batch):
    checked=[]
    for p in batch:
        path=scoped(repo,p['path'])
        if not path.is_file() or digest(path)!=p['sha256']:raise Blocked('Patch source checksum differs: '+p['path'])
        content=path.read_text()
        if content.count(p['before'])!=1:raise Blocked('Patch requires one exact occurrence: '+p['path'])
        checked.append((path,content.replace(p['before'],p['after'],1)))
    for path,content in checked:path.write_text(content)

def changes(repo, authorized, folder):
    # Aider cannot commit; enumerate new, changed and deleted paths, including untracked files.
    output=run(['/usr/bin/git','-c','core.fsmonitor=false','status','--porcelain=v1','-z','--untracked-files=all'],cwd=repo).stdout
    changed=[]
    for entry in output.split('\0'):
        if not entry:continue
        if entry[:2].strip() in ('R','C') or entry[:1] in ('R','C'):raise Blocked('Renames/copies require manual review.')
        name=entry[3:];scoped(repo,name);changed.append(name)
        if name not in authorized:raise Blocked('Unauthorized changed path: '+name)
        p=repo/name
        if not p.exists():raise Blocked('File deletion requires separate review; automatic acceptance is refused.')
        if p.is_symlink() or (p.exists() and p.stat().st_size>1024**2):raise Blocked('Changed file exceeds safe file policy.')
    diff=run(['/usr/bin/git','diff','--no-ext-diff','--no-textconv','--binary','HEAD'],cwd=repo).stdout
    if len(diff.encode())>1024**2:raise Blocked('Patch exceeds 1 MiB review budget.')
    (folder/'changes.patch').write_text(diff)
    for name in changed:
        if run(['/usr/bin/git','ls-files','--error-unmatch',name],cwd=repo).returncode:
            raise Blocked('New files are not supported in this first local-AI adapter; use a separately reviewed task.')
    return changed

def ollama_request(path, data=None):
    # No redirects, proxies, remote host, auto-pull or API credentials.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args):raise Blocked('Local model redirected; remote inference is forbidden.')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    req=urllib.request.Request('http://127.0.0.1:11434/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
    with opener.open(req,timeout=3) as r:return json.loads(r.read(1024**2))

def local_agent(broker,spec,repo,folder,diagnostic=''):
    cfg=broker.setting('localAI',{})
    binary=pathlib.Path(cfg.get('aider','/nonexistent'))
    if not binary.is_absolute() or not binary.is_file():raise Blocked('Aider is not configured. Install/configure only after explicit dependency approval; no remote fallback.')
    prompt='Task: '+spec['instructions']+'\nAcceptance: '+json.dumps(spec['acceptanceCriteria'])+'\nEdit only: '+json.dumps(spec['authorizedPaths'])+'\nNo dependencies, commands, commits, web access or extra files.\n'+diagnostic
    context=len(prompt.encode())+sum(scoped(repo,p).stat().st_size for p in spec['authorizedPaths'])
    if context>spec['maxContextBytes']:raise Blocked('Local context budget exceeded; narrow the task.')
    message=folder/'message.txt';message.write_text(prompt);config=folder/'aider.yml';config.write_text('{}\n')
    cache=folder/'home/.aider/caches';cache.mkdir(parents=True,exist_ok=True);(cache/'model_prices_and_context_window.json').write_text(json.dumps({'ollama_chat/'+spec['model']:{'max_input_tokens':8192,'max_output_tokens':1200,'input_cost_per_token':0,'output_cost_per_token':0,'litellm_provider':'ollama_chat','mode':'chat'}}))
    return [str(binary),'--model','ollama_chat/'+spec['model'],'--edit-format','whole','--weak-model','ollama_chat/'+spec['model'],'--no-stream','--no-auto-commits','--no-dirty-commits','--no-git','--no-auto-lint','--no-auto-test','--no-suggest-shell-commands','--no-check-update','--no-show-release-notes','--no-notifications','--no-analytics','--no-show-model-warnings','--no-detect-urls','--no-pretty','--yes-always','--config',str(config),'--env-file','/dev/null','--map-tokens','0','--input-history-file',str(folder/'input.history'),'--chat-history-file',str(folder/'chat.history'),'--message-file',str(message),*spec['authorizedPaths']]

def child_plan(argv,repo,folder,spec,local_ai=False,common_repo=REPO):
    (folder/'tmp').mkdir(exist_ok=True)
    policy=folder/'sandbox.sb';policy.write_text(sandbox(repo,folder,spec['authorizedPaths'] if local_ai else (),local_ai,common_repo))
    return ['/usr/bin/sandbox-exec','-f',str(policy),*argv]
