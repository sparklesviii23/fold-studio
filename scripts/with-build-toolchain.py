#!/usr/bin/env python3
"""Use the existing qualified build toolchain. Do not install dependencies."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    receipt = repository / 'reports/qwen-rna/BUILD_COMMAND.json'
    if not receipt.is_file():
        raise SystemExit('Cargo is missing from PATH. Select the existing Rust toolchain before building.')
    recorded = json.loads(receipt.read_text())['environment']
    environment = dict(os.environ)
    for key in ('CARGO_HOME', 'RUSTUP_HOME', 'PATH'):
        if not isinstance(recorded.get(key), str) or not recorded[key]:
            raise SystemExit('The recorded build environment is incomplete: ' + key)
        environment[key] = recorded[key]
    for key in ('CARGO_HOME', 'RUSTUP_HOME'):
        if not Path(environment[key]).is_dir():
            raise SystemExit('The recorded toolchain is missing: ' + environment[key])
    for name in ('cargo', 'rustc', 'node', 'python3'):
        executable = shutil.which(name, path=environment['PATH'])
        if executable is None:
            raise SystemExit('The recorded build environment cannot find ' + name)
        if args.check:
            subprocess.run([executable, '--version'], env=environment, check=True)
    print('Using the existing recorded build toolchain. Process and signature guards remain enabled.', flush=True)
    if not args.check:
        raise SystemExit(subprocess.run(['/bin/bash', str(repository / 'scripts/build-local-app.sh')],
                                       cwd=repository, env=environment).returncode)


if __name__ == '__main__':
    main()
