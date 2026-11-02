#!/usr/bin/env python3
"""Release licence check: fail if the repository tracks third-party weights, datasets or their cached outputs.

    python3 scripts/check-release-licenses.py            # checks `git ls-files` in the fold-studio repository
    python3 scripts/check-release-licenses.py FILE...    # checks the given paths (used by tests)

The virtual cell fetches every outside model and dataset into the user's library after the user has seen its licence
(scientific/virtual_cell_plugins.py). None of them, and nothing computed from restricted ones (embeddings, cached
predictions), may enter the repository. Reviewed exceptions go in scripts/release-allowlist.txt as
`<glob>  # reason`.
"""
import fnmatch
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
WEIGHTS = ('.safetensors', '.ckpt', '.pt', '.pth', '.bin', '.gguf', '.onnx', '.msgpack')
DATA = ('.h5ad', '.loom', '.mtx', '.parquet', '.arrow', '.h5mu')
LIBRARY_DIRS = ('virtualcell/data/', 'virtualcell/plugins/', 'virtualcell/reference/', 'virtualcell/cache/')
MAX_BYTES = 50 * 1024 * 1024


def allowlist():
    f = REPO / 'scripts' / 'release-allowlist.txt'
    if not f.is_file():
        return []
    return [line.split('#', 1)[0].strip() for line in f.read_text().splitlines() if line.split('#', 1)[0].strip()]


def problems(paths, base=REPO):
    allowed = allowlist()
    out = []
    for p in paths:
        if any(fnmatch.fnmatch(p, g) for g in allowed):
            continue
        low = p.lower()
        if low.endswith(WEIGHTS):
            out.append((p, 'model weights'))
        elif low.endswith(DATA):
            out.append((p, 'single-cell or tabular dataset'))
        elif any(d in low for d in LIBRARY_DIRS):
            out.append((p, 'virtual cell library content (data, plugin or cached output)'))
        else:
            f = base / p
            if f.is_file() and f.stat().st_size > MAX_BYTES:
                out.append((p, f'larger than {MAX_BYTES // 2**20} MB'))
    return out


def main(argv):
    if argv:
        paths, base = argv, pathlib.Path.cwd()
    else:
        paths = subprocess.run(['git', 'ls-files'], cwd=REPO, capture_output=True, text=True, check=True).stdout.splitlines()
        base = REPO
    found = problems(paths, base)
    for p, why in found:
        print(f'BLOCKED  {p}  ({why})')
    print(f'{len(paths)} files checked, {len(found)} blocked.')
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
