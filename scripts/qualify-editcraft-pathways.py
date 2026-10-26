#!/usr/bin/env python3
"""One fresh approved source-only deployment and bounded numerical CPU reference.

No biological collection, GPU, model weights, private uploads or automatic retry.
"""
import argparse,datetime,json,math,os,pathlib,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'remote_worker')]
REPORT=ROOT/'reports/editcraft/pathway-cloud-reference.json'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--approved-total-usd',type=float,required=True);args=parser.parse_args()
    if args.approved_total_usd!=1.25 or REPORT.exists():raise SystemExit('Requires fresh $1.25 approval and no existing attempt. Reconnect to saved work; never repeat automatically.')
    from worker import Service
    from cloud_accounts import environment
    service=Service(ROOT.parent/'validation/bindcraft-fab-amme-native')
    project='a8def624-3640-49e8-89cc-7012f1e8d924'
    for key in ('MODAL_TOKEN_ID','MODAL_TOKEN_SECRET','MODAL_CONFIG_PATH','MODAL_PROFILE'):os.environ.pop(key,None)
    os.environ.update(environment(service));os.environ['FOLD_EDITCRAFT_CHILD']='1'
    evidence={'state':'started','started':datetime.datetime.now(datetime.timezone.utc).isoformat(),'maximumApprovedUSD':1.25,'phaseAllowances':{'sourceUpdateAndHealthUSD':1,'singleNumericalReferenceUSD':.25},'scope':'One source-only EditCraft update, retaining existing runtimes/assets; one 2-CPU/4-GiB/300-second mathematical reference with BH and BY stages. Synthetic finite population only. No biological claims, private upload, GPU, model/download assets or automatic retries.','providerReportedUSD':None,'biologicalBenchmarkComplete':False,'fullEditCraftComplete':False}
    def save():
        pending=REPORT.with_suffix('.pending');pending.write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n');pending.replace(REPORT)
    def rpc(action,**payload):return service.dispatch(action,{'projectId':project,**payload})
    save()
    try:
        evidence['deployment']=rpc('editcraft_deploy',approvedCPUDeployment=True,maxApprovedUSD=1,includeModelRuntimes=True,includeToolRuntimes=True,includeSinglecellRuntime=True);save()
        reference=json.loads((ROOT/'fixtures/editcraft/pathways/finite-null-reference.json').read_text())
        plan={'schemaVersion':1,'seconds':300,'stages':[{'id':method.lower(),'operation':'pathway_enrichment','parameters':{**reference['parameters'],'multipleTesting':method}} for method in ('BH','BY')]}
        job=rpc('editcraft_prepare',plan=plan,allowanceUSD=.25);evidence['experiment']=job;save()
        if job['estimatedUSD']>.25 or job['resources']!={'cpu':2,'memoryGiB':4,'gpu':False}:raise RuntimeError('Reviewed reference exceeds its approved workload.')
        evidence['experiment']=rpc('editcraft_submit',id=job['id'],approvedTransfer=True,approvedCost=True);save();print('Submitted one mathematical reference',job['id'],flush=True)
        deadline=time.monotonic()+380
        while time.monotonic()<deadline:
            job=rpc('editcraft_refresh',id=job['id']);evidence['experiment']=job;save()
            if job['state'] in ('completed','failed','cancelled','deadline_exceeded'):break
            time.sleep(5)
        if job['state']!='completed':raise RuntimeError('Reference stopped or needs reconciliation. No automatic retry.')
        job=rpc('editcraft_result',id=job['id']);evidence['experiment']=job;checks={}
        for method in ('BH','BY'):
            result=job['result']['results'][method.lower()]['result'];row=next(r for r in result['rows'] if r['id']=='selected');outside=next(r for r in result['rows'] if r['id']=='outside')
            checks[method]={'rawExactFiniteNull':math.isclose(row['pValue'],reference['expected']['selectedRawP'],rel_tol=1e-12),'adjustedExactFiniteNull':math.isclose(row['adjustedPValue'],reference['expected']['selected'+method+'AdjustedP'],rel_tol=1e-12),'entireSuppliedFamilyRetained':result['testedFamilySize']==3 and len(result['rows'])==3,'exactOverlapIdentities':row['overlapGenes']==['g1','g2','g3'],'outsideBackgroundExplicit':outside['outsideBackground']==['other'] and outside['noTestableMembers'] and outside['foldEnrichment'] is None,'noUnadjustedImplicitMethod':result['multipleTesting']==method}
        evidence['referenceChecks']=checks
        if not all(flag for group in checks.values() for flag in group.values()):raise RuntimeError('Real cloud reference disagrees with the independent finite null.')
        evidence.update(state='reference_completed',finished=datetime.datetime.now(datetime.timezone.utc).isoformat(),numericalCloudReferencePassed=True);save();print(json.dumps(checks,indent=2),flush=True)
    except BaseException as exc:
        evidence.update(state='stopped_for_inspection',failureType=type(exc).__name__,failure=str(exc));save();raise
    finally:service.db.close()

if __name__=='__main__':main()
