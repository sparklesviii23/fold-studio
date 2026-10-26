#!/usr/bin/env python3
"""One explicitly approved CPU qualification, with persisted exact-once job IDs.

Source preparation $1, public reference preparation $0.50, four bounded CPU
calculations $0.50. Estimates are not provider-enforced billing limits.
Never invoke without fresh approval of this exact $2 scope. No GPU or models.
"""
import argparse,datetime,json,os,pathlib,sys,time
REPO=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(REPO/'scientific'),str(REPO/'remote_worker')]
PATH=REPO/'reports/editcraft/offtarget-validation.json'
GUIDE='ACGTTGCAACGTTGCAACGT'
def reverse(text):return text.translate(str.maketrans('ACGT','TGCA'))[::-1]
def oracle(p):
 # Intentionally independent exhaustive reference, only for tiny synthetic cases.
 records={};name=None
 for line in p['reference']['fasta'].splitlines():
  if line.startswith('>'):name=line[1:].split()[0];records[name]=''
  elif line.strip():records[name]+=line.strip().upper()
 expected=[];width=23
 for contig,source in records.items():
  for start in range(len(source)):
   if p['reference']['topology']=='linear' and start+width>len(source):continue
   forward=''.join(source[(start+i)%len(source)] for i in range(width))
   for strand,target in [('+',forward),('-',reverse(forward))]:
    if target[21:]!='GG':continue
    for guide in p['guides']:
     differences=sum(a!=b for a,b in zip(guide['sequence'],target[:20]))
     if differences<=p['mismatches']:expected.append([guide['id'],contig,start,strand,differences,target])
 return sorted(expected)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--approved-total-usd',type=float,required=True);parser.add_argument('--resume-setup-after-inspection',action='store_true');args=parser.parse_args()
 if args.approved_total_usd!=2:raise SystemExit('Requires fresh approval of this exact $2 CPU-only source/reference/validation scope.')
 previous=json.loads(PATH.read_text()) if PATH.exists() else None
 if previous and (not args.resume_setup_after_inspection or previous.get('experiments') or previous.get('deployment') or previous.get('referencePreparation')):raise SystemExit('Existing qualification evidence preserved. Reconcile its job IDs in the app; no automatic scientific retry. Setup-only resume requires manual inspection before any deployment or science was recorded.')
 from worker import Service
 from cloud_accounts import environment
 from fold_rapid.editcraft_toolchain import MANIFEST,manifest_sha
 service=Service(REPO.parent/'validation/bindcraft-fab-amme-native');project='a8def624-3640-49e8-89cc-7012f1e8d924'
 for key in ('MODAL_TOKEN_ID','MODAL_TOKEN_SECRET','MODAL_CONFIG_PATH','MODAL_PROFILE'):os.environ.pop(key,None)
 os.environ.update(environment(service));os.environ['FOLD_EDITCRAFT_CHILD']='1'
 evidence={'state':'started','started':datetime.datetime.now(datetime.timezone.utc).isoformat(),'maximumApprovedUSD':2,'phaseAllowances':{'deploymentUSD':1,'referenceUSD':.5,'scientificReferencesUSD':.5},'manifestSha256':manifest_sha(),'scope':'Pinned stable Cas-OFFinder CPU build, NCBI E. coli complete assembly, four bounded public/synthetic calculations. No GPU, private uploads, trained models or automatic retries.','providerReportedUSD':None,'experiments':[],'independentScientificBenchmarkComplete':False}
 if previous:evidence['previousSetupAttempts']=[previous]
 def save():
  temp=PATH.with_suffix('.pending');temp.write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n');temp.replace(PATH)
 def rpc(action,**p):return service.dispatch(action,{'projectId':project,**p})
 def run(operation,params):
  plan={'schemaVersion':1,'seconds':120,'stages':[{'id':'reference','operation':operation,'parameters':params}]};job=rpc('editcraft_prepare',plan=plan,allowanceUSD=.15)
  entry={'id':job['id'],'state':job['state'],'plan':plan,'estimatedUSD':job['estimatedUSD']};evidence['experiments'].append(entry);save()
  if sum(e['estimatedUSD'] for e in evidence['experiments'])>.5:raise RuntimeError('This phase would exceed its approved local estimate reserve.')
  job=rpc('editcraft_submit',id=job['id'],approvedTransfer=True,approvedCost=True);entry.update(state=job['state']);save();print(operation,'submitted',job['id'],flush=True)
  deadline=time.monotonic()+200
  while time.monotonic()<deadline:
   job=rpc('editcraft_refresh',id=job['id']);entry.update(state=job['state'],remote=job.get('remote'));save()
   if job['state'] in ('completed','failed','cancelled','deadline_exceeded'):break
   time.sleep(5)
  if job['state']!='completed':raise RuntimeError('Reference calculation did not complete. Keep its saved identity; no automatic retry.')
  job=rpc('editcraft_result',id=job['id']);entry['result']=job['result'];save();return job['result']['results']['reference']['result'],entry
 save()
 try:
  # A lease in deploy() prevents replacing the service under live scientific work.
  evidence['deployment']=rpc('editcraft_deploy',approvedCPUDeployment=True,maxApprovedUSD=1,includeModelRuntimes=True,includeToolRuntimes=True);save();print('CPU source deployed; original trained-model manifest retained',flush=True)
  identity='ecoli-k12-ASM584v2';evidence['referencePreparation']=rpc('editcraft_reference_prepare',referenceId=identity,approvedReferenceDownload=True,maxApprovedUSD=.5);save()
  deadline=time.monotonic()+660;receipt=None
  while time.monotonic()<deadline:
   health=rpc('editcraft_health');evidence['health']=health;save();receipt=health.get('references',{}).get(identity)
   if receipt:break
   if health.get('referencePreparation',{}).get('state')=='failed':raise RuntimeError('Reference preparation failed; preserve original state, no retry.')
   time.sleep(5)
  if not receipt:raise RuntimeError('Reference preparation needs reconciliation; no duplicate download.')
  if {k:v['length'] for k,v in receipt['contigs'].items()}!=MANIFEST['references'][identity]['contigs']:raise RuntimeError('Published assembly contig coverage does not match.')
  site=GUIDE+'AGG';variant='T'+GUIDE[1:]+'TGG'
  cases=[{'nuclease':'SpCas9','pam':'NGG','mismatches':1,'guides':[{'id':'match','sequence':GUIDE},{'id':'absent','sequence':'G'*20}],'reference':{'kind':'inline','assembly':'synthetic-strands-v1','topology':'linear','fasta':'>forward\n'+site+'\n>reverse\n'+reverse(variant)+'\n'}},{'nuclease':'SpCas9','pam':'NGG','mismatches':0,'guides':[{'id':'origin','sequence':GUIDE}],'reference':{'kind':'inline','assembly':'synthetic-circle-v1','topology':'circular','fasta':'>circle\n'+site[11:]+site[:11]+'\n'}}]
  for params in cases:
   result,entry=run('cas_offinder',params);actual=sorted([r['guideId'],r['contig'],r['upstreamStart0'],r['strand'],r['mismatches'],r['sequence5to3']] for r in result['rows']);expected=oracle(params)
   entry['referenceChecks']={'independentExhaustiveOracle':expected,'actual':actual,'exactAgreement':actual==expected,'scope':'Independent exact enumeration on small synthetic references; not a genome-wide or biological activity benchmark.'};save()
   if actual!=expected:raise RuntimeError('Upstream enumeration disagrees with the independent synthetic oracle.')
  reference={'id':identity,'fastaSha256':receipt['fastaSha256']};window,entry=run('reference_window',{'reference':reference,'contig':'NC_000913.3','start':1,'end':1000,'strand':1})
  seq=window['sequence'];start=next(i for i in range(len(seq)-22) if seq[i+21:i+23]=='GG');spacer=seq[start:start+20]
  params={'nuclease':'SpCas9','pam':'NGG','mismatches':0,'guides':[{'id':'reference_spacer','sequence':spacer}],'reference':{'kind':'catalog',**reference}}
  result,entry=run('cas_offinder',params);entry['referenceChecks']={'assembly':receipt['assembly'],'allContigsAndOriginalBytesVerified':result['reference']==receipt,'expectedObservedSite':{'contig':'NC_000913.3','start':start+1,'strand':'+'},'containsExactObservedSite':any(r['contig']=='NC_000913.3' and r['start']==start+1 and r['strand']=='+' and r['mismatches']==0 for r in result['rows']),'coverage':'Complete public bacterial assembly; no human-genome qualification inferred.'};save()
  if not entry['referenceChecks']['allContigsAndOriginalBytesVerified'] or not entry['referenceChecks']['containsExactObservedSite']:raise RuntimeError('Whole-reference search did not retain the expected original site or reference receipt.')
  evidence.update(state='reference_runs_completed',finished=datetime.datetime.now(datetime.timezone.utc).isoformat(),scientificReferenceChecksPassed=True,nativeFormVerification='tracked separately',fullEditCraftComplete=False);save();print('Four CPU references completed; no whole-platform completion claim',flush=True)
 except BaseException as exc:
  evidence.update(state='stopped_for_inspection',failureType=type(exc).__name__,failure=str(exc));save();raise
 finally:service.db.close()
if __name__=='__main__':main()
