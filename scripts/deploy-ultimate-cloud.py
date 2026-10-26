#!/usr/bin/env python3
"""One explicitly approved source deployment and CPU inventory check only."""
import argparse,datetime,json,os,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scientific'),str(ROOT/'remote_worker')]
REPORT=ROOT/'reports/ultimate/cloud-deployment.json'

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--approved-total-usd',type=float,required=True);args=parser.parse_args()
 if args.approved_total_usd!=1 or REPORT.exists():raise SystemExit('Fresh $1 approval and no previous attempt required. Reconcile saved state; never redeploy automatically.')
 from worker import Service
 from cloud_accounts import environment
 from fold_rapid.contracts import canonical,digest
 service=Service(ROOT.parent/'validation/bindcraft-fab-amme-native')
 for key in ('MODAL_TOKEN_ID','MODAL_TOKEN_SECRET','MODAL_CONFIG_PATH','MODAL_PROFILE'):os.environ.pop(key,None)
 os.environ.update(environment(service));os.environ['FOLD_PROVIDER_CHILD']='1'
 project='a8def624-3640-49e8-89cc-7012f1e8d924'
 evidence={'state':'started','started':datetime.datetime.now(datetime.timezone.utc).isoformat(),'maximumApprovedUSD':1,'scope':'One guarded source-only Modal deployment and one CPU inventory check. No GPU, scientific job, private research upload, model download or automatic retry.','providerReportedUSD':None,'fullFabScientificallyQualified':False}
 def save():
  pending=REPORT.with_suffix('.pending');pending.write_text(json.dumps(evidence,indent=2,allow_nan=False)+'\n');pending.replace(REPORT)
 save()
 try:
  evidence['deployment']=service.dispatch('biology_modal_deploy',{'projectId':project,'approvedDeployment':True});save()
  evidence['health']=evidence['deployment'].get('health') or service.dispatch('biology_modal_check',{'projectId':project,'approvedControlCost':True});save()
  source=ROOT/'remote_worker'
  expected=digest(canonical({str(p.relative_to(source)):digest(p.read_bytes()) for p in sorted((source/'fold_rapid').glob('*.py'))}).encode())
  health=evidence['health'];bindcraft=next(e for e in health['models']['engines'] if e['id']=='bindcraft2')
  evidence['checks']={'remoteController':health.get('controllerLocation')=='remote','linux':health.get('executionPlatform','').startswith('Linux'),'sourceCodeMatches':health.get('sourceCodeSha256')==expected,'fabContractPresent':'Fab' in bindcraft['modalities'],'fabQualificationTruthful':bindcraft.get('fullFabScientificQualification') is False}
  if not all(evidence['checks'].values()):raise ValueError('CPU deployment checks differ; no scientific calculation started.')
  evidence['state']='cpu_deployment_verified'
 except BaseException as error:
  evidence.update(state='failed_no_automatic_retry',error=str(error));raise
 finally:
  evidence['finished']=datetime.datetime.now(datetime.timezone.utc).isoformat();save();service.db.close()

if __name__=='__main__':main()
