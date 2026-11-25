"""Every scientific action the interface calls must be admitted by the native host (src-tauri/src/main.rs ACTIONS).

A missing name is refused in the installed app with "Unsupported scientific action" although the worker supports it;
the development preview bypasses the native host and cannot show the problem.
"""
import pathlib, re, sys, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scientific'))
import cell_em_actions, cell_physics_actions, light_pulse_actions, virtual_cell_actions

DEV_ONLY = {'preview_export', 'preview_confidence_export'}


def native():
    text = (ROOT / 'src-tauri' / 'src' / 'main.rs').read_text()
    return set(re.findall(r'"([a-z0-9_]+)"', re.search(r'const ACTIONS: &\[&str\] = &\[(.*?)\];', text, re.S).group(1)))


class NativeAllowlistTests(unittest.TestCase):
    def test_cell_and_virtual_cell_actions_are_admitted(self):
        allowed = native()
        for actions in (virtual_cell_actions.ACTIONS, cell_em_actions.ACTIONS, cell_physics_actions.ACTIONS, light_pulse_actions.ACTIONS):
            self.assertEqual(sorted(a for a in actions if a not in allowed), [])

    def test_every_action_named_in_the_interface_is_admitted(self):
        allowed = native() | DEV_ONLY
        called = set()
        for f in (ROOT / 'src').rglob('*.ts*'):
            called |= set(re.findall(r"(?:rpc|call)(?:<[^>(]*>)?\(\s*(?:'[^']*',\s*)?'([a-z][a-z0-9]*_[a-z0-9_]+)'", f.read_text()))
        self.assertEqual(sorted(called - allowed), [])


if __name__ == '__main__':
    unittest.main()
