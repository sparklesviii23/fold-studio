"""One bounded local prototype attempt, exposed in the existing read-only run controller."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
import uuid

REPO=Path(__file__).resolve().parents[1];sys.path.insert(0,str(REPO/'scientific'))
import gpu_tasks as G


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path);p.add_argument('--child');a=p.parse_args()
    library=a.library.resolve();out=a.output_dir.resolve();service=SimpleNamespace(root=library)
    source=library/'oncology/perturbseq/norman2019/NormanWeissman2019_filtered.h5ad'
    if not a.child:
        if not (out/'SPLIT_MANIFEST.json').is_file():p.error('Freeze the split before starting training.')
        claim=out/'LOCAL_ATTEMPT.json'
        if claim.exists():raise ValueError('One local attempt is already recorded. No automatic retry.')
        rec={'id':uuid.uuid4().hex,'provider':'local','recipe':'predictive_k562_pair_prototype','state':'local_running','gpu':None,
             'title':'K-562 · genetic RNA-response prototype','projectId':'fef08806-d3ac-4846-8143-60a76b8c1e63',
             'created':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'timeout':900,'phase':'Local count checks and small-model training; no cloud allocation'}
        with claim.open('x') as f:json.dump({'jobId':rec['id'],'maximumSeconds':900,'automaticRetry':False},f,indent=2)
        G._write(service,rec);folder=G._folder(service)/rec['id']
        with (folder/'stdout.txt').open('w') as log:
            child=subprocess.Popen([sys.executable,'-B',__file__,'--library',str(library),'--output-dir',str(out),'--child',rec['id']],
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True,cwd=REPO,
                env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',MPLCONFIGDIR=str(out.parent.parent.parent/'work/stage3/matplotlib')))
        print(json.dumps({'jobId':rec['id'],'pid':child.pid,'log':str(folder/'stdout.txt')}));return
    rec=G._read(service,a.child);rec['launched']=time.time();G._write(service,rec);folder=G._folder(service)/a.child;code=0
    def expired(*_):raise TimeoutError('The one local attempt reached its 15-minute limit.')
    signal.signal(signal.SIGALRM,expired);signal.alarm(900)
    try:
        import k562_prototype as K
        print('[fold] local-only prototype; raw source is read-only; one sealed test evaluation',flush=True)
        plan=json.loads((out/'SPLIT_MANIFEST.json').read_text());K.verify_plan(plan,source);meta=K.metadata(source)
        selected,audit=K.select_genes(source,meta,plan,out)
        K.train(source,out,plan,meta,selected)
        report=K.evaluate(source,out,plan,meta,selected)
        K.render_report(out,report,audit)
        shutil.copy2(REPO/'scripts/predict-k562-prototype.py',out/'predict.py')
        spec=importlib.util.spec_from_file_location('portable_k562',out/'predict.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        labels,genes,values=module.predict(out/'MODEL.npz',report['testConditions'])
        import numpy as np
        with np.load(out/'SEALED_TEST_PREDICTIONS.npz',allow_pickle=False) as z:
            np.testing.assert_array_equal(genes,z['genes']);np.testing.assert_allclose(values,z['residual_mlp'],rtol=1e-10,atol=1e-12)
        K.write(out/'MODEL_CARD.json',{'schema':K.SCHEMA,'context':plan['context'],'intervention':'simultaneous two-gene CRISPR activation',
            'requires':'Measured single-activation RNA responses in the pinned screen','outputs':'Mean RNA-response difference from loading-group-matched controls',
            'status':'research prototype; not automatically promoted','wholeCellStateModel':False,'timeDynamicsSupported':False,
            'sourceSha256':plan['source']['sha256'],'modelSha256':K.digest(out/'MODEL.npz'),'portableStandaloneReproductionPassed':True,
            'implementationCommit':subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip()})
        result=folder/'outputs';result.mkdir(exist_ok=True)
        for path in out.iterdir():
            if path.is_file() and path.name!='LOCAL_ATTEMPT.json':shutil.copy2(path,result/path.name)
        rec['outputs']=[{'path':p.name,'bytes':p.stat().st_size,'sha256':K.digest(p)} for p in result.iterdir() if p.is_file()]
        print('[fold] standalone weights reproduce sealed predictions; result files returned to the controller',flush=True)
    except Exception as error:
        import traceback;traceback.print_exc();code=1;rec['error']=str(error)
    finally:
        signal.alarm(0)
        rec.update(state='done' if code==0 else 'failed',phase='Local prototype completed' if code==0 else 'Local prototype failed',returncode=code,finished=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
        G._write(service,rec)
        print('[fold] local prototype '+rec['state'],flush=True)


if __name__=='__main__':main()
