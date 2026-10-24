"""Bounded real dual-MPNN campaign test; unavailable predictors remain blocked.
Uses approved existing checkpoints only. Never edits the user's live database.
"""
import base64,copy,json,os,pathlib,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'remote_worker'),str(ROOT/'scientific')]
from fold_rapid.unified import CampaignStore,run,atomic
from fold_rapid.contracts import digest,file_digest,canonical
from fold_rapid.adapters import collect
from fold_rapid.molecules import inspect
from process_memory import process_memory,exceeds_footprint_budget


def main():
    original=json.loads((ROOT/'reports/bgmee-authentic-mpnn.json').read_text())['result']['settings']
    source=pathlib.Path(original['input']);raw=source.read_bytes()
    if digest(raw)!=original['sha256']:raise ValueError('Original research coordinates changed.')
    root=ROOT.parent/'validation/unified-cpu-controller';store=CampaignStore(root)
    engines=['proteinmpnn','solublempnn','esmfold2_fast','af2_multimer']
    value={'schemaVersion':1,'kind':'unified','strategy':'evolution','target':{'format':'cif','contentBase64':base64.b64encode(raw).decode(),'sha256':digest(raw),'chains':['A','B','C']},'parents':[{'id':'original-ANGPTL3-8-peptide','binderChains':['D'],'sequences':original['sequences']}],'generators':[],'workflow':{'redesign':['proteinmpnn','solublempnn'],'predictors':['esmfold2_fast','af2_multimer'],'rosetta':False,'count':1},'stageBudgets':{e:{'seconds':60,'hourlyEstimateUSD':1} for e in engines},'budget':{'seconds':600,'maxEstimatedUSD':1},'seed':42,'constraints':{'D':{'mutable':[2,3],'excluded':{'2':'C','3':'W'},'preferred':{'2':'A'}}},'policy':{'maxDescendants':16}}
    submitted=store.submit(value,'real-dual-mpnn-original-v2',True);id=submitted['campaignId'];cfg=json.loads((ROOT.parent/'validation/bgmee-native-controller/engine/biology-config.json').read_text())
    class CPUStages:
        def preflight(self,engine,value):return {'ready':engine in ('proteinmpnn','solublempnn'),'reason':'This bounded test authorizes existing CPU MPNNs only; no GPU/ESM execution or synthetic predictor substitute.'}
        def __call__(self,stage,value,checkpoint,cancelled):
            engine=value['engine'];folder=store.folder(id)/'stages'/stage['stageId']/'jobs'/stage['stageId'];folder.mkdir(parents=True,exist_ok=True);(folder/'output').mkdir(exist_ok=True)
            atomic(folder/'manifest.json',value);(folder/'target.cif').write_bytes(raw);atomic(folder/'target-mapping.json',inspect(raw,'cif'));checkpoint({'jobId':stage['stageId']})
            if engine=='proteinmpnn':
                request=copy.deepcopy(original)
                # Same observed coordinates, masks, seed and exclusions as the
                # portable handoff; native runner verifies fixed atom equality.
                for ch,rows in request['constraints']['residues'].items():
                    mask=value['biology']['constraints'].get(ch,{'mutable':[]})
                    for i,row in enumerate(rows,1):
                        row['design']=i in mask['mutable']
                        for key in ('excluded','preferred'):
                            row.pop(key,None)
                            if str(i) in mask.get(key,{}):row[key]=mask[key][str(i)]
                atomic(folder/'native-request.json',request)
                command=[str(ROOT.parent/'runtimes/jax-cpu/bin/python'),'-B',str(ROOT/'scientific/mpnn_runner.py'),str(folder/'native-request.json'),str(folder/'native-result.json')]
            else:
                checkpoint_model=cfg['models']['solublempnn']
                if file_digest(pathlib.Path(checkpoint_model['path']))!=checkpoint_model['sha256']:raise ValueError('Approved SolubleMPNN checksum changed.')
                atomic(folder/'biology-runtime.json',{'runtime':cfg['runtimes']['solublempnn'],'models':{'solublempnn':checkpoint_model}})
                command=[cfg['runtimes']['solublempnn']['python'],'-B','-m','fold_rapid.biology_tasks',engine,str(folder)]
            env={**os.environ,'PYTHONPATH':str(ROOT/'remote_worker'),'BGMEE_DEVICE':'cpu','JAX_PLATFORMS':'cpu','OMP_NUM_THREADS':'2','PYTHONDONTWRITEBYTECODE':'1','HF_HUB_OFFLINE':'1'};started=time.monotonic();peak=0
            with (folder/'execution.log').open('wb') as log:
                child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=env)
                try:
                    while child.poll() is None:
                        if cancelled() or time.monotonic()-started>60:raise ValueError('Bounded CPU task cancelled/timed out.')
                        try:
                            memory=process_memory(child.pid);peak=max(peak,memory['physicalFootprintBytes'],memory['residentBytes'])
                            if exceeds_footprint_budget(memory,14*1024**3):raise ValueError('Protected CPU memory limit exceeded.')
                        except ProcessLookupError:pass
                        time.sleep(.2)
                    if child.returncode:raise ValueError('Authentic model failed; inspect retained execution.log.')
                except BaseException:
                    child.terminate();child.wait(timeout=10);raise
            if engine=='proteinmpnn':
                result=json.loads((folder/'native-result.json').read_text());atomic(folder/'output/mpnn.json',{'candidates':result['candidates']})
                for i,row in enumerate(result['candidates']):(folder/'output'/f'sequence-{i}.fasta').write_text('>chain=D\n'+row['chains']['D']+'\n')
            provenance={'jobId':stage['stageId'],'manifestSha256':digest(canonical(value).encode()),'computeProvider':'local_cpu_validation','device':'cpu','scientificCUDAQualified':False,'wallSeconds':time.monotonic()-started,'peakObservedFootprintBytes':peak,'sourceBackboneSha256':digest(raw)}
            records=collect(folder,value,provenance);atomic(folder/'provenance.json',provenance)
            from fold_rapid.store import Store
            # Real transport evidence in the same isolated stage store.
            stage_store=Store(folder.parents[1]);submission=stage_store.submit(value,stage['stageId']);actual=stage_store.folder(submission['jobId'])
            # Keep the canonical stage job ID for native import readback.
            for path in folder.iterdir():
                if path.name not in ('supervisor.log',):
                    import shutil
                    if path.is_dir():shutil.copytree(path,actual/path.name,dirs_exist_ok=True)
                    else:shutil.copy2(path,actual/path.name)
            from fold_rapid.runner import package
            package(actual);stage_store.finish(submission['jobId'],'completed',result={'candidates':len(records),'device':'cpu'})
            checkpoint({'jobId':submission['jobId']})
            return {'folder':str(actual),'job':stage_store.get(submission['jobId'])}
    result=run(root,id,CPUStages());candidates=store.candidates(id)
    report={'test':'Actual portable unified controller with genuine CPU MPNNs; predictor stages deliberately blocked, no fabricated predictions','campaignId':id,'state':result['state'],'root':str(root),'originalCoordinateSha256':digest(raw),'originalPreserved':file_digest(source)==digest(raw),'originalSequence':original['sequences']['D'],'descendants':[{'id':c['candidateId'],'engine':c['generator'],'sequence':c['sequences']['D'],'parents':c['parents'],'hasFreshCoordinates':bool(c['coordinates'])} for c in candidates if c['operation']=='REDESIGN'],'stages':result['stages'],'qualifiedCandidates':result['qualifiedCandidates'],'paidCompute':False,'modelDownloads':False,'fabRestarted':False,'scientificCloudQualified':False}
    atomic(ROOT/'reports/unified-authentic-cpu.json',report);print(canonical(report))
    if len(report['descendants'])!=2:raise ValueError('Dual-MPNN controller validation is incomplete; retain the failure report.')


if __name__=='__main__':main()
