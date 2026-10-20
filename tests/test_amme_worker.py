"""Real small subprocess lifecycle checks; no model computation or Fab output."""
import json
import os
import pathlib
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scientific'))
from amme_campaign import environment,SCHEDULER_FLAG,FOOTPRINT_LIMIT
from amme_worker import run_guarded,cleanup_stale,start_idle_assertion,release_idle_assertion


class AMMEWorker(unittest.TestCase):
    def test_idle_assertion_needs_a_real_positive_process_identity(self):
        for value in (None,False,0,-1,'123'):
            with self.subTest(value=value),self.assertRaises(ValueError):start_idle_assertion(value)

    def test_unavailable_power_helper_does_not_fail_the_scientific_calculation(self):
        with patch('amme_worker.subprocess.Popen',side_effect=OSError('unavailable')):
            process,report=start_idle_assertion(123)
        self.assertIsNone(process);self.assertEqual(report['state'],'unavailable')
        self.assertIsNone(release_idle_assertion(process))

    @unittest.skipUnless(sys.platform=='darwin','macOS idle assertions')
    def test_actual_idle_assertion_is_released_without_terminating_the_worker(self):
        child=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)'])
        assertion=None
        try:
            assertion,report=start_idle_assertion(child.pid)
            self.assertEqual(report['state'],'active');self.assertTrue(report['displaySleepUnchanged'])
            self.assertIsNone(assertion.poll())
            release_idle_assertion(assertion)
            self.assertIsNotNone(assertion.poll());self.assertIsNone(child.poll())
        finally:
            release_idle_assertion(assertion);child.terminate();child.wait(timeout=5)

    def test_cpu_scheduler_requires_tested_flag(self):
        value=environment({'XLA_FLAGS':'--xla_cpu_parallel_codegen_split_count=2'})
        self.assertIn(SCHEDULER_FLAG,value['XLA_FLAGS'])
        self.assertEqual(value['JAX_PLATFORMS'],'cpu')
        self.assertEqual(environment(value),value)
        with self.assertRaisesRegex(ValueError,'conflicting'):
            environment({'XLA_FLAGS':'--xla_cpu_scheduler_type=CPU_SCHEDULER_TYPE_DEFAULT'})

    def test_budget_cannot_be_raised(self):
        with self.assertRaisesRegex(ValueError,'cannot exceed'):
            run_guarded([],env={},folder='.',footprint_limit=FOOTPRINT_LIMIT+1)

    @unittest.skipUnless(sys.platform=='darwin','Requires actual macOS libproc measurements')
    def test_real_subprocess_finishes_and_private_scratch_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=pathlib.Path(directory);(folder/'neighbor').write_text('keep')
            result=run_guarded([sys.executable,'-B','-c','import time;time.sleep(.3)'],env=os.environ,folder=folder)
            self.assertEqual(result.returncode,0)
            report=json.loads((folder/'amme-memory.json').read_text())
            self.assertEqual(report['state'],'finished');self.assertTrue(report['ownedScratchRemoved'])
            self.assertEqual(report['idleSleepPrevention']['state'],'released')
            self.assertGreater(report['peakFootprintBytes'],0)
            self.assertFalse(list(folder.glob('amme-worker-*')))
            self.assertEqual((folder/'neighbor').read_text(),'keep')

    def test_interrupt_kills_actual_child_and_cleans_scratch(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=pathlib.Path(directory)
            with patch('amme_worker.process_memory',side_effect=KeyboardInterrupt('technical cancellation')):
                with self.assertRaises(KeyboardInterrupt):
                    run_guarded([sys.executable,'-B','-c','import time;time.sleep(60)'],env=os.environ,folder=folder)
            report=json.loads((folder/'amme-memory.json').read_text())
            self.assertEqual(report['state'],'interrupted');self.assertTrue(report['ownedScratchRemoved'])
            self.assertIsNotNone(report['exitCode']);self.assertFalse(list(folder.glob('amme-worker-*')))

    def test_compressed_footprint_limit_stops_actual_child_even_with_small_rss(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=pathlib.Path(directory)
            reading={'residentBytes':1024,'physicalFootprintBytes':FOOTPRINT_LIMIT+1,'processStartAbstime':123}
            with patch('amme_worker.process_memory',return_value=reading):
                with self.assertRaisesRegex(RuntimeError,'task-memory safety ceiling'):
                    run_guarded([sys.executable,'-B','-c','import time;time.sleep(60)'],env=os.environ,folder=folder)
            report=json.loads((folder/'amme-memory.json').read_text())
            self.assertEqual(report['state'],'bounded_resource_refusal');self.assertTrue(report['ownedScratchRemoved'])
            self.assertIsNotNone(report['exitCode'])

    @unittest.skipUnless(sys.platform=='darwin','Requires actual macOS process identity')
    def test_stale_tape_cleanup_keeps_a_live_orphan_and_unknown_directories(self):
        from process_memory import process_memory
        with tempfile.TemporaryDirectory() as directory:
            parent=pathlib.Path(directory);owned=parent/'amme-worker-owned';owned.mkdir()
            unknown=parent/'amme-worker-unknown';unknown.mkdir();(unknown/'keep').write_text('keep')
            child=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)'])
            try:
                owner={'ownerFormat':'fold-amme-private-v1','supervisorPid':2147483647,'supervisorIdentity':1,
                    'workerPid':child.pid,'workerIdentity':process_memory(child.pid)['processStartAbstime']}
                (owned/'owner.json').write_text(json.dumps(owner))
                self.assertEqual(cleanup_stale(parent),[]);self.assertTrue(owned.exists())
                child.terminate();child.wait(timeout=5)
                self.assertEqual(cleanup_stale(parent),[owned.name]);self.assertFalse(owned.exists())
                self.assertEqual((unknown/'keep').read_text(),'keep')
            finally:
                if child.poll() is None:child.kill();child.wait()


if __name__=='__main__':unittest.main()
