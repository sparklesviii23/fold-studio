"""One approved remote installation plan; no client-side scientific loop."""
import json
import os
import pathlib
import signal
import subprocess
import sys
import time
from .contracts import canonical,digest
from .unified import atomic
from .execution import require_cloud

PLAN='bindcraft-dual-mpnn-af2'
STEPS=(('runtime','bindcraft2'),('runtime','boltzgen'),('models','bindcraft2'),('models','solublempnn'))


def execute(command,output,timeout):
    child=subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},start_new_session=True)
    try:return child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        # pip/build subprocesses inherit this group; don't commit storage while
        # a surviving installer still writes to it after its supervisor exits.
        try:os.killpg(child.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        child.wait()
        raise


def describe(plan):
    if plan!=PLAN:raise ValueError('Unknown reviewed cloud bootstrap plan.')
    return {'plan':PLAN,'steps':[{'kind':k,'engine':e} for k,e in STEPS],'scientificEngines':['bindcraft2','proteinmpnn','solublempnn','af2_multimer'],'approximateAFArchiveTransferGB':5.6,'approximateRetainedAFWeightsGB':2.6,'solubleMPNNBytes':6681301,'otherStorage':'Pinned CUDA JAX, Torch, BoltzGen and ESM runtime dependencies; no ESM or BoltzGen trained checkpoints in this plan.','gpuComputation':False,'scientificQualified':False}


def run(root,plan,key,approved=False,publish=lambda row:None):
    require_cloud({'mode':'cloud','provider':'modal','localFallback':False});description=describe(plan)
    if approved is not True:raise ValueError('Approve CPU setup, checkpoint downloads and storage for this exact plan.')
    if not isinstance(key,str) or not key or len(key)>100:raise ValueError('A stable bootstrap request key is required.')
    root=pathlib.Path(root);folder=root/'bootstraps'/digest(key.encode());folder.mkdir(parents=True,exist_ok=True);path=folder/'status.json'
    if path.is_file():return json.loads(path.read_text())
    row={'plan':description,'state':'running','started':time.time(),'steps':[],'gpuStarted':False,'scientificQualified':False,'requestKey':key};atomic(path,row);publish(row)
    deadline=time.monotonic()+1680  # Leave two minutes to persist a receipt before the provider timeout.
    try:
        for kind,engine in STEPS:
            entry={'kind':kind,'engine':engine,'state':'running','started':time.time()};row['steps'].append(entry);atomic(path,row);publish(row)
            command=[sys.executable,'-B','-m','fold_rapid.install' if kind=='runtime' else 'fold_rapid.models','--root',str(root),'--engine',engine,'--approve']
            log=folder/(kind+'-'+engine+'.log')
            try:
                with log.open('ab') as output:exit_code=execute(command,output,timeout=max(1,deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                entry.update(state='failed',error='Reviewed CPU setup time allowance exhausted.',finished=time.time(),logArtifact=str(log.relative_to(root)))
                raise ValueError('CPU setup time allowance exhausted; partial cache and logs retained. No automatic retry.') from None
            entry.update(state='installed' if exit_code==0 else 'failed',exitCode=exit_code,finished=time.time(),logArtifact=str(log.relative_to(root)))
            atomic(path,row);publish(row)
            if exit_code:raise ValueError('Remote '+kind+' setup failed for '+engine+'; log and partial cache retained. No automatic retry.')
        from .registry import inventory
        row.update(state='models_cached_gpu_validation_pending',inventory=inventory(root),finished=time.time())
    except Exception as exc:row.update(state='failed',error=str(exc)[:2000],finished=time.time(),automaticRetry=False)
    atomic(path,row);publish(row);return row
