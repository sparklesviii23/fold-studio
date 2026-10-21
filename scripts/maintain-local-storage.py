"""Remove only owned build staging and share identical immutable AF2 weights."""
import errno
import hashlib
import os
import pathlib
import shutil
import subprocess
import uuid

ROOT=pathlib.Path(__file__).resolve().parents[2]


def sha(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(4*1024**2):value.update(block)
    return value.digest()


def clean():
    processes=subprocess.check_output(['/bin/ps','-axo','comm='],text=True).splitlines()
    for path in (ROOT/'build-cache/current',ROOT/'runtime-build'):
        if not path.exists():continue
        if path.is_symlink():raise ValueError('Build staging must not be a symlink: '+str(path))
        if any(line.strip().startswith(str(path)+'/') for line in processes):raise RuntimeError('A process still owns build staging: '+str(path))
        # Finder can recreate .DS_Store while an observed directory is removed.
        # First detach its visible pathname; never follow arbitrary cleanup paths.
        discard=ROOT/('.discard-build-'+uuid.uuid4().hex)
        path.rename(discard)
        for attempt in range(3):
            try:shutil.rmtree(discard);break
            except OSError as error:
                if error.errno!=errno.ENOTEMPTY or attempt==2:raise
    app=ROOT/'current/FOLD STUDIO Metal Dev.app/Contents/Resources/models/alphafold'
    for reference in (ROOT/'models/alphafold').glob('params_*.npz'):
        bundled=app/reference.name
        if reference.is_symlink() or bundled.is_symlink() or not bundled.is_file():continue
        if reference.stat().st_ino==bundled.stat().st_ino:continue
        if reference.stat().st_size!=bundled.stat().st_size or sha(reference)!=sha(bundled):continue
        pending=reference.with_name(reference.name+'.share-'+uuid.uuid4().hex)
        try:os.link(bundled,pending);os.replace(pending,reference)
        finally:pending.unlink(missing_ok=True)


if __name__=='__main__':clean()
