"""Offline CUDA entry. Verify all mounted bytes before importing training code."""
import hashlib,json,os,signal,time,traceback
from pathlib import Path,PurePosixPath


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
    return h.hexdigest()


def verify_assets(root,manifest):
    seen=set()
    for item in manifest['files']:
        name=item['path'];p=PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or str(p)!=name or name in seen:raise ValueError('Unsafe or duplicate staged asset path.')
        seen.add(name);path=Path(root)/name
        if not path.is_file() or path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:raise ValueError('Staged input changed: '+name)
    return seen


def main(root,out,archive):
    out.mkdir(parents=True,exist_ok=True);start=time.monotonic()
    def event(phase,**values):
        row={'phase':phase,'seconds':time.monotonic()-start,**values};line=json.dumps(row,allow_nan=False)
        with (out/'events.jsonl').open('a') as f:f.write(line+'\n')
        print(line,flush=True)
    def expired(*_):raise TimeoutError('Fixed study time limit reached; no retry.')
    signal.signal(signal.SIGALRM,expired);signal.alarm(2670)
    try:
        manifest=json.loads((root/'ASSET_MANIFEST.json').read_text());event('verifying_staged_inputs')
        # Checkpoint bytes live once in the shared cache; every study verifies them.
        checkpoint=Path('/cache/models/qwen-cell')/manifest['checkpointRevision']
        view=root/'checkpoint'
        if view.is_symlink():
            if view.resolve()!=checkpoint:raise ValueError('Unexpected checkpoint view.')
        elif view.exists():raise ValueError('Unexpected pre-existing checkpoint view.')
        else:view.symlink_to(checkpoint,target_is_directory=True)
        verify_assets(root,manifest)
        from qwen_cell_cloud_training import run
        event('study_started',automaticRetry=False,maximumSeconds=2700)
        run(root,out,archive,event)
    except BaseException as error:
        traceback.print_exc();(out/'FAILURE.json').write_text(json.dumps({'state':'failed','reason':str(error),'automaticRetry':False}))
        event('study_failed',reason=str(error));raise
    finally:signal.alarm(0)
