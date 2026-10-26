#!/usr/bin/env python3
"""One separately approved $2 public CPU single-cell qualification. Never retry science.

$1 isolated runtime deployment, $0.50 public 5.9 MB H5AD preparation,
$0.50 one 2-CPU/8-GiB reference and actual processed-artifact transfer check.
These are estimate allowances, not provider-enforced billing caps.
"""
import argparse,datetime,hashlib,json,math,os,pathlib,sys,tempfile,time
REPO=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(REPO/'scientific'),str(REPO/'remote_worker')]
PATH=REPO/'reports/editcraft/singlecell-validation.json'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--approved-total-usd',type=float,required=True);parser.add_argument('--resume-after-inspection',action='store_true');parser.add_argument('--verify-saved-artifact',action='store_true');args=parser.parse_args()
 previous=json.loads(PATH.read_text()) if PATH.exists() else None
 if args.verify_saved_artifact:
  if args.approved_total_usd!=1.25 or args.resume_after_inspection or not previous or previous.get('state')!='stopped_for_inspection' or previous.get('experiment',{}).get('state')!='completed' or not previous.get('referenceChecks',{}).get('allProcessedRoundTripChecks'):raise SystemExit('Saved-artifact verification requires the completed original calculation and inspected transfer failure. Never repeat science.')
  return verify_saved_artifact(previous)
 if args.resume_after_inspection:
  if args.approved_total_usd!=1.25 or not previous or previous.get('state')!='stopped_for_inspection' or previous.get('experiment',{}).get('state') not in ('failed','cancelled','deadline_exceeded'):raise SystemExit('Manual resume requires inspection of a stopped attempt and fresh $1.25 approval. Never duplicate active or completed science.')
 elif args.approved_total_usd!=2 or previous:raise SystemExit('Initial qualification requires fresh $2 approval and no previous evidence. Existing attempts are never overwritten or repeated automatically.')
 from worker import Service
 from cloud_accounts import environment
 from fold_rapid.editcraft_singlecell import MANIFEST,manifest_sha
 service=Service(REPO.parent/'validation/bindcraft-fab-amme-native');project='a8def624-3640-49e8-89cc-7012f1e8d924'
 for key in ('MODAL_TOKEN_ID','MODAL_TOKEN_SECRET','MODAL_CONFIG_PATH','MODAL_PROFILE'):os.environ.pop(key,None)
 os.environ.update(environment(service));os.environ['FOLD_EDITCRAFT_CHILD']='1'
 evidence={'state':'started','started':datetime.datetime.now(datetime.timezone.utc).isoformat(),'maximumApprovedUSD':args.approved_total_usd,'phaseAllowances':{'deploymentUSD':1,'datasetPreparationUSD':0 if previous else .5,'referenceAndTransferUSD':.25 if previous else .5},'manifestSha256':manifest_sha(),'scope':'Pinned isolated Scanpy CPU runtime, original public PBMC3k H5AD (5,855,727 bytes), one bounded QC/normalization/PCA/UMAP/Leiden/marker reference and processed H5AD transfer integrity check. No GPU, trained models, private uploads or automatic scientific retries.','providerReportedUSD':None,'independentBiologicalBenchmarkComplete':False,'fullEditCraftComplete':False}
 if previous:evidence['previousAttempts']=[previous]
 def save():
  pending=PATH.with_suffix('.pending');pending.write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n');pending.replace(PATH)
 def rpc(action,**payload):return service.dispatch(action,{'projectId':project,**payload})
 save()
 try:
  evidence['deployment']=rpc('editcraft_deploy',approvedCPUDeployment=True,maxApprovedUSD=1,includeModelRuntimes=True,includeToolRuntimes=True,includeSinglecellRuntime=True);save();print('Scientific CPU runtimes deployed; original model assets retained',flush=True)
  spec=MANIFEST['datasets']['pbmc3k'];deadline=time.monotonic()+240;receipt=None
  if not previous:evidence['datasetPreparation']=rpc('editcraft_dataset_prepare',kind='public',datasetId='pbmc3k',approvedTransfer=True,approvedCost=True,maxApprovedUSD=.5);save()
  else:evidence['datasetPreparation']={'state':'reusing_existing_verified_dataset','sha256':spec['sha256'],'newTransferApproved':False};save()
  while time.monotonic()<deadline:
   health=rpc('editcraft_health');evidence['health']=health;receipt=health.get('datasets',{}).get(spec['sha256']);save()
   if receipt:break
   if health.get('datasetPreparation',{}).get('state')=='failed':raise RuntimeError('Dataset preparation failed; preserve original state, no automatic retry.')
   time.sleep(5)
  if not receipt:raise RuntimeError('Dataset preparation needs reconciliation; no duplicate transfer.')
  params={'datasetSha256':spec['sha256'],'seed':42,'minGenes':200,'maxGenes':2500,'minCells':3,'maxMitoPct':5,'mitoPrefix':'MT-','nTopGenes':2000,'nPCs':30,'nNeighbors':10,'maxDisplayCells':3000,'resolution':.5,'minDist':.5,'displayGenes':['CD3D','MS4A1','NKG7','LST1','S100A8'],'metadataColumns':[]}
  plan={'schemaVersion':1,'seconds':600,'stages':[{'id':'reference','operation':'scanpy_analysis','parameters':params}]}
  reference_allowance=evidence['phaseAllowances']['referenceAndTransferUSD']
  job=rpc('editcraft_prepare',plan=plan,allowanceUSD=reference_allowance);evidence['experiment']=job;save()
  if job['estimatedUSD']>reference_allowance or job['resources']!={'cpu':2,'memoryGiB':8,'gpu':False}:raise RuntimeError('Reference differs from the approved CPU/memory estimate.')
  job=rpc('editcraft_submit',id=job['id'],approvedTransfer=True,approvedCost=True);evidence['experiment']=job;save();print('submitted',job['id'],flush=True)
  deadline=time.monotonic()+680
  while time.monotonic()<deadline:
   job=rpc('editcraft_refresh',id=job['id']);evidence['experiment']=job;save()
   if job['state'] in ('completed','failed','cancelled','deadline_exceeded'):break
   time.sleep(5)
  if job['state']!='completed':raise RuntimeError('Reference did not complete. Preserve its real identity/artifacts; no automatic retry.')
  job=rpc('editcraft_result',id=job['id']);evidence['experiment']=job;result=job['result']['results']['reference']['result'];save()
  cells=result['cells'];checks={'originalPublicMatrixShape':result['inputShape']==[2700,32738],'exactSourceBytesRetained':result['source']['sha256']==spec['sha256'],'allRetainedCellsDisplayed':result['display']['allRetainedCellsDisplayed'],'retainedCellCountConsistent':len(cells)==result['filteredShape'][0]==result['qualityControl']['retainedCells'],'uniqueObservedBarcodes':len({c['barcode'] for c in cells})==len(cells),'finiteActualUMAP':all(len(c['umap'])==2 and all(math.isfinite(v) for v in c['umap']) for c in cells),'declaredQCThresholds':all(c['genesDetected']<2500 and c['mitoPercent']<5 and c['totalCounts']>0 for c in cells),'expressionMatchesCellOrder':all(len(g['values'])==len(cells) and all(math.isfinite(v) and v>=0 for v in g['values']) for g in result['expression']),'allProcessedRoundTripChecks':all(result['artifact']['roundTripChecks'].values()),'originalCellCount':2700,'actualRetainedCellCount':len(cells),'actualClusters':result['clusters'],'independentCellTypeOrPerturbationBenchmark':False}
  means=[]
  for value in result['clusterExpression']:
   gene=next(g for g in result['expression'] if g['name']==value['gene']);values=[v for c,v in zip(cells,gene['values']) if c['cluster']==value['cluster']];means.append(bool(values) and abs(sum(values)/len(values)-value['meanLogNormalizedExpression'])<1e-5)
  checks['populationMeansAgreeWithActualReturnedExpression']=all(means);evidence['referenceChecks']=checks;save()
  required=['originalPublicMatrixShape','exactSourceBytesRetained','allRetainedCellsDisplayed','retainedCellCountConsistent','uniqueObservedBarcodes','finiteActualUMAP','declaredQCThresholds','expressionMatchesCellOrder','allProcessedRoundTripChecks','populationMeansAgreeWithActualReturnedExpression']
  if not all(checks[key] for key in required):raise RuntimeError('Single-cell reference failed actual data/geometry/metadata checks.')
  # Only this disposable downloaded COPY is removed. Original source, output and
  # complete scientific evidence remain in the real research volume.
  with tempfile.TemporaryDirectory(prefix='fold-public-h5ad-transfer-') as temporary:
   exported=rpc('editcraft_artifact_export',id=job['id'],artifactSha256=result['artifact']['sha256'],path=str(pathlib.Path(temporary)/'processed.h5ad'))
   evidence['processedH5ADTransfer']={k:v for k,v in exported.items() if k!='path'};save()
   if exported['sha256']!=result['artifact']['sha256'] or exported['bytes']!=result['artifact']['bytes']:raise RuntimeError('Processed H5AD transfer differs from its original checksum.')
  evidence.update(state='reference_completed',finished=datetime.datetime.now(datetime.timezone.utc).isoformat(),nativeVerification='tracked separately',scientificReferenceChecksPassed=True);save();print(json.dumps(checks,indent=2),flush=True)
 except BaseException as exc:
  evidence.update(state='stopped_for_inspection',failureType=type(exc).__name__,failure=str(exc));save();raise
 finally:service.db.close()

def verify_saved_artifact(evidence):
 """Finish the approved worker correction/transfer; no new scientific attempt."""
 from worker import Service
 from cloud_accounts import environment
 service=Service(REPO.parent/'validation/bindcraft-fab-amme-native');identity=evidence['experiment']['id'];project=evidence['experiment']['projectId']
 for key in ('MODAL_TOKEN_ID','MODAL_TOKEN_SECRET','MODAL_CONFIG_PATH','MODAL_PROFILE'):os.environ.pop(key,None)
 os.environ.update(environment(service));os.environ['FOLD_EDITCRAFT_CHILD']='1'
 def save():PATH.write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n')
 def rpc(action,**p):return service.dispatch(action,{'projectId':project,**p})
 evidence.setdefault('artifactVerificationAttempts',[]).append({'previousFailure':evidence.get('failure'),'started':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scientificJobId':identity,'scientificCalculationRepeated':False,'authorization':'Finishes the same approved $1.25 correction scope; no additional science or data preparation.'});save()
 try:
  evidence['artifactCorrectionDeployment']=rpc('editcraft_deploy',approvedCPUDeployment=True,maxApprovedUSD=1,includeModelRuntimes=True,includeToolRuntimes=True,includeSinglecellRuntime=True);save();print('Artifact-path correction deployed; checking unchanged saved output only',flush=True)
  job=rpc('editcraft_result',id=identity);result=job['result']['results']['reference']['result']
  with tempfile.TemporaryDirectory(prefix='fold-public-h5ad-transfer-') as temporary:
   exported=rpc('editcraft_artifact_export',id=identity,artifactSha256=result['artifact']['sha256'],path=str(pathlib.Path(temporary)/'processed.h5ad'))
   if exported['sha256']!=result['artifact']['sha256'] or exported['bytes']!=result['artifact']['bytes']:raise RuntimeError('Original processed file checksum/size mismatch.')
   evidence['processedH5ADTransfer']={k:v for k,v in exported.items() if k!='path'}
  evidence.update(state='reference_completed',finished=datetime.datetime.now(datetime.timezone.utc).isoformat(),scientificReferenceChecksPassed=True,nativeVerification='tracked separately');evidence.pop('failure',None);evidence.pop('failureType',None);save();print(json.dumps(evidence['processedH5ADTransfer']),flush=True)
 except BaseException as exc:
  evidence.update(state='stopped_for_inspection',failureType=type(exc).__name__,failure=str(exc));save();raise
 finally:service.db.close()
if __name__=='__main__':main()
