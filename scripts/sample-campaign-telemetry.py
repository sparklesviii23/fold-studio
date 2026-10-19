"""Read-only macOS process measurements; GPU counters are explicitly system-wide."""
import argparse,datetime,hashlib,json,os,pathlib,plistlib,re,sqlite3,subprocess
p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--job',required=True);p.add_argument('--report',required=True);a=p.parse_args();root=pathlib.Path(a.root).resolve();report_path=pathlib.Path(a.report)
def command(args):return subprocess.run(args,capture_output=True,text=True,timeout=15)
db=sqlite3.connect('file:'+str(root/'library.sqlite3')+'?mode=ro',uri=True);row=db.execute('SELECT state,data FROM jobs WHERE id=?',(a.job,)).fetchone();db.close()
if not row:raise SystemExit('Job missing.')
state,data=row[0],json.loads(row[1]);pid=data.get('pid');job_path=root/'jobs'/a.job;settings=job_path/'execution-settings.json';sample={'observedUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'jobState':state,'processes':[]}
if pid:
 parent=command(['/bin/ps','-p',str(pid),'-o','command='])
 if parent.returncode==0 and '--bindcraft-cpu-job '+a.job in parent.stdout:
  group=os.getpgid(pid);all_processes=command(['/bin/ps','-axo','pid,ppid,pgid,pcpu,rss,comm'])
  for line in all_processes.stdout.splitlines()[1:]:
   fields=line.split(None,5)
   if len(fields)!=6 or int(fields[2])!=group:continue
   process={'pid':int(fields[0]),'parentPid':int(fields[1]),'groupId':group,'psCpuPercent':float(fields[3]),'psResidentKiB':int(fields[4]),'executable':fields[5]}
   if process['pid']!=pid:
    memory=command(['/usr/bin/vmmap','-summary',fields[0]])
    for name,pattern in [('physicalFootprint','Physical footprint:'),('peakPhysicalFootprint','Physical footprint (peak):')]:
     found=re.search(re.escape(pattern)+r'\s+(\S+)',memory.stdout)
     if found:process[name]={'rawVmmapUnit':found.group(1),'method':'vmmap -summary; rounded OS process footprint, not total machine memory'}
   sample['processes'].append(process)
 else:sample['processObservation']='Worker no longer exists or its identity changed; no reused PID was measured.'
gpu=subprocess.run(['/usr/sbin/ioreg','-a','-r','-d','1','-c','AGXAccelerator'],capture_output=True,timeout=15)
if gpu.returncode==0:
 try:sample['systemGpuCounters']=[item.get('PerformanceStatistics',{}) for item in plistlib.loads(gpu.stdout)]
 except Exception as error:sample['systemGpuObservationError']=str(error)
lines=(job_path/'execution.log').read_text(errors='replace').splitlines()
for line in reversed(lines):
 if line.startswith('FOLD_PROGRESS '):sample['lastObservedOptimizerProgress']=json.loads(line.removeprefix('FOLD_PROGRESS '));break
existing=json.loads(report_path.read_text()) if report_path.exists() else {'jobId':a.job,'root':str(root),'scope':'Read-only OS process footprint/CPU measurements and system-wide GPU counters during the actual native packaged campaign. GPU utilization includes rendering/other apps and is not exclusive campaign utilization. Samples do not yield a whole-run GPU average or separately measured compilation/inference timing.','runtime':data.get('runtime'),'modelCheckpoints':data.get('checkpointSha256'),'executionSettingsSha256':hashlib.sha256(settings.read_bytes()).hexdigest(),'hardware':{'machine':os.uname().machine,'cpu':command(['/usr/sbin/sysctl','-n','machdep.cpu.brand_string']).stdout.strip(),'memoryBytes':int(command(['/usr/sbin/sysctl','-n','hw.memsize']).stdout.strip()),'macOS':command(['/usr/bin/sw_vers','-productVersion']).stdout.strip()},'samples':[]}
if existing['jobId']!=a.job or existing['root']!=str(root):raise SystemExit('Refusing to mix campaign telemetry identities.')
existing['samples'].append(sample);report_path.write_text(json.dumps(existing,indent=2,allow_nan=False)+'\n');print(json.dumps({'observedUtc':sample['observedUtc'],'jobState':state,'processes':[{key:value for key,value in process.items() if key in ('pid','psCpuPercent','peakPhysicalFootprint')} for process in sample['processes']],'systemGpuCounters':sample.get('systemGpuCounters')}))
