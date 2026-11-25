"""Locate the workspace folder that holds runtimes/, models/ and validation/.

Order: the FOLD_WORKSPACE environment variable, then the nearest parent of this
file that contains a runtimes/ folder (works for a source checkout and for the
packaged app inside the workspace), then the parent of the repository.
Install receipts write paths as ${FOLD_WORKSPACE}/...; expand() resolves them.
"""
import os
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def root():
    configured = os.environ.get('FOLD_WORKSPACE')
    if configured:
        return pathlib.Path(configured).expanduser().resolve()
    for folder in HERE.parents:
        if (folder / 'runtimes').is_dir():
            return folder
    return HERE.parent.parent


def expand(value):
    return value.replace('${FOLD_WORKSPACE}', str(root()))
