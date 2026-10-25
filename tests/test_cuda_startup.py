"""Offline process-control fixtures; these do not qualify CUDA model inference."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'remote_worker'),str(ROOT/'tests')]
from fold_rapid import cuda_exec,hardware
from fold_rapid.store import Store
from test_rapid_worker import fixture
from test_unified_campaign import fixture as unified_fixture,SyntheticStages
from fold_rapid.unified import CampaignStore,run

class CUDAStartupTests(unittest.TestCase):
    def test_framework_is_selected_by_actual_engine_not_package_availability(self):
        self.assertEqual(hardware.framework('proteinmpnn'),'jax')
        self.assertEqual(hardware.framework('solublempnn'),'torch')
        with self.assertRaises(ValueError):hardware.framework('unknown')

    def test_probe_and_original_script_share_process_and_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=pathlib.Path(tmp)
            script=folder/'model.py';script.write_text("import os,sys,json,pathlib\npathlib.Path('observed.json').write_text(json.dumps({'pid':os.getpid(),'args':sys.argv[1:]}))")
            (folder/'cuda-entry.json').write_text(json.dumps({'engine':'solublempnn','command':[sys.executable,str(script),'seed','42']}))
            old=os.getcwd();argv=sys.argv[:];paths=sys.path[:]
            try:
                os.chdir(folder)
                with patch.object(cuda_exec,'numerical_probe',return_value={'fixture':True,'pid':os.getpid()}) as probe:cuda_exec.main(folder)
                row=json.loads((folder/'observed.json').read_text());receipt=json.loads((folder/'cuda-probe.json').read_text())
                probe.assert_called_once_with('solublempnn');self.assertEqual(row['pid'],receipt['probe']['pid']);self.assertEqual(row['args'],['seed','42']);self.assertTrue(receipt['sameProcessAsModel'])
            finally:os.chdir(old);sys.argv=argv;sys.path[:]=paths

    def test_failed_probe_never_starts_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=pathlib.Path(tmp);(folder/'cuda-entry.json').write_text(json.dumps({'engine':'solublempnn','command':['python','must-not-run.py']}))
            with patch.object(cuda_exec,'numerical_probe',side_effect=ValueError('fixture CUDA failure')),patch.object(cuda_exec,'entry',side_effect=AssertionError('model must not start')):
                with self.assertRaises(ValueError):cuda_exec.main(folder)
            self.assertFalse(json.loads((folder/'cuda-probe.json').read_text())['passed'])

    def test_cancel_terminates_blocked_cuda_import_and_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=pathlib.Path(tmp);fake=folder/'fake';fake.mkdir();jax=fake/'jax';jax.mkdir();(jax/'__init__.py').write_text('import time;time.sleep(60)');(jax/'numpy.py').write_text('')
            store=Store(folder/'rapid');m=fixture();m.update(engine='bindcraft2',operation='design');m['budget']['seconds']=30;id=store.submit(m,'cancel-startup')['jobId']
            code="""import pathlib,sys
from fold_rapid import runner,hardware
hardware.inventory=lambda:{'detected':True,'devices':[{'fixture':True}]}
import platform
platform.system=lambda:'Linux'
runner.prepare=lambda *args,**kwargs:{'command':[sys.executable,'must-not-run.py'],'environment':{'PYTHONPATH':sys.argv[3]},'models':{}}
runner.execute(pathlib.Path(sys.argv[1]),sys.argv[2])
"""
            process=subprocess.Popen([sys.executable,'-c',code,str(store.root),id,str(fake)],env={**os.environ,'PYTHONPATH':str(ROOT/'remote_worker')},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                until=time.monotonic()+8
                while time.monotonic()<until and store.get(id)['state']!='running':time.sleep(.03)
                self.assertEqual(store.get(id)['state'],'running');child=next(e['childPid'] for e in store.events(id) if e['kind']=='started')
                store.cancel(id);self.assertEqual(process.wait(timeout=12),0);self.assertEqual(store.get(id)['state'],'cancelled')
                with self.assertRaises(ProcessLookupError):os.kill(child,0)
                self.assertTrue((store.folder(id)/'results.zip').is_file());self.assertFalse(json.loads((store.folder(id)/'provenance.json').read_text())['cudaNumericalProbePassed'])
            finally:
                if process.poll() is None:process.kill();process.wait()

    def test_one_failed_model_stops_further_paid_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=CampaignStore(tmp);id=store.submit(unified_fixture(),'failed-fixture',True)['campaignId']
            class Failed(SyntheticStages):
                def __call__(self,stage,m,checkpoint,cancelled):
                    self.calls.append(m['engine'])
                    return {'folder':tmp,'job':{'state':'failed','error':'fixture runtime failure'}}
            executor=Failed(pathlib.Path(tmp),store,id);result=run(tmp,id,executor)
            self.assertEqual(len(executor.calls),1);self.assertEqual(result['state'],'PARTIALLY_COMPLETE');self.assertIn('remaining paid stages',result['events'][-1]['message'])

if __name__=='__main__':unittest.main()
