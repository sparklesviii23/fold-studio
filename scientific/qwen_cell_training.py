"""Bounded, offline direct-Qwen development pilot. Never downloads or promotes."""
import json
from pathlib import Path
import signal
import time
import numpy as np
from qwen_cell_data import verify_bundle,sha,write


def validate_checkpoint(folder,metadata):
    folder=Path(folder)
    if metadata.get('model')!='Qwen/Qwen2.5-Coder-3B-Instruct' or metadata.get('revision')!='488639f1ff808d1d3d0ba301aef8c11461451ec5':
        raise ValueError('The first pilot requires the explicitly pinned 3B checkpoint.')
    allowed={'config.json','model.safetensors.index.json','model-00001-of-00002.safetensors','model-00002-of-00002.safetensors'}
    if {r['rfilename'] for r in metadata['files']}!=allowed:raise ValueError('Unexpected checkpoint artifact list.')
    checks=[]
    for row in metadata['files']:
        p=folder/row['rfilename']
        if not p.is_file() or p.stat().st_size!=row['size']:raise ValueError('Compatible checkpoint not available: '+row['rfilename'])
        digest=sha(p)
        if row.get('lfs') and digest!=row['lfs']['sha256']:raise ValueError('Checkpoint integrity failed: '+row['rfilename'])
        checks.append({'path':p.name,'sha256':digest,'bytes':p.stat().st_size})
    config=json.loads((folder/'config.json').read_text())
    if config.get('model_type')!='qwen2' or config.get('hidden_size')!=2048:raise ValueError('Unexpected Qwen model architecture.')
    return checks


def run(checkpoint,data,out,metadata,steps=30,max_seconds=900,device='mps',teacher_weight=0.):
    if not 1<=steps<=30 or not 1<=max_seconds<=900:raise ValueError('Pilot limit: at most 30 steps and 900 seconds.')
    if not 0<=teacher_weight<=.5:raise ValueError('Invalid teacher weight.')
    out=Path(out)
    if out.exists():raise ValueError('Existing run evidence is preserved; choose a new output folder.')
    if device not in ('mps','cpu'):raise ValueError('The first pilot is local CPU or Apple GPU only.')
    manifest=verify_bundle(data);metadata=json.loads(Path(metadata).read_text());out.mkdir(parents=True)
    started=time.monotonic();events=(out/'events.jsonl').open('w')
    def event(phase,**values):
        row={'phase':phase,'seconds':time.monotonic()-started,**values};events.write(json.dumps(row,allow_nan=False)+'\n');events.flush();print(json.dumps(row),flush=True)
    def deadline(*_):raise TimeoutError('The 15-minute local pilot limit was reached; no automatic retry.')
    previous=signal.signal(signal.SIGALRM,deadline)
    def stopped(*_):raise KeyboardInterrupt('Local Qwen training stopped.')
    previous_term=signal.signal(signal.SIGTERM,stopped);signal.alarm(max_seconds)
    try:
        checks=validate_checkpoint(checkpoint,metadata);event('checkpoint_verified',model=metadata['model'],revision=metadata['revision'])
        import torch
        from transformers import Qwen2Model
        from safetensors.torch import save_file
        from qwen_cell_model import QwenCellPredictor,objective,masked_mse,trainable_state,load_trainable_state
        torch.manual_seed(20261106);torch.set_num_threads(2)
        if device=='mps' and not torch.backends.mps.is_available():raise ValueError('Apple GPU is unavailable; no fallback or retry started.')
        with np.load(Path(data)/'data.npz',allow_pickle=False) as archive:arrays={k:archive[k] for k in archive.files}
        dtype=torch.float16 if device=='mps' else torch.float32
        # local_files_only + trust_remote_code=False: no remote code, model fetch or fallback.
        base=Qwen2Model.from_pretrained(str(checkpoint),local_files_only=True,trust_remote_code=False,
                                       use_safetensors=True,dtype=dtype,attn_implementation='eager').to(device)
        model=QwenCellPredictor(base,arrays['trainX'].shape[1],arrays['decoder'],arrays['targetCenter'],arrays['targetScale'],rank=8,layers=2).to(device)
        report=model.parameter_report();event('model_ready',**report)
        versions={n:p._version for n,p in model.named_parameters() if not p.requires_grad}
        initial=trainable_state(model);initial={n:v.clone() for n,v in initial.items()}
        optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=1e-4,weight_decay=.01)
        tensor=lambda x:torch.as_tensor(x,device=device,dtype=torch.float32)
        tx,ty,tm,teacher=[tensor(arrays[k]) for k in ['trainX','trainY','trainMask','trainTeacher']]
        vx,vy,vm=[tensor(arrays[k]) for k in ['validationX','validationY','validationMask']]
        def validate():
            model.eval();rows=[]
            with torch.no_grad():
                for i in range(len(vx)):rows.append(float(masked_mse(model(vx[i:i+1]),vy[i:i+1],vm[i:i+1]).cpu()))
            return float(np.mean(rows))
        best_score=validate();initial_score=best_score;best={n:v.clone() for n,v in trainable_state(model).items()};best_step=0
        save_file(best,str(out/'adapters.safetensors'));event('validation',step=0,developmentMse=best_score)
        order=np.random.default_rng(20261106).permutation(len(tx));completed=0
        for step in range(1,steps+1):
            i=int(order[(step-1)%len(order)]);model.train();optimizer.zero_grad(set_to_none=True)
            pred=model(tx[i:i+1]);loss=objective(pred,ty[i:i+1],tm[i:i+1],teacher[i:i+1],teacher_weight)
            if not bool(torch.isfinite(loss)):raise ValueError('Nonfinite training loss; no retry.')
            loss.backward();grad=torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.,error_if_nonfinite=True)
            optimizer.step();completed=step;event('training',step=step,objective=float(loss.detach().cpu()),gradientNorm=float(grad.cpu()))
            if step%10==0 or step==steps:
                score=validate();event('validation',step=step,developmentMse=score)
                if score<best_score:
                    best_score=score;best_step=step;best={n:v.clone() for n,v in trainable_state(model).items()};save_file(best,str(out/'adapters.safetensors'))
        last=trainable_state(model);changed=[n for n in last if not torch.equal(initial[n],last[n])]
        frozen_unchanged=all(p._version==versions[n] for n,p in model.named_parameters() if not p.requires_grad)
        if not frozen_unchanged or not any('.lora_' in n for n in changed):raise ValueError('Weight-update verification failed.')
        # Preserve final-step weights as well as the validation-selected checkpoint.
        save_file(last,str(out/'final-step-adapters.safetensors'));load_trainable_state(model,best);model.eval()
        with torch.no_grad():prediction=np.concatenate([model(vx[i:i+1]).cpu().numpy() for i in range(len(vx))])
        np.savez_compressed(out/'development-predictions.npz',conditions=arrays['validationConditions'],prediction=prediction,genes=arrays['genes'])
        baseline={}
        for name,value in {'unchanged':np.zeros_like(arrays['validationY']),
                           'training_pair_mean':np.broadcast_to(arrays['targetCenter'],arrays['validationY'].shape),
                           'additive':arrays['validationAdditive'],'scaled_additive':arrays['validationScaledAdditive']}.items():
            baseline[name]=float(masked_mse(tensor(value.copy()),vy,vm).cpu())
        receipt={'schema':'fold.qwen-cell.pilot/1','state':'done','model':metadata['model'],'revision':metadata['revision'],
                 'checkpointFiles':checks,'dataSha256':manifest['dataSha256'],'parameters':report,'completedSteps':completed,
                 'initialDevelopmentMse':initial_score,'selectedDevelopmentMse':best_score,'selectedStep':best_step,
                 'baselinesDevelopmentMse':baseline,'updatedParameterNames':changed,'qwenAdapterWeightsUpdated':True,
                 'originalQwenWeightVersionsUnchanged':frozen_unchanged,'selectedCheckpointUpdatesQwenAdapters':best_step>0,
                 'teacherWeight':teacher_weight,'legacyTestOutcomesAggregated':False,'independentTestEvaluated':False,
                 'scientificStatus':'Development pilot only. No independent accuracy or whole-cell capability established.',
                 'cloudJobs':0,'automaticRetry':False,'seconds':time.monotonic()-started,'device':device,
                 'software':{'torch':torch.__version__,'transformers':__import__('transformers').__version__},
                 'trainingCodeSha256':sha(__file__),'modelCodeSha256':sha(Path(__file__).with_name('qwen_cell_model.py')),
                 'files':{p.name:sha(p) for p in out.iterdir() if p.suffix in ('.safetensors','.npz')}}
        write(out/'receipt.json',receipt);return receipt
    except BaseException as error:
        write(out/'failure.json',{'state':'stopped' if isinstance(error,KeyboardInterrupt) else 'failed','reason':str(error),
                                  'seconds':time.monotonic()-started,'automaticRetry':False,'promoted':False})
        raise
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,previous);signal.signal(signal.SIGTERM,previous_term);events.close()
