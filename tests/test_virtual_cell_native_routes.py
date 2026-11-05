"""Native admission must agree with the working scientific service, before packaging."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_check', ROOT / 'scripts/check-scientific-package.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


class NativeRouteTests(unittest.TestCase):
    def test_current_routes_match_the_registry(self):
        check.check_native_actions(ROOT)

    def test_missing_route_or_provider_route_fails_before_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'scientific').mkdir()
            (root / 'src-tauri/src').mkdir(parents=True)
            (root / 'scientific/virtual_cell_actions.py').write_text("ACTIONS = {'vcell_gene_explore'}\n")
            rust = root / 'src-tauri/src/main.rs'
            rust.write_text('const ACTIONS: &[&str] = &["vcell_get"];')
            with self.assertRaisesRegex(RuntimeError, 'differ'):
                check.check_native_actions(root)
            rust.write_text('const ACTIONS: &[&str] = &["vcell_gene_explore", "gpu_task_terminal_remote"];')
            with self.assertRaisesRegex(RuntimeError, 'Provider-only'):
                check.check_native_actions(root)


if __name__ == '__main__':
    unittest.main()
