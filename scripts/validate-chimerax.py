#!/usr/bin/env python3
"""Live integration acceptance against separately installed ChimeraX.

Run only with a new, disposable --root and a --report output path. Launches its
own headless session, uses real coordinates, verifies auth and native results,
then terminates only the exact PID created by this script.
"""
import argparse,json,os,pathlib,signal,sys,time,urllib.error,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scientific'))
from worker import Service
from observatory import Observatory
parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--report',required=True);args=parser.parse_args()
folder=pathlib.Path(args.root).resolve()
if (folder/'library.sqlite3').exists():raise SystemExit('Choose a NEW disposable test library. Existing data is never used.')
service=Service(folder,ROOT/'fixtures');bridge=Observatory(service);project=service.library({})['projects'][0]['id'];pid=None;checks=[]
def check(name,condition,details=None):
    checks.append({'name':name,'passed':bool(condition),'details':details})
    if not condition:raise AssertionError(name)
def execute(command):
    result=bridge.chimerax_execute({'projectId':project,'command':command,'confirmed':True})
    return result
try:
    launched=bridge.chimerax_start({'headless':True});pid=launched['pid'];start=time.monotonic()
    for _ in range(60):
        status=bridge.chimerax_status({})
        if status['connected']:break
        time.sleep(1)
    check('Genuine installed interpreter connected',status['connected'],{'version':status.get('version'),'startupSeconds':round(time.monotonic()-start,2)})
    catalog=bridge.chimerax_catalog({});check('Live command discovery',catalog['count']>100 and catalog['completeMetadata'],{'count':catalog['count'],'fingerprint':catalog['fingerprint']})
    for headers,name in [({},'Unauthenticated command request rejected'),({'Authorization':'Bearer '+bridge.connection()['token'],'Origin':'https://example.org'},'Browser-origin command request rejected')]:
        code=None
        try:urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:'+str(bridge.connection()['port'])+'/run?command=version',headers=headers),timeout=5)
        except urllib.error.HTTPError as error:code=error.code
        check(name,code==403)
    item=next(r for r in service.library({})['records'] if r['kind']=='structure')
    opened=bridge.chimerax_open({'projectId':project,'structureId':item['id']});check('Exact source checksum and model mapping',opened['state']=='completed' and bool(opened['mapping']),{'mapping':opened['mapping']})
    model=opened['mapping'][0]['modelId'];spec='#'+model+'/A:'
    for command in ['version','select '+spec+'20@CA','color sel orange','style sel stick','info atoms '+spec+'20']:
        result=execute(command);check('Native: '+command,result['state']=='completed',{'latencyMs':result.get('latencyMs'),'output':result.get('output')})
    result=execute('distance '+spec+'20@CA '+spec+'21@CA');value=result['output']['python values'][0];check('Real Cα distance',result['state']=='completed' and abs(value-3.7908803727)<1e-5,{'valueAngstrom':value})
    result=execute('foldCommandThatDoesNotExist');check('Native unknown-command error preserved',result['state']=='failed' and result['output']['error']['type']=='UserError',result['output']['error'])
    result=execute('build start peptide "FOLD validation peptide" ACDE -57,-47');check('Installed build bundle command executes',result['state']=='completed')
    before=service.library({})['records'];native=bridge.chimerax_import({'projectId':project,'modelId':model,'structureId':item['id']});check('Native mmCIF transfer creates a separate asset',native['id']!=item['id'] and len(service.library({})['records'])==len(before)+1,{'newStructureId':native['id'],'sha256':native['data']['sha256']})
    selected=bridge.chimerax_select({'projectId':project,'structureId':item['id'],'atoms':[{'authChain':'A','auth':20,'insertion':'','atomName':'CA','altLoc':'','element':'C','xyz':[15.138,51.394,-75.132]}]});check('Local identity sends native selection',selected['state']=='completed' and selected['snapshot']['models'][0]['selected'][0]['atom']=='CA')
    result=execute('move x 1 models #'+model);check('Changed native coordinates invalidate mapping fingerprint',result['snapshot']['models'][0]['positionsSha256']!=opened['mapping'][0]['positionsSha256'])
    try:bridge.chimerax_select({'projectId':project,'structureId':item['id'],'atoms':[{'authChain':'A','auth':20,'insertion':'','atomName':'CA','altLoc':'','element':'C','xyz':[15.138,51.394,-75.132]}]});refused=False
    except ValueError:refused=True
    check('Synchronization refuses changed coordinates',refused)
    # Known transformed/perturbed test coordinates, clearly labeled as QA input.
    # Actual Matchmaker results must recover the rigid transform and identify the
    # deliberately displaced Cα. These are algorithm tests, not biological data.
    reopened=bridge.chimerax_open({'projectId':project,'structureId':item['id']});source_model=reopened['mapping'][0]['modelId']
    atoms=bridge.request('/fold/atoms?model='+source_model)['atoms'];last_ca=next(a for a in reversed(atoms) if a['atom']=='CA')
    lines=[]
    for i,a in enumerate(atoms,1):
        x,y,z=a['xyz'];x,y,z=-y+7,x-3,z+2
        if a is last_ca:x+=5
        lines.append(f"ATOM  {i:5d} {a['atom']:>4s} {a['residueName']:>3s} {a['chain']:1s}{a['residue']:4d}{a['insertion']:1s}   {x:8.3f}{y:8.3f}{z:8.3f}{1:6.2f}{0:6.2f}          {a['element']:>2s}")
    path=folder/'known-perturbed-validation.pdb';path.write_text('\n'.join(lines)+'\nEND\n')
    perturbed=service.import_structure({'projectId':project,'path':str(path),'name':'QA known transform + 5 Å Cα perturbation','source':'Artificial test perturbation of genuine source coordinates; algorithm validation only'})
    originals={r['id']:r['data']['sha256'] for r in (item,perturbed)}
    fit=bridge.comparison_run({'projectId':project,'structureId':perturbed['id'],'referenceId':item['id'],'movingChain':'A','referenceChain':'A','cutoff':None})
    full=fit['fits'][0]
    check('Measured all-pair Cα superposition executes',full['alignedPairs']==460 and full['fitPairs']==460 and full['fullRmsd']>0.1,{'rmsdAngstrom':full['fullRmsd'],'pairs':full['alignedPairs'],'command':fit['command']})
    import math
    recomputed=math.sqrt(sum(pair['distanceAngstrom']**2 for pair in full['pairs'])/len(full['pairs']))
    check('Native all-pair RMSD agrees with returned residuals',abs(recomputed-full['fullRmsd'])<1e-4,{'native':full['fullRmsd'],'recomputed':recomputed})
    fit=bridge.comparison_run({'projectId':project,'structureId':perturbed['id'],'referenceId':item['id'],'movingChain':'A','referenceChain':'A','cutoff':2})
    core=fit['fits'][0]
    check('Pruning separates fit and all-aligned RMSD',core['fitPairs']==459 and core['fitRmsd']<0.001 and core['fullRmsd']>0.1,{'fitRmsd':core['fitRmsd'],'fullRmsd':core['fullRmsd'],'fitPairs':core['fitPairs']})
    check('Outlier residue correspondence is explicit',sum(not p['usedInFit'] for p in core['pairs'])==1 and core['pairs'][-1]['moving']['residue']==last_ca['residue'],{'lastPair':core['pairs'][-1]})
    entries=bridge.observatory_library({'projectId':project})
    check('Measured comparisons persist with both source fingerprints',any(e['id']==fit['analysisId'] and e['data']['sourceStructures'][0]['sha256']==perturbed['data']['sha256'] for e in entries))
    import hashlib
    check('Superposition preserves both saved coordinate assets',all(hashlib.sha256((folder/'assets'/r['data']['asset']).read_bytes()).hexdigest()==originals[r['id']] for r in (item,perturbed)))
    aligned=bridge.chimerax_import({'projectId':project,'structureId':perturbed['id'],'modelId':fit['movingModelId'],'comparisonId':fit['analysisId']})
    check('Aligned export retains measured comparison provenance',aligned['data']['metadata']['comparisonId']==fit['analysisId'] and aligned['data']['metadata']['comparison']['sourceStructures'][1]['sha256']==item['data']['sha256'])
    execute('move x 1 models #'+fit['movingModelId'])
    try:bridge.chimerax_import({'projectId':project,'modelId':fit['movingModelId'],'comparisonId':fit['analysisId']});refused=False
    except ValueError:refused=True
    check('Aligned import refuses stale native fit coordinates',refused)
finally:
    if pid:
        # PID belongs to this exact Popen call, never an arbitrary installation.
        try:os.kill(pid,signal.SIGTERM)
        except ProcessLookupError:pass
    report={'date':time.strftime('%Y-%m-%d'),'checks':checks,'passed':all(c['passed'] for c in checks)}
    pathlib.Path(args.report).parent.mkdir(parents=True,exist_ok=True);pathlib.Path(args.report).write_text(json.dumps(report,indent=2))
    service.db.close()
print(json.dumps({'checks':len(checks),'passed':report['passed'],'report':args.report}))
