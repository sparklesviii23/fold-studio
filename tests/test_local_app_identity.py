"""Local launcher must preserve workers and avoid conflicting privacy identities."""
import importlib.util
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('local_app_launcher', pathlib.Path(__file__).parents[1] / 'scripts/open-local-app.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LocalAppIdentity(unittest.TestCase):
    old = pathlib.Path('/Applications/Old Fold.app')
    new = pathlib.Path('/Applications/New Fold.app')

    def test_detects_background_worker_after_its_window_has_closed(self):
        command = str(self.old) + '/Contents/Resources/runtime/bin/python3.12 -B ' + str(self.old) + '/Contents/Resources/scientific/bindcraft_runner.py /tmp/settings.json'
        with patch.object(launcher, 'bundle_id', return_value='fold'), patch.object(launcher, 'signing_requirement', side_effect=lambda p: 'old' if p == self.old else 'new'):
            self.assertEqual(launcher.choose_app(self.new, [command]), (self.old, True))

    def test_same_seal_at_relocated_path_can_open(self):
        with patch.object(launcher, 'bundle_id', return_value='fold'), patch.object(launcher, 'signing_requirement', return_value='same'):
            self.assertEqual(launcher.choose_app(self.new, [str(self.old) + '/Contents/MacOS/fold']), (self.new, False))

    def test_no_active_build_allows_update(self):
        with patch.object(launcher, 'bundle_id', return_value='fold'):
            self.assertEqual(launcher.choose_app(self.new, []), (self.new, False))

    def test_two_already_conflicting_builds_refuse_without_killing_them(self):
        with patch.object(launcher, 'bundle_id', return_value='fold'), patch.object(launcher, 'signing_requirement', side_effect=lambda p: str(p)):
            with self.assertRaisesRegex(RuntimeError, 'Multiple fold builds'):
                launcher.choose_app(self.new, [str(p) + '/Contents/MacOS/fold' for p in (self.old, self.new)])

    def test_different_app_and_shell_arguments_are_not_mistaken_for_fold(self):
        other = pathlib.Path('/Applications/Other.app')
        with patch.object(launcher, 'bundle_id', side_effect=lambda p: 'other' if p == other else 'fold'):
            self.assertEqual(launcher.choose_app(self.new, [str(other) + '/Contents/MacOS/other', '/bin/zsh -c open ' + str(self.old)]), (self.new, False))

    @unittest.skipUnless(sys.platform == 'darwin' and shutil.which('clang'), 'macOS package sealing with CLT')
    def test_sealing_refuses_an_actual_live_child_before_mutating_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            app = pathlib.Path(directory) / 'Live Fold.app'
            executable = app / 'Contents/Resources/runtime/bin/sleep'
            executable.parent.mkdir(parents=True)
            # A fresh tiny local executable avoids copying Apple's restricted
            # platform binaries, which macOS can kill when moved out of /bin.
            subprocess.run(['clang', '-x', 'c', '-', '-o', str(executable)],
                           input='#include <unistd.h>\nint main(void) { sleep(60); return 0; }\n',
                           text=True, capture_output=True, check=True, timeout=20)
            marker = app / 'Contents/Resources/__pycache__/keep'
            marker.parent.mkdir(); marker.write_text('unchanged')
            child = subprocess.Popen([str(executable), '60'])
            try:
                result = subprocess.run(['/bin/bash', str(pathlib.Path(__file__).parents[1] / 'scripts/seal-app.sh'), str(app)], capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Cannot re-sign a running', result.stderr)
                self.assertEqual(marker.read_text(), 'unchanged')
                self.assertIsNone(child.poll())
            finally:
                child.terminate(); child.wait(timeout=5)
