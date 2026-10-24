"""Detached scientific supervisor, one accelerator lease, enforced deadlines."""
import fcntl
import json
import os
import pathlib
import signal
import subprocess
import sys
import time
import zipfile
import threading
from . import VERSION
from .adapters import prepare,collect,parse_progress
from .contracts import canonical,deadline_seconds,digest,file_digest
from .store import Store,TERMINAL,now

def spawn(root,id):
    store=Store(root);folder=store.folder(id)
    with (folder/'supervisor.log').open('ab') as log:
        child=subprocess.Popen([sys.executable,'-m','fold_rapid.cli','--root',str(root),'run-job',id],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True,env={**os.environ,'PYTHONPATH':str(pathlib.Path(__file__).resolve().parents[1])})
    threading.Thread(target=child.wait,daemon=True).start()
    return child.pid

def stop(child):
    if child.poll() is None:
        try:os.killpg(child.pid,signal.SIGTERM)
        except ProcessLookupError:return
        try:child.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.wait(timeout=5)

def gpu_usage():
    try:
        p=subprocess.run(['nvidia-smi','--query-compute-apps=pid,used_gpu_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=3)
        return {int(a.strip()):int(b.strip()) for line in p.stdout.splitlines() if ',' in line for a,b in [line.split(',',1)] if a.strip().isdigit() and b.strip().isdigit()}
    except (OSError,subprocess.TimeoutExpired):return {}

def owned_processes(pid):
    parents={}
    if pathlib.Path('/proc').is_dir():
        for entry in pathlib.Path('/proc').iterdir():
            if not entry.name.isdecimal():continue
            try:parents[int(entry.name)]=int((entry/'stat').read_text().rsplit(')',1)[1].split()[1])
            except (OSError,ValueError,IndexError):continue
    result={pid}
    for _ in range(len(parents)+1):
        added={p for p,parent in parents.items() if parent in result}-result
        if not added:break
        result.update(added)
    return result

def execute(root,id):
    store=Store(root);job=store.get(id);folder=store.folder(id);manifest=job['manifest'];child=None
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        # Exactly one runner owns each immutable job, even after concurrent requests.
        result=db.execute("UPDATE jobs SET runner_pid=?,updated=? WHERE id=? AND runner_pid IS NULL",(os.getpid(),now(),id))
        if result.rowcount!=1:return
    limit=deadline_seconds(manifest);submitted=__import__('datetime').datetime.fromisoformat(job['created']).timestamp()
    expires=submitted+limit;started=time.monotonic();state='failed';error=None;peak=0
    lease=(store.root/'accelerator.lock').open('a+')
    def interrupted():
        if store.get(id)['state']=='cancel_requested':return 'cancelled'
        if time.time()>=expires:return 'deadline_exceeded'
        return None
    try:
        while True:
            state=interrupted()
            if state:break
            try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:time.sleep(.15)
        if state:
            package(folder);store.finish(id,state);return
        with store.db() as db:db.execute("UPDATE jobs SET state='preparing',updated=? WHERE id=?",(now(),id))
        prepared=prepare(root,folder,manifest)
        provenance={'jobId':id,'workerVersion':VERSION,'sourceRevision':prepared.get('sourceRevision'),'runtimeReceipt':prepared.get('runtimeReceipt'),'models':prepared['models'],'manifestSha256':job['manifest_hash'],'cudaQualified':False,'requestedSchedulingMode':manifest['mode'],'effectivePolicy':'One original engine workflow; fixed scientific settings. Adaptive cross-engine scheduling awaits measured GPU costs.','imageDigest':os.environ.get('RAPID_IMAGE_DIGEST','unrecorded-local-image')}
        provenance.update(executionHost=__import__('socket').gethostname(),executionPlatform=__import__('platform').platform(),engineRole=os.environ.get('FOLD_ENGINE_ROLE'),imageRecipeSha256=os.environ.get('RAPID_IMAGE_RECIPE_SHA256'),computeProvider=os.environ.get('FOLD_COMPUTE_PROVIDER','configured_worker'),biologyCodeSha256=os.environ.get('BGMEE_CODE_SHA256'))
        if manifest['engine'] not in ('structure_screen','rosetta'):
            from .hardware import require_cuda
            provenance['cudaProbe']=require_cuda(prepared['command'][0],prepared['environment'],timeout=max(1,min(120,expires-time.time())))
        (folder/'provenance.json').write_text(canonical(provenance))
        interruption=interrupted()
        if interruption:package(folder);store.finish(id,interruption);return
        env={**os.environ,**prepared['environment'],'PYTHONUNBUFFERED':'1','RAPID_ROOT':str(root),'RAPID_JOB_ID':id}
        # Retain package importability when started from an installed wheel or source tree.
        if manifest['engine']=='structure_screen':env['PYTHONPATH']=str(pathlib.Path(__file__).resolve().parents[1])
        with (folder/'execution.log').open('wb') as log:
            child=subprocess.Popen(prepared['command'],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,cwd=folder,start_new_session=True,pass_fds=(lease.fileno(),))
            with store.db() as db:db.execute("UPDATE jobs SET state='running',updated=? WHERE id=?",(now(),id))
            store.event(id,{'kind':'started','childPid':child.pid,'command':prepared['command'],'sourceRevision':prepared.get('sourceRevision')})
            state=None;offset=0;last_sample=0
            while child.poll() is None:
                state=interrupted()
                if time.monotonic()-last_sample>=2:
                    usage=gpu_usage();used=sum(usage.get(pid,0) for pid in owned_processes(child.pid));peak=max(peak,used);last_sample=time.monotonic()
                    ceiling=manifest['budget'].get('gpuMemoryMiB')
                    if ceiling and used>ceiling:state='failed';error='Measured GPU allocation exceeded the task ceiling; outputs retained.'
                    with (folder/'execution.log').open('rb') as source:
                        source.seek(offset);block=source.read(32000);offset=source.tell()
                    for line in block.decode(errors='replace').splitlines()[-20:]:store.event(id,parse_progress(line))
                    store.event(id,{'kind':'resources','peakObservedChildGPU_MiB':peak,'elapsedSeconds':time.monotonic()-started,'remainingSeconds':max(0,expires-time.time())})
                if state:stop(child);break
                time.sleep(.15)
        if state is None and child.returncode!=0:state='failed';error=f'Upstream process exited with code {child.returncode}; inspect execution.log.'
        provenance.update(wallSeconds=time.monotonic()-started,peakObservedChildGPU_MiB=peak,exitCode=child.returncode)
        (folder/'provenance.json').write_text(canonical(provenance))
        # Preserve partial/rejected outputs without upgrading their acceptance.
        candidates=collect(folder,manifest,provenance)
        if state is None:
            if manifest['engine'] in ('structure_screen','proteinmpnn','af2_multimer','solublempnn','esmfold2','esmfold2_fast','rosetta','rfdiffusion'):state='completed'
            else:state='completed' if any(c['outcome'] in ('accepted','passed_upstream_filters') for c in candidates) else 'no_qualified_candidates'
        result={'candidates':len(candidates),'accepted':sum(c['outcome']=='accepted' for c in candidates),'passedUpstreamFilters':sum(c['outcome']=='passed_upstream_filters' for c in candidates),'wallSeconds':time.monotonic()-started,'peakObservedChildGPU_MiB':peak,'exactStepResume':False,'scientificCUDAQualified':False}
        (folder/'result.json').write_text(canonical(result))
        package(folder)
        store.finish(id,state,error,result)
    except BaseException as exc:
        if child is not None:stop(child)
        error=f'{type(exc).__name__}: {str(exc)[:2000]}'
        store.finish(id,interrupted() or 'failed',error)
        # A failed dependency check or partial upstream failure still produces
        # an inspectable, checksummed evidence package, never a fake candidate.
        try:
            (folder/'failure.json').write_text(canonical({'error':error,'scientificCUDAQualified':False}))
            package(folder)
        except (OSError,ValueError) as packaging_error:store.event(id,{'kind':'packaging_failed','message':str(packaging_error)[:2000]})
    finally:lease.close()

def package(folder):
    inventory=[]
    for path in sorted(folder.rglob('*')):
        if not path.is_file() or path.is_symlink() or path.name.endswith('.partial') or path.name in ('results.zip','artifact-manifest.json','supervisor.log'):continue
        if folder.resolve() not in path.resolve().parents:raise ValueError('Invalid output path.')
        inventory.append({'path':str(path.relative_to(folder)),'bytes':path.stat().st_size,'sha256':file_digest(path)})
    (folder/'artifact-manifest.json').write_text(canonical(inventory))
    with zipfile.ZipFile(folder/'results.zip.partial','w',zipfile.ZIP_DEFLATED) as archive:
        for item in inventory:archive.write(folder/item['path'],item['path'])
        archive.write(folder/'artifact-manifest.json','artifact-manifest.json')
    os.replace(folder/'results.zip.partial',folder/'results.zip')
