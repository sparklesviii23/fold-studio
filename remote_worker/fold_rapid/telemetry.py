"""Observed device and owned process resources. Missing data stays unknown."""
import csv,os,pathlib,subprocess,time

def sample(pid):
    result={'timestampUnix':time.time(),'scientificPID':pid,'device':None,'processRSSMiB':None,'errors':[]}
    try:
        query='name,uuid,memory.total,memory.used,utilization.gpu,utilization.memory'
        p=subprocess.run(['nvidia-smi','--query-gpu='+query,'--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=2)
        if p.returncode:raise ValueError('nvidia-smi query returned '+str(p.returncode))
        rows=list(csv.reader(p.stdout.splitlines()))
        if rows:
            name,uuid,total,used,util,memutil=[v.strip() for v in rows[0]]
            def numeric(v):
                try:return float(v)
                except ValueError:return None
            result['device']={'name':name,'uuid':uuid,'totalMiB':numeric(total),'usedMiB':numeric(used),'utilizationPercent':numeric(util),'memoryUtilizationPercent':numeric(memutil),'scope':'device_total_not_attributed_to_scientific_process'}
    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:result['errors'].append(type(exc).__name__+': '+str(exc)[:200])
    try:
        status=pathlib.Path('/proc')/str(pid)/'status'
        for line in status.read_text().splitlines():
            if line.startswith('VmRSS:'):result['processRSSMiB']=float(line.split()[1])/1024
    except (OSError,ValueError) as exc:result['errors'].append('Process RSS unavailable: '+type(exc).__name__)
    return result
