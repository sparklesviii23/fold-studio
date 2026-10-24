"""Standalone cloud image recipe. No macOS bundle or local model binaries.

Image definition is offline; deploying it builds on Modal only after explicit
approval. Scientific environments/checkpoints install remotely into the model
Volume, each using the existing hashed Linux dependency lock and source pin.
"""
import io
import json
import pathlib
import shutil
import tarfile
from .contracts import digest,canonical,file_digest

RECIPE='rapid-cuda13-core-v1'
BASE='nvidia/cuda:13.0.2-runtime-ubuntu24.04@sha256:6a0e31b59e70890446f2c17356d6efc0d54260090a8c63d6ca7c2ad049db95d2'


def verify_release(root):
    root=pathlib.Path(root);receipt=json.loads((root/'release.json').read_text())
    if receipt.get('modelWeightsIncluded') or receipt.get('privateResearchIncluded'):raise ValueError('Cloud deployment source must exclude research data and local weights.')
    for name,expected in receipt['files'].items():
        path=root/name
        if path.is_symlink() or root.resolve() not in path.resolve().parents or not path.is_file() or file_digest(path)!=expected:raise ValueError('Cloud source integrity mismatch: '+name)
    for name in ('bindcraft2','boltzgen'):
        if not (root/'sources'/name/'rapid-source.json').is_file():raise ValueError('Pinned scientific source is missing: '+name)
    if not (root/'worker/native_analysis/biology_assessment.py').is_file():raise ValueError('Standalone cloud assessments are missing.')
    return receipt


def prepare_release(destination,raw):
    """A single source-only cache, never a copied app or checkpoint directory."""
    destination=pathlib.Path(destination)
    if len(raw)>8*1024**2:raise ValueError('Cloud source archive exceeds its reviewed limit.')
    staging=destination.with_name(destination.name+'.pending')
    if staging.exists():shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
            members=archive.getmembers()
            if sum(m.size for m in members)>32*1024**2:raise ValueError('Cloud source expands beyond its bounded size.')
            for member in members:
                path=pathlib.PurePosixPath(member.name)
                if not path.parts or path.parts[0]!='release' or path.is_absolute() or '..' in path.parts or member.issym() or member.islnk() or not (member.isdir() or member.isfile()):raise ValueError('Invalid cloud source member.')
            archive.extractall(staging,filter='data')
        verify_release(staging/'release')
        if destination.exists():shutil.rmtree(destination)
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging,ignore_errors=True);raise
    return destination/'release'


def definition(release):
    import modal
    release=pathlib.Path(release);receipt=verify_release(release)
    recipe_sha=digest(canonical({'recipe':RECIPE,'base':BASE,'coreLock':file_digest(release/'worker/environments/core.lock'),'sourceManifest':file_digest(release/'release.json')}).encode())
    image=(modal.Image.from_registry(BASE,add_python='3.12')
      .apt_install('ca-certificates','python3-venv')
      .add_local_dir(release,'/opt/fold-rapid-release',copy=True)
      .run_commands('python -m pip install --no-cache-dir --require-hashes -r /opt/fold-rapid-release/worker/environments/core.lock')
      .env({'PYTHONPATH':'/opt/fold-rapid-release/worker','RAPID_RELEASE_DIR':'/opt/fold-rapid-release','RAPID_IMAGE_RECIPE':RECIPE,'RAPID_IMAGE_RECIPE_SHA256':recipe_sha,'FOLD_ENGINE_ROLE':'cloud'}))
    return image,{'name':'Fold Studio RAPID Cloud Engine','recipe':RECIPE,'recipeSha256':recipe_sha,'baseImageDigest':BASE,'sourceCommit':receipt['sourceCommit'],'sourceManifestSha256':file_digest(release/'release.json'),'scientificEnvironments':'Remote isolated hashed Linux CUDA runtimes; no Mac binaries','checkpoints':'Separate persistent remote model volume; explicit downloads only','scientificQualified':False}
