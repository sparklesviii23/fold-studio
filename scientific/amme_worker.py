"""macOS supervisor for an isolated Fab worker; imports no scientific runtime.

The14GiB ceiling includes compressed task allocations. An asynchronous allocator
can overshoot between samples; the guard is a stop policy, not a reservation.
"""
import json
import os
import pathlib
import shutil
import signal
import subprocess
import tempfile
import time

from amme_campaign import (DISK_RESERVE, FOOTPRINT_LIMIT, SSD_QUOTA,
                           atomic_json, environment)
from process_memory import exceeds_footprint_budget, process_memory


def start_idle_assertion(pid):
    """Keep a long Fab job running through idle time; display sleep is unchanged."""
    if type(pid) is not int or pid <= 0:
        raise ValueError('A positive worker PID is required for the idle assertion.')
    try:
        process=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(pid)],
                                 stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return process,{'state':'active','mode':'prevent_idle_sleep','workerPid':pid,
                        'assertionPid':process.pid,'displaySleepUnchanged':True}
    except OSError as error:
        return None,{'state':'unavailable','error':str(error),'workerPid':pid}


def release_idle_assertion(process):
    if process is None:return None
    if process.poll() is None:
        try:process.terminate()
        except ProcessLookupError:pass
        try:process.wait(timeout=2)
        except subprocess.TimeoutExpired:process.kill();process.wait()
    return process.returncode


def cleanup_stale(directory):
    """Reclaim only marked private tapes after BOTH owning processes are gone."""
    removed=[]
    def inactive(pid, identity):
        if type(pid) is not int or pid<=0 or type(identity) is not int or identity<=0:
            return False
        try:
            return process_memory(pid)['processStartAbstime'] != identity
        except OSError:
            try:os.kill(pid,0)
            except ProcessLookupError:return True
            except PermissionError:pass
            return False
    for folder in pathlib.Path(directory).glob('amme-worker-*'):
        owner=folder/'owner.json'
        if folder.is_symlink() or not folder.is_dir() or owner.is_symlink():continue
        try:
            if owner.stat().st_size>32768:continue
            value=json.loads(owner.read_text())
            if value.get('ownerFormat')!='fold-amme-private-v1':continue
            if not all(inactive(value.get(key+'Pid'),value.get(key+'Identity')) for key in ('supervisor','worker')):continue
            shutil.rmtree(folder);removed.append(folder.name)
        except (OSError,ValueError,TypeError,AttributeError):continue
    return removed


def run_guarded(command, *, env, folder, timeout_seconds=48 * 3600,
                footprint_limit=FOOTPRINT_LIMIT, scratch_parent=None):
    if not 0 < footprint_limit <= FOOTPRINT_LIMIT:
        raise ValueError('Fab worker budget must be positive and cannot exceed14GiB.')
    folder = pathlib.Path(folder).resolve(strict=True)
    scratch_parent = pathlib.Path(scratch_parent).resolve(strict=True) if scratch_parent else folder
    recovered=cleanup_stale(scratch_parent)
    if shutil.disk_usage(scratch_parent).free < SSD_QUOTA + DISK_RESERVE:
        raise ValueError('Fab SSD execution requires10GiB tape space plus2GiB free-space reserve.')
    started = time.monotonic()
    samples = []
    report = {'state': 'starting', 'memoryCeilingBytes': footprint_limit,
              'reclaimedStalePrivateTapes': recovered,
              'timeoutSeconds': timeout_seconds,
              'ssdQuotaBytes': SSD_QUOTA, 'diskReserveBytes': DISK_RESERVE,
              'memoryMeasurement': 'macOS libproc physical footprint including compressed allocations; RSS also checked.',
              'scope': 'Resource supervision; no scientific acceptance or optimizer-step recovery implied.'}
    child = None
    idle_assertion = None
    previous_handler = signal.getsignal(signal.SIGTERM)

    def interrupted(signum, frame):
        raise KeyboardInterrupt('Fab supervisor received ' + signal.Signals(signum).name)

    def stop():
        if child is not None and child.poll() is None:
            try:
                child.terminate()
            except ProcessLookupError:
                child.wait(); return
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()

    with tempfile.TemporaryDirectory(prefix='amme-worker-', dir=scratch_parent) as scratch:
        scratch = pathlib.Path(scratch)
        scratch.chmod(0o700)
        try:
            signal.signal(signal.SIGTERM, interrupted)
            launch_env = environment(env)
            launch_env.update(FOLD_AMME_POLICY='fab-cpu-ssd-v1', FOLD_AMME_SCRATCH=str(scratch))
            atomic_json(folder / 'amme-stage.json', {'stage': 'worker_initialization'})
            # The native CPU campaign explicitly disables process fan-out. Keep
            # this single scientific child in the native job's original group:
            # cancellation and recovery can still find it if its parent dies.
            child = subprocess.Popen(command, env=launch_env)
            idle_assertion,report['idleSleepPrevention']=start_idle_assertion(child.pid)
            supervisor_identity = process_memory(os.getpid())['processStartAbstime']
            report.update(state='running', workerPid=child.pid)
            atomic_json(folder / 'amme-memory.json', report)
            identity = None
            last_sample = 0
            while child.poll() is None:
                try:
                    reading = process_memory(child.pid)
                except OSError:
                    if child.poll() is not None:
                        break
                    raise
                if identity is None:
                    identity=reading['processStartAbstime']
                    atomic_json(scratch/'owner.json',{'ownerFormat':'fold-amme-private-v1',
                        'supervisorPid':os.getpid(),'supervisorIdentity':supervisor_identity,
                        'workerPid':child.pid,'workerIdentity':identity})
                if reading['processStartAbstime'] != identity:
                    raise RuntimeError('Fab worker identity changed; stopping resource supervision.')
                report['peakFootprintBytes'] = max(report.get('peakFootprintBytes', 0), reading['physicalFootprintBytes'])
                report['peakResidentBytes'] = max(report.get('peakResidentBytes', 0), reading['residentBytes'])
                if exceeds_footprint_budget(reading, footprint_limit):
                    raise RuntimeError('Fab worker crossed the configured task-memory safety ceiling (' + str(footprint_limit) + ' bytes; at most14GiB).')
                now = time.monotonic()
                if now - last_sample >= 1:
                    last_sample = now
                    pressure = int(subprocess.check_output(
                        ['/usr/sbin/sysctl', '-n', 'kern.memorystatus_vm_pressure_level'], text=True, timeout=2).strip())
                    swap = subprocess.check_output(['/usr/sbin/sysctl', '-n', 'vm.swapusage'], text=True, timeout=2).strip()
                    try:
                        stage = json.loads((folder / 'amme-stage.json').read_text()).get('stage', 'initialization')
                    except (OSError, ValueError):
                        stage = 'initialization'
                    samples.append({**reading, 'elapsedSeconds': now - started, 'stage': stage,
                                    'systemMemoryPressureLevel': pressure, 'swapUsage': swap})
                    report['highestSystemMemoryPressureLevel'] = max(report.get('highestSystemMemoryPressureLevel', 0), pressure)
                    report.setdefault('initialSwapUsage', swap)
                    report['latestSwapUsage'] = swap
                    # Bound long-campaign telemetry. Full per-step events are in
                    # the existing log, while these are the latest60samples.
                    samples = samples[-60:]
                    report['latestSamples'] = samples
                    atomic_json(folder / 'amme-memory.json', report)
                    if pressure >= 4:
                        raise RuntimeError('macOS reports critical memory pressure; Fab worker stopped.')
                if now - started > timeout_seconds:
                    raise RuntimeError('Fab worker reached the bounded execution timeout.')
                time.sleep(.1)
            report.update(state='finished' if child.returncode == 0 else 'worker_failed',
                          exitCode=child.returncode)
        except BaseException as error:
            report.update(state='interrupted' if isinstance(error, KeyboardInterrupt) else 'bounded_resource_refusal',
                          error=type(error).__name__ + ': ' + str(error))
            raise
        finally:
            stop()
            assertion_exit=release_idle_assertion(idle_assertion)
            if idle_assertion is not None:
                report['idleSleepPrevention'].update(state='released',exitCode=assertion_exit)
            signal.signal(signal.SIGTERM, previous_handler)
            report['elapsedSeconds'] = time.monotonic() - started
            report['exitCode'] = child.returncode if child is not None else None
            # Temp directory is owned by this supervisor; no neighbor is removed.
            shutil.rmtree(scratch)
            report['ownedScratchRemoved'] = not scratch.exists()
            atomic_json(folder / 'amme-memory.json', report)
    return subprocess.CompletedProcess(command, child.returncode)
