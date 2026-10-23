"""Validation CPU must not be mistaken for an unrelated scientific calculation."""
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from local_worker.core import resources
from local_worker.executor import command


class ValidationAdmissionTests(unittest.TestCase):
    def test_owned_test_cpu_is_excluded_but_external_and_owned_science_are_not(self):
        responses = [subprocess.CompletedProcess([], 0, '1'),
                     subprocess.CompletedProcess([], 0, 'Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 1000000.\n'),
                     subprocess.CompletedProcess([], 0,
                       '100 1 100 0 worker\n'
                       '101 100 120000 99 /Users/test/FoldStudio-MetalPort/runtimes/python -m unittest\n'
                       '102 101 120000 99 /Users/test/FoldStudio-MetalPort/amme_worker.py\n'
                       '200 1 120000 99 /Users/test/FoldStudio-MetalPort/scientific/other.py\n')]
        with tempfile.TemporaryDirectory() as folder, patch('local_worker.core.os.getpid', return_value=100), patch('local_worker.core.run', side_effect=responses):
            snapshot = resources(pathlib.Path(folder)/'repo')
        self.assertEqual({v['pid'] for v in snapshot['scientificWorkloads']}, {102, 200})

    def test_typecheck_targets_the_real_repository_configuration(self):
        from local_worker.core import REPO
        args = command('typecheck', REPO)
        self.assertTrue((REPO/args[-1]).is_file())

    def test_readonly_checks_can_read_resolved_shared_dependencies_without_writing_them(self):
        from local_worker.core import REPO
        from local_worker.executor import sandbox
        with tempfile.TemporaryDirectory() as folder:
            policy=sandbox(REPO,pathlib.Path(folder))
        self.assertIn(str((REPO/'node_modules').resolve()),policy)
        self.assertNotIn('(allow file-write* (subpath "'+str((REPO/'node_modules').resolve()),policy)
        args=command('frontend-tests',REPO)
        self.assertIn('--no-cache',args)
        self.assertIn('--pool=threads',args)
        self.assertEqual(args[args.index('--configLoader')+1],'runner')


if __name__ == '__main__': unittest.main()
