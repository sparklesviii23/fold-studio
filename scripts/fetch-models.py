"""Download the pinned model files in scientific/model-assets.json.

Each file is fetched from its publisher at the pinned revision, written to a
.partial file, checked against its SHA-256 and size, then moved into place.
Files that already exist with the right hash are skipped. Interrupted
downloads resume from the .partial file.

Usage: python3 scripts/fetch-models.py [--workspace DIR] [--only REPO_SUBSTRING] [--dry-run]
"""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys
import tarfile
import urllib.request

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scientific'))
import workspace  # noqa: E402


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 24), b''):
            digest.update(block)
    return digest.hexdigest()


def fetch(url, dest, size, expected):
    partial = dest.with_name(dest.name + '.partial')
    have = partial.stat().st_size if partial.exists() else 0
    if have > size:
        partial.unlink()
        have = 0
    if have < size:
        request = urllib.request.Request(url, headers={'Range': f'bytes={have}-'} if have else {})
        with urllib.request.urlopen(request, timeout=120) as response, open(partial, 'ab' if have else 'wb') as target:
            if have and response.status != 206:
                raise RuntimeError('Server ignored the resume request: ' + url)
            done = have
            for block in iter(lambda: response.read(1 << 22), b''):
                target.write(block)
                done += len(block)
                print(f'\r  {done / 1e9:6.2f} / {size / 1e9:.2f} GB', end='', flush=True)
        print()
    if partial.stat().st_size != size or sha256(partial) != expected:
        partial.unlink()
        raise RuntimeError('Checksum mismatch, download removed: ' + dest.name)
    partial.replace(dest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', help='workspace folder (default: FOLD_WORKSPACE or the repository parent)')
    parser.add_argument('--only', help='fetch only repositories whose name contains this text')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if args.workspace:
        os.environ['FOLD_WORKSPACE'] = args.workspace
    root = workspace.root()
    assets = json.loads((REPO / 'scientific' / 'model-assets.json').read_text())
    total = 0
    for name, model in assets['models'].items():
        if args.only and args.only not in name:
            continue
        print(f'{name}  [{model["license"]}]')
        for entry in model['files']:
            dest = root / entry['dest']
            if 'present' in entry and (root / entry['present']).is_dir():
                print('  ok      ' + entry['present'])
                continue
            if dest.exists() and dest.stat().st_size == entry['bytes'] and sha256(dest) == entry['sha256']:
                print('  ok      ' + entry['dest'])
                continue
            url = f'{model["repository"]}/resolve/{entry["revision"]}/{entry["file"]}'
            total += entry['bytes']
            print(f'  fetch   {entry["dest"]}  ({entry["bytes"] / 1e9:.2f} GB)')
            if args.dry_run:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(dest.parent).free < entry['bytes'] + 3 * 1024 ** 3:
                raise SystemExit('Not enough disk space (need the file size plus 3 GiB).')
            fetch(url, dest, entry['bytes'], entry['sha256'])
            if 'extractTo' in entry:
                with tarfile.open(dest) as archive:
                    archive.extractall(root / entry['extractTo'], filter='data')
                dest.unlink()
    print(f'{"Would download" if args.dry_run else "Downloaded"} {total / 1e9:.2f} GB into {root}')


if __name__ == '__main__':
    main()
