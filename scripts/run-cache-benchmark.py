#!/usr/bin/env python3
"""Run the two explicitly approved cache trials once; never retry a submission."""
import fcntl,json,pathlib,sys,time
REPO=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO/'scientific'))
from worker import Service
from biology_modal import read
FOLDER=REPO/'reports/cache-benchmark'
PROJECT='0e985c2f-7583-4634-a416-c525790da308'
ROOT=(REPO/'../validation/bindcraft-fab-amme-native').resolve()
def write(value):
 p=FOLDER/'results.json';t=p.with_suffix('.pending');t.write_text(json.dumps(value,indent=2));t.replace(p)
def run():
 approval=json.loads((FOLDER/'proposal.json').read_text())
 if approval.get('approvedTotalUSD')!=4.5:raise ValueError('Explicit benchmark approval missing.')
 if (FOLDER/'results.json').exists():raise ValueError('Benchmark already recorded; no automatic resubmission.')
 report={'state':'waiting_for_cpu_deployment','runs':[],'totalApprovedUSD':4.5,'speedupMeasured':False}
 write(report)
 until=time.monotonic()+600
 while True:
  deployment=json.loads((ROOT/'cloud-engine-deployment/status.json').read_text())
  if deployment['state']=='deployed':break
  if deployment['state']=='failed' or time.monotonic()>until:raise ValueError('CPU deployment did not complete; no GPU submitted.')
  time.sleep(10)
 s=Service(ROOT)
 try:
  original=read(s,{'projectId':PROJECT,'id':approval['sourceRequest']})
  m=original['manifest'];g=m['generators']
  if len(g)!=1 or g[0]['engine']!='bindcraft2':raise ValueError('Benchmark source must contain one BindCraft generator.')
  for index in range(2):
   report['state']='preparing';write(report)
   params={'projectId':PROJECT,'structureId':original['sourceRecordId'],'targetChains':m['target']['chains'],'binderChains':m['parents'][0]['binderChains'] if m['parents'] else [],'generators':g,'workflow':{'redesign':[],'predictors':[],'rosetta':False,'count':1,'purpose':'compilation_benchmark'},'strategy':m['strategy'],'seed':m['seed'],'seconds':1200,'stageSeconds':900,'stageLimitsSeconds':{'bindcraft2':900},'maxEstimatedUSD':1.75,'constraints':m.get('constraints',{}),'policy':m['policy'],'resourcePricing':m['budget']['resourcePricing']}
   row=s.dispatch('biology_unified_prepare',params)
   if row['configuration']!=original['configuration']:raise ValueError('Compute profile changed; benchmark stopped before launch.')
   trial={'index':index+1,'requestId':row['id'],'state':'prepared','quote':row['estimate'],'baselineSourceCampaign':original['campaignId']}
   report['runs'].append(trial);write(report)
   # Durable intent precedes dispatch. Any uncertainty stops this script.
   trial['state']='submission_attempted';report['state']='running';write(report)
   row=s.dispatch('biology_modal_submit',{'projectId':PROJECT,'id':row['id'],'approvedResearchTransfer':True,'approvedWorkload':True,'maxEstimatedCostUSD':1.75})
   trial.update(state=row['state'],campaignId=row.get('campaignId'),callId=row.get('callId'));write(report)
   until=time.monotonic()+1500
   while True:
    row=s.dispatch('biology_modal_refresh',{'projectId':PROJECT,'id':trial['requestId']})
    trial.update(state=row['state'],campaignId=row.get('campaignId'),remote=row.get('remote'));write(report)
    if row['state'] in ('COMPLETED','PARTIALLY_COMPLETE','FAILED','CANCELLED'):break
    if time.monotonic()>until:raise ValueError('Polling limit reached; inspect existing remote request. No retry or second launch.')
    time.sleep(45)
   stages=row.get('remote',{}).get('stages',[])
   if len(stages)!=1 or stages[0]['state']!='STAGE_COMPLETE':raise ValueError('First/second benchmark stage did not finish; no further paid work.')
  a,b=[r['remote']['stages'][0]['result']['wallSeconds'] for r in report['runs']]
  report.update(state='completed',speedupMeasured=True,firstWallSeconds=a,secondWallSeconds=b,speedup=a/b,threeTimesFaster=a/b>=3,scope='Paired runner wall time, not isolated compilation or numerical equivalence; cache hits need execution-log evidence.')
  write(report)
 finally:s.db.close()
if __name__=='__main__':
 FOLDER.mkdir(parents=True,exist_ok=True)
 with (FOLDER/'benchmark.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  if (FOLDER/'results.json').exists():raise SystemExit('Benchmark already recorded; existing evidence left unchanged.')
  try:run()
  except BaseException as exc:
   p=FOLDER/'results.json';r=json.loads(p.read_text()) if p.exists() else {}
   r.update(state='stopped',error=str(exc),automaticRetry=False);write(r);raise
