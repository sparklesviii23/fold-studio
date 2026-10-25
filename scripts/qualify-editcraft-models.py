#!/usr/bin/env python3
"""Explicitly approved, bounded PUBLIC CPU references; never install or launch a GPU.
Run with the existing provider interpreter. No automatic retries. Saved jobs survive
this client; resume their identities with normal EditCraft controls after interruption.
"""
import argparse,csv,io,json,os,pathlib,re,sys,time,datetime
REPO=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(REPO/'scientific'),str(REPO/'remote_worker')]

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--approved-cpu-reference-allowance',type=float,required=True);parser.add_argument('--resume-after-inspection',action='store_true');parser.add_argument('--additional-editor-contexts',action='store_true');args=parser.parse_args()
 if args.approved_cpu_reference_allowance!=1:raise SystemExit('Requires the separately approved $1 public CPU reference scope, not a GPU authorization.')
 from worker import Service
 from cloud_accounts import environment
 s=Service(REPO.parent/'validation/bindcraft-fab-amme-native');project='a8def624-3640-49e8-89cc-7012f1e8d924'
 for k in ('MODAL_TOKEN_ID','MODAL_TOKEN_SECRET','MODAL_CONFIG_PATH','MODAL_PROFILE'):os.environ.pop(k,None)
 os.environ.update(environment(s));os.environ['FOLD_EDITCRAFT_CHILD']='1'
 def rpc(action,**payload):return s.dispatch(action,{'projectId':project,**payload})
 discovery=REPO/'reports/editcraft/discovery'
 with (discovery/'uzh-dqbm-cmi-crispr--sample_data-abemax_sampledata.csv').open(encoding='utf-8-sig') as f:sample=list(csv.DictReader(f))[:2]
 prime_text=(discovery/'uzh-dqbm-cmi-PRIDICT2--README.md').read_text();prime=re.search(r'--sequence "([ACGT]+\([ACGT]/[ACGT]\)[ACGT]+)"',prime_text).group(1)
 cases=[('rs3_activity',{'nuclease':'SpCas9','tracrRNA':'Hsu2013','sequences':[{'id':'official_'+str(i+1),'sequence':seq} for i,seq in enumerate(['GACGAAAGCGACAACGCGTTCATCCGGGCA','AGAAAACACTAGCATCCCCACCCGCGGACT'])]}),('bedict_per_base',{'editor':'ABEmax','sequences':[{'id':r['ID'],'sequence':r['seq']} for r in sample]}),('pridict2_design',{'editSequence':prime,'cellContext':'HEK','folds':5}),('rna_ensemble',{'sequence':'GGGAAACCC','temperatureC':37,'pairProbabilityThreshold':.001})]
 if args.additional_editor_contexts:
  cases += [('bedict_per_base',{**cases[1][1],'editor':'BE4max'}),('rs3_activity',{**cases[0][1],'tracrRNA':'Chen2013'})]
 evidence={'state':'running','started':datetime.datetime.now(datetime.timezone.utc).isoformat(),'maximumApprovedUSD':1,'scope':'Four public CPU reference calculations; no GPU, no private uploads, no automatic retries','projectId':project,'experiments':[],'scientificBenchmarkComplete':False,'nativeWorkflowDemonstrated':False}
 path=REPO/'reports/editcraft/model-validation.json'
 if path.is_file():
  if not args.resume_after_inspection:raise SystemExit('Existing evidence file preserved. Inspect recorded job identities; do not automatically repeat these calculations.')
  evidence=json.loads(path.read_text())
  if any(e['state'] not in ('completed','failed','cancelled','deadline_exceeded','prepared') for e in evidence['experiments']):raise SystemExit('A saved calculation still needs reconciliation. No duplicate launch.')
  evidence['state']='resumed_after_manual_inspection';evidence.pop('failure',None);evidence.pop('failureType',None)
 def save():
  pending=path.with_suffix('.pending');pending.write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n');pending.replace(path)
 save()
 try:
  for operation,params in cases:
   if any(e['operation']==operation and e['state']=='completed' and e['input']['stages'][0]['parameters']==params for e in evidence['experiments']):continue
   plan={'schemaVersion':1,'seconds':600,'stages':[{'id':'reference','operation':operation,'parameters':params}]}
   job=rpc('editcraft_prepare',plan=plan,allowanceUSD=.25);entry={'operation':operation,'id':job['id'],'input':plan,'estimatedUSD':job['estimatedUSD'],'state':'prepared'};evidence['experiments'].append(entry);save()
   if sum(e['estimatedUSD'] for e in evidence['experiments'])>1:raise RuntimeError('Public reference reserve would exceed the approved scope.')
   print(operation,'prepared',job['id'],flush=True);job=rpc('editcraft_submit',id=job['id'],approvedTransfer=True,approvedCost=True);entry['state']=job['state'];save()
   deadline=time.monotonic()+680
   while time.monotonic()<deadline:
    job=rpc('editcraft_refresh',id=job['id']);entry['state']=job['state'];entry['remote']=job.get('remote');save()
    if job['state'] in ('completed','failed','cancelled','deadline_exceeded'):break
    time.sleep(10)
   else:raise RuntimeError('Client wait ended; reconnect to the saved job, never resubmit.')
   if job['state']!='completed':raise RuntimeError(operation+' did not complete; preserve scientific failure and stop this reference sequence.')
   job=rpc('editcraft_result',id=job['id']);entry['result']=job['result'];save();r=job['result']['results']['reference']['result'];checks={}
   if operation=='rs3_activity':
    expected=[-.90030944,1.11451622] if params['tracrRNA']=='Hsu2013' else None;values=[row['predictedActivity'] for row in r['rows']];checks={'publishedREADMEExpected':expected,'actual':values,'absoluteTolerance':5e-6,'agrees':all(abs(x-y)<=5e-6 for x,y in zip(expected,values)) if expected else None,'isIndependentBenchmark':False}
   elif operation=='bedict_per_base':checks={'allFiveRunsRetained':all(len(row['runProbabilities'])==5 for row in r['rows']),'returnedBases':len(r['rows']),'publishedExpectedNumericValues':None,'isIndependentBenchmark':False}
   elif operation=='pridict2_design':checks={'candidateCount':len(r['rows']),'foldsPerModel':r['foldsPerModel'],'modelGroups':r['upstreamModelGroups'],'publishedExpectedNumericValues':None,'isIndependentBenchmark':False}
   else:checks={'expectedMFE':'(((...)))','mfeStructureMatches':r['dotBracket']=='(((...)))','ensembleEnergyAtMostMFE':r['ensembleFreeEnergyKcalMol']<=r['mfeKcalMol']+1e-5,'marginalsBounded':all(0<=v<=1 for v in r['unpairedProbabilities']),'isIndependentBenchmark':False}
   entry['referenceChecks']=checks;save();print(operation,'completed',json.dumps(checks),flush=True)
  evidence['state']='reference_runs_completed';save()
 except BaseException as exc:
  evidence['state']='stopped_for_inspection';evidence['failureType']=type(exc).__name__;evidence['failure']=str(exc);save();raise
 finally:s.db.close()
if __name__=='__main__':main()
