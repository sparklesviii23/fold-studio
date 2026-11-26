#!/usr/bin/env python3
"""Reuse a running local build instead of competing for its macOS privacy grant.

Ad-hoc builds have hash-based signing identities. Never launch a different build
under the same bundle ID while its window or scientific children are alive.
No TCC settings, signing requirements or running calculations are modified.
"""
import argparse
import pathlib
import plistlib
import subprocess


def app_from_command(command):
    command = command.strip()
    for suffix in ('.app/Contents/Resources/', '.app/Contents/MacOS/'):
        end = command.find(suffix)
        if end >= 0 and command.startswith('/') and ' -' not in command[:end]:
            return pathlib.Path(command[:end + 4])
    return None


def bundle_id(app):
    with (app / 'Contents/Info.plist').open('rb') as stream:
        return plistlib.load(stream)['CFBundleIdentifier']


def signing_requirement(app):
    result = subprocess.run(['/usr/bin/codesign', '-d', '-r-', str(app)],
                            capture_output=True, text=True, check=True)
    lines = (result.stdout + result.stderr).splitlines()
    return next(line.split('=>', 1)[1].strip() for line in lines if 'designated =>' in line)


def choose_app(requested, commands):
    """Fail closed on multiple active identities; never stop a live process."""
    identifier = bundle_id(requested)
    active = {}
    for command in commands:
        candidate = app_from_command(command)
        if candidate is not None:
            candidate = candidate.resolve()
        if candidate is None or candidate in active:
            continue
        try:
            if bundle_id(candidate) == identifier:
                active[candidate] = signing_requirement(candidate)
        except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError):
            raise RuntimeError('Cannot verify an active app build: ' + str(candidate))
    if len(set(active.values())) > 1:
        raise RuntimeError('Multiple fold builds are active. Close their windows before reopening; keep scientific workers running.')
    if active and signing_requirement(requested) not in active.values():
        return next(iter(active)), True
    return requested, False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', type=pathlib.Path)
    parser.add_argument('--data-root', type=pathlib.Path, help='Explicit development data root; production default is Application Support.')
    args = parser.parse_args()
    requested = args.app.expanduser().resolve(strict=True)
    # argv[0] only: an app path mentioned in shell arguments is not a process.
    commands = subprocess.check_output(['/bin/ps', '-axo', 'comm='], text=True).splitlines()
    selected, deferred = choose_app(requested, commands)
    if deferred:
        print('Update deferred: reusing the build owning the current window or calculation. Close the app and finish its jobs before changing builds.', flush=True)
    print('Opening ' + str(selected), flush=True)
    command = ['/usr/bin/open', '-a', str(selected)]
    if args.data_root:
        command.extend(['--env', 'FOLD_DATA_DIR=' + str(args.data_root.expanduser().resolve(strict=True))])
    subprocess.run(command, check=True)


if __name__ == '__main__':
    main()
