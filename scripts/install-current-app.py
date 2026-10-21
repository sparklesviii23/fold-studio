#!/usr/bin/env python3
"""Replace one local app safely; keep no historical release bundles."""
import argparse
import fcntl
import pathlib
import plistlib
import shutil
import subprocess
import tempfile
import sys


def identifier(app):
    with (app / 'Contents/Info.plist').open('rb') as stream:
        return plistlib.load(stream)['CFBundleIdentifier']


def require_idle(destination, bundle_id):
    commands = subprocess.check_output(['/bin/ps', '-axo', 'comm='], text=True)
    for line in commands.splitlines():
        executable = line.strip()
        if '.app/Contents/' not in executable or not executable.startswith('/'):
            continue
        app = pathlib.Path(executable.split('.app/Contents/', 1)[0] + '.app')
        if app.resolve() == destination or (app.is_dir() and identifier(app) == bundle_id):
            raise RuntimeError('Close the current app and finish its workers before updating it. No running app or job was stopped.')


def verify(app):
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)


def install(source, destination):
    source = source.resolve(strict=True)
    bundle_id = identifier(source)
    if destination.exists() and identifier(destination) != bundle_id:
        raise ValueError('Destination belongs to another application.')
    if source == destination:
        raise ValueError('The build input must be separate from the installed app.')
    require_idle(destination, bundle_id)
    verify(source)
    with tempfile.TemporaryDirectory(prefix='.app-update-', dir=destination.parent) as directory:
        staging = pathlib.Path(directory) / destination.name
        # APFS clones avoid a second physical copy of unchanged models during activation.
        subprocess.run(['/bin/cp', '-cR', '-P', str(source), str(staging)], check=True)
        verify(staging)
        require_idle(destination, bundle_id)
        previous = pathlib.Path(directory) / 'previous.app'
        if destination.exists():
            destination.rename(previous)
        try:
            staging.rename(destination)
            verify(destination)
        except BaseException:
            if destination.exists():
                shutil.rmtree(destination)
            if previous.exists():
                previous.rename(destination)
            raise
        # TemporaryDirectory removes the prior bundle after successful verification.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=pathlib.Path)
    parser.add_argument('--destination', required=True, type=pathlib.Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    destination = args.destination.expanduser().resolve()
    if args.check_only:
        require_idle(destination, identifier(destination))
        return
    if not args.source:
        parser.error('--source is required for installation')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with (destination.parent / '.current-app.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        install(args.source.expanduser(), destination)
    print('Updated current app: ' + str(destination))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
