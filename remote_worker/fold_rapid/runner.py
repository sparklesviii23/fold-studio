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

def execute(root,id,*,cache_root=None):
    store=Store(root);job=store.get(id);folder=store.folder(id);manifest=job['manifest'];child=None
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        # Exactly one runner owns each immutable job, even after concurrent requests.
        result=db.execute("UPDATE jobs SET runner_pid=?,updated=? WHERE id=? AND runner_pid IS NULL",(os.getpid(),now(),id))
        if result.rowcount!=1:return
    limit=deadline_seconds(manifest);submitted=__import__('datetime').datetime.fromisoformat(job['created']).timestamp()
    expires=submitted+limit;started=time.monotonic();state='failed';error=None;peak=None;device_peak=None;host_peak=None
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
        prepared=prepare(root,folder,manifest,cache_root=cache_root)
        provenance={'jobId':id,'workerVersion':VERSION,'sourceRevision':prepared.get('sourceRevision'),'runtimeReceipt':prepared.get('runtimeReceipt'),'models':prepared['models'],'manifestSha256':job['manifest_hash'],'cudaQualified':False,'requestedSchedulingMode':manifest['mode'],'effectivePolicy':'One original engine workflow; fixed scientific settings. Adaptive cross-engine scheduling awaits measured GPU costs.','imageDigest':os.environ.get('RAPID_IMAGE_DIGEST','unrecorded-local-image')}
        provenance['compilationCache']={'directory':prepared['environment'].get('JAX_COMPILATION_CACHE_DIR'),'reuseMeasured':False,'scope':'JAX persistent cache; graph/runtime/hardware compatibility still determines hits.'}
        from .adapters import cache_snapshot
        provenance['compilationCache']['before']=cache_snapshot(prepared['environment'].get('JAX_COMPILATION_CACHE_DIR'))
        provenance.update(executionHost=__import__('socket').gethostname(),executionPlatform=__import__('platform').platform(),engineRole=os.environ.get('FOLD_ENGINE_ROLE'),imageRecipeSha256=os.environ.get('RAPID_IMAGE_RECIPE_SHA256'),computeProvider=os.environ.get('FOLD_COMPUTE_PROVIDER','configured_worker'),biologyCodeSha256=os.environ.get('BGMEE_CODE_SHA256'))
        cuda=manifest['engine'] not in ('structure_screen','rosetta')
        command=prepared['command']
        if cuda:
            from .hardware import inventory as gpu_inventory
            provenance['hardware']=gpu_inventory()
            if __import__('platform').system()!='Linux' or not provenance['hardware']['detected']:raise ValueError('Scientific execution requires a real Linux NVIDIA GPU; no CPU fallback.')
            (folder/'cuda-entry.json').write_text(canonical({'engine':manifest['engine'],'command':command}))
            command=[command[0],'-m','fold_rapid.cuda_exec',str(folder)]
            provenance['cudaNumericalProbePassed']=False
        (folder/'provenance.json').write_text(canonical(provenance))
        interruption=interrupted()
        if interruption:package(folder);store.finish(id,interruption);return
        env={**os.environ,**prepared['environment'],'PYTHONUNBUFFERED':'1','RAPID_ROOT':str(root),'RAPID_JOB_ID':id}
        # Retain package importability when started from an installed wheel or source tree.
        env['PYTHONPATH']=os.pathsep.join(filter(None,[str(pathlib.Path(__file__).resolve().parents[1]),env.get('PYTHONPATH')]))
        with (folder/'execution.log').open('wb') as log:
            child=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,cwd=folder,start_new_session=True,pass_fds=(lease.fileno(),))
            with store.db() as db:db.execute("UPDATE jobs SET state='running',updated=? WHERE id=?",(now(),id))
            store.event(id,{'kind':'started','childPid':child.pid,'command':prepared['command'],'sourceRevision':prepared.get('sourceRevision')})
            state=None;offset=0;last_sample=0;startup=time.monotonic();pending=b''
            def forward(final=False):
                nonlocal offset,pending
                from .events import redact
                with (folder/'execution.log').open('rb') as source:
                    source.seek(offset);block=source.read(262144);offset=source.tell()
                pending+=block
                lines=pending.split(b'\n');pending=lines.pop()
                if final and pending:lines.append(pending);pending=b''
                # Preserve every line, including final output after the child exits.
                for raw in lines:
                    line=raw.decode(errors='replace')
                    store.event(id,{**parse_progress(line),'message':line,'rawReference':'execution.log','source':'stdout_stderr'})
                    print(redact(line),flush=True)  # Official FunctionCall logs include the scientific child.
                return bool(block)
            while child.poll() is None:
                state=interrupted()
                if cuda and not (folder/'cuda-probe.json').is_file() and time.monotonic()-startup>=120:
                    state='failed';error='CUDA startup exceeded 120 seconds; supervised process stopped. No remaining campaign stages should be launched.'
                if time.monotonic()-last_sample>=2:
                    from .telemetry import sample
                    observed=sample(child.pid)
                    device_used=(observed.get('device') or {}).get('usedMiB')
                    if device_used is not None:device_peak=max(device_peak or 0,device_used)
                    if observed['processRSSMiB'] is not None:host_peak=max(host_peak or 0,observed['processRSSMiB'])
                    usage=gpu_usage();owned=owned_processes(child.pid)&set(usage);used=sum(usage[pid] for pid in owned) if owned else None
                    if used is not None:peak=max(peak or 0,used)
                    last_sample=time.monotonic()
                    ceiling=manifest['budget'].get('gpuMemoryMiB')
                    if ceiling and used is not None and used>ceiling:state='failed';error='Measured GPU allocation exceeded the task ceiling; outputs retained.'
                    forward()
                    store.event(id,{'kind':'resources','observation':observed,'peakObservedDeviceGPU_MiB':device_peak,'peakObservedHostRSS_MiB':host_peak,'peakObservedChildGPU_MiB':peak,'childGPUAttributionAvailable':used is not None,'elapsedSeconds':time.monotonic()-started,'remainingSeconds':max(0,expires-time.time())})
                if state:stop(child);break
                time.sleep(.15)
        while forward():pass
        forward(final=True)
        if state is None and child.returncode!=0:state='failed';error=f'Upstream process exited with code {child.returncode}; inspect execution.log.'
        if cuda:
            receipt=folder/'cuda-probe.json'
            reading=json.loads(receipt.read_text()) if receipt.is_file() else {'passed':False,'reason':error or 'No completed numerical receipt.'}
            provenance.update(cudaProbe=reading,cudaNumericalProbePassed=reading.get('passed') is True)
            if not provenance['cudaNumericalProbePassed'] and state is None:state='failed';error='CUDA numerical check failed before model execution; inspect execution.log.'
        provenance['compilationCache']['after']=cache_snapshot(prepared['environment'].get('JAX_COMPILATION_CACHE_DIR'))
        provenance.update(peakObservedDeviceGPU_MiB=device_peak,peakObservedHostRSS_MiB=host_peak,gpuMemoryScopes='Device total and owned-process attribution are separate; unknown attribution remains null.',wallSeconds=time.monotonic()-started,peakObservedChildGPU_MiB=peak,childGPUAttributionAvailable=peak is not None,exitCode=child.returncode)
        (folder/'provenance.json').write_text(canonical(provenance))
        # Preserve partial/rejected outputs without upgrading their acceptance.
        candidates=collect(folder,manifest,provenance)
        if state is None:
            if manifest['engine'] in ('structure_screen','proteinmpnn','af2_multimer','solublempnn','esmfold2','esmfold2_fast','rosetta','rfdiffusion'):state='completed'
            else:state='completed' if any(c['outcome'] in ('accepted','passed_upstream_filters') for c in candidates) else 'no_qualified_candidates'
        result={'candidates':len(candidates),'accepted':sum(c['outcome']=='accepted' for c in candidates),'passedUpstreamFilters':sum(c['outcome']=='passed_upstream_filters' for c in candidates),'wallSeconds':time.monotonic()-started,'peakObservedChildGPU_MiB':peak,'exactStepResume':False,'scientificCUDAQualified':False}
        (folder/'result.json').write_text(canonical(result))
        from .watchdog import diagnose
        tail=(folder/'execution.log').read_bytes()[-65536:].decode(errors='replace')
        (folder/'watchdog.json').write_text(canonical(diagnose(state,error or '',tail,provenance.get('cudaProbe'))))
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
